"""
Cynapse TUI Keybindings

Global hotkeys and navigation controls for the Synaptic Fortress Interface.
"""

from dataclasses import dataclass
from typing import Dict, Callable, Optional
from enum import Enum


class KeyAction(Enum):
    """Named actions that can be triggered by keys."""
    # Global
    HELP = "help"
    VOICE_TOGGLE = "voice_toggle"
    SECURITY_SCAN = "security_scan"
    LOCKDOWN = "lockdown"
    QUIT = "quit"
    BACK = "back"
    
    # Navigation
    MOVE_UP = "move_up"
    MOVE_DOWN = "move_down"
    MOVE_LEFT = "move_left"
    MOVE_RIGHT = "move_right"
    SELECT = "select"
    TOGGLE = "toggle"
    CYCLE_ZONE = "cycle_zone"
    JUMP_TOP = "jump_top"
    JUMP_BOTTOM = "jump_bottom"
    
    # Sentinel Grid
    ARM_ALL = "arm_all"
    DISARM_ALL = "disarm_all"
    RELOAD_MANIFESTS = "reload_manifests"
    QUICK_SELECT_1 = "quick_select_1"
    QUICK_SELECT_2 = "quick_select_2"
    QUICK_SELECT_3 = "quick_select_3"
    QUICK_SELECT_4 = "quick_select_4"
    QUICK_SELECT_5 = "quick_select_5"
    QUICK_SELECT_6 = "quick_select_6"
    QUICK_SELECT_7 = "quick_select_7"
    QUICK_SELECT_8 = "quick_select_8"
    QUICK_SELECT_9 = "quick_select_9"
    
    # Operations Bay
    INSERT_MODE = "insert_mode"
    FEED_DOCUMENT = "feed_document"
    START_TRAINING = "start_training"
    DELETE_DOCUMENT = "delete_document"


@dataclass
class KeyBinding:
    """A keybinding with its action and description."""
    key: str
    action: KeyAction
    description: str
    zone: Optional[str] = None  # None = global, or "sentinel", "operations"
    requires_shift: bool = False


# Global keybindings (available from any screen)
GLOBAL_BINDINGS = [
    KeyBinding("h", KeyAction.HELP, "Help overlay (this screen)"),
    KeyBinding("v", KeyAction.VOICE_TOGGLE, "Voice wake - toggle 18kHz whistle monitor"),
    KeyBinding("s", KeyAction.SECURITY_SCAN, "Security audit - immediate integrity scan"),
    KeyBinding("L", KeyAction.LOCKDOWN, "Emergency lockdown - isolate all", requires_shift=True),
    KeyBinding("Q", KeyAction.QUIT, "Quit system - secure wipe and exit", requires_shift=True),
    KeyBinding("\x1b", KeyAction.BACK, "Back / Close modal / Return to previous"),  # Escape
    KeyBinding(":", KeyAction.BACK, "Vim-style quit (followed by q)"),
]

# Navigation bindings
NAVIGATION_BINDINGS = [
    KeyBinding("h", KeyAction.MOVE_LEFT, "Move left / previous item"),
    KeyBinding("\x1b[D", KeyAction.MOVE_LEFT, "Move left (arrow)"),  # Left arrow
    KeyBinding("j", KeyAction.MOVE_DOWN, "Move down / next item"),
    KeyBinding("\x1b[B", KeyAction.MOVE_DOWN, "Move down (arrow)"),  # Down arrow
    KeyBinding("k", KeyAction.MOVE_UP, "Move up / previous item"),
    KeyBinding("\x1b[A", KeyAction.MOVE_UP, "Move up (arrow)"),  # Up arrow
    KeyBinding("l", KeyAction.MOVE_RIGHT, "Move right / select item"),
    KeyBinding("\x1b[C", KeyAction.MOVE_RIGHT, "Move right (arrow)"),  # Right arrow
    KeyBinding("\r", KeyAction.SELECT, "Activate / Confirm selection"),  # Enter
    KeyBinding(" ", KeyAction.TOGGLE, "Toggle state (on/off for sentinels)"),
    KeyBinding("\t", KeyAction.CYCLE_ZONE, "Cycle between screen zones"),  # Tab
    KeyBinding("g", KeyAction.JUMP_TOP, "Jump to top (gg)"),
    KeyBinding("G", KeyAction.JUMP_BOTTOM, "Jump to bottom", requires_shift=True),
]

# Sentinel Grid specific bindings
SENTINEL_BINDINGS = [
    KeyBinding("a", KeyAction.ARM_ALL, "Arm all dormant sentinels", zone="sentinel"),
    KeyBinding("d", KeyAction.DISARM_ALL, "Disarm all sentinels (return to dormant)", zone="sentinel"),
    KeyBinding("r", KeyAction.RELOAD_MANIFESTS, "Reload neuron manifests", zone="sentinel"),
    KeyBinding("1", KeyAction.QUICK_SELECT_1, "Quick-select neuron 1", zone="sentinel"),
    KeyBinding("2", KeyAction.QUICK_SELECT_2, "Quick-select neuron 2", zone="sentinel"),
    KeyBinding("3", KeyAction.QUICK_SELECT_3, "Quick-select neuron 3", zone="sentinel"),
    KeyBinding("4", KeyAction.QUICK_SELECT_4, "Quick-select neuron 4", zone="sentinel"),
    KeyBinding("5", KeyAction.QUICK_SELECT_5, "Quick-select neuron 5", zone="sentinel"),
    KeyBinding("6", KeyAction.QUICK_SELECT_6, "Quick-select neuron 6", zone="sentinel"),
    KeyBinding("7", KeyAction.QUICK_SELECT_7, "Quick-select neuron 7", zone="sentinel"),
    KeyBinding("8", KeyAction.QUICK_SELECT_8, "Quick-select neuron 8", zone="sentinel"),
    KeyBinding("9", KeyAction.QUICK_SELECT_9, "Quick-select neuron 9", zone="sentinel"),
]

