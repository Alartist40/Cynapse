# Cynapse Handoff Document

> **Session Date:** 2026-08-30  
> **Version:** v2.4.0  
> **Repository:** https://github.com/Alartist40/cynapse.git  
> **License:** MIT

---

## What Is Cynapse?

**Cynapse is the "motherboard" AI agent** — a terminal-first Go application that connects models, memory, tools, and files into a single, persistent, private AI system.

**The metaphor:** A motherboard doesn't *do* computation — it connects the CPU, GPU, RAM, and storage so they work as one system. Cynapse doesn't *generate* intelligence — it connects LLMs, memory (DENDRITE), tools (synapses), and files so they work as one brain.

**One-line install:**
```bash
curl -fsSL https://raw.githubusercontent.com/Alartist40/cynapse/main/install.sh | bash
```

---

## What Makes It Unique

| Feature | How Cynapse Does It | Why It Matters |
|---------|---------------------|----------------|
| **Model Management** | Search & download GGUFs from HuggingFace directly in terminal | Like PocketPal AI, but for desktop — no browser, no Python |
| **Persistent Memory** | DENDRITE knowledge graph (nodes + edges) with multi-hop BFS | Remembers facts and relationships, not just chat history |
| **Multimodal** | Drop files in `./workspace/`, `/attach` in chat | Images, PDFs, text — all in a terminal UI |
| **Plugins** | Any executable with `--meta` JSON output | Language-agnostic: Rust, Python, Bash, C — no SDK |
| **Local Inference** | Ollama integration OR direct llama-server subprocess | Run models offline, zero API costs, total privacy |
| **Self-Compressing Context** | At 50% of model context, middle turns archive into DENDRITE | Long sessions stay usable without manual `/clear` |
| **Heuristic Safety Stack** | approval + netguard + redact + confirm (operator prompts) | Catches cooperative-mode mistakes without removing capability |
| **Portability** | Single Go binary (~15MB) | Runs on Pi 5, desktop, server, WSL — no Python dependency hell |

---

## Current State (v2.4.0)

### ✅ Completed

| Feature | Files |
|---------|-------|
| **Vendored llama.cpp (b10434) — static, no Ollama dep** | `leafcutter/llama.cpp/`, `leafcutter/build.rs` |
| **FFI struct layouts aligned to b10434** | `leafcutter/src/llama_ffi/bindings.rs` |
| **Optimized sampler (zero alloc hot path)** | `leafcutter/src/inference/sampler.rs` |
| **2.5+ tok/s on ARMv9-A (matches Ollama)** | Benchmarked on Orange Pi 6 Plus |
| HuggingFace model search & download | `internal/models/*.go` |
| Local model registry (JSON) | `internal/models/registry.go` |
| Ollama GGUF import | `internal/models/ollama.go` |
| Direct llama-server subprocess provider | `internal/llm/llamaserver.go`, `llamaserver_process.go` |
| Multimodal attachments (images, PDFs, text) | `internal/attachments/attachments.go` |
| TUI `/attach` slash commands | `internal/tui/tui.go` |
| TUI Local Models menu | `internal/tui/tui.go` |
| HF auth for gated/private models | `internal/models/huggingface.go`, `cmd/cynapse/main.go` |
| Config expansion (models, local settings, hf_token) | `internal/config/config.go` |
| CLI `cynapse model <cmd>` | `cmd/cynapse/main.go` |
| DENDRITE multi-hop retrieval (1/2/3 hop) | `internal/memory/dendrite.go` |
| Auto-compression to DENDRITE (v2.3.0) | `internal/compressor/compressor.go` |
| Approval gate (destructive shell) (v2.3.0) | `internal/approval/approval.go` |
| SSRF guard (outbound HTTP) (v2.3.0) | `internal/netguard/netguard.go` |
| Secret redaction (v2.3.0) | `internal/redact/redact.go` |
| Operator confirmation protocol (v2.3.0) | `internal/confirm/confirm.go` |

### 🔄 In Progress / Not Started

