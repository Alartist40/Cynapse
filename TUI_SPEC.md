# TUI_SPEC.md — Cynapse Interface Specification (OpenCode-Inspired)

**Version**: 3.0.0  
**Date**: 2026-02-03  
**Inspiration**: OpenCode (minimalism), Claude Code (execution transparency), Claude Teams (multi-agent)  
**Goal**: Beautiful, minimal interface with powerful multi-agent orchestration

---

## Executive Summary

**Design Philosophy**: 
> "Invisible until needed, beautiful when visible, powerful when used."

Combine OpenCode's **minimal command-palette interface** with Claude Code's **execution transparency** and Claude Teams' **multi-agent chat splitting**. Add Cynapse's unique **neural personality** through loading states and thinking indicators.

**Key Principles**:
1. **Zero clutter**: Empty space is feature, not bug
2. **Command palette as gateway**: `/` reveals all power
3. **Transparent execution**: See AI think, code, and execute
4. **Multi-agent visibility**: Subagents as parallel chat threads
5. **Keyboard-first**: Every action has a shortcut
6. **Unique personality**: Cynapse neural aesthetics (pulsing, synaptic)

---

## Part 1: Layout Architecture

### 1.1 Default View (Minimal)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                                                                 │
│                      [Empty Workspace]                          │
│                                                                 │
│                                                                 │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  🐝 Cynapse  —  How can I help you today?                       │
│  > _                                                            │
├─────────────────────────────────────────────────────────────────┤
│  [●] Elara-3B  ∿ thinking...     [Ctrl+I] Info  [/] Tools       │
└─────────────────────────────────────────────────────────────────┘
```

**Elements**:
- **Main area**: Empty by default, fills with conversation
- **Input bar**: Bottom, always visible, `>` prompt
- **Status bar**: Bottom-most, model selector + state + shortcuts

### 1.2 Active Conversation View

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  👤 Add JWT authentication to the API                          │
│                                                                 │
│  🐝 I'll help you add JWT authentication. Let me start by     │
│     examining the current API structure...                      │
│                                                                 │
│     ∿ thinking...                                               │
│                                                                 │
│     💭 The user wants JWT auth. I should:                      │
│        1. Check existing auth structure                        │
│        2. Add PyJWT dependency                                 │
│        3. Create auth middleware                               │
│        4. Add login endpoint                                   │
│                                                                 │
│     🔧 Reading src/api/routes.py...                            │
│                                                                 │
│     │ 1  from flask import Flask                               │
│     │ 2  from flask_jwt_extended import JWTManager             │
│     │ 3                                                      │
│     │ 4  app = Flask(__name__)                                 │
│     │ 5  jwt = JWTManager(app)                                 │
│                                                                 │
│     ✓ Created src/auth/jwt_handler.py                          │
│                                                                 │
│  [Apply] [Test] [Explain] [Regenerate]                         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  > _                                                            │
├─────────────────────────────────────────────────────────────────┤
│  [●] Elara-3B  ○ ready     [Ctrl+I] Info  [/] Tools  [↑] Hist  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Multi-Agent View (HiveMind Active)

When HiveMind spawns subagents, conversation splits into threads:

```
┌─────────────────────────────────────────────────────────────────┐
│  🐝 LEAD (You)              │  🔍 RESEARCHER        │  💻 CODER    │
│  ───────────────────────────┼───────────────────────┼────────────│
│                             │                       │              │
│  👤 Analyze codebase        │  ∿ scanning...        │  ⏳ waiting  │
│                             │                       │              │
│  🐝 Breaking this down...   │  📄 Found 3 auth      │              │
│                             │     patterns          │              │
│  🔍 Researcher: Found       │  ✓ Complete           │  🚀 Starting │
│     patterns in:            │                       │              │
│     - src/auth/             │                       │  💭 JWT vs   │
│     - tests/test_auth.py    │                       │     Session? │
│                             │                       │              │
│  💻 Coder: Implementing...  │                       │  🔧 Writing  │
│                             │                       │     handler  │
│                             │                       │              │
├─────────────────────────────┴───────────────────────┴────────────┤
│  > _ (message all)  [Tab] Switch thread  [Enter] Focus thread   │
├─────────────────────────────────────────────────────────────────┤
│  [●] HiveMind  ∿ 3 agents active  [Ctrl+I] Info  [/] Tools      │
└─────────────────────────────────────────────────────────────────┘
```

**Interaction**:
- `Tab` cycles between agent threads
- `Enter` focuses specific thread for detailed interaction
- Input bar shows context: "message all" vs "message Researcher"
- Each thread shows own thinking/code/output stream

---

## Part 2: Visual Design System

### 2.1 Color Palette (Cynapse Neural Theme)

**Core Colors**:
```
Background:      #0A0A0F (Deep Space)
Surface:         #12121A (Panel)
Border:          #2A2A3A (Subtle)

