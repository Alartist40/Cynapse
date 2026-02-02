# TUI Architecture Specification: Cynapse Unified Hub

## 1. UX Philosophy
- **Paradigm**: Modern, reactive TUI with a persistent dashboard and modal interaction.
- **Unified Interface**: Merges the Hub's orchestration (`cynapse.py`) and HiveMind's AI capabilities (`hivemind.py`) into a single screen.
- **Keyboard-First**: Navigation via `hjkl` or Arrows, shortcut keys (`v` for Voice, `a` for Assembly).
- **Responsiveness**: Async updates for background tasks (e.g., waiting for whistle detection, model assembly).

## 2. Layout Architecture
```
┌──────────────────────────────────────────────────────────────────┐
│ Cynapse Hub v1.0 [STATUS: GHOST SHELL DISCONNECTED]        [?]   │
├───────────────────┬──────────────────────────────────────────────┤
│ NEURONS           │  DASHBOARD / ACTIVE SESSION                  │
│ [🦡] Meerkat      │                                              │
│ [🐦] Canary       │  > Ghost Shell Status: ⚪ SHARD 1 [OK]       │
│ [🐺] Wolverine    │  > Ghost Shell Status: 🔴 SHARD 2 [MISSING]  │
│ [🦏] Rhino        │  > Ghost Shell Status: ⚪ SHARD 3 [OK]       │
│ [🐙] Octopus      │                                              │
│ [🐘] Elephant     │  ------------------------------------------  │
│ [🦫] Beaver       │  HIVE MIND (QUEEN):                          │
│ [🌙] Elara        │  "Enter query or whistle to start..."        │
│                   │                                              │
│                   │  User: How do I scan for CVEs?               │
│                   │  Queen: I recommend using the Meerkat neuron.│
│                   │                                              │
├───────────────────┴──────────────────────────────────────────────┤
│ [v] Voice On  [s] Settings  [l] Logs  [q] Quit     [SYSTEM IDLE] │
└──────────────────────────────────────────────────────────────────┘
```

## 3. Component Hierarchy

### 3.1 Core Components (Powered by Textual)
- **CynapseApp**: Main application container managing state and event routing.
- **NeuronSidebar**: A `ListView` of available security tools with real-time status indicators.
- **TerminalConsole**: A `RichLog` widget capturing stdout/stderr from active neurons and audit events.
- **ChatWidget**: A specialized input/output component for the HiveMind AI ecosystem.
- **StatusFooter**: A `Footer` widget showing mnemonic keyboard shortcuts and system health.

### 3.2 Widget Specifications
| Widget | Library (Textual) | Purpose |
|--------|------------------|---------|
| Sidebar | `ListView` | Quick neuron switching and status icons |
| Chat Console | `ScrollableContainer` | Threaded conversation with Queen/Drones |
| Audit Feed | `RichLog` | Real-time view of `audit.ndjson` entries |
| Settings Modal| `ModalScreen` | Configuration of whistle frequency, API keys |

## 4. Technology Stack Recommendation

**Recommendation: Textual (Python)**
- **Rationale**:
    - **Async-Native**: Built on `asyncio`, perfect for long-running tasks like model assembly or voice listening without freezing the UI.
    - **CSS Styling**: Allows for "Cynapse Green" or "Ghost Shell Dark" themes without manual ANSI math.
    - **Legacy GUI Replacement**: Replaces the removed `devale` GUI with a more efficient, keyboard-driven alternative.
    - **Zero-Dependency (almost)**: Only depends on `rich`, fitting the minimal bloat strategy.

## 5. Migration Strategy

### 5.1 Orchestration Abstraction
Refactor `CynapseHub` to be a backend class:
- **hub_backend.py**: Business logic (discovery, execution, logging).
- **hub_tui.py**: Textual interface that calls `backend.run_neuron()`.
- **hub_cli.py**: Legacy CLI for minimal environments.

### 5.2 Feature Parity Roadmap
| GUI/CLI Feature | TUI Equivalent | Priority |
|-----------------|----------------|----------|
| Neuron Selection | Sidebar + Filter ( `/` ) | P0 |
| Model Assembly | Center Panel Animation + Status | P0 |
| AI Chat | Dedicated Chat Tab/Pane | P1 |
| Audit Log View | Live Scrollable Feed Panel | P2 |

## 6. Dependency Analysis
- **New Dependency**: `textual` (≈ 2.5 MB including dependencies).
- **Total Impact**: Minimal compared to current GUI libraries (like Tkinter or Qt), while providing 10x the functionality.

## 7. Accessibility & UX Details
- **Dynamic Resizing**: Dashboard automatically collapses sidebar on small terminals.
- **Visual Cues**: Color-coded neuron statuses (Green: Verified, Yellow: Unsigned, Red: Error).
- **Acoustic Feedback**: Visual "ripple" effect when 18 kHz whistle is detected.
