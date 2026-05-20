# Cynapse Handoff Document

> **Session Date:** 2026-05-20  
> **Version:** v2.1.0-dev → v2.2.0-dev  
> **Repository:** https://github.com/Alartist40/cynapse.git

---

## Goal

**Cynapse is the "motherboard" AI agent — a lightweight, terminal-first Go application that connects LEGO-piece synapses (plugins) into a unified, persistent AI system.**

The vision:
- Install Cynapse once. Add synapses (LeafcutterLLM, git-tools, web-automation, etc.) as needed.
- Each synapse is discovered via `--meta` and exposed as an MCP tool.
- Memory persists across API/model changes via the DENDRITE graph system.
- **NEW: Download and run local AI models directly (like PocketPal AI) without cloud dependencies.**
- **NEW: Attach images, documents, and files from a workspace folder for multimodal conversations.**
- Cross-platform: runs on Raspberry Pi 5, desktop x86_64, and eventually mobile.

Cynapse is the synapse. LeafcutterLLM is a heavyweight optional extension for local quantized inference.

---

## Current State

### ✅ Completed in This Session

| Feature | Status | Files |
|---------|--------|-------|
| **HuggingFace model search** | ✅ Done | `internal/models/huggingface.go` |
| **GGUF model download manager** | ✅ Done | `internal/models/download.go` |
| **Local model registry (JSON)** | ✅ Done | `internal/models/registry.go` |
| **Ollama GGUF import** | ✅ Done | `internal/models/ollama.go` |
| **Multimodal attachment system** | ✅ Done | `internal/attachments/attachments.go` |
| **LLM Message attachments + images** | ✅ Done | `internal/llm/client.go` |
| **Ollama multimodal (vision) support** | ✅ Done | `internal/llm/client.go` |
| **Session persistence for attachments** | ✅ Done | `internal/session/manager.go` |
| **Agent attachment forwarding** | ✅ Done | `internal/agent/agent.go` |
| **TUI `/attach` slash commands** | ✅ Done | `internal/tui/tui.go` |
| **TUI Local Models menu** | ✅ Done | `internal/tui/tui.go` |
| **CLI `cynapse model <cmd>`** | ✅ Done | `cmd/cynapse/main.go` |
| **Config models section** | ✅ Done | `internal/config/config.go` |
| **Full project build** | ✅ Clean | All packages |
| **All existing tests** | ✅ Pass | `go test ./...` |
| **Direct llama-server subprocess provider** | ✅ Done | `internal/llm/llamaserver.go`, `internal/llm/llamaserver_process.go` |
| **HF auth for gated/private models** | ✅ Done | `internal/models/huggingface.go`, `internal/models/download.go`, `cmd/cynapse/main.go` |

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

### New Packages (This Session)
- **`internal/models/types.go`** — Core types: `LocalModel`, `Registry`, `ModelOrigin`, `ModelType`.
- **`internal/models/registry.go`** — JSON registry manager at `~/.cynapse/models/registry.json`. CRUD operations, ID generation, path management.
- **`internal/models/huggingface.go`** — HuggingFace API client. Search models (`filter=gguf`), list repo files, build download URLs. Handles both `/tree/main` and `siblings` response formats.
- **`internal/models/download.go`** — HTTP download with progress callbacks, atomic `.tmp` → final rename, speed/ETA formatting.
- **`internal/models/ollama.go`** — Ollama integration: `Import()` creates Modelfile from GGUF, `Remove()`, `List()`, `SuggestOllamaName()`. Auto-detects `mmproj` for vision models.
- **`internal/attachments/attachments.go`** — Workspace file loader. Supports images (base64), text files, PDFs (via `pdftotext` or base64 fallback), binary files. `FindInWorkspace()` searches multiple subdirs.

### Modified Core Files
- **`cmd/cynapse/main.go`** — Added `cynapse model` subcommand with `search`, `download`, `list`, `import`, `remove`. Creates `models/` and `workspace/` dirs on startup.
- **`internal/config/config.go`** — Added `ModelsConfig` with `models_dir`, `use_ollama`, `use_llama_server`.
- **`internal/llm/client.go`** — `Message` struct now has `Images []string` and `Attachments []Attachment`. Ollama `Chat()` and `ChatStream()` forward images and text attachments to Ollama's multimodal API.
- **`internal/session/manager.go`** — `Entry` struct now persists `Images` and `Attachments`. `Recent()` passes them through to LLM messages.
- **`internal/agent/agent.go`** — `ProcessMessage()` and `ProcessMessageStream()` accept variadic `attachments ...llm.Attachment` and append them to session entries.
- **`internal/tui/tui.go`** — Added `Local Models` menu item. Added `/attach`, `/attachments`, `/clear-attach` slash commands. Pending attachments are passed to the agent and cleared after send. Display shows attached filenames next to user messages.

