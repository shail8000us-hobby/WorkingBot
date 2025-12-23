#!/bin/bash

# GridBot Easy Commands Script
# This makes controlling your bot super easy!

# Colors for pretty output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Go to bot directory
cd /Users/shailendrasinghrajawat/Projects/WorkingBot

# Show menu
echo ""
echo "🤖 ═══════════════════════════════════════════════"
echo "   GRIDBOT EASY CONTROL PANEL"
echo "═══════════════════════════════════════════════"
echo ""
echo "What do you want to do?"
echo ""
echo "  1) Check bot status"
echo "  2) Start bot"
echo "  3) Stop bot"
echo "  4) Restart bot"
echo "  5) View logs (last 20 lines)"
echo "  6) Watch logs (live)"
echo "  7) Open WebUI in browser"
echo "  8) Check bot health"
echo "  9) Exit"
echo ""
echo -n "Enter your choice (1-9): "
read choice

case $choice in
    1)
        echo ""
        echo -e "${BLUE}🔍 Checking bot status...${NC}"
        echo ""
        if launchctl list | grep -q "com.gridbot.webui"; then
            PID=$(launchctl list | grep com.gridbot.webui | awk '{print $2}')
            echo -e "${GREEN}✅ Bot is RUNNING (PID: $PID)${NC}"
        else
            echo -e "${RED}❌ Bot is NOT running${NC}"
        fi
        ;;
    
    2)
        echo ""
        echo -e "${BLUE}▶️  Starting bot...${NC}"
        launchctl start com.gridbot.webui
        sleep 2
        if launchctl list | grep -q "com.gridbot.webui"; then
            echo -e "${GREEN}✅ Bot started successfully!${NC}"
        else
            echo -e "${RED}❌ Failed to start bot${NC}"
        fi
        ;;
    
    3)
        echo ""
        echo -e "${YELLOW}⏸️  Stopping bot...${NC}"
        launchctl stop com.gridbot.webui
        sleep 1
        echo -e "${GREEN}✅ Bot stopped${NC}"
        ;;
    
    4)
        echo ""
        echo -e "${BLUE}🔄 Restarting bot...${NC}"
        launchctl stop com.gridbot.webui
        sleep 2
        launchctl start com.gridbot.webui
        sleep 2
        if launchctl list | grep -q "com.gridbot.webui"; then
            echo -e "${GREEN}✅ Bot restarted successfully!${NC}"
        else
            echo -e "${RED}❌ Failed to restart bot${NC}"
        fi
        ;;
    
    5)
        echo ""
        echo -e "${BLUE}📜 Last 20 log entries:${NC}"
        echo ""
        tail -20 webui_backend.log
        ;;
    
    6)
        echo ""
        echo -e "${BLUE}📡 Watching logs live... (Press Ctrl+C to stop)${NC}"
        echo ""
        sleep 1
        tail -f webui_backend.log
        ;;
    
    7)
        echo ""
        echo -e "${BLUE}🌐 Opening WebUI in browser...${NC}"
        open http://localhost:5555
        echo -e "${GREEN}✅ Browser opened!${NC}"
        ;;
    
    8)
        echo ""
        echo -e "${BLUE}🏥 Checking bot health...${NC}"
        echo ""
        curl -s http://localhost:5555/api/health | python3 -m json.tool | head -15
        ;;
    
    9)
        echo ""
        echo -e "${GREEN}👋 Goodbye!${NC}"
        exit 0
        ;;
    
    *)
        echo ""
        echo -e "${RED}❌ Invalid choice. Please run the script again.${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

