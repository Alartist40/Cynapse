//! Cynapse core library: config, DENDRITE graph memory, sessions,
//! agent loop, LLM providers, and the tool/safety stack.
//!
//! This is the Rust port of the Go `cynapse` agent. Types are named and
//! structured to match the original so that behaviour stays byte-compatible.

pub mod compressor;
pub mod config;
pub mod dendrite;
pub mod llm;
pub mod persona;
pub mod redact;
pub mod session;

/// Semantic version reported by `cynapse version`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
