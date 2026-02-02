# Changelog

All notable changes to Cynapse Ghost Shell Hub are documented in this file.

## [1.2.0] - 2026-02-02

### 🔒 Security Fixes

#### P0: Critical - Command Injection in Beaver Miner
- **Fixed** command injection vulnerability in `neurons/beaver_miner/verifier.py` (CVSS 8.8)
- Added strict input validation for all LLM-generated rule parameters
- Implemented regex validators for IP addresses, ports, and protocols
- Shell metacharacter detection blocks malicious inputs
- Created shared `utils/security.py` module for reusable validation

#### P0: High - API Key Logging in Rhino Gateway
- **Fixed** information disclosure in `neurons/rhino_gateway/log.go`
- API keys now masked in logs (first 4 characters + asterisks)
- Added SHA256 hash prefix for log correlation without exposure
- Changed log file permissions to 0600 (owner-only)

#### P1: Medium - Missing Signature Verifier
- **Added** `neurons/elephant_sign/verify.py` for Python-based Ed25519 verification
- Provides wrapper for Rust binary with Python fallback
- Supports PEM, DER, and raw key formats

#### P2: Low - PyPDF Vulnerability
- Documented requirement for `pypdf>=6.6.2` to address CVE-2026-22690 and CVE-2026-22691

### 🚀 New Features

#### Synaptic Fortress TUI
Complete terminal user interface implementation based on `TUI.md` specification:

- **Color System** (`tui/colors.py`)
  - Purple Dynasty primary palette
  - Electric Blue secondary palette
  - Alert Gold/Amber complement colors
  - ANSI 256 color support with fallback detection

- **Symbol Dictionary** (`tui/symbols.py`)
  - Semantic symbols: `●` active, `▸` standby, `○` dormant, `✓` complete, `✗` error
  - Status tags: `[running]`, `[complete]`, `[standby]`, `[arrested]`
  
- **State Management** (`tui/state.py`)
  - Observer pattern for efficient UI updates
  - Tracks mode, security status, neurons, shards, documents
  - Singleton global state access

- **Keybindings** (`tui/keybindings.py`)
  - Vim-style navigation (hjkl)
  - Global hotkeys: `h` (help), `v` (voice), `s` (scan), `L` (lockdown), `Q` (quit)
  - Multi-key sequences: `gg` (jump top), `:q` (back)
  - Zone-specific controls for Sentinel Grid and Operations Bay

- **Four-Zone Layout** (`tui/layout.py`)
  - Zone 1: Perimeter (top status bar)
  - Zone 2: Sentinel Grid (left sidebar, 28% width)
  - Zone 3: Activation Chamber (top-right, dynamic)
  - Zone 4: Operations Bay (bottom-right, RAG laboratory)

- **Interface Modes** (`tui/modes/`)
  - `neural_assembly.py`: USB shard combination visualization
  - `pharmacode.py`: Model loading with 8-segment progress bars
  - `operations.py`: RAG document ingestion and Queen chat
  - `breach.py`: Full-screen red alert overlay

- **Widgets** (`tui/widgets/`)
  - `status_bar.py`: Security status, integrity %, voice monitor
  - `sentinel_grid.py`: Neuron list with scrolling and selection
  - `animations.py`: ThinkingDot, SignalPropagation, Spinner

- **Main TUI** (`tui/main.py`)
  - 10fps refresh rate with frame limiting
  - Raw terminal mode for instant key response
  - Proper cleanup on exit

### 📁 Code Restructuring

- **New `utils/` Package**
  - `utils/__init__.py`: Package initialization
  - `utils/security.py`: Shared security functions
    - `validate_path()`: Path traversal prevention
    - `validate_ip()`: IP address validation
    - `validate_port()`: Port number validation
    - `validate_protocol()`: Protocol validation
    - `sanitize_llm_output()`: LLM output sanitization
    - `mask_api_key()`: API key masking for logs
    - `hash_api_key()`: SHA256 hash for correlation

- **Updated `cynapse.py`**
  - Added `--tui` command line option
  - Updated help text with new options

### 📚 Documentation

- **Updated `README.md`**
  - Comprehensive project overview
  - Feature list with all 12 neurons
  - TUI usage guide with keybindings
  - Updated project structure
  - Configuration examples
  - Security documentation

- **New `DEPENDENCIES.md`**
  - Complete dependency list with versions
  - Purpose description for each package
  - Required vs optional categorization
  - Dependency reduction recommendations
  - Minimum vs full installation instructions

- **Updated `architecture.md`**
  - New `utils/` package documentation
  - TUI architecture section
  - Security improvements

### 🗑️ Removed Files

- `report.md` - Security audit report (issues resolved)
- `newplan.md` - Empty planning document
- `no_dependency.md` - Portable deployment strategy (merged into README)
- All `prd.md` files in neurons (10 files) - Product requirement documents

---

## [1.1.0] - 2026-01-21

### 🐛 Bug Fixes

- **Fixed ModuleNotFoundError in hivemind.py**: Refactored with lazy imports - heavy dependencies (torch, transformers) only load when specific features are used
- **Fixed AdamW import error in trainer.py**: Removed top-level torch import, teacher model loads on-demand
- **Fixed router import in terminal_chat.py**: Added robust fallback pattern for router module

### 🚀 New Features

#### Portable USB Deployment
- Complete portable Python environment for USB drives
- Auto-detection of USB mount points on Windows, Linux, and macOS
- Embedded Python distribution for Windows (no Python installation required)
- Single-click launchers for each platform

#### Enhanced Security
- Sensitive data redaction in logs
- Configurable sensitive keywords list
- Audit logging improvements

### 🔧 Improvements

- Lazy loading for all heavy dependencies
- Reduced startup time from ~5s to <1s for basic operations
- Better error messages for missing dependencies

---

## [1.0.0] - 2026-01-15

### Initial Release

- Core Hub orchestrator with neuron discovery
- 12 security neurons implemented
- HiveMind AI system with Queen and Drones
- Voice trigger detection (18kHz ultrasonic whistle)
- Ghost Shell 3-shard model storage
- Ed25519 signature verification
- Audit logging in NDJSON format
- Configuration via INI files
- CLI interface with command completion
