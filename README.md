# Cynapse: The Ghost Shell Hub

> *"Your AI should know you—but no one else."*

**Cynapse** is a bio-digital security ecosystem designed for high-privacy environments. It orchestrates 8 specialized "neurons" (security tools) through a central hub, presenting them in a Neural Operations Center TUI. The system implements air-gapped security with USB-sharded authentication, local AI inference, and zero cloud dependencies.

**Version**: 2.2.0-agent
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

# Initialize directories
python cynapse_entry.py --init
```
This creates all required directories and configuration files.

### Step 2: Verify Installation
```bash
python cynapse_entry.py --health
```
Checks that all components are properly configured.

### Step 3: Launch
```bash
python cynapse_entry.py --tui
```
You're now in the Synaptic Fortress!

---

### 🔍 Key Improvements (v2.1.0-fix)

We have newly implemented critical performance, architecture optimizations, and Multi-Agent capabilities:

1.  **HiveMind 2.0 (Multi-Agent System)**:
    *   **Lead Agent (Elara)**: Orchestrates complex tasks by breaking them down and assigning them to specialized subagents.
    *   **Subagents**: Specialized agents (Researcher, Coder, Tester) that execute tasks in parallel.
    *   **Artifact Passing**: Agents communicate by passing file references (artifacts) rather than full context, preserving privacy and token budget.

2.  **Low-End Hardware Optimization**:
    *   **Lazy Loading**: Heavy libraries like `numpy` and `torch` now only load when absolutely needed, reducing startup time (< 300ms) and memory usage.
    *   **TUI Rendering**: Replaced the flickering `print()` loop with a double-buffered `sys.stdout.write()` system, increasing frame rate from 4fps to **10fps** without extra CPU load.

2.  **Architecture Robustness**:
    *   **Thread Safety**: Added locks to `HiveMind` to prevent race conditions when spawning multiple bees.
    *   **Non-Blocking UI**: Chat deployment now runs in a background thread, so the interface never freezes while waiting for AI.
    *   **Central Config**: Unified configuration management via `cynapse.utils.config`.

3.  **Integration & Security**:
    *   **Neuron Discovery**: Robust `manifest.json` parsing for proper metadata loading.
    *   **Sensitive Data Redaction**: Automatic scrubbing of API keys and tokens from logs.

---

## 🚀 Features

### Core Capabilities
- **Synaptic Fortress TUI**: A cyberpunk terminal interface that visualizes your system's security state as a living organism with 4 interactive zones
- **HiveMind AI**: An n8n-style workflow engine for local AI (Elara 3B) training and tool orchestration
- **Ghost Shell**: Physical security via USB-sharded authentication (2-of-3 Shamir Secret Sharing) and RAM-only model assembly
- **Zero Cloud Dependencies**: All AI training and inference happens on-device
- **Low-End Optimized**: Runs on 2GB RAM devices with lazy-loading and efficient TUI rendering

### Security Model
- **Air-Gap Ready**: No hardcoded external API calls in core startup
- **Sharded Authentication**: Multi-factor auth combining physical (USB) + acoustic (18kHz whistle)
- **Signed Code**: Ed25519 signature verification before neuron execution
- **Audit Trail**: NDJSON append-only logging with sensitive data redaction

---

## 📋 System Requirements

### Minimum (Core Only)
- Python 3.10+
- 2GB RAM
- Linux/macOS/Windows
- Core dependencies: numpy, cryptography, aiohttp, psutil, pyyaml

### Recommended (Full AI Features)
- Python 3.10+
- 8GB+ RAM (16GB for model training)
- 10GB disk space
- Linux or macOS (Windows supported with WSL)
- [Ollama](https://ollama.ai) installed and running
- GPU optional but recommended for Elara inference

---

## 🔧 Installation

### Prerequisites
Before installing, ensure you have:
1. Python 3.10 or higher
2. pip package manager
3. (Optional but recommended) Ollama for local LLM inference

### Installation Steps

#### Step 1: Clone Repository
```bash
git clone https://github.com/Alartist40/Cynapse.git
cd Cynapse
```

#### Step 2: Run Setup Script (Recommended)
We provide a helper script that handles everything for you (virtual environment, dependencies, and launching).

```bash
chmod +x run.sh
./run.sh --tui
```

This will:
1. Create a virtual environment (`.venv`) if missing.
2. Install necessary dependencies.
3. Launch Cynapse.

#### Alternative: Manual Setup

If you prefer to manage it yourself:

1. **Create venv**: `python3 -m venv .venv`
2. **Activate**: `source .venv/bin/activate`
3. **Install**: `pip install -r requirements.txt`
4. **Run**: `python cynapse_entry.py --tui`

This creates:
- `cynapse/data/` directory structure (storage, documents, models, temp)
- `cynapse/data/agent_artifacts/` for multi-agent deliverables
- `workflows/` directory with YAML templates
- `logs/` directory for audit trails
- `cynapse/data/config.ini` with default settings
- `hivemind.yaml` with workflow configuration

#### Step 4: Verify Installation
```bash
python cynapse_entry.py --health
```

Expected output:
```
🏥 Cynapse Health Check
==================================================
📁 Directory structure:     ✅ All directories present
⚙️  Configuration:         ✅ config.ini & hivemind.yaml present  
🧩 Module imports:         ✅ All modules import successfully
🧠 Neuron discovery:       ✅ 9 neurons discovered
📦 Core dependencies:      ✅ All installed
==================================================
📊 Summary: All systems operational!
🎉 Ready to launch: python cynapse_entry.py --tui
```

#### Step 5: Launch TUI
```bash
python cynapse_entry.py --tui
```

---

## 🧠 The 8 Neurons

Cynapse orchestrates 8 specialized security neurons, each with unique capabilities:

| Neuron | Icon | Purpose | Key Features |
|--------|------|---------|--------------|
| **Elara** | 🌙 | 3B Parameter AI Model | MoE architecture (8+1 experts), TiDAR dual-head (AR + Diffusion), RoPE embeddings, SwiGLU activation, INT8 quantization, 32 recursive layers |
| **Bat** | 🦇 | USB Shard Cryptography | 2-of-3 Shamir Secret Sharing, ChaCha20-Poly1305/AES-256-GCM encryption, 18kHz ultrasonic authentication, hardware stick attestation, active canary triggers, CTF-style recovery |
| **Beaver** | 🦫 | AI Firewall Generator | Natural language → rules (iptables/nftables/Suricata), LightweightNLU parsing, RuleIntent validation, Cynapse audit logging, Elephant signing integration |
| **Canary** | 🐤 | Distributed Deception | Stealth decoy generation (AWS creds, model weights), honeytoken tracking, distributed watcher mesh, behavioral fingerprinting, lockdown escalation |
| **Meerkat** | 🦔 | Vulnerability Scanner | Async software discovery, CVE matching, risk scoring, SQLite-backed vulnerability database, TUI-native output, zero external files |
| **Octopus** | 🐙 | Container Escape Tester | 10 escape vectors (difficulty 1-4 stars), automated defense validation, aiodocker integration, graceful degradation, cleanup automation |
| **Owl** | 🦉 | PII Redaction | Async Tesseract OCR, regex-based PII detection (email, phone, SSN, API keys), PIL image redaction, PDF support, masked output reporting |
| **Wolverine** | 🐺 | RAG Security Auditor | 12 parallel attack vectors, RAG poisoning tests, ChromaDB integration, Ollama LLM querying, refusal detection, Cynapse audit logging |

**Architecture Notes:**
- All neurons support Cynapse audit logging (NDJSON format)
- All neurons integrate with Hub for coordinated operations
- Lazy loading ensures missing dependencies don't crash system
- Each neuron has its own manifest JSON for discovery

---

## 🎮 TUI Controls Reference

The Synaptic Fortress uses vim-style navigation with context-aware controls across four zones.

### Global Hotkeys (Always Active)

| Key | Action | Description |
|-----|--------|-------------|
| `h` | Help | Show help overlay with all commands |
| `v` | Voice Toggle | Enable/disable 18kHz ultrasonic listening |
| `s` | Security Scan | Trigger system security scan |
| `L` | Lockdown | ⚠️ EMERGENCY: Enter lockdown mode (Shift+L) |
| `:q` or `Esc` | Back | Return to previous mode/close dialog |
| `Q` | Quit | Exit Synaptic Fortress (Shift+Q) |

### Navigation (Vim-Style)

| Key | Action |
|-----|--------|
| `j` or `↓` | Move cursor down in Sentinel Grid |
| `k` or `↑` | Move cursor up in Sentinel Grid |
| `Enter` | Activate selected neuron |
| `Space` | Toggle neuron state (dormant ↔ standby ↔ active) |
| `Tab` | Cycle between zones |
| `a` | Arm all dormant neurons |
| `d` | Disarm all active/standby neurons |

### Operations Bay (Chat/RAG)

| Key | Action |
|-----|--------|
| `i` | Enter input mode (start typing) |
| `Enter` | Submit message / spawn bee |
| `Backspace` | Delete last character |
| `Ctrl+F` | Feed document to HiveMind |

### Mode-Specific

**Neural Assembly Mode:**
- Shows USB shard combination visualization
- Displays synaptic pathways and signal propagation
- 3 shard slots (Bat-1, Bat-2, Bat-3)

**Pharmacode Mode:**
- Shows model loading/training progress
- 8-segment progress bars for TiDAR, RoPE, MoE
- Pharmacological metaphors (ampules, viscosity, pH)

**Breach Mode:**
- `Enter` - Isolate threat
- `s` - Audit system
- Cannot exit without action (requires intervention)

### Visual Indicators

**Status Symbols:**
- `●` - Active (running, processing)
- `▸` - Charged (armed, standby)
- `○` - Dormant (offline, sleeping)
- `✓` - Fused (complete, success)
- `∿` - Oscillating (training, adapting)
- `✗` - Breach (error, compromised)

**Zone Colors:**
- Deep Purple (#93): Headers, borders, authority
- Synapse Violet (#141): Charged pathways, standby states
- Active Magenta (#201): Active signals, live connections
- Cyan Electric (#51): Active data, ready states
- Complement Gold (#220): Success, completion
- Breach Red (#196): Critical intrusion

---

## 🐝 HiveMind Workflow System

HiveMind is Cynapse's workflow orchestration engine, inspired by n8n. It manages AI model training, document ingestion, and tool automation.

### Concepts

- **Bee**: A workflow definition (collection of nodes)
- **Instance**: A running execution of a bee (has unique ID)
- **Node**: Single unit of work (file reading, LLM generation, etc.)
- **Honeycomb**: SQLite storage + in-memory vector database
- **Trigger**: Event that starts a bee (user input, file upload, schedule)

### Using Workflows

**Initialize HiveMind:**
```bash
python cynapse/core/hivemind.py init
```

**Create a bee:**
```bash
python cynapse/core/hivemind.py bee create --name my_chat --type deployment
```

**Spawn (run) a bee:**
```bash
python cynapse/core/hivemind.py run --bee <bee_id>
```

**Quick commands:**
```bash
# Train on documents
python cynapse/core/hivemind.py train --docs ./documents/

