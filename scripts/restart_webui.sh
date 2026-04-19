#!/usr/bin/env bash
# Restart backend only — use for pure backend (Python) changes.
# No frontend rebuild. Takes ~5-8s.
#
# Usage: ./scripts/restart_webui.sh

launchctl stop com.gridbot.production.webui
# launchctl stop is synchronous — process is dead before this line returns.
# Do NOT kill -9 here: it triggers launchd's 30s ThrottleInterval, adding ~30s to boot.
launchctl start com.gridbot.production.webui

for i in $(seq 1 45); do
  sleep 1
  if curl -sf http://localhost:5555/api/health > /dev/null 2>&1; then
    echo "✅ Backend up in ${i}s — http://localhost:5555"
    exit 0
  fi
done
echo "❌ Backend did not respond after 45s — check logs/webui_production_error.log"
exit 1
