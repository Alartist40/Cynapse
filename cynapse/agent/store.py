import os
import json
import threading
from typing import Dict, List, Any
from pathlib import Path
from .core import Agent

class AgentContextManager:
    """Manages isolated context windows for each agent"""
    
    def __init__(self, base_path: str = "./cynapse/data/agent_contexts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._contexts: Dict[str, List[Dict]] = {}
        self._lock = threading.Lock()
    
    def create_context(self, agent_id: str, system_prompt: str):
        with self._lock:
            self._contexts[agent_id] = [
                {"role": "system", "content": system_prompt}
            ]
    
    def add_message(self, agent_id: str, role: str, content: str):
        with self._lock:
            if agent_id not in self._contexts:
                self._contexts[agent_id] = []
            self._contexts[agent_id].append({
                "role": role, "content": content
            })
    
    def get_context(self, agent_id: str) -> List[Dict]:
        with self._lock:
            return self._contexts.get(agent_id, []).copy()
    
    def clear_context(self, agent_id: str):
        with self._lock:
            if agent_id in self._contexts:
                system_msg = self._contexts[agent_id][0]
                self._contexts[agent_id] = [system_msg]

class ArtifactStore:
    """Filesystem-based artifact storage with reference passing"""
    
    def __init__(self, base_path: str = "./cynapse/data/agent_artifacts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def write_artifact(self, agent_id: str, name: str, content: Any, 
                       format: str = "json") -> str:
        """Write artifact and return reference path"""
        agent_dir = self.base_path / agent_id
        agent_dir.mkdir(exist_ok=True)
        
        path = agent_dir / f"{name}.{format}"
        
        if format == "json":
            with open(path, 'w') as f:
                json.dump(content, f, indent=2)
        else:
            with open(path, 'w') as f:
                f.write(str(content))
        
        return str(path)
    
    def read_artifact(self, reference: str) -> Any:
        """Read artifact from reference path"""
        path = Path(reference)
        if not path.exists():
            return None
        
        suffix = path.suffix
        if suffix == '.json':
            with open(path) as f:
                return json.load(f)
        else:
            with open(path) as f:
                return f.read()
    
    def get_agent_workspace(self, agent_id: str) -> Path:
        """Get private workspace for agent"""
        workspace = self.base_path / agent_id / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace
