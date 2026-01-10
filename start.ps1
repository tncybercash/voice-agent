#Requires -Version 5.1
<#
.SYNOPSIS
    AI Voice Agent - All-in-One Startup Script for Windows

.DESCRIPTION
    This script starts all components of the AI Voice Agent system:
    - Docker services (LiveKit, Speaches)
    - Ollama LLM server
    - Python Voice Agent
    - Agent API Server
    - Next.js Frontend

.NOTES
    Run this script from the project root directory
    Requires: Docker, Python 3.11+, Node.js 18+, pnpm, Ollama
#>

param(
    [switch]$SkipDocker,
    [switch]$SkipOllama,
    [switch]$SkipAgent,
    [switch]$SkipAPI,
    [switch]$SkipFrontend,
    [switch]$GPU,
    [switch]$Help
)

# Colors for output
$Colors = @{
    Success = "Green"
    Info = "Cyan"
    Warning = "Yellow"
    Error = "Red"
    Header = "Magenta"
}

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Colors.Header
    Write-Host "  $Message" -ForegroundColor $Colors.Header
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor $Colors.Header
    Write-Host ""
}

function Write-Step {
    param([string]$Message)
    Write-Host "▶ $Message" -ForegroundColor $Colors.Info
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor $Colors.Success
}

function Write-Warn {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor $Colors.Warning
}

function Write-Err {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor $Colors.Error
}

function Show-Help {
    Write-Host @"

AI Voice Agent - Startup Script

USAGE:
    .\start.ps1 [OPTIONS]

OPTIONS:
    -SkipDocker     Skip starting Docker services (LiveKit, Speaches)
    -SkipOllama     Skip starting Ollama LLM server
    -SkipAgent      Skip starting Python voice agent
    -SkipAPI        Skip starting Agent API server
    -SkipFrontend   Skip starting Next.js frontend
    -GPU            Use GPU-accelerated Speaches (requires NVIDIA GPU + CUDA)
    -Help           Show this help message

EXAMPLES:
    .\start.ps1                    # Start everything
    .\start.ps1 -GPU               # Start with GPU acceleration
    .\start.ps1 -SkipDocker        # Start without Docker (services already running)
    .\start.ps1 -SkipOllama        # Use cloud LLM instead of local Ollama

PREREQUISITES:
    - Docker Desktop
    - Python 3.11+
    - Node.js 18+ with pnpm
    - Ollama (optional, for local LLM)
    - PostgreSQL 13+ with pgvector

"@
    exit 0
}

function Test-Command {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

function Test-GPU {
    # Check if nvidia-smi exists and can detect a GPU
    if (Test-Command "nvidia-smi") {
        try {
            $null = nvidia-smi 2>&1
            return $LASTEXITCODE -eq 0
        } catch {
            return $false
        }
    }
    return $false
}

function Test-Port {
    param([int]$Port)
    $connection = Test-NetConnection -ComputerName localhost -Port $Port -WarningAction SilentlyContinue
    return $connection.TcpTestSucceeded
}

function Wait-ForService {
    param(
        [string]$Name,
        [int]$Port,
        [int]$TimeoutSeconds = 60
    )
    
    Write-Step "Waiting for $Name on port $Port..."
    $elapsed = 0
    $interval = 2
    
    while ($elapsed -lt $TimeoutSeconds) {
        if (Test-Port -Port $Port) {
            Write-Success "$Name is ready!"
            return $true
        }
        Start-Sleep -Seconds $interval
        $elapsed += $interval
        Write-Host "." -NoNewline
    }
    
    Write-Host ""
    Write-Warn "$Name did not start within $TimeoutSeconds seconds"
    return $false
}

# Show help if requested
if ($Help) {
    Show-Help
}

# Header
Write-Header "🎙️ AI Voice Agent - Startup Script"

# Check prerequisites
Write-Step "Checking prerequisites..."

$prereqsMet = $true

if (-not (Test-Command "docker")) {
    Write-Err "Docker is not installed or not in PATH"
    $prereqsMet = $false
}

if (-not (Test-Command "python")) {
    Write-Err "Python is not installed or not in PATH"
    $prereqsMet = $false
}

if (-not (Test-Command "node")) {
    Write-Err "Node.js is not installed or not in PATH"
    $prereqsMet = $false
}

if (-not (Test-Command "pnpm")) {
    Write-Warn "pnpm is not installed. Installing..."
    npm install -g pnpm
}

if (-not $SkipOllama -and -not (Test-Command "ollama")) {
    Write-Warn "Ollama is not installed. Local LLM will not be available."
    Write-Warn "Install from: https://ollama.ai/"
}

if (-not $prereqsMet) {
    Write-Err "Please install missing prerequisites and try again."
    exit 1
}

Write-Success "Prerequisites check passed!"

# Get project root directory
$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) {
    $ProjectRoot = Get-Location
}

