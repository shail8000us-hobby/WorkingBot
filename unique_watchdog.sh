#!/bin/bash

# Unique Bot Watchdog - Ensures only ONE bot system runs
# This script runs every minute and enforces uniqueness

BOT_DIR="/Users/shailendrasinghrajawat/Projects/WorkingBot"
LOCK_FILE="$BOT_DIR/.bot_manager.lock"
PID_FILE="$BOT_DIR/.bot_manager.pid"

# Function to check if our bot manager is running
is_our_manager_running() {
    if [ -f "$LOCK_FILE" ] && [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            # Clean up stale files
            rm -f "$LOCK_FILE" "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Function to kill all unauthorized bot processes
kill_unauthorized_bots() {
    echo "$(date): Checking for unauthorized bot processes..."
    
    # Kill all Python processes with bot-related names
    pkill -f "python.*bot" 2>/dev/null
    pkill -f "python.*trading" 2>/dev/null
    pkill -f "python.*grid" 2>/dev/null
    pkill -f "python.*run" 2>/dev/null
    pkill -f "app.py" 2>/dev/null
    
    # Kill all SSR processes
    pkill -f "ssr" 2>/dev/null
    pkill -f "grid_loop" 2>/dev/null
    
    # Kill any other suspicious processes
    ps aux | grep -E "(bot|trading|grid|run)" | grep -v grep | grep -v "unique_" | awk '{print $2}' | xargs kill -9 2>/dev/null
}

# Function to stop unauthorized launchd services
stop_unauthorized_services() {
    echo "$(date): Checking for unauthorized launchd services..."
    
    # Stop all bot-related services
    launchctl unload ~/Library/LaunchAgents/com.ssr.*.plist 2>/dev/null
    launchctl unload ~/Library/LaunchAgents/com.gridbot.*.plist 2>/dev/null
    launchctl unload ~/Library/LaunchAgents/com.*.bot.*.plist 2>/dev/null
}

# Main watchdog logic
main() {
    echo "$(date): Unique Bot Watchdog running..."
    
    # If our manager is not running, kill everything
    if ! is_our_manager_running; then
        echo "$(date): Our bot manager not running - killing all unauthorized bots"
        kill_unauthorized_bots
        stop_unauthorized_services
    else
        echo "$(date): Our bot manager is running - checking for unauthorized processes"
        # Still kill unauthorized processes even if our manager is running
        kill_unauthorized_bots
    fi
    
    # Log status every hour
    if [ $(date +%M) = "00" ]; then
        echo "$(date): Watchdog check complete"
    fi
}

# Run the watchdog
main
