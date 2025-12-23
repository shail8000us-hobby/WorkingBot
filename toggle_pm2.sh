#!/bin/bash
# ============================================================================
# Enable/Disable PM2 Integration for WebUI
# ============================================================================
#
# This script toggles PM2 integration for the WebUI bot management system.
#
# Usage:
#   ./toggle_pm2.sh enable   # Enable PM2 integration
#   ./toggle_pm2.sh disable  # Disable PM2 integration
#   ./toggle_pm2.sh status   # Show current status
#
# ============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

ENV_FILE="grid_config.env"

# Check if env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: $ENV_FILE not found${NC}"
    exit 1
fi

# Function to get current status
get_status() {
    if grep -q "^USE_PM2=true" "$ENV_FILE" 2>/dev/null; then
        echo "enabled"
    elif grep -q "^USE_PM2=false" "$ENV_FILE" 2>/dev/null; then
        echo "disabled"
    else
        echo "not_set"
    fi
}

# Function to show status
show_status() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           PM2 Integration Status                               ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    STATUS=$(get_status)
    
    if [ "$STATUS" == "enabled" ]; then
        echo -e "${GREEN}✅ PM2 Integration: ENABLED${NC}"
        echo ""
        echo "Bot management via WebUI will use PM2:"
        echo "  • Automatic restart on crash"
        echo "  • Graceful shutdown (30s timeout)"
        echo "  • Better log management"
        echo "  • Resource monitoring"
        echo ""
        echo "WebUI routes affected:"
        echo "  • POST /api/bot/start → pm2 start gridbot-live"
        echo "  • POST /api/bot/stop → pm2 stop gridbot-live (graceful)"
        echo "  • POST /api/bot/restart → pm2 restart gridbot-live"
        echo "  • GET /api/bot/status → pm2 jlist (enhanced status)"
        echo ""
        echo "Additional PM2 routes available:"
        echo "  • GET /api/pm2/enabled"
        echo "  • GET /api/pm2/bots"
        echo "  • GET /api/pm2/logs/:mode"
        echo "  • POST /api/pm2/reload/:mode"
        echo "  • POST /api/pm2/save"
        echo "  • POST /api/pm2/flush-logs"
        
    elif [ "$STATUS" == "disabled" ]; then
        echo -e "${YELLOW}⚠️  PM2 Integration: DISABLED${NC}"
        echo ""
        echo "Bot management via WebUI uses direct process control:"
        echo "  • Manual restart required on crash"
        echo "  • Graceful shutdown (30s timeout)"
        echo "  • Basic log management"
        echo "  • Limited monitoring"
        echo ""
        echo "WebUI routes use:"
        echo "  • POST /api/bot/start → bot_launcher.py"
        echo "  • POST /api/bot/stop → SIGTERM (graceful)"
        echo "  • POST /api/bot/restart → stop + start"
        echo "  • GET /api/bot/status → PID file check"
        
    else
        echo -e "${YELLOW}⚠️  PM2 Integration: NOT CONFIGURED${NC}"
        echo ""
        echo "USE_PM2 variable not found in $ENV_FILE"
        echo "Run: ./toggle_pm2.sh enable"
    fi
    
    echo ""
    echo -e "${CYAN}─────────────────────────────────────────────────────────────────${NC}"
    
    # Check if PM2 is installed
    if command -v pm2 &> /dev/null; then
        PM2_VERSION=$(pm2 --version 2>/dev/null | head -1)
        echo -e "${GREEN}✅ PM2 Installed: v${PM2_VERSION}${NC}"
        
        # Check running bots
        BOT_COUNT=$(pm2 jlist 2>/dev/null | python3 -c "import sys, json; print(len([p for p in json.load(sys.stdin) if 'gridbot' in p.get('name', '')]))" 2>/dev/null || echo "0")
        
        if [ "$BOT_COUNT" -gt 0 ]; then
            echo -e "${GREEN}✅ GridBots Running: $BOT_COUNT${NC}"
        else
            echo -e "${YELLOW}ℹ️  No GridBots currently running in PM2${NC}"
        fi
    else
        echo -e "${RED}❌ PM2 Not Installed${NC}"
        echo -e "${YELLOW}   Install: sudo npm install -g pm2${NC}"
    fi
    
    echo -e "${CYAN}─────────────────────────────────────────────────────────────────${NC}"
    echo ""
}

