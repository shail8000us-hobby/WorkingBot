#!/bin/bash
# webui/start_clean.sh
# Clean startup script for WebUI backend with single instance protection

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                                       ║${NC}"
echo -e "${CYAN}║   🌐 GridBot WebUI - Clean Startup                                    ║${NC}"
echo -e "${CYAN}║                                                                       ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT"

echo -e "${YELLOW}Step 1: Cleaning up existing WebUI processes...${NC}"

# Stop any existing WebUI backend processes
echo "  Stopping existing WebUI backend processes..."
pkill -f "app.py" 2>/dev/null || echo "    No existing WebUI processes found"

# Wait for processes to stop
sleep 2

# Check if any WebUI processes are still running
if ps aux | grep -E "app.py" | grep -v grep > /dev/null; then
    echo -e "  ${RED}❌ Some WebUI processes are still running${NC}"
    echo "  Force killing remaining processes..."
    pkill -9 -f "app.py" 2>/dev/null || true
    sleep 1
fi

# Clean up any stale lock files
echo "  Cleaning up stale lock files..."
rm -f .webui_instance.lock 2>/dev/null || true

echo -e "  ${GREEN}✅ Cleanup complete${NC}"
echo ""

echo -e "${YELLOW}Step 2: Starting WebUI backend with single instance protection...${NC}"

# Start WebUI backend
echo "  Starting WebUI backend..."
python3 webui/backend/app.py --port 5555 &

# Wait a moment for startup
sleep 3

# Check if WebUI started successfully
if ps aux | grep -E "app.py" | grep -v grep > /dev/null; then
    echo -e "  ${GREEN}✅ WebUI backend started successfully${NC}"
    
    # Get the PID of the new WebUI process
    WEBUI_PID=$(ps aux | grep -E "app.py" | grep -v grep | awk '{print $2}' | head -1)
    echo "  WebUI PID: $WEBUI_PID"
    
    # Test if WebUI is responding
    echo "  Testing WebUI connectivity..."
    if curl -s http://localhost:5555/api/health > /dev/null; then
        echo -e "  ${GREEN}✅ WebUI is responding to requests${NC}"
    else
        echo -e "  ${YELLOW}⚠️  WebUI started but not yet responding (may need more time)${NC}"
    fi
else
    echo -e "  ${RED}❌ Failed to start WebUI backend${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ WebUI Backend Started Successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}📖 Quick Guide:${NC}"
echo ""
echo -e "  ${YELLOW}Access WebUI:${NC}"
echo -e "    • URL: ${GREEN}http://localhost:5555${NC}"
echo -e "    • Open in your browser"
echo ""
echo -e "  ${YELLOW}Stop WebUI:${NC}"
echo -e "    • Run: ${GREEN}./webui/stop.sh${NC}"
echo -e "    • Or: ${GREEN}pkill -f app.py${NC}"
echo ""
echo -e "  ${YELLOW}Check Status:${NC}"
echo -e "    • Run: ${GREEN}ps aux | grep app.py${NC}"
echo -e "    • Or: ${GREEN}curl http://localhost:5555/api/health${NC}"
echo ""
echo -e "  ${YELLOW}Single Instance Protection:${NC}"
echo -e "    • Only ONE WebUI backend can run at a time"
echo -e "    • Lock file: ${GREEN}.webui_instance.lock${NC}"
echo -e "    • Automatic cleanup on exit"
echo ""
echo -e "${GREEN}🚀 WebUI is ready for use!${NC}"

