#!/bin/bash
# Quick diagnostic for symbol-aware frontend integration
# Run this while testing in browser to verify backend is responding correctly

echo "=== 🔍 SYMBOL INTEGRATION DIAGNOSTIC ==="
echo ""
echo "Testing all symbol-aware endpoints..."
echo ""

# Test 1: Symbols endpoint
echo "1️⃣ Testing /api/symbols (SymbolContext needs this)"
curl -s "http://localhost:5557/api/symbols" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
symbols = data.get('symbols', [])
print(f\"   ✅ Found {len(symbols)} symbols: {', '.join([s['name'] for s in symbols])}\")
print(f\"   ✅ Enabled: {', '.join([s['name'] for s in symbols if s.get('enabled')])}\")
" || echo "   ❌ FAILED - SymbolContext won't work!"

echo ""

# Test 2: Config endpoint with symbol
echo "2️⃣ Testing /api/config/flat?symbol=BTCUSD"
curl -s "http://localhost:5557/api/config/flat?symbol=BTCUSD" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"   ✅ Symbol: {data.get('symbol', 'N/A')}\")
print(f\"   ✅ Has config data: {len(data.get('config', {}))} fields\")
" || echo "   ❌ FAILED - ConfigPanel won't load!"

echo ""

# Test 3: Positions endpoint with symbol
echo "3️⃣ Testing /api/positions?symbol=BTCUSD"
curl -s "http://localhost:5557/api/positions?symbol=BTCUSD" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
summary = data.get('summary', {})
total = summary.get('total_positions', 0)
filtered = summary.get('filtered_by_symbol', 'N/A')
all_symbols = summary.get('total_all_symbols', 0)
print(f\"   ✅ Filtered: {total} positions (filter: {filtered})\")
print(f\"   ✅ Total across all symbols: {all_symbols}\")
" || echo "   ❌ FAILED - PositionsPanel won't filter!"

echo ""

# Test 4: Guardian endpoint with symbol
echo "4️⃣ Testing /api/guardian/status?symbol=BTCUSD"
curl -s "http://localhost:5557/api/guardian/status?symbol=BTCUSD" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"   ✅ Symbol: {data.get('symbol', 'N/A')}\")
print(f\"   ✅ Monitors all: {data.get('monitors_all_symbols', False)}\")
" || echo "   ❌ FAILED - GuardianPanel won't work!"

echo ""

# Test 5: Bot status endpoint with symbol
echo "5️⃣ Testing /api/bot/status?symbol=BTCUSD"
curl -s "http://localhost:5557/api/bot/status?symbol=BTCUSD" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"   ✅ Symbol: {data.get('symbol', 'N/A')}\")
print(f\"   ✅ Running: {data.get('running', False)}\")
print(f\"   ✅ Single process: {data.get('single_process_mode', False)}\")
" || echo "   ❌ FAILED - Bot status won't show!"

echo ""
echo "=== 🎯 SUMMARY ==="
echo ""
echo "If all 5 tests show ✅ - Backend is ready for frontend!"
echo ""
echo "Next: Check browser DevTools for:"
echo "  • Console: No 'useSymbol' errors"
echo "  • Network: API calls include ?symbol= parameter"
echo ""
echo "Frontend URL: http://localhost:3001"
echo "Press F12 in browser to open DevTools"
