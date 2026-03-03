#!/usr/bin/env python3
"""Analyze MMM session data for profitability insights."""
import json, sqlite3, sys
from datetime import datetime

DB = '/Users/ssr/Projects/WorkingBot/webui/backend/data/mmm_sessions.db'
SID = sys.argv[1] if len(sys.argv) > 1 else 'mmm24feb26-3'

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
row = conn.execute('SELECT data_json FROM mmm_sessions WHERE session_id=?', (SID,)).fetchone()
conn.close()

if not row:
    print(f"Session {SID} not found")
    sys.exit(1)

data = json.loads(row['data_json'])
params = data.get('params', {})

print(f"{'='*70}")
print(f"SESSION: {data.get('session_id')} | Status: {data.get('strategy_status')}")
print(f"Created: {data.get('created_at')}")
print(f"Updated: {data.get('updated_at')}")
print(f"Heartbeats: {data.get('heartbeat_count', 0)}")
print(f"{'='*70}")

print(f"\n--- PARAMETERS ---")
for k, v in sorted(params.items()):
    print(f"  {k}: {v}")

print(f"\n--- P&L ---")
print(f"  Realized P&L:   ${data.get('realized_pnl', 0):.4f}")
print(f"  Unrealized P&L: ${data.get('unrealized_pnl', 0):.4f}")
print(f"  Total P&L:      ${data.get('total_pnl', 0):.4f}")
print(f"  Peak P&L:       ${data.get('peak_pnl', 'N/A')}")
print(f"  Max Drawdown:   ${data.get('max_drawdown', 'N/A')}")

print(f"\n--- ACTIVITY COUNTS ---")
print(f"  Total Adjustments: {data.get('total_adjustments', 0)}")
print(f"  Total Reversals:   {data.get('total_reversals', 0)}")
print(f"  Total Shifts:      {data.get('total_shifts', 0)}")
print(f"  Total Close@5:     {data.get('total_close_at_5', 0)}")

ce = data.get('ce', {})
pe = data.get('pe', {})

print(f"\n--- CE SIDE ---")
print(f"  Active Strike:  {ce.get('active_strike')}")
print(f"  Active Lots:    {ce.get('active_lots')}")
print(f"  Original Lots:  {ce.get('original_lots')}")
print(f"  Original Prem:  ${ce.get('original_premium', 0):.2f}")
print(f"  Total Lots:     {ce.get('total_lots')}")
print(f"  Frozen Positions: {len(ce.get('frozen_positions', []))}")
print(f"  Positions:      {len(ce.get('positions', []))}")
print(f"  Adj Fills:      {len(ce.get('adjustment_fills', []))}")

# Show positions detail
for i, pos in enumerate(ce.get('positions', [])[:10]):
    print(f"    pos[{i}]: strike={pos.get('strike')} lots={pos.get('lots')} status={pos.get('status')} entry_prem={pos.get('entry_premium', 0):.2f}")

print(f"\n--- PE SIDE ---")
print(f"  Active Strike:  {pe.get('active_strike')}")
print(f"  Active Lots:    {pe.get('active_lots')}")
print(f"  Original Lots:  {pe.get('original_lots')}")
print(f"  Original Prem:  ${pe.get('original_premium', 0):.2f}")
print(f"  Total Lots:     {pe.get('total_lots')}")
print(f"  Frozen Positions: {len(pe.get('frozen_positions', []))}")
print(f"  Positions:      {len(pe.get('positions', []))}")
print(f"  Adj Fills:      {len(pe.get('adjustment_fills', []))}")

for i, pos in enumerate(pe.get('positions', [])[:10]):
    print(f"    pos[{i}]: strike={pos.get('strike')} lots={pos.get('lots')} status={pos.get('status')} entry_prem={pos.get('entry_premium', 0):.2f}")

# Perp hedge
perp = data.get('perp_hedge', {})
if perp:
    print(f"\n--- PERP HEDGE ---")
    print(f"  Current Lots: {perp.get('lots', 0)}")
    print(f"  Avg Entry:    {perp.get('avg_entry', 0)}")
    print(f"  Realized P&L: ${perp.get('realized_pnl', 0):.4f}")
    print(f"  Unrealized:   ${perp.get('unrealized_pnl', 0):.4f}")
    print(f"  Total Hedges: {perp.get('total_hedge_count', 0)}")
    print(f"  Last Delta:   {perp.get('last_delta', 0):.4f}")

