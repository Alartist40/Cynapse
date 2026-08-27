//! HTTP API server using Axum — Direct llama.cpp FFI backend OR Native Streaming
//!
//! Dual-wire compatibility server supporting both native Ollama `/api/*` endpoints
//! (NDJSON streaming) and OpenAI `/v1/*` endpoints (SSE streaming).

pub mod ollama_routes;
pub mod types;

use axum::{
    body::Body,
    extract::State,
    http::{HeaderMap, StatusCode},
    middleware,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;

use crate::inference::engine::Engine as NativeEngine;
use crate::model::scheduler::ModelScheduler;
use crate::profiles::{render_chat_prompt, resolve_profile};
use crate::tokenizer::GgufBpeTokenizer;
use tokio_stream::StreamExt;

#[cfg(feature = "llama-ffi")]
use crate::llama_ffi::{backend_init, LlamaContext, LlamaModel};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
pub struct GenerateRequest {
    pub prompt: String,
    #[serde(default = "default_max_tokens")]
    pub max_tokens: usize,
    #[serde(default = "default_temperature")]
    pub temperature: f32,
    #[serde(default = "default_top_p")]
    pub top_p: f32,
}

fn default_max_tokens() -> usize {
    256
}
fn default_temperature() -> f32 {
    0.7
}
fn default_top_p() -> f32 {
    0.9
}

#[derive(Serialize, Deserialize)]
pub struct GenerateResponse {
    pub id: String,
    #[serde(skip_serializing_if = "String::is_empty", default)]
    pub text: String,
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub tokens: Vec<usize>,
    pub took_ms: i64,
    #[serde(skip_serializing_if = "String::is_empty", default)]
    pub error: String,
}

#[derive(Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
    pub engine: String,
}

#[derive(Debug, Deserialize)]
pub struct ChatCompletionRequest {
    pub model: String,
    pub messages: Vec<ChatMessage>,
    #[serde(default = "default_max_tokens")]
    pub max_tokens: usize,
    #[serde(default = "default_temperature")]
    pub temperature: f32,
    #[serde(default = "default_top_p")]
    pub top_p: f32,
    #[serde(default)]
    pub stream: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatCompletionResponse {
    pub id: String,
    pub object: String,
    pub created: u64,
    pub model: String,
    pub choices: Vec<Choice>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Choice {
    pub index: usize,
    pub message: ChatMessage,
    pub finish_reason: String,
}

// ---------------------------------------------------------------------------
// Unified Engine Trait
// ---------------------------------------------------------------------------

pub trait LeafcutterEngine: Send + Sync {
    fn generate(
        &self,
        prompt: &str,
        max_tokens: usize,
        temperature: f32,
        top_p: f32,
    ) -> Result<(String, Vec<usize>), String>;
    fn generate_streaming(
        &self,
        prompt: &str,
        max_tokens: usize,
        temperature: f32,
        top_p: f32,
        on_token: Box<dyn FnMut(&str) -> bool + Send>,
    ) -> Result<(), String>;
    fn name(&self) -> &str;
    fn max_seq_len(&self) -> usize;
}

pub type SharedEngine = Arc<dyn LeafcutterEngine>;

async fn auth_middleware(
    req: axum::extract::Request,
    next: axum::middleware::Next,
) -> axum::response::Response {
    let key = std::env::var("LEAFCUTTER_API_KEY").unwrap_or_default();
    if key.is_empty() {
        return next.run(req).await;
    }
    match req.headers().get("X-API-Key") {
        Some(v) if v.to_str().map(|s| s == key).unwrap_or(false) => next.run(req).await,
        _ => axum::response::Response::builder()
            .status(StatusCode::UNAUTHORIZED)
            .body(Body::from("Missing or invalid X-API-Key header"))
            .unwrap(),
    }
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

pub async fn generate_handler(
    State(state): State<ollama_routes::ApiState>,
    Json(req): Json<GenerateRequest>,
) -> Result<Json<GenerateResponse>, (StatusCode, String)> {
    let start = Instant::now();
    let id = format!(
        "req-{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0)
    );

    let text = state
        .scheduler
        .with_engine("default", None, |engine| {
            let tok = GgufBpeTokenizer::from_gguf(&engine.gguf_path);
            let tokens = tok.as_ref().map(|t| t.encode(&req.prompt)).unwrap_or_default();
            let gen = engine.generate(&tokens, req.max_tokens, req.temperature, req.top_p);
            tok.as_ref().map(|t| t.decode(&gen)).unwrap_or_default()
        })
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e))?;

    Ok(Json(GenerateResponse {
        id,
        text,
        tokens: Vec::new(),
        took_ms: start.elapsed().as_millis() as i64,
        error: String::new(),
    }))
}

pub async fn health_handler(
    State(state): State<ollama_routes::ApiState>,
) -> Json<HealthResponse> {
    let active_name = state
        .scheduler
        .currently_loaded()
        .map(|(n, _, _)| n)
        .unwrap_or_else(|| "standby".to_string());

    Json(HealthResponse {
        status: "ok".to_string(),
        version: format!("v{}", env!("CARGO_PKG_VERSION")),
        engine: active_name,
    })
}

pub async fn chat_completions_handler(
    State(state): State<ollama_routes::ApiState>,
    Json(req): Json<ChatCompletionRequest>,
) -> Result<axum::response::Response, (StatusCode, String)> {
    use axum::response::IntoResponse;

    let mut system_prompt = String::new();
    let mut history = Vec::new();
    for m in &req.messages {
        if m.role == "system" {
            if !system_prompt.contains(&m.content) {
                if !system_prompt.is_empty() {
                    system_prompt.push('\n');
                }
                system_prompt.push_str(&m.content);
            }
        } else {
            history.push((m.role.clone(), m.content.clone()));
        }
    }

    let profile = resolve_profile(&HashMap::new(), Some(&req.model));
    let prompt = render_chat_prompt(&profile, &system_prompt, &history);
    let requested_max = if req.max_tokens == 0 { 1024 } else { req.max_tokens };
    let model_name = req.model.clone();

    if req.stream {
        let (tx, rx) = tokio::sync::mpsc::channel::<String>(128);
        let req_id = format!("chatcmpl-{}", uuid::Uuid::new_v4());
        let created = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let scheduler = state.scheduler.clone();
        tokio::task::spawn_blocking(move || {
            let req_id_clone = req_id.clone();
            let model_name_clone = model_name.clone();
            let tx_clone = tx.clone();

            let _ = scheduler.with_engine(&model_name_clone, None, |engine| {
                let tok = GgufBpeTokenizer::from_gguf(&engine.gguf_path);
                let tokens = tok
                    .as_ref()
                    .map(|t| t.encode(&prompt))
                    .filter(|t| !t.is_empty())
                    .unwrap_or_else(|| engine.tokenize(&prompt, true));
                let stop_token_ids: Vec<usize> = profile.stop_tokens.iter().map(|s| s.0).collect();

                engine.generate_streaming_with_stops(
                    &tokens,
                    requested_max,
                    req.temperature,
                    req.top_p,
                    &stop_token_ids,
                    |_id, piece| {
                        let json_chunk = serde_json::json!({
                            "id": req_id_clone,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_name_clone,
                            "choices": [{
                                "index": 0,
                                "delta": { "content": piece },
                                "finish_reason": null
                            }]
                        });
                        tx_clone.blocking_send(json_chunk.to_string()).is_ok()
                    },
                );
            });
            let _ = tx.blocking_send("[DONE]".to_string());
        });

        use axum::response::sse::Event;
        let stream = tokio_stream::wrappers::ReceiverStream::new(rx)
            .map(|data| Ok::<_, std::convert::Infallible>(Event::default().data(data)));
        return Ok(axum::response::Sse::new(stream).into_response());
    }

    let text = state
        .scheduler
        .with_engine(&model_name, None, |engine| {
            let tok = GgufBpeTokenizer::from_gguf(&engine.gguf_path);
            let tokens = tok
                .as_ref()
                .map(|t| t.encode(&prompt))
                .filter(|t| !t.is_empty())
                .unwrap_or_else(|| engine.tokenize(&prompt, true));
            let gen = engine.generate(&tokens, requested_max, req.temperature, req.top_p);
            tok.as_ref().map(|t| t.decode(&gen)).unwrap_or_else(|| engine.decode(&gen))
        })
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e))?;

    let resp = ChatCompletionResponse {
        id: format!("chatcmpl-{}", uuid::Uuid::new_v4()),
        object: "chat.completion".to_string(),
        created: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs(),
        model: req.model,
        choices: vec![Choice {
            index: 0,
            message: ChatMessage {
                role: "assistant".to_string(),
                content: text,
            },
            finish_reason: "stop".to_string(),
        }],
    };

    Ok(Json(resp).into_response())
}

