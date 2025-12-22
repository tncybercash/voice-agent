# Run agent locally (standalone, outside Docker)

Write-Host "🤖 Starting Voice Agent..." -ForegroundColor Cyan
Write-Host ""

Set-Location agent

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "📦 Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate virtual environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Cyan
& ".\.venv\Scripts\Activate.ps1"

# Install/update dependencies
Write-Host "📥 Installing dependencies..." -ForegroundColor Cyan
pip install -q -r requirements.txt

Write-Host ""
Write-Host "✅ Starting agent..." -ForegroundColor Green
Write-Host "   LiveKit: ws://localhost:7880" -ForegroundColor White
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Run agent
python myagent.py start
