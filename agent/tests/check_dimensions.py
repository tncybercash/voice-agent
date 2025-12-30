"""Check embedding dimensions in database"""
import asyncio
from database import get_db_pool

async def check():
    pool = await get_db_pool()
    
    # Check current embedding dimensions using pgvector function
    row = await pool.fetchrow("""
        SELECT 
            chunk_index,
            vector_dims(embedding) as embedding_dim
        FROM rag_documents 
        LIMIT 1
    """)
    
    if row:
        print(f"Embedding dimension in database: {row['embedding_dim']}")
    
    # Count total chunks
    count = await pool.fetchval("SELECT COUNT(*) FROM rag_documents")
    print(f"Total chunks: {count}")
    
    await pool.close()

asyncio.run(check())
