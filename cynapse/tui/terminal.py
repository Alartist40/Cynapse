import sys
import tty
import termios
import fcntl
import os
import shutil
from typing import Optional

class Terminal:
    """
    Raw terminal mode for instant key response and rendering.
    """
    
    def __init__(self):
        self.old_settings = None
        self.width = 80
        self.height = 24
        self.update_size()

    def setup(self):
        """Enter raw mode"""
        fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(fd)
        tty.setraw(sys.stdin.fileno())
        # Non-blocking read
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        
        # Hide cursor initially
        self.hide_cursor()
        
    def restore(self):
        """Restore original terminal settings"""
        if self.old_settings:
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, self.old_settings)
            
            # Restore blocking read
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl & ~os.O_NONBLOCK)
            
        self.show_cursor()
        print("\033[0m") # Reset colors

    def update_size(self):
        """Get terminal dimensions"""
        size = shutil.get_terminal_size()
        self.width = size.columns
        self.height = size.lines

    def clear(self):
        """Clear screen"""
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    def move(self, x: int, y: int):
        """Move cursor to position (1-indexed)"""
        # Clamp to screen
        x = max(1, min(x, self.width))
        y = max(1, min(y, self.height))
        sys.stdout.write(f"\033[{y};{x}H")

    def write(self, text: str):
        """Write to buffer (no flush)"""
        sys.stdout.write(text)

    def flush(self):
        """Flush buffer to screen"""
        sys.stdout.flush()

    def print_at(self, x: int, y: int, text: str):
        """Move cursor and write text in one operation"""
        self.move(x, y)
        self.write(text)

    def hide_cursor(self):
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    def show_cursor(self):
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    def read_key(self, timeout: float = 0.05) -> Optional[str]:
        """Non-blocking key read"""
        import select
        
        fd = sys.stdin.fileno()
        r, w, e = select.select([fd], [], [], timeout)
        
        if r:
            try:
                ch = sys.stdin.read(1)
                if ch == '\x1b': # Escape sequence
                    # Read more to verify if it's a sequence
                    seq = ch
                    # Try to read next chars immediately
                    try:
                        seq += sys.stdin.read(2)
                        return seq
                    except IOError:
                        return ch
                return ch
            except IOError:
                return None
        return None
