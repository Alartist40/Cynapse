# Cynapse Architecture Reference

**Version**: 4.0.0 (Ghost Shell)
**Date**: 2026-02-17
**Status**: Performance Optimized

---

## 1. Executive Summary

Cynapse v4.0.0 "Ghost" marks the most significant evolution of the project: a complete migration from Python to a **Go-first architecture**. This shift solves the Python GIL bottlenecks, streamlines dependencies into a single binary, and provides <100ms startup times.

### Key Achievements in v4.0.0

1.  **Go Core**: Entire orchestration engine (HiveMind) rewritten in Go.
2.  **Bubble Tea TUI**: Declarative, flicker-free terminal interface.
3.  **Goroutine Concurrency**: Neurons execute in true parallel threads.
4.  **IPC Bridge**: High-speed JSON-over-stdin/stdout bridge for Python AI neurons (Elara, Owl).
5.  **Compiled-in Safety**: Constitutional AI rules are hardcoded and compiled, preventing interference.

---

## 2. Directory Structure (v4)

### New Project Layout

```
Cynapse/
├── v4/                           # [GO ROOT] New architecture home
│   ├── cmd/cynapse/              # Entry point (main.go)
│   ├── internal/                 # Deep logic (not importable externally)
│   │   ├── core/                 # Shared types & Constitutional Validator
│   │   ├── tui/                  # Bubble Tea Implementation
│   │   ├── hivemind/             # Goroutine Workflow Engine
│   │   ├── neurons/              # Go-native security tools (Bat, Beaver, etc.)
│   │   ├── bridge/               # Python IPC Bridge logic
│   │   └── techsupport/          # IT Mode registry & executor
│   ├── python/                   # [PYTHON] AI Neuron Bridge Servers
│   │   ├── elara/                # Elara MoE Bridge
│   │   └── owl/                  # Owl OCR Bridge
│   ├── scripts/                  # Build & automation scripts
│   └── dist/                     # Compiled binaries
```

---

## 3. High-Level Architecture

### The Ghost Shell Model

```
┌───────────────────────────────────────────────────────────────┐
│                    GO USER INTERFACE (TUI)                    │
│  Bubble Tea | Lipgloss Styling | <10ms Input Latency           │
└───────────────────────────┬───────────────────────────────────┘
                            │ (Events / Channels)
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                    CORE GO ENGINE (v4)                        │
│                                                               │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐  │
│   │  TUI Model   │────►│  HiveMind    │────►│  Validator   │  │
│   │  (State)     │     │ (Goroutines) │     │ (Compiled-in)│  │
│   └──────────────┘     └──────┬───────┘     └──────────────┘  │
│                               │                               │
└───────────────────────────────┼───────────────────────────────┘
                                │ (IPC Bridge / Native)
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                      CAPABILITY LAYER                         │
│                                                               │
│  ┌──────────────┐   ┌────────────────┐   ┌─────────────────┐  │
│  │   Neurons    │   │    IT Mode     │   │   AI Neurons    │  │
│  │ (Go-Native)  │   │ (Go-Registry)  │   │ (Python Bridge) │  │
│  └──────────────┘   └────────────────┘   └─────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

## 4. Component Details

### 4.1 Go TUI (internal/tui)
- **Engine**: Charm Bubble Tea (The Elm Architecture in Go).
- **Styling**: Lipgloss for adaptive, responsive UI elements.
- **State**: Centralized `Model` struct with concurrent message handling.

### 4.2 HiveMind v4.0 (internal/hivemind)
- **Execution**: Every workflow step (Node) runs via goroutines.
- **Storage**: Honeycomb SQLite backend for workflow persistence and memory.
- **Event Bus**: Broadcasts execution updates to the TUI in real-time.

### 4.3 Constitutional AI (internal/core/validator)
- **Hardness**: Principles are constant strings compiled into the binary.
- **Validator**: Optimized regex engine performing input/output checks without Python overhead.

### 4.4 Python Bridge (internal/bridge)
- **Protocol**: JSON-L (JSON lines) over standard I/O.
- **Management**: Go spawns and monitors Python bridge servers as sub-processes.
- **Resilience**: Automatic restart of bridge servers on failure.

---

## 5. Performance Metrics

| Metric | v3 (Python) | v4 (Go) | Improvement |
|--------|-------------|---------|-------------|
| **Startup Time** | 2.5s - 5.0s | **~45ms** | ~100x |
| **Memory (Idle)** | 150MB+ | **~12MB** | ~12x |
| **Input Latency** | 20ms - 100ms | **<5ms** | ~20x |
| **Binary Size** | N/A (Venv ~300MB) | **4.4MB** | ~70x |

---

## 6. Security Model
1. **Zero Trust**: Bridge processes are strictly isolated.
2. **Immutability**: The Go core cannot be modified by external scripts or the AI.
3. **Static Analysis**: Go's type system prevents many class-of-vulnerabilities common in Python implementations.

---

---
