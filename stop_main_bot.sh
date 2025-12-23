#!/bin/bash
# Stop WorkingBot (Main/Live) - All Components
# Location: /Users/ssr/Projects/WorkingBot/stop_main_bot.sh

PROJECT_DIR="/Users/ssr/Projects/WorkingBot"

echo "=========================================="
echo "  Stopping WorkingBot (LIVE TRADING)"
echo "=========================================="
echo ""

# Stop Trading Bot
echo "🤖 Stopping Trading Bot..."
pkill -f "$PROJECT_DIR/bot/run.py" && echo "   ✅ Trading Bot stopped" || echo "   ℹ️  Trading Bot not running"

# Stop Guardian Bot via LaunchAgent
echo "🛡️  Stopping Guardian Bot..."
if launchctl list | grep -q "com.gridbot.guardian"; then
    launchctl stop com.gridbot.guardian
    launchctl unload ~/Library/LaunchAgents/com.gridbot.guardian.plist 2>/dev/null
    echo "   ✅ Guardian Bot stopped (LaunchAgent unloaded)"
else
    # Fallback to process kill
    pkill -f "$PROJECT_DIR/bot/guardian/guardian_bot.py" && echo "   ✅ Guardian Bot stopped" || echo "   ℹ️  Guardian Bot not running"
fi

# Stop WebUI
echo "🌐 Stopping WebUI..."
launchctl stop com.gridbot.webui 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist 2>/dev/null && echo "   ✅ WebUI stopped" || echo "   ℹ️  WebUI not running"

# Wait for graceful shutdown
sleep 2

# Force kill if needed
if pgrep -f "$PROJECT_DIR" > /dev/null; then
    echo "⚠️  Force killing remaining processes..."
    pkill -9 -f "$PROJECT_DIR/bot"
    pkill -9 -f "$PROJECT_DIR/webui"
fi

# Clean lock files
echo "🧹 Cleaning lock files..."
cd "$PROJECT_DIR"
rm -f .bot_instance*.lock .heartbeat .webui_instance.lock

echo ""
echo "=========================================="
echo "  WorkingBot Stopped Successfully!"
echo "=========================================="
echo ""

# Verify
REMAINING=$(ps aux | grep "$PROJECT_DIR" | grep python | grep -v grep | wc -l)
if [ "$REMAINING" -eq 0 ]; then
    echo "✅ All processes stopped"
else
    echo "⚠️  Warning: $REMAINING process(es) still running:"
    ps aux | grep "$PROJECT_DIR" | grep python | grep -v grep | awk '{print "   •", $2, $11, $12, $13}'
fi
