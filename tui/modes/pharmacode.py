"""
Pharmacode Injection Mode

Visualization for model loading and training progress.
Uses pharmaceutical/medical terminology for cyberpunk aesthetic.
"""

from typing import List
from ..state import CynapseState
from ..colors import (
    CYAN_ELECTRIC, SYNAPSE_VIOLET, COMPLEMENT_GOLD, WARNING_AMBER,
    DORMANT_GRAY, WHITE_MATTER, RESET
)
from ..symbols import ACTIVE_SIGNAL, SYNAPSE_FUSED, DORMANT_SYNAPSE, get_spinner_frame


class PharmacodeInjectionMode:
    """
    Renders the Pharmacode Injection visualization.
    
    Shows model loading with pharmaceutical terminology
    and minimal 8-segment progress bars.
    """
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._tick = 0
    
    def render(self, state: CynapseState, ampules: List[dict] = None) -> List[str]:
        """
        Render the pharmacode injection visualization.
        
        Args:
            state: Current application state
            ampules: List of ampule dicts with 'name', 'progress', 'status'
            
        Returns:
            List of strings to display
        """
        lines = []
        
        # Header
        lines.append(f"{WHITE_MATTER}CYNAPSE // SERUM_INJECTION v2.4{RESET}")
        lines.append(f"{SYNAPSE_VIOLET}{'═' * min(50, self.width - 4)}{RESET}")
        lines.append("")
        
        # Default ampules if not provided
        if ampules is None:
            ampules = [
                {"name": "TiDAR_DIFFUSION", "progress": state.model_progress, "status": state.model_status},
                {"name": "ROPE_EMBEDDINGS", "progress": 100 if state.model_progress > 50 else 0, "status": "complete" if state.model_progress > 50 else "standby"},
                {"name": "EXPERT_MoE", "progress": 0, "status": "standby"},
            ]
        
        # Render each ampule
        for i, ampule in enumerate(ampules[:3]):  # Max 3 ampules
            ampule_lines = self._render_ampule(
                label=chr(65 + i),  # A, B, C
                name=ampule.get("name", "UNKNOWN"),
                progress=ampule.get("progress", 0),
                status=ampule.get("status", "standby")
            )
            lines.extend(ampule_lines)
            lines.append("")
        
        # Pharmacological footer
        lines.append("")
        footer = self._render_footer()
        lines.append(footer)
        
        # Pad to fill height
        while len(lines) < self.height:
            lines.append("")
        
        return lines[:self.height]
    
    def _render_ampule(self, label: str, name: str, progress: float, status: str) -> List[str]:
        """Render a single ampule with progress bar."""
        lines = []
        
        # Ampule header
        lines.append(f"AMPULE_{label}  [{name}]")
        
        # 8-segment progress bar
        bar = self._render_progress_bar(progress, 8)
        
        # Status and spinner
        if status == "complete":
            symbol = SYNAPSE_FUSED.colored()
            status_tag = f"{COMPLEMENT_GOLD}[complete]{RESET}"
            comment = "// fused"
        elif status == "running":
            spinner = get_spinner_frame(self._tick)
            symbol = f"{WARNING_AMBER}{spinner}{RESET}"
            status_tag = f"{WARNING_AMBER}[running]{RESET}"
            comment = "// dispersing..."
        else:
            symbol = DORMANT_SYNAPSE.colored()
            status_tag = f"{DORMANT_GRAY}[standby]{RESET}"
            comment = "// awaiting..."
        
        lines.append(f"{bar}  {progress:.0f}%  {symbol}  {status_tag}  {comment}")
        
        # Sub-info based on status
        if status == "running":
            lines.append(f"{DORMANT_GRAY}> uptake_rate: 847MB/s{RESET}")
            lines.append(f"{DORMANT_GRAY}> receptor_saturation: nominal{RESET}")
        elif status == "complete":
            lines.append(f"{DORMANT_GRAY}> myelination: complete{RESET}")
        
        return lines
    
    def _render_progress_bar(self, progress: float, segments: int = 8) -> str:
        """
        Render a minimal segment progress bar.
        
        Uses only 8 segments to minimize redraw.
        """
        filled = int((progress / 100) * segments)
        empty = segments - filled
        
        bar = f"{CYAN_ELECTRIC}[{'█' * filled}{DORMANT_GRAY}{'▒' * empty}{CYAN_ELECTRIC}]{RESET}"
        return bar
    
    def _render_footer(self) -> str:
        """Render pharmacological metrics footer."""
        # Pseudo-scientific metrics for aesthetic
        return f"{DORMANT_GRAY}VISCOSITY: 1.2cp │ pH: 7.35 │ TEMP: 310K{RESET}"
    
    def tick(self):
        """Advance animation by one tick."""
        self._tick += 1
