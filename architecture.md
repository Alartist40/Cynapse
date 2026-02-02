# Cynapse Architecture

This document maps every component in the Cynapse Ghost Shell Hub system, their locations, purposes, and relationships.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CYNAPSE HUB (32 GB USB)                       │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  HUB_TUI.PY │  │  CYNAPSE.PY │◄─│   CONFIG    │  │   LOGGER    │  │
│  │ Reactive UI │  │ Orchestrator│  │  Settings   │  │   NDJSON    │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └─────────────┘  │
│         └──────┬─────────┘                                           │
│                │                                                     │
│         ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    NEURONS (12 Tools)                        │    │
│  ├─────────┬─────────┬─────────┬─────────┬─────────┬───────────┤    │
│  │ Rhino   │ Meerkat │ Canary  │Wolverine│ TinyML  │    Owl    │    │
│  │ Gateway │ Scanner │ Token   │ RedTeam │ Anomaly │    OCR    │    │
│  ├─────────┼─────────┼─────────┼─────────┼─────────┼───────────┤    │
│  │Elephant │ Parrot  │ Octopus │ Beaver  │ DevAle  │   Elara   │    │
│  │  Sign   │ Wallet  │   CTF   │  Miner  │         │   (AI)    │    │
│  └─────────┴─────────┴─────────┴─────────┴─────────┴───────────┘    │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    GHOST SHELL (bat_ghost)                   │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │    │
│  │  │  BAT-1  │  │  BAT-2  │  │  BAT-3  │  │    ASSEMBLER    │ │    │
│  │  │ Shard 1 │  │ Shard 2 │  │ Shard 3 │  │   + Detector    │ │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────┘    │
│  └─────────────────────────────────────────────────────────────┘    │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                     HIVEMIND (Personal AI)                   │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │    │
│  │  │  QUEEN  │  │ DRONES  │  │ WORKERS │  │   HONEYCOMB     │ │    │
│  │  │   3B    │  │ Ollama  │  │ AirLLM  │  │   Vector DB     │ │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure Map

