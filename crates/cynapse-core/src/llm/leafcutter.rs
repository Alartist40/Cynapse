//! Leafcutter provider — spawns `leafcutter server` locally and talks to its
//! OpenAI-compatible HTTP API.
//!
//! Faithful Rust port of Go `internal/llm/leafcutter.go`: the binary is
//! auto-detected from PATH (or `LlmConfig::leafcutter_path`), a free port is
//! chosen, the model is passed by absolute path, and a `/health` probe waits
//! for readiness. Chat + streaming reuse the OpenAI `chat/completions` wire
//! format (with the `/v1` prefix) but, like the Go port, send only plain
//! role/content messages (no tools — leafcutter is a raw inference server).

use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use anyhow::{anyhow, Context as _, Result};
use async_trait::async_trait;
use serde_json::{json, Value};
use tokio::sync::mpsc;

use crate::config::LlmConfig;
use crate::llm::providers::{BaseClient, Cancelled, LlmClient, StreamHandle};
use crate::llm::{Request, Response, Usage};

/// Spawn a `leafcutter server` subprocess and return a client for it.
pub(crate) fn new(base: BaseClient, cfg: &LlmConfig) -> Result<Arc<dyn LlmClient>> {
    let model_id = cfg.model.clone();
    let model_path = resolve_model_path(&model_id, &cfg.models_dir)?;

    let bin = if cfg.leafcutter_path.is_empty() {
        find_leafcutter()
    } else {
        let p = cfg.leafcutter_path.clone();
        if std::path::Path::new(&p).exists() {
            p
        } else {
            anyhow::bail!("leafcutter binary not found at configured path: {p}");
        }
    };
    if bin.is_empty() {
        anyhow::bail!(
            "leafcutter binary not found in PATH. Install from https://github.com/Alartist40/LeafcutterLLM"
        );
    }

    let port = find_free_port().context("finding a free port for leafcutter")?;
    let base_url = format!("http://127.0.0.1:{port}");

    let mut cmd = std::process::Command::new(&bin);
    cmd.args(["server", "--model", &model_path, "--port", &port.to_string()]);

    // LD_LIBRARY_PATH for llama.cpp shared libs when installed via install.sh.
    if let Some(home) = dirs::home_dir() {
        let lib = home.join(".leafcutter/llama.cpp/build/bin");
        if lib.exists() {
            let prev = std::env::var("LD_LIBRARY_PATH").unwrap_or_default();
            cmd.env("LD_LIBRARY_PATH", format!("{}:{}", lib.display(), prev));
        }
    }

    let mut child = cmd
        .spawn()
        .with_context(|| format!("starting leafcutter server: {bin}"))?;

    if let Err(e) = wait_for_server(&base_url, Duration::from_secs(30)) {
        let _ = child.kill();
        let _ = child.wait();
        return Err(e.context("leafcutter server failed to start"));
    }

    let instance = LeafcutterClient {
        base,
        base_url,
        model: Mutex::new(model_id),
        // Wrapped in a Mutex so `std::process::Child` satisfies `Sync`.
        child: Mutex::new(child),
    };
    Ok(Arc::new(instance))
}

/// A `leafcutter server` client. Dropping the last handle kills the child.
pub struct LeafcutterClient {
    base: BaseClient,
    base_url: String,
    model: Mutex<String>,
    child: Mutex<std::process::Child>,
}

