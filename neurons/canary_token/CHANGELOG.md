# Changelog

## [1.1.0] - 2026-02-02
### 🚀 Improvements
- **Hub Refactor Integration**: Updated for compatibility with the new Cynapse Hub restructuring
- **TUI Support**: Added semantic metadata for the Synaptic Fortress Interface
- **Security Audit**: Verified implementation against the 2026 security audit report


All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-01-07

### Added
- **bait_gen.py**: Script to generate deceptive "bait" files.
    - `aws_credentials.json`: Fake AWS keys.
    - `model_weights.onnx`: 4MB binary with legitimate ONNX header.
    - `Cookies.json`: Fake Chrome session cookies.
- **canary.py**: Main detection agent.
    - Cross-platform file system monitoring (Windows `ReadDirectoryChangesW`, Linux `inotify`) using `ctypes`.
    - 500ms timeout on watcher loops to ensure clean `Ctrl-C` termination.
    - JSON logging to `canary.log`.
    - Integration with `elara_tts.py` for voice alerts.
- **elara_tts.py**: Mock Text-to-Speech handler for immediate alert feedback.
- **Documentation**: Comprehensive `README.md` with setup and usage instructions.

### Security & Stealth
- Watcher uses native OS APIs via `ctypes` to avoid suspicious third-party dependencies.
- Bait files follow standard naming conventions to attract attackers searching for credentials.
