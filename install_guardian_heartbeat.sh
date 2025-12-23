#!/bin/bash
# Install Guardian and Heartbeat LaunchAgents
# This script installs both services to run automatically at boot

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="/Users/ssr/Projects/WorkingBot"
LAUNCHAGENTS_DIR="$HOME/Library/LaunchAgents"

echo ""
echo "============================================"
echo "🛡️  Guardian & Heartbeat Installation"
echo "============================================"
echo ""

# Check if running from project root
if [ ! -f "$PROJECT_ROOT/bot/guardian/core/guardian_bot.py" ]; then
    echo -e "${RED}❌ Error: Guardian bot file not found!${NC}"
    echo "Expected: $PROJECT_ROOT/bot/guardian/core/guardian_bot.py"
    exit 1
fi

if [ ! -f "$PROJECT_ROOT/bot/heartbeat/monitor.py" ]; then
    echo -e "${RED}❌ Error: Heartbeat monitor file not found!${NC}"
    echo "Expected: $PROJECT_ROOT/bot/heartbeat/monitor.py"
    exit 1
fi

# Create logs directory
mkdir -p "$PROJECT_ROOT/bot/logs"
echo -e "${GREEN}✅ Logs directory ready${NC}"

# Function to install a launchagent
install_launchagent() {
    local SERVICE_NAME=$1
    local PLIST_FILE="com.workingbot.${SERVICE_NAME}.plist"
    local SOURCE_PLIST="$PROJECT_ROOT/launchagents/$PLIST_FILE"
    local DEST_PLIST="$LAUNCHAGENTS_DIR/$PLIST_FILE"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Installing $SERVICE_NAME service..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check if source plist exists
    if [ ! -f "$SOURCE_PLIST" ]; then
        echo -e "${RED}❌ Error: Source plist not found: $SOURCE_PLIST${NC}"
        return 1
    fi
    
    # Unload existing service if loaded
    if launchctl list | grep -q "com.workingbot.${SERVICE_NAME}"; then
        echo -e "${YELLOW}⚠️  Unloading existing service...${NC}"
        launchctl unload "$DEST_PLIST" 2>/dev/null || true
        sleep 2
    fi
    
    # Copy plist file
    echo "📋 Copying plist file..."
    cp "$SOURCE_PLIST" "$DEST_PLIST"
    
    # Set permissions
    echo "🔐 Setting permissions..."
    chmod 644 "$DEST_PLIST"
    
    # Load the service
    echo "🚀 Loading service..."
    launchctl load "$DEST_PLIST"
    
    # Wait a moment for service to start
    sleep 3
    
    # Verify service is loaded
    if launchctl list | grep -q "com.workingbot.${SERVICE_NAME}"; then
        echo -e "${GREEN}✅ Service loaded successfully${NC}"
        
        # Check if actually running (PID exists)
        if launchctl list | grep "com.workingbot.${SERVICE_NAME}" | grep -q -v "^\-"; then
            echo -e "${GREEN}✅ Service is running${NC}"
        else
            echo -e "${YELLOW}⚠️  Service loaded but may not be running yet${NC}"
            echo "   Check logs in: $PROJECT_ROOT/bot/logs/launchagent_${SERVICE_NAME}*.log"
        fi
    else
        echo -e "${RED}❌ Failed to load service${NC}"
        return 1
    fi
    
    return 0
}

# Install Guardian
if install_launchagent "guardian"; then
    echo -e "${GREEN}✅ Guardian installation complete${NC}"
else
    echo -e "${RED}❌ Guardian installation failed${NC}"
    exit 1
fi

# Install Heartbeat
if install_launchagent "heartbeat"; then
    echo -e "${GREEN}✅ Heartbeat installation complete${NC}"
else
    echo -e "${RED}❌ Heartbeat installation failed${NC}"
    exit 1
fi

echo ""
echo "============================================"
echo "📊 Installation Summary"
echo "============================================"
echo ""
echo "Services installed:"
echo -e "  ${GREEN}✅${NC} Guardian Bot    - com.workingbot.guardian"
echo -e "  ${GREEN}✅${NC} Heartbeat Monitor - com.workingbot.heartbeat"
echo ""
echo "Service status:"
launchctl list | grep "com.workingbot" || echo "  (No services found in launchctl list)"
echo ""
echo "Log files:"
echo "  Guardian:  $PROJECT_ROOT/bot/logs/launchagent_guardian*.log"
echo "  Heartbeat: $PROJECT_ROOT/bot/logs/launchagent_heartbeat*.log"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 Management Commands"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Check status:"
echo "  launchctl list | grep workingbot"
echo ""
echo "View logs:"
echo "  tail -f $PROJECT_ROOT/bot/logs/launchagent_guardian.log"
echo "  tail -f $PROJECT_ROOT/bot/logs/launchagent_heartbeat.log"
echo ""
echo "Stop services:"
echo "  launchctl unload ~/Library/LaunchAgents/com.workingbot.guardian.plist"
echo "  launchctl unload ~/Library/LaunchAgents/com.workingbot.heartbeat.plist"
echo ""
echo "Start services:"
echo "  launchctl load ~/Library/LaunchAgents/com.workingbot.guardian.plist"
echo "  launchctl load ~/Library/LaunchAgents/com.workingbot.heartbeat.plist"
echo ""
echo "Restart services:"
echo "  launchctl kickstart -k gui/$(id -u)/com.workingbot.guardian"
echo "  launchctl kickstart -k gui/$(id -u)/com.workingbot.heartbeat"
echo ""
echo "============================================"
echo "✅ Installation Complete!"
echo "============================================"
echo ""
echo -e "${GREEN}Both services will now start automatically at boot!${NC}"
echo ""

