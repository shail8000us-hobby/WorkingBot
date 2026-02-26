#!/usr/bin/env python3
"""Deep analysis of MMM session."""
import json, sqlite3, sys
from datetime import datetime

DB = '/Users/ssr/Projects/WorkingBot/webui/backend/data/mmm_sessions.db'
SID = sys.argv[1] if len(sys.argv) > 1 else 'mmm24feb26-3'

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
row = conn.execute('SELECT data_json FROM mmm_sessions WHERE session_id=?', (SID,)).fetchone()
conn.close()
data = json.loads(row['data_json'])

# Adjustment history details
adj_hist = data.get('adjustment_history', [])
print(f"=== ADJUSTMENT HISTORY ({len(adj_hist)}) ===")
for a in adj_hist:
    ts = str(a.get('timestamp', ''))[:19]
    loss = a.get('loss_to_cover', a.get('total_loss', 'N/A'))
    lots = a.get('lots_sold', a.get('lots', 'N/A'))
    print(f"  [{ts}] type={a.get('type')} agg={a.get('aggressor','?')} loss={loss} lots_sold={lots} strike={a.get('strike','?')} hedge_side={a.get('hedge_side','?')}")

# Full positions analysis
ce = data.get('ce', {})
pe = data.get('pe', {})

print(f"\n=== ALL CE POSITIONS ===")
total_ce_premium_collected = 0
for p in ce.get('positions', []):
    lots = p.get('lots', 0)
    prem = p.get('entry_premium', 0)
    usd_val = prem * lots * 0.001
    total_ce_premium_collected += usd_val
    print(f"  strike={p.get('strike')} lots={lots} prem=${prem:.2f} USD=${usd_val:.4f} status={p.get('status')} created={str(p.get('created_at',''))[:19]}")
print(f"  TOTAL CE PREMIUM COLLECTED: ${total_ce_premium_collected:.4f}")

print(f"\n=== ALL PE POSITIONS ===")
total_pe_premium_collected = 0
for p in pe.get('positions', []):
    lots = p.get('lots', 0)
    prem = p.get('entry_premium', 0)
    usd_val = prem * lots * 0.001
    total_pe_premium_collected += usd_val
    print(f"  strike={p.get('strike')} lots={lots} prem=${prem:.2f} USD=${usd_val:.4f} status={p.get('status')} created={str(p.get('created_at',''))[:19]}")
print(f"  TOTAL PE PREMIUM COLLECTED: ${total_pe_premium_collected:.4f}")

print(f"\n=== PREMIUM COLLECTION SUMMARY ===")
print(f"  CE collected: ${total_ce_premium_collected:.4f}")
print(f"  PE collected: ${total_pe_premium_collected:.4f}")
print(f"  TOTAL collected: ${total_ce_premium_collected + total_pe_premium_collected:.4f}")
print(f"  Realized P&L: ${data.get('realized_pnl', 0):.4f}")
print(f"  Unrealized P&L: ${data.get('unrealized_pnl', 0):.4f}")

# Lots escalation analysis 
print(f"\n=== LOTS ESCALATION ANALYSIS ===")
print(f"  Initial lots: {data.get('params',{}).get('initial_lots')} per side")
print(f"  CE total_lots now: {ce.get('total_lots')} (max_lots_per_side: {data.get('params',{}).get('max_lots_per_side')})")
print(f"  PE total_lots now: {pe.get('total_lots')}")
print(f"  CE active_lots: {ce.get('active_lots')}")
print(f"  PE active_lots: {pe.get('active_lots')}")
print(f"  Combined total: {ce.get('total_lots',0) + pe.get('total_lots',0)} lots")

# Calculate ratio of premium collected per lot
ce_total = ce.get('total_lots', 0)
pe_total = pe.get('total_lots', 0)
if ce_total > 0:
    print(f"\n  CE premium/lot: ${total_ce_premium_collected/ce_total:.6f}")
if pe_total > 0:
    print(f"  PE premium/lot: ${total_pe_premium_collected/pe_total:.6f}")

# Trigger snapshots
print(f"\n=== TRIGGER SNAPSHOTS ===")
print(f"  CE: {json.dumps(ce.get('trigger_snapshot', {}))}")
print(f"  PE: {json.dumps(pe.get('trigger_snapshot', {}))}")

