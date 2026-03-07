#!/bin/bash
# QUICK FIX - Stop old backend and start with real data

echo "🔧 QUICK FIX - Stopping old backend and starting with real Delta data"
echo "======================================================================"
echo ""

# Kill any process on port 5000
echo "🛑 Killing existing backend..."
lsof -ti:5000 | xargs kill -9 2>/dev/null || true
sleep 2

echo "✅ Old backend stopped"
echo ""

# Start new backend with auto-reload
echo "🚀 Starting backend with auto-reload and real data fix..."
cd webui
./start_dev_full.sh
