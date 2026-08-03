//! LLM message types shared across providers, sessions, and the agent.
//!
//! Faithful port of the type definitions in Go
//! `internal/llm/client.go`. JSON shapes match so session JSONL and
//! provider payloads interoperate with the original.

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Conversation role.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    System,
    User,
    Assistant,
    Tool,
}

impl Role {
    pub fn as_str(&self) -> &'static str {
        match self {
            Role::System => "system",
            Role::User => "user",
            Role::Assistant => "assistant",
            Role::Tool => "tool",
        }
    }

    pub fn from_str(s: &str) -> Role {
        match s {
            "system" => Role::System,
            "user" => Role::User,
            "assistant" => Role::Assistant,
            "tool" => Role::Tool,
            _ => Role::User,
        }
    }
}

impl std::fmt::Display for Role {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// A file attached to a message.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Attachment {
    /// "image" | "text" | "pdf" | "binary"
    #[serde(rename = "type")]
    pub kind: String,
    pub filename: String,
    pub mime: String,
    /// text or base64
    pub content: String,
}

/// A tool invocation the model requested.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ToolCall {
    pub id: String,
    pub name: String,
    /// Raw JSON argument object.
    pub arguments: Value,
}

/// Tool schema advertised to the model.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ToolSchema {
    pub name: String,
    pub description: String,
    /// JSON-Schema-style parameter definition.
    pub parameters: Value,
}

/// A single message in the conversation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Message {
    pub role: Role,
    pub content: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_call_id: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub tool_calls: Vec<ToolCall>,
    /// Base64-encoded images for multimodal models (Ollama format).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub images: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub attachments: Vec<Attachment>,
}

impl Message {
    pub fn text(role: Role, content: impl Into<String>) -> Message {
        Message {
            role,
            content: content.into(),
            tool_call_id: None,
            tool_calls: Vec::new(),
            images: Vec::new(),
            attachments: Vec::new(),
        }
    }
}

/// A generation request.
#[derive(Debug, Clone)]
pub struct Request {
    pub system_prompt: String,
    pub messages: Vec<Message>,
    pub tools: Vec<ToolSchema>,
    pub max_tokens: u64,
    pub temperature: f64,
}

impl Default for Request {
    fn default() -> Self {
        Request {
            system_prompt: String::new(),
            messages: Vec::new(),
            tools: Vec::new(),
            max_tokens: 4096,
            temperature: 0.7,
        }
    }
}

/// A non-streamed generation response.
#[derive(Debug, Clone, Default)]
pub struct Response {
    pub content: String,
    pub tool_calls: Vec<ToolCall>,
    pub usage: Usage,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Usage {
    pub input_tokens: usize,
    pub output_tokens: usize,
}

/// Token count estimate shared by the compressor (≈ 4 chars/token).
pub fn estimate_tokens_chars(text: &str) -> usize {
    let runes = text.chars().count();
    let t = (runes + 3) / 4;
    t.max(1)
}
