#!/bin/bash
# ============================================================================
# Mac → Windows Bot Remote Control Script
# ============================================================================
# 
# This script allows Mac to remotely control the Windows GridBot via SMB mount.
# Since SSH is not available on Windows (192.168.1.32), we use SMB file operations
# to trigger actions.
#
# Usage:
#   ./control_windows_bot.sh start     # Start Windows bot (demo mode)
#   ./control_windows_bot.sh stop      # Stop Windows bot
#   ./control_windows_bot.sh status    # Check Windows bot status
#   ./control_windows_bot.sh logs      # View last 100 lines of Windows logs
#
# Requirements:
#   - Windows D_Drive mounted at /Volumes/D_Drive-1
#   - Windows batch files exist (start_bot.bat, stop_bot.bat)
#
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
WINDOWS_IP="192.168.1.32"
WINDOWS_MOUNT="/Volumes/D_Drive-1"
WINDOWS_PROJECT_DIR="$WINDOWS_MOUNT/Projects/WorkingBot"
COMMAND_FILE="$WINDOWS_PROJECT_DIR/.remote_command"
RESPONSE_FILE="$WINDOWS_PROJECT_DIR/.remote_response"

# Check if action provided
ACTION="${1:-}"

if [ -z "$ACTION" ]; then
    echo -e "${RED}❌ Error: Action required${NC}"
    echo "Usage: $0 [start|stop|status|logs|verify]"
    exit 1
fi

# Function to check if Windows share is mounted
check_mount() {
    if [ ! -d "$WINDOWS_MOUNT" ]; then
        echo -e "${RED}❌ Windows share not mounted at $WINDOWS_MOUNT${NC}"
        echo -e "${YELLOW}Attempting to mount...${NC}"
        open "smb://smbuser@${WINDOWS_IP}/D_Drive"
        sleep 3
        if [ ! -d "$WINDOWS_MOUNT" ]; then
            echo -e "${RED}❌ Failed to mount. Please mount manually.${NC}"
            exit 1
        fi
    fi
    echo -e "${GREEN}✅ Windows share mounted${NC}"
}

# Function to write command for Windows to execute
write_command() {
    local cmd="$1"
    echo "$cmd" > "$COMMAND_FILE"
    echo -e "${BLUE}📤 Command written: $cmd${NC}"
}

# Function to wait for response (if Windows has a polling script)
wait_response() {
    local timeout=30
    local elapsed=0
    rm -f "$RESPONSE_FILE" 2>/dev/null || true
    
    while [ $elapsed -lt $timeout ]; do
        if [ -f "$RESPONSE_FILE" ]; then
            cat "$RESPONSE_FILE"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    
    echo -e "${YELLOW}⚠️  No response from Windows (timeout)${NC}"
    return 1
}

# Function to start Windows bot via batch file
start_bot() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}   Starting Windows Bot (Demo Mode - Testnet)${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Create a PowerShell command file that Windows can execute
    cat > "$WINDOWS_PROJECT_DIR/run_start_bot.ps1" << 'PSEOF'
Set-Location "D:\Projects\WorkingBot"
$Env:PYTHONPATH = "D:\Projects\WorkingBot"
$Env:TRADING_MODE = "demo"
$Env:EXECUTE_ORDERS = "false"

# Start bot using batch file
Start-Process -FilePath "cmd" -ArgumentList "/c","start_bot.bat demo" -NoNewWindow
Start-Sleep -Seconds 2

# Write status
"Bot start command executed at $(Get-Date)" | Out-File -FilePath "D:\Projects\WorkingBot\.remote_response" -Encoding utf8
PSEOF
    
    echo -e "${GREEN}✅ Created PowerShell startup script on Windows${NC}"
    echo -e "${YELLOW}⚠️  Windows must execute: powershell.exe -File D:\\Projects\\WorkingBot\\run_start_bot.ps1${NC}"
    echo ""
    echo -e "${BLUE}Since SSH is not available, please manually run on Windows:${NC}"
    echo -e "${CYAN}PowerShell (as Admin):${NC}"
    echo "  cd D:\\Projects\\WorkingBot"
    echo "  powershell.exe -ExecutionPolicy Bypass -File run_start_bot.ps1"
    echo ""
    echo "OR double-click: start_bot.bat"
}

