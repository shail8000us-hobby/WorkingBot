#!/bin/bash
# ============================================================================
# PM2 Trading Bot Manager - Production Process Management
# ============================================================================
#
# Manage all trading bots with clear separation by instrument and direction
#
# Usage:
#   ./pm2_manager.sh start btc-long       # Start BTC LONG bot
#   ./pm2_manager.sh start btc-short      # Start BTC SHORT bot
#   ./pm2_manager.sh start eth-long       # Start ETH LONG bot
#   ./pm2_manager.sh start eth-short      # Start ETH SHORT bot
#   ./pm2_manager.sh start guardian       # Start guardian bot (auto-restart)
#   ./pm2_manager.sh start webui          # Start WebUI backend
#   ./pm2_manager.sh start all-bots       # Start all trading bots
#   ./pm2_manager.sh start all            # Start everything
#   ./pm2_manager.sh stop <name>          # Stop specific bot
#   ./pm2_manager.sh restart <name>       # Restart specific bot
#   ./pm2_manager.sh status               # Show all processes
#   ./pm2_manager.sh logs <name>          # View logs
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

CONFIG_FILE="ecosystem.production.config.js"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$SCRIPT_DIR" || exit 1

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo -e "${RED}❌ PM2 is not installed${NC}"
    echo -e "${YELLOW}Install with: npm install -g pm2${NC}"
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
    echo -e "${CYAN}║        PM2 Trading Bot Manager - Multi-Instrument              ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}Starting Individual Bots:${NC}"
    echo "  ./pm2_manager.sh start btc-long     # BTC LONG position"
    echo "  ./pm2_manager.sh start btc-short    # BTC SHORT position"
    echo "  ./pm2_manager.sh start eth-long     # ETH LONG position"
    echo "  ./pm2_manager.sh start eth-short    # ETH SHORT position"
    echo "  ./pm2_manager.sh start guardian     # Guardian monitoring (auto-restart)"
    echo "  ./pm2_manager.sh start webui        # WebUI backend server"
    echo ""
    echo -e "${GREEN}Starting Multiple:${NC}"
    echo "  ./pm2_manager.sh start all-bots     # All 4 trading bots"
    echo "  ./pm2_manager.sh start all          # Everything (bots + guardian + webui)"
    echo ""
    echo -e "${GREEN}Stopping:${NC}"
    echo "  ./pm2_manager.sh stop btc-long      # Stop specific bot"
    echo "  ./pm2_manager.sh stop all-bots      # Stop all trading bots"
    echo "  ./pm2_manager.sh stop all           # Stop everything"
    echo ""
    echo -e "${GREEN}Restarting:${NC}"
    echo "  ./pm2_manager.sh restart btc-long   # Restart specific bot"
    echo "  ./pm2_manager.sh restart all-bots   # Restart all trading bots"
    echo ""
    echo -e "${GREEN}Monitoring:${NC}"
    echo "  ./pm2_manager.sh status             # Show all processes"
    echo "  ./pm2_manager.sh logs btc-long      # View logs (Ctrl+C to exit)"
    echo "  ./pm2_manager.sh monit              # Real-time monitoring dashboard"
    echo ""
    echo -e "${GREEN}Process Names:${NC}"
    echo "  - gridbot-BTCUSD-LONG"
    echo "  - gridbot-BTCUSD-SHORT"
    echo "  - gridbot-ETHUSD-LONG"
    echo "  - gridbot-ETHUSD-SHORT"
    echo "  - guardian-live"
    echo "  - webui-backend"
    echo ""
}

# Function to get PM2 process name
get_process_name() {
    local name=$1
    case "$name" in
        btc-long) echo "gridbot-BTCUSD-LONG" ;;
        btc-short) echo "gridbot-BTCUSD-SHORT" ;;
        eth-long) echo "gridbot-ETHUSD-LONG" ;;
        eth-short) echo "gridbot-ETHUSD-SHORT" ;;
        guardian) echo "guardian-live" ;;
        webui) echo "webui-backend" ;;
        all-bots) echo "all-bots" ;;
        all) echo "all" ;;
        *) echo "" ;;
    esac
}

# Main command handler
COMMAND=${1:-help}
TARGET=${2:-}

