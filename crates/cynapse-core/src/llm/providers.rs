//! LLM providers: Ollama (NDJSON) and OpenAI-compatible (SSE).
//!
//! Faithful port of Go `internal/llm/client.go` for the two providers in
//! v1 scope. The base client replicates the retry policy (429/5xx retry,
//! attempt*2s backoff); the streaming contract matches Go — text chunks
//! flow on the `chunks` channel and, when the model calls tools, a final
//! JSON-encoded `[]ToolCall` chunk arrives as a control message.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use anyhow::{anyhow, Context as _, Result};
use async_trait::async_trait;
use futures_util::StreamExt;
use serde::Deserialize;
use serde_json::{json, Value};
use tokio::sync::mpsc;

use crate::config::LlmConfig;
use crate::llm::{Request, Response, Role, ToolCall, Usage};
/// Shared cancellation token; dropping a stream handle does not cancel the
/// underlying task, so consumers can flip this to stop early.
pub type Cancelled = Arc<AtomicBool>;

/// Handle returned by streaming requests: text chunks plus an error channel.
pub struct StreamHandle {
    pub chunks: mpsc::UnboundedReceiver<String>,
    pub errors: mpsc::UnboundedReceiver<anyhow::Error>,
}

#[async_trait]
pub trait LlmClient: Send + Sync {
    async fn chat(&self, req: &Request) -> Result<Response>;
    fn chat_stream(&self, req: &Request, cancelled: Cancelled) -> StreamHandle;
    fn provider(&self) -> &'static str;
    /// Switch the model used for subsequent requests. No-op for
    /// providers that bake the model in at construction time.
    fn set_model(&self, _model: &str) {}
    /// The model in use, for the TUI status bar.
    fn current_model(&self) -> String {
        String::new()
    }
}

/// Build the provider configured in `cfg`.
pub fn new(cfg: &LlmConfig) -> Result<Arc<dyn LlmClient>> {
    let http = reqwest::Client::builder()
        .timeout(Duration::from_secs(300))
        .build()
        .context("building http client")?;
    let base = BaseClient {
        http,
        max_retries: cfg.max_retries,
    };

    match cfg.provider.to_lowercase().as_str() {
        "ollama" => {
            let base_url = if cfg.ollama_base_url.is_empty() {
                "http://localhost:11434".to_string()
            } else {
                cfg.ollama_base_url.trim_end_matches('/').to_string()
            };
            Ok(Arc::new(OllamaClient {
                base,
                base_url,
                model: Mutex::new(cfg.model.clone()),
            }))
        }
        "openai" => {
            let base_url = if cfg.openai_base_url.is_empty() {
                "https://api.openai.com/v1".to_string()
            } else {
                cfg.openai_base_url.trim_end_matches('/').to_string()
            };
            if cfg.openai_key.is_empty() {
                return Err(anyhow!("openai provider requires openai_key or OPENAI_API_KEY"));
            }
            Ok(Arc::new(OpenAiClient {
                base,
                api_key: cfg.openai_key.clone(),
                base_url,
                model: Mutex::new(cfg.model.clone()),
            }))
        }
        "anthropic" => {
            #[cfg(feature = "anthropic")]
            {
                let base = BaseClient {
                    http: reqwest::Client::builder()
                        .timeout(Duration::from_secs(300))
                        .build()
                        .context("building http client")?,
                    max_retries: cfg.max_retries,
                };
                return Ok(Arc::new(crate::llm::anthropic::AnthropicClient::new(
                    base,
                    cfg.anthropic_key.clone(),
                    cfg.model.clone(),
                )));
            }
            #[cfg(not(feature = "anthropic"))]
            {
                Err(anyhow!(
                    "anthropic provider not compiled in; build with --features cynapse-core/anthropic"
                ))
            }
        }
        "gemini" => Err(anyhow!("gemini provider is deferred (v2 scope)")),
        "local" => Err(anyhow!("local provider is deferred; use leafcutter for local inference")),
        "leafcutter" => crate::llm::leafcutter::new(base, cfg),
        other => Err(anyhow!("unknown provider: {other}")),
    }
}

