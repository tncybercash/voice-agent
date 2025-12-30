"""
Test script to verify RAG is working properly.
Tests document indexing and retrieval.
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_rag():
    print("=" * 60)
    print("RAG System Test")
    print("=" * 60)
    
    # 1. Test database connection
    print("\n[1] Testing database connection...")
    try:
        from database import get_db_pool
        pool = await get_db_pool()
        print(f"    ✓ Database connected successfully")
        
        # Check if rag_documents table exists and has data
        doc_count = await pool.fetchval("SELECT COUNT(*) FROM rag_documents")
        print(f"    ✓ RAG Documents in database: {doc_count}")
    except Exception as e:
        print(f"    ✗ Database error: {e}")
        return
    
    # 2. Test embedding service
    print("\n[2] Testing embedding service...")
    try:
        from database.rag import EmbeddingService
        embedding_service = EmbeddingService(
            provider="sentence-transformers",
            model="all-MiniLM-L6-v2"
        )
        await embedding_service.initialize()
        
        test_text = "What are the bank's operating hours?"
        embedding = await embedding_service.embed(test_text)
        print(f"    ✓ Embedding service working")
        print(f"    ✓ Embedding dimension: {len(embedding)}")
    except Exception as e:
        print(f"    ✗ Embedding error: {e}")
        return
    
    # 3. Test document indexing
    print("\n[3] Testing document indexing...")
    try:
        from database.rag import RAGIndexer
        docs_path = Path(__file__).parent / "docs"
        
        indexer = RAGIndexer(
            docs_path=str(docs_path),
            db_pool=pool,
            embedding_service=embedding_service,
            chunk_size=1000,
            chunk_overlap=200
        )
        
        # Index documents
        print(f"    Indexing documents from: {docs_path}")
        await indexer.index_directory()
        
        # Check counts after indexing
        doc_count = await pool.fetchval("SELECT COUNT(*) FROM rag_documents")
        print(f"    ✓ Document chunks indexed: {doc_count}")
        
        # List indexed documents
        docs = await pool.fetch("SELECT DISTINCT filename FROM rag_documents")
        print("\n    Indexed documents:")
        for doc in docs:
            chunk_count = await pool.fetchval(
                "SELECT COUNT(*) FROM rag_documents WHERE filename = $1", 
                doc['filename']
            )
            print(f"      - {doc['filename']} ({chunk_count} chunks)")
            
    except Exception as e:
        print(f"    ✗ Indexing error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. Test RAG retrieval
    print("\n[4] Testing RAG retrieval...")
    try:
        from database.rag import RAGService
        rag_service = RAGService(indexer)
        
        # Test queries
        test_queries = [
            "What are the bank opening hours?",
            "How do I open an account?",
            "What is the interest rate?",
            "How do I transfer money?",
        ]
        
        for query in test_queries:
            print(f"\n    Query: '{query}'")
            results = await rag_service.search(query, top_k=2)
            
            if results:
                print(f"    Found {len(results)} relevant chunks:")
                for i, result in enumerate(results, 1):
                    score = result.get('similarity', result.get('score', 0))
                    content = result.get('content', '')[:100]
                    print(f"      [{i}] Score: {score:.3f}")
                    print(f"          Content: {content}...")
            else:
                print("    No results found")
                
    except Exception as e:
        print(f"    ✗ Retrieval error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. Test context augmentation
    print("\n[5] Testing context augmentation...")
    try:
        context = await rag_service.get_context_for_query(
            "What services does the bank offer?",
            max_tokens=500
        )
        if context:
            print(f"    ✓ Context generated ({len(context)} chars)")
            print(f"    Preview: {context[:200]}...")
        else:
            print("    ✗ No context generated")
    except Exception as e:
        print(f"    ✗ Context error: {e}")
    
    print("\n" + "=" * 60)
    print("RAG Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_rag())
