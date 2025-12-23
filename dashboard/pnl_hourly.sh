#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
LOCKDIR="$HOME/.gridbot_pnl.lock"
if ! mkdir "$LOCKDIR" 2>/dev/null; then echo "[skip] already running"; exit 0; fi
trap 'rmdir "$LOCKDIR"' EXIT

set -a
[ -f .env.reports ] && source .env.reports
set +a

SINCE="$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || python3 - <<'PY'
import datetime; print((datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'))
PY
)"
UNTIL="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || python3 - <<'PY'
import datetime; print(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))
PY
)"

PYBIN="$PWD/.venv/bin/python3"
[ -x "$PYBIN" ] || PYBIN="$(command -v python3)"

mkdir -p reports

"$PYBIN" -m bot.reports.pnl_html --since "$SINCE" --until "$UNTIL" --tz "Asia/Kolkata" --outdir reports || true
"$PYBIN" "$PWD/delta_pnl_tracker.py" --since "$SINCE" --until "$UNTIL" --outdir reports || true

LATEST_HTML="$(ls -1t reports/pnl_report_*.html 2>/dev/null | head -n1 || true)"
if [ -n "${LATEST_HTML:-}" ] && [ -n "${EMAIL_TO:-${SENDER_EMAIL:-}}" ]; then
  "$PYBIN" tools/send_report.py --file "$LATEST_HTML" --to "${EMAIL_TO:-${SENDER_EMAIL}}"
fi