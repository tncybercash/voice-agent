# Voice AI Agent - Enhanced Backend Setup Guide

## 🎉 System Overview

Your voice AI agent now has:
- **PostgreSQL database** for agent instructions, sessions, and RAG documents
- **Concurrent session management** - supports 20+ simultaneous users with isolated conversations
- **Flexible LLM providers** - switch between Ollama, vLLM (local pip installation), or OpenRouter
- **RAG system with Docling** - advanced document parsing (PDF, DOCX, PPTX, HTML, tables, OCR)
- **Database-backed prompts** - pull agent instructions from PostgreSQL
- **Local STT/TTS** - Speaches Whisper (STT) and Kokoro (TTS) on GPU/CPU

## 🏗️ Architecture

```
Frontend (Next.js) → LiveKit → Agent (Python)
                                  ├─ PostgreSQL (sessions, instructions, RAG)
                                  ├─ vLLM (local LLM inference on port 8000)
                                  ├─ Speaches GPU (STT/TTS on port 8003)
                                  └─ Speaches CPU (fallback on port 8002)
```

## 📋 Complete Setup Steps

### 1. Prerequisites

- Python 3.11.6 (installed)
- PostgreSQL 13+ with pgvector extension
- Docker Desktop (for LiveKit and Speaches)
- NVIDIA GPU with 8GB+ VRAM (for vLLM and Speaches GPU)
- Windows PowerShell

### 2. Initialize PostgreSQL Database

```powershell
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE voice_agent;

# Connect to database
\c voice_agent

# Run initialization script (from ai-voice-agent root directory)
\i agent/database/init.sql

# Verify tables were created
\dt

# Expected output: agent_instructions, agent_sessions, conversation_messages, rag_documents, system_config
```

### 3. Install Python Dependencies

```powershell
# Navigate to agent folder
cd agent

# Activate virtual environment (if execution policy allows)
.\.venv\Scripts\Activate.ps1

# Or use pip directly with venv
.\.venv\Scripts\pip.exe install -r requirements.txt
```

Key dependencies:
- `livekit` + `livekit-agents` - Voice agent framework
- `asyncpg` - Async PostgreSQL driver (5-30 connection pool)
- `sentence-transformers` - RAG embeddings (all-MiniLM-L6-v2, 384 dimensions)
- `docling` - Advanced document parsing (PDF, DOCX, PPTX, HTML, tables, OCR)
- `aiohttp` - Async HTTP for LLM providers with connection pooling
- `aiofiles` - Async file operations
- `vllm` - Local LLM inference server

### 4. Configure Environment Variables

The `.env` file is already configured. Key settings:

```bash
# LLM Provider (currently using vLLM)
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8000
VLLM_MODEL=unsloth/Llama-3.2-1B-Instruct
LLM_MAX_CONCURRENT=20

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_DB=voice_agent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=Developer@@11
POSTGRES_MIN_CONN=5
POSTGRES_MAX_CONN=30

# RAG Settings
RAG_ENABLED=true
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200
EMBEDDING_MODEL=all-MiniLM-L6-v2

# STT/TTS (Speaches GPU)
WHISPER_LOCAL_URL=http://localhost:8003/v1
WHISPER_LOCAL_MODEL=Systran/faster-whisper-base.en
SPEACHES_TTS_URL=http://localhost:8003/v1
SPEACHES_TTS_MODEL=speaches-ai/Kokoro-82M-v1.0-ONNX
SPEACHES_TTS_VOICE=af_heart

# Session Management
SESSION_TIMEOUT_MINUTES=30
```

### 5. Start Docker Services

```powershell
# From ai-voice-agent root directory
docker-compose up -d

# This starts:
# - LiveKit (ports 7880, 7881)
# - Speaches CPU (port 8002)
# - Speaches GPU (port 8003) - requires NVIDIA GPU
```

Verify services:
```powershell
docker ps

# Expected: livekit, speaches (CPU), speaches-gpu containers running
```

### 6. Start vLLM Server

vLLM is installed locally via pip (not Docker) for faster startup:

```powershell
# Activate venv
cd agent
.\.venv\Scripts\python.exe -m vllm.entrypoints.openai.api_server `
    --model unsloth/Llama-3.2-1B-Instruct `
    --port 8000 `
    --host 0.0.0.0 `
    --max-num-seqs 20 `
    --dtype auto `
    --gpu-memory-utilization 0.5 `
    --max-model-len 4096

