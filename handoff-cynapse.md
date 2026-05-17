# Cynapse Handoff Document

> **Session Date:** 2026-05-14  
> **Version:** v2.0.0-beta → v2.1.0-dev  
> **Repository:** https://github.com/Alartist40/cynapse.git

---

## Goal

**Cynapse is the "motherboard" AI agent — a lightweight, terminal-first Go application that connects LEGO-piece synapses (plugins) into a unified, persistent AI system.**

The vision:
- Install Cynapse once. Add synapses (LeafcutterLLM, git-tools, web-automation, etc.) as needed.
- Each synapse is discovered via `--meta` and exposed as an MCP tool.
- Memory persists across API/model changes via the DENDRITE graph system.
- Cross-platform: runs on Raspberry Pi 5, desktop x86_64, and eventually mobile.

Cynapse is the synapse. LeafcutterLLM is a heavyweight optional extension for local quantized inference.

---

## Current State

### ✅ Completed in This Session

| Feature | Status | Files |
|---------|--------|-------|
| **Leafcutter `--meta` integration** | ✅ Done | `LeafcutterLLM/rust/src/main.rs` |
| **Synapse local-path installation** | ✅ Done | `internal/synapse/registry.go`, `cmd/cynapse/main.go` |
| **Synapse manifest system (`synapses.json`)** | ✅ Done | `internal/synapse/registry.go` |
| **Synapse SHA-256 URL download** | ✅ Done | `internal/synapse/registry.go` |
| **OpenAI SSE streaming** | ✅ Done | `internal/llm/client.go` |
| **Anthropic SSE streaming** | ✅ Done | `internal/llm/client.go` |
| **DENDRITE multi-hop traversal (2-hop, 3-hop BFS)** | ✅ Done | `internal/memory/dendrite.go` |
| **DENDRITE relevance engine fix** | ✅ Done | `internal/memory/dendrite_context.go` |
| **DENDRITE token budget bugfix** | ✅ Done | `internal/memory/dendrite_context.go` |
| **DENDRITE fact deduplication** | ✅ Done | `internal/memory/memory.go` |
| **DENDRITE FTS5 graceful fallback** | ✅ Done | `internal/memory/dendrite_store.go` |
| **Integration test suite (13 tests)** | ✅ All Pass | `internal/memory/dendrite_integration_test.go` |
| **Full project build** | ✅ Clean | All packages |

### 🔄 In Progress / Partial

| Feature | Status | Notes |
|---------|--------|-------|
| **Gemini streaming** | ❌ Stubbed | Returns "not implemented" — lowest priority |
| **Remote synapse registry** | ❌ Not built | `Registry.Install(name)` without `--path` returns error pointing to `--path` usage |
| **Cynapse ↔ Leafcutter runtime bridge** | ❌ Not started | Synapse installs but Cynapse doesn't yet use Leafcutter as an LLM backend |

### 🚧 Blocked

| Blocker | Impact | Resolution |
|---------|--------|------------|
| None | — | — |

---

## Active Files

### Core Application
- **`cmd/cynapse/main.go`** — Entry point. CLI parsing, TUI initialization, synapse/config subcommands. Updated to support `--path` flag for synapse installation.
- **`internal/llm/client.go`** — LLM client factory + implementations for Anthropic, OpenAI, Gemini, Ollama. Now has full SSE streaming for OpenAI and Anthropic (with tool-call buffering and reconstruction).
- **`internal/agent/agent.go`** — Core agent loop. Tool execution, streaming orchestration, background self-improvement fork. Unchanged in this session.
- **`internal/tui/tui.go`** — Bubble Tea TUI. Streaming chunk consumption, menu system, DENDRITE server launcher. Unchanged in this session.

### Synapse System
- **`internal/synapse/registry.go`** — Completely rewritten. Supports:
  - `Discover(dir)` — scans for executables, reads `synapses.json` manifest, falls back to `--meta`
  - `Install(name, dir)` — known-synapse lookup (currently returns helpful error)
  - `InstallFromPath(name, dir, sourcePath)` — copy binary, chmod, verify `--meta`, write manifest
  - `InstallFromURL(name, dir, url, hash)` — download with optional SHA-256 verification
  - `Uninstall(name, dir)` — removes binary + manifest entry
  - `VerifyBinary(filePath, hash)` — SHA-256 checksum verification
  - `synapses.json` manifest persistence in `~/.cynapse/synapses/`

