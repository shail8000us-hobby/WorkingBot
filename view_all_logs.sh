#!/bin/bash
# View all bot logs together for debugging

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║              COMBINED LOGS - Bot + Guardian + Reconciliation      ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Get number of lines (default 100)
LINES=${1:-100}

echo "📊 Showing last $LINES lines from each process..."
echo ""

# Create temp files for each log
GRIDBOT_LOG=$(mktemp)
GUARDIAN_LOG=$(mktemp)

# Fetch logs
pm2 logs gridbot-live --lines $LINES --nostream > "$GRIDBOT_LOG" 2>&1
pm2 logs guardian-live --lines $LINES --nostream > "$GUARDIAN_LOG" 2>&1

# Combine and sort by timestamp
{
    # GridBot logs with prefix
    cat "$GRIDBOT_LOG" | while IFS= read -r line; do
        echo -e "${GREEN}[GRIDBOT]${NC} $line"
    done
    
    # Guardian logs with prefix
    cat "$GUARDIAN_LOG" | while IFS= read -r line; do
        echo -e "${BLUE}[GUARDIAN]${NC} $line"
    done
} | sort -t: -k1,2

# Cleanup
rm -f "$GRIDBOT_LOG" "$GUARDIAN_LOG"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💡 Usage: ./view_all_logs.sh [lines]"
echo "   Example: ./view_all_logs.sh 200  (show last 200 lines)"
echo ""
echo "🔍 Filter specific issues:"
echo "   ./view_all_logs.sh 500 | grep -i error"
echo "   ./view_all_logs.sh 500 | grep -i '92000'"
echo "   ./view_all_logs.sh 500 | grep -i reconciliation"
