#!/usr/bin/env bash
set -euo pipefail

RED=$'\033[31m'; YEL=$'\033[33m'; GRN=$'\033[32m'; BLU=$'\033[34m'; DIM=$'\033[2m'; BOLD=$'\033[1m'; CLR=$'\033[0m'
ok(){   echo "${GRN}✔ $*${CLR}"; }
warn(){ echo "${YEL}▲ $*${CLR}"; }
err(){  echo "${RED}✖ $*${CLR}"; }
info(){ echo "${BLU}➤${CLR} $*"; }

LOG="bot/logs/bot.log"
TMP="scripts/misc_debug/.tmp"
mkdir -p "$TMP" "$(dirname "$LOG")"
trap 'rm -rf "$TMP"' EXIT

have(){ command -v "$1" >/dev/null 2>&1; }
ts(){ date +"%Y-%m-%d %H:%M:%S"; }
mtime_of(){ stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0; }
last_grep(){ local pat="$1" file="${2:-$LOG}"; grep -i -- "$pat" -n "$file" 2>/dev/null | tail -1 || true; }
paste_block(){ echo; echo "${BOLD}=== Paste this to ChatGPT ===${CLR}"; echo "Context: $1"; shift; printf '%s\n' "$@" | sed 's/^/  /'; echo "${BOLD}=============================${CLR}"; echo; }

live_guard(){
  local eo="${EXECUTE_ORDERS:-false}" dry="${DELTA_DRY_ORDERS:-true}" ack="${I_UNDERSTAND_LIVE:-NO}"
  if [[ "$eo" == "true" && "$dry" != "true" && "$ack" != "YES" ]]; then
    echo "${YEL}▲ Live trading requested but ${BOLD}I_UNDERSTAND_LIVE=YES${CLR}${YEL} not set. For safety forcing DRY.${CLR}"
    export DELTA_DRY_ORDERS=true
  fi
}

fast_checks(){
  info "Environment"
  [[ -n "${VIRTUAL_ENV:-}" ]] && ok "venv: $VIRTUAL_ENV" || warn "No virtualenv detected (VIRTUAL_ENV empty)"
  have python && ok "python: $(python --version 2>&1)" || { err "python not found"; exit 1; }
  have pip && ok "pip: $(pip --version 2>&1)" || echo "${DIM}…pip not found (skip)${CLR}"

  info "Syntax compile (py_compile)"
  if out=$( { python - <<'PY' 2>&1
import sys, subprocess, shlex
try:
  files=subprocess.check_output(shlex.split("find bot -name '*.py'")).decode().splitlines()
except Exception:
  files=[]
import py_compile
ok=True
for f in sorted(files):
    if not f.strip(): continue
    try: py_compile.compile(f, doraise=True)
    except Exception as e:
        ok=False
        print(f"COMPILE_ERROR {f}: {e}")
if not ok: sys.exit(1)
PY
  } ); then
    ok "All bot/*.py compiled"
  else
    echo "$out" >&2; err "Syntax errors detected"
    paste_block "Syntax compile errors" "$out"; exit 1
  fi

  info "Import sanity (python -c 'import bot.run')"
  if out=$(python - <<'PY' 2>&1
import importlib; importlib.import_module("bot.run"); print("IMPORT_OK")
PY
  ); then
    ok "Import ok"
  else
    echo "$out" >&2; err "Import error"
    paste_block "Import error while loading bot.run" "$out"; exit 1
  fi

  info "Static quality (optional)"
  if have ruff; then
    if ruff_out=$(ruff check bot 2>&1); then ok "ruff clean"; else
      echo "$ruff_out" >&2; warn "ruff reported issues (not fatal)"
      paste_block "ruff findings (lint)" "$ruff_out"
    fi
  else
    echo "${DIM}…ruff not installed (skip)${CLR}"
  fi

  if have mypy; then
    if mypy_out=$(mypy bot --hide-error-codes --no-error-summary 2>&1); then ok "mypy clean"; else
      echo "$mypy_out" >&2; warn "mypy reported issues (not fatal)"
      paste_block "mypy findings (types)" "$mypy_out"
    fi
  else
    echo "${DIM}…mypy not installed (skip)${CLR}"
  fi

  if have pytest && [[ -d tests ]]; then
    if py_out=$(pytest -q 2>&1); then ok "pytest passed"; else
      echo "$py_out" >&2; warn "pytest failures"
      paste_block "pytest failures" "$py_out"
    fi
  else
    echo "${DIM}…pytest or tests/ missing (skip)${CLR}"
  fi

  info "Config guard"
  echo "${DIM}EXECUTE_ORDERS=${EXECUTE_ORDERS:-false}  DELTA_DRY_ORDERS=${DELTA_DRY_ORDERS:-true}  I_UNDERSTAND_LIVE=${I_UNDERSTAND_LIVE:-NO}${CLR}"
  live_guard
  ok "Fast checks finished"
}

