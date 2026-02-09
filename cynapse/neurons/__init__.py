"""
Cynapse Neurons - Security & AI Modules
======================================

This package contains 8 specialized neurons:
- Elara: 3B parameter AI model (MoE, TiDAR, RoPE)
- Bat: Ghost Shell threshold cryptography vault  
- Beaver: AI firewall rule generator
- Canary: Distributed deception system
- Meerkat: Vulnerability scanner
- Octopus: Container escape tester
- Owl: PII OCR redactor
- Wolverine: RAG security auditor

All imports are lazy-loaded to avoid dependency errors.
"""

import importlib
import warnings

# Lazy loading to handle missing dependencies gracefully
def _lazy_import(module_name, class_name):
    """Lazy import to avoid loading dependencies until needed"""
    try:
        module = importlib.import_module(module_name, package='cynapse.neurons')
        return getattr(module, class_name)
    except ImportError as e:
        warnings.warn(f"Could not import {class_name} from {module_name}: {e}")
        return None

# Lazy-loaded classes
Elara = None
ElaraConfig = None
GhostShell = None
BeaverMiner = None
CanaryNeuron = None
MeerkatScanner = None
OctopusValidator = None
OwlRedactor = None
WolverineAuditor = None
ElephantSigner = None

try:
    from .elara import Elara, ElaraConfig
except ImportError:
    pass

try:
    from .bat import GhostShell
except ImportError:
    pass

try:
    from .beaver import BeaverMiner
except ImportError:
    pass

try:
    from .canary import CanaryNeuron
except ImportError:
    pass

try:
    from .meerkat import MeerkatScanner
except ImportError:
    pass

try:
    from .octopus import OctopusValidator
except ImportError:
    pass

try:
    from .owl import OwlRedactor
except ImportError:
    pass

try:
    from .wolverine import WolverineAuditor
except ImportError:
    pass

try:
    from .elephant.tui import ElephantSigner
except ImportError:
    pass

__all__ = [
    'Elara', 'ElaraConfig',
    'GhostShell', 'BeaverMiner', 'CanaryNeuron',
    'MeerkatScanner', 'OctopusValidator', 'OwlRedactor',
    'WolverineAuditor', 'ElephantSigner'
]

__version__ = "2.0.0"
