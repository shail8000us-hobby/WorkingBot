#!/bin/bash
# Setup WebUI Auto-Recovery System
# Fixes root causes of backend hanging and ensures 24/7 operation

set -e

PROJECT_ROOT="/Users/ssr/Projects/WorkingBot"
LAUNCHAGENTS_DIR="$HOME/Library/LaunchAgents"

echo "=========================================="
echo "🛡️  WebUI Auto-Recovery Setup"
echo "=========================================="
echo ""

# Create logs directory
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/data"

# Stop existing services
echo "📋 Stopping existing services..."
launchctl unload "$LAUNCHAGENTS_DIR/com.gridbot.webui.plist" 2>/dev/null || true
launchctl unload "$LAUNCHAGENTS_DIR/com.gridbot.webui.guardian.plist" 2>/dev/null || true

# Kill any existing hung processes
echo "🧹 Cleaning up hung processes..."
pkill -9 -f "webui/backend/app.py" 2>/dev/null || true
lsof -ti:5555 | xargs kill -9 2>/dev/null || true
sleep 2

# Create LaunchAgent for Guardian (monitors and auto-restarts WebUI)
echo "📝 Creating Guardian LaunchAgent..."
cat > "$LAUNCHAGENTS_DIR/com.gridbot.webui.guardian.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.gridbot.webui.guardian</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/ssr/Projects/WorkingBot/webui_guardian.py</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>/Users/ssr/Projects/WorkingBot</string>
    
    <key>StandardOutPath</key>
    <string>/Users/ssr/Projects/WorkingBot/logs/webui_guardian.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/ssr/Projects/WorkingBot/logs/webui_guardian_error.log</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>/Users/ssr/Projects/WorkingBot</string>
    </dict>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

# Load Guardian
echo "🚀 Starting Guardian..."
launchctl load "$LAUNCHAGENTS_DIR/com.gridbot.webui.guardian.plist"
sleep 3

# Verify Guardian is running
if launchctl list | grep -q "com.gridbot.webui.guardian"; then
    echo "✅ Guardian is running"
else
    echo "❌ Guardian failed to start - check logs"
    exit 1
fi

# Wait for Guardian to start WebUI
echo "⏳ Waiting for WebUI to start (via Guardian)..."
sleep 10

# Check if WebUI is responding
if curl -s -m 3 http://localhost:5555/api/health > /dev/null 2>&1; then
    echo "✅ WebUI is running and responding"
else
    echo "⚠️  WebUI may still be starting - Guardian will monitor and restart if needed"
fi

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "📊 Management Commands:"
echo "  Status:  launchctl list | grep gridbot.webui"
echo "  Logs:    tail -f $PROJECT_ROOT/logs/webui_guardian.log"
echo "  Restart: launchctl stop com.gridbot.webui.guardian && launchctl start com.gridbot.webui.guardian"
echo ""
echo "🛡️  Guardian Features:"
echo "  ✅ Auto-detects hung processes (uninterruptible sleep)"
echo "  ✅ Health checks every 30 seconds"
echo "  ✅ Auto-restart on failure (max 5 attempts)"
echo "  ✅ Memory leak detection (restarts at 2GB)"
echo "  ✅ Port conflict resolution"
echo ""


