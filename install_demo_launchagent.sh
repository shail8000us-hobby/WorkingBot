#!/bin/bash
# Install Demo LaunchAgent for WorkingBot-demo
# This will auto-start Demo WebUI (5556) on Mac boot

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Install Demo LaunchAgent (WorkingBot-demo)                    ║"
echo "╔════════════════════════════════════════════════════════════════╗"
echo ""

PROJECT_DIR="/Users/ssr/Projects/WorkingBot"
DEMO_DIR="/Users/ssr/Projects/WorkingBot-demo"

# Check if demo directory exists
if [ ! -d "$DEMO_DIR" ]; then
    echo "❌ Demo directory not found: $DEMO_DIR"
    exit 1
fi

# Create LaunchAgents directory
mkdir -p ~/Library/LaunchAgents

# Stop and unload old demo services
echo "🛑 Stopping old demo services..."
launchctl stop com.gridbot.demo.webui 2>/dev/null || true
launchctl stop com.gridbot.demo.guardian 2>/dev/null || true
launchctl stop com.workingbot.demo.webui 2>/dev/null || true
launchctl stop com.workingbot.demo.bot 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.gridbot.demo.* 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.workingbot.demo.* 2>/dev/null || true
rm -f ~/Library/LaunchAgents/com.gridbot.demo.*
rm -f ~/Library/LaunchAgents/com.workingbot.demo.*
sleep 2

# Copy plist from production WorkingBot to demo
echo "📦 Installing Demo LaunchAgent..."
echo ""

echo "1️⃣  Demo WebUI (Port 5556)"
cp "$PROJECT_DIR/launchd/com.gridbot.demo.webui.plist" ~/Library/LaunchAgents/
chmod 644 ~/Library/LaunchAgents/com.gridbot.demo.webui.plist
echo "   ✅ Installed"

echo ""
echo "🚀 Loading and starting demo WebUI..."
echo ""

# Load and start Demo WebUI
launchctl load ~/Library/LaunchAgents/com.gridbot.demo.webui.plist
launchctl start com.gridbot.demo.webui
sleep 3

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Installation Complete!                                        ║"
echo "╔════════════════════════════════════════════════════════════════╗"
echo ""

# Check status
echo "📊 LaunchAgent Status:"
launchctl list | grep "com.gridbot.demo" | awk '{printf "   %-35s PID: %s\n", $3, $1}'
echo ""

echo "📊 Ports:"
lsof -i :5556 > /dev/null 2>&1 && echo "   ✅ Port 5556: Demo WebUI" || echo "   ⏳ Port 5556: Starting..."
echo ""

echo "📝 Logs:"
echo "   • Demo WebUI: tail -f $DEMO_DIR/logs/webui_demo.log"
echo ""

echo "🌐 Demo WebUI: http://localhost:5556"
echo ""
echo "✅ Demo WebUI will auto-start on Mac boot"
echo "✅ Demo WebUI will auto-restart on crash"
echo ""
echo "⚠️  Note: Demo uses port 5556 (Production uses 5555)"
