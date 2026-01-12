#!/bin/bash
# WebUI v1 Health Check Script
# Quick verification that webUI is stable and operational

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 WebUI v1 Health Check - $(date '+%Y-%m-%d %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

# Check 1: Backend Health
echo -n "Checking Backend Health... "
if curl -s --max-time 3 http://localhost:5555/api/health | grep -q "healthy"; then
    echo -e "${GREEN}✅ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL++))
fi

# Check 2: Config API
echo -n "Checking Config API... "
if curl -s --max-time 3 http://localhost:5555/api/config/all | grep -q "GRIDBOT_SYMBOL"; then
    echo -e "${GREEN}✅ PASS${NC}"
    SYMBOL=$(curl -s http://localhost:5555/api/config/all | python3 -c "import sys,json; print(json.load(sys.stdin)['config'].get('GRIDBOT_SYMBOL', 'N/A'))" 2>/dev/null)
    echo "   └─ Symbol: $SYMBOL"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL++))
fi

# Check 3: Frontend Serving
echo -n "Checking Frontend... "
if curl -s --max-time 3 http://localhost:5555/ | grep -q "SSR BOT"; then
    echo -e "${GREEN}✅ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL++))
fi

# Check 4: Bot Status
echo -n "Checking Bot Status... "
BOT_RESPONSE=$(curl -s --max-time 3 http://localhost:5555/api/bot/status)
if echo "$BOT_RESPONSE" | grep -q '"running"'; then
    IS_RUNNING=$(echo "$BOT_RESPONSE" | python3 -c "import sys,json; print('true' if json.load(sys.stdin).get('running') else 'false')" 2>/dev/null)
    if [ "$IS_RUNNING" = "true" ]; then
        echo -e "${GREEN}✅ PASS${NC} (Running)"
        ((PASS++))
    else
        echo -e "${YELLOW}⚠️  WARN${NC} (Stopped)"
        ((PASS++))
    fi
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL++))
fi

# Check 5: LaunchAgent
echo -n "Checking LaunchAgent... "
if launchctl list | grep -q "com.gridbot.production.webui"; then
    echo -e "${GREEN}✅ PASS${NC}"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL++))
fi

# Check 6: Port Availability
echo -n "Checking Port 5555... "
if lsof -ti:5555 > /dev/null 2>&1; then
    PID=$(lsof -ti:5555 | head -1)
    echo -e "${GREEN}✅ PASS${NC} (PID: $PID)"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL++))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Results: ${GREEN}$PASS Passed${NC} | ${RED}$FAIL Failed${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 WebUI v1 is STABLE and OPERATIONAL!${NC}"
    echo ""
    echo "Access your WebUI at: http://localhost:5555"
    echo ""
    exit 0
else
    echo -e "${RED}⚠️  Some issues detected. Run fix commands:${NC}"
    echo ""
    echo "  # Restart WebUI backend"
    echo "  launchctl kickstart -k gui/\$(id -u)/com.gridbot.production.webui"
    echo ""
    echo "  # Check logs"
    echo "  tail -f webui/backend/logs/backend_fixed.log"
    echo ""
    exit 1
fi
