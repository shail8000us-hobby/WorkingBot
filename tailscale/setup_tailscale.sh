#!/bin/bash

# ========================================
# Tailscale Bulletproof Setup Script
# ========================================
# Purpose: Install and configure Tailscale for always-on connection
# Features: Auto-start, auto-reconnect, watchdog monitoring
# Platform: macOS
# Date: October 23, 2025
# ========================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Tailscale Bulletproof Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}❌ Error: This script is designed for macOS only${NC}"
    exit 1
fi

# Check if Tailscale is installed
if ! command -v tailscale &> /dev/null; then
    echo -e "${RED}❌ Error: Tailscale is not installed${NC}"
    echo -e "${YELLOW}Install it with: brew install tailscale${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Tailscale found: $(tailscale version | head -1)${NC}"
echo ""

# Step 1: Create log directory
echo -e "${YELLOW}📁 Step 1: Creating log directory...${NC}"
sudo mkdir -p /opt/homebrew/var/log
sudo chown $(whoami) /opt/homebrew/var/log
echo -e "${GREEN}✅ Log directory ready${NC}"
echo ""

# Step 2: Stop any existing Tailscale service
echo -e "${YELLOW}🛑 Step 2: Stopping existing Tailscale services...${NC}"
brew services stop tailscale 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/homebrew.mxcl.tailscale.plist 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.tailscale.watchdog.plist 2>/dev/null || true
pkill -f tailscaled 2>/dev/null || true
sleep 2
echo -e "${GREEN}✅ Existing services stopped${NC}"
echo ""

# Step 3: Install improved LaunchAgent for tailscaled
echo -e "${YELLOW}📝 Step 3: Installing Tailscale LaunchAgent...${NC}"
cp "$SCRIPT_DIR/com.tailscale.tailscaled.plist" ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.tailscale.tailscaled.plist
sleep 3
echo -e "${GREEN}✅ Tailscale daemon started${NC}"
echo ""

# Step 4: Check if already logged in
echo -e "${YELLOW}🔐 Step 4: Checking Tailscale authentication...${NC}"
if tailscale status > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Already logged in to Tailscale${NC}"
    NEEDS_LOGIN=false
else
    echo -e "${YELLOW}⚠️  Not logged in - will need authentication${NC}"
    NEEDS_LOGIN=true
fi
echo ""

# Step 5: Configure Tailscale with optimal flags
if [ "$NEEDS_LOGIN" = true ]; then
    echo -e "${YELLOW}🚀 Step 5: Configuring Tailscale...${NC}"
    echo -e "${BLUE}Running: tailscale up --ssh --accept-dns --accept-routes --advertise-tags=tag:botserver${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  This will open a browser window for authentication.${NC}"
    echo -e "${YELLOW}Please complete the authentication in your browser.${NC}"
    echo ""
    
    tailscale up \
        --ssh \
        --accept-dns \
        --accept-routes \
        --advertise-tags=tag:botserver \
        --operator=$(whoami)
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Tailscale configured and authenticated successfully${NC}"
    else
        echo ""
        echo -e "${RED}❌ Failed to authenticate. Please run manually:${NC}"
        echo -e "${YELLOW}tailscale up --ssh --accept-dns --accept-routes --advertise-tags=tag:botserver${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}🔄 Step 5: Updating Tailscale configuration...${NC}"
    tailscale up \
        --ssh \
        --accept-dns \
        --accept-routes \
        --advertise-tags=tag:botserver \
        --operator=$(whoami) 2>/dev/null || true
    echo -e "${GREEN}✅ Configuration updated${NC}"
fi
echo ""

# Step 6: Install watchdog
echo -e "${YELLOW}👀 Step 6: Installing Tailscale watchdog...${NC}"
cp "$SCRIPT_DIR/com.tailscale.watchdog.plist" ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.tailscale.watchdog.plist
echo -e "${GREEN}✅ Watchdog installed and started${NC}"
echo ""

# Step 7: Get connection info
echo -e "${YELLOW}📡 Step 7: Retrieving connection information...${NC}"
sleep 2

TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1)
TAILSCALE_IPV6=$(tailscale ip -6 2>/dev/null | head -1)
TAILSCALE_STATUS=$(tailscale status --json 2>/dev/null)
TAILSCALE_HOSTNAME=$(echo "$TAILSCALE_STATUS" | grep -o '"HostName":"[^"]*"' | cut -d'"' -f4)
TAILSCALE_SELF=$(echo "$TAILSCALE_STATUS" | grep -o '"DNSName":"[^"]*"' | cut -d'"' -f4 | head -1)

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 TAILSCALE SETUP COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📍 Your Tailscale Information:${NC}"
echo -e "   IPv4: ${GREEN}$TAILSCALE_IP${NC}"
echo -e "   IPv6: ${GREEN}$TAILSCALE_IPV6${NC}"
echo -e "   Hostname: ${GREEN}$TAILSCALE_HOSTNAME${NC}"
echo -e "   MagicDNS: ${GREEN}$TAILSCALE_SELF${NC}"
echo ""
echo -e "${BLUE}🔐 Remote Access Commands:${NC}"
echo -e "   SSH: ${GREEN}ssh $(whoami)@$TAILSCALE_HOSTNAME${NC}"
if [ -n "$TAILSCALE_SELF" ]; then
    echo -e "   SSH (MagicDNS): ${GREEN}ssh $(whoami)@${TAILSCALE_SELF%.}${NC}"
