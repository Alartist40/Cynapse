//! JSONL chat-session persistence.
//!
//! Faithful port of Go `internal/session/manager.go`: append-only
//! JSONL transcripts, atomic compact/replace via temp-file + rename.

use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, MutexGuard};

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

use crate::llm::{Attachment, Message, Role, ToolCall};

/// One persisted transcript line.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Entry {
    pub role: Role,
    pub content: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_call_id: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub tool_calls: Vec<ToolCall>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub images: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub attachments: Vec<Attachment>,
    pub ts: i64,
}

impl Entry {
    fn to_message(&self) -> Message {
        Message {
            role: self.role,
            content: self.content.clone(),
            tool_call_id: self.tool_call_id.clone(),
            tool_calls: self.tool_calls.clone(),
            images: self.images.clone(),
            attachments: self.attachments.clone(),
        }
    }
}

/// One user's chat history, persisted as JSONL.
pub struct Session {
    pub key: String,
    entries: Mutex<Vec<Entry>>,
    file_path: PathBuf,
    file_mode: u32,
}

fn lock_entries(m: &Mutex<Vec<Entry>>) -> MutexGuard<'_, Vec<Entry>> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

impl Session {
    fn load(path: &Path) -> Result<Session> {
        let mut entries = Vec::new();
        match fs::read_to_string(path) {
            Ok(text) => {
                for line in text.lines() {
                    if let Ok(e) = serde_json::from_str::<Entry>(line) {
                        entries.push(e);
                    }
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e).context("reading session"),
        }
        Ok(Session {
            key: String::new(),
            entries: Mutex::new(entries),
            file_path: path.to_path_buf(),
            file_mode: 0o644,
        })
    }

    /// Append an entry: records it in memory and appends a JSON line.
    pub fn append(&self, mut e: Entry) -> Result<()> {
        e.ts = now();
        {
            let mut entries = lock_entries(&self.entries);
            entries.push(e.clone());
        }

        let mode = if self.file_mode != 0 {
            self.file_mode
        } else {
            0o644
        };
        let mut f = open_append(&self.file_path, mode).context("opening session file")?;
        let data = serde_json::to_vec(&e)?;
        f.write_all(&data)?;
        f.write_all(b"\n")?;
        f.sync_all()?;
        Ok(())
    }

    /// Last n messages as LLM messages (for the context window).
    pub fn recent(&self, n: usize) -> Vec<Message> {
        let entries = lock_entries(&self.entries);
        let start = entries.len().saturating_sub(n);
        entries[start..].iter().map(Entry::to_message).collect()
    }

    /// Snapshot copy of the full transcript.
    pub fn entries(&self) -> Vec<Entry> {
        lock_entries(&self.entries).clone()
    }

    /// Atomically swap the in-memory transcript and persist it
    /// (temp-file + rename), surviving crashes.
    pub fn replace(&self, entries: Vec<Entry>) -> Result<()> {
        {
            let mut cur = lock_entries(&self.entries);
            *cur = entries.clone();
        }
        write_jsonl_atomic(&self.file_path, ".replace", &entries)
    }

    pub fn len(&self) -> usize {
        lock_entries(&self.entries).len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Rewrite the file atomically keeping only the last `keep` entries.
    pub fn compact(&self, keep: usize) -> Result<()> {
        let mut entries = lock_entries(&self.entries);
        if entries.len() <= keep {
            return Ok(());
        }
        let keep_from = entries.len() - keep;
        entries.drain(..keep_from);
        let snapshot = entries.clone();
        drop(entries);
        write_jsonl_atomic(&self.file_path, ".compacting", &snapshot)
    }
}

/// Write entries to a temp file then atomically rename over the target.
fn write_jsonl_atomic(path: &Path, suffix: &str, entries: &[Entry]) -> Result<()> {
    let tmp = path.with_extension(format!(
        "{}.{}",
        path.extension().and_then(|e| e.to_str()).unwrap_or("jsonl"),
        &suffix[1..]
    ));

    let mut f = File::create(&tmp).context("creating temp file")?;
    for e in entries {
        let data = serde_json::to_vec(e)?;
        f.write_all(&data)?;
        f.write_all(b"\n")?;
    }
    f.sync_all()?;
    drop(f);
    fs::rename(&tmp, path).context("renaming temp file")?;
    Ok(())
}

/// Open a file for append/create, applying `mode` on creation.
fn open_append(path: &Path, mode: u32) -> std::io::Result<File> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        OpenOptions::new()
            .append(true)
            .create(true)
            .write(true)
            .mode(mode)
            .open(path)
    }
    #[cfg(not(unix))]
    {
        OpenOptions::new().append(true).create(true).write(true).open(path)
    }
}

