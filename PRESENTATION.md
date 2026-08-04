# Cynapse: The Motherboard AI Agent

> **One terminal. Every model. A brain that never forgets. Zero subscriptions.**

---

## The One-Sentence Pitch

**Cynapse is the only AI system that lets you search, download, and run AI models directly from your terminal — while remembering everything you ever told it, in a graph-structured brain called DENDRITE.**

---

## The Problem (Why This Exists)

You are juggling **5 different apps** right now:
- ChatGPT for general questions
- Claude for coding
- Ollama or LM Studio for local models
- Perplexity for research
- A notes app for what the AI told you last week

**None of them talk to each other.**

Every time you start a new chat, you start from zero. Your AI doesn't *remember* you — it remembers a shallow summary. Your documents live in one app, your images in another, your code in a third. And if you want privacy? You need a PhD in Python environments, CUDA drivers, and HuggingFace transformers.

**AI should be yours. Not rented by the token.**

---

## What Cynapse Does Differently

### 1. 🧠 It Remembers Everything (For Real)

Most AI apps store "memory" as a text file of summaries. Cynapse stores memory in **DENDRITE** — a knowledge graph where every fact is a node and every relationship is an edge.

```
[You] ──likes──► [Go programming]
   │                  │
   └──works on──► [Cynapse project] ──uses──► [Bubble Tea TUI]
```

Ask "What UI library did I use for my AI project?" and DENDRITE performs **multi-hop traversal** (2-hop, 3-hop BFS) to find the answer — even if you haven't mentioned it in months. This isn't chat history. This is a **second brain**.

### 2. 💻 Your Personal AI App Store

Inspired by **PocketPal AI** (the mobile app that lets you download models to your phone), Cynapse brings that same power to your terminal:

```bash
# Search for models
cynapse model search llama3.2

# Download one (with live progress bar)
cynapse model download Qwen/Qwen2.5-0.5B-Instruct-GGUF qwen2.5-0.5b-instruct-q4_0.gguf

# Run it immediately
cynapse
> hello!
CYNAPSE: Hello! How can I help you today?
```

**No Python. No pip. No conda. No Jupyter.** Just a single Go binary that downloads models like you'd download a song.

### 3. 📎 It Can See Your Files

Drop an image, PDF, or text file into `./workspace/` and talk to it:

```bash
> /attach architecture.png
📎 Attached: architecture.png

> explain this diagram
CYNAPSE: This shows a microservices architecture with...
```

Images become base64. PDFs become extracted text. Code files become context. **Your documents are no longer trapped in separate apps.**

### 4. 🔒 Privacy Is The Default

When you run a local model, **nothing leaves your machine**. No API keys. No data mining. No "training on your conversations." Your DENDRITE memory lives in a SQLite file on your disk. Your models live in `~/.cynapse/models/`. **You own everything.**

### 5. 🛡 Heuristic Safety Stack — Without Needing a PhD

Every dangerous operation routes through small, stdlib-only Go inspection layers **before** anything touches your machine:

- **Approval gate** — refuses `rm -rf`, `mkfs`, `dd of=/dev/*`, fork bombs, `curl|bash`.  The LLM can't bypass it with creative encodings *for cooperative mode mistakes*.
- **SSRF guard** — `web_fetch` won't reach `127.0.0.1`, `192.168.x.x`, or AWS metadata at `169.254.169.254` under default policy.  Loosen to local-dev profile so Ollama on localhost still works.
- **Secret redaction** — OpenAI / Anthropic / HF / AWS / GitHub tokens, PEM keys, JWTs and URL `?api_key=` leaks get masked before they touch your session JSONL.
- **Confirmation protocol** — every Warn+ command shows `D / O / S / A`.  `Sudo` adds an inline password prompt (no echo).  `Always` writes to `~/.cynapse/allowlist` so the operator decides what survives restarts.

