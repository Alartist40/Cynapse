# Cynapse: The Ghost Shell Hub

> *"Your AI should know you—but no one else."*

**Cynapse** is a bio-digital security ecosystem designed for high-privacy environments. It orchestrates 8 specialized "neurons" (security tools) through a central hub, presenting them in a Neural Operations Center TUI. The system implements air-gapped security with USB-sharded authentication, local AI inference, and zero cloud dependencies.

**Version**: 3.0.0 (The "Self-Repair" Update)  
**Author**: Alejandro Eduardo Garcia Romero  
**License**: MIT

---

## ⚡ Quick Start

Get Cynapse running in under 5 minutes:

### Step 1: Initialize the System
```bash
# Create and activate virtual environment (Recommended)
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Initialize directories
python cynapse_entry.py --init
```

### Step 2: Verify Installation
```bash
python cynapse_entry.py --health
```

### Step 3: Launch
```bash
python cynapse_entry.py --tui
```
You're now in the Synaptic Fortress!

---

## 🚀 New in v3.0.0

### 1. Minimalist TUI (OpenCode Inspired)
A completely rewritten, keyboard-centric interface.
- **Command Palette**: Press `/` to access tools instantly.
- **Threaded Chat**: Organize conversations with Lead, Researcher, and Coder agents.
- **Visuals**: Beautiful, minimal neural aesthetics.

### 2. IT Mode (Self-Repair)
Cynapse can now fix itself.
- **Tech Support Directory**: `cynapse/core/tech_support/`
- **Modules**: Self-contained python scripts that solve specific issues (e.g., Image Repair).
- **Auto-Execution**: The HiveMind detects issues and runs the appropriate module.

### 3. Core Values (Constitutional AI)
Safety is now hardcoded.
- **Constitution**: Immutable principles in `cynapse/core/core_values/constitution.md`.
- **Validator**: An immutable layer that checks every AI output against the Constitution.
- **Enforcement**: Guaranteed truth, privacy, and safety.

---

## 🧠 The 8 Neurons

Cynapse orchestrates 8 specialized security neurons:

| Neuron | Icon | Purpose | Key Features |
|--------|------|---------|--------------|
| **Elara** | 🌙 | 3B Parameter AI Model | MoE architecture, TiDAR dual-head, RoPE, SwiGLU |
| **Bat** | 🦇 | USB Shard Cryptography | 2-of-3 Shamir Secret Sharing, 18kHz ultrasonic auth |
| **Beaver** | 🦫 | AI Firewall Generator | Natural language → rules (iptables/nftables) |
| **Canary** | 🐤 | Distributed Deception | Stealth decoy generation, honeytoken tracking |
| **Meerkat** | 🦔 | Vulnerability Scanner | CVE matching, risk scoring, TUI output |
| **Octopus** | 🐙 | Container Escape Tester | 10 escape vectors, automated defense validation |
| **Owl** | 🦉 | PII Redaction | OCR-based PII detection and redaction |
| **Wolverine** | 🐺 | RAG Security Auditor | RAG poisoning tests, refusal detection |

---

## 🎮 TUI Controls

The Synaptic Fortress uses a Command Palette workflow.

| Key | Action |
|-----|--------|
| `/` | **Open Command Palette** (Run any tool) |
| `Ctrl+N` | New Thread |
| `Ctrl+W` | Close Thread |
| `Ctrl+Tab` | Switch Thread |
| `Ctrl+I` | Toggle Help Overlay |
| `Ctrl+Q` | Quit |

**Common Commands:**
- `/scan` - Run Meerkat vulnerability scan
- `/fix` - Run IT Mode repair
- `/auth` - Authenticate via USB/Voice
- `/clear` - Clear chat history

---

## 🔧 Installation

### Prerequisites
- Python 3.10+
- pip
- (Optional) Ollama for local LLM inference

### Manual Setup

1. **Clone**: `git clone https://github.com/Alartist40/Cynapse.git`
2. **Venv**: `python3 -m venv .venv` && `source .venv/bin/activate`
3. **Install**: `pip install -r requirements.txt`
4. **Init**: `python cynapse_entry.py --init`
5. **Run**: `python cynapse_entry.py --tui`

---

## 🤝 Contributing

Contributions are welcome! Please read our [architecture.md](architecture.md) first.

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- **Alejandro Eduardo Garcia Romero** - Creator
- **Frank Niu (OpenCode)** - Inspiration for the v3 TUI and Agentic patterns
- **Anthropic** - Inspiration for Constitutional AI and Artifacts
