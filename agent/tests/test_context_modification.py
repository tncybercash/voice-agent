"""
Test to verify chat context modification works for RAG augmentation.
This simulates exactly what happens in on_user_turn_completed.
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

async def test_chat_context_modification():
    """Test modifying chat context with RAG augmented instructions"""
    from livekit.agents import llm as llm_mod
    from database.rag import RAGService, RAGIndexer, EmbeddingService
    from database import get_db_pool
    
    print("=" * 60)
    print("TESTING CHAT CONTEXT MODIFICATION")
    print("=" * 60)
    
    # 1. Initialize RAG service (same as agent startup)
    print("\n1. Initializing RAG service...")
    db_pool = await get_db_pool()
    
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "ollama")
    embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    embedding_service = EmbeddingService(
        provider=embedding_provider, 
        model=embedding_model,
        ollama_url=ollama_url
    )
    await embedding_service.initialize()
    print(f"   Embedding: {embedding_provider}/{embedding_model}")
    
    docs_path = Path(__file__).parent / "docs"
    indexer = RAGIndexer(
        docs_path=str(docs_path),
        db_pool=db_pool,
        embedding_service=embedding_service,
        chunk_size=1000,
        chunk_overlap=200
    )
    
    rag_service = RAGService(indexer)
    print("   RAG service ready!")
    
    # 2. Create a mock chat context (simulating what LiveKit creates)
    print("\n2. Creating mock chat context (like LiveKit's temp_mutable_chat_ctx)...")
    base_instructions = """You are Batsi, a friendly voice assistant for TN CyberTech Bank.

STYLE:
- Be conversational and friendly
- Give SHORT responses (1-2 sentences)

BANKING: Ask for login before transactions.
GENERAL: Just respond naturally."""

    chat_ctx = llm_mod.ChatContext()
    chat_ctx.add_message(role='system', content=base_instructions)
    chat_ctx.add_message(role='assistant', content='Hello! How can I help you today?')
    # User message is added SEPARATELY, not in this context
    
    print(f"   Initial items: {len(chat_ctx.items)}")
    print(f"   System message: {chat_ctx.items[0].content[0][:50]}...")
    
    # 3. Simulate on_user_turn_completed: augment the chat context
    user_query = "What is your USSD code"
    print(f"\n3. User asks: '{user_query}'")
    print("   Calling RAG augment_prompt()...")
    
    augmented = await rag_service.augment_prompt(
        user_query=user_query,
        base_instructions=base_instructions
    )
    
    # 4. NOW the KEY part: modify chat_ctx.items DIRECTLY
    print("\n4. Modifying chat context system message DIRECTLY...")
    for i, item in enumerate(chat_ctx.items):
        if hasattr(item, 'role') and item.role == 'system':
            # Create new system message with augmented instructions
            # Note: content must be a list for ChatMessage
            new_system_msg = llm_mod.ChatMessage(
                id=item.id,
                role='system',
                content=[augmented]  # Must be a list!
            )
            chat_ctx.items[i] = new_system_msg
            print(f"   ✓ Updated system message at index {i}")
            break
    
    # 5. Verify the context now contains USSD code
    print("\n5. Verifying modified chat context...")
    system_msg = chat_ctx.items[0]
    system_content = system_msg.content[0] if isinstance(system_msg.content, list) else system_msg.content
    
    if "*236#" in system_content:
        print("   ✓ SUCCESS! USSD code *236# is in the chat context!")
        print(f"   System message length: {len(system_content)} chars")
    else:
        print("   ✗ FAIL! USSD code not found in chat context")
    
    # 6. Show what the LLM will see
    print("\n6. What the LLM will see (first 1500 chars of system message):")
    print("-" * 60)
    print(system_content[:1500])
    print("-" * 60)
    
    # Cleanup
    from database import close_db_pool
    await close_db_pool()
    print("\n✓ Test complete!")

if __name__ == "__main__":
    asyncio.run(test_chat_context_modification())