Yet the agent still ships with `bash`, `web_fetch` and full system access unchanged — **the gates are pre-execution, not removal**.  See [`SECURITY.md`](SECURITY.md) for the trust model.

---

## What Makes Cynapse Stand Out

| Feature | ChatGPT | Claude | Ollama | LM Studio | **Cynapse** |
|---------|:-------:|:------:|:------:|:---------:|:-----------:|
| Multiple LLM providers | ❌ | ❌ | ⚠️ | ⚠️ | ✅ **5 backends** |
| Persistent knowledge graph | ❌ | ❌ | ❌ | ❌ | ✅ **DENDRITE** |
| Terminal-native UI | ❌ | ❌ | ❌ | ❌ | ✅ **Bubble Tea** |
| Search & download models | ❌ | ❌ | ❌ | ⚠️ | ✅ **HF integration** |
| Image/PDF attachments | 💰 | 💰 | ⚠️ | ⚠️ | ✅ **Built-in** |
| Plugin system | ⚠️ | ⚠️ | ❌ | ❌ | ✅ **Synapses** |
| Offline capable | ❌ | ❌ | ✅ | ✅ | ✅ **Local models** |
| Single binary, no deps | N/A | N/A | ❌ | ❌ | ✅ **Go binary** |
| Open source & self-hosted | ❌ | ❌ | ✅ | ⚠️ | ✅ **MIT License** |

💰 = Paid tier only

**The difference:** Cynapse isn't *one more* AI chat app. It's the **motherboard** that connects models, memory, tools, and files into a single, persistent, private system.

---

## For Programmers: The Technical Story

### Why Go?

Because **Python is a deployment nightmare** for end-user tools. Cynapse compiles to a **~15MB single binary** with zero Python dependencies. It runs on a Raspberry Pi 5, a gaming rig, or a headless server over SSH. No virtualenv. No pip. No "it works on my machine."

### Architecture At A Glance

```
┌─────────────────────────────────────────────────────────────┐
│                    TUI (Bubble Tea)                         │
│         Terminal UI with menus, streaming, attachments      │
├─────────────────────────────────────────────────────────────┤
│                      Agent Layer                            │
│    ProcessMessage → Tool Loop → Stream → Self-Improvement   │
├─────────────────────────────────────────────────────────────┤
│  LLM Clients  │  Synapses  │  DENDRITE  │  MCP  │  Tools   │  Safety Stack  │
│  Anthropic    │  Registry  │  Graph     │  Mgr  │  Profile │   approve ⛔  │
│  OpenAI       │  Manifest  │  SQLite    │       │  Bash    │   netguard 🌐 │
│  Gemini       │  --meta    │  FTS5/LIKE │       │  File    │   redact 🚨  │
│  Ollama       │            │  Auto-     │       │  Search  │   confirm ❓ │
│  Local GGUF   │            │  Compress  │       │          │               │
│  (HF Search,  │            │            │       │          │               │
│   Download,   │            │            │       │          │               │
│   Import)     │            │            │       │          │               │
├─────────────────────────────────────────────────────────────┤
│  Config (YAML)  │  Sessions (JSONL)  │  Models (JSON)       │
│  Env overrides  │  Auto-compaction   │  Registry + GGUFs    │
└─────────────────────────────────────────────────────────────┘
```

### The Synapse Protocol: Dead Simple

Want to add a plugin? Any executable that prints this when called with `--meta` becomes a tool:

```json
{
  "name": "git-tools",
  "version": "1.0.0",
  "tools": [
    {
      "name": "git_log",
      "description": "Show recent git commits",
      "parameters": {
        "type": "object",
        "properties": {
          "n": { "type": "integer", "description": "Number of commits" }
        }
      }
    }
  ]
}
```

That's it. Write it in **Rust, Python, Bash, or C**. Cynapse discovers it, converts it to an MCP tool, and the LLM can call it. No SDK. No boilerplate.