impl Drop for LeafcutterClient {
    fn drop(&mut self) {
        if let Ok(mut child) = self.child.lock() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[async_trait]
impl LlmClient for LeafcutterClient {
    async fn chat(&self, req: &Request) -> Result<Response> {
        let model = self.model.lock().unwrap_or_else(|e| e.into_inner()).clone();
        let body = build_leafcutter_request(model, req, false);
        let url = format!("{}/v1/chat/completions", self.base_url);
        let data = self.base.do_request("POST", &url, &[], Some(&body)).await?;
        let parsed: Value = serde_json::from_slice(&data).context("parsing leafcutter response")?;

        let mut result = Response {
            usage: Usage::default(),
            ..Default::default()
        };
        if let Some(usage) = parsed.get("usage") {
            result.usage.input_tokens =
                usage.get("prompt_tokens").and_then(|v| v.as_i64()).unwrap_or(0) as usize;
            result.usage.output_tokens =
                usage.get("completion_tokens").and_then(|v| v.as_i64()).unwrap_or(0) as usize;
        }
        if let Some(choices) = parsed.get("choices").and_then(|c| c.as_array()) {
            if let Some(first) = choices.first() {
                if let Some(content) = first.pointer("/message/content").and_then(|c| c.as_str()) {
                    result.content = content.to_string();
                }
            }
        }
        Ok(result)
    }

    fn chat_stream(&self, req: &Request, cancelled: Cancelled) -> StreamHandle {
        let (chunks_tx, chunks) = mpsc::unbounded_channel();
        let (errors_tx, errors) = mpsc::unbounded_channel();
        let model = self.model.lock().unwrap_or_else(|e| e.into_inner()).clone();
        let body = build_leafcutter_request(model.clone(), req, true);
        let url = format!("{}/v1/chat/completions", self.base_url);
        let http = self.base.http.clone();
        // Clone the request pieces for the non-streaming fallback.
        let fallback_req = req.clone();

        tokio::spawn(async move {
            let send_err = |tx: &mpsc::UnboundedSender<anyhow::Error>, e: anyhow::Error| {
                let _ = tx.send(e);
            };
            let resp = match http
                .post(&url)
                .header(reqwest::header::CONTENT_TYPE, "application/json")
                .header("Accept", "text/event-stream")
                .json(&body)
                .send()
                .await
            {
                Ok(r) => r,
                Err(e) => {
                    send_err(&errors_tx, anyhow!("leafcutter request failed: {e}"));
                    return;
                }
            };
            if !resp.status().is_success() {
                let status = resp.status();
                let body = resp.text().await.unwrap_or_default();
                send_err(
                    &errors_tx,
                    anyhow!("leafcutter HTTP {status}: {}", truncate(&body, 300)),
                );
                return;
            }

            // Leafcutter's native-streaming engine does not always honour
            // `stream: true` (and may close the connection abruptly), so read
            // the whole body, then handle SSE or fall back to a plain JSON
            // completion.
            let body = match resp.text().await {
                Ok(b) => b,
                Err(e) => {
                    send_err(&errors_tx, anyhow!("reading leafcutter response: {e}"));
                    return;
                }
            };
            if cancelled.load(std::sync::atomic::Ordering::Relaxed) {
                return;
            }

            let mut sse_seen = false;
            for line in body.lines() {
                if !line.starts_with("data: ") {
                    continue;
                }
                sse_seen = true;
                let data = line.trim_start_matches("data: ");
                if data == "[DONE]" {
                    break;
                }
                let parsed: Value = match serde_json::from_str(data) {
                    Ok(v) => v,
                    Err(_) => continue,
                };
                if let Some(content) = parsed
                    .pointer("/choices/0/delta/content")
                    .and_then(|c| c.as_str())
                {
                    if !content.is_empty() {
                        let _ = chunks_tx.send(content.to_string());
                    }
                }
            }

            if !sse_seen {
                // Non-SSE body: either a single chat.completion JSON or a
                // non-streaming fallback. Emit its content as one chunk.
                if let Some(content) = serde_json::from_str::<Value>(&body)
                    .ok()
                    .and_then(|v| v.pointer("/choices/0/message/content").and_then(|c| c.as_str()).map(|s| s.to_string()))
                {
                    if !content.is_empty() {
                        let _ = chunks_tx.send(content);
                    }
                    return;
                }
                // Nothing parseable from the stream: do a non-streaming
                // fallback request so the turn still completes.
                let fallback_body = build_leafcutter_request(
                    model.clone(),
                    &fallback_req,
                    false,
                );
                match http
                    .post(&url)
                    .header(reqwest::header::CONTENT_TYPE, "application/json")
                    .json(&fallback_body)
                    .send()
                    .await
                {
                    Ok(r) if r.status().is_success() => {
                        let text = match r.text().await {
                            Ok(t) => t,
                            Err(e) => {
                                send_err(&errors_tx, anyhow!("leafcutter fallback read: {e}"));
                                return;
                            }
                        };
                        match serde_json::from_str::<Value>(&text)
                            .ok()
                            .and_then(|v| v.pointer("/choices/0/message/content").and_then(|c| c.as_str()).map(|s| s.to_string()))
                        {
                            Some(content) if !content.is_empty() => {
                                let _ = chunks_tx.send(content);
                            }
                            _ => {
                                send_err(
                                    &errors_tx,
                                    anyhow!(
                                        "leafcutter stream produced no content: {}",
                                        truncate(&text, 300)
                                    ),
                                );
                            }
                        }
                    }
                    Ok(r) => {
                        let status = r.status();
                        let text = r.text().await.unwrap_or_default();
                        send_err(
                            &errors_tx,
                            anyhow!("leafcutter fallback HTTP {status}: {}", truncate(&text, 300)),
                        );
                    }
                    Err(e) => {
                        send_err(&errors_tx, anyhow!("leafcutter fallback request failed: {e}"));
                    }
                }
            }
        });

        StreamHandle { chunks, errors }
    }

    fn provider(&self) -> &'static str {
        "leafcutter"
    }

    fn current_model(&self) -> String {
        self.model.lock().unwrap_or_else(|e| e.into_inner()).clone()
    }
}

/// Minimal OpenAI-shaped leafcutter request (role/content messages only, no
/// tools, matching the Go client).
fn build_leafcutter_request(model: String, req: &Request, stream: bool) -> Value {
    let mut messages: Vec<Value> = Vec::new();
    if !req.system_prompt.is_empty() {
        messages.push(json!({"role": "system", "content": req.system_prompt}));
    }
    for m in &req.messages {
        messages.push(json!({"role": m.role.as_str(), "content": m.content}));
    }
    json!({
        "model": model,
        "max_tokens": req.max_tokens,
        "temperature": req.temperature,
        "messages": messages,
        "stream": stream,
    })
}

// ─── Helpers ────────────────────────────────────────────────────────────────

fn resolve_model_path(model_id: &str, models_dir: &str) -> Result<String> {
    if model_id.is_empty() {
        anyhow::bail!(
            "no local model path specified. Set model to a local model ID or absolute GGUF path"
        );
    }
    let rel = model_id.starts_with("hf:") || !std::path::Path::new(model_id).is_absolute();
    if !rel {
        let p = std::path::Path::new(model_id);
        if !p.exists() {
            anyhow::bail!("model file not found: {model_id}");
        }
        if p.is_dir() {
            anyhow::bail!("model path is a directory (expected a GGUF file): {model_id}");
        }
        return Ok(model_id.to_string());
    }

    // Relative / HF id: scan `models_dir` for a matching GGUF by file stem or
    // parent directory name. Full HuggingFace registry is v2 scope.
    if !models_dir.is_empty() {
        let root = std::path::Path::new(models_dir);
        if root.is_dir() {
            let want = model_id
                .trim_start_matches("hf:")
                .to_lowercase();
            let mut found: Option<std::path::PathBuf> = None;
            if let Ok(mut walk) = std::fs::read_dir(root) {
                while let Some(Ok(ent)) = walk.next() {
                    let p = ent.path();
                    if p.is_file() {
                        let name = p.file_name().and_then(|n| n.to_str()).unwrap_or("").to_lowercase();
                        if name.ends_with(".gguf")
                            && (p.file_stem().and_then(|s| s.to_str()).unwrap_or("").to_lowercase()
                                .contains(&want)
                                || name.contains(&want))
                        {
                            found = Some(p);
                            break;
                        }
                    } else if p.is_dir() {
                        let dir = p.file_name().and_then(|n| n.to_str()).unwrap_or("").to_lowercase();
                        if dir.contains(&want) || want.contains(&dir) && !want.is_empty() {
                            if let Ok(entries) = std::fs::read_dir(&p) {
                                for e in entries.flatten() {
                                    let fp = e.path();
                                    if fp.is_file()
                                        && fp.extension().and_then(|x| x.to_str()) == Some("gguf")
                                    {
                                        found = Some(fp);
                                        break;
                                    }
                                }
                            }
                        }
                    }
                    if found.is_some() {
                        break;
                    }
                }
            }
            if let Some(p) = found {
                return Ok(p.to_string_lossy().into_owned());
            }
        }
    }
    anyhow::bail!("model file not found: {model_id}")
}

/// Locate the leafcutter binary in PATH or known install locations.
fn find_leafcutter() -> String {
    for dir in std::env::var("PATH").unwrap_or_default().split(':') {
        let candidate = std::path::Path::new(dir).join("leafcutter");
        if candidate.is_file() {
            return candidate.to_string_lossy().into_owned();
        }
    }
    let home = dirs::home_dir().unwrap_or_default();
    let candidates = [
        home.join(".local/bin/leafcutter"),
        home.join(".leafcutter/LeafcutterLLM/rust/target/release/leafcutter"),
        std::path::PathBuf::from("/usr/local/bin/leafcutter"),
        std::path::PathBuf::from("./leafcutter"),
    ];
    for c in candidates {
        if c.is_file() {
            return c.to_string_lossy().into_owned();
        }
    }
    String::new()
}

/// Grab an ephemeral free port by binding a listener and releasing it.
fn find_free_port() -> Option<u16> {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").ok()?;
    let port = listener.local_addr().ok()?.port();
    Some(port)
}

/// Poll the address until the leafcutter server accepts connections.
fn wait_for_server(addr: &str, timeout: Duration) -> Result<()> {
    let url = url::Url::parse(addr)
        .with_context(|| format!("invalid leafcutter address: {addr}"))?;
    let host = url
        .host_str()
        .context("leafcutter address missing host")?
        .to_string();
    let port = url
        .port()
        .context("leafcutter address missing port")?;
    let socket: std::net::SocketAddr = format!("{host}:{port}")
        .parse()
        .with_context(|| format!("parsing leafcutter address: {addr}"))?;

    let deadline = Instant::now() + timeout;
    loop {
        if std::net::TcpStream::connect_timeout(&socket, Duration::from_millis(200)).is_ok() {
            return Ok(());
        }
        if Instant::now() >= deadline {
            break;
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    anyhow::bail!("timed out waiting for server at {addr}")
}

fn truncate(s: &str, n: usize) -> String {
    let mut out: String = s.chars().take(n).collect();
    if s.chars().count() > n {
        out.push_str("…");
    }
    out
}