# Note: First run will download the model (~2.2GB)
# Startup time: 1-2 minutes (much faster than Docker version)
```

**GPU Memory Allocation:**
- vLLM: 50% (4GB) - handles 20 concurrent LLM requests
- Speaches GPU: Remaining 50% - handles STT/TTS

Test vLLM is running:
```powershell
curl http://localhost:8000/v1/models
```

### 7. Verify PostgreSQL Connection

```powershell
# Test database connection
cd agent
python -c "import asyncio; from database.connection import get_db_pool; asyncio.run(get_db_pool().execute('SELECT 1'))"

# Should return without errors
```

## 🎯 Key Features

### 1. Database-Backed Agent Instructions

Update agent prompts without code changes or restarting:

```sql
-- Update instructions
UPDATE agent_instructions 
SET instructions = 'Your new instructions here...
You are a helpful banking assistant...'
WHERE is_active = true AND is_local_mode = true;

-- Set initial greeting
UPDATE agent_instructions
SET initial_greeting = 'Hello! I''m your banking assistant. How can I help you today?'
WHERE id = 1;

-- View current instructions
SELECT name, instructions, initial_greeting, is_active 
FROM agent_instructions 
WHERE is_local_mode = true;
```

### 2. Concurrent User Sessions (20+ Users)

Each user gets completely isolated context:
- **Separate conversation history** - stored per session_id
- **Independent LLM context** - no shared state
- **No conversation overlap** - UUID-based isolation
- **Auto-cleanup** - sessions idle >30min automatically cleaned
- **Database persistence** - all messages saved for analytics

Technical implementation:
- `UserSession` dataclass with UUID session_id
- room_id → session_id mapping for LiveKit integration
- Background asyncio task for cleanup every 60 seconds
- JSONB context field for flexible metadata storage

### 3. RAG Document Indexing with Docling

Drop files in `agent/docs/` folder for automatic indexing:

**Supported formats:**
- **Basic text**: `.txt`, `.md`, `.py`, `.json`, `.csv`, `.log`
- **Advanced parsing (Docling)**: `.pdf`, `.docx`, `.pptx`, `.html`, `.xlsx`
  - Table extraction (converts to markdown)
  - OCR for scanned documents
  - Metadata extraction (title, authors, dates)

**How it works:**
1. Files in `docs/` are detected on startup
2. Docling parses complex documents (tables, layouts, images)
3. Content chunked (1000 chars, 200 overlap)
4. sentence-transformers generates 384-dim embeddings
5. Stored in PostgreSQL with pgvector
6. Semantic search with cosine similarity

**Add new documents:**
```powershell
# Just copy files to docs/ folder
cp "C:\path\to\document.pdf" agent\docs\

# Restart agent or wait for auto-detection
# Agent will index new files automatically
```

### 4. LLM Provider Switching

Switch between providers without code changes:

**vLLM (Current - Recommended for Production):**
```bash
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8000
VLLM_MODEL=unsloth/Llama-3.2-1B-Instruct
```
- Best for: 20+ concurrent users
- Latency: ~50-200ms per request
- Cost: Free (local GPU)
- GPU: 50% allocation (4GB on 8GB card)

**Ollama (Development):**
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest
```
- Best for: Single user testing
- Latency: ~300-500ms per request
- Cost: Free (local)

**OpenRouter (Cloud API):**
```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-4o
```
- Best for: Quick setup, no GPU
- Latency: ~500-1000ms per request
- Cost: Pay per token

**Google Gemini (Cloud LLM):**
```bash
LLM_PROVIDER=google
GOOGLE_API_KEY=your-google-api-key
GOOGLE_MODEL=gemini-2.0-flash
```
- Best for: High-quality responses, large context windows
- Latency: ~200-500ms per request
- Cost: Pay per token (free tier available)
- Get API key from: https://aistudio.google.com/apikey

**Google Realtime API (Speech-to-Speech - Best Quality):**
```bash
LLM_PROVIDER=google_realtime
GOOGLE_API_KEY=your-google-api-key
GOOGLE_REALTIME_MODEL=gemini-2.0-flash-live-001
GOOGLE_REALTIME_VOICE=Puck
```
- Best for: Most natural, human-like conversations
- Features: Direct speech-to-speech, emotional understanding
- Voice options: Puck, Charon, Kore, Fenrir, Aoede
- Latency: Very low (~100-200ms)
- Cost: Pay per audio minute
- Note: When using this mode, STT and TTS are built-in (not needed separately)

**Automatic Failover:**
If primary provider fails, system automatically falls back to next available provider.

### 5. Advanced Document Parsing (Docling Integration)

Docling provides enterprise-grade document processing:

**Features:**
- **PDF parsing**: Extract text, tables, images with layout preservation
- **DOCX/PPTX**: Parse Microsoft Office documents with formatting
- **HTML**: Extract clean text from web pages
- **Table extraction**: Converts tables to markdown format
- **OCR**: Optical character recognition for scanned documents
- **Metadata**: Extract document properties (title, authors, creation date)

