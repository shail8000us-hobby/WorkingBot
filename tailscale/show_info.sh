#!/bin/bash

# ========================================
# Tailscale Quick Start Card
# ========================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      🔐 TAILSCALE VPN - QUICK REFERENCE CARD              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get connection info
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1)
TAILSCALE_IPV6=$(tailscale ip -6 2>/dev/null | head -1)
TAILSCALE_STATUS=$(tailscale status --json 2>/dev/null)
HOSTNAME=$(echo "$TAILSCALE_STATUS" | jq -r '.Self.HostName // "unknown"')
DNSNAME=$(echo "$TAILSCALE_STATUS" | jq -r '.Self.DNSName // "unknown"' | sed 's/\.$//')
MAGICDNS_SUFFIX=$(echo "$TAILSCALE_STATUS" | jq -r '.MagicDNSSuffix // "unknown"')
USERNAME=$(whoami)

echo -e "${GREEN}📍 CONNECTION INFORMATION${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "IPv4:        ${YELLOW}$TAILSCALE_IP${NC}"
echo -e "IPv6:        ${YELLOW}$TAILSCALE_IPV6${NC}"
echo -e "Hostname:    ${YELLOW}$HOSTNAME${NC}"
echo -e "MagicDNS:    ${YELLOW}$DNSNAME${NC}"
echo -e "Tailnet:     ${YELLOW}$MAGICDNS_SUFFIX${NC}"
echo ""

echo -e "${GREEN}🔐 REMOTE SSH ACCESS${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}ssh $USERNAME@$DNSNAME${NC}"
echo -e "${YELLOW}ssh $USERNAME@$TAILSCALE_IP${NC}"
echo ""

echo -e "${GREEN}🌐 REMOTE WEB ACCESS${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "Backend API:  ${YELLOW}http://$TAILSCALE_IP:5555${NC}"
echo -e "              ${YELLOW}http://$DNSNAME:5555${NC}"
echo ""
echo -e "Frontend UI:  ${YELLOW}http://$TAILSCALE_IP:3000${NC}"
echo -e "              ${YELLOW}http://$DNSNAME:3000${NC}"
echo ""

echo -e "${GREEN}🛠️  SERVICE STATUS${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check daemon
if pgrep -f tailscaled > /dev/null; then
    echo -e "Daemon:      ${GREEN}✅ Running${NC}"
else
    echo -e "Daemon:      ${YELLOW}⚠️  Not Running${NC}"
fi

# Check connection
if tailscale status > /dev/null 2>&1; then
    echo -e "Connection:  ${GREEN}✅ Connected${NC}"
else
    echo -e "Connection:  ${YELLOW}⚠️  Disconnected${NC}"
fi

# Check watchdog
if launchctl list | grep -q com.tailscale.watchdog; then
    echo -e "Watchdog:    ${GREEN}✅ Running${NC}"
else
    echo -e "Watchdog:    ${YELLOW}⚠️  Not Running${NC}"
fi

echo ""

echo -e "${GREEN}📝 ESSENTIAL COMMANDS${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "Status:           ${YELLOW}tailscale status${NC}"
echo -e "Restart daemon:   ${YELLOW}sudo launchctl kickstart -k system/com.tailscale.tailscaled${NC}"
echo -e "View logs:        ${YELLOW}tail -f /opt/homebrew/var/log/tailscaled.log${NC}"
echo -e "Watchdog logs:    ${YELLOW}tail -f /opt/homebrew/var/log/tailscale_watchdog.log${NC}"
echo -e "Run tests:        ${YELLOW}~/Projects/WorkingBot/tailscale/test_tailscale.sh${NC}"
echo -e "Full guide:       ${YELLOW}cat ~/Projects/WorkingBot/tailscale/TAILSCALE_SETUP_GUIDE.md${NC}"
echo ""

echo -e "${GREEN}📊 CURRENT STATUS${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tailscale status 2>/dev/null || echo "Unable to get status"
echo ""

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  ✅ Copy the SSH/URL commands above to access remotely    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
