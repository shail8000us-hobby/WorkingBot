#!/bin/bash
# ============================================================================
# PM2 AsyncBot Manager - Production Ready Process Management
# ============================================================================
#
# Manages AsyncBot via PM2 for production deployment
#
# Features:
#   ✅ Start/Stop/Restart AsyncBot in demo or live mode
#   ✅ View logs and status
#   ✅ Graceful shutdown with order cancellation
#   ✅ Automatic restart on crash
#   ✅ Memory monitoring and limits
#   ✅ Full WebUI integration
#
# Usage:
#   ./pm2_async_bot.sh start live      # Start AsyncBot in live mode
#   ./pm2_async_bot.sh start demo      # Start AsyncBot in demo mode
#   ./pm2_async_bot.sh stop live       # Stop live bot (graceful)
#   ./pm2_async_bot.sh restart live    # Restart live bot
#   ./pm2_async_bot.sh status          # Show all PM2 processes
#   ./pm2_async_bot.sh logs live       # Tail live bot logs
#   ./pm2_async_bot.sh monit           # Open PM2 monitoring dashboard
#
# ============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/Users/ssr/Projects/WorkingBot"
ECOSYSTEM_FILE="ecosystem.config.js"

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo -e "${RED}❌ Error: PM2 is not installed${NC}"
    echo -e "${YELLOW}Install with: sudo npm install -g pm2${NC}"
    exit 1
fi

# Function to show help
show_help() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         PM2 AsyncBot Manager - Production Ready                ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Usage:"
    echo "  ${GREEN}./pm2_async_bot.sh start <mode>${NC}     Start AsyncBot (mode: live/demo)"
    echo "  ${GREEN}./pm2_async_bot.sh stop <mode>${NC}      Stop AsyncBot gracefully"
    echo "  ${GREEN}./pm2_async_bot.sh restart <mode>${NC}   Restart AsyncBot"
    echo "  ${GREEN}./pm2_async_bot.sh status${NC}           Show all PM2 processes"
    echo "  ${GREEN}./pm2_async_bot.sh logs <mode>${NC}      Tail logs (live/demo)"
    echo "  ${GREEN}./pm2_async_bot.sh monit${NC}            Open PM2 monitoring dashboard"
    echo "  ${GREEN}./pm2_async_bot.sh list${NC}             List all PM2 processes"
    echo "  ${GREEN}./pm2_async_bot.sh save${NC}             Save PM2 process list"
    echo "  ${GREEN}./pm2_async_bot.sh startup${NC}          Setup PM2 auto-startup on boot"
    echo ""
    echo "Examples:"
    echo "  ${YELLOW}./pm2_async_bot.sh start live${NC}      # Start AsyncBot trading live"
    echo "  ${YELLOW}./pm2_async_bot.sh stop live${NC}       # Stop live bot gracefully"
    echo "  ${YELLOW}./pm2_async_bot.sh logs live${NC}       # Watch live bot logs"
    echo "  ${YELLOW}./pm2_async_bot.sh monit${NC}           # Open monitoring dashboard"
    echo ""
    echo "Features:"
    echo "  ✅ AsyncBot v2.0 (Actor + Event Sourcing + Saga)"
    echo "  ✅ 100% Feature Parity with old GridBot"
    echo "  ✅ Auto-restart on crash"
    echo "  ✅ Graceful shutdown (30s timeout)"
    echo "  ✅ Memory monitoring (500MB limit)"
    echo "  ✅ Full WebUI integration"
    echo "  ✅ TP Retry Queue"
    echo "  ✅ Reconciliation system"
    echo ""
}

# Function to start bot
start_bot() {
    MODE=$1
    
    if [ -z "$MODE" ]; then
        echo -e "${RED}❌ Error: Mode required (live/demo)${NC}"
        echo "Usage: ./pm2_async_bot.sh start <mode>"
        exit 1
    fi
    
    if [ "$MODE" != "live" ] && [ "$MODE" != "demo" ]; then
        echo -e "${RED}❌ Error: Invalid mode '$MODE' (must be 'live' or 'demo')${NC}"
        exit 1
    fi
    
    PROCESS_NAME="gridbot-$MODE"
    
    echo -e "${BLUE}🚀 Starting AsyncBot in ${MODE} mode...${NC}"
    echo ""
    
    # Check if already running
    if pm2 jlist 2>/dev/null | grep -q "\"name\":\"$PROCESS_NAME\"" && pm2 jlist 2>/dev/null | grep -q "\"status\":\"online\""; then
        echo -e "${YELLOW}⚠️  AsyncBot ($MODE) is already running${NC}"
        echo ""
        pm2 jlist | grep -A 10 "\"name\":\"$PROCESS_NAME\"" | head -15
        echo ""
        echo "To restart: ./pm2_async_bot.sh restart $MODE"
        exit 0
    fi
    
    # Start via PM2
    cd "$PROJECT_DIR" || exit 1
    pm2 start "$ECOSYSTEM_FILE" --only "$PROCESS_NAME"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ AsyncBot started successfully in ${MODE} mode!${NC}"
        echo ""
        echo "Process details:"
        pm2 describe "$PROCESS_NAME"
        echo ""
        echo "Next steps:"
        echo "  • View logs: ${CYAN}./pm2_async_bot.sh logs $MODE${NC}"
        echo "  • Monitor: ${CYAN}./pm2_async_bot.sh monit${NC}"
        echo "  • Check status: ${CYAN}./pm2_async_bot.sh status${NC}"
        echo "  • WebUI: http://localhost:5555"
        echo ""
        echo "Features active:"
        echo "  ✅ Actor Pattern (lock-free)"
        echo "  ✅ Event Sourcing (audit trail)"
        echo "  ✅ Saga Pattern (transactional orders)"
        echo "  ✅ TP Retry Queue (10s recovery)"
        echo "  ✅ Reconciliation (5min fallback)"
        echo "  ✅ Memory monitoring (500MB limit)"
        echo "  ✅ Guardian integration"
        echo "  ✅ WebUI monitoring"
        echo ""
    else
        echo -e "${RED}❌ Failed to start AsyncBot${NC}"
        exit 1
    fi
}