# Trade history analysis
trade_hist = data.get('trade_history', [])
print(f"\n--- TRADE HISTORY ({len(trade_hist)} trades) ---")
if trade_hist:
    total_premium_collected = 0
    total_lots_sold = 0
    ce_trades = 0
    pe_trades = 0
    for t in trade_hist:
        side = t.get('side', '')
        lots = t.get('lots', 0)
        prem = t.get('premium', 0) or t.get('fill_premium', 0) or 0
        total_premium_collected += prem * lots * 0.001  # USD value
        total_lots_sold += lots
        if 'ce' in side.lower() or 'call' in side.lower():
            ce_trades += 1
        else:
            pe_trades += 1
    
    print(f"  CE trades: {ce_trades}")
    print(f"  PE trades: {pe_trades}")
    print(f"  Total lots sold: {total_lots_sold}")
    print(f"  Total premium collected (est): ${total_premium_collected:.4f}")
    
    # Last 5 trades
    print(f"\n  Last 10 trades:")
    for t in trade_hist[-10:]:
        ts = t.get('timestamp', t.get('time', ''))[:19]
        print(f"    [{ts}] {t.get('side','?')} lots={t.get('lots','?')} strike={t.get('strike','?')} prem={t.get('premium', t.get('fill_premium', '?'))}")

# Adjustment history
adj_hist = data.get('adjustment_history', [])
print(f"\n--- ADJUSTMENT HISTORY ({len(adj_hist)} adjustments) ---")
if adj_hist:
    std_adj = [a for a in adj_hist if a.get('type') == 'standard']
    rev_adj = [a for a in adj_hist if a.get('type') == 'reversal']
    shift_adj = [a for a in adj_hist if a.get('type') in ('shift', 'strike_shift')]
    print(f"  Standard: {len(std_adj)}")
    print(f"  Reversals: {len(rev_adj)}")
    print(f"  Shifts: {len(shift_adj)}")
    
    # Last 10 adjustments
    print(f"\n  Last 10 adjustments:")
    for a in adj_hist[-10:]:
        ts = a.get('timestamp', '')[:19]
        print(f"    [{ts}] type={a.get('type')} aggressor={a.get('aggressor')} loss={a.get('loss_to_cover', a.get('total_loss', '?')):.2f} lots_sold={a.get('lots_sold', '?')}")

# Trigger snapshot analysis
print(f"\n--- TRIGGER SNAPSHOTS ---")
ce_snap = ce.get('trigger_snapshot', {})
pe_snap = pe.get('trigger_snapshot', {})
print(f"  CE snapshots: {json.dumps(ce_snap, indent=4)}")
print(f"  PE snapshots: {json.dumps(pe_snap, indent=4)}")

# Regime state
print(f"\n--- REGIME STATE ---")
print(f"  Vol regime: {data.get('_vol_regime', 'N/A')}")
print(f"  Gamma regime: {data.get('_gamma_regime', 'N/A')}")
print(f"  Trend regime: {data.get('_trend_regime', 'N/A')}")
print(f"  Aggregate action: {data.get('_regime_action', 'N/A')}")

# Session timing
print(f"\n--- TIMING ANALYSIS ---")
entry_time = data.get('entry_time', data.get('created_at', ''))
if entry_time:
    try:
        start = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
        now = datetime.fromisoformat(data.get('updated_at', '').replace('Z', '+00:00'))
        duration = now - start
        hours = duration.total_seconds() / 3600
        print(f"  Running: {hours:.1f} hours")
        hb = data.get('heartbeat_count', 0) 
        interval = params.get('adjustment_interval', 60)
        print(f"  Heartbeats: {hb} (expected ~{int(hours*3600/interval)} at {interval}s interval)")
        adj = data.get('total_adjustments', 0)
        if hours > 0:
            print(f"  Adjustments/hour: {adj/hours:.1f}")
            pnl = data.get('total_pnl', 0)
            print(f"  P&L/hour: ${pnl/hours:.4f}")
    except:
        pass

print(f"\n{'='*70}")
