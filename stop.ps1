#Requires -Version 5.1
<#
.SYNOPSIS
    AI Voice Agent - Stop All Services Script

.DESCRIPTION
    Stops all running AI Voice Agent services:
    - Docker containers (LiveKit, Speaches)
    - Python processes (Agent, API)
    - Node.js processes (Frontend)
    - Ollama (optional)
#>

param(
    [switch]$IncludeOllama,
    [switch]$Help
)

# Colors
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

if ($Help) {
    Write-Host @"

AI Voice Agent - Stop Script

USAGE:
    .\stop.ps1 [OPTIONS]

OPTIONS:
    -IncludeOllama    Also stop Ollama server
    -Help             Show this help message

"@
    exit 0
}

Write-Header "🛑 Stopping AI Voice Agent Services"

# Stop Docker containers
Write-Step "Stopping Docker containers..."
docker-compose down 2>$null
Write-Success "Docker containers stopped"

# Stop Python processes
Write-Step "Stopping Python processes..."
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "agent\.py|uvicorn|api_server"
} | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Success "Python processes stopped"

# Stop Node.js processes (Next.js)
Write-Step "Stopping Node.js processes..."
Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "next"
} | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Success "Node.js processes stopped"

# Stop Ollama if requested
if ($IncludeOllama) {
    Write-Step "Stopping Ollama..."
    Get-Process -Name "ollama" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Success "Ollama stopped"
}

Write-Header "✅ All Services Stopped"

Write-Host @"
All AI Voice Agent services have been stopped.

To restart, run:
    .\start.ps1

"@ -ForegroundColor $Colors.Info
