#!/usr/bin/env bash
cd "$(dirname "$0")/.."

# Ensure folders exist
mkdir -p bot/logs reports

# Check for existing bot instances (improved pattern matching)
# Note: Don't use -o pipefail here as grep may return non-zero when no matches
EXISTING_BOTS=$(ps aux | grep -E "bot\.run|bot/run|-m bot\.run" | grep -v grep | wc -l | tr -d ' ' || echo "0")
if [ "$EXISTING_BOTS" -gt 0 ]; then
    echo "❌ ERROR: $EXISTING_BOTS trading bot instance(s) already running!"
    echo "Please stop existing bots before starting a new one."
    echo ""
    echo "Running instances:"
    ps aux | grep -E "bot\.run|bot/run|-m bot\.run" | grep -v grep
    echo ""
    echo "To stop existing bots:"
    echo "  ./dashboard/stop.sh"
    echo "  or kill the PIDs shown above"
    echo ""
    echo "Or use WebUI Emergency Kill:"
    echo "  curl -X POST http://localhost:5555/api/emergency/kill-all"
    exit 1
fi

echo "✅ No existing bot instances found, starting new bot..."
echo ""

# Use UNIFIED LAUNCHER in daemon mode (always background)
echo "🚀 Starting bot using unified launcher..."
python3 bot_launcher.py --daemon "$@"

if [ $? -eq 0 ]; then
    echo "✅ Bot started successfully!"
    echo "   PID: $(cat reports/bot.pid 2>/dev/null || echo 'unknown')"
    echo "   Logs: tail -f bot/logs/bot.log"
    echo "   Stop: ./dashboard/stop.sh"
    echo ""
    echo "🌐 WebUI will detect bot automatically within 2 seconds"
else
    echo "❌ Failed to start bot"
    exit 1
fi
