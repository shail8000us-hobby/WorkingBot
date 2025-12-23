#!/bin/bash
echo "🔍 WebUI Service Status Check"
echo "======================================"
echo ""
echo "LaunchAgents:"
launchctl list | grep gridbot.webui
echo ""
echo "Health Check:"
curl -s http://localhost:5555/api/health | python3 -m json.tool 2>/dev/null || echo "❌ WebUI not responding"
echo ""
echo "Recent Logs:"
tail -20 logs/launchagent_webui.log 2>/dev/null || echo "No logs yet"
