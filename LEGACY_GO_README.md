# 🧠 CYNAPSE — The AI Agent Motherboard

**Your terminal. Your models. Your plugins. One brain.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Go 1.22+](https://img.shields.io/badge/Go-1.22+-00ADD8?logo=go)](https://golang.org)
[![Tests](https://img.shields.io/badge/tests-69%2F69%20pass-brightgreen)](internal/compressor/compressor_test.go)
[![Security](https://img.shields.io/badge/security-heuristic_stack-blueviolet)](SECURITY.md)

> *"Like a motherboard connects components, Cynapse connects AI tools into a single, persistent intelligence."*

Cynapse is a **modular, terminal-first AI agent** built in Go. It doesn't try to be everything — it connects everything. Install the core once, then snap on **synapses** (plugins) like LEGO pieces: local LLM inference, git tools, web automation, benchmarking, or build your own.

**Why Cynapse?**
- 🧩 **LEGO-piece architecture** — install only what you need
- 🧠 **Persistent memory** — DENDRITE graph memory survives API changes, model switches, even reinstalls
- ⚡ **Streaming everywhere** — watch text appear word-by-word (Ollama, OpenAI, Anthropic, local)
- 💻 **Run models locally** — search, download, and run GGUF models from HuggingFace (like PocketPal AI)
- 📎 **Multimodal attachments** — drop images, PDFs, and text files into `./workspace/` and chat about them
- 🖥️ **Terminal-native** — runs on a Raspberry Pi 5, a gaming rig, or over SSH
- 🔌 **MCP-native** — every synapse speaks the Model Context Protocol
- 🗜 **Self-compressing context** — at 50% of model context, older turns move silently to DENDRITE memory; `/compress` to force
- 🛡 **Heuristic safety stack** — secret redaction, destructive-command approval, SSRF guard, operator-resolved allowlist

---

## ⚡ One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/Alartist40/cynapse/main/install.sh | bash
```

That's it. The installer handles Go, dependencies, build, and PATH setup automatically.

**What happens:**
1. Detects your OS/arch (Linux, macOS, Windows / x86_64, ARM64, ARMv7)
2. Installs Go if missing
3. Installs system dependencies (`build-essential`, `sqlite3`, etc.)
4. Offers to install Ollama for local model inference
5. Clones and builds Cynapse
6. Creates `~/.cynapse/` home directory + `./workspace/` for attachments
7. Generates a default `config.yaml`
8. Adds `cynapse` to your PATH

**Then just run:**
```bash
cynapse
```

---

## 🚀 Usage

### Interactive Chat (Default)

```bash
cynapse
```

A beautiful purple & orange TUI appears. Type naturally. Press **Ctrl+K** for the command menu.

### Local Model Management (PocketPal-Style)

Search, download, and run AI models directly on your machine. No cloud required.

```bash
# Search HuggingFace for GGUF models
cynapse model search qwen2.5

# Download a specific model file
cynapse model download Qwen/Qwen2.5-0.5B-Instruct-GGUF qwen2.5-0.5b-instruct-q4_0.gguf

# Download a gated/private model (requires HF token)
cynapse model download meta-llama/Llama-3.2-1B-Instruct-GGUF \
  Llama-3.2-1B-Instruct-Q4_0.gguf --token hf_xxx

# Or set token via environment:
export HF_TOKEN=hf_xxx

# List downloaded models
cynapse model list

# Import into Ollama (recommended)
cynapse model import hf:Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q4_0.gguf

# Run directly without Ollama (uses llama-server)
# In TUI: Ctrl+K → Local Models → select model
```

### Multimodal Attachments

Drop files in `./workspace/` then attach them in chat:

```bash
# In the TUI:
> /attach image.png
📎 Attached: image.png (image)

> /attach report.pdf
📎 Attached: report.pdf (pdf)

> what does this diagram show?
CYNAPSE: This diagram illustrates...

# List pending attachments
> /attachments

# Clear all attachments
> /clear-attach
```

**Supported file types:**
- **Images:** PNG, JPG, GIF, BMP, WebP → base64 for vision models
- **Text:** TXT, MD, CSV, JSON, code files → read as text
- **PDFs:** Extracted via `pdftotext` (if available) or base64 fallback

### Manage Synapses (Plugins)

```bash
# List installed synapses
cynapse synapse list

# Install from a local binary
cynapse synapse add leafcutter --path ./leafcutter

# Install from a URL (with optional SHA-256 verification)
cynapse synapse add speedtest --url https://example.com/speedtest --hash abc123...

# Remove a synapse
cynapse synapse remove git-tools

# Search available synapses
cynapse synapse search inference
```

### Configuration

```bash
# Create default config
cynapse config init

# Edit config
nano ~/.cynapse/config.yaml
```

**Example `~/.cynapse/config.yaml`:**
```yaml
llm:
  provider: "ollama"              # ollama | anthropic | openai | gemini | local
  model: "qwen2.5"
  ollama_base_url: "http://localhost:11434"
  llama_server_path: ""           # path to llama-server binary
  local_gpu_layers: 0             # GPU offloading for local models
  local_context_size: 4096        # Context window for local models
  max_tokens: 4096
  temperature: 0.7

memory:
  persona_path: "~/.cynapse/data/persona"
  sessions_path: "~/.cynapse/data/sessions"
  dendrite_db_path: "~/.cynapse/data/dendrite.db"

mcp:
  enabled: true
  servers: []

tools:
  profile: "standard"             # minimal | standard | full
  work_dir: "./workspace"

models:
  models_dir: "~/.cynapse/models"
  use_ollama: true
  use_llama_server: false
  hf_token: ""                    # HuggingFace token for gated models

security:
  mode: "standard"                # trust-local | standard | strict
  redact_secrets: true            # strip API keys before they hit the JSONL
  net_policy: "local-dev"         # secure | local-dev
  approval_policy: "balanced"     # trust-local | balanced | strict
```

Memory file `~/.cynapse/allowlist` is auto-created.  Each line is a
rule like `bash:rm -rf node_modules` that lets the operator skip the
confirmation prompt.  Sensitive kinds (`sudo`, `password`) refuse the
`Always` option, so secrets never persist.

---

## 🛡 Heuristic Safety Stack

Every dangerous operation in Cynapse routes through a stack of in-process
heuristics.  **None of them are security boundaries** — see
[`SECURITY.md`](SECURITY.md) for the trust model.  They catch
cooperative-mode mistakes before exfiltration happens.

| Layer | Triggers on | Default behaviour |
|-------|-------------|-------------------|
| `internal/approval` | `rm -rf`, `mkfs`, `dd of=/dev/*`, fork bombs, `curl|bash`, `/dev/tcp`, force-push | Warn+ prompts, Danger+ denies |
| `internal/netguard` | outbound HTTP to loopback, RFC1918, link-local, `169.254.169.254` | refuses by default; LocalDevPolicy allows Ollama |
| `internal/redact`   | OpenAI / Anthropic / HF / GH / AWS / Slack / Stripe / Twilio tokens, PEM, JWTs, URL secrets | masks before persistence |
| `internal/confirm`  | every Warn+ command from the LLM | interactive prompt with `AllowOnce / Section / Always` |

When the bash tool sees a command that needs confirmation, you get:

```
⚠  Run shell command?
   sudo systemctl restart nginx

   [D) Decline / O) Allow once / S) Allow for this section / A) Always allow]:
```

Sudo prompts additionally ask for the password inline (no echo to
the terminal).  The agent never sees persisted secrets — passwords
are kept in-flight only and discarded when the command finishes.

To see and edit what's been allowed permanently:

```bash
cat ~/.cynapse/allowlist
# bash:rm -rf node_modules
# bash:go test ./...
# ssh:github.com:git pull
```

Remove a line to tighten policy again; the operator is the source of truth.

---

## 📦 Synapses — LEGO Pieces for Your Agent

Synapses are discovered as executables in `~/.cynapse/synapses/` that respond to `--meta` with JSON metadata. Install them from local binaries, remote URLs, or build your own.

| Synapse | What It Does | Install |
|---------|-------------|---------|
| **leafcutter** | CPU-optimized local LLM inference (70B on 4GB via quantization) | `cynapse synapse add leafcutter --path <binary>` |
| **git-tools** | Repository management, commit analysis, history search | `cynapse synapse add git-tools --path <binary>` |
| **web-automation** | Browser control, screenshots, web scraping | `cynapse synapse add web-automation --path <binary>` |
| **speedtest** | LLM benchmarking and performance metrics | `cynapse synapse add speedtest --path <binary>` |

> **Building your own?** Any executable that prints JSON when called with `--meta` is a synapse. That's the entire protocol.

---

## 🧠 DENDRITE — Graph Memory That Thinks in Connections

Cynapse doesn't store memory in flat files. It stores it in **DENDRITE**, a neural-inspired knowledge graph where every concept is a node and every relationship is a wire.

```
[User Profile] ←────→ [Project: Leafcutter]
      ↓                     ↓
[Preferences] ←────→ [Quantization]
      ↓
[Fact: prefers dark mode]
```

### How It Works
- **Write `[[wiki-links]]`** in any node content — backlinks auto-wire themselves
- **Missing nodes become placeholders** — create them later, connections are never lost
- **Relevance scoring** — title match (+15), content frequency (+2), recency (+5), connectivity (+0.3 per link)
- **Multi-hop traversal** — 1-hop, 2-hop, or 3-hop BFS for rich context retrieval
- **Token budgeting** — 40% of the prompt budget for core identity, 60% for conversation-relevant context
- **Self-improving** — heartbeat curator asks the LLM to consolidate daily logs into long-term memory

### Persistence
- **SQLite + WAL mode** — fast, reliable, single-file
- **FTS5 full-text search** — with graceful fallback to `LIKE` queries on minimal systems
- **Fact deduplication** — identical facts merge instead of creating duplicate nodes
- **Cross-platform** — works on systems without the FTS5 extension (Pi Zero, embedded Linux)

### Visual Explorer
Press **DENDRITE** in the TUI menu (Ctrl+K → DENDRITE) to launch an interactive D3.js graph visualization. Works 100% offline.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CYNAPSE CORE                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────────────────┐    │
│  │   TUI   │  │  Agent  │  │  DENDRITE Memory    │    │
│  │(Bubble  │  │ (Tool   │  │  - Graph nodes      │    │
│  │  Tea)   │  │  Loop)  │  │  - SQLite store     │    │
│  └────┬────┘  └────┬────┘  │  - Context builder  │    │
│       │            │       └─────────────────────┘    │
│       └────────────┘                                   │
│                        ┌──────────────┐                │
│                        │ MCP Manager  │                │
│                        │ (Tool Router)│                │
│                        └──────┬───────┘                │
└───────────────────────────────┼────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
   ┌────┴────┐           ┌─────┴─────┐          ┌─────┴─────┐
   │Synapses │           │  Local    │          │  Remote   │
   │(Plugins)│           │  Tools    │          │  APIs     │
   └────┬────┘           │(file I/O, │          │(Ollama,   │
        │                │ shell,    │          │ OpenAI,   │
   ┌────┴────┐           │ search)   │          │ Anthropic)│
   │leafcutter│           └───────────┘          └───────────┘
   │git-tools │
   │web-auto  │
   └─────────┘
```

---

## ✨ What's New

### v2.3.0 (Latest)
- ✅ **Auto-compressing context** — middle turns archive into DENDRITE at 50% context; `/compress` to force
- ✅ **Operator confirmation protocol** — `Decline / AllowOnce / AllowSection / AllowAlways` for every destructive op
- ✅ **Secret redaction engine** — OpenAI / Anthropic / HF / GH / AWS / PEM / JWT auto-masked before persistence
- ✅ **Approval gate** — destructiveshell patterns (rm -rf, mkfs, fork bombs, curl|bash) refused or prompted
- ✅ **SSRF guard** — `web_fetch` refuses loopback / RFC1918 / metadata endpoints under default policy
- ✅ **Sudo password handoff** — agent never sees pwd inline; piped via `sudo -S -p ''` only when typed by operator
- ✅ **Persistent allowlist** at `~/.cynapse/allowlist` — rules survive restarts, sensitive kinds refused
- ✅ **56 new tests** — go vet / go test ./... clean

### v2.2.0
- ✅ **Local model management** — search, download, and run GGUF models from HuggingFace
- ✅ **Direct llama-server inference** — run models without Ollama (auto port allocation, health checks)
- ✅ **Ollama GGUF import** — one-command import with auto-generated Modelfiles
- ✅ **HuggingFace authentication** — `--token` flag, `HF_TOKEN` env var, config support for gated models
- ✅ **Multimodal attachments** — images, PDFs, text files from `./workspace/` folder
- ✅ **Vision model support** — base64 image encoding for Ollama and local llama-server
- ✅ **TUI slash commands** — `/attach`, `/attachments`, `/clear-attach`
- ✅ **TUI Local Models menu** — switch between Ollama and direct local inference

### v2.1.0
- ✅ **OpenAI & Anthropic streaming** — SSE-based with tool-call reconstruction
- ✅ **Synapse local-path installation** — `cynapse synapse add <name> --path <binary>`
- ✅ **Synapse manifest system** — `synapses.json` caches metadata, no need to execute binaries on startup
- ✅ **Synapse URL download** — install from remote URLs with SHA-256 verification
- ✅ **DENDRITE multi-hop traversal** — 2-hop and 3-hop neighborhood queries
- ✅ **DENDRITE fact deduplication** — identical memories merge instead of duplicating
- ✅ **DENDRITE FTS5 fallback** — works on systems without the FTS5 SQLite extension
- ✅ **Relevance engine overhaul** — FTS5 + word-by-word search + stop-word filtering
- ✅ **13 integration tests** — full lifecycle, persistence, traversal, deduplication

### v2.0.0-beta
- Multi-LLM support (Ollama, Anthropic, OpenAI, Gemini)
- MCP integration
- TUI with Bubble Tea
- Session management
- Heartbeat curator

---

## 🛠️ Manual Build

```bash
# Clone
git clone https://github.com/Alartist40/cynapse.git
cd cynapse

# Install dependencies (Debian/Ubuntu)
sudo apt-get install build-essential pkg-config libsqlite3-dev

# Build
go build -o cynapse ./cmd/cynapse

# Install
sudo mv cynapse /usr/local/bin/

# Setup home directory
mkdir -p ~/.cynapse/{synapses,data,logs}
cp config.yaml ~/.cynapse/

# Run
cynapse
```

---

## 🧪 Testing

```bash
# Run all tests
go test ./...

# Run memory tests with verbosity
go test ./internal/memory/... -v

# Build check
go build ./...
```

**Current test status:** `69/69 passing` across `internal/{api,approval,compressor,confirm,memory,netguard,redact,tools}`.

---

## 🖥️ System Requirements

| | Minimum | Recommended |
|--|---------|-------------|
| **RAM** | 2GB | 4GB+ |
| **Disk** | 500MB | 2GB+ |
| **Go** | 1.22+ | 1.22+ |
| **OS** | Linux, macOS, Windows | Linux x86_64/ARM64 |

**Tested on:**
- Raspberry Pi 5 (8GB) — primary target platform
- Ubuntu 22.04+ / Debian 12+
- macOS Ventura+ (Intel & Apple Silicon)
- Windows 10/11 (WSL2 recommended)

---

## 🔮 Roadmap

- [x] Local model search & download from HuggingFace
- [x] Direct llama-server subprocess inference
- [x] Multimodal attachments (images, PDFs, text)
- [x] HuggingFace authentication for gated models
- [ ] Gemini streaming support
- [ ] Cynapse ↔ Leafcutter runtime bridge (use Leafcutter as LLM backend)
- [ ] Remote synapse registry (download synapses without `--path`)
- [ ] Semantic search in DENDRITE (vector embeddings)
- [ ] Vision model auto-pairing (auto-download mmproj)
- [ ] Model quantization advisor (RAM-based suggestions)
- [ ] Voice synapse (STT + TTS)
- [ ] Multi-agent federation

---

## 🤝 Contributing

Contributions welcome! See [handoff-cynapse.md](handoff-cynapse.md) for current state and context.

**Priority areas:**
- New synapse development
- LLM provider integrations
- DENDRITE graph algorithms
- Cross-platform testing

---

## 📜 License

MIT License — see [LICENSE](LICENSE).

---

## 🙏 Acknowledgments

- [Bubble Tea](https://github.com/charmbracelet/bubbletea) — the TUI framework that makes terminals beautiful
- [MCP](https://modelcontextprotocol.io) — Anthropic's Model Context Protocol
- [LeafcutterLLM](https://github.com/Alartist40/LeafcutterLLM) — our Rust inference engine synapse

---

**Built with 💜 for the terminal. Designed for the future.**

> *"The synapse is not the neuron. The synapse is the connection. Cynapse is the connection."*
