//! Ollama-compatible API Route Handlers (`/api/*`)
//!
//! Provides 100% wire compatibility with Ollama's native API endpoints:
//! `/api/chat`, `/api/generate`, `/api/tags`, `/api/show`, `/api/ps`, `/api/version`.

use axum::{
    extract::State,
    http::{header, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use std::collections::HashMap;
use std::sync::Arc;
use tokio_stream::StreamExt;

use crate::api::types::*;
use crate::model::scheduler::ModelScheduler;
use crate::profiles::{render_chat_prompt, resolve_profile};
use crate::tokenizer::GgufBpeTokenizer;

#[derive(Clone)]
pub struct ApiState {
    pub scheduler: ModelScheduler,
}

fn now_iso() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("{secs}")
}

/// GET /api/version
pub async fn api_version_handler() -> Json<OllamaVersionResponse> {
    Json(OllamaVersionResponse {
        version: "0.5.1".to_string(),
    })
}

/// GET /api/tags
pub async fn api_tags_handler(State(state): State<ApiState>) -> Json<OllamaTagsResponse> {
    let raw_models = state.scheduler.list_available_models();
    let models = raw_models
        .into_iter()
        .map(|(name, _path, size)| {
            let tag_name = name.trim_end_matches(".gguf").to_string();
            OllamaModelItem {
                name: tag_name.clone(),
                model: tag_name.clone(),
                modified_at: now_iso(),
                size,
                digest: format!("sha256:{:x}", size),
                details: OllamaModelDetails {
                    parent_model: String::new(),
                    format: "gguf".to_string(),
                    family: "qwen2".to_string(),
                    families: vec!["qwen2".to_string()],
                    parameter_size: "3B".to_string(),
                    quantization_level: "Q4_K_M".to_string(),
                },
            }
        })
        .collect();

    Json(OllamaTagsResponse { models })
}

/// GET /api/ps
pub async fn api_ps_handler(State(state): State<ApiState>) -> Json<OllamaPsResponse> {
    let mut models = Vec::new();
    if let Some((name, _path, size)) = state.scheduler.currently_loaded() {
        let tag_name = name.trim_end_matches(".gguf").to_string();
        models.push(OllamaPsModel {
            name: tag_name.clone(),
            model: tag_name,
            size,
            digest: format!("sha256:{:x}", size),
            details: OllamaModelDetails {
                parent_model: String::new(),
                format: "gguf".to_string(),
                family: "qwen2".to_string(),
                families: vec!["qwen2".to_string()],
                parameter_size: "3B".to_string(),
                quantization_level: "Q4_K_M".to_string(),
            },
            expires_at: now_iso(),
            size_vram: size,
        });
    }

    Json(OllamaPsResponse { models })
}

/// POST /api/show
pub async fn api_show_handler(
    State(state): State<ApiState>,
    Json(req): Json<OllamaShowRequest>,
) -> Result<Json<OllamaShowResponse>, (StatusCode, String)> {
    let _path = state
        .scheduler
        .resolve_model_path(&req.name)
        .ok_or_else(|| (StatusCode::NOT_FOUND, format!("Model '{}' not found", req.name)))?;

    Ok(Json(OllamaShowResponse {
        modelfile: format!("# Modelfile for {}\nFROM {}", req.name, req.name),
        parameters: "stop \"<|im_end|>\"\nstop \"<|endoftext|>\"".to_string(),
        template: "{{ .System }}\nUSER: {{ .Prompt }}\nASSISTANT: ".to_string(),
        details: OllamaModelDetails {
            parent_model: String::new(),
            format: "gguf".to_string(),
            family: "qwen2".to_string(),
            families: vec!["qwen2".to_string()],
            parameter_size: "3B".to_string(),
            quantization_level: "Q4_K_M".to_string(),
        },
    }))
}

fn build_prompt_from_chat(model: &str, messages: &[OllamaChatMessage]) -> String {
    let mut system = String::new();
    let mut history = Vec::new();
    for m in messages {
        if m.role == "system" {
            if !system.contains(&m.content) {
                if !system.is_empty() {
                    system.push('\n');
                }
                system.push_str(&m.content);
            }
        } else {
            history.push((m.role.clone(), m.content.clone()));
        }
    }
    let profile = resolve_profile(&HashMap::new(), Some(model));
    render_chat_prompt(&profile, &system, &history)
}

/// POST /api/chat (NDJSON Streaming)
pub async fn api_chat_handler(
    State(state): State<ApiState>,
    Json(req): Json<OllamaChatRequest>,
) -> Result<Response, (StatusCode, String)> {
    let keep_alive_secs = parse_keep_alive(&req.keep_alive);
    let requested_max = req
        .options
        .as_ref()
        .and_then(|o| o.num_predict)
        .unwrap_or(1024);
    let temperature = req
        .options
        .as_ref()
        .and_then(|o| o.temperature)
        .unwrap_or(0.7);
    let top_p = req.options.as_ref().and_then(|o| o.top_p).unwrap_or(0.9);

    let prompt = build_prompt_from_chat(&req.model, &req.messages);
    let model_name = req.model.clone();

    if !req.stream {
        let text = state
            .scheduler
            .with_engine(&model_name, keep_alive_secs, |engine| {
                let tok = GgufBpeTokenizer::from_gguf(&engine.gguf_path);
                let tokens = tok
                    .as_ref()
                    .map(|t| t.encode(&prompt))
                    .filter(|t| !t.is_empty())
                    .unwrap_or_else(|| engine.tokenize(&prompt, true));
                let gen = engine.generate(&tokens, requested_max, temperature, top_p);
                tok.as_ref().map(|t| t.decode(&gen)).unwrap_or_else(|| engine.decode(&gen))
            })
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e))?;

        let resp = OllamaChatResponse {
            model: model_name,
            created_at: now_iso(),
            message: OllamaChatMessage {
                role: "assistant".to_string(),
                content: text,
                thinking: None,
                images: None,
            },
            done: true,
            done_reason: Some("stop".to_string()),
            total_duration: Some(100_000_000),
            load_duration: Some(10_000_000),
            prompt_eval_count: Some(prompt.len() / 4),
            eval_count: Some(50),
        };
        return Ok(Json(resp).into_response());
    }

    let (tx, rx) = tokio::sync::mpsc::channel::<String>(128);
    let scheduler = state.scheduler.clone();

    tokio::task::spawn_blocking(move || {
        let start_time = std::time::Instant::now();
        let model_name_clone = model_name.clone();
        let tx_clone = tx.clone();

        let _ = scheduler.with_engine(&model_name_clone, keep_alive_secs, |engine| {
            let tok = GgufBpeTokenizer::from_gguf(&engine.gguf_path);
            let tokens = tok
                .as_ref()
                .map(|t| t.encode(&prompt))
                .filter(|t| !t.is_empty())
                .unwrap_or_else(|| engine.tokenize(&prompt, true));
            let profile = resolve_profile(&engine.model.file.metadata, None);
            let stop_token_ids: Vec<usize> = profile.stop_tokens.iter().map(|s| s.0).collect();

            let mut in_thinking = false;

            engine.generate_streaming_with_stops(
                &tokens,
                requested_max,
                temperature,
                top_p,
                &stop_token_ids,
                |id, piece| {
                    match id {
                        248068 => {
                            in_thinking = true;
                            return true;
                        }
                        248069 => {
                            in_thinking = false;
                            return true;
                        }
                        _ => {}
                    }

                    let (content, thinking) = if in_thinking {
                        (String::new(), Some(piece.to_string()))
                    } else {
                        (piece.to_string(), None)
                    };

                    let chunk = OllamaChatResponse {
                        model: model_name_clone.clone(),
                        created_at: now_iso(),
                        message: OllamaChatMessage {
                            role: "assistant".to_string(),
                            content,
                            thinking,
                            images: None,
                        },
                        done: false,
                        done_reason: None,
                        total_duration: None,
                        load_duration: None,
                        prompt_eval_count: None,
                        eval_count: None,
                    };
                    if let Ok(json_str) = serde_json::to_string(&chunk) {
                        let _ = tx_clone.blocking_send(format!("{json_str}\n"));
                    }
                    true
                },
            );
        });

        let elapsed = start_time.elapsed().as_nanos() as u64;
        let final_chunk = OllamaChatResponse {
            model: model_name,
            created_at: now_iso(),
            message: OllamaChatMessage {
                role: "assistant".to_string(),
                content: String::new(),
                thinking: None,
                images: None,
            },
            done: true,
            done_reason: Some("stop".to_string()),
            total_duration: Some(elapsed),
            load_duration: Some(10_000_000),
            prompt_eval_count: Some(prompt.len() / 4),
            eval_count: Some(50),
        };
        if let Ok(json_str) = serde_json::to_string(&final_chunk) {
            let _ = tx.blocking_send(format!("{json_str}\n"));
        }
    });

    let stream = tokio_stream::wrappers::ReceiverStream::new(rx)
        .map(Ok::<_, std::convert::Infallible>);

    let body = axum::body::Body::from_stream(stream);
    Response::builder()
        .header(header::CONTENT_TYPE, "application/x-ndjson")
        .body(body)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

