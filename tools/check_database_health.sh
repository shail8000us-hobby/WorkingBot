#!/bin/bash
#
# Quick Database Stats - Check Event Database Health
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DB_PATH="$PROJECT_ROOT/data/bot_events_LONG.db"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "   📊 EVENT DATABASE HEALTH CHECK"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Database file size
if [ -f "$DB_PATH" ]; then
    DB_SIZE=$(ls -lh "$DB_PATH" | awk '{print $5}')
    echo "Database Size: $DB_SIZE"
    echo ""
else
    echo "❌ Database not found: $DB_PATH"
    exit 1
fi

# Event counts
echo "Event Counts:"
sqlite3 "$DB_PATH" "SELECT event_type, COUNT(*) as count FROM events GROUP BY event_type ORDER BY count DESC LIMIT 10" | \
    awk -F'|' '{printf "  %-30s %10s\n", $1, $2}'

echo ""

# Total events
TOTAL=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM events")
echo "Total Events: $(printf "%'d" $TOTAL)"

# Guardian signal ratio
GUARDIAN_GO=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM events WHERE event_type='guardian_signal_go'")
GUARDIAN_STOP=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM events WHERE event_type='guardian_signal_stop'")
GUARDIAN_TOTAL=$((GUARDIAN_GO + GUARDIAN_STOP))
GUARDIAN_PCT=$(echo "scale=1; $GUARDIAN_TOTAL * 100 / $TOTAL" | bc)

echo "Guardian Signals: $(printf "%'d" $GUARDIAN_TOTAL) (${GUARDIAN_PCT}% of total)"

# Date range
OLDEST=$(sqlite3 "$DB_PATH" "SELECT datetime(MIN(timestamp), 'unixepoch', 'localtime') FROM events")
NEWEST=$(sqlite3 "$DB_PATH" "SELECT datetime(MAX(timestamp), 'unixepoch', 'localtime') FROM events")

echo ""
echo "Date Range:"
echo "  Oldest: $OLDEST"
echo "  Newest: $NEWEST"

echo ""

# Memory warning
if [ $TOTAL -gt 50000 ]; then
    echo "⚠️  WARNING: Database has >50K events"
    echo "   Recommended: Run cleanup to free memory"
    echo "   Command: ./tools/emergency_memory_fix.sh"
elif [ $TOTAL -gt 100000 ]; then
    echo "🚨 CRITICAL: Database has >100K events"  
    echo "   High memory usage - cleanup URGENTLY needed!"
    echo "   Command: ./tools/emergency_memory_fix.sh"
else
    echo "✅ Database size healthy (<50K events)"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
