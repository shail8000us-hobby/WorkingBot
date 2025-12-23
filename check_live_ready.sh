#!/bin/bash
# Live Trading Pre-Flight Check Script
# Run this before starting live trading

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                                                                      ║"
echo "║           🚨 LIVE TRADING PRE-FLIGHT CHECK 🚨                        ║"
echo "║                                                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check counter
CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

# Function to print check result
check() {
    local name="$1"
    local command="$2"
    local expected="$3"
    
    printf "%-50s" "$name"
    
    result=$(eval "$command" 2>&1)
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        if [ -n "$expected" ]; then
            if echo "$result" | grep -q "$expected"; then
                echo -e "${GREEN}✅ PASS${NC}"
                ((CHECKS_PASSED++))
            else
                echo -e "${RED}❌ FAIL${NC}"
                echo "   Expected: $expected"
                echo "   Got: $result"
                ((CHECKS_FAILED++))
            fi
        else
            echo -e "${GREEN}✅ PASS${NC}"
            ((CHECKS_PASSED++))
        fi
    else
        echo -e "${RED}❌ FAIL${NC}"
        echo "   Error: $result"
        ((CHECKS_FAILED++))
    fi
}

check_warning() {
    local name="$1"
    local command="$2"
    local expected="$3"
    
    printf "%-50s" "$name"
    
    result=$(eval "$command" 2>&1)
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        if [ -n "$expected" ]; then
            if echo "$result" | grep -q "$expected"; then
                echo -e "${YELLOW}⚠️  WARNING${NC}"
                echo "   $expected"
                ((WARNINGS++))
            else
                echo -e "${GREEN}✅ OK${NC}"
                ((CHECKS_PASSED++))
            fi
        else
            echo -e "${GREEN}✅ OK${NC}"
            ((CHECKS_PASSED++))
        fi
    else
        echo -e "${YELLOW}⚠️  WARNING${NC}"
        echo "   $expected"
        ((WARNINGS++))
    fi
}

echo "1. CHECKING SYSTEM STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
# Inverted check - we want NO bots running
if ps aux | grep 'bot/run.py' | grep -v grep >/dev/null 2>&1; then
    printf "%-50s" "No trading bots running"
    echo -e "${RED}❌ FAIL${NC}"
    echo "   ERROR: Bot is already running! Stop it first."
    ((CHECKS_FAILED++))
else
    printf "%-50s" "No trading bots running"
    echo -e "${GREEN}✅ PASS${NC}"
    ((CHECKS_PASSED++))
fi
check "WebUI LaunchAgent active" "launchctl list | grep com.gridbot.webui | grep -v grep"
check "WebUI responding" "curl -s http://localhost:5555 | head -1"
check "Lock files clean" "[ ! -f /tmp/trading_bot.lock ]"
check "Reports directory exists" "[ -d reports ]"
check "Logs directory writable" "[ -w . ]"
echo ""

echo "2. CHECKING CONFIGURATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check "Trading mode = live" "grep '^TRADING_MODE=live' grid_config.env"
check "Execute orders enabled" "grep '^EXECUTE_ORDERS=true' .env"
check "Live mode acknowledged" "grep '^I_UNDERSTAND_LIVE=.*YES' .env"
check "Max loss configured" "grep '^MAX_ACCOUNT_LOSS_INR=' grid_config.env"
check "Guardian limit configured" "grep '^GUARDIAN_MAX_ACCOUNT_LOSS_INR=' grid_config.env"
check "Grid parameters set" "grep '^GRIDBOT_LOWER=' grid_config.env"
check "Volatility protection on" "grep '^VOLATILITY_SAFETY_ENABLED=true' grid_config.env"
echo ""

echo "3. CHECKING SAFETY SYSTEMS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check "Guardian enabled" "grep '^GUARDIAN_ENABLED=true' grid_config.env"
check "Heartbeat enabled" "grep '^ENABLE_HEARTBEAT=true' grid_config.env"
check "Circuit breaker on" "grep '^CIRCUIT_BREAKER_ENABLED=true' grid_config.env"
check "Liquidation protection on" "grep '^LIQUIDATION_PROTECTION_ENABLED=true' grid_config.env"
check "Margin limit set (≤40%)" "grep '^MARGIN_UTILIZATION_MAX=40' grid_config.env"
echo ""

