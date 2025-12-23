#!/bin/bash
# Tmux Control Service - Can be called by WebUI to start/stop tmux
# This runs outside the LaunchAgent context with proper terminal access

WORKING_DIR="/Users/shailendrasinghrajawat/Projects/WorkingBot"
TMUX_BIN="/opt/homebrew/bin/tmux"
SOCKET_PATH="$HOME/.tmux-gridbot/default"
SESSION_NAME="gridbot"
DAEMON_SCRIPT="$WORKING_DIR/scripts/start_tmux_daemon.sh"

# Action: start, stop, status
ACTION="$1"

case "$ACTION" in
    start)
        # Start the session
        bash "$DAEMON_SCRIPT"
        exit $?
        ;;
    
    stop)
        # Stop the session
        if "$TMUX_BIN" -S "$SOCKET_PATH" has-session -t "$SESSION_NAME" 2>/dev/null; then
            "$TMUX_BIN" -S "$SOCKET_PATH" kill-session -t "$SESSION_NAME"
            echo "Session stopped"
            exit 0
        else
            echo "No session to stop"
            exit 1
        fi
        ;;
    
    status)
        # Check status
        if "$TMUX_BIN" -S "$SOCKET_PATH" has-session -t "$SESSION_NAME" 2>/dev/null; then
            echo "running"
            exit 0
        else
            echo "stopped"
            exit 1
        fi
        ;;
    
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
