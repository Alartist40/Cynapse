//! Cynapse core library: config, DENDRITE graph memory, sessions,
//! agent loop, LLM providers, and the tool/safety stack.
//!
//! This is the Rust port of the Go `cynapse` agent. Types are named and
//! structured to match the original so that behaviour stays byte-compatible.

pub mod adhd;
pub mod agent;
pub mod approval;
pub mod attachments;
pub mod compressor;
pub mod config;
pub mod confirm;
pub mod dendrite;
pub mod gateway;
pub mod graft;
pub mod hf;
pub mod llm;
pub mod netguard;
pub mod ocr;
pub mod persona;
pub mod redact;
pub mod session;
pub mod tools;

/// Semantic version reported by `cynapse version`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