**Example indexed content:**
```
Filename: product_catalog.pdf
Chunks: 15
Embedding dimension: 384
Tables extracted: 3 (pricing, features, specifications)
Total tokens: ~12,000
```

**Search relevance:**
- Cosine similarity ranking
- Top 5 most relevant chunks returned
- Injected into LLM prompt as context

## 📊 Database Schema

### agent_instructions
Stores system prompts and initial greetings:
```sql
CREATE TABLE agent_instructions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    instructions TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_local_mode BOOLEAN DEFAULT false,
    initial_greeting TEXT,
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```
- **Purpose**: Database-backed prompts (update without code changes)
- **Usage**: Agent loads `is_active=true AND is_local_mode=true` on startup
- **Example**: Banking assistant instructions, customer service scripts

### agent_sessions
One row per user conversation:
```sql
CREATE TABLE agent_sessions (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL UNIQUE,  -- UUID for isolation
    room_id VARCHAR(255),              -- LiveKit room
    participant_id VARCHAR(255),       -- LiveKit participant
    llm_provider VARCHAR(50),          -- ollama/vllm/openrouter
    status VARCHAR(20) DEFAULT 'active',
    context JSONB,                     -- Flexible metadata
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    last_activity TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP
);
```
- **Purpose**: Track active conversations and user context
- **UUID isolation**: Each session has globally unique ID
- **Auto-cleanup**: Sessions with `last_activity > 30min` marked as ended
- **Concurrency**: Supports 20+ simultaneous sessions

### conversation_messages
Full conversation history:
```sql
CREATE TABLE conversation_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES agent_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,    -- user/assistant/system
    content TEXT NOT NULL,
    metadata JSONB,               -- Timestamps, tokens, latency
    created_at TIMESTAMP DEFAULT NOW()
);
```
- **Purpose**: Persist all messages for analytics and debugging
- **CASCADE delete**: When session ends, messages auto-deleted after retention period
- **Analytics**: Query by session_id for conversation replay
- **Metadata**: Store LLM tokens used, response time, model version

### rag_documents
Document chunks with vector embeddings:
```sql
CREATE TABLE rag_documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    total_chunks INTEGER,
    embedding vector(384),        -- pgvector for similarity search
    file_hash VARCHAR(64),
    metadata JSONB,               -- File type, tables, OCR data
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(filename, chunk_index)
);

-- Vector similarity index (IVFFlat algorithm)
CREATE INDEX rag_documents_embedding_idx ON rag_documents 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```
- **Purpose**: Store document embeddings for semantic search
- **Vector dimension**: 384 (from all-MiniLM-L6-v2 model)
- **Chunking**: 1000 chars per chunk, 200 char overlap
- **Search**: Cosine similarity with IVFFlat index for fast retrieval
- **Deduplication**: file_hash prevents re-indexing unchanged files

### system_config
Key-value configuration store:
```sql
CREATE TABLE system_config (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```
- **Purpose**: Runtime configuration (feature flags, limits, API keys)
- **Flexibility**: JSONB allows complex nested configs
- **Example**: Store LLM temperature, max tokens, timeout settings

## 🔧 Usage Examples

### Query Active Sessions

```sql
-- View all active conversations
SELECT id, session_id, room_id, participant_id, llm_provider, 
       message_count, last_activity
FROM agent_sessions
WHERE status = 'active'
ORDER BY last_activity DESC;

-- Count concurrent users (last 5 minutes)
SELECT COUNT(*) as active_users
FROM agent_sessions
WHERE status = 'active'
AND last_activity > NOW() - INTERVAL '5 minutes';

-- View conversation history for specific session
SELECT role, content, created_at
FROM conversation_messages
WHERE session_id = 'your-uuid-here'
ORDER BY created_at ASC;
```

### Search RAG Documents

```sql
-- Find documents similar to a query embedding
-- (First generate embedding using sentence-transformers)
SELECT 
    filename, 
    content,
    chunk_index,
    1 - (embedding <=> '[0.1, 0.2, ..., 0.384]'::vector) as similarity
FROM rag_documents
WHERE embedding IS NOT NULL
ORDER BY embedding <=> '[0.1, 0.2, ..., 0.384]'::vector
LIMIT 5;

-- List all indexed documents
SELECT 
    filename,
    COUNT(*) as chunks,
    MAX(total_chunks) as total_chunks,
    MAX(created_at) as indexed_at
FROM rag_documents
GROUP BY filename
ORDER BY indexed_at DESC;

-- Search by filename
SELECT filename, chunk_index, content
FROM rag_documents
WHERE filename LIKE '%product%'
ORDER BY chunk_index;
```

