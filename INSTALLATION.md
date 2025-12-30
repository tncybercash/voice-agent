# Installation Guide for New Features

## Backend Dependencies

The following packages need to be installed for the strict knowledge base and web search features:

### Required Python Packages (Added to requirements.txt)
- `langchain>=0.1.0` - LangChain framework for web search tools
- `langchain-community>=0.1.0` - Community tools including DuckDuckGo search
- `duckduckgo-search>=4.0.0` - DuckDuckGo search API wrapper

### Installation Steps

#### 1. Install Python Dependencies

**Windows (PowerShell):**
```powershell
cd "c:\Users\gregorys\Documents\Grebles Dev\ai-voice-agent\agent"
pip install -r requirements.txt
```

Or install just the new packages:
```powershell
pip install langchain>=0.1.0 langchain-community>=0.1.0 duckduckgo-search>=4.0.0
```

#### 2. Apply Database Migrations

```powershell
cd "c:\Users\gregorys\Documents\Grebles Dev\ai-voice-agent\agent"
$env:PGPASSWORD='Developer@@11'
psql -U postgres -d voice_agent -f database/update_instructions_strict.sql
psql -U postgres -d voice_agent -f database/add_duration_column.sql
```

#### 3. Frontend (No Installation Needed)

The frontend already has all required dependencies:
- ✅ `sonner` - Toast notifications (already in package.json v2.0.7)
- ✅ `@livekit/components-react` - LiveKit hooks (already installed)
- ✅ `next-themes` - Theme support (already installed)

No frontend installation required!

## Verification

### Verify Python Packages Installed
```powershell
pip show langchain langchain-community duckduckgo-search
```

Expected output should show all three packages installed.

### Verify Database Migrations Applied
```powershell
$env:PGPASSWORD='Developer@@11'
psql -U postgres -d voice_agent -c "\d agent_sessions"
```

Should show `duration_seconds` column.

```powershell
psql -U postgres -d voice_agent -c "SELECT substring(instructions, 1, 100) FROM agent_instructions WHERE is_active = true;"
```

Should show "Strict Information Policy" section in instructions.

## Troubleshooting

### Import Error: No module named 'langchain'
**Solution:** Run `pip install langchain langchain-community duckduckgo-search`

### Import Error: No module named 'duckduckgo_search'
**Solution:** Run `pip install duckduckgo-search>=4.0.0`

### Database Error: column "duration_seconds" does not exist
**Solution:** Run the migration: `psql -U postgres -d voice_agent -f database/add_duration_column.sql`

### Frontend: Toast notifications not showing
**Solution:** 
1. Check browser console for errors
2. Verify sonner is installed: `cd front-end && pnpm list sonner`
3. Hard refresh: Ctrl+Shift+R

## Quick Test After Installation

1. **Start agent:**
   ```powershell
   cd agent
   python agent.py
   ```

2. **Start frontend:**
   ```powershell
   cd front-end
   pnpm dev
   ```

3. **Test web search:**
   - Connect to agent
   - Ask: "What's the weather today?"
   - Agent should ask permission
   - Say "yes"
   - Should see toast notifications

4. **Test timer:**
   - Connect to agent
   - Timer should appear in top-left header
   - Should count up (00:00, 00:01, 00:02...)

## Summary

✅ **Backend:** 3 new packages added to requirements.txt
✅ **Frontend:** No new packages needed (all already installed)
✅ **Database:** 2 SQL migrations to run
✅ **Total installation time:** ~2 minutes