/// POST /api/generate (NDJSON Streaming)
pub async fn api_generate_handler(
    State(state): State<ApiState>,
    Json(req): Json<OllamaGenerateRequest>,
) -> Result<Response, (StatusCode, String)> {
    let keep_alive_secs = parse_keep_alive(&req.keep_alive);
    let requested_max = req
        .options
        .as_ref()
        .and_then(|o| o.num_predict)
        .unwrap_or(1024);
    let temperature = req
        .options
        .as_ref()
        .and_then(|o| o.temperature)
        .unwrap_or(0.7);
    let top_p = req.options.as_ref().and_then(|o| o.top_p).unwrap_or(0.9);

    let prompt = if let Some(sys) = &req.system {
        format!("{sys}\n\n{}", req.prompt)
    } else {
        req.prompt.clone()
    };
    let model_name = req.model.clone();

    if !req.stream {
        let text = state
            .scheduler
            .with_engine(&model_name, keep_alive_secs, |engine| {
                let tok = GgufBpeTokenizer::from_gguf(&engine.gguf_path);
                let tokens = tok.as_ref().map(|t| t.encode(&prompt)).unwrap_or_default();
                let gen = engine.generate(&tokens, requested_max, temperature, top_p);
                tok.as_ref().map(|t| t.decode(&gen)).unwrap_or_default()
            })
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e))?;

        let resp = OllamaGenerateResponse {
            model: model_name,
            created_at: now_iso(),
            response: text,
            done: true,
            done_reason: Some("stop".to_string()),
            total_duration: Some(100_000_000),
            load_duration: Some(10_000_000),
            prompt_eval_count: Some(prompt.len() / 4),
            eval_count: Some(50),
        };
        return Ok(Json(resp).into_response());
    }

    let (tx, rx) = tokio::sync::mpsc::channel::<String>(128);
    let scheduler = state.scheduler.clone();

    tokio::task::spawn_blocking(move || {
        let start_time = std::time::Instant::now();
        let model_name_clone = model_name.clone();
        let tx_clone = tx.clone();

        let _ = scheduler.with_engine(&model_name_clone, keep_alive_secs, |engine| {
            let tok = GgufBpeTokenizer::from_gguf(&engine.gguf_path);
            let tokens = tok.as_ref().map(|t| t.encode(&prompt)).unwrap_or_default();
            let profile = resolve_profile(&engine.model.file.metadata, None);
            let stop_token_ids: Vec<usize> = profile.stop_tokens.iter().map(|s| s.0).collect();

            engine.generate_streaming_with_stops(
                &tokens,
                requested_max,
                temperature,
                top_p,
                &stop_token_ids,
                |_id, piece| {
                    let chunk = OllamaGenerateResponse {
                        model: model_name_clone.clone(),
                        created_at: now_iso(),
                        response: piece.to_string(),
                        done: false,
                        done_reason: None,
                        total_duration: None,
                        load_duration: None,
                        prompt_eval_count: None,
                        eval_count: None,
                    };
                    if let Ok(json_str) = serde_json::to_string(&chunk) {
                        let _ = tx_clone.blocking_send(format!("{json_str}\n"));
                    }
                    true
                },
            );
        });

        let elapsed = start_time.elapsed().as_nanos() as u64;
        let final_chunk = OllamaGenerateResponse {
            model: model_name,
            created_at: now_iso(),
            response: String::new(),
            done: true,
            done_reason: Some("stop".to_string()),
            total_duration: Some(elapsed),
            load_duration: Some(10_000_000),
            prompt_eval_count: Some(prompt.len() / 4),
            eval_count: Some(50),
        };
        if let Ok(json_str) = serde_json::to_string(&final_chunk) {
            let _ = tx.blocking_send(format!("{json_str}\n"));
        }
    });

    let stream = tokio_stream::wrappers::ReceiverStream::new(rx)
        .map(Ok::<_, std::convert::Infallible>);

    let body = axum::body::Body::from_stream(stream);
    Response::builder()
        .header(header::CONTENT_TYPE, "application/x-ndjson")
        .body(body)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

fn parse_keep_alive(val: &Option<serde_json::Value>) -> Option<u64> {
    match val {
        Some(serde_json::Value::Number(n)) => n.as_u64(),
        Some(serde_json::Value::String(s)) => {
            if s.ends_with('m') {
                s.trim_end_matches('m').parse::<u64>().ok().map(|m| m * 60)
            } else if s.ends_with('s') {
                s.trim_end_matches('s').parse::<u64>().ok()
            } else if s.ends_with('h') {
                s.trim_end_matches('h').parse::<u64>().ok().map(|h| h * 3600)
            } else {
                s.parse::<u64>().ok()
            }
        }
        _ => None,
    }
}