/// All models available from a running Ollama instance.
pub async fn list_ollama_models(base_url: &str) -> Result<Vec<String>> {
    let base_url = if base_url.is_empty() {
        "http://localhost:11434"
    } else {
        base_url
    };
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(30))
        .build()?;
    let url = format!("{}/api/tags", base_url.trim_end_matches('/'));
    let resp = client
        .get(&url)
        .send()
        .await
        .context("connecting to ollama")?;
    let data: Value = resp
        .json()
        .await
        .context("parsing ollama response")?;
    let mut names = Vec::new();
    if let Some(models) = data.get("models").and_then(|m| m.as_array()) {
        for m in models {
            if let Some(name) = m.get("name").and_then(|n| n.as_str()) {
                names.push(name.to_string());
            }
        }
    }
    Ok(names)
}

// ─── Base client: shared HTTP + retry logic ─────────────────────────────────

pub(crate) struct BaseClient {
    pub(crate) http: reqwest::Client,
    max_retries: u32,
}

impl BaseClient {
    pub(crate) async fn do_request(
        &self,
        method: &str,
        url: &str,
        headers: &[(&str, String)],
        body: Option<&Value>,
    ) -> Result<Vec<u8>> {
        let mut last_err: Option<anyhow::Error> = None;
        for attempt in 0..=self.max_retries {
            if attempt > 0 {
                tokio::time::sleep(Duration::from_secs(attempt as u64 * 2)).await;
            }

            let mut rb = self.http.request(reqwest::Method::from_bytes(method.as_bytes()).unwrap(), url);
            rb = rb.header(reqwest::header::CONTENT_TYPE, "application/json");
            for (k, v) in headers {
                rb = rb.header(*k, v);
            }
            if let Some(b) = body {
                rb = rb.json(b);
            }

            let resp = match rb.send().await {
                Ok(r) => r,
                Err(e) => {
                    last_err = Some(e.into());
                    continue;
                }
            };
            let status = resp.status();
            let data = resp.bytes().await?;
            let text = String::from_utf8_lossy(&data);

            if status.as_u16() == 429 || status.is_server_error() {
                last_err = Some(anyhow!("HTTP {}: {}", status, truncate(&text, 200)));
                continue;
            }
            if status.is_client_error() {
                return Err(anyhow!("HTTP {}: {}", status, truncate(&text, 300)));
            }
            return Ok(data.to_vec());
        }
        Err(anyhow!(
            "after {} retries: {}",
            self.max_retries,
            last_err.map(|e| e.to_string()).unwrap_or_else(|| "request failed".into())
        ))
    }
}

// ─── Ollama ─────────────────────────────────────────────────────────────────

pub struct OllamaClient {
    base: BaseClient,
    base_url: String,
    model: Mutex<String>,
}

#[derive(Deserialize)]
struct OllamaResponse {
    message: OllamaResponseMessage,
    #[serde(default)]
    prompt_eval_count: usize,
    #[serde(default)]
    eval_count: usize,
}

#[derive(Deserialize)]
struct OllamaResponseMessage {
    #[serde(default)]
    content: String,
    #[serde(default)]
    thinking: String,
    #[serde(default)]
    tool_calls: Vec<OllamaResponseToolCall>,
}

#[derive(Deserialize)]
struct OllamaResponseToolCall {
    #[serde(default)]
    id: String,
    function: OllamaResponseFunction,
}

#[derive(Deserialize)]
struct OllamaResponseFunction {
    #[serde(default)]
    name: String,
    arguments: Value,
}

