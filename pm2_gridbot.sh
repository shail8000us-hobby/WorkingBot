#!/bin/bash
# ============================================================================
# PM2 GridBot Manager - Production Process Management
# ============================================================================
#
# This script provides easy commands to manage GridBot with PM2
#
# Usage:
#   ./pm2_gridbot.sh start live    # Start live bot
#   ./pm2_gridbot.sh start demo    # Start demo bot
#   ./pm2_gridbot.sh start guardian-live    # Start guardian for live
#   ./pm2_gridbot.sh start guardian-demo    # Start guardian for demo
#   ./pm2_gridbot.sh start heartbeat        # Start heartbeat monitor
#   ./pm2_gridbot.sh start all              # Start all components
#   ./pm2_gridbot.sh stop live     # Stop live bot (graceful, 30s timeout)
#   ./pm2_gridbot.sh restart live  # Restart live bot
#   ./pm2_gridbot.sh logs live     # View live bot logs
#   ./pm2_gridbot.sh status        # Show all bots status
#   ./pm2_gridbot.sh monit         # Real-time monitoring
#
# ============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

CONFIG_FILE="ecosystem.gridbot.config.js"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$SCRIPT_DIR" || exit 1

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo -e "${RED}❌ PM2 is not installed${NC}"
    echo -e "${YELLOW}Install with: sudo npm install -g pm2${NC}"
    exit 1
fi

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Config file not found: $CONFIG_FILE${NC}"
    exit 1
fi

# Function to show usage
show_usage() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           PM2 GridBot Manager - Usage Guide                   ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}Starting:${NC}"
    echo "  ./pm2_gridbot.sh start live            # Start live trading bot"
    echo "  ./pm2_gridbot.sh start demo            # Start demo trading bot"
    echo "  ./pm2_gridbot.sh start guardian-live   # Start guardian (live mode)"
    echo "  ./pm2_gridbot.sh start guardian-demo   # Start guardian (demo mode)"
    echo "  ./pm2_gridbot.sh start heartbeat       # Start heartbeat monitor"
    echo "  ./pm2_gridbot.sh start all             # Start all components"
    echo ""
    echo -e "${GREEN}Stopping (Graceful - 30s timeout):${NC}"
    echo "  ./pm2_gridbot.sh stop live             # Stop live bot (cancels orders)"
    echo "  ./pm2_gridbot.sh stop demo             # Stop demo bot"
    echo "  ./pm2_gridbot.sh stop guardian-live    # Stop guardian"
    echo "  ./pm2_gridbot.sh stop heartbeat        # Stop heartbeat"
    echo "  ./pm2_gridbot.sh stop all              # Stop all bots"
    echo ""
    echo -e "${GREEN}Restarting:${NC}"
    echo "  ./pm2_gridbot.sh restart live          # Restart live bot"
    echo "  ./pm2_gridbot.sh restart demo          # Restart demo bot"
    echo "  ./pm2_gridbot.sh restart all           # Restart all bots"
    echo ""
    echo -e "${GREEN}Monitoring:${NC}"
    echo "  ./pm2_gridbot.sh status         # Show bot status"
    echo "  ./pm2_gridbot.sh logs live      # View live bot logs (Ctrl+C to exit)"
    echo "  ./pm2_gridbot.sh logs demo      # View demo bot logs"
    echo "  ./pm2_gridbot.sh monit          # Real-time monitoring dashboard"
    echo ""
    echo -e "${GREEN}Advanced:${NC}"
    echo "  ./pm2_gridbot.sh reload live    # Zero-downtime reload"
    echo "  ./pm2_gridbot.sh flush          # Clear all log files"
    echo "  ./pm2_gridbot.sh describe live  # Detailed bot information"
    echo "  ./pm2_gridbot.sh startup        # Enable auto-start on boot"
    echo "  ./pm2_gridbot.sh save           # Save current PM2 process list"
    echo ""
    echo -e "${GREEN}Maintenance:${NC}"
    echo "  ./pm2_gridbot.sh update         # Update PM2"
    echo "  ./pm2_gridbot.sh install-rotate # Install log rotation"
    echo ""
}

