"""
Cynapse TUI Layout

Four-zone layout architecture for the Synaptic Fortress Interface.
"""

import os
import sys
from typing import Tuple, Optional
from .colors import Colors, DEEP_PURPLE, RESET, BOLD


class Terminal:
    """Terminal utilities for the TUI."""
    
    @staticmethod
    def get_size() -> Tuple[int, int]:
        """Get terminal size as (columns, rows)."""
        try:
            size = os.get_terminal_size()
            return size.columns, size.lines
        except OSError:
            return 80, 24  # Default fallback (minimum supported)
    
    @staticmethod
    def clear():
        """Clear the terminal screen."""
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
    
    @staticmethod
    def move_cursor(row: int, col: int):
        """Move cursor to specified position (1-indexed)."""
        sys.stdout.write(f"\033[{row};{col}H")
        sys.stdout.flush()
    
    @staticmethod
    def hide_cursor():
        """Hide the terminal cursor."""
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
    
    @staticmethod
    def show_cursor():
        """Show the terminal cursor."""
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
    
    @staticmethod
    def enable_raw_mode():
        """Enable raw terminal mode for instant key response."""
        if sys.platform != 'win32':
            import tty
            import termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setraw(fd)
            return old_settings
        return None
    
    @staticmethod
    def disable_raw_mode(old_settings):
        """Restore terminal settings."""
        if sys.platform != 'win32' and old_settings:
            import termios
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class Box:
    """Box drawing utilities."""
    
    # Unicode box drawing characters
    HORIZONTAL = "═"
    VERTICAL = "║"
    TOP_LEFT = "╔"
    TOP_RIGHT = "╗"
    BOTTOM_LEFT = "╚"
    BOTTOM_RIGHT = "╝"
    T_DOWN = "╦"
    T_UP = "╩"
    T_RIGHT = "╠"
    T_LEFT = "╣"
    CROSS = "╬"
    
    # Single line variants
    H_THIN = "─"
    V_THIN = "│"
    TL_THIN = "┌"
    TR_THIN = "┐"
    BL_THIN = "└"
    BR_THIN = "┘"
    
    @classmethod
    def horizontal_line(cls, width: int, thick: bool = True) -> str:
        """Create a horizontal line."""
        char = cls.HORIZONTAL if thick else cls.H_THIN
        return char * width
    
    @classmethod
    def draw_box(cls, width: int, height: int, title: str = "", thick: bool = True) -> list:
        """
        Generate lines for a box.
        
        Args:
            width: Box width in characters
            height: Box height in lines
            title: Optional title for top border
            thick: Use thick box characters
            
        Returns:
            List of strings, one per line
        """
        h = cls.HORIZONTAL if thick else cls.H_THIN
        v = cls.VERTICAL if thick else cls.V_THIN
        tl = cls.TOP_LEFT if thick else cls.TL_THIN
        tr = cls.TOP_RIGHT if thick else cls.TR_THIN
        bl = cls.BOTTOM_LEFT if thick else cls.BL_THIN
        br = cls.BOTTOM_RIGHT if thick else cls.BR_THIN
        
        lines = []
        
        # Top border with optional title
        if title:
            title_space = width - 4  # Account for corners and padding
            if len(title) > title_space:
                title = title[:title_space-3] + "..."
            left_pad = 2
            right_pad = width - 2 - left_pad - len(title)
            top = f"{tl}{h * left_pad}{title}{h * right_pad}{tr}"
        else:
            top = f"{tl}{h * (width - 2)}{tr}"
        lines.append(top)
        
        # Middle lines (empty)
        for _ in range(height - 2):
            lines.append(f"{v}{' ' * (width - 2)}{v}")
        
        # Bottom border
        lines.append(f"{bl}{h * (width - 2)}{br}")
        
        return lines


