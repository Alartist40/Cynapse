# CYNAPSE — Ghost Shell (Native Terminal Edition)

Pure Go terminal TUI. No browser, no HTTP server — just a single binary that runs directly in your terminal.

## Features

- ✅ **Native Terminal UI** — Runs in any terminal emulator
- ✅ **Real Boot Checks** — Verifies Ollama, config, memory, LLM before launch
- ✅ **Idle & Active States** — Large hero when idle, shrinks when active
- ✅ **Purple + Orange Theme** — Minimalist, high-contrast design
- ✅ **Live Stats** — Response time, token count in status bar
- ✅ **Multi-Provider LLM** — Ollama (local), Anthropic, OpenAI, Gemini
- ✅ **Hermes-Style Memory** — Markdown persona files, SQLite store, heartbeat curator
- ✅ **Tools** — bash, file ops, web fetch, memory tools
- ✅ **MCP Integration** — Connect external tool servers
- ✅ **Single Binary** — `./cynapse` and go

## Quick Start

```bash
# Make sure Ollama is running
ollama serve  # in another terminal

# Build & run
go mod tidy
go build -o cynapse ./cmd/cynapse
./cynapse
```

## Usage

**Boot sequence:**
- Shows CYNAPSE hero logo
- Runs 6 real system checks
- Only proceeds if all pass

**Idle state:**
- Large centered CYNAPSE logo
- Type to chat

**Active state (after first message):**
- Logo shrinks to top-left
- Full conversation area
- Status bar shows: Model | Response time | Token count

**Menu:**
- Press `/` → Opens menu
- Navigate: ↑↓ or j/k
- Select: Enter
- Commands: Status, Models, Memory, Heartbeat, Clear, Help, Quit

## Config

Edit `config.yaml` to switch providers:

```yaml
llm:
  provider: "ollama"         # or anthropic | openai | gemini
  model: "qwen3.5:9b"        # model name
  ollama_base_url: "http://localhost:11434"
```

## Memory System

Like Hermes Agent:
- **Persona files**: `./data/persona/<device>/SOUL.md`, `MEMORY.md`, `USER.md`, etc.
- **Daily logs**: `./data/persona/<device>/logs/daily/YYYY-MM-DD.md`
- **SQLite store**: `./data/memory.db` (full-text searchable)
- **Heartbeat curator**: Runs every 6 hours, updates MEMORY.md

## Cross-Compile for Pi

```bash
make build-pi        # Pi 5 (arm64)
make build-pi-zero   # Pi Zero 2W (armv7)
```

## Architecture

```
Terminal TUI (Bubble Tea)
        ↓
  Agent Core
        ↓
  LLM Client → Ollama / Anthropic / OpenAI / Gemini
        ↓
 Tools + MCP Servers
 Memory (Persona + SQLite)
 Session (JSONL logs)
```

## Colors

- **Purple** `#9b59b6` — Primary (hero, accents)
- **Orange** `#e67e22` — Secondary (warnings, system messages)
- **Background** `#0a0e14` — Deep dark
- **Dim** `#4a5568` — Secondary text
- **Bright** `#e4e7eb` — Primary text

---

v1.0.0 Ghost Shell — Built for small hardware, runs everywhere.
