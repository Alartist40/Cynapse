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

static ENGINE_CACHE: std::sync::OnceLock<Mutex<Option<(String, Engine)>>> = std::sync::OnceLock::new();

fn get_engine_cache() -> &'static Mutex<Option<(String, Engine)>> {
    ENGINE_CACHE.get_or_init(|| Mutex::new(None))
}

/// Pre-load and pre-fault the GGUF model in the background at CLI bootup so
/// prompt 1 token generation starts instantly (<10ms).
pub fn prewarm_leafcutter_engine(cfg: &LlmConfig) {
    let model_id = cfg.model.clone();
    let models_dir = cfg.models_dir.clone();
    if let Ok(model_path) = resolve_model_path(&model_id, &models_dir) {
        tokio::task::spawn_blocking(move || {
            let cache_mutex = get_engine_cache();
            let mut guard = cache_mutex.lock().unwrap_or_else(|e| e.into_inner());
            if guard.is_none() {
                if let Ok(new_eng) = Engine::load(&model_path) {
                    *guard = Some((model_path, new_eng));
                }
            }
        });
    }
}

#[derive(Debug, Clone)]
pub struct ModelStatus {
    pub loaded: bool,
    pub path: Option<String>,
}

/// Explicitly load a model file or HuggingFace ID into RAM memory cache.
pub fn load_engine_model(target: &str, models_dir: &str) -> Result<ModelStatus> {
    let resolved_path = resolve_model_path(target, models_dir)?;
    let cache_mutex = get_engine_cache();
    let mut guard = cache_mutex.lock().unwrap_or_else(|e| e.into_inner());

    if let Some((ref loaded_path, _)) = *guard {
        if loaded_path == &resolved_path {
            return Ok(ModelStatus {
                loaded: true,
                path: Some(resolved_path),
            });
        }
    }

    let new_eng = Engine::load(&resolved_path).map_err(|e| anyhow!("{e}"))?;
    *guard = Some((resolved_path.clone(), new_eng));

    Ok(ModelStatus {
        loaded: true,
        path: Some(resolved_path),
    })
}

/// Unload and free any loaded model from RAM.
pub fn unload_engine_model() -> bool {
    let cache_mutex = get_engine_cache();
    let mut guard = cache_mutex.lock().unwrap_or_else(|e| e.into_inner());
    let had_model = guard.is_some();
    *guard = None;
    had_model
}

/// Get current loaded engine memory status.
pub fn get_engine_status() -> ModelStatus {
    let cache_mutex = get_engine_cache();
    let guard = cache_mutex.lock().unwrap_or_else(|e| e.into_inner());
    if let Some((ref path, _)) = *guard {
        ModelStatus {
            loaded: true,
            path: Some(path.clone()),
        }
    } else {
        ModelStatus {
            loaded: false,
            path: None,
        }
    }
}

/// List cached models in local model directories (`~/.cache/cynapse/models/` and configured models_dir).
pub fn list_cached_models(models_dir: &str) -> Vec<(String, u64)> {
    let mut results = Vec::new();
    let mut dirs_to_check = vec![PathBuf::from(models_dir)];
    if let Some(user_cache) = dirs::cache_dir() {
        dirs_to_check.push(user_cache.join("cynapse").join("models"));
    }

    for dir in dirs_to_check {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_file() && path.extension().and_then(|e| e.to_str()) == Some("gguf") {
                    let size = entry.metadata().map(|m| m.len()).unwrap_or(0);
                    let name = path.file_name().unwrap_or_default().to_string_lossy().to_string();
                    results.push((name, size));
                }
            }
        }
    }

    results.sort_by(|a, b| a.0.cmp(&b.0));
    results.dedup_by(|a, b| a.0 == b.0);
    results
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

        // Extract user message and history turns from req.messages
        let mut history: Vec<(String, String)> = Vec::new();
        let mut user_msg = String::new();

        for m in &req.messages {
            if m.role.as_str() == "user" {
                if !user_msg.is_empty() {
                    history.push(("user".to_string(), user_msg));
                }
                user_msg = m.content.clone();
            } else if m.role.as_str() == "assistant" {
                history.push(("assistant".to_string(), m.content.clone()));
            }
        }

        if user_msg.is_empty() {
            if let Some(last) = req.messages.last() {
                user_msg = last.content.clone();
            }
        }

        if history.len() > 4 {
            history = history[history.len() - 4..].to_vec();
        }

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

            let cache_mutex = get_engine_cache();
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

            let prompt_text = render_chat_prompt(&profile, &user_msg, &history);
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

    // Direct HuggingFace URI or repo@quant identifier
    if model_id.starts_with("hf:") || (model_id.contains('/') && !model_id.starts_with('.')) {
        if let Ok(path) = crate::hf::download_hf_model(model_id) {
            return Ok(path.to_string_lossy().into_owned());
        }
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

    let mut search_dirs = vec![
        models_dir.to_string(),
        "./models".into(),
        "../models".into(),
        "../../models".into(),
        "~/Downloads/models".into(),
        "~/Downloads".into(),
        "~/models".into(),
        "~/.leafcutter/models".into(),
        "~/.cache/cynapse/models".into(),
        "~/.cynapse/models".into(),
    ];
    if let Ok(home) = std::env::var("HOME") {
        search_dirs.push(format!("{home}/Downloads/models"));
        search_dirs.push(format!("{home}/Downloads"));
        search_dirs.push(format!("{home}/models"));
    }

    let want = model_id.trim_start_matches("hf:").to_lowercase();
    for dir_str in search_dirs {
        if dir_str.trim().is_empty() {
            continue;
        }
        let expanded = if let Some(stripped) = dir_str.strip_prefix("~/") {
            if let Ok(home) = std::env::var("HOME") {
                format!("{home}/{stripped}")
            } else {
                dir_str
            }
        } else {
            dir_str
        };
        let root = std::path::Path::new(&expanded);
        if root.is_dir() {
            let candidate = root.join(model_id);
            if candidate.exists() && candidate.is_file() {
                return Ok(candidate.to_string_lossy().into_owned());
            }
            if let Ok(entries) = std::fs::read_dir(root) {
                for ent in entries.flatten() {
                    let p = ent.path();
                    if p.is_file() {
                        let name = p.file_name().and_then(|n| n.to_str()).unwrap_or("").to_lowercase();
                        if name.ends_with(".gguf") && (name.contains(&want) || p.file_stem().and_then(|s| s.to_str()).unwrap_or("").to_lowercase().contains(&want)) {
                            return Ok(p.to_string_lossy().into_owned());
                        }
                    }
                }
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