#!/bin/bash
# Hot reload Guardian config without restart

echo "🔄 Reloading Guardian configuration..."

# Find Guardian process
GUARDIAN_PID=$(pgrep -f "guardian_bot.py")

if [ -z "$GUARDIAN_PID" ]; then
    echo "❌ Guardian process not found!"
    exit 1
fi

echo "📍 Found Guardian process: PID $GUARDIAN_PID"

# Send SIGUSR1 signal to trigger config reload
kill -SIGUSR1 $GUARDIAN_PID

if [ $? -eq 0 ]; then
    echo "✅ Config reload signal sent successfully!"
    echo "📝 Check Guardian logs for confirmation:"
    echo "   pm2 logs guardian-live --lines 20"
else
    echo "❌ Failed to send reload signal"
    exit 1
fi