# Function to get bot name
get_bot_name() {
    local mode=$1
    case "$mode" in
        live) echo "gridbot-live" ;;
        demo) echo "gridbot-demo" ;;
        guardian-live) echo "guardian-live" ;;
        guardian-demo) echo "guardian-demo" ;;
        heartbeat) echo "heartbeat" ;;
        all) echo "all" ;;
        *) echo "" ;;
    esac
}

# Main command handler
COMMAND=${1:-help}
MODE=${2:-}

case $COMMAND in
    start)
        if [ -z "$MODE" ]; then
            echo -e "${RED}❌ Please specify what to start${NC}"
            echo -e "${YELLOW}Options: live, demo, guardian-live, guardian-demo, heartbeat, all${NC}"
            exit 1
        fi
        
        if [ "$MODE" == "all" ]; then
            echo -e "${BLUE}🚀 Starting all components...${NC}"
            pm2 start "$CONFIG_FILE"
            pm2 save --force
            echo ""
            echo -e "${GREEN}✅ All components started${NC}"
            echo -e "${CYAN}View status: ./pm2_gridbot.sh status${NC}"
        else
            BOT_NAME=$(get_bot_name "$MODE")
            if [ -z "$BOT_NAME" ]; then
                echo -e "${RED}❌ Invalid mode: $MODE${NC}"
                echo -e "${YELLOW}Options: live, demo, guardian-live, guardian-demo, heartbeat, all${NC}"
                exit 1
            fi
            
            echo -e "${BLUE}🚀 Starting $BOT_NAME...${NC}"
            pm2 start "$CONFIG_FILE" --only "$BOT_NAME"
            pm2 save --force
            echo ""
            echo -e "${GREEN}✅ $BOT_NAME started${NC}"
            echo -e "${CYAN}View logs: ./pm2_gridbot.sh logs $MODE${NC}"
            echo -e "${CYAN}View status: ./pm2_gridbot.sh status${NC}"
        fi
        ;;
    
    stop)
        if [ "$MODE" == "all" ]; then
            echo -e "${YELLOW}🛑 Stopping all bots (graceful shutdown, 30s timeout)...${NC}"
            pm2 stop all
            echo -e "${GREEN}✅ All bots stopped${NC}"
        else
            BOT_NAME=$(get_bot_name "$MODE")
            if [ -z "$BOT_NAME" ]; then
                echo -e "${RED}❌ Invalid mode: $MODE (use 'live', 'demo', or 'all')${NC}"
                exit 1
            fi
            
            echo -e "${YELLOW}🛑 Stopping $BOT_NAME (graceful shutdown, 30s timeout)...${NC}"
            pm2 stop "$BOT_NAME"
            
            # Wait a moment and check if cleanup ran
            sleep 2
            echo ""
            echo -e "${CYAN}🔍 Checking cleanup status...${NC}"
            if tail -50 reports/bot.log 2>/dev/null | grep -q "GRACEFUL SHUTDOWN"; then
                echo -e "${GREEN}✅ Graceful shutdown confirmed - orders cancelled${NC}"
            else
                echo -e "${YELLOW}⚠️  Note: Check reports/bot.log for cleanup confirmation${NC}"
            fi
        fi
        pm2 save --force
        ;;
    
    restart)
        if [ "$MODE" == "all" ]; then
            echo -e "${BLUE}🔄 Restarting all bots...${NC}"
            pm2 restart all
        else
            BOT_NAME=$(get_bot_name "$MODE")
            if [ -z "$BOT_NAME" ]; then
                echo -e "${RED}❌ Invalid mode: $MODE (use 'live', 'demo', or 'all')${NC}"
                exit 1
            fi
            
            echo -e "${BLUE}🔄 Restarting $BOT_NAME...${NC}"
            pm2 restart "$BOT_NAME"
        fi
        pm2 save --force
        echo -e "${GREEN}✅ Restart complete${NC}"
        ;;
    
    reload)
        BOT_NAME=$(get_bot_name "$MODE")
        if [ -z "$BOT_NAME" ]; then
            echo -e "${RED}❌ Invalid mode: $MODE (use 'live' or 'demo')${NC}"
            exit 1
        fi
        
        echo -e "${BLUE}🔄 Reloading $BOT_NAME (zero-downtime)...${NC}"
        pm2 reload "$BOT_NAME"
        pm2 save --force
        echo -e "${GREEN}✅ Reload complete${NC}"
        ;;
    
    logs)
        if [ -z "$MODE" ]; then
            echo -e "${CYAN}📋 Showing all logs (Ctrl+C to exit)...${NC}"
            pm2 logs
        else
            BOT_NAME=$(get_bot_name "$MODE")
            if [ -z "$BOT_NAME" ]; then
                echo -e "${RED}❌ Invalid mode: $MODE (use 'live' or 'demo')${NC}"
                exit 1
            fi
            
            echo -e "${CYAN}📋 Showing $BOT_NAME logs (Ctrl+C to exit)...${NC}"
            pm2 logs "$BOT_NAME" --nostream --lines 50
            echo ""
            echo -e "${CYAN}Following logs (Ctrl+C to exit)...${NC}"
            pm2 logs "$BOT_NAME"
        fi
        ;;
    
    status)
        echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║                    GridBot Status                              ║${NC}"
        echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
        pm2 list
        echo ""
        echo -e "${CYAN}💡 Tip: Use './pm2_gridbot.sh monit' for real-time monitoring${NC}"
        ;;
    
    monit)
        echo -e "${CYAN}📊 Opening real-time monitoring dashboard...${NC}"
        echo -e "${CYAN}Press Ctrl+C to exit${NC}"
        sleep 1
        pm2 monit
        ;;
    
    describe)
        BOT_NAME=$(get_bot_name "$MODE")
        if [ -z "$BOT_NAME" ]; then
            echo -e "${RED}❌ Invalid mode: $MODE (use 'live' or 'demo')${NC}"
            exit 1
        fi
        
        echo -e "${CYAN}ℹ️  Detailed information for $BOT_NAME:${NC}"
        pm2 describe "$BOT_NAME"
        ;;
    
    flush)
        echo -e "${YELLOW}🗑️  Flushing all PM2 logs...${NC}"
        pm2 flush
        echo -e "${GREEN}✅ Logs cleared${NC}"
        ;;
    
    save)
        echo -e "${BLUE}💾 Saving PM2 process list...${NC}"
        pm2 save --force
        echo -e "${GREEN}✅ Process list saved${NC}"
        ;;
    
    startup)
        echo -e "${BLUE}🔧 Configuring auto-start on boot...${NC}"
        echo ""
        pm2 startup
        echo ""
        echo -e "${YELLOW}⚠️  Copy and run the command above (with sudo)${NC}"
        echo -e "${YELLOW}⚠️  Then run: ./pm2_gridbot.sh save${NC}"
        ;;
    
    update)
        echo -e "${BLUE}⬆️  Updating PM2...${NC}"
        sudo npm install -g pm2@latest
        pm2 update
        echo -e "${GREEN}✅ PM2 updated${NC}"
        ;;
    
    install-rotate)
        echo -e "${BLUE}📦 Installing pm2-logrotate module...${NC}"
        pm2 install pm2-logrotate
        
        echo -e "${BLUE}🔧 Configuring log rotation...${NC}"
        pm2 set pm2-logrotate:max_size 10M
        pm2 set pm2-logrotate:retain 30
        pm2 set pm2-logrotate:compress true
        pm2 set pm2-logrotate:rotateInterval '0 0 * * *'  # Daily at midnight
        
        echo -e "${GREEN}✅ Log rotation configured:${NC}"
        echo "   - Max file size: 10MB"
        echo "   - Retention: 30 files"
        echo "   - Compression: Enabled"
        echo "   - Rotation: Daily at midnight"
        ;;
    
    help|--help|-h)
        show_usage
        ;;
    
    *)
        echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
        echo ""
        show_usage
        exit 1
        ;;
esac