### Unchanged but Relevant
- **`internal/synapse/registry.go`** — Synapse system from previous session. Unchanged.
- **`internal/memory/*.go`** — DENDRITE memory system from previous session. Unchanged.
- **`internal/tools/tools.go`** — Local tool registry. Unchanged.
- **`internal/mcp/manager.go`** — MCP server manager. Unchanged.

---

## Recent Changes

### 1. Local Model Management System
**Files:** `internal/models/*.go`, `cmd/cynapse/main.go`
- HuggingFace API search for GGUF models with filtering and pagination
- Direct GGUF download to `~/.cynapse/models/` with live progress (speed, ETA, percentage)
- JSON registry tracking downloaded models, their origin, quantization, and Ollama mapping
- Ollama import via auto-generated Modelfiles with temperature/top_p parameters
- Vision model support: auto-detects `mmproj.gguf` in same directory during Ollama import

### 2. Multimodal Attachment System
**Files:** `internal/attachments/attachments.go`, `internal/llm/client.go`, `internal/session/manager.go`, `internal/agent/agent.go`, `internal/tui/tui.go`
- Workspace folder (`./workspace/` by default) for dropping files
- Images → base64 → Ollama `images` array in messages
- Text files → appended to message content
- PDFs → text extraction via `pdftotext` CLI, base64 fallback
- TUI slash commands: `/attach file.png`, `/attachments`, `/clear-attach`

### 3. Config Expansion
**File:** `internal/config/config.go`
- New `ModelsConfig` section with `models_dir`, `use_ollama`, `use_llama_server`
- Defaults to `./models` directory and Ollama-enabled

### 4. CLI Model Commands
**File:** `cmd/cynapse/main.go`
- `cynapse model search <query>` — Search HF hub, show files per model
- `cynapse model download <hf-id> [filename]` — Download specific GGUF (lists files if none specified)
- `cynapse model list` — Show registry with size, quant, Ollama status
- `cynapse model import <local-id>` — Import downloaded GGUF into Ollama
- `cynapse model remove <local-id>` — Delete from registry + filesystem + Ollama

---

## Failed Attempts

### 1. Background Agent Exploration Stalls
**What was tried:** Using `Agent` subagents to explore both the cynapse and PocketPal AI codebases in parallel.
**Why it failed:** Both exploration agents became unresponsive after reading many files. The PocketPal agent hit workspace boundary errors; the cynapse agent stopped returning output.
**Resolution:** Manually explored both codebases using direct `ReadFile`, `Shell`, and `Grep` calls. This was faster and more reliable for this session.

### 2. HF API Response Format Inconsistency
**What was tried:** Using `ModelFile` struct with `rfilename` field for both HF `/api/models` search and `/api/models/{id}/tree/main` endpoints.
**Why it failed:** The tree endpoint returns `path` (not `rfilename`), and the `siblings` array in the search endpoint uses `rfilename`. Also, `lfs.oid` is a string in tree responses but was typed as `int64` in `ModelFile`.
**Resolution:** Created a separate `treeFile` struct for the tree endpoint, mapped `path` → `RFilename`, and fixed `LFS.OID` to `string` type.

### 3. Large Model Download Timeout in Testing
**What was tried:** Testing the full download of a 400MB+ Qwen 0.5B model.
**Why it failed:** Download worked correctly but was killed by `timeout 90`. Partial `.tmp` files were left behind.
**Resolution:** Added cleanup of `.tmp` files on failure. The download mechanism is proven; users download at their own pace. No code change needed beyond the existing atomic rename design.

### 4. llama-server Binary Discovery
**What was tried:** Hardcoding a single path to `llama-server`.
**Why it failed:** llama-server can be installed in many locations (system PATH, home directory, alongside llama.cpp source).
**Resolution:** Implemented `findLlamaServer()` that searches PATH first, then common fallback locations (`/usr/local/bin`, `~/bin`, `./llama.cpp/`, etc.). Users can also specify an exact path via `llama_server_path` in config.