#[async_trait]
impl LlmClient for OllamaClient {
    async fn chat(&self, req: &Request) -> Result<Response> {
        let model = self.model.lock().unwrap_or_else(|e| e.into_inner()).clone();
        let api_req = build_ollama_request(model, req, false);
        let url = format!("{}/api/chat", self.base_url);
        let data = self
            .base
            .do_request("POST", &url, &[], Some(&api_req))
            .await?;

        let o: OllamaResponse = serde_json::from_slice(&data).context("parsing ollama response")?;
        let mut result = Response {
            content: o.message.content,
            thinking: o.message.thinking,
            usage: Usage {
                input_tokens: o.prompt_eval_count,
                output_tokens: o.eval_count,
            },
            ..Default::default()
        };
        for tc in o.message.tool_calls {
            result.tool_calls.push(ToolCall {
                id: tc.id,
                name: tc.function.name,
                arguments: tc.function.arguments,
            });
        }
        Ok(result)
    }

    fn chat_stream(&self, req: &Request, cancelled: Cancelled) -> StreamHandle {
        let (chunks_tx, chunks) = mpsc::unbounded_channel();
        let (errors_tx, errors) = mpsc::unbounded_channel();
        let model = self.model.lock().unwrap_or_else(|e| e.into_inner()).clone();
        let api_req = build_ollama_request(model, req, true);
        let url = format!("{}/api/chat", self.base_url);
        let http = self.base.http.clone();

        tokio::spawn(async move {
            let send_err = |tx: &mpsc::UnboundedSender<anyhow::Error>, e: anyhow::Error| {
                let _ = tx.send(e);
            };

            let resp = match http
                .post(&url)
                .header(reqwest::header::CONTENT_TYPE, "application/json")
                .json(&api_req)
                .send()
                .await
            {
                Ok(r) => r,
                Err(e) => {
                    send_err(&errors_tx, anyhow!("ollama request failed: {e}"));
                    return;
                }
            };
            if !resp.status().is_success() {
                let status = resp.status();
                let body = resp.text().await.unwrap_or_default();
                send_err(&errors_tx, anyhow!("ollama HTTP {status}: {}", truncate(&body, 300)));
                return;
            }

            let mut tool_calls: Vec<ToolCall> = Vec::new();
            let mut buffer: Vec<u8> = Vec::new();
            let mut stream = resp.bytes_stream();
            while let Some(chunk) = stream.next().await {
                if cancelled.load(Ordering::Relaxed) {
                    return;
                }
                let chunk = match chunk {
                    Ok(c) => c,
                    Err(e) => {
                        send_err(&errors_tx, anyhow!("reading stream: {e}"));
                        return;
                    }
                };
                buffer.extend_from_slice(&chunk);
                while let Some(pos) = buffer.iter().position(|&b| b == b'\n') {
                    let line: Vec<u8> = buffer.drain(..=pos).collect();
                    let line = String::from_utf8_lossy(&line[..line.len() - 1]).to_string();
                    if let Err(e) = handle_ollama_line(&line, &mut tool_calls, &chunks_tx) {
                        send_err(&errors_tx, e);
                    }
                }
            }
            if !buffer.is_empty() {
                let line = String::from_utf8_lossy(&buffer).to_string();
                if let Err(e) = handle_ollama_line(&line, &mut tool_calls, &chunks_tx) {
                    send_err(&errors_tx, e);
                }
            }
            if !tool_calls.is_empty() {
                let _ = chunks_tx.send(serde_json::to_string(&tool_calls).unwrap_or_default());
            }
        });

        StreamHandle { chunks, errors }
    }

    fn provider(&self) -> &'static str {
        "ollama"
    }

    fn set_model(&self, model: &str) {
        *self.model.lock().unwrap_or_else(|e| e.into_inner()) = model.to_string();
    }

    fn current_model(&self) -> String {
        self.model.lock().unwrap_or_else(|e| e.into_inner()).clone()
    }
}

