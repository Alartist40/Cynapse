//! DENDRITE — the persistent graph-memory subsystem.
//!
//! Byte-compatible port of the Go `internal/memory` graph stack:
//! in-memory [`graph::Dendrite`], SQLite persistence via
//! [`store::DendriteStore`], and system-prompt assembly via
//! [`context::DendriteContext`].

pub mod context;
pub mod graph;
pub mod reflection;
pub mod store;

pub use context::DendriteContext;
pub use graph::{Dendrite, Node, NodeType};
pub use reflection::ReflectionWorker;
pub use store::DendriteStore;
