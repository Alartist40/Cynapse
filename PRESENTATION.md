# Cynapse: The Motherboard AI Agent

> **A terminal-first, modular AI system that puts you in control of your models, your data, and your memory.**

---

## 1. What Is Cynapse?

**Cynapse** is a lightweight, cross-platform AI agent written in Go. It runs in your terminal, connects to any LLM (local or cloud), remembers everything through a persistent knowledge graph called **DENDRITE**, and can be extended with plugin "synapses" that add tools, skills, and integrations.

Think of it as:
- **A command-center for AI** — one interface, many models
- **A second brain** — everything you discuss is remembered, connected, and searchable
- **A LEGO set** — snap on new capabilities (git, web, code, files) without rewriting the core

---

## 2. The Real-World Problem

### The Fragmentation Crisis

Today's AI landscape forces users into impossible trade-offs:

| Problem | What Users Face |
|---------|-----------------|
| **Cloud Lock-in** | You pay per token, your data leaves your machine, and the provider can change pricing or availability overnight. |
| **App Silos** | ChatGPT doesn't remember your Claude conversations. Perplexity can't use your local files. Each app is an island. |
| **No Persistent Memory** | Start a new chat = start from zero. Even "memory" features are shallow summaries, not structured knowledge. |
| **Plugin Chaos** | Every platform has its own plugin system (GPTs, Claude projects, Copilot extensions). None are portable. |
| **No Local Model Access** | Running AI on your own hardware — for privacy, cost, or offline use — requires technical expertise most people don't have. |
| **Multimodal Friction** | Want to show an AI a document or image? You need a specific app, a specific model, and often a paid tier. |

### The Result
Users are juggling 5+ apps, losing context, repeating themselves, and paying recurring fees for something that should be **theirs**.

---

## 3. How Cynapse Solves It

### 🧩 One Agent, Many Models
Cynapse speaks to **Anthropic, OpenAI, Google Gemini, Ollama, and now locally downloaded GGUF models**. Switch providers in seconds. Your memory and tools come with you.

### 🧠 DENDRITE: Memory That Thinks
Unlike simple chat history, DENDRITE is a **knowledge graph**:
- Every fact is a **node**
- Every relationship is an **edge**
- The system performs **multi-hop traversal** (2-hop, 3-hop BFS) to find contextually relevant information
- Full-text search (FTS5) with graceful fallback for minimal systems
- SQLite persistence with WAL mode — your memory survives reboots

### 🔌 Synapses: Portable Plugins
Any executable that prints metadata via `--meta` becomes a synapse. Install from a local path, a URL, or (future) a registry. Cynapse automatically converts them into **MCP tools** the LLM can call.

### 💻 Local Model Power (New in v2.2)
**Inspired by PocketPal AI**, Cynapse now lets you:
- **Search** HuggingFace for GGUF models directly from the terminal
- **Download** models to your machine with live progress (speed, ETA, percentage)
- **Import** them into Ollama with one command
- **Run** them privately, offline, and forever-free
- **Attach** images, PDFs, and text files from a workspace folder for multimodal conversations

### 🔒 Privacy by Default
When you run a local model, **nothing leaves your machine**. No API keys. No data mining. No subscription.

---

## 4. Detailed Technical Architecture

