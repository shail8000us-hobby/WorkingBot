#!/bin/bash
# ============================================================================
# Quick Start Script for PM2 Trading System
# ============================================================================
#
# This script helps you quickly start the trading system with proper checks
#
# Usage: ./quick_start.sh
#
# ============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║           WorkingBot PM2 Trading System - Quick Start         ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "ecosystem.production.config.js" ]; then
    echo -e "${RED}❌ Error: Not in WorkingBot directory${NC}"
    echo -e "${YELLOW}Please run from /Users/ssr/Projects/WorkingBot${NC}"
    exit 1
fi

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo -e "${RED}❌ PM2 is not installed${NC}"
    echo -e "${YELLOW}Installing PM2...${NC}"
    npm install -g pm2
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to install PM2${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ PM2 installed${NC}"
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"
echo ""

# Show current status
echo -e "${BLUE}📊 Current PM2 Status:${NC}"
pm2 list
echo ""

# Interactive menu
echo -e "${CYAN}What would you like to do?${NC}"
echo ""
echo "  1) Start Guardian + WebUI (recommended first)"
echo "  2) Start BTC LONG bot"
echo "  3) Start ETH LONG bot"
echo "  4) Start all trading bots"
echo "  5) Start everything"
echo "  6) Stop all"
echo "  7) View status"
echo "  8) Setup Guardian LaunchAgent (auto-start on boot)"
echo "  9) Exit"
echo ""
read -p "Enter choice [1-9]: " choice

case $choice in
    1)
        echo -e "${BLUE}🚀 Starting Guardian and WebUI...${NC}"
        ./pm2_manager.sh start guardian
        ./pm2_manager.sh start webui
        echo ""
        echo -e "${GREEN}✅ Core services started${NC}"
        echo -e "${CYAN}📍 WebUI: http://localhost:5555${NC}"
        ;;
    2)
        echo -e "${BLUE}🚀 Starting BTC LONG bot...${NC}"
        ./pm2_manager.sh start btc-long
        echo ""
        echo -e "${GREEN}✅ BTC LONG bot started${NC}"
        ;;
    3)
        echo -e "${BLUE}🚀 Starting ETH LONG bot...${NC}"
        ./pm2_manager.sh start eth-long
        echo ""
        echo -e "${GREEN}✅ ETH LONG bot started${NC}"
        ;;
    4)
        echo -e "${BLUE}🚀 Starting all trading bots...${NC}"
        ./pm2_manager.sh start all-bots
        echo ""
        echo -e "${GREEN}✅ All trading bots started${NC}"
        ;;
    5)
        echo -e "${BLUE}🚀 Starting everything...${NC}"
        ./pm2_manager.sh start all
        echo ""
        echo -e "${GREEN}✅ All components started${NC}"
        echo -e "${CYAN}📍 WebUI: http://localhost:5555${NC}"
        ;;
    6)
        echo -e "${YELLOW}🛑 Stopping all processes...${NC}"
        ./pm2_manager.sh stop all
        echo ""
        echo -e "${GREEN}✅ All processes stopped${NC}"
        ;;
    7)
        ./pm2_manager.sh status
        ;;
    8)
        echo -e "${BLUE}⚙️  Setting up Guardian LaunchAgent...${NC}"
        
        # Copy plist file
        cp com.gridbot.guardian.plist ~/Library/LaunchAgents/
        
        # Load the agent
        launchctl unload ~/Library/LaunchAgents/com.gridbot.guardian.plist 2>/dev/null
        launchctl load ~/Library/LaunchAgents/com.gridbot.guardian.plist
        
        echo ""
        echo -e "${GREEN}✅ Guardian LaunchAgent installed${NC}"
        echo -e "${CYAN}Guardian will now start automatically on system boot${NC}"
        echo ""
        echo "Check status with:"
        echo "  launchctl list | grep gridbot.guardian"
        ;;
    9)
        echo -e "${CYAN}Goodbye!${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Next steps:${NC}"
echo ""
echo "  • View logs:    ${CYAN}./pm2_manager.sh logs btc-long${NC}"
echo "  • Monitor:      ${CYAN}./pm2_manager.sh monit${NC}"
echo "  • Check status: ${CYAN}./pm2_manager.sh status${NC}"
echo "  • Open WebUI:   ${CYAN}http://localhost:5555${NC}"
echo ""
echo -e "${YELLOW}📖 Full documentation: PM2_PROCESS_MANAGER_GUIDE.md${NC}"
echo ""
