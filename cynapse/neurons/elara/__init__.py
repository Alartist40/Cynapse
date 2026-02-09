"""
Elara Neuron - Local AI Model
=============================

3B parameter model with MoE, TiDAR, and RoPE.
Optimized for local training and inference.
"""

from .model_loader import ElaraModelLoader
from .inference import ElaraInference

__all__ = ['ElaraModelLoader', 'ElaraInference']
