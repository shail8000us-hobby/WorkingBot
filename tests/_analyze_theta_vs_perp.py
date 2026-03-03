#!/usr/bin/env python3
"""
Deep theta vs perp analysis for the user's two key observations:
1. Perp should only activate when strike becomes ATM
2. Selling calls in downtrend on 0DTE is fine (theta is friend)
"""
import json, sqlite3
from datetime import datetime

DB = '/Users/ssr/Projects/WorkingBot/webui/backend/data/mmm_sessions.db'

def load_session(sid):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT data_json FROM mmm_sessions WHERE session_id=?", (sid,)).fetchone()
    conn.close()
    return json.loads(row['data_json'])

s3 = load_session('mmm24feb26-3')
s4 = load_session('mmm24feb26-4')

print("=" * 80)
print("ANALYSIS 1: CE CALL SELLING PROFITABILITY IN 9% DOWNTREND (S3)")
print("=" * 80)

# BTC moved from ~69200 to ~62800 = 9.2% crash
# CE = CALL options. In a down market, calls go OTM and decay.
# Let's trace every CE position's P&L contribution

ce3 = s3.get('ce', {})
positions = ce3.get('positions', [])

print(f"\nBTC movement: ~$69,200 → ~$62,800 (9.2% crash over 17.5 hours)")
print(f"Expiry: 24022026 (same day = 0DTE)")
print(f"\n{'Strike':<10} {'Lots':<6} {'Entry$':<10} {'Status':<10} {'Dist from Spot':<18} {'Premium Now':<14} {'P&L per lot':<15} {'Total P&L':<12}")
print("-" * 105)

# Current spot: ~62800
spot = 62800
total_ce_pnl_estimate = 0
total_ce_premium_collected = 0
total_ce_lots = 0

# CE trigger snapshots show current premiums at old strikes
ce_snaps = ce3.get('ce', {}).get('trigger_snapshot', {})

for pos in positions:
    strike = pos.get('strike', 0)
    lots = pos.get('lots', 0)
    entry_prem = pos.get('entry_premium', 0)
    status = pos.get('status', '')
    
    # Distance from current spot (calls are OTM when strike > spot)
    dist = strike - spot
    dist_pct = (dist / spot) * 100
    otm_label = f"+${dist:.0f} ({dist_pct:.1f}% OTM)"
    
    # Estimate current premium based on trigger snapshots or close-at-5
    current_prem = 0
    snap_key = str(int(strike))
    if snap_key in ce_snaps:
        current_prem = ce_snaps[snap_key]
    elif status == 'closed':
        current_prem = 5.0  # closed at threshold
    
    # P&L: we SOLD these, so profit = entry - current
    pnl_per_lot = (entry_prem - current_prem) * 0.001  # per lot in USD
    total_pnl = pnl_per_lot * lots
    collected = entry_prem * lots * 0.001
    
    total_ce_pnl_estimate += total_pnl
    total_ce_premium_collected += collected
    total_ce_lots += lots
    
    print(f"{strike:<10.0f} {lots:<6} ${entry_prem:<9.2f} {status:<10} {otm_label:<18} ${current_prem:<13.2f} ${pnl_per_lot:<14.4f} ${total_pnl:<11.4f}")

print("-" * 105)
print(f"{'TOTALS':<10} {total_ce_lots:<6} {'':10} {'':10} {'':18} {'':14} {'':15} ${total_ce_pnl_estimate:<11.4f}")
print(f"\nTotal CE premium collected: ${total_ce_premium_collected:.4f}")
print(f"Total CE estimated P&L: ${total_ce_pnl_estimate:.4f}")

# Now PE side
print(f"\n{'='*80}")
print(f"ANALYSIS 1B: PE PUT SELLING IN 9% DOWNTREND (S3)")
print(f"{'='*80}")

pe3 = s3.get('pe', {})
pe_positions = pe3.get('positions', [])
pe_snaps = s3.get('pe', {}).get('trigger_snapshot', {})

total_pe_pnl = 0
total_pe_collected = 0

