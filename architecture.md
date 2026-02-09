# Cynapse Architecture Reference

**Version**: 2.1.0-fix
**Date**: 2026-02-09
**Status**: Production Ready - Optimized for Low-End Hardware

---

## 1. Executive Summary

Cynapse has evolved from a loose collection of scripts into a fully integrated, executable security ecosystem. This architecture ensures modularity, easier distribution, and secure separation of concerns while maintaining the bio-digital aesthetic.

### Key Achievements in v2.0.0

1. **System Integration**: TUI now connects to HiveMind, chat spawns actual workflow bees
2. **Infrastructure**: Complete data directory structure with configuration management
3. **Module System**: Lazy loading prevents dependency cascade failures
4. **Health Monitoring**: Comprehensive diagnostics system for troubleshooting
5. **Polyglot Support**: Rust (Elephant) and Go (Rhino) components properly integrated

### The Cynapse Ecosystem

The system is now a **Unified Security Hub** that manages:

1. **Core Intelligence**: The `hub` orchestrator and `hivemind` AI automation engine
2. **Visual Interface**: The `tui` (Synaptic Fortress) for user interaction across 4 zones
3. **Neural Defense**: 8 specialized `neurons` (polyglot tools in Python, Go, and Rust)
4. **Data Layer**: SQLite + in-memory storage with configuration management

---

## 2. Directory Structure

### Complete File Tree

```
Cynapse/
├── cynapse_entry.py              # [ENTRY] Main executable with argparse commands
├── cynapse.spec                  # [BUILD] PyInstaller packaging configuration
├── requirements.txt              # [DEPS] Core Python dependencies
├── requirements-full.txt         # [DEPS] Complete stack with AI/ML
├── hivemind.yaml                 # [CONFIG] Workflow engine configuration
│
├── build_scripts/                # [BUILD] Build automation
│   └── build_all.py              # Master build script for polyglot components
│
├── cynapse/                      # [PACKAGE] Main application package
│   ├── __init__.py               # Package-level exports with version info
│   │
│   ├── core/                     # [CORE] Business logic
│   │   ├── __init__.py           # Core class exports
│   │   ├── hub.py                # CynapseHub - orchestrator & neuron discovery
│   │   └── hivemind.py           # HiveMind - AI workflow engine
│   │
│   ├── tui/                      # [UI] Synaptic Fortress Interface
│   │   ├── __init__.py           # TUI exports
│   │   ├── main.py               # Main TUI loop with 4-zone layout
│   │   └── main.py.bak           # Backup of original before integration
│   │
│   ├── neurons/                  # [TOOLS] Security neurons
│   │   ├── __init__.py           # All 8 neurons with lazy loading
│   │   ├── bat.py                # Ghost Shell - USB shard cryptography
│   │   ├── beaver.py             # Beaver Miner - AI firewall generator
│   │   ├── canary.py             # Canary Token - deception system
│   │   ├── elara.py              # Elara - 3B AI model
│   │   ├── meerkat.py            # Meerkat Scanner - CVE detection
│   │   ├── octopus.py            # Octopus - container escape tester
│   │   ├── owl.py                # Owl - PII OCR redaction
│   │   ├── wolverine.py          # Wolverine - RAG security auditor
│   │   ├── rhino.go              # [GO] Zero-trust API gateway
│   │   │
│   │   ├── elephant/             # [RUST] Cryptographic signing
│   │   │   ├── __init__.py
│   │   │   ├── elephant.rs       # Core Rust signing logic
│   │   │   ├── tui.py            # Python/TUI integration wrapper
│   │   │   └── Cargo.toml        # Rust build manifest (NEW in v2.0.0)
│   │   │
│   │   └── *_manifest.json       # Neuron metadata (4 files)
│   │
│   └── utils/                    # [SHARED] Helper libraries
│       ├── __init__.py           # Utility exports
│       ├── security.py           # Input validation & sanitization
│       ├── config.py             # [NEW] Centralized configuration handling
│       └── audit.py              # [NEW] Standardized neuron audit logging
│
├── cynapse/data/                 # [DATA] Runtime data (created by --init)
│   ├── config.ini                # Hub configuration
│   ├── storage/                  # Persistent state storage
│   ├── documents/                # RAG document repository
│   ├── models/                   # AI model storage
│   └── temp/                     # Ephemeral workspace
│
├── workflows/                    # [WORKFLOWS] HiveMind definitions
│   ├── chat_assistant.yaml       # Conversational AI workflow
│   └── document_ingestion.yaml   # RAG training workflow
│
├── logs/                         # [LOGS] Audit trails
│   └── audit.ndjson              # Append-only event log
│
└── Documentation/                # [DOCS] Project documentation
    ├── README.md                 # Quick start and usage
    ├── architecture.md           # This file - technical details
    ├── Changelog.md              # Version history
    ├── HIVE.md                   # HiveMind workflow engine
    ├── TUI.md                    # TUI detailed reference
    ├── neurons.md                # Individual neuron docs
    ├── AI.md                     # Elara model architecture
    └── PACKAGE.md                # Packaging and distribution
```

