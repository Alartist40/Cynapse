**TUI.md**

```markdown
# Cynapse TUI Specification
## The Synaptic Fortress Interface

**Version**: 1.0  
**Status**: Specification Ready for Implementation  
**Theme**: Cyberpunk-Biological Fusion (Purple Dynasty)

---

## 1. Design Philosophy

### 1.1 Core Concept
The Cynapse TUI is not a dashboard—it is a **neural security operations center**. Every pixel serves the narrative of a biological-digital fortress that is **alive, watching, and armed**.

The interface treats the computer as an organism:
- **Perimeter**: The nervous system (threat detection)
- **Sentinels**: The immune system (defense neurons)
- **Activation**: The synaptic cleft (authentication/assembly)
- **Operations**: The cortex (cognition/RAG processing)

### 1.2 Inspirations
- **Claude Code**: Minimalist inline status, efficient character usage, zero-bloat information density
- **Fastfetch**: System awareness display, aesthetic ASCII art integration
- **Ghost in the Shell**: Bio-digital fusion, synaptic pathway visualization
- **Pharmacological interfaces**: Medical clean-room precision meets cyberpunk mystery

### 1.3 Efficiency Constraints
- **No Unicode block bars**: Redrawing 50-character progress bars is CPU-expensive
- **Static skeletons, moving pulses**: Update 1-3 characters per animation frame, not entire lines
- **Three-color discipline**: Deep purple (authority), electric blue (data), gold (alerts)

---

## 2. Visual Language System

### 2.1 Color Palette (ANSI 256)

```yaml
# Primary - Purple Dynasty (Mystery, Security, Authority)
DEEP_PURPLE:        "\033[38;5;93m"    # Headers, borders, section titles
SYNAPSE_VIOLET:     "\033[38;5;141m"   # Charged pathways, standby states
ACTIVE_MAGENTA:     "\033[38;5;201m"   # Active signals, live connections
ROYAL_PURPLE:       "\033[38;5;129m"   # Accent highlights

# Secondary - Electric Blue (Data, Information, Flow)
CYAN_ELECTRIC:      "\033[38;5;51m"    # Active data, ready states
DEEP_BLUE:          "\033[38;5;27m"    # Secondary borders, dividers
CYBER_BLUE:         "\033[38;5;33m"    # Informational text
MUTED_BLUE:         "\033[38;5;67m"    # Secondary text, timestamps

# Complement - Alert Gold/Amber (Action Required, Complete)
COMPLEMENT_GOLD:    "\033[38;5;220m"   # Success, completion, fused synapses
WARNING_AMBER:      "\033[38;5;178m"   # Processing, oscillation, standby
BREACH_RED:         "\033[38;5;196m"   # Critical intrusion, system breach
INTERRUPT_ORANGE:   "\033[38;5;208m"   # Warnings, manual intervention needed

