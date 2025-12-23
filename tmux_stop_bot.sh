#!/bin/bash
# ============================================================================
# Tmux Bot Stopper - Graceful shutdown with 30s timeout
# ============================================================================
#
# This script properly stops the bot running in tmux by:
# 1. Sending Ctrl+C (SIGINT) to the bot process
# 2. Waiting up to 30 seconds for graceful cleanup
# 3. Only force-killing if cleanup fails
#
# Usage:
#   ./tmux_stop_bot.sh [session_name]
#
# Default session name: gridbot
# ============================================================================

SESSION_NAME="${1:-gridbot}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}🛑 Graceful Bot Shutdown via Tmux${NC}"
echo -e "${BLUE}============================================================================${NC}"

# Check if session exists
if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Tmux session '$SESSION_NAME' not found${NC}"
    echo -e "${YELLOW}   Available sessions:${NC}"
    tmux list-sessions 2>/dev/null || echo -e "${YELLOW}   No tmux sessions running${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found tmux session: $SESSION_NAME${NC}"

# Get the PID of the bot process from the session
echo -e "${BLUE}🔍 Looking for bot process...${NC}"

# Try to find bot PID from reports/bot.pid
if [ -f "reports/bot.pid" ]; then
    BOT_PID=$(cat reports/bot.pid 2>/dev/null)
    
    # Verify process is still running
    if ps -p "$BOT_PID" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Found bot process (PID: $BOT_PID)${NC}"
    else
        echo -e "${YELLOW}⚠️  PID file exists but process not running${NC}"
        BOT_PID=""
    fi
else
    # Fallback: search for python process running bot
    BOT_PID=$(pgrep -f "python.*bot/run.py" 2>/dev/null | head -1)
    
    if [ -n "$BOT_PID" ]; then
        echo -e "${GREEN}✓ Found bot process (PID: $BOT_PID)${NC}"
    else
        echo -e "${YELLOW}⚠️  No bot process found${NC}"
        echo -e "${YELLOW}   Killing tmux session anyway...${NC}"
        tmux kill-session -t "$SESSION_NAME"
        echo -e "${GREEN}✓ Tmux session terminated${NC}"
        exit 0
    fi
fi

# Send Ctrl+C to the tmux session (SIGINT)
echo -e "${BLUE}📤 Sending Ctrl+C (SIGINT) to bot...${NC}"
tmux send-keys -t "$SESSION_NAME" C-c

# Wait up to 30 seconds for graceful shutdown
echo -e "${BLUE}⏳ Waiting for graceful shutdown (max 30 seconds)...${NC}"

for i in {1..60}; do
    # Check if process still exists
    if ! ps -p "$BOT_PID" > /dev/null 2>&1; then
        ELAPSED=$((i / 2))
        echo -e "${GREEN}✅ Bot stopped gracefully (${ELAPSED}s)${NC}"
        
        # Check log for cleanup confirmation
        if tail -50 reports/bot.log 2>/dev/null | grep -q "GRACEFUL SHUTDOWN"; then
            echo -e "${GREEN}✅ Cleanup confirmed in log${NC}"
        else
            echo -e "${YELLOW}⚠️  Note: No 'GRACEFUL SHUTDOWN' message in log${NC}"
        fi
        
        # Kill tmux session
        echo -e "${BLUE}🗑️  Removing tmux session...${NC}"
        tmux kill-session -t "$SESSION_NAME" 2>/dev/null
        echo -e "${GREEN}✅ Done!${NC}"
        exit 0
    fi
    
    # Progress indicator every 5 seconds
    if [ $((i % 10)) -eq 0 ]; then
        ELAPSED=$((i / 2))
        echo -e "${YELLOW}   Still waiting... (${ELAPSED}s / 30s)${NC}"
    fi
    
    sleep 0.5
done

# Still running after 30 seconds
echo -e "${RED}⚠️  Bot did not stop within 30 seconds${NC}"
echo -e "${YELLOW}🔨 Sending force kill (SIGKILL)...${NC}"

if ps -p "$BOT_PID" > /dev/null 2>&1; then
    kill -9 "$BOT_PID" 2>/dev/null
    sleep 1
fi

# Kill tmux session
tmux kill-session -t "$SESSION_NAME" 2>/dev/null

if ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo -e "${RED}❌ Failed to stop bot (PID: $BOT_PID)${NC}"
    exit 2
else
    echo -e "${YELLOW}⚠️  Bot force-killed (cleanup may not have completed)${NC}"
    echo -e "${YELLOW}   Run: python3 cancel_pending_orders.py${NC}"
    exit 1
fi
