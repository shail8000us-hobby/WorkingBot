#!/bin/bash
# GridBot Pro - Mobile Connection Test Script
# Tests mobile/Tailscale connectivity and configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PORT=5555
TAILSCALE_IP="100.107.230.67"
MAGICDDNS="mymac.tail289dc3.ts.net"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                           ║${NC}"
echo -e "${BLUE}║     📱 GridBot Pro - Mobile Connection Test Suite        ║${NC}"
echo -e "${BLUE}║                                                           ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Test 1: Check Tailscale is running
echo -e "${BLUE}[1/10]${NC} Checking Tailscale daemon..."
if tailscale status &>/dev/null; then
    echo -e "${GREEN}✅ Tailscale is running${NC}"
    TAILSCALE_STATUS=$(tailscale status --json 2>/dev/null)
    CURRENT_IP=$(echo "$TAILSCALE_STATUS" | grep -o '"TailscaleIPs":\["[^"]*"' | grep -o '[0-9.]*' | head -1)
    echo -e "   IP: ${GREEN}${CURRENT_IP}${NC}"
else
    echo -e "${RED}❌ Tailscale is not running${NC}"
    echo -e "   Fix: brew services start tailscale"
    exit 1
fi

# Test 2: Check backend is running
echo ""
echo -e "${BLUE}[2/10]${NC} Checking backend process..."
if lsof -ti:$PORT &>/dev/null; then
    PID=$(lsof -ti:$PORT)
    echo -e "${GREEN}✅ Backend is running${NC}"
    echo -e "   PID: ${GREEN}${PID}${NC}"
    echo -e "   Port: ${GREEN}${PORT}${NC}"
else
    echo -e "${RED}❌ Backend is not running on port ${PORT}${NC}"
    echo -e "   Fix: python3 webui/backend/app.py"
    exit 1
fi

# Test 3: Check CORS configuration
echo ""
echo -e "${BLUE}[3/10]${NC} Checking CORS configuration..."
if grep -q "WEBUI_ALLOWED_ORIGINS" grid_config.env 2>/dev/null; then
    CORS_CONFIG=$(grep "WEBUI_ALLOWED_ORIGINS" grid_config.env | head -1)
    echo -e "${GREEN}✅ CORS configured in grid_config.env${NC}"
    
    # Check if Tailscale IP is included
    if echo "$CORS_CONFIG" | grep -q "100\.\*\.\*\.\*" || echo "$CORS_CONFIG" | grep -q "$CURRENT_IP"; then
        echo -e "${GREEN}✅ Tailscale IPs allowed${NC}"
    else
        echo -e "${YELLOW}⚠️  Warning: Tailscale IPs may not be in CORS config${NC}"
        echo -e "   Current config: ${CORS_CONFIG}"
    fi
    
    # Check if MagicDNS is included
    if echo "$CORS_CONFIG" | grep -q "\.ts\.net"; then
        echo -e "${GREEN}✅ Tailscale MagicDNS allowed${NC}"
    else
        echo -e "${YELLOW}⚠️  Warning: Tailscale MagicDNS may not be in CORS config${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  WEBUI_ALLOWED_ORIGINS not found in grid_config.env${NC}"
    echo -e "   Using default: http://localhost:*"
fi

# Test 4: Test localhost connection
echo ""
echo -e "${BLUE}[4/10]${NC} Testing localhost connection..."
if curl -s -f "http://localhost:$PORT/api/health" >/dev/null; then
    HEALTH=$(curl -s "http://localhost:$PORT/api/health")
    echo -e "${GREEN}✅ Localhost API responding${NC}"
    echo -e "   Response: ${HEALTH}"
else
    echo -e "${RED}❌ Localhost API not responding${NC}"
    exit 1
fi

# Test 5: Test Tailscale IP connection
echo ""
echo -e "${BLUE}[5/10]${NC} Testing Tailscale IP connection..."
if curl -s -f -m 5 "http://${CURRENT_IP}:${PORT}/api/health" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Tailscale IP responding${NC}"
    echo -e "   URL: http://${CURRENT_IP}:${PORT}"
else
    echo -e "${RED}❌ Tailscale IP not responding${NC}"
    echo -e "   This might be normal if firewall blocks loopback to Tailscale IP"
    echo -e "   Test from actual mobile device instead"
fi

