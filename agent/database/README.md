# Database Setup Guide

## Quick Start (New Server Deployment)

When deploying to a new server with a fresh PostgreSQL database, the system will automatically create all required tables.

### Prerequisites
1. PostgreSQL 13+ installed
2. PostgreSQL extensions: `uuid-ossp` and `pgvector`
3. Database user with CREATE privileges

### Automatic Table Creation

The `init.sql` script will create all tables automatically on first run:

```bash
psql -U postgres -d voice_agent -f agent/database/init.sql
```

### Tables Created

#### Core Tables
1. **agent_instructions** - System prompts and configurations
2. **agent_sessions** - User conversation sessions (includes `duration_seconds`)
3. **conversation_messages** - All user/assistant messages
4. **user_profiles** - Anonymous and authenticated user tracking
5. **conversation_summaries** - AI-generated conversation summaries

#### Optional Tables
6. **rag_documents** - RAG document storage (can be removed if not using RAG)
7. **system_config** - Key-value configuration store

### Environment Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp agent/.env.example agent/.env
   ```

2. Configure database connection in `.env`:
   ```env
   POSTGRES_HOST=127.0.0.1
   POSTGRES_PORT=5432
   POSTGRES_DB=voice_agent
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_secure_password
   ```

3. Run the initialization:
   ```bash
   psql -U postgres -d voice_agent -f agent/database/init.sql
   ```

### Features Included

- ✅ **Conversation Duration Tracking** - `agent_sessions.duration_seconds`
- ✅ **User Profile Management** - Anonymous and authenticated users
- ✅ **Message History** - Full conversation storage
- ✅ **Conversation Summaries** - AI-generated summaries with key topics
- ✅ **Multi-tenancy** - Profile-based session isolation
- ✅ **Vector Search** - pgvector support for RAG (optional)

### Verify Installation

Check that tables were created:

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;
```

Expected tables:
- agent_instructions
- agent_sessions
- conversation_messages
- conversation_summaries
- rag_documents (optional)
- system_config
- user_profiles

### First Run

The system will automatically:
1. Create default agent instructions
2. Insert system configuration defaults
3. Set up database triggers for auto-updating timestamps
4. Grant necessary permissions

No manual migrations needed! 🚀
