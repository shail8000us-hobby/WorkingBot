#!/usr/bin/env bash
set -euo pipefail

export EXECUTE_ORDERS=false DELTA_DRY_ORDERS=true
unset WD_MAX_API_FAIL WD_MAX_STALE_S WD_AUTOSAVE_EVERY DELTA_BASE_URL

echo "1) Kill-switch…"
python3 -m bot.run & pid=$!
sleep 1
touch bot/panic.on
wait $pid || true
rm -f bot/panic.on
grep -i "CIRCUIT BREAKER: Kill switch" -n bot/logs/bot.log >/dev/null && echo "   OK"

echo "2) Autosave heartbeat…"
export WD_AUTOSAVE_EVERY=2
scripts/clean_run.sh >/dev/null 2>&1 || true
sleep 3
ls -l bot/state.json bot/.autosave.touch || true
unset WD_AUTOSAVE_EVERY

echo "3) API fail path…"
export WD_MAX_API_FAIL=2 DELTA_BASE_URL="https://invalid.example"
python3 -m bot.run || true
grep -i "Ticker failed on all paths" -n bot/logs/bot.log >/dev/null && echo "   OK"
unset WD_MAX_API_FAIL DELTA_BASE_URL

echo "4) Normal dry run…"
python3 -m bot.run
echo "Smoke test done."
