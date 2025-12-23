#!/bin/bash
# Hot Reload Test Script
# Tests if volatility parameters update instantly without restarting the bot

set -e

CONFIG_FILE="/Users/shailendrasinghrajawat/Projects/WorkingBot/grid_config.env"
LOG_FILE="/Users/shailendrasinghrajawat/Projects/WorkingBot/logs/bot_live.log"
BACKUP_FILE="/tmp/grid_config.env.backup"

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                    🔥 HOT RELOAD TEST SCRIPT 🔥                          ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Backup current config
echo "📋 Creating backup of current config..."
cp "$CONFIG_FILE" "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"
echo ""

# Get current values
echo "📊 Current values in config:"
grep "^VOLATILITY_MAX_IV=" "$CONFIG_FILE" || echo "VOLATILITY_MAX_IV not found"
grep "^VOLATILITY_MAX_RV=" "$CONFIG_FILE" || echo "VOLATILITY_MAX_RV not found"
grep "^VOLATILITY_MAX_SPREAD=" "$CONFIG_FILE" || echo "VOLATILITY_MAX_SPREAD not found"
echo ""

# Change value 1: MAX_IV
echo "🔄 TEST 1: Changing VOLATILITY_MAX_IV from 35 to 50..."
sed -i.tmp 's/^VOLATILITY_MAX_IV=.*/VOLATILITY_MAX_IV=50/' "$CONFIG_FILE"
rm -f "${CONFIG_FILE}.tmp"
echo "✅ Config updated! Waiting for hot reload..."
echo ""

# Monitor logs for 10 seconds
echo "👀 Monitoring logs for hot reload message..."
echo "   (Looking for: 'HOT RELOAD' or 'MAX_IV')"
echo ""
timeout 10 tail -f "$LOG_FILE" | grep --line-buffered -i "hot reload\|max_iv.*→" &
LOG_PID=$!

sleep 12
kill $LOG_PID 2>/dev/null || true
echo ""

# Change value 2: MAX_RV
echo "🔄 TEST 2: Changing VOLATILITY_MAX_RV from 40 to 60..."
sed -i.tmp 's/^VOLATILITY_MAX_RV=.*/VOLATILITY_MAX_RV=60/' "$CONFIG_FILE"
rm -f "${CONFIG_FILE}.tmp"
echo "✅ Config updated! Waiting for hot reload..."
echo ""

echo "👀 Monitoring logs for hot reload message..."
timeout 10 tail -f "$LOG_FILE" | grep --line-buffered -i "hot reload\|max_rv.*→" &
LOG_PID=$!

sleep 12
kill $LOG_PID 2>/dev/null || true
echo ""

# Change value 3: MAX_SPREAD
echo "🔄 TEST 3: Changing VOLATILITY_MAX_SPREAD from 10 to 15..."
sed -i.tmp 's/^VOLATILITY_MAX_SPREAD=.*/VOLATILITY_MAX_SPREAD=15/' "$CONFIG_FILE"
rm -f "${CONFIG_FILE}.tmp"
echo "✅ Config updated! Waiting for hot reload..."
echo ""

echo "👀 Monitoring logs for hot reload message..."
timeout 10 tail -f "$LOG_FILE" | grep --line-buffered -i "hot reload\|max_spread.*→" &
LOG_PID=$!

sleep 12
kill $LOG_PID 2>/dev/null || true
echo ""

# Restore original config
echo "🔙 Restoring original config..."
mv "$BACKUP_FILE" "$CONFIG_FILE"
echo "✅ Config restored!"
echo ""

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                         TEST COMPLETED                                   ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📝 Summary:"
echo "   - Changed VOLATILITY_MAX_IV: 35 → 50 → 35"
echo "   - Changed VOLATILITY_MAX_RV: 40 → 60 → 40"
echo "   - Changed VOLATILITY_MAX_SPREAD: 10 → 15 → 10"
echo ""
echo "🔍 Check the output above for '🔥 INSTANT HOT RELOAD' messages"
echo "   If you see them, hot reload is working!"
echo ""
echo "💡 You can also check recent logs manually:"
echo "   tail -50 $LOG_FILE | grep -i 'hot reload'"
echo ""