### Monitor System Performance

```sql
-- Average messages per session
SELECT 
    AVG(message_count) as avg_messages,
    MAX(message_count) as max_messages,
    COUNT(*) as total_sessions
FROM agent_sessions;

-- Sessions by LLM provider
SELECT 
    llm_provider,
    COUNT(*) as session_count,
    AVG(message_count) as avg_messages
FROM agent_sessions
GROUP BY llm_provider;

-- Busiest times (sessions per hour)
SELECT 
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as sessions_started
FROM agent_sessions
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY hour
ORDER BY hour DESC;
```

### Update Agent Configuration

```sql
-- Update instructions (takes effect immediately for new sessions)
UPDATE agent_instructions 
SET instructions = 'You are a banking assistant specialized in account inquiries.
Always verify user identity before sharing account details.
Be polite and professional.'
WHERE id = 1;

-- Change initial greeting
UPDATE agent_instructions
SET initial_greeting = 'Welcome! I''m your AI banking assistant. How may I assist you today?'
WHERE id = 1;

-- Add new instruction set (multi-language support)
INSERT INTO agent_instructions (name, instructions, is_active, is_local_mode, initial_greeting, language)
VALUES (
    'Banking Assistant - Spanish',
    'Eres un asistente bancario especializado en consultas de cuentas...',
    false,
    true,
    '¡Bienvenido! Soy tu asistente bancario de IA.',
    'es'
);
```

### Clean Up Old Data

```sql
-- Delete ended sessions older than 7 days
DELETE FROM agent_sessions
WHERE status = 'ended'
AND ended_at < NOW() - INTERVAL '7 days';

-- Note: conversation_messages will cascade delete

-- Archive old conversations (before deleting)
CREATE TABLE conversation_messages_archive AS
SELECT * FROM conversation_messages cm
JOIN agent_sessions s ON cm.session_id = s.session_id
WHERE s.ended_at < NOW() - INTERVAL '7 days';

-- Remove old RAG documents
DELETE FROM rag_documents
WHERE filename NOT IN (
    SELECT DISTINCT filename FROM rag_documents
    WHERE created_at > NOW() - INTERVAL '30 days'
);
```

## 🚀 Running the System

### Starting All Services (Complete Workflow)

**Terminal 1 - Docker Services:**
```powershell
# From ai-voice-agent root
docker-compose up -d
docker ps  # Verify LiveKit, Speaches CPU/GPU running
```

**Terminal 2 - vLLM Server:**
```powershell
cd agent
.\.venv\Scripts\python.exe -m vllm.entrypoints.openai.api_server `
    --model unsloth/Llama-3.2-1B-Instruct `
    --port 8000 `
    --host 0.0.0.0 `
    --max-num-seqs 20 `
    --dtype auto `
    --gpu-memory-utilization 0.5 `
    --max-model-len 4096

# Wait for: "Uvicorn running on http://0.0.0.0:8000"
```

**Terminal 3 - Voice Agent:**
```powershell
cd agent
.\.venv\Scripts\python.exe agent.py dev

# The agent will:
# 1. Connect to PostgreSQL and load agent instructions
# 2. Initialize RAG service and index docs/ folder
# 3. Start session manager with cleanup task
# 4. Connect to LLM provider (vLLM)
# 5. Setup STT (Speaches Whisper) and TTS (Speaches Kokoro)
# 6. Connect to LiveKit on ws://localhost:7880
```

**Terminal 4 - Frontend (Next.js):**
```powershell
cd front-end
pnpm dev

# Access UI at: http://localhost:3000
```

### Quick Start (After Initial Setup)

```powershell
# 1. Start Docker (if not running)
docker-compose up -d

# 2. Start vLLM (in separate terminal)
cd agent
.\.venv\Scripts\python.exe -m vllm.entrypoints.openai.api_server --model unsloth/Llama-3.2-1B-Instruct --port 8000 --host 0.0.0.0 --max-num-seqs 20 --dtype auto --gpu-memory-utilization 0.5 --max-model-len 4096

# 3. Start agent (in another terminal)
cd agent
.\.venv\Scripts\python.exe agent.py dev

