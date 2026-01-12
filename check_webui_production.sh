#!/bin/bash
# WebUI Production Status Checker
# Created: January 5, 2026

echo "═══════════════════════════════════════════════════════════"
echo "🚀 GridBot WebUI - Production Status"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check LaunchAgents
echo "📦 LaunchAgent Services:"
launchctl list | grep gridbot.webui | while read -r line; do
    echo "   ✅ $line"
done
echo ""

# Check port 5555
echo "🌐 Port 5555 Status:"
if lsof -i :5555 | grep -q LISTEN; then
    PID=$(lsof -ti :5555)
    echo "   ✅ Active - PID: $PID"
else
    echo "   ❌ Not listening"
fi
echo ""

# Health check
echo "💊 Backend Health:"
HEALTH=$(curl -s http://localhost:5555/api/health 2>&1)
if echo "$HEALTH" | grep -q "healthy"; then
    echo "   ✅ Healthy"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null | sed 's/^/      /'
else
    echo "   ❌ Unhealthy or not responding"
fi
echo ""

# Options Chain check
echo "📊 Options Chain API:"
OC_HEALTH=$(curl -s http://localhost:5555/api/options-chain/health 2>&1)
if echo "$OC_HEALTH" | grep -q "ok"; then
    echo "   ✅ Active"
    echo "$OC_HEALTH" | python3 -m json.tool 2>/dev/null | sed 's/^/      /'
else
    echo "   ❌ Not responding"
fi
echo ""

# Check for dev servers (should be none)
echo "🔍 Dev Server Check:"
if ps aux | grep -E "react-app-rewired|npm start" | grep -v grep > /dev/null; then
    echo "   ⚠️  WARNING: Dev server still running!"
    ps aux | grep -E "react-app-rewired|npm start" | grep -v grep | awk '{print "      PID:", $2}'
else
    echo "   ✅ No dev servers (correct for production)"
fi
echo ""

# Check ports 3000-3002 (should be free)
echo "🚫 Dev Ports (3000-3002):"
USED_PORTS=""
for port in 3000 3001 3002; do
    if lsof -i :$port 2>/dev/null | grep -q LISTEN; then
        USED_PORTS="$USED_PORTS $port"
    fi
done

if [ -z "$USED_PORTS" ]; then
    echo "   ✅ All free (correct for production)"
else
    echo "   ⚠️  WARNING: Ports in use:$USED_PORTS"
fi
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════"
echo "📝 Summary:"
echo ""
echo "   Access WebUI:      http://localhost:5555"
echo "   Options Chain:     http://localhost:5555 → Options Chain tab"
echo "   Backend Logs:      tail -f logs/launchagent_webui.log"
echo "   Error Logs:        tail -f logs/launchagent_webui_error.log"
echo ""
echo "   Restart Backend:   launchctl restart com.gridbot.webui"
echo "   Rebuild Frontend:  cd webui/frontend && npm run build"
echo "═══════════════════════════════════════════════════════════"
