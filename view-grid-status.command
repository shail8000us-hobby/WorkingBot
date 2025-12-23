#!/bin/bash
# Quick access script to view Grid Status
# Double-click this file in Finder to see grid loops and history

cd "$(dirname "$0")"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                 Grid Status & Loop History                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Show the most recent grid status display
pm2 logs gridbot-live --lines 200 --nostream | grep -A 100 "GRID STATUS" | tail -80

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "Press any key to exit..."
read -n 1