```
cynapse/
├── cynapse.py                    # [CORE] Main orchestrator
├── hub_tui.py                    # [UI] Reactive Textual TUI
├── hivemind.py                   # [CORE] HiveMind CLI
├── requirements.txt              # [CONFIG] Python dependencies
├── .gitignore                    # [CONFIG] Git ignore rules
├── README.md                     # [DOCS] Project documentation
├── CHANGELOG.md                  # [DOCS] Version history
├── architecture.md               # [DOCS] This file
│
├── config/                       # [CONFIG] Configuration directory
│   ├── config.ini.example        # Hub settings template
│   └── user_keys.json.example    # API keys template
│
├── hivemind/                     # [HIVEMIND] AI Ecosystem
│   ├── queen/                    # Queen Model logic
│   ├── drones/                   # Specialist routers
│   ├── interact/                 # Chat interface
│   └── learn/                    # Adaptation logic
│
├── neurons/                      # [NEURONS] Security tools
│   ├── __template__/             # Template for new neurons
│   │   └── manifest.json
│   │
│   ├── bat_ghost/                # [GHOST] Distributed AI system
│   │   ├── manifest.json         # Neuron metadata
│   │   ├── whistle_detector.py   # 18 kHz detection
│   │   ├── assemble.py           # Shard assembly
│   │   ├── bat1/                 # Bat-1 shard carrier
│   │   │   ├── manifest.json
│   │   │   └── README.md
│   │   ├── bat2/                 # Bat-2 shard carrier
│   │   │   └── manifest.json
│   │   └── bat3/                 # Bat-3 shard carrier
│   │       ├── manifest.json
│   │       └── flag10.txt        # CTF flag
│   │
│   ├── rhino_gateway/            # [1] Zero-Trust LLM Gateway
│   │   ├── manifest.json
│   │   ├── main.go               # Go source
│   │   ├── README.md
│   │   └── CHANGELOG.md
│   │
│   ├── meerkat_scanner/          # [2] Air-Gap CVE Scanner
│   │   ├── manifest.json
│   │   ├── scan.py               # Scanner script
│   │   ├── db_build.py           # Database builder
│   │   └── README.md
│   │
│   ├── canary_token/             # [3] AI Honeypot Generator
│   │   ├── manifest.json
│   │   ├── canary.py             # Token generator
│   │   ├── bait_gen.py           # AI bait creator
│   │   └── README.md
│   │
│   ├── wolverine_redteam/        # [4] Local RAG Security
│   │   ├── manifest.json
│   │   ├── redteam.py            # RAG engine
│   │   └── README.md
│   │
│   ├── tinyml_anomaly/           # [5] Edge Anomaly Detection
│   │   ├── manifest.json
│   │   ├── main.py               # Detection engine
│   │   └── README.md
│   │
│   ├── owl_ocr/                  # [6] Privacy OCR Redaction
│   │   ├── manifest.json
│   │   ├── redact.py             # Redaction script
│   │   └── README.md
│   │
│   ├── elephant_sign/            # [7] Cryptographic Signing
│   │   ├── manifest.json
│   │   ├── sign.py               # Signing tool
│   │   └── verify.py             # Verification tool
│   │
│   ├── parrot_wallet/            # [8] Voice Crypto Wallet
│   │   ├── manifest.json
│   │   ├── wallet.py             # Wallet operations
│   │   └── README.md
│   │
│   ├── octopus_ctf/              # [9] Container Escape CTF
│   │   ├── manifest.json
│   │   ├── main.py               # CTF controller
│   │   ├── Dockerfile
│   │   └── rootfs/               # Challenge filesystem
│   │
│   ├── beaver_miner/             # [10] Firewall Rule AI
│   │   ├── manifest.json
│   │   ├── rule_miner.py         # Main script
│   │   ├── rule_generator.py     # Rule generation
│   │   └── templates/            # Rule templates
│   │
│   ├── devale/                   # [11] Dev Assistant
│   │   ├── manifest.json
│   │   ├── main.py               # Entry point
│   │   ├── devale.py             # Core logic
│   │   └── gui/                  # UI components
│   │
│   └── elara/                    # [12] Custom AI Model
│       ├── manifest.json
│       ├── model.py              # Model architecture
│       ├── sample.py             # Inference script
│       ├── train.py              # Training script
│       ├── verify.py             # Architecture verify
│       ├── bench.py              # Benchmarks
│       └── config/               # Model configs
│
├── temp/                         # [TEMP] Ephemeral storage
│   ├── assembled.gguf            # Reconstructed model
│   ├── voice_query.wav           # Last voice input
│   └── logs/
│       └── audit.ndjson          # Audit trail
│
├── data/                         # [DATA] Persistent storage
│   ├── training/                 # Training documents
│   └── storage/
│       ├── model/                # Model data
│       └── voice/                # Voice data
│
├── assets/                       # [ASSETS] Visual resources
│   ├── logo_deer.svg             # Cynapse logo
│   └── icons/                    # Animal icons
│
├── build/                        # [BUILD] Build scripts
│   ├── build_all.sh              # Unix build
│   ├── build_all.ps1             # Windows build
│   └── portable/                 # USB-ready distribution
│       ├── python/               # Embedded Python
│       ├── cynapse/              # Application copy
│       ├── run_cynapse.bat       # Windows launcher
│       └── run_hivemind.bat      # HiveMind launcher
│
└── tests/                        # [TEST] (empty - tests removed)
```

---

## Component Details

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **Orchestrator** | `cynapse.py` | Central hub that discovers, verifies, and executes neurons. |
| **Reactive TUI** | `hub_tui.py` | Modern, stable terminal interface using Textual. Optional. |
| **Config Loader** | `cynapse.py: _load_config()` | Reads INI configuration. |
| **Neuron Discovery** | `cynapse.py: _discover_neurons()` | Scans neurons/ directory |
| **Audit Logger** | `cynapse.py: AuditLogger` | NDJSON event logging |
| **Voice Listener** | `cynapse.py: _voice_loop()` | Background whistle detection |