# 4. Start frontend (in another terminal)
cd front-end
pnpm dev
```

### What Happens on Startup

1. **PostgreSQL Connection**: Agent connects to `voice_agent` database with connection pool (5-30 connections)
2. **Load Instructions**: Fetches active agent instructions from `agent_instructions` table
3. **RAG Initialization**: 
   - Loads sentence-transformers model (all-MiniLM-L6-v2)
   - Scans `docs/` folder for documents
   - Parses files with Docling (PDF, DOCX, PPTX, HTML, tables)
   - Generates embeddings and stores in `rag_documents` table
4. **LLM Provider**: Connects to vLLM on http://localhost:8000
5. **Session Manager**: Starts background cleanup task (every 60s, removes sessions idle >30min)
6. **STT/TTS Setup**: Connects to Speaches GPU on port 8003
7. **LiveKit Connection**: Connects to ws://localhost:7880 and waits for participants

### User Session Flow

1. **User Joins**: Frontend connects to LiveKit room
2. **Session Created**: Agent creates new `UserSession` with:
   - Unique UUID session_id
   - room_id and participant_id mapping
   - Database record in `agent_sessions` table
   - Isolated conversation history
3. **Initial Greeting**: Agent speaks initial_greeting from database
4. **Conversation Loop**:
   - User speaks → Speaches Whisper (STT) → Text
   - RAG augmentation (if enabled and relevant docs found)
   - Text → vLLM (LLM) → Response text
   - Response → Speaches Kokoro (TTS) → Audio
   - Message saved to `conversation_messages` table
5. **User Disconnects**: Session marked as 'ended', cleanup after 30min

### Multiple Concurrent Users

The system handles 20+ concurrent users through:
- **Session Isolation**: Each user has unique UUID session_id
- **Database Pooling**: 30 max PostgreSQL connections
- **LLM Concurrency**: 20 max concurrent vLLM requests (Semaphore)
- **HTTP Connection Pooling**: aiohttp TCPConnector with keepalive
- **Async Architecture**: asyncio for non-blocking I/O

Example: 25 users simultaneously:
- Each gets isolated conversation context
- vLLM processes 20 requests, queues 5
- PostgreSQL handles all DB operations with pooling
- No conversation overlap or context bleeding
1. Connect to PostgreSQL
2. Load instructions from database
3. Index documents from docs/ folder
4. Start LLM provider manager
5. Create isolated sessions per user

## 🔄 Switching LLM Providers

### Current Setup: vLLM (Local, High-Performance)

**Configuration:**
```bash
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8000
VLLM_MODEL=unsloth/Llama-3.2-1B-Instruct
LLM_MAX_CONCURRENT=20
```

**Start Command:**
```powershell
cd agent
.\.venv\Scripts\python.exe -m vllm.entrypoints.openai.api_server `
    --model unsloth/Llama-3.2-1B-Instruct `
    --port 8000 `
    --host 0.0.0.0 `
    --max-num-seqs 20 `
    --dtype auto `
    --gpu-memory-utilization 0.5 `
    --max-model-len 4096
```

**Pros:**
- ✅ Handles 20+ concurrent users
- ✅ Low latency (~50-200ms per request)
- ✅ Free (uses local GPU)
- ✅ OpenAI-compatible API
- ✅ No API rate limits

**Cons:**
- ❌ Requires GPU (8GB VRAM)
- ❌ 1-2 minute startup time
- ❌ Manual server management

**Best for:** Production with 20+ concurrent users, cost-sensitive deployments

---

### Alternative 1: Ollama (Local, Simple Setup)

