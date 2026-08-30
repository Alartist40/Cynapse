//! Axum server: chat UI, MJPEG camera stream, JSON chat API, auth.

use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use axum::{
    body::Body,
    extract::{Query, State as AxState},
    http::{header, HeaderMap, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;
use tokio::time::sleep;

use crate::gateway::state::GatewayState;

/// Default on-disk location of the camera JPEG. The camera-feed.service
/// (or any other producer) drops frames here.
const DEFAULT_CAMERA_JPEG: &str = "/tmp/vision_feed.jpg";

/// Default interval at which we re-read the JPEG for streaming.
const STREAM_TICK: Duration = Duration::from_millis(120);

/// Launch the gateway on the configured address. Blocks until shutdown.
pub async fn run_server(state: Arc<GatewayState>) -> Result<()> {
    let addr: SocketAddr = state
        .config
        .gateway
        .address
        .parse()
        .map_err(|e| anyhow::anyhow!("invalid gateway address {:?}: {e}", state.config.gateway.address))?;

    let app = Router::new()
        .route("/", get(index_page))
        .route("/health", get(health))
        .route("/camera.jpg", get(camera_frame))
        .route("/stream", get(stream_mjpeg))
        .route("/api/chat", post(chat_handler))
        .route("/api/status", get(status_handler))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    eprintln!("cynapse gateway listening on http://{addr}");
    axum::serve(listener, app).await?;
    Ok(())
}

/// ────────────────────────────────────────────────────────────────────────────
///
/// Routes
///
/// ────────────────────────────────────────────────────────────────────────────

async fn health() -> impl IntoResponse {
    Json(serde_json::json!({
        "status": "ok",
        "version": crate::VERSION,
    }))
}

async fn status_handler(
    AxState(state): AxState<Arc<GatewayState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let model = &state.config.llm;
    Ok(Json(serde_json::json!({
        "version": crate::VERSION,
        "llm": {
            "provider": model.provider,
            "model": model.model,
        },
        "gateway": {
            "address": state.config.gateway.address,
            "auth_enabled": !state.config.gateway.auth_token.is_empty(),
        },
    })))
}

#[derive(Deserialize)]
struct ChatRequest {
    message: String,
    /// Optional bearer token; mirrors the X-Auth-Token header so the web UI
    /// can include it via XHR without a custom header (browsers allow custom
    /// headers, but we keep it simple).
    #[serde(default)]
    token: Option<String>,
}

#[derive(Serialize)]
struct ChatResponse {
    reply: String,
}

async fn chat_handler(
    AxState(state): AxState<Arc<GatewayState>>,
    headers: HeaderMap,
    Json(req): Json<ChatRequest>,
) -> Result<Json<ChatResponse>, (StatusCode, String)> {
    reject_unauthorized(&headers, req.token.as_deref(), &state.config.gateway.auth_token)
        .map_err(|s| (StatusCode::UNAUTHORIZED, s))?;

    let agent = state.agent().await.map_err(internal)?;
    let reply = agent
        .process_message(&req.message, vec![])
        .await
        .map_err(internal)?;
    Ok(Json(ChatResponse { reply }))
}

async fn camera_frame(
    AxState(state): AxState<Arc<GatewayState>>,
    headers: HeaderMap,
    Query(q): Query<AuthQuery>,
) -> Result<Response, (StatusCode, String)> {
    reject_unauthorized(&headers, q.token.as_deref(), &state.config.gateway.auth_token)
        .map_err(|s| (StatusCode::UNAUTHORIZED, s))?;

    let path = camera_path(&state);
    let bytes = match std::fs::read(&path) {
        Ok(b) if !b.is_empty() => b,
        _ => return Err((StatusCode::SERVICE_UNAVAILABLE, "no camera frame available".into())),
    };
    Ok(([(header::CONTENT_TYPE, HeaderValue::from_static("image/jpeg"))], bytes).into_response())
}

/// MJPEG stream — multipart/x-mixed-replace, one boundary per JPEG frame.
async fn stream_mjpeg(
    AxState(state): AxState<Arc<GatewayState>>,
    headers: HeaderMap,
    Query(q): Query<AuthQuery>,
) -> Result<Response, (StatusCode, String)> {
    reject_unauthorized(&headers, q.token.as_deref(), &state.config.gateway.auth_token)
        .map_err(|s| (StatusCode::UNAUTHORIZED, s))?;

    let path = camera_path(&state);
    let boundary = "frameboundary";
    let content_type = format!("multipart/x-mixed-replace; boundary={boundary}");
    let last_frame: Mutex<Vec<u8>> = Mutex::new(Vec::new());

    let stream = async_stream::stream! {
        loop {
            let frame = match std::fs::read(&path) {
                Ok(b) if !b.is_empty() => b,
                _ => Vec::new(),
            };
            let mut last = last_frame.lock().await;
            if !frame.is_empty() && frame != *last {
                let header = format!(
                    "\r\n--{boundary}\r\nContent-Type: image/jpeg\r\nContent-Length: {}\r\n\r\n",
                    frame.len()
                );
                let mut chunk = Vec::with_capacity(header.len() + frame.len());
                chunk.extend_from_slice(header.as_bytes());
                chunk.extend_from_slice(&frame);
                *last = frame;
                yield Ok::<_, std::io::Error>(chunk);
            } else {
                drop(last);
            }
            sleep(STREAM_TICK).await;
        }
    };

    let body = Body::from_stream(stream);
    Ok(Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, content_type)
        .body(body)
        .unwrap())
}

// ────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct AuthQuery {
    #[serde(default)]
    token: Option<String>,
}

