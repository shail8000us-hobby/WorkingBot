#!/bin/bash
# Start Async GridBot (Phase 2+3 Production)
# Default mode after cutover

echo "╔════════════════════════════════════════════════════════╗"
echo "║      🚀 Starting Async GridBot (Production)            ║"
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
echo "🚀 Starting Async GridBot..."
echo ""

# Ensure async mode (default, but explicit)
export USE_ASYNC_BOT=true
unset USE_LEGACY_BOT

# Start async bot
cd /Users/ssr/Projects/WorkingBot
nohup python3 -m bot.run > bot_live.log 2>&1 &
ASYNC_PID=$!

sleep 3

# Check if started successfully
if ps -p $ASYNC_PID > /dev/null 2>&1; then
    echo "✅ Async bot started successfully"
    echo "   PID: $ASYNC_PID"
    echo "   Mode: Async (Phase 2+3)"
    echo "   Log: bot_live.log"
    echo ""
    echo "Monitor with:"
    echo "  tail -f bot_live.log"
    echo ""
    echo "Check status:"
    echo "  grep -i 'asyncgridbot\|actor\|saga' bot_live.log | tail -10"
    echo ""
    echo "Emergency rollback:"
    echo "  ./rollback_to_legacy.sh"
else
    echo "❌ Failed to start async bot"
    echo "   Check logs: tail -50 bot_live.log"
    echo ""
    echo "Rollback to legacy:"
    echo "   ./rollback_to_legacy.sh"
    exit 1
fi
