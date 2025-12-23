#!/bin/bash
# Kill ALL bot instances and restart in async mode
# Comprehensive cleanup of all bot-related processes

echo "╔════════════════════════════════════════════════════════╗"
echo "║     🧹 Cleaning Up All Bot Instances                  ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Kill all bot.run processes
echo "🛑 Stopping bot.run processes..."
pkill -f "bot.run" 2>/dev/null && echo "   ✅ Killed bot.run processes" || echo "   ℹ️  No bot.run processes found"

# Kill PM2 managed bots if any
echo "🛑 Stopping PM2 managed bots..."
pm2 delete gridbot-live 2>/dev/null && echo "   ✅ Stopped PM2 gridbot-live" || echo "   ℹ️  No PM2 gridbot-live"
pm2 delete gridbot-demo 2>/dev/null && echo "   ✅ Stopped PM2 gridbot-demo" || echo "   ℹ️  No PM2 gridbot-demo"

# Kill shadow mode processes
echo "🛑 Stopping shadow mode processes..."
pkill -f "migrate_to_async" 2>/dev/null && echo "   ✅ Killed shadow mode" || echo "   ℹ️  No shadow mode running"
pkill -f "shadow_mode" 2>/dev/null && echo "   ✅ Killed shadow mode scripts" || echo "   ℹ️  No shadow mode scripts"

# Kill any Python processes with 'grid' in command
echo "🛑 Stopping grid-related Python processes..."
pkill -f "python.*grid" 2>/dev/null && echo "   ✅ Killed grid processes" || echo "   ℹ️  No grid processes"

# Clean up stale PID files
echo "🧹 Cleaning stale PID files..."
rm -f /Users/ssr/Projects/WorkingBot/.pids/shadow_mode.pid 2>/dev/null
rm -f /Users/ssr/Projects/WorkingBot/.pids/trading.pid 2>/dev/null
rm -f /Users/ssr/Projects/WorkingBot/.pids/reconciliation.pid 2>/dev/null
rm -f /Users/ssr/Projects/WorkingBot/reports/bot.pid 2>/dev/null
echo "   ✅ Cleaned PID files"

# Wait for processes to terminate
echo ""
echo "⏳ Waiting for processes to terminate..."
sleep 3

# Verify all stopped
REMAINING=$(ps aux | grep -E "python.*bot.*run|gridbot|shadow_mode" | grep -v grep | grep -v "pm2 logs" | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "⚠️  Warning: $REMAINING bot processes still running"
    ps aux | grep -E "python.*bot.*run|gridbot|shadow_mode" | grep -v grep | grep -v "pm2 logs"
    echo ""
    echo "Force killing remaining processes..."
    pkill -9 -f "bot.run" 2>/dev/null
    pkill -9 -f "gridbot" 2>/dev/null
    sleep 2
fi

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║     🚀 Starting Async GridBot                          ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Ensure we're using async mode
export USE_ASYNC_BOT=true
unset USE_LEGACY_BOT

# Start async bot
cd /Users/ssr/Projects/WorkingBot
nohup python3 -m bot.run > bot_live.log 2>&1 &
BOT_PID=$!

sleep 3

# Verify bot started
if ps -p $BOT_PID > /dev/null 2>&1; then
    echo "✅ Async GridBot started successfully"
    echo "   PID: $BOT_PID"
    echo "   Mode: Async (Phase 2+3)"
    echo "   Log: bot_live.log"
    echo ""
    
    # Show initial startup messages
    echo "📋 Startup log (last 15 lines):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    tail -15 bot_live.log | grep -E "AsyncGridBot|actor|WebSocket|connected" || tail -15 bot_live.log
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    echo "📊 Monitor with:"
    echo "   tail -f bot_live.log"
    echo ""
    echo "🔍 Check status:"
    echo "   ps aux | grep bot.run | grep -v grep"
    echo ""
    echo "⚠️  Emergency rollback:"
    echo "   ./rollback_to_legacy.sh"
    echo ""
else
    echo "❌ Failed to start async bot"
    echo ""
    echo "📋 Last 30 log lines:"
    tail -30 bot_live.log
    echo ""
    echo "Rollback to legacy:"
    echo "   ./rollback_to_legacy.sh"
    exit 1
fi

# Final verification
echo "✅ Verification:"
ASYNC_RUNNING=$(ps aux | grep "python.*bot.run" | grep -v grep | wc -l)
echo "   Async bot instances: $ASYNC_RUNNING (should be 1)"

if [ "$ASYNC_RUNNING" -eq 1 ]; then
    echo ""
    echo "🎉 Success! Single async bot instance running cleanly."
elif [ "$ASYNC_RUNNING" -gt 1 ]; then
    echo ""
    echo "⚠️  Warning: Multiple instances detected!"
    ps aux | grep "python.*bot.run" | grep -v grep
else
    echo ""
    echo "❌ Error: No bot running!"
fi
