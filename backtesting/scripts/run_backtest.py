"""
CLI: Run a Single Backtest Session
=====================================
Runs one or more MMM backtest sessions from the command line.

Usage:
    # Run MMM backtest for a single date (fresh mode)
    python -m backtesting.scripts.run_backtest --date 08-03-2026

    # Run across a date range
    python -m backtesting.scripts.run_backtest --start 01-03-2026 --end 10-03-2026

    # Run with custom params
    python -m backtesting.scripts.run_backtest --date 08-03-2026 \\
        --ce-premium 150 --pe-premium 150 --lots 10 --slippage 2

    # Import mode (start from specific strikes)
    python -m backtesting.scripts.run_backtest --date 08-03-2026 \\
        --mode import --ce-strike 97000 --pe-strike 93000 \\
        --ce-premium 120 --pe-premium 120

    # Save results to JSON
    python -m backtesting.scripts.run_backtest --date 08-03-2026 --output results.json
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backtesting.data_store import DataStore
from backtesting.engine import run_session
from backtesting.strategies.mmm import MMMAdapter
from backtesting.analytics import (
    generate_session_report, generate_multi_session_report,
    result_to_summary_dict, compute_portfolio_metrics,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run_backtest")


def _build_params(args) -> dict:
    return {
        "desired_ce_premium":        args.ce_premium,
        "desired_pe_premium":        args.pe_premium,
        "initial_lots":              args.lots,
        "min_trigger_move_pct":      args.trigger_pct,
        "shift_threshold":           getattr(args, "shift_threshold", 50.0),
        "close_at_threshold":        args.close_at,
        "wind_down_enabled":         not getattr(args, "no_wind_down", False),
        "wind_down_minutes":         getattr(args, "wind_down_mins", 120),
        "harvest_enabled":           not getattr(args, "no_harvest", False),
        "recycle_enabled":           not getattr(args, "no_recycle", False),
        "perp_hedge_enabled":        getattr(args, "perp_hedge", False),
        # Import mode fields
        "ce_strike":                 getattr(args, "ce_strike", 0),
        "pe_strike":                 getattr(args, "pe_strike", 0),
        "ce_entry_premium":          getattr(args, "ce_entry_premium", args.ce_premium),
        "pe_entry_premium":          getattr(args, "pe_entry_premium", args.pe_premium),
    }


def run_one(expiry_date: str, args, store: DataStore) -> dict:
    """Run a single backtest session and return the result dict."""
    underlying = args.underlying.upper()

    # Load data
    try:
        df = store.read_options_data(expiry_date, underlying)
    except FileNotFoundError:
        print(f"  ❌ No data for {expiry_date}. Run collect_data.py first.")
        return {"expiry_date": expiry_date, "strategy_status": "ERROR", "error": "No data",
                "total_pnl": 0, "net_pnl": 0, "max_drawdown": 0}

    perp_df = store.read_perp_data(expiry_date, underlying)

    params = _build_params(args)
    params["expiry_date"] = expiry_date

    adapter = MMMAdapter(mode=args.mode)

    result = run_session(
        df=df,
        algo_adapter=adapter,
        params=params,
        entry_ist_time=args.entry_time,
        expiry_date=expiry_date,
        underlying=underlying,
        slippage_bps=args.slippage,
        initial_margin_usd=args.margin,
        perp_df=perp_df,
    )

    return result


def main():
    parser = argparse.ArgumentParser(description="Run MMM backtest")

    # Date selection
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--date",  type=str, help="Single date: DD-MM-YYYY")
    grp.add_argument("--start", type=str, help="Start date: DD-MM-YYYY")

    parser.add_argument("--end",         type=str, default=None)
    parser.add_argument("--underlying",  type=str, default="BTC")
    parser.add_argument("--mode",        type=str, default="fresh",     choices=["fresh", "import"])
    parser.add_argument("--entry-time",  type=str, default="09:15",     help="IST entry time HH:MM")
    # Strategy params
    parser.add_argument("--ce-premium",  type=float, default=150.0)
    parser.add_argument("--pe-premium",  type=float, default=150.0)
    parser.add_argument("--lots",        type=int,   default=10)
    parser.add_argument("--trigger-pct", type=float, default=3.0)
    parser.add_argument("--close-at",    type=float, default=5.0)
    # Import mode
    parser.add_argument("--ce-strike",   type=float, default=0)
    parser.add_argument("--pe-strike",   type=float, default=0)
    # Simulation params
    parser.add_argument("--slippage",    type=float, default=2.0,        help="Slippage bps")
    parser.add_argument("--margin",      type=float, default=500_000.0,  help="Starting margin USD")
    # Output
    parser.add_argument("--output",      type=str,   default=None,       help="JSON output file path")
    parser.add_argument("--verbose",     action="store_true")
    parser.add_argument("--quiet",       action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.CRITICAL)

    store = DataStore()

    # ── Collect expiry list ────────────────────────────────────────────────────
    if args.date:
        expiries = [args.date]
    else:
        end = args.end or datetime.now(timezone.utc).strftime("%d-%m-%Y")
        from backtesting.data_collector.expiry_resolver import get_expiry_range
        expiries = get_expiry_range(args.start, end)

    print(f"\n🚀 MMM Backtest — {len(expiries)} session(s), mode={args.mode}")

    results = []
    for i, expiry in enumerate(expiries):
        print(f"[{i+1}/{len(expiries)}] {expiry} ...", end=" ", flush=True)
        r = run_one(expiry, args, store)
        results.append(r)
        net = r.get("net_pnl", r.get("total_pnl", 0))
        status = r.get("strategy_status", "?")
        icon = "✅" if status == "COMPLETE" else "⚠️" if status == "STOPPED" else "❌"
        print(f"{icon} {status}: ${net:>+,.2f}")

    # ── Report ────────────────────────────────────────────────────────────────
    if len(results) == 1:
        print(generate_session_report(results[0], verbose=args.verbose))
    else:
        print(generate_multi_session_report(results))

    # ── JSON output ──────────────────────────────────────────────────────────
    if args.output:
        output_data = {
            "sessions": [result_to_summary_dict(r) for r in results],
            "portfolio": compute_portfolio_metrics(results),
        }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2, default=str)
        print(f"\n💾 Results saved to {args.output}")


if __name__ == "__main__":
    main()
