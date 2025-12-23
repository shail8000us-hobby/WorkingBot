#!/bin/bash
# Start tmux from LaunchAgent (daemon mode)
# This script works around tmux's TTY requirements

set -e

# Configuration
PROJECT_ROOT="/Users/shailendrasinghrajawat/Projects/WorkingBot"
SESSION_NAME="gridbot"
TMUX_BIN="/opt/homebrew/bin/tmux"
SOCKET_DIR="/Users/shailendrasinghrajawat/.tmux-gridbot"
SOCKET_PATH="${SOCKET_DIR}/default"

# Create socket directory if it doesn't exist
mkdir -p "$SOCKET_DIR"
chmod 700 "$SOCKET_DIR"

# Clean up old socket if it exists but is stale
if [ -e "$SOCKET_PATH" ]; then
    # Try to connect - if it fails, remove the stale socket
    if ! "$TMUX_BIN" -S "$SOCKET_PATH" list-sessions &>/dev/null; then
        echo "Removing stale socket..."
        rm -f "$SOCKET_PATH"
    fi
fi

cd "$PROJECT_ROOT"

# Check if session already exists
if "$TMUX_BIN" -S "$SOCKET_PATH" has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "✅ tmux session '$SESSION_NAME' already exists"
    exit 0
fi

# Start tmux in detached mode with custom socket
# This bypasses the need for a controlling terminal
echo "🚀 Starting tmux session in daemon mode..."

# Create a new detached session for Trading Bot (will be 2/3 width on left)
"$TMUX_BIN" -S "$SOCKET_PATH" new-session -d -s "$SESSION_NAME" -n "Bots"

# Send the trading bot command to the first pane
"$TMUX_BIN" -S "$SOCKET_PATH" send-keys -t "$SESSION_NAME:0.0" \
    "cd $PROJECT_ROOT && export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH && python3 -u bot/run.py 2>&1 | tee -a logs/bot_live.log; exec bash" C-m

# Wait a moment for first pane to initialize
sleep 0.5

# Split window vertically for Guardian (will be top 2/3 on right side)
"$TMUX_BIN" -S "$SOCKET_PATH" split-window -h -t "$SESSION_NAME:0.0"

# Send the guardian command
"$TMUX_BIN" -S "$SOCKET_PATH" send-keys -t "$SESSION_NAME:0.1" \
    "cd $PROJECT_ROOT && export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH && python3 -u bot/guardian/guardian_bot.py 2>&1 | tee -a logs/guardian.log; exec bash" C-m

# Wait a moment
sleep 0.5

# Split the right pane horizontally for Health Monitor (will be bottom 1/3 on right side)
"$TMUX_BIN" -S "$SOCKET_PATH" split-window -v -t "$SESSION_NAME:0.1"

# Send the monitor command
"$TMUX_BIN" -S "$SOCKET_PATH" send-keys -t "$SESSION_NAME:0.2" \
    "cd $PROJECT_ROOT && export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH && python3 -u bot/heartbeat/monitor.py 2>&1 | tee -a logs/monitor.log; exec bash" C-m

# Wait a moment for all panes to initialize
sleep 0.5

# Set specific pane sizes:
# - Pane 0 (Trading): 2/3 width of total window (left side)
# - Pane 1 (Guardian): 2/3 height of right column (top right)
# - Pane 2 (Monitor): 1/3 height of right column (bottom right)

# First, make pane 0 (Trading) take 66% of the width
"$TMUX_BIN" -S "$SOCKET_PATH" resize-pane -t "$SESSION_NAME:0.0" -x 66%

# Then split the right column: Guardian gets 66% height
"$TMUX_BIN" -S "$SOCKET_PATH" resize-pane -t "$SESSION_NAME:0.1" -y 66%

# Set mouse mode on
"$TMUX_BIN" -S "$SOCKET_PATH" set-option -t "$SESSION_NAME" mouse on

echo "✅ tmux session created successfully!"
echo "📺 To attach: tmux -S $SOCKET_PATH attach -t $SESSION_NAME"
echo "📝 Socket location: $SOCKET_PATH"

exit 0

