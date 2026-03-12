#!/bin/bash
# Start GridBot WebUI Backend (Flask-SocketIO / Python direct)
#
# Usage:
#   ./start_webui.sh          # Normal start
#   ./start_webui.sh stop     # Stop the server
#   ./start_webui.sh restart  # Restart the server
#   ./start_webui.sh status   # Check if running

set -e

PROJECT_DIR="/Users/ssr/Projects/WorkingBot"
PID_FILE="/tmp/gridbot_webui.pid"
LOCK_FILE="$HOME/.gridbot_webui_instance_5555.lock"
LOG_FILE="$PROJECT_DIR/logs/webui_backend.log"
PYTHON="$PROJECT_DIR/.venv/bin/python3"

cd "$PROJECT_DIR"
mkdir -p logs

export PYTHONPATH="$PROJECT_DIR"

# ============================================================================
# Helper: Stop existing instance
# ============================================================================
stop_server() {
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            echo "Stopping WebUI (PID $OLD_PID)..."
            kill "$OLD_PID" 2>/dev/null || true
            for i in {1..10}; do
                if ! ps -p "$OLD_PID" > /dev/null 2>&1; then break; fi
                sleep 0.5
            done
            if ps -p "$OLD_PID" > /dev/null 2>&1; then
                kill -9 "$OLD_PID" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi

    pkill -f "python.*webui/backend/app.py" 2>/dev/null || true
    rm -f "$LOCK_FILE"
}

# ============================================================================
# Handle commands
# ============================================================================
case "${1:-start}" in
    stop)
        stop_server
        echo "✅ Server stopped"
        exit 0
        ;;
    status)
        if [ -f "$PID_FILE" ] && ps -p "$(cat "$PID_FILE")" > /dev/null 2>&1; then
            echo "✅ Running (PID $(cat "$PID_FILE"))"
            curl -s http://localhost:5555/api/health 2>/dev/null && echo "" || echo "⚠️  Not responding on port 5555"
        else
            echo "❌ Not running"
        fi
        exit 0
        ;;
    restart)
        stop_server
        sleep 2
        ;;
    start)
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

# ============================================================================
# Start
# ============================================================================
stop_server
sleep 1

echo "🚀 Starting GridBot WebUI Backend..."

nohup "$PYTHON" "$PROJECT_DIR/webui/backend/app.py" \
    > "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

echo "✅ Started (PID: $NEW_PID)"
echo "📝 Logs: $LOG_FILE"

echo "⏳ Waiting for server..."
for i in {1..30}; do
    if curl -s http://localhost:5555/api/health > /dev/null 2>&1; then
        echo "✅ Server responding on port 5555"
        echo ""
        echo "   Dashboard: http://localhost:5555"
        echo "   Health:    http://localhost:5555/api/health"
        echo "   Logs:      tail -f $LOG_FILE"
        exit 0
    fi
    sleep 1
done

echo "❌ Server failed to start within 30s"
echo "   Check logs: tail -50 $LOG_FILE"
tail -20 "$LOG_FILE"
exit 1
