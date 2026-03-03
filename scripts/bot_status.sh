#!/bin/bash
# Quick Bot Status Check
# Shows current running bot instances and their health

echo "╔════════════════════════════════════════════════════════╗"
echo "║            🤖 Bot Status Report                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check bot.run instances
BOT_COUNT=$(ps -ef | grep "[P]ython.*bot.run" | wc -l | tr -d ' ')
echo "📊 Running bot.run instances: $BOT_COUNT"

if [ "$BOT_COUNT" -gt 0 ]; then
    echo ""
    ps -ef | grep "[P]ython.*bot.run" | awk '{printf "   PID: %s\n   CMD: %s\n", $2, substr($0, index($0,$8))}'
    echo ""
    
    # Check if it's async mode
    if grep -q "AsyncGridBot.*started successfully" bot_live.log 2>/dev/null; then
        echo "✅ Mode: ASYNC (Phase 2+3)"
    elif grep -q "WebSocket GridBot" bot_live.log 2>/dev/null; then
        echo "⚠️  Mode: LEGACY (Threaded)"
    else
        echo "❓ Mode: Unknown"
    fi
    
    # Check WebSocket status
    echo ""
    if tail -20 bot_live.log 2>/dev/null | grep -q "WebSocket connected successfully"; then
        echo "✅ WebSocket: Connected"
    elif tail -50 bot_live.log 2>/dev/null | grep -q "WebSocket connected successfully"; then
        echo "✅ WebSocket: Connected (earlier)"
    else
        echo "❌ WebSocket: Not connected or failed"
    fi
    
    # Check for recent activity
    echo ""
    RECENT_TICKER=$(tail -10 bot_live.log 2>/dev/null | grep -c "v2/ticker")
    if [ "$RECENT_TICKER" -gt 0 ]; then
        echo "✅ Activity: Receiving ticker updates ($RECENT_TICKER in last 10 lines)"
    else
        echo "⚠️  Activity: No recent ticker updates"
    fi
    
    # Check for errors
    echo ""
    ERROR_COUNT=$(tail -50 bot_live.log 2>/dev/null | grep -c "ERROR")
    if [ "$ERROR_COUNT" -eq 0 ]; then
        echo "✅ Errors: None in last 50 lines"
    else
        echo "⚠️  Errors: $ERROR_COUNT in last 50 lines"
        tail -50 bot_live.log 2>/dev/null | grep "ERROR" | tail -3
    fi
    
    # Show actor status
    echo ""
    if tail -20 bot_live.log 2>/dev/null | grep -q "actor.*Message loop started"; then
        echo "✅ Actors: Running"
    elif tail -50 bot_live.log 2>/dev/null | grep -q "actor.*Message loop started"; then
        echo "✅ Actors: Started (earlier)"
    else
        echo "❓ Actors: Status unknown"
    fi
    
else
    echo ""
    echo "❌ No bot.run instances running"
    echo ""
    echo "To start async bot:"
    echo "   ./clean_start_async.sh"
fi

# Check for other bot processes
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Other bot processes:"
OTHER=$(ps -ef | grep "[P]ython.*bot" | grep -v "bot.run" | wc -l | tr -d ' ')
if [ "$OTHER" -gt 0 ]; then
    ps -ef | grep "[P]ython.*bot" | grep -v "bot.run" | awk '{printf "   %s: %s\n", $2, substr($0, index($0,$8))}'
else
    echo "   None"
fi

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║            📝 Quick Commands                           ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "Monitor logs:      tail -f bot_live.log"
echo "Check process:     ps -p $BOT_COUNT -o pid,etime,command"
echo "Stop bot:          pkill -f bot.run"
echo "Restart async:     ./clean_start_async.sh"
echo "Rollback legacy:   ./rollback_to_legacy.sh"
echo ""
