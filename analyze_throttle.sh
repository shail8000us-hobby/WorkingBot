#!/bin/bash
# Throttle Mechanism Analyzer
# Monitors order timing and throttle effectiveness
# Created: Nov 7, 2025

echo "🚦 Throttle Mechanism Analyzer"
echo "=============================="
echo ""

LOG_FILE="/Users/ssr/Projects/WorkingBot/bot/logs/bot.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Log file not found: $LOG_FILE"
    exit 1
fi

echo "📊 Analyzing order timing from logs..."
echo ""

# Extract throttle events
echo "=== THROTTLE EVENTS ==="
grep "THROTTLE" "$LOG_FILE" | tail -20
echo ""

# Extract order placements with timestamps
echo "=== RECENT ORDER PLACEMENTS ==="
grep -E "BUY order placed|SELL order placed" "$LOG_FILE" | tail -20
echo ""

# Extract missed fills
echo "=== MISSED FILL DETECTION ==="
grep -E "Missed fill detected|order state='filled'" "$LOG_FILE" | tail -10
echo ""

# Check for race conditions
echo "=== POTENTIAL RACE CONDITIONS ==="
grep -E "Pending BUY adjustment|Pending SELL adjustment" "$LOG_FILE" | tail -10
echo ""

# Summary statistics
echo "=== STATISTICS (Last 24 hours) ==="
CUTOFF_TIME=$(date -v-24H "+%Y-%m-%d %H:%M:%S")
echo "Throttle activations: $(grep -c "THROTTLE" "$LOG_FILE" || echo 0)"
echo "BUY orders placed: $(grep -c "BUY order placed" "$LOG_FILE" || echo 0)"
echo "SELL orders placed: $(grep -c "SELL order placed" "$LOG_FILE" || echo 0)"
echo "Missed fills detected: $(grep -c "Missed fill detected" "$LOG_FILE" || echo 0)"
echo ""

# Real-time monitor option
read -p "Start real-time monitor? (y/n): " monitor
if [ "$monitor" = "y" ]; then
    echo "👀 Monitoring for throttle and order events (Ctrl+C to stop)..."
    tail -f "$LOG_FILE" | grep --line-buffered -E "THROTTLE|order placed|Missed fill|adjustment needed"
fi