pub fn create_app() -> Router {
    let key = std::env::var("LEAFCUTTER_API_KEY").unwrap_or_default();
    if !key.is_empty() {
        println!("🔐 Auth enabled — send X-API-Key header on all requests");
    } else {
        println!("🔓 Auth disabled (LEAFCUTTER_API_KEY not set) — server is open");
    }

    let scheduler = ModelScheduler::new();
    let api_state = ollama_routes::ApiState { scheduler };

    Router::new()
        .route("/health", get(health_handler))
        .route("/generate", post(generate_handler))
        .route("/v1/chat/completions", post(chat_completions_handler))
        .route("/v1/models", get(ollama_routes::api_tags_handler))
        .route("/api/version", get(ollama_routes::api_version_handler))
        .route("/api/tags", get(ollama_routes::api_tags_handler))
        .route("/api/ps", get(ollama_routes::api_ps_handler))
        .route("/api/show", post(ollama_routes::api_show_handler))
        .route("/api/chat", post(ollama_routes::api_chat_handler))
        .route("/api/generate", post(ollama_routes::api_generate_handler))
        .with_state(api_state)
        .layer(middleware::from_fn(auth_middleware))
}

pub async fn run_server(_engine: Option<SharedEngine>, port: u16, host: &str) {
    let app = create_app();
    let addr = format!("{}:{}", host, port);
    println!("🚀 Leafcutter server listening on http://{}", addr);

    let listener = match tokio::net::TcpListener::bind(&addr).await {
        Ok(l) => l,
        Err(e) => {
            eprintln!("❌ Failed to bind to {}: {}", addr, e);
            std::process::exit(1);
        }
    };
    if let Err(e) = axum::serve(listener, app).await {
        eprintln!("❌ Server error: {}", e);
        std::process::exit(1);
    }
}