# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.0] - 2026-06-16

### Added
- **Architectural**: `internal/compressor` package — automatic context-window
  compression that archives middle turns into DENDRITE memory nodes when
  the live transcript exceeds 50% of the model's context length.  The
  active transcript retains `[head + handoff + tail]`.  Wired into both
  `ProcessMessage` and `ProcessMessageStream`, plus a `/compress` slash
  command to force the operation.
- **Architectural**: `internal/confirm` package — interactive human-in-the-loop
  prompt protocol with `Decline / AllowOnce / AllowSection / AllowAlways`
  choices.  Persistent allowlist at `~/.cynapse/allowlist` survives
  restarts; sensitive requests (sudo, password) refuse the `Always`
  option so secrets are never persisted.  Bash tool routes sudo
  commands through `sudo -S -p ''` with the typed password fed on stdin.
- **Architectural**: `internal/redact` package — secret-pattern scanner
  covering OpenAI / Anthropic / HF / GitHub / AWS / Slack / Stripe /
  Twilio tokens, PEM keys, JWTs, plus URL query-param leaks and a
  recursive JSON-key walk.  Agent runs every tool output and final
  reply through it before persistence.
- **Architectural**: `internal/approval` package — destructive-shell
  pattern detector (mkfs, dd-of-dev, rm-rf, fork bombs, curl|bash,
  dev-tcp, force-push, …).  Two canned policies: `balanced` (default,
  Warn+ prompts, Danger+ denies) and `trust-local` (Critical only).
- **Architectural**: `internal/netguard` package — SSRF guard for
  outbound HTTP.  Blocks loopback, RFC1918, link-local, and the AWS
  metadata 169.254.169.254 endpoint by default; a `LocalDevPolicy`
  loosens it so Ollama on localhost still works.
- **Configuration**: new `security: { mode, redact_secrets, net_policy,
  approval_policy }` block in `config.yaml`.  Three modes:
  `trust-local`, `standard`, `strict`.
- **TUI**: `/compress` slash command for manual compaction.
- **Tests**: 9 confirm + 11 approval + 10 netguard + 11 redact +
  10 compressor + 5 tools integration = **56 new tests**, all green.

### Changed
- **Session files**: transcripts now respect `cfg.SessionFileMode()` —
  `0600` under `strict` security mode, `0644` otherwise.
- **Config files**: `config.yaml` is now written `0600` (was `0644`).
- **Toolset**: `tools.BuildProfile` signature gains policy/confirm
  parameters; `WebFetchTool` requires a `netguard.Policy`.
- **Tool interface**: `Confirmer` is now an interface (`Check(req)
  (Resolved, error)`) instead of a single-shot bool callback.

### Security
- Closed-loop verification: `go test ./...` passes; `go vet ./...` clean.
- All four heuristic layers (`redact`, `approval`, `netguard`,
  `confirm`) are pure Go, stdlib only, and gated independently.

## [2.2.0] - 2026-05-20

### Added
- **Architectural**: HuggingFace model search & download pipeline.
- **Architectural**: Local model registry (JSON) under `~/.cynapse/models/`.
- **Architectural**: Ollama GGUF import via auto-generated Modelfiles.
- **Architectural**: Direct llama-server subprocess provider (auto port,
  OpenAI-compatible /v1/chat/completions interface).
- **Architectural**: Multimodal attachments (images, PDFs, text).
- **Architectural**: HF authentication (`--token`, `HF_TOKEN` env, config).
- **TUI**: `/attach`, `/attachments`, `/clear-attach` slash commands.
- **TUI**: Local Models menu for switching Ollama vs direct inference.

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
