#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p snapshots

TS="$(date +%Y%m%d_%H%M%S)"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
OUT="snapshots/${BRANCH}_${TS}.tgz"

tar -czf "$OUT" \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude "bot/logs" \
  --exclude "snapshots/*.tgz" \
  --exclude "__pycache__" \
  --exclude ".DS_Store" \
  .

echo "Snapshot written: $OUT"
