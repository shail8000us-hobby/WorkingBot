#!/bin/bash
# Quick Instance Status Check

echo "🔍 WorkingBot Instance Status"
echo "======================================"
echo ""

echo "📊 LaunchAgents:"
launchctl list | grep gridbot | awk '{printf "   %-30s PID: %s\n", $3, $1}' || echo "   None running"
echo ""

echo "📊 Processes:"
ps aux | grep "/Users/ssr/Projects/WorkingBot" | grep python | grep -v grep | awk '{printf "   PID %-6s CPU: %-5s MEM: %-5s %s\n", $2, $3"%", $4"%", $11}' || echo "   None running"
echo ""

echo "📊 Ports:"
lsof -i :5555 > /dev/null 2>&1 && echo "   ✅ 5555: WebUI" || echo "   ❌ 5555: Not listening"
echo ""

echo "📊 Instance Locks:"
if [ -f .webui_instance_5555.lock ]; then
    echo "   ✅ WebUI lock exists:"
    cat .webui_instance_5555.lock | sed 's/^/      /'
else
    echo "   ❌ No WebUI lock"
fi
echo ""

echo "📊 Demo Status (should be separate):"
launchctl list | grep demo | awk '{printf "   %-30s PID: %s\n", $3, $1}' || echo "   None running"

