#!/bin/bash
# WebUI startup script with automatic permission fix

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_BUILD="$PROJECT_DIR/webui/frontend/build"

# Fix permissions on frontend build directory
if [ -d "$FRONTEND_BUILD" ]; then
    chmod -R 755 "$FRONTEND_BUILD" 2>/dev/null || true
fi

# Start the WebUI
cd "$PROJECT_DIR"
exec /usr/bin/python3 webui/backend/app.py
