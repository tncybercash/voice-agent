import asyncio
from database import get_db_pool

async def check():
    pool = await get_db_pool()
    row = await pool.fetchrow('SELECT content FROM rag_documents WHERE chunk_index = 11')
    print("="*60)
    print("Chunk 11 content:")
    print("="*60)
    print(row['content'])
    await pool.close()

asyncio.run(check())
