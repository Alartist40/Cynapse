from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import uuid
from datetime import datetime

class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"

class AgentRole(Enum):
    LEAD = "lead"
    RESEARCHER = "researcher"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"

@dataclass
class Task:
    """Unit of work assigned to subagent"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    role: AgentRole = AgentRole.RESEARCHER
    dependencies: List[str] = field(default_factory=list)
    status: AgentState = AgentState.IDLE
    assigned_to: Optional[str] = None
    output_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

@dataclass
class Agent:
    """Agent instance configuration"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    role: AgentRole = AgentRole.RESEARCHER
    state: AgentState = AgentState.IDLE
    context_window: List[Dict] = field(default_factory=list)
    workspace_path: str = ""
    parent_id: Optional[str] = None
    max_iterations: int = 10
    token_budget: int = 100000

@dataclass
class Plan:
    """High-level execution plan"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    goal: str = ""
    tasks: List[Task] = field(default_factory=list)
    strategy: str = "sequential"
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Message:
    """Inter-agent communication"""
    from_agent: str
    to_agent: str
    content: str
    message_type: str = "text"  # text, command, completion, error
    reference_path: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

class AgentContextManager:
    """Manages isolated context windows for each agent"""
    
    def __init__(self, base_path: str = "./cynapse/data/agent_contexts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._contexts: Dict[str, List[Dict]] = {}
        # self._lock = threading.Lock() # Threading handled by caller if needed
    
    def create_context(self, agent_id: str, system_prompt: str):
        self._contexts[agent_id] = [
            {"role": "system", "content": system_prompt}
        ]
    
    def add_message(self, agent_id: str, role: str, content: str):
        if agent_id not in self._contexts:
            self._contexts[agent_id] = []
        self._contexts[agent_id].append({
            "role": role, "content": content
        })
    
    def get_context(self, agent_id: str) -> List[Dict]:
        return self._contexts.get(agent_id, []).copy()
    
    def clear_context(self, agent_id: str):
        if agent_id in self._contexts:
            system_msg = self._contexts[agent_id][0]
            self._contexts[agent_id] = [system_msg]
