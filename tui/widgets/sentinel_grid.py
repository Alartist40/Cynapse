"""
Sentinel Grid Widget

Left sidebar displaying the list of neurons with their status.
Supports navigation and quick toggling.
"""

from typing import List, Tuple
from ..state import CynapseState, NeuronStatus
from ..colors import (
    DEEP_PURPLE, CYAN_ELECTRIC, SYNAPSE_VIOLET, DORMANT_GRAY,
    COMPLEMENT_GOLD, BREACH_RED, WHITE_MATTER, RESET
)
from ..symbols import (
    ACTIVE_SIGNAL, CHARGED_PATHWAY, DORMANT_SYNAPSE, BREACH, CURSOR,
    get_neuron_status_symbol
)


class SentinelGrid:
    """
    Renders the Sentinel Grid (left sidebar).
    
    Shows individual neuron entries with status and contextual alerts.
    """
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
    
    def render(self, state: CynapseState, neurons: dict = None) -> List[str]:
        """
        Render the sentinel grid.
        
        Args:
            state: Current application state
            neurons: Dict of neuron_id -> neuron info
            
        Returns:
            List of strings to display in the sentinel zone
        """
        lines = []
        
        # Header
        header = f"{DEEP_PURPLE}╔{'═' * (self.width - 2)}╗{RESET}"
        lines.append(header)
        
        title = "SENTINEL GRID"
        title_line = f"{DEEP_PURPLE}║{RESET} {WHITE_MATTER}{title}{RESET}"
        lines.append(self._pad_line(title_line))
        
        lines.append(f"{DEEP_PURPLE}╠{'═' * (self.width - 2)}╣{RESET}")
        
        # Neuron list
        neuron_list = state.get_neuron_list()
        selected_idx = state.selected_neuron_index
        
        # Calculate visible range (scrolling)
        visible_count = self.height - 6  # Account for header, footer, etc.
        start_idx = 0
        if selected_idx >= visible_count:
            start_idx = selected_idx - visible_count + 1
        
        visible_neurons = neuron_list[start_idx:start_idx + visible_count]
        
        for i, (neuron_id, status) in enumerate(visible_neurons):
            actual_idx = start_idx + i
            is_selected = actual_idx == selected_idx
            
            line = self._render_neuron_line(neuron_id, status, is_selected)
            lines.append(line)
        
        # Pad remaining space
        remaining = visible_count - len(visible_neurons)
        for _ in range(remaining):
            lines.append(self._pad_line(f"{DEEP_PURPLE}║{RESET}"))
        
        # Alerts section
        lines.append(f"{DEEP_PURPLE}╠{'═' * (self.width - 2)}╣{RESET}")
        alert_line = self._render_alerts(state)
        lines.append(alert_line)
        
        # Footer with hints
        lines.append(f"{DEEP_PURPLE}╠{'═' * (self.width - 2)}╣{RESET}")
        hints = f" [a]rm [d]isarm [r]eload"
        lines.append(self._pad_line(f"{DEEP_PURPLE}║{RESET}{DORMANT_GRAY}{hints}{RESET}"))
        
        # Close box
        lines.append(f"{DEEP_PURPLE}╚{'═' * (self.width - 2)}╝{RESET}")
        
        return lines[:self.height]
    
    def _render_neuron_line(self, neuron_id: str, status: NeuronStatus, selected: bool) -> str:
        """Render a single neuron entry."""
        # Get status symbol
        symbol = get_neuron_status_symbol(status.value if isinstance(status, NeuronStatus) else str(status))
        
        # Selection indicator
        if selected:
            prefix = f"{CYAN_ELECTRIC}{CURSOR.char}{RESET}"
        else:
            prefix = " "
        
        # Truncate neuron name if needed
        max_name_len = self.width - 12
        display_name = neuron_id[:max_name_len] if len(neuron_id) > max_name_len else neuron_id
        
        # Status text
        status_val = status.value if isinstance(status, NeuronStatus) else str(status)
        
        line = f"{DEEP_PURPLE}║{RESET}{prefix} {display_name:15} [{symbol}] {DORMANT_GRAY}{status_val}{RESET}"
        return self._pad_line(line)
    
    def _render_alerts(self, state: CynapseState) -> str:
        """Render contextual alerts."""
        # Check for any error states
        error_neurons = [n for n, s in state.neurons.items() if s == NeuronStatus.ERROR]
        
        if error_neurons:
            alert = f" {BREACH_RED}⚠ Alert: {len(error_neurons)} neuron(s) in error state{RESET}"
        elif state.integrity_percentage < 100:
            alert = f" {COMPLEMENT_GOLD}⚠ Integrity: {state.integrity_percentage:.0f}%{RESET}"
        else:
            alert = f" {DORMANT_GRAY}All systems nominal{RESET}"
        
        return self._pad_line(f"{DEEP_PURPLE}║{RESET}{alert}")
    
    def _pad_line(self, line: str) -> str:
        """Pad a line to full width with border."""
        visible = line
        # Remove ANSI codes for length calculation
        for code in [DEEP_PURPLE, CYAN_ELECTRIC, SYNAPSE_VIOLET, DORMANT_GRAY,
                     COMPLEMENT_GOLD, BREACH_RED, WHITE_MATTER, RESET]:
            visible = visible.replace(code, '')
        
        # Also remove symbol characters that are already colored
        # (rough estimate)
        
        padding = self.width - len(visible) - 1
        if padding > 0:
            return line + ' ' * padding + f"{DEEP_PURPLE}║{RESET}"
        return line[:self.width - 1] + f"{DEEP_PURPLE}║{RESET}"
