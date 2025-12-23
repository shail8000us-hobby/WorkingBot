#!/bin/bash
# Watch logs with optional filtering

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Get filter from command line (optional)
FILTER=${1:-""}

clear
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         LIVE LOGS - Bot + Guardian (Press Ctrl+C to exit)        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

if [ -n "$FILTER" ]; then
    echo -e "${YELLOW}🔍 Filter active: ${BOLD}$FILTER${NC}"
else
    echo -e "${GREEN}📊 Showing all logs${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Function to colorize important keywords
colorize_line() {
    local line=$1
    
    # Highlight errors in red
    line=$(echo "$line" | sed -E "s/(ERROR|CRITICAL|FAILED|❌)/${RED}\1${NC}/gi")
    
    # Highlight warnings in yellow
    line=$(echo "$line" | sed -E "s/(WARNING|WARN|⚠️)/${YELLOW}\1${NC}/gi")
    
    # Highlight success in green
    line=$(echo "$line" | sed -E "s/(SUCCESS|PASS|✅|🟢)/${GREEN}\1${NC}/gi")
    
    # Highlight prices in cyan
    line=$(echo "$line" | sed -E "s/(\$[0-9,]+\.?[0-9]*|₹[0-9,]+\.?[0-9]*)/${CYAN}\1${NC}/g")
    
    # Highlight order IDs in magenta
    line=$(echo "$line" | sed -E "s/(Order ID: [0-9]+|order_id[\":]* *[0-9]+)/${MAGENTA}\1${NC}/gi")
    
    echo -e "$line"
}

# Stream logs with color coding
if [ -n "$FILTER" ]; then
    # With filter
    pm2 logs --raw --lines 100 | grep -i "$FILTER" --line-buffered | while IFS= read -r line; do
        if [[ $line == *"gridbot"* ]] || [[ $line == "3|"* ]]; then
            colorize_line "${GREEN}[BOT]${NC} $line"
        elif [[ $line == *"guardian"* ]] || [[ $line == "1|"* ]]; then
            colorize_line "${BLUE}[GRD]${NC} $line"
        else
            colorize_line "$line"
        fi
    done
else
    # No filter - show all
    pm2 logs --raw --lines 100 | while IFS= read -r line; do
        if [[ $line == *"gridbot"* ]] || [[ $line == "3|"* ]]; then
            colorize_line "${GREEN}[BOT]${NC} $line"
        elif [[ $line == *"guardian"* ]] || [[ $line == "1|"* ]]; then
            colorize_line "${BLUE}[GRD]${NC} $line"
        else
            colorize_line "$line"
        fi
    done
fi
