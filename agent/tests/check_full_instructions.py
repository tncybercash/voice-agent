"""Check FULL agent instructions from database"""
import asyncio
from database import get_db_pool

async def check_instructions():
    pool = await get_db_pool()
    
    # Get active instructions - FULL content
    row = await pool.fetchrow("""
        SELECT name, instructions
        FROM agent_instructions 
        WHERE is_active = true AND is_local_mode = true
    """)
    
    if row:
        print("="*60)
        print(f"Active Instructions: {row['name']}")
        print("="*60)
        instructions = row['instructions']
        
        # Check for USSD codes in instructions
        if "*141" in instructions:
            print("\n⚠️ WARNING: Old USSD code *141 found in instructions!")
        if "*236#" in instructions:
            print("\n✓ Correct USSD code *236# found in instructions!")
        if "USSD" in instructions.upper():
            print(f"\n🔍 Found USSD mention in instructions")
        
        # Search for any * codes
        import re
        codes = re.findall(r'\*\d+[#*\d]*', instructions)
        if codes:
            print(f"\n📱 All * codes found in instructions: {codes}")
        
        print("\n" + "="*60)
        print("FULL INSTRUCTIONS:")
        print("="*60)
        print(instructions)
    else:
        print("No active instructions found in database!")
    
    await pool.close()

asyncio.run(check_instructions())
