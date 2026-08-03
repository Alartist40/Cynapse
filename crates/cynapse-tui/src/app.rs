//! The chat TUI application.
//!
//! Implemented in milestone 6. This module currently only hosts the
//! entrypoint shape so the binary and CLI can be wired end-to-end.

use anyhow::Result;

/// Entrypoint for the interactive chat TUI.
///
/// `session_key` selects which persisted session to open ("" = new).
pub async fn run(_session_key: Option<String>) -> Result<()> {
    anyhow::bail!("chat TUI not yet implemented (milestone 6)")
}