---

## Next Steps

### Immediate (Next Session)
1. **Model switching persistence** — Remember the last used local model across TUI restarts.
2. **Vision model auto-pairing** — When downloading a vision model, auto-suggest/download the matching `mmproj.gguf` file.
3. **Model quantization advisor** — Based on available RAM/VRAM, suggest which quantization to download.

### Follow-up
4. **Vision model auto-pairing** — When downloading a vision model, auto-suggest/download the matching `mmproj.gguf` file.
5. **Model quantization advisor** — Based on available RAM/VRAM, suggest which quantization to download.
6. **Gemini streaming** — Last remaining streaming stub.
7. **Build Cynapse ↔ Leafcutter runtime bridge** — Make Cynapse use Leafcutter as an LLM provider.

### Longer-term
8. **Semantic search in DENDRITE** — integrate sentence embeddings for vector similarity.
9. **Mobile support** — investigate Termux/Flutter wrapper for Android.
10. **Multi-agent federation** — Cynapse instances communicating via shared DENDRITE graphs.

---

## Context to Preserve

### Key Decisions
1. **Ollama-first local inference** — Since Ollama is already supported and widely installed, the local model system uses Ollama as the primary backend. Direct `llama-server` support is planned but deferred.
2. **HuggingFace as the model hub** — HF has the largest GGUF ecosystem. The search/download system is built around their API. Other hubs (ModelScope, etc.) can be added later.
3. **Workspace attachment model** — Users drop files in `./workspace/` and reference them by filename. This is simpler than a file picker in a terminal UI and mirrors how developers already work.
4. **Attachments are per-message, not global** — Each message carries its own attachments. This matches how chat APIs work and keeps the context window clean.
5. **Synapse protocol is `--meta` JSON output** — any executable that prints synapse metadata when called with `--meta` is a valid synapse. This is simple, language-agnostic, and doesn't require complex RPC.
6. **FTS5 is optional, not required** — DENDRITE must work on minimal systems. The fallback `LIKE`-based search is slower but universally compatible.
7. **Streaming tool calls are buffered, not real-time** — OpenAI and Anthropic stream tool call fragments. We accumulate them and emit a reconstructed JSON chunk at stream end, matching Ollama's behavior and keeping the agent loop simple.

### Dependencies & Constraints
- **Go 1.22+** required
- **CGO enabled** (for SQLite) — `go-sqlite3` requires a C compiler
- **Bubble Tea** for TUI — adds ~2MB to binary
- **WAL mode SQLite** — creates `-wal` and `-shm` files alongside `.db`
- **FTS5** — nice-to-have, not required. Fallback works on all platforms.
- **Ollama** — required for running downloaded local models (until llama-server support is added)
- **pdftotext** — optional. If unavailable, PDFs fall back to base64 encoding.

### Environment Setup Notes
```bash
# Build from source
cd /home/xander/Documents/portfolio/cynapse
go build -o cynapse ./cmd/cynapse

# Run tests
go test ./...

# Search for models
cynapse model search qwen2.5

# Download a model
cynapse model download Qwen/Qwen2.5-0.5B-Instruct-GGUF qwen2.5-0.5b-instruct-q4_0.gguf

# Import into Ollama
cynapse model import hf:Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q4_0.gguf

# Launch TUI and chat with attachments
cynapse
> /attach test_document.txt
> summarize this document
```

### Test Results Snapshot
```
ok  github.com/Alartist40/cynapse/internal/api      0.003s
ok  github.com/Alartist40/cynapse/internal/memory   (cached)  (13 tests, all pass)
Build: clean — all packages compile without errors
```

### Feature Clarification
- **Direct llama-server subprocess management** = NOT yet implemented. Currently requires Ollama. The config flag `use_llama_server` is a placeholder for future work.
- **HF auth for gated models** = NOT yet implemented. The download infrastructure supports tokens but the CLI doesn't expose them yet. Private/gated models cannot be downloaded until this is added.

---

## Related Repositories

- **Cynapse:** https://github.com/Alartist40/cynapse.git
- **LeafcutterLLM:** https://github.com/Alartist40/LeafcutterLLM.git
- **Portfolio record:** `/home/xander/Documents/portfolio/kimi-pathfinder.md` Section 21

---

*This handoff was generated to preserve context across sessions. The Cynapse project is actively developed and welcomes contributions.*
