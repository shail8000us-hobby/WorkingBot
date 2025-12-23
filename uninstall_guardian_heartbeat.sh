#!/bin/bash
# Uninstall Guardian and Heartbeat LaunchAgents

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

LAUNCHAGENTS_DIR="$HOME/Library/LaunchAgents"

echo ""
echo "============================================"
echo "🗑️  Uninstall Guardian & Heartbeat"
echo "============================================"
echo ""

# Function to uninstall a launchagent
uninstall_launchagent() {
    local SERVICE_NAME=$1
    local PLIST_FILE="com.workingbot.${SERVICE_NAME}.plist"
    local DEST_PLIST="$LAUNCHAGENTS_DIR/$PLIST_FILE"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Uninstalling $SERVICE_NAME service..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check if service is loaded
    if launchctl list | grep -q "com.workingbot.${SERVICE_NAME}"; then
        echo "🛑 Unloading service..."
        launchctl unload "$DEST_PLIST" 2>/dev/null || true
        sleep 2
        echo -e "${GREEN}✅ Service unloaded${NC}"
    else
        echo -e "${YELLOW}⚠️  Service was not loaded${NC}"
    fi
    
    # Remove plist file
    if [ -f "$DEST_PLIST" ]; then
        echo "📋 Removing plist file..."
        rm "$DEST_PLIST"
        echo -e "${GREEN}✅ Plist file removed${NC}"
    else
        echo -e "${YELLOW}⚠️  Plist file not found${NC}"
    fi
    
    echo ""
}

# Uninstall Guardian
uninstall_launchagent "guardian"

# Uninstall Heartbeat
uninstall_launchagent "heartbeat"

echo "============================================"
echo "✅ Uninstallation Complete!"
echo "============================================"
echo ""
echo "Services removed:"
echo "  ❌ Guardian Bot"
echo "  ❌ Heartbeat Monitor"
echo ""
echo "Note: Log files are kept in bot/logs/"
echo "To remove logs manually:"
echo "  rm /Users/ssr/Projects/WorkingBot/bot/logs/launchagent_guardian*.log"
echo "  rm /Users/ssr/Projects/WorkingBot/bot/logs/launchagent_heartbeat*.log"
echo ""

