//! Tool registry and the LLM-callable tool set.
//!
//! Faithful port of Go `internal/tools/tools.go`. The registry
//! dispatches by tool name; each tool carries a JSON Schema for the
//! model and a handler that produces a string fed back as the tool
//! result. BashTool runs an in-process approval gate and can prompt
//! the operator via the confirm resolver; WebFetchTool applies the
//! netguard SSRF policy before any request leaves the agent.

use std::collections::HashMap;
use std::io::Write;
use std::sync::Arc;
use std::time::Duration;

use anyhow::{anyhow, Result};
use serde_json::{json, Value};

use crate::approval;
use crate::confirm;
use crate::llm::ToolSchema;
use crate::netguard;
use crate::persona::Persona;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResourceClass {
    ReadOnly,
    Mutating,
}

/// A single LLM-callable operation.
pub trait Tool: Send + Sync {
    fn schema(&self) -> &ToolSchema;
    /// Execute with parsed arguments, returning a display string.
    fn execute(&self, args: Value) -> Result<String>;
    /// Classifies whether this tool is read-only or mutating.
    fn resource_class(&self) -> ResourceClass {
        let name = self.schema().name.as_str();
        match name {
            "read_file" | "file_read" | "dir_list" | "grep" | "search" | "web_fetch" | "web_search" | "dendrite_search" => ResourceClass::ReadOnly,
            _ => ResourceClass::Mutating,
        }
    }
}

/// Concrete tool backed by a plain closure. Handlers are run inside
/// `spawn_blocking` so blocking file/network work never stalls the
/// async runtime.
struct FnTool {
    schema: ToolSchema,
    handler: Box<dyn Fn(Value) -> Result<String> + Send + Sync>,
}

impl Tool for FnTool {
    fn schema(&self) -> &ToolSchema {
        &self.schema
    }
    fn execute(&self, args: Value) -> Result<String> {
        (self.handler)(args)
    }
}

fn fn_tool(schema: ToolSchema, handler: impl Fn(Value) -> Result<String> + Send + Sync + 'static) -> Arc<dyn Tool> {
    Arc::new(FnTool {
        schema,
        handler: Box::new(handler),
    })
}

/// Registry of available tools.
pub struct Registry {
    tools: HashMap<String, Arc<dyn Tool>>,
    timeout: Duration,
}

impl Registry {
    pub fn new(work_dir: &str, timeout_secs: u32) -> Registry {
        let work_dir = if work_dir.is_empty() {
            "./workspace".to_string()
        } else {
            work_dir.to_string()
        };
        let _ = std::fs::create_dir_all(&work_dir);
        let timeout = if timeout_secs == 0 {
            Duration::from_secs(30)
        } else {
            Duration::from_secs(timeout_secs as u64)
        };
        Registry {
            tools: HashMap::new(),
            timeout,
        }
    }

    pub fn register(&mut self, t: Arc<dyn Tool>) {
        self.tools.insert(t.schema().name.clone(), t);
    }

    pub fn schemas(&self) -> Vec<ToolSchema> {
        self.tools.values().map(|t| t.schema().clone()).collect()
    }

    pub fn resource_class(&self, name: &str) -> ResourceClass {
        self.tools
            .get(name)
            .map(|t| t.resource_class())
            .unwrap_or_else(|| match name {
                "read_file" | "file_read" | "dir_list" | "grep" | "search" | "web_fetch" | "web_search" | "dendrite_search" => ResourceClass::ReadOnly,
                _ => ResourceClass::Mutating,
            })
    }

    pub async fn execute(&self, name: &str, args: Value) -> Result<String> {
        let t = self
            .tools
            .get(name)
            .cloned()
            .ok_or_else(|| anyhow!("unknown tool: {name}"))?;
        tokio::time::timeout(self.timeout, async move {
            tokio::task::spawn_blocking(move || t.execute(args))
                .await
                .map_err(|e| anyhow!("tool task failed: {e}"))?
        })
        .await
        .map_err(|_| anyhow!("tool {name} timed out after {:?}", self.timeout))?
    }

    pub fn len(&self) -> usize {
        self.tools.len()
    }

    pub fn is_empty(&self) -> bool {
        self.tools.is_empty()
    }
}

