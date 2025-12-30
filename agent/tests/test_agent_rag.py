"""
Test if agent can pull from RAG
"""
import asyncio
from database import get_db_pool
from database.rag import EmbeddingService, RAGIndexer, RAGService

async def test_agent_rag():
    print("=" * 60)
    print("Testing Agent RAG Integration")
    print("=" * 60)
    
    # Initialize components
    print("\n[1] Initializing database and embedding service...")
    pool = await get_db_pool()
    emb = EmbeddingService()
    await emb.initialize()
    print("    ✓ Ready")
    
    # Create indexer and RAG service
    print("\n[2] Creating RAG service...")
    from pathlib import Path
    indexer = RAGIndexer(
        docs_path=str(Path(__file__).parent / 'docs'),
        db_pool=pool,
        embedding_service=emb
    )
    rag_service = RAGService(indexer)
    print("    ✓ RAG service created")
    
    # Check what's in the database
    print("\n[3] Checking database contents...")
    count = await pool.fetchval('SELECT COUNT(*) FROM rag_documents')
    files = await pool.fetch('SELECT DISTINCT filename FROM rag_documents')
    print(f"    Documents in database: {count} chunks")
    print(f"    Files: {[f['filename'] for f in files]}")
    
    # Test queries
    print("\n[4] Testing RAG queries...")
    test_queries = [
        "What are the bank operating hours?",
        "How do I open an account?",
        "What services does the bank offer?",
        "Can I transfer money?"
    ]
    
    for query in test_queries:
        print(f"\n    Query: '{query}'")
        
        # Get raw search results
        results = await indexer.search(query, limit=2, similarity_threshold=0.1)
        print(f"    Raw results: {len(results)} chunks found")
        
        if results:
            for i, result in enumerate(results, 1):
                print(f"      [{i}] {result['filename']}")
                print(f"          {result['content'][:100]}...")
        
        # Get formatted context
        context = await rag_service.get_context(query, max_tokens=500)
        if context:
            print(f"    Context length: {len(context)} chars")
            print(f"    Context preview: {context[:150]}...")
        else:
            print("    ⚠ No context returned")
    
    # Test augment_prompt
    print("\n[5] Testing prompt augmentation...")
    base_instructions = "You are a helpful banking assistant."
    augmented = await rag_service.augment_prompt(
        "What are your hours?",
        base_instructions
    )
    
    if "Relevant Knowledge Base Context" in augmented:
        print("    ✓ Prompt successfully augmented with RAG context")
        print(f"    Augmented length: {len(augmented)} chars")
    else:
        print("    ✗ Prompt not augmented")
        print(f"    Result: {augmented[:200]}...")
    
    print("\n" + "=" * 60)
    print("RAG Integration Test Complete!")
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(test_agent_rag())
