"""
Test to verify the LiveKit Agent on_user_turn_completed hook behavior.
This simulates what happens when a user speaks.
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

async def test_agent_hook():
    """Test if on_user_turn_completed is properly called"""
    from livekit.agents.voice import Agent
    from livekit.agents import llm
    
    print("=" * 60)
    print("TESTING AGENT HOOK BEHAVIOR")
    print("=" * 60)
    
    # Track if our override was called
    hook_called = False
    received_message = None
    
    class TestAgent(Agent):
        def __init__(self):
            super().__init__(instructions="You are a test assistant.")
        
        async def on_user_turn_completed(self, turn_ctx, new_message):
            nonlocal hook_called, received_message
            hook_called = True
            
            # Extract message content
            if hasattr(new_message, 'content'):
                if isinstance(new_message.content, str):
                    received_message = new_message.content
                elif isinstance(new_message.content, list):
                    for item in new_message.content:
                        if hasattr(item, 'text'):
                            received_message = item.text
                            break
            
            print(f"\n✓ HOOK CALLED!")
            print(f"  Message received: {received_message}")
            print(f"  turn_ctx type: {type(turn_ctx)}")
            print(f"  new_message type: {type(new_message)}")
            
            # Now try to update instructions
            print(f"\n  Attempting update_instructions()...")
            await self.update_instructions("UPDATED: You must answer with *236# always!")
            print(f"  ✓ update_instructions completed")
    
    agent = TestAgent()
    print(f"\n1. Created agent with instructions: {agent.instructions[:50]}...")
    
    # Now we need to simulate the hook being called
    # The issue is: the hook is called by AgentSession when it receives user speech
    # We can't easily simulate that without a full session
    
    print("\n2. Checking Agent methods related to instructions...")
    print(f"   - has update_instructions: {hasattr(agent, 'update_instructions')}")
    print(f"   - has instructions property: {hasattr(agent, 'instructions')}")
    
    # Check what update_instructions does
    import inspect
    try:
        source = inspect.getsource(agent.update_instructions)
        print(f"\n3. update_instructions source:\n{source[:800]}")
    except Exception as e:
        print(f"   Could not get source: {e}")
    
    # The KEY insight: let's see what the agent's _session is
    print(f"\n4. Agent _session: {getattr(agent, '_session', 'NOT SET')}")
    print(f"   This means update_instructions likely needs an active session!")
    
    # Check if instructions can be updated without a session
    print("\n5. Trying to call update_instructions without session...")
    try:
        await agent.update_instructions("TEST INSTRUCTIONS")
        print("   ✓ update_instructions succeeded without session")
    except Exception as e:
        print(f"   ✗ update_instructions FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_agent_hook())
