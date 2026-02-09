from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum, auto
from pathlib import Path

# Message types for chat
@dataclass
class Message:
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: float
    thread_id: str = "lead"
    metadata: Dict = field(default_factory=dict)

# Visual theme colors
class Colors:
    # Core Colors from Spec
    BACKGROUND = "\033[48;5;232m"  # #0A0A0F approx
    SURFACE = "\033[48;5;234m"     # #12121A approx
    BORDER = "\033[38;5;237m"      # #2A2A3A
    
    TEXT_PRIMARY = "\033[38;5;255m"   # White
    TEXT_SECONDARY = "\033[38;5;243m" # Gray
    TEXT_MUTED = "\033[38;5;240m"     # Dark Gray
    
    ACCENT_PURPLE = "\033[38;5;93m"   # Brand
    ACCENT_CYAN = "\033[38;5;51m"     # Thinking
    ACCENT_GREEN = "\033[38;5;48m"    # Success
    ACCENT_AMBER = "\033[38;5;214m"   # Warning
    ACCENT_RED = "\033[38;5;196m"     # Error
    
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

# Semantic Symbols
class Symbols:
    ACTIVE = "●"
    CHARGED = "▸"
    DORMANT = "○"
    FUSED = "✓"
    OSCILLATING = "∿"
    BREACH = "✗"
    WARNING = "⚠"
    CURSOR = "►"
    SHARD = "◆"
    PROMPT = ">"

@dataclass
class TUIState:
    # UI State
    show_palette: bool = False
    palette_query: str = ""
    palette_selection: int = 0
    show_help: bool = False
    active_thread: str = "lead"  # lead, or agent_id
    
    # Input
    input_buffer: str = ""
    cursor_position: int = 0
    input_history: List[str] = field(default_factory=list)
    history_index: int = -1
    
    # Conversation
    messages: List[Message] = field(default_factory=list)
    threads: Dict[str, List[Message]] = field(default_factory=dict)
    
    # Model
    current_model: str = "elara-3b"
    model_state: str = "ready"  # ready, thinking, executing
    
    # System
    running: bool = True
    
    def __post_init__(self):
        # Initialize default thread
        if "lead" not in self.threads:
            self.threads["lead"] = []

    def add_message(self, role: str, content: str, thread_id: str = None):
        import time
        t_id = thread_id or self.active_thread
        msg = Message(role=role, content=content, timestamp=time.time(), thread_id=t_id)
        
        if t_id not in self.threads:
            self.threads[t_id] = []
            
        self.threads[t_id].append(msg)
        self.messages.append(msg) # Global log
