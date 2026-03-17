"""
MMM Trade Simulation — Replay & Analysis Tool
Loads all STOPPED sessions from DB and produces a comprehensive performance report.

Run:
    python3 webui/backend/routes/mmm/tests/simulate_mmm_trades.py
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

LOT_SIZE_BTC = 0.001  # 1 lot = 0.001 BTC on Delta Exchange

DB_PATH = "webui/backend/data/mmm_sessions.db"

# ─── Data Loading ─────────────────────────────────────────────────────────────

def load_sessions() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT session_id, data_json FROM mmm_sessions WHERE status='STOPPED' ORDER BY created_at"
    )
    sessions = []
    for r in cur.fetchall():
        data = json.loads(r["data_json"])
        if data.get("adjustment_history"):
            sessions.append(data)
    conn.close()
    return sessions


# ─── Session Metrics ──────────────────────────────────────────────────────────

def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def compute_session_metrics(data: Dict) -> Dict:
    sid = data["session_id"]
    adj_history: List[Dict] = data.get("adjustment_history", [])
    pnl_history: List[Dict] = data.get("pnl_history", [])
    params = data.get("params", {})
    if isinstance(params, list):
        params = {}

    entry_time = data.get("entry_time") or data.get("created_at", "")
    expiry_time = data.get("expiry_time", "")

    # Duration
    try:
        t_start = parse_ts(entry_time)
        t_end = parse_ts(data.get("updated_at", entry_time))
        duration_h = (t_end - t_start).total_seconds() / 3600
    except Exception:
        duration_h = 0

    realized_pnl = data.get("realized_pnl", 0) or 0
    unrealized_pnl = data.get("unrealized_pnl", 0) or 0
    total_pnl = realized_pnl + unrealized_pnl

    # Adjustment breakdown by side/type
    adj_by_side = defaultdict(int)
    adj_by_type = defaultdict(int)
    lots_by_side = defaultdict(int)
    premium_by_side = defaultdict(float)
    reversal_count = 0
    whipsaw_pairs = 0
    prev_aggressor = None

    for adj in adj_history:
        side = adj.get("side", "?")
        atype = adj.get("type", "standard")
        lots = adj.get("lots_sold", 0) or 0
        prem = adj.get("premium", 0) or 0
        aggressor = adj.get("aggressor", "?")

        adj_by_side[side] += 1
        adj_by_type[atype] += 1
        lots_by_side[side] += lots
        premium_by_side[side] += prem

        if "reversal" in atype:
            reversal_count += 1

        if prev_aggressor and prev_aggressor != aggressor:
            whipsaw_pairs += 1
        prev_aggressor = aggressor

    # PnL curve stats
    peak_pnl = data.get("peak_pnl", 0) or 0
    if pnl_history:
        pnl_values = [p["total_pnl"] for p in pnl_history]
        peak_pnl = max(pnl_values)
        max_drawdown = peak_pnl - min(pnl_values[pnl_values.index(peak_pnl):])
    else:
        max_drawdown = 0

    total_premium_collected = data.get("total_premium_collected", 0) or 0
    total_fees = data.get("total_fees", 0) or 0

    # Per-adjustment premium received
    adj_premium_list = [a.get("premium_collected", 0) or 0 for a in adj_history]
    avg_premium_per_adj = sum(adj_premium_list) / len(adj_premium_list) if adj_premium_list else 0

    # Trigger efficiency: premium level at each adjustment vs entry_premium
    trigger_pct_list = []
    for adj in adj_history:
        prem_at_trigger = adj.get("premium", 0) or 0
        # We don't have the snapshot at that moment, but we can approximate:
        # trigger fires when premium rises > min_trigger_move% from snapshot.
        # premium collected = premium × lots × LOT_SIZE_BTC
        pc = adj.get("premium_collected", 0) or 0
        lots = adj.get("lots_sold", 0) or 0
        if lots > 0:
            implied_prem = pc / (lots * LOT_SIZE_BTC)
            trigger_pct_list.append(implied_prem)

    initial_lots = params.get("initial_lots", 1) or 1
    min_trigger_move = params.get("min_trigger_move", 10.0)

    return {
        "session_id": sid,
        "duration_h": duration_h,
        "entry_time": entry_time[:16] if entry_time else "?",
        "expiry_time": expiry_time[:10] if expiry_time else "?",
        "initial_lots": initial_lots,
        "min_trigger_move": min_trigger_move,
        "adj_count": len(adj_history),
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": total_pnl,
        "total_premium_collected": total_premium_collected,
        "total_fees": total_fees,
        "net_pnl": total_pnl - total_fees,
        "adj_by_side": dict(adj_by_side),
        "adj_by_type": dict(adj_by_type),
        "lots_by_side": dict(lots_by_side),
        "premium_by_side": dict(premium_by_side),
        "reversal_count": reversal_count,
        "whipsaw_pairs": whipsaw_pairs,
        "peak_pnl": peak_pnl,
        "max_drawdown": max_drawdown,
        "avg_premium_per_adj": avg_premium_per_adj,
        "pnl_history": pnl_history,
        "adj_history": adj_history,
        "params": params,
    }


# ─── Trigger Efficiency Simulation ────────────────────────────────────────────

def simulate_trigger_efficiency(adj_history: List[Dict], pnl_history: List[Dict]) -> List[Dict]:
    """
    For each adjustment, find what CE/PE premiums were just before it fired.
    Compute how much premium excess existed at trigger time.
    """
    if not pnl_history:
        return []

    pnl_map = {p["timestamp"]: p for p in pnl_history}
    pnl_sorted = sorted(pnl_history, key=lambda x: x["timestamp"])

    results = []
    for adj in adj_history:
        adj_ts = adj.get("timestamp", "")
        side = adj.get("side", "?")
        aggressor = adj.get("aggressor", "?")
        prem_fill = adj.get("premium", 0) or 0
        lots = adj.get("lots_sold", 0) or 0
        adj_type = adj.get("type", "standard")

        # Find nearest pnl_history entry just before or at this adjustment
        snapshot_entry = None
        for ph in pnl_sorted:
            if ph["timestamp"] <= adj_ts:
                snapshot_entry = ph
            else:
                break

        ce_prem_at_trigger = snapshot_entry["ce_premium"] if snapshot_entry else None
        pe_prem_at_trigger = snapshot_entry["pe_premium"] if snapshot_entry else None

        # Dollar excess at trigger = aggressor premium × lots × LOT_SIZE_BTC
        # (aggressor = the side that spiked and triggered the hedge)
        agg_prem = ce_prem_at_trigger if aggressor == "CE" else pe_prem_at_trigger
        dollar_excess_at_trigger = (agg_prem or 0) * lots * LOT_SIZE_BTC

        results.append({
            "adj_num": adj.get("adjustment_number", 0),
            "timestamp": adj_ts[:16],
            "side_sold": side,
            "aggressor": aggressor,
            "adj_type": adj_type,
            "premium_fill": prem_fill,
            "lots": lots,
            "ce_prem_at_trigger": ce_prem_at_trigger,
            "pe_prem_at_trigger": pe_prem_at_trigger,
            "dollar_collected": adj.get("premium_collected", 0) or 0,
            "dollar_excess_at_trigger": dollar_excess_at_trigger,
        })

    return results


def simulate_dollar_floor(
    trigger_events: List[Dict],
    pnl_history: List[Dict],
    min_trigger_dollar: float,
    min_trigger_move_pct: float,
    initial_lots: int,
) -> Dict:
    """
    Retroactively simulate Phase 1 (dollar floor trigger).
    For each beat in pnl_history, determine if dollar floor would have fired
    before the actual % trigger fired.

    Returns: count of beats where dollar floor would have caught it earlier.
    """
    if not pnl_history or not trigger_events:
        return {"early_fires": 0, "missed_by_pct_only": 0, "dollar_only_fires": 0}

    adj_timestamps = {e["timestamp"] for e in trigger_events}

    # Build set of actual adjustment timestamps (normalized to minute)
    actual_adj_minutes = set()
    for adj in trigger_events:
        ts = adj["timestamp"]
        actual_adj_minutes.add(ts[:16])  # YYYY-MM-DDTHH:MM

    # Simulate dollar floor over pnl_history using approximate snapshot
    # Snapshot = last seen premium after adjustment (approximation)
    ce_snapshot = None
    pe_snapshot = None
    dollar_only_fires = 0  # fires dollar but pct didn't — potential earlier trigger
    matched_fires = 0       # both fire at same beat

    for i, ph in enumerate(sorted(pnl_history, key=lambda x: x["timestamp"])):
        ce_now = ph.get("ce_premium", 0) or 0
        pe_now = ph.get("pe_premium", 0) or 0
        ts_min = ph["timestamp"][:16]

        # Init snapshot on first beat
        if ce_snapshot is None:
            ce_snapshot = ce_now
            pe_snapshot = pe_now
            continue

        # Pct excess
        ce_excess_pct = ((ce_now - ce_snapshot) / ce_snapshot * 100) if ce_snapshot > 0 else 0
        pe_excess_pct = ((pe_now - pe_snapshot) / pe_snapshot * 100) if pe_snapshot > 0 else 0

        # Dollar excess (using initial_lots as proxy)
        ce_dollar = max(ce_now - ce_snapshot, 0) * initial_lots * LOT_SIZE_BTC
        pe_dollar = max(pe_now - pe_snapshot, 0) * initial_lots * LOT_SIZE_BTC

        pct_fired = ce_excess_pct > min_trigger_move_pct or pe_excess_pct > min_trigger_move_pct
        dollar_fired = (min_trigger_dollar > 0) and (
            ce_dollar > min_trigger_dollar or pe_dollar > min_trigger_dollar
        )

        if dollar_fired and not pct_fired:
            dollar_only_fires += 1  # dollar catches what % misses (dead zone)

        # After an actual adjustment, reset snapshots (ratchet)
        if ts_min in actual_adj_minutes:
            ce_snapshot = ce_now
            pe_snapshot = pe_now
            matched_fires += 1

    return {
        "dollar_only_fires": dollar_only_fires,
        "matched_fires": matched_fires,
        "pct": min_trigger_move_pct,
        "dollar_floor": min_trigger_dollar,
    }


# ─── ASCII PnL Curve ──────────────────────────────────────────────────────────

def ascii_pnl_curve(pnl_history: List[Dict], width: int = 60, height: int = 8) -> str:
    if not pnl_history:
        return "  (no pnl history)"

    values = [p["total_pnl"] for p in pnl_history]
    min_v, max_v = min(values), max(values)
    span = max_v - min_v if max_v != min_v else 1.0

    # Downsample to width
    step = max(1, len(values) // width)
    sampled = values[::step][:width]

    rows = []
    for row in range(height - 1, -1, -1):
        threshold = min_v + span * row / (height - 1)
        line = ""
        for v in sampled:
            line += "█" if v >= threshold else " "
        # Y-axis label on edges
        if row == height - 1:
            rows.append(f"  ${max_v:+.2f} │{line}│")
        elif row == 0:
            rows.append(f"  ${min_v:+.2f} │{line}│")
        else:
            rows.append(f"         │{line}│")

    rows.append("         └" + "─" * len(sampled) + "┘")
    rows.append(f"          {'start':^{len(sampled)//2}}{'end':^{len(sampled)//2}}")
    return "\n".join(rows)


# ─── Report ───────────────────────────────────────────────────────────────────

def print_report(sessions_data: List[Dict], metrics_list: List[Dict]):
    print()
    print("=" * 80)
    print("  MMM TRADE SIMULATION REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)

    # ── Overview table ─────────────────────────────────────────────────────────
    print()
    print("SESSION OVERVIEW")
    print("-" * 80)
    hdr = f"{'Session':<18} {'Duration':>8} {'Adjs':>5} {'TrigPct':>8} {'PremCollected':>14} {'RealizedPnL':>12} {'TotalPnL':>10} {'Wips':>5}"
    print(hdr)
    print("-" * 80)

    totals = defaultdict(float)
    win_count = 0

    for m in metrics_list:
        won = m["realized_pnl"] > 0
        if won:
            win_count += 1
        flag = "✓" if won else "✗"
        print(
            f"{flag} {m['session_id']:<16} {m['duration_h']:>7.1f}h {m['adj_count']:>5} "
            f"{m['min_trigger_move']:>7.0f}% "
            f"${m['total_premium_collected']:>12.4f} "
            f"${m['realized_pnl']:>10.4f} "
            f"${m['total_pnl']:>8.4f} "
            f"{m['whipsaw_pairs']:>5}"
        )
        totals["premium"] += m["total_premium_collected"]
        totals["realized"] += m["realized_pnl"]
        totals["total_pnl"] += m["total_pnl"]
        totals["adj"] += m["adj_count"]
        totals["duration_h"] += m["duration_h"]
        totals["whipsaw"] += m["whipsaw_pairs"]

    print("-" * 80)
    print(
        f"  {'TOTAL':<16} {totals['duration_h']:>7.1f}h {int(totals['adj']):>5} "
        f"{'':>8} "
        f"${totals['premium']:>12.4f} "
        f"${totals['realized']:>10.4f} "
        f"${totals['total_pnl']:>8.4f} "
        f"{int(totals['whipsaw']):>5}"
    )

    n = len(metrics_list)
    print()
    print(f"  Win Rate: {win_count}/{n} sessions = {100*win_count/n:.0f}%")
    print(f"  Avg PnL/session: ${totals['realized']/n:.4f} realized, ${totals['total_pnl']/n:.4f} total")
    print(f"  Avg adjustments/session: {totals['adj']/n:.1f}")
    print(f"  Total premium collected: ${totals['premium']:.4f}")
    print(f"  Avg premium/session: ${totals['premium']/n:.4f}")

    # ── Adjustment breakdown ───────────────────────────────────────────────────
    print()
    print("ADJUSTMENT BREAKDOWN BY SESSION")
    print("-" * 80)
    print(f"  {'Session':<18} {'Total':>6} {'CE→sold':>8} {'PE→sold':>8} {'Reversals':>10} {'StdAdj':>7} {'Harvest':>8}")
    print("-" * 80)

    all_ce_adjs = 0
    all_pe_adjs = 0
    all_reversals = 0

    for m in metrics_list:
        abs_ = m["adj_by_side"]
        abt = m["adj_by_type"]
        ce_adjs = abs_.get("CE", 0)
        pe_adjs = abs_.get("PE", 0)
        all_ce_adjs += ce_adjs
        all_pe_adjs += pe_adjs
        all_reversals += m["reversal_count"]
        harvest = abt.get("harvest", 0)
        std = abt.get("standard", 0)
        rev = m["reversal_count"]
        print(
            f"  {m['session_id']:<18} {m['adj_count']:>6} {ce_adjs:>8} {pe_adjs:>8} {rev:>10} {std:>7} {harvest:>8}"
        )

    print("-" * 80)
    total_adjs = int(totals["adj"])
    print(f"  {'TOTAL':<18} {total_adjs:>6} {all_ce_adjs:>8} {all_pe_adjs:>8} {all_reversals:>10}")
    print()
    print(f"  CE sold (hedge) : {all_ce_adjs} adjustments = {100*all_ce_adjs/max(total_adjs,1):.0f}%  (means PE was the aggressor)")
    print(f"  PE sold (hedge) : {all_pe_adjs} adjustments = {100*all_pe_adjs/max(total_adjs,1):.0f}%  (means CE was the aggressor)")
    print(f"  Reversals       : {all_reversals} = {100*all_reversals/max(total_adjs,1):.0f}% of adjustments")

    # ── Per-adjustment details for richest session ─────────────────────────────
    best = max(metrics_list, key=lambda m: len(m["pnl_history"]))
    print()
    print(f"DETAILED ADJUSTMENT REPLAY — {best['session_id']}")
    print("-" * 80)

    trigger_events = simulate_trigger_efficiency(
        best["adj_history"], best["pnl_history"]
    )

    print(
        f"  {'#':>3} {'Time':>16} {'Aggressor':>10} {'Sold':>5} {'Lots':>5} "
        f"{'FillPrem':>10} {'CE@Trigger':>11} {'PE@Trigger':>11} "
        f"{'$Collected':>11} {'$Excess':>9}"
    )
    print(f"  {'-'*3} {'-'*16} {'-'*10} {'-'*5} {'-'*5} {'-'*10} {'-'*11} {'-'*11} {'-'*11} {'-'*9}")

    for te in trigger_events:
        ce_s = f"{te['ce_prem_at_trigger']:.1f}" if te["ce_prem_at_trigger"] is not None else "N/A"
        pe_s = f"{te['pe_prem_at_trigger']:.1f}" if te["pe_prem_at_trigger"] is not None else "N/A"
        print(
            f"  {te['adj_num']:>3} {te['timestamp']:>16} {te['aggressor']:>10} {te['side_sold']:>5} "
            f"{te['lots']:>5} {te['premium_fill']:>10.1f} {ce_s:>11} {pe_s:>11} "
            f"${te['dollar_collected']:>9.4f} ${te['dollar_excess_at_trigger']:>7.4f}"
        )

    # ── Dollar floor simulation ────────────────────────────────────────────────
    print()
    print("PHASE 1 SIMULATION: Dollar Floor Trigger (min_trigger_dollar)")
    print("-" * 80)
    print("  Shows how many beats had dollar excess > threshold but % trigger didn't fire yet.")
    print("  These are 'dead zone' beats where losses accumulated without triggering.")
    print()

    floor_thresholds = [0.05, 0.10, 0.25, 0.50, 1.00]
    print(f"  {'Session':<18} {'TrigPct':>8}", end="")
    for fl in floor_thresholds:
        print(f"  ${fl:.2f}/beat", end="")
    print()
    print(f"  {'-'*18} {'-'*8}", end="")
    for fl in floor_thresholds:
        print(f"  {'-'*9}", end="")
    print()

    for m in metrics_list:
        if not m["pnl_history"]:
            continue
        params = m["params"] if isinstance(m["params"], dict) else {}
        min_trig_pct = m["min_trigger_move"]
        initial_lots = m["initial_lots"]
        te = simulate_trigger_efficiency(m["adj_history"], m["pnl_history"])
        print(f"  {m['session_id']:<18} {min_trig_pct:>7.0f}%", end="")
        for fl in floor_thresholds:
            result = simulate_dollar_floor(te, m["pnl_history"], fl, min_trig_pct, initial_lots)
            fires = result["dollar_only_fires"]
            print(f"  {fires:>9}", end="")
        print()

    print()
    print("  Interpretation: Non-zero counts = beats where dollar floor would have fired")
    print("  BEFORE the % trigger. This reveals dead-zone accumulation risk.")
    print("  Higher counts at lower thresholds = more sensitivity (may over-trigger).")
    print("  Sweet spot: threshold where count > 0 but < ~5% of total beats.")

    # ── PnL curves for top 3 sessions ─────────────────────────────────────────
    top3 = sorted(metrics_list, key=lambda m: len(m["pnl_history"]), reverse=True)[:3]
    print()
    print("PnL CURVES (top 3 sessions by history depth)")
    print("-" * 80)
    for m in top3:
        ph = m["pnl_history"]
        print()
        print(f"  {m['session_id']} | {len(ph)} beats | {m['adj_count']} adj | realized ${m['realized_pnl']:.4f}")
        print(ascii_pnl_curve(ph, width=60, height=8))

    # ── Aggressor pattern analysis ─────────────────────────────────────────────
    print()
    print("AGGRESSOR PATTERN ANALYSIS (all sessions combined)")
    print("-" * 80)
    consecutive_same = 0
    consecutive_switch = 0
    all_aggressors = []
    for m in metrics_list:
        for adj in m["adj_history"]:
            all_aggressors.append(adj.get("aggressor", "?"))

    for i in range(1, len(all_aggressors)):
        if all_aggressors[i] == all_aggressors[i - 1]:
            consecutive_same += 1
        else:
            consecutive_switch += 1

    ce_agg_count = all_aggressors.count("CE")
    pe_agg_count = all_aggressors.count("PE")
    print(f"  CE as aggressor: {ce_agg_count} ({100*ce_agg_count/max(len(all_aggressors),1):.0f}%)")
    print(f"  PE as aggressor: {pe_agg_count} ({100*pe_agg_count/max(len(all_aggressors),1):.0f}%)")
    print(f"  Same-dir runs:   {consecutive_same} (price kept moving same direction)")
    print(f"  Direction switch:{consecutive_switch} (price reversed — whipsaw candidate)")
    if (consecutive_same + consecutive_switch) > 0:
        chop_pct = 100 * consecutive_switch / (consecutive_same + consecutive_switch)
        print(f"  Choppiness:      {chop_pct:.0f}% ({chop_pct:.0f}% of transitions reversed direction)")
        if chop_pct > 50:
            print("  ⚠  HIGH choppiness — market was whipsawing more than trending.")
            print("     Consider raising min_trigger_move or adding whipsaw cooldown.")
        elif chop_pct < 25:
            print("  ✓  LOW choppiness — market was trending. Adjustments were directional.")

    # ── Premium efficiency ─────────────────────────────────────────────────────
    print()
    print("PREMIUM EFFICIENCY (premium_collected per adjustment)")
    print("-" * 80)
    print(f"  {'Session':<18} {'Adjs':>5} {'TotalPrem($)':>13} {'Avg$/Adj':>10} {'$/Hour':>8} {'PnL/Prem%':>10}")
    print(f"  {'-'*18} {'-'*5} {'-'*13} {'-'*10} {'-'*8} {'-'*10}")

    for m in metrics_list:
        total_prem = m["total_premium_collected"]
        avg = total_prem / max(m["adj_count"], 1)
        per_hour = total_prem / max(m["duration_h"], 0.1)
        pnl_prem_pct = 100 * m["realized_pnl"] / max(total_prem, 0.001)
        print(
            f"  {m['session_id']:<18} {m['adj_count']:>5} ${total_prem:>11.4f} "
            f"${avg:>8.4f} ${per_hour:>6.4f} {pnl_prem_pct:>9.1f}%"
        )

    # ── Key insights ───────────────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("KEY INSIGHTS & FINDINGS")
    print("=" * 80)

    realized_wins = [m for m in metrics_list if m["realized_pnl"] > 0]
    realized_losses = [m for m in metrics_list if m["realized_pnl"] <= 0]

    avg_winning_pnl = sum(m["realized_pnl"] for m in realized_wins) / max(len(realized_wins), 1)
    avg_losing_pnl = sum(m["realized_pnl"] for m in realized_losses) / max(len(realized_losses), 1)
    expectancy = (win_count / n) * avg_winning_pnl + ((n - win_count) / n) * avg_losing_pnl

    print(f"""
  1. WIN RATE: {win_count}/{n} = {100*win_count/n:.0f}%
     Avg winning session:   ${avg_winning_pnl:.4f}
     Avg losing session:    ${avg_losing_pnl:.4f}
     Expectancy per session:${expectancy:.4f}

  2. TOTAL PREMIUM vs REALIZED
     Total premium sold: ${totals['premium']:.4f}
     Total realized PnL: ${totals['realized']:.4f}
     Capture rate:       {100*totals['realized']/max(totals['premium'],0.001):.1f}% of premium was kept as profit
     (Remainder offset by buybacks/unrealized losses)

  3. AGGRESSOR SKEW
     PE was aggressor {100*pe_agg_count/max(len(all_aggressors),1):.0f}% of the time.
     {('→ Market has been downward-biased (PE premiums spike more). CE sells dominate.' if pe_agg_count > ce_agg_count else '→ Market has been upward-biased (CE premiums spike more). PE sells dominate.')}

  4. TRIGGER MOVE % EFFECTIVENESS
     10% sessions: {len([m for m in metrics_list if m['min_trigger_move'] == 10.0])} sessions — avg PnL ${sum(m['realized_pnl'] for m in metrics_list if m['min_trigger_move'] == 10.0)/max(1,len([m for m in metrics_list if m['min_trigger_move'] == 10.0])):.4f}
     20% sessions: {len([m for m in metrics_list if m['min_trigger_move'] == 20.0])} sessions — avg PnL ${sum(m['realized_pnl'] for m in metrics_list if m['min_trigger_move'] == 20.0)/max(1,len([m for m in metrics_list if m['min_trigger_move'] == 20.0])):.4f}
     15% sessions: {len([m for m in metrics_list if m['min_trigger_move'] == 15.0])} sessions — avg PnL ${sum(m['realized_pnl'] for m in metrics_list if m['min_trigger_move'] == 15.0)/max(1,len([m for m in metrics_list if m['min_trigger_move'] == 15.0])):.4f}

  5. WHIPSAW SUMMARY
     Total direction reversals (adj-to-adj): {all_reversals}
     = {100*all_reversals/max(total_adjs,1):.0f}% of adjustments were reversals.
     {('⚠  >20% reversal rate — significant choppiness. Dollar floor helps by NOT adding filter; phase 2 frozen check may help cover stranded positions from reversals.' if all_reversals/max(total_adjs,1) > 0.20 else '✓  Reversal rate acceptable.')}
""")

    print("=" * 80)
    print("END OF REPORT")
    print("=" * 80)
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sessions = load_sessions()
    print(f"Loaded {len(sessions)} completed sessions with adjustment history.")

    metrics_list = []
    for s in sessions:
        m = compute_session_metrics(s)
        metrics_list.append(m)

    print_report(sessions, metrics_list)
