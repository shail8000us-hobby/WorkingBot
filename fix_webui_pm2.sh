#!/bin/bash
# WebUI PM2 Control Quick Fix
# Rebuilds frontend and restarts backend to ensure latest code is running

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 WebUI PM2 Control Fix - $(date '+%Y-%m-%d %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd /Users/ssr/Projects/WorkingBot

# Step 1: Rebuild frontend
echo "Step 1: Rebuilding frontend..."
cd webui/frontend
if npm run build > /tmp/webui_build.log 2>&1; then
    echo "✅ Frontend build successful"
else
    echo "❌ Frontend build failed. Check /tmp/webui_build.log"
    exit 1
fi

cd ../..

# Step 2: Restart backend
echo ""
echo "Step 2: Restarting production webUI backend..."
if launchctl kickstart -k gui/$(id -u)/com.gridbot.production.webui 2>&1; then
    echo "✅ Backend restart initiated"
else
    echo "⚠️  Backend restart may have failed"
fi

# Step 3: Wait for backend
echo ""
echo "Step 3: Waiting for backend to be ready..."
sleep 5

# Step 4: Test endpoints
echo ""
echo "Step 4: Testing PM2 endpoints..."

# Test health
if curl -s --max-time 3 http://localhost:5555/api/health | grep -q "healthy"; then
    echo "✅ Health endpoint: OK"
else
    echo "❌ Health endpoint: FAILED"
    exit 1
fi

# Test PM2 status
if curl -s --max-time 3 http://localhost:5555/api/pm2/status | grep -q "success"; then
    echo "✅ PM2 status endpoint: OK"
else
    echo "❌ PM2 status endpoint: FAILED"
    exit 1
fi

# Test PM2 control (restart live bot to verify control works)
echo ""
echo "Step 5: Testing PM2 control (restarting gridbot-live)..."
RESPONSE=$(curl -s -X POST http://localhost:5555/api/pm2/restart/gridbot-live)
if echo "$RESPONSE" | grep -q '"success":true' || echo "$RESPONSE" | grep -q '"success": true'; then
    echo "✅ PM2 control endpoint: OK"
    echo "   └─ gridbot-live restarted successfully"
else
    echo "❌ PM2 control endpoint: FAILED"
    echo "   Response: $RESPONSE"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All backend systems are working!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Now in your browser:"
echo "  1. Open http://localhost:5555"
echo "  2. Clear cache: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)"
echo "  3. Open DevTools Console (F12) to check for errors"
echo "  4. Try PM2 control buttons"
echo ""
echo "If still having issues:"
echo "  • Check browser console for errors (red messages)"
echo "  • Try: open /Users/ssr/Projects/WorkingBot/test_pm2_webui.html"
echo "  • Report exact error message from browser console"
echo ""
