"""Check current agent instructions"""
import asyncio
from database import get_db_pool

async def check_instructions():
    pool = await get_db_pool()
    
    # Get active instructions
    row = await pool.fetchrow("""
        SELECT name, LEFT(instructions, 500) as instructions_preview, initial_greeting 
        FROM agent_instructions 
        WHERE is_active = true AND is_local_mode = true
    """)
    
    if row:
        print("="*60)
        print(f"Active Instructions: {row['name']}")
        print("="*60)
        print(f"Preview: {row['instructions_preview']}...")
        print(f"\nInitial Greeting: {row['initial_greeting']}")
    else:
        print("No active instructions found in database!")
    
    await pool.close()

asyncio.run(check_instructions())