### Memory System (DENDRITE)
- **`internal/memory/dendrite.go`** — In-memory graph. Thread-safe. Auto-wires backlinks on `Upsert()`. Now includes `Neighbors2Hop()` and `Neighbors3Hop()` for richer context retrieval.
- **`internal/memory/dendrite_context.go`** — Prompt assembler. Token-budgeted (40% core / 60% context). Fixed `findRelevant()` to use FTS5 + word-by-word search + stop-word filtering. Fixed token budget overflow bug.
- **`internal/memory/dendrite_store.go`** — SQLite persistence. WAL mode. **Now gracefully falls back to `LIKE`-based search when FTS5 is unavailable** (critical for Pi 5, minimal Linux, embedded systems).
- **`internal/memory/memory.go`** — Persona manager. Bridges markdown files ↔ graph nodes. Now deduplicates facts in `SaveFact()`.
- **`internal/memory/dendrite_integration_test.go`** — New comprehensive test suite covering full lifecycle, multi-hop traversal, fact deduplication, and FTS5 relevance.

### Configuration
- **`internal/config/config.go`** — Config loading/saving. Unchanged.
- **`internal/session/manager.go`** — Session persistence (JSONL). Unchanged.
- **`internal/tools/tools.go`** — Local tool registry. Unchanged.
- **`internal/mcp/manager.go`** — MCP server manager. Unchanged.

---

## Recent Changes

### 1. LeafcutterLLM `--meta` Flag
**File:** `../LeafcutterLLM/rust/src/main.rs`  
Added `--meta` CLI argument that prints Cynapse-compatible synapse metadata JSON and exits without loading a model. This enables synapse discovery without requiring a model file.

### 2. Synapse Installation System (Complete Rewrite)
**Files:** `internal/synapse/registry.go`, `cmd/cynapse/main.go`
- Replaced stub `Install()` with full local-path installation
- Added `synapses.json` manifest for metadata persistence
- Added `InstallFromPath()` — copies, chmods, verifies `--meta`, records manifest
- Added `InstallFromURL()` — downloads with optional SHA-256 verification
- Added `Discover()` manifest-first discovery with `--meta` fallback
- CLI updated: `cynapse synapse add leafcutter --path ./leafcutter`

### 3. OpenAI & Anthropic Streaming
**File:** `internal/llm/client.go`
- Implemented full SSE (Server-Sent Events) parsing for both providers
- Text chunks forwarded in real-time to TUI
- Tool calls buffered from deltas and reconstructed at stream end
- Compatible with existing agent tool-loop logic

### 4. DENDRITE Robustness Overhaul
**Files:** `internal/memory/*.go`
- **Multi-hop traversal:** `Neighbors2Hop()`, `Neighbors3Hop()` for richer context
- **Relevance engine fix:** `findRelevant()` now uses FTS5 + word-by-word title/content/tag search + stop-word filtering. Previously searched for the entire query string as a substring (almost never matched).
- **Token budget fix:** `used+cost > used+ctxBudget` → `used+cost > maxTokens`
- **FTS5 fallback:** Store creates a `LIKE`-based fallback table when FTS5 extension is unavailable. Critical for cross-platform deployment.
- **Fact deduplication:** `SaveFact()` checks for identical existing memory before creating new nodes.

### 5. Integration Test Suite
**File:** `internal/memory/dendrite_integration_test.go`
- `TestDendrite_FullLifecycle` — create → link → query → persist → reload
- `TestDendrite_MultiHopTraversal` — 1-hop, 2-hop, 3-hop BFS verification
- `TestDendrite_FactDeduplication` — duplicate prevention
- `TestDendrite_FTS5Relevance` — prompt assembly with relevance scoring

---

## Failed Attempts

### 1. Direct `Registry.Install()` Remote Download
**What was tried:** Implementing a full remote registry with HTTP download URLs for each known synapse.
**Why it failed:** No remote registry server exists yet. The synapse metadata in `getKnownSynapses()` has no download URLs.
**Resolution:** Implemented `InstallFromPath()` and `InstallFromURL()` instead. The CLI now guides users to use `--path` for local binaries. A remote registry can be added later without API changes.

