#!/bin/bash
#
# Emergency Memory Fix - Cleanup Event Database
# 
# Run this script to immediately clean up the bloated event database
# and free up system memory.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "   🚨 EMERGENCY MEMORY FIX"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check if bot is running
if pgrep -f "guardian_bot.py" > /dev/null; then
    echo "⚠️  Guardian bot is currently running"
    echo ""
    echo "For safety, please stop the bot first:"
    echo "  killall -TERM python3"
    echo ""
    read -p "Stop guardian bot now? (yes/no): " response
    if [ "$response" = "yes" ]; then
        echo "Stopping guardian bot..."
        killall -TERM python3 || true
        sleep 2
        echo "✅ Bot stopped"
    else
        echo "❌ Cleanup cancelled - please stop the bot manually first"
        exit 1
    fi
fi

echo ""
echo "Running database cleanup..."
echo ""

# Run cleanup (dry-run first)
cd "$PROJECT_ROOT"
python3 tools/cleanup_event_database.py --dry-run

echo ""
read -p "Proceed with cleanup? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    python3 tools/cleanup_event_database.py --keep-days 7
    
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "   ✅ CLEANUP COMPLETE"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "Next steps:"
    echo "  1. Restart guardian bot (automatic cleanup now active)"
    echo "  2. Monitor memory usage: watch -n 5 'ps aux | grep guardian'"
    echo "  3. Database will auto-cleanup every hour going forward"
    echo ""
else
    echo "❌ Cleanup cancelled"
    exit 1
fi
