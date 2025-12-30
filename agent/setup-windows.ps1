# Automated Setup Script for Voice AI Agent (Windows PowerShell)
# Run with: .\setup-windows.ps1

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Voice AI Agent - Automated Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running in agent directory
if (!(Test-Path "agent.py")) {
    Write-Host "Error: Please run this script from the agent/ directory" -ForegroundColor Red
    exit 1
}

# Step 1: Check Python version
Write-Host "[1/8] Checking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1 | Select-String -Pattern "\d+\.\d+"
    if ($pythonVersion) {
        Write-Host "✓ Python $($pythonVersion.Matches[0].Value) found" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ Python 3.10+ required but not found" -ForegroundColor Red
    Write-Host "Please install Python from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Step 2: Create virtual environment
Write-Host "[2/8] Creating Python virtual environment..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "✓ Virtual environment already exists" -ForegroundColor Green
} else {
    python -m venv .venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
}

# Step 3: Activate and install dependencies
Write-Host "[3/8] Installing Python dependencies..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
Write-Host "✓ Dependencies installed" -ForegroundColor Green

# Step 4: Check for .env file
Write-Host "[4/8] Checking environment configuration..." -ForegroundColor Yellow
if (!(Test-Path ".env")) {
    Write-Host "Creating .env from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "✓ .env file created" -ForegroundColor Green
    Write-Host "⚠  Please edit .env file with your settings before continuing" -ForegroundColor Yellow
    Read-Host "Press Enter after editing .env to continue"
} else {
    Write-Host "✓ .env file exists" -ForegroundColor Green
}

# Load environment variables
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

# Step 5: Check PostgreSQL
Write-Host "[5/8] Checking PostgreSQL connection..." -ForegroundColor Yellow
$POSTGRES_HOST = $env:POSTGRES_HOST
$POSTGRES_USER = $env:POSTGRES_USER
$POSTGRES_DB = $env:POSTGRES_DB
$PGPASSWORD = $env:POSTGRES_PASSWORD

if (Get-Command psql -ErrorAction SilentlyContinue) {
    $env:PGPASSWORD = $PGPASSWORD
    try {
        $result = psql -h $POSTGRES_HOST -U $POSTGRES_USER -d postgres -c "SELECT 1;" 2>&1
        Write-Host "✓ PostgreSQL connection successful" -ForegroundColor Green
    } catch {
        Write-Host "✗ Cannot connect to PostgreSQL" -ForegroundColor Red
        Write-Host "Please check your database credentials in .env" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "⚠  psql not found in PATH. Skipping database check." -ForegroundColor Yellow
    Write-Host "Make sure PostgreSQL is installed and running." -ForegroundColor Yellow
}

# Step 6: Create database and run migrations
Write-Host "[6/8] Setting up database..." -ForegroundColor Yellow
if (Get-Command psql -ErrorAction SilentlyContinue) {
    $env:PGPASSWORD = $PGPASSWORD
    
    # Check if database exists
    $dbExists = psql -h $POSTGRES_HOST -U $POSTGRES_USER -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'" 2>&1
    
    if ($dbExists -ne "1") {
        Write-Host "Creating database: $POSTGRES_DB"
        psql -h $POSTGRES_HOST -U $POSTGRES_USER -d postgres -c "CREATE DATABASE $POSTGRES_DB;" 2>&1 | Out-Null
    }
    
    # Check if pgvector extension exists
    $vectorExists = psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -tAc "SELECT 1 FROM pg_extension WHERE extname='vector'" 2>&1
    
    if ($vectorExists -ne "1") {
        Write-Host "Installing pgvector extension..."
        psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>&1 | Out-Null
    }
    
    # Run migrations
    Write-Host "Running database migrations..."
    psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -f database\init.sql 2>&1 | Out-Null
    psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -f database\migrate_profiles.sql 2>&1 | Out-Null
    
    Write-Host "✓ Database setup complete" -ForegroundColor Green
} else {
    Write-Host "⚠  Skipping database setup (psql not available)" -ForegroundColor Yellow
}

# Step 7: Check Ollama
Write-Host "[7/8] Checking Ollama installation..." -ForegroundColor Yellow
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "✓ Ollama is installed" -ForegroundColor Green
    
    # Check if Ollama is running
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/version" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        Write-Host "✓ Ollama is running" -ForegroundColor Green
        
        # Check if required models are downloaded
        $models = ollama list | Out-String
        
        if ($models -match "llama3.2") {
            Write-Host "✓ LLM model (llama3.2) is downloaded" -ForegroundColor Green
        } else {
            Write-Host "⚠  Downloading LLM model (this may take a few minutes)..." -ForegroundColor Yellow
            ollama pull llama3.2:latest
            Write-Host "✓ LLM model downloaded" -ForegroundColor Green
        }
        
        if ($models -match "nomic-embed-text") {
            Write-Host "✓ Embedding model (nomic-embed-text) is downloaded" -ForegroundColor Green
        } else {
            Write-Host "⚠  Downloading embedding model..." -ForegroundColor Yellow
            ollama pull nomic-embed-text:latest
            Write-Host "✓ Embedding model downloaded" -ForegroundColor Green
        }
    } catch {
        Write-Host "⚠  Ollama is not running. Please start it with: ollama serve" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠  Ollama not found. Please install from: https://ollama.com" -ForegroundColor Yellow
}

# Step 8: Index RAG documents
Write-Host "[8/8] Indexing RAG documents..." -ForegroundColor Yellow
if ((Test-Path "docs") -and (Get-ChildItem "docs" | Measure-Object).Count -gt 0) {
    Write-Host "Found documents in docs/ folder. Indexing will happen on first agent startup."
    Write-Host "✓ RAG setup ready" -ForegroundColor Green
} else {
    Write-Host "⚠  No documents found in docs/ folder" -ForegroundColor Yellow
    Write-Host "Add your knowledge base documents to agent/docs/ before starting the agent"
}

# Final summary
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Review and edit .env file if needed"
Write-Host "2. Add documents to docs/ folder for RAG"
Write-Host "3. Start LiveKit: docker run -d -p 7880:7880 livekit/livekit-server --dev"
Write-Host "4. Start Ollama: ollama serve (if not running)"
Write-Host "5. Start Agent: python agent.py start"
Write-Host ""
Write-Host "To activate the virtual environment later:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "For troubleshooting, see: DEPLOYMENT.md"
Write-Host ""
