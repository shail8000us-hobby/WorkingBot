#!/bin/bash
# Test script for Grid Hot Reload (Infinite Uptime)
# This script simulates grid parameter changes and verifies detection

set -e

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                          ║"
echo "║          🧪 TESTING GRID HOT RELOAD (INFINITE UPTIME)                   ║"
echo "║                                                                          ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Config file
CONFIG_FILE="grid_config.env"
BACKUP_FILE="grid_config.env.test_backup"

# Backup current config
echo -e "${YELLOW}📋 Backing up current grid_config.env...${NC}"
cp "$CONFIG_FILE" "$BACKUP_FILE"
echo -e "${GREEN}✅ Backup created: $BACKUP_FILE${NC}"
echo ""

# Function to restore config on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🔄 Restoring original config...${NC}"
    cp "$BACKUP_FILE" "$CONFIG_FILE"
    rm "$BACKUP_FILE"
    echo -e "${GREEN}✅ Config restored${NC}"
}
trap cleanup EXIT

# Get current values
echo -e "${YELLOW}📊 Reading current grid parameters...${NC}"
CURRENT_STEP=$(grep "^GRID_STEP=" "$CONFIG_FILE" | cut -d'=' -f2)
CURRENT_LOWER=$(grep "^GRID_LOWER=" "$CONFIG_FILE" | cut -d'=' -f2)
CURRENT_UPPER=$(grep "^GRID_UPPER=" "$CONFIG_FILE" | cut -d'=' -f2)
CURRENT_REF=$(grep "^REFERENCE_LEVEL=" "$CONFIG_FILE" | cut -d'=' -f2)

echo "  Current GRID_STEP: $CURRENT_STEP"
echo "  Current GRID_LOWER: $CURRENT_LOWER"
echo "  Current GRID_UPPER: $CURRENT_UPPER"
echo "  Current REFERENCE_LEVEL: $CURRENT_REF"
echo ""

# Test 1: Change GRID_STEP
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}🧪 TEST 1: Changing GRID_STEP${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
NEW_STEP=$((CURRENT_STEP + 100))
echo "  Changing GRID_STEP from $CURRENT_STEP to $NEW_STEP"

# Modify config
sed -i.bak "s/^GRID_STEP=.*/GRID_STEP=$NEW_STEP/" "$CONFIG_FILE"
rm "${CONFIG_FILE}.bak"

echo -e "${GREEN}✅ Config file updated${NC}"
echo ""
echo "📋 Expected behavior:"
echo "  1. Bot detects change within 5 seconds"
echo "  2. Logs: 🔄 GRID CHANGE DETECTED (Hot Reload)"
echo "  3. Cancels pending BUY order"
echo "  4. Rebuilds grid with new step"
echo "  5. Places new BUY at correct level"
echo ""
echo -e "${YELLOW}👀 Watch your bot logs to see:${NC}"
echo "  pm2 logs gridbot-demo  (if using PM2)"
echo "  OR check bot/logs/bot.log"
echo ""
read -p "Press Enter when you've verified the change was detected..."
echo ""

# Test 2: Change multiple parameters
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}🧪 TEST 2: Changing GRID_LOWER and GRID_UPPER${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
NEW_LOWER=$((CURRENT_LOWER + 1000))
NEW_UPPER=$((CURRENT_UPPER + 1000))
echo "  Changing GRID_LOWER from $CURRENT_LOWER to $NEW_LOWER"
echo "  Changing GRID_UPPER from $CURRENT_UPPER to $NEW_UPPER"

# Modify config
sed -i.bak "s/^GRID_LOWER=.*/GRID_LOWER=$NEW_LOWER/" "$CONFIG_FILE"
sed -i.bak "s/^GRID_UPPER=.*/GRID_UPPER=$NEW_UPPER/" "$CONFIG_FILE"
rm "${CONFIG_FILE}.bak"

echo -e "${GREEN}✅ Config file updated${NC}"
echo ""
echo "📋 Expected behavior:"
echo "  1. Bot detects change within 5 seconds"
echo "  2. Logs show old and new grid parameters"
echo "  3. Cancels pending BUY (if exists)"
echo "  4. Rebuilds grid with new bounds"
echo "  5. Continues trading seamlessly"
echo ""
echo -e "${YELLOW}👀 Watch your bot logs again...${NC}"
read -p "Press Enter when you've verified the second change..."
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ TEST COMPLETE${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎯 If you saw the following in logs, the test PASSED:"
echo "  ✅ 🔄 GRID CHANGE DETECTED (Hot Reload)"
echo "  ✅ 🗑️  Cancelling old pending BUY"
echo "  ✅ ✅ Successfully cancelled old BUY order"
echo "  ✅ ✅ Grid rebuilt: X rungs from Y to Z"
echo "  ✅ 🎯 Grid updated! Bot will place new BUY at correct level"
echo "  ✅ 💡 NO RESTART NEEDED - Infinite uptime maintained!"
echo ""
echo "🚀 Your bot now supports INFINITE UPTIME!"
echo "   Change grid parameters anytime - no restart needed!"
echo ""

