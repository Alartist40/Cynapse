# Cynapse: The Ghost Shell Hub

> *"Your AI should know you—but no one else."*

**Cynapse** is a bio-digital security ecosystem designed for high-privacy environments. It orchestrates 8 specialized "neurons" (security tools) through a central hub, presenting them in a Neural Operations Center TUI. The system implements air-gapped security with USB-sharded authentication, local AI inference, and zero cloud dependencies.

**Version**: 4.0.1 (The "Ghost Shell" Restoration)
**Author**: Alejandro Eduardo Garcia Romero  
**License**: MIT

---

## ⚡ Quick Start

Get Cynapse running in seconds with the new Go-native core:

### Step 1: Set up AI Environment
```bash
# Optional but recommended for Elara/Owl
python3 -m venv v4/python/venv
source v4/python/venv/bin/activate
pip install -r v4/python/requirements-ai.txt
```

### Step 2: Build the System
```bash
cd v4
chmod +x scripts/build.sh
./scripts/build.sh
```

### Step 3: Verify & Launch
```bash
./dist/cynapse --health
./dist/cynapse
```
You're now in the Synaptic Fortress!

---

## 🚀 New in v4.0.1 "Ghost Shell"

### 1. Go-First Architecture
Cynapse has been reconstructed in Go for massive performance gains.
- **Fast Startup**: ~6ms cold start (no Python import lag).
- **Single Binary**: Portability without "dependency hell" (mostly).
- **Concurrency**: True parallel neuron execution via goroutines.

### 2. High-Performance TUI (Bubble Tea)
The TUI is now implemented in native Go using the Charm ecosystem.
- **Zero Flicker**: Declarative rendering via Bubble Tea.
- **Responsive**: Instant keyboard input handling.
- **Command Palette**: Press `/` for instant action.

### 3. Neurons as Plugins
- **Go-Native**: 6 neurons (Bat, Beaver, Canary, Meerkat, Octopus, Wolverine) rewritten in Go for speed.
- **Python Bridge**: Elara (3B MoE) and Owl (OCR) remain in Python, connected via high-speed IPC bridge.

### 4. Compiled-in Constitutional AI
- **Core Values**: Safety principles are compiled directly into the Go binary.
- **Validator**: Impossible for the AI to modify its own guardrails.

---

## 🧠 The 8 Neurons

| Neuron | Icon | Implementation | Purpose |
|--------|------|----------------|---------|
| **Elara** | 🌙 | Python (Bridge) | 3B Parameter AI Model (MoE architecture) |
| **Bat** | 🦇 | Go (Native) | USB Shard Cryptography (2-of-3 SSS) |
| **Beaver** | 🦫 | Go (Native) | AI Firewall Generator (NL → iptables/nftables) |
| **Canary** | 🐤 | Go (Native) | Distributed Deception & Honeypots |
| **Meerkat** | 🦔 | Go (Native) | High-speed Concurrent Port Scanner |
| **Octopus** | 🐙 | Go (Native) | Container Escape Tester (10+ vectors) |
| **Owl** | 🦉 | Python (Bridge) | OCR-based PII Redaction |
| **Wolverine** | 🐺 | Go (Native) | RAG Security Auditor & Log Analysis |

---

## 🎮 TUI Controls

| Key | Action |
|-----|--------|
| `/` | **Open Command Palette** |
| `Ctrl+I` | Toggle Help Overlay |
| `Ctrl+Q` | Quit |
| `Enter` | Send Message |
| `Esc` | Close Palette / Help |

---

## 🔧 Installation

### Prerequisites
- Go 1.22+
- Python 3.10+ (for Elara/Owl)
- GCC/Make (for build)

### Manual Setup
1. **Clone**: `git clone https://github.com/Alartist40/Cynapse.git`
2. **Build**: `cd v4 && ./scripts/build.sh`
3. **Run**: `./dist/cynapse`

---

## 📂 Project Structure (v4)
```
v4/
├── cmd/cynapse/      # Go Entry Point
├── internal/
│   ├── tui/          # Bubble Tea Interface
│   ├── hivemind/     # Goroutine Engine
│   ├── core/         # Types & Validator
│   ├── neurons/      # Go-Native Tools
│   └── bridge/       # Python IPC Bridge
└── python/           # AI Bridge Servers
```

---

## 🤝 Contributing
Contributions are welcome! Please read our [architecture.md](architecture.md).

## 📄 License
MIT License. See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments
- **Alejandro Eduardo Garcia Romero** - Creator
- **Charm (Bubble Tea)** - For the TUI engine
- **Anthropic** - Inspiration for Constitutional AI
