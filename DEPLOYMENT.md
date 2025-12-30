# Voice Agent - Quick Start Deployment Guide

This guide will help you deploy the voice agent to a new server in minutes.

## Prerequisites

- Python 3.10+
- PostgreSQL 13+ (with pgvector extension)
- Ollama (for local LLM)
- Node.js 18+ (for frontend)
- LiveKit server (or use cloud)

## Quick Deploy (5 Minutes)

### Step 1: Clone & Setup Environment

```bash
# Clone repository
git clone <your-repo-url>
cd ai-voice-agent

# Copy environment template
cd agent
cp .env.example .env

# Edit .env with your settings
nano .env  # or your preferred editor
```

### Step 2: Run Setup Script

**Windows:**
```powershell
.\setup-windows.ps1
```

**Linux/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

This will:
- ✅ Create Python virtual environment
- ✅ Install all dependencies
- ✅ Setup PostgreSQL database
- ✅ Install pgvector extension
- ✅ Run migrations
- ✅ Index RAG documents

### Step 3: Start Services

**Option A: Start All Services (Docker)**
```bash
docker-compose up -d
```

**Option B: Start Manually**
```bash
# Terminal 1: Start LiveKit
docker run -d -p 7880:7880 -p 7881:7881 livekit/livekit-server --dev --bind 0.0.0.0

# Terminal 2: Start Ollama
ollama serve

# Terminal 3: Start Speaches (STT/TTS)
docker-compose up speaches-gpu  # or speaches for CPU

# Terminal 4: Start Agent
cd agent
.venv/Scripts/activate  # Windows
source .venv/bin/activate  # Linux/Mac
python agent.py start
```

### Step 4: Start Frontend

```bash
cd front-end
pnpm install
pnpm dev
```

### Step 5: Test

Open browser: `http://localhost:3000`

---

## Detailed Setup Instructions

### 1. Database Setup

**Install PostgreSQL:**
```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib

# Windows - Download from: https://www.postgresql.org/download/windows/

# macOS
brew install postgresql
```

**Install pgvector:**
```bash
# Ubuntu/Debian
sudo apt install postgresql-17-pgvector

# Windows - Download from: https://github.com/pgvector/pgvector/releases

# macOS
brew install pgvector
```

**Create Database:**
```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create database
CREATE DATABASE voice_agent;

-- Connect to database
\c voice_agent

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Exit
\q
```

**Run Migrations:**
```bash
cd agent
psql -U postgres -d voice_agent -f database/init.sql
psql -U postgres -d voice_agent -f database/migrate_profiles.sql
```

### 2. Ollama Setup

**Install Ollama:**
```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows - Download from: https://ollama.com/download/windows

# macOS
brew install ollama
```

**Download Models:**
```bash
# LLM for conversations
ollama pull llama3.2:latest

# Embedding model for RAG
ollama pull nomic-embed-text:latest
```

**Start Ollama:**
```bash
ollama serve
# Runs on http://localhost:11434
```

### 3. Python Environment

```bash
cd agent

# Create virtual environment
python -m venv .venv

# Activate
# Windows:
.venv\Scripts\activate.bat

# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import livekit; print('✓ LiveKit installed')"
python -c "import asyncpg; print('✓ Database driver installed')"
python -c "import docling; print('✓ Docling installed')"
```

### 4. Configuration

**Edit `.env` file:**

**Required Settings:**
```env
# LiveKit
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# Database
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=voice_agent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=YOUR_PASSWORD_HERE

# LLM
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest

# RAG
RAG_ENABLED=true
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text:latest

# STT/TTS
SPEACHES_STT_URL=http://localhost:8003/v1
SPEACHES_TTS_URL=http://localhost:8003/v1
```

### 5. RAG Documents

```bash
# Add your documents to the docs folder
cd agent/docs

# Supported formats:
# - .txt, .md (basic text)
# - .pdf, .docx, .pptx (with Docling)
# - .html, .xlsx (with Docling)

# Documents will be indexed on agent startup
```

### 6. Frontend Setup

```bash
cd front-end

# Install pnpm if needed
npm install -g pnpm

# Install dependencies
pnpm install

# Configure environment
cp .env.example .env.local

# Edit .env.local with your LiveKit settings

# Start development server
pnpm dev
```

---

## Production Deployment

### Using Docker Compose (Recommended)

```bash
# Build all services
docker-compose build

# Start production stack
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f agent
```

### Manual Production Setup

