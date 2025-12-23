#!/bin/bash
# Uninstall Guardian Bot Auto-Start (macOS)

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🛑 Uninstalling Guardian Auto-Start...${NC}"
echo ""

PLIST_FILE="$HOME/Library/LaunchAgents/com.gridbot.guardian.plist"

if [ ! -f "$PLIST_FILE" ]; then
    echo -e "${YELLOW}⚠️  Guardian auto-start is not installed${NC}"
    exit 0
fi

# Unload the service
echo "Unloading service..."
launchctl unload "$PLIST_FILE" 2>/dev/null || true

# Remove plist file
echo "Removing plist file..."
rm -f "$PLIST_FILE"

echo ""
echo -e "${GREEN}✅ Guardian auto-start uninstalled${NC}"
echo ""
echo "Guardian will no longer start automatically on system boot"
echo "You can still start it manually: ./dashboard/start_guardian.sh"
echo ""