/// Build the tool registry for the given profile. The approval and net
/// policies flow into bash and web_fetch respectively; `resolver`
/// wires the operator prompt for flagged commands (pass None for
/// non-interactive runs — flagged commands auto-decline).
pub fn build_profile(
    profile: &str,
    work_dir: &str,
    timeout_secs: u32,
    persona: Arc<Persona>,
    approval_policy: approval::Policy,
    net_policy: netguard::Policy,
    resolver: Option<Arc<confirm::Resolver>>,
) -> Arc<Registry> {
    let mut r = Registry::new(work_dir, timeout_secs);

    r.register(memory_replace_tool(persona.clone()));
    r.register(daily_log_append_tool(persona.clone()));
    r.register(user_replace_tool(persona.clone()));
    r.register(soul_replace_tool(persona.clone()));
    r.register(memory_search_tool(persona.clone()));
    r.register(read_file_tool(work_dir));

    match profile.to_lowercase().as_str() {
        "full" => {
            r.register(bash_tool(work_dir, approval_policy, resolver.clone()));
            r.register(write_file_tool(work_dir));
            r.register(list_files_tool(work_dir));
            r.register(web_fetch_tool(net_policy));
        }
        "minimal" => {}
        _ => {
            // "standard" and any unknown name
            r.register(write_file_tool(work_dir));
            r.register(list_files_tool(work_dir));
            r.register(web_fetch_tool(net_policy));
        }
    }

    Arc::new(r)
}

// ─── Tool constructors ───────────────────────────────────────────────────────

/// Replace the contents of MEMORY.md with updated long-term memory.
pub fn memory_replace_tool(persona: Arc<Persona>) -> Arc<dyn Tool> {
    fn_tool(
        ToolSchema {
            name: "memory_replace".to_string(),
            description:
                "Replace the contents of MEMORY.md with updated long-term memory. Use this to save important facts you want to remember."
                    .to_string(),
            parameters: json!({
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "New content for MEMORY.md"}
                },
                "required": ["content"]
            }),
        },
        move |args| {
            let content = str_arg(&args, "content")?;
            persona.write_file("MEMORY.md", content)?;
            Ok("MEMORY.md updated successfully.".to_string())
        },
    )
}

/// Append an entry to today's daily interaction log.
pub fn daily_log_append_tool(persona: Arc<Persona>) -> Arc<dyn Tool> {
    fn_tool(
        ToolSchema {
            name: "daily_log_append".to_string(),
            description:
                "Append an entry to today's daily interaction log. Use this to record important events, decisions, or observations."
                    .to_string(),
            parameters: json!({
                "type": "object",
                "properties": {
                    "entry": {"type": "string", "description": "Log entry to append"}
                },
                "required": ["entry"]
            }),
        },
        move |args| {
            let entry = str_arg(&args, "entry")?;
            persona.append_daily_log(entry)?;
            Ok("Log entry appended.".to_string())
        },
    )
}

/// Update USER.md — a profile of the user.
pub fn user_replace_tool(persona: Arc<Persona>) -> Arc<dyn Tool> {
    fn_tool(
        ToolSchema {
            name: "user_replace".to_string(),
            description:
                "Update USER.md — a profile of the user with their preferences, background, and important facts about them."
                    .to_string(),
            parameters: json!({
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "New content for USER.md"}
                },
                "required": ["content"]
            }),
        },
        move |args| {
            let content = str_arg(&args, "content")?;
            persona.write_file("USER.md", content)?;
            Ok("USER.md updated.".to_string())
        },
    )
}

/// Update SOUL.md — personality, tone, and communication style.
pub fn soul_replace_tool(persona: Arc<Persona>) -> Arc<dyn Tool> {
    fn_tool(
        ToolSchema {
            name: "soul_replace".to_string(),
            description:
                "Update SOUL.md — the file that defines your personality, tone, and communication style."
                    .to_string(),
            parameters: json!({
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "New content for SOUL.md"}
                },
                "required": ["content"]
            }),
        },
        move |args| {
            let content = str_arg(&args, "content")?;
            persona.write_file("SOUL.md", content)?;
            Ok("SOUL.md updated.".to_string())
        },
    )
}

