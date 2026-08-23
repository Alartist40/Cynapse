//! DENDRITE v2 — Asynchronous background memory reflection worker.
//!
//! After user/agent chat turns, this worker runs an out-of-band LLM call
//! to distill key facts (L1) and procedural workflows (L2) from the conversation
//! history, saving them into the Dendrite graph and store without blocking live output.

use std::sync::Arc;
use std::time::Duration;

use crate::dendrite::graph::{Dendrite, NodeType};
use crate::dendrite::store::DendriteStore;
use crate::llm::{LlmClient, Message, Request, Role};

/// Reflects on recent chat history and distills L1 atomic facts / L2 procedures.
pub struct ReflectionWorker {
    graph: Arc<Dendrite>,
    store: Option<Arc<DendriteStore>>,
    llm: Arc<dyn LlmClient>,
}

impl ReflectionWorker {
    pub fn new(
        graph: Arc<Dendrite>,
        store: Option<Arc<DendriteStore>>,
        llm: Arc<dyn LlmClient>,
    ) -> Self {
        Self { graph, store, llm }
    }

    /// Run reflection on recent conversation messages in a background Tokio task.
    pub fn spawn_reflection(&self, messages: Vec<Message>) {
        if messages.len() < 2 {
            return;
        }

        let graph = self.graph.clone();
        let store = self.store.clone();
        let llm = self.llm.clone();

        tokio::spawn(async move {
            if let Err(e) = Self::do_reflection(graph, store, llm, &messages).await {
                eprintln!("[dendrite reflection worker] background task error: {}", e);
            }
        });
    }

    async fn do_reflection(
        graph: Arc<Dendrite>,
        store: Option<Arc<DendriteStore>>,
        llm: Arc<dyn LlmClient>,
        messages: &[Message],
    ) -> Result<(), String> {
        let mut transcript = String::new();
        for msg in messages.iter().take(6) {
            let role = match msg.role {
                Role::User => "User",
                Role::Assistant => "Assistant",
                Role::System => "System",
                Role::Tool => "Tool",
            };
            if !msg.content.is_empty() {
                transcript.push_str(&format!("{}: {}\n", role, msg.content));
            }
        }

        if transcript.is_empty() {
            return Ok(());
        }

        let prompt = format!(
            "Analyze the conversation transcript below. Extract key facts, user preferences, or learned procedural steps.\n\
             Return ONLY a short summary bullet list of facts or steps, preceded by '#fact' or '#procedure'.\n\n\
             TRANSCRIPT:\n{}\n\nFACTS & PROCEDURES:",
            transcript
        );

        let req = Request {
            system_prompt: "You are a memory curator. Summarize key facts.".to_string(),
            messages: vec![Message::text(Role::User, prompt)],
            tools: Vec::new(),
            max_tokens: 200,
            temperature: 0.2,
        };

        let res = llm.chat(&req).await.map_err(|e| e.to_string())?;
        let output = res.content.trim().to_string();

        if output.is_empty() {
            return Ok(());
        }

        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or(Duration::ZERO)
            .as_secs() as i64;

        let node_id = format!("reflection_{}", timestamp);
        let title = format!("Reflected Memory {}", timestamp);

        let node_type = if output.contains("#procedure") {
            NodeType::Procedure
        } else {
            NodeType::AtomicFact
        };

        let node = graph.upsert(&node_id, &title, &output, node_type, Some(vec!["#reflection".into()]));

        if let Some(s) = store {
            let _ = s.save(&node);
        }

        Ok(())
    }
}
