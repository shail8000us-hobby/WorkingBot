#!/bin/bash
# Watch all bot logs together in real-time

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         LIVE LOGS - Bot + Guardian (Press Ctrl+C to exit)        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "🔴 LIVE MODE - Logs updating continuously..."
echo ""

# Function to format log line with color
format_log() {
    local source=$1
    local line=$2
    
    if [ "$source" = "gridbot" ]; then
        echo -e "${GREEN}[GRIDBOT]${NC} $line"
    else
        echo -e "${BLUE}[GUARDIAN]${NC} $line"
    fi
}

# Use pm2 logs with --raw flag for continuous streaming
# This will show logs from both processes, color-coded
pm2 logs --raw --lines 50 | while IFS= read -r line; do
    # Detect which process the log is from
    if [[ $line == *"gridbot-live"* ]] || [[ $line == "3|gridbot-"* ]]; then
        format_log "gridbot" "$line"
    elif [[ $line == *"guardian-live"* ]] || [[ $line == "1|guardian"* ]]; then
        format_log "guardian" "$line"
    else
        # Unknown source, just print it
        echo "$line"
    fi
done
