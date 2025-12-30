#!/bin/bash
# Health Check Script for Voice AI Agent Services

echo "Voice AI Agent - Health Check"
echo "=============================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Load environment
if [ -f "agent/.env" ]; then
    export $(cat agent/.env | grep -v '^#' | xargs)
fi

# Check PostgreSQL
echo -n "PostgreSQL Database... "
if command -v psql &> /dev/null; then
    if PGPASSWORD=$POSTGRES_PASSWORD psql -h ${POSTGRES_HOST:-localhost} -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-voice_agent} -c "SELECT 1;" &> /dev/null; then
        # Check tables exist
        TABLE_COUNT=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h ${POSTGRES_HOST:-localhost} -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-voice_agent} -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")
        echo -e "${GREEN}✓ Connected ($TABLE_COUNT tables)${NC}"
    else
        echo -e "${RED}✗ Cannot connect${NC}"
    fi
else
    echo -e "${YELLOW}⚠  psql not found${NC}"
fi

# Check pgvector extension
echo -n "pgvector Extension... "
if command -v psql &> /dev/null; then
    VECTOR_EXISTS=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h ${POSTGRES_HOST:-localhost} -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-voice_agent} -tAc "SELECT 1 FROM pg_extension WHERE extname='vector';" 2>/dev/null)
    if [ "$VECTOR_EXISTS" = "1" ]; then
        echo -e "${GREEN}✓ Installed${NC}"
    else
        echo -e "${RED}✗ Not installed${NC}"
    fi
else
    echo -e "${YELLOW}⚠  Cannot check${NC}"
fi

# Check Ollama
echo -n "Ollama Service... "
if curl -s http://localhost:11434/api/version &> /dev/null; then
    VERSION=$(curl -s http://localhost:11434/api/version | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    echo -e "${GREEN}✓ Running (v$VERSION)${NC}"
    
    # Check models
    echo -n "  - LLM Model (llama3.2)... "
    if ollama list 2>/dev/null | grep -q "llama3.2"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗ Not found${NC}"
    fi
    
    echo -n "  - Embedding Model (nomic-embed-text)... "
    if ollama list 2>/dev/null | grep -q "nomic-embed-text"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗ Not found${NC}"
    fi
else
    echo -e "${RED}✗ Not running${NC}"
fi

# Check LiveKit
echo -n "LiveKit Server... "
if curl -s http://localhost:7880/ &> /dev/null; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
fi

# Check Speaches (STT/TTS)
echo -n "Speaches STT/TTS... "
if curl -s http://localhost:8003/v1/models &> /dev/null; then
    echo -e "${GREEN}✓ Running (GPU)${NC}"
elif curl -s http://localhost:8002/v1/models &> /dev/null; then
    echo -e "${GREEN}✓ Running (CPU)${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
fi

# Check Python environment
echo -n "Python Virtual Environment... "
if [ -d "agent/.venv" ]; then
    echo -e "${GREEN}✓ Exists${NC}"
    
    # Check if dependencies installed
    if [ -f "agent/.venv/bin/python" ] || [ -f "agent/.venv/Scripts/python.exe" ]; then
        echo -n "  - Dependencies... "
        if agent/.venv/bin/python -c "import livekit" 2>/dev/null || agent/.venv/Scripts/python.exe -c "import livekit" 2>/dev/null; then
            echo -e "${GREEN}✓ Installed${NC}"
        else
            echo -e "${RED}✗ Missing${NC}"
        fi
    fi
else
    echo -e "${RED}✗ Not found${NC}"
fi

# Check RAG documents
echo -n "RAG Documents... "
if [ -d "agent/docs" ]; then
    DOC_COUNT=$(find agent/docs -type f \( -name "*.txt" -o -name "*.md" -o -name "*.pdf" -o -name "*.docx" \) | wc -l)
    if [ $DOC_COUNT -gt 0 ]; then
        echo -e "${GREEN}✓ $DOC_COUNT documents${NC}"
    else
        echo -e "${YELLOW}⚠  No documents${NC}"
    fi
else
    echo -e "${RED}✗ docs/ folder not found${NC}"
fi

# Check indexed documents in database
echo -n "Indexed RAG Chunks... "
if command -v psql &> /dev/null; then
    CHUNK_COUNT=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h ${POSTGRES_HOST:-localhost} -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-voice_agent} -tAc "SELECT COUNT(*) FROM rag_documents;" 2>/dev/null)
    if [ ! -z "$CHUNK_COUNT" ]; then
        echo -e "${GREEN}✓ $CHUNK_COUNT chunks${NC}"
    else
        echo -e "${YELLOW}⚠  0 chunks${NC}"
    fi
else
    echo -e "${YELLOW}⚠  Cannot check${NC}"
fi

# Check disk space
echo -n "Disk Space... "
if command -v df &> /dev/null; then
    DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $DISK_USAGE -lt 80 ]; then
        echo -e "${GREEN}✓ ${DISK_USAGE}% used${NC}"
    elif [ $DISK_USAGE -lt 90 ]; then
        echo -e "${YELLOW}⚠  ${DISK_USAGE}% used${NC}"
    else
        echo -e "${RED}✗ ${DISK_USAGE}% used (low space!)${NC}"
    fi
else
    echo -e "${YELLOW}⚠  Cannot check${NC}"
fi

# Summary
echo ""
echo "=============================="
echo "For detailed logs:"
echo "  docker-compose logs -f"
echo "  journalctl -u voice-agent -f"
echo ""
echo "To restart services:"
echo "  docker-compose restart"
echo "  systemctl restart voice-agent"
echo ""