fn build_ollama_request(model: String, req: &Request, stream: bool) -> Value {
    let mut messages: Vec<Value> = Vec::new();
    if !req.system_prompt.is_empty() {
        messages.push(json!({"role": "system", "content": req.system_prompt}));
    }
    for m in &req.messages {
        let mut content = m.content.clone();
        let mut images: Vec<String> = Vec::new();
        for att in &m.attachments {
            match att.kind.as_str() {
                "image" => images.push(att.content.clone()),
                "text" | "pdf" => {
                    content.push_str(&format!("\n\n[Attachment: {}]\n{}", att.filename, att.content));
                }
                _ => {}
            }
        }
        images.extend(m.images.clone());

        let mut msg = json!({
            "role": m.role.as_str(),
            "content": content,
        });
        if !images.is_empty() {
            msg["images"] = json!(images);
        }
        if !m.tool_calls.is_empty() {
            let calls: Vec<Value> = m
                .tool_calls
                .iter()
                .map(|tc| {
                    json!({"function": {"name": tc.name, "arguments": tc.arguments}})
                })
                .collect();
            msg["tool_calls"] = json!(calls);
        }
        messages.push(msg);
    }

    let tools: Vec<Value> = req
        .tools
        .iter()
        .map(|t| {
            json!({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
            })
        })
        .collect();

    json!({
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": stream,
        "options": {
            "num_predict": req.max_tokens,
            "temperature": req.temperature,
        }
    })
}

fn handle_ollama_line(
    line: &str,
    tool_calls: &mut Vec<ToolCall>,
    chunks_tx: &mpsc::UnboundedSender<String>,
) -> Result<()> {
    if line.trim().is_empty() {
        return Ok(());
    }
    let parsed: Value = match serde_json::from_str(line) {
        Ok(v) => v,
        Err(_) => return Ok(()), // skip malformed lines
    };
    if let Some(message) = parsed.get("message") {
        if let Some(thinking) = message.get("thinking").and_then(|t| t.as_str()) {
            if !thinking.is_empty() {
                let _ = chunks_tx.send(format!("[thinking]{thinking}"));
            }
        }
        if let Some(calls) = message.get("tool_calls").and_then(|c| c.as_array()) {
            for call in calls {
                let name = call
                    .get("function")
                    .and_then(|f| f.get("name"))
                    .and_then(|n| n.as_str())
                    .unwrap_or("")
                    .to_string();
                let args = call
                    .get("function")
                    .and_then(|f| f.get("arguments"))
                    .cloned()
                    .unwrap_or(Value::Null);
                tool_calls.push(ToolCall {
                    id: String::new(),
                    name,
                    arguments: args,
                });
            }
        }
        if let Some(content) = message.get("content").and_then(|c| c.as_str()) {
            if !content.is_empty() {
                let _ = chunks_tx.send(content.to_string());
            }
        }
    }
    Ok(())
}

// ─── OpenAI-compatible ──────────────────────────────────────────────────────

pub struct OpenAiClient {
    base: BaseClient,
    api_key: String,
    base_url: String,
    model: Mutex<String>,
}

#[derive(Deserialize)]
struct OpenAiResponse {
    #[serde(default)]
    choices: Vec<OpenAiChoice>,
    #[serde(default)]
    usage: OpenAiUsage,
}

#[derive(Deserialize)]
struct OpenAiChoice {
    message: OpenAiResponseMessage,
}

#[derive(Deserialize)]
struct OpenAiResponseMessage {
    #[serde(default)]
    content: String,
    #[serde(default)]
    tool_calls: Vec<OpenAiResponseToolCall>,
}

#[derive(Deserialize)]
struct OpenAiResponseToolCall {
    #[serde(default)]
    id: String,
    function: OpenAiResponseFunction,
}

#[derive(Deserialize)]
struct OpenAiResponseFunction {
    #[serde(default)]
    name: String,
    /// JSON-encoded argument string; parsed into an object below.
    arguments: String,
}

#[derive(Deserialize, Default)]
struct OpenAiUsage {
    #[serde(default)]
    prompt_tokens: usize,
    #[serde(default)]
    completion_tokens: usize,
}

