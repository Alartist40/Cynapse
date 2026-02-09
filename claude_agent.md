
# Create CLAUDE_AGENT.md with proper content

claude_agent_content = '''# CLAUDE_AGENT.md — Multi-Agent Architecture Specification

**Version**: 1.0.0  
**Date**: 2026-02-03  
**Based on**: Anthropic's Agent Teams, "Building Effective Agents", and reverse-engineered findings  
**Goal**: Enable team to build hierarchical multi-agent system similar to Claude Code's implementation

---

## Executive Summary

Claude Code's multi-agent system uses a **Lead Agent + Subagent** architecture where:
- **Lead Agent**: Coordinates work, maintains high-level context, delegates tasks
- **Subagents**: Execute tasks in isolated contexts with parallel processing
- **Communication**: Tool-based messaging + filesystem artifact passing
- **Key Innovation**: Subagents write to disk and pass references, not full content (avoids "game of telephone")

**Critical Trade-off**: Multi-agent uses **15x more tokens** than chat—only use for high-value parallel tasks.

---

## Part 1: Architecture Overview

### 1.1 The "Lead + Subagent" Pattern

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LEAD AGENT                                  │
│  (Main Claude Code session / Your HiveMind Queen)                   │
│                                                                     │
│  Responsibilities:                                                  │
│  • High-level planning                                              │
│  • Task decomposition                                               │
│  • Subagent orchestration                                           │
│  • Final synthesis                                                  │
│  • User communication                                               │
└────────────────────────┬────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Subagent 1  │ │  Subagent 2  │ │  Subagent N  │
│  (Research)  │ │  (Code Gen)  │ │  (Testing)   │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┴────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Shared Filesystem   │
              │   (Artifacts, Code,   │
              │    Research Notes)    │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Lead Agent Reads    │
              │   & Synthesizes       │
              └───────────────────────┘
```

### 1.2 Core Components

| Component | Purpose | Implementation |
|-----------|---------|----------------|
| **Lead Agent** | Coordinator | Main LLM with orchestration tools |
| **Subagent Pool** | Workers | Separate LLM instances, isolated contexts |
| **Task Queue** | Work distribution | Priority queue with dependencies |
| **Mailbox System** | Inter-agent messaging | Tool-based async communication |
| **Artifact Store** | Shared state | Filesystem with structured paths |
| **Context Manager** | Memory isolation | Per-agent context windows |

### 1.3 Key Design Principles

**1. Context Isolation**
- Each subagent has independent context window
- No "bleed" between agent contexts
- Lead agent maintains only high-level summary

**2. Reference Passing (Not Content Passing)**
- Subagents write artifacts to disk
- Other agents receive references (file paths)
- Avoids context bloat from passing full content

**3. Parallel Execution**
- Subagents run simultaneously
- Lead agent monitors via status checks
- Synchronization points for dependencies

**4. Hierarchical Control**
- Lead can spawn, pause, terminate subagents
- Subagents report status but don't control siblings
- User interacts only with Lead

---

## Part 2: Technical Implementation

### 2.1 Data Models

```python
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
```

### 2.2 Core System Classes

```python
import os
import json
import threading
from queue import Queue
from pathlib import Path

class AgentContextManager:
    """Manages isolated context windows for each agent"""
    
    def __init__(self, base_path: str = "./agent_contexts"):
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
    
    def __init__(self, base_path: str = "./agent_artifacts"):
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
```

### 2.3 Lead Agent Implementation

```python
class LeadAgent:
    """
    Orchestrates subagents, manages high-level planning,
    synthesizes results into coherent output.
    """
    
    def __init__(self, agent_id: str, llm_client, context_manager: AgentContextManager,
                 artifact_store: ArtifactStore, mailbox: Mailbox):
        self.agent_id = agent_id
        self.llm = llm_client
        self.context = context_manager
        self.artifacts = artifact_store
        self.mailbox = mailbox
        
        self.subagents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}
        self.active_plans: Dict[str, Plan] = {}
        
        # Initialize context
        self.context.create_context(agent_id, self._get_system_prompt())
        self.mailbox.register_agent(agent_id)
    
    def _get_system_prompt(self) -> str:
        return """You are the Lead Agent in a multi-agent system.
Your role is to:
1. Analyze user requests and break them into subtasks
2. Spawn specialized subagents for parallel execution
3. Monitor progress and handle dependencies
4. Synthesize subagent outputs into coherent final responses
5. Manage token budget efficiently (15x cost of single agent)

Use tools to:
- spawn_subagent(role, task_description) -> agent_id
- assign_task(agent_id, task) -> task_id
- check_status(agent_id) -> status
- read_artifact(reference_path) -> content
- send_message(agent_id, message)
- terminate_subagent(agent_id)

Always pass references (file paths) between agents, never full content."""
    
    def spawn_subagent(self, role: AgentRole, task_description: str) -> str:
        """Create new subagent with isolated context"""
        agent_id = str(uuid.uuid4())[:8]
        
        # Create agent config
        agent = Agent(
            id=agent_id,
            name=f"{role.value}_{agent_id}",
            role=role,
            parent_id=self.agent_id,
            workspace_path=str(self.artifacts.get_agent_workspace(agent_id))
        )
        
        # Initialize subagent context
        system_prompt = self._get_role_prompt(role)
        self.context.create_context(agent_id, system_prompt)
        self.mailbox.register_agent(agent_id)
        
        # Store agent
        self.subagents[agent_id] = agent
        
        # Start subagent thread
        thread = threading.Thread(
            target=self._run_subagent,
            args=(agent_id, task_description)
        )
        thread.daemon = True
        thread.start()
        
        return agent_id
    
    def _get_role_prompt(self, role: AgentRole) -> str:
        prompts = {
            AgentRole.RESEARCHER: "You are a Research Agent. Gather information, analyze data, and write findings to your workspace. Pass references to your output files.",
            AgentRole.CODER: "You are a Code Generation Agent. Write code, tests, and documentation. Save files to your workspace and return file paths only.",
            AgentRole.TESTER: "You are a Testing Agent. Run tests, analyze coverage, report bugs. Write results to workspace.",
            AgentRole.REVIEWER: "You are a Code Review Agent. Review code for bugs, style, security. Write review comments to workspace."
        }
        return prompts.get(role, "You are a specialized agent.")
    
    def _run_subagent(self, agent_id: str, task_description: str):
        """Execute subagent in isolated thread"""
        agent = self.subagents[agent_id]
        agent.state = AgentState.EXECUTING
        
        try:
            # Get context
            context = self.context.get_context(agent_id)
            context.append({"role": "user", "content": task_description})
            
            # Execute with LLM (simplified)
            response = self.llm.generate(context)
            
            # Write output to artifact store
            output_path = self.artifacts.write_artifact(
                agent_id, "output", 
                {"task": task_description, "result": response}
            )
            
            # Notify lead agent
            self.mailbox.send(Message(
                from_agent=agent_id,
                to_agent=self.agent_id,
                content="Task completed",
                message_type="completion",
                reference_path=output_path
            ))
            
            agent.state = AgentState.COMPLETED
            
        except Exception as e:
            agent.state = AgentState.FAILED
            self.mailbox.send(Message(
                from_agent=agent_id,
                to_agent=self.agent_id,
                content=f"Error: {str(e)}",
                message_type="error"
            ))
    
    def orchestrate(self, user_request: str) -> str:
        """Main entry point for user requests"""
        # Add to context
        self.context.add_message(self.agent_id, "user", user_request)
        
        # Step 1: Plan decomposition
        plan = self._create_plan(user_request)
        
        # Step 2: Spawn subagents for parallel tasks
        task_agents = {}
        for task in plan.tasks:
            if not task.dependencies:  # No dependencies = parallel
                agent_id = self.spawn_subagent(task.role, task.description)
                task.assigned_to = agent_id
                task_agents[task.id] = agent_id
        
        # Step 3: Wait for completion and handle dependencies
        results = self._wait_for_completion(task_agents)
        
        # Step 4: Synthesize results
        final_response = self._synthesize(results, user_request)
        
        # Cleanup
        self._cleanup_subagents(task_agents.values())
        
        return final_response
    
    def _create_plan(self, user_request: str) -> Plan:
        """Break request into subtasks"""
        # Use LLM to create plan
        context = self.context.get_context(self.agent_id)
        planning_prompt = f"""Break this request into subtasks:
        Request: {user_request}
        
        Format: JSON list of tasks with role, description, dependencies.
        Roles: researcher, coder, tester, reviewer"""
        
        context.append({"role": "user", "content": planning_prompt})
        plan_json = self.llm.generate(context)
        
        # Parse and create plan
        plan_data = json.loads(plan_json)
        tasks = [Task(**t) for t in plan_data.get('tasks', [])]
        
        plan = Plan(
            goal=user_request,
            tasks=tasks,
            strategy="parallel" if len(tasks) > 1 else "sequential",
            created_by=self.agent_id
        )
        
        self.active_plans[plan.id] = plan
        return plan
    
    def _wait_for_completion(self, task_agents: Dict[str, str], timeout: float = 300.0) -> Dict[str, Any]:
        """Wait for all subagents to complete"""
        results = {}
        start_time = time.time()
        
        while task_agents and (time.time() - start_time) < timeout:
            msg = self.mailbox.receive(self.agent_id, block=True, timeout=1.0)
            
            if msg and msg.message_type == "completion":
                # Read artifact
                content = self.artifacts.read_artifact(msg.reference_path)
                results[msg.from_agent] = content
                
                # Remove from pending
                for task_id, agent_id in list(task_agents.items()):
                    if agent_id == msg.from_agent:
                        del task_agents[task_id]
        
        return results
    
    def _synthesize(self, results: Dict[str, Any], original_request: str) -> str:
        """Combine subagent outputs into coherent response"""
        context = self.context.get_context(self.agent_id)
        
        synthesis_prompt = f"""Synthesize these subagent results into a coherent response:
        
Original Request: {original_request}

Subagent Results:
{json.dumps(results, indent=2)}

Provide a unified, coherent response that integrates all findings."""
        
        context.append({"role": "user", "content": synthesis_prompt})
        return self.llm.generate(context)
    
    def _cleanup_subagents(self, agent_ids):
        """Terminate and cleanup subagents"""
        for agent_id in agent_ids:
            if agent_id in self.subagents:
                # Signal termination
                self.mailbox.send(Message(
                    from_agent=self.agent_id,
                    to_agent=agent_id,
                    content="terminate",
                    message_type="command"
                ))
                del self.subagents[agent_id]
```

---

## Part 3: Tool Definitions (TeammateTool Schema)

Based on reverse-engineered findings from paddo.dev:

```python
from typing import Literal

class TeammateTool:
    """
    Tool interface for agent team coordination.
    Matches Claude Code's TeammateTool schema.
    """
    
    name: str = "teammate"
    
    operations = [
        "spawnTeam",      # Create new team
        "discoverTeams",  # List available teams
        "cleanup",        # Cleanup team resources
        "write",          # Direct message to teammate
        "broadcast",      # Message all teammates
        "approvePlan",    # Approve execution plan
        "rejectPlan",     # Reject execution plan
        "requestShutdown",# Request team shutdown
        "approveShutdown",# Approve shutdown request
    ]
    
    def spawn_team(self, team_name: str, agents: List[Dict]) -> str:
        """Create new team with specified agents"""
        pass
    
    def write(self, to_agent: str, message: str, requires_response: bool = False) -> str:
        """Send direct message to teammate"""
        pass
    
    def broadcast(self, message: str) -> str:
        """Send message to all teammates"""
        pass
    
    def approve_plan(self, plan_id: str) -> str:
        """Approve proposed execution plan"""
        pass
```

---

## Part 4: Integration with HiveMind

### 4.1 HiveMind as Lead Agent

```python
class HiveMindLeadAgent(LeadAgent):
    """
    HiveMind integration: Treats HiveMind as the Lead Agent,
    with Bees (workflows) as subagent tasks.
    """
    
    def __init__(self, hivemind_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hivemind = hivemind_instance
    
    def spawn_subagent(self, role: AgentRole, task_description: str) -> str:
        """Spawn subagent as HiveMind Bee"""
        # Create bee workflow
        bee = self.hivemind.create_bee(
            name=f"agent_{role.value}_{uuid.uuid4().hex[:6]}",
            bee_type=BeeType.DEPLOYMENT if role in [AgentRole.CODER, AgentRole.TESTER] else BeeType.TRAINING,
            nodes=self._role_to_nodes(role, task_description)
        )
        
        # Spawn bee
        instance_id = self.hivemind.spawn_bee(bee.id, {
            'task': task_description,
            'parent_agent': self.agent_id
        })
        
        return instance_id
    
    def _role_to_nodes(self, role: AgentRole, task: str) -> List[Node]:
        """Convert agent role to HiveMind workflow nodes"""
        if role == AgentRole.RESEARCHER:
            return [
                Node('search', 'web_search', {'query': task}),
                Node('analyze', 'llm', {'prompt': f'Analyze: {task}'}),
                Node('store', 'vector_store', {}, {'texts': 'analyze.output'})
            ]
        elif role == AgentRole.CODER:
            return [
                Node('generate', 'llm', {'prompt': f'Write code for: {task}'}),
                Node('write', 'file_writer', {'path': './output/code.py'}),
                Node('test', 'code_execute', {'code': 'python -m pytest'})
            ]
        # ... other roles
```

---

## Part 5: Best Practices & Anti-Patterns

### 5.1 When to Use Multi-Agent

**DO Use** (High-value parallel tasks):
- Research across multiple sources simultaneously
- Code generation + testing in parallel
- Multi-file refactoring
- Security audit + performance analysis

**DON'T Use** (Overkill):
- Simple Q&A (15x token cost)
- Single-file edits
- Tasks with strict sequential dependencies
- Low-complexity requests

### 5.2 Token Budget Management

```python
class TokenBudget:
    """Track and enforce token limits per agent"""
    
    def __init__(self, max_tokens: int = 100000):
        self.max_tokens = max_tokens
        self.used_tokens = 0
    
    def check_budget(self, estimated_tokens: int) -> bool:
        return (self.used_tokens + estimated_tokens) <= self.max_tokens
    
    def spend(self, tokens: int):
        self.used_tokens += tokens
        if self.used_tokens > self.max_tokens * 0.8:
            # Warn at 80%
            pass
```

### 5.3 Error Handling

```python
class AgentErrorHandler:
    """Handle subagent failures gracefully"""
    
    def handle_failure(self, agent_id: str, error: Exception) -> str:
        strategies = {
            'timeout': self._retry_with_longer_timeout,
            'context_overflow': self._summarize_and_retry,
            'tool_error': self._escalate_to_lead,
        }
        
        error_type = self._classify_error(error)
        strategy = strategies.get(error_type, self._escalate_to_lead)
        return strategy(agent_id, error)
```

---

## Part 6: Summary

### Key Architectural Decisions

1. **Lead + Subagent Hierarchy**: Clear chain of command
2. **Filesystem Artifacts**: Reference passing, not content passing
3. **Tool-Based Communication**: Async, decoupled messaging
4. **Context Isolation**: No leakage between agents
5. **Parallel by Default**: Maximize throughput

### Implementation Checklist

- [ ] AgentContextManager for isolated contexts
- [ ] ArtifactStore with reference passing
- [ ] Mailbox for inter-agent messaging
- [ ] LeadAgent orchestration logic
- [ ] Subagent lifecycle management
- [ ] Token budget tracking
- [ ] Error handling and retry logic
- [ ] Integration with HiveMind Bees

### References

1. Anthropic: "Building Effective Agents" (Dec 2024)
2. Anthropic Engineering: "How we built our multi-agent research system" (Jun 2025)
3. Claude Code Docs: "Orchestrate teams of Claude Code sessions"
4. paddo.dev: "Claude Code's Hidden Multi-Agent System" (Jan 2026)
5. GitHub: realmikekelly/claude-sneakpeek

---

*"A single agent is a conversation. A multi-agent system is an organization."*
'''

with open('/mnt/kimi/output/CLAUDE_AGENT.md', 'w', encoding='utf-8') as f:
    f.write(claude_agent_content)

print("CLAUDE_AGENT.md created successfully!")
print(f"Total length: {len(claude_agent_content)} characters")
print(f"Total lines: {len(claude_agent_content.splitlines())}")
