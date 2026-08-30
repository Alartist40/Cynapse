//! Persona — the markdown-defined identity plus the DENDRITE graph
//! it is synced to.
//!
//! Faithful port of Go `internal/memory/memory.go`: file lifecycle
//! (read/write/atomic-write with `.bak`), daily logs, fact saving
//! with dedup, and graph-backed system-prompt compilation.

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use anyhow::{Context, Result};

use crate::compressor::PersonaSink;
use crate::dendrite::{Dendrite, DendriteContext, DendriteStore, NodeType};

/// Map of persona filename → graph node metadata.
const NODE_MAP: [(&str, &str, &str, NodeType); 7] = [
    ("IDENTITY.md", "identity", "Identity", NodeType::Identity),
    ("SOUL.md", "soul", "Soul", NodeType::Identity),
    ("AGENTS.md", "agents", "Agent Rules", NodeType::Concept),
    ("USER.md", "user", "User Profile", NodeType::Person),
    ("TOOLS.md", "tools", "Tools", NodeType::Concept),
    ("MEMORY.md", "memory_notes", "Memory", NodeType::Memory),
    ("HEARTBEAT.md", "heartbeat", "Heartbeat", NodeType::Concept),
];

const SEED_FILES: [(&str, &str, &str, NodeType); 7] = NODE_MAP;

pub struct Persona {
    device_id: String,
    base_path: PathBuf,
    defaults_path: PathBuf,
    graph: Arc<Dendrite>,
    store: Arc<DendriteStore>,
    _context: Arc<DendriteContext>,
    mu: Mutex<()>,
}

impl Persona {
    pub fn new(
        device_id: &str,
        base_path: &Path,
        defaults_path: &Path,
        db_path: &Path,
    ) -> Result<Persona> {
        let dir = base_path.join(device_id);
        fs::create_dir_all(&dir).context("creating persona dir")?;
        fs::create_dir_all(dir.join("logs").join("daily")).ok();
        fs::create_dir_all(dir.join("logs").join("heartbeat")).ok();
        fs::create_dir_all(dir.join("skills")).ok();

        if let Some(parent) = db_path.parent() {
            fs::create_dir_all(parent).ok();
        }

        let graph = Arc::new(Dendrite::new());
        let store = Arc::new(DendriteStore::open(db_path).context("graph store")?);

        if let Err(e) = store.load_all(&graph) {
            eprintln!("WARNING: could not load graph nodes: {e}");
        }

        let context = DendriteContext::new(graph.clone(), Some(store.clone()));

        let p = Persona {
            device_id: device_id.to_string(),
            base_path: dir,
            defaults_path: defaults_path.to_path_buf(),
            graph,
            store,
            _context: context,
            mu: Mutex::new(()),
        };

        // If the graph is empty, seed it from the default markdown files.
        if p.graph.is_empty() {
            p.seed_from_markdown_files();
        }

        Ok(p)
    }

    /// Convert the old flat `.md` files into initial graph nodes.
    /// Runs once on first boot, then never again (graph is persisted).
    fn seed_from_markdown_files(&self) {
        let mut seeded = 0;
        for (file, id, title, node_type) in SEED_FILES {
            let path = self.defaults_path.join(file);
            let data = match fs::read_to_string(&path) {
                Ok(d) => d,
                Err(_) => {
                    format!("# {}\nDefault {} for Cynapse AI agent.\n", title, title)
                }
            };
            self.graph.upsert(id, title, &data, node_type, None);
            seeded += 1;
        }

        // Second pass: save all nodes so auto-wired backlinks persist.
        for n in self.graph.all() {
            if let Err(e) = self.store.save(&n) {
                eprintln!("WARNING: could not save seeded node {}: {e}", n.id);
            }
        }

        eprintln!("[PERSONA] seeded {seeded} nodes from markdown defaults");
    }

    pub fn graph(&self) -> Arc<Dendrite> {
        self.graph.clone()
    }

    pub fn store(&self) -> Arc<DendriteStore> {
        self.store.clone()
    }

    pub fn device_id(&self) -> &str {
        &self.device_id
    }

    /// System prompt for CYNAPSE agent — warm, natural, direct, and conversational.
    pub fn compile_system_prompt(&self, user_message: &str) -> String {
        self.compile_system_prompt_with_focus(user_message, false)
    }

    pub fn compile_system_prompt_with_focus(&self, _user_message: &str, focus: bool) -> String {
        // Use the model's native system prompt (from its profile) as the base.
        // Only append CYNAPSE-specific context when tools/memory are relevant.
        // This keeps token count low and avoids confusing the model with a
        // completely different persona than it was trained on.
        String::new()
    }

    pub fn read_file(&self, name: &str) -> Result<String> {
        let _guard = self.mu.lock().unwrap_or_else(|e| e.into_inner());
        fs::read_to_string(self.base_path.join(name)).context("reading persona file")
    }

    /// Write a file and sync it to the graph if it's a core node.
    pub fn write_file(&self, name: &str, content: &str) -> Result<()> {
        let _guard = self.mu.lock().unwrap_or_else(|e| e.into_inner());

        if let Some((id, title, node_type)) = node_meta(name) {
            let node = self.graph.upsert(id, title, content, node_type, None);
            if let Err(e) = self.store.save(&node) {
                eprintln!("WARNING: could not sync {name} to graph: {e}");
            }
        }

        fs::write(self.base_path.join(name), content).context("writing persona file")
    }

