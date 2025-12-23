#!/bin/bash
# Quick access script to view GridBot logs
# Double-click this file in Finder to open logs in Terminal

cd "$(dirname "$0")"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    GridBot Live Logs                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Starting log viewer... Press Ctrl+C to exit"
echo ""

# Show last 50 lines, then follow live
pm2 logs gridbot-live --lines 50

# Keep terminal open if logs stop
echo ""
echo "Log viewer stopped. Press any key to exit..."
read -n 1