print(f"\n{'Strike':<10} {'Lots':<6} {'Entry$':<10} {'Status':<10} {'Dist from Spot':<18} {'Premium Now':<14} {'P&L per lot':<15} {'Total P&L':<12}")
print("-" * 105)

for pos in pe_positions:
    strike = pos.get('strike', 0)
    lots = pos.get('lots', 0)
    entry_prem = pos.get('entry_premium', 0)
    status = pos.get('status', '')
    
    # Puts are OTM when strike < spot, ITM when strike > spot
    dist = spot - strike
    dist_pct = (dist / spot) * 100
    if dist > 0:
        otm_label = f"-${dist:.0f} ({dist_pct:.1f}% OTM)"
    else:
        otm_label = f"+${abs(dist):.0f} ({abs(dist_pct):.1f}% ITM!)"
    
    # Current premium from snapshot
    current_prem = 0
    snap_key = str(int(strike))
    if snap_key in pe_snaps:
        current_prem = pe_snaps[snap_key]
    elif status == 'closed':
        current_prem = 5.0
    
    pnl_per_lot = (entry_prem - current_prem) * 0.001
    total_pnl = pnl_per_lot * lots
    collected = entry_prem * lots * 0.001
    
    total_pe_pnl += total_pnl
    total_pe_collected += collected
    
    print(f"{strike:<10.0f} {lots:<6} ${entry_prem:<9.2f} {status:<10} {otm_label:<18} ${current_prem:<13.2f} ${pnl_per_lot:<14.4f} ${total_pnl:<11.4f}")

print("-" * 105)
print(f"Total PE premium collected: ${total_pe_collected:.4f}")
print(f"Total PE estimated P&L: ${total_pe_pnl:.4f}")

print(f"\n{'='*80}")
print(f"COMBINED OPTIONS P&L: CE (${total_ce_pnl_estimate:.4f}) + PE (${total_pe_pnl:.4f}) = ${total_ce_pnl_estimate + total_pe_pnl:.4f}")
print(f"Session reported realized: ${s3.get('realized_pnl', 0):.4f}")
print(f"{'='*80}")

# ============================================================
# ANALYSIS 2: S4 PERP DAMAGE vs OPTIONS PROFIT
# ============================================================
print(f"\n\n{'='*80}")
print(f"ANALYSIS 2: S4 — PERP HEDGE DAMAGE vs OPTIONS PROFIT")
print(f"{'='*80}")

ce4 = s4.get('ce', {})
pe4 = s4.get('pe', {})
perp4 = s4.get('perp_hedge', {})

# CE P&L in S4
print(f"\n--- S4 CE CALLS (same downtrend, perp ON) ---")
ce4_pnl = 0
for pos in ce4.get('positions', []):
    strike = pos.get('strike', 0)
    lots = pos.get('lots', 0)
    entry = pos.get('entry_premium', 0)
    status = pos.get('status', '')
    
    snap_key = str(int(strike))
    ce4_snaps = s4.get('ce', {}).get('trigger_snapshot', {})
    current = ce4_snaps.get(snap_key, 5.0 if status == 'closed' else 0)
    
    pnl = (entry - current) * lots * 0.001
    ce4_pnl += pnl
    print(f"  {strike:.0f}: {lots} lots, entry=${entry:.2f}, now=${current:.2f}, P&L=${pnl:.4f} [{status}]")

print(f"  CE total P&L: ${ce4_pnl:.4f}")

# PE P&L in S4
print(f"\n--- S4 PE PUTS ---")
pe4_pnl = 0
for pos in pe4.get('positions', []):
    strike = pos.get('strike', 0)
    lots = pos.get('lots', 0)
    entry = pos.get('entry_premium', 0)
    status = pos.get('status', '')
    
    snap_key = str(int(strike))
    pe4_snaps = s4.get('pe', {}).get('trigger_snapshot', {})
    current = pe4_snaps.get(snap_key, 5.0 if status == 'closed' else entry)
    
    pnl = (entry - current) * lots * 0.001
    pe4_pnl += pnl
    
    # ATM check
    dist_from_spot = abs(strike - spot)
    atm_label = " *** NEAR ATM ***" if dist_from_spot < 500 else ""
    print(f"  {strike:.0f}: {lots} lots, entry=${entry:.2f}, now=${current:.2f}, P&L=${pnl:.4f} [{status}]{atm_label}")

