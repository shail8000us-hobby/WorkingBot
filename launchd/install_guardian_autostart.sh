#!/bin/bash
# Install Guardian Bot Auto-Start (macOS)

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                       ║${NC}"
echo -e "${GREEN}║   🛡️  INSTALL GUARDIAN AUTO-START (macOS)                             ║${NC}"
echo -e "${GREEN}║                                                                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}❌ This script is for macOS only${NC}"
    echo ""
    echo "For Linux, use: systemd/install_guardian_autostart.sh"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Source and destination files
PLIST_SOURCE="$SCRIPT_DIR/com.gridbot.guardian.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.gridbot.guardian.plist"

# Check if plist file exists
if [ ! -f "$PLIST_SOURCE" ]; then
    echo -e "${RED}❌ Plist file not found: $PLIST_SOURCE${NC}"
    exit 1
fi

echo "Source file: $PLIST_SOURCE"
echo "Destination: $PLIST_DEST"
echo ""

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$HOME/Library/LaunchAgents"

# Check if already installed
if [ -f "$PLIST_DEST" ]; then
    echo -e "${YELLOW}⚠️  Guardian auto-start is already installed${NC}"
    echo ""
    read -p "Reinstall? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled"
        exit 0
    fi
    
    # Unload first
    echo "Unloading existing service..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Copy plist file
echo "Installing plist file..."
cp "$PLIST_SOURCE" "$PLIST_DEST"

# Fix permissions
chmod 644 "$PLIST_DEST"

# Load the service
echo "Loading service..."
launchctl load "$PLIST_DEST"

# Give it a moment
sleep 2

# Check if loaded
if launchctl list | grep -q "com.gridbot.guardian"; then
    echo ""
    echo -e "${GREEN}✅ Guardian auto-start installed successfully!${NC}"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Guardian will now start automatically on system boot${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Check status:  launchctl list | grep guardian"
    echo "View logs:     tail -f $PROJECT_ROOT/bot/logs/guardian.log"
    echo "Uninstall:     ./launchd/uninstall_guardian_autostart.sh"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Failed to load service${NC}"
    echo ""
    echo "Check logs:"
    echo "  tail -f $PROJECT_ROOT/bot/logs/guardian_error.log"
    exit 1
fi

