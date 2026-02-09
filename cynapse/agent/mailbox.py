import threading
from queue import Queue
from typing import Dict, Optional
from .core import Message

class Mailbox:
    """Async message queue for inter-agent communication"""
    
    def __init__(self):
        self._queues: Dict[str, Queue] = {}
        self._broadcast_queue: Queue = Queue()
        self._lock = threading.Lock()
    
    def register_agent(self, agent_id: str):
        with self._lock:
            self._queues[agent_id] = Queue()
    
    def send(self, message: Message):
        if message.to_agent == "broadcast":
            self._broadcast_queue.put(message)
        else:
            if message.to_agent in self._queues:
                self._queues[message.to_agent].put(message)
    
    def receive(self, agent_id: str, block: bool = False, timeout: float = 0.1) -> Optional[Message]:
        # Check direct messages first
        if agent_id in self._queues:
            try:
                return self._queues[agent_id].get(block=block, timeout=timeout)
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
