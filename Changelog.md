# Changelog

All notable changes to the Cynapse project will be documented in this file.

## [2.1.0-fix] - 2026-02-09

### Added
- **Centralized Configuration**: `cynapse.utils.config.ConfigManager` for unified settings handling.
- **TUI Optimization**: Double-buffered rendering using `sys.stdout.write` to eliminate screen flicker.
- **Threaded Bee Spawning**: Non-blocking bee deployment in `HiveMind` to keep TUI responsive during heavy tasks.
- **Lazy Loading**: `numpy` and `torch` are now loaded on demand in `HiveMind`, significantly reducing startup time and memory footprint (optimized for 2GB RAM devices).
- **Security**: Added `redact_sensitive` utility to scrub keys/tokens from logs.
- **Audit System**: Created `cynapse.utils.audit.AuditLogger` to unify logging across neurons (Bat, Wolverine).

### Changed
- **Neuron Discovery**: `CynapseHub` now robustly parses `manifest.json` files in subdirectories, allowing for rich metadata.
- **TUI Frame Rate**: Increased from 4fps to 10fps for smoother animations (utilizing new buffered rendering).
- **Model Loading**: Standardized `sys.path` injection for Elara model to handle absolute paths correctly.
- **TUI Input**: Moved chat deployment to background thread to prevent UI freezing while waiting for HiveMind.
- **Wolverine Neuron**: Fixed crash by implementing shared `AuditLogger`.

### [2.2.0-agent] - 2026-02-09

### Added
- **HiveMind Agent Architecture**: Full implementation of "Lead Agent + Subagent" pattern inspired by Claude Code.
  - `LeadAgent`: Orchestrates tasks, plans execution, and synthesizes results.
  - `Subagent`: Runs in isolated threads for parallel task execution.
  - `ArtifactStore`: Filesystem-based artifact passing to save tokens and preserve privacy.
  - `Mailbox`: Asynchronous message passing between agents.
- **Setup Automation**: Added `run.sh` script to automatically handle virtual environment creation, activation, and dependency installation.
- **Documentation**: Added `CREDITS.md` to acknowledge research inspirations.


### Fixed
- **Health Check**: Fixed `ImportError` in `security.py` by implementing missing `redact_sensitive`.
- **Indentation Error**: Corrected logic in `cynapse/tui/main.py` input handler.
- **Pathing**: Resolved inconsistent module resolution for `elara` throughout the codebase.

### Removed
- **Legacy Documentation**: Deleted `neurons.md`, `AI.md`, `HIVE.md`, `PACKAGE.md`, `PREVIOUS.md`, `TRAINING.md`, `TUI.md` to consolidate information into `architecture.md` and `README.md`.

---

## [2.0.0] - 2026-02-03

### Added
- Initial modular architecture (Hub, HiveMind, Neurons).
- Synaptic Fortress TUI with 4-zone layout.
- Polyglot support structure (Python/Go/Rust).
- Basic security features (Shamir Secret Sharing, Ed25519 signing).
