#!/bin/bash
# Enhanced Trading Bot Launcher with Combined Logs
# Starts Guardian (if not running) and Trading bot with combined log viewer

echo "🚀 Enhanced GridBot Launcher with Combined Logs"
echo "================================================"

# Check if Guardian is running
if ! pm2 list | grep -q "guardian-live.*online"; then
    echo "🛡️ Starting Guardian bot..."
    pm2 start ecosystem.config.js --only guardian-live
    echo "✅ Guardian started"
else
    echo "✅ Guardian already running"
fi

# Start Trading bot
echo "📈 Starting Trading bot..."
pm2 start ecosystem.config.js --only gridbot-live

# Wait a moment for trading bot to initialize
sleep 2

# Start combined log viewer
echo "👁️ Starting combined log viewer..."
echo "   You will see both Guardian and Trading bot logs simultaneously"
echo "   Press Ctrl+C to stop viewing (bots continue running)"
echo ""

# Start the combined log viewer in foreground
python3 view_combined_logs.py

echo ""
echo "📋 Log viewer stopped"
echo "💡 Tips:"
echo "   - Bots continue running in background via PM2"
echo "   - Use 'pm2 list' to check status"
echo "   - Use 'pm2 logs gridbot-live' for trading bot only"
echo "   - Use 'pm2 logs guardian-live' for guardian only"
echo "   - Run 'view_combined_logs.py' anytime to resume combined viewing"
