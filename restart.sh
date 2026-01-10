#!/bin/bash

#######################################
# AI Voice Agent - Restart Script
#######################################

set -e

# Get script directory
cd "$(dirname "${BASH_SOURCE[0]}")"

echo ""
echo "Restarting AI Voice Agent..."
echo ""

# Stop all services
./stop.sh

echo ""
sleep 2

# Start all services
./start.sh
