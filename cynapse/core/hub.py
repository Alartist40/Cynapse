"""
Cynapse Hub - Core Orchestrator
"""
import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional

class CynapseHub:
    """
    Central orchestrator that discovers, verifies, and executes neurons.
    """
    def __init__(self, config_path: str = None):
        self.root_dir = Path(__file__).parent.parent
        self.neurons_dir = self.root_dir / "neurons"
        self.config_path = config_path or (self.root_dir / "data" / "config.ini")
        self.neurons: Dict[str, Dict] = {}
        
        self._discover_neurons()
        
    def _discover_neurons(self):
        """Scan neurons directory for manifests"""
        if not self.neurons_dir.exists():
            return

        # Simple discovery for python/go/rust binaries
        # In a real impl, this would parse manifest.json files
        for item in self.neurons_dir.iterdir():
            if item.is_file():
                if item.suffix == ".py" and item.name != "__init__.py":
                    self.neurons[item.stem] = {
                        "path": item,
                        "type": "python"
                    }
                elif item.suffix == ".go": # Assuming built binaries mostly
                     self.neurons[item.stem] = {
                        "path": item,
                        "type": "go_source"
                    }
            elif item.is_dir():
                # Check for manifest or main file
                pass
                
    def list_neurons(self) -> List[str]:
        return list(self.neurons.keys())

    def get_neuron(self, name: str) -> Optional[Dict]:
        return self.neurons.get(name)