# Chat with AI
python cynapse/core/hivemind.py chat --query "Hello"
```

**View status:**
```bash
python cynapse/core/hivemind.py bee list
python cynapse/core/hivemind.py status
```

### Pre-built Workflows

Located in `workflows/`:

1. **chat_assistant.yaml** - Conversational AI with context retrieval
   - User input → Vector search → LLM generation → Output
   
2. **document_ingestion.yaml** - RAG training pipeline
   - File reading → Text chunking → Embedding generation → Vector storage

Customize these or create new ones following the YAML schema. See HIVE.md for detailed workflow documentation.

### 🤖 Multi-Agent Orchestration (New in v2.2.0)

Elara now acts as a **Lead Agent** that can spawn specialized subagents.

**Concept**:
- **Lead Agent**: You talk to Elara. She plans the task.
- **Subagents**: Elara spawns a "Researcher" or "Coder" bee to do the work.
- **Artifacts**: Agents write results to `cynapse/data/agent_artifacts` and pass the path back to Elara.

**Usage**:
This happens automatically when using HiveMind for complex tasks, or you can trigger it via code:
```python
hive.orchestrate_agent("Research the history of cryptography and write a summary")
```

---

## 🛠️ Usage

### CLI Mode

Run specific tasks without the TUI interface:

```bash
# Initialize system infrastructure
python cynapse_entry.py --init

