# Changelog

## [2.0.0] - 2026-02-03
### Added
-   **Native Packaging**: Added `cynapse.spec` and `build_all.py` to create standalone executables via PyInstaller.
-   **Unified Entry Point**: Introduced `cynapse_entry.py` to handle both CLI and TUI modes via a single command.
-   **Package Structure**: Restructured code into a proper `cynapse` Python package with `core`, `tui`, `neurons`, and `utils` subpackages.
-   **Build System**: Added scripts to orchestrate the compilation of Polyglot components (Go/Rust).

### Changed
-   **Architecture**: Moved from a flat file structure to a modular package architecture.
-   **TUI Integration**: Renamed `TUI.py` to `cynapse/tui/main.py` and integrated it with the `CynapseHub`.
-   **Elephant Integration**: Refactored `elephant/elephenttui.py` to `cynapse/neurons/elephant/tui.py` for better integration with the main TUI.
-   **HiveMind**: Relocated `hivemind.py` to `cynapse/core/` and updated imports.

### Fixed
-   **Import Conflicts**: Resolved circular or missing imports caused by the previous flat structure.
-   **Dependency Management**: Consolidated all Python dependencies into `requirements.txt`.
-   **Security Utils**: Standardized security functions (input validation, key masking) in `cynapse/utils/security.py`.

### Removed
-   **Legacy Scripts**: Removed redundant standalone scripts in favor of the unified `neurons` directory.
-   **Flat Structure**: Cleaned up root directory bloat.
