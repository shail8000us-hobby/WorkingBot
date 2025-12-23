#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

KEEP_STATE=${KEEP_STATE_BACKUPS:-20}
KEEP_SNAP=${KEEP_SNAPSHOTS:-7}

# 1) state.backup.*.json — keep newest $KEEP_STATE, delete the rest
ls -1t state.backup.*.json 2>/dev/null | awk "NR>${KEEP_STATE}" | while IFS= read -r f; do
  [ -n "$f" ] && rm -f -- "$f"
done

# 2) snapshots/main_*.tgz — keep newest $KEEP_SNAP, delete the rest
mkdir -p snapshots
ls -1t snapshots/main_*.tgz 2>/dev/null | awk "NR>${KEEP_SNAP}" | while IFS= read -r f; do
  [ -n "$f" ] && rm -f -- "$f"
done

# 3) Optional: delete stray .json backups older than 14 days in repo root (keep state.json)
find . -maxdepth 1 -type f -name "*.json" -mtime +14 -not -name "state.json" -delete 2>/dev/null || true