# Function to stop Windows bot
stop_bot() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}   Stopping Windows Bot${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Create stop script
    cat > "$WINDOWS_PROJECT_DIR/run_stop_bot.ps1" << 'PSEOF'
Set-Location "D:\Projects\WorkingBot"

# Find and kill bot process
$procs = Get-Process | Where-Object { $_.Path -and ($_.Path -like '*python*') -and ($_.CommandLine -like '*bot\run.py*') }
if ($procs) {
    foreach ($p in $procs) {
        Stop-Process -Id $p.Id -Force
        "Stopped PID: $($p.Id)" | Out-File -FilePath "D:\Projects\WorkingBot\.remote_response" -Append -Encoding utf8
    }
} else {
    "No bot process found" | Out-File -FilePath "D:\Projects\WorkingBot\.remote_response" -Encoding utf8
}
PSEOF
    
    echo -e "${GREEN}✅ Created PowerShell stop script on Windows${NC}"
    echo -e "${YELLOW}⚠️  Windows must execute: powershell.exe -File D:\\Projects\\WorkingBot\\run_stop_bot.ps1${NC}"
}

# Function to check bot status
check_status() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}   Windows Bot Status${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Check if heartbeat file exists and is recent
    local heartbeat="$WINDOWS_PROJECT_DIR/.heartbeat"
    if [ -f "$heartbeat" ]; then
        local last_update=$(stat -f "%Sm" "$heartbeat")
        echo -e "${GREEN}✅ Heartbeat file exists${NC}"
        echo -e "   Last update: $last_update"
    else
        echo -e "${RED}❌ No heartbeat file${NC}"
    fi
    
    # Check if log file exists and show last few lines
    local logfile="$WINDOWS_PROJECT_DIR/bot/logs/bot.log"
    if [ -f "$logfile" ]; then
        echo ""
        echo -e "${BLUE}Last 5 log entries:${NC}"
        tail -5 "$logfile"
    else
        echo -e "${RED}❌ No log file found${NC}"
    fi
    
    # Check if guardian is running
    local guardian_health="$WINDOWS_PROJECT_DIR/.guardian_health"
    if [ -f "$guardian_health" ]; then
        echo ""
        echo -e "${GREEN}✅ Guardian health file exists${NC}"
        cat "$guardian_health"
    fi
}

# Function to view logs
view_logs() {
    local logfile="$WINDOWS_PROJECT_DIR/bot/logs/bot.log"
    local lines="${2:-100}"
    
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}   Windows Bot Logs (Last $lines lines)${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    if [ -f "$logfile" ]; then
        tail -n "$lines" "$logfile"
    else
        echo -e "${RED}❌ Log file not found: $logfile${NC}"
    fi
}

# Function to verify sync and files
verify_sync() {
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}   Verifying Windows Bot Files${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    local files=(
        "bot/run.py"
        "bot/strategy/gridbot.py"
        "bot/strategy/modules/grid_calculator.py"
        "bot/strategy/modules/position_manager.py"
        "bot/strategy/handlers/long_handler.py"
        "grid_config.env"
        "start_bot.bat"
    )
    
    local all_ok=true
    for file in "${files[@]}"; do
        if [ -f "$WINDOWS_PROJECT_DIR/$file" ]; then
            local size=$(stat -f "%z" "$WINDOWS_PROJECT_DIR/$file")
            local date=$(stat -f "%Sm" "$WINDOWS_PROJECT_DIR/$file")
            echo -e "${GREEN}✅${NC} $file (${size} bytes, $date)"
        else
            echo -e "${RED}❌${NC} $file (MISSING)"
            all_ok=false
        fi
    done
    
    echo ""
    if [ "$all_ok" = true ]; then
        echo -e "${GREEN}✅ All critical files present${NC}"
    else
        echo -e "${RED}❌ Some files are missing${NC}"
    fi
}

# Main logic
check_mount

case "$ACTION" in
    start)
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    status)
        check_status
        ;;
    logs)
        view_logs "$@"
        ;;
    verify)
        verify_sync
        ;;
    *)
        echo -e "${RED}❌ Unknown action: $ACTION${NC}"
        echo "Valid actions: start, stop, status, logs, verify"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Command completed${NC}"