Text Primary:    #E4E4E7 (White)
Text Secondary:  #71717A (Gray)
Text Muted:      #52525B (Dark Gray)

Accent Primary:  #8B5CF6 (Purple - Cynapse brand)
Accent Secondary:#06B6D4 (Cyan - AI/Thinking)
Accent Success:  #10B981 (Green - Success)
Accent Warning:  #F59E0B (Amber - Warning)
Accent Error:    #EF4444 (Red - Error)
```

**Semantic Usage**:
- **Purple (#8B5CF6)**: Brand, model selector, active state
- **Cyan (#06B6D4)**: AI thinking, processing, neural activity
- **Green (#10B981)**: Success, completion, file saved
- **Amber (#F59E0B)**: Warning, attention needed
- **Red (#EF4444)**: Error, breach, critical

### 2.2 Typography & Icons

**Font**: System monospace + Nerd Font icons (fallback to ASCII)

**Icon Set**:
```
🐝 Cynapse/Lead Agent
🔍 Researcher Agent  
💻 Coder Agent
🧪 Tester Agent
👤 User
∿ Thinking/Processing (animated wave)
💭 Thought process
🔧 Tool execution
📄 File reference
✓ Success
⚠ Warning
✗ Error
● Active model
○ Ready/Idle
⏳ Waiting
🚀 Starting
```

**Animation States**:
- **Thinking**: `∿` (cyan, pulsing)
- **Processing**: `◐` (rotating)
- **Executing**: `▹` (sliding)
- **Complete**: `✓` (green, solid)

### 2.3 Component Styles

**Input Bar**:
```
┌─────────────────────────────────────────────────────────────────┐
│  > _                                                            │
└─────────────────────────────────────────────────────────────────┘
```
- `>`: Prompt symbol (purple when active, gray when idle)
- `_`: Cursor (blinking cyan)
- Background: Slightly lighter than main bg

**Status Bar**:
```
[●] Elara-3B  ∿ thinking...     [Ctrl+I] Info  [/] Tools  [↑] Hist
```
- Left: Model indicator + state
- Right: Keyboard shortcuts (muted)
- Dynamic: Changes based on context

**Code Block**:
```
│ 1  import jwt
│ 2  from datetime import datetime, timedelta
│ 3  
│ 4  def create_token(user_id: str) -> str:
│ 5      payload = {"user_id": user_id, "exp": datetime.utcnow() + timedelta(hours=24)}
│ 6      return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
│
[Apply] [Copy] [Test] [Explain]
```
- Left border: Purple accent
- Line numbers: Muted gray
- Syntax: Highlighted keywords
- Actions: Inline buttons

**Tool Execution**:
```
🔧 pip install pyjwt
   Collecting pyjwt
     Downloading PyJWT-2.8.0-py3-none-any.whl (22 kB)
     Installing collected packages: pyjwt
   Successfully installed pyjwt-2.8.0
   ✓ Complete (2.3s)
```
- Command: Amber
- Output: Gray
- Success: Green checkmark + timing

---

## Part 3: Command Palette (/)

Press `/` to open command palette—gateway to all functionality.

### 3.1 Palette Interface

```
┌─────────────────────────────────────────────────────────────────┐
│  > /                                                            │
├─────────────────────────────────────────────────────────────────┤
│  🔧 Tools                                                       │
│     @file        Include file in context                        │
│     @folder      Include folder structure                       │
│     @web         Fetch URL content                              │
│                                                                 │
│  ⚙️  Settings                                                   │
│     /model       Change AI model                                │
│     /theme       Change color theme                             │
│     /skills      Manage agent skills                            │
│     /new         Start new conversation                         │
│                                                                 │
│  🐝 HiveMind                                                    │
│     /agent       Spawn subagent                                 │
│     /mode        Switch mode (chat/agent/train)                 │
│     /bees        View active bees                               │
│                                                                 │
│  💻 System                                                      │
│     /terminal    Open terminal panel                            │
│     /clear       Clear conversation                             │
│     /export      Export chat history                            │
│     /quit        Exit Cynapse                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Quick Commands