# Function to stop bot
stop_bot() {
    MODE=$1
    
    if [ -z "$MODE" ]; then
        echo -e "${RED}❌ Error: Mode required (live/demo)${NC}"
        echo "Usage: ./pm2_async_bot.sh stop <mode>"
        exit 1
    fi
    
    PROCESS_NAME="gridbot-$MODE"
    
    echo -e "${YELLOW}🛑 Stopping AsyncBot ($MODE) gracefully...${NC}"
    echo ""
    echo "Graceful shutdown sequence:"
    echo "  1. Send SIGTERM signal"
    echo "  2. Cancel pending orders (30s timeout)"
    echo "  3. Save final state"
    echo "  4. Exit cleanly"
    echo ""
    
    pm2 stop "$PROCESS_NAME"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ AsyncBot stopped gracefully${NC}"
        echo ""
        echo "Process is stopped but preserved in PM2 list."
        echo "To start again: ${CYAN}./pm2_async_bot.sh start $MODE${NC}"
        echo "To remove from list: ${CYAN}pm2 delete $PROCESS_NAME${NC}"
        echo ""
    else
        echo -e "${RED}❌ Failed to stop AsyncBot${NC}"
        exit 1
    fi
}

# Function to restart bot
restart_bot() {
    MODE=$1
    
    if [ -z "$MODE" ]; then
        echo -e "${RED}❌ Error: Mode required (live/demo)${NC}"
        echo "Usage: ./pm2_async_bot.sh restart <mode>"
        exit 1
    fi
    
    PROCESS_NAME="gridbot-$MODE"
    
    echo -e "${BLUE}🔄 Restarting AsyncBot ($MODE)...${NC}"
    echo ""
    
    pm2 restart "$PROCESS_NAME"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ AsyncBot restarted successfully${NC}"
        echo ""
        pm2 describe "$PROCESS_NAME"
        echo ""
    else
        echo -e "${RED}❌ Failed to restart AsyncBot${NC}"
        exit 1
    fi
}

# Function to show status
show_status() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           PM2 Process Status - AsyncBot v2.0                   ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    pm2 list
    
    echo ""
    echo -e "${CYAN}─────────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo "Commands:"
    echo "  • View logs: ${GREEN}./pm2_async_bot.sh logs <mode>${NC}"
    echo "  • Monitor: ${GREEN}./pm2_async_bot.sh monit${NC}"
    echo "  • Restart: ${GREEN}./pm2_async_bot.sh restart <mode>${NC}"
    echo ""
}

# Function to view logs
view_logs() {
    MODE=$1
    
    if [ -z "$MODE" ]; then
        echo -e "${YELLOW}⚠️  Mode not specified, showing all bot logs${NC}"
        pm2 logs --lines 50
        exit 0
    fi
    
    PROCESS_NAME="gridbot-$MODE"
    
    echo -e "${CYAN}📋 Tailing logs for AsyncBot ($MODE)...${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""
    
    pm2 logs "$PROCESS_NAME" --lines 100
}

# Function to open monitoring dashboard
open_monit() {
    echo -e "${CYAN}📊 Opening PM2 monitoring dashboard...${NC}"
    echo -e "${YELLOW}Press Q to exit${NC}"
    echo ""
    
    pm2 monit
}

# Function to list processes
list_processes() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║              PM2 Process List                                   ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    pm2 list
}

# Function to save process list
save_processes() {
    echo -e "${BLUE}💾 Saving PM2 process list...${NC}"
    echo ""
    echo "This saves the current PM2 process list for:"
    echo "  • Auto-startup on system reboot"
    echo "  • Resurrection after PM2 updates"
    echo ""
    
    pm2 save
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ PM2 process list saved${NC}"
        echo ""
        echo "Processes will be automatically restored on:"
        echo "  • System reboot (if PM2 startup is configured)"
        echo "  • PM2 update"
        echo "  • Manual resurrection with: pm2 resurrect"
        echo ""
    else
        echo -e "${RED}❌ Failed to save process list${NC}"
        exit 1
    fi
}

# Function to setup startup
setup_startup() {
    echo -e "${BLUE}🔧 Setting up PM2 auto-startup...${NC}"
    echo ""
    echo "This configures PM2 to automatically start on system boot."
    echo ""
    
    pm2 startup
    
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Copy and run the command above (as sudo if required)${NC}"
    echo ""
    echo "After running the startup command:"
    echo "  1. Start your bot: ${CYAN}./pm2_async_bot.sh start live${NC}"
    echo "  2. Save process list: ${CYAN}./pm2_async_bot.sh save${NC}"
    echo "  3. Reboot to test: ${CYAN}sudo reboot${NC}"
    echo ""
}

# Main command handler
COMMAND=${1:-help}
MODE=$2

case $COMMAND in
    start)
        start_bot "$MODE"
        ;;
    
    stop)
        stop_bot "$MODE"
        ;;
    
    restart)
        restart_bot "$MODE"
        ;;
    
    status)
        show_status
        ;;
    
    logs)
        view_logs "$MODE"
        ;;
    
    monit|monitor)
        open_monit
        ;;
    
    list|ls)
        list_processes
        ;;
    
    save)
        save_processes
        ;;
    
    startup)
        setup_startup
        ;;
    
    help|--help|-h)
        show_help
        ;;
    
    *)
        echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac

