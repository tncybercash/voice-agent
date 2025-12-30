"""Find USSD content"""
import asyncio
from database import get_db_pool

async def find_ussd():
    pool = await get_db_pool()
    
    # Search for USSD or *263#
    rows = await pool.fetch(
        "SELECT chunk_index, content FROM rag_documents WHERE content LIKE '%USSD%' OR content LIKE '%*263#%' ORDER BY chunk_index"
    )
    
    if rows:
        print(f"Found {len(rows)} chunks with USSD content:\n")
        for row in rows:
            print(f"{'='*60}")
            print(f"Chunk {row['chunk_index']}")
            print('='*60)
            print(row['content'])
            print()
    else:
        print("No USSD content found!")
        print("\nShowing ALL chunks to verify:")
        all_rows = await pool.fetch("SELECT chunk_index, LEFT(content, 150) FROM rag_documents ORDER BY chunk_index")
        for r in all_rows:
            print(f"Chunk {r['chunk_index']}: {r['left']}")
    
    await pool.close()

asyncio.run(find_ussd())
