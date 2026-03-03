#!/bin/bash
# Manual bot logs viewer - run this when you want to see bot logs
# Usage: ./view_bot_logs.sh

echo "🤖 Bot Logs Viewer"
echo "=================="
echo ""
echo "Choose what logs you want to view:"
echo "1. Guardian Bot Logs (live)"
echo "2. WebUI Backend Logs (live)"
echo "3. All Logs in tmux (recommended)"
echo "4. Exit"
echo ""

read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo "📊 Opening Guardian Bot logs..."
        tail -f guardian_restart.log
        ;;
    2)
        echo "🌐 Opening WebUI Backend logs..."
        tail -f webui_backend.log
        ;;
    3)
        echo "🚀 Opening tmux session with all logs..."
        tmux new-session -d -s botlogs
        tmux send-keys -t botlogs "tail -f guardian_restart.log" Enter
        tmux new-window -t botlogs -n webui
        tmux send-keys -t botlogs:webui "tail -f webui_backend.log" Enter
        echo ""
        echo "✅ tmux session created! Now run: tmux attach -t botlogs"
        echo "   - Window 0: Guardian Bot logs"
        echo "   - Window 1: WebUI logs"
        echo "   - Press Ctrl+B then 0 or 1 to switch windows"
        echo "   - Press Ctrl+B then d to detach"
        ;;
    4)
        echo "👋 Goodbye!"
        exit 0
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again."
        exit 1
        ;;
esac

