#!/bin/bash
# Start WorkingBot (Main/Live) - All Components
# Location: /Users/ssr/Projects/WorkingBot/start_main_bot.sh

set -e

PROJECT_DIR="/Users/ssr/Projects/WorkingBot"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  Starting WorkingBot (LIVE TRADING)"
echo "=========================================="
echo ""

# Check if trading bot already running
if pgrep -f "$PROJECT_DIR/bot/run.py" > /dev/null; then
    echo "❌ Trading bot already running!"
    echo "   Use stop_main_bot.sh first"
    exit 1
fi

# Check if WebUI already running (LaunchAgent or manual)
if launchctl list | grep -q "com.gridbot.webui"; then
    echo "⚠️  WebUI LaunchAgent already loaded"
    if lsof -i :5555 > /dev/null 2>&1; then
        echo "❌ WebUI already running on port 5555!"
        echo "   Stop it first: launchctl stop com.gridbot.webui"
        exit 1
    fi
fi

# Check if Guardian already running
if launchctl list | grep -q "com.gridbot.guardian"; then
    GUARDIAN_STATUS=$(launchctl list | grep "com.gridbot.guardian" | awk '{print $1}')
    if [ "$GUARDIAN_STATUS" != "-" ]; then
        echo "✅ Guardian already running (PID: $GUARDIAN_STATUS)"
        GUARDIAN_RUNNING=1
    else
        echo "⚠️  Guardian LaunchAgent loaded but not running"
        GUARDIAN_RUNNING=0
    fi
else
    GUARDIAN_RUNNING=0
fi

# Clean old locks (only if processes truly dead)
echo "🧹 Cleaning old lock files..."
rm -f .bot_instance*.lock .heartbeat .webui_instance*.lock

# Start WebUI via LaunchAgent
echo "🌐 Starting WebUI on port 5555..."
launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist
sleep 3

# Verify WebUI
if lsof -i :5555 > /dev/null 2>&1; then
    echo "   ✅ WebUI started on port 5555"
else
    echo "   ⚠️  WebUI may not be running, check logs"
fi

# Start Trading Bot
echo "🤖 Starting Trading Bot..."
nohup python3 -m bot.run > bot.log 2>&1 &
BOT_PID=$!
echo "   ✅ Trading Bot started (PID: $BOT_PID)"
sleep 2

# Start Guardian Bot via LaunchAgent (if not already running)
if [ $GUARDIAN_RUNNING -eq 0 ]; then
    echo "🛡️  Starting Guardian Bot via LaunchAgent..."
    
    # Check if plist exists
    if [ ! -f ~/Library/LaunchAgents/com.gridbot.guardian.plist ]; then
        echo "   📝 Installing Guardian LaunchAgent..."
        cp com.gridbot.guardian.plist ~/Library/LaunchAgents/
        chmod 644 ~/Library/LaunchAgents/com.gridbot.guardian.plist
    fi
    
    # Load and start
    launchctl load ~/Library/LaunchAgents/com.gridbot.guardian.plist 2>/dev/null || true
    launchctl start com.gridbot.guardian
    sleep 2
    
    # Verify
    if launchctl list | grep -q "com.gridbot.guardian"; then
        GUARDIAN_PID=$(launchctl list | grep "com.gridbot.guardian" | awk '{print $1}')
        echo "   ✅ Guardian Bot started (PID: $GUARDIAN_PID)"
    else
        echo "   ⚠️  Guardian may not have started, check logs/guardian_launchd_error.log"
    fi
else
    echo "🛡️  Guardian Bot already running - skipping"
fi

echo ""
echo "=========================================="
echo "  WorkingBot Started Successfully!"
echo "=========================================="
echo ""
echo "📊 Status:"
ps aux | grep "$PROJECT_DIR" | grep python | grep -v grep | awk '{print "   •", $2, $11, $12, $13}'
echo ""
echo "🌐 WebUI: http://localhost:5555"
echo "📝 Logs:"
echo "   • Bot: $PROJECT_DIR/bot.log"
echo "   • Guardian: $PROJECT_DIR/logs/guardian.log"
echo "   • WebUI: $PROJECT_DIR/logs/launchagent_webui.log"
echo ""
echo "🛑 To stop: ./stop_main_bot.sh"
