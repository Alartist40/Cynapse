//! The agent loop: circuit-breakered multi-turn tool-calling chat.
//!
//! Faithful port of Go `internal/agent/agent.go`. Both a blocking
//! (`process_message`) and a streaming (`process_message_stream`)
//! entry point are provided; the streaming one emits JSON-encoded
//! `[]ToolCall` control chunks that are routed to tool execution
//! rather than displayed.

use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use anyhow::{anyhow, Result};
use tokio::sync::mpsc;

use crate::compressor::Compactor;
use crate::config::Config;
use crate::llm::{self, Cancelled, LlmClient, Message, Request, Role, ToolCall};
use crate::ocr;
use crate::persona::Persona;
use crate::redact;
use crate::session::{Entry, Manager, Session};
use crate::tools::Registry;

/// Cap on tool-calling iterations per user turn.
pub const MAX_TOOL_ITERATIONS: usize = 10;

/// Prevents hammering a failing LLM provider. Transitions:
/// closed → open (N consecutive errors) → half-open (after cooldown)
/// → closed (success) or back to open (failure).
pub struct CircuitBreaker {
    inner: Mutex<BreakerInner>,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum BreakerState {
    Closed,
    Open,
    HalfOpen,
}

struct BreakerInner {
    state: BreakerState,
    failures: u32,
    last_failure: Instant,
    max_failures: u32,
    cooldown: Duration,
}

impl CircuitBreaker {
    pub fn new(max_failures: u32, cooldown: Duration) -> CircuitBreaker {
        CircuitBreaker {
            inner: Mutex::new(BreakerInner {
                state: BreakerState::Closed,
                failures: 0,
                last_failure: Instant::now(),
                max_failures,
                cooldown,
            }),
        }
    }

    fn lock(&self) -> std::sync::MutexGuard<'_, BreakerInner> {
        self.inner.lock().unwrap_or_else(|e| e.into_inner())
    }

    pub fn allow(&self) -> bool {
        let mut b = self.lock();
        match b.state {
            BreakerState::Closed => true,
            BreakerState::Open => {
                if b.last_failure.elapsed() >= b.cooldown {
                    b.state = BreakerState::HalfOpen;
                    true
                } else {
                    false
                }
            }
            BreakerState::HalfOpen => true, // allow exactly one probe request
        }
    }

    pub fn record_success(&self) {
        let mut b = self.lock();
        b.state = BreakerState::Closed;
        b.failures = 0;
    }

    pub fn record_failure(&self) {
        let mut b = self.lock();
        b.failures += 1;
        b.last_failure = Instant::now();
        if b.state == BreakerState::HalfOpen || b.failures >= b.max_failures {
            b.state = BreakerState::Open;
        }
    }
}

/// Runs one chat session: owns the LLM client, the persona, the
/// session store, and the tool registry.
pub struct Agent {
    device_id: String,
    llm: Arc<dyn LlmClient>,
    persona: Arc<Persona>,
    sessions: Arc<Manager>,
    tools: Arc<Registry>,
    cfg: Config,
    cb: Arc<CircuitBreaker>,
    comp: Arc<Compactor>,
    redact: bool,
    http: reqwest::Client,
}

/// Resolve the model's context length for compression purposes.
fn context_window_tokens(cfg: &Config) -> usize {
    if cfg.llm.local_context_size > 0 {
        cfg.llm.local_context_size as usize
    } else {
        4096
    }
}

impl Agent {
    pub fn new(
        device_id: String,
        llm_client: Arc<dyn LlmClient>,
        persona: Arc<Persona>,
        sessions: Arc<Manager>,
        tools: Arc<Registry>,
        cfg: Config,
    ) -> Agent {
        let redact = cfg.effective_redaction();
        let comp = Arc::new(Compactor::new(
            context_window_tokens(&cfg),
            Some(persona.clone()),
        ));
        Agent {
            device_id,
            llm: llm_client,
            persona,
            sessions,
            tools,
            cfg,
            cb: Arc::new(CircuitBreaker::new(3, Duration::from_secs(30))),
            comp,
            redact,
            http: reqwest::Client::new(),
        }
    }

