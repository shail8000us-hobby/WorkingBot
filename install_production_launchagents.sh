#!/bin/bash
# Install Production LaunchAgents for WorkingBot
# This will auto-start WebUI (5555) + Guardian on Mac boot

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Install Production LaunchAgents (WorkingBot)                  ║"
echo "╔════════════════════════════════════════════════════════════════╗"
echo ""

PROJECT_DIR="/Users/ssr/Projects/WorkingBot"
cd "$PROJECT_DIR"

# Create LaunchAgents directory
mkdir -p ~/Library/LaunchAgents

# Stop and unload old services
echo "🛑 Stopping old services..."
launchctl stop com.gridbot.webui 2>/dev/null || true
launchctl stop com.gridbot.guardian 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.gridbot.guardian.plist 2>/dev/null || true
rm -f ~/Library/LaunchAgents/com.gridbot.webui.plist
rm -f ~/Library/LaunchAgents/com.gridbot.guardian.plist
sleep 2

# Install new production services
echo "📦 Installing Production LaunchAgents..."
echo ""

# WebUI
echo "1️⃣  WebUI (Port 5555)"
cp launchd/com.gridbot.production.webui.plist ~/Library/LaunchAgents/
chmod 644 ~/Library/LaunchAgents/com.gridbot.production.webui.plist
echo "   ✅ Installed"

# Guardian
echo "2️⃣  Guardian Bot"
cp launchd/com.gridbot.production.guardian.plist ~/Library/LaunchAgents/
chmod 644 ~/Library/LaunchAgents/com.gridbot.production.guardian.plist
echo "   ✅ Installed"

echo ""
echo "🚀 Loading and starting services..."
echo ""

# Load and start WebUI
launchctl load ~/Library/LaunchAgents/com.gridbot.production.webui.plist
launchctl start com.gridbot.production.webui
sleep 3

# Load and start Guardian
launchctl load ~/Library/LaunchAgents/com.gridbot.production.guardian.plist
launchctl start com.gridbot.production.guardian
sleep 3

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Installation Complete!                                        ║"
echo "╔════════════════════════════════════════════════════════════════╗"
echo ""

# Check status
echo "📊 LaunchAgent Status:"
launchctl list | grep "com.gridbot.production" | awk '{printf "   %-35s PID: %s\n", $3, $1}'
echo ""

echo "📊 Ports:"
lsof -i :5555 > /dev/null 2>&1 && echo "   ✅ Port 5555: WebUI" || echo "   ⏳ Port 5555: Starting..."
echo ""

echo "📝 Logs:"
echo "   • WebUI: tail -f logs/webui_production.log"
echo "   • Guardian: tail -f logs/guardian_production.log"
echo ""

echo "🌐 WebUI: http://localhost:5555"
echo ""
echo "✅ Production services will auto-start on Mac boot"
echo "✅ Services will auto-restart on crash"
