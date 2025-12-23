#!/bin/bash
# Unified Bot + Shadow Mode Manager
# Control: WebUI for config, Terminal for start/stop

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# PID files
SHADOW_PID_FILE=".pids/shadow_mode.pid"
THREADED_PID_FILE=".pids/threaded_bot.pid"

show_header() {
    clear
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║                                                        ║"
    echo "║    🤖 Unified Bot + Shadow Mode Controller 🤖         ║"
    echo "║                                                        ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
}

show_status() {
    echo -e "${BLUE}═══ System Status ═══${NC}"
    
    # Check threaded bot
    if pm2 list 2>/dev/null | grep -q "gridbot-live.*online"; then
        echo -e "Threaded Bot:    ${GREEN}RUNNING${NC} (PM2: gridbot-live)"
    elif ps aux | grep -E "python.*bot/run.py" | grep -v grep > /dev/null; then
        echo -e "Threaded Bot:    ${GREEN}RUNNING${NC} (Direct)"
    else
        echo -e "Threaded Bot:    ${RED}STOPPED${NC}"
    fi
    
    # Check shadow mode
    if [ -f "$SHADOW_PID_FILE" ]; then
        SHADOW_PID=$(cat "$SHADOW_PID_FILE")
        if ps -p "$SHADOW_PID" > /dev/null 2>&1; then
            echo -e "Shadow Mode:     ${GREEN}RUNNING${NC} (PID: $SHADOW_PID)"
        else
            echo -e "Shadow Mode:     ${RED}STOPPED${NC} (stale PID)"
        fi
    else
        echo -e "Shadow Mode:     ${RED}STOPPED${NC}"
    fi
    
    # Check WebUI
    if ps aux | grep -E "python.*webui/backend/app.py" | grep -v grep > /dev/null; then
        echo -e "WebUI Backend:   ${GREEN}RUNNING${NC}"
    else
        echo -e "WebUI Backend:   ${YELLOW}STOPPED${NC}"
    fi
    
    echo ""
}

start_all() {
    show_header
    echo -e "${BLUE}🚀 Starting Unified System...${NC}"
    echo ""
    
    # Clean up stale lock files
    echo "🧹 Cleaning stale locks..."
    rm -f .bot_instance_live.lock
    
    # Step 1: Start threaded bot with PM2
    echo ""
    echo "📌 Step 1: Starting threaded bot with PM2..."
    if pm2 list 2>/dev/null | grep -q "gridbot-live.*online"; then
        echo -e "${YELLOW}⚠️  Threaded bot already running${NC}"
    else
        pm2 start ecosystem.config.js --only gridbot-live
        echo -e "${GREEN}✅ Threaded bot started${NC}"
    fi
    
    # Wait for bot to initialize
    echo ""
    echo "⏳ Waiting 10 seconds for bot initialization..."
    sleep 10
    
    # Step 2: Start shadow mode in background
    echo ""
    echo "📌 Step 2: Starting shadow mode..."
    mkdir -p .pids logs
    
    # Run shadow mode in background and capture PID
    nohup python3 scripts/migrate_to_async.py --mode shadow --duration 24 \
        > logs/shadow_mode.log 2>&1 &
    SHADOW_PID=$!
    echo $SHADOW_PID > "$SHADOW_PID_FILE"
    echo -e "${GREEN}✅ Shadow mode started (PID: $SHADOW_PID)${NC}"
    
    # Step 3: Show status
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║              ✅ UNIFIED SYSTEM STARTED ✅              ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    show_status
    
    echo -e "${BLUE}📊 Monitoring:${NC}"
    echo "  • Shadow mode logs: tail -f logs/shadow_mode.log"
    echo "  • Dashboard:        ./scripts/shadow_mode_dashboard.sh"
    echo "  • PM2 status:       pm2 list"
    echo "  • PM2 logs:         pm2 logs gridbot-live"
    echo ""
    echo -e "${YELLOW}💡 Control configuration via WebUI:${NC} http://localhost:5555"
    echo -e "${YELLOW}💡 Stop system:${NC} ./scripts/unified_bot_control.sh stop"
    echo ""
}

