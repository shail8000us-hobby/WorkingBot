#!/bin/bash
# Clean Restart WorkingBot with New Single-Instance System
# Location: /Users/ssr/Projects/WorkingBot/clean_restart_with_guardian.sh

set -e

PROJECT_DIR="/Users/ssr/Projects/WorkingBot"
cd "$PROJECT_DIR"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Clean Restart with Guardian LaunchAgent                       ║"
echo "╔════════════════════════════════════════════════════════════════╗"
echo ""

# Step 1: Stop everything cleanly
echo "📍 Step 1/5: Stopping all components..."
echo "─────────────────────────────────────────"

# Stop bot
if pgrep -f "$PROJECT_DIR/bot/run.py" > /dev/null; then
    echo "🤖 Stopping Trading Bot..."
    pkill -f "$PROJECT_DIR/bot/run.py"
    sleep 2
else
    echo "🤖 Trading Bot not running"
fi

# Stop guardian (old manual process)
if pgrep -f "$PROJECT_DIR/bot/guardian/guardian_bot.py" > /dev/null; then
    echo "🛡️  Stopping old Guardian process..."
    pkill -f "$PROJECT_DIR/bot/guardian/guardian_bot.py"
    sleep 2
fi

# Stop guardian LaunchAgent if exists
if launchctl list | grep -q "com.gridbot.guardian"; then
    echo "🛡️  Stopping Guardian LaunchAgent..."
    launchctl stop com.gridbot.guardian 2>/dev/null || true
    launchctl unload ~/Library/LaunchAgents/com.gridbot.guardian.plist 2>/dev/null || true
fi

# Stop WebUI
if launchctl list | grep -q "com.gridbot.webui"; then
    echo "🌐 Stopping WebUI LaunchAgent..."
    launchctl stop com.gridbot.webui 2>/dev/null || true
    launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist 2>/dev/null || true
    sleep 3
fi

# Force kill any remaining
echo "🔪 Force killing any remaining processes..."
pkill -9 -f "$PROJECT_DIR/webui/backend/app.py" 2>/dev/null || true
pkill -9 -f "$PROJECT_DIR/bot/guardian" 2>/dev/null || true
sleep 2

echo "✅ All components stopped"
echo ""

# Step 2: Clean lock files
echo "📍 Step 2/5: Cleaning lock files..."
echo "─────────────────────────────────────────"
rm -f .bot_instance*.lock .heartbeat .webui_instance*.lock
echo "✅ Lock files cleaned"
echo ""

# Step 3: Install Guardian LaunchAgent
echo "📍 Step 3/5: Installing Guardian LaunchAgent..."
echo "─────────────────────────────────────────"

if [ -f com.gridbot.guardian.plist ]; then
    cp com.gridbot.guardian.plist ~/Library/LaunchAgents/
    chmod 644 ~/Library/LaunchAgents/com.gridbot.guardian.plist
    echo "✅ Guardian LaunchAgent installed"
else
    echo "❌ com.gridbot.guardian.plist not found in project root!"
    exit 1
fi
echo ""

# Step 4: Start WebUI
echo "📍 Step 4/5: Starting WebUI..."
echo "─────────────────────────────────────────"

launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist 2>/dev/null || true
launchctl start com.gridbot.webui
sleep 5

# Check if WebUI started
WEBUI_STATUS=$(launchctl list | grep "com.gridbot.webui" | awk '{print $1}')
if [ "$WEBUI_STATUS" != "-" ] && [ -n "$WEBUI_STATUS" ]; then
    echo "✅ WebUI LaunchAgent started (PID: $WEBUI_STATUS)"
    
    # Wait a bit more for port to bind
    sleep 2
    
    if lsof -i :5555 > /dev/null 2>&1; then
        WEBUI_PID=$(lsof -t -i :5555)
        echo "✅ WebUI listening on port 5555 (PID: $WEBUI_PID)"
    else
        echo "⚠️  WebUI process running but port not yet listening..."
        echo "   This is normal, give it a few more seconds"
    fi
else
    echo "❌ WebUI failed to start"
    echo "   Check logs: tail -20 logs/launchagent_webui_error.log"
    tail -20 logs/launchagent_webui_error.log
fi
echo ""

# Step 5: Start Guardian
echo "📍 Step 5/5: Starting Guardian via LaunchAgent..."
echo "─────────────────────────────────────────"

launchctl load ~/Library/LaunchAgents/com.gridbot.guardian.plist 2>/dev/null || true
launchctl start com.gridbot.guardian
sleep 3

if launchctl list | grep -q "com.gridbot.guardian"; then
    GUARDIAN_STATUS=$(launchctl list | grep "com.gridbot.guardian" | awk '{print $1}')
    if [ "$GUARDIAN_STATUS" != "-" ]; then
        echo "✅ Guardian started (PID: $GUARDIAN_STATUS)"
    else
        echo "⚠️  Guardian LaunchAgent loaded but not running yet"
        echo "   Check: tail -f logs/guardian_launchd_error.log"
    fi
else
    echo "❌ Guardian failed to load"
    exit 1
fi
echo ""

# Final status
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Startup Complete!                                             ║"
echo "╔════════════════════════════════════════════════════════════════╗"
echo ""

echo "📊 LaunchAgent Status:"
launchctl list | grep gridbot || echo "   No gridbot services found"
echo ""

echo "📊 Processes:"
ps aux | grep "$PROJECT_DIR" | grep python | grep -v grep | awk '{print "   •", $2, $11, $12, $13}' || echo "   No processes running"
echo ""

echo "📊 Ports:"
lsof -i :5555 > /dev/null 2>&1 && echo "   ✅ Port 5555: WebUI" || echo "   ❌ Port 5555: Not listening"
echo ""

echo "🌐 WebUI: http://localhost:5555"
echo "📝 Logs:"
echo "   • WebUI: tail -f logs/launchagent_webui.log"
echo "   • Guardian: tail -f logs/guardian_launchd.log"
echo ""

echo "🤖 Trading Bot Status: Not started (manual start required)"
echo "   To start: nohup python3 -m bot.run > bot.log 2>&1 &"
echo ""

echo "✅ WebUI and Guardian now managed by LaunchAgent"
echo "✅ Will auto-start on system boot"
echo "✅ Will auto-restart on crash"
echo ""

# Test instance lock
echo "🔒 Testing Instance Lock..."
if python3 -c "from webui.backend.utils.instance_lock import check_webui_instance; import sys; sys.exit(0 if check_webui_instance('.', 5555) else 1)"; then
    echo "   ✅ Instance lock working (WebUI detected as running)"
else
    echo "   ⚠️  Instance lock not detecting WebUI (may need to wait for startup)"
fi
echo ""

echo "🛑 To stop: ./stop_main_bot.sh"
