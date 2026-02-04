#!/bin/bash
# TradingView Signal Monitor
# Run this to watch for new signals in real-time

echo "🔴 TradingView Signal Monitor - Press Ctrl+C to stop"
echo "📡 Webhook: https://ca26-103-167-195-5.ngrok-free.app/api/tradingview/webhook"
echo "⏰ Checking every 5 seconds..."
echo ""

LAST_COUNT=0

while true; do
    # Get current signal count
    CURRENT_COUNT=$(curl -s http://localhost:5555/api/tradingview/signals | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(len(data.get('signals', [])))
except:
    print(0)
" 2>/dev/null)
    
    # Check if new signals arrived
    if [ "$CURRENT_COUNT" -gt "$LAST_COUNT" ]; then
        echo "🚨 NEW SIGNAL RECEIVED! Total: $CURRENT_COUNT"
        
        # Show the latest signal
        curl -s http://localhost:5555/api/tradingview/signals | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    signals = data.get('signals', [])
    if signals:
        latest = signals[0]  # Most recent signal
        price = float(latest['price'])
        created = latest['created_at'][:19].replace('T', ' ')
        print(f'📊 {created} | {latest[\"symbol\"]} {latest[\"action\"].upper()} @ \${price:,.0f}')
        print(f'💼 Strategy: {latest[\"strategy\"]} | Message: {latest.get(\"message\", \"N/A\")}')
    print('')
except:
    print('Error parsing signal')
        " 2>/dev/null
        
        LAST_COUNT=$CURRENT_COUNT
    else
        echo "⏳ Waiting for signals... (Current: $CURRENT_COUNT)"
    fi
    
    sleep 5
done