print(f"  PE total P&L: ${pe4_pnl:.4f}")

# Perp P&L
print(f"\n--- S4 PERP FUTURES ---")
print(f"  Lots: {perp4.get('lots', 0)} (LONG)")
print(f"  Avg entry: ${perp4.get('avg_entry', 0):.2f}")
print(f"  Current BTC: ~${spot}")
print(f"  Realized P&L: ${perp4.get('realized_pnl', 0):.4f}")
print(f"  Unrealized P&L: ${perp4.get('unrealized_pnl', 0):.4f}")
print(f"  TOTAL PERP P&L: ${perp4.get('realized_pnl', 0) + perp4.get('unrealized_pnl', 0):.4f}")

print(f"\n--- S4 COMPONENT BREAKDOWN ---")
options_pnl = ce4_pnl + pe4_pnl
perp_pnl = perp4.get('realized_pnl', 0) + perp4.get('unrealized_pnl', 0)
print(f"  Options P&L (CE+PE): ${options_pnl:.4f}")
print(f"  Perp Hedge P&L:      ${perp_pnl:.4f}")
print(f"  NET TOTAL:           ${options_pnl + perp_pnl:.4f}")
print(f"  WITHOUT PERP IT WOULD BE: ${options_pnl:.4f}")

# ============================================================
# ANALYSIS 3: WHEN DID PE STRIKE BECOME ATM?
# ============================================================
print(f"\n\n{'='*80}")
print(f"ANALYSIS 3: STRIKE vs SPOT — WHEN DID THINGS GET CLOSE TO ATM?")
print(f"{'='*80}")

# S3 analysis
print(f"\n--- S3 (no perp) ---")
ce3_active = ce3.get('active_strike', 0)
pe3_active = pe3.get('active_strike', 0)
print(f"  CE active strike: {ce3_active} (${ce3_active - spot:.0f} from spot = {(ce3_active-spot)/spot*100:.1f}% OTM)")
print(f"  PE active strike: {pe3_active} (${spot - pe3_active:.0f} from spot = {(spot-pe3_active)/spot*100:.1f}% OTM)")

# Check all CE strikes for proximity to spot
print(f"\n  All CE strike distances from spot ~${spot}:")
ce3_strikes = set()
for pos in ce3.get('positions', []):
    s = pos.get('strike', 0)
    if s > 0:
        ce3_strikes.add(s)
for s in sorted(ce3_strikes):
    d = s - spot
    print(f"    {s:.0f}: ${d:.0f} away ({d/spot*100:.1f}% OTM) {'*** CLOSE ***' if abs(d) < 2000 else ''}")

# S4 analysis
print(f"\n--- S4 (perp ON) ---")
ce4_active = ce4.get('active_strike', 0)
pe4_active = pe4.get('active_strike', 0)
print(f"  CE active strike: {ce4_active} (${ce4_active - spot:.0f} from spot = {(ce4_active-spot)/spot*100:.1f}% OTM)")
print(f"  PE active strike: {pe4_active} (${spot - pe4_active:.0f} from spot = {(spot-pe4_active)/spot*100:.1f}% ATM!)")

pe4_snap = s4.get('pe', {}).get('trigger_snapshot', {})
print(f"\n  PE trigger snapshot: {pe4_snap}")
print(f"  PE strike 63000 premium: ${pe4_snap.get('63000', 0):.2f}")
print(f"  PE strike 63000 distance: ${spot - 63000:.0f} ({(spot-63000)/spot*100:.1f}% from spot)")
print(f"  PE strike 62000 (shifted): distance ${spot - 62000:.0f} ({(spot-62000)/spot*100:.1f}% OTM)")

