#!/bin/bash
# Test Monitoring System Integration
# Tests bot-to-WebUI wiring, API endpoints, and data quality

set -e

echo "================================================"
echo "🧪 Bot-to-WebUI Monitoring Integration Tests"
echo "================================================"
echo ""

# Check if WebUI is running
echo "1️⃣  Checking WebUI backend status..."
if curl -s http://localhost:5555/api/health > /dev/null 2>&1; then
    echo "✅ WebUI backend is running on port 5555"
else
    echo "❌ WebUI backend is NOT running"
    echo ""
    echo "Please start WebUI backend:"
    echo "  launchctl start com.gridbot.webui"
    exit 1
fi

echo ""

# Check if bot is running
echo "2️⃣  Checking bot status..."
if [ -f "runtime_state.json" ]; then
    echo "✅ Bot runtime state file exists"
    LAST_UPDATE=$(jq -r '.metadata.last_update // "unknown"' runtime_state.json 2>/dev/null || echo "unknown")
    echo "   Last update: $LAST_UPDATE"
else
    echo "⚠️  Bot runtime state file not found (bot may not be running)"
fi

echo ""

# Test monitoring API routes
echo "3️⃣  Testing monitoring API routes..."
echo ""

echo "📊 Monitoring Status:"
curl -s http://localhost:5555/api/monitoring/status | python3 -m json.tool
echo ""

echo "🏥 Price Health:"
curl -s http://localhost:5555/api/monitoring/price-health | python3 -m json.tool
echo ""

echo "📈 Pre-Order Stats:"
curl -s http://localhost:5555/api/monitoring/pre-order-stats | python3 -m json.tool
echo ""

echo "🎯 TP Verification:"
curl -s http://localhost:5555/api/monitoring/tp-verification | python3 -m json.tool
echo ""

echo "⚠️  Anomalies:"
curl -s http://localhost:5555/api/monitoring/anomalies | python3 -m json.tool
echo ""

echo "🔮 Predictive Map:"
curl -s http://localhost:5555/api/monitoring/predictive-map | python3 -m json.tool
echo ""

# Run pytest integration tests
echo "4️⃣  Running pytest integration tests..."
echo ""

if command -v pytest &> /dev/null; then
    pytest tests/integration/test_bot_webui_wiring.py -v --tb=short
else
    echo "⚠️  pytest not installed. Install with: pip install pytest"
    echo "    Skipping pytest tests."
fi

echo ""
echo "================================================"
echo "✅ Monitoring Integration Tests Complete"
echo "================================================"