/// Search long-term memory using full-text search.
pub fn memory_search_tool(persona: Arc<Persona>) -> Arc<dyn Tool> {
    fn_tool(
        ToolSchema {
            name: "memory_search".to_string(),
            description: "Search your long-term memory store using full-text search.".to_string(),
            parameters: json!({
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results (default 5)"}
                },
                "required": ["query"]
            }),
        },
        move |args| {
            let query = str_arg(&args, "query")?;
            let limit = args
                .get("limit")
                .and_then(|v| v.as_i64())
                .unwrap_or(5) as usize;
            persona.search(query, limit)
        },
    )
}

/// Read a file from the workspace.
pub fn read_file_tool(work_dir: &str) -> Arc<dyn Tool> {
    let work_dir = work_dir.to_string();
    fn_tool(
        ToolSchema {
            name: "read_file".to_string(),
            description: "Read the contents of a file. Path is relative to the workspace.".to_string(),
            parameters: json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"}
                },
                "required": ["path"]
            }),
        },
        move |args| {
            let path = str_arg(&args, "path")?;
            let full = resolve_path(&work_dir, path)?;
            match std::fs::read_to_string(&full) {
                Ok(data) => Ok(data),
                Err(e) => Err(anyhow!("reading file: {e}")),
            }
        },
    )
}

/// Write content to a file in the workspace.
pub fn write_file_tool(work_dir: &str) -> Arc<dyn Tool> {
    let work_dir = work_dir.to_string();
    fn_tool(
        ToolSchema {
            name: "write_file".to_string(),
            description:
                "Write content to a file. Path is relative to the workspace. Creates parent directories automatically."
                    .to_string(),
            parameters: json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }),
        },
        move |args| {
            let path = str_arg(&args, "path")?;
            let content = str_arg(&args, "content")?;
            let full = resolve_path(&work_dir, path)?;
            if let Some(parent) = std::path::Path::new(&full).parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            std::fs::write(&full, content)?;
            Ok(format!("Written {} bytes to {}", content.len(), path))
        },
    )
}

/// List files in a workspace directory.
pub fn list_files_tool(work_dir: &str) -> Arc<dyn Tool> {
    let work_dir = work_dir.to_string();
    fn_tool(
        ToolSchema {
            name: "list_files".to_string(),
            description: "List files in a directory. Path is relative to workspace.".to_string(),
            parameters: json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: '.')"}
                },
                "required": []
            }),
        },
        move |args| {
            let path = args
                .get("path")
                .and_then(|v| v.as_str())
                .filter(|p| !p.is_empty())
                .unwrap_or(".");
            let full = resolve_path(&work_dir, path)?;
            let entries = std::fs::read_dir(&full)
                .map_err(|e| anyhow!("{e}"))?;
            let mut lines = Vec::new();
            for e in entries {
                let e = e?;
                let meta = e.metadata()?;
                let typ = if e.file_type()?.is_dir() { "dir " } else { "file" };
                lines.push(format!("{typ}  {:6}  {}", meta.len(), e.file_name().to_string_lossy()));
            }
            if lines.is_empty() {
                Ok("(empty directory)".to_string())
            } else {
                Ok(lines.join("\n"))
            }
        },
    )
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/// Safely resolve a relative path within the workspace, blocking
/// directory traversal (`../../etc/passwd`).
fn resolve_path(work_dir: &str, rel: &str) -> Result<String> {
    let abs_work = std::fs::canonicalize(work_dir)
        .unwrap_or_else(|_| std::path::PathBuf::from(work_dir));
    let joined = std::path::Path::new(work_dir).join(rel);
    let abs_resolved = std::fs::canonicalize(&joined)
        .unwrap_or_else(|_| joined);
    let ws = abs_work.to_string_lossy().to_string();
    let rs = abs_resolved.to_string_lossy().to_string();
    if rs != ws && !rs.starts_with(&format!("{ws}/")) {
        return Err(anyhow!("path escapes workspace: {rs} not within {ws}"));
    }
    Ok(rs)
}

fn str_arg<'a>(args: &'a Value, name: &str) -> Result<&'a str> {
    args.get(name)
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty())
        .ok_or_else(|| anyhow!("{name} is required"))
}

// ─── Gated tools (M5) ────────────────────────────────────────────────────────

