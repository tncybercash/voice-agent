#!/bin/bash
# Automated Setup Script for Voice AI Agent (Linux/Mac)
# Run with: chmod +x setup.sh && ./setup.sh

set -e  # Exit on error

echo "=========================================="
echo "Voice AI Agent - Automated Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in agent directory
if [ ! -f "agent.py" ]; then
    echo -e "${RED}Error: Please run this script from the agent/ directory${NC}"
    exit 1
fi

# Step 1: Check Python version
echo -e "${YELLOW}[1/8] Checking Python version...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
else
    echo -e "${RED}✗ Python 3.10+ required but not found${NC}"
    echo "Please install Python from: https://www.python.org/downloads/"
    exit 1
fi

# Step 2: Create virtual environment
echo -e "${YELLOW}[2/8] Creating Python virtual environment...${NC}"
if [ -d ".venv" ]; then
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
else
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Step 3: Activate and install dependencies
echo -e "${YELLOW}[3/8] Installing Python dependencies...${NC}"
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Step 4: Check for .env file
echo -e "${YELLOW}[4/8] Checking environment configuration...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}⚠  Please edit .env file with your settings before continuing${NC}"
    read -p "Press Enter after editing .env to continue..."
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Step 5: Check PostgreSQL
echo -e "${YELLOW}[5/8] Checking PostgreSQL connection...${NC}"
if command -v psql &> /dev/null; then
    if PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d postgres -c "SELECT 1;" &> /dev/null; then
        echo -e "${GREEN}✓ PostgreSQL connection successful${NC}"
    else
        echo -e "${RED}✗ Cannot connect to PostgreSQL${NC}"
        echo "Please check your database credentials in .env"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠  psql not found in PATH. Skipping database check.${NC}"
    echo "Make sure PostgreSQL is installed and running."
fi

# Step 6: Create database and run migrations
echo -e "${YELLOW}[6/8] Setting up database...${NC}"
if command -v psql &> /dev/null; then
    # Check if database exists
    DB_EXISTS=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'")
    
    if [ "$DB_EXISTS" != "1" ]; then
        echo "Creating database: $POSTGRES_DB"
        PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d postgres -c "CREATE DATABASE $POSTGRES_DB;"
    fi
    
    # Check if pgvector extension exists
    VECTOR_EXISTS=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -tAc "SELECT 1 FROM pg_extension WHERE extname='vector'")
    
    if [ "$VECTOR_EXISTS" != "1" ]; then
        echo "Installing pgvector extension..."
        PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "CREATE EXTENSION IF NOT EXISTS vector;"
    fi
    
    # Run migrations
    echo "Running database migrations..."
    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -f database/init.sql > /dev/null 2>&1 || true
    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -f database/migrate_profiles.sql > /dev/null 2>&1 || true
    
    echo -e "${GREEN}✓ Database setup complete${NC}"
else
    echo -e "${YELLOW}⚠  Skipping database setup (psql not available)${NC}"
fi

# Step 7: Check Ollama
echo -e "${YELLOW}[7/8] Checking Ollama installation...${NC}"
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✓ Ollama is installed${NC}"
    
    # Check if Ollama is running
    if curl -s http://localhost:11434/api/version &> /dev/null; then
        echo -e "${GREEN}✓ Ollama is running${NC}"
        
        # Check if required models are downloaded
        if ollama list | grep -q "llama3.2"; then
            echo -e "${GREEN}✓ LLM model (llama3.2) is downloaded${NC}"
        else
            echo -e "${YELLOW}⚠  Downloading LLM model (this may take a few minutes)...${NC}"
            ollama pull llama3.2:latest
            echo -e "${GREEN}✓ LLM model downloaded${NC}"
        fi
        
        if ollama list | grep -q "nomic-embed-text"; then
            echo -e "${GREEN}✓ Embedding model (nomic-embed-text) is downloaded${NC}"
        else
            echo -e "${YELLOW}⚠  Downloading embedding model...${NC}"
            ollama pull nomic-embed-text:latest
            echo -e "${GREEN}✓ Embedding model downloaded${NC}"
        fi
    else
        echo -e "${YELLOW}⚠  Ollama is not running. Please start it with: ollama serve${NC}"
    fi
else
    echo -e "${YELLOW}⚠  Ollama not found. Please install from: https://ollama.com${NC}"
fi

# Step 8: Index RAG documents
echo -e "${YELLOW}[8/8] Indexing RAG documents...${NC}"
if [ -d "docs" ] && [ "$(ls -A docs)" ]; then
    echo "Found documents in docs/ folder. Indexing will happen on first agent startup."
    echo -e "${GREEN}✓ RAG setup ready${NC}"
else
    echo -e "${YELLOW}⚠  No documents found in docs/ folder${NC}"
    echo "Add your knowledge base documents to agent/docs/ before starting the agent"
fi

# Final summary
echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review and edit .env file if needed"
echo "2. Add documents to docs/ folder for RAG"
echo "3. Start LiveKit: docker run -d -p 7880:7880 livekit/livekit-server --dev"
echo "4. Start Ollama: ollama serve (if not running)"
echo "5. Start Agent: python agent.py start"
echo ""
echo "To activate the virtual environment later:"
echo "  source .venv/bin/activate"
echo ""
echo "For troubleshooting, see: DEPLOYMENT.md"
echo ""
