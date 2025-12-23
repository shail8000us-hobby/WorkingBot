#!/bin/bash
# Fix Bot Instance Lock Issues - Permanent Solution
# 
# This script fixes the 27-restart issue caused by conflicting bot instances

set -e

PROJECT_ROOT="/Users/ssr/Projects/WorkingBot"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🔧 Bot Instance Lock Fixer${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Step 1: Find all running bot instances
echo -e "${YELLOW}1️⃣  Finding all running bot instances...${NC}"
echo ""

# Find Python processes running bot.run
BOT_PIDS=$(ps aux | grep -E "python.*bot\.run|python.*bot_launcher" | grep -v grep | awk '{print $2}' || true)

if [ -z "$BOT_PIDS" ]; then
    echo -e "${GREEN}  ✅ No standalone bot processes found${NC}"
else
    echo -e "${YELLOW}  ⚠️  Found standalone bot processes:${NC}"
    ps aux | grep -E "python.*bot\.run|python.*bot_launcher" | grep -v grep | awk '{print "     PID: "$2" | Started: "$9" "$10}'
    echo ""
    
    echo -e "${YELLOW}  These are NOT managed by PM2 and are causing conflicts!${NC}"
    echo ""
    
    read -p "  Kill these processes? [y/N]: " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for pid in $BOT_PIDS; do
            echo -e "${YELLOW}    Killing PID $pid...${NC}"
            kill -15 $pid 2>/dev/null || kill -9 $pid 2>/dev/null || true
            sleep 1
        done
        echo -e "${GREEN}  ✅ Standalone processes killed${NC}"
    fi
fi

echo ""

# Step 2: Check PM2 status
echo -e "${YELLOW}2️⃣  Checking PM2 status...${NC}"
PM2_STATUS=$(pm2 list 2>&1 || echo "")

if echo "$PM2_STATUS" | grep -q "gridbot-live"; then
    echo -e "${GREEN}  ✅ PM2 gridbot-live configured${NC}"
    
    # Check restart count
    RESTART_COUNT=$(pm2 describe 0 2>/dev/null | grep "restart time" | awk '{print $NF}' || echo "0")
    if [ "$RESTART_COUNT" -gt 10 ]; then
        echo -e "${RED}  ⚠️  High restart count detected: $RESTART_COUNT restarts!${NC}"
        echo -e "${YELLOW}     This indicates recurring crash issues${NC}"
    fi
else
    echo -e "${RED}  ❌ PM2 gridbot-live not found${NC}"
fi

echo ""

# Step 3: Clean up lock files
echo -e "${YELLOW}3️⃣  Cleaning up lock files...${NC}"

LOCK_FILES=$(find . -maxdepth 2 -name ".bot_instance*.lock" 2>/dev/null || true)

if [ -z "$LOCK_FILES" ]; then
    echo -e "${GREEN}  ✅ No lock files found${NC}"
else
    echo -e "${YELLOW}  Found lock files:${NC}"
    for lock in $LOCK_FILES; do
        echo "     $lock"
        # Read PID from lock file
        if [ -f "$lock" ]; then
            LOCK_PID=$(head -1 "$lock" 2>/dev/null || echo "unknown")
            LOCK_TIME=$(sed -n '3p' "$lock" 2>/dev/null || echo "unknown")
            echo "       PID: $LOCK_PID | Time: $LOCK_TIME"
            
            # Check if PID is still running
            if ps -p "$LOCK_PID" > /dev/null 2>&1; then
                echo -e "${RED}       ⚠️  Process still running!${NC}"
            else
                echo -e "${GREEN}       ✅ Process not running (stale lock)${NC}"
                rm -f "$lock"
                echo -e "${GREEN}       ✅ Removed stale lock${NC}"
            fi
        fi
    done
fi

echo ""

# Step 4: Reset PM2 restart count
echo -e "${YELLOW}4️⃣  Resetting PM2 restart counter...${NC}"

if pm2 describe 0 > /dev/null 2>&1; then
    pm2 reset 0 > /dev/null 2>&1
    echo -e "${GREEN}  ✅ PM2 restart counter reset${NC}"
else
    echo -e "${YELLOW}  ⚠️  Could not reset (bot may not be in PM2)${NC}"
fi

echo ""

# Step 5: Start bot properly
echo -e "${YELLOW}5️⃣  Starting bot via PM2...${NC}"

# Stop any running instance first
pm2 stop gridbot-live > /dev/null 2>&1 || true
sleep 2

# Delete and readd to clear all state
# pm2 delete gridbot-live > /dev/null 2>&1 || true
# sleep 1

# Start fresh
pm2 start gridbot-live > /dev/null 2>&1 || echo "Start failed"
sleep 3

# Check status
if pm2 list | grep "gridbot-live" | grep -q "online"; then
    echo -e "${GREEN}  ✅ Bot started successfully via PM2${NC}"
    
    # Get PID
    BOT_PID=$(pm2 list | grep "gridbot-live" | awk '{print $12}')
    echo -e "${GREEN}     PID: $BOT_PID${NC}"
else
    echo -e "${RED}  ❌ Bot failed to start${NC}"
    echo ""
    echo -e "${YELLOW}  Check logs: pm2 logs gridbot-live --lines 50${NC}"
    exit 1
fi

echo ""

# Step 6: Verify no conflicts
echo -e "${YELLOW}6️⃣  Final verification...${NC}"

STANDALONE_COUNT=$(ps aux | grep -E "python.*bot\.run" | grep -v grep | wc -l || echo "0")
PM2_ONLINE=$(pm2 list | grep "gridbot-live" | grep -c "online" || echo "0")

if [ "$STANDALONE_COUNT" -eq 0 ] && [ "$PM2_ONLINE" -eq 1 ]; then
    echo -e "${GREEN}  ✅ Perfect! Only ONE bot running (via PM2)${NC}"
elif [ "$STANDALONE_COUNT" -gt 0 ]; then
    echo -e "${RED}  ⚠️  Warning: $STANDALONE_COUNT standalone process(es) still running!${NC}"
elif [ "$PM2_ONLINE" -eq 0 ]; then
    echo -e "${RED}  ⚠️  Warning: PM2 bot not online!${NC}"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ Fix Complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}📊 Current Status:${NC}"
pm2 list | grep gridbot-live
echo ""
echo -e "${YELLOW}💡 Next Steps:${NC}"
echo "  • Monitor: pm2 logs gridbot-live"
echo "  • Status:  pm2 status"
echo "  • Save state: pm2 save (to persist across reboots)"
echo ""
echo -e "${YELLOW}🚨 IMPORTANT - To Prevent Future Issues:${NC}"
echo "  • ALWAYS use PM2 to start bot: ./pm2_gridbot.sh start live"
echo "  • NEVER run: python -m bot.run directly"
echo "  • PM2 handles restarts, logging, and monitoring automatically"
echo ""
