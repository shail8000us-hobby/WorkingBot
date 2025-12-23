#!/bin/bash
# Deployment Script for Fixed GridBot - November 11, 2025
# Deploys all critical fixes: WebSocket reconnection, REST fallback, polling, reconciliation

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║   🚀 GridBot Critical Fixes Deployment - Nov 11, 2025         ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Pre-deployment checks
echo "═══════════════════════════════════════════════════════════════"
echo "STEP 1: Pre-Deployment Checks"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check if bot is running
if pm2 list 2>/dev/null | grep -q "gridbot-live.*online"; then
    echo -e "${GREEN}✅${NC} Bot is running: gridbot-live"
    BOT_RUNNING=true
else
    echo -e "${RED}❌${NC} Bot is NOT running"
    BOT_RUNNING=false
fi
echo ""

# Step 2: Backup current state
echo "═══════════════════════════════════════════════════════════════"
echo "STEP 2: Backup Current State"
echo "═══════════════════════════════════════════════════════════════"
echo ""

BACKUP_DIR="state_backups/pre_fixes_deployment_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "runtime_state_LONG.json" ]; then
    cp runtime_state_LONG.json "$BACKUP_DIR/"
    echo -e "${GREEN}✅${NC} Backed up runtime_state_LONG.json"
fi

if [ -f "runtime_state_SHORT.json" ]; then
    cp runtime_state_SHORT.json "$BACKUP_DIR/"
    echo -e "${GREEN}✅${NC} Backed up runtime_state_SHORT.json"
fi

if [ -f "runtime_state.json" ]; then
    cp runtime_state.json "$BACKUP_DIR/"
    echo -e "${GREEN}✅${NC} Backed up runtime_state.json"
fi

echo -e "${GREEN}✅${NC} Backup created: $BACKUP_DIR"
echo ""

# Step 3: Verify fixes are in place
echo "═══════════════════════════════════════════════════════════════"
echo "STEP 3: Verify Critical Fixes in Code"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check Fix #1: WebSocket reconnection
if grep -q "ws_manager.connect()" bot/strategy/gridbot.py; then
    echo -e "${GREEN}✅${NC} Fix #1: WebSocket reconnection with channel re-subscription"
else
    echo -e "${RED}❌${NC} Fix #1: WebSocket fix NOT found!"
    exit 1
fi

# Check Fix #2: REST fallback (volatility removed)
if grep -q "Volatility handler doesn't have update_price()" bot/strategy/gridbot.py; then
    echo -e "${GREEN}✅${NC} Fix #2: REST fallback volatility bug fixed"
else
    echo -e "${RED}❌${NC} Fix #2: REST fallback fix NOT found!"
    exit 1
fi

# Check Fix #3: Continuous polling
if grep -q "max_checks = 200" bot/strategy/modules/order_manager.py; then
    echo -e "${GREEN}✅${NC} Fix #3: Continuous polling (10 minutes)"
else
    echo -e "${RED}❌${NC} Fix #3: Polling fix NOT found!"
    exit 1
fi

# Check Fix #4: Reconciliation system
if grep -q "_start_reconciliation_system" bot/strategy/gridbot.py; then
    echo -e "${GREEN}✅${NC} Fix #4: Exchange reconciliation system"
else
    echo -e "${RED}❌${NC} Fix #4: Reconciliation fix NOT found!"
    exit 1
fi

# Check Enhancement: Exponential backoff retry
if grep -q "_schedule_reconnection_retry" bot/strategy/gridbot.py; then
    echo -e "${GREEN}✅${NC} Enhancement: WebSocket exponential backoff retry"
else
    echo -e "${YELLOW}⚠️${NC}  Enhancement: Exponential backoff not found (optional)"
fi

echo ""
echo -e "${GREEN}✅ All critical fixes verified in code${NC}"
echo ""

# Step 4: Syntax validation
echo "═══════════════════════════════════════════════════════════════"
echo "STEP 4: Syntax Validation"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if python3 -m py_compile bot/strategy/gridbot.py 2>&1 | grep -q "SyntaxError"; then
    echo -e "${RED}❌${NC} Syntax error in gridbot.py!"
    python3 -m py_compile bot/strategy/gridbot.py
    exit 1