---

## 3. Component Integration

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CYNAPSE ECOSYSTEM v2.0.0                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         USER INTERFACE LAYER                          │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │              Synaptic Fortress TUI (4 Zones)                   │  │   │
│  │  │  ┌─────────────┐  ┌─────────────────┐  ┌──────────────────┐  │  │   │
│  │  │  │  Perimeter  │  │ Activation      │  │   Operations     │  │  │   │
│  │  │  │  (Status)   │  │ Chamber         │  │   Bay (Chat)     │  │  │   │
│  │  │  └──────┬──────┘  │ (Visual)        │  │        ↑         │  │  │   │
│  │  │         │         └─────────────────┘  │   User Input ────┼──┘  │   │
│  │  │  ┌──────┴──────┐                       └──────────────────┘     │   │
│  │  │  │Sentinel Grid│                                              │   │
│  │  │  │(Neurons)    │                                              │   │
│  │  │  └─────────────┘                                              │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  │                              │                                      │   │
│  │                              ▼                                      │   │
│  │              InputHandler._handle_operations()                      │   │
│  │                              │                                      │   │
│  └──────────────────────────────┼──────────────────────────────────────┘   │
│                                 │                                          │
│  ┌──────────────────────────────┼──────────────────────────────────────┐   │
│  │                         CORE LOGIC LAYER                            │   │
│  │                              │                                      │   │
│  │                              ▼                                      │   │
│  │              ┌───────────────────────────────┐                       │   │
│  │              │    CynapseHub               │                       │   │
│  │              │  ┌─────────────────────────┐│                       │   │
│  │              │  │ - Neuron discovery      ││                       │   │
│  │              │  │ - Manifest parsing      ││                       │   │
│  │              │  │ - Configuration mgmt    ││                       │   │
│  │              │  │ - Execution dispatch    ││                       │   │
│  │              │  └─────────────────────────┘│                       │   │
│  │              │              │              │                       │   │
│  │              └──────────────┼──────────────┘                       │   │
│  │                             │                                      │   │
│  │              ┌──────────────┴──────────────┐                       │   │
│  │              ▼                              ▼                       │   │
│  │    ┌───────────────────┐      ┌─────────────────────┐               │   │
│  │    │   HiveMind        │      │   Config System     │               │   │
│  │    │ ┌───────────────┐ │      │ ┌─────────────────┐ │               │   │
│  │    │ │ - Workflow    │ │      │ │ - config.ini    │ │               │   │
│  │    │ │   engine      │ │      │ │ - hivemind.yaml │ │               │   │
│  │    │ │ - Bee spawning│ │      │ └─────────────────┘ │               │   │
│  │    │ │ - Node exec   │ │      └─────────────────────┘               │   │
│  │    │ └───────────────┘ │                                            │   │
│  │    └──────────┬────────┘                                            │   │
│  │               │                                                     │   │
│  │               ▼                                                     │   │
│  │    ┌───────────────────┐                                            │   │
│  │    │ deploy_chat()   │                                            │   │
│  │    │ (Chat query →   │                                            │   │
│  │    │  Bee instance)  │                                            │   │
│  │    └──────────┬──────┘                                            │   │
│  └───────────────┼────────────────────────────────────────────────────┘   │
│                  │                                                        │
│  ┌───────────────┼────────────────────────────────────────────────────┐   │
│  │               ▼             NEURAL LAYER (8 Neurons)              │   │
│  │  ┌──────────────────────────────────────────────────────────┐    │   │
│  │  │  Python Neurons      │  Polyglot Neurons                 │    │   │
│  │  │  ┌────┬────┬────┐   │  ┌──────────┬──────────┐          │    │   │
│  │  │  │Bat │Beav│Can │   │  │Elephant  │ Rhino    │          │    │   │
│  │  │  │Meer│Octo│Owl │   │  │ [Rust]   │ [Go]     │          │    │   │
│  │  │  │Wolv│Elar│    │   │  │Signing   │ Gateway  │          │    │   │
│  │  │  └────┴────┴────┘   │  └──────────┴──────────┘          │    │   │
│  │  └──────────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    DATA & STORAGE LAYER                            │   │
│  │  ┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │   │
│  │  │  SQLite        │  │  In-Memory       │  │  Filesystem      │   │   │
│  │  │  (hivemind.db) │  │  (Vector DB)     │  │  (NDJSON Logs)   │   │   │
│  │  └────────────────┘  └──────────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow

