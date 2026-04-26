#!/bin/bash
# Guardian Status Check — runs every 5 min via cron, logs to logs/guardian_monitor.log

cd /Users/ssr/Projects/WorkingBot || exit 1

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DB="data/bot_events_BTCUSD_SHORT.db"

echo "=== Guardian Status Check: $TIMESTAMP ==="

# 1. PM2 process status
PM2_STATUS=$(pm2 jlist 2>/dev/null | python3 -c "
import sys, json
try:
    procs = json.load(sys.stdin)
    for p in procs:
        if p.get('name') in ('guardian-btc-SHORT', 'gridbot-btc-SHORT'):
            print(f\"  {p['name']}: {p['pm2_env']['status']} (restarts: {p['pm2_env']['restart_time']})\")
except Exception as e:
    print(f'  [pm2 parse error: {e}]')
" 2>/dev/null)

echo "PM2:"
echo "${PM2_STATUS:-  [pm2 unavailable]}"

# 2. Latest Guardian signal from EventStore
if [ -f "$DB" ]; then
    SIGNAL_ROW=$(sqlite3 "$DB" "
        SELECT event_type, json_extract(data,'$.reason'), json_extract(data,'$.details.pnl_inr'),
               datetime(timestamp,'unixepoch','localtime')
        FROM events
        WHERE event_type IN ('guardian_signal_go','guardian_signal_stop')
        ORDER BY timestamp DESC LIMIT 1;
    " 2>/dev/null)

    if [ -n "$SIGNAL_ROW" ]; then
        SIG_TYPE=$(echo "$SIGNAL_ROW" | cut -d'|' -f1)
        SIG_REASON=$(echo "$SIGNAL_ROW" | cut -d'|' -f2)
        SIG_PNL=$(echo "$SIGNAL_ROW" | cut -d'|' -f3)
        SIG_TS=$(echo "$SIGNAL_ROW" | cut -d'|' -f4)

        if [ "$SIG_TYPE" = "guardian_signal_go" ]; then
            echo "Signal: GO ✅ (at $SIG_TS)"
        else
            echo "Signal: STOP 🔴 — $SIG_REASON (at $SIG_TS)"
        fi

        if [ -n "$SIG_PNL" ]; then
            printf "  Account P&L: ₹%.0f\n" "$SIG_PNL"
        fi
    else
        echo "Signal: [no signal in EventStore]"
    fi
else
    echo "Signal: [EventStore DB not found: $DB]"
fi

echo ""