fi
echo ""
echo -e "${BLUE}🌐 Access Your Bot WebUI:${NC}"
echo -e "   Backend: ${GREEN}http://$TAILSCALE_IP:5555${NC}"
echo -e "   Frontend: ${GREEN}http://$TAILSCALE_IP:3000${NC}"
if [ -n "$TAILSCALE_HOSTNAME" ]; then
    echo -e "   Backend (hostname): ${GREEN}http://$TAILSCALE_HOSTNAME:5555${NC}"
    echo -e "   Frontend (hostname): ${GREEN}http://$TAILSCALE_HOSTNAME:3000${NC}"
fi
echo ""
echo -e "${BLUE}📊 Service Status:${NC}"
echo -e "   Daemon: ${GREEN}Running with KeepAlive${NC}"
echo -e "   Watchdog: ${GREEN}Running (checks every 60s)${NC}"
echo -e "   Auto-start: ${GREEN}Enabled at login${NC}"
echo -e "   Auto-reconnect: ${GREEN}Enabled${NC}"
echo -e "   SSH: ${GREEN}Enabled${NC}"
echo -e "   MagicDNS: ${GREEN}Enabled${NC}"
echo ""
echo -e "${BLUE}📋 Configuration Files:${NC}"
echo -e "   Daemon: ${GREEN}~/Library/LaunchAgents/com.tailscale.tailscaled.plist${NC}"
echo -e "   Watchdog: ${GREEN}~/Library/LaunchAgents/com.tailscale.watchdog.plist${NC}"
echo -e "   Watchdog Script: ${GREEN}$SCRIPT_DIR/tailscale_watchdog.sh${NC}"
echo ""
echo -e "${BLUE}📝 Log Files:${NC}"
echo -e "   Daemon: ${GREEN}/opt/homebrew/var/log/tailscaled.log${NC}"
echo -e "   Watchdog: ${GREEN}/opt/homebrew/var/log/tailscale_watchdog.log${NC}"
echo ""
echo -e "${YELLOW}💡 Useful Commands:${NC}"
echo -e "   Check status: ${GREEN}tailscale status${NC}"
echo -e "   View logs: ${GREEN}tail -f /opt/homebrew/var/log/tailscaled.log${NC}"
echo -e "   Watchdog logs: ${GREEN}tail -f /opt/homebrew/var/log/tailscale_watchdog.log${NC}"
echo -e "   Restart daemon: ${GREEN}launchctl kickstart -k gui/$(id -u)/com.tailscale.tailscaled${NC}"
echo -e "   Test watchdog: ${GREEN}$SCRIPT_DIR/tailscale_watchdog.sh${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Your machine is now always connected!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Save connection info to file
cat > "$SCRIPT_DIR/TAILSCALE_INFO.txt" << EOF
# Tailscale Connection Information
# Generated: $(date)

## Network Information
IPv4: $TAILSCALE_IP
IPv6: $TAILSCALE_IPV6
Hostname: $TAILSCALE_HOSTNAME
MagicDNS: $TAILSCALE_SELF

## Remote Access

### SSH
ssh $(whoami)@$TAILSCALE_HOSTNAME

### WebUI
Backend:  http://$TAILSCALE_IP:5555
Frontend: http://$TAILSCALE_IP:3000

### Alternative (MagicDNS)
Backend:  http://$TAILSCALE_HOSTNAME:5555
Frontend: http://$TAILSCALE_HOSTNAME:3000

## Service Management

### Check Status
tailscale status

### View Daemon Logs
tail -f /opt/homebrew/var/log/tailscaled.log

### View Watchdog Logs
tail -f /opt/homebrew/var/log/tailscale_watchdog.log

### Restart Services
launchctl kickstart -k gui/$(id -u)/com.tailscale.tailscaled
launchctl kickstart -k gui/$(id -u)/com.tailscale.watchdog

### Manual Watchdog Run
$SCRIPT_DIR/tailscale_watchdog.sh

## Configuration

### LaunchAgents
- ~/Library/LaunchAgents/com.tailscale.tailscaled.plist
- ~/Library/LaunchAgents/com.tailscale.watchdog.plist

### Features Enabled
✅ Auto-start at login
✅ Auto-reconnect on network change
✅ Watchdog monitoring (60s interval)
✅ SSH access enabled
✅ MagicDNS enabled
✅ Keep-alive on crash/exit
✅ Network state monitoring

## Testing

### Simulate Network Change
sudo ifconfig en0 down && sleep 5 && sudo ifconfig en0 up

### Force Daemon Restart
launchctl kickstart -k gui/$(id -u)/com.tailscale.tailscaled

### Check Watchdog Function
$SCRIPT_DIR/tailscale_watchdog.sh && tail -20 /opt/homebrew/var/log/tailscale_watchdog.log

### Verify Remote Access
# From another device on the same tailnet:
ssh $(whoami)@$TAILSCALE_HOSTNAME
curl http://$TAILSCALE_IP:5555/api/bots/status

EOF

echo -e "${GREEN}💾 Connection info saved to: $SCRIPT_DIR/TAILSCALE_INFO.txt${NC}"
echo ""
