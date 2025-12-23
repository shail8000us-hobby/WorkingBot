#!/bin/bash
# Ultra-Simple WebUI Starter - Just Start Backend

cd "$(dirname "$0")/webui/backend" || exit 1

# Kill anything on port 5555
lsof -ti:5555 2>/dev/null | xargs kill -9 2>/dev/null
rm -f .backend.pid
sleep 2

echo "🚀 Starting WebUI Backend..."
python3 app.py &
BACKEND_PID=$!

sleep 3

echo ""
echo "✅ Backend PID: $BACKEND_PID"
echo "🌐 Access: http://localhost:5555"
echo "📱 Mobile: http://100.107.230.67:5555"
echo "📝 Logs: tail -f /tmp/gridbot_webui.log"
echo ""