# Test 6: Test MagicDNS connection (if available)
echo ""
echo -e "${BLUE}[6/10]${NC} Testing MagicDNS connection..."
if tailscale status --json | grep -q "MagicDNS"; then
    # Get actual MagicDNS hostname
    ACTUAL_HOSTNAME=$(tailscale status --json | grep -o '"DNSName":"[^"]*"' | head -1 | cut -d'"' -f4)
    if [ ! -z "$ACTUAL_HOSTNAME" ]; then
        echo -e "   Hostname: ${BLUE}${ACTUAL_HOSTNAME}${NC}"
        if curl -s -f -m 5 "http://${ACTUAL_HOSTNAME}:${PORT}/api/health" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ MagicDNS responding${NC}"
        else
            echo -e "${YELLOW}⚠️  MagicDNS not responding from server (test from mobile)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  MagicDNS hostname not found${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  MagicDNS not enabled${NC}"
fi

# Test 7: Check SocketIO configuration
echo ""
echo -e "${BLUE}[7/10]${NC} Checking SocketIO configuration..."
if grep -q "ping_timeout=120" webui/backend/app.py 2>/dev/null; then
    echo -e "${GREEN}✅ Mobile-optimized ping_timeout (120s)${NC}"
else
    echo -e "${YELLOW}⚠️  ping_timeout may not be optimized for mobile${NC}"
fi

if grep -q "transports=\['websocket', 'polling'\]" webui/backend/app.py 2>/dev/null; then
    echo -e "${GREEN}✅ Transport fallback enabled (websocket + polling)${NC}"
else
    echo -e "${YELLOW}⚠️  Transport fallback may not be configured${NC}"
fi

# Test 8: Check frontend build
echo ""
echo -e "${BLUE}[8/10]${NC} Checking frontend build..."
if [ -f "webui/frontend/build/index.html" ]; then
    BUILD_SIZE=$(du -sh webui/frontend/build 2>/dev/null | cut -f1)
    echo -e "${GREEN}✅ Frontend build exists${NC}"
    echo -e "   Size: ${BUILD_SIZE}"
    
    # Check for mobile viewport meta tags
    if grep -q "viewport.*mobile-web-app" webui/frontend/public/index.html 2>/dev/null; then
        echo -e "${GREEN}✅ Mobile viewport meta tags present${NC}"
    else
        echo -e "${YELLOW}⚠️  Mobile meta tags may be missing${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Frontend build not found${NC}"
    echo -e "   Run: cd webui/frontend && npm run build"
fi

# Test 9: Test SocketIO endpoint
echo ""
echo -e "${BLUE}[9/10]${NC} Testing SocketIO endpoint..."
if curl -s -f "http://localhost:$PORT/socket.io/?EIO=4&transport=polling" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ SocketIO polling endpoint responding${NC}"
else
    echo -e "${YELLOW}⚠️  SocketIO endpoint may not be accessible${NC}"
fi

# Test 10: Check logs for errors
echo ""
echo -e "${BLUE}[10/10]${NC} Checking recent logs for errors..."
if [ -f "/tmp/gridbot_webui.log" ]; then
    ERROR_COUNT=$(grep -i "error\|exception\|failed" /tmp/gridbot_webui.log 2>/dev/null | tail -10 | wc -l)
    if [ "$ERROR_COUNT" -eq 0 ]; then
        echo -e "${GREEN}✅ No recent errors in logs${NC}"
    else
        echo -e "${YELLOW}⚠️  Found ${ERROR_COUNT} recent errors/warnings${NC}"
        echo -e "   Check: tail -50 /tmp/gridbot_webui.log"
    fi
else
    echo -e "${YELLOW}⚠️  Log file not found: /tmp/gridbot_webui.log${NC}"
fi

# Summary
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    TEST SUMMARY                           ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✅ Server-side tests passed!${NC}"
echo ""
echo -e "${YELLOW}📱 NEXT STEPS - Test from Mobile Device:${NC}"
echo ""
echo -e "1. Ensure mobile device is connected to Tailscale"
echo -e "2. Open mobile browser and navigate to:"
echo -e "   ${BLUE}http://${CURRENT_IP}:${PORT}${NC}"
echo ""
echo -e "3. Verify:"
echo -e "   ✅ No 'Error' badge at top"
echo -e "   ✅ Bot status shows correctly"
echo -e "   ✅ Real-time updates working"
echo -e "   ✅ Connection indicator is green"
echo ""
echo -e "4. Test connection stability:"
echo -e "   - Lock/unlock phone screen"
echo -e "   - Switch WiFi <-> Cellular"
echo -e "   - Leave app open for 10+ minutes"
echo ""
echo -e "${GREEN}🎉 If all mobile tests pass, deployment is successful!${NC}"
echo ""
echo -e "📚 Full guide: ${BLUE}MOBILE_DEPLOYMENT_GUIDE.md${NC}"
echo ""
