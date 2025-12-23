#!/bin/bash

# GridBot Pro - Backtest Web UI Startup Script
# Port: 5556 (Dedicated for backtesting)

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                                                                  ║"
echo "║         GRIDBOT PRO - BACKTEST WEB UI                           ║"
echo "║                                                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "Starting on http://localhost:5556"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if frontend is built
if [ ! -d "frontend/build" ]; then
    echo "⚠️  Frontend not built yet!"
    echo ""
    echo "Building frontend (this may take a few minutes)..."
    echo ""
    
    cd frontend
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "Installing dependencies..."
        npm install
    fi
    
    echo "Building production bundle..."
    npm run build
    
    cd ..
    
    echo ""
    echo "✅ Frontend built successfully!"
    echo ""
fi

# Start backend
echo "Starting backend server..."
echo ""

cd backend
python3 app.py