### Neuron Class Hierarchy

```python
CynapseHub
  ├── neurons: Dict[str, Neuron]  # All loaded neurons
  ├── logger: AuditLogger         # Event logging
  └── config: ConfigParser        # Settings

Neuron
  ├── path: Path                  # Filesystem location
  ├── manifest: NeuronManifest    # Metadata
  ├── binary: Path                # Entry point
  └── signature: Path             # Signature file

NeuronManifest (dataclass)
  ├── name: str
  ├── version: str
  ├── description: str
  ├── author: str
  ├── animal: str                 # Emoji icon
  ├── platform: List[str]
  ├── entry_point: str
  ├── requires_signature: bool
  ├── dependencies: List[str]
  └── commands: Dict[str, str]
```

---

### Ghost Shell Components

| Component | File | Purpose |
|-----------|------|---------|
| **Whistle Detector** | `bat_ghost/whistle_detector.py` | Detects 18 kHz ultrasonic tone |
| **Shard Assembler** | `bat_ghost/assemble.py` | Combines encrypted shards |
| **Bat-1 Manifest** | `bat_ghost/bat1/manifest.json` | Shard 1 metadata |
| **Bat-2 Manifest** | `bat_ghost/bat2/manifest.json` | Shard 2 with canary |
| **Bat-3 Manifest** | `bat_ghost/bat3/manifest.json` | Shard 3 with CTF flag |

### Whistle Detection Flow

```
Audio Input → PyAudio → FFT Analysis → Frequency Matching → Detection
                ↓
           18 kHz Band → Energy Check → Threshold → Consecutive Count
                                                          ↓
                                              WHISTLE_DETECTED ──→ Assemble Shards
```

### Shard Assembly Flow

```
Bat-1           Bat-2           Bat-3
  │               │               │
  └─── shard1 ────┴─── shard2 ───┴─── shard3 ───┐
                                                │
              ┌────────────────────────────────┘
              ▼
     ┌─────────────────┐
     │ Verify SHA256   │ ← Check manifest hashes
     └────────┬────────┘
              ▼
     ┌─────────────────┐
     │ Decrypt (XOR)   │ ← User assembly key
     └────────┬────────┘
              ▼
     ┌─────────────────┐
     │ Concatenate     │ ← RAM only
     └────────┬────────┘
              ▼
     ┌─────────────────┐
     │ assembled.gguf  │ ← temp/ directory
     └─────────────────┘
```

---

### Elara AI Model Architecture

| Layer | Purpose |
|-------|---------|
| **Embedding** | Token + Position embeddings |
| **RoPE** | Rotary Position Embeddings |
| **Transformer Blocks** (×32) | Recursive blocks with MoE |
| **LayerNorm** | Pre-normalization |
| **CausalSelfAttention** | Multi-head attention |
| **MLP/MoE** | SwiGLU activation, sparse experts |
| **LM Head** | Autoregressive output |
| **Diffusion Head** | TiDAR drafting |

### Model Specifications

```python
GPTConfig:
  block_size: 1024        # Context length
  vocab_size: 50304       # Vocabulary
  n_layer: 32             # Transformer layers
  n_head: 16              # Attention heads
  n_embd: 1280            # Embedding dimension
  num_experts: 8          # MoE experts
  num_shared_experts: 1   # Always-active expert
  moe_top_k: 2            # Experts per token
  recursion_depth: 2      # TRM iterations
  use_diffusion_head: True # TiDAR enabled
```

---

## Interfaces

### 3.1 Hybrid Architecture
Cynapse implements a **Hybrid Presentation Layer**. It detects terminal capabilities and the presence of dependencies to provide the best possible experience while maintaining absolute portability.

### 3.2 Modern TUI (`hub_tui.py`)
- Reactive dashboard using Textual.
- Persistent status monitoring and animated scans.
- Requires: `pip install textual`.