# Neutral - Matter (Inactivity, Background)
DORMANT_GRAY:       "\033[38;5;245m"   # Inactive neurons, disabled paths
WHITE_MATTER:       "\033[38;5;255m"   # Primary text, labels
DEEP_BACKGROUND:    "\033[48;5;17m"    # Deep navy background (optional)
```

### 2.2 Symbol Dictionary (Universal Semantic Layer)

These symbols must maintain consistent meaning across all interface modes:

| Symbol | Name | Meaning | State |
|--------|------|---------|-------|
| `●` | ACTIVE_SIGNAL | Action potential traveling, current flowing | Live, processing, in-motion |
| `▸` | CHARGED_PATHWAY | Myelinated pathway, ready to fire, standby | Armed, charged, awaiting trigger |
| `○` | DORMANT_SYNAPSE | Resting potential, -70mV, inactive | Offline, sleeping, disabled |
| `✓` | SYNAPSE_FUSED | Vesicles released, action complete, success | Finished, verified, secure |
| `∿` | OSCILLATING | Feedback loop, learning, plasticity in progress | Training, adapting, processing |
| `✗` | BREACH | Synaptic failure, intrusion detected, apoptosis | Error, breach, compromised |
| `⚠` | WARNING | Threshold potential approached, caution | Alert, attention required |
| `►` | CURSOR | Selection indicator, current focus | Navigation marker |

### 2.3 Status Tags (Inline Metadata)

Appended to lines or sections to indicate operational state:

```yaml
[running]:    Amber  # Currently processing, active computation
[complete]:   Gold   # Done, success state
[standby]:    Gray   # Waiting for trigger or input
[arrested]:   Red    # Error state, blocked, security halt
[pruning]:    Purple # Cleanup operations, optimization
[arming]:     Blue   # Preparing for activation, charging
[dormant]:    Gray   # Powered but inactive, sleeping
```

---

## 3. Layout Architecture

### 3.1 The Four Security Zones

The interface is strictly divided into four zones, reflecting the security architecture:

```
╔═══════════════════════════════════════════════════════════════════════════[  ZONE 1: PERIMETER  ]══╗
║ Global system status, integrity monitoring, breach alerts                        [Top Bar - Always]   ║
╠════════════════════════════════╦════════════════════════════════════════════════════════════════════╣
║ ZONE 2: SENTINEL GRID          ║  ZONE 3: ACTIVATION CHAMBER                                      ║
║ [Defense Neurons]              ║  Dynamic visualization area                                      ║
║ Left 25% of screen             ║  Top-right, 50% width                                            ║
║ Toggle switches, status        ║  Context-aware: Assembly/Pharmacode/Maintenance                  ║
║                                ║                                                                  ║
║                                ║  ─────────────────────────────────────────────────────────────   ║
║                                ║  ZONE 4: OPERATIONS BAY (RAG Laboratory)                         ║
║                                ║  Bottom-right, remaining space                                   ║
║                                ║  Document ingestion, AI chat, training controls                  ║
╠════════════════════════════════╩════════════════════════════════════════════════════════════════════╣
║ [h] Help  [v] Voice  [s] Scan  [L] Lockdown  [:q] Back  [Q] Quit              [Command Footer]      ║
╚════════════════════════════════════════════════════════════════════════════════════════════════════╝
```

### 3.2 Zone Specifications

#### Zone 1: PERIMETER (Top Status Bar)
- **Height**: 1 line (single row)
- **Content**: 
  - Security status icon (`●` Secure, `∿` Scanning, `✗` Breach)
  - Integrity percentage (checksum validation)
  - Last breach timestamp
  - Voice monitor status (`○` Off, `▸` Standby, `●` Listening)
  - USB Shard status (`●●○` format showing 2/3 mounted)
- **Behavior**: 
  - Static for 90% of operations
  - Flashing red background (`\033[48;5;52m`) during breach
  - Amber pulse during scanning operations
  - Updates only on state change (no continuous redraw)

#### Zone 2: SENTINEL GRID (Left Sidebar)
- **Width**: 25-30% of terminal width
- **Content List**:
  - Individual neuron entries (► rhino_gateway [○] dormant)
  - Contextual alerts (`└ Alert: Injection Vuln!` in amber)
  - Quick-action hints (`[h] Help [s] Scan [L] Lock`)
- **Interaction**:
  - Arrow keys/hjkl navigate the list
  - `Enter` toggles neuron active/dormant
  - `Space` quick-arm/disarm
  - Visual feedback: Active neurons glow purple `●`, dormant fade to gray `○`
- **Items**: Minimum 12 neurons (scrolling if terminal too short)

#### Zone 3: ACTIVATION CHAMBER (Dynamic Visualization)
- **Location**: Top-right quadrant
- **Purpose**: Visual feedback for long-running operations
- **Modes** (automatically detected):
  1. **NEURAL_ASSEMBLY**: USB shard combination, synaptic connection diagrams
  2. **PHARMACODE_INJECTION**: Model loading, training progress (8-segment bars)
  3. **MAINTENANCE_MODE**: Simple horizontal axons, system idle
  4. **BREACH_ALERT**: Full-screen red overlay, intrusion details

#### Zone 4: OPERATIONS BAY (RAG Laboratory)
- **Location**: Bottom-right, remaining space
- **Purpose**: The "safe workspace" for AI interaction
- **Components**:
  - Document ingestion list (last 3-4 feeds with `✓` status)
  - Training progress (if active)
  - Chat/query interface
  - Queen response area with citation links
- **Visual**: Blue-dominant (calm, cognitive), minimal purple accents

### 3.3 Command Footer (Bottom)
- **Height**: 1 line
- **Content**: 
  - Global hotkey legend (always visible)
  - Current mode indicator (`[Mode: PHARMACODE_INJECT]`)
  - Context-sensitive hints change based on active zone

---

## 4. Control Scheme

### 4.1 Global Hotkeys (One-Touch Access)
Available from any screen, immediate action:

| Key | Action | Safety |
|-----|--------|--------|
| `h` | Help overlay | None (safe) |
| `v` | Voice Wake (toggle 18kHz monitor) | Requires 3s hold to deactivation |
| `s` | Security Scan (audit all perimeters) | Immediate |
| `L` | Emergency Lockdown (capital L) | Requires Shift (hard to accidental) |
| `Q` | Quit system (capital Q) | Requires Shift, clears RAM shards |
| `:q` or `Esc` | Back / Close modal / Return to previous | Vim-standard |
| `Ctrl+C` | Force interrupt (graceful degradation) | Signal handler |

### 4.2 Navigation (Vim-Inspired + Accessible)
Standard movement across all zones:

| Input | Action |
|-------|--------|
| `h` / `←` | Move left / previous item |
| `j` / `↓` | Move down / next item |
| `k` / `↑` | Move up / previous item |
| `l` / `→` | Move right / select item |
| `Enter` | Activate/Confirm current selection |
| `Space` | Toggle state (on/off, expand/collapse) |
| `Tab` | Cycle between zones (Perimeter→Sentinel→Activation→Operations) |
| `gg` | Jump to top (Sentinel Grid) |
| `G` | Jump to bottom (Operations Bay) |

### 4.3 Contextual Controls

**Sentinel Grid Specific:**
- `a` - Arm all dormant sentinels
- `d` - Disarm all (return to dormant)
- `r` - Reload neuron manifests
- `1-9` - Quick-select neuron by number

**Operations Bay Specific:**
- `i` - Insert/chat mode (like vim insert)
- `Ctrl+F` - Feed document to Queen (RAG ingestion)
- `Ctrl+T` - Start training mode
- `Ctrl+D` - Delete document from index

---

## 5. Interface Modes

### 5.1 Mode A: NEURAL_ASSEMBLY (Ghost Shell Activation)
**Trigger**: USB shard insertion, `v` key (voice wake initiated)

**Visual**:
```
NEURAL_ASSEMBLY MODE
PRE_01 >───────●───────> POST_01  ✓ [complete]
         ╲
          ╲ 2.3ms latency
           ╲
PRE_02 >──────●────────> POST_02  ▸ [charging]
         ╲
          ╲ decrypting shard_02...
           ╲
PRE_03 >──────○────────> POST_03  ○ [standby]

SYNAPTIC_CHARGE: 66% │ THROUGHPUT: 847Mb/s │ NODES: 2/3
```

**Characteristics**:
- Diagonal lines (`╲`) represent synaptic clefts (gaps between neurons)
- Signal `●` travels left-to-right (3-4 character updates, not full redraw)
- When complete, changes to `✓` and shifts from Cyan to Gold
- Bottom stats line updates only when values change

### 5.2 Mode B: PHARMACODE_INJECTION (Model Loading/Training)
**Trigger**: AI model loading, document ingestion, training epochs

**Visual**:
```
CYNAPSE // SERUM_INJECTION v2.4
═══════════════════════════════════════════════════

AMPULE_A  [TiDAR_DIFFUSION]    
[████▒▒▒▒]  45%  ∿  [running]  // dispersing...
> uptake_rate: 847MB/s
> receptor_saturation: nominal

AMPULE_B  [ROPE_EMBEDDINGS]    
[████████]  100%  ✓  [complete]  // fused
> myelination: complete

AMPULE_C  [EXPERT_MoE]    
[▒▒▒▒▒▒▒▒]  0%  ○  [standby]  // awaiting...

VISCOSITY: 1.2cp │ pH: 7.35 │ TEMP: 310K
```

**Characteristics**:
- Only 8 segments (`█` vs `▒`), not 50 (minimal redraw)
- Pharmacological metrics (viscosity, pH, temperature) for cyber-bio flavor
- `∿` spinner rotates (`| / - \`) for active loading
- Progress segments fill as data loads, but cursor only updates changed blocks

### 5.3 Mode C: OPERATIONS (RAG Laboratory)
**Trigger**: Document analysis, AI chat, idle research mode

**Visual**:
```
┌─[OPERATIONS BAY: HiveMind RAG]────────────────────────────────────┐
│ STATUS: ● Queen Active │ Docs: 147 │ Training: ░░░░░░ 0%           │
├─────────────────────────────────────────────────────────────────────┤
│ > RAG System ready. 147 documents indexed.                          │
│                                                                     │
│ 📁 Recent Feeds:                                                    │
│   ├─ security_audit_2026.pdf    [✓ embedded]                        │
│   ├─ research_notes.md          [✓ embedded]                        │
│   ├─ codebase_architecture.txt  [✓ embedded]                        │
│   └─ ... and 144 more                                             │
│                                                                     │
│ prompt: How do I mitigate the command injection in beaver_miner?    │
│                                                                     │
│ 🐝 Queen: Based on your security_audit_2026.pdf...                  │
│           [View Source] [Generate Patch]                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Characteristics**:
- Blue-dominant (calm, cognitive workspace)
- Document list shows ingestion status (`✓` = embedded in vector DB)
- Chat interface mimics terminal prompt (`prompt:`)
- Citations link back to source documents

### 5.4 Mode D: PERIMETER BREACH (Emergency)
**Trigger**: Security audit failure, intrusion detection, integrity violation

**Visual**:
```
╔═══════════════════════════════════════════════════════════════════╗
║ ██ PERIMETER BREACH DETECTED ██                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  ⚠ CRITICAL: neurons/beaver_miner/verifier.py                     ║
║     └─ Command Injection Vector (CVE-2024-XXXX)                   ║
║                                                                    ║
║  AUTO-DEFENSE ACTIVATED:                                          ║
║  > wolverine_redteam  [●] ACTIVE                                  ║
║  > canary_token       [●] DEPLOYED                                ║
║                                                                    ║
║  [Enter] Isolate Threat  [s] Full Audit  [L] Emergency Lockdown   ║
║                                                                    ║
╚═══════════════════════════════════════════════════════════════════╝
```

**Characteristics**:
- Red background flash (`\033[48;5;52m`) with gold text
- Overrides all other zones (full-screen modal)
- Automatic sentinel activation (shown in list)
- Cannot be dismissed without action (security constraint)

---

## 6. Animation System Specification

### 6.1 The "Thinking Dot" Protocol
**Purpose**: Indicate activity without CPU-heavy progress bars

**Implementation**:
```
Line state: [running]
Animation:  ● (bright cyan) → ∙ (dim gray) → ● (bright cyan)
Cycle:      500ms              500ms           500ms
Chars:      Single character toggle, minimal redraw

Line state: [standby]
Animation:  ○ (static, dormant gray)
Chars:      No animation, zero CPU usage
```

### 6.2 Signal Propagation (Neural Mode)
**Purpose**: Show data travel without redrawing entire pathway

**Implementation**:
- Pathway string: `>───────●───────>`
- Update only the position of `●` (one character change per tick)
- Wave effect: `●` bright, adjacent characters `▸` (dim) trail behind
- Frame rate: 4fps maximum (250ms updates) to prevent terminal flicker

### 6.3 Pharmacode Pulse (Loading Mode)
**Purpose**: Indicate processing with minimal graphics

**Implementation**:
- Spinner: `∿` character rotates through `|`, `/`, `-`, `\`
- Updates inline after percentage: `[45% ∿]`
- No bar redrawing, only the spinner character changes

---

## 7. Help System (Overlay)

**Trigger**: `h` key from any screen

**Behavior**: Semi-transparent overlay (dim colors) over current screen

**Content**:
```
╔═══════════════════════════════════════════════════════════════════╗
║  CYNAPSE COMMAND REFERENCE          [h] Help  [:q] Close          ║
╠═══════════════════════════════════════════════════════════════════╣
║  GLOBAL CONTROLS                                                  ║
║   h          Help overlay (this screen)                           ║
║   v          Voice wake - toggle 18kHz whistle monitor            ║
║   s          Security audit - immediate integrity scan            ║
║   L          Emergency lockdown (Shift+L) - isolate all          ║
║   Q          Quit system (Shift+Q) - secure wipe and exit        ║
║   :q / Esc   Back / Close modal / Return to previous             ║
║                                                                    ║
║  NAVIGATION                                                        ║
║   hjkl       Move cursor (vim-style)                              ║
║   Arrows     Move cursor (accessible alternative)                 ║
║   Enter      Activate / Confirm selection                         ║
║   Space      Toggle state (on/off for sentinels)                  ║
║   Tab        Cycle between screen zones                           ║
║                                                                    ║
║  SENTINEL GRID (Left Panel)                                        ║
║   a          Arm all dormant sentinels                            ║
║   d          Disarm all sentinels (return to dormant)             ║
║   r          Reload neuron manifests                              ║
║                                                                    ║
║  OPERATIONS BAY (RAG Laboratory)                                   ║
║   i          Insert/chat mode (start typing to AI)                ║
║   Ctrl+F     Feed document to Queen (RAG ingestion)               ║
║   Ctrl+T     Start training mode on fed documents                 ║
║                                                                    ║
║  STATUS SYMBOLS                                                    ║
║   ● Active Signal    ▸ Charged Pathway    ○ Dormant Synapse       ║
║   ✓ Complete/Fused   ∿ Oscillating        ✗ Breach/Error          ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## 8. Implementation Notes for Developers

### 8.1 Rendering Strategy
- **Library**: `rich` (Python) recommended for layout management
- **Update Policy**: Render static elements once, update only dynamic characters
- **Animation FPS**: Cap at 4fps (250ms) to prevent terminal flicker and CPU waste
- **Color Detection**: Check `$COLORTERM` for truecolor support, fallback to 256-color

### 8.2 State Management
- **Single Source of Truth**: `CynapseState` class holds:
  - Current mode (Assembly/Pharmacode/Operations/Breach)
  - Sentinel states (dict of neuron_id → status)
  - Assembly progress (percentage, shard status)
  - Operations data (document list, chat history)
- **Observer Pattern**: UI updates triggered by state changes, not polling

### 8.3 Input Handling
- **Raw Mode**: Terminal must be in raw mode for instant key response (no Enter required)
- **Key Buffer**: 50ms debounce on rapid keypresses
- **Interrupt Safety**: `Ctrl+C` must always return to clean state (reset terminal, wipe temp)

### 8.4 Security Integration
- **Audit Trail**: Every UI action logged to `.cynapse/logs/audit.ndjson`:
  ```json
  {"timestamp": 1234567890, "event": "ui_action", "data": {"key": "L", "zone": "global"}}
  ```
- **Lockdown Visual**: When `L` pressed, immediate full-screen red flash before actual lockdown logic

---

## 9. Accessibility Considerations

- **High Contrast Mode**: Environment variable `CYNAPSE_HIGH_CONTRAST=1` forces white-on-black, removes dim grays
- **Screen Reader**: Semantic labels in brackets (e.g., `[STATUS: SECURE]`) for parsing
- **No Blink**: Avoid `\033[5m` (blink ANSI code), use color/brightness changes instead
- **Minimum Size**: Design for 80x24 (standard terminal), graceful degradation below 80 columns

---

## 10. Future Expansion Points

- **Split Mode**: Allow horizontal/vertical splitting of Operations Bay (multiple document views)
- **Macro Recording**: Record `h` `j` `Enter` sequences as automated playbooks
- **Remote View**: SSH-friendly mode (monochrome, no Unicode drawing chars)
- **Touch Support**: For tablet deployments (larger hit targets, on-screen keyboard hints)

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-21  
**Author**: Compiler (System Architect)  
**Status**: Ready for Implementation
```

This specification document provides your team with everything needed to implement the visuals: exact color codes, layout diagrams, symbol meanings, animation specifications, and interaction patterns. The structure separates the "what" (visual design) from the "how" (implementation notes) so both designers and developers can work from the same source.