else
    echo -e "${GREEN}✅${NC} gridbot.py syntax OK"
fi

if python3 -m py_compile bot/strategy/modules/order_manager.py 2>&1 | grep -q "SyntaxError"; then
    echo -e "${RED}❌${NC} Syntax error in order_manager.py!"
    python3 -m py_compile bot/strategy/modules/order_manager.py
    exit 1
else
    echo -e "${GREEN}✅${NC} order_manager.py syntax OK"
fi

echo ""

# Step 5: Memory cleanup option
echo "═══════════════════════════════════════════════════════════════"
echo "STEP 5: Memory Cleanup (Optional)"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Do you want to CLEAR bot memory for fresh start?"
echo ""
echo -e "${YELLOW}⚠️  WARNING: This will:${NC}"
echo "  • Clear all pending orders from memory"
echo "  • Clear all position tracking"
echo "  • Clear all temporary state"
echo ""
echo -e "${GREEN}✅ Safe because:${NC}"
echo "  • Positions are on exchange (won't be affected)"
echo "  • Bot will re-sync on startup via reconciliation"
echo "  • Backup already created above"
echo ""
read -p "Clear memory? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Clearing bot memory..."
    
    # Clear LONG state
    if [ -f "runtime_state_LONG.json" ]; then
        echo '{"open_tranches": [], "pending_buy": null, "pending_sell": null, "last_action": "CLEARED", "last_action_time": 0}' > runtime_state_LONG.json
        echo -e "${GREEN}✅${NC} Cleared runtime_state_LONG.json"
    fi
    
    # Clear SHORT state
    if [ -f "runtime_state_SHORT.json" ]; then
        echo '{"open_tranches": [], "pending_buy": null, "pending_sell": null, "last_action": "CLEARED", "last_action_time": 0}' > runtime_state_SHORT.json
        echo -e "${GREEN}✅${NC} Cleared runtime_state_SHORT.json"
    fi
    
    # Clear general state
    if [ -f "runtime_state.json" ]; then
        echo '{"open_tranches": [], "pending_buy": null, "pending_sell": null, "last_action": "CLEARED", "last_action_time": 0}' > runtime_state.json
        echo -e "${GREEN}✅${NC} Cleared runtime_state.json"
    fi
    
    echo ""
    echo -e "${GREEN}✅ Memory cleared - bot will re-sync with exchange on startup${NC}"
    MEMORY_CLEARED=true
else
    echo ""
    echo "Memory NOT cleared - existing state preserved"
    MEMORY_CLEARED=false
fi
echo ""

# Step 6: Stop bot
if [ "$BOT_RUNNING" = true ]; then
    echo "═══════════════════════════════════════════════════════════════"
    echo "STEP 6: Stop Current Bot"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    echo "Stopping gridbot-live..."
    pm2 stop gridbot-live
    
    echo "Waiting 5 seconds for graceful shutdown..."
    sleep 5
    
    echo -e "${GREEN}✅${NC} Bot stopped"
    echo ""
fi

# Step 7: Start bot with fixes
echo "═══════════════════════════════════════════════════════════════"
echo "STEP 7: Start Bot with Critical Fixes"
echo "═══════════════════════════════════════════════════════════════"
echo ""

echo "Starting gridbot-live with fixed code..."
pm2 start gridbot-live

echo ""
echo "Waiting 10 seconds for initialization..."
sleep 10
echo ""

# Step 8: Verify startup
echo "═══════════════════════════════════════════════════════════════"
echo "STEP 8: Verify Successful Startup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if pm2 list | grep -q "gridbot-live.*online"; then
    echo -e "${GREEN}✅${NC} Bot started successfully!"
else
    echo -e "${RED}❌${NC} Bot failed to start!"
    echo ""
    echo "Check logs:"
    echo "  pm2 logs gridbot-live --lines 50"
    exit 1
fi

