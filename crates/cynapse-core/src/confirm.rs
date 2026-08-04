//! Interactive prompt protocol for any subsystem needing a
//! human-in-the-loop decision.
//!
//! Faithful port of Go `internal/confirm/confirm.go`. Three decision
//! modes: AllowOnce (no memory), AllowSection (rest of the current
//! section), AllowAlways (persisted rule in `~/.cynapse/allowlist`).
//! The decision logic (file/section memory, scope matching) is pure
//! and testable; the prompt UI is a thin stdin wrapper that the TUI
//! swaps for a message-based implementation.

use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::sync::{Arc, Mutex, RwLock};

use anyhow::{anyhow, Result};

/// What the operator chose when prompted.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Decision {
    Decline,
    AllowOnce,
    AllowSection,
    AllowAlways,
}

impl Decision {
    pub fn as_str(&self) -> &'static str {
        match self {
            Decision::Decline => "decline",
            Decision::AllowOnce => "once",
            Decision::AllowSection => "section",
            Decision::AllowAlways => "always",
        }
    }

    fn short_key(&self) -> &'static str {
        match self {
            Decision::Decline => "D",
            Decision::AllowOnce => "O",
            Decision::AllowSection => "S",
            Decision::AllowAlways => "A",
        }
    }
}

/// The shape of the question being asked.
#[derive(Debug, Clone)]
pub struct Request {
    /// Names the subsystem asking: "bash", "sudo", "ssh",
    /// "password", "synapse", "model_download", ...
    pub kind: String,
    /// One-line title, ~30-50 chars, e.g. "Run shell command?"
    pub title: String,
    /// Long body — the actual command, URL, etc.
    pub detail: String,
    /// Prompt choices; default order Decline, Once, Section, Always.
    pub options: HashMap<Decision, String>,
    /// When true, switches to password mode (no echo).
    pub secret: bool,
    /// Shown when secret; e.g. "Password for root:"
    pub prompt: String,
    /// Stable identifier used to persist AllowAlways decisions.
    pub rule_key: String,
    /// Free-form tag like "section:llm-rebuild" that AllowSection
    /// decisions latch onto.
    pub scope: String,
}

impl Request {
    pub fn is_sensitive(&self) -> bool {
        matches!(self.kind.as_str(), "password" | "sudo" | "keyring")
    }
}

/// What the operator actually decided, with follow-on effects.
#[derive(Debug, Clone)]
pub struct Resolved {
    pub decision: Decision,
    /// Operator's typed value for a secret prompt; empty otherwise.
    pub input: String,
    /// Non-empty when an AllowAlways was written to the rule file.
    pub remembered_rule: String,
}

/// The surface for asking. Tests stub this; the TUI wires a
/// message-based implementation.
pub trait Prompter: Send + Sync {
    fn ask(&self, r: &Request) -> Result<Resolved>;
}

// ─── In-memory section scope registry ───────────────────────────────────────

/// Tracks AllowSection decisions for the lifetime of one "scope"
/// (typically one conversation turn).
pub struct Section {
    scope: String,
    allowed: Mutex<HashMap<String, bool>>,
}

impl Section {
    pub fn new(scope: &str) -> Section {
        Section {
            scope: scope.to_string(),
            allowed: Mutex::new(HashMap::new()),
        }
    }

    pub fn scope(&self) -> &str {
        &self.scope
    }

    pub fn allow_rule(&self, rule_key: &str) {
        self.allowed
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .insert(rule_key.to_string(), true);
    }

    pub fn is_allowed(&self, rule_key: &str) -> bool {
        self.allowed
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .get(rule_key)
            .copied()
            .unwrap_or(false)
    }
}

// ─── Persistent allowlist ──────────────────────────────────────────────────

/// Persists AllowAlways rules across restarts. Backed by a file in
/// ~/.cynapse/ so the operator can audit and edit it.
pub struct Allowlist {
    rules: RwLock<HashMap<String, bool>>,
    path: String,
}

impl Allowlist {
    /// Read rules from path into memory. A missing file is fine.
    pub fn load(path: &Path) -> Result<Allowlist> {
        let mut rules = HashMap::new();
        if let Ok(text) = fs::read_to_string(path) {
            for line in text.lines() {
                let key = line.trim();
                if key.is_empty() || key.starts_with('#') {
                    continue;
                }
                rules.insert(key.to_string(), true);
            }
        }
        Ok(Allowlist {
            rules: RwLock::new(rules),
            path: path.to_string_lossy().to_string(),
        })
    }