class Layout:
    """
    Four-zone layout manager for the TUI.
    
    Zone 1: PERIMETER (Top Status Bar) - 1 line
    Zone 2: SENTINEL GRID (Left Sidebar) - 25-30% width
    Zone 3: ACTIVATION CHAMBER (Top-right) - Dynamic
    Zone 4: OPERATIONS BAY (Bottom-right) - Dynamic
    Footer: Command line - 1 line
    """
    
    MIN_WIDTH = 80
    MIN_HEIGHT = 24
    SENTINEL_WIDTH_PERCENT = 0.28  # 28% for sentinel grid
    
    def __init__(self):
        self._cols, self._rows = Terminal.get_size()
        self._cached_zones = None
        self._last_size = (self._cols, self._rows)
    
    def refresh_size(self):
        """Update cached terminal size."""
        self._cols, self._rows = Terminal.get_size()
        if (self._cols, self._rows) != self._last_size:
            self._cached_zones = None
            self._last_size = (self._cols, self._rows)
    
    @property
    def cols(self) -> int:
        return max(self._cols, self.MIN_WIDTH)
    
    @property
    def rows(self) -> int:
        return max(self._rows, self.MIN_HEIGHT)
    
    def get_zone_dimensions(self) -> dict:
        """
        Calculate dimensions for all zones.
        
        Returns:
            Dict with zone names as keys and (x, y, width, height) tuples
        """
        if self._cached_zones and (self._cols, self._rows) == self._last_size:
            return self._cached_zones
        
        # Zone 1: Perimeter (full width, 1 line at top)
        perimeter = (0, 0, self.cols, 1)
        
        # Footer (full width, 1 line at bottom)
        footer = (0, self.rows - 1, self.cols, 1)
        
        # Available space for zones 2-4
        content_height = self.rows - 3  # Minus perimeter, footer, and divider
        
        # Zone 2: Sentinel Grid (left side)
        sentinel_width = int(self.cols * self.SENTINEL_WIDTH_PERCENT)
        sentinel = (0, 1, sentinel_width, content_height + 1)
        
        # Right side width
        right_width = self.cols - sentinel_width - 1  # -1 for border
        right_x = sentinel_width
        
        # Split right side between zones 3 and 4 (roughly 40/60)
        activation_height = int(content_height * 0.4)
        operations_height = content_height - activation_height
        
        # Zone 3: Activation Chamber (top right)
        activation = (right_x, 1, right_width, activation_height)
        
        # Zone 4: Operations Bay (bottom right)
        operations = (right_x, 1 + activation_height, right_width, operations_height + 1)
        
        self._cached_zones = {
            'perimeter': perimeter,
            'sentinel': sentinel,
            'activation': activation,
            'operations': operations,
            'footer': footer,
        }
        
        return self._cached_zones
    
    def render_frame(self) -> list:
        """
        Render the static frame/skeleton of the layout.
        
        Returns:
            List of strings, one per row
        """
        zones = self.get_zone_dimensions()
        frame = [' ' * self.cols for _ in range(self.rows)]
        
        # Perimeter header
        perimeter_title = f"[  ZONE 1: PERIMETER  ]"
        header_line = f"{DEEP_PURPLE}╔{'═' * (self.cols - 2)}╗{RESET}"
        frame[0] = header_line
        
        # Build main content area
        sentinel_width = zones['sentinel'][2]
        
        for row in range(1, self.rows - 1):
            # Left border
            line = f"{DEEP_PURPLE}║{RESET}"
            
            # Sentinel area content placeholder
            line += ' ' * (sentinel_width - 2)
            
            # Vertical divider
            line += f"{DEEP_PURPLE}║{RESET}"
            
            # Right area content placeholder
            right_width = self.cols - sentinel_width - 2
            line += ' ' * right_width
            
            # Right border
            line += f"{DEEP_PURPLE}║{RESET}"
            
            frame[row] = line
        
        # Footer
        footer_line = f"{DEEP_PURPLE}╚{'═' * (self.cols - 2)}╝{RESET}"
        frame[self.rows - 1] = footer_line
        
        return frame
    
    def render_perimeter(self, status_icon: str, integrity: float, 
                         voice_status: str, shard_status: str) -> str:
        """
        Render the perimeter status bar content.
        
        Args:
            status_icon: Security status icon (●, ∿, ✗)
            integrity: Integrity percentage
            voice_status: Voice monitor status icon
            shard_status: USB shard status string (●●○)
            
        Returns:
            Formatted status bar string
        """
        zones = self.get_zone_dimensions()
        width = zones['perimeter'][2] - 4  # Account for borders
        
        left_content = f" {status_icon} SECURE │ Integrity: {integrity:.0f}% "
        right_content = f" Voice: {voice_status} │ Shards: {shard_status} "
        
        # Calculate padding
        padding = width - len(left_content) - len(right_content)
        if padding < 0:
            padding = 1
        
        return left_content + (' ' * padding) + right_content
    
    def render_footer(self, mode: str, hints: list) -> str:
        """
        Render the command footer.
        
        Args:
            mode: Current mode name
            hints: List of (key, action) tuples for hints
            
        Returns:
            Formatted footer string
        """
        zones = self.get_zone_dimensions()
        width = zones['footer'][2] - 4
        
        hint_str = '  '.join(f"[{k}] {a}" for k, a in hints[:6])
        mode_str = f"[Mode: {mode}]"
        
        padding = width - len(hint_str) - len(mode_str)
        if padding < 0:
            hint_str = hint_str[:width - len(mode_str) - 4] + "..."
            padding = 1
        
        return ' ' + hint_str + (' ' * padding) + mode_str + ' '


# Global layout instance
_layout: Optional[Layout] = None


def get_layout() -> Layout:
    """Get the global layout instance."""
    global _layout
    if _layout is None:
        _layout = Layout()
    return _layout
