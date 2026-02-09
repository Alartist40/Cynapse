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
class Message:
    """Inter-agent message"""
    from_agent: str
    to_agent: str
    content: str
    message_type: str = "text" # text, command, completion, error
    reference_path: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