Type `/` then:

| Command | Action |
|---------|--------|
| `/gpt4` | Switch to GPT-4 model |
| `/elara` | Switch to Elara model |
| `/dark` | Dark theme |
| `/light` | Light theme |
| `/new` | New conversation (keep history) |
| `/clear` | Clear screen (keep context) |
| `/agent <role>` | Spawn subagent (researcher/coder/tester) |
| `/mode agent` | Enter multi-agent mode |
| `/mode chat` | Return to single chat |

### 3.3 Context Mentions (@)

In any message, type `@` to include context:

```
> @src/main.py @docs/api.md Add error handling to the login function
```

**Types**:
- `@filename` — Include file
- `@folder/` — Include folder tree
- `@url` — Fetch and include web content
- `@history` — Include conversation summary

---

## Part 4: Keyboard Shortcuts

### 4.1 Global Shortcuts

| Key | Action |
|-----|--------|
| `/` | Open command palette |
| `Ctrl+I` | Toggle info/help overlay |
| `Ctrl+P` | Command palette (alternate) |
| `Ctrl+N` | New conversation |
| `Ctrl+Shift+N` | New window |
| `Ctrl+Q` | Quit |
| `Esc` | Close palette/overlay, return to input |
| `↑/↓` | Navigate history (in input) |

### 4.2 Input Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line |
| `Ctrl+A` | Select all |
| `Ctrl+C` | Copy selection |
| `Ctrl+V` | Paste |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Tab` | Accept autocomplete |
| `Ctrl+Space` | Trigger autocomplete |

### 4.3 Multi-Agent Shortcuts

| Key | Action |
|-----|--------|
| `Tab` | Cycle agent threads |
| `Shift+Tab` | Reverse cycle |
| `Ctrl+1/2/3` | Jump to thread N |
| `Enter` | Focus selected thread |
| `Backspace` | Return to "message all" |
| `Ctrl+A` | Message all agents |

### 4.4 Terminal Shortcuts (when focused)

| Key | Action |
|-----|--------|
| `Ctrl+C` | Interrupt |
| `Ctrl+D` | EOF |
| `Ctrl+L` | Clear |
| `↑/↓` | History |
| `Ctrl+\`` | Toggle terminal visibility |

---

## Part 5: Info/Help Overlay (Ctrl+I)

### 5.1 Overlay Design

```
┌─────────────────────────────────────────────────────────────────┐
│  CYPnase v1.2.0                              [Ctrl+I] Close [X] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ⌨️  KEYBOARD SHORTCUTS                                         │
│  ─────────────────────                                          │
│  /              Command palette                                 │
│  Ctrl+I         Toggle this help                                │
│  Ctrl+N         New conversation                                │
│  ↑/↓            Message history                                 │
│  Tab            Cycle agents (in multi-agent)                   │
│                                                                 │
│  🤖 CURRENT MODEL                                               │
│  ─────────────────                                              │
│  Name:          Elara-3B                                        │
│  Provider:      Local (HiveMind)                                │
│  Context:       4,096 tokens                                    │
│  Used:          1,247 tokens                                    │
│  Temperature:   0.7                                             │
│                                                                 │
│  🐝 HIVEMIND STATUS                                             │
│  ──────────────────                                             │
│  Mode:          Chat                                            │
│  Active Bees:   0                                               │
│  Queen:         Online                                          │
│                                                                 │
│  📁 WORKSPACE                                                   │
│  ────────────                                                   │
│  Path:          /home/user/projects/cynapse                     │
│  Files:         42                                              │
│  Git:           main* (2 modified)                              │
│                                                                 │
│  ⚙️  SYSTEM                                                     │
│  ─────────                                                      │
│  Platform:      Linux x64                                       │
│  Python:        3.10.12                                         │
│  Memory:        2.4GB / 16GB                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Sections

1. **Keyboard Shortcuts**: All available shortcuts
2. **Current Model**: Active model info, token usage
3. **HiveMind Status**: Mode, active bees, queen status
4. **Workspace**: Current directory, file count, git status
5. **System**: Platform, Python version, memory usage

---

## Part 6: Execution Transparency

### 6.1 Thought Streaming

Show AI's reasoning process in real-time:

```
💭 I need to add JWT authentication. Let me think through this:
   1. First, check if there's existing auth code...
   2. Look for requirements.txt to see dependencies...
   3. The user probably wants PyJWT, not authlib...

   Actually, I should check the current API structure first.