    /// Write to a temp file then atomically rename over the target,
    /// preserving the original as `.bak` on success. Prevents data
    /// loss from a crash or bad LLM output mid-write.
    pub fn atomic_write(&self, name: &str, content: &str) -> Result<()> {
        let _guard = self.mu.lock().unwrap_or_else(|e| e.into_inner());

        let base_path = self.base_path.join(name);
        let tmp_path = PathBuf::from(format!("{}.tmp", base_path.display()));
        let backup_path = PathBuf::from(format!("{}.bak", base_path.display()));

        // Always remove the stale temp file on exit.
        let remove_tmp = || {
            let _ = fs::remove_file(&tmp_path);
        };

        fs::write(&tmp_path, content).context("write temp file")?;
        // Rename existing file to .bak (ignore error if it doesn't exist).
        let _ = fs::rename(&base_path, &backup_path);
        // Atomically move temp → final.
        if let Err(e) = fs::rename(&tmp_path, &base_path) {
            // Attempt to restore the backup on failure.
            let _ = fs::rename(&backup_path, &base_path);
            remove_tmp();
            return Err(e).context("rename temp to final");
        }
        remove_tmp();

        // Sync to the graph if it's a known core node.
        if let Some((id, title, node_type)) = node_meta(name) {
            let node = self.graph.upsert(id, title, content, node_type, None);
            if let Err(e) = self.store.save(&node) {
                eprintln!("WARNING: could not sync {name} to graph: {e}");
            }
        }

        // Remove backup on success.
        let _ = fs::remove_file(&backup_path);
        Ok(())
    }

    /// Append an entry to today's interaction log.
    pub fn append_daily_log(&self, entry: &str) -> Result<()> {
        let _guard = self.mu.lock().unwrap_or_else(|e| e.into_inner());

        let date = chrono::Local::now().format("%Y-%m-%d").to_string();
        let path = self.base_path.join("logs").join("daily").join(format!("{date}.md"));

        let ts = chrono::Local::now().format("%H:%M:%S").to_string();
        let mut f = std::fs::OpenOptions::new()
            .append(true)
            .create(true)
            .write(true)
            .open(&path)
            .context("opening daily log")?;
        use std::io::Write;
        writeln!(f, "\n## {ts}\n{entry}")?;
        Ok(())
    }

    /// Read daily log files from the last N days.
    pub fn read_recent_logs(&self, days: usize) -> String {
        let _guard = self.mu.lock().unwrap_or_else(|e| e.into_inner());

        let mut parts = Vec::new();
        for i in 0..days {
            let date = (chrono::Local::now() - chrono::Duration::days(i as i64))
                .format("%Y-%m-%d")
                .to_string();
            let path = self.base_path.join("logs").join("daily").join(format!("{date}.md"));
            if let Ok(data) = fs::read_to_string(&path) {
                parts.push(format!("## {date}\n{data}"));
            }
        }
        parts.join("\n\n")
    }

    /// Full-text search on the graph, formatted for display.
    pub fn search(&self, query: &str, limit: usize) -> Result<String> {
        let ids = self.store.fts_search(query, limit)?;
        if ids.is_empty() {
            return Ok("(no memories found)".to_string());
        }
        let mut lines = Vec::new();
        for id in ids {
            if let Some(node) = self.graph.get(&id) {
                lines.push(format!("## {}\n{}", node.title, node.content));
            }
        }
        Ok(lines.join("\n\n"))
    }

    /// Create a new memory node for a discovered fact. If an identical
    /// fact already exists, update the existing node instead.
    pub fn save_fact(&self, fact: &str, tags: &str) -> Result<()> {
        let _guard = self.mu.lock().unwrap_or_else(|e| e.into_inner());

        // Dedup: check for an identical existing memory.
        let trimmed = fact.trim();
        for n in self.graph.all() {
            if n.node_type == NodeType::Memory && n.content.trim() == trimmed {
                // Update tags if new ones provided.
                if !tags.trim().is_empty() {
                    let new_tags: Vec<String> = tags
                        .split(',')
                        .map(|t| t.trim().to_string())
                        .filter(|t| !t.is_empty())
                        .collect();
                    let mut merged: Vec<String> = n.tags.clone();
                    for t in new_tags {
                        if !merged.contains(&t) {
                            merged.push(t);
                        }
                    }
                    let mut node = n;
                    node.tags = merged;
                    node.updated_at = now();
                    let _ = self.store.save(&node);
                }
                return Ok(()); // existing fact, no new node needed
            }
        }

        let id = format!("fact_{}", now_nanos());
        let title = format!("Fact: {}", truncate(trimmed, 40));

        let tag_list: Vec<String> = if tags.trim().is_empty() {
            Vec::new()
        } else {
            tags.split(',').map(|t| t.trim().to_string()).collect()
        };

        let node = self.graph.upsert(&id, &title, trimmed, NodeType::Memory, Some(tag_list));
        self.store.save(&node)
    }
}

impl PersonaSink for Persona {
    fn save_fact(&self, fact: &str, tags: &str) -> Result<()> {
        Persona::save_fact(self, fact, tags)
    }

    fn append_daily_log(&self, entry: &str) -> Result<()> {
        Persona::append_daily_log(self, entry)
    }
}

fn node_meta(name: &str) -> Option<(&'static str, &'static str, NodeType)> {
    NODE_MAP
        .iter()
        .find(|(file, _, _, _)| *file == name)
        .map(|(_, id, title, ty)| (*id, *title, *ty))
}

fn truncate(s: &str, n: usize) -> String {
    if s.chars().count() <= n {
        s.to_string()
    } else {
        let mut out: String = s.chars().take(n).collect();
        out.push_str("...");
        out
    }
}

fn now() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn now_nanos() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0)
}