### User Input → Bee Spawning Flow

```
User types in TUI Operations Bay
        │
        ▼
┌────────────────────────────────────────┐
│ InputHandler._handle_operations()     │
│ - Captures 'i' key press              │
│ - Reads input buffer                  │
│ - On Enter (\r), spawns bee           │
└──────────┬─────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────┐
│ SynapticFortress._get_hivemind()      │
│ - Lazy initialization                 │
│ - Loads hivemind.yaml config          │
│ - Returns HiveMind instance           │
└──────────┬─────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────┐
│ HiveMind.deploy_chat(query)           │
│ - Creates deployment bee            │
│ - Adds LLM node with query            │
│ - Adds output node                   │
│ - Spawns instance                    │
└──────────┬─────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────┐
│ HiveMind.spawn_bee(bee_id)            │
│ - Creates BeeInstance                  │
│ - Starts thread (Thread Safe Lock)     │
│ - Returns instance_id                 │
└──────────┬─────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────┐
│ Bee execution thread                  │
│ - Lazy Load: numpy/torch              │
│ - Executes LLM node                   │
│   - Try llama-cpp (local model)       │
│   - Fallback to Ollama               │
│ - Captures output                     │
│ - Executes output node                │
│ - Updates status in DB                │
└──────────┬─────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────┐
│ TUI updates with result              │
│ Shows: "🐝 Bee spawned: {id[:8]}..."  │
└────────────────────────────────────────┘
```

### Neuron Discovery Flow

```
CynapseHub initialization
        │
        ▼
┌────────────────────────────────────────┐
│ _discover_neurons()                   │
│ - Scan cynapse/neurons/ directory     │
│ - Look for manifest.json files        │
│ - Check .py, .go files as fallback    │
└──────────┬─────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────┐
│ Parse manifest files                  │
│ - name, version, description          │
│ - entry_point                         │
│ - dependencies                        │
│ - commands                            │
└──────────┬─────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────┐
│ Store in self.neurons dict            │
│ Key: neuron name                       │
│ Value: metadata + path                │
└────────────────────────────────────────┘
```

---

## 5. Configuration System

### Dual-Config Architecture

Cynapse uses two configuration files with distinct responsibilities:

#### 1. `cynapse/data/config.ini` (Hub Configuration)

**Purpose**: Core system settings, neuron discovery, security policies

**Sections**:

```ini
[general]
hub_name = CynapseGhostShell
version = 2.0.0
log_level = INFO
data_dir = ./cynapse/data

[neurons]
neurons_dir = ./cynapse/neurons
verify_signatures = false
timeout_seconds = 30
auto_discover = true

[security]
audit_logging = true
sensitive_keywords = key,secret,token,password
require_signatures = false

[voice]
enabled = true
whistle_frequency = 18000
whistle_threshold = 50
sample_rate = 48000
timeout_seconds = 30

[assembly]
temp_dir = ./cynapse/data/temp
enable_encryption = true
shards_required = 2

[ollama]
enabled = true
endpoint = http://localhost:11434
default_model = llama3.2
fallback_models = llama3.1,phi4

[hivemind]
db_path = ./hivemind.db
document_path = ./cynapse/data/documents
workflow_path = ./workflows
max_concurrent_bees = 5
sandbox_enabled = true
auto_approve = false
```