echo "4. CHECKING GRID CONFIGURATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
LOWER=$(grep '^GRIDBOT_LOWER=' grid_config.env | cut -d'=' -f2)
UPPER=$(grep '^GRIDBOT_UPPER=' grid_config.env | cut -d'=' -f2)
STEP=$(grep '^GRIDBOT_STEP=' grid_config.env | cut -d'=' -f2)
REF=$(grep '^GRIDBOT_REF=' grid_config.env | cut -d'=' -f2)
LOT=$(grep '^GRIDBOT_LOT=' grid_config.env | cut -d'=' -f2)
MAX_OPEN=$(grep '^GRIDBOT_MAX_OPEN=' grid_config.env | cut -d'=' -f2)

echo "   Lower:     $LOWER"
echo "   Upper:     $UPPER"
echo "   Step:      $STEP"
echo "   Reference: $REF"
echo "   Lot Size:  $LOT"
echo "   Max Open:  $MAX_OPEN"
echo ""

# Calculate first BUY
FIRST_BUY=$((REF - STEP))
echo "   First BUY will be at: $FIRST_BUY"
echo ""

echo "5. WARNINGS & RECOMMENDATIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_warning "Telegram configured" "grep '^TELEGRAM_BOT_TOKEN=.*' grid_config.env | grep -v '^TELEGRAM_BOT_TOKEN=\*\*\*'" "Telegram notifications not configured"
check_warning "Two-Man Rule enabled" "grep '^TWO_MAN_RULE_ENABLED=true' grid_config.env" "Two-Man Rule disabled"
check_warning "Conservative lot size" "[ $LOT -le 1 ]" "Lot size > 1 (risky for first run)"
check_warning "Conservative max open" "[ $MAX_OPEN -le 3 ]" "Max open > 3 (risky for first run)"
echo ""

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                         SUMMARY                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "Checks Passed:  ${GREEN}$CHECKS_PASSED${NC}"
echo -e "Checks Failed:  ${RED}$CHECKS_FAILED${NC}"
echo -e "Warnings:       ${YELLOW}$WARNINGS${NC}"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                                      ║${NC}"
    echo -e "${GREEN}║                    ✅ ALL CRITICAL CHECKS PASSED                     ║${NC}"
    echo -e "${GREEN}║                                                                      ║${NC}"
    echo -e "${GREEN}║                  YOU ARE READY FOR LIVE TRADING                      ║${NC}"
    echo -e "${GREEN}║                                                                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "🚀 To start trading:"
    echo "   1. Open WebUI: http://localhost:5555/bot-control"
    echo "   2. Click 'Start Bot (Live Mode)'"
    echo "   3. Confirm the safety dialog"
    echo "   4. Monitor actively for first 2-4 hours!"
    echo ""
    echo "📊 Or via command line:"
    echo "   python3 bot/run.py live infinite"
    echo ""
    echo "⚠️  IMPORTANT:"
    echo "   - This is REAL MONEY trading"
    echo "   - Monitor closely for first few hours"
    echo "   - Read LIVE_TRADING_CHECKLIST.md"
    echo "   - Know emergency stop: pkill -9 -f 'python.*bot/run.py'"
    echo ""
    exit 0
else
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                                                                      ║${NC}"
    echo -e "${RED}║                    ❌ SOME CHECKS FAILED                             ║${NC}"
    echo -e "${RED}║                                                                      ║${NC}"
    echo -e "${RED}║              DO NOT START LIVE TRADING YET!                          ║${NC}"
    echo -e "${RED}║                                                                      ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Please fix the failed checks above before starting live trading."
    echo ""
    echo "For help, see:"
    echo "  - LIVE_TRADING_CHECKLIST.md"
    echo "  - WEBUI_CONTROL_GUIDE.md"
    echo ""
    exit 1
fi
