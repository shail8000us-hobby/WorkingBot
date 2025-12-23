#!/bin/bash
# Emergency Rollback Script - Restore Old REST-based GridBot

echo "🚨 EMERGENCY ROLLBACK - Restoring Old GridBot"
echo "=" * 60

# Stop bot first
echo "Stopping bot..."
./stop_bot.sh

# Find latest backups
GBOT_BACKUP=$(ls -t bot/strategy/gbot_clean.py.BACKUP_* 2>/dev/null | head -1)
RUN_BACKUP=$(ls -t bot/run.py.BACKUP_* 2>/dev/null | head -1)

if [ -z "$GBOT_BACKUP" ] || [ -z "$RUN_BACKUP" ]; then
    echo "❌ No backups found!"
    echo "Cannot rollback - please restore manually"
    exit 1
fi

echo "Found backups:"
echo "  - $GBOT_BACKUP"
echo "  - $RUN_BACKUP"
echo ""

# Restore backups
echo "Restoring gbot_clean.py..."
cp "$GBOT_BACKUP" bot/strategy/gbot_clean.py

echo "Restoring run.py..."
cp "$RUN_BACKUP" bot/run.py

echo ""
echo "✅ Rollback complete!"
echo ""
echo "Old REST-based GridBot restored"
echo "You can now restart with: ./start_bot.sh"
echo ""
echo "=" * 60

