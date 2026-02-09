from .terminal import Terminal
from .state import TUIState, Colors, Symbols

class Renderer:
    """
    Handles rendering of the TUI based on the current state.
    """
    def __init__(self, terminal: Terminal):
        self.term = terminal
        
    def render(self, state: TUIState):
        """Main render loop"""
        # We don't clear the whole screen every frame to avoid flicker, 
        # but for simplicity in this MVP we might, or use optimized updates.
        # For now, clear is safer.
        self.term.clear()
        
        self.draw_layout(state)
        
        if state.show_help:
            self.draw_help_overlay(state)
            
        if state.show_palette:
            self.draw_command_palette(state)
            
        self.term.flush()
        
    def draw_layout(self, state: TUIState):
        """Draw the main layout borders and content"""
        h = self.term.height
        w = self.term.width
        
        # 1. Main Area (Conversation)
        # Using 3 lines for status + inputbar
        chat_height = h - 4 
        
        self.draw_thread_view(state, 1, 1, w, chat_height)
        
        # 2. Input Bar (Bottom - 2)
        self.draw_input_bar(state, 1, h - 2, w)
        
        # 3. Status Bar (Bottom)
        self.draw_status_bar(state, 1, h, w)
        
    def draw_thread_view(self, state: TUIState, x, y, w, h):
        """Render the active conversation thread"""
        messages = state.threads.get(state.active_thread, [])
        
        # Simple scrolling: show last N messages that fit
        # We need to calculate line wrapping for each message
        
        rendered_lines = []
        for msg in messages:
            # Header
            role_color = Colors.ACCENT_PURPLE if msg.role == 'assistant' else Colors.TEXT_PRIMARY
            role_icon = "🐝" if msg.role == 'assistant' else "👤"
            rendered_lines.append(f"{role_color}{role_icon} {msg.content.splitlines()[0] if msg.content else ''}{Colors.RESET}")
            
            # Content (wrapped)
            # Simplistic wrapping for now
            lines = msg.content.splitlines()
            if len(lines) > 1:
                for line in lines[1:]:
                     rendered_lines.append(f"  {Colors.TEXT_SECONDARY}{line}{Colors.RESET}")
            elif not lines:
                 pass # Empty content
            
            rendered_lines.append("") # Spacer
            
        # Slice to fit height
        visible_lines = rendered_lines[-(h-2):]
        
        # Draw border
        self.term.print_at(x, y, f"{Colors.BORDER}┌{'─' * (w-2)}┐{Colors.RESET}")
        for i in range(h-2):
            self.term.print_at(x, y+1+i, f"{Colors.BORDER}│{' ' * (w-2)}│{Colors.RESET}")
            
            # Draw content if available
            if i < len(visible_lines):
                line_content = visible_lines[i]
                # Strip ANSI for length calc (simplified)
                # This is tricky without a proper library, so we just print and hope.
                # Ideally, we calculate real length.
                self.term.print_at(x+2, y+1+i, line_content)
                
        self.term.print_at(x, y+h-1, f"{Colors.BORDER}└{'─' * (w-2)}┘{Colors.RESET}")

        # Empty state prompt
        if not messages:
            center_msg = "[Empty Workspace]"
            center_x = x + (w // 2) - (len(center_msg) // 2)
            center_y = y + (h // 2)
            self.term.print_at(center_x, center_y, f"{Colors.TEXT_MUTED}{center_msg}{Colors.RESET}")

    def draw_input_bar(self, state: TUIState, x, y, w):
        """Draw input area"""
        # Border
        self.term.print_at(x, y, f"{Colors.BORDER}├{'─' * (w-2)}┤{Colors.RESET}")
        
        # Prompt
        prompt = f"{Colors.ACCENT_PURPLE}{Symbols.PROMPT} {Colors.RESET}"
        self.term.print_at(x+2, y+1, prompt)
        
        # Input content
        input_text = state.input_buffer
        # Handle scrolling if too long (omitted for MVP)
        self.term.write(f"{Colors.TEXT_PRIMARY}{input_text}{Colors.RESET}")
        
        # Cursor
        if not state.show_palette: # Only show cursor if not in palette
            cursor_visual = f"{Colors.ACCENT_CYAN}_{Colors.RESET}"
            # self.term.write(cursor_visual) # In non-blocking, we might blink it
            # Using actual terminal cursor for now is easier for input sync
            # But the terminal class hides it. Let's fake it.
            cursor_x = x + 4 + state.cursor_position
            if cursor_x < w - 1:
                self.term.print_at(cursor_x, y+1, cursor_visual)

    def draw_status_bar(self, state: TUIState, x, y, w):
        """Draw global status"""
        # Format: [●] Model  Status  Shortcuts
        
        status_color = Colors.ACCENT_CYAN if state.model_state == "thinking" else Colors.TEXT_SECONDARY
        status_icon = Symbols.OSCILLATING if state.model_state == "thinking" else Symbols.DORMANT
        
        bar = f"{Colors.ACCENT_PURPLE}[{Symbols.ACTIVE}] {state.current_model}{Colors.RESET}  "
        bar += f"{status_color}{status_icon} {state.model_state}{Colors.RESET}"
        
        shortcuts = f"{Colors.TEXT_MUTED}  [Ctrl+I] Info  [/] Tools  [Ctrl+Q] Quit{Colors.RESET}"
        
        # Right align shortcuts
        padding = w - (len(state.current_model) + len(state.model_state) + 30) # Approx length
        if padding < 1: padding = 1
        
        self.term.print_at(x, y, f"{Colors.BORDER}└{'─' * (w-2)}┘{Colors.RESET}") # Bottom border
        # Actually status is INSIDE the last box in spec?
        # Spec says:
        # └─────────────────────────────────────────────────────────────────┘
        # [●] Elara-3B ...
        
        # Let's put it on the line of the bottom border? No, that looks messy.
        # Spec 1.1:
        # │  [●] Elara-3B ...                                             │
        # └─────────────────────────────────────────────────────────────────┘
        
        self.term.print_at(x+2, y-1, f"{bar}{' ' * padding}{shortcuts}")

    def draw_command_palette(self, state: TUIState):
        """Overlay command palette"""
        w = self.term.width
        h = self.term.height
        
        # Center box
        box_w = min(60, w - 4)
        box_h = 10
        x = (w - box_w) // 2
        y = (h - box_h) // 4
        
        # Clear area
        for i in range(box_h):
             self.term.print_at(x, y+i, " " * box_w)
             
        # Draw Box
        self.term.print_at(x, y, f"{Colors.BORDER}┌{'─' * (box_w-2)}┐{Colors.RESET}")
        self.term.print_at(x+2, y+1, f"{Colors.ACCENT_PURPLE}> {state.palette_query}{Colors.RESET}")
        self.term.print_at(x, y+2, f"{Colors.BORDER}├{'─' * (box_w-2)}┤{Colors.RESET}")
        
        options = [
            ("/agent researcher", "Spawn Research Agent"),
            ("/agent coder", "Spawn Coding Agent"),
            ("/model elara", "Switch to Elara"),
            ("/clear", "Clear Conversation"),
            ("/quit", "Exit")
        ]
        
        # Filter options
        filtered = [o for o in options if state.palette_query in o[0]]
        
        for i, (cmd, desc) in enumerate(filtered[:5]):
            prefix = f"{Colors.ACCENT_CYAN}➜{Colors.RESET}" if i == state.palette_selection else " "
            self.term.print_at(x+2, y+3+i, f"{prefix} {Colors.TEXT_PRIMARY}{cmd:<20} {Colors.TEXT_MUTED}{desc}{Colors.RESET}")
            
        self.term.print_at(x, y+box_h-1, f"{Colors.BORDER}└{'─' * (box_w-2)}┘{Colors.RESET}")

    def draw_help_overlay(self, state: TUIState):
        # Similar logic to palette but full screen info
        w = self.term.width
        h = self.term.height
        
        x = (w - 70) // 2
        y = (h - 20) // 2
        
        # Check bounds
        if x < 1: x = 1
        if y < 1: y = 1
        
        box_w = min(70, w-2)
        box_h = min(20, h-2)
        
        # Fill background
        for i in range(box_h):
            self.term.print_at(x, y+i, f"{Colors.SURFACE}{' ' * box_w}{Colors.RESET}")
            
        self.term.print_at(x, y, f"{Colors.BORDER}┌{'─'*(box_w-2)}┐{Colors.RESET}")
        self.term.print_at(x+2, y+1, f"{Colors.BOLD}CYNAPSE v3.0{Colors.RESET}")
        
        help_text = [
            "",
            "KEYBOARD SHORTCUTS",
            "──────────────────",
            "/           Open Command Palette",
            "Ctrl+I      Toggle Help",
            "Ctrl+Q      Quit",
            "Enter       Send Message",
            "",
            "Use /agent <role> to spawn subagents.",
            "Press Esc to close."
        ]
        
        for i, line in enumerate(help_text):
            self.term.print_at(x+4, y+3+i, line)
            
        self.term.print_at(x, y+box_h-1, f"{Colors.BORDER}└{'─'*(box_w-2)}┘{Colors.RESET}")
