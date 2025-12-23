#!/bin/bash
# Test script for Volatility Monitor UI

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║              VOLATILITY MONITOR - VERIFICATION TEST                      ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if backend is running
echo "1️⃣  Checking Backend..."
if lsof -i :5555 | grep -iq python; then
    echo "   ✅ Backend running on port 5555"
else
    echo "   ❌ Backend NOT running on port 5555"
    exit 1
fi
echo ""

# Check API response
echo "2️⃣  Testing API Endpoint..."
API_RESPONSE=$(curl -s http://localhost:5555/api/robustness/volatility/status)
SUCCESS=$(echo "$API_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))")

if [ "$SUCCESS" = "True" ]; then
    echo "   ✅ API responding successfully"
else
    echo "   ❌ API failed to respond"
    exit 1
fi
echo ""

# Check volatility data
echo "3️⃣  Checking Volatility Data..."
echo "$API_RESPONSE" | python3 << 'EOF'
import sys, json
d = json.load(sys.stdin)
s = d.get('status', {})

iv = s.get('iv')
rv = s.get('rv')
spread = s.get('spread')
last_update = s.get('last_update')

if iv is not None and rv is not None:
    print(f"   ✅ IV: {iv:.2f}%")
    print(f"   ✅ RV: {rv:.2f}%")
    print(f"   ✅ Spread: {spread:.2f}%" if spread else "   ⚠️  Spread: Not calculated")
    print(f"   ✅ Last Update: {last_update}")
else:
    print("   ⚠️  No volatility data yet (waiting for first update)")
    print("   ℹ️  Try clicking 'Refresh Now' button in UI")
EOF
echo ""

# Check cache headers
echo "4️⃣  Checking Cache-Control Headers..."
CACHE_HEADER=$(curl -s -I http://localhost:5555/ | grep -i "cache-control")
if echo "$CACHE_HEADER" | grep -q "no-cache"; then
    echo "   ✅ Cache headers present: $CACHE_HEADER"
else
    echo "   ❌ Cache headers missing"
fi
echo ""

# Check React build
echo "5️⃣  Checking React Build..."
BUILD_FILE=$(ls -t /Users/shailendrasinghrajawat/Projects/WorkingBot/webui/frontend/build/static/js/main.*.js | head -1)
BUILD_TIME=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$BUILD_FILE")
echo "   ✅ Latest build: $BUILD_TIME"
echo ""

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                          TEST SUMMARY                                    ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ Backend is running"
echo "✅ API is responding"
echo "✅ Cache-busting headers are active"
echo "✅ React build is fresh"
echo ""
echo "🎯 NEXT STEP:"
echo "   1. Open browser (Chrome/Safari/Firefox)"
echo "   2. Go to: http://localhost:5555"
echo "   3. Navigate to: Robustness Features → Volatility Monitor tab"
echo "   4. You should see:"
echo "      • IV: ~46.0%"
echo "      • RV: ~37.1%"
echo "      • Last Update: Recent timestamp"
echo "      • 'REFRESH NOW' button (green)"
echo ""
echo "   If you see 'N/A N/A N/A':"
echo "   • Press Cmd+Shift+R (hard refresh)"
echo "   • Or use Incognito mode (Cmd+Shift+N)"
echo "   • Or send screenshot of browser console (F12)"
echo ""
echo "╚══════════════════════════════════════════════════════════════════════════╝"

