#!/bin/bash
# Quick access script to view PM2 Monitor
# Double-click this file in Finder to open PM2 monitor

cd "$(dirname "$0")"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    PM2 Process Monitor                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Opening PM2 monitor... Press 'q' to exit"
echo ""

pm2 monit