| Feature | Status | Notes |
|---------|--------|-------|
| Cynapse ↔ Leafcutter runtime bridge | ✅ Done | Vendored llama.cpp b10434, static FFI, 2.5 tok/s |
| TUI-based Confirmer (Bubble Tea message channel) | ⚠ Stub | TUI still uses StdinPrompter; replace with message-passed prompt when chat is active |
| Gemini streaming | ❌ Stubbed | Returns "not implemented" |
| Remote synapse registry | ❌ Not built | Currently requires `--path` for synapse install |
| Model switching persistence | ❌ Not started | Remember last model across TUI restarts |
| Vision model auto-pairing | ❌ Not started | Auto-suggest `mmproj.gguf` for vision models |
| Approval gate prompt commands like `/allowed list` | ❌ Not started | UI affordance vs. open `~/.cynapse/allowlist` |

---

## Architecture Overview

```
cmd/cynapse/           → Entry point, CLI parsing, TUI bootstrap
internal/agent/        → Core agent loop, tool orchestration, streaming
internal/api/          → DENDRITE web UI server (D3.js visualization)
internal/attachments/  → Workspace file loading (images, PDFs, text)
internal/compressor/   → Auto context→DENDRITE archival (when threshold)
internal/config/       → YAML config with env overrides + security.* block
internal/llm/          → LLM client factory + 5 provider implementations
internal/mcp/          → Model Context Protocol server manager
internal/memory/       → DENDRITE graph, SQLite store, persona manager
internal/models/       → HuggingFace search, download, registry, Ollama import
internal/netguard/     → SSRF guard for outbound HTTP (loopback, RFC1918, AWS meta)
internal/redact/       → Regex + JSON-key + URL-param secret scanner
internal/session/      → JSONL session persistence with atomic compaction
internal/synapse/      → Plugin discovery, installation, manifest system
internal/tools/        → Built-in tools (bash, file, search) with profiles
                        + approval gate confirm integration
internal/confirmation/ → interactive prompt protocol with
                        AllowOnce / AllowSection / AllowAlways decisions
                        and persistent allowlist at ~/.cynapse/allowlist
internal/confirm/      → Confirm protocol package (operator prompts)
internal/tui/          → Bubble Tea model, key handling, rendering
```

(Note: `internal/confirmation` in the diagram above is a coarse
parent of `internal/confirm`, `internal/redact` and `internal/approval`
for visual clarity — they live at the package level, not under a
single parent.)

---

## LLM Providers

| Provider | Chat | Streaming | Tools | Multimodal | Notes |
|----------|------|-----------|-------|------------|-------|
| Anthropic | ✅ | ✅ SSE | ✅ | ❌ | `partial_json` fragment buffering |
| OpenAI | ✅ | ✅ SSE | ✅ | ❌ | Delta-based streaming |
| Gemini | ✅ | ❌ Stub | ✅ | ❌ | Streaming not yet implemented |
| Ollama | ✅ | ✅ NDJSON | ✅ | ✅ Images | `images[]` + text attachments |
| Local (llama-server) | ✅ | ✅ SSE | ✅ | ✅ Images | Subprocess with OpenAI-compatible API |

All providers implement `Close()` for cleanup (critical for killing llama-server on exit).

---

## Key Implementation Details

### DENDRITE Memory
- **Graph:** In-memory adjacency list, auto-backlinks on `Upsert()`
- **Persistence:** SQLite WAL mode, creates `-wal` and `-shm` files
- **Search:** FTS5 primary, `LIKE` fallback for systems without FTS5 extension
- **Context assembly:** 40% core / 60% context token budget, stop-word filtering

### Local Model Pipeline
1. `HFSearcher.Search()` — queries HF API with `filter=gguf`
2. `HFSearcher.ListFiles()` — handles both `/tree/main` (returns `path`) and `siblings` (returns `rfilename`) formats
3. `DownloadHF()` — HTTP download with progress callback, atomic `.tmp` → final rename
4. `Registry.Add()` — JSON record in `~/.cynapse/models/registry.json`
5. **Ollama path:** `OllamaImporter.Import()` generates Modelfile, runs `ollama create`
6. **Direct path:** `localClient` spawns `llama-server`, waits for `/health`, uses OpenAI API