```

**Display rules**:
- Collapsible (click to expand/collapse)
- Italic, muted color
- Stream in real-time as AI generates
- Can be disabled in settings

### 6.2 Tool Execution

Show every tool call and result:

```
🔧 read_file(path="src/api/routes.py")
   ✓ Read 45 lines (1.2KB)

🔧 write_file(path="src/auth/jwt.py", content="...")
   ✓ Created file (320 bytes)

🔧 shell(command="pip install pyjwt")
   Collecting pyjwt...
   Successfully installed pyjwt-2.8.0
   ✓ Exit code 0 (2.3s)

🔧 edit_file(path="src/api/routes.py", old="...", new="...")
   ✓ Applied 3 changes
```

**Format**:
- Tool icon + name + arguments
- Output (truncated if > 10 lines, with "... [show more]")
- Success/failure indicator
- Timing for performance visibility

### 6.3 Code Generation

Stream code as it's generated:

```
💻 Generating src/auth/jwt_handler.py...

│ 1  import jwt
│ 2  from datetime import datetime, timedelta
│ 3  from typing import Optional
│ 4  
│ 5  SECRET_KEY = "your-secret-key"  # Change in production
│ 6  
│ 7  def create_token(user_id: str, expires_hours: int = 24) -> str:
│ 8      """Create a new JWT token for user."""
│ 9      payload = {
│ 10         "user_id": user_id,
│ 11         "exp": datetime.utcnow() + timedelta(hours=expires_hours),
│ 12         "iat": datetime.utcnow()
│ 13     }
│ 14     return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
│ 15 
│ 16 def verify_token(token: str) -> Optional[dict]:
│ 17     """Verify and decode a JWT token."""
│ 18     try:
│ 19         return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
│ 20     except jwt.ExpiredSignatureError:
│ 21         return None
│ 22     except jwt.InvalidTokenError:
│ 22         return None

✓ Complete (14 lines)

[Apply] [Copy] [Test] [Explain] [Regenerate]
```

---

## Part 7: Multi-Agent Interface (HiveMind)

### 7.1 Agent Thread Display

Each subagent gets own thread panel:

```
┌─────────────────────────────────────────────────────────────────┐
│  🐝 Lead        │  🔍 Researcher    │  💻 Coder       │  🧪 Tester│
│  ───────────────┼───────────────────┼─────────────────┼──────────│
│                 │                   │                 │          │
│  👤 Add auth    │  ∿ scanning...    │  ⏳ queued      │  ⏳ queued│
│                 │                   │                 │          │
│  🐝 Breaking    │  📄 Found:        │                 │          │
│     down...     │     - Basic auth  │                 │          │
│                 │     - API keys    │                 │          │
│                 │     - No JWT yet  │                 │          │
│                 │                   │                 │          │
│                 │  ✓ Done (12s)     │  🚀 Starting... │          │
│                 │                   │                 │          │
│                 │                   │  💭 Using       │          │
│                 │                   │     PyJWT...    │          │
│                 │                   │                 │          │
├─────────────────┴───────────────────┴─────────────────┴──────────┤
│  > _ [message all agents]  [Tab] Switch  [Enter] Focus          │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Thread States

| State | Indicator | Description |
|-------|-----------|-------------|
| **Queued** | `⏳` | Waiting for dependencies |
| **Thinking** | `∿` | AI reasoning |
| **Executing** | `🔧` | Running tools |
| **Active** | `●` | Working, no blocking |
| **Complete** | `✓` | Finished successfully |
| **Error** | `✗` | Failed, needs attention |