#[async_trait]
impl LlmClient for OpenAiClient {
    async fn chat(&self, req: &Request) -> Result<Response> {
        let model = self.model.lock().unwrap_or_else(|e| e.into_inner()).clone();
        let api_req = build_openai_request(model, req, false);
        let url = format!("{}/chat/completions", self.base_url);
        let headers = vec![("Authorization", format!("Bearer {}", self.api_key))];
        let data = self
            .base
            .do_request("POST", &url, &headers, Some(&api_req))
            .await?;

        let o: OpenAiResponse = serde_json::from_slice(&data).context("parsing openai response")?;
        let mut result = Response {
            usage: Usage {
                input_tokens: o.usage.prompt_tokens,
                output_tokens: o.usage.completion_tokens,
            },
            ..Default::default()
        };
        if let Some(choice) = o.choices.first() {
            result.content = choice.message.content.clone();
            for tc in &choice.message.tool_calls {
                let args = serde_json::from_str::<Value>(&tc.function.arguments)
                    .unwrap_or_else(|_| json!(tc.function.arguments));
                result.tool_calls.push(ToolCall {
                    id: tc.id.clone(),
                    name: tc.function.name.clone(),
                    arguments: args,
                });
            }
        }
        Ok(result)
    }

    fn chat_stream(&self, req: &Request, cancelled: Cancelled) -> StreamHandle {
        let (chunks_tx, chunks) = mpsc::unbounded_channel();
        let (errors_tx, errors) = mpsc::unbounded_channel();
        let model = self.model.lock().unwrap_or_else(|e| e.into_inner()).clone();
        let api_req = build_openai_request(model, req, true);
        let url = format!("{}/chat/completions", self.base_url);
        let http = self.base.http.clone();
        let api_key = self.api_key.clone();

        tokio::spawn(async move {
            let send_err = |tx: &mpsc::UnboundedSender<anyhow::Error>, e: anyhow::Error| {
                let _ = tx.send(e);
            };

            let resp = match http
                .post(&url)
                .header(reqwest::header::CONTENT_TYPE, "application/json")
                .header("Authorization", format!("Bearer {api_key}"))
                .header("Accept", "text/event-stream")
                .json(&api_req)
                .send()
                .await
            {
                Ok(r) => r,
                Err(e) => {
                    send_err(&errors_tx, anyhow!("openai request failed: {e}"));
                    return;
                }
            };
            if !resp.status().is_success() {
                let status = resp.status();
                let body = resp.text().await.unwrap_or_default();
                send_err(&errors_tx, anyhow!("openai HTTP {status}: {}", truncate(&body, 300)));
                return;
            }

            // SSE: "data: {...}" lines, accumulated per tool-call index.
            let mut buffers: Vec<(String, String, String)> = Vec::new(); // id, name, args
            let mut has_tool_calls = false;
            let mut buf: Vec<u8> = Vec::new();
            let mut stream = resp.bytes_stream();
            while let Some(chunk) = stream.next().await {
                if cancelled.load(Ordering::Relaxed) {
                    return;
                }
                let chunk = match chunk {
                    Ok(c) => c,
                    Err(e) => {
                        send_err(&errors_tx, anyhow!("reading stream: {e}"));
                        return;
                    }
                };
                buf.extend_from_slice(&chunk);
                while let Some(pos) = buf.iter().position(|&b| b == b'\n') {
                    let line: Vec<u8> = buf.drain(..=pos).collect();
                    let line = String::from_utf8_lossy(&line[..line.len() - 1]).to_string();
                    if !handle_openai_sse_line(
                        &line,
                        &mut buffers,
                        &mut has_tool_calls,
                        &chunks_tx,
                    ) {
                        break;
                    }
                }
            }

            if has_tool_calls && !buffers.is_empty() {
                let mut tool_calls: Vec<ToolCall> = Vec::new();
                for (id, name, args) in &buffers {
                    if name.is_empty() {
                        continue;
                    }
                    let args = serde_json::from_str::<Value>(args).unwrap_or_else(|_| json!(args));
                    tool_calls.push(ToolCall {
                        id: id.clone(),
                        name: name.clone(),
                        arguments: args,
                    });
                }
                if !tool_calls.is_empty() {
                    let _ = chunks_tx.send(serde_json::to_string(&tool_calls).unwrap_or_default());
                }
            }
        });

        StreamHandle { chunks, errors }
    }

