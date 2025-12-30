"""Analyze all chunks to understand content distribution"""
import asyncio

async def analyze():
    from database import get_db_pool
    
    db_pool = await get_db_pool()
    
    # Get all chunks
    sql = """
        SELECT chunk_index, content, LENGTH(content) as length
        FROM rag_documents
        ORDER BY chunk_index
    """
    rows = await db_pool.fetch(sql)
    
    print(f"Total chunks: {len(rows)}\n")
    
    for row in rows:
        print(f"{'='*60}")
        print(f"Chunk {row['chunk_index']} ({row['length']} chars)")
        print('='*60)
        content = row['content']
        
        # Check for USSD mentions
        if 'ussd' in content.lower() or '*263#' in content:
            print(">>> CONTAINS USSD REFERENCE <<<")
        
        # Show first 400 chars
        print(content[:400])
        if len(content) > 400:
            print("...")
        print()
    
    await db_pool.close()

if __name__ == "__main__":
    asyncio.run(analyze())
