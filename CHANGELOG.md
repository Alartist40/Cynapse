# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0-beta] - 2026-05-12

### Added
- **Architectural**: **DENDRITE** Graph Memory system (Neurons, Branches, Connections).
- **Feature**: Interactive Visual Explorer for knowledge nodes (D3.js).
- **Feature**: Offline support for visual explorer (embedded D3.js).
- **Feature**: Intelligent context assembly with relevance scoring and recency boost.
- **Feature**: Full-text search (FTS5) for long-term memory.
- **Core**: Thread-safe memory core with concurrent stress testing.
- **TUI**: DENDRITE integration in command menu and help.

### Changed
- **Memory**: Replaced flat-file memory with SQLite-backed graph nodes.
- **Build**: Added mandatory `sqlite_fts5` build tag requirement.

### Fixed
- **Performance**: Optimized backlink wiring with placeholder neuron strategy (O(1)).
- **Safety**: Fixed race conditions in prompt assembly and cache invalidation.

## [1.0.0] - 2026-05-08

### Added
- **Architectural**: Tool calling support in streaming mode (`ProcessMessageStream`).
- **Architectural**: Session persistence for streaming responses.
- **Architectural**: Enhanced tool calling support for OpenAI, Anthropic, and Gemini providers.
- **Feature**: `config edit` CLI command to modify configuration using `$EDITOR`.
- **Feature**: `config.CreateDefault` function to generate initial configuration files.
- **Security**: SHA-256 binary verification framework for Synapse installations.
- **TUI**: Tool execution progress feedback in the chat view.
- **TUI**: Dedicated menu hotkey (Ctrl+K) to prevent character-based locking.

### Changed
- **UX**: Changed menu trigger from `/` to `Ctrl+K`.
- **UX**: Updated help text and UI hints to reflect new hotkeys.
- **Core**: Enabled background Curator (heartbeat) mechanism for automatic memory maintenance.
- **Core**: Default configuration path moved to `~/.cynapse/config.yaml`.
- **Core**: Improved goroutine cleanup and context cancellation on TUI exit.

### Fixed
- **Critical**: Corrected import paths across all internal packages (`github.com/yourusername/cynapse` -> `github.com/Alartist40/cynapse`).
- **Critical**: Fixed missing `bufio` import in `internal/llm/client.go`.
- **Critical**: Removed syntax error (orphaned brace) in `internal/llm/client.go`.
- **Security**: Fixed path traversal vulnerability in `resolvePath` helper.
- **Bug**: Fixed streaming context loss where session history was ignored in stream mode.
- **Bug**: Fixed redundant newline issue in CLI help outputs (satisfying `go vet`).
- **Bug**: Updated `session.Entry` to correctly track `ToolCallID` for multi-turn conversations.

### Security
- Added strict workspace boundary checks in `resolvePath` to prevent directory traversal attacks.
- Added infrastructure for mandatory binary checksum verification before execution.
