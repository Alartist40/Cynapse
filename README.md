# 🦌 Cynapse – Ghost Shell Hub

<div align="center">

**Plug in three USBs, whistle, and your AI comes alive.**

[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Neurons](https://img.shields.io/badge/Neurons-12-orange.svg)](#neurons)
[![TUI](https://img.shields.io/badge/TUI-Synaptic%20Fortress-purple.svg)](#tui)

</div>

---

## 📖 Overview

Cynapse is a **specialized security ecosystem** designed for air-gapped and high-security environments. It orchestrates 12+ standalone security "neurons" (tools) through a central hub, providing:

- **Physical Security**: Sharded AI model storage across multiple USB drives (Ghost Shell)
- **Voice Control**: Hands-free operation via ultrasonic whistle triggers (18kHz)
- **Local AI**: On-premise training and inference with the HiveMind system
- **Portable Deployment**: Run entirely from USB on any Windows, Mac, or Linux system

### Core Philosophy

> *"Your AI should know you—but no one else."*

Cynapse treats your computer as a living organism, with 12 specialized neurons working together through a central nervous system. The architecture ensures that sensitive AI models and security tools remain under your physical control.

---

## ✨ Features

### 🧠 HiveMind AI System
- **Queen**: Your personal AI model trained on your style and preferences
- **Drones**: Specialized AI agents for specific tasks
- **RAG Laboratory**: Document ingestion and retrieval-augmented generation
- **Local Training**: Fine-tune models without cloud dependencies

### 🔐 Ghost Shell Security
- AI model split across 3 USB shards using Shamir's Secret Sharing
- Requires physical presence of all shards to reconstruct
- Ed25519 signature verification for all binaries
- Tamper detection and automatic lockdown

### 🐾 12 Security Neurons

| Neuron | Animal | Purpose |
|--------|--------|---------|
| **bat_ghost** | 🦇 Bat | USB shard management and model reconstruction |
| **beaver_miner** | 🦫 Beaver | LLM-powered firewall rule generation |
| **canary_token** | 🐤 Canary | Decoy file deployment and breach detection |
| **elara** | 🌙 Moon | AI companion and orchestration |
| **elephant_sign** | 🐘 Elephant | Binary signature verification |
| **meerkat_scanner** | 🦔 Meerkat | Network vulnerability scanning |
| **octopus_ctf** | 🐙 Octopus | CTF challenge management |
| **owl_ocr** | 🦉 Owl | Document OCR and text extraction |
| **parrot_wallet** | 🦜 Parrot | Cryptocurrency wallet management |
| **rhino_gateway** | 🦏 Rhino | API gateway and rate limiting |
| **tinyml_anomaly** | 🔬 TinyML | Edge ML anomaly detection |
| **wolverine_redteam** | 🐺 Wolverine | Red team tooling |

### 🖥️ Synaptic Fortress TUI

A cyberpunk-biological fusion terminal interface featuring:
- **Purple Dynasty** color theme with ANSI 256 colors
- **Four-zone layout**: Perimeter, Sentinel Grid, Activation Chamber, Operations Bay
- **Vim-style navigation** with hjkl keys
- **Real-time animations** with minimal CPU usage
- **Security modes**: Normal, Scanning, and Breach Alert

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/cynapse.git
cd cynapse

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running Cynapse

```bash
# Start interactive CLI
python cynapse.py

# Launch the TUI (Terminal User Interface)
python cynapse.py --tui

# List available neurons
python cynapse.py --list

# Run verification tests
python cynapse.py --test

# Run a specific neuron
python cynapse.py beaver_miner generate --threat "block SSH brute force"
```

### HiveMind AI

```bash
# Start HiveMind interactive menu
python hivemind.py

# Or use CLI mode
python hivemind.py interact --model queen --auto-route
python hivemind.py feed --teacher meta-llama/Llama-2-70b-chat-hf
python hivemind.py learn --mode observe
```

---

## 🖥️ TUI Usage

The Synaptic Fortress TUI provides a rich visual interface:

```bash
python cynapse.py --tui
```

### Keybindings

| Key | Action |
|-----|--------|
| `h` | Toggle help overlay |
| `v` | Toggle voice monitor (18kHz whistle) |
| `s` | Start security scan |
| `L` | Emergency lockdown (Shift+L) |
| `Q` | Quit (Shift+Q) |
| `j/k` | Navigate up/down |
| `Enter` | Activate selected item |
| `Space` | Toggle neuron state |
| `a` | Arm all neurons |
| `d` | Disarm all neurons |
| `Tab` | Cycle between zones |
| `Esc` | Back / Close modal |

### Interface Zones

1. **Perimeter (Top)**: Security status, integrity %, voice monitor, shard status
2. **Sentinel Grid (Left)**: List of all neurons with status icons
3. **Activation Chamber (Top-Right)**: Mode-specific visualizations
4. **Operations Bay (Bottom-Right)**: RAG laboratory and chat interface

---

## 📁 Project Structure

```
cynapse/
├── cynapse.py           # Main hub orchestrator
├── hivemind.py          # HiveMind AI CLI
├── tui/                 # Terminal User Interface
│   ├── main.py          # TUI entry point
│   ├── colors.py        # ANSI 256 color palette
│   ├── symbols.py       # Semantic symbols
│   ├── state.py         # Centralized state management
│   ├── layout.py        # Four-zone layout system
│   ├── keybindings.py   # Keyboard controls
│   ├── modes/           # Interface modes
│   │   ├── neural_assembly.py
│   │   ├── pharmacode.py
│   │   ├── operations.py
│   │   └── breach.py
│   └── widgets/         # Reusable UI components
│       ├── status_bar.py
│       ├── sentinel_grid.py
│       └── animations.py
├── utils/               # Shared utilities
│   └── security.py      # Input validation, sanitization
├── neurons/             # Security tool modules
│   ├── bat_ghost/
│   ├── beaver_miner/
│   ├── canary_token/
│   ├── elara/
│   ├── elephant_sign/
│   ├── meerkat_scanner/
│   ├── octopus_ctf/
│   ├── owl_ocr/
│   ├── parrot_wallet/
│   ├── rhino_gateway/
│   ├── tinyml_anomaly/
│   └── wolverine_redteam/
├── hivemind/            # AI subsystem
│   ├── queen/           # Main AI model
│   ├── drones/          # Specialized agents
│   ├── interact/        # Chat interface
│   └── learn/           # Training system
├── config/              # Configuration files
├── data/                # Data storage
└── requirements.txt     # Python dependencies
```

---

## 🔧 Configuration

### Hub Configuration

Edit `config/hub.ini`:

```ini
[hub]
log_level = INFO
neurons_dir = ./neurons
temp_dir = ./temp

[security]
require_signatures = true
audit_logging = true
sensitive_keywords = key,secret,token,password

[voice]
enabled = true
frequency = 18000
threshold = 0.7
```

### Neuron Manifests

Each neuron has a `manifest.json`:

```json
{
  "name": "beaver_miner",
  "version": "1.0.0",
  "description": "LLM-powered firewall rule generator",
  "author": "Cynapse Team",
  "animal": "beaver",
  "platform": ["linux", "darwin", "win32"],
  "entry_point": "rule_miner.py",
  "requires_signature": true,
  "dependencies": ["ollama"],
  "commands": {
    "generate": "Generate firewall rules from threat description",
    "verify": "Verify generated rules in sandbox"
  }
}
```

---

## 🛡️ Security

### Implemented Protections

- **Input Validation**: All LLM outputs are sanitized before use in shell commands
- **Path Traversal Prevention**: All file paths validated against base directories
- **API Key Masking**: Sensitive data masked in logs (first 4 chars + hash)
- **Signature Verification**: Ed25519 signatures on all neuron binaries
- **Audit Logging**: NDJSON audit trail of all operations

### Security Audit

Run the built-in security tests:

```bash
python cynapse.py --test
```

---

## 📦 Dependencies

See [DEPENDENCIES.md](DEPENDENCIES.md) for a complete list with descriptions.

### Minimal Installation

```bash
pip install numpy pycryptodome PyYAML colorama psutil tqdm
```

### Full Installation (with AI)

```bash
pip install -r requirements.txt
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements.txt
pip install pytest black flake8

# Run tests
python cynapse.py --test

# Format code
black cynapse.py tui/ utils/
```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/cynapse/issues)
- **Documentation**: [Wiki](https://github.com/yourusername/cynapse/wiki)

---

<div align="center">

**Built with 🧠 by the Cynapse Team**

*"The mind is the best firewall."*

</div>