fn reject_unauthorized(
    headers: &HeaderMap,
    body_token: Option<&str>,
    expected: &str,
) -> Result<(), String> {
    if expected.is_empty() {
        return Ok(());
    }
    let provided = headers
        .get("x-auth-token")
        .and_then(|v| v.to_str().ok())
        .or(body_token);
    match provided {
        Some(t) if t == expected => Ok(()),
        _ => Err("missing or invalid auth token".to_string()),
    }
}

fn camera_path(_state: &GatewayState) -> PathBuf {
    // Allow override via env so tests/dev can point at a fixture.
    if let Ok(p) = std::env::var("CYNAPSE_CAMERA_JPEG") {
        if !p.is_empty() {
            return PathBuf::from(p);
        }
    }
    PathBuf::from(DEFAULT_CAMERA_JPEG)
}

fn internal<E: std::fmt::Display>(e: E) -> (StatusCode, String) {
    (StatusCode::INTERNAL_SERVER_ERROR, e.to_string())
}

// ────────────────────────────────────────────────────────────────────────────
// Embedded HTML UI
// ────────────────────────────────────────────────────────────────────────────

async fn index_page(
    AxState(state): AxState<Arc<GatewayState>>,
) -> impl IntoResponse {
    let token = &state.config.gateway.auth_token;
    let token_param = if token.is_empty() {
        String::new()
    } else {
        format!("?token={token}")
    };
    let html = INDEX_HTML.replace("__TOKEN_PARAM__", &token_param);
    ([(header::CONTENT_TYPE, HeaderValue::from_static("text/html; charset=utf-8"))], html)
}