    pub fn is_allowed(&self, rule_key: &str) -> bool {
        self.rules
            .read()
            .unwrap_or_else(|e| e.into_inner())
            .get(rule_key)
            .copied()
            .unwrap_or(false)
    }

    /// Write rule to the persistent allowlist, deduplicating and
    /// preserving human comments.
    pub fn remember(&self, rule_key: &str) -> Result<()> {
        if rule_key.is_empty() {
            return Ok(());
        }
        {
            let mut rules = self.rules.write().unwrap_or_else(|e| e.into_inner());
            if rules.get(rule_key).copied().unwrap_or(false) {
                return Ok(());
            }
            rules.insert(rule_key.to_string(), true);
        }
        self.flush()
    }

    /// Remove a rule from the persistent allowlist.
    pub fn forget(&self, rule_key: &str) -> Result<()> {
        if rule_key.is_empty() {
            return Ok(());
        }
        {
            let mut rules = self.rules.write().unwrap_or_else(|e| e.into_inner());
            if !rules.get(rule_key).copied().unwrap_or(false) {
                return Ok(());
            }
            rules.remove(rule_key);
        }
        self.flush()
    }

    fn flush(&self) -> Result<()> {
        let rules = self.rules.read().unwrap_or_else(|e| e.into_inner());
        let mut out = String::from(
            "# Cynapse operator allowlist — one rule per line.\n\
             # Generated automatically.  Removing a line tightens policy again.\n\
             # Format: <kind>:<stable-rule-key>\n",
        );
        let mut keys: Vec<&String> = rules.keys().collect();
        keys.sort();
        for k in keys {
            out.push_str(k);
            out.push('\n');
        }
        drop(rules);
        if let Some(parent) = Path::new(&self.path).parent() {
            let _ = fs::create_dir_all(parent);
        }
        write_mode_0600(&self.path, out.as_bytes())
    }

    /// Copy of the rule set for the /allowed TUI command.
    pub fn snapshot(&self) -> Vec<String> {
        let rules = self.rules.read().unwrap_or_else(|e| e.into_inner());
        let mut out: Vec<String> = rules.keys().cloned().collect();
        out.sort();
        out
    }
}

// ─── Stdin Prompter ─────────────────────────────────────────────────────────

/// Default UI: prints the prompt and reads a decision from stdin.
pub struct StdinPrompter {
    /// Reads decisions from stdin by default.
    reader: Option<Mutex<Box<dyn std::io::BufRead + Send>>>,
    /// Writes prompts to stderr by default.
    writer: Option<Mutex<Box<dyn std::io::Write + Send>>>,
}

impl Default for StdinPrompter {
    fn default() -> Self {
        StdinPrompter {
            reader: None,
            writer: None,
        }
    }
}

impl StdinPrompter {
    /// Construct a prompter with an explicit reader and writer
    /// (handy for tests and the TUI).
    pub fn with_io(
        reader: Box<dyn std::io::BufRead + Send>,
        writer: Box<dyn std::io::Write + Send>,
    ) -> StdinPrompter {
        StdinPrompter {
            reader: Some(Mutex::new(reader)),
            writer: Some(Mutex::new(writer)),
        }
    }
}

impl Prompter for StdinPrompter {
    fn ask(&self, r: &Request) -> Result<Resolved> {
        if r.secret {
            return self.ask_secret(r);
        }
        self.ask_decision(r)
    }
}

