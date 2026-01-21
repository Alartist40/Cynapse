# Changelog

All notable changes to Cynapse Ghost Shell Hub are documented in this file.

## [1.0.0] - 2026-01-09

### 🎉 Initial Release

The first complete release of Cynapse Ghost Shell Hub, integrating 12 security tools into a unified voice-controlled ecosystem, plus the **HiveMind** Personal AI Ecosystem.

---

### Core Systems Implemented

#### Cynapse Hub Orchestrator (`cynapse.py`)
- **Neuron Discovery System**: Auto-discovers all neurons in `neurons/` directory
- **Manifest Loading**: Parses `manifest.json` for each neuron
- **Signature Verification**: Verifies binary signatures using Elephant Sign
- **Command Execution Engine**: Runs neurons with proper subprocess handling
- **Audit Logging**: NDJSON format logging to `temp/logs/audit.ndjson`
- **Voice Control Integration**: Background thread for whistle detection
- **CLI Interface**: Interactive command-line with help, list, status commands

#### Ghost Shell System (`neurons/bat_ghost/`)
- **Whistle Detector** (`whistle_detector.py`):
  - 18 kHz ultrasonic frequency detection
  - FFT-based frequency analysis using NumPy
  - Configurable threshold and tolerance
  - Consecutive detection window to reduce false positives
  - Test tone generation capability

- **Shard Assembler** (`assemble.py`):
  - SHA256 hash verification for all shards
  - XOR encryption with user assembly key
  - RAM-only assembly in temp directory
  - Model splitting utility for creating shards
  - Automatic cleanup on exit

- **Bat Manifests** (bat1/, bat2/, bat3/):
  - Bat-1: Whisper Wake (ultrasonic detector)
  - Bat-2: Canary Shard (honeypot functionality)
  - Bat-3: CTF Shard (red-team challenge with flag)

---

### 12 Neurons Integrated

#### 1. Rhino Gateway (`neurons/rhino_gateway/`)
- Zero-Trust LLM Gateway
- Secure API proxy with rate limiting
- Access control and request validation
- Source: Project 1 - Zero-Trust LLM Gateway

#### 2. Meerkat Scanner (`neurons/meerkat_scanner/`)
- Air-Gap Update Scanner
- Offline CVE vulnerability scanning
- Local database for air-gapped environments
- Source: Project 2 - Air-Gap Update Scanner (MVP)

#### 3. Canary Token (`neurons/canary_token/`)
- AI-powered honeypot generator
- Creates convincing decoy files
- Triggers alerts on unauthorized access
- Source: Project 3 - AI Canarytoken

#### 4. Wolverine RedTeam (`neurons/wolverine_redteam/`)
- Local RAG for security testing
- Offline retrieval-augmented generation
- Attack scenario generation
- Source: Project 4 - Local RAG Red-Team

#### 5. TinyML Anomaly (`neurons/tinyml_anomaly/`)
- Edge device anomaly detection
- Lightweight ML models for IoT
- TensorFlow Lite export support
- Source: Project 5 - TinyML Anomaly Guard

#### 6. Owl OCR (`neurons/owl_ocr/`)
- One-file Privacy OCR
- Document redaction with Tesseract
- PII detection and removal
- Source: Project 6 - One-file Privacy OCR

#### 7. Elephant Sign (`neurons/elephant_sign/`)
- Signed-Model Distribution
- ED25519 cryptographic signing
- Model and binary verification
- Source: Project 7 - Signed-Model Distribution

#### 8. Parrot Wallet (`neurons/parrot_wallet/`)
- Off-Grid Voice Wallet
- BIP39 mnemonic support
- Voice command cryptocurrency operations
- Source: Project 8 - Off-Grid Voice Wallet

#### 9. Octopus CTF (`neurons/octopus_ctf/`)
- Container Escape Trainer
- Docker-based security challenges
- Progressive difficulty levels
- Source: Project 9 - Container Escape Trainer

#### 10. Beaver Miner (`neurons/beaver_miner/`)
- AI Firewall Rule-Miner
- Traffic log analysis
- Automated rule generation
- Source: Project 10 - AI Firewall Rule-Miner

