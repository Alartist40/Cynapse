"""
Cynapse TUI Symbol Dictionary

Universal semantic symbols for the Synaptic Fortress Interface.
These symbols maintain consistent meaning across all interface modes.
"""

from dataclasses import dataclass
from enum import Enum
from .colors import (
    CYAN_ELECTRIC, SYNAPSE_VIOLET, DORMANT_GRAY, COMPLEMENT_GOLD,
    WARNING_AMBER, BREACH_RED, INTERRUPT_ORANGE, ACTIVE_MAGENTA, RESET
)


class SymbolType(Enum):
    """Types of symbols used in the interface."""
    ACTIVE_SIGNAL = "●"      # Action potential traveling, current flowing
    CHARGED_PATHWAY = "▸"    # Myelinated pathway, ready to fire, standby
    DORMANT_SYNAPSE = "○"    # Resting potential, inactive
    SYNAPSE_FUSED = "✓"      # Vesicles released, action complete, success
    OSCILLATING = "∿"        # Feedback loop, learning, plasticity in progress
    BREACH = "✗"             # Synaptic failure, intrusion detected
    WARNING = "⚠"            # Threshold potential approached, caution
    CURSOR = "►"             # Selection indicator, current focus


@dataclass
class Symbol:
    """A symbol with its meaning and color."""
    char: str
    meaning: str
    state: str
    color: str
    
    def __str__(self) -> str:
        return f"{self.color}{self.char}{RESET}"
    
    def colored(self) -> str:
        return f"{self.color}{self.char}{RESET}"
    
    def plain(self) -> str:
        return self.char


# Symbol instances with their semantic meanings
ACTIVE_SIGNAL = Symbol("●", "Action potential traveling", "Live, processing", CYAN_ELECTRIC)
CHARGED_PATHWAY = Symbol("▸", "Myelinated pathway, ready to fire", "Armed, standby", SYNAPSE_VIOLET)
DORMANT_SYNAPSE = Symbol("○", "Resting potential, -70mV", "Offline, sleeping", DORMANT_GRAY)
SYNAPSE_FUSED = Symbol("✓", "Vesicles released, action complete", "Finished, verified", COMPLEMENT_GOLD)
OSCILLATING = Symbol("∿", "Feedback loop, learning", "Training, adapting", WARNING_AMBER)
BREACH = Symbol("✗", "Synaptic failure, intrusion detected", "Error, compromised", BREACH_RED)
WARNING = Symbol("⚠", "Threshold potential approached", "Alert, attention", INTERRUPT_ORANGE)
CURSOR = Symbol("►", "Selection indicator", "Navigation marker", ACTIVE_MAGENTA)


# Status tags with their colors
class StatusTag(Enum):
    """Status tags appended to lines or sections."""
    RUNNING = ("running", WARNING_AMBER)
    COMPLETE = ("complete", COMPLEMENT_GOLD)
    STANDBY = ("standby", DORMANT_GRAY)
    ARRESTED = ("arrested", BREACH_RED)
    PRUNING = ("pruning", SYNAPSE_VIOLET)
    ARMING = ("arming", CYAN_ELECTRIC)
    DORMANT = ("dormant", DORMANT_GRAY)
    
    @property
    def label(self) -> str:
        return self.value[0]
    
    @property
    def color(self) -> str:
        return self.value[1]
    
    def format(self) -> str:
        """Return formatted status tag like [running]."""
        return f"{self.color}[{self.label}]{RESET}"


def get_neuron_status_symbol(status: str) -> Symbol:
    """
    Get the appropriate symbol for a neuron status.
    
    Args:
        status: One of 'active', 'standby', 'dormant', 'error'
        
    Returns:
        Appropriate Symbol instance
    """
    status_map = {
        'active': ACTIVE_SIGNAL,
        'running': ACTIVE_SIGNAL,
        'standby': CHARGED_PATHWAY,
        'ready': CHARGED_PATHWAY,
        'dormant': DORMANT_SYNAPSE,
        'inactive': DORMANT_SYNAPSE,
        'complete': SYNAPSE_FUSED,
        'success': SYNAPSE_FUSED,
        'training': OSCILLATING,
        'learning': OSCILLATING,
        'error': BREACH,
        'breach': BREACH,
        'warning': WARNING,
        'alert': WARNING,
    }
    return status_map.get(status.lower(), DORMANT_SYNAPSE)


# Spinner frames for oscillating animation
SPINNER_FRAMES = ['|', '/', '-', '\\']


def get_spinner_frame(tick: int) -> str:
    """Get the current spinner character for animation."""
    return SPINNER_FRAMES[tick % len(SPINNER_FRAMES)]
