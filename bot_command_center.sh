#!/bin/bash
# GridBot Command Center - All Essential Commands in One Place
# 
# This is your one-stop command hub for managing the entire trading system

set -e

PROJECT_ROOT="/Users/ssr/Projects/WorkingBot"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

show_header() {
    clear
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                                  ║${NC}"
    echo -e "${CYAN}║               ${MAGENTA}🤖 GridBot Command Center 🤖${CYAN}                     ║${NC}"
    echo -e "${CYAN}║                                                                  ║${NC}"
    echo -e "${CYAN}║              ${GREEN}Your Complete Bot Management Hub${CYAN}                  ║${NC}"
    echo -e "${CYAN}║                                                                  ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

show_menu() {
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  📊 BOT MANAGEMENT${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo "  1)  🚀 Start Bot (Live)"
    echo "  2)  🛑 Stop Bot (Live)"
    echo "  3)  🔄 Restart Bot (Live)"
    echo "  4)  📊 Bot Status"
    echo "  5)  📝 Watch Live Logs"
    echo "  6)  🔍 Check Bot Health"
    echo ""
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  🌐 BACKEND/FRONTEND${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo "  7)  🔄 Restart Backend (WebUI)"
    echo "  8)  🌐 Check Backend Status"
    echo "  9)  🔗 Sync Backend/Frontend"
    echo "  10) 🚀 Start Development Mode"
    echo "  11) 🏭 Build Production Frontend"
    echo ""
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  📊 MONITORING & LOGS${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo "  12) 👁️  Watch All Bots (Multi-pane)"
    echo "  13) 📝 View Bot Logs (Last 100 lines)"
    echo "  14) ⚠️  View Errors Only"
    echo "  15) 💊 View Health Checks"
    echo "  16) 🛡️  View Guardian Logs"
    echo ""
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  🔧 MAINTENANCE & FIXES${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo "  17) 🔧 Fix Bot Instance Lock"
    echo "  18) 🧹 Clean Stale Locks"
    echo "  19) 📱 Disable Telegram Alerts"
    echo "  20) 💾 Save PM2 State"
    echo "  21) 🔄 Reset PM2 Restart Counter"
    echo ""
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  📈 TRADING STATUS${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo "  22) 💰 Check Positions"
    echo "  23) 📊 View Pending Orders"
    echo "  24) 🎯 Grid Status"
    echo "  25) 📈 Account Balance"
    echo ""
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  🚨 EMERGENCY${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo "  26) 🚨 Emergency Stop All"
    echo "  27) 🔥 Kill All Bot Processes"
    echo "  28) 🆘 Full System Restart"
    echo ""
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo "  0)  🚪 Exit"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Function implementations
start_bot() {
    echo -e "${GREEN}🚀 Starting Live Trading Bot...${NC}"
    ./pm2_gridbot.sh start live
    echo ""
    pm2 status | grep gridbot-live
}

stop_bot() {
    echo -e "${YELLOW}🛑 Stopping Live Trading Bot (graceful, 30s timeout)...${NC}"
    ./pm2_gridbot.sh stop live
}

restart_bot() {
    echo -e "${CYAN}🔄 Restarting Live Trading Bot...${NC}"
    ./pm2_gridbot.sh restart live
    sleep 2
    pm2 logs gridbot-live --lines 20 --nostream
}

bot_status() {
    echo -e "${BLUE}📊 Bot Status:${NC}"
    echo ""
    pm2 status
    echo ""
    echo -e "${BLUE}Process Details:${NC}"
    pm2 describe gridbot-live | head -30
}

watch_logs() {
    echo -e "${GREEN}📝 Watching Live Logs (Ctrl+C to exit)${NC}"
    echo ""
    pm2 logs gridbot-live
}

check_health() {
    echo -e "${GREEN}🔍 Checking Bot Health...${NC}"
    echo ""
    
    # Check PM2 status
    echo -e "${YELLOW}PM2 Status:${NC}"
    pm2 list | grep gridbot-live || echo "Not running in PM2"
    echo ""
    
    # Check lock files
    echo -e "${YELLOW}Lock Files:${NC}"
    if [ -f ".bot_instance_live.lock" ]; then
        PID=$(head -1 .bot_instance_live.lock)
        echo "  Lock exists: PID $PID"
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "  ${GREEN}✅ Process running${NC}"
        else
            echo -e "  ${RED}⚠️  Stale lock (process not running)${NC}"
        fi
    else
        echo "  No lock file"
    fi
    echo ""
    
    # Check recent logs
    echo -e "${YELLOW}Recent Activity:${NC}"
    pm2 logs gridbot-live --lines 5 --nostream
}

restart_backend() {
    echo -e "${CYAN}🔄 Restarting Backend (WebUI)...${NC}"
    launchctl stop com.gridbot.webui
    sleep 2
    launchctl start com.gridbot.webui
    sleep 2
    
    echo ""
    echo -e "${GREEN}Testing backend...${NC}"
    curl -s http://localhost:5555/api/health | python3 -m json.tool 2>/dev/null || echo "Backend starting..."
}

check_backend() {
    echo -e "${BLUE}🌐 Backend Status:${NC}"
    echo ""
    
    echo -e "${YELLOW}LaunchAgent:${NC}"
    launchctl list | grep gridbot.webui
    echo ""
    
    echo -e "${YELLOW}Port 5555:${NC}"
    lsof -i :5555 | head -5 || echo "Nothing on port 5555"
    echo ""
    
    echo -e "${YELLOW}Health Check:${NC}"
    curl -s http://localhost:5555/api/health || echo "Backend not responding"
}

sync_backend_frontend() {
    ./sync_backend_frontend.sh
}

watch_all_bots() {
    echo -e "${GREEN}👁️  Opening Multi-Pane View (tmux)${NC}"
    echo -e "${YELLOW}Press Ctrl+B then D to detach${NC}"
    sleep 2
    ./watch_bot_logs.sh all
}

view_bot_logs() {
    echo -e "${BLUE}📝 Last 100 Lines:${NC}"
    echo ""
    pm2 logs gridbot-live --lines 100 --nostream
}

view_errors() {
    echo -e "${RED}⚠️  Errors Only:${NC}"
    echo ""
    tail -200 bot/logs/bot.log | grep -E "ERROR|CRITICAL|Exception" | tail -50
}

view_health_checks() {
    echo -e "${GREEN}💊 Health Checks (Phase 2 & 3):${NC}"
    echo ""
    pm2 logs gridbot-live --lines 200 --nostream | grep -E "Memory check|Health check|Circuit breaker|Watchdog" | tail -30
}

view_guardian() {
    echo -e "${BLUE}🛡️  Guardian Logs:${NC}"
    echo ""
    pm2 logs guardian-live --lines 50 --nostream 2>/dev/null || echo "Guardian not running"
}

fix_instance_lock() {
    ./fix_bot_instance_lock.sh
}

clean_locks() {
    echo -e "${YELLOW}🧹 Cleaning Stale Locks...${NC}"
    find . -maxdepth 2 -name ".bot_instance*.lock" -exec rm -v {} \;
    echo -e "${GREEN}✅ Done${NC}"
}

disable_telegram() {
    ./disable_telegram_alerts.sh
}

save_pm2() {
    echo -e "${GREEN}💾 Saving PM2 State...${NC}"
    pm2 save
    echo -e "${GREEN}✅ State saved${NC}"
}

reset_pm2_counter() {
    echo -e "${YELLOW}🔄 Resetting PM2 Restart Counter...${NC}"
    pm2 reset gridbot-live
    echo -e "${GREEN}✅ Counter reset${NC}"
}

check_positions() {
    echo -e "${BLUE}💰 Checking Positions...${NC}"
    echo ""
    python3 -c "
from bot.strategy.gridbot import GridBot
import json

bot = GridBot(trading_mode='live')
positions = bot.position_mgr.get_positions()
print(json.dumps(positions, indent=2))
" 2>/dev/null || echo "Could not fetch positions"
}

emergency_stop() {
    echo -e "${RED}🚨 EMERGENCY STOP ALL${NC}"
    read -p "Are you sure? [y/N]: " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pm2 stop all
        launchctl stop com.gridbot.webui
        echo -e "${GREEN}✅ All services stopped${NC}"
    fi
}

kill_all_bots() {
    echo -e "${RED}🔥 KILL ALL BOT PROCESSES${NC}"
    read -p "Are you ABSOLUTELY sure? [y/N]: " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -9 -f "bot.run" || true
        pkill -9 -f "bot_launcher" || true
        pm2 stop all || true
        echo -e "${GREEN}✅ All bot processes killed${NC}"
    fi
}

full_restart() {
    echo -e "${CYAN}🆘 FULL SYSTEM RESTART${NC}"
    read -p "This will restart everything. Continue? [y/N]: " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping all services..."
        pm2 stop all || true
        launchctl stop com.gridbot.webui || true
        sleep 2
        
        echo "Cleaning locks..."
        rm -f .bot_instance*.lock
        
        echo "Starting services..."
        launchctl start com.gridbot.webui
        sleep 2
        ./pm2_gridbot.sh start live
        
        echo -e "${GREEN}✅ System restarted${NC}"
    fi
}

# Main loop
while true; do
    show_header
    show_menu
    
    read -p "Enter choice [0-28]: " choice
    echo ""
    
    case $choice in
        1) start_bot ;;
        2) stop_bot ;;
        3) restart_bot ;;
        4) bot_status ;;
        5) watch_logs ;;
        6) check_health ;;
        7) restart_backend ;;
        8) check_backend ;;
        9) sync_backend_frontend ;;
        10) echo "1" | ./sync_backend_frontend.sh ;;
        11) echo "5" | ./sync_backend_frontend.sh ;;
        12) watch_all_bots ;;
        13) view_bot_logs ;;
        14) view_errors ;;
        15) view_health_checks ;;
        16) view_guardian ;;
        17) fix_instance_lock ;;
        18) clean_locks ;;
        19) disable_telegram ;;
        20) save_pm2 ;;
        21) reset_pm2_counter ;;
        22) check_positions ;;
        23) echo "Coming soon: View Pending Orders" ;;
        24) echo "Coming soon: Grid Status" ;;
        25) echo "Coming soon: Account Balance" ;;
        26) emergency_stop ;;
        27) kill_all_bots ;;
        28) full_restart ;;
        0) echo -e "${GREEN}👋 Goodbye!${NC}"; exit 0 ;;
        *) echo -e "${RED}Invalid choice${NC}" ;;
    esac
    
    echo ""
    read -p "Press Enter to continue..."
done