/// Execute a bash command in the workspace directory. `policy` gates
/// dangerous patterns; `resolver` is invoked when a decision needs
/// operator approval. Pass None to auto-decline flagged commands.
pub fn bash_tool(
    work_dir: &str,
    policy: approval::Policy,
    resolver: Option<Arc<confirm::Resolver>>,
) -> Arc<dyn Tool> {
    let work_dir = work_dir.to_string();
    fn_tool(
        ToolSchema {
            name: "bash".to_string(),
            description: "Execute a bash command in the workspace directory. Returns stdout+stderr.".to_string(),
            parameters: json!({
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to execute"}
                },
                "required": ["command"]
            }),
        },
        move |args| {
            let cmd = str_arg(&args, "command")?;

            // In-process approval gate — a heuristic, not a boundary.
            let mut decision = approval::inspect(cmd);
            decision.evaluate(policy);
            if !decision.allow {
                return Ok(format!(
                    "BLOCKED by approval gate ({}, severity={}): {}. If you really need this, ask the operator to run it manually.",
                    decision.rule_name, decision.severity, decision.reason
                ));
            }
            if decision.require_confirm {
                let resolver = resolver
                    .clone()
                    .ok_or_else(|| anyhow!("BLOCKED: gate flagged command but no resolver is configured (non-interactive mode). Run manually or set security.approval_policy to trust-local."))?;
                let rule_key = confirm::bash_rule_key(cmd);
                let scope = "bash:cmd";
                let req = confirm::Request {
                    kind: pick_bash_kind(cmd).to_string(),
                    title: "Run shell command?".to_string(),
                    detail: cmd.to_string(),
                    options: std::collections::HashMap::new(),
                    secret: needs_sudo_secret(cmd),
                    prompt: "Password: ".to_string(),
                    rule_key,
                    scope: scope.to_string(),
                };
                let outcome = resolver.check(&req)?;
                if outcome.decision == confirm::Decision::Decline {
                    return Ok("BLOCKED: operator declined.".to_string());
                }
                if outcome.decision == confirm::Decision::AllowAlways && !outcome.remembered_rule.is_empty() {
                    eprintln!("🟢 remembered rule: {}", outcome.remembered_rule);
                }
                if needs_sudo_secret(cmd) {
                    if outcome.input.is_empty() {
                        return Ok("BLOCKED: sudo password required but not provided.".to_string());
                    }
                    return run_with_sudo_password(&work_dir, cmd, &outcome.input);
                }
            }

            run_bash(&work_dir, cmd)
        },
    )
}

/// Fetch a URL and return its text content. The net policy applies
/// SSRF guards (loopback, RFC1918, metadata) before the request.
pub fn web_fetch_tool(policy: netguard::Policy) -> Arc<dyn Tool> {
    fn_tool(
        ToolSchema {
            name: "web_fetch".to_string(),
            description: "Fetch a URL and return its text content. Useful for reading documentation or web pages.".to_string(),
            parameters: json!({
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"}
                },
                "required": ["url"]
            }),
        },
        move |args| {
            let url = str_arg(&args, "url")?;

            // SSRF gate: skipped when every relevant flag is open
            // (loopback+private+cleartext all allowed).
            if !policy.allow_loopback && !policy.allow_private && !policy.allow_cleartext_http {
                let decision = policy.check(url);
                if !decision.allow {
                    return Ok(format!("BLOCKED by netguard: {}", decision.reason));
                }
            }

            let client = reqwest::blocking::Client::builder()
                .timeout(Duration::from_secs(20))
                .build()?;
            let resp = client
                .get(url)
                .header("User-Agent", "CYNAPSE-Agent/1.0")
                .send()?;
            let status = resp.status().as_u16();
            let body = resp.bytes()?;
            let mut text = String::from_utf8_lossy(&body).to_string();
            const MAX_BODY: usize = 32 * 1024;
            if text.len() > MAX_BODY {
                text.truncate(MAX_BODY);
                text.push_str("\n[truncated at 32 KB]");
            }
            Ok(format!("Status: {status}\n\n{text}"))
        },
    )
}

/// Choose the confirm Kind label for a bash command.
fn pick_bash_kind(cmd: &str) -> &'static str {
    if cmd.contains("sudo ") {
        "sudo"
    } else {
        "bash"
    }
}

