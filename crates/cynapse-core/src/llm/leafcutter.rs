use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use anyhow::{anyhow, Context as _, Result};
use async_trait::async_trait;
use tokio::sync::mpsc;

use leafcutter::inference::engine::Engine;
use leafcutter::model::gguf::GGUFile;
use leafcutter::profiles::{render_chat_prompt, resolve_profile};
use leafcutter::tokenizer::gguf::GgufBpeTokenizer;

use crate::config::LlmConfig;
use crate::llm::providers::{BaseClient, Cancelled, LlmClient, StreamHandle};
use crate::llm::{Request, Response, Usage};

/// Embedded native Leafcutter engine client (in-process).
pub struct LeafcutterClient {
    base: BaseClient,
    models_dir: String,
    model_name: Mutex<String>,
}

pub(crate) fn new(base: BaseClient, cfg: &LlmConfig) -> Result<Arc<dyn LlmClient>> {
    let instance = LeafcutterClient {
        base,
        models_dir: cfg.models_dir.clone(),
        model_name: Mutex::new(cfg.model.clone()),
    };
    Ok(Arc::new(instance))
}

#[async_trait]
impl LlmClient for LeafcutterClient {
    async fn chat(&self, req: &Request) -> Result<Response> {
        let stream = self.chat_stream(req, Cancelled::default());
        let mut full_text = String::new();
        let mut rx = stream.chunks;
        while let Some(chunk) = rx.recv().await {
            full_text.push_str(&chunk);
        }
        Ok(Response {
            content: full_text,
            thinking: String::new(),
            usage: Usage::default(),
            tool_calls: Vec::new(),
        })
    }

    fn chat_stream(&self, req: &Request, cancelled: Cancelled) -> StreamHandle {
        let (chunks_tx, chunks) = mpsc::unbounded_channel();
        let (errors_tx, errors) = mpsc::unbounded_channel();

        let model_id = self.model_name.lock().unwrap_or_else(|e| e.into_inner()).clone();
        let models_dir = self.models_dir.clone();

        let model_path = match resolve_model_path(&model_id, &models_dir) {
            Ok(p) => PathBuf::from(p),
            Err(e) => {
                let _ = errors_tx.send(e);
                return StreamHandle { chunks, errors };
            }
        };

        // Extract history turns from req.messages
        let mut history: Vec<(String, String)> = Vec::new();
        for m in &req.messages {
            if m.role.as_str() != "system" {
                history.push((m.role.as_str().to_string(), m.content.clone()));
            }
        }
        let system_prompt = req.system_prompt.clone();
        let requested_max = if req.max_tokens == 0 { 1024 } else { req.max_tokens } as usize;
        let temperature = req.temperature as f32;

        tokio::task::spawn_blocking(move || {
            let send_err = |tx: &mpsc::UnboundedSender<anyhow::Error>, e: anyhow::Error| {
                let _ = tx.send(e);
            };

            let path_str = match model_path.to_str() {
                Some(p) => p,
                None => {
                    send_err(&errors_tx, anyhow!("invalid model path: {}", model_path.display()));
                    return;
                }
            };

            static ENGINE_CACHE: std::sync::OnceLock<Mutex<Option<(String, Engine)>>> = std::sync::OnceLock::new();
            let cache_mutex = ENGINE_CACHE.get_or_init(|| Mutex::new(None));
            let mut guard = cache_mutex.lock().unwrap_or_else(|e| e.into_inner());

            let engine = match guard.as_mut() {
                Some((loaded_path, eng)) if loaded_path == path_str => eng,
                _ => {
                    let new_eng = match Engine::load(path_str) {
                        Ok(e) => e,
                        Err(e) => {
                            send_err(&errors_tx, anyhow!("failed to load embedded leafcutter engine: {e}"));
                            return;
                        }
                    };
                    *guard = Some((path_str.to_string(), new_eng));
                    &mut guard.as_mut().unwrap().1
                }
            };

            let gguf = GGUFile::open(path_str).ok();
            let profile = resolve_profile(
                &gguf.as_ref().map(|f| &f.metadata).cloned().unwrap_or_default(),
                None,
            );

            let prompt_text = render_chat_prompt(&profile, &system_prompt, &history);
            let tok = GgufBpeTokenizer::from_gguf(&engine.gguf_path);
            let tokens = tok
                .as_ref()
                .map(|t| t.encode(&prompt_text))
                .filter(|t| !t.is_empty())
                .unwrap_or_else(|| engine.tokenize(&prompt_text, true));

            if tokens.is_empty() {
                send_err(&errors_tx, anyhow!("empty tokenized prompt"));
                return;
            }

            let stop_token_ids: Vec<usize> = profile.stop_tokens.iter().map(|s| s.0).collect();

            engine.generate_streaming_with_stops(
                &tokens,
                requested_max,
                temperature,
                profile.sampling.top_p,
                &stop_token_ids,
                |_id, piece| {
                    if cancelled.load(std::sync::atomic::Ordering::Relaxed) {
                        return false;
                    }
                    let _ = chunks_tx.send(piece.to_string());
                    true
                },
            );
        });

        StreamHandle { chunks, errors }
    }

    fn provider(&self) -> &'static str {
        "leafcutter"
    }

    fn current_model(&self) -> String {
        self.model_name.lock().unwrap_or_else(|e| e.into_inner()).clone()
    }

    fn set_model(&self, model: &str) {
        if let Ok(mut m) = self.model_name.lock() {
            *m = model.to_string();
        }
    }
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