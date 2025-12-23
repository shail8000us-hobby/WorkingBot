#!/bin/bash
#
# Fix Bot Memory Issues - Clear Stale EventStore Data
# 
# This script backs up and resets the bot's event database
# to fix issues with stale pending orders and positions
#
# Run this when bot shows:
# - Wrong pending order price (like $38 OPTIONS instead of $95,000 FUTURES)
# - Stale positions that should have closed
# - "Pending BUY @ $38" in logs when it should be grid level
#

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}================================${NC}"
echo -e "${YELLOW}   BOT MEMORY CLEANUP TOOL${NC}"
echo -e "${YELLOW}================================${NC}"
echo

# Find the database
DB_FILE="bot_events_LONG.db"

if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}❌ Database not found: $DB_FILE${NC}"
    echo -e "   Current directory: $(pwd)"
    echo -e "   Expected location: /Users/ssr/Projects/WorkingBot/$DB_FILE"
    exit 1
fi

echo -e "${GREEN}✅ Found database: $DB_FILE${NC}"
echo

# Check current size
DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
echo -e "   Current size: $DB_SIZE"
echo

# Ask for confirmation
echo -e "${YELLOW}⚠️  WARNING: This will:${NC}"
echo -e "   1. Backup current database to: ${DB_FILE}.backup_$(date +%Y%m%d_%H%M%S)"
echo -e "   2. Delete the database (bot will recreate fresh on next start)"
echo -e "   3. Clear all stale positions and pending orders from memory"
echo
echo -e "${RED}⚠️  You will lose event history but gain clean state${NC}"
echo
read -p "Continue? (yes/no): " response

if [ "$response" != "yes" ]; then
    echo -e "${YELLOW}Cancelled.${NC}"
    exit 0
fi

# Backup
BACKUP_FILE="${DB_FILE}.backup_$(date +%Y%m%d_%H%M%S)"
echo
echo -e "${GREEN}📦 Creating backup...${NC}"
cp "$DB_FILE" "$BACKUP_FILE"
echo -e "   ✅ Backup created: $BACKUP_FILE"

# Delete
echo
echo -e "${GREEN}🗑️  Deleting stale database...${NC}"
rm "$DB_FILE"
echo -e "   ✅ Database deleted"

echo
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}   ✅ CLEANUP COMPLETE!${NC}"
echo -e "${GREEN}================================${NC}"
echo
echo -e "Next steps:"
echo -e "  1. ${YELLOW}Restart the bot${NC} (it will create fresh database)"
echo -e "  2. ${YELLOW}Verify clean state${NC} in logs (no $38 OPTIONS order)"
echo -e "  3. ${YELLOW}Test auto-recreate${NC} by manually cancelling a grid order"
echo
echo -e "If you need to restore:"
echo -e "  mv $BACKUP_FILE $DB_FILE"
echo