### 7.3 Interaction Model

**Global Input** (default):
- Message broadcast to all agents
- Lead agent coordinates
- Visible in all threads

**Focused Thread**:
- `Enter` on thread = focus
- Input goes only to that agent
- Other agents continue independently
- `Backspace` or `Esc` returns to global

**Thread Commands**:
- `/agent <role>` — Spawn new agent
- `/merge` — Merge thread back to lead
- `/kill` — Terminate agent

---

## Part 8: State Management

### 8.1 State Object

```python
@dataclass
class TUIState:
    # UI State
    show_palette: bool = False
    palette_query: str = ""
    palette_selection: int = 0
    show_help: bool = False
    active_thread: str = "lead"  # lead, agent_id, or "all"

    # Input
    input_buffer: str = ""
    cursor_position: int = 0
    input_history: List[str] = field(default_factory=list)
    history_index: int = -1

    # Conversation
    messages: List[Message] = field(default_factory=list)
    threads: Dict[str, List[Message]] = field(default_factory=dict)  # agent_id -> messages
    streaming_message: Optional[Message] = None

    # Model
    current_model: str = "elara"
    model_state: str = "ready"  # ready, thinking, executing
    token_usage: int = 0

    # System
    theme: str = "dark"
    workspace_path: Path = Path(".")
    git_branch: str = ""
    git_status: str = ""
```

### 8.2 State Transitions

```
IDLE → / → PALETTE_OPEN → select → execute → IDLE
IDLE → type → TYPING → Enter → SENDING → STREAMING → IDLE
IDLE → Ctrl+I → HELP_OPEN → Esc/Ctrl+I → IDLE
IDLE → Tab → THREAD_SWITCH (if multi-agent)
STREAMING → Ctrl+C → INTERRUPT → IDLE
```

---

## Part 9: Implementation Notes

### 9.1 Rendering Strategy

**Incremental Updates**:
- Only redraw changed lines
- Cursor position updates without full redraw
- Streaming text appends to buffer

**Animation**:
- Thinking indicator: 3-frame cycle (200ms)
- Progress bars: 10 segments, update on % change
- No full-screen animations (performance)

### 9.2 Backend Integration

**Streaming**:
```python
async def stream_response(prompt: str, thread_id: str):
    async for chunk in llm.generate_stream(prompt):
        if chunk.type == "thought":
            state.add_thought(thread_id, chunk.content)
        elif chunk.type == "tool_call":
            state.add_tool_call(thread_id, chunk.tool, chunk.args)
        elif chunk.type == "tool_result":
            state.add_tool_result(thread_id, chunk.result)
        elif chunk.type == "content":
            state.append_message(thread_id, chunk.content)

        renderer.refresh_thread(thread_id)
```

### 9.3 Performance Targets

- **Startup**: < 300ms
- **Input latency**: < 8ms
- **Render**: < 16ms
- **Memory**: < 50MB base
- **Streaming**: 60fps for text, 30fps for UI updates

---

## Part 10: Migration from v2.0

### Changes

| v2.0 (IDE-style) | v3.0 (OpenCode-style) |
|------------------|-----------------------|
| Three fixed panels | Flexible threads |
| File tree always visible | Command palette access |
| Terminal panel | Overlay terminal |
| Static layout | Dynamic multi-agent |
| Biological colors | Neural purple/cyan |

### Migration

1. Remove panel layout system
2. Implement command palette (`/`)
3. Add thread-based conversation
4. Implement streaming display
5. Add execution transparency
6. Update color scheme
7. Implement help overlay

---

## Appendix: Quick Reference

### Commands

```
/               Open palette
/model <name>   Switch model
/theme <name>   Switch theme
/new            New conversation
/clear          Clear screen
/agent <role>   Spawn agent
/mode <mode>    Switch mode
/quit           Exit
```

### Shortcuts

```
Ctrl+I          Help/Info
Ctrl+N          New conversation
Ctrl+P          Palette
Ctrl+C          Interrupt
Tab             Next thread
Shift+Tab       Prev thread
Esc             Close/Cancel
↑/↓             History
```

---

*"Invisible power, visible craftsmanship."*
