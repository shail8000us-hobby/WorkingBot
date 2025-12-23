#!/bin/bash
# Emergency Rollback to Legacy Threaded GridBot
# Use this if async bot has critical issues

echo "╔════════════════════════════════════════════════════════╗"
echo "║      🔄 Rolling Back to Legacy Threaded Bot            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Find current bot PID
BOT_PID=$(pgrep -f "bot.run" | head -1)

if [ -n "$BOT_PID" ]; then
    echo "🛑 Stopping current bot (PID: $BOT_PID)..."
    kill -SIGTERM $BOT_PID
    sleep 3
    
    # Force kill if still running
    if ps -p $BOT_PID > /dev/null 2>&1; then
        echo "   Force stopping..."
        kill -9 $BOT_PID
    fi
    echo "✅ Bot stopped"
else
    echo "ℹ️  No bot currently running"
fi

echo ""
echo "🔄 Starting legacy threaded bot..."
echo ""

# Set environment variable for legacy mode
export USE_LEGACY_BOT=true

# Start legacy bot
cd /Users/ssr/Projects/WorkingBot
nohup python3 -m bot.run > bot_live.log 2>&1 &
LEGACY_PID=$!

sleep 2

# Check if started successfully
if ps -p $LEGACY_PID > /dev/null 2>&1; then
    echo "✅ Legacy bot started successfully"
    echo "   PID: $LEGACY_PID"
    echo "   Log: bot_live.log"
    echo ""
    echo "Monitor with: tail -f bot_live.log"
    echo ""
    echo "To switch back to async: unset USE_LEGACY_BOT && ./bot_command_center.sh restart"
else
    echo "❌ Failed to start legacy bot"
    echo "   Check logs: tail -50 bot_live.log"
    exit 1
fi