    fn provider(&self) -> &'static str {
        "openai"
    }

    fn set_model(&self, model: &str) {
        *self.model.lock().unwrap_or_else(|e| e.into_inner()) = model.to_string();
    }

    fn current_model(&self) -> String {
        self.model.lock().unwrap_or_else(|e| e.into_inner()).clone()
    }
}

pub(crate) fn build_openai_request(model: String, req: &Request, stream: bool) -> Value {    let mut messages: Vec<Value> = Vec::new();
    if !req.system_prompt.is_empty() {
        messages.push(json!({"role": "system", "content": req.system_prompt}));
    }
    for m in &req.messages {
        let mut msg = json!({
            "role": m.role.as_str(),
            "content": m.content,
        });
        if m.role == Role::Tool {
            msg["tool_call_id"] = json!(m.tool_call_id.clone().unwrap_or_default());
        }
        if !m.tool_calls.is_empty() {
            let calls: Vec<Value> = m
                .tool_calls
                .iter()
                .map(|tc| {
                    json!({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments.to_string(),
                        }
                    })
                })
                .collect();
            msg["tool_calls"] = json!(calls);
        }
        messages.push(msg);
    }

    let tools: Vec<Value> = req
        .tools
        .iter()
        .map(|t| {
            json!({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
            })
        })
        .collect();

    json!({
        "model": model,
        "max_tokens": req.max_tokens,
        "temperature": req.temperature,
        "messages": messages,
        "tools": tools,
        "stream": stream,
    })
}

/// Handle one SSE line for OpenAI. Returns false if `[DONE]` was seen.
pub(crate) fn handle_openai_sse_line(
    line: &str,
    buffers: &mut Vec<(String, String, String)>,
    has_tool_calls: &mut bool,
    chunks_tx: &mpsc::UnboundedSender<String>,
) -> bool {
    let Some(data) = line.strip_prefix("data: ") else {
        return true;
    };
    if data == "[DONE]" {
        return false;
    }
    let parsed: Value = match serde_json::from_str(data) {
        Ok(v) => v,
        Err(_) => return true,
    };
    let Some(choices) = parsed.get("choices").and_then(|c| c.as_array()) else {
        return true;
    };
    if choices.is_empty() {
        return true;
    }
    let delta = &choices[0]["delta"];
    if let Some(calls) = delta.get("tool_calls").and_then(|c| c.as_array()) {
        *has_tool_calls = true;
        for call in calls {
            let index = call.get("index").and_then(|i| i.as_i64()).unwrap_or(0) as usize;
            while buffers.len() <= index {
                buffers.push((String::new(), String::new(), String::new()));
            }
            let buf = &mut buffers[index];
            if let Some(id) = call.get("id").and_then(|i| i.as_str()) {
                if !id.is_empty() {
                    buf.0 = id.to_string();
                }
            }
            if let Some(name) = call.get("function").and_then(|f| f.get("name")).and_then(|n| n.as_str()) {
                if !name.is_empty() {
                    buf.1 = name.to_string();
                }
            }
            if let Some(args) = call.get("function").and_then(|f| f.get("arguments")).and_then(|a| a.as_str()) {
                buf.2.push_str(args);
            }
        }
        return true;
    }
    if let Some(content) = delta.get("content").and_then(|c| c.as_str()) {
        if !content.is_empty() {
            let _ = chunks_tx.send(content.to_string());
        }
    }
    true
}

fn truncate(s: &str, n: usize) -> String {
    if s.chars().count() <= n {
        s.to_string()
    } else {
        let mut out: String = s.chars().take(n).collect();
        out.push_str("…");
        out
    }
}