**Loading**: Parsed by `CynapseHub` on initialization using `configparser`

#### 2. `hivemind.yaml` (Workflow Engine Configuration)

**Purpose**: HiveMind workflow settings, model paths, security policies

**Structure**:

```yaml
hive:
  name: "cynapse_hive"
  max_concurrent_bees: 5
  log_level: "INFO"
  db_path: "./hivemind.db"
  document_path: "./cynapse/data/documents"
  workflow_path: "./workflows"
  queen_model: "./cynapse/data/models/elara.gguf"
  sandbox_enabled: true
  auto_approve: false

storage:
  vector_backend: "numpy"
  state_backend: "sqlite"
  document_path: "./cynapse/data/documents"

models:
  queen:
    path: "./cynapse/data/models/elara.gguf"
    context_length: 4096
    gpu_layers: -1
  fallback:
    - name: "llama3.2"
      endpoint: "http://localhost:11434"
    - name: "llama3.1"
      endpoint: "http://localhost:11434"

security:
  sandbox_enabled: true
  max_file_size: "100MB"
  allowed_paths:
    - "./workflows"
    - "./cynapse/data/documents"
  blocked_commands:
    - "rm -rf /"
    - "format"
    - "mkfs"
```

**Loading**: Parsed by `HiveConfig.from_yaml()` using PyYAML

---

## 6. Component Details

### The Hub (cynapse.core.hub)

**Responsibilities**:
1. **Neuron Discovery**: Scans `cynapse/neurons/` on startup, parses manifest.json files
2. **Configuration Management**: Loads and validates `config.ini`
3. **Execution Dispatch**: Routes commands to appropriate neurons
4. **Integration Point**: Connects TUI, HiveMind, and individual neurons

**Key Methods**:
- `__init__(config_path)`: Initialize with optional custom config
- `_discover_neurons()`: Scan and catalog available neurons
- `list_neurons()`: Return list of discovered neuron names
- `get_neuron(name)`: Retrieve neuron metadata
- `execute_neuron(name, args)`: Execute a neuron by name

**Integration with TUI**:
- Hub provides real neuron status for Sentinel Grid display
- TUI calls Hub methods to toggle neuron states
- Bidirectional communication for status updates

### HiveMind (cynapse.core.hivemind)

**Responsibilities**:
1. **Workflow Orchestration**: Execute node-based workflows (bees)
2. **AI Integration**: Manage Elara model and Ollama fallback
3. **State Management**: SQLite storage for bees and instances
4. **Vector Operations**: In-memory vector database for RAG

**Architecture**:

```
HiveMind
├── Honeycomb (storage)
│   ├── SQLite: bees, instances, memory
│   └── In-Memory: vectors for RAG
├── Node Handlers
│   ├── FileReaderNode
│   ├── TextChunkerNode
│   ├── LLMNode (llama-cpp → Ollama fallback)
│   ├── CodeExecuteNode
│   ├── VectorStoreNode
│   └── OutputNode
└── Execution Engine
    ├── spawn_bee(): Create thread
    ├── _execute_bee(): Run nodes
    └── State updates
```

**Node Handler Registry**:
```python
    'file_reader': FileReaderNode(),
    'text_chunker': TextChunkerNode(),
    'llm': LLMNode(),
    'code_execute': CodeExecuteNode(),
    'vector_store': VectorStoreNode(),  # Lazy numpy load
    'output': OutputNode(),
}
```

**LLM Fallback Chain**:
1. Try llama-cpp with local Elara model
2. If unavailable, try Ollama API
3. If both fail, raise RuntimeError

### Agent System (cynapse.agent)

**New in v2.2.0**: A multi-agent system designed for complex task orchestration.

**Components**:
- **LeadAgent**: The coordinator. Breaks down high-level user requests into granular `Tasks`.
- **Subagent**: Specialized workers (Researcher, Coder, etc.) that execute tasks.
- **ArtifactStore**: A filesystem-based shared memory. Agents write large outputs (code, docs) to disk and pass *references* (file paths) to other agents, rather than passing the full content in the prompt. This drastically reduces token usage.
- **Mailbox**: Thread-safe message queue for agent-to-agent communication.

