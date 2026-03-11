#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# start_backtesting.sh — Start the MMM Backtesting Engine (port 5557)
# ──────────────────────────────────────────────────────────────────────────────
# Usage:
#   ./start_backtesting.sh           # start in background with logs
#   ./start_backtesting.sh --dev     # start frontend dev server (hot-reload)
#   ./start_backtesting.sh --stop    # kill backtesting server

set -e
WORKDIR="$(cd "$(dirname "$0")" && pwd)"
PORT=5557
LOG_FILE="/tmp/backtesting_ui.log"
PID_FILE="/tmp/backtesting_ui.pid"

case "$1" in
  --stop)
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      echo "Stopping backtesting server (PID $PID)…"
      kill "$PID" 2>/dev/null && echo "Stopped." || echo "Already stopped."
      rm -f "$PID_FILE"
    else
      echo "No PID file found. Server may not be running."
    fi
    ;;
  --dev)
    echo "Starting Backtesting Backend (Flask) on port $PORT…"
    cd "$WORKDIR"
    python3 -m backtesting.ui.backend.app --port $PORT &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID"
    echo ""
    echo "Starting Frontend Dev Server (Vite)…"
    cd "$WORKDIR/backtesting/ui/frontend"
    npm run dev
    ;;
  *)
    echo "Starting MMM Backtesting Engine on http://localhost:$PORT"
    cd "$WORKDIR"
    nohup python3 -m backtesting.ui.backend.app --port $PORT > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    sleep 1
    if kill -0 "$PID" 2>/dev/null; then
      echo "✅ Server started (PID: $PID) → http://localhost:$PORT"
      echo "   Logs: tail -f $LOG_FILE"
    else
      echo "❌ Server failed to start. Check: $LOG_FILE"
      cat "$LOG_FILE" | tail -20
    fi
    ;;
esac