case $COMMAND in
    start)
        if [ -z "$TARGET" ]; then
            echo -e "${RED}❌ Please specify what to start${NC}"
            echo -e "${YELLOW}Options: btc-long, btc-short, eth-long, eth-short, guardian, webui, all-bots, all${NC}"
            exit 1
        fi
        
        if [ "$TARGET" == "all" ]; then
            echo -e "${BLUE}🚀 Starting all components...${NC}"
            pm2 start "$CONFIG_FILE"
            pm2 save --force
            echo ""
            echo -e "${GREEN}✅ All components started${NC}"
            pm2 status
        elif [ "$TARGET" == "all-bots" ]; then
            echo -e "${BLUE}🚀 Starting all trading bots...${NC}"
            pm2 start "$CONFIG_FILE" --only gridbot-btc-long
            pm2 start "$CONFIG_FILE" --only gridbot-btc-short
            pm2 start "$CONFIG_FILE" --only gridbot-eth-long
            pm2 start "$CONFIG_FILE" --only gridbot-eth-short
            pm2 save --force
            echo ""
            echo -e "${GREEN}✅ All trading bots started${NC}"
            pm2 status | grep gridbot
        else
            PROCESS_NAME=$(get_process_name "$TARGET")
            if [ -z "$PROCESS_NAME" ]; then
                echo -e "${RED}❌ Invalid target: $TARGET${NC}"
                echo -e "${YELLOW}Options: btc-long, btc-short, eth-long, eth-short, guardian, webui, all-bots, all${NC}"
                exit 1
            fi
            
            echo -e "${BLUE}🚀 Starting $PROCESS_NAME...${NC}"
            pm2 start "$CONFIG_FILE" --only "$PROCESS_NAME"
            pm2 save --force
            echo ""
            echo -e "${GREEN}✅ $PROCESS_NAME started${NC}"
            pm2 describe "$PROCESS_NAME" | head -20
        fi
        ;;
    
    stop)
        if [ "$TARGET" == "all" ]; then
            echo -e "${YELLOW}🛑 Stopping all processes...${NC}"
            pm2 stop all
            echo -e "${GREEN}✅ All processes stopped${NC}"
        elif [ "$TARGET" == "all-bots" ]; then
            echo -e "${YELLOW}🛑 Stopping all trading bots...${NC}"
            pm2 stop gridbot-btc-long gridbot-btc-short gridbot-eth-long gridbot-eth-short
            echo -e "${GREEN}✅ All trading bots stopped${NC}"
        else
            PROCESS_NAME=$(get_process_name "$TARGET")
            if [ -z "$PROCESS_NAME" ]; then
                echo -e "${RED}❌ Invalid target: $TARGET${NC}"
                exit 1
            fi
            
            echo -e "${YELLOW}🛑 Stopping $PROCESS_NAME...${NC}"
            pm2 stop "$PROCESS_NAME"
            echo -e "${GREEN}✅ $PROCESS_NAME stopped${NC}"
        fi
        ;;
    
    restart)
        if [ "$TARGET" == "all" ]; then
            echo -e "${BLUE}🔄 Restarting all processes...${NC}"
            pm2 restart all
            echo -e "${GREEN}✅ All processes restarted${NC}"
        elif [ "$TARGET" == "all-bots" ]; then
            echo -e "${BLUE}🔄 Restarting all trading bots...${NC}"
            pm2 restart gridbot-btc-long gridbot-btc-short gridbot-eth-long gridbot-eth-short
            echo -e "${GREEN}✅ All trading bots restarted${NC}"
        else
            PROCESS_NAME=$(get_process_name "$TARGET")
            if [ -z "$PROCESS_NAME" ]; then
                echo -e "${RED}❌ Invalid target: $TARGET${NC}"
                exit 1
            fi
            
            echo -e "${BLUE}🔄 Restarting $PROCESS_NAME...${NC}"
            pm2 restart "$PROCESS_NAME"
            echo -e "${GREEN}✅ $PROCESS_NAME restarted${NC}"
        fi
        ;;
    
    status)
        echo -e "${CYAN}📊 PM2 Process Status${NC}"
        echo ""
        pm2 status
        ;;
    
    logs)
        if [ -z "$TARGET" ]; then
            echo -e "${CYAN}📝 All logs (Ctrl+C to exit)${NC}"
            pm2 logs
        else
            PROCESS_NAME=$(get_process_name "$TARGET")
            if [ -z "$PROCESS_NAME" ]; then
                echo -e "${RED}❌ Invalid target: $TARGET${NC}"
                exit 1
            fi
            
            echo -e "${CYAN}📝 Logs for $PROCESS_NAME (Ctrl+C to exit)${NC}"
            pm2 logs "$PROCESS_NAME"
        fi
        ;;
    
    monit)
        echo -e "${CYAN}📊 Opening PM2 monitoring dashboard...${NC}"
        pm2 monit
        ;;
    
    save)
        echo -e "${GREEN}💾 Saving PM2 process list...${NC}"
        pm2 save --force
        echo -e "${GREEN}✅ PM2 process list saved${NC}"
        ;;
    
    delete)
        if [ -z "$TARGET" ]; then
            echo -e "${RED}❌ Please specify what to delete${NC}"
            exit 1
        fi
        
        if [ "$TARGET" == "all" ]; then
            echo -e "${RED}🗑️  Deleting all PM2 processes...${NC}"
            pm2 delete all
            pm2 save --force
            echo -e "${GREEN}✅ All processes deleted${NC}"
        else
            PROCESS_NAME=$(get_process_name "$TARGET")
            if [ -z "$PROCESS_NAME" ]; then
                echo -e "${RED}❌ Invalid target: $TARGET${NC}"
                exit 1
            fi
            
            echo -e "${RED}🗑️  Deleting $PROCESS_NAME...${NC}"
            pm2 delete "$PROCESS_NAME"
            pm2 save --force
            echo -e "${GREEN}✅ $PROCESS_NAME deleted${NC}"
        fi
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