    pub fn persona(&self) -> &Arc<Persona> {
        &self.persona
    }

    /// Force an immediate context→DENDRITE archive pass. Returns the
    /// number of turns moved and tokens saved.
    pub fn compress_now(&self) -> Result<(usize, usize)> {
        if !self.comp.enabled() {
            return Err(anyhow!("compression not configured (no context length)"));
        }
        let sess = self.sessions.get(&self.device_id)?;
        let all = sess.entries();
        if !self.comp.should_compress(&all) {
            return Ok((0, 0));
        }
        let (kept, res) = self.comp.compress(&all);
        if let Some(e) = &res.err {
            return Err(anyhow!("{e}"));
        }
        sess.replace(kept)?;
        Ok((res.turns_moved, res.original_tokens.saturating_sub(res.compressed_tokens)))
    }

    /// Clear all stored session entries for this device.
    pub fn clear_session(&self) -> Result<()> {
        let sess = self.sessions.get(&self.device_id)?;
        sess.clear()
    }

    /// Handle one user turn; returns the final text response.
    pub async fn process_message(&self, user_msg: &str, attachments: Vec<llm::Attachment>) -> Result<String> {
        let sess = self.sessions.get(&self.device_id)?;

        let content = ocr::augment_with_ocr(
            user_msg,
            &ocr::to_core_attachments(&attachments),
            &self.cfg.ocr,
            &self.cfg.llm.ollama_base_url,
            &self.http,
        )
        .await;

        sess.append(Entry {
            role: Role::User,
            content: content.clone(),
            tool_call_id: None,
            tool_calls: Vec::new(),
            images: Vec::new(),
            attachments,
            ts: 0,
        })?;

        // Auto-compress BEFORE building the LLM request so the model
        // never sees an over-the-limit transcript.
        if self.comp.enabled() {
            let all = sess.entries();
            if self.comp.should_compress(&all) {
                let (kept, _res) = self.comp.compress(&all);
                if let Err(e) = sess.replace(kept) {
                    eprintln!("[AGENT:{}] compressor replace failed: {e}", self.device_id);
                }
            }
        }

        if sess.len() > self.cfg.memory.max_session_messages as usize {
            sess.compact(self.cfg.memory.max_session_messages as usize / 2)?;
        }

        let all_tools = self.tools.schemas();

        let mut req = Request {
            system_prompt: self.persona.compile_system_prompt(user_msg),
            messages: sess.recent(12),
            tools: all_tools,
            max_tokens: self.cfg.llm.max_tokens,
            temperature: self.cfg.llm.temperature,
        };

        let mut final_response = String::new();
        for _ in 0..MAX_TOOL_ITERATIONS {
            if !self.cb.allow() {
                return Err(anyhow!(
                    "LLM unavailable (circuit breaker open). The provider may be experiencing issues. Try again in a few moments."
                ));
            }
            let resp = match self.llm.chat(&req).await {
                Ok(r) => r,
                Err(e) => {
                    self.cb.record_failure();
                    return Err(anyhow!("LLM error: {e}"));
                }
            };
            self.cb.record_success();

            if resp.tool_calls.is_empty() {
                final_response = resp.content;
                break;
            }

            let tcs = resp.tool_calls;
            req.messages.push(Message {
                role: Role::Assistant,
                content: String::new(),
                tool_call_id: None,
                tool_calls: tcs.clone(),
                images: Vec::new(),
                attachments: Vec::new(),
            });
            sess.append(Entry {
                role: Role::Assistant,
                content: String::new(),
                tool_call_id: None,
                tool_calls: tcs.clone(),
                images: Vec::new(),
                attachments: Vec::new(),
                ts: 0,
            })?;

            for tc in &tcs {
                let result = self.execute_tool(&tc).await;
                let content = match result {
                    Ok(c) => c,
                    Err(e) => format!("Error: {e}"),
                };
                let content = if self.redact { redact::redact(&content) } else { content };
                let msg = Message {
                    role: Role::Tool,
                    content: content.clone(),
                    tool_call_id: Some(tc.id.clone()),
                    tool_calls: Vec::new(),
                    images: Vec::new(),
                    attachments: Vec::new(),
                };
                req.messages.push(msg);
                sess.append(Entry {
                    role: Role::Tool,
                    content,
                    tool_call_id: Some(tc.id.clone()),
                    tool_calls: Vec::new(),
                    images: Vec::new(),
                    attachments: Vec::new(),
                    ts: 0,
                })?;
            }
        }

        if final_response.is_empty() {
            final_response = "(agent reached tool iteration limit)".to_string();
        }
        if self.redact {
            final_response = redact::redact(&final_response);
        }

        sess.append(Entry {
            role: Role::Assistant,
            content: final_response.clone(),
            tool_call_id: None,
            tool_calls: Vec::new(),
            images: Vec::new(),
            attachments: Vec::new(),
            ts: 0,
        })?;

        self.spawn_self_improve(user_msg, &final_response);

        Ok(final_response)
    }

