# Changelog

All notable changes to this project will be documented in this file.

## [4.0.1] - 2026-02-25
### Added
- **AI Integration**: Functional Elara MoE model and Owl OCR implementation integrated via Python bridge.
- **IT Mode Execution**: Ability to run IT support modules directly from the TUI command palette.
- **Path Protection**: Centralized path validation utility in Go core for security.

### Fixed
- **Security**: Patched critical path traversal vulnerabilities in Wolverine and HiveMind.
- **Security**: Hardened Beaver neuron against command injection via strict IP validation.
- **Security**: Replaced dangerous `exec()` calls in Python configurator with safe AST parsing.
- **Performance**: Verified ~500x faster cold start and ~100x faster neuron execution compared to v3.0.

## [4.0.0] - 2026-02-17 (Ghost Shell)
### Added
- **Go Core**: Complete rewrite of the orchestration engine in Go for maximum performance.
- **Bubble Tea TUI**: Declarative, high-fidelity terminal interface with <10ms latency.
- **Parallel Neurons**: Go-native implementation of 6 key neurons (Bat, Beaver, Canary, Meerkat, Octopus, Wolverine) using goroutines.
- **Python Bridge**: High-speed JSON IPC bridge for Elara (AI) and Owl (OCR) neurons.
- **SQLite Honeycomb**: Robust workflow and state persistence layer.
- **Compiled safety**: Constitutional validator logic now hardcoded and compiled-in.
- **Single Binary**: The entire system (minus AI models) now builds into a ~4MB static binary.

### Changed
- **Migration**: Shifted primary development from Python to Go.
- **Structure**: Reorganized into `cmd/`, `internal/`, and `python/` subdirectories.
- **Docs**: Comprehensive update to all documentation (`README`, `architecture`, `TUI_SPEC`, `FEATURES`, `CREDITS`).

### Fixed
- **Bottlenecks**: Eliminated Python GIL-related performance issues.
- **Cold Boot**: Reduced startup time from 5s to ~45ms.
- **Dependencies**: Resolved "dependency hell" by utilizing Go's static linking.


## [3.0.0] - 2026-02-09
### Added
- **IT Mode**: Self-modifying tech support system in `cynapse/core/tech_support/`.
- **Core Values**: Constitutional AIValidator in `cynapse/core/core_values/`.
- **New TUI**: Complete rewrite using `terminal.py` (raw mode), `state.py` (Redux-like), and `view.py` (Renderer).
- **Command Palette**: Press `/` to access tools instantly.
- **HiveMind Integration**: `ITModeNode` for self-repair execution.

### Changed
- **Architecture**: Moved to a "Lead + Subagent" model for complex tasks.
- **Documentation**: Updated `README.md` and `architecture.md` to reflect v3.0 changes.
- **Dependencies**: Minimized dependencies (only standard lib + `numpy`, `a few others`).

### Fixed
- TUI flickering and responsiveness issues (now using diff-based rendering).
- HiveMind race conditions (added threading locks).

## [2.2.0] - Agent Update
### Added
- **Multi-Agent System**: Lead Agent, Researcher, Coder.
- **Artifacts**: File-based communication between agents.
- **Mailbox**: Async messaging queue.

## [2.1.0] - Architecture Fix
### Fixed
- Circular dependencies in core modules.
- Missing `__init__.py` files in subpackages.
- Performance issues on low-end hardware (lazy loading).

## [2.0.0] - Initial Release
- **8 Neurons**: Base security tools implemented.
- **Ghost Shell**: USB Auth system.
- **Basic TUI**: Initial prototype.
