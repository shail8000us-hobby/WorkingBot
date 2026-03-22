#!/usr/bin/env bash
# Restart backend only — use for pure backend (Python) changes.
# No frontend rebuild. Takes ~5-8s.
#
# Usage: ./scripts/restart_webui.sh

launchctl stop com.gridbot.production.webui
# Kill any lingering process on 5555 (stop can be slow on eventlet)
sleep 1 && kill -9 $(lsof -ti:5555) 2>/dev/null || true
launchctl start com.gridbot.production.webui

for i in $(seq 1 15); do
  sleep 1
  if curl -sf http://localhost:5555/api/health > /dev/null 2>&1; then
    echo "✅ Backend up in ${i}s — http://localhost:5555"
    exit 0
  fi
done
echo "❌ Backend did not respond after 15s — check logs/webui_production_error.log"
exit 1
