#!/bin/bash
# Live Bot Log Monitor - Watch all bot logs in real-time
# Usage: ./watch_bot_logs.sh [bot_name]
# Without argument: Shows menu

set -e

PROJECT_ROOT="/Users/ssr/Projects/WorkingBot"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

show_help() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  📊 GridBot Live Log Monitor${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}Quick Commands:${NC}"
    echo "  ./watch_bot_logs.sh main       # Main trading bot"
    echo "  ./watch_bot_logs.sh guardian   # Guardian bot"
    echo "  ./watch_bot_logs.sh webui      # WebUI backend"
    echo "  ./watch_bot_logs.sh all        # All bots side-by-side"
    echo "  ./watch_bot_logs.sh errors     # Only errors from all bots"
    echo ""
    echo -e "${YELLOW}Interactive Menu:${NC}"
    echo "  ./watch_bot_logs.sh            # Show this menu"
    echo ""
}

watch_main_bot() {
    echo -e "${GREEN}📊 Watching Main Trading Bot (PM2)${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""
    # Check if bot is running in PM2
    if pm2 list 2>/dev/null | grep -q "gridbot-live"; then
        pm2 logs gridbot-live --raw --lines 100
    elif pm2 list 2>/dev/null | grep -q "gridbot-demo"; then
        pm2 logs gridbot-demo --raw --lines 100
    elif [ -f "bot/logs/bot.log" ]; then
        tail -f bot/logs/bot.log | grep --color=always -E "ERROR|WARNING|CRITICAL|FILL|ORDER|POSITION|$"
    else
        echo -e "${RED}❌ No bot running (PM2 or file)${NC}"
        echo ""
        echo -e "${YELLOW}Start bot with: ./pm2_gridbot.sh start live${NC}"
    fi
}

watch_guardian() {
    echo -e "${GREEN}🛡️  Watching Guardian Bot (PM2)${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""
    # Check if guardian is running in PM2
    if pm2 list 2>/dev/null | grep -q "guardian-live"; then
        pm2 logs guardian-live --raw --lines 100
    elif pm2 list 2>/dev/null | grep -q "guardian-demo"; then
        pm2 logs guardian-demo --raw --lines 100
    elif [ -f "bot/logs/guardian.log" ]; then
        tail -f bot/logs/guardian.log | grep --color=always -E "ERROR|WARNING|CRITICAL|RESTART|RECOVERY|$"
    else
        echo -e "${RED}❌ No guardian running (PM2 or file)${NC}"
        echo ""
        echo -e "${YELLOW}Start guardian with: ./pm2_gridbot.sh start guardian-live${NC}"
    fi
}

watch_webui() {
    echo -e "${GREEN}🌐 Watching WebUI Backend (logs/launchagent_webui.log + launchagent_webui_error.log)${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""
    tail -f logs/launchagent_webui.log logs/launchagent_webui_error.log | grep --color=always -E "ERROR|WARNING|CRITICAL|$"
}

watch_all_bots() {
    echo -e "${GREEN}📊 Watching ALL Bots (Multi-pane View)${NC}"
    echo -e "${YELLOW}This will open tmux with 3 panes. Press Ctrl+B then D to detach${NC}"
    echo ""
    
    # Check if tmux is installed
    if ! command -v tmux &> /dev/null; then
        echo -e "${RED}❌ tmux is not installed. Install with: brew install tmux${NC}"
        exit 1
    fi
    
    # Check if PM2 is available
    if command -v pm2 &> /dev/null; then
        # Create tmux session with PM2 logs
        tmux new-session -d -s botlogs "pm2 logs gridbot-live --raw 2>/dev/null || tail -f bot/logs/bot.log"
        tmux split-window -h -t botlogs "pm2 logs guardian-live --raw 2>/dev/null || tail -f bot/logs/guardian.log"
        tmux split-window -v -t botlogs "tail -f logs/launchagent_webui.log logs/launchagent_webui_error.log"
        tmux select-layout -t botlogs tiled
        tmux attach-session -t botlogs
    else
        # Fallback to file-based logs
        tmux new-session -d -s botlogs "tail -f bot/logs/bot.log"
        tmux split-window -h -t botlogs "tail -f bot/logs/guardian.log"
        tmux split-window -v -t botlogs "tail -f logs/launchagent_webui.log logs/launchagent_webui_error.log"
        tmux select-layout -t botlogs tiled
        tmux attach-session -t botlogs
    fi
}

watch_errors_only() {
    echo -e "${GREEN}🚨 Watching Errors from ALL Bots${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""
    tail -f bot/logs/bot.log bot/logs/guardian.log logs/launchagent_webui.log logs/launchagent_webui_error.log 2>/dev/null | \
        grep --color=always -E "ERROR|CRITICAL|FATAL|Exception|Traceback"
}

watch_live_mode() {
    echo -e "${GREEN}🔴 Watching LIVE Trading (bot_live.log)${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""
    if [ -f "logs/bot_live.log" ]; then
        tail -f logs/bot_live.log | grep --color=always -E "FILL|ORDER|POSITION|ERROR|WARNING|$"
    else
        echo -e "${RED}❌ logs/bot_live.log not found (bot not in live mode?)${NC}"
    fi
}

watch_health_checks() {
    echo -e "${GREEN}💊 Watching Health Checks (Phase 2 & 3 features)${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""
    tail -f bot/logs/bot.log | grep --color=always -E "Memory check|Health check|Circuit breaker|Watchdog|$"
}

# Main menu
if [ $# -eq 0 ]; then
    show_help
    echo -e "${BLUE}Select an option:${NC}"
    echo "  1) Main Trading Bot"
    echo "  2) Guardian Bot"
    echo "  3) WebUI Backend"
    echo "  4) All Bots (tmux multi-pane)"
    echo "  5) Errors Only (all bots)"
    echo "  6) Live Trading Mode"
    echo "  7) Health Checks (Phase 2 & 3)"
    echo "  0) Exit"
    echo ""
    read -p "Enter choice [0-7]: " choice
    
    case $choice in
        1) watch_main_bot ;;
        2) watch_guardian ;;
        3) watch_webui ;;
        4) watch_all_bots ;;
        5) watch_errors_only ;;
        6) watch_live_mode ;;
        7) watch_health_checks ;;
        0) exit 0 ;;
        *) echo -e "${RED}Invalid choice${NC}"; exit 1 ;;
    esac
else
    case "$1" in
        main|trading|bot)
            watch_main_bot
            ;;
        guardian|guard)
            watch_guardian
            ;;
        webui|backend|web)
            watch_webui
            ;;
        all|multi)
            watch_all_bots
            ;;
        errors|error)
            watch_errors_only
            ;;
        live|production)
            watch_live_mode
            ;;
        health|phase2|phase3)
            watch_health_checks
            ;;
        help|-h|--help)
            show_help
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo ""
            show_help
            exit 1
            ;;
    esac
fi
