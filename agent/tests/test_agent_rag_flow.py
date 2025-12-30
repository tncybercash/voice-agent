"""
Test if RAG is actually being used in the agent.
This simulates what happens when a user speaks.
"""
import asyncio
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_agent_rag():
    """Simulate the agent's RAG flow"""
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    print("="*60)
    print("SIMULATING AGENT RAG FLOW")
    print("="*60)
    
    # 1. Initialize like the agent does
    from database import get_db_pool
    from database.rag import RAGIndexer, RAGService, EmbeddingService
    
    print("\n1. Initializing services (like agent startup)...")
    db_pool = await get_db_pool()
    
    # Use the SAME environment variables as the agent
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "ollama")
    embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    print(f"   Embedding Provider: {embedding_provider}")
    print(f"   Embedding Model: {embedding_model}")
    print(f"   Ollama URL: {ollama_url}")
    
    embedding_service = EmbeddingService(
        provider=embedding_provider, 
        model=embedding_model,
        ollama_url=ollama_url
    )
    await embedding_service.initialize()
    print(f"   Embedding dimension: {embedding_service.dimension}")
    
    docs_path = Path(__file__).parent / "docs"
    indexer = RAGIndexer(
        docs_path=str(docs_path),
        db_pool=db_pool,
        embedding_service=embedding_service,
        chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "1000")),
        chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
    )
    
    rag_service = RAGService(indexer)
    print("   RAG service initialized")
    
    # 2. Load base instructions (like agent does)
    print("\n2. Loading agent instructions...")
    from database.repository import AgentInstructionRepository
    repo = AgentInstructionRepository(db_pool)
    instruction = await repo.get_active_instruction(is_local_mode=True)
    base_instructions = instruction.instructions if instruction else "You are Batsi."
    print(f"   Loaded instructions: {len(base_instructions)} chars")
    
    # 3. Simulate user asking about USSD code
    user_query = "What is your USSD code"
    print(f"\n3. Simulating user query: '{user_query}'")
    
    # 4. Call augment_prompt (what _augment_instructions does)
    print("\n4. Calling rag_service.augment_prompt()...")
    augmented = await rag_service.augment_prompt(user_query, base_instructions)
    
    print(f"   Base instructions: {len(base_instructions)} chars")
    print(f"   Augmented instructions: {len(augmented)} chars")
    print(f"   Context added: {len(augmented) - len(base_instructions)} chars")
    
    # 5. Check if USSD code is in augmented
    if "*236#" in augmented:
        print("\n   [OK] USSD code *236# IS in augmented instructions!")
    else:
        print("\n   [FAIL] USSD code *236# NOT in augmented instructions!")
    
    # 6. Show what LLM would receive
    print("\n" + "="*60)
    print("AUGMENTED INSTRUCTIONS (first 3000 chars):")
    print("="*60)
    print(augmented[:3000])
    
    await db_pool.close()
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_agent_rag())