# Run health diagnostics
python cynapse_entry.py --health

# List discovered neurons
python cynapse_entry.py --cli

# Run self-tests
python cynapse_entry.py --test

# Show version
python cynapse_entry.py --version
```

### TUI Mode

Launch the Synaptic Fortress:

```bash
python cynapse_entry.py --tui
```

**Quick Start in TUI:**
1. Press `i` to enter input mode
2. Type: "Hello Cynapse"
3. Press `Enter` to spawn a bee
4. Watch for bee ID confirmation in chat
5. Press `Q` to exit

### Building from Source

Create a standalone executable:

```bash
python build_scripts/build_all.py
```

This will:
1. Build Rust components (Elephant signing library)
2. Build Go components (Rhino gateway)
3. Package Python code with PyInstaller
4. Output to `dist/Cynapse`

*Note: Requires Go 1.20+ and Rust/Cargo installed for full polyglot compilation.*

---

## ⚠️ Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'X'"

**Cause**: Missing Python dependencies

**Solution**:
```bash
# For core functionality
pip install -r requirements.txt

# For full features including AI
pip install -r requirements-full.txt
```

### Issue: "Cannot import SynapticFortress: name 'Enum' is not defined"

**Cause**: Missing enum import (fixed in v2.0.0)

**Solution**: Ensure you're using the latest version. If modifying code, add:
```python
from enum import Enum, auto
```

### Issue: Chat messages don't spawn bees

**Cause**: Ollama not running or not installed

**Solution**:
1. Install Ollama: https://ollama.ai
2. Start Ollama service: `ollama serve`
3. Pull a model: `ollama pull llama3.2`
4. Verify in `hivemind.yaml`: `endpoint: http://localhost:11434`