**1. Use Production Database:**
```env
POSTGRES_HOST=your-db-server.com
POSTGRES_PORT=5432
POSTGRES_DB=voice_agent
POSTGRES_USER=voice_agent_user
POSTGRES_PASSWORD=strong_password_here
```

**2. Use Production LiveKit:**
```env
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
```

**3. Configure Reverse Proxy (Nginx):**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;  # Frontend
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api/ {
        proxy_pass http://localhost:8000;  # Agent API
    }
}
```

**4. Setup Systemd Service (Linux):**
```bash
# Create service file
sudo nano /etc/systemd/system/voice-agent.service
```

```ini
[Unit]
Description=Voice AI Agent
After=network.target postgresql.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/ai-voice-agent/agent
Environment="PATH=/path/to/.venv/bin"
ExecStart=/path/to/.venv/bin/python agent.py start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl enable voice-agent
sudo systemctl start voice-agent
sudo systemctl status voice-agent
```

**5. Setup Process Manager (PM2 - Alternative):**
```bash
npm install -g pm2

# Start agent
pm2 start agent.py --name voice-agent --interpreter python

# Start frontend
cd front-end
pm2 start "pnpm start" --name voice-frontend

# Save configuration
pm2 save
pm2 startup
```

---

## Troubleshooting

### Database Connection Issues

```bash
# Test database connection
psql -U postgres -d voice_agent -c "SELECT version();"

# Check if pgvector is installed
psql -U postgres -d voice_agent -c "SELECT * FROM pg_extension WHERE extname = 'vector';"

# If not installed:
psql -U postgres -d voice_agent -c "CREATE EXTENSION vector;"
```

### Ollama Connection Issues

```bash
# Test Ollama
curl http://localhost:11434/api/version

# Check if models are downloaded
ollama list

# Re-download if needed
ollama pull llama3.2:latest
ollama pull nomic-embed-text:latest
```

### RAG Not Working

```bash
# Check documents are indexed
psql -U postgres -d voice_agent -c "SELECT COUNT(*) FROM rag_documents;"

# Manually trigger indexing
cd agent
python -c "
import asyncio
from database.rag import RAGIndexer
from database import get_db_pool

async def index():
    pool = await get_db_pool()
    indexer = RAGIndexer('docs', pool)
    await indexer.index_directory()

asyncio.run(index())
"
```

### Port Conflicts

```bash
# Check what's using a port
# Windows:
netstat -ano | findstr :7880

# Linux/Mac:
lsof -i :7880

# Kill process if needed
# Windows:
taskkill /PID <pid> /F

# Linux/Mac:
kill -9 <pid>
```

---

## Environment Variables Reference

See `.env.example` for complete list with descriptions.

**Critical Variables:**
- `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
- `EMBEDDING_MODEL` (for RAG)

---

## Health Checks

```bash
# Check all services
./health-check.sh

# Or manually:

# Database
psql -U postgres -d voice_agent -c "SELECT 1;"

# Ollama
curl http://localhost:11434/api/version

# LiveKit
curl http://localhost:7880/

# Agent (when running)
curl http://localhost:8000/health
```

---

## Backup & Restore

**Backup Database:**
```bash
pg_dump -U postgres voice_agent > backup_$(date +%Y%m%d).sql
```

**Restore Database:**
```bash
psql -U postgres voice_agent < backup_20251230.sql
```

---

## Security Checklist

- [ ] Change default PostgreSQL password
- [ ] Use strong LIVEKIT_API_SECRET
- [ ] Enable PostgreSQL SSL in production
- [ ] Use HTTPS for all web traffic
- [ ] Restrict database access to localhost or VPN
- [ ] Keep API keys in environment variables, not code
- [ ] Regular security updates: `apt update && apt upgrade`

---

## Support

- Documentation: `agent/database/PROFILE_TRACKING.md`
- Setup Guide: `agent/SETUP_GUIDE.md`
- Issues: GitHub Issues
- Discord: [Your Discord Server]

## Quick Commands Cheat Sheet

```bash
# Start everything (Docker)
docker-compose up -d

# Stop everything
docker-compose down

# View logs
docker-compose logs -f agent

# Restart agent only
docker-compose restart agent

# Database migrations
psql -U postgres -d voice_agent -f agent/database/migrate_profiles.sql

# Check agent status
pm2 status  # if using PM2
systemctl status voice-agent  # if using systemd

# Update code
git pull
cd agent && pip install -r requirements.txt
cd front-end && pnpm install
pm2 restart all  # or systemctl restart voice-agent
```
