"""
Session Report
===============
Generates a formatted text / dict report for a backtest session.
Includes all metrics, weakness probe results, and trade summary.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .metrics import compute_session_metrics, compute_weakness_probes

log = logging.getLogger("backtesting.session_report")


def generate_session_report(
    result: Dict[str, Any],
    verbose: bool = False,
) -> str:
    """
    Generate a human-readable text report for a single session.

    Args:
        result:  Session result dict from MMMAdapter.get_session_result()
        verbose: If True, include full adjustment history

    Returns:
        Formatted string report.
    """
    metrics = compute_session_metrics(result)
    lines = []

    def ln(x=""): lines.append(x)
    def header(x): lines.append(f"\n{'═'*50}\n  {x}\n{'═'*50}")

    header(f"MMM Backtest Report — {result.get('expiry_date', '?')}")

    # ── Session info ─────────────────────────────────────────────────────────
    ln(f"  Algo:           {result.get('algo', 'MMM')} ({result.get('mode', 'fresh')})")
    ln(f"  Status:         {result.get('strategy_status', '?')}")
    ln(f"  Duration:       {metrics['duration_hours']:.2f}h")
    ln(f"  Total beats:    {metrics['total_beats']}")
    ln()

    # ── P&L summary ──────────────────────────────────────────────────────────
    ln("═" * 50)
    ln(f"  NET P&L:        ${metrics['net_pnl']:>+10,.2f}")
    ln(f"  Total P&L:      ${metrics['total_pnl']:>+10,.2f}")
    ln(f"  Realized:       ${metrics['realized_pnl']:>+10,.2f}")
    ln(f"  Unrealized:     ${metrics['unrealized_pnl']:>+10,.2f}")
    ln(f"  Fees:           ${metrics['total_fees']:>+10,.2f}")
    ln(f"  Slippage:       ${metrics['total_slippage_usd']:>+10,.2f}")
    ln("═" * 50)

    # ── Risk ─────────────────────────────────────────────────────────────────
    ln(f"  Peak P&L:       ${metrics['peak_pnl']:>+10,.2f}")
    ln(f"  Max Drawdown:   ${metrics['max_drawdown']:>10,.2f}  ({metrics['max_drawdown_pct']:.1f}% of peak)")
    ln(f"  Calmar Ratio:   {metrics['calmar_ratio']}")
    ln()

    # ── Events ──────────────────────────────────────────────────────────────
    ln(f"  Adjustments:    {metrics['adjustment_count']}")
    ln(f"  Both-sides-up:  {metrics['both_sides_up']}")
    ln(f"  Strike shifts:  {metrics['shift_count']}")
    ln(f"  Close-at-5:     {metrics['close_at_5_count']}")
    ln(f"  Harvests (M1):  {metrics['harvest_count']}")
    ln(f"  Recycles (M2):  {metrics['recycle_count']}")
    ln(f"  P&L/adj:        ${metrics['pnl_per_adjustment']:>+8,.2f}")
    ln()

    # ── Positions ────────────────────────────────────────────────────────────
    ce = result.get("ce", {})
    pe = result.get("pe", {})
    if ce or pe:
        ln("  Positions at end:")
        if ce:
            ln(f"    CE: {int(ce.get('active_lots', 0))}L @ {ce.get('active_strike', '?')}")
        if pe:
            ln(f"    PE: {int(pe.get('active_lots', 0))}L @ {pe.get('active_strike', '?')}")
        ln()

    # ── Verbose: adjustment history ───────────────────────────────────────────
    if verbose:
        adj_history = result.get("adjustment_history", [])
        if adj_history:
            ln("  Adjustment History:")
            for i, adj in enumerate(adj_history[:20], 1):   # Cap at 20
                ln(f"    {i:2}. {adj}")
            if len(adj_history) > 20:
                ln(f"    ... and {len(adj_history)-20} more")
            ln()

    return "\n".join(lines)


def generate_multi_session_report(
    results: List[Dict[str, Any]],
) -> str:
    """
    Generate a summary report across multiple backtest sessions.

    Args:
        results: List of session result dicts.

    Returns:
        Formatted multi-session summary string.
    """
    from .metrics import compute_portfolio_metrics, compute_weakness_probes

    portfolio = compute_portfolio_metrics(results)
    probes    = compute_weakness_probes(results)
    lines     = []

    def ln(x=""): lines.append(x)
    def header(x): lines.append(f"\n{'═'*56}\n  {x}\n{'═'*56}")

    header(f"MMM Backtest Portfolio Report — {len(results)} Sessions")

    # ── Portfolio metrics ────────────────────────────────────────────────────
    ln(f"  Win rate:         {portfolio['win_rate']:.1f}%")
    ln(f"  Total net P&L:    ${portfolio['total_net_pnl']:>+12,.2f}")
    ln(f"  Avg net P&L:      ${portfolio['avg_net_pnl']:>+12,.2f} ± ${portfolio['std_net_pnl']:,.2f}")
    ln(f"  Best session:     ${portfolio['best_session_pnl']:>+12,.2f}")
    ln(f"  Worst session:    ${portfolio['worst_session_pnl']:>+12,.2f}")
    ln()
    ln(f"  Sharpe ratio:     {portfolio['sharpe_ratio']:.4f}")
    ln(f"  Sortino ratio:    {portfolio['sortino_ratio']:.4f}")
    ln(f"  Max drawdown:     ${portfolio['max_drawdown']:>12,.2f}")
    ln(f"  Calmar ratio:     {portfolio['calmar_ratio']}")
    ln()

    # ── Algo stats ────────────────────────────────────────────────────────────
    ln(f"  Avg adjustments:  {portfolio['avg_adjustments']:.1f}/session")
    ln(f"  Avg shifts:       {portfolio['avg_shifts']:.1f}/session")
    ln(f"  Both-sides-up:    {portfolio['total_both_sides_up']} total")
    ln(f"  Total fees:       ${portfolio['total_fees']:>12,.2f}")
    ln(f"  Total slippage:   ${portfolio['total_slippage']:>12,.2f}")
    ln()

    # ── Weakness probes ──────────────────────────────────────────────────────
    header("Weakness Probes")
    for probe_name, probe_data in probes.items():
        ln(f"\n  [{probe_name.replace('_', ' ').upper()}]")
        for k, v in probe_data.items():
            ln(f"    {k:<30}: {v}")

    # ── Per-session table ─────────────────────────────────────────────────────
    header("Per Session Summary")
    ln(f"  {'Date':<12}  {'Status':<10}  {'Net P&L':>10}  {'Adj':>4}  {'Drawdown':>10}")
    ln("  " + "-" * 52)
    for r in results:
        m = compute_session_metrics(r)
        ln(
            f"  {r.get('expiry_date','?'):<12}  "
            f"{r.get('strategy_status','?'):<10}  "
            f"${m['net_pnl']:>+9,.2f}  "
            f"{m['adjustment_count']:>4}  "
            f"${m['max_drawdown']:>9,.2f}"
        )

    return "\n".join(lines)


def result_to_summary_dict(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a session result to a flat summary dict for JSON export / web API.
    """
    metrics = compute_session_metrics(result)
    return {
        "expiry_date":        result.get("expiry_date", ""),
        "strategy_status":    result.get("strategy_status", ""),
        "algo":               result.get("algo", "MMM"),
        "net_pnl":            metrics["net_pnl"],
        "total_pnl":          metrics["total_pnl"],
        "total_fees":         metrics["total_fees"],
        "total_slippage":     metrics["total_slippage_usd"],
        "max_drawdown":       metrics["max_drawdown"],
        "peak_pnl":           metrics["peak_pnl"],
        "calmar_ratio":       metrics["calmar_ratio"],
        "adjustment_count":   metrics["adjustment_count"],
        "both_sides_up":      metrics["both_sides_up"],
        "shift_count":        metrics["shift_count"],
        "close_at_5_count":   metrics["close_at_5_count"],
        "harvest_count":      metrics["harvest_count"],
        "duration_hours":     metrics["duration_hours"],
        "total_beats":        metrics["total_beats"],
        "total_fills":        metrics["total_fills"],
    }
