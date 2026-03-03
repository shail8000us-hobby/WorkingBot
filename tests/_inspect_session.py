#!/usr/bin/env python3
import sqlite3, json

db = sqlite3.connect('webui/backend/data/mmm_sessions.db')
cur = db.cursor()
cur.execute('SELECT data_json FROM mmm_sessions WHERE session_id = ?', ('mmm20feb26-5',))
data = json.loads(cur.fetchone()[0])

# Full auto-close events by strike
analytics = data.get('analytics', {})
auto_close_events = analytics.get('auto_close_events', [])
print(f'All {len(auto_close_events)} auto-close events:')
close_by_strike = {}
for e in auto_close_events:
    key = f"{e.get('side','?').upper()} @ {e.get('strike')}"
    close_by_strike.setdefault(key, []).append(e)
    print(f"  {e.get('timestamp')} | {e.get('side','?').upper()} @ {e.get('strike')} | lots={e.get('lots')} | pnl={e.get('realized_pnl',0):.4f}")

print(f'\nClose summary by strike:')
for k, events in close_by_strike.items():
    total_lots = sum(e.get('lots', 0) for e in events)
    print(f"  {k}: {total_lots} lots in {len(events)} events")

# Last reconciliation
recon = data.get('last_reconciliation', {})
print(f'\nLast reconciliation: {recon.get("timestamp")}')
print(f'  Session symbols: {recon.get("session_symbols", [])}')
print(f'  Exchange positions:')
for sym, pos in recon.get('exchange_positions', {}).items():
    print(f'    {sym}: size={pos.get("size")}, side={pos.get("side")}, pnl={pos.get("unrealized_pnl",0):.4f}')
print(f'  Discrepancies: {recon.get("discrepancies", [])}')

# All session's original and shifted strikes
print(f'\noriginal_strike CE: {data.get("ce", {}).get("original_strike")}')
print(f'original_strike PE: {data.get("pe", {}).get("original_strike")}')
print(f'entry_mode: {data.get("entry_mode")}')
print(f'entry_time: {data.get("entry_time")}')
print(f'expiry: {data.get("expiry")}')

# Wind-down history
wd = data.get('_wind_down_history', [])
print(f'\nWind-down history: {len(wd)} entries')
for w in wd[-5:]:
    print(f'  {w}')

db.close()
