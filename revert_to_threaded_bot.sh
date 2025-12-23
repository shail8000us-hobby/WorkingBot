#!/bin/bash
# Revert to Threaded GridBot (Emergency Fallback)
# Created: November 12, 2025
# Reason: Async bot missing order entry logic

set -e

echo "🔄 Reverting to Threaded GridBot..."
echo ""
echo "Reason: Async bot is missing initial order placement logic"
echo "Issue: Bot connects but never places any orders"
echo "See: ASYNC_BOT_NO_ORDERS_ANALYSIS_NOV12_2025.md"
echo ""

# Set environment to use legacy threaded bot
export USE_ASYNC_BOT=false

echo "✅ Environment configured for threaded bot"
echo ""
echo "Starting bot in legacy mode..."
echo ""

# Start bot with threaded mode
cd /Users/ssr/Projects/WorkingBot
python -m bot.run

echo ""
echo "✅ Bot started in THREADED mode"
echo ""
echo "Next Steps:"
echo "1. Monitor bot for order placement"
echo "2. Fix async bot order entry logic"
echo "3. Test async bot in shadow mode"
echo "4. Re-cutover when fixed and validated"