# Key question: when in the adjustment history did things get close to ATM?
print(f"\n  S4 Adjustment timeline vs ATM proximity:")
adj4 = s4.get('adjustment_history', [])
for a in adj4:
    ts = str(a.get('timestamp', ''))[:19]
    atype = a.get('type', '?')
    strike = a.get('strike', 0)
    agg = a.get('aggressor', '?')
    lots = a.get('lots_sold', a.get('lots', '?'))
    
    # What side is this strike for?
    if strike > spot:
        dist = strike - spot
        side = 'CE (OTM)'
    else:
        dist = spot - strike
        side = 'PE'
        if dist < 500:
            side = 'PE (ATM!!)'
        elif dist < 1500:
            side = 'PE (NEAR-ATM)'
        else:
            side = f'PE ({dist/spot*100:.1f}% OTM)'
    
    print(f"  [{ts}] {atype:18s} agg={agg} {side:20s} strike={strike:.0f} lots={lots}")

# ============================================================
# ANALYSIS 4: WHAT IF PERP ONLY ON ATM?
# ============================================================
print(f"\n\n{'='*80}")
print(f"ANALYSIS 4: HYPOTHETICAL — PERP ONLY WHEN STRIKE WITHIN 2% OF SPOT")
print(f"{'='*80}")

# In S4, when did strikes come within 2% of spot?
# Spot was around 63000-64000 during S4's run
# PE strike 63000 = always within 1% if spot was 63000-64000
# CE strikes were all > 64200 = >2% above spot

print(f"\n  S4 PE strike 63000 was ALWAYS near ATM (spot was ~$63,000-64,000)")
print(f"  S4 PE strike 62000 (original) was ~1-3% OTM")
print(f"  S4 CE strikes 64200-65400 were 2-4% OTM = safe for theta decay")
print(f"")
print(f"  If perp activated ONLY when PE@63000 crossed into <1% ATM:")
print(f"    - Perp would hedge the PE delta (puts going ITM)")
print(f"    - NOT hedge the CE delta (calls going OTM = profitable theta)")
print(f"    - Net effect: protect against PE blow-up without killing CE profit")
print(f"")
print(f"  Current perp hedges NET portfolio delta (CE + PE combined):")
print(f"    - Portfolio delta = {s4.get('portfolio_delta', 0):.4f}")
print(f"    - This INCLUDES the CE profit (calls decaying = positive delta shift)")
print(f"    - Perp neutralizes BOTH the bad PE delta AND the good CE theta")
print(f"    - Result: perp fights against your profitable CE decay")

# S3 profitability breakdown by time
print(f"\n\n{'='*80}")
print(f"ANALYSIS 5: S3 THETA POWER — HOW CALLS DECAYED OVER 17.5 HOURS")
print(f"{'='*80}")

# The adjustment history shows when positions were opened
adj3 = s3.get('adjustment_history', [])
print(f"\n  Timeline of CE positions opened (all going further OTM as BTC fell):")
ce3_positions = ce3.get('positions', [])
for pos in ce3_positions:
    created = str(pos.get('created_at', ''))[:19]
    strike = pos.get('strike', 0)
    lots = pos.get('lots', 0)
    entry = pos.get('entry_premium', 0)
    status = pos.get('status', '')
    
    otm_dist = strike - spot
    collected_usd = entry * lots * 0.001
    
    # If closed, profit = (entry - 5) * lots * 0.001
    if status == 'closed':
        profit = (entry - 5) * lots * 0.001
        label = f"CLOSED → profit ${profit:.4f}"
    else:
        snap_key = str(int(strike))
        current = ce_snaps.get(snap_key, entry)
        profit = (entry - current) * lots * 0.001
        label = f"{status} → unrealized ${profit:.4f}"
    
    print(f"  [{created}] Strike {strike:.0f} ({otm_dist:.0f} OTM) | {lots} lots @ ${entry:.2f} | collected ${collected_usd:.4f} | {label}")

print(f"\n  KEY INSIGHT: Every CE position opened during the crash was further OTM")
print(f"  Theta worked on ALL of them. The 0DTE time decay is the profit engine.")
print(f"  Even the 152-lot position at 64800 @ $21 = still OTM by $2000+")
