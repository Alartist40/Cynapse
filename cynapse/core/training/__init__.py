"""
Cynapse Training System
=======================

Local training infrastructure for Elara model.
Uses Ollama as training mentor for guidance.
"""

from .data_loader import DocumentDataLoader
from .checkpoint import CheckpointManager
from .ollama_mentor import OllamaMentor

# Lazy import for trainer (requires torch)
try:
    from .trainer import ElaraTrainer
except ImportError:
    ElaraTrainer = None

__all__ = [
    'ElaraTrainer',
    'DocumentDataLoader', 
    'CheckpointManager',
    'OllamaMentor'
]
