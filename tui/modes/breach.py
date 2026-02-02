"""
Perimeter Breach Mode

Full-screen emergency overlay for security breaches.
Red alert with auto-defense activation display.
"""

from typing import List
from ..state import CynapseState
from ..colors import (
    BREACH_RED, COMPLEMENT_GOLD, CYAN_ELECTRIC, WHITE_MATTER,
    BG_BREACH_RED, RESET, BOLD
)
from ..symbols import WARNING, ACTIVE_SIGNAL


class BreachMode:
    """
    Renders the Perimeter Breach emergency overlay.
    
    Full-screen modal that cannot be dismissed without action.
    Shows threat details and auto-defense activations.
    """
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._tick = 0
    
    def render(self, state: CynapseState, threat_details: dict = None) -> List[str]:
        """
        Render the breach alert overlay.
        
        Args:
            state: Current application state
            threat_details: Dict with 'location', 'type', 'cve' etc.
            
        Returns:
            List of strings for full-screen overlay
        """
        lines = []
        
        # Top border
        lines.append(f"{BREACH_RED}╔{'═' * (self.width - 2)}╗{RESET}")
        
        # Flashing header (toggles based on tick)
        if self._tick % 2 == 0:
            header = f"{BG_BREACH_RED}{BOLD} ██ PERIMETER BREACH DETECTED ██ {RESET}"
        else:
            header = f"{BREACH_RED}{BOLD} ██ PERIMETER BREACH DETECTED ██ {RESET}"
        
        lines.append(self._box_line(self._center(header)))
        lines.append(f"{BREACH_RED}╠{'═' * (self.width - 2)}╣{RESET}")
        lines.append(self._box_line(""))
        
        # Threat details
        if threat_details is None:
            threat_details = {
                'location': 'unknown',
                'type': 'Security Violation',
                'cve': 'CVE-XXXX-XXXX'
            }
        
        warning = WARNING.colored()
        lines.append(self._box_line(f"  {warning} {COMPLEMENT_GOLD}CRITICAL:{RESET} {threat_details.get('location', 'Unknown Location')}"))
        lines.append(self._box_line(f"     └─ {threat_details.get('type', 'Unknown Threat')} ({threat_details.get('cve', 'No CVE')})"))
        lines.append(self._box_line(""))
        
        # Auto-defense status
        lines.append(self._box_line(f"  {WHITE_MATTER}AUTO-DEFENSE ACTIVATED:{RESET}"))
        
        defenses = [
            ("wolverine_redteam", "ACTIVE"),
            ("canary_token", "DEPLOYED"),
        ]
        
        for defense_name, defense_status in defenses:
            symbol = ACTIVE_SIGNAL.colored()
            lines.append(self._box_line(f"  > {defense_name:20} [{symbol}] {defense_status}"))
        
        lines.append(self._box_line(""))
        lines.append(self._box_line(""))
        
        # Action buttons
        actions = (
            f"  {CYAN_ELECTRIC}[Enter]{RESET} Isolate Threat  "
            f"{CYAN_ELECTRIC}[s]{RESET} Full Audit  "
            f"{BREACH_RED}[L]{RESET} Emergency Lockdown"
        )
        lines.append(self._box_line(actions))
        lines.append(self._box_line(""))
        
        # Bottom border
        lines.append(f"{BREACH_RED}╚{'═' * (self.width - 2)}╝{RESET}")
        
        # Pad to fill height (centered vertically)
        content_height = len(lines)
        if content_height < self.height:
            top_padding = (self.height - content_height) // 2
            bottom_padding = self.height - content_height - top_padding
            
            empty_line = f"{BREACH_RED}║{' ' * (self.width - 2)}║{RESET}"
            lines = [empty_line] * top_padding + lines + [empty_line] * bottom_padding
        
        return lines[:self.height]
    
    def _box_line(self, content: str) -> str:
        """Wrap content in box borders."""
        # Estimate visible length
        visible = content
        for code in [BREACH_RED, COMPLEMENT_GOLD, CYAN_ELECTRIC, WHITE_MATTER, 
                     BG_BREACH_RED, RESET, BOLD]:
            visible = visible.replace(code, '')
        
        padding = self.width - len(visible) - 2
        if padding < 0:
            content = content[:self.width - 5] + "..."
            padding = 0
        
        return f"{BREACH_RED}║{RESET}{content}{' ' * padding}{BREACH_RED}║{RESET}"
    
    def _center(self, text: str) -> str:
        """Center text within box width."""
        visible = text
        for code in [BREACH_RED, COMPLEMENT_GOLD, BG_BREACH_RED, RESET, BOLD]:
            visible = visible.replace(code, '')
        
        padding = (self.width - len(visible) - 2) // 2
        return ' ' * max(0, padding) + text
    
    def tick(self):
        """Advance animation by one tick."""
        self._tick += 1
