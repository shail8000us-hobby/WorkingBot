#!/usr/bin/env bash
# Production start: clean backend start with environment loading
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🚀 Starting GridBot WebUI Backend (Production Mode)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Load environment (order matters: config -> secrets -> local overrides)
if [ -f "$PROJECT_ROOT/grid_config.env" ]; then
    echo "✓ Loading grid_config.env"
    set -a
    source "$PROJECT_ROOT/grid_config.env"
    set +a
else
    echo "❌ grid_config.env not found!"
    exit 1
fi

if [ -f "$PROJECT_ROOT/secrets/api_keys.env" ]; then
    echo "✓ Loading secrets/api_keys.env"
    set -a
    source "$PROJECT_ROOT/secrets/api_keys.env"
    set +a
else
    echo "⚠️  WARNING: secrets/api_keys.env not found!"
fi

if [ -f "$PROJECT_ROOT/.env.local" ]; then
    echo "✓ Loading .env.local (local overrides)"
    set -a
    source "$PROJECT_ROOT/.env.local"
    set +a
fi

# Set production mode
export FLASK_ENV=production
unset FLASK_DEBUG

# Validate required variables
REQUIRED_VARS=(
    "WEBUI_AUTH_TOKEN"
    "GRIDBOT_SYMBOL"
    "GRIDBOT_LOWER"
    "GRIDBOT_UPPER"
)

MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "❌ Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    exit 1
fi

# Verify frontend build exists
if [ ! -d "$PROJECT_ROOT/webui/frontend/build" ]; then
    echo "❌ Frontend build not found!"
    echo "   Run: ./scripts/build_frontend.sh"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Environment loaded"
echo "✓ Frontend build verified"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📍 Backend: http://localhost:5555"
echo "📍 Logs: /tmp/gridbot_webui.log"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Start backend
exec python3 -m webui.backend.app