### LLM Provider Matrix

| Provider | Chat | Streaming | Tools | Multimodal | Implementation Notes |
|----------|------|-----------|-------|------------|---------------------|
| **Anthropic** | ✅ | ✅ SSE | ✅ | ❌ | `partial_json` fragment buffering |
| **OpenAI** | ✅ | ✅ SSE | ✅ | ❌ | Delta-based streaming |
| **Gemini** | ✅ | ❌ Stub | ✅ | ❌ | Streaming pending |
| **Ollama** | ✅ | ✅ NDJSON | ✅ | ✅ Images | `images[]` array + attachments |
| **Local Direct** | ✅ | ✅ SSE | ✅ | ✅ Images | llama-server subprocess, OpenAI API |

### DENDRITE: Memory That Thinks in Connections

Not a key-value store. Not a text log. A **graph**.

| Component | Data Structure | Persistence | Key Feature |
|-----------|---------------|-------------|-------------|
| **Graph** | Adjacency list | SQLite WAL | Multi-hop BFS (2-hop, 3-hop) |
| **Store** | SQLite + FTS5/LIKE fallback | WAL mode | Works on minimal systems (Pi 5, embedded) |
| **Context** | Token-budgeted assembly | In-memory | 40% core / 60% context split |
| **Persona** | Markdown + graph nodes | File + DB | Daily logs, fact deduplication |

The FTS5 fallback is critical: DENDRITE works even on systems without the SQLite FTS5 extension. We fall back to `LIKE`-based search automatically.

### Model Management Pipeline

```
User Query
    ↓
HuggingFace API Search (filter=gguf, sort=downloads)
    ↓
File Listing (/tree/main + siblings format normalization)
    ↓
Download (HTTP progress callback, atomic .tmp→final, optional auth)
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

### Testing

```bash
$ go test ./...

ok  	github.com/Alartist40/cynapse/internal/api            	0.003s
ok  	github.com/Alartist40/cynapse/internal/approval       	0.008s   11 tests
ok  	github.com/Alartist40/cynapse/internal/compressor     	0.010s   10 tests
ok  	github.com/Alartist40/cynapse/internal/confirm        	0.007s    9 tests
ok  	github.com/Alartist40/cynapse/internal/memory         	0.018s   13 tests
ok  	github.com/Alartist40/cynapse/internal/netguard       	0.034s   10 tests
ok  	github.com/Alartist40/cynapse/internal/redact         	0.008s   11 tests
ok  	github.com/Alartist40/cynapse/internal/tools          	7.957s    5 tests
```

**69 integration tests** covering the full compression lifecycle, persistent allowlist semantics (with vs. without secrets), approval-gate policy resolution, netguard DNS-aware SSRF blocking, redact layer for every provider key format — all passing.

---

## Quick Start

### One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/Alartist40/cynapse/main/install.sh | bash
```

This installs Go (if missing), system dependencies, optionally Ollama, builds Cynapse, and adds it to your PATH.

### Download Your First Model

```bash
cynapse model search qwen2.5
cynapse model download Qwen/Qwen2.5-0.5B-Instruct-GGUF qwen2.5-0.5b-instruct-q4_0.gguf
cynapse model import hf:Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q4_0.gguf
```

### Start Chatting

```bash
cynapse
> /attach my-document.pdf
> summarize the key points
> /attach screenshot.png
> what's wrong with this error?
```

---

## The Philosophy

> **"The synapse is not the neuron. The synapse is the connection. Cynapse is the connection."**

AI shouldn't be a collection of disconnected apps that you rent. It should be **yours**: a single system that learns, remembers, and grows with you — running on hardware you already own, in a terminal you already use.

**Cynapse doesn't rent you intelligence. It gives you the tools to build your own.**

---

*Built with Go, Bubble Tea, and the belief that AI should belong to its users.*
*MIT License — https://github.com/Alartist40/cynapse*
