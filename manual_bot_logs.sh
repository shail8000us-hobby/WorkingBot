#!/bin/bash
# Manual Bot Logs Viewer - NO AUTOMATIC EXECUTION
# Run this manually when you want to see bot logs

echo "🤖 Manual Bot Logs Viewer"
echo "========================="
echo ""
echo "This script will NOT run automatically."
echo "You must run it manually when you want to see logs."
echo ""
echo "Choose what you want to do:"
echo "1. View Guardian Bot logs (live)"
echo "2. View WebUI Backend logs (live)"
echo "3. Create tmux session with all logs"
echo "4. Just show recent log files"
echo "5. Exit"
echo ""

read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo "📊 Showing Guardian Bot logs (press Ctrl+C to stop):"
        tail -f guardian_restart.log
        ;;
    2)
        echo "🌐 Showing WebUI Backend logs (press Ctrl+C to stop):"
        tail -f webui_backend.log
        ;;
    3)
        echo "🚀 Creating tmux session with all logs..."
        tmux new-session -d -s botlogs
        tmux send-keys -t botlogs "tail -f guardian_restart.log" Enter
        tmux new-window -t botlogs -n webui
        tmux send-keys -t botlogs:webui "tail -f webui_backend.log" Enter
        echo ""
        echo "✅ tmux session 'botlogs' created!"
        echo "To attach: tmux attach -t botlogs"
        echo "To detach: Ctrl+B then d"
        echo ""
        tmux attach -t botlogs
        ;;
    4)
        echo "📋 Recent log files:"
        ls -la *.log | head -10
        echo ""
        echo "To view a specific log: tail -f [filename]"
        ;;
    5)
        echo "👋 Goodbye!"
        exit 0
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again."
        exit 1
        ;;
esac

