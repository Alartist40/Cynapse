import json
import uuid
import threading
import time
from typing import Dict, Any, List
from .core import Agent, Task, AgentRole, AgentState, Message
from .store import AgentContextManager, ArtifactStore
from .mailbox import Mailbox
from .worker import Subagent

class Plan:
    def __init__(self, goal: str, tasks: List[Task], strategy: str = "parallel", created_by: str = ""):
        self.id = str(uuid.uuid4())[:8]
        self.goal = goal
        self.tasks = tasks
        self.strategy = strategy
        self.created_by = created_by

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
        # In a real system, this might be a separate process or container
        worker = Subagent(agent_id, self.llm, self.context, self.artifacts, self.mailbox)
        thread = threading.Thread(
            target=worker.run,
            args=(task_description, self.agent_id)
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
    
    def orchestrate(self, user_request: str) -> str:
        """Main entry point for user requests"""
        # Add to context
        self.context.add_message(self.agent_id, "user", user_request)
        
        # Step 1: Plan decomposition
        # For this prototype, we'll do a simple mock plan or direct execution
        # In a real implementation, we'd use the LLM to generate the plan
        plan = self._create_simplistic_plan(user_request)
        
        # Step 2: Spawn subagents for parallel tasks
        task_agents = {}
        for task in plan.tasks:
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
    
    def _create_simplistic_plan(self, user_request: str) -> Plan:
        """Simple rule-based planner for prototype"""
        tasks = []
        if "research" in user_request.lower():
            tasks.append(Task(role=AgentRole.RESEARCHER, description=user_request))
        elif "code" in user_request.lower() or "write" in user_request.lower():
            tasks.append(Task(role=AgentRole.CODER, description=user_request))
        else:
            # Default to researcher
            tasks.append(Task(role=AgentRole.RESEARCHER, description=user_request))
            
        return Plan(goal=user_request, tasks=tasks)
    
    def _wait_for_completion(self, task_agents: Dict[str, str], timeout: float = 300.0) -> Dict[str, Any]:
        """Wait for all subagents to complete"""
        results = {}
        start_time = time.time()
        
        # Create a reverse mapping for easier lookup
        agent_to_task = {v: k for k, v in task_agents.items()}
        pending_agents = set(task_agents.values())
        
        while pending_agents and (time.time() - start_time) < timeout:
            msg = self.mailbox.receive(self.agent_id, block=True, timeout=1.0)
            
            if msg and msg.message_type == "completion":
                # Read artifact
                if msg.reference_path:
                    content = self.artifacts.read_artifact(msg.reference_path)
                else:
                    content = msg.content
                    
                results[msg.from_agent] = content
                
                if msg.from_agent in pending_agents:
                    pending_agents.remove(msg.from_agent)
            
            elif msg and msg.message_type == "error":
                results[msg.from_agent] = f"Error: {msg.content}"
                if msg.from_agent in pending_agents:
                    pending_agents.remove(msg.from_agent)
        
        return results
    
    def _synthesize(self, results: Dict[str, Any], original_request: str) -> str:
        """Combine subagent outputs into coherent response"""
        # In real implementation: use LLM to synthesize
        # For prototype: simple concatenation
        
        synthesis = f"Results for: {original_request}\n\n"
        for agent_id, result in results.items():
            role = self.subagents[agent_id].role.value
            synthesis += f"--- Agent {role} ({agent_id}) ---\n"
            if isinstance(result, dict):
                synthesis += json.dumps(result, indent=2)
            else:
                synthesis += str(result)
            synthesis += "\n\n"
            
        return synthesis
    
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
