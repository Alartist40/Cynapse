//! Terminal UI for cynapse, built on ratatui.
//!
//! The root `cynapse` binary re-exports everything from this crate
//! (and transitively `cynapse_core`) via the pattern below, matching
//! jcode's single-entry-point layout.

pub use cynapse_core::*;

pub mod app;
pub mod theme;
