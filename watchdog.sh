#!/bin/bash

# Process Watchdog - Ensures only one of each bot type runs
# Runs every minute via cron

BOT_DIR="/Users/shailendrasinghrajawat/Projects/WorkingBot"
PID_DIR="$BOT_DIR/.pids"

# PID files
TRADING_PID="$PID_DIR/trading_bot.pid"
HEALTH_PID="$PID_DIR/health_bot.pid"
MONITORING_PID="$PID_DIR/monitoring_bot.pid"

# Function to check if process is running
is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

# Function to count running processes of a type
count_processes() {
    local pattern=$1
    ps aux | grep -E "$pattern" | grep -v grep | wc -l
}

# Check for multiple trading bots
trading_count=$(count_processes "python.*bot.run")
if [ "$trading_count" -gt 1 ]; then
    echo "$(date): WARNING - Multiple trading bots detected ($trading_count). Cleaning up..."
    pkill -f "python.*bot.run"
    sleep 2
    # Restart one trading bot
    cd "$BOT_DIR"
    nohup python3 -m bot.run > "$BOT_DIR/logs/trading_bot.log" 2>&1 &
    echo $! > "$TRADING_PID"
fi

# Check for multiple health monitors
health_count=$(count_processes "python.*health")
if [ "$health_count" -gt 1 ]; then
    echo "$(date): WARNING - Multiple health monitors detected ($health_count). Cleaning up..."
    pkill -f "python.*health"
    sleep 2
    # Restart one health monitor
    cd "$BOT_DIR"
    nohup python3 -m bot.health.health_monitor > "$BOT_DIR/logs/health_monitor.log" 2>&1 &
    echo $! > "$HEALTH_PID"
fi

# Check for multiple monitoring bots
monitoring_count=$(count_processes "python.*monitoring")
if [ "$monitoring_count" -gt 1 ]; then
    echo "$(date): WARNING - Multiple monitoring bots detected ($monitoring_count). Cleaning up..."
    pkill -f "python.*monitoring"
    sleep 2
    # Restart one monitoring bot
    cd "$BOT_DIR"
    nohup python3 -m bot.monitoring.webui > "$BOT_DIR/logs/monitoring_bot.log" 2>&1 &
    echo $! > "$MONITORING_PID"
fi

# Log status every hour
if [ $(date +%M) = "00" ]; then
    echo "$(date): Watchdog check - Trading: $trading_count, Health: $health_count, Monitoring: $monitoring_count"
fi