**Configuration:**
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest
```

**Start Command:**
```powershell
# Ollama runs as service (auto-starts)
ollama pull llama3.2
ollama serve
```

**Pros:**
- ✅ Easy setup (single binary)
- ✅ Auto-starts on Windows
- ✅ Free (local)
- ✅ Multiple model support

**Cons:**
- ❌ Lower concurrency (~5 users max)
- ❌ Higher latency (~300-500ms)
- ❌ Less optimized for production

**Best for:** Development, testing, single-user demos

---

### Alternative 2: OpenRouter (Cloud API)

**Configuration:**
```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-4o
```

**Setup:**
1. Sign up at https://openrouter.ai
2. Get API key
3. Update `.env` file

**Pros:**
- ✅ No GPU required
- ✅ Instant startup
- ✅ Multiple models (GPT-4, Claude, Llama)
- ✅ High reliability
- ✅ Scales automatically

**Cons:**
- ❌ Pay per token (~$0.01-0.03/1K tokens)
- ❌ Higher latency (~500-1000ms)
- ❌ API rate limits
- ❌ Internet dependency

**Best for:** No GPU available, need GPT-4 quality, prototyping

---

### Switching Providers

**Step 1:** Update `.env` file
```bash
# Change this line:
LLM_PROVIDER=vllm   # Change to: ollama or openrouter
```

**Step 2:** Restart agent
```powershell
# Stop current agent (Ctrl+C)
# Start agent
cd agent
.\.venv\Scripts\python.exe agent.py dev
```

**No code changes needed!** The system automatically:
1. Detects provider from environment
2. Initializes appropriate provider class
3. Connects to correct endpoint
4. Handles failover if provider unavailable

---

### Automatic Failover

System automatically tries providers in order:
1. **Primary**: Set by `LLM_PROVIDER` env var
2. **Fallback 1**: Ollama (if available)
3. **Fallback 2**: OpenRouter (if API key present)

Example: vLLM crashes → System switches to Ollama → No downtime

Check logs for failover events:
```
[LLMProviderManager] vLLM connection failed: Connection refused
[LLMProviderManager] Falling back to ollama provider
[LLMProviderManager] ollama provider initialized successfully
```

## 📝 System Architecture Details

### Connection Pooling
- **PostgreSQL**: 5-30 connections (asyncpg pool)
- **HTTP (LLM)**: aiohttp TCPConnector with 30s keepalive
- **Concurrency**: asyncio.Semaphore limits 20 concurrent LLM requests

### Session Isolation
- Each user has unique UUID session_id (RFC 4122)
- room_id (LiveKit) → session_id mapping
- Separate conversation history per session
- JSONB context field for flexible metadata
- No shared state between users

### Auto-cleanup
- Background asyncio task runs every 60 seconds
- Marks sessions as 'ended' if idle >30 minutes
- `UPDATE agent_sessions SET status='ended', ended_at=NOW() WHERE last_activity < NOW() - INTERVAL '30 minutes'`
- Cascade deletes conversation_messages after retention period

### Failover Logic
1. Try primary LLM provider (from LLM_PROVIDER env var)
2. If connection fails → log error, try next provider
3. Retry with exponential backoff (max 3 attempts)
4. Fall back to Ollama if available
5. Fall back to OpenRouter if API key present
6. If all fail → return error to user

### RAG Embeddings
- Model: sentence-transformers/all-MiniLM-L6-v2
- Dimension: 384
- Similarity: Cosine distance with pgvector
- Index: IVFFlat with 100 lists (fast approximate search)
- Search: Top 5 most similar chunks injected into LLM prompt

### Performance Metrics
- **Throughput**: 20 concurrent users @ ~3 requests/min = 60 req/min
- **Latency**: STT (100-300ms) + LLM (50-200ms) + TTS (200-400ms) = ~350-900ms total
- **Database**: Query time <10ms (indexed lookups)
- **RAG search**: <50ms for vector similarity search
- **Memory**: ~2GB agent process + 4GB vLLM + 2GB Speaches = 8GB total

## 🐛 Troubleshooting

### Issue: Database connection fails

**Symptoms:**
```
asyncpg.exceptions.InvalidCatalogNameError: database "voice_agent" does not exist
```

**Solution:**
```powershell
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE voice_agent;
\c voice_agent

# Run initialization script
\i agent/database/init.sql
```

**Verify:**
```powershell
psql -U postgres -d voice_agent -c "SELECT COUNT(*) FROM agent_instructions"
# Should return: 1 row
```

---

### Issue: vLLM server won't start

**Symptoms:**
```
CUDA out of memory
RuntimeError: CUDA error: out of memory
```

**Solution 1 - Reduce GPU memory:**
```powershell
# Lower --gpu-memory-utilization from 0.5 to 0.4
.\.venv\Scripts\python.exe -m vllm.entrypoints.openai.api_server `
    --model unsloth/Llama-3.2-1B-Instruct `
    --gpu-memory-utilization 0.4 `
    ...
```

**Solution 2 - Stop Speaches GPU:**
```powershell
# Use CPU version instead
docker-compose stop speaches-gpu

# Update .env
WHISPER_LOCAL_URL=http://localhost:8002/v1
SPEACHES_TTS_URL=http://localhost:8002/v1
```

**Solution 3 - Switch to Ollama:**
```bash
# In .env file
LLM_PROVIDER=ollama
```

---

### Issue: RAG not indexing documents

**Symptoms:**
- No documents in `rag_documents` table
- Error: `ModuleNotFoundError: No module named 'docling'`

**Solution:**
```powershell
# Install docling
cd agent
.\.venv\Scripts\pip.exe install docling

# Verify installation
.\.venv\Scripts\python.exe -c "import docling; print('OK')"

# Check docs folder exists
ls docs/

# Restart agent to trigger re-indexing
```

**Verify:**
```sql
-- Check indexed documents
SELECT filename, COUNT(*) as chunks
FROM rag_documents
GROUP BY filename;
```

---

### Issue: Agent can't connect to LiveKit

**Symptoms:**
```
ConnectionError: Cannot connect to ws://localhost:7880
```

