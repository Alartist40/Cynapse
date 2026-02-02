"""
Cynapse TUI Color Palette

ANSI 256 color definitions for the Synaptic Fortress Interface.
Based on the Purple Dynasty theme with Electric Blue accents.
"""

# Primary - Purple Dynasty (Mystery, Security, Authority)
DEEP_PURPLE = "\033[38;5;93m"       # Headers, borders, section titles
SYNAPSE_VIOLET = "\033[38;5;141m"   # Charged pathways, standby states
ACTIVE_MAGENTA = "\033[38;5;201m"   # Active signals, live connections
ROYAL_PURPLE = "\033[38;5;129m"     # Accent highlights

# Secondary - Electric Blue (Data, Information, Flow)
CYAN_ELECTRIC = "\033[38;5;51m"     # Active data, ready states
DEEP_BLUE = "\033[38;5;27m"         # Secondary borders, dividers
CYBER_BLUE = "\033[38;5;33m"        # Informational text
MUTED_BLUE = "\033[38;5;67m"        # Secondary text, timestamps

# Complement - Alert Gold/Amber (Action Required, Complete)
COMPLEMENT_GOLD = "\033[38;5;220m"  # Success, completion, fused synapses
WARNING_AMBER = "\033[38;5;178m"    # Processing, oscillation, standby
BREACH_RED = "\033[38;5;196m"       # Critical intrusion, system breach
INTERRUPT_ORANGE = "\033[38;5;208m" # Warnings, manual intervention needed

# Neutral - Matter (Inactivity, Background)
DORMANT_GRAY = "\033[38;5;245m"     # Inactive neurons, disabled paths
WHITE_MATTER = "\033[38;5;255m"     # Primary text, labels

# Background colors
BG_DEEP_NAVY = "\033[48;5;17m"      # Deep navy background
BG_BREACH_RED = "\033[48;5;52m"     # Breach alert background

# Reset
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
BLINK = "\033[5m"  # Use sparingly - accessibility concerns


class Colors:
    """Color utilities for the TUI."""
    
    # Semantic color mappings
    HEADER = DEEP_PURPLE
    BORDER = DEEP_PURPLE
    ACTIVE = CYAN_ELECTRIC
    STANDBY = SYNAPSE_VIOLET
    SUCCESS = COMPLEMENT_GOLD
    WARNING = WARNING_AMBER
    ERROR = BREACH_RED
    TEXT = WHITE_MATTER
    MUTED = DORMANT_GRAY
    HIGHLIGHT = ACTIVE_MAGENTA
    
    @staticmethod
    def colorize(text: str, color: str) -> str:
        """Wrap text in ANSI color codes."""
        return f"{color}{text}{RESET}"
    
    @staticmethod
    def header(text: str) -> str:
        """Style text as a header."""
        return f"{BOLD}{DEEP_PURPLE}{text}{RESET}"
    
    @staticmethod
    def success(text: str) -> str:
        """Style text as success."""
        return f"{COMPLEMENT_GOLD}{text}{RESET}"
    
    @staticmethod
    def error(text: str) -> str:
        """Style text as error."""
        return f"{BREACH_RED}{text}{RESET}"
    
    @staticmethod
    def warning(text: str) -> str:
        """Style text as warning."""
        return f"{WARNING_AMBER}{text}{RESET}"
    
    @staticmethod
    def active(text: str) -> str:
        """Style text as active/running."""
        return f"{CYAN_ELECTRIC}{text}{RESET}"
    
    @staticmethod
    def muted(text: str) -> str:
        """Style text as muted/secondary."""
        return f"{DORMANT_GRAY}{text}{RESET}"
    
    @staticmethod
    def check_color_support() -> bool:
        """Check if terminal supports 256 colors."""
        import os
        colorterm = os.environ.get('COLORTERM', '')
        term = os.environ.get('TERM', '')
        return colorterm in ('truecolor', '24bit') or '256' in term
    
    @staticmethod
    def high_contrast_mode() -> bool:
        """Check if high contrast mode is enabled."""
        import os
        return os.environ.get('CYNAPSE_HIGH_CONTRAST', '0') == '1'
