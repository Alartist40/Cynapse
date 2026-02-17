# TUI_SPEC.md — Cynapse Interface Specification (Ghost Shell)

**Version**: 4.0.0  
**Date**: 2026-02-17  
**Engine**: Charm Bubble Tea (Go)  
**Goal**: Flicker-free, high-performance terminal orchestration

---

## Executive Summary

**Design Philosophy**: 
> "Immediate response, functional elegance, architectural clarity."

Cynapse v4.0.0 migrates the TUI from Python's blocking loops to **Go's Bubble Tea (TEA)** architecture. This transition provides sub-10ms input latency and leverages Go's concurrency for real-time update streaming without TUI lag.

**Key Principles**:
1. **The Elm Architecture (TEA)**: Predictable state transitions (Model → View → Update).
2. **Lipgloss Components**: Adaptive layout and high-fidelity terminal styling.
3. **Async Event Bus**: Real-time HiveMind updates streamed via Go channels.
4. **Binary Embedding**: All icons, help files, and constitutional rules are compiled-in.
5. **Ultra-Low Overhead**: <20MB RAM footprint for the entire UI and core engine.

---

## Part 1: Layout Architecture (v4)

### 1.1 Model State View
The TUI is structured as a single Model that manages:
- **Navigation**: Command Palette vs. Chat View.
- **Components**: Threaded chat history, input field, and help overlay.
- **Events**: Incoming messages from HiveMind or Neuron execution.

### 1.2 Layout Composition
```
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│                     THREADED CHAT VIEW                        │
│  [Lead] Message A                                             │
│  [Meerkat] Port Scan Result: 22, 80 open                      │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│  > _ [Input Field]                                            │
├───────────────────────────────────────────────────────────────┤
│  v4.0.0 | HiveMind: Active | [Ctrl+H] Help | [/] Commands     │
└───────────────────────────────────────────────────────────────┘
```

---

## Part 2: Visual Design System

### 2.1 Color Palette (v4 Neural Theme)
Managed via Lipgloss adaptive styles.

| Symbol | Color | Purpose |
|--------|-------|---------|
| **Brand** | Purple (`#8B5CF6`) | Main borders, headers, and highlights. |
| **Think** | Cyan (`#06B6D4`) | Processing indicators and neural feedback. |
| **Alert** | Amber (`#F59E0B`) | Warnings or IT Mode requires attention. |
| **Fatal** | Red (`#EF4444`) | System errors or security violations. |

---

## Part 3: Command Palette (/)

The command palette is implemented as a filtered list overlay.

### 3.1 Integrated Commands
- `/help`: Show integrated help menu.
- `/clear`: Flush current chat state.
- `/model`: Select active LLM (Elara, GPT-4, etc.).
- `/it`: Enter IT Support Mode for specialized diagnostics.
- `/hive`: Launch a HiveMind workflow Bee.
- `/exit`: Terminate application gracefully.

---

## Part 4: Performance Targets (v4)

| Metric | Target | Result |
|--------|--------|--------|
| **Startup** | < 100ms | **~6ms** |
| **Input Latency** | < 10ms | **<1ms** |
| **Render Rate** | 60fps | **60fps** |
| **Memory** | < 30MB | **~5.6MB** |

---

## Part 5: Implementation Notes

### 5.1 Concurrency Model
The TUI runs in a dedicated goroutine. Interaction with the HiveMind engine occurs through a thread-safe **Event Bus**.
- **Commands**: TUI sends `Msg` structs to the engine.
- **Updates**: Engine sends `Event` structs back to the TUI; TUI updates its `Model` and triggers a re-render.

### 5.2 Build Integration
Styles are defined as static Lipgloss constants to avoid runtime CSS-style parsing overhead.

---

*"Architected for speed, designed for clarity."*
