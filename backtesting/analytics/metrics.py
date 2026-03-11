"""
Backtesting Analytics — Metrics
=================================
Computes all key performance metrics from a session result dict.

Metrics:
  - Basic P&L (total, realized, unrealized, fees, net)
  - Sharpe, Sortino, Calmar ratios
  - Max Drawdown
  - Win rate (across multi-session sweeps)
  - Adjustment / harvest / recycle analytics
  - Weakness probes (slippage cost, liquidity events, etc.)
"""

import math
import logging
from typing import List, Dict, Any, Optional

log = logging.getLogger("backtesting.metrics")

LOT_SIZE_BTC = 0.001


# ══════════════════════════════════════════════════════════════════════════════
# Single-session metrics
# ══════════════════════════════════════════════════════════════════════════════

def compute_session_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute all analytics for a single session result.

    Args:
        result: Session result dict from MMMAdapter.get_session_result()

    Returns:
        Metrics dict with all computed values.
    """
    fills = result.get("fills", [])

    realized    = result.get("realized_pnl",   0.0)
    unrealized  = result.get("unrealized_pnl", 0.0)
    total_pnl   = result.get("total_pnl",      realized + unrealized)
    total_fees  = result.get("total_fees_usd",  result.get("total_fees", 0.0))
    net_pnl     = total_pnl - total_fees
    peak_pnl    = result.get("peak_pnl",       total_pnl)
    max_dd      = result.get("max_drawdown",    0.0)

    # Session duration
    start_ms    = result.get("start_ts_ms", result.get("entry_ts_ms", 0))
    end_ms      = result.get("end_ts_ms",   start_ms)
    duration_h  = (end_ms - start_ms) / 3_600_000 if end_ms > start_ms else 0.0

    # Slippage analysis
    total_slip = result.get("total_slippage_usd", _sum_fills(fills, "slippage"))

    # Adjustment analytics
    adj_count     = result.get("adjustment_count", 0)
    adj_history   = result.get("adjustment_history", [])
    both_sides_up = sum(1 for a in adj_history if a.get("type") == "both_sides_up")
    shift_count   = result.get("shift_count", 0)
    close_at_5    = result.get("close_at_5_count", 0)
    harvest_count = result.get("harvest_count", 0)
    recycle_count = result.get("recycle_count", 0)

    # Calmar ratio: annualized return / max drawdown
    calmar = _safe_div(net_pnl, max_dd) if max_dd > 0 else float("inf")

    # P&L per adjustment
    pnl_per_adj = _safe_div(net_pnl, adj_count) if adj_count else 0.0

    # Margin utilization peak
    final_margin = result.get("final_margin", {})
    peak_margin_util = final_margin.get("utilization_pct", 0.0)

    return {
        # ── P&L ──────────────────────────────────────────────────────────────
        "realized_pnl":       round(realized, 4),
        "unrealized_pnl":     round(unrealized, 4),
        "total_pnl":          round(total_pnl, 4),
        "total_fees":         round(total_fees, 4),
        "net_pnl":            round(net_pnl, 4),
        "total_slippage_usd": round(abs(total_slip), 4),
        # ── Risk ─────────────────────────────────────────────────────────────
        "peak_pnl":           round(peak_pnl, 4),
        "max_drawdown":       round(max_dd, 4),
        "max_drawdown_pct":   round(_safe_div(max_dd, peak_pnl) * 100 if peak_pnl > 0 else 0, 2),
        "calmar_ratio":       round(calmar, 4) if calmar != float("inf") else "∞",
        # ── Session ──────────────────────────────────────────────────────────
        "duration_hours":     round(duration_h, 2),
        "total_beats":        result.get("total_beats", 0),
        "strategy_status":    result.get("strategy_status", "UNKNOWN"),
        # ── Algo events ───────────────────────────────────────────────────────
        "adjustment_count":   adj_count,
        "both_sides_up":      both_sides_up,
        "shift_count":        shift_count,
        "close_at_5_count":   close_at_5,
        "harvest_count":      harvest_count,
        "recycle_count":      recycle_count,
        "pnl_per_adjustment": round(pnl_per_adj, 4),
        # ── Margin ────────────────────────────────────────────────────────────
        "peak_margin_util_pct": peak_margin_util,
        # ── Fill summary ─────────────────────────────────────────────────────
        "total_fills":        len(fills),
        "sell_fills":         sum(1 for f in fills if f.get("side") == "sell"),
        "buy_fills":          sum(1 for f in fills if f.get("side") == "buy"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Multi-session metrics (across date sweeps)
# ══════════════════════════════════════════════════════════════════════════════

def compute_portfolio_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute aggregate metrics across multiple backtest sessions.

    Args:
        results: List of session result dicts (one per expiry date)

    Returns:
        Portfolio-level metrics dict.
    """
    if not results:
        return {"error": "No results provided"}

    metrics_list = [compute_session_metrics(r) for r in results]
    net_pnls     = [m["net_pnl"] for m in metrics_list]
    drawdowns    = [m["max_drawdown"] for m in metrics_list]

    n_sessions   = len(results)
    n_profitable = sum(1 for p in net_pnls if p > 0)
    win_rate     = n_profitable / n_sessions if n_sessions > 0 else 0.0

    total_net_pnl = sum(net_pnls)
    avg_net_pnl   = total_net_pnl / n_sessions
    std_pnl       = _stdev(net_pnls)
    worst_pnl     = min(net_pnls)
    best_pnl      = max(net_pnls)

    sharpe  = _safe_div(avg_net_pnl, std_pnl) if std_pnl > 0 else 0.0
    sortino = _sortino(net_pnls)
    max_dd  = max(drawdowns) if drawdowns else 0.0
    calmar  = _safe_div(avg_net_pnl, max_dd) if max_dd > 0 else float("inf")

    return {
        # Summary
        "n_sessions":          n_sessions,
        "n_profitable":        n_profitable,
        "win_rate":            round(win_rate * 100, 2),      # %
        # Returns
        "total_net_pnl":       round(total_net_pnl, 4),
        "avg_net_pnl":         round(avg_net_pnl, 4),
        "std_net_pnl":         round(std_pnl, 4),
        "best_session_pnl":    round(best_pnl, 4),
        "worst_session_pnl":   round(worst_pnl, 4),
        # Risk ratios
        "sharpe_ratio":        round(sharpe, 4),
        "sortino_ratio":       round(sortino, 4),
        "max_drawdown":        round(max_dd, 4),
        "calmar_ratio":        round(calmar, 4) if calmar != float("inf") else "∞",
        # Algo stats averages
        "avg_adjustments":     round(_avg([m["adjustment_count"] for m in metrics_list]), 2),
        "avg_shifts":          round(_avg([m["shift_count"] for m in metrics_list]), 2),
        "avg_harvest":         round(_avg([m["harvest_count"] for m in metrics_list]), 2),
        "total_both_sides_up": sum(m["both_sides_up"] for m in metrics_list),
        # Cost analysis
        "total_fees":          round(sum(m["total_fees"] for m in metrics_list), 4),
        "total_slippage":      round(sum(m["total_slippage_usd"] for m in metrics_list), 4),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Weakness probe metrics
# ══════════════════════════════════════════════════════════════════════════════

def compute_weakness_probes(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute the 7 built-in MMM weakness probe metrics.

    Returns a dict with a named section per probe.
    """
    probes = {}

    # ── Probe 1: Liquidity Crunch ─────────────────────────────────────────────
    liquidity_events = sum(
        1 for r in results
        for e in r.get("adjustment_history", [])
        if e.get("type") == "liquidity_rejected"
    )
    probes["liquidity_crunch"] = {
        "total_rejected_orders": liquidity_events,
        "sessions_affected": sum(
            1 for r in results
            if any(e.get("type") == "liquidity_rejected" for e in r.get("adjustment_history", []))
        ),
    }

    # ── Probe 2: Slippage Impact ──────────────────────────────────────────────
    total_slip = sum(r.get("total_slippage_usd", 0) for r in results)
    avg_slip   = total_slip / len(results) if results else 0
    probes["slippage_impact"] = {
        "total_slippage_usd":   round(total_slip, 4),
        "avg_per_session_usd":  round(avg_slip, 4),
        "slippage_as_pct_pnl":  round(
            _safe_div(total_slip, abs(sum(r.get("net_pnl", 0) for r in results))) * 100, 2
        ),
    }

    # ── Probe 3: Both-Sides-Up ────────────────────────────────────────────────
    bsu_sessions = [r for r in results if any(
        e.get("type") == "both_sides_up" for e in r.get("adjustment_history", [])
    )]
    bsu_pnls = [r.get("net_pnl", 0) for r in bsu_sessions]
    probes["both_sides_up"] = {
        "frequency_pct":     round(len(bsu_sessions) / len(results) * 100 if results else 0, 2),
        "avg_pnl_when_bsu":  round(_avg(bsu_pnls), 4) if bsu_pnls else 0,
        "worst_pnl_when_bsu": round(min(bsu_pnls), 4) if bsu_pnls else 0,
    }

    # ── Probe 4: Max Drawdown Sessions ───────────────────────────────────────
    max_dd_vals = [r.get("max_drawdown", 0) for r in results]
    probes["drawdown"] = {
        "worst_drawdown":    round(max(max_dd_vals), 4) if max_dd_vals else 0,
        "avg_drawdown":      round(_avg(max_dd_vals), 4),
        "sessions_over_1000": sum(1 for d in max_dd_vals if d > 1000),
    }

    # ── Probe 5: Adjustment Count Distribution ───────────────────────────────
    adj_counts = [r.get("adjustment_count", 0) for r in results]
    probes["adjustments"] = {
        "avg_per_session":  round(_avg(adj_counts), 2),
        "max_in_session":   max(adj_counts) if adj_counts else 0,
        "pnl_per_adj":      round(
            _safe_div(sum(r.get("net_pnl", 0) for r in results), sum(adj_counts)), 4
        ) if sum(adj_counts) > 0 else 0,
    }

    # ── Probe 6: M1 Harvest Effectiveness ────────────────────────────────────
    probes["harvest_effectiveness"] = {
        "avg_harvests_per_session": round(_avg([r.get("harvest_count", 0) for r in results]), 2),
        "total_harvests":           sum(r.get("harvest_count", 0) for r in results),
    }

    # ── Probe 7: Strategy Survival Rate ──────────────────────────────────────
    statuses = [r.get("strategy_status", "") for r in results]
    probes["survival"] = {
        "complete":   statuses.count("COMPLETE"),
        "stopped":    statuses.count("STOPPED"),
        "error":      statuses.count("ERROR"),
        "survival_pct": round(
            statuses.count("COMPLETE") / len(results) * 100 if results else 0, 1
        ),
    }

    return probes


# ══════════════════════════════════════════════════════════════════════════════
# Statistical helpers
# ══════════════════════════════════════════════════════════════════════════════

def _stdev(values: list) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(variance)


def _sortino(returns: list) -> float:
    """Sortino ratio: mean / downside deviation."""
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    downside = [min(r, 0) ** 2 for r in returns]
    downside_std = math.sqrt(sum(downside) / len(downside)) if downside else 0.0
    return _safe_div(mean, downside_std)


def _avg(values: list) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _safe_div(a, b) -> float:
    if b == 0:
        return 0.0
    return a / b


def _sum_fills(fills: list, field: str) -> float:
    return sum(abs(f.get(field, 0) or 0) for f in fills)
