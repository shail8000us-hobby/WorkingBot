#!/usr/bin/env bash
set -euo pipefail

STAMP=$(date +"%Y%m%d-%H%M%S")
OUT="artifacts/${STAMP}"
mkdir -p "$OUT"

# Save bot logs
mkdir -p "$OUT/logs"
if [[ -d bot/logs ]]; then
  cp -R bot/logs "$OUT/" || true
fi

# Save key repo context
git rev-parse --short HEAD >/dev/null 2>&1 && GIT_HEAD=$(git rev-parse --short HEAD) || GIT_HEAD="(no-git)"
{
  echo "Timestamp: $(date -Is)"
  echo "Git HEAD: $GIT_HEAD"
  echo
  echo "=== ENV (redacted) ==="
  env | sed -E 's/(API|SECRET|KEY|TOKEN|PASS)[^=]*=[^$]*/\1=REDACTED/Ig'
  echo
  echo "=== Python ==="
  command -v python && python --version
  echo
  echo "=== pip freeze (first 200 lines) ==="
  pip freeze | head -n 200 || true
  echo
  echo "=== git status ==="
  git status -sb 2>/dev/null || echo "(no git repo)"
} > "$OUT/context.txt"

# Copy config/state if present
[[ -f bot/state.json        ]] && cp bot/state.json        "$OUT/" || true
[[ -f bot/config.yaml       ]] && cp bot/config.yaml       "$OUT/" || true
[[ -f bot/.env              ]] && sed -E 's/(API|SECRET|KEY|TOKEN|PASS)[^=]*=.*/\1=REDACTED/Ig' bot/.env > "$OUT/.env.redacted" || true

# Tail last part of current log for convenience
[[ -f bot/logs/bot.log      ]] && tail -n 500 bot/logs/bot.log > "$OUT/last500.log" || true

echo "Snapshot saved to: ${OUT}"
echo "Zip it (optional): cd artifacts && tar -czf ${STAMP}.tar.gz ${STAMP}"
