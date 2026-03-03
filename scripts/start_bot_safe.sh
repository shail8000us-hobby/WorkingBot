#!/bin/bash
# Updated Start Script with Fixed WebUI
# Location: /Users/ssr/Projects/WorkingBot/start_bot_safe.sh

set -e

PROJECT_DIR="/Users/ssr/Projects/WorkingBot"
cd "$PROJECT_DIR"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Safe Start: WorkingBot (LIVE)                                 ║"
echo "╔════════════════════════════════════════════════════════════════╗"
echo ""

# Check WebUI
echo "🌐 Checking WebUI..."
if launchctl list | grep -q "com.gridbot.webui"; then
    WEBUI_PID=$(launchctl list | grep "com.gridbot.webui" | awk '{print $1}')
    if [ "$WEBUI_PID" != "-" ] && [ -n "$WEBUI_PID" ]; then
        echo "   ✅ WebUI running (PID: $WEBUI_PID)"
    else
        echo "   ⚠️  WebUI LaunchAgent loaded but not running"
        echo "   Starting WebUI..."
        launchctl start com.gridbot.webui
        sleep 3
    fi
else
    echo "   ⚠️  WebUI LaunchAgent not loaded"
    echo "   Loading and starting WebUI..."
    launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist
    sleep 3
fi

# Check Guardian
echo "🛡️  Checking Guardian..."
if launchctl list | grep -q "com.gridbot.guardian"; then
    GUARDIAN_PID=$(launchctl list | grep "com.gridbot.guardian" | awk '{print $1}')
    if [ "$GUARDIAN_PID" != "-" ] && [ -n "$GUARDIAN_PID" ]; then
        echo "   ✅ Guardian running (PID: $GUARDIAN_PID)"
    else
        echo "   ⚠️  Guardian LaunchAgent loaded but not running"
        echo "   Starting Guardian..."
        launchctl start com.gridbot.guardian
        sleep 2
    fi
else
    echo "   ⚠️  Guardian LaunchAgent not loaded"
    if [ -f com.gridbot.guardian.plist ]; then
        echo "   Installing and starting Guardian..."
        cp com.gridbot.guardian.plist ~/Library/LaunchAgents/
        chmod 644 ~/Library/LaunchAgents/com.gridbot.guardian.plist
        launchctl load ~/Library/LaunchAgents/com.gridbot.guardian.plist
        sleep 2
    else
        echo "   ❌ Guardian plist not found!"
    fi
fi

# Check Trading Bot
echo "🤖 Checking Trading Bot..."
if pgrep -f "$PROJECT_DIR/bot/run.py" > /dev/null; then
    BOT_PID=$(pgrep -f "$PROJECT_DIR/bot/run.py")
    echo "   ✅ Trading Bot running (PID: $BOT_PID)"
else
    echo "   ⚠️  Trading Bot not running"
    read -p "   Start Trading Bot? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "   Starting Trading Bot..."
        nohup python3 -m bot.run > bot.log 2>&1 &
        BOT_PID=$!
        echo "   ✅ Trading Bot started (PID: $BOT_PID)"
    fi
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Status Summary                                                 ║"
echo "╔════════════════════════════════════════════════════════════════╗"
echo ""

./check_instance_status.sh

echo ""
echo "🌐 WebUI: http://localhost:5555"
echo "📝 Logs:"
echo "   • WebUI: tail -f logs/launchagent_webui.log"
echo "   • Guardian: tail -f logs/guardian_launchd.log"
echo "   • Bot: tail -f bot.log"
