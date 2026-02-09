# Changelog

All notable changes to this project will be documented in this file.

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