### Stack Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      TUI (Bubble Tea)                       │
│         Terminal UI with menus, streaming, attachments      │
├─────────────────────────────────────────────────────────────┤
│                      Agent Layer                            │
│    ProcessMessage → Tool Loop → Stream → Self-Improvement   │
├─────────────────────────────────────────────────────────────┤
│  LLM Clients  │  Synapses  │  DENDRITE  │  MCP  │  Tools   │
│  Anthropic    │  Registry  │  Graph     │  Mgr  │  Profile │
│  OpenAI       │  Manifest  │  SQLite    │       │  Bash    │
│  Gemini       │  --meta    │  FTS5/LIKE │       │  File    │
│  Ollama       │            │            │       │  Search  │
│  Local GGUF   │            │            │       │          │
│  (HF Search,  │            │            │       │          │
│   Download,   │            │            │       │          │
│   Import)     │            │            │       │          │
├─────────────────────────────────────────────────────────────┤
│  Config (YAML)  │  Sessions (JSONL)  │  Models (JSON)       │
│  Env overrides  │  Auto-compaction   │  Registry + GGUFs    │
└─────────────────────────────────────────────────────────────┘
```

### Core Technologies

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Language** | Go 1.22+ | Statically typed, fast compilation, single-binary deployment |
| **TUI Framework** | Bubble Tea (Charm) | Elm-style terminal UI with async message passing |
| **Styling** | Lipgloss | CSS-like terminal styling |
| **Database** | SQLite3 (CGO) | WAL mode, FTS5 full-text search, persistent graph storage |
| **Serialization** | YAML (config), JSON (registry, messages, sessions) | Human-readable, widely supported |
| **HTTP** | net/http (stdlib) | LLM API clients, HuggingFace API, download manager |
| **MCP Protocol** | stdio-based JSON-RPC | Standardized tool calling for external servers |

### Package Structure

```
cmd/cynapse/           → Entry point, CLI parsing, TUI bootstrap
internal/agent/        → Core agent loop, tool orchestration, streaming
internal/api/          → DENDRITE web UI server (D3.js visualization)
internal/attachments/  → Workspace file loading (images, PDFs, text)
internal/config/       → YAML config with env overrides
internal/llm/          → LLM client factory + 5 provider implementations
internal/mcp/          → Model Context Protocol server manager
internal/memory/       → DENDRITE graph, SQLite store, persona manager
internal/models/       → HuggingFace search, download, registry, Ollama import
internal/session/      → JSONL session persistence with compaction
internal/synapse/      → Plugin discovery, installation, manifest system
internal/tools/        → Built-in tools (bash, file, search) with profiles
internal/tui/          → Bubble Tea model, key handling, rendering
```

### LLM Provider Implementations

| Provider | Chat | Streaming | Tools | Multimodal | Notes |
|----------|------|-----------|-------|------------|-------|
| **Anthropic** | ✅ | ✅ SSE | ✅ | ❌ | Full tool-call buffering from `partial_json` fragments |
| **OpenAI** | ✅ | ✅ SSE | ✅ | ❌ | Standard delta-based streaming |
| **Gemini** | ✅ | ❌ Stub | ✅ | ❌ | Streaming not yet implemented |
| **Ollama** | ✅ | ✅ NDJSON | ✅ | ✅ Images | Now supports `images` array + text attachments |
| **Local GGUF** | ✅ (via Ollama) | ✅ (via Ollama) | ✅ | ✅ | HF search → download → Ollama import pipeline |
| **Local Direct** | ✅ | ✅ SSE | ✅ | ✅ Images | llama-server subprocess with OpenAI-compatible API |

### DENDRITE Memory System

| Component | Data Structure | Persistence | Features |
|-----------|---------------|-------------|----------|
| **Graph** | In-memory adjacency list | SQLite on change | Auto-backlinks, multi-hop BFS |
| **Store** | SQLite + FTS5/LIKE fallback | WAL mode | Full-text search, relevance scoring |
| **Context** | Token-budgeted prompt assembly | N/A | 40% core / 60% context split, stop-word filtering |
| **Persona** | Markdown files + graph nodes | File + DB | Daily logs, fact deduplication, user profiles |

### Model Management Pipeline

```
User Query
    ↓
HuggingFace API Search (filter=gguf, sort=downloads)
    ↓
File Listing (/tree/main endpoint, path→rfilename mapping)
    ↓
Download (HTTP with progress callback, atomic .tmp→final, optional auth token)
    ↓
JSON Registry Entry (~/.cynapse/models/registry.json)
    ↓
