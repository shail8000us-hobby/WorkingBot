#!/bin/bash

# 🚀 STANDALONE BOT LAUNCHER
# Run this script to start your trading bot without any IDE

echo "🚀 Starting Trading Bot Standalone..."

# Navigate to bot directory
cd "$(dirname "$0")"

# Load environment variables
source secrets/api_keys.env
source grid_config.env

# Start WebUI Backend
echo "📊 Starting WebUI Backend..."
python3 webui/backend/app.py &
WEBUI_PID=$!

# Wait for WebUI to start
sleep 5

# Start Trading Bot
echo "🤖 Starting Trading Bot..."
python3 bot/run.py &
BOT_PID=$!

# Wait for bot to initialize
sleep 10

# Start WebUI Frontend
echo "🌐 Starting WebUI Frontend..."
cd webui/frontend
npm start &
FRONTEND_PID=$!

echo "✅ Bot is now running!"
echo "📊 WebUI: http://localhost:5555"
echo "🤖 Bot PID: $BOT_PID"
echo "📊 Backend PID: $WEBUI_PID"
echo "🌐 Frontend PID: $FRONTEND_PID"

# Keep script running
wait
