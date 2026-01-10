#!/bin/bash

#######################################
# AI Voice Agent - Startup Script
#######################################

set -e

# Colors
GREEN="\033[0;32m"
CYAN="\033[0;36m"
NC="\033[0m"

print_step() {
    echo -e "${CYAN}>> $1${NC}"
}

print_success() {
    echo -e "${GREEN}OK  $1${NC}"
}

# Get script directory
cd "$(dirname "${BASH_SOURCE[0]}")"

echo ""
echo "Starting AI Voice Agent..."
echo ""

# Kill all existing processes first
print_step "Stopping existing services..."

# Kill Python processes (agent and API server)
pkill -9 -f "agent.py" 2>/dev/null || true
pkill -9 -f "api_server.py" 2>/dev/null || true

# Kill Node/pnpm processes
pkill -9 -f "next dev" 2>/dev/null || true
pkill -9 -f "pnpm dev" 2>/dev/null || true
pkill -9 -f "node.*next" 2>/dev/null || true

sleep 1

# Free ports using lsof or fuser (multiple attempts)
for i in {1..3}; do
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti:3000 | xargs -r kill -9 2>/dev/null || true
        lsof -ti:8000 | xargs -r kill -9 2>/dev/null || true
        lsof -ti:8081 | xargs -r kill -9 2>/dev/null || true
    elif command -v fuser >/dev/null 2>&1; then
        fuser -k 3000/tcp 2>/dev/null || true
        fuser -k 8000/tcp 2>/dev/null || true
        fuser -k 8081/tcp 2>/dev/null || true
    fi
    sleep 1
done

print_success "All ports cleared"

# 1. Start Docker containers
print_step "Starting Docker containers..."
docker-compose up -d
print_success "Docker containers started"

echo ""
sleep 2

# 2. Start Agent
print_step "Starting Voice Agent..."
cd agent
if [ -d ".venv" ]; then
    source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
fi
python agent.py start &
cd ..
print_success "Voice Agent started"

echo ""
sleep 2

# 3. Start API Server
print_step "Starting API Server..."
cd agent
if [ -d ".venv" ]; then
    source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
fi
python api_server.py &
cd ..
print_success "API Server started"

echo ""
sleep 2

# 4. Start Frontend
print_step "Starting Frontend..."
cd front-end
pnpm dev --port 3000 &
cd ..
print_success "Frontend started"

echo ""
echo -e "${GREEN} All services started!${NC}"
echo ""
echo "Access the application at: http://localhost:3000"
echo ""
