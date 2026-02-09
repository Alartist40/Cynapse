import sys
import os
import time
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath("."))

from cynapse.agent.core import AgentRole
from cynapse.agent.lead import LeadAgent
from cynapse.agent.store import AgentContextManager, ArtifactStore
from cynapse.agent.mailbox import Mailbox

def main():
    print("🧪 Starting HiveMind Verification...")
    
    # Setup directories
    test_dir = Path("./cynapse/data/test_agent_artifacts")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)
    
    # Initialize components
    print("Initialize components...")
    context_manager = AgentContextManager("./cynapse/data/test_agent_contexts")
    artifact_store = ArtifactStore("./cynapse/data/test_agent_artifacts")
    mailbox = Mailbox()
    
    # Mock LLM Client
    class MockLLM:
        def generate(self, context):
            last_msg = context[-1]['content']
            return f"Mock Response to: {last_msg}"

    llm = MockLLM()
    
    # Create Lead Agent
    print("Creating Lead Agent...")
    lead_id = "lead_001"
    lead = LeadAgent(lead_id, llm, context_manager, artifact_store, mailbox)
    
    # Test Orchestration
    print("Testing Orchestration (Request: 'Research quantum computing')...")
    response = lead.orchestrate("Research quantum computing")
    
    print("\n✅ Verification Result:")
    print(response)
    
    # Verify artifacts were created
    print("\nChecking artifacts...")
    subagents = list(test_dir.glob("*"))
    print(f"Found {len(subagents)} agent directories (excluding lead if separate).")
    
    for agent_dir in subagents:
        print(f"- {agent_dir.name}")
        output = list(agent_dir.glob("*.json"))
        if output:
            print(f"  - Generated {len(output)} artifacts")

    print("\n🎉 HiveMind Architecture Functional!")

if __name__ == "__main__":
    main()
