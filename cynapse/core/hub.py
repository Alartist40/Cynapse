"""
Cynapse Hub - Core Orchestrator
"""
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from cynapse.utils.config import ConfigManager

class CynapseHub:
    """
    Central orchestrator that discovers, verifies, and executes neurons.
    """
    def __init__(self, config_path: str = None):
        self.root_dir = Path(__file__).parent.parent
        self.config = ConfigManager(config_path)
        self.neurons_dir = Path(self.config.get("neurons", "neurons_dir", "./cynapse/neurons"))
        self.neurons: Dict[str, Dict] = {}
        
        # Logging setup
        logging.basicConfig(level=self.config.get("general", "log_level", "INFO"))
        self.logger = logging.getLogger("CynapseHub")
        
        self._discover_neurons()
        
    def _discover_neurons(self):
        """Scan neurons directory for manifests"""
        if not self.neurons_dir.exists():
            self.logger.warning(f"Neurons directory not found: {self.neurons_dir}")
            return

        self.logger.info(f"Scanning neurons in {self.neurons_dir}...")
        
        for item in self.neurons_dir.iterdir():
            # 1. Check for Manifest in subdirectories
            if item.is_dir():
                manifest_path = item / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path, 'r') as f:
                            manifest = json.load(f)
                            name = manifest.get("name", item.name)
                            self.neurons[name] = {
                                "path": item,
                                "type": "module",
                                "manifest": manifest
                            }
                            self.logger.debug(f"Discovered module neuron: {name}")
                    except json.JSONDecodeError:
                        self.logger.error(f"Invalid manifest in {item}")
                    continue

                # Check for manifest with directory name inside directory
                manifest_path = item / f"{item.name}_manifest.json"
                if manifest_path.exists():
                     try:
                        with open(manifest_path, 'r') as f:
                            manifest = json.load(f)
                            name = manifest.get("name", item.name)
                            self.neurons[name] = {
                                "path": item,
                                "type": "module",
                                "manifest": manifest
                            }
                            self.logger.debug(f"Discovered module neuron: {name}")
                     except json.JSONDecodeError:
                        self.logger.error(f"Invalid manifest in {item}")
                     continue

            # 2. Check for Manifest alongside .py file (e.g. bat.py + bat_manifest.json)
            if item.suffix == ".py" and item.name != "__init__.py":
                manifest_path = item.with_name(f"{item.stem}_manifest.json")
                manifest = {}
                if manifest_path.exists():
                    try:
                        with open(manifest_path, 'r') as f:
                            manifest = json.load(f)
                    except json.JSONDecodeError:
                         self.logger.error(f"Invalid manifest: {manifest_path}")

                self.neurons[item.stem] = {
                    "path": item,
                    "type": "python",
                    "manifest": manifest
                }
                self.logger.debug(f"Discovered script neuron: {item.stem}")

            # 3. Check for binary/Go files
            elif item.suffix == ".go":
                self.neurons[item.stem] = {
                    "path": item,
                    "type": "go_source",
                    "manifest": {}
                }

    def list_neurons(self) -> List[str]:
        return list(self.neurons.keys())

    def get_neuron(self, name: str) -> Optional[Dict]:
        return self.neurons.get(name)
