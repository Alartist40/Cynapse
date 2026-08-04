//! Tool registry and the LLM-callable tool set.
//!
//! Faithful port of Go `internal/tools/tools.go`. The registry
//! dispatches by tool name; each tool carries a JSON Schema for the
//! model and a handler that produces a string fed back as the tool
//! result. M5 adds the approval/netguard gated tools (bash, web_fetch).

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use anyhow::{anyhow, Result};
use serde_json::{json, Value};

use crate::llm::ToolSchema;
use crate::persona::Persona;

/// A single LLM-callable operation.
pub trait Tool: Send + Sync {
    fn schema(&self) -> &ToolSchema;
    /// Execute with parsed arguments, returning a display string.
    fn execute(&self, args: Value) -> Result<String>;
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

/// Build the tool registry for the given profile. BashTool (needs
/// the approval gate) and WebFetchTool (needs netguard) are wired in
/// M5; everything else is available now.
pub fn build_profile(profile: &str, work_dir: &str, timeout_secs: u32, persona: Arc<Persona>) -> Arc<Registry> {
    let mut r = Registry::new(work_dir, timeout_secs);

    r.register(memory_replace_tool(persona.clone()));
    r.register(daily_log_append_tool(persona.clone()));
    r.register(user_replace_tool(persona.clone()));
    r.register(soul_replace_tool(persona.clone()));
    r.register(memory_search_tool(persona.clone()));
    r.register(read_file_tool(work_dir));

    match profile.to_lowercase().as_str() {
        "minimal" => {}
        "full" | "standard" => {
            r.register(write_file_tool(work_dir));
            r.register(list_files_tool(work_dir));
        }
        _ => {
            r.register(write_file_tool(work_dir));
            r.register(list_files_tool(work_dir));
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