#### 11. DevAle (`neurons/devale/`)
- AI Development Assistant
- Local LLM integration
- Code generation and analysis
- Source: DevAle Official

#### 12. Elara (`neurons/elara/`)
- Custom 2.8B Parameter AI Model
- DeepSeek-inspired MoE architecture
- TiDAR hybrid inference
- Recursive reasoning blocks (TRM)

---

### AI Model Enhancements (Elara)

Based on `improvement.md` recommendations:

#### RoPE (Rotary Positional Embeddings)
- Added `precompute_freqs_cis()` function
- Added `reshape_for_broadcast()` helper
- Added `apply_rotary_emb()` for Q/K rotation
- Better long-context handling than vanilla sinusoidal

#### SwiGLU Activation
- Replaced GELU with SwiGLU in MLP class
- Three projections: gate, up, down
- Formula: `down(SiLU(gate(x)) * up(x))`
- Matches modern LLMs (LLaMA, Mistral)

#### Model Architecture
- **Parameters**: ~2.8B (optimized for mobile)
- **Layers**: 32 transformer blocks
- **Heads**: 16 attention heads
- **Embedding Dim**: 1280
- **MoE**: 8 experts + 1 shared expert, top-k=2
- **Recursion Depth**: 2 iterations per block
- **TiDAR**: Diffusion head for drafting

---

### Configuration System

#### `config/config.ini.example`
- General settings (hub name, version, log level)
- Voice settings (frequency, threshold, sample rate)
- Assembly settings (temp dir, encryption)
- Logging settings (directory, max size)
- Neuron settings (discovery dir, verification)

#### `config/user_keys.json.example`
- Assembly key for shard encryption
- API keys for optional cloud services
- Model paths for Whisper and Elara

---

### Build System

#### `build/build_all.sh`
- Unix/Linux/macOS build script
- Python dependency installation
- Test suite execution
- Neuron compilation (Go, Python)
- Binary signing

#### `build/build_all.ps1`
- Windows PowerShell build script
- Same functionality as Unix script
- Windows-specific path handling

---

### Test Suite (`tests/test_hub.py`)

- **TestNeuronDiscovery**: Verifies all 12 neurons present
- **TestManifestValidation**: Validates JSON manifests
- **TestConfigFiles**: Checks config templates
- **TestDirectoryStructure**: Verifies folder layout
- **TestCynapseHub**: Tests hub functionality
- **TestGhostShell**: Tests bat system components
- **TestElaraModel**: Tests model file presence

---

### Data Directories Created

- `data/training/`: For user training documents
- `data/storage/model/`: For AI model data
- `data/storage/voice/`: For voice recognizer data

---

### Files Created

| File | Purpose |
|------|---------|
| `cynapse.py` | Main orchestrator (~400 lines) |
| `config/config.ini.example` | Configuration template |
| `config/user_keys.json.example` | API keys template |
| `neurons/bat_ghost/whistle_detector.py` | 18 kHz detection |
| `neurons/bat_ghost/assemble.py` | Shard assembly |
| `neurons/*/manifest.json` | Neuron manifests (12 files) |
| `tests/test_hub.py` | Test suite |
| `build/build_all.sh` | Unix build script |
| `build/build_all.ps1` | Windows build script |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Git ignore rules |
| `README.md` | Full documentation |
| `CHANGELOG.md` | This file |
| `architecture.md` | System architecture |

---

### Technical Specifications

- **Python**: 3.8+ required
- **Audio**: PyAudio with PortAudio
- **ML Framework**: PyTorch 2.0+
- **Cryptography**: Ed25519 via cryptography library
- **Platforms**: Windows, macOS, Linux

---

### Security Features

- Signature verification for all neurons
- Encrypted shard storage
- RAM-only model assembly
- Audit logging with timestamps
- No cloud dependencies (fully offline capable)

---

## Future Roadmap

### v2.0 (Planned)
- Shamir 2-of-3 backup for shards
- Voice profile recognition
- Plugin marketplace for community neurons

### v3.0 (Planned)
- Hardware wallet integration (YubiKey form factor)
- Encrypted IPFS backup
- Multi-language voice support (es, ja, en)