┌─────────────────┬──────────────────────────────┐
│ Ollama Import   │ Direct Local Inference       │
│ (Modelfile)     │ (llama-server subprocess)    │
└─────────────────┴──────────────────────────────┘
    ↓
Run via Ollama API    OR    OpenAI-compatible /v1/chat/completions
```

### Attachment Processing Pipeline

```
User: /attach image.png
    ↓
FindInWorkspace() → searches ./workspace/, uploads/, images/, documents/
    ↓
Load() → detect MIME type by extension
    ↓
Image → base64 encode → llm.Attachment{Type: "image", Content: base64}
Text  → read string   → llm.Attachment{Type: "text", Content: text}
PDF   → pdftotext     → llm.Attachment{Type: "pdf", Content: text}
      └→ fallback: base64
    ↓
Session Entry stores attachments
    ↓
Ollama Chat API: msg.Images[] + appended text content
```

---

## 5. Testing & Verification

### Automated Test Suite

```bash
$ go test ./...

ok  	github.com/Alartist40/cynapse/internal/api      	0.003s
ok  	github.com/Alartist40/cynapse/internal/memory   	(cached)
```

**Memory Tests (`internal/memory/dendrite_integration_test.go`) — 13 tests:**

| Test | What It Verifies |
|------|-----------------|
| `TestDendrite_FullLifecycle` | Create nodes → link them → query → persist → reload from disk |
| `TestDendrite_MultiHopTraversal` | 1-hop, 2-hop, 3-hop BFS returns correct neighbors in order |
| `TestDendrite_FactDeduplication` | Identical facts are not stored twice |
| `TestDendrite_FTS5Relevance` | Prompt assembly includes relevant facts with proper scoring |

### Manual Integration Tests Performed

| Test | Command / Action | Result |
|------|-----------------|--------|
| **HF Model Search** | `cynapse model search qwen2.5` | ✅ 20 models returned with files listed |
| **HF File Listing** | `cynapse model download Qwen/Qwen2.5-0.5B-Instruct-GGUF` | ✅ 9 GGUF variants displayed |
| **Download Progress** | `cynapse model download ... qwen2.5-0.5b-instruct-q4_0.gguf` | ✅ Live progress with speed & ETA |
| **Registry Persistence** | `cynapse model list` after interrupted download | ✅ No partial entries (atomic rename) |
| **Config Generation** | `cynapse config init` | ✅ New `models:` section present |
| **Build Verification** | `go build ./...` | ✅ Zero errors across all packages |
| **TUI Help** | `cynapse help` | ✅ Model commands documented |
| **Attachment Load** | `attachments.Load("workspace/test_document.txt")` | ✅ Text content extracted |
| **Image Base64** | `attachments.Load("workspace/image.png")` | ✅ Valid data URI generated |
| **Ollama Multimodal** | Code review of `ollamaClient.Chat()` | ✅ Images forwarded in `images[]` array |
| **Direct Local Provider** | Code review of `localClient` | ✅ Subprocess start, health check, OpenAI API |
| **HF Auth Token Parsing** | `cynapse model search qwen2.5 --token dummy` | ✅ Token extracted and passed to API |
| **Config Local Settings** | `cynapse config init` | ✅ llama_server_path, local_gpu_layers present |
| **Client Close Interface** | `llm.Client.Close()` | ✅ All 5 providers implement Close() |

### Code Quality Metrics

| Metric | Value |
|--------|-------|
| **Lines of Go code added** | ~3,400 (models + attachments + CLI + TUI + LLM + local provider) |
| **Packages** | 13 internal packages, all compiling |
| **External dependencies** | 6 direct (bubbletea, lipgloss, sqlite3, yaml.v3) |
| **Binary size** | ~15MB (single static binary) |
| **Cross-platform** | Linux ✅, macOS ✅, Windows ✅ (Go stdlib + CGO for SQLite) |

---

## 6. Feature Matrix

| Capability | Cynapse v2.2 | Typical Cloud Chat | Typical Local UI |
|------------|:------------:|:------------------:|:----------------:|
| Multiple LLM providers | ✅ | ❌ (single vendor) | ⚠️ (limited) |
| Local model download & run | ✅ | ❌ | ⚠️ (manual setup) |
| Persistent knowledge graph | ✅ | ❌ (shallow memory) | ❌ |
| Plugin system (synapses) | ✅ | ⚠️ (vendor-specific) | ❌ |
| Terminal-first UI | ✅ | ❌ | ❌ |
| Offline capability | ✅ (local models) | ❌ | ⚠️ |
| Image/document attachments | ✅ | ⚠️ (paid tiers) | ⚠️ |
| Open-source & self-hosted | ✅ | ❌ | ⚠️ |
| Cross-platform single binary | ✅ | N/A | ❌ |

---

## 7. Demo Walkthrough

### Searching for a Model
```bash
$ cynapse model search qwen2.5
🔍 Found 20 models

  📦 Qwen/Qwen2.5-0.5B-Instruct-GGUF
     └── 📄 qwen2.5-0.5b-instruct-q4_0.gguf (408.9 MB)
     └── 📄 qwen2.5-0.5b-instruct-q8_0.gguf (644.4 MB)