    /// Execute a single tool by name, updating the session as it goes.
    async fn execute_tool(&self, tc: &ToolCall) -> Result<String> {
        eprintln!(
            "[AGENT:{}] tool={} args={}",
            self.device_id,
            tc.name,
            truncate(&tc.arguments.to_string(), 120)
        );
        self.tools.execute(&tc.name, tc.arguments.clone()).await
    }

    /// Streaming variant of `process_message`. Returns two channels
    /// (chunks + errors); the caller is expected to render chunks
    /// into the TUI.
    pub async fn process_message_stream(
        &self,
        user_msg: &str,
        attachments: Vec<llm::Attachment>,
    ) -> (mpsc::UnboundedReceiver<String>, mpsc::UnboundedReceiver<anyhow::Error>) {
        let (chunks_tx, chunks_rx) = mpsc::unbounded_channel();
        let (errors_tx, errors_rx) = mpsc::unbounded_channel();
        let cancelled: Cancelled = Arc::new(AtomicBool::new(false));

        let me = Arc::new(Self {
            device_id: self.device_id.clone(),
            llm: self.llm.clone(),
            persona: self.persona.clone(),
            sessions: self.sessions.clone(),
            tools: self.tools.clone(),
            cfg: self.cfg.clone(),
            cb: self.cb.clone(),
            comp: self.comp.clone(),
            redact: self.redact,
            http: self.http.clone(),
        });

        let sess_fut = self.sessions.get(&self.device_id);
        let user_msg = user_msg.to_string();

        tokio::spawn(async move {
            let sess = match sess_fut {
                Ok(s) => s,
                Err(e) => {
                    let _ = errors_tx.send(anyhow!("getting session: {e}"));
                    return;
                }
            };

            let agent = &me;
            let content = ocr::augment_with_ocr(
                &user_msg,
                &ocr::to_core_attachments(&attachments),
                &agent.cfg.ocr,
                &agent.cfg.llm.ollama_base_url,
                &agent.http,
            )
            .await;
            if let Err(e) = agent
                .append_user_and_maybe_compress(&sess, content, attachments)
                .await
            {
                let _ = errors_tx.send(e);
                return;
            }

            let all_tools = agent.tools.schemas();

            for _ in 0..MAX_TOOL_ITERATIONS {
                if !agent.cb.allow() {
                    let _ = errors_tx.send(anyhow!(
                        "LLM unavailable (circuit breaker open). The provider may be experiencing issues. Try again in a few moments."
                    ));
                    return;
                }

                let req = Request {
                    system_prompt: agent.persona.compile_system_prompt(&user_msg),
                    messages: sess.recent(12),
                    tools: all_tools.clone(),
                    max_tokens: agent.cfg.llm.max_tokens,
                    temperature: agent.cfg.llm.temperature,
                };

                let mut handle = agent.llm.chat_stream(&req, cancelled.clone());
                let mut full_response = String::new();
                let mut saw_tool_calls = false;

                loop {
                    tokio::select! {
                        maybe = handle.chunks.recv() => match maybe {
                            Some(chunk) => {
                                if let Some(tcs) = parse_tool_call_chunk(&chunk) {
                                    saw_tool_calls = true;
                                    if let Err(e) = sess.append(Entry {
                                        role: Role::Assistant,
                                        content: String::new(),
                                        tool_call_id: None,
                                        tool_calls: tcs.clone(),
                                        images: Vec::new(),
                                        attachments: Vec::new(),
                                        ts: 0,
                                    }) {
                                        let _ = errors_tx.send(e);
                                        return;
                                    }
                                    let is_all_readonly = tcs.iter().all(|tc| agent.tools.resource_class(&tc.name) == crate::tools::ResourceClass::ReadOnly);
                                    if is_all_readonly && tcs.len() > 1 {
                                        for tc in &tcs {
                                            let _ = chunks_tx.send(format!("\n[tool:parallel] {}\n", tc.name));
                                        }
                                        let futures = tcs.iter().map(|tc| {
                                            let tc = tc.clone();
                                            let agent = agent.clone();
                                            async move {
                                                let res = agent.execute_tool(&tc).await;
                                                (tc, res)
                                            }
                                        });
                                        let results = futures_util::future::join_all(futures).await;
                                        for (tc, result) in results {
                                            let content = match result {
                                                Ok(c) => c,
                                                Err(e) => format!("Error: {e}"),
                                            };
                                            let content = if agent.redact { redact::redact(&content) } else { content };
                                            if let Err(e) = sess.append(Entry {
                                                role: Role::Tool,
                                                content: content.clone(),
                                                tool_call_id: Some(tc.id.clone()),
                                                tool_calls: Vec::new(),
                                                images: Vec::new(),
                                                attachments: Vec::new(),
                                                ts: 0,
                                            }) {
                                                let _ = errors_tx.send(e);
                                                return;
                                            }
                                            let _ = chunks_tx.send(format!("[tool result] {}\n", tc.name));
                                        }
                                    } else {
                                        for tc in &tcs {
                                            let _ = chunks_tx.send(format!("\n[tool] {}\n", tc.name));
                                            let result = agent.execute_tool(tc).await;
                                            let content = match result {
                                                Ok(c) => c,
                                                Err(e) => format!("Error: {e}"),
                                            };
                                            let content = if agent.redact { redact::redact(&content) } else { content };
                                            if let Err(e) = sess.append(Entry {
                                                role: Role::Tool,
                                                content: content.clone(),
                                                tool_call_id: Some(tc.id.clone()),
                                                tool_calls: Vec::new(),
                                                images: Vec::new(),
                                                attachments: Vec::new(),
                                                ts: 0,
                                            }) {
                                                let _ = errors_tx.send(e);
                                                return;
                                            }
                                            let _ = chunks_tx.send(format!("[tool result] {}\n", tc.name));
                                        }
                                    }
                                } else {
                                    full_response.push_str(&chunk);
                                    let _ = chunks_tx.send(chunk);
                                }
                            }
                            None => break,
                        },
                        maybe_err = handle.errors.recv() => match maybe_err {
                            Some(err) => {
                                agent.cb.record_failure();
                                let _ = errors_tx.send(err);
                                return;
                            }
                            None => break,
                        },
                    }
                }

                agent.cb.record_success();

                if !saw_tool_calls {
                    let clean_resp = strip_thinking_tags(&full_response);
                    if !clean_resp.is_empty() {
                        if let Err(e) = sess.append(Entry {
                            role: Role::Assistant,
                            content: clean_resp.clone(),
                            tool_call_id: None,
                            tool_calls: Vec::new(),
                            images: Vec::new(),
                            attachments: Vec::new(),
                            ts: 0,
                        }) {
                            let _ = errors_tx.send(e);
                            return;
                        }
                        agent.spawn_self_improve(&user_msg, &clean_resp);
                    }
                    return;
                }
                // saw_tool_calls: loop back for the next LLM turn with
                // the tool results now in the session.
            }

            let _ = chunks_tx.send("\n(agent reached tool iteration limit)\n".to_string());
        });

        (chunks_rx, errors_rx)
    }

