import time
from .core import AgentState, Message
from .store import AgentContextManager, ArtifactStore
from .mailbox import Mailbox

class Subagent:
    """
    Worker agent that executes tasks in a separate thread.
    """
    
    def __init__(self, agent_id: str, llm_client, context_manager: AgentContextManager,
                 artifact_store: ArtifactStore, mailbox: Mailbox):
        self.agent_id = agent_id
        self.llm = llm_client
        self.context = context_manager
        self.artifacts = artifact_store
        self.mailbox = mailbox
        self.running = True
        
    def run(self, task_description: str, lead_agent_id: str):
        """Execute subagent loop"""
        try:
            # 1. Update context
            context = self.context.get_context(self.agent_id)
            context.append({"role": "user", "content": task_description})
            
            # 2. Execute with LLM (Mocked for now if no real LLM client)
            if hasattr(self.llm, 'generate'):
                response = self.llm.generate(context)
            else:
                # Mock response for testing/prototype
                time.sleep(2) # Simulate work
                response = f"Processed: {task_description}"
            
            # 3. Write output to artifact store
            output_path = self.artifacts.write_artifact(
                self.agent_id, "output", 
                {"task": task_description, "result": response}
            )
            
            # 4. Notify lead agent
            self.mailbox.send(Message(
                from_agent=self.agent_id,
                to_agent=lead_agent_id,
                content="Task completed",
                message_type="completion",
                reference_path=output_path
            ))
            
        except Exception as e:
            self.mailbox.send(Message(
                from_agent=self.agent_id,
                to_agent=lead_agent_id,
                content=str(e),
                message_type="error"
            ))
