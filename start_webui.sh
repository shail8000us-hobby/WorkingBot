#!/bin/bash
# Start GridBot WebUI Backend via Gunicorn (production server)
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

cd "$PROJECT_DIR"
mkdir -p logs

# Ensure gunicorn is in PATH
export PATH="/Users/ssr/Library/Python/3.9/bin:/opt/homebrew/bin:$PATH"
export PYTHONPATH="$PROJECT_DIR"

# ============================================================================
# Helper: Stop existing instance
# ============================================================================
stop_server() {
    # Kill by PID file
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            echo "Stopping Gunicorn (PID $OLD_PID)..."
            kill "$OLD_PID" 2>/dev/null || true
            # Wait for graceful shutdown (max 5s)
            for i in {1..10}; do
                if ! ps -p "$OLD_PID" > /dev/null 2>&1; then
                    break
                fi
                sleep 0.5
            done
            # Force kill if still alive
            if ps -p "$OLD_PID" > /dev/null 2>&1; then
                kill -9 "$OLD_PID" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi

    # Also kill any orphaned app.py processes
    pkill -f "gunicorn.*wsgi:app" 2>/dev/null || true
    pkill -f "python.*webui/backend/app.py" 2>/dev/null || true

    # Clean stale lock
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
        ;; # Fall through to start
    start)
        ;; # Fall through to start
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

# ============================================================================
# Start Gunicorn
# ============================================================================
stop_server
sleep 1

echo "🚀 Starting GridBot WebUI Backend (Gunicorn)..."

# Start Gunicorn with eventlet worker, writing PID file
nohup gunicorn \
    -c "$PROJECT_DIR/gunicorn_config.py" \
    "webui.backend.wsgi:app" \
    > "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

echo "✅ Gunicorn started (PID: $NEW_PID)"
echo "📝 Logs: $LOG_FILE"

# Wait for server to accept connections (server starts fast with deferred monitors)
echo "⏳ Waiting for server..."
for i in {1..20}; do
    if curl -s http://localhost:5555/api/health > /dev/null 2>&1; then
        echo "✅ Server is responding on port 5555"
        echo ""
        echo "   Dashboard: http://localhost:5555"
        echo "   Health:    http://localhost:5555/api/health"
        echo "   Logs:      tail -f $LOG_FILE"
        exit 0
    fi
    sleep 1
done

echo "❌ Server failed to start within 20s"
echo "   Check logs: tail -50 $LOG_FILE"
tail -20 "$LOG_FILE"
exit 1
