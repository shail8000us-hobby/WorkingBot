#!/bin/bash

# Heartbeat Monitor Startup Script
# Starts the heartbeat monitoring system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                               ║${NC}"
echo -e "${BLUE}║   💓 HEARTBEAT MONITOR STARTUP                               ║${NC}"
echo -e "${BLUE}║                                                               ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Change to project directory
cd "$PROJECT_DIR"

# Check if heartbeat monitor module exists
if [ ! -f "bot/heartbeat/monitor.py" ]; then
    echo -e "${RED}❌ Heartbeat monitor module not found${NC}"
    echo -e "${YELLOW}   Expected: bot/heartbeat/monitor.py${NC}"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Starting Heartbeat Monitor...${NC}"
echo -e "${YELLOW}   Project Directory: $PROJECT_DIR${NC}"
echo ""

# Start the heartbeat monitor
python3 -m bot.heartbeat.monitor

echo -e "${GREEN}✅ Heartbeat Monitor started successfully${NC}"