**Solution:**
```powershell
# Check LiveKit container running
docker ps | findstr livekit

# If not running, start it
docker-compose up -d livekit

# Check LiveKit logs
docker logs ai-voice-agent-livekit-1

# Verify port 7880 open
Test-NetConnection -ComputerName localhost -Port 7880
```

---

### Issue: Speaches STT/TTS not working

**Symptoms:**
```
Connection refused: http://localhost:8003/v1
```

**Solution:**
```powershell
# Check Speaches containers
docker ps | findstr speaches

# View logs
docker logs ai-voice-agent-speaches-1
docker logs ai-voice-agent-speaches-gpu-1

# Restart containers
docker-compose restart speaches speaches-gpu

# Test STT endpoint
curl http://localhost:8003/v1/models
```

---

### Issue: High latency / slow responses

**Symptoms:**
- Responses take >5 seconds
- Timeout errors

**Diagnosis:**
1. **Check vLLM latency:**
```powershell
# Time a test request
Measure-Command {
    curl http://localhost:8000/v1/chat/completions `
        -Method POST `
        -Headers @{"Content-Type"="application/json"} `
        -Body '{"model":"unsloth/Llama-3.2-1B-Instruct","messages":[{"role":"user","content":"Hi"}]}'
}
# Should be <1 second
```

2. **Check database latency:**
```sql
EXPLAIN ANALYZE 
SELECT * FROM agent_sessions 
WHERE status = 'active' 
ORDER BY last_activity DESC 
LIMIT 10;
-- Execution time should be <10ms
```

3. **Check RAG search latency:**
```sql
EXPLAIN ANALYZE
SELECT * FROM rag_documents 
ORDER BY embedding <=> '[0.1, ...]'::vector 
LIMIT 5;
-- Execution time should be <50ms
```

**Solutions:**
- **vLLM slow**: Reduce `--max-model-len` to 2048
- **Database slow**: Rebuild indexes: `REINDEX TABLE agent_sessions;`
- **RAG slow**: Increase IVFFlat lists: `CREATE INDEX ... WITH (lists = 200);`
- **Network slow**: Check firewall, use localhost instead of 127.0.0.1

---

### Issue: Multiple users experiencing overlapping conversations

**Symptoms:**
- User A hears context from User B's conversation
- Session mixing

**Diagnosis:**
```sql
-- Check if sessions have unique session_ids
SELECT session_id, COUNT(*) as count
FROM agent_sessions
WHERE status = 'active'
GROUP BY session_id
HAVING COUNT(*) > 1;
-- Should return 0 rows
```

**Solution:**
- Restart agent (ensures SessionManager singleton is fresh)
- Verify room_id is unique per LiveKit room
- Check logs for session creation: `[SessionManager] Created session {uuid} for room {room_id}`

---

### Issue: Out of memory errors

**Symptoms:**
```
MemoryError: Unable to allocate array
RuntimeError: CUDA out of memory
```

**Solutions:**

1. **Reduce vLLM GPU memory:**
```powershell
--gpu-memory-utilization 0.3  # Down from 0.5
```

2. **Lower max concurrent requests:**
```bash
# In .env
LLM_MAX_CONCURRENT=10  # Down from 20
```

3. **Reduce PostgreSQL connections:**
```bash
# In .env
POSTGRES_MAX_CONN=15  # Down from 30
```

4. **Clear embeddings cache:**
```powershell
rm -r C:\Users\$env:USERNAME\.cache\huggingface\
```

5. **Monitor memory:**
```powershell
# Windows Task Manager: Ctrl+Shift+Esc
# Or PowerShell:
Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Select-Object ProcessName, WS -ExpandProperty WS
```

## 📚 Additional Resources

### Official Documentation
- **PostgreSQL**: https://www.postgresql.org/docs/
- **pgvector**: https://github.com/pgvector/pgvector - Vector similarity search
- **vLLM**: https://github.com/vllm-project/vllm - High-performance LLM inference
- **Sentence Transformers**: https://www.sbert.net/ - Embedding models
- **Docling**: https://github.com/DS4SD/docling - Document parsing
- **LiveKit**: https://docs.livekit.io/ - Real-time communication
- **asyncpg**: https://magicstack.github.io/asyncpg/ - Async PostgreSQL driver

### Model References
- **Llama 3.2 1B**: https://huggingface.co/unsloth/Llama-3.2-1B-Instruct
- **Faster Whisper**: https://huggingface.co/Systran/faster-whisper-base.en
- **Kokoro TTS**: https://huggingface.co/speaches-ai/Kokoro-82M-v1.0-ONNX
- **all-MiniLM-L6-v2**: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

### Community & Support
- **LiveKit Community**: https://livekit.io/community
- **vLLM Discord**: https://discord.gg/vllm
- **Hugging Face Forums**: https://discuss.huggingface.co/

---

## 🎓 Common Workflows

### Workflow 1: Daily Development

```powershell
# 1. Start Docker services (if not already running)
docker-compose up -d

