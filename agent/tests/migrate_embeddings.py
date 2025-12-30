"""Update RAG table to support 768-dimensional embeddings (nomic-embed-text)"""
import asyncio
import logging
from database import get_db_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    """Update rag_documents table for new embedding dimensions"""
    
    db_pool = await get_db_pool()
    
    try:
        # Drop and recreate the table with new dimension
        logger.info("Dropping existing rag_documents table...")
        await db_pool.execute("DROP TABLE IF EXISTS rag_documents CASCADE")
        
        logger.info("Creating rag_documents table with 768 dimensions...")
        await db_pool.execute("""
            CREATE TABLE rag_documents (
                id SERIAL PRIMARY KEY,
                filename TEXT NOT NULL,
                content TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                total_chunks INTEGER NOT NULL,
                embedding vector(768),  -- Changed from 384 to 768 for nomic-embed-text
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(filename, chunk_index)
            )
        """)
        
        logger.info("Creating index on embeddings...")
        await db_pool.execute("""
            CREATE INDEX ON rag_documents USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        
        logger.info("✓ Migration complete!")
        logger.info("  - Table recreated with 768-dimensional vectors")
        logger.info("  - IVFFlat index created for fast similarity search")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await db_pool.close()

if __name__ == "__main__":
    asyncio.run(migrate())