Write-Host "Project root: $ProjectRoot" -ForegroundColor Gray

# ============================================
# 1. Start Docker Services
# ============================================
if (-not $SkipDocker) {
    Write-Header "🐳 Starting Docker Services"
    
    Set-Location $ProjectRoot
    
    # Check if Docker is running
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Docker is not running. Please start Docker Desktop and try again."
        exit 1
    }
    
    # Determine which Speaches service to use
    if ($GPU) {
        $speachesService = "speaches-gpu"
        Write-Step "Using GPU-accelerated Speaches (-GPU flag)"
    } elseif (Test-GPU) {
        $speachesService = "speaches-gpu"
        Write-Step "GPU detected! Using GPU-accelerated Speaches automatically"
    } else {
        $speachesService = "speaches"
        Write-Step "No GPU detected, using CPU-based Speaches"
    }
    
    Write-Step "Starting LiveKit and $speachesService..."
    
    docker-compose up -d livekit $speachesService
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Docker services started!"
        
        # Wait for services
        Wait-ForService -Name "LiveKit" -Port 7880 -TimeoutSeconds 30
        $speachesPort = if ($speachesService -eq "speaches-gpu") { 8003 } else { 8002 }
        $speachesName = if ($speachesService -eq "speaches-gpu") { "Speaches (GPU)" } else { "Speaches (CPU)" }
        Wait-ForService -Name $speachesName -Port $speachesPort -TimeoutSeconds 60
    } else {
        Write-Err "Failed to start Docker services"
    }
}

# ============================================
# 2. Start Ollama
# ============================================
if (-not $SkipOllama) {
    Write-Header "🧠 Starting Ollama LLM Server"
    
    if (Test-Command "ollama") {
        # Check if Ollama is already running
        if (Test-Port -Port 11434) {
            Write-Success "Ollama is already running on port 11434"
        } else {
            Write-Step "Starting Ollama server..."
            
            # Start Ollama in background
            Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
            
            Wait-ForService -Name "Ollama" -Port 11434 -TimeoutSeconds 30
            
            # Pull models if not present
            Write-Step "Checking for required models..."
            $models = ollama list 2>&1
            
            if ($models -notmatch "llama3.2") {
                Write-Step "Pulling llama3.2 model (this may take a while)..."
                ollama pull llama3.2:latest
            }
            
            if ($models -notmatch "nomic-embed-text") {
                Write-Step "Pulling nomic-embed-text model..."
                ollama pull nomic-embed-text:latest
            }
            
            Write-Success "Ollama is ready!"
        }
    } else {
        Write-Warn "Ollama not found. Skipping local LLM setup."
    }
}