### Issue: "Directory not found" errors

**Cause**: System not initialized

**Solution**:
```bash
python cynapse_entry.py --init
```

### Issue: Neuron discovery returns empty list

**Cause**: Running from wrong directory

**Solution**: Ensure you're in the project root (where `cynapse_entry.py` is located)

### Issue: TUI displays but doesn't respond to input

**Cause**: Terminal not in raw mode or encoding issues

**Solution**:
- Use a terminal that supports ANSI escape codes (iTerm2, GNOME Terminal, Windows Terminal)
- Ensure UTF-8 locale: `export LANG=en_US.UTF-8`
- Try running with `python -u cynapse_entry.py --tui` for unbuffered output

### Issue: Elara model not found

**Cause**: 3B model weights not downloaded

**Solution**: The Elara model architecture is included, but weights must be downloaded separately:
1. Download from releases (when available)
2. Place in `cynapse/data/models/elara.gguf`
3. Or use Ollama as fallback for chat features

### Issue: Permission denied on Linux

**Cause**: File permissions or missing execute rights

**Solution**:
```bash
chmod +x cynapse_entry.py
chmod -R 755 cynapse/
```

### Issue: Windows terminal colors not showing

**Cause**: Windows CMD doesn't support ANSI colors by default

**Solution**: Use Windows Terminal or PowerShell with ANSI support, or run in WSL2.

---

## 📂 Architecture

The project is structured as a unified Python package:

```
cynapse/
├── core/           # Central logic (Hub, HiveMind)
├── tui/            # User interface (Synaptic Fortress)
├── neurons/        # Security tools (8 neurons)
└── utils/          # Shared utilities (security, config)

data/               # Runtime data (models, documents, logs)
workflows/          # HiveMind YAML workflow definitions
logs/               # Audit trails
```

See [architecture.md](architecture.md) for detailed technical documentation.

---

## 📝 Documentation

- **README.md** (this file) - Quick start and usage guide
- [architecture.md](architecture.md) - Technical architecture and component details
- [fix.md](fix.md) - Latest optimization and fix guide
- [Changelog.md](Changelog.md) - Version history and migration guide

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes with tests
4. Run health check: `python cynapse_entry.py --health`
5. Submit pull request

### Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Add docstrings for public APIs
- Update documentation for user-facing changes

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **Alejandro Eduardo Garcia Romero** - Creator and lead developer
- **Cynapse Community** - Contributors and testers
- **Open Source Libraries** - PyTorch, Transformers, ChromaDB, Ollama, and many more

---

## 🔗 Links

- **Repository**: https://github.com/Alartist40/Cynapse
- **Issues**: https://github.com/Alartist40/Cynapse/issues
- **Releases**: https://github.com/Alartist40/Cynapse/releases
- **Documentation**: See `docs/` directory (when available)

---

**Built with passion for privacy and security.** 🔒