### 3.3 Cynapse CLI (`cynapse.py`)
- Standard input/output loop for minimal environments.
- Supports direct neuron command routing.
- Zero external dependencies required for core functionality.

---

## Data Flow Diagrams

### Neuron Execution Flow

```
User Command
      │
      ▼
┌─────────────────┐
│   CynapseHub    │
│   run_neuron()  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Find Neuron    │────▶│ Verify Signature│
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  Log: start     │     │   Signature OK? │
└────────┬────────┘     └────────┬────────┘
         │                       │ Yes
         ▼                       ▼
┌─────────────────────────────────────────┐
│           Execute Subprocess            │
│   (python/exe/sh based on extension)    │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────┐     ┌─────────────────┐
│  Log: complete  │     │  Return Result  │
└─────────────────┘     └─────────────────┘
```

### Audit Log Format

```json
{
  "timestamp": 1736366400.123,
  "iso_time": "2026-01-09T01:00:00Z",
  "event": "neuron_execute_start",
  "data": {
    "name": "meerkat_scanner",
    "args": ["--scan", "192.168.1.0/24"]
  }
}
```

---

## Integration Points

### Inter-Neuron Communication

| From | To | Purpose |
|------|----|---------|
| Cynapse Hub | All Neurons | Execution, verification |
| bat_ghost | Elara | Model assembly |
| elephant_sign | All Binaries | Signature verification |
| parrot_wallet | TTS Engine | Voice output |
| meerkat_scanner | beaver_miner | CVE → Firewall rules |

### External Dependencies

| Component | Dependency | Purpose |
|-----------|------------|---------|
| Whistle Detector | PyAudio + PortAudio | Audio capture |
| Elara Model | PyTorch 2.0+ | Neural network |
| Elephant Sign | cryptography | Ed25519 signing |
| Owl OCR | Tesseract | OCR engine |
| Octopus CTF | Docker | Container runtime |

---

## Security Architecture

### Authentication Layers

1. **Physical**: USB sticks required for shards
2. **Acoustic**: 18 kHz whistle authentication
3. **Cryptographic**: SHA256 + XOR encryption
4. **Signature**: Ed25519 binary verification

### Threat Mitigations

| Threat | Mitigation |
|--------|------------|
| Shard theft | Encryption + 3-shard requirement |
| Fake neuron | Signature verification |
| Log tampering | NDJSON append-only |
| Model extraction | RAM-only assembly |
| Replay attack | Timestamps in logs |

---

## File Format Reference

### manifest.json Schema

```json
{
  "name": "string (required)",
  "version": "string (required)",
  "description": "string (required)",
  "author": "string",
  "animal": "emoji string",
  "platform": ["win", "linux", "mac"],
  "entry_point": "string (required)",
  "requires_signature": "boolean",
  "dependencies": ["string"],
  "commands": {
    "command_name": "description"
  }
}
```

### config.ini Schema

```ini
[general]
hub_name = string
version = string
log_level = DEBUG|INFO|WARNING|ERROR

[voice]
whistle_frequency = integer (Hz)
whistle_threshold = integer
sample_rate = integer

[assembly]
temp_dir = path
enable_encryption = boolean

[neurons]
neurons_dir = path
verify_signatures = boolean
timeout_seconds = integer
```

---

## Performance Characteristics

| Operation | Typical Time |
|-----------|-------------|
| Hub initialization | < 500ms |
| Neuron discovery | ~10ms per neuron |
| Whistle detection | ~100ms response |
| Shard assembly | 2-5 seconds |
| Elara inference | 50-200ms per token |

---

## Extension Guide

### Adding a New Neuron

1. Copy `neurons/__template__/` to `neurons/your_neuron/`
2. Edit `manifest.json` with your metadata
3. Create your entry point script
4. Add to neurons directory
5. Hub auto-discovers on next run

### Creating Custom Shards

```bash
cd neurons/bat_ghost
python assemble.py --split /path/to/model.gguf
# Creates shard1.gguf, shard2.gguf, shard3.gguf
```

---

*Last updated: 2026-01-21*
