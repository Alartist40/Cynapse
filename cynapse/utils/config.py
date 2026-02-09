"""
Cynapse Configuration Manager
=============================

Centralized configuration handling for Cynapse.
Reads from cynapse/data/config.ini and provides defaults.
"""

import os
import configparser
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG = {
    "general": {
        "hub_name": "CynapseGhostShell",
        "version": "2.0.0",
        "log_level": "INFO",
        "data_dir": "./cynapse/data"
    },
    "neurons": {
        "neurons_dir": "./cynapse/neurons",
        "verify_signatures": "false",
        "timeout_seconds": "30",
        "auto_discover": "true"
    },
    "security": {
        "audit_logging": "true",
        "sensitive_keywords": "key,secret,token,password",
        "require_signatures": "false",
        "sandbox_enabled": "true"
    },
    "voice": {
        "enabled": "true",
        "whistle_frequency": "18000",
        "whistle_threshold": "50",
        "sample_rate": "48000",
        "timeout_seconds": "30"
    },
    "assembly": {
        "temp_dir": "./cynapse/data/temp",
        "enable_encryption": "true",
        "shards_required": "2"
    },
    "ollama": {
        "enabled": "true",
        "endpoint": "http://localhost:11434",
        "default_model": "llama3.2",
        "fallback_models": "llama3.1,phi4"
    },
    "hivemind": {
        "db_path": "./hivemind.db",
        "document_path": "./cynapse/data/documents",
        "workflow_path": "./workflows",
        "max_concurrent_bees": "5",
        "sandbox_enabled": "true",
        "auto_approve": "false"
    }
}

class ConfigManager:
    """Manages loading and validation of config.ini"""
    
    def __init__(self, config_path: str = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Default location
            self.config_path = Path("./cynapse/data/config.ini")
            
        self.config = configparser.ConfigParser()
        self.load()
        
    def load(self):
        """Load configuration from file or create if missing"""
        if not self.config_path.exists():
            self._create_default()
        else:
            self.config.read(self.config_path)
            
    def _create_default(self):
        """Create default configuration file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.read_dict(DEFAULT_CONFIG)
        with open(self.config_path, 'w') as f:
            self.config.write(f)
            
    def get(self, section: str, key: str, fallback: Any = None) -> str:
        """Get a configuration value"""
        return self.config.get(section, key, fallback=fallback)
        
    def get_boolean(self, section: str, key: str, fallback: bool = False) -> bool:
        """Get a boolean configuration value"""
        return self.config.getboolean(section, key, fallback=fallback)
        
    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """Get an integer configuration value"""
        return self.config.getint(section, key, fallback=fallback)
