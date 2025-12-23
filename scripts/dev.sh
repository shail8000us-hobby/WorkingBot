#!/usr/bin/env bash
# Development mode: run backend with live reload and log streaming
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🚀 Starting GridBot WebUI Backend (Development Mode)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Load environment
if [ -f "$PROJECT_ROOT/grid_config.env" ]; then
    echo "✓ Loading grid_config.env"
    set -a
    source "$PROJECT_ROOT/grid_config.env"
    set +a
fi

if [ -f "$PROJECT_ROOT/secrets/api_keys.env" ]; then
    echo "✓ Loading secrets/api_keys.env"
    set -a
    source "$PROJECT_ROOT/secrets/api_keys.env"
    set +a
fi

if [ -f "$PROJECT_ROOT/.env.local" ]; then
    echo "✓ Loading .env.local"
    set -a
    source "$PROJECT_ROOT/.env.local"
    set +a
fi

# Set development defaults
export FLASK_ENV=development
export FLASK_DEBUG=1

# Verify auth token
if [ -z "$WEBUI_AUTH_TOKEN" ]; then
    echo "⚠️  WARNING: WEBUI_AUTH_TOKEN not set!"
    echo "   Generate one with: openssl rand -base64 32"
    echo "   Set it in .env.local or export it"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📍 Backend: http://localhost:5555"
echo "📍 Logs: /tmp/gridbot_webui.log"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run backend with log streaming
python3 -m webui.backend.app 2>&1 | tee -a /tmp/gridbot_webui.log
