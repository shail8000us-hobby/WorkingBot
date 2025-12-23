#!/bin/bash
# webui/stop.sh
# Stop WebUI backend and clean up lock files

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                                       ║${NC}"
echo -e "${CYAN}║   🛑 GridBot WebUI - Stop Script                                      ║${NC}"
echo -e "${CYAN}║                                                                       ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT"

echo -e "${YELLOW}Step 1: Stopping WebUI backend processes...${NC}"

# Check if any WebUI processes are running
if ps aux | grep -E "app.py" | grep -v grep > /dev/null; then
    echo "  Found running WebUI processes:"
    ps aux | grep -E "app.py" | grep -v grep | awk '{print "    PID:", $2, "Command:", $11, $12, $13, $14, $15}'
    
    echo "  Stopping WebUI processes..."
    pkill -f "app.py" 2>/dev/null || true
    
    # Wait for graceful shutdown
    sleep 3
    
    # Check if processes are still running
    if ps aux | grep -E "app.py" | grep -v grep > /dev/null; then
        echo "  Force killing remaining processes..."
        pkill -9 -f "app.py" 2>/dev/null || true
        sleep 1
    fi
    
    echo -e "  ${GREEN}✅ WebUI processes stopped${NC}"
else
    echo -e "  ${GREEN}✅ No WebUI processes found${NC}"
fi

echo ""
echo -e "${YELLOW}Step 2: Cleaning up lock files...${NC}"

# Clean up WebUI lock file
if [ -f ".webui_instance.lock" ]; then
    rm -f .webui_instance.lock
    echo -e "  ${GREEN}✅ Removed .webui_instance.lock${NC}"
else
    echo -e "  ${GREEN}✅ No WebUI lock file found${NC}"
fi

# Clean up any other related lock files
rm -f .webui_backend.lock 2>/dev/null || true

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ WebUI Backend Stopped Successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}📖 Next Steps:${NC}"
echo ""
echo -e "  ${YELLOW}To start WebUI again:${NC}"
echo -e "    • Run: ${GREEN}./webui/start_clean.sh${NC}"
echo -e "    • Or: ${GREEN}python3 webui/backend/app.py --port 5555${NC}"
echo ""
echo -e "  ${YELLOW}Verify cleanup:${NC}"
echo -e "    • Run: ${GREEN}ps aux | grep app.py${NC}"
echo -e "    • Should show no results"
echo ""
echo -e "  ${YELLOW}Check lock files:${NC}"
echo -e "    • Run: ${GREEN}ls -la .webui_instance.lock${NC}"
echo -e "    • Should show 'No such file'"
echo ""
echo -e "${GREEN}🛑 WebUI is completely stopped!${NC}"