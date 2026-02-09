# Cynapse Architecture Reference

**Version**: 3.0.0
**Date**: 2026-02-09
**Status**: Production Ready

---

## 1. Executive Summary

Cynapse v3.0.0 introduces a major architectural shift towards **Self-Modifying AI** (IT Mode) and **Constitutional Safeguards** (Core Values), accessed via a completely redesigned **Command-Palette TUI**.

### Key Achievements in v3.0.0

1.  **Redesigned TUI**: Minimalist, command-palette driven interface inspired by OpenCode.
2.  **IT Mode**: Self-repairing tech support modules that evolve with new issues.
3.  **Core Values**: Immutable constitutional guardrails for AI safety.
4.  **Multi-Agent HiveMind**: Interactive agent threads (Lead, Researcher, Coder).

---

## 2. Directory Structure

### Complete File Tree

```
Cynapse/
├── cynapse_entry.py              # [ENTRY] Main executable
├── cynapse/                      # [PACKAGE] Main application package
│   ├── core/                     # [CORE] Business logic
│   │   ├── hivemind.py           # HiveMind - Workflow & Agent Engine
│   │   ├── core_values/          # [NEW] Constitutional AI
│   │   │   ├── validator.py      # Validator logic
│   │   │   └── constitution.md   # Immutable principles
│   │   ├── tech_support/         # [NEW] IT Mode (Self-Modifying)
│   │   │   ├── modules/          # IT Modules (image_fix, etc.)
│   │   │   └── registry/         # Module metadata
│   │   └── agent/                # [AGENT] Multi-agent system
│   │
│   ├── tui/                      # [UI] New TUI Architecture
│   │   ├── main.py               # Main loop
│   │   ├── state.py              # UI State (Redux-like)
│   │   ├── view.py               # Renderer
│   │   └── terminal.py           # Raw terminal handling
│   │
│   └── neurons/                  # [TOOLS] Security neurons (Legacy + New)
│
└── workflows/                    # [WORKFLOWS] HiveMind definitions
```

---

## 3. High-Level Architecture

### The Tri-Layer Brain

```
┌───────────────────────────────────────────────────────────────┐
│                     USER INTERFACE (TUI)                      │
│  Command Palette | Threaded Chat | Minimalist Visuals         │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                     CORE AGENTIC LOGIC                        │
│                                                               │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐  │
│   │  Lead Agent  │────►│  HiveMind    │────►│  Core Values │  │
│   │ (Orchestrate)│     │ (Execute)    │     │ (Safeguard)  │  │
│   └──────────────┘     └──────┬───────┘     └──────────────┘  │
│                               │                               │
└───────────────────────────────┼───────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                      CAPABILITY LAYER                         │
│                                                               │
│  ┌──────────────┐   ┌────────────────┐   ┌─────────────────┐  │
│  │   Neurons    │   │    IT Mode     │   │   External      │  │
│  │ (Sec Tools)  │   │ (Self-Repair)  │   │ (Shell/Files)   │  │
│  └──────────────┘   └────────────────┘   └─────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

## 4. Component Details

### 4.1 The New TUI (cynapse.tui)

**Philosophy**: "Invisible until needed."
- **Command Palette (`/`)**: Main entry point for actions.
- **Threaded View**: Conversations split into sub-threads for different agents.
- **State Management**: React-like state object in `state.py`.
- **Renderer**: Diff-based rendering for performance in `view.py`.

### 4.2 Core Values (cynapse.core.core_values)

**Purpose**: Prevent AI drift and ensure safety.
- **Constitution**: `constitution.md` (Signed & Immutable).
- **Validator**: Regex and logic checks on every Input/Output.
- **Enforcement**: HiveMind injects validator into every node execution context.

### 4.3 IT Mode (cynapse.core.tech_support)

**Purpose**: Self-evolving technical support.
- **Modules**: Standalone python files in `modules/` that solve specific problems.
- **Registry**: JSON index of capabilities.
- **Execution**: `ITModeNode` in HiveMind dynamically loads and runs these modules.
- **Learning**: (Future) System will generate new modules based on solved issues.

### 4.4 HiveMind v3.0 (cynapse.core.hivemind)

**Evolution**:
- **v1**: Script runner.
- **v2**: Standard Workflow Engine (n8n style).
- **v3**: Agentic Orchestrator with Constitutional Guardrails.

**New Node Types**:
- `ITModeNode`: For executing tech support modules.
- `LLMNode` (Enhanced): Integrated with ConstitutionalValidator.

---

## 5. Security Model

### Constitutional Guards
1. **Input Validation**: Check for jailbreaks before processing.
2. **Output Validation**: Check for harmful content before display.
3. **Immutable Core**: Constitution cannot be changed by the AI.

### IT Mode Safety
1. **Sandboxing**: IT modules run with limited permissions.
2. **Registry Control**: Only signed/approved modules are loaded.
3. **Audit Logging**: All IT actions are logged to `cynapse/logs`.

---

## 6. Development

### Adding an IT Module
1. Create `cynapse/core/tech_support/modules/my_fix.py`.
2. Implement `execute(self, operation, **kwargs)`.
3. Add to `registry/index.json`.

### Extending TUI
1. Add state field to `TUIState` in `state.py`.
2. Add rendering logic to `Renderer` in `view.py`.
3. Handle input in `CynapseTUI` in `main.py`.

---
