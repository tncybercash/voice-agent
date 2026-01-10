<div align="center">
  <h1>🎙️ AI Voice Agent</h1>
  <p>Enterprise-grade, real-time AI voice assistant with speech recognition, LLM processing, and voice synthesis powered by <a href="https://livekit.io">LiveKit</a>.</p>
  
  <p>
    <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python">
    <img src="https://img.shields.io/badge/Next.js-15-black.svg" alt="Next.js">
    <img src="https://img.shields.io/badge/LiveKit-Agents-purple.svg" alt="LiveKit">
    <img src="https://img.shields.io/badge/PostgreSQL-13+-336791.svg" alt="PostgreSQL">
  </p>
</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Running the Application](#-running-the-application)
- [Docker Deployment](#-docker-deployment)
- [API Reference](#-api-reference)
- [Features](#-features)
- [Troubleshooting](#-troubleshooting)
- [Project Structure](#-project-structure)

---

## 🧩 Overview

This repository contains a complete, production-ready AI voice assistant system featuring:

- 🎤 **Real-time voice conversations** via WebRTC (LiveKit)
- 🧠 **Multiple LLM providers** (Ollama, vLLM, OpenRouter, Google Gemini)
- 🗣️ **High-quality TTS** using Kokoro voice synthesis
- 👂 **Accurate STT** using Whisper models
- 🔍 **RAG (Retrieval-Augmented Generation)** via MCP server
- 🔗 **Shareable links & embeddable widgets** for distribution
- 👤 **User session management** with conversation history
- 📱 **Responsive UI** with mobile and desktop support

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │   Browser   │    │  Share Link │    │   Embedded  │                  │
│  │  (Next.js)  │    │    Users    │    │   Widget    │                  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                  │
└─────────┼──────────────────┼──────────────────┼─────────────────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │ WebSocket/HTTP
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           INFRASTRUCTURE                                 │
│                                                                          │
│  ┌─────────────────┐              ┌─────────────────┐                   │
│  │   LiveKit       │◄────────────►│   Next.js API   │                   │
│  │   Server        │   WebRTC     │   (Token Gen)   │                   │
│  │   :7880         │              │   :3000         │                   │
│  └────────┬────────┘              └────────┬────────┘                   │
│           │                                │                             │
│           │ LiveKit SDK                    │ HTTP                        │
│           ▼                                ▼                             │
│  ┌─────────────────┐              ┌─────────────────┐                   │
│  │   Python Agent  │              │   Agent API     │                   │
│  │   (Voice AI)    │◄────────────►│   Server        │                   │
│  │                 │              │   :8000         │                   │
│  └────────┬────────┘              └────────┬────────┘                   │
│           │                                │                             │
└───────────┼────────────────────────────────┼─────────────────────────────┘
            │                                │
            ▼                                ▼
┌───────────────────────┐          ┌───────────────────────┐
│   AI/ML SERVICES      │          │   DATA LAYER          │
│                       │          │                       │
│  ┌─────────────────┐  │          │  ┌─────────────────┐  │
│  │  Speaches       │  │          │  │  PostgreSQL     │  │
│  │  (STT/TTS)      │  │          │  │  + pgvector     │  │
│  │  :8002/:8003    │  │          │  │  :5432          │  │
│  └─────────────────┘  │          │  └─────────────────┘  │
│                       │          │                       │
│  ┌─────────────────┐  │          │  ┌─────────────────┐  │
│  │  Ollama/vLLM    │  │          │  │  MCP Server     │  │
│  │  (LLM)          │  │          │  │  (Knowledge)    │  │
│  │  :11434/:8000   │  │          │  │                 │  │
│  └─────────────────┘  │          │  └─────────────────┘  │
└───────────────────────┘          └───────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend (Python Agent)
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| LiveKit Agents SDK | Latest | Voice agent framework |
| asyncpg | Latest | PostgreSQL async driver |
| aiohttp | Latest | Async HTTP client |
| MCP (Model Context Protocol) | Latest | Knowledge base tools |

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 15.5.8 | React framework |
| React | 19.0.0 | UI library |
| LiveKit Components | 2.9.15 | WebRTC components |
| Tailwind CSS | 4.x | Styling |
| TypeScript | 5.x | Type safety |

### AI/ML Services
| Service | Purpose | Default Port |
|---------|---------|--------------|
| Speaches (CPU) | STT (Whisper) + TTS (Kokoro) | 8002 |
| Speaches (GPU) | STT + TTS with GPU acceleration | 8003 |
| Ollama | Local LLM inference | 11434 |
| vLLM | Production LLM serving | 8000 |

### Infrastructure
| Component | Purpose | Default Port |
|-----------|---------|--------------|
| PostgreSQL + pgvector | Database with vector search | 5432 |
| LiveKit Server | WebRTC signaling | 7880, 7881 |
| Redis (optional) | Caching | 6379 |

---

## 📋 Prerequisites

Before installation, ensure you have:

### Required
- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Node.js 18+** - [Download](https://nodejs.org/)
- **pnpm** - `npm install -g pnpm`
- **PostgreSQL 13+** with pgvector extension
- **Docker & Docker Compose** - [Download](https://www.docker.com/)

### Optional (for local LLM)
- **Ollama** - [Download](https://ollama.ai/)
- **NVIDIA GPU** + CUDA (for GPU acceleration)

---

## 📥 Installation

### Quick Start (Automated)

```bash
# Windows
.\start.ps1

# Linux/macOS
chmod +x start.sh && ./start.sh
```

### Manual Installation

#### Step 1: Clone the Repository
```bash
git clone https://github.com/tncybercash/voice-agent.git
cd voice-agent
```

#### Step 2: Database Setup
```bash
# Create PostgreSQL database
psql -U postgres -c "CREATE DATABASE voice_agent;"

# Enable extensions
psql -U postgres -d voice_agent -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
psql -U postgres -d voice_agent -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Initialize schema
psql -U postgres -d voice_agent -f agent/database/init.sql
```

#### Step 3: Install Ollama (Local LLM)
```bash
# Install Ollama from https://ollama.ai/

# Pull required models
ollama pull llama3.2:latest
ollama pull nomic-embed-text:latest

# Start Ollama server (runs on port 11434)
ollama serve
```

#### Step 4: Setup Python Agent
```bash
cd agent

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\Activate.ps1

# Activate (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your settings
```

#### Step 5: Setup Frontend
```bash
cd front-end

# Install dependencies
pnpm install

# Copy and configure environment
cp .env.example .env.local
# Edit .env.local with your settings
```

#### Step 6: Start Docker Services
```bash
# Start LiveKit and Speaches (CPU)
docker-compose up livekit speaches -d

# OR with GPU support
docker-compose up livekit speaches-gpu -d
```

---

## ⚙️ Configuration

### Agent Environment Variables (`agent/.env`)

```env
# ============================================
# LIVEKIT CONFIGURATION
# ============================================
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# ============================================
# LLM PROVIDER
# Options: "ollama", "vllm", "openrouter", "google", "google_realtime"
# ============================================
LLM_PROVIDER=ollama
USE_ONLINE_MODEL=false

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest

# vLLM Configuration (alternative)
VLLM_BASE_URL=http://localhost:8000
VLLM_MODEL=unsloth/Llama-3.2-1B-Instruct

# Google Configuration (cloud)
GOOGLE_API_KEY=your_google_api_key
GOOGLE_REALTIME_MODEL=gemini-2.0-flash-exp
GOOGLE_REALTIME_VOICE=Aoede

# OpenRouter Configuration (cloud)
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=openai/gpt-4o-mini

# ============================================
# STT (Speech-to-Text)
# ============================================
SPEACHES_STT_URL=http://localhost:8003/v1
SPEACHES_STT_MODEL=Systran/faster-whisper-base.en

# ============================================
# TTS (Text-to-Speech)
# ============================================
SPEACHES_TTS_URL=http://localhost:8003/v1
SPEACHES_TTS_MODEL=speaches-ai/Kokoro-82M-v1.0-ONNX
SPEACHES_TTS_VOICE=af_heart

# ============================================
# DATABASE
# ============================================
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=voice_agent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# ============================================
# MCP SERVER (Knowledge Base)
# ============================================
MCP_SERVER_URL=https://your-mcp-server.com

# ============================================
# VAD (Voice Activity Detection)
# ============================================
VAD_MIN_SPEECH=0.15
VAD_MIN_SILENCE=0.9
VAD_PREFIX_PADDING=0.5
```

### Frontend Environment Variables (`front-end/.env.local`)

```env
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
AGENT_API_URL=http://localhost:8000
```

---

## 🚀 Running the Application

### Option 1: All-in-One Script (Recommended)

```bash
# Windows PowerShell
.\start.ps1

# Linux/macOS
./start.sh
```

### Option 2: Manual Start (Development)

Open 5 separate terminals:

**Terminal 1: Docker Services**
```bash
docker-compose up livekit speaches-gpu -d
```

**Terminal 2: Ollama**
```bash
ollama serve
```

**Terminal 3: Python Agent**
```bash
cd agent
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate   # Linux/macOS
python agent.py start
```

**Terminal 4: Agent API Server**
```bash
cd agent
.\.venv\Scripts\Activate.ps1
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 5: Frontend**
```bash
cd front-end
pnpm dev
```

### Access the Application
- **Main App**: http://localhost:3000
- **Agent API**: http://localhost:8000
- **LiveKit Dashboard**: http://localhost:7880

---

## 🐳 Docker Deployment

### Development
```bash
docker-compose up -d
```

### Production
```bash
# Build and deploy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f

# Scale agent workers
docker-compose up -d --scale agent=3
```

### Docker Services Overview

| Service | Image | Ports | Description |
|---------|-------|-------|-------------|
| `livekit` | livekit/livekit-server | 7880, 7881 | WebRTC signaling |
| `speaches` | speaches-ai/speaches:cpu | 8002 | STT/TTS (CPU) |
| `speaches-gpu` | speaches-ai/speaches:cuda | 8003 | STT/TTS (GPU) |
| `postgres` | postgres:15-alpine | 5432 | Database |

---

## 📡 API Reference

### Agent API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /health` | GET | Health check |
| `GET /api/share-links` | GET | List all share links |
| `POST /api/share-links` | POST | Create share link |
| `GET /api/share-links/{code}/validate` | GET | Validate share code |
| `GET /api/embed-keys` | GET | List embed API keys |
| `POST /api/embed-keys` | POST | Create embed key |
| `POST /api/embed/session` | POST | Create embed session |

### Frontend API Routes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /api/connection-details` | POST | Get LiveKit tokens |
| `GET /api/instructions` | GET | Get agent instructions |
| `GET /api/share-links` | GET | Manage share links |
| `GET /api/embed-keys` | GET | Manage embed keys |

---

## ✨ Features

### Core Features
- ✅ Real-time voice conversations
- ✅ Multiple LLM provider support
- ✅ High-quality speech synthesis (Kokoro)
- ✅ Accurate speech recognition (Whisper)
- ✅ Session management with history
- ✅ User profile tracking

### Advanced Features
- ✅ RAG (Retrieval-Augmented Generation)
- ✅ Web search integration
- ✅ Shareable conversation links
- ✅ Embeddable widget for external sites
- ✅ Multi-language support
- ✅ Vision capabilities (Google Realtime)

### UI/UX
- ✅ Responsive design (mobile/desktop)
- ✅ Dark/light theme
- ✅ Conversation transcript
- ✅ Real-time audio visualization
- ✅ Call duration timer

---

## 🔧 Troubleshooting

### Common Issues

#### "Connection refused" to LiveKit
```bash
# Ensure LiveKit is running
docker-compose ps livekit
docker-compose logs livekit
```

#### "Model not found" in Ollama
```bash
# Pull the required model
ollama pull llama3.2:latest
ollama list  # Verify installation
```

#### Database connection errors
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Verify database exists
psql -U postgres -c "\l" | grep voice_agent
```

#### STT/TTS not working
```bash
# Check Speaches service
curl http://localhost:8003/v1/models
docker-compose logs speaches-gpu
```

### Health Check Script
```bash
# Run comprehensive health check
./health-check.sh
```

---

## 📁 Project Structure

```
ai-voice-agent/
├── agent/                          # Python voice agent
│   ├── agent.py                    # Main agent entry point
│   ├── api_server.py               # REST API server
│   ├── session_manager.py          # Session management
│   ├── tools.py                    # Agent tools (search, etc.)
│   ├── requirements.txt            # Python dependencies
│   ├── Dockerfile                  # Agent container
│   ├── database/                   # Database layer
│   │   ├── init.sql               # Schema initialization
│   │   ├── connection.py          # DB connection pool
│   │   ├── repository.py          # Data access layer
│   │   ├── rag.py                 # RAG implementation
│   │   └── models.py              # Data models
│   ├── providers/                  # LLM providers
│   │   └── llm_provider.py        # Multi-provider support
│   └── tests/                      # Test files
│
├── front-end/                      # Next.js frontend
│   ├── app/                        # App router pages
│   │   ├── (app)/                 # Main app routes
│   │   ├── s/[code]/              # Share link pages
│   │   ├── embed/                 # Embed widget
│   │   └── api/                   # API routes
│   ├── components/                 # React components
│   │   ├── app/                   # App-specific components
│   │   └── livekit/               # LiveKit UI components
│   ├── hooks/                      # Custom React hooks
│   ├── lib/                        # Utilities
│   └── styles/                     # Global styles
│
├── livekit/                        # LiveKit server config
│   └── Dockerfile
│
├── docker-compose.yml              # Docker orchestration
├── start.ps1                       # Windows startup script
├── start.sh                        # Linux/macOS startup script
├── health-check.sh                 # System health check
│
├── INSTALLATION.md                 # Detailed installation guide
├── DEPLOYMENT.md                   # Production deployment guide
├── TESTING_GUIDE.md               # Testing documentation
└── README.md                       # This file
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📞 Support

- **Documentation**: See `/docs` folder
- **Issues**: [GitHub Issues](https://github.com/tncybercash/voice-agent/issues)

---

<div align="center">
  <p>Built with ❤️ using LiveKit, Next.js, and Python</p>
</div>
