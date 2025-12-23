#!/bin/bash

# Bot Process Manager - Ensures only one of each type runs
# Usage: ./bot_manager.sh [start|stop|status|restart] [trading|health|monitoring]

BOT_DIR="/Users/shailendrasinghrajawat/Projects/WorkingBot"
PID_DIR="$BOT_DIR/.pids"
LOG_DIR="$BOT_DIR/logs"

# Create necessary directories
mkdir -p "$PID_DIR" "$LOG_DIR"

# PID files
TRADING_PID="$PID_DIR/trading_bot.pid"
HEALTH_PID="$PID_DIR/health_bot.pid"
MONITORING_PID="$PID_DIR/monitoring_bot.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Function to start trading bot
start_trading() {
    echo -e "${BLUE}Starting Trading Bot...${NC}"
    
    if is_running "$TRADING_PID"; then
        echo -e "${YELLOW}Trading bot is already running (PID: $(cat $TRADING_PID))${NC}"
        return 1
    fi
    
    # Kill any existing trading processes
    pkill -f "python.*bot.run" 2>/dev/null
    pkill -f "python.*bot.guardian" 2>/dev/null
    
    # Start trading bot
    cd "$BOT_DIR"
    nohup python3 -m bot.run > "$LOG_DIR/trading_bot.log" 2>&1 &
    local pid=$!
    echo $pid > "$TRADING_PID"
    
    sleep 2
    if is_running "$TRADING_PID"; then
        echo -e "${GREEN}Trading bot started successfully (PID: $pid)${NC}"
        return 0
    else
        echo -e "${RED}Failed to start trading bot${NC}"
        rm -f "$TRADING_PID"
        return 1
    fi
}

# Function to start health monitor
start_health() {
    echo -e "${BLUE}Starting Health Monitor...${NC}"
    
    if is_running "$HEALTH_PID"; then
        echo -e "${YELLOW}Health monitor is already running (PID: $(cat $HEALTH_PID))${NC}"
        return 1
    fi
    
    # Kill any existing health processes
    pkill -f "python.*health" 2>/dev/null
    pkill -f "python.*monitor" 2>/dev/null
    
    # Start health monitor
    cd "$BOT_DIR"
    nohup python3 -m bot.health.health_monitor > "$LOG_DIR/health_monitor.log" 2>&1 &
    local pid=$!
    echo $pid > "$HEALTH_PID"
    
    sleep 2
    if is_running "$HEALTH_PID"; then
        echo -e "${GREEN}Health monitor started successfully (PID: $pid)${NC}"
        return 0
    else
        echo -e "${RED}Failed to start health monitor${NC}"
        rm -f "$HEALTH_PID"
        return 1
    fi
}

# Function to start monitoring bot
start_monitoring() {
    echo -e "${BLUE}Starting Monitoring Bot...${NC}"
    
    if is_running "$MONITORING_PID"; then
        echo -e "${YELLOW}Monitoring bot is already running (PID: $(cat $MONITORING_PID))${NC}"
        return 1
    fi
    
    # Kill any existing monitoring processes
    pkill -f "python.*monitoring" 2>/dev/null
    pkill -f "python.*webui" 2>/dev/null
    
    # Start monitoring bot
    cd "$BOT_DIR"
    nohup python3 -m bot.monitoring.webui > "$LOG_DIR/monitoring_bot.log" 2>&1 &
    local pid=$!
    echo $pid > "$MONITORING_PID"
    
    sleep 2
    if is_running "$MONITORING_PID"; then
        echo -e "${GREEN}Monitoring bot started successfully (PID: $pid)${NC}"
        return 0
    else
        echo -e "${RED}Failed to start monitoring bot${NC}"
        rm -f "$MONITORING_PID"
        return 1
    fi
}