impl StdinPrompter {
    fn ask_decision(&self, r: &Request) -> Result<Resolved> {
        self.println(&format!("\n⚠  {}", r.title));
        if !r.detail.is_empty() {
            for line in r.detail.lines() {
                self.println(&format!("   {line}"));
            }
        }

        let mut opts = r.options.clone();
        if opts.is_empty() {
            opts.insert(Decision::Decline, "Decline".to_string());
            opts.insert(Decision::AllowOnce, "Allow once".to_string());
            opts.insert(Decision::AllowSection, "Allow for this section".to_string());
            if !r.is_sensitive() {
                opts.insert(Decision::AllowAlways, "Always allow".to_string());
            }
        }
        if r.is_sensitive() {
            opts.remove(&Decision::AllowAlways);
        }

        let mut line = String::from("\n   [");
        let keys = if r.is_sensitive() {
            vec![Decision::Decline, Decision::AllowOnce, Decision::AllowSection]
        } else {
            vec![Decision::Decline, Decision::AllowOnce, Decision::AllowSection, Decision::AllowAlways]
        };
        for (i, k) in keys.iter().enumerate() {
            if i > 0 {
                line.push('/');
            }
            line.push_str(&format!("{}) {}", k.short_key(), opts.get(k).map(|s| s.as_str()).unwrap_or("")));
        }
        line.push_str("]: ");
        self.println(&line);

        let mut input = String::new();
        match self.input_line(&mut input) {
            Ok(false) => return Ok(Resolved { decision: Decision::Decline, input: String::new(), remembered_rule: String::new() }),
            Err(_) => return Ok(Resolved { decision: Decision::Decline, input: String::new(), remembered_rule: String::new() }),
            Ok(true) => {}
        }
        let raw = input.trim().to_lowercase();

        match raw.as_str() {
            "d" | "decline" | "no" | "n" => Ok(Resolved { decision: Decision::Decline, input: String::new(), remembered_rule: String::new() }),
            "o" | "once" | "y" | "yes" => Ok(Resolved { decision: Decision::AllowOnce, input: String::new(), remembered_rule: String::new() }),
            "s" | "section" => Ok(Resolved { decision: Decision::AllowSection, input: String::new(), remembered_rule: String::new() }),
            "a" | "always" => {
                if r.is_sensitive() {
                    Ok(Resolved { decision: Decision::AllowOnce, input: String::new(), remembered_rule: String::new() })
                } else {
                    Ok(Resolved { decision: Decision::AllowAlways, input: String::new(), remembered_rule: r.rule_key.clone() })
                }
            }
            _ => Ok(Resolved { decision: Decision::Decline, input: String::new(), remembered_rule: String::new() }),
        }
    }

    fn ask_secret(&self, r: &Request) -> Result<Resolved> {
        let prompt = if r.prompt.is_empty() {
            "Enter value: "
        } else {
            r.prompt.as_str()
        };
        self.println(&format!("\n🔑 {prompt}"));
        let mut input = String::new();
        match self.input_line(&mut input) {
            Ok(true) => Ok(Resolved { decision: Decision::AllowOnce, input: input.trim_end_matches('\n').to_string(), remembered_rule: String::new() }),
            _ => Ok(Resolved { decision: Decision::Decline, input: String::new(), remembered_rule: String::new() }),
        }
    }

    fn input_line(&self, out: &mut String) -> std::io::Result<bool> {
        match &self.reader {
            Some(r) => {
                let mut r = r.lock().unwrap_or_else(|e| e.into_inner());
                let n = std::io::BufRead::read_line(&mut *r, out)?;
                Ok(n > 0)
            }
            None => {
                use std::io::BufRead;
                let stdin = std::io::stdin();
                let n = stdin.lock().read_line(out)?;
                Ok(n > 0)
            }
        }
    }

    fn println(&self, line: &str) {
        let result = match &self.writer {
            Some(w) => {
                let mut w = w.lock().unwrap_or_else(|e| e.into_inner());
                writeln_std(&mut *w, line)
            }
            None => {
                use std::io::Write;
                let mut err = std::io::stderr();
                let r = err.write_all(line.as_bytes());
                let _ = err.write_all(b"\n");
                let _ = err.flush();
                r
            }
        };
        let _ = result;
    }
}

fn writeln_std(w: &mut dyn std::io::Write, line: &str) -> std::io::Result<()> {
    w.write_all(line.as_bytes())?;
    w.write_all(b"\n")?;
    w.flush()
}

// ─── Policy resolution ────────────────────────────────────────────────────

/// Ties together the persistent allowlist, in-memory section scope,
/// and the prompter.
pub struct Resolver {
    pub allowlist: Option<Arc<Allowlist>>,
    pub section: Option<Arc<Section>>,
    pub prompter: Option<Arc<dyn Prompter>>,
}

impl Resolver {
    pub fn new(prompter: Option<Arc<dyn Prompter>>) -> Resolver {
        Resolver {
            allowlist: None,
            section: None,
            prompter,
        }
    }

