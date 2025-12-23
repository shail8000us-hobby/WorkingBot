#!/bin/bash
###############################################################################
# Quick Fix for tmux Control Issues
#
# Cleans up stale sockets and restarts control daemon
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}${BLUE}"
echo "================================================================================"
echo "🔧 tmux Quick Fix - Cleaning Up and Restarting"
echo "================================================================================"
echo -e "${NC}\n"

cd /Users/shailendrasinghrajawat/Projects/WorkingBot

echo -e "${YELLOW}Step 1: Killing any existing tmux session...${NC}"
/opt/homebrew/bin/tmux -S ~/.tmux-gridbot/default kill-session -t gridbot 2>/dev/null || true
echo -e "${GREEN}✅ Session killed${NC}\n"

echo -e "${YELLOW}Step 2: Removing stale socket...${NC}"
rm -f ~/.tmux-gridbot/default
echo -e "${GREEN}✅ Socket removed${NC}\n"

echo -e "${YELLOW}Step 3: Killing any bot processes...${NC}"
pkill -9 -f "bot/run.py" 2>/dev/null || true
pkill -9 -f "bot/guardian" 2>/dev/null || true
pkill -9 -f "bot/heartbeat" 2>/dev/null || true
sleep 2
echo -e "${GREEN}✅ Bot processes cleared${NC}\n"

echo -e "${YELLOW}Step 4: Restarting tmux control daemon...${NC}"
pkill -9 -f "tmux_control_daemon.py" 2>/dev/null || true
sleep 2

# Check if LaunchAgent will restart it
if launchctl list | grep -q "com.gridbot.tmuxcontrol"; then
    echo "  LaunchAgent will auto-restart daemon..."
    sleep 5
else
    echo "  Starting daemon manually..."
    cd scripts
    python3 tmux_control_daemon.py &
    cd ..
fi

echo -e "${GREEN}✅ Control daemon restarted${NC}\n"

echo -e "${YELLOW}Step 5: Waiting for daemon to initialize...${NC}"
sleep 5

echo -e "${BLUE}🔍 Testing daemon...${NC}"
if curl -s http://127.0.0.1:5556/api/tmux/status > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Control daemon responding!${NC}\n"
else
    echo -e "${RED}⚠️  Control daemon not responding yet (may need more time)${NC}\n"
fi

echo -e "${BOLD}${BLUE}================================================================================${NC}"
echo -e "${BOLD}${GREEN}✅ tmux Cleanup Complete!${NC}"
echo -e "${BOLD}${BLUE}================================================================================${NC}\n"

echo -e "${BOLD}Next Steps:${NC}"
echo "  1. Open WebUI: ${BLUE}http://localhost:5555${NC}"
echo "  2. Navigate to tmux Control Center panel"
echo "  3. Click 'Start with tmux'"
echo "  4. Should work now!"
echo ""

echo -e "${YELLOW}If still fails:${NC}"
echo "  • Check logs: ${BLUE}tail -f logs/tmux_control_daemon.log${NC}"
echo "  • Manual start: ${BLUE}./scripts/start_tmux_daemon.sh${NC}"
echo ""

echo -e "${GREEN}🎉 Ready to try again!${NC}\n"