**Flow**:
1. User Request → LeadAgent
2. LeadAgent plans → Spawns Subagents
3. Subagents execute → Write Artifacts → Notify LeadAgent
4. LeadAgent reads Artifacts → Synthesizes Final Response


### The TUI (cynapse.tui)

**Architecture**:

```
SynapticFortress
├── Terminal (raw mode handling)
├── HiveState (central state)
├── Animator (4fps animation)
├── InputHandler (keyboard processing)
│   └── _get_hivemind() reference
├── Zone Renderers
│   ├── PerimeterZone (top status)
│   ├── SentinelGridZone (left sidebar)
│   ├── ActivationChamberZone (top-right dynamic)
│   ├── OperationsBayZone (bottom-right chat)
│   └── CommandFooterZone (bottom hotkeys)
└── Hub integration (lazy)
```

**Four-Zone Layout**:

```
╔═══════════════════════════════════════════════════════════════════════════╗
║ [Zone 1: PERIMETER]  Status: SECURE  Shards: ◆◆○  Voice: v  100%          ║
╠════════════════════════════════╦══════════════════════════════════════════╣
║ Zone 2: SENTINEL GRID          ║  Zone 3: ACTIVATION CHAMBER             ║
║ [Defense Neurons]              ║  Dynamic visualization                   ║
║ Left 25% of screen             ║  Context-aware display                   ║
║                                ║                                          ║
║ ► 🦇 bat_ghost    ● [standby]  ║  ─────────────────────────────────────   ║
║   🦫 beaver_miner ○ [dormant]  ║  Zone 4: OPERATIONS BAY                  ║
║   🐤 canary_token ○ [dormant]  ║  Chat / RAG / Execution                   ║
║   ...                          ║                                          ║
║                                ║  > Hello Cynapse                         ║
║                                ║  🐝 Response here...                     ║
║                                ║  >>> _                                   ║
╠════════════════════════════════╩══════════════════════════════════════════╣
║ [h] Help  [v] Voice  [s] Scan  [L] Lockdown  [:q] Back  [Q] Quit          ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

**Animation System**:
- Target: 10fps (0.1s intervals) for fluid UI
- Double-buffered rendering (sys.stdout.write)
- No flicker updates
- Static skeletons with moving pulses
- Spinner: `["|", "/", "-", "\"]`
- Pulse: `["●", "◐", "◑", "◒"]`

---

## 7. Security Model

### Ghost Shell Architecture

**Physical Security Layers**:

```
User Authentication
        │
        ├──► Physical: USB stick presence (3 shards)
        │
        ├──► Acoustic: 18kHz ultrasonic whistle
        │
        ├──► Knowledge: Assembly key for XOR decryption
        │
        └──► Cryptographic: Shamir Secret Sharing (2-of-3)
                    │
                    ▼
            Model Reconstruction
                    │
            ┌───────┴───────┐
            ▼               ▼
    Decrypted Model     RAM-Only Storage
    (elara.gguf)        (tmpfs)
            │               │
            └───────┬───────┘
                    ▼
            AI Inference Engine
```

**Shamir Secret Sharing**:
- Secret (encryption key) split into 3 shares
- Any 2 shares can reconstruct the key
- Losing 1 share is survivable
- Pure Python implementation (no dependencies)

**Encryption Chain**:
1. Model encrypted with ChaCha20-Poly1305
2. Encryption key split via Shamir's Secret Sharing
3. Shares distributed to 3 USB sticks
4. Reconstruction requires 2 sticks + assembly key

### Audit & Logging

**NDJSON Format** (newline-delimited JSON):
```json
{
  "timestamp": "2026-02-03T14:30:00Z",
  "neuron": "hivemind",
  "event": "bee_spawned",
  "severity": "info",
  "data": {
    "instance_id": "abc123_xyz789",
    "bee_type": "deployment",
    "trigger": "user_chat"
  }
}
```

**Security Properties**:
- Append-only (no modification)
- 0600 permissions (owner-only)
- Sensitive data redaction (keys, tokens, passwords)
- Hash-based integrity verification

---

## 8. Structural Efficiency Report

### Why This Architecture?

1. **Namespace Isolation**: Moving code into `cynapse.*` prevents global namespace pollution and makes imports explicit (`from cynapse.core.hub import CynapseHub`).

2. **Packaging Readiness**: PyInstaller requires a clean entry point and defined package tree. The previous flat structure made resource bundling nearly impossible.

3. **Polyglot Management**: Specialized subdirectories for `elephant` (Rust) and `rhino` (Go) allow source code to remain self-contained with their specific build manifests.

4. **TUI Unification**: The conflict between main TUI and neuron-specific TUI is resolved by importing the neuron TUI *into* the main TUI as a component.

5. **Lazy Loading**: Prevents dependency cascade failures. Users can start with core features and add AI capabilities later.

### Key Improvements from v1.x

| Aspect | v1.x | v2.0.0 | Improvement |
|--------|------|---------|-------------|
| **Entry Point** | Multiple scripts | Single `cynapse_entry.py` | Unified CLI |
| **Dependencies** | All required | Tiered (core/full) | Flexible installation |
| **Neuron Discovery** | Manual | Auto via manifests | Easier extension |
| **TUI Connectivity** | Disconnected | Integrated with HiveMind | Functional chat |
| **Configuration** | Hardcoded | Dual config system | User-customizable |
| **Health Monitoring** | None | Comprehensive diagnostics | Better troubleshooting |
| **Documentation** | Sparse | Detailed guides | Easier adoption |

---

## 9. Performance Considerations

### Resource Targets

| Component | Target | Current |
|-----------|--------|---------|
| Hub initialization | < 500ms | < 300ms |
| Neuron discovery | ~10ms each | ~2ms |
| TUI startup | < 1s | ~200ms |
| Whistle detection | ~100ms | Variable |
| Bee spawning | < 500ms | ~300ms |
| LLM inference | 50-200ms/token | Model-dependent |

### Optimization Strategies

1. **Lazy Loading**: Heavy dependencies (torch, transformers) only load when needed
2. **Static Skeletons**: TUI uses static layouts with minimal updates (4fps)
3. **Single Character Updates**: Differential rendering instead of full screen redraws
4. **Connection Pooling**: SQLite with WAL mode for concurrent access
5. **Memory Mapping**: Large models loaded on-demand with paging

---

## 10. Integration Points

### Inter-Neuron Communication

| From | To | Purpose | Mechanism |
|------|-----|---------|-----------|
| CynapseHub | All Neurons | Execution dispatch | Subprocess / Import |
| bat_ghost | HiveMind | Model assembly | File system (temp) |
| elephant | All Binaries | Signature verification | Ed25519 verification |
| HiveMind | Elara | AI inference | Direct import / llama-cpp |
| parrot_wallet | TTS Engine | Voice output | Subprocess (future) |
| meerkat_scanner | beaver_miner | CVE → Firewall rules | Event bus (planned) |

### External Dependencies

| Component | Dependency | Purpose | Load Strategy |
|-----------|-----------|---------|---------------|
| TUI | termios, select | Raw terminal mode | Startup |
| Elara | torch, transformers | Neural network | Lazy |
| Elephant | cryptography | Ed25519 signing | Startup |
| Owl | pytesseract, PIL | OCR engine | On-demand |
| Octopus | aiodocker | Container runtime | Optional |
| HiveMind | chromadb, ollama | Vector DB / LLM | Lazy |
| Bat | pyaudio, scipy | Audio capture | On-demand |

---

## 11. Development Guidelines

### Adding a New Neuron

1. **Create Directory**:
   ```bash
   mkdir cynapse/neurons/your_neuron
   ```

2. **Create Module**:
   ```python
   # cynapse/neurons/your_neuron.py
   class YourNeuron:
       def __init__(self):
           pass
       
       def execute(self, args):
           # Implementation
           pass
   ```

3. **Create Manifest**:
   ```json
   {
     "name": "your_neuron",
     "version": "1.0.0",
     "description": "What it does",
     "entry_point": "your_neuron.py",
     "dependencies": [],
     "commands": {
       "run": "Execute the neuron"
     }
   }
   ```

4. **Export in __init__.py**:
   ```python
   try:
       from .your_neuron import YourNeuron
   except ImportError:
       pass
   ```

5. **Test**:
   ```bash
   python cynapse_entry.py --health
   python cynapse_entry.py --cli  # Should list your neuron
   ```

### Creating Custom Workflows

1. **Define Workflow YAML**:
   ```yaml
   name: custom_workflow
   type: training  # or deployment
   nodes:
     - id: input
       type: file_reader
       config: { path: "./data.txt" }
     
     - id: process
       type: text_chunker
       config: { chunk_size: 512 }
       inputs: { text: "input.content" }
     
     - id: output
       type: output
       config: { format: "json" }
       inputs: { content: "process.chunks" }
   ```

2. **Place in workflows/**:
   ```bash
   cp custom_workflow.yaml workflows/
   ```

3. **Load and Execute**:
   ```python
   from cynapse.core.hivemind import HiveMind, HiveConfig
   
   hive = HiveMind(HiveConfig.from_yaml('./hivemind.yaml'))
   bee = hive.load_bee_from_yaml('workflows/custom_workflow.yaml')
   instance_id = hive.spawn_bee(bee.id)
   ```

---

## 12. Migration Guide

### From v1.x to v2.0.0

**Breaking Changes**:

1. **Import Paths**:
   ```python
   # Old (v1.x)
   from cynapse import CynapseHub
   
   # New (v2.0.0)
   from cynapse.core.hub import CynapseHub
   from cynapse.core.hivemind import HiveMind
   ```

2. **Initialization Required**:
   ```bash
   # Must run before first use
   python cynapse_entry.py --init
   ```

3. **Dependency Tiers**:
   ```bash
   # Choose based on needs
   pip install -r requirements.txt      # Core only
   pip install -r requirements-full.txt # With AI
   ```

4. **Configuration Files**:
   - v1.x: Hardcoded or minimal config
   - v2.0.0: `config.ini` + `hivemind.yaml` required

**Non-Breaking but Recommended**:

1. Use `--health` to verify installation
2. Review new TUI controls (added Ctrl+F for document ingestion)
3. Check workflow YAML format (standardized node types)

---

## Appendix A: File Format Reference

### Neuron Manifest Schema

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

### Workflow YAML Schema

```yaml
name: string (required)
type: enum [training, deployment]
trigger: enum [user_query, file_upload, schedule, webhook]
nodes:
  - id: string (required, unique)
    type: enum [file_reader, text_chunker, llm, code_execute, vector_store, output, ...]
    config: object (type-specific)
    inputs: object (mapping to other node outputs)
    condition: string (optional, Python expression)
```

### Audit Log Entry Schema

```json
{
  "timestamp": "ISO8601 string",
  "neuron": "string (neuron name)",
  "event": "string (event type)",
  "severity": "enum [debug, info, warning, error, critical]",
  "data": "object (event-specific)",
  "integrity": "string (SHA256 hash, optional)"
}
```

---

## Appendix B: Glossary

- **Bee**: Workflow definition in HiveMind
- **Ghost Shell**: Sharded AI model storage system using Shamir's Secret Sharing
- **HiveMind**: AI ecosystem with Queen (Elara) and Drones (specialist models)
- **Neuron**: Standalone security tool with manifest
- **RAG**: Retrieval-Augmented Generation
- **Shamir's Secret Sharing**: Threshold cryptography (split secret, reconstruct with k-of-n shares)
- **Synaptic Fortress**: Terminal User Interface (TUI)
- **TiDAR**: Time-aware Diffusion with Auto-Regressive refinement
- **MoE**: Mixture of Experts (model architecture)
- **RoPE**: Rotary Position Embeddings
- **TRM**: Temporal Recursion Mechanism (recursive transformer layers)

---

**Document Control**:
- **Author**: Alejandro Eduardo Garcia Romero
- **Version**: 2.0.0
- **Last Updated**: 2026-02-03
- **Status**: Production Ready
- **Classification**: Open Source (MIT License)

**Related Documents**:
- README.md - Quick start guide
- Changelog.md - Version history
- HIVE.md - Workflow engine details
- TUI.md - Interface reference
- neurons.md - Individual neuron docs
- AI.md - Elara model architecture