# ============================================
# 3. Start Python Agent
# ============================================
if (-not $SkipAgent) {
    Write-Header "🤖 Starting Python Voice Agent"
    
    $agentDir = Join-Path $ProjectRoot "agent"
    Set-Location $agentDir
    
    # Check for virtual environment
    $venvPath = Join-Path $agentDir ".venv"
    if (-not (Test-Path $venvPath)) {
        Write-Step "Creating Python virtual environment..."
        python -m venv .venv
    }
    
    # Activate virtual environment
    Write-Step "Activating virtual environment..."
    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    & $activateScript
    
    # Install dependencies
    Write-Step "Installing/updating Python dependencies..."
    pip install -q -r requirements.txt
    
    # Check for .env file
    $envFile = Join-Path $agentDir ".env"
    if (-not (Test-Path $envFile)) {
        $envExample = Join-Path $agentDir ".env.example"
        if (Test-Path $envExample) {
            Write-Step "Creating .env from .env.example..."
            Copy-Item $envExample $envFile
            Write-Warn "Please edit agent/.env with your configuration!"
        } else {
            Write-Warn "No .env file found. Please create one from the template."
        }
    }
    
    # Kill any existing agent processes on port 8081
    Write-Step "Checking for existing agent processes..."
    $agentProcess = Get-NetTCPConnection -LocalPort 8081 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    if ($agentProcess) {
        Write-Step "Stopping existing agent process (PID: $agentProcess)..."
        Stop-Process -Id $agentProcess -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    
    # Clean old log
    Remove-Item (Join-Path $agentDir "agent.log") -ErrorAction SilentlyContinue
    
    # Start agent in new terminal with logging
    Write-Step "Starting voice agent..."
    $logFile = Join-Path $agentDir "agent.log"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$agentDir'; & '.\.venv\Scripts\Activate.ps1'; python agent.py start 2>&1 | Tee-Object -FilePath '$logFile'"
    
    Write-Success "Voice agent started in new terminal!"
}

# ============================================
# 4. Start Agent API Server
# ============================================
if (-not $SkipAPI) {
    Write-Header "🌐 Starting Agent API Server"
    
    $agentDir = Join-Path $ProjectRoot "agent"
    
    # Start API server in new terminal
    Write-Step "Starting API server on port 8000..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$agentDir'; & '.\.venv\Scripts\Activate.ps1'; python api_server.py"
    
    Start-Sleep -Seconds 3
    Wait-ForService -Name "Agent API" -Port 8000 -TimeoutSeconds 30
    
    Write-Success "API server started!"
}

# ============================================
# 5. Start Frontend
# ============================================
if (-not $SkipFrontend) {
    Write-Header "💻 Starting Next.js Frontend"
    
    $frontendDir = Join-Path $ProjectRoot "front-end"
    Set-Location $frontendDir
    
    # Check for node_modules
    $nodeModules = Join-Path $frontendDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Step "Installing frontend dependencies..."
        pnpm install
    }
    
    # Check for .env.local
    $envLocal = Join-Path $frontendDir ".env.local"
    if (-not (Test-Path $envLocal)) {
        $envExample = Join-Path $frontendDir ".env.example"
        if (Test-Path $envExample) {
            Write-Step "Creating .env.local from .env.example..."
            Copy-Item $envExample $envLocal
            Write-Warn "Please edit front-end/.env.local with your configuration!"
        }
    }
    
    # Kill any existing process on port 3000
    Write-Step "Checking port 3000..."
    $processOnPort = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    if ($processOnPort) {
        Write-Step "Stopping existing process on port 3000 (PID: $processOnPort)..."
        Stop-Process -Id $processOnPort -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    
    # Start frontend in new terminal
    Write-Step "Starting Next.js development server on port 3000..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendDir'; pnpm dev"
    
    Start-Sleep -Seconds 5
    Wait-ForService -Name "Frontend" -Port 3000 -TimeoutSeconds 60
    
    Write-Success "Frontend started!"
}

# ============================================
# Summary
# ============================================
Write-Header "✅ Startup Complete!"

Write-Host @"

🎉 All services are running!

SERVICES:
  📍 Frontend:     http://localhost:3000
  📍 Agent API:    http://localhost:8000
  📍 LiveKit:      ws://localhost:7880
  📍 Ollama:       http://localhost:11434

NEXT STEPS:
  1. Open http://localhost:3000 in your browser
  2. Click "START CALL" to begin a conversation
  3. Allow microphone access when prompted

TO STOP:
  - Close all terminal windows
  - Run: docker-compose down

LOGS:
  - Docker: docker-compose logs -f
  - Agent: Check the agent terminal window

"@ -ForegroundColor $Colors.Info

# Return to project root
Set-Location $ProjectRoot