### Attachment Flow
1. User: `/attach image.png`
2. `attachments.FindInWorkspace()` searches `./workspace/`, `uploads/`, `images/`, `documents/`
3. `attachments.Load()` detects MIME type by extension
4. Image → base64 → `llm.Attachment{Type: "image"}`
5. Text → string → `llm.Attachment{Type: "text"}`
6. PDF → `pdftotext` (if available) → `llm.Attachment{Type: "pdf"}`
7. Session `Entry` persists attachments
8. Ollama client forwards `Images[]` + appends text attachments to content

---

## Testing

```bash
# Build
go build ./...

# Tests (69 tests across 8 packages)
go test ./...
# ok  internal/api             0.003s
# ok  internal/approval        0.008s   11 tests
# ok  internal/compressor      0.010s   10 tests
# ok  internal/confirm         0.007s    9 tests
# ok  internal/memory          0.018s   13 tests (incl. FTS5 fallback)
# ok  internal/netguard        0.034s   10 tests
# ok  internal/redact          0.008s   11 tests
# ok  internal/tools           7.957s    5 integration tests
```

**Manual smoke tests performed:**
- Bash gate: `dd if=/dev/zero of=/dev/sda` → BLOCKED with rule explanation
- Bash gate: `curl https://example.com/x | bash` → resolver prompt lands with D/O/S/A options
- Sudo path: `sudo systemctl restart nginx` → triggers inline password prompt (no echo); password piped via `sudo -S -p ''`
- Redact: paste `sk-proj-AAA...XXX` into a tool result → masked in session JSONL
- SSRF: `web_fetch("http://169.254.169.254/")` → BLOCKED under standard policy
- Auto-compress: 30-turn stress test → middle 14 turns moved to DENDRITE, transcript reduced from 8000+ tokens to ~3000
- `go build ./...` → zero errors across all 16 packages

---

## Environment

```bash
# Build
cd /home/xander/Documents/portfolio/cynapse
go build -o cynapse ./cmd/cynapse

# Run
cynapse

# Search & download models
cynapse model search qwen2.5
cynapse model download Qwen/Qwen2.5-0.5B-Instruct-GGUF qwen2.5-0.5b-instruct-q4_0.gguf

# Import or run directly
cynapse model import hf:Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q4_0.gguf
# OR in TUI: Ctrl+K → Local Models → select (starts llama-server directly)
```

### Dependencies
- **Go 1.22+**
- **CGO enabled** (for SQLite)
- **Ollama** — optional but recommended for local models
- **llama-server** — optional, for direct inference without Ollama
- **pdftotext** — optional, for PDF text extraction

---

## Key Decisions

1. **Go over Python** — Single binary deployment, no dependency hell, runs on minimal systems.
2. **Ollama-first, llama-server-direct as fallback** — Ollama is widely installed; direct llama-server removes the middleman for advanced users.
3. **HuggingFace as model hub** — Largest GGUF ecosystem. Other hubs (ModelScope) can be added later.
4. **Workspace attachment model** — Users drop files in `./workspace/` and reference by filename. No file picker needed in terminal UI.
5. **Synapse protocol: `--meta` JSON** — Any executable printing metadata is a valid plugin. Language-agnostic, zero SDK.
6. **FTS5 optional** — DENDRITE must work on Pi 5 and minimal Linux. `LIKE` fallback is slower but universally compatible.
7. **Streaming tool calls buffered** — OpenAI/Anthropic stream fragments. We accumulate and emit reconstructed JSON at stream end, keeping the agent loop simple.
8. **Compression BEFORE the LLM call** — context is reduced in-session, not after. The model never sees the over-the-limit transcript.
9. **Heuristic safety gates, not capability removal** — bash and web_fetch keep working; pre-execution rules catch mistakes. Operators can pin `[A] Always` to `~/.cynapse/allowlist`.
10. **Sensitive requests refuse persistence** — `sudo` and password prompts never get the `Always` option. Secrets live only in stdin transiently.
11. **DNS-aware netguard** — resolves the URL hostname and checks every A record against the gate, defeating the "DNS points to 127.0.0.1 even though we asked for example.com" trick.

---

## Related

- **Repository:** https://github.com/Alartist40/cynapse.git
- **LeafcutterLLM:** https://github.com/Alartist40/LeafcutterLLM.git
- **Presentation:** `PRESENTATION.md` in repo root

---

*This handoff preserves context across sessions. Cynapse is actively developed and welcomes contributions.*
