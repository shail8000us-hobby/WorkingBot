#!/usr/bin/env bash
# Build frontend + restart backend — use after any src/ change.
# Uses incremental build cache (fast path ~20s, cold ~60s).
#
# Usage: ./scripts/deploy_webui.sh

set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "📦 Building frontend..."
cd "$PROJECT_ROOT/webui/frontend"
npm run build 2>&1 | grep -E "compiled|Compiled|error|Error|✅|❌|budget|Budget" || true

echo "🔄 Restarting backend..."
launchctl stop com.gridbot.production.webui
launchctl start com.gridbot.production.webui

echo "⏳ Waiting for backend..."
for i in $(seq 1 20); do
  sleep 1
  if curl -sf http://localhost:5555/api/health > /dev/null 2>&1; then
    echo "✅ Live at http://localhost:5555  (ready in ${i}s)"
    exit 0
  fi
done
echo "❌ Backend did not respond after 20s"
tail -20 "$PROJECT_ROOT/logs/webui_production_error.log"
exit 1