# 2. Start vLLM in separate terminal
cd agent
.\.venv\Scripts\python.exe -m vllm.entrypoints.openai.api_server --model unsloth/Llama-3.2-1B-Instruct --port 8000 --host 0.0.0.0 --max-num-seqs 20 --dtype auto --gpu-memory-utilization 0.5 --max-model-len 4096

# 3. Start agent in another terminal
cd agent
.\.venv\Scripts\python.exe agent.py dev

# 4. Start frontend in another terminal
cd front-end
pnpm dev

# 5. Access http://localhost:3000
```

### Workflow 2: Update Agent Instructions

```sql
-- Connect to database
psql -U postgres -d voice_agent

-- Update instructions
UPDATE agent_instructions 
SET instructions = 'New instructions here...'
WHERE id = 1;

-- Update greeting
UPDATE agent_instructions
SET initial_greeting = 'New greeting here...'
WHERE id = 1;

-- Exit
\q
```

**No restart needed!** New sessions will use updated instructions.

### Workflow 3: Add Documents to RAG

```powershell
# 1. Copy documents to docs folder
cp "C:\path\to\document.pdf" agent\docs\

# 2. Restart agent (or wait for auto-detection if watch enabled)
# Agent will automatically index new files

# 3. Verify in database
psql -U postgres -d voice_agent -c "SELECT filename, COUNT(*) FROM rag_documents GROUP BY filename"
```

### Workflow 4: Monitor Production

```sql
-- Connect to database
psql -U postgres -d voice_agent

-- Active users right now
SELECT COUNT(*) as active_users
FROM agent_sessions
WHERE status = 'active'
AND last_activity > NOW() - INTERVAL '5 minutes';

-- Total conversations today
SELECT COUNT(*) as total_sessions
FROM agent_sessions
WHERE created_at > CURRENT_DATE;

-- Average messages per conversation
SELECT AVG(message_count) as avg_messages
FROM agent_sessions
WHERE created_at > CURRENT_DATE;

-- LLM provider distribution
SELECT llm_provider, COUNT(*) as count
FROM agent_sessions
WHERE created_at > CURRENT_DATE
GROUP BY llm_provider;
```

### Workflow 5: Switch LLM Providers

```powershell
# 1. Edit .env file
notepad agent\.env

# 2. Change LLM_PROVIDER line:
#    LLM_PROVIDER=vllm    → Change to: ollama or openrouter

# 3. Save and close

# 4. Restart agent (Ctrl+C in agent terminal, then restart)
cd agent
.\.venv\Scripts\python.exe agent.py dev
```

---

## ✅ System Health Checklist

Before starting a production session:

- [ ] PostgreSQL running: `Get-Service postgresql*`
- [ ] Database initialized: `psql -U postgres -d voice_agent -c "\dt"`
- [ ] Docker containers up: `docker ps` (LiveKit, Speaches)
- [ ] vLLM server running: `curl http://localhost:8000/v1/models`
- [ ] Agent instructions loaded: `psql -U postgres -d voice_agent -c "SELECT * FROM agent_instructions WHERE is_active=true"`
- [ ] RAG documents indexed: `psql -U postgres -d voice_agent -c "SELECT COUNT(*) FROM rag_documents"`
- [ ] Network ports open: 7880 (LiveKit), 8000 (vLLM), 8002/8003 (Speaches)
- [ ] GPU available: `nvidia-smi` (if using vLLM/Speaches GPU)

---

## 🎯 Next Steps

1. **Customize Agent Instructions**
   - Update `agent_instructions` table with your specific use case
   - Add domain-specific knowledge to initial_greeting

2. **Add Training Documents**
   - Drop PDFs, DOCX, PPTX into `agent/docs/` folder
   - Agent will automatically index and use for RAG

3. **Tune Performance**
   - Adjust `LLM_MAX_CONCURRENT` based on expected traffic
   - Monitor with PostgreSQL queries (see Workflow 4)

4. **Setup Monitoring**
   - Add logging dashboard (Grafana + Prometheus)
   - Track session durations, message counts, LLM latency

5. **Production Deployment**
   - Move to cloud GPU (AWS g4dn, GCP T4)
   - Setup PostgreSQL replication
   - Add Redis for session caching
   - Implement rate limiting

---

**System Ready!** 🚀

Start all services and access the frontend at http://localhost:3000