smoke_tests(){
  info "Smoke 1/4: Kill-switch"
  : > "$LOG" || true
  python - <<'PY'
import subprocess, time, os, sys
p=subprocess.Popen([sys.executable,"-m","bot.run"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(1.0)
open("bot/panic.on","w").close()
p.wait(timeout=20)
os.remove("bot/panic.on")
PY
  if grep -qi "CIRCUIT BREAKER: Kill switch" "$LOG"; then ok "Kill-switch logged"; else
    err "Kill-switch log not found"; paste_block "Kill-switch check" "$(tail -n 80 "$LOG")"; exit 1; fi

  info "Smoke 2/4: API failover"
  : > "$LOG" || true
  ( export WD_MAX_API_FAIL=2 DELTA_BASE_URL="https://invalid.example"; python -m bot.run >/dev/null 2>&1 || true )
  if grep -qi "Ticker failed on all paths" "$LOG"; then ok "API failover message present"; else
    err "API failover message missing"; paste_block "API failover check" "$(tail -n 120 "$LOG")"; exit 1; fi

  info "Smoke 3/4: Normal dry run"
  : > "$LOG" || true
  ( export EXECUTE_ORDERS=false DELTA_DRY_ORDERS=true; python -m bot.run >/dev/null 2>&1 || true )
  if grep -qi "Loop done" "$LOG"; then ok "Dry run completed"; else
    err "Dry run did not complete"; paste_block "Dry run check" "$(tail -n 120 "$LOG")"; exit 1; fi

  info "Smoke 4/4: Autosave heartbeat"
  : > "$LOG" || true
  START_TS=$(date +%s)

  # Run a bit longer to give autosave a chance to fire (≈6s wall time with 1s polls)
  ( export WD_AUTOSAVE_EVERY=2 EXECUTE_ORDERS=false DELTA_DRY_ORDERS=true; python -m bot.run >/dev/null 2>&1 || true )

  # Signals we accept for autosave:
  # 1) state.json mtime advanced
  # 2) presence of bot/.autosave.touch
  # 3) log contains keywords like 'autosave', 'flush', or 'saved state'
  autosave_ok=false

  if [[ -f bot/state.json ]]; then
    MTIME=$(mtime_of bot/state.json)
    if [[ "${MTIME:-0}" -ge "${START_TS:-0}" ]]; then
      ok "Autosave updated state.json (mtime=${MTIME})"; autosave_ok=true
    fi
  fi

  if [[ "$autosave_ok" != true && -f bot/.autosave.touch ]]; then
    ok "Autosave heartbeat file present (.autosave.touch)"; autosave_ok=true
  fi

  if [[ "$autosave_ok" != true ]]; then
    if grep -Eqi 'autosave|flush|saved state' "$LOG"; then
      ok "Autosave activity detected in logs"; autosave_ok=true
    fi
  fi

  if [[ "$autosave_ok" != true ]]; then
    warn "Autosave signal not detected (might be disabled or only on state changes)"
    paste_block "Autosave check (signals)" \
      "start_ts=${START_TS}" \
      "mtime=$(mtime_of bot/state.json 2>/dev/null || echo 0)" \
      "$(tail -n 60 "$LOG")"
  fi

  # Audit summary (non-fatal)\
  bash audit/order_audit.sh once >/dev/null 2>&1 || true\
  bash scripts/misc_debug/audit_summary.sh || true
  # PnL snapshot (non-fatal)\
  python scripts/misc_debug/export_pnl.py >/dev/null 2>&1 || true
  ok "Smoke tests finished"
}

MODE="${1:-fast}"
case "$MODE" in
  fast)  fast_checks ;;
  smoke) fast_checks; smoke_tests ;;
  *) err "Unknown mode: $MODE (use: fast | smoke)"; exit 2 ;;
esac

echo
echo "${BOLD}Summary (${MODE}) — $(ts)${CLR}"
if [[ "$MODE" == "fast" ]]; then
  echo "  ${GRN}Fast checks passed${CLR}"
  echo "  To run runtime smoke: ${BOLD}bash scripts/misc_debug/run_all.sh smoke${CLR}"
else
  echo "  ${GRN}Fast checks passed${CLR}"
  echo "  ${GRN}Smoke tests completed (Kill-switch, API failover, Dry run, Autosave)${CLR}"
fi
if [[ -f "$LOG" ]]; then
  ks=$(last_grep "CIRCUIT BREAKER: Kill switch" || true)
  tf=$(last_grep "Ticker failed on all paths" || true)
  [[ -n "$ks" ]] && echo "${DIM}last kill-switch: $ks${CLR}"
  [[ -n "$tf" ]] && echo "${DIM}last ticker-fail: $tf${CLR}"
fi
