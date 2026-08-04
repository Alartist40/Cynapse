//! Anthropic provider (feature-gated).
//!
//! Ported structure for the `anthropic` feature. V1 defaults do not
//! compile this in; the factory returns a helpful error otherwise.

use async_trait::async_trait;
use serde_json::{json, Value};

use crate::config::LlmConfig;
use crate::llm::providers::{BaseClient, Cancelled, LlmClient, StreamHandle};
use crate::llm::{Request, Response};

pub struct AnthropicClient {
    base: BaseClient,
    api_key: String,
    model: String,
}

impl AnthropicClient {
    pub fn new(base: BaseClient, api_key: String, model: String) -> AnthropicClient {
        AnthropicClient { base, api_key, model }
    }

    pub fn from_config(cfg: &LlmConfig) -> anyhow::Result<AnthropicClient> {
        let http = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(300))
            .build()?;
        Ok(AnthropicClient {
            base: BaseClient { http, max_retries: cfg.max_retries },
            api_key: cfg.anthropic_key.clone(),
            model: cfg.model.clone(),
        })
    }
}

#[async_trait]
impl LlmClient for AnthropicClient {
    async fn chat(&self, _req: &Request) -> anyhow::Result<Response> {
        anyhow::bail!("anthropic non-streaming chat not implemented yet (feature under construction)")
    }

    fn chat_stream(&self, _req: &Request, _cancelled: Cancelled) -> StreamHandle {
        let (_, chunks) = tokio::sync::mpsc::unbounded_channel();
        let (errors_tx, errors) = tokio::sync::mpsc::unbounded_channel();
        let _ = errors_tx.send(anyhow::anyhow!(
            "anthropic streaming not implemented yet (feature under construction)"
        ));
        StreamHandle { chunks, errors }
    }

    fn provider(&self) -> &'static str {
        "anthropic"
    }
}

#[allow(unused)]
fn _shape_placeholder() -> Value {
    json!({"model": "", "max_tokens": 0, "messages": [], "tools": []})
}