    /// Return the operator decision for r. RuleKey and Scope are both
    /// optional.
    pub fn check(&self, r: &Request) -> Result<Resolved> {
        if r.rule_key.is_empty() {
            let prompter = self
                .prompter
                .clone()
                .ok_or_else(|| anyhow!("no prompter configured"))?;
            return prompter.ask(r);
        }

        if !r.is_sensitive() {
            if let Some(al) = &self.allowlist {
                if al.is_allowed(&r.rule_key) {
                    return Ok(Resolved {
                        decision: Decision::AllowAlways,
                        input: String::new(),
                        remembered_rule: r.rule_key.clone(),
                    });
                }
            }
        }
        if let Some(sec) = &self.section {
            if sec.is_allowed(&r.rule_key) {
                return Ok(Resolved {
                    decision: Decision::AllowSection,
                    input: String::new(),
                    remembered_rule: String::new(),
                });
            }
        }

        let prompter = self
            .prompter
            .clone()
            .ok_or_else(|| anyhow!("no prompter configured"))?;
        let mut out = prompter.ask(r)?;

        match out.decision {
            Decision::AllowAlways => {
                // Defensive: never persist secrets.
                if r.is_sensitive() {
                    out.decision = Decision::AllowOnce;
                    return Ok(out);
                }
                if let Some(al) = &self.allowlist {
                    al.remember(&r.rule_key)?;
                }
                out.remembered_rule = r.rule_key.clone();
                Ok(out)
            }
            Decision::AllowSection => {
                if let Some(sec) = &self.section {
                    sec.allow_rule(&r.rule_key);
                }
                Ok(out)
            }
            _ => Ok(out),
        }
    }
}

// ─── Stable RuleKeys ──────────────────────────────────────────────────────

/// Deterministic allowlist key for a shell command. Trivial formatting
/// differences collapse to one rule; the exact string is the identity
/// (any AllowAlways rule is exact-string, not a regex).
pub fn bash_rule_key(command: &str) -> String {
    let s = command.replace("\\\n", " ");
    let s = s.replace("\\\r\n", " ");
    format!("bash:{}", s.split_whitespace().collect::<Vec<_>>().join(" "))
}

pub fn ssh_rule_key(host: &str, command: &str) -> String {
    format!("ssh:{}:{}", host.trim(), command.split_whitespace().collect::<Vec<_>>().join(" "))
}

pub fn download_rule_key(url_or_id: &str) -> String {
    format!("download:{url_or_id}")
}

pub fn sudo_rule_key(command: &str) -> String {
    format!("sudo:{}", command.split_whitespace().collect::<Vec<_>>().join(" "))
}

