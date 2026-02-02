"""
Neural Assembly Mode

Visualization for Ghost Shell shard assembly and USB combination.
Displays synaptic connection diagrams with signal propagation animation.
"""

from typing import List, Tuple
from ..state import CynapseState, get_state
from ..colors import (
    CYAN_ELECTRIC, SYNAPSE_VIOLET, DORMANT_GRAY, COMPLEMENT_GOLD,
    WARNING_AMBER, WHITE_MATTER, RESET
)
from ..symbols import ACTIVE_SIGNAL, CHARGED_PATHWAY, DORMANT_SYNAPSE, SYNAPSE_FUSED


class NeuralAssemblyMode:
    """
    Renders the Neural Assembly visualization.
    
    Shows USB shard combination with synaptic pathway diagrams
    and signal propagation animation.
    """
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._tick = 0
        self._signal_positions = [0, 0, 0]  # Position of signal for each shard
    
    def render(self, state: CynapseState) -> List[str]:
        """
        Render the neural assembly visualization.
        
        Args:
            state: Current application state
            
        Returns:
            List of strings to display in the activation zone
        """
        lines = []
        
        # Header
        header = f"{WHITE_MATTER}NEURAL_ASSEMBLY MODE{RESET}"
        lines.append(self._center(header))
        lines.append("")
        
        # Render each shard connection
        for i, shard in enumerate(state.shards):
            shard_lines = self._render_shard_connection(
                shard_num=i + 1,
                mounted=shard.mounted,
                verified=shard.verified,
                progress=shard.progress
            )
            lines.extend(shard_lines)
        
        # Stats line
        lines.append("")
        stats = self._render_stats(state)
        lines.append(stats)
        
        # Pad to fill height
        while len(lines) < self.height:
            lines.append("")
        
        return lines[:self.height]
    
    def _render_shard_connection(self, shard_num: int, mounted: bool, 
                                  verified: bool, progress: float) -> List[str]:
        """Render a single shard connection diagram."""
        lines = []
        
        # Determine symbol and color
        if verified and progress >= 100:
            symbol = SYNAPSE_FUSED
            status = f"{COMPLEMENT_GOLD}[complete]{RESET}"
        elif mounted and progress > 0:
            symbol = ACTIVE_SIGNAL
            status = f"{WARNING_AMBER}[charging]{RESET}"
        elif mounted:
            symbol = CHARGED_PATHWAY
            status = f"{SYNAPSE_VIOLET}[standby]{RESET}"
        else:
            symbol = DORMANT_SYNAPSE
            status = f"{DORMANT_GRAY}[not mounted]{RESET}"
        
        # Build the pathway visualization
        # PRE_0X >───────●───────> POST_0X  [status]
        
        pathway_width = min(20, self.width - 30)
        
        # Animate signal position for active shards
        if mounted and not verified:
            signal_pos = int((progress / 100) * pathway_width)
        else:
            signal_pos = pathway_width if verified else 0
        
        pathway = ""
        for i in range(pathway_width):
            if i == signal_pos:
                pathway += symbol.colored()
            else:
                pathway += "─"
        
        line = f"PRE_0{shard_num} >{pathway}> POST_0{shard_num}  {status}"
        lines.append(line)
        
        # Add sub-info line
        if mounted and not verified:
            info = f"         ╲ decrypting shard_0{shard_num}..."
            lines.append(f"{DORMANT_GRAY}{info}{RESET}")
        elif verified:
            latency = 1.2 + (shard_num * 0.4)
            info = f"         ╲ {latency:.1f}ms latency"
            lines.append(f"{DORMANT_GRAY}{info}{RESET}")
        else:
            lines.append("")
        
        return lines
    
    def _render_stats(self, state: CynapseState) -> str:
        """Render the bottom stats line."""
        charge_pct = state.assembly_progress
        throughput = state.assembly_throughput
        nodes = state.mounted_shards
        
        stats = (
            f"SYNAPTIC_CHARGE: {charge_pct:.0f}% │ "
            f"THROUGHPUT: {throughput:.0f}Mb/s │ "
            f"NODES: {nodes}/3"
        )
        return f"{CYAN_ELECTRIC}{stats}{RESET}"
    
    def _center(self, text: str) -> str:
        """Center text within the width."""
        # Account for ANSI codes when calculating padding
        visible_len = len(text.replace(RESET, '').replace(WHITE_MATTER, ''))
        padding = (self.width - visible_len) // 2
        return ' ' * max(0, padding) + text
    
    def tick(self):
        """Advance animation by one tick."""
        self._tick += 1