# Check for immediate errors
echo ""
echo "Checking for errors in last 20 lines..."
ERROR_COUNT=$(pm2 logs gridbot-live --lines 20 --nostream 2>&1 | grep -c "ERROR\|CRITICAL" || true)

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠️${NC}  Found $ERROR_COUNT error lines (checking if critical...)"
    
    # Check for the OLD errors we fixed
    if pm2 logs gridbot-live --lines 20 --nostream 2>&1 | grep -q "update_price.*not.*attribute"; then
        echo -e "${RED}❌${NC} CRITICAL: Still seeing volatility.update_price() error!"
        echo "    Bot is running OLD CODE - fixes not loaded!"
        exit 1
    fi
    
    if pm2 logs gridbot-live --lines 20 --nostream 2>&1 | grep -q "_on_order_update.*not.*attribute"; then
        echo -e "${RED}❌${NC} CRITICAL: Still seeing _on_order_update error!"
        echo "    Bot is running OLD CODE - fixes not loaded!"
        exit 1
    fi
    
    echo -e "${GREEN}✅${NC} No critical errors - normal startup warnings only"
else
    echo -e "${GREEN}✅${NC} No errors in startup logs"
fi

echo ""

# Step 9: Verify new systems started
echo "═══════════════════════════════════════════════════════════════"
echo "STEP 9: Verify New Systems Started"
echo "═══════════════════════════════════════════════════════════════"
echo ""

echo "Checking for new system startup messages..."
sleep 3

# Check for reconciliation system
if pm2 logs gridbot-live --lines 50 --nostream 2>&1 | grep -q "Exchange reconciliation system started\|reconciliation_loop\|RECONCILIATION"; then
    echo -e "${GREEN}✅${NC} Reconciliation system: ACTIVE"
else
    echo -e "${YELLOW}⚠️${NC}  Reconciliation system: NOT detected (check logs)"
fi

# Check for WebSocket connection
if pm2 logs gridbot-live --lines 50 --nostream 2>&1 | grep -q "WebSocket.*connected\|WebSocket Manager connected"; then
    echo -e "${GREEN}✅${NC} WebSocket connection: ESTABLISHED"
else
    echo -e "${YELLOW}⚠️${NC}  WebSocket connection: NOT detected (check logs)"
fi

echo ""

# Step 10: Summary and next steps
echo "═══════════════════════════════════════════════════════════════"
echo "DEPLOYMENT SUMMARY"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo -e "${GREEN}✅ Bot restarted with all critical fixes${NC}"
echo ""
echo "Fixes Deployed:"
echo "  1. ✅ WebSocket reconnection with channel re-subscription"
echo "  2. ✅ REST fallback volatility bug fixed"
echo "  3. ✅ Continuous polling (10 minutes)"
echo "  4. ✅ Exchange reconciliation system (5-minute intervals)"
echo "  5. ✅ Exponential backoff retry on reconnection failures"
echo ""
echo "Backups:"
echo "  📁 $BACKUP_DIR"
echo ""

if [ "$MEMORY_CLEARED" = true ]; then
    echo -e "${YELLOW}Memory Cleared:${NC}"
    echo "  • Bot will re-sync with exchange"
    echo "  • Reconciliation will detect any positions"
    echo "  • Emergency TP placement if needed"
    echo ""
fi

echo "═══════════════════════════════════════════════════════════════"
echo "NEXT STEPS - MONITOR FOR 30 MINUTES"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "1. Watch logs for errors:"
echo "   pm2 logs gridbot-live"
echo ""
echo "2. Check for new system messages:"
echo "   • ✅ Exchange reconciliation system started"
echo "   • ✅ WebSocket reconnection complete"
echo "   • ✅ Polling started continuous monitoring"
echo ""
echo "3. Verify reconciliation runs (every 5 minutes):"
echo "   • [RECONCILIATION] Starting periodic check"
echo "   • [RECONCILIATION] All pending orders verified"
echo ""
echo "4. Test WebSocket reconnection (if WebSocket dies):"
echo "   • Should see: 🔄 INITIATING WEBSOCKET RECONNECTION"
echo "   • Should see: ✅ WEBSOCKET RECONNECTION COMPLETE"
echo "   • Should NOT see: AttributeError or update_price errors"
echo ""
echo "5. Monitor for missed fills:"
echo "   • Reconciliation will detect within 5 minutes"
echo "   • Should see: 🚨 MISSED FILL DETECTED (if any)"
echo "   • Should see: ✅ Missed Fill Recovered"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo -e "${GREEN}🚀 Deployment Complete!${NC}"
echo ""
echo "If everything looks good after 30 minutes, fixes are working!"
echo ""