/// Write bytes with mode 0600 (owner read/write only).
fn write_mode_0600(path: &str, data: &[u8]) -> Result<()> {
    #[cfg(unix)]
    {
        use std::io::Write;
        use std::os::unix::fs::OpenOptionsExt;
        let mut f = fs::OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .mode(0o600)
            .open(path)?;
        f.write_all(data)?;
        f.sync_all()?;
        Ok(())
    }
    #[cfg(not(unix))]
    {
        std::fs::write(path, data)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;

    struct ScriptedPrompter {
        answers: Mutex<std::collections::VecDeque<Decision>>,
    }

    impl ScriptedPrompter {
        fn new(answers: Vec<Decision>) -> ScriptedPrompter {
            ScriptedPrompter {
                answers: Mutex::new(answers.into()),
            }
        }
    }

    impl Prompter for ScriptedPrompter {
        fn ask(&self, _r: &Request) -> Result<Resolved> {
            let mut q = self.answers.lock().unwrap_or_else(|e| e.into_inner());
            let d = q.pop_front().unwrap_or(Decision::Decline);
            Ok(Resolved { decision: d, input: String::new(), remembered_rule: String::new() })
        }
    }

    fn req(rule_key: &str) -> Request {
        Request {
            kind: "bash".to_string(),
            title: "Run shell command?".to_string(),
            detail: "ls -la".to_string(),
            options: HashMap::new(),
            secret: false,
            prompt: String::new(),
            rule_key: rule_key.to_string(),
            scope: String::new(),
        }
    }

    #[test]
    fn once_decision_does_not_memorize() {
        let p = Arc::new(ScriptedPrompter::new(vec![Decision::AllowOnce]));
        let res = Resolver::new(Some(p));
        let out = res.check(&req("bash:ls")).unwrap();
        assert_eq!(out.decision, Decision::AllowOnce);
        assert!(out.remembered_rule.is_empty());
        // Second ask prompts again.
        let p = Arc::new(ScriptedPrompter::new(vec![Decision::Decline]));
        let res2 = Resolver::new(Some(p));
        let out2 = res2.check(&req("bash:ls")).unwrap();
        assert_eq!(out2.decision, Decision::Decline);
    }

    #[test]
    fn section_decision_memorizes_within_scope() {
        let section = Arc::new(Section::new("turn:1"));
        let p = Arc::new(ScriptedPrompter::new(vec![Decision::AllowSection]));
        let mut res = Resolver::new(Some(p));
        res.section = Some(section.clone());
        let out = res.check(&req("bash:ls")).unwrap();
        assert_eq!(out.decision, Decision::AllowSection);
        // Second ask within same section is auto-allowed.
        let out2 = res.check(&req("bash:ls")).unwrap();
        assert_eq!(out2.decision, Decision::AllowSection);
        assert!(section.is_allowed("bash:ls"));
    }

    #[test]
    fn always_decision_persists() {
        let dir = std::env::temp_dir().join(format!("cynapse-conf-{}", std::process::id()));
        let path = dir.join("allowlist");
        let _ = std::fs::remove_dir_all(&dir);
        let al = Arc::new(Allowlist::load(&path).unwrap());
        let p = Arc::new(ScriptedPrompter::new(vec![Decision::AllowAlways]));
        let mut res = Resolver::new(Some(p));
        res.allowlist = Some(al.clone());
        let out = res.check(&req("bash:ls")).unwrap();
        assert_eq!(out.decision, Decision::AllowAlways);
        assert_eq!(out.remembered_rule, "bash:ls");
        // Now auto-allowed without prompting.
        let p2 = Arc::new(ScriptedPrompter::new(vec![Decision::Decline]));
        let mut res2 = Resolver::new(Some(p2));
        res2.allowlist = Some(al.clone());
        let out2 = res2.check(&req("bash:ls")).unwrap();
        assert_eq!(out2.decision, Decision::AllowAlways);
        // File persisted.
        let text = std::fs::read_to_string(&path).unwrap();
        assert!(text.contains("bash:ls"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn sensitive_requests_never_persist() {
        let al = Arc::new(Allowlist::load(std::path::Path::new("/nonexistent-allowlist")).unwrap());
        let p = Arc::new(ScriptedPrompter::new(vec![Decision::AllowAlways]));
        let mut res = Resolver::new(Some(p));
        res.allowlist = Some(al.clone());
        let mut r = req("sudo:ls");
        r.kind = "sudo".to_string();
        r.secret = true;
        let out = res.check(&r).unwrap();
        assert_eq!(out.decision, Decision::AllowOnce, "secret never persists");
        assert!(out.remembered_rule.is_empty());
    }

    #[test]
    fn bash_rule_key_collapses_noise() {
        assert_eq!(bash_rule_key("rm -rf /tmp/x"), "bash:rm -rf /tmp/x");
        assert_eq!(bash_rule_key("rm -rf  /tmp/x"), "bash:rm -rf /tmp/x");
        assert_eq!(bash_rule_key("rm -rf \\\n/tmp/x"), "bash:rm -rf /tmp/x");
    }

    #[test]
    fn stdin_prompter_parse() {
        let p = StdinPrompter::with_io(
            Box::new(std::io::BufReader::new("y\n".as_bytes())),
            Box::new(Vec::<u8>::new()),
        );
        let out = p.ask(&req("")).unwrap();
        assert_eq!(out.decision, Decision::AllowOnce);
    }

    #[test]
    fn allowlist_remember_forget() {
        let dir = std::env::temp_dir().join(format!("cynapse-allowlist-{}", std::process::id()));
        let path = dir.join("allowlist");
        let _ = std::fs::remove_dir_all(&dir);
        let al = Allowlist::load(&path).unwrap();
        al.remember("bash:foo").unwrap();
        assert!(al.is_allowed("bash:foo"));
        al.forget("bash:foo").unwrap();
        assert!(!al.is_allowed("bash:foo"));
        let _ = std::fs::remove_dir_all(&dir);
    }
}
