#!/usr/bin/env bash
# GridBot Dashboard - Stop Bot
# Usage: ./dashboard/stop.sh

cd "$(dirname "$0")/.."

echo "🛑 Stopping GridBot..."
echo ""

# Use UNIFIED STOPPER (single source of truth)
python3 bot_stopper.py --graceful

exit $?
