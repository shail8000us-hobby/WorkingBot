#!/bin/bash
# Race Condition Detector
# Analyzes log patterns for duplicate order issues
# Created: Nov 7, 2025

echo "🔍 Race Condition Detector"
echo "========================="
echo ""

LOG_FILE="/Users/ssr/Projects/WorkingBot/bot/logs/bot.log"

# Analyze order timing gaps
echo "📊 Order Timing Analysis"
echo "----------------------"
echo ""

# Extract order placements with timestamps
echo "Recent BUY orders (with time gaps):"
grep "BUY order placed @" "$LOG_FILE" | tail -20 | while read -r line; do
    timestamp=$(echo "$line" | awk '{print $1" "$2}')
    price=$(echo "$line" | grep -oE '\$[0-9,]+')
    order_id=$(echo "$line" | grep -oE 'ID[: ]+[0-9]+' | grep -oE '[0-9]+')
    echo "  $timestamp | $price | Order: $order_id"
done
echo ""

# Check for duplicate orders at same price within 5 minutes
echo "🚨 Potential Duplicate Orders (same price, <5min gap):"
grep "BUY order placed @" "$LOG_FILE" | tail -50 | awk '{
    timestamp = $1" "$2
    price = $10
    if (prices[price]) {
        print "  DUPLICATE: " price " at " timestamp " (previous: " prices[price] ")"
    }
    prices[price] = timestamp
}'
echo ""

# Check fill processing timing
echo "⏱️  Fill Processing Timeline:"
grep -E "_on_fill_processed|Fill detected|TP placed" "$LOG_FILE" | tail -20
echo ""

# Mutex lock analysis
echo "🔒 Mutex Lock Activity:"
grep -E "position_mgr.state_lock|Acquiring lock|Released lock" "$LOG_FILE" | tail -10
echo ""

# Reconciliation timing
echo "🔄 Reconciliation Events:"
grep -E "Pending.*adjustment|reconcile|Reconciliation complete" "$LOG_FILE" | tail -15
echo ""

# Critical sequence analysis
echo "🎯 Critical: Fill → TP → Next Order Sequence"
echo "(Last 5 sequences)"
grep -E "filled @|TP.*placed|Next BUY placed|Next SELL placed" "$LOG_FILE" | tail -15
echo ""

# Summary
echo "=== RISK INDICATORS ==="
dup_count=$(grep "BUY order placed @" "$LOG_FILE" | tail -100 | awk '{print $10}' | sort | uniq -d | wc -l)
rapid_orders=$(grep "BUY order placed" "$LOG_FILE" | tail -20 | awk '{
    if (prev != "") {
        cmd = "date -j -f \"%Y-%m-%d %H:%M:%S\" \""$1" "$2"\" +%s"
        cmd | getline curr_time
        close(cmd)
        
        cmd2 = "date -j -f \"%Y-%m-%d %H:%M:%S\" \"" prev_time "\" +%s"
        cmd2 | getline prev_time_sec
        close(cmd2)
        
        gap = curr_time - prev_time_sec
        if (gap < 30) print gap
    }
    prev_time = $1" "$2
    prev = $0
}' | wc -l)

echo "Duplicate price orders (last 100): $dup_count"
echo "Orders placed <30s apart (last 20): $(echo $rapid_orders | tr -d ' ')"
echo "Throttle activations: $(grep -c THROTTLE "$LOG_FILE")"
echo ""

if [ "$(echo $rapid_orders | tr -d ' ')" -gt 0 ] || [ "$dup_count" -gt 0 ]; then
    echo "⚠️  WARNING: Potential race condition detected!"
    echo "   Check logs for duplicate orders or rapid placement"
else
    echo "✅ No obvious race conditions in recent logs"
fi
