"""Truncate RAG database and re-index documents"""
import asyncio
import logging
from pathlib import Path
from database import get_db_pool
from database.rag import RAGIndexer, EmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def truncate_and_reindex():
    """Clear RAG data and re-index all documents"""
    
    # Initialize database
    logger.info("Connecting to database...")
    db_pool = await get_db_pool()
    
    try:
        # Truncate the rag_documents table
        logger.info("Truncating rag_documents table...")
        await db_pool.execute("TRUNCATE TABLE rag_documents")
        logger.info("✓ Table truncated")
        
        # Initialize RAG components
        logger.info("\nInitializing RAG service...")
        embedding_service = EmbeddingService()
        await embedding_service.initialize()
        
        docs_path = Path(__file__).parent / "docs"
        indexer = RAGIndexer(
            docs_path=str(docs_path),
            db_pool=db_pool,
            embedding_service=embedding_service,
            chunk_size=1000,
            chunk_overlap=200
        )
        
        # Re-index all documents
        logger.info(f"\nIndexing documents from {docs_path}...")
        results = await indexer.index_directory()
        
        # Show results
        logger.info("\n" + "="*60)
        logger.info("Indexing Results:")
        logger.info("="*60)
        total_chunks = 0
        for filename, chunks in results.items():
            logger.info(f"  {filename}: {chunks} chunks")
            total_chunks += chunks
        logger.info(f"\nTotal: {len(results)} files, {total_chunks} chunks")
        logger.info("="*60)
        
        # Verify
        count = await db_pool.fetchval("SELECT COUNT(*) FROM rag_documents")
        logger.info(f"\n✓ Verified: {count} chunks in database")
        
    finally:
        await db_pool.close()
        logger.info("\nDone!")

if __name__ == "__main__":
    asyncio.run(truncate_and_reindex())
