"""
Cynapse - Ghost Shell Security Hub
==================================

A specialized, air-gapped security ecosystem with:
- 8 security neurons (Bat, Beaver, Canary, Meerkat, Octopus, Owl, Wolverine, Elara)
- Ghost Shell threshold cryptography (2-of-3 Shamir Secret Sharing)
- HiveMind workflow orchestration
- Synaptic Fortress TUI

Version: 2.0.0
Author: Alejandro Eduardo Garcia Romero
License: MIT

Usage:
    from cynapse import CynapseHub, HiveMind
    hub = CynapseHub()
    neurons = hub.list_neurons()
"""

from .core import CynapseHub, HiveMind

__version__ = "2.0.0"
__author__ = "Alejandro Eduardo Garcia Romero"
__license__ = "MIT"

__all__ = [
    'CynapseHub',
    'HiveMind',
]
