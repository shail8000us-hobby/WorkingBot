#!/bin/bash
# Shadow Mode Deployment Dashboard
# Real-time monitoring for Phase 2+3 deployment validation

REPORT_FILE="logs/shadow_mode_report.json"
STATE_DIR="migration_states"
LOG_FILE="logs/deployment_$(date +%Y%m%d).log"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

clear

echo "╔════════════════════════════════════════════════════════╗"
echo "║     Phase 2+3 Shadow Mode Deployment Dashboard        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Function to display metrics
show_metrics() {
    if [ -f "$REPORT_FILE" ]; then
        local match_rate=$(jq -r '.match_rate // 0' "$REPORT_FILE")
        local comparisons=$(jq -r '.stats.comparisons // 0' "$REPORT_FILE")
        local matches=$(jq -r '.stats.matches // 0' "$REPORT_FILE")
        local discrepancies=$(jq -r '.stats.discrepancies // 0' "$REPORT_FILE")
        local async_errors=$(jq -r '.stats.async_errors // 0' "$REPORT_FILE")
        local threaded_errors=$(jq -r '.stats.threaded_errors // 0' "$REPORT_FILE")
        local duration=$(jq -r '.duration_minutes // 0' "$REPORT_FILE")
        
        # Display status
        echo -e "${BLUE}═══ Deployment Status ═══${NC}"
        echo -e "Duration:        ${duration} minutes"
        echo -e "Comparisons:     ${comparisons}"
        echo ""
        
        # Match rate (color coded)
        if (( $(echo "$match_rate >= 99.9" | bc -l) )); then
            echo -e "Match Rate:      ${GREEN}${match_rate}%${NC} ✅ READY FOR CUTOVER"
        elif (( $(echo "$match_rate >= 95.0" | bc -l) )); then
            echo -e "Match Rate:      ${YELLOW}${match_rate}%${NC} ⚠️  INVESTIGATE DISCREPANCIES"
        else
            echo -e "Match Rate:      ${RED}${match_rate}%${NC} ❌ NOT READY"
        fi
        
        echo ""
        echo -e "${BLUE}═══ Details ═══${NC}"
        echo -e "Matches:         ${GREEN}${matches}${NC}"
        echo -e "Discrepancies:   ${YELLOW}${discrepancies}${NC}"
        echo -e "Async Errors:    ${RED}${async_errors}${NC}"
        echo -e "Threaded Errors: ${RED}${threaded_errors}${NC}"
        echo ""
        
        # Recent discrepancies
        if [ "$discrepancies" -gt 0 ]; then
            echo -e "${YELLOW}═══ Recent Discrepancies ═══${NC}"
            jq -r '.recent_discrepancies[]? | "[\(.timestamp)] \(.details.type // "unknown")"' "$REPORT_FILE" | tail -5
            echo ""
        fi
    else
        echo -e "${YELLOW}⏳ Waiting for report file...${NC}"
        echo ""
    fi
}

# Function to show recent logs
show_logs() {
    echo -e "${BLUE}═══ Recent Events ═══${NC}"
    if [ -f "$LOG_FILE" ]; then
        tail -10 "$LOG_FILE" | while read -r line; do
            if [[ "$line" == *"✅"* ]]; then
                echo -e "${GREEN}${line}${NC}"
            elif [[ "$line" == *"⚠️"* ]]; then
                echo -e "${YELLOW}${line}${NC}"
            elif [[ "$line" == *"❌"* ]]; then
                echo -e "${RED}${line}${NC}"
            else
                echo "$line"
            fi
        done
    else
        echo "No log file yet"
    fi
    echo ""
}

# Function to show system status
show_system_status() {
    echo -e "${BLUE}═══ System Health ═══${NC}"
    
    # Check if async system is running
    if pgrep -f "async_gridbot" > /dev/null; then
        echo -e "Async System:    ${GREEN}RUNNING${NC}"
    else
        echo -e "Async System:    ${RED}STOPPED${NC}"
    fi
    
    # Check if threaded system is running (PM2 or direct)
    if pm2 list 2>/dev/null | grep -q "gridbot-.*online"; then
        local bot_name=$(pm2 list 2>/dev/null | grep "gridbot-.*online" | awk '{print $2}' | head -1)
        echo -e "Threaded System: ${GREEN}RUNNING${NC} (PM2: $bot_name)"
    elif pgrep -f "bot_launcher\|grid_strategy\|bot/run.py" > /dev/null; then
        echo -e "Threaded System: ${GREEN}RUNNING${NC} (Direct)"
    else
        echo -e "Threaded System: ${RED}STOPPED${NC}"
    fi
    
    # Check snapshot freshness
    if [ -f "data/monitoring_snapshot.json" ]; then
        local age=$(($(date +%s) - $(stat -f %m data/monitoring_snapshot.json)))
        if [ "$age" -lt 120 ]; then
            echo -e "Snapshot Age:    ${GREEN}${age}s${NC}"
        else
            echo -e "Snapshot Age:    ${YELLOW}${age}s (STALE)${NC}"
        fi
    else
        echo -e "Snapshot:        ${RED}MISSING${NC}"
    fi
    
    echo ""
}

# Function to show progress bar
show_progress() {
    if [ -f "$REPORT_FILE" ]; then
        local duration=$(jq -r '.duration_minutes // 0' "$REPORT_FILE")
        local target=1440  # 24 hours in minutes
        local progress=$((duration * 100 / target))
        
        echo -e "${BLUE}═══ Progress to 24h Target ═══${NC}"
        printf "["
        local filled=$((progress / 2))
        for ((i=0; i<50; i++)); do
            if [ $i -lt $filled ]; then
                printf "="
            else
                printf " "
            fi
        done
        printf "] %d%%\n" "$progress"
        echo ""
    fi
}

# Main monitoring loop
while true; do
    clear
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║     Phase 2+3 Shadow Mode Deployment Dashboard        ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    echo "Press Ctrl+C to exit"
    echo ""
    
    show_system_status
    show_progress
    show_metrics
    show_logs
    
    echo -e "${BLUE}Last updated: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${BLUE}Refreshing in 10 seconds...${NC}"
    
    sleep 10
done