# Function to stop specific bot
stop_bot() {
    local bot_type=$1
    local pid_file=""
    local process_name=""
    
    case $bot_type in
        "trading")
            pid_file="$TRADING_PID"
            process_name="Trading Bot"
            ;;
        "health")
            pid_file="$HEALTH_PID"
            process_name="Health Monitor"
            ;;
        "monitoring")
            pid_file="$MONITORING_PID"
            process_name="Monitoring Bot"
            ;;
        *)
            echo -e "${RED}Invalid bot type: $bot_type${NC}"
            return 1
            ;;
    esac
    
    echo -e "${YELLOW}Stopping $process_name...${NC}"
    
    if is_running "$pid_file"; then
        local pid=$(cat "$pid_file")
        
        # Send SIGTERM (graceful shutdown)
        echo -e "${BLUE}Sending graceful shutdown signal (SIGTERM)...${NC}"
        kill -TERM "$pid" 2>/dev/null
        
        # Wait up to 30 seconds for cleanup to complete
        echo -e "${BLUE}Waiting for cleanup (max 30 seconds)...${NC}"
        for i in {1..30}; do
            if ! is_running "$pid_file"; then
                echo -e "${GREEN}$process_name stopped gracefully after ${i} seconds${NC}"
                rm -f "$pid_file"
                return 0
            fi
            sleep 1
        done
        
        # Still running after 30 seconds, use force
        if is_running "$pid_file"; then
            echo -e "${YELLOW}⚠️  Process still running after 30s, using force kill...${NC}"
            kill -9 "$pid" 2>/dev/null
            sleep 1
        fi
        
        rm -f "$pid_file"
        echo -e "${GREEN}$process_name stopped${NC}"
    else
        echo -e "${YELLOW}$process_name is not running${NC}"
    fi
}

# Function to show status
show_status() {
    echo -e "${BLUE}=== BOT PROCESS STATUS ===${NC}"
    echo ""
    
    # Trading Bot
    if is_running "$TRADING_PID"; then
        local pid=$(cat "$TRADING_PID")
        echo -e "${GREEN}✓ Trading Bot: RUNNING (PID: $pid)${NC}"
    else
        echo -e "${RED}✗ Trading Bot: STOPPED${NC}"
    fi
    
    # Health Monitor
    if is_running "$HEALTH_PID"; then
        local pid=$(cat "$HEALTH_PID")
        echo -e "${GREEN}✓ Health Monitor: RUNNING (PID: $pid)${NC}"
    else
        echo -e "${RED}✗ Health Monitor: STOPPED${NC}"
    fi
    
    # Monitoring Bot
    if is_running "$MONITORING_PID"; then
        local pid=$(cat "$MONITORING_PID")
        echo -e "${GREEN}✓ Monitoring Bot: RUNNING (PID: $pid)${NC}"
    else
        echo -e "${RED}✗ Monitoring Bot: STOPPED${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}=== SYSTEM PROCESSES ===${NC}"
    ps aux | grep -E "python.*bot|python.*run|python.*health|python.*monitoring" | grep -v grep || echo "No bot processes found"
}

# Function to stop all bots
stop_all() {
    echo -e "${YELLOW}Stopping all bots...${NC}"
    stop_bot "trading"
    stop_bot "health"
    stop_bot "monitoring"
    
    # Kill any remaining bot processes
    pkill -f "python.*bot" 2>/dev/null
    pkill -f "python.*run" 2>/dev/null
    
    echo -e "${GREEN}All bots stopped${NC}"
}

# Function to start all bots
start_all() {
    echo -e "${BLUE}Starting all bots...${NC}"
    start_health
    start_monitoring
    start_trading
}

# Main script logic
case $1 in
    "start")
        case $2 in
            "trading") start_trading ;;
            "health") start_health ;;
            "monitoring") start_monitoring ;;
            "all") start_all ;;
            *) echo -e "${RED}Usage: $0 start [trading|health|monitoring|all]${NC}" ;;
        esac
        ;;
    "stop")
        case $2 in
            "trading") stop_bot "trading" ;;
            "health") stop_bot "health" ;;
            "monitoring") stop_bot "monitoring" ;;
            "all") stop_all ;;
            *) echo -e "${RED}Usage: $0 stop [trading|health|monitoring|all]${NC}" ;;
        esac
        ;;
    "restart")
        case $2 in
            "trading") stop_bot "trading" && sleep 2 && start_trading ;;
            "health") stop_bot "health" && sleep 2 && start_health ;;
            "monitoring") stop_bot "monitoring" && sleep 2 && start_monitoring ;;
            "all") stop_all && sleep 3 && start_all ;;
            *) echo -e "${RED}Usage: $0 restart [trading|health|monitoring|all]${NC}" ;;
        esac
        ;;
    "status")
        show_status
        ;;
    *)
        echo -e "${BLUE}Bot Process Manager${NC}"
        echo "Usage: $0 [start|stop|restart|status] [trading|health|monitoring|all]"
        echo ""
        echo "Examples:"
        echo "  $0 start trading     # Start only trading bot"
        echo "  $0 stop all          # Stop all bots"
        echo "  $0 restart trading   # Restart trading bot"
        echo "  $0 status            # Show status of all bots"
        ;;
esac