/// Owns the on-disk sessions dir and lazily loads session records.
pub struct Manager {
    base_path: PathBuf,
    mode: u32,
    sessions: Mutex<std::collections::HashMap<String, Arc<Session>>>,
}

impl Manager {
    /// Create a Manager storing transcripts under `base_path` with the
    /// given file mode (0 → 0644).
    pub fn new_with_mode(base_path: impl Into<PathBuf>, mode: u32) -> Result<Manager> {
        let base_path = base_path.into();
        let mode = if mode == 0 { 0o644 } else { mode };
        fs::create_dir_all(&base_path).context("creating sessions dir")?;
        Ok(Manager {
            base_path,
            mode,
            sessions: Mutex::new(std::collections::HashMap::new()),
        })
    }

    pub fn get(&self, key: &str) -> Result<Arc<Session>> {
        {
            let map = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
            if let Some(s) = map.get(key) {
                return Ok(s.clone());
            }
        }

        let path = self.base_path.join(format!("{}.jsonl", sanitize_key(key)));
        let mut session = Session::load(&path).context("loading session")?;
        session.key = key.to_string();
        session.file_mode = self.mode;

        let arc = Arc::new(session);
        let mut map = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
        map.entry(key.to_string()).or_insert_with(|| arc.clone());
        Ok(arc)
    }

    pub fn list(&self) -> Result<Vec<String>> {
        let mut keys = Vec::new();
        for entry in fs::read_dir(&self.base_path)? {
            let entry = entry?;
            let name = entry.file_name().to_string_lossy().to_string();
            if let Some(stem) = name.strip_suffix(".jsonl") {
                keys.push(stem.to_string());
            }
        }
        keys.sort();
        Ok(keys)
    }
}

fn sanitize_key(k: &str) -> String {
    k.chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                c
            } else {
                '_'
            }
        })
        .collect()
}

fn now() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_dir(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("cynapse-sess-{tag}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn entry(role: Role, content: &str) -> Entry {
        Entry {
            role,
            content: content.to_string(),
            tool_call_id: None,
            tool_calls: Vec::new(),
            images: Vec::new(),
            attachments: Vec::new(),
            ts: 0,
        }
    }

    #[test]
    fn append_and_reload_roundtrip() {
        let dir = temp_dir("rt");
        let m = Manager::new_with_mode(dir.clone(), 0o644).unwrap();
        let s = m.get("test-session").unwrap();
        s.append(entry(Role::User, "hello")).unwrap();
        s.append(entry(Role::Assistant, "hi there")).unwrap();

        // Reload from disk via a fresh manager.
        let m2 = Manager::new_with_mode(dir.clone(), 0o644).unwrap();
        let s2 = m2.get("test-session").unwrap();
        assert_eq!(s2.len(), 2);
        let recent = s2.recent(1);
        assert_eq!(recent.len(), 1);
        assert_eq!(recent[0].content, "hi there");
        assert_eq!(recent[0].role, Role::Assistant);
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn compact_keeps_last_n() {
        let dir = temp_dir("compact");
        let m = Manager::new_with_mode(dir.clone(), 0o644).unwrap();
        let s = m.get("c").unwrap();
        for i in 0..10 {
            s.append(entry(Role::User, &format!("msg {i}"))).unwrap();
        }
        s.compact(4).unwrap();
        assert_eq!(s.len(), 4);
        let recent = s.recent(10);
        assert_eq!(recent[0].content, "msg 6");
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn replace_atomic() {
        let dir = temp_dir("replace");
        let m = Manager::new_with_mode(dir.clone(), 0o644).unwrap();
        let s = m.get("r").unwrap();
        s.append(entry(Role::User, "old")).unwrap();
        let fresh = vec![entry(Role::User, "a"), entry(Role::User, "b")];
        s.replace(fresh).unwrap();
        assert_eq!(s.len(), 2);
        let m2 = Manager::new_with_mode(dir.clone(), 0o644).unwrap();
        assert_eq!(m2.get("r").unwrap().len(), 2);
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn sanitize_key_replaces_illegal_chars() {
        assert_eq!(sanitize_key("my session/01!"), "my_session_01_");
        assert_eq!(sanitize_key("plain-ok_123"), "plain-ok_123");
    }
}
