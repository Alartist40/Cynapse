from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import json

class AuditLogger:
    """Minimal Cynapse audit bridge"""
    
    AUDIT_PATH = Path.home() / ".cynapse" / "logs" / "audit.ndjson"
    
    def __init__(self, neuron_name: str = "cynapse_core"):
        self.neuron_name = neuron_name

    def log(self, event_type: str, data: Dict, integrity_hash: Optional[str] = None):
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "neuron": self.neuron_name,
            "event": event_type,
            "data": data
        }
        if integrity_hash:
            entry["integrity"] = integrity_hash
        
        self.AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(self.AUDIT_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def trigger_canary(self, stick_id: str, reason: str):
        """Alert Canary neuron to potential physical tampering"""
        self.log("canary_trigger_request", {
            "stick_id": stick_id,
            "reason": reason,
            "severity": "critical"
        })
