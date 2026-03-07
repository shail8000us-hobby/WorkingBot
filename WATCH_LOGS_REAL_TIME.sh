#!/bin/bash
echo "👀 Watching backend logs in real-time..."
echo "📝 Try adding a todo in your browser NOW"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
tail -f /Users/shailendrasinghrajawat/Projects/WorkingBot/logs/launchagent_webui.log | grep --line-buffered -E "POST /api/todos|📝|❌|✅|ERROR|Exception|Traceback|Creating|todo"




