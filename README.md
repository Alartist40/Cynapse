# 🧠 CYNAPSE - Ghost Shell AI Agent
**Modular AI Agent System for the Terminal**

![image alt](++++++++)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Go 1.22+](https://img.shields.io/badge/Go-1.22+-00ADD8?logo=go)](https://golang.org)

CYNAPSE is a modular AI agent that runs entirely in your terminal. Built with Go and Bubble Tea, it combines the power of multiple LLM providers with a beautiful TUI interface and extensible synapse (plugin) system.

**Philosophy:** Like Arch Linux for AI - install only what you need, control everything, no bloat.

---

## ⚡ Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/Alartist40/cynapse/main/install.sh | bash
```

That's it! The installer will:
- Auto-detect your OS and architecture
- Install Go and dependencies if needed
- Build CYNAPSE
- Set up ~/.cynapse/ directory
- Add `cynapse` to your PATH

---

## 🚀 Usage

### Run Interactive Chat

```bash
cynapse
```

### Manage Synapses (Extensions)

```bash
# List installed synapses
cynapse synapse list

# Install a synapse
cynapse synapse add leafcutter

# Remove a synapse
cynapse synapse remove git-tools

# Search available synapses
cynapse synapse search inference
```

### Configuration

```bash
# Show config location
cynapse config

# Create default config
cynapse config init

# Edit config
nano ~/.cynapse/config.yaml
```

---

## 📦 Synapses (Optional Extensions)

CYNAPSE uses a modular synapse system - install only what you need:

| Synapse | Description | Install |
|---------|-------------|---------|
| **leafcutter** | CPU-optimized LLM inference engine | `cynapse synapse add leafcutter` |
| **git-tools** | Repository management and analysis | `cynapse synapse add git-tools` |
| **web-automation** | Browser control and scraping | `cynapse synapse add web-automation` |
| **speedtest** | LLM benchmarking and metrics | `cynapse synapse add speedtest` |

> **Like biological synapses:** Each extension creates new neural connections, expanding capabilities without bloating the core.

---

## 🎨 Features

- ✅ **Beautiful TUI** - Purple & orange themed terminal interface
- ✅ **Streaming Responses** - See text appear word-by-word
- ✅ **Multi-LLM Support** - Ollama, Anthropic, OpenAI, Gemini
- ✅ **Model Switching** - Change models on the fly with `/` menu
- ✅ **Memory System** - Persona-driven memory with SQLite storage
- ✅ **MCP Integration** - Model Context Protocol for tool calling
- ✅ **Modular Synapses** - Extend functionality with plugins
- ✅ **Request Cancellation** - Cancel long-running requests
- ✅ **Session Management** - JSONL conversation logs
- ✅ **Cross-platform** - Linux, macOS, Windows

---

## 🏗️ Architecture

```
CYNAPSE Core (Your Brain)
├─ TUI Interface
├─ Agent System
├─ Memory & Persona
└─ MCP Manager
    └─ Synapses (Load on demand)
        ├─ LeafcutterLLM
        ├─ GitTools  
        ├─ WebAutomation
        └─ Your custom extensions...
```

---

## 💻 Manual Installation (Advanced)

If you prefer to build manually:

```bash
# Clone repository
git clone https://github.com/Alartist40/cynapse.git
cd cynapse

# Install dependencies (Linux/Debian)
sudo apt-get install build-essential pkg-config libopenblas-dev libsqlite3-dev

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

## 🔧 Configuration

CYNAPSE uses `~/.cynapse/config.yaml`:

```yaml
# LLM Provider
llm:
  provider: "ollama"              # ollama | anthropic | openai | gemini
  model: "qwen3.5:9b"
  ollama_base_url: "http://localhost:11434"
  max_tokens: 4096
  temperature: 0.7

# Memory System
memory:
  persona_path: "~/.cynapse/data/persona"
  sessions_path: "~/.cynapse/data/sessions"
  db_path: "~/.cynapse/data/memory.db"

# MCP Servers (auto-loaded from synapses)
mcp:
  enabled: true
  servers: []

# Tools
tools:
  profile: "standard"             # minimal | standard | full
  work_dir: "./workspace"
```

---

## 🎯 Building Your Own Synapse

Want to build custom extensions? Use the synapse template:

```bash
# Clone template
git clone https://github.com/Alartist40/cynapse-synapse-template my-synapse
cd my-synapse

# Implement your tools in internal/tools.go
# Update synapse.yaml with metadata

# Build
go build -o my-synapse ./cmd/synapse

# Test
echo '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | ./my-synapse

# Users can install with:
# cynapse synapse add my-synapse
```

See [Synapse Development Guide](docs/SYNAPSE_DEVELOPMENT.md) for details.

---

## 📊 System Requirements

**Minimum:**
- Go 1.22+ (auto-installed by installer)
- 2GB RAM
- 500MB disk space

**Recommended:**
- 4GB+ RAM (for larger models)
- 8GB+ RAM (for LeafcutterLLM with 7B models)

**Supported Platforms:**
- Linux (x86_64, arm64, armv7)
- macOS (x86_64, arm64)
- Windows (x86_64)

**Tested On:**
- Raspberry Pi 5 (8GB)
- Raspberry Pi Zero 2W
- Ubuntu 22.04+
- macOS Ventura+
- Windows 10/11

---

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md).

**Areas to contribute:**
- New synapse development
- LLM provider integrations
- Documentation improvements
- Bug fixes and performance optimizations

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file.

---

## 🙏 Acknowledgments

- Built with [Bubble Tea](https://github.com/charmbracelet/bubbletea) TUI framework
- Inspired by biological neural networks
- MCP protocol by Anthropic

---

## 📬 Contact

**Author:** Alartist40  
**Repository:** [github.com/Alartist40/cynapse](https://github.com/Alartist40/cynapse)  
**Website:** [alartist40.github.io](https://alartist40.github.io)

---

**Built with 💜 for the terminal**