# Function to enable PM2
enable_pm2() {
    echo -e "${BLUE}🔧 Enabling PM2 integration...${NC}"
    
    # Check if PM2 is installed
    if ! command -v pm2 &> /dev/null; then
        echo -e "${RED}❌ Error: PM2 is not installed${NC}"
        echo -e "${YELLOW}Install with: sudo npm install -g pm2${NC}"
        exit 1
    fi
    
    # Update or add USE_PM2 variable
    if grep -q "^USE_PM2=" "$ENV_FILE"; then
        # Update existing
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' 's/^USE_PM2=.*/USE_PM2=true/' "$ENV_FILE"
        else
            # Linux
            sed -i 's/^USE_PM2=.*/USE_PM2=true/' "$ENV_FILE"
        fi
        echo -e "${GREEN}✅ Updated USE_PM2=true in $ENV_FILE${NC}"
    else
        # Add new
        echo "" >> "$ENV_FILE"
        echo "# PM2 Integration" >> "$ENV_FILE"
        echo "USE_PM2=true" >> "$ENV_FILE"
        echo -e "${GREEN}✅ Added USE_PM2=true to $ENV_FILE${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}✅ PM2 integration enabled${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Restart WebUI for changes to take effect${NC}"
    echo ""
    echo "Steps to switch to PM2:"
    echo ""
    echo "1. Stop any running bot (WebUI or command line):"
    echo "   ./bot_stopper.py"
    echo ""
    echo "2. Restart WebUI backend:"
    echo "   cd webui && ./restart.sh"
    echo ""
    echo "3. Start bot via PM2:"
    echo "   ./pm2_gridbot.sh start live"
    echo "   OR use WebUI Start Bot button"
    echo ""
    echo "4. Verify status:"
    echo "   ./pm2_gridbot.sh status"
    echo ""
}

# Function to disable PM2
disable_pm2() {
    echo -e "${BLUE}🔧 Disabling PM2 integration...${NC}"
    
    # Update USE_PM2 variable
    if grep -q "^USE_PM2=" "$ENV_FILE"; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' 's/^USE_PM2=.*/USE_PM2=false/' "$ENV_FILE"
        else
            # Linux
            sed -i 's/^USE_PM2=.*/USE_PM2=false/' "$ENV_FILE"
        fi
        echo -e "${GREEN}✅ Updated USE_PM2=false in $ENV_FILE${NC}"
    else
        # Add new
        echo "" >> "$ENV_FILE"
        echo "# PM2 Integration" >> "$ENV_FILE"
        echo "USE_PM2=false" >> "$ENV_FILE"
        echo -e "${GREEN}✅ Added USE_PM2=false to $ENV_FILE${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}✅ PM2 integration disabled${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Restart WebUI for changes to take effect${NC}"
    echo ""
    echo "Steps to switch to direct mode:"
    echo ""
    echo "1. Stop any PM2-managed bots:"
    echo "   ./pm2_gridbot.sh stop all"
    echo ""
    echo "2. Restart WebUI backend:"
    echo "   cd webui && ./restart.sh"
    echo ""
    echo "3. Start bot directly:"
    echo "   python3 bot_launcher.py --daemon"
    echo "   OR use WebUI Start Bot button"
    echo ""
}

# Main command handler
COMMAND=${1:-status}

case $COMMAND in
    enable)
        enable_pm2
        echo ""
        show_status
        ;;
    
    disable)
        disable_pm2
        echo ""
        show_status
        ;;
    
    status)
        show_status
        ;;
    
    help|--help|-h)
        echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║           PM2 Integration Toggle - Help                       ║${NC}"
        echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo "Usage:"
        echo "  ./toggle_pm2.sh enable    # Enable PM2 integration"
        echo "  ./toggle_pm2.sh disable   # Disable PM2 integration"
        echo "  ./toggle_pm2.sh status    # Show current status"
        echo "  ./toggle_pm2.sh help      # Show this help"
        echo ""
        echo "What it does:"
        echo "  • Sets USE_PM2=true/false in grid_config.env"
        echo "  • WebUI bot management routes use PM2 when enabled"
        echo "  • Falls back to direct process control when disabled"
        echo ""
        echo "Benefits of PM2:"
        echo "  ✅ Auto-restart on crash"
        echo "  ✅ Better log management"
        echo "  ✅ Resource monitoring"
        echo "  ✅ Zero-downtime reload"
        echo "  ✅ Startup on boot"
        echo ""
        ;;
    
    *)
        echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
        echo ""
        echo "Usage:"
        echo "  ./toggle_pm2.sh enable|disable|status|help"
        exit 1
        ;;
esac
