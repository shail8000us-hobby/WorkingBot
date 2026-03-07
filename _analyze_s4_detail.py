#!/usr/bin/env python3
"""Analyze perp hedge details for mmm24feb26-4."""
import json, sqlite3

DB = 'webui/backend/data/mmm_sessions.db'
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT data_json FROM mmm_sessions WHERE session_id='mmm24feb26-4'").fetchone()
conn.close()
data = json.loads(row['data_json'])

# Activity log
with open('webui/backend/data/mmm_activity_log.json') as f:
    alog = json.load(f)
entries = alog.get('entries', alog.get('activities', []))
s4 = [e for e in entries if e.get('session_id') == 'mmm24feb26-4']
print(f'Activity entries: {len(s4)}')
from collections import Counter
types = Counter(e.get('activity_type', 'unknown') for e in s4)
print(f'Types: {dict(types)}')
print()
for e in s4:
    ts = str(e.get('timestamp', ''))[:19]
    msg = e.get('message', '')[:150]
    print(f'  [{ts}] {e.get("activity_type","?")} | {msg}')

# Perp hedge details
perp = data.get('perp_hedge', {})
print(f'\n=== PERP HEDGE STATE ===')
for k, v in sorted(perp.items()):
    print(f'  {k}: {v}')

# Perp history
for key in ['perp_hedge_history', '_perp_history', 'perp_trades']:
    hist = data.get(key, [])
    if hist:
        print(f'\n=== {key} ({len(hist)} entries) ===')
        for h in hist[-15:]:
            print(f'  {h}')

# Any perp-related keys in session
print(f'\n=== ALL PERP-RELATED SESSION KEYS ===')
for k in sorted(data.keys()):
    if 'perp' in k.lower() or 'hedge' in k.lower() or 'delta' in k.lower():
        v = data[k]
        if isinstance(v, (list, dict)) and len(str(v)) > 200:
            v = f'[{type(v).__name__} with {len(v)} items]'
        print(f'  {k}: {v}')

# Compare with session 3 (no perp)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
row3 = conn.execute("SELECT data_json FROM mmm_sessions WHERE session_id='mmm24feb26-3'").fetchone()
conn.close()
d3 = json.loads(row3['data_json'])

print(f'\n{"="*70}')
print(f'=== SIDE-BY-SIDE: Session 3 (no perp) vs Session 4 (perp) ===')
print(f'{"="*70}')
print(f'{"Metric":<35} {"S3 (no perp)":<20} {"S4 (perp)":<20}')
print(f'{"-"*75}')
print(f'{"Duration (hours)":<35} {"17.5":<20} {"3.4":<20}')
print(f'{"Initial lots":<35} {d3["params"]["initial_lots"]:<20} {data["params"]["initial_lots"]:<20}')
print(f'{"min_trigger_move":<35} {d3["params"]["min_trigger_move"]:<20} {data["params"]["min_trigger_move"]:<20}')
print(f'{"shift_threshold":<35} {d3["params"]["shift_threshold"]:<20} {data["params"]["shift_threshold"]:<20}')
print(f'{"max_lots_per_side":<35} {d3["params"]["max_lots_per_side"]:<20} {data["params"]["max_lots_per_side"]:<20}')
print(f'{"max_adjustments":<35} {d3["params"]["max_adjustments"]:<20} {data["params"]["max_adjustments"]:<20}')
print(f'{"perp_hedge_enabled":<35} {d3["params"]["perp_hedge_enabled"]:<20} {data["params"]["perp_hedge_enabled"]:<20}')
print(f'{"regime_enabled":<35} {d3["params"].get("regime_enabled","?"):<20} {data["params"].get("regime_enabled","?"):<20}')
print(f'{"gamma_cap_enabled":<35} {d3["params"].get("gamma_cap_enabled","?"):<20} {data["params"].get("gamma_cap_enabled","?"):<20}')
print(f'{"adj_interval":<35} {d3["params"]["adjustment_interval"]:<20} {data["params"]["adjustment_interval"]:<20}')
print(f'{"max_loss_amount":<35} {d3["params"]["max_loss_amount"]:<20} {data["params"]["max_loss_amount"]:<20}')
print(f'{"trailing_stop_pct":<35} {d3["params"]["trailing_stop_pct"]:<20} {data["params"]["trailing_stop_pct"]:<20}')
print(f'{"-"*75}')
r3 = d3.get('realized_pnl', 0)
u3 = d3.get('unrealized_pnl', 0)
r4 = data.get('realized_pnl', 0)
u4 = data.get('unrealized_pnl', 0)
print(f'{"Realized P&L":<35} {"$"+str(round(r3,4)):<20} {"$"+str(round(r4,4)):<20}')
print(f'{"Unrealized P&L":<35} {"$"+str(round(u3,4)):<20} {"$"+str(round(u4,4)):<20}')
print(f'{"Net P&L (R+U)":<35} {"$"+str(round(r3+u3,4)):<20} {"$"+str(round(r4+u4,4)):<20}')
print(f'{"CE total lots":<35} {d3.get("ce",{}).get("total_lots",0):<20} {data.get("ce",{}).get("total_lots",0):<20}')
print(f'{"PE total lots":<35} {d3.get("pe",{}).get("total_lots",0):<20} {data.get("pe",{}).get("total_lots",0):<20}')
print(f'{"Total adjustments":<35} {len(d3.get("adjustment_history",[])):<20} {len(data.get("adjustment_history",[])):<20}')
print(f'{"Strike shifts":<35} {sum(1 for a in d3.get("adjustment_history",[]) if "shift" in a.get("type","")):<20} {sum(1 for a in data.get("adjustment_history",[]) if "shift" in a.get("type","")):<20}')
print(f'{"Reversals":<35} {sum(1 for a in d3.get("adjustment_history",[]) if "reversal" in a.get("type","")):<20} {sum(1 for a in data.get("adjustment_history",[]) if "reversal" in a.get("type","")):<20}')

# Perp hedge P&L
perp4 = data.get('perp_hedge', {})
print(f'\n{"Perp lots":<35} {"N/A":<20} {perp4.get("lots",0):<20}')
print(f'{"Perp realized P&L":<35} {"N/A":<20} {"$"+str(round(perp4.get("realized_pnl",0),4)):<20}')
print(f'{"Perp unrealized P&L":<35} {"N/A":<20} {"$"+str(round(perp4.get("unrealized_pnl",0),4)):<20}')
print(f'{"Perp total P&L":<35} {"N/A":<20} {"$"+str(round(perp4.get("realized_pnl",0)+perp4.get("unrealized_pnl",0),4)):<20}')
print(f'{"Perp avg entry":<35} {"N/A":<20} {perp4.get("avg_entry",0):<20}')
print(f'{"Total hedges":<35} {"N/A":<20} {perp4.get("total_hedge_count",0):<20}')

# PE strikes analysis
print(f'\n=== S4 PE POSITION DETAIL (the problem) ===')
pe = data.get('pe', {})
for p in pe.get('positions', []):
    print(f'  strike={p.get("strike")} lots={p.get("lots")} prem=${p.get("entry_premium",0):.2f} status={p.get("status")} created={str(p.get("created_at",""))[:19]}')

print(f'\n=== S4 CE POSITION DETAIL ===')
ce = data.get('ce', {})
for p in ce.get('positions', []):
    print(f'  strike={p.get("strike")} lots={p.get("lots")} prem=${p.get("entry_premium",0):.2f} status={p.get("status")} created={str(p.get("created_at",""))[:19]}')
