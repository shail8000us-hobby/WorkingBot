#!/bin/bash
# Development startup script with auto-reload

echo "🚀 Starting WebUI Backend in Development Mode"
echo "=============================================="
echo ""

# Kill existing backend if running
if [ -f ".webui_backend.pid" ]; then
    OLD_PID=$(cat .webui_backend.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "🛑 Stopping existing backend (PID: $OLD_PID)..."
        kill $OLD_PID
        sleep 2
    fi
    rm .webui_backend.pid
fi

# Set development environment
export FLASK_ENV=development
export FLASK_DEBUG=1

echo "✅ Development mode enabled"
echo "🔄 Auto-reload: ON"
echo "📝 Watching for file changes..."
echo ""

# Start with auto-reload
python3 dev_server.py