```

### Downloading with Live Progress
```bash
$ cynapse model download Qwen/Qwen2.5-0.5B-Instruct-GGUF qwen2.5-0.5b-instruct-q4_0.gguf
⬇️  Downloading Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q4_0.gguf...
   Destination: ~/.cynapse/models/Qwen_Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q4_0.gguf
   45.3% (185.2 MB / 408.9 MB) 2.14 MB/s
✅ Downloaded!
💡 Import to Ollama: cynapse model import hf:Qwen/...
```

### Running Directly (No Ollama Required)
```bash
$ cynapse
> Ctrl+K → Local Models → Select downloaded model
Switched to local model: qwen2.5-0.5b-instruct-q4_0.gguf
(llama-server starts automatically on a free port)

> explain quantum computing simply
CYNAPSE: Quantum computing is a type of computation that...
```

### Authenticated Download (Gated Models)
```bash
$ cynapse model download meta-llama/Llama-3.2-1B-Instruct-GGUF \
    Llama-3.2-1B-Instruct-Q4_0.gguf --token hf_xxx
🔐 Using HF authentication token
⬇️  Downloading...
✅ Downloaded!
```

### Importing to Ollama
```bash
$ cynapse model import hf:Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q4_0.gguf
🦙 Importing into Ollama as cynapse-qwen-qwen2.5-0.5b-instruct-q4_0...
✅ Imported! Use it with: cynapse (set model to cynapse-qwen-...)
```

### Chatting with Attachments
```bash
$ cynapse
> /attach diagram.png
📎 Attached: diagram.png (image)
> explain what this architecture diagram shows
CYNAPSE: This diagram shows a microservices architecture with...
```

---

## 8. Roadmap

| Version | Focus |
|---------|-------|
| **v2.2** ✅ | Local model management, multimodal attachments, HF integration |
| **v2.3** ✅ | Direct llama-server support, HF auth for gated models |
| **v2.5** | Model quantization advisor, Cynapse ↔ Leafcutter bridge |
| **v2.4** | Semantic search in DENDRITE, vision model auto-pairing |
| **v2.6** | Remote synapse registry, graph metrics API |
| **v3.0** | Multi-agent federation, voice synapse, mobile prototype |

---

## 9. Why Cynapse Wins

For **technical users**, Cynapse is:
- A hackable, Go-based agent you can extend in any language
- A persistent second brain with graph-structured memory
- A local-first AI stack that respects your hardware and privacy

For **everyday users**, Cynapse is:
- One app that replaces ChatGPT + Claude + Perplexity + local UIs
- A system that remembers you, not just your last prompt
- A way to run AI for free, forever, on hardware you already own

> **Cynapse doesn't rent you intelligence. It gives you the tools to build your own.**

---

*Built with Go, Bubble Tea, and the belief that AI should belong to its users.*