### 2. Anthropic Tool Call Streaming (Initial Approach)
**What was tried:** Streaming Anthropic tool calls the same way as Ollama (JSON array chunk at end).
**Why it failed:** Anthropic's streaming format uses `content_block_delta` with `partial_json` fragments that must be accumulated across multiple SSE events.
**Resolution:** Implemented proper fragment buffering with `content_block_start` (for ID/Name) + `content_block_delta` (for `partial_json`) reconstruction.

### 3. FTS5-First Persistence Tests
**What was tried:** Running persistence tests assuming FTS5 was available.
**Why it failed:** The test environment (and many minimal Linux installs) lacks the SQLite FTS5 extension.
**Resolution:** Made `DendriteStore` gracefully detect missing FTS5 and fall back to a regular `dendrite_fts_fallback` table with `LIKE` queries. All tests now pass regardless of FTS5 availability.

### 4. Wiki-Link Placeholder Cleanup in Tests
**What was tried:** Writing test content with `[[leafcutter]]` inside a sentence saying "No longer mentioning [[leafcutter]]".
**Why it failed:** The wiki-link parser correctly identified `[[leafcutter]]` as a link, so the backlink was maintained despite the test expecting it to be removed.
**Resolution:** Changed test content to plain text "leafcutter" (no brackets) to properly test backlink rewiring.

---

## Next Steps

### Immediate (Next Session)
1. **Implement Gemini streaming** — last remaining streaming stub
2. **Build Cynapse ↔ Leafcutter runtime bridge** — make Cynapse use Leafcutter as an LLM provider (add `leafcutter` provider to `llm.New()`)
3. **Write synapse development docs** — guide for building custom synapses

### Follow-up
4. **Remote synapse registry** — JSON endpoint listing available synapses with download URLs
5. **Semantic search in DENDRITE** — integrate sentence embeddings for vector similarity (instead of purely lexical)
6. **Graph metrics API** — centrality, clustering coefficient, pathfinding for the D3.js visualizer

### Longer-term
7. **Mobile support** — investigate Termux/Flutter wrapper for Android
8. **Voice synapse** — speech-to-text + text-to-speech integration
9. **Multi-agent federation** — Cynapse instances communicating via shared DENDRITE graphs

---

## Context to Preserve

### Key Decisions
1. **Synapse protocol is `--meta` JSON output** — any executable that prints synapse metadata when called with `--meta` is a valid synapse. This is simple, language-agnostic, and doesn't require complex RPC.
2. **Manifest-first discovery** — `synapses.json` in `~/.cynapse/synapses/` caches metadata so we don't need to execute every binary on startup. Binaries without `--meta` can still be registered via manual manifest entries.
3. **FTS5 is optional, not required** — DENDRITE must work on minimal systems. The fallback `LIKE`-based search is slower but universally compatible.
4. **Streaming tool calls are buffered, not real-time** — OpenAI and Anthropic stream tool call fragments. We accumulate them and emit a reconstructed JSON chunk at stream end, matching Ollama's behavior and keeping the agent loop simple.

### Dependencies & Constraints
- **Go 1.22+** required
- **CGO enabled** (for SQLite) — `go-sqlite3` requires a C compiler
- **Bubble Tea** for TUI — adds ~2MB to binary
- **WAL mode SQLite** — creates `-wal` and `-shm` files alongside `.db`
- **FTS5** — nice-to-have, not required. Fallback works on all platforms.

### Environment Setup Notes
```bash
# Build from source
cd /home/xander/Documents/portfolio/cynapse
go build -o cynapse ./cmd/cynapse

# Run tests
go test ./...

# Install Leafcutter synapse (after building Leafcutter)
cynapse synapse add leafcutter \
  --path /home/xander/Documents/portfolio/LeafcutterLLM/rust/target/release/leafcutter

# Verify synapse loaded
cynapse synapse list
```

### Test Results Snapshot
```
ok  github.com/Alartist40/cynapse/internal/api      0.003s
ok  github.com/Alartist40/cynapse/internal/memory   0.018s  (13 tests, all pass)
```

---

## Related Repositories

- **Cynapse:** https://github.com/Alartist40/cynapse.git
- **LeafcutterLLM:** https://github.com/Alartist40/LeafcutterLLM.git
- **Portfolio record:** `/home/xander/Documents/portfolio/kimi-pathfinder.md` Section 21

---

*This handoff was generated to preserve context across sessions. The Cynapse project is actively developed and welcomes contributions.*
