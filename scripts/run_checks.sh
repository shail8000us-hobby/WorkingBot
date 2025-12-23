#!/usr/bin/env bash
set -euo pipefail

# ANSI colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# safe defaults
export EXECUTE_ORDERS=false DELTA_DRY_ORDERS=true
unset WD_MAX_API_FAIL WD_MAX_STALE_S WD_AUTOSAVE_EVERY DELTA_BASE_URL

# 1) Full smoke (kill-switch, API failover, normal run)
scripts/smoke.sh

# 2) Autosave verification (mtime check for state.json)
export WD_AUTOSAVE_EVERY=2
start_ts=$(date +%s)
scripts/clean_run.sh >/dev/null 2>&1 || true
sleep 3
mtime=$(stat -f %m bot/state.json 2>/dev/null || stat -c %Y bot/state.json 2>/dev/null || echo 0)
echo "state.json mtime=$mtime  start=$start_ts"
[ "$mtime" -ge "$start_ts" ] && echo "Autosave OK ✅" || echo -e "${RED}Autosave check FAILED ❌${NC}"
unset WD_AUTOSAVE_EVERY

# 3) Quick log spot-checks
echo
echo "==== LOG SPOT CHECKS ===="
grep -i "CIRCUIT BREAKER" bot/logs/bot.log | tail -3 || true
grep -i "Ticker failed on all paths" bot/logs/bot.log | tail -3 || true

# 4) Highlight any errors/warnings with color
echo
echo "==== ERRORS / WARNINGS FOUND ===="
grep -iE "ERROR|WARNING|Traceback" bot/logs/bot.log | tail -20 \
  | sed -E "s/(ERROR)/${RED}\1${NC}/Ig; s/(WARNING)/${YELLOW}\1${NC}/Ig; s/(Traceback)/${RED}\1${NC}/Ig" \
  || echo "No errors/warnings in logs 🎉"

echo
echo "All checks done."