    /// Shared preamble for the streaming path: record the user turn and
    /// run auto-compression + session bounds.
    async fn append_user_and_maybe_compress(
        &self,
        sess: &Session,
        user_msg: String,
        attachments: Vec<llm::Attachment>,
    ) -> Result<()> {
        sess.append(Entry {
            role: Role::User,
            content: user_msg,
            tool_call_id: None,
            tool_calls: Vec::new(),
            images: Vec::new(),
            attachments,
            ts: 0,
        })?;

        if self.comp.enabled() {
            let all = sess.entries();
            if self.comp.should_compress(&all) {
                let (kept, _res) = self.comp.compress(&all);
                if let Err(e) = sess.replace(kept) {
                    eprintln!("[AGENT:{}] compressor replace failed: {e}", self.device_id);
                }
            }
        }

        if sess.len() > self.cfg.memory.max_session_messages as usize {
            sess.compact(self.cfg.memory.max_session_messages as usize / 2)?;
        }
        Ok(())
    }

    /// Post-turn background memory curation: asks the LLM whether
    /// anything worth saving happened.
    fn spawn_self_improve(&self, user_msg: &str, agent_response: &str) {
        // Skip background curation for short casual turns under 25 chars (e.g. "hey there")
        if user_msg.trim().len() < 25 {
            return;
        }
        let persona = self.persona.clone();
        let llm = self.llm.clone();
        let device_id = self.device_id.clone();
        let user_msg = user_msg.to_string();
        let agent_response = agent_response.to_string();

        tokio::spawn(async move {
            tokio::time::sleep(Duration::from_secs(3)).await;
            let prompt = format!(
                "Review this conversation turn.\n\nUser: {user_msg}\n\nAssistant: {agent_response}\n\nDecide:\n1. Is there a fact worth saving to long-term memory? If yes, provide it.\n2. Should the USER.md profile be updated?\n3. What is a good one-line summary for the daily log?\n\nRespond in JSON only:\n{{\"save_fact\":\"\",\"save_fact_tags\":\"\",\"update_user\":false,\"daily_log\":\"\"}}"
            );

            let req = Request {
                system_prompt: "You are a memory curator. Respond only with the requested JSON.".to_string(),
                messages: vec![Message::text(Role::User, prompt)],
                tools: Vec::new(),
                max_tokens: 300,
                temperature: 0.2,
            };

            let resp = match llm.chat(&req).await {
                Ok(r) => r,
                Err(_) => return,
            };

            let mut content = resp.content.trim().to_string();
            content = content.trim_start_matches("```json").to_string();
            content = content.trim_start_matches("```").to_string();
            content = content.trim_end_matches("```").to_string();
            content = content.trim().to_string();

            #[derive(serde::Deserialize)]
            struct Decision {
                #[serde(default)]
                save_fact: String,
                #[serde(default)]
                save_fact_tags: String,
                #[serde(default)]
                update_user: bool,
                #[serde(default)]
                daily_log: String,
            }

            let decision = match serde_json::from_str::<Decision>(&content) {
                Ok(d) => d,
                Err(_) => {
                    // Retry once with stricter JSON extraction.
                    let Some(f) = extract_json(&content) else {
                        return;
                    };
                    match serde_json::from_str::<Decision>(&f) {
                        Ok(d) => d,
                        Err(_) => return,
                    }
                }
            };

            if !decision.save_fact.trim().is_empty() {
                let _ = persona.save_fact(decision.save_fact.trim(), decision.save_fact_tags.trim());
                eprintln!("[AGENT:{device_id}] saved memory: {}", truncate(&decision.save_fact, 80));
            }
            if !decision.daily_log.trim().is_empty() {
                let _ = persona.append_daily_log(decision.daily_log.trim());
            }
            if decision.update_user {
                let _ = persona.write_file("USER.md", &read_user_md(&persona));
            }
        });
    }
}