stop_all() {
    show_header
    echo -e "${BLUE}🛑 Stopping Unified System...${NC}"
    echo ""
    
    # Step 1: Stop shadow mode
    echo "📌 Step 1: Stopping shadow mode..."
    if [ -f "$SHADOW_PID_FILE" ]; then
        SHADOW_PID=$(cat "$SHADOW_PID_FILE")
        if ps -p "$SHADOW_PID" > /dev/null 2>&1; then
            kill $SHADOW_PID
            echo -e "${GREEN}✅ Shadow mode stopped (PID: $SHADOW_PID)${NC}"
        else
            echo -e "${YELLOW}⚠️  Shadow mode not running${NC}"
        fi
        rm -f "$SHADOW_PID_FILE"
    else
        echo -e "${YELLOW}⚠️  No shadow mode PID file found${NC}"
    fi
    
    # Step 2: Stop threaded bot
    echo ""
    echo "📌 Step 2: Stopping threaded bot..."
    if pm2 list 2>/dev/null | grep -q "gridbot-live.*online"; then
        pm2 stop gridbot-live
        echo -e "${GREEN}✅ Threaded bot stopped${NC}"
    else
        echo -e "${YELLOW}⚠️  Threaded bot not running via PM2${NC}"
    fi
    
    # Clean up
    echo ""
    echo "🧹 Cleaning up..."
    rm -f .bot_instance_live.lock
    
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║              ✅ UNIFIED SYSTEM STOPPED ✅              ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    show_status
}

restart_all() {
    echo -e "${BLUE}🔄 Restarting Unified System...${NC}"
    echo ""
    stop_all
    sleep 3
    start_all
}

show_logs() {
    show_header
    echo -e "${BLUE}📋 Available Logs:${NC}"
    echo ""
    echo "1) Shadow mode logs (live)"
    echo "2) Threaded bot logs (PM2)"
    echo "3) Shadow mode report"
    echo "4) Back to menu"
    echo ""
    read -p "Select option (1-4): " choice
    
    case $choice in
        1)
            echo ""
            echo -e "${BLUE}📊 Shadow Mode Logs (Ctrl+C to exit):${NC}"
            tail -f logs/shadow_mode.log
            ;;
        2)
            echo ""
            echo -e "${BLUE}📊 Threaded Bot Logs (Ctrl+C to exit):${NC}"
            pm2 logs gridbot-live
            ;;
        3)
            echo ""
            if [ -f "logs/shadow_mode_report.json" ]; then
                echo -e "${BLUE}📊 Shadow Mode Report:${NC}"
                cat logs/shadow_mode_report.json | jq '.' 2>/dev/null || cat logs/shadow_mode_report.json
            else
                echo -e "${YELLOW}⚠️  No report file found yet${NC}"
            fi
            echo ""
            read -p "Press Enter to continue..."
            ;;
        4)
            return
            ;;
    esac
}

show_dashboard() {
    ./scripts/shadow_mode_dashboard.sh
}

# Main menu
main_menu() {
    while true; do
        show_header
        show_status
        
        echo -e "${BLUE}═══ Actions ═══${NC}"
        echo "1) 🚀 Start Both (Threaded + Shadow)"
        echo "2) 🛑 Stop Both"
        echo "3) 🔄 Restart Both"
        echo "4) 📊 View Logs"
        echo "5) 📈 Shadow Mode Dashboard"
        echo "6) 🔍 Status Only"
        echo "7) ❌ Exit"
        echo ""
        read -p "Select option (1-7): " choice
        
        case $choice in
            1)
                start_all
                read -p "Press Enter to continue..."
                ;;
            2)
                stop_all
                read -p "Press Enter to continue..."
                ;;
            3)
                restart_all
                read -p "Press Enter to continue..."
                ;;
            4)
                show_logs
                ;;
            5)
                show_dashboard
                ;;
            6)
                # Just refresh
                ;;
            7)
                echo ""
                echo "👋 Goodbye!"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option${NC}"
                sleep 1
                ;;
        esac
    done
}

# Parse command line arguments
case "${1:-menu}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    status)
        show_header
        show_status
        ;;
    logs)
        show_logs
        ;;
    dashboard)
        show_dashboard
        ;;
    menu)
        main_menu
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|dashboard|menu}"
        echo ""
        echo "Commands:"
        echo "  start      - Start both threaded bot and shadow mode"
        echo "  stop       - Stop both systems"
        echo "  restart    - Restart both systems"
        echo "  status     - Show current status"
        echo "  logs       - View logs"
        echo "  dashboard  - Open shadow mode dashboard"
        echo "  menu       - Interactive menu (default)"
        exit 1
        ;;
esac
