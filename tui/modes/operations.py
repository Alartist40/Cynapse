"""
Operations Mode (RAG Laboratory)

The workspace for AI interaction, document ingestion,
and Queen chat interface.
"""

from typing import List
from ..state import CynapseState
from ..colors import (
    CYAN_ELECTRIC, DEEP_BLUE, COMPLEMENT_GOLD, DORMANT_GRAY,
    WHITE_MATTER, RESET
)
from ..symbols import ACTIVE_SIGNAL, SYNAPSE_FUSED
from ..layout import Box


class OperationsMode:
    """
    Renders the Operations Bay / RAG Laboratory.
    
    Blue-dominant design for calm, cognitive workspace.
    Shows document ingestion, chat interface, and training controls.
    """
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
    
    def render(self, state: CynapseState) -> List[str]:
        """
        Render the operations bay.
        
        Args:
            state: Current application state
            
        Returns:
            List of strings to display
        """
        lines = []
        
        # Box header
        header = f"{DEEP_BLUE}┌─[OPERATIONS BAY: HiveMind RAG]{'─' * (self.width - 35)}┐{RESET}"
        lines.append(header)
        
        # Status line
        queen_status = ACTIVE_SIGNAL.colored() if state.model_progress > 50 else f"{DORMANT_GRAY}○{RESET}"
        status_line = (
            f"{DEEP_BLUE}│{RESET} STATUS: {queen_status} Queen {'Active' if state.model_progress > 50 else 'Standby'} │ "
            f"Docs: {state.document_count} │ "
            f"Training: {self._mini_progress(state.training_progress)}"
        )
        lines.append(self._pad_line(status_line))
        
        # Divider
        lines.append(f"{DEEP_BLUE}├{'─' * (self.width - 2)}┤{RESET}")
        
        # RAG status message
        lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET} > RAG System ready. {state.document_count} documents indexed."))
        lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET}"))
        
        # Recent feeds
        lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET} 📁 Recent Feeds:"))
        
        # Show last 3-4 documents
        visible_docs = state.documents[:4] if state.documents else []
        for i, doc in enumerate(visible_docs):
            prefix = "├─" if i < len(visible_docs) - 1 else "└─"
            status = f"{COMPLEMENT_GOLD}[✓ embedded]{RESET}" if doc.embedded else f"{DORMANT_GRAY}[pending]{RESET}"
            doc_line = f"{DEEP_BLUE}│{RESET}   {prefix} {doc.name[:30]}  {status}"
            lines.append(self._pad_line(doc_line))
        
        if len(state.documents) > 4:
            lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET}   └─ ... and {len(state.documents) - 4} more"))
        elif not state.documents:
            lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET}   {DORMANT_GRAY}(no documents ingested){RESET}"))
        
        lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET}"))
        
        # Chat area
        lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET} {CYAN_ELECTRIC}prompt:{RESET} {state.current_prompt or '_'}"))
        lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET}"))
        
        # Last response if any
        if state.chat_history:
            last_msg = state.chat_history[-1]
            if last_msg['role'] == 'assistant':
                content = last_msg['content'][:self.width - 20]
                lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET} 🐝 Queen: {content}"))
                lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET}           {CYAN_ELECTRIC}[View Source] [Generate Patch]{RESET}"))
        else:
            lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET} {DORMANT_GRAY}🐝 Queen awaiting query...{RESET}"))
        
        lines.append(self._pad_line(f"{DEEP_BLUE}│{RESET}"))
        
        # Footer
        footer = f"{DEEP_BLUE}└{'─' * (self.width - 2)}┘{RESET}"
        lines.append(footer)
        
        # Pad to fill height
        while len(lines) < self.height:
            lines.insert(-1, self._pad_line(f"{DEEP_BLUE}│{RESET}"))
        
        return lines[:self.height]
    
    def _pad_line(self, line: str) -> str:
        """Pad a line to full width with border."""
        # Rough estimate of visible length (accounting for ANSI codes)
        visible = line
        for code in [DEEP_BLUE, CYAN_ELECTRIC, COMPLEMENT_GOLD, DORMANT_GRAY, WHITE_MATTER, RESET]:
            visible = visible.replace(code, '')
        
        padding = self.width - len(visible) - 1
        if padding > 0:
            return line + ' ' * padding + f"{DEEP_BLUE}│{RESET}"
        return line[:self.width - 1] + f"{DEEP_BLUE}│{RESET}"
    
    def _mini_progress(self, progress: float) -> str:
        """Render a tiny progress indicator."""
        if progress == 0:
            return f"{DORMANT_GRAY}░░░░░░ 0%{RESET}"
        
        filled = int(progress / 100 * 6)
        bar = '█' * filled + '░' * (6 - filled)
        return f"{CYAN_ELECTRIC}{bar} {progress:.0f}%{RESET}"
