"""Debug RAG embedding search"""
import asyncio
import sys
import logging

logging.basicConfig(level=logging.WARNING)  # Reduce noise

async def test_rag():
    from database import get_db_pool
    from database.rag import RAGIndexer, RAGService, EmbeddingService
    from pathlib import Path
    
    # Initialize
    print("Initializing database...")
    db_pool = await get_db_pool()
    
    print("Initializing RAG service...")
    embedding_service = EmbeddingService()
    docs_path = Path(__file__).parent / "docs"
    indexer = RAGIndexer(
        docs_path=str(docs_path),
        db_pool=db_pool,
        embedding_service=embedding_service,
        chunk_size=1000,
        chunk_overlap=200
    )
    rag_service = RAGService(indexer)
    
    # Test queries
    test_queries = [
        "What is the USSD code",
        "What are your operating hours",
        "How do I open an account",
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: '{query}'")
        print('='*60)
        
        results = await indexer.search(query, limit=5, similarity_threshold=-1.0)
        
        print(f"Top {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. similarity={result['similarity']:.4f} [chunk {result['chunk_index']}]")
            content_preview = result['content'][:120].replace('\n', ' ')
            print(f"     {content_preview}...")
    
    await db_pool.close()
    print("\n\nDone!")

if __name__ == "__main__":
    asyncio.run(test_rag())
