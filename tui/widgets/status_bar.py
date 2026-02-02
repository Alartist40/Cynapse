"""
Status Bar Widget

Top perimeter status bar showing security status, integrity, and monitoring.
"""

from ..state import CynapseState, SecurityStatus
from ..colors import (
    DEEP_PURPLE, CYAN_ELECTRIC, COMPLEMENT_GOLD, BREACH_RED,
    WARNING_AMBER, DORMANT_GRAY, WHITE_MATTER, RESET, BG_BREACH_RED
)
from ..symbols import ACTIVE_SIGNAL, CHARGED_PATHWAY, DORMANT_SYNAPSE, BREACH, OSCILLATING


class StatusBar:
    """
    Renders the top perimeter status bar.
    
    Shows security status, integrity percentage, voice monitor,
    and USB shard status.
    """
    
    def __init__(self, width: int):
        self.width = width
        self._tick = 0
    
    def render(self, state: CynapseState) -> str:
        """
        Render the status bar.
        
        Args:
            state: Current application state
            
        Returns:
            Formatted status bar string
        """
        # Security status icon
        if state.security_status == SecurityStatus.SECURE:
            status_icon = ACTIVE_SIGNAL.colored()
            status_text = f"{COMPLEMENT_GOLD}SECURE{RESET}"
            bg = ""
        elif state.security_status == SecurityStatus.SCANNING:
            status_icon = f"{WARNING_AMBER}{OSCILLATING.char}{RESET}"
            status_text = f"{WARNING_AMBER}SCANNING{RESET}"
            bg = ""
        else:  # BREACH
            status_icon = f"{BREACH_RED}{BREACH.char}{RESET}"
            status_text = f"{BREACH_RED}BREACH{RESET}"
            bg = BG_BREACH_RED if self._tick % 2 == 0 else ""
        
        # Voice monitor status
        if state.voice_monitor_active:
            voice_icon = ACTIVE_SIGNAL.colored()
        else:
            voice_icon = DORMANT_SYNAPSE.colored()
        
        # Shard status
        shard_str = ""
        for shard in state.shards:
            if shard.mounted:
                shard_str += f"{CYAN_ELECTRIC}●{RESET}"
            else:
                shard_str += f"{DORMANT_GRAY}○{RESET}"
        
        # Breach timestamp
        breach_info = ""
        if state.last_breach:
            breach_info = f" │ Last: {state.last_breach.strftime('%H:%M:%S')}"
        
        # Build the status bar
        left = f" {status_icon} {status_text} │ Integrity: {state.integrity_percentage:.0f}%{breach_info}"
        right = f"Voice: {voice_icon} │ Shards: {shard_str} "
        
        # Calculate padding
        # Rough visible length calculation
        visible_left = len(left) - len(COMPLEMENT_GOLD) - len(RESET) * 2 - len(CYAN_ELECTRIC) - 10
        visible_right = len(right) - 20  # Rough estimate for ANSI codes
        
        center_padding = self.width - visible_left - visible_right - 4  # -4 for borders
        if center_padding < 1:
            center_padding = 1
        
        bar = f"{bg}{DEEP_PURPLE}║{RESET}{left}{' ' * center_padding}{right}{DEEP_PURPLE}║{RESET}"
        
        return bar
    
    def tick(self):
        """Advance animation by one tick."""
        self._tick += 1
