#!/bin/bash
# GridBot Web UI - Start Script

echo "=================================="
echo "Starting GridBot Web UI"
echo "=================================="
echo ""

# Check if backend dependencies are installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "❌ Backend dependencies not installed."
    echo "   Run: ./install.sh"
    exit 1
fi

# Check if frontend is built
if [ ! -d "frontend/build" ]; then
    echo "⚠️  Frontend not built. Building now..."
    cd frontend
    npm run build
    cd ..
fi

echo "🚀 Starting GridBot Web UI..."
echo ""

# Set port (default 5555 to avoid conflicts with AirPlay and other bots)
export WEBUI_PORT=${WEBUI_PORT:-5555}

echo "   GridBot Web UI:  http://localhost:$WEBUI_PORT"
echo "   Backend API:     http://localhost:$WEBUI_PORT/api"
echo ""
echo "   (Using port $WEBUI_PORT - set WEBUI_PORT env var to change)"
echo ""
echo "   Press Ctrl+C to stop"
echo ""
echo "=================================="
echo ""

# Load environment variables (BEFORE starting backend)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
    echo "✅ Loaded .env"
fi

if [ -f "$PROJECT_DIR/secrets/api_keys.env" ]; then
    set -a
    source "$PROJECT_DIR/secrets/api_keys.env"
    set +a
    echo "✅ Loaded secrets/api_keys.env"
fi

echo "   Trading Mode: ${TRADING_MODE:-live}"
echo "   API Key: $([ -n "$DELTA_API_KEY" ] && echo '✅ Loaded' || echo '❌ Missing')"
echo ""

# Start the backend server
cd backend
python3 app.py

