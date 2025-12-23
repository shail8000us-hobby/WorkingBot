#!/bin/bash
# Live Trading Startup Script
# Fixes all environment and module issues

cd /Users/shailendrasinghrajawat/Projects/WorkingBot

echo "🚀 STARTING LIVE TRADING BOTS"
echo "============================="

# Set up environment
export PYTHONPATH="/Users/shailendrasinghrajawat/Projects/WorkingBot:$PYTHONPATH"
export TRADING_MODE="live"

# Kill existing tmux session
tmux kill-session -t gridbot 2>/dev/null || true
sleep 2

# Create new tmux session
tmux new-session -d -s gridbot -x 120 -y 30

# Split into 3 panes
tmux split-window -h -t gridbot
tmux split-window -v -t gridbot:0.1

echo "✅ Created tmux session with 3 panes"

# Start Guardian Bot (Pane 0)
echo "Starting Guardian Bot..."
tmux send-keys -t gridbot:0.0 "cd /Users/shailendrasinghrajawat/Projects/WorkingBot && export PYTHONPATH=/Users/shailendrasinghrajawat/Projects/WorkingBot && export TRADING_MODE=live && python3 bot/guardian/guardian_bot.py" Enter

# Start Heartbeat Monitor (Pane 1)
echo "Starting Heartbeat Monitor..."
tmux send-keys -t gridbot:0.1 "cd /Users/shailendrasinghrajawat/Projects/WorkingBot && export PYTHONPATH=/Users/shailendrasinghrajawat/Projects/WorkingBot && export TRADING_MODE=live && while true; do python3 bot/heartbeat/monitor.py; sleep 10; done" Enter

# Start Trading Bot (Pane 2)
echo "Starting Trading Bot..."
tmux send-keys -t gridbot:0.2 "cd /Users/shailendrasinghrajawat/Projects/WorkingBot && export PYTHONPATH=/Users/shailendrasinghrajawat/Projects/WorkingBot && export TRADING_MODE=live && python3 bot/strategy/gbot_ws.py" Enter

echo ""
echo "✅ ALL BOTS STARTED!"
echo ""
echo "📱 TO VIEW LIVE TRADING:"
echo "   tmux attach -t gridbot"
echo ""
echo "🎮 TMUX CONTROLS:"
echo "   Ctrl+B + ←/→  Switch panes"
echo "   Ctrl+B + d     Detach (keep running)"
echo "   Ctrl+C         Stop bot in current pane"
echo ""
echo "🔴 LIVE TRADING ACTIVE!"