/// Check if a raw chunk is a JSON-encoded `[]ToolCall`. Returns the
/// tool calls and true if it matches.
fn parse_tool_call_chunk(chunk: &str) -> Option<Vec<ToolCall>> {
    let chunk = chunk.trim();
    if chunk.is_empty() || chunk == "[]" {
        return None;
    }
    if !chunk.starts_with('[') {
        return None;
    }
    let tcs: Vec<ToolCall> = serde_json::from_str(chunk).ok()?;
    if tcs.is_empty() {
        return None;
    }
    Some(tcs)
}

fn read_user_md(persona: &Persona) -> String {
    persona
        .read_file("USER.md")
        .unwrap_or_else(|_| "# User Profile\n".to_string())
}

fn truncate(s: &str, n: usize) -> String {
    if s.chars().count() <= n {
        s.to_string()
    } else {
        let mut out: String = s.chars().take(n).collect();
        out.push_str("...");
        out
    }
}

/// Find the first balanced `{...}` block in s, or None.
fn extract_json(s: &str) -> Option<String> {
    let start = s.find('{')?;
    let mut depth = 0;
    for (i, c) in s[start..].char_indices() {
        match c {
            '{' => depth += 1,
            '}' => {
                depth -= 1;
                if depth == 0 {
                    return Some(s[start..start + i + 1].to_string());
                }
            }
            _ => {}
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_tool_call_chunk_rejects_text() {
        assert!(parse_tool_call_chunk("hello world").is_none());
        assert!(parse_tool_call_chunk("[]").is_none());
        assert!(parse_tool_call_chunk("").is_none());
    }

    #[test]
    fn parse_tool_call_chunk_accepts_json() {
        let s = r#"[{"id":"call_1","name":"read_file","arguments":{"path":"a.txt"}}]"#;
        let tcs = parse_tool_call_chunk(s).unwrap();
        assert_eq!(tcs.len(), 1);
        assert_eq!(tcs[0].name, "read_file");
    }

    #[test]
    fn circuit_breaker_opens_after_failures() {
        let cb = CircuitBreaker::new(2, Duration::from_millis(50));
        assert!(cb.allow());
        cb.record_failure();
        assert!(cb.allow());
        cb.record_failure();
        assert!(!cb.allow());
        cb.record_failure();
        assert!(!cb.allow());
    }

    #[test]
    fn circuit_breaker_recovers_after_cooldown() {
        let cb = CircuitBreaker::new(1, Duration::from_millis(30));
        assert!(cb.allow());
        cb.record_failure();
        assert!(!cb.allow());
        std::thread::sleep(Duration::from_millis(60));
        assert!(cb.allow()); // half-open probe
        cb.record_success();
        assert!(cb.allow());
    }

    #[test]
    fn extract_json_finds_balanced_block() {
        assert_eq!(extract_json(r#"xx {"a": {"b": 1}} yy"#).unwrap(), r#"{"a": {"b": 1}}"#);
        assert!(extract_json("no braces").is_none());
    }
}

fn strip_thinking_tags(input: &str) -> String {
    let mut s = input.to_string();
    while let Some(pos) = s.find("[thinking]") {
        if let Some(end) = s[pos..].find('\n') {
            s.replace_range(pos..pos + end + 1, "");
        } else {
            s.replace_range(pos..pos + 10, "");
        }
    }
    while let Some(start) = s.find("<think>") {
        if let Some(end) = s[start..].find("</think>") {
            s.replace_range(start..start + end + 8, "");
        } else {
            s.truncate(start);
            break;
        }
    }
    if let Some(pos) = s.find("Thinking Process:") {
        s.truncate(pos);
    }
    if let Some(pos) = s.find("Thinking:") {
        s.truncate(pos);
    }
    s.trim().to_string()
}
