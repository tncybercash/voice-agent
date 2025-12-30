"""Quick check of chunk content"""
import asyncio
from database import get_db_pool

async def check():
    pool = await get_db_pool()
    rows = await pool.fetch(
        'SELECT chunk_index, LEFT(content, 250) as preview FROM rag_documents ORDER BY chunk_index'
    )
    for r in rows:
        print(f"\n{'='*60}")
        print(f"Chunk {r['chunk_index']}")
        print('='*60)
        print(r['preview'])
        if '*263#' in r['preview'] or 'ussd' in r['preview'].lower():
            print(">>> CONTAINS USSD/CODE <<<")
    await pool.close()

asyncio.run(check())