const INDEX_HTML: &str = r#"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>cynapse — local robot brain</title>
<style>
  :root { color-scheme: light dark; --fg:#e8dcc8; --bg:#1c1408; --accent:#cb9b4e; --dim:#73644e; }
  * { box-sizing: border-box; }
  body { margin:0; font:14px/1.4 ui-sans-serif, system-ui, sans-serif; background:var(--bg); color:var(--fg); }
  header { padding:.6rem 1rem; border-bottom:1px solid #3a2c1c; display:flex; justify-content:space-between; align-items:center; }
  header h1 { margin:0; font-size:1rem; color:var(--accent); letter-spacing:.04em; }
  header .status { font-size:.8rem; color:var(--dim); }
  main { display:grid; grid-template-columns: 1.4fr 1fr; gap:1rem; padding:1rem; min-height:calc(100vh - 3rem); }
  @media (max-width: 760px) { main { grid-template-columns: 1fr; } }
  .panel { background:#231a0e; border:1px solid #3a2c1c; border-radius:6px; padding:.8rem; }
  .panel h2 { margin:.2rem 0 .6rem; font-size:.9rem; color:var(--accent); letter-spacing:.04em; text-transform:uppercase; }
  .cam img, .cam .ph { width:100%; aspect-ratio:4/3; background:#0d0905; border-radius:4px; }
  .cam .ph { display:flex; align-items:center; justify-content:center; color:var(--dim); }
  .log { height: calc(100vh - 14rem); overflow-y:auto; padding:.4rem .2rem; }
  .msg { margin:.35rem 0; padding:.4rem .6rem; border-radius:4px; max-width:92%; white-space:pre-wrap; }
  .me { background:#3a2c1c; margin-left:auto; }
  .bot { background:#1f160a; border:1px solid #3a2c1c; }
  .sys { background:transparent; color:var(--dim); font-size:.78rem; font-style:italic; }
  form { display:flex; gap:.4rem; margin-top:.6rem; }
  textarea { flex:1; resize:vertical; min-height:2.6rem; max-height:8rem; background:#0d0905; color:var(--fg); border:1px solid #3a2c1c; border-radius:4px; padding:.4rem .6rem; font:inherit; }
  button { background:var(--accent); color:#1c1408; border:0; border-radius:4px; padding:.4rem .9rem; font-weight:600; cursor:pointer; }
  button:disabled { opacity:.5; cursor:not-allowed; }
  a { color:var(--accent); }
</style>
</head>
<body>
<header>
  <h1>🌿 cynapse · local robot brain</h1>
  <span class="status" id="status">loading…</span>
</header>
<main>
  <section class="panel cam">
    <h2>camera</h2>
    <img id="cam" alt="camera feed" src="/stream__TOKEN_PARAM__">
    <div class="ph" id="camPh" style="display:none">no frame</div>
  </section>
  <section class="panel">
    <h2>chat</h2>
    <div class="log" id="log"></div>
    <form id="f">
      <textarea id="msg" placeholder="Ask the brain, or give it a command…" autofocus></textarea>
      <button id="send" type="submit">Send</button>
    </form>
  </section>
</main>
<script>
const TOKEN_PARAM = "__TOKEN_PARAM__";
const TOKEN = new URLSearchParams(TOKEN_PARAM.replace(/^\?/, "")).get("token") || "";
const log = document.getElementById("log");
const f = document.getElementById("f");
const msg = document.getElementById("msg");
const send = document.getElementById("send");
const status = document.getElementById("status");

function add(text, who) {
  const el = document.createElement("div");
  el.className = "msg " + who;
  el.textContent = text;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
}

async function loadStatus() {
  try {
    const r = await fetch("/api/status" + TOKEN_PARAM);
    if (!r.ok) throw new Error("status " + r.status);
    const j = await r.json();
    status.textContent = `${j.llm.provider} · ${j.llm.model}`;
  } catch (e) {
    status.textContent = "offline";
  }
}

async function ask(text) {
  add(text, "me");
  add("…", "sys");
  const placeholder = log.lastChild;
  send.disabled = true;
  try {
    const r = await fetch("/api/chat" + TOKEN_PARAM, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, token: TOKEN || undefined }),
    });
    const j = await r.json();
    placeholder.remove();
    if (!r.ok) {
      add("Error " + r.status + ": " + (j || r.statusText), "sys");
    } else {
      add(j.reply, "bot");
    }
  } catch (e) {
    placeholder.remove();
    add("network error: " + e.message, "sys");
  } finally {
    send.disabled = false;
  }
}

f.addEventListener("submit", (e) => {
  e.preventDefault();
  const t = msg.value.trim();
  if (!t) return;
  msg.value = "";
  ask(t);
});

const img = document.getElementById("cam");
const ph = document.getElementById("camPh");
img.addEventListener("error", () => {
  img.style.display = "none";
  ph.style.display = "flex";
});
img.addEventListener("load", () => {
  img.style.display = "";
  ph.style.display = "none";
});

loadStatus();
</script>
</body>
</html>
"#;