# Operations Bay specific bindings
OPERATIONS_BINDINGS = [
    KeyBinding("i", KeyAction.INSERT_MODE, "Insert/chat mode (start typing to AI)", zone="operations"),
    KeyBinding("\x06", KeyAction.FEED_DOCUMENT, "Feed document to Queen (Ctrl+F)", zone="operations"),
    KeyBinding("\x14", KeyAction.START_TRAINING, "Start training mode (Ctrl+T)", zone="operations"),
    KeyBinding("\x04", KeyAction.DELETE_DOCUMENT, "Delete document from index (Ctrl+D)", zone="operations"),
]


class KeyHandler:
    """
    Handles key input and maps to actions.
    """
    
    def __init__(self):
        self._bindings: Dict[str, KeyBinding] = {}
        self._action_handlers: Dict[KeyAction, Callable] = {}
        self._gg_pending = False  # For gg command
        self._colon_pending = False  # For :q command
        self._current_zone = "global"
        
        # Load all bindings
        self._load_bindings()
    
    def _load_bindings(self):
        """Load all keybindings into the lookup dict."""
        all_bindings = (
            GLOBAL_BINDINGS + 
            NAVIGATION_BINDINGS + 
            SENTINEL_BINDINGS + 
            OPERATIONS_BINDINGS
        )
        for binding in all_bindings:
            # Store multiple bindings per key (zone-specific)
            key = f"{binding.zone or 'global'}:{binding.key}"
            self._bindings[key] = binding
    
    def set_zone(self, zone: str):
        """Set the current active zone for key handling."""
        self._current_zone = zone
    
    def register_handler(self, action: KeyAction, handler: Callable):
        """Register a handler function for an action."""
        self._action_handlers[action] = handler
    
    def handle_key(self, key: str) -> Optional[KeyAction]:
        """
        Handle a key press and return the action, if any.
        
        Args:
            key: The raw key string from terminal
            
        Returns:
            The KeyAction if found, None otherwise
        """
        # Handle multi-key sequences
        if self._gg_pending:
            self._gg_pending = False
            if key == 'g':
                return self._execute_action(KeyAction.JUMP_TOP)
            # If not 'g', fall through to normal handling
        
        if self._colon_pending:
            self._colon_pending = False
            if key == 'q':
                return self._execute_action(KeyAction.BACK)
            # If not 'q', fall through to normal handling
        
        # Check for sequence starters
        if key == 'g':
            self._gg_pending = True
            return None
        
        if key == ':':
            self._colon_pending = True
            return None
        
        # Look up binding: try zone-specific first, then global
        binding = self._bindings.get(f"{self._current_zone}:{key}")
        if not binding:
            binding = self._bindings.get(f"global:{key}")
        
        if binding:
            return self._execute_action(binding.action)
        
        return None
    
    def _execute_action(self, action: KeyAction) -> KeyAction:
        """Execute the handler for an action and return the action."""
        handler = self._action_handlers.get(action)
        if handler:
            try:
                handler()
            except Exception:
                pass  # Don't crash on handler errors
        return action
    
    def get_help_text(self, section: str = "all") -> str:
        """
        Generate help text for keybindings.
        
        Args:
            section: "global", "navigation", "sentinel", "operations", or "all"
            
        Returns:
            Formatted help text
        """
        lines = []
        
        bindings_map = {
            "global": ("GLOBAL CONTROLS", GLOBAL_BINDINGS),
            "navigation": ("NAVIGATION", NAVIGATION_BINDINGS),
            "sentinel": ("SENTINEL GRID (Left Panel)", SENTINEL_BINDINGS),
            "operations": ("OPERATIONS BAY (RAG Laboratory)", OPERATIONS_BINDINGS),
        }
        
        sections = [section] if section != "all" else bindings_map.keys()
        
        for sec in sections:
            if sec in bindings_map:
                title, bindings = bindings_map[sec]
                lines.append(f"  {title}")
                for b in bindings:
                    key_display = self._format_key(b.key)
                    lines.append(f"   {key_display:12} {b.description}")
                lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_key(key: str) -> str:
        """Format a key for display."""
        special_keys = {
            "\x1b": "Esc",
            "\r": "Enter",
            " ": "Space",
            "\t": "Tab",
            "\x1b[A": "↑",
            "\x1b[B": "↓",
            "\x1b[C": "→",
            "\x1b[D": "←",
            "\x06": "Ctrl+F",
            "\x14": "Ctrl+T",
            "\x04": "Ctrl+D",
        }
        return special_keys.get(key, key)


# Global key handler instance
_key_handler: Optional[KeyHandler] = None


def get_key_handler() -> KeyHandler:
    """Get the global key handler instance."""
    global _key_handler
    if _key_handler is None:
        _key_handler = KeyHandler()
    return _key_handler
