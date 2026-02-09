import json
import threading
import uuid
import time
from typing import Dict, List, Optional, Any
from .base import Agent, Task, Plan, AgentRole, AgentState, Message, AgentContextManager
from .artifacts import ArtifactStore, Mailbox

class LeadAgent:
    """
    Lead Agent: Coordinates specialized subagents.
    Based on the 'Lead + Subagent' pattern from claude_agent.md.
    """
    
    def __init__(self, agent_id: str, context_manager: AgentContextManager,
                 artifact_store: ArtifactStore, mailbox: Mailbox, hivemind_ref=None):
        self.agent_id = agent_id
        self.context = context_manager
        self.artifacts = artifact_store
        self.mailbox = mailbox
        self.hivemind = hivemind_ref  # Reference to HiveMind for LLM/tools
        
        self.subagents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}
        self.active_plans: Dict[str, Plan] = {}
        
        # Initialize context
        self.context.create_context(agent_id, self._get_system_prompt())
        self.mailbox.register_agent(agent_id)
        
        # Start mailbox listener thread
        # threading.Thread(target=self._listen_for_messages, daemon=True).start()

    def _get_system_prompt(self) -> str:
        return """You are the Lead Agent (Elara) in the Cynapse HiveMind.
Your role is to orchestrate a team of specialized subagents to solve complex tasks.

Responsibilities:
1. Decompose user requests into parallel subtasks.
2. Spawn specialized subagents (Researcher, Coder, Tester).
3. Coordinate execution using async messaging.
4. Synthesize final results from subagent artifacts.

Methodology:
- Avoid passing full context; use reference paths to artifacts (files).
- Monitor subagents and handle failures.
"""
    
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
        # self.context.create_context(agent_id, system_prompt) # Context managed by HiveMind node
        self.mailbox.register_agent(agent_id)
        
        # Store agent
        self.subagents[agent_id] = agent
        
        # Execute subagent: In Cynapse, this maps to a HiveMind Bee (Workflow)
        # We spawn a bee that runs the subagent logic
        if self.hivemind:
            bee_id = self._create_agent_bee(agent_id, role, task_description)
            self.hivemind.spawn_bee_instance(bee_id, {
                'task': task_description, 
                'role': role.value,
                'agent_id': agent_id,
                'parent_id': self.agent_id,
                'workspace': agent.workspace_path
            })
        
        return agent_id
    
    def _create_agent_bee(self, agent_id: str, role: AgentRole, task: str) -> str:
        """
        Dynamically creates a Bee workflow definition for this agent.
        This maps the Agent abstract concept to a concrete HiveMind Workflow.
        """
        # This would interface with HiveMind to create a temporary .md workflow
        # For now, we assume a generic 'agent_runner' bee exists or we create one on fly
        # Returning a placeholder bee ID
        return "agent_runner" 

    def _get_role_prompt(self, role: AgentRole) -> str:
        prompts = {
            AgentRole.RESEARCHER: "You are a Research Agent. Gather information and write findings to artifacts.",
            AgentRole.CODER: "You are a Code Generation Agent. Write code and tests to your workspace.",
            AgentRole.TESTER: "You are a Testing Agent. Run tests and report bugs.",
            AgentRole.REVIEWER: "You are a Code Review Agent. Review code for quality and security."
        }
        return prompts.get(role, "You are a specialized subagent.")

    def orchestrate(self, user_request: str) -> str:
        """
        Main entry point:
        1. Plan
        2. Spawn
        3. Wait
        4. Synthesize
        """
        print(f"🤖 Lead Agent: Orchestrating '{user_request}'...")
        
        # 1. Plan (Simplified for v2.2 - normally uses LLM)
        # For demo, if request contains "research", spawn researcher
        tasks = []
        if "research" in user_request.lower() or "find" in user_request.lower():
            tasks.append(Task(description=user_request, role=AgentRole.RESEARCHER))
        elif "code" in user_request.lower() or "write" in user_request.lower():
            tasks.append(Task(description=user_request, role=AgentRole.CODER))
        else:
            # Default to researcher
            tasks.append(Task(description=user_request, role=AgentRole.RESEARCHER))
            
        # 2. Spawn Subagents
        active_agents = {}
        for task in tasks:
            print(f"  ↳ Spawning {task.role.value} for: {task.description}")
            agent_id = self.spawn_subagent(task.role, task.description)
            active_agents[agent_id] = task
            task.assigned_to = agent_id
            task.status = AgentState.EXECUTING
            
        # 3. Wait for feedback (Simulated for this implementation step)
        # In a real async loop we'd wait for Mailbox messages
        # Here we just acknowledge the spawn
        
        return f"Orchestration started: {len(active_agents)} agents spawned."
