#!/bin/bash
# Phase 1 Deployment Script
# November 9, 2025

echo "🚀 PHASE 1 DEPLOYMENT - All Fixes"
echo "=================================="
echo ""

# Step 1: Import tests
echo "📦 Step 1: Import Tests"
python3 -c "from bot.strategy.modules.fill_audit_log import FillAuditLog; print('  ✅ fill_audit_log')" || exit 1
python3 -c "from bot.strategy.modules.order_manager import OrderManager; print('  ✅ order_manager')" || exit 1
python3 -c "from bot.strategy.handlers.long_handler import LongFillHandler; print('  ✅ long_handler')" || exit 1
python3 -c "from bot.strategy.gridbot import GridBot; print('  ✅ gridbot')" || exit 1
echo ""

# Step 2: Syntax checks
echo "🔍 Step 2: Syntax Checks"
python3 -m py_compile bot/strategy/modules/fill_audit_log.py || exit 1
python3 -m py_compile bot/strategy/modules/order_manager.py || exit 1
python3 -m py_compile bot/strategy/handlers/long_handler.py || exit 1
python3 -m py_compile bot/strategy/gridbot.py || exit 1
echo "  ✅ All syntax checks passed"
echo ""

# Step 3: Kill existing bot
echo "🛑 Step 3: Stopping Existing Bot"
BOT_PID=$(ps aux | grep bot_launcher | grep -v grep | awk '{print $2}')
if [ -n "$BOT_PID" ]; then
    echo "  Found bot process: $BOT_PID"
    kill $BOT_PID
    sleep 2
    echo "  ✅ Bot stopped"
else
    echo "  ℹ️  No bot running"
fi
echo ""

# Step 4: Start bot
echo "🚀 Step 4: Starting Bot with New Code"
echo "  Command: python3 bot_launcher.py --mode live"
echo ""
echo "📋 What to monitor in logs:"
echo "  - 🐕 Watchdog started"
echo "  - 🛡️ TP placed with retry"
echo "  - 📝 Updated audit log"
echo "  - 📅 Scheduled next grid order (if throttled)"
echo ""
echo "To monitor: tail -f bot/logs/bot.log | grep -E 'Watchdog|TP placed|audit log|RETRY|THROTTLE'"
echo ""
echo "Ready to start? Run: python3 bot_launcher.py --mode live"
