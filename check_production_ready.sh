#!/bin/bash
# Production Readiness Check - Run this before starting the bot

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                  AsyncGridBot Production Readiness Check                 ║"
echo "║                        November 12, 2025 11:45 PM                        ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

check_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((PASS++))
}

check_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((FAIL++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
}

echo "1. Configuration File Checks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "grid_config.env" ]; then
    check_pass "grid_config.env exists"
else
    check_fail "grid_config.env missing"
fi

if [ -f "secrets/api_keys.env" ]; then
    check_pass "secrets/api_keys.env exists"
else
    check_fail "secrets/api_keys.env missing"
fi

echo ""
echo "2. Grid Configuration Values"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

source grid_config.env 2>/dev/null

if [ "$GRIDBOT_LOWER" = "99000" ]; then
    check_pass "GRIDBOT_LOWER = 99000"
else
    check_fail "GRIDBOT_LOWER = $GRIDBOT_LOWER (expected 99000)"
fi

if [ "$GRIDBOT_UPPER" = "112000" ]; then
    check_pass "GRIDBOT_UPPER = 112000"
else
    check_fail "GRIDBOT_UPPER = $GRIDBOT_UPPER (expected 112000)"
fi

if [ "$GRIDBOT_STEP" = "500" ]; then
    check_pass "GRIDBOT_STEP = 500"
else
    check_fail "GRIDBOT_STEP = $GRIDBOT_STEP (expected 500)"
fi

if [ "$GRIDBOT_MAX_OPEN" = "5" ]; then
    check_pass "GRIDBOT_MAX_OPEN = 5"
else
    check_fail "GRIDBOT_MAX_OPEN = $GRIDBOT_MAX_OPEN (expected 5)"
fi

if [ "$GRIDBOT_LOT" = "1" ]; then
    check_pass "GRIDBOT_LOT = 1"
else
    check_fail "GRIDBOT_LOT = $GRIDBOT_LOT (expected 1)"
fi

echo ""
echo "3. Code Bug Fixes Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Bug #1: Instance variables stored
if grep -q "self.lower_price = lower_price" bot/strategy/async_gridbot.py; then
    check_pass "Bug #1 Fixed: Instance variables stored"
else
    check_fail "Bug #1 NOT Fixed: Instance variables missing"
fi

# Check Bug #2: tell() method exists
if grep -q "async def tell" bot/strategy/actors/base_actor.py; then
    check_pass "Bug #2 Fixed: tell() method exists"
else
    check_fail "Bug #2 NOT Fixed: tell() method missing"
fi

# Check Bug #3: Size field in messages
size_count=$(grep -c '"size":' bot/strategy/async_gridbot.py | head -1)
if [ "$size_count" -ge "6" ]; then
    check_pass "Bug #3 Fixed: Size field in $size_count messages"
else
    check_fail "Bug #3 NOT Fixed: Size field only in $size_count messages (need 6)"
fi

# Check Bug #4: lot_size attribute
if grep -q "self.lot_size = 1.0" bot/strategy/async_gridbot.py; then
    check_pass "Bug #4 Fixed: lot_size attribute exists"
else
    check_fail "Bug #4 NOT Fixed: lot_size attribute missing"
fi

echo ""
echo "4. Python File Syntax Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if python3 -m py_compile bot/strategy/async_gridbot.py 2>/dev/null; then
    check_pass "async_gridbot.py syntax valid"
else
    check_fail "async_gridbot.py has syntax errors"
fi

if python3 -m py_compile bot/strategy/actors/base_actor.py 2>/dev/null; then
    check_pass "base_actor.py syntax valid"
else
    check_fail "base_actor.py has syntax errors"
fi

if python3 -m py_compile bot/run.py 2>/dev/null; then
    check_pass "run.py syntax valid"
else
    check_fail "run.py has syntax errors"
fi

echo ""
echo "5. Dependencies Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if python3 -c "import httpx" 2>/dev/null; then
    check_pass "httpx installed"
else
    check_fail "httpx not installed"
fi

if python3 -c "import dotenv" 2>/dev/null; then
    check_pass "python-dotenv installed"
else
    check_fail "python-dotenv not installed"
fi

if python3 -c "import websockets" 2>/dev/null; then
    check_pass "websockets installed"
else
    check_fail "websockets not installed"
fi

echo ""
echo "6. Safety Checks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$EXECUTE_ORDERS" = "true" ]; then
    check_warn "EXECUTE_ORDERS=true (LIVE TRADING ENABLED)"
else
    check_pass "EXECUTE_ORDERS=$EXECUTE_ORDERS (safe)"
fi

if [ "$I_UNDERSTAND_LIVE" = "YES" ]; then
    check_warn "I_UNDERSTAND_LIVE=YES (confirmed live trading)"
else
    check_fail "I_UNDERSTAND_LIVE=$I_UNDERSTAND_LIVE (must be YES for live)"
fi

if [ "$TRADING_MODE" = "live" ]; then
    check_warn "TRADING_MODE=live (REAL MONEY)"
else
    check_pass "TRADING_MODE=$TRADING_MODE"
fi

echo ""
echo "7. Process Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if pgrep -f "python3 -m bot.run" > /dev/null; then
    check_warn "Bot is currently running (PID: $(pgrep -f 'python3 -m bot.run'))"
else
    check_pass "No bot process running"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                           READINESS SUMMARY                              ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "Checks Passed: ${GREEN}$PASS${NC}"
echo -e "Checks Failed: ${RED}$FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED - READY FOR PRODUCTION${NC}"
    echo ""
    echo "Next Steps:"
    echo "1. Cancel duplicate orders on Delta Exchange"
    echo "2. Start bot: python3 -m bot.run"
    echo "3. Monitor for 5 minutes to ensure single order placement"
    echo "4. Check logs for any errors"
    echo ""
    exit 0
else
    echo -e "${RED}❌ SOME CHECKS FAILED - FIX ISSUES BEFORE STARTING${NC}"
    echo ""
    echo "Fix the failed checks above before starting the bot."
    echo ""
    exit 1
fi