# Regime
print(f"\n=== REGIME STATE ===")
for key in sorted(data.keys()):
    if key.startswith('_vol_') or key.startswith('_gamma_') or key.startswith('_trend_') or key.startswith('_regime'):
        val = data[key]
        if isinstance(val, list) and len(val) > 5:
            val = f"[{len(val)} items, last={val[-1]}]"
        print(f"  {key}: {val}")

# Session runtime / efficiency
params = data.get('params', {})
entry_time = data.get('entry_time', data.get('created_at', ''))
updated = data.get('updated_at', '')
if entry_time and updated:
    try:
        start = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(updated.replace('Z', '+00:00'))
        hours = (end - start).total_seconds() / 3600
        adj = len(adj_hist)
        rpnl = data.get('realized_pnl', 0)
        print(f"\n=== EFFICIENCY METRICS ===")
        print(f"  Duration: {hours:.1f} hours")
        print(f"  Adjustments: {adj} ({adj/hours:.1f}/hr)" if hours > 0 else "  Adjustments: {adj}")
        print(f"  Realized P&L/hour: ${rpnl/hours:.4f}" if hours > 0 else "")
        print(f"  Total P&L/hour: ${data.get('total_pnl',0)/hours:.4f}" if hours > 0 else "")
        print(f"  Premium collected/hour: ${(total_ce_premium_collected+total_pe_premium_collected)/hours:.4f}" if hours > 0 else "")
    except Exception as e:
        print(f"  timing error: {e}")

# Also analyze the other running session
print(f"\n\n{'#'*70}")
print(f"# ALSO: mmm25feb26-1")
print(f"{'#'*70}")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
row2 = conn.execute('SELECT data_json FROM mmm_sessions WHERE session_id=?', ('mmm25feb26-1',)).fetchone()
conn.close()
if row2:
    d2 = json.loads(row2['data_json'])
    p2 = d2.get('params', {})
    ce2 = d2.get('ce', {})
    pe2 = d2.get('pe', {})
    print(f"Status: {d2.get('strategy_status')}")
    print(f"Created: {d2.get('created_at')}")
    print(f"Expiry: {p2.get('expiry')}")
    print(f"Initial lots: {p2.get('initial_lots')}")
    print(f"Realized P&L: ${d2.get('realized_pnl', 0):.4f}")
    print(f"Unrealized: ${d2.get('unrealized_pnl', 0):.4f}")
    print(f"Total P&L: ${d2.get('total_pnl', 0):.4f}")
    print(f"CE lots: {ce2.get('total_lots')} PE lots: {pe2.get('total_lots')}")
    print(f"Adjustments: {len(d2.get('adjustment_history', []))}")
    adj2 = d2.get('adjustment_history', [])
    for a in adj2[-5:]:
        ts = str(a.get('timestamp', ''))[:19]
        print(f"  [{ts}] type={a.get('type')} agg={a.get('aggressor')} loss={a.get('loss_to_cover', a.get('total_loss', 'N/A'))} lots={a.get('lots_sold', 'N/A')}")

# All recent sessions - compare P&L
print(f"\n\n{'#'*70}")
print(f"# ALL SESSIONS COMPARISON")
print(f"{'#'*70}")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT session_id, status, data_json, created_at FROM mmm_sessions ORDER BY created_at DESC LIMIT 10').fetchall()
conn.close()
for r in rows:
    d = json.loads(r['data_json'])
    p = d.get('params', {})
    adjs = len(d.get('adjustment_history', []))
    entry = d.get('entry_time', d.get('created_at', ''))
    updated = d.get('updated_at', '')
    hours = 0
    if entry and updated:
        try:
            s = datetime.fromisoformat(entry.replace('Z','+00:00'))
            e = datetime.fromisoformat(updated.replace('Z','+00:00'))
            hours = (e-s).total_seconds()/3600
        except: pass
    
    rpnl = d.get('realized_pnl', 0)
    upnl = d.get('unrealized_pnl', 0)
    tpnl = d.get('total_pnl', 0)
    pph = f"${rpnl/hours:.4f}/hr" if hours > 0 else "N/A"
    
    ce_t = d.get('ce',{}).get('total_lots',0)
    pe_t = d.get('pe',{}).get('total_lots',0)
    
    print(f"  {r['session_id']:16s} | {r['status']:8s} | {hours:5.1f}h | adjs={adjs:3d} | R=${rpnl:8.4f} U=${upnl:8.4f} T=${tpnl:8.4f} | {pph:12s} | CE:{ce_t:4d} PE:{pe_t:4d} lots | exp={p.get('expiry','?')}")
