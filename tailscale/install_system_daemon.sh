#!/bin/bash

# ========================================
# Tailscale System Daemon Setup
# ========================================
# Purpose: Install Tailscale as a system-level daemon (requires sudo)
# Date: October 23, 2025
# ========================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Installing Tailscale System Daemon${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if we're root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}This script must be run as root (use sudo)${NC}"
    exit 1
fi

PLIST_PATH="/Library/LaunchDaemons/com.tailscale.tailscaled.plist"

echo -e "${YELLOW}Creating system LaunchDaemon...${NC}"

cat > "$PLIST_PATH" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tailscale.tailscaled</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/tailscaled</string>
        <string>-verbose=1</string>
        <string>-port</string>
        <string>41641</string>
    </array>
    
    <!-- Run as root -->
    <key>UserName</key>
    <string>root</string>
    
    <!-- Auto-start at boot -->
    <key>RunAtLoad</key>
    <true/>
    
    <!-- Keep alive - restart if crashes -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
        <key>NetworkState</key>
        <true/>
    </dict>
    
    <!-- Throttle restart attempts -->
    <key>ThrottleInterval</key>
    <integer>5</integer>
    
    <!-- Logging -->
    <key>StandardOutPath</key>
    <string>/opt/homebrew/var/log/tailscaled.log</string>
    
    <key>StandardErrorPath</key>
    <string>/opt/homebrew/var/log/tailscaled.error.log</string>
    
    <!-- Environment -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    
    <!-- Process settings -->
    <key>ProcessType</key>
    <string>Background</string>
    
    <key>Nice</key>
    <integer>-10</integer>
    
    <!-- Ensure socket permissions -->
    <key>SoftResourceLimits</key>
    <dict>
        <key>NumberOfFiles</key>
        <integer>10240</integer>
    </dict>
</dict>
</plist>
EOF

echo -e "${GREEN}✅ LaunchDaemon plist created${NC}"

# Set proper permissions
chown root:wheel "$PLIST_PATH"
chmod 644 "$PLIST_PATH"

echo -e "${GREEN}✅ Permissions set${NC}"

# Load the daemon
echo -e "${YELLOW}Loading daemon...${NC}"
launchctl load -w "$PLIST_PATH"

echo -e "${GREEN}✅ Daemon loaded${NC}"

# Wait for daemon to start
sleep 3

# Check if running
if pgrep -f tailscaled > /dev/null; then
    echo -e "${GREEN}✅ tailscaled is running!${NC}"
else
    echo -e "${RED}❌ Failed to start tailscaled${NC}"
    echo -e "${YELLOW}Check logs: tail -f /opt/homebrew/var/log/tailscaled.error.log${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}System daemon installed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
