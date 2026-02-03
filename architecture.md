# Cynapse Architecture Reference

**Version**: 2.0.0  
**Date**: 2026-02-03  
**Status**: Restructured & Optimized for Packaging

---

## 1. Executive Summary

Cynapse has evolved from a loose collection of scripts into a structured Python package (`cynapse`) with native packaging capabilities. This architecture ensures modularity, easier distribution, and secure separation of concerns.

The system is now a **Unified Security Hub** that manages:
1.  **Core Intelligence**: The `hub` orchestrator and `hivemind` AI automation.
2.  **Visual Interface**: The `tui` (Synaptic Fortress) for user interaction.
3.  **Neural Defense**: A collection of `neurons` (polyglot tools in Python, Go, and Rust) that perform specialized security tasks.

---

## 2. Directory Structure

The new structure follows standard Python packaging conventions while maintaining the "Neuron" concept.

```
cynapse_project/
├── cynapse_entry.py          # [ENTRY] Main executable script
├── cynapse.spec              # [BUILD] PyInstaller packaging spec
├── requirements.txt          # [DEPS] Python dependencies
├── build_scripts/            # [BUILD] Polyglot build helpers
│   └── build_all.py          # Master build script
│
├── cynapse/                  # [PACKAGE] Main application package
│   ├── __init__.py
│   │
│   ├── core/                 # [CORE] Business logic
│   │   ├── hub.py            # Orchestrator & Discovery
│   │   ├── hivemind.py       # AI Workflow Engine
│   │   └── audit.py          # (Planned) Security Logging
│   │
│   ├── tui/                  # [UI] Synaptic Fortress Interface
│   │   ├── main.py           # Main TUI loop (formerly TUI.py)
│   │   ├── layout.py         # Visual zones
│   │   └── widgets.py        # UI components
│   │
│   ├── neurons/              # [TOOLS] Security Neurons
│   │   ├── __init__.py       # Neuron registry
│   │   ├── bat.py            # Ghost Shell (USB security)
│   │   ├── beaver.py         # Firewall Miner
│   │   ├── canary.py         # Honeytokens
│   │   ├── elara.py          # AI Model Interface
│   │   ├── meerkat.py        # Network Scanner
│   │   ├── octopus.py        # CTF Challenges
│   │   ├── owl.py            # OCR/Redaction
│   │   ├── wolverine.py      # Red Team Auditing
│   │   │
│   │   ├── elephant/         # [RUST] Cryptographic Signing
│   │   │   ├── elephant.rs   # Core Rust logic
│   │   │   ├── tui.py        # Python/TUI wrapper
│   │   │   └── Cargo.toml    # Rust build manifest
│   │   │
│   │   └── rhino_gateway/    # [GO] Zero-Trust Gateway
│   │       └── rhino.go      # Go source
│   │
│   └── utils/                # [SHARED] Helper libraries
│       ├── security.py       # Input validation & sanitization
│       └── config.py         # Configuration handling
│
└── data/                     # [DATA] Default configs & assets
    └── config.ini
```

---

## 3. Structural efficiency Report

### 3.1 Why this new structure?
1.  **Namespace Isolation**: Moving code into `cynapse.*` prevents global namespace pollution and makes imports explicit (`from cynapse.core.hub import CynapseHub`).
2.  **Packaging Readiness**: PyInstaller requires a clean entry point (`cynapse_entry.py`) and a defined package tree to correctly bundle resources. The previous flat structure made resource bundling nearly impossible.
3.  **Polyglot Management**: Specialized subdirectories for `elephant` (Rust) and `rhino` (Go) allow us to keep source code self-contained with their specific build manifests (`Cargo.toml`, `go.mod`).
4.  **TUI Unification**: The conflict between the main TUI and the neuron-specific TUI (Elephant) is resolved by importing the neuron TUI *into* the main TUI as a component, rather than having competing main loops.

### 3.2 Key Improvements
-   **Single Entry Point**: Users now run one script (`cynapse_entry.py`) instead of needing to know whether to run `TUI.py` or `cynapse.py`.
-   **Modular Neurons**: Adding a new neuron is now as simple as dropping a file into `cynapse/neurons/`. The `Hub` auto-discovers these modules.
-   **Native Binary**: The `build_scripts/build_all.py` pipeline enables compiles the entire project into a single binary (`dist/Cynapse`), solving the "dependency hell" problem for end users.

---

## 4. Component Interaction

### The Hub (`cynapse.core.hub`)
The central nervous system. It:
1.  Scans `cynapse/neurons/` on startup.
2.  Verifies signatures (using Elephant).
3.  Initializes the `AuditLogger`.
4.  Launches the TUI or processes CLI commands.

### The TUI (`cynapse.tui`)
The visual cortex. It:
1.  Imports `CynapseHub` to get the system state.
2.  Visualizes `neurons` (Sentinels) and `hivemind` (Operations).
3.  Delegates specific visuals (like "Activation") to neuron-specific TUI modules (e.g., `elephant.tui`).

### HiveMind (`cynapse.core.hivemind`)
The cognitive engine. It:
1.  Operates as an advanced workflow engine.
2.  Can be triggered by the TUI (Operations zone).
3.  Manages the AI model (Elara) lifecycle.

---

## 5. Security Model Preservation

Despite the restructuring, the **Ghost Shell** security model is preserved:
-   **Air-Gap Ready**: No hardcoded external API calls in core startup.
-   **Sharded Auth**: `bat.py` still manages the USB shard logic.
-   **Signed Code**: `elephant` verifies integrity before execution.
