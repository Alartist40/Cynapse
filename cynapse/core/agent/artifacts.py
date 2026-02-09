import json
import threading
from queue import Queue
from pathlib import Path
from typing import Dict, Any, Optional

class ArtifactStore:
    """Filesystem-based artifact storage with reference passing"""
    
    def __init__(self, base_path: str = "./cynapse/data/agent_artifacts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def write_artifact(self, agent_id: str, name: str, content: Any, 
                       format: str = "json") -> str:
        """Write artifact and return reference path (reference passing, not content passing)"""
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

class Mailbox:
    """Async message queue for inter-agent communication using queue.Queue"""
    
    def __init__(self):
        self._queues: Dict[str, Queue] = {}
        self._broadcast_queue: Queue = Queue()
        self._lock = threading.Lock()
    
    def register_agent(self, agent_id: str):
        with self._lock:
            self._queues[agent_id] = Queue()
    
    def send(self, message):
        """Send message using Agent message dataclass"""
        if message.to_agent == "broadcast":
            self._broadcast_queue.put(message)
        else:
            if message.to_agent in self._queues:
                self._queues[message.to_agent].put(message)
    
    def receive(self, agent_id: str, block: bool = False, timeout: float = 0.1):
        """Receive next message for agent"""
        # Check direct messages first
        if agent_id in self._queues:
            try:
                msg = self._queues[agent_id].get(block=block, timeout=timeout)
                return msg
            except:
                pass
        
        # Check broadcast
        try:
            return self._broadcast_queue.get(block=False)
        except:
            return None
    
    def get_pending_count(self, agent_id: str) -> int:
        if agent_id in self._queues:
            return self._queues[agent_id].qsize()
        return 0
