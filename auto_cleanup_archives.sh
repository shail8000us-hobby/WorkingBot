#!/bin/bash
# Automatic Archive Cleanup Script
# Deletes archived files on November 25, 2025 if not accessed

CLEANUP_DATE="2025-11-25"
CURRENT_DATE=$(date +%Y-%m-%d)

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        Automatic Archive Cleanup - November 25, 2025        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if it's time to cleanup
if [[ "$CURRENT_DATE" < "$CLEANUP_DATE" ]]; then
    echo -e "${YELLOW}⏰ Scheduled cleanup date: $CLEANUP_DATE${NC}"
    echo -e "${GREEN}📅 Current date: $CURRENT_DATE${NC}"
    echo ""
    echo "Not yet time to cleanup. Archives are safe."
    echo ""
    echo "Archives to be deleted on $CLEANUP_DATE:"
    echo "  - logs/archive_20251112/"
    echo "  - .doc_archive_nov12_2025/"
    echo "  - archive/setup_scripts/"
    echo "  - config_backups/archive/"
    echo "  - bot/audit/archive/"
    exit 0
fi

# It's time to cleanup
echo -e "${RED}🗑️  Cleanup date reached: $CLEANUP_DATE${NC}"
echo ""
echo "The following archives will be DELETED:"
echo "  - logs/archive_20251112/"
echo "  - .doc_archive_nov12_2025/"
echo "  - archive/setup_scripts/"
echo "  - config_backups/archive/"
echo "  - bot/audit/archive/"
echo ""

# Safety check - require confirmation
read -p "⚠️  Are you sure you want to DELETE these archives? (yes/no): " confirmation

if [[ "$confirmation" != "yes" ]]; then
    echo -e "${YELLOW}❌ Cleanup cancelled by user${NC}"
    exit 1
fi

echo ""
echo -e "${RED}🗑️  Starting cleanup...${NC}"
echo ""

# Delete archives
cd /Users/ssr/Projects/WorkingBot

if [ -d "logs/archive_20251112" ]; then
    echo "Deleting logs/archive_20251112/..."
    rm -rf logs/archive_20251112
    echo "  ✓ Deleted"
fi

if [ -d ".doc_archive_nov12_2025" ]; then
    echo "Deleting .doc_archive_nov12_2025/..."
    rm -rf .doc_archive_nov12_2025
    echo "  ✓ Deleted"
fi

if [ -d "archive/setup_scripts" ]; then
    echo "Deleting archive/setup_scripts/..."
    rm -rf archive/setup_scripts
    echo "  ✓ Deleted"
fi

if [ -d "config_backups/archive" ]; then
    echo "Deleting config_backups/archive/..."
    rm -rf config_backups/archive
    echo "  ✓ Deleted"
fi

if [ -d "bot/audit/archive" ]; then
    echo "Deleting bot/audit/archive/..."
    rm -rf bot/audit/archive
    echo "  ✓ Deleted"
fi

echo ""
echo -e "${GREEN}✅ Cleanup completed!${NC}"
echo ""
echo "Summary saved to: archive_cleanup_log_$(date +%Y%m%d_%H%M%S).txt"

# Create cleanup log
cat > "archive_cleanup_log_$(date +%Y%m%d_%H%M%S).txt" << LOGEOF
Archive Cleanup Log
Date: $(date)
Cleanup scheduled for: $CLEANUP_DATE

Archives deleted:
- logs/archive_20251112/
- .doc_archive_nov12_2025/
- archive/setup_scripts/
- config_backups/archive/
- bot/audit/archive/

Status: Completed successfully
LOGEOF

echo "Done!"
