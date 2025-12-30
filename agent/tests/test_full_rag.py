"""Test the complete RAG flow - from user query to augmented instructions"""
import asyncio
import logging
from database import get_db_pool
from database.rag import RAGIndexer, RAGService, EmbeddingService
from pathlib import Path
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_full_rag_flow():
    """Test the complete RAG pipeline"""
    
    print("="*60)
    print("TESTING COMPLETE RAG FLOW")
    print("="*60)
    
    # 1. Initialize database
    print("\n1. Connecting to database...")
    db_pool = await get_db_pool()
    print("   OK Connected")
    
    # 2. Initialize embedding service with Ollama
    print("\n2. Initializing Ollama embeddings...")
    embedding_service = EmbeddingService(
        provider="ollama",
        model="nomic-embed-text:latest",
        ollama_url="http://localhost:11434"
    )
    await embedding_service.initialize()
    print(f"   ✓ Embedding model loaded: {embedding_service.model_name} (dim={embedding_service.dimension})")
    
    # 3. Initialize RAG indexer
    print("\n3. Setting up RAG indexer...")
    docs_path = Path(__file__).parent / "docs"
    indexer = RAGIndexer(
        docs_path=str(docs_path),
        db_pool=db_pool,
        embedding_service=embedding_service,
        chunk_size=1000,
        chunk_overlap=200
    )
    print(f"   ✓ Indexer initialized, docs path: {docs_path}")
    
    # 4. Create RAG service
    print("\n4. Creating RAG service...")
    rag_service = RAGService(indexer)
    print("   ✓ RAG service created")
    
    # 5. Test query
    query = "What is the USSD code"
    print(f"\n5. Testing query: '{query}'")
    
    # 5a. Test search
    print("\n   5a. Running search...")
    results = await indexer.search(query, limit=5, similarity_threshold=-1.0)
    print(f"   Found {len(results)} results:")
    for i, r in enumerate(results, 1):
        print(f"      {i}. similarity={r['similarity']:.4f} [chunk {r['chunk_index']}]")
        print(f"         Preview: {r['content'][:100]}...")
    
    # 5b. Test get_context
    print("\n   5b. Getting context...")
    context = await rag_service.get_context(query)
    print(f"   Context length: {len(context)} chars")
    if "*236#" in context:
        print("   ✓ USSD code *236# found in context!")
    else:
        print("   ✗ WARNING: USSD code *236# NOT found in context!")
    
    # 5c. Test augment_prompt
    print("\n   5c. Testing augment_prompt...")
    base_instructions = "You are Batsi, a TN CyberTech Bank assistant."
    augmented = await rag_service.augment_prompt(query, base_instructions)
    print(f"   Base instructions length: {len(base_instructions)}")
    print(f"   Augmented instructions length: {len(augmented)}")
    
    if "*236#" in augmented:
        print("   ✓ USSD code *236# found in augmented prompt!")
    else:
        print("   ✗ WARNING: USSD code *236# NOT found in augmented prompt!")
    
    # Show the augmented prompt
    print("\n" + "="*60)
    print("AUGMENTED PROMPT (what the LLM sees):")
    print("="*60)
    print(augmented[:2000])
    if len(augmented) > 2000:
        print(f"\n... [truncated, total {len(augmented)} chars]")
    
    await db_pool.close()
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_full_rag_flow())
