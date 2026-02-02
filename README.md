# 🦌 Cynapse – Ghost Shell Hub

<div align="center">

**Plug in three USBs, whistle, and your AI comes alive.**

[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Neurons](https://img.shields.io/badge/Neurons-12-orange.svg)](#neurons)

</div>

---

## 📖 Overview

**Cynapse** is a physical + digital security ecosystem that transforms **12 standalone security tools** into a **single voice-orchestrated arsenal**. It features:

- **🎙️ Voice Control**: Speak commands or whistle 18 kHz to activate
- **🔐 Distributed AI**: Model shards split across 3 USB sticks (Ghost Shell)
- **🔒 Cryptographic Signing**: All neurons verified before execution
- **📝 Audit Logging**: Every action logged in NDJSON format
- **🧩 Modular Design**: Easy to add custom neurons

### Core Components

| Component | Description |
|-----------|-------------|
| **Cynapse Hub** (32 GB USB) | Your orchestrator, logger, and vault |
| **Ghost Shell** (3 × 4 GB USBs) | Bat-1, Bat-2, Bat-3 with sharded AI model |
| **12 Neurons** | Security tools as signed, self-checking modules |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** ([Download](https://www.python.org/downloads/))
- **Git** ([Download](https://git-scm.com/downloads))
- **Windows 10/11**, **macOS 10.15+**, or **Linux**

### Installation

```bash
# Clone the repository
git clone https://github.com/Alartist40/Cynapse.git
cd Cynapse/cynapse

# Install dependencies
pip install -r requirements.txt

# Run Cynapse Hub
python cynapse.py
```

### First Run

```
   _____                                  
  / ____|                                 
 | |    _   _ _ __   __ _ _ __  ___  ___ 
 | |   | | | | '_ \ / _` | '_ \/ __|/ _ \
 | |___| |_| | | | | (_| | |_) \__ \  __/
  \_____\__, |_| |_|\__,_| .__/|___/\___|
         __/ |           | |             
        |___/            |_|   Ghost Shell Hub

🦌 Cynapse Hub v1.0 initialized
📦 12 neurons loaded: 🦏 🦡 🦇 🦉 🐘 🐺 🦜 🐙 🦫 🦌 🌙 🐦

cynapse> list
cynapse> help
```

### Modern TUI Mode (Recommended)

For a stable, non-scrolling interface with real-time status monitoring:

```bash
python cynapse.py --tui
```

---

## 🧠 The 12 Neurons

| # | Animal | Neuron | Description |
|---|--------|--------|-------------|
| 1 | 🦏 | **Rhino Gateway** | Zero-Trust LLM Gateway |
| 2 | 🦡 | **Meerkat Scanner** | Air-Gap Update Scanner (CVE) |
| 3 | 🐦 | **Canary Token** | AI-powered honeypot generator |
| 4 | 🐺 | **Wolverine RedTeam** | Local RAG for security testing |
| 5 | 🐁 | **TinyML Anomaly** | Edge device anomaly detection |
| 6 | 🦉 | **Owl OCR** | Privacy-focused document redaction |
| 7 | 🐘 | **Elephant Sign** | Cryptographic model signing |
| 8 | 🦜 | **Parrot Wallet** | Off-grid voice cryptocurrency wallet |
| 9 | 🐙 | **Octopus CTF** | Container escape training |
| 10 | 🦫 | **Beaver Miner** | AI firewall rule generator |
| 11 | 🦌 | **DevAle** | AI development assistant |
| 12 | 🌙 | **Elara** | Custom 2.8B parameter AI model |
| 13 | 🐝 | **HiveMind** | Personal AI Ecosystem (Queen + Drones) |

---

## 🦇 Ghost Shell System

The Ghost Shell is a distributed AI system split across three USB sticks:

```
Bat-1 (Whisper Wake)    → Shard 1 + Ultrasonic detector
Bat-2 (Canary Shard)    → Shard 2 + Honeypot decoy
Bat-3 (CTF Shard)       → Shard 3 + Red-team challenge
```

### How It Works

1. **Plug in all three Bat USBs** + Cynapse Hub
2. **Whistle 18 kHz** (dog whistle or generated tone)
3. **Ghost Shell awakens**: Shards combine in RAM
4. **Elara responds** to your voice query
5. **Bats go dark**: RAM cleared, model erased

### Creating Shards

```bash
cd cynapse/neurons/bat_ghost
python assemble.py --split path/to/elara.gguf
```

---

## 🔧 Fresh Computer Setup

### Windows

1. **Install Python 3.8+**
   - Download from [python.org](https://www.python.org/downloads/)
   - ✅ Check "Add Python to PATH" during installation

2. **Install Git**
   - Download from [git-scm.com](https://git-scm.com/downloads)

3. **Install PortAudio** (for voice control)
   ```powershell
   # Install via Chocolatey (optional)
   choco install portaudio
   ```

4. **Clone and Setup**
   ```powershell
   git clone https://github.com/Alartist40/Cynapse.git
   cd Cynapse\cynapse
   pip install -r requirements.txt
   python cynapse.py
   ```

### macOS

```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python portaudio

# Clone and setup
git clone https://github.com/Alartist40/Cynapse.git
cd Cynapse/cynapse
pip3 install -r requirements.txt
python3 cynapse.py
```

### Linux (Ubuntu/Debian)

```bash
# Install dependencies
sudo apt update
sudo apt install python3 python3-pip portaudio19-dev git

# Clone and setup
git clone https://github.com/Alartist40/Cynapse.git
cd Cynapse/cynapse
pip3 install -r requirements.txt
python3 cynapse.py
```

---

## 🎤 Voice Control

### Enabling Voice Control

```
cynapse> voice
Starting voice listener...
Whistle 18 kHz to wake Ghost Shell
```

### Generating Test Tones

```bash
cd cynapse/neurons/bat_ghost
python whistle_detector.py --generate-test
# Creates test_tone_18000hz.wav
```

### Voice Commands

| Command | Action |
|---------|--------|
| Whistle 18 kHz | Wake Ghost Shell |
| "Scan network" | Run Meerkat Scanner |
| "Redact document" | Run Owl OCR |
| "Redact document" | Run Owl OCR |
| "Exit" | Shut down hub |

---

## 🐝 HiveMind Ecosystem

HiveMind allows you to train a custom model (Queen) using large open-source models (Workers) and route queries to specialists (Drones).

### Quick Usage

**The Easiest Way: Interactive Menu**
Simply run the script without arguments to launch the dashboard:
```bash
python hivemind.py
# Opens the control panel:
# 1. [Interact] Chat with Queen & Drones
# 2. [Feed]     Train Queen on 70B Model
# 3. [Learn]    Teach Queen your style
```

### Manual Commands
If you prefer direct commands:
```bash
# Feed: Train Queen (3B) using a Teacher (AirLLM 70B)
python hivemind.py feed --teacher meta-llama/Llama-2-70b-chat-hf

# Interact: Chat with automatic routing
python hivemind.py interact --auto-route
```


---

## 📂 Directory Structure

```
cynapse/
├── cynapse.py              # Main orchestrator
├── hivemind.py             # HiveMind CLI (lazy loading)
├── build_portable.py       # Portable build script
├── no_dependency.md        # Portability strategy
├── config/
│   ├── config.ini.example  # Configuration template
│   └── user_keys.json.example  # API keys template
├── hivemind/               # HiveMind AI ecosystem
│   ├── queen/              # Queen model trainer
│   ├── drones/             # Specialist routers
│   ├── interact/           # Chat interface
│   └── learn/              # Adaptation logic
├── neurons/                # 12 security tools
│   ├── bat_ghost/          # Ghost Shell system
│   ├── rhino_gateway/      # Zero-Trust Gateway
│   ├── meerkat_scanner/    # CVE Scanner
│   ├── elara/              # Custom 2.8B AI model
│   └── ...
├── .cynapse/               # Internal data (logs, etc.)
│   └── logs/               # Audit logs (NDJSON)
├── temp/                   # RAM-disk operations
├── data/
│   ├── training/           # Training documents
│   └── storage/            # Model & voice data
├── assets/                 # Logos and icons
├── build/                  # Build scripts
│   └── portable/           # USB-ready distribution
└── airllm/                 # 70B model loader
```

---

## ⚙️ Configuration

### Setting Up API Keys

1. Copy the example file:
   ```bash
   cp config/user_keys.json.example config/user_keys.json
   ```

2. Edit `config/user_keys.json`:
   ```json
   {
       "assembly_key": "YOUR_32_CHARACTER_SECRET_KEY_HERE",
       "openai_api_key": "sk-...",
       "whisper_model_path": "neurons/elara/whisper/ggml-tiny.en-q5_1.bin"
   }
   ```

### Configuration Options

Edit `config/config.ini`:

```ini
[voice]
whistle_frequency = 18000
whistle_threshold = 1000000

[assembly]
enable_encryption = true

[neurons]
verify_signatures = true
```

---

## 🧪 Testing

### Verify Installation

```bash
cd cynapse
python cynapse.py --help
python hivemind.py --help
```

---

## 🔨 Building

### Portable USB Deployment (No Python Required)

Create a standalone distribution that runs on any Windows PC:

```bash
cd cynapse
python build_portable.py
# Output: build/portable/
```

Copy `build/portable/` to a USB stick and run `run_cynapse.bat` on any Windows machine.

See [no_dependency.md](no_dependency.md) for detailed portability strategies.

### Windows

```powershell
cd cynapse\build
.\build_all.ps1
```

### Unix/Linux/macOS

```bash
cd cynapse/build
chmod +x build_all.sh
./build_all.sh
```

---

## 🔐 Security Considerations

- **Never commit** `config/user_keys.json` (contains secrets)
- **Shards are encrypted** with your assembly key
- **All neurons verified** before execution (when signatures enabled)
- **Audit logs** track every action with timestamps
- **RAM-only assembly** – no model persisted to disk

---

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 👤 Author

**Alejandro Eduardo Garcia Romero**

- GitHub: [@Alartist40](https://github.com/Alartist40)

---

<div align="center">

**🦌 Cynapse – Your AI Security Arsenal**

*"Speak a codeword, and your entire security posture executes – offline, encrypted, and ephemeral."*

</div>
