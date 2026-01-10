#!/bin/bash

#######################################
# AI Voice Agent - Stop Script
#######################################

set -e

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

echo ""
echo "Stopping AI Voice Agent..."
echo ""

# Stop Python processes
print_step "Stopping Python processes..."
pkill -f "agent.py" 2>/dev/null || true
pkill -f "api_server.py" 2>/dev/null || true
sleep 1
print_success "Python processes stopped"

# Stop Node.js processes
print_step "Stopping Node.js processes..."
pkill -f "next-server" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
pkill -f "pnpm dev" 2>/dev/null || true
sleep 1
print_success "Node.js processes stopped"

# Free ports
print_step "Freeing ports..."
if command -v lsof >/dev/null 2>&1; then
    lsof -ti:3000 | xargs -r kill -9 2>/dev/null || true
    lsof -ti:8000 | xargs -r kill -9 2>/dev/null || true
    lsof -ti:8081 | xargs -r kill -9 2>/dev/null || true
elif command -v fuser >/dev/null 2>&1; then
    fuser -k 3000/tcp 2>/dev/null || true
    fuser -k 8000/tcp 2>/dev/null || true
    fuser -k 8081/tcp 2>/dev/null || true
fi
print_success "Ports freed"

# Stop Docker containers
print_step "Stopping Docker containers..."
docker-compose down
print_success "Docker containers stopped"

echo ""
echo -e "${GREEN}✓ All services stopped!${NC}"
echo ""