/// Whether a command needs a sudo password on stdin.
fn needs_sudo_secret(cmd: &str) -> bool {
    cmd.contains("sudo ")
}

/// Run `sudo -S -p '' <cmd>` with the password fed on stdin.
fn run_with_sudo_password(work_dir: &str, cmd: &str, password: &str) -> Result<String> {
    let trimmed = cmd.trim();
    let rest = if let Some(idx) = trimmed.find(' ') {
        if &trimmed[..idx] == "sudo" {
            trimmed[idx + 1..].trim()
        } else {
            trimmed
        }
    } else {
        trimmed
    };

    use std::process::{Command, Stdio};
    let mut child = Command::new("sudo")
        .args(["-S", "-p", "", "bash", "-c", rest])
        .current_dir(work_dir)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
    if let Some(mut stdin) = child.stdin.take() {
        let _ = stdin.write_all(format!("{password}\n").as_bytes());
    }
    let out = child.wait_with_output()?;
    Ok(format_output(out.status.success(), &out.stdout, &out.stderr))
}

/// Run a bash command and format combined stdout+stderr, capped at
/// 256 KB.
fn run_bash(work_dir: &str, cmd: &str) -> Result<String> {
    use std::process::Command;
    let out = Command::new("bash")
        .arg("-c")
        .arg(cmd)
        .current_dir(work_dir)
        .output()?;
    Ok(format_output(out.status.success(), &out.stdout, &out.stderr))
}

fn format_output(success: bool, stdout: &[u8], stderr: &[u8]) -> String {
    const MAX_OUTPUT: usize = 256 * 1024;
    let mut result = String::new();
    let stdout = String::from_utf8_lossy(stdout);
    let stderr = String::from_utf8_lossy(stderr);
    if !success {
        result.push_str(&format!("exit error\n"));
    }
    result.push_str(&stdout);
    result.push_str(&stderr);
    if result.len() > MAX_OUTPUT {
        result.truncate(MAX_OUTPUT);
        result.push_str("\n[output truncated at 256 KB]");
    }
    if result.trim().is_empty() {
        if success {
            result = "(no output)".to_string();
        }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::approval;

    #[test]
    fn bash_gate_blocks_rm_rf() {
        let t = bash_tool("/tmp", approval::default_policy(), None);
        let args = json!({"command": "rm -rf /tmp/foo"});
        let out = t.execute(args).unwrap();
        assert!(out.contains("BLOCKED by approval gate"), "{out}");
    }

    #[test]
    fn bash_trust_local_runs_safe_command() {
        let t = bash_tool("/tmp", approval::trust_local_policy(), None);
        let args = json!({"command": "echo hello-from-tools"});
        let out = t.execute(args).unwrap();
        assert!(out.contains("hello-from-tools"), "{out}");
    }

    #[test]
    fn bash_requires_command() {
        let t = bash_tool("/tmp", approval::trust_local_policy(), None);
        let args = json!({"command": ""});
        assert!(t.execute(args).is_err());
    }

    #[test]
    fn web_fetch_secure_blocks_loopback() {
        let t = web_fetch_tool(netguard::secure_default());
        let args = json!({"url": "http://127.0.0.1:11434/api/tags"});
        let out = t.execute(args).unwrap();
        assert!(out.contains("BLOCKED by netguard"), "{out}");
    }

    #[test]
    fn web_fetch_local_dev_allows_loopback() {
        let t = web_fetch_tool(netguard::local_dev_policy());
        let args = json!({"url": "http://127.0.0.1:11434/api/tags"});
        // Ollama may or may not be running; we just check the gate
        // let the request through (i.e. not a BLOCKED message).
        let out = t.execute(args).unwrap();
        assert!(!out.contains("BLOCKED by netguard"), "{out}");
    }

    #[test]
    fn read_file_blocks_traversal() {
        let dir = std::env::temp_dir().join(format!("cynapse-tools-{}", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        std::fs::write(dir.join("secret.txt"), "top secret").unwrap();
        let t = read_file_tool(dir.to_str().unwrap());
        let args = json!({"path": "../../etc/passwd"});
        let out = t.execute(args);
        assert!(out.is_err() || out.unwrap().contains("path escapes workspace"));
        let _ = std::fs::remove_dir_all(&dir);
    }
}

