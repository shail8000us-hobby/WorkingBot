"""
CLI: Parameter Sweep / Optimization
=====================================
Run parameter optimization for MMM backtesting from the command line.

Usage:
    # Grid search (exhaustive)
    python -m backtesting.scripts.sweep_params \\
        --mode grid \\
        --start 01-02-2026 --end 10-03-2026 \\
        --param desired_ce_premium 100 150 200 \\
        --param desired_pe_premium 100 150 200 \\
        --param initial_lots 5 10 \\
        --output grid_results.json

    # Walk-forward optimization
    python -m backtesting.scripts.sweep_params \\
        --mode walk_forward \\
        --start 01-01-2026 --end 10-03-2026 \\
        --train-days 20 --test-days 5 \\
        --param desired_ce_premium 100 150 200 \\
        --param initial_lots 5 10

    # Bayesian optimization (needs scikit-optimize)
    python -m backtesting.scripts.sweep_params \\
        --mode bayesian \\
        --start 01-02-2026 --end 10-03-2026 \\
        --param-range desired_ce_premium 50 300 real \\
        --param-range initial_lots 3 25 int \\
        --n-calls 50
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backtesting.data_collector.expiry_resolver import get_expiry_range

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("sweep_params")


def main():
    parser = argparse.ArgumentParser(description="MMM Parameter Optimization")

    # Mode
    parser.add_argument("--mode", choices=["grid", "walk_forward", "bayesian"],
                        default="grid", help="Optimization mode")

    # Date range
    parser.add_argument("--start",     type=str, required=True, help="Start date DD-MM-YYYY")
    parser.add_argument("--end",       type=str, required=True, help="End date DD-MM-YYYY")
    parser.add_argument("--underlying", type=str, default="BTC")

    # Grid / categorical params: --param name val1 val2 val3
    parser.add_argument("--param", action="append", nargs="+", metavar=("NAME", "VAL"),
                        help="Parameter name followed by values: --param initial_lots 5 10 15")

    # Continuous params for Bayesian: --param-range name min max type
    parser.add_argument("--param-range", action="append", nargs=4,
                        metavar=("NAME", "MIN", "MAX", "TYPE"),
                        help="Continuous param range for Bayesian: --param-range desired_ce_premium 50 300 real")

    # Walk-forward settings
    parser.add_argument("--train-days",  type=int, default=20)
    parser.add_argument("--test-days",   type=int, default=5)
    parser.add_argument("--optimize-on", type=str, default="sharpe_ratio")

    # Bayesian settings
    parser.add_argument("--n-calls",    type=int, default=50)

    # Execution
    parser.add_argument("--slippage",   type=float, default=2.0)
    parser.add_argument("--margin",     type=float, default=500_000.0)
    parser.add_argument("--entry-time", type=str,   default="09:15")
    parser.add_argument("--output",     type=str,   default=None)
    parser.add_argument("--top-n",      type=int,   default=5)

    args = parser.parse_args()

    # ── Build param grid ─────────────────────────────────────────────────────
    param_grid = {}
    if args.param:
        for spec in args.param:
            name   = spec[0]
            values = spec[1:]
            # Auto-detect numeric vs string
            parsed = []
            for v in values:
                try:
                    parsed.append(int(v))
                except ValueError:
                    try:
                        parsed.append(float(v))
                    except ValueError:
                        parsed.append(v)
            param_grid[name] = parsed

    # ── Build param space (for Bayesian) ─────────────────────────────────────
    param_space = {}
    if args.param_range:
        for spec in args.param_range:
            name, lo, hi, dtype = spec
            param_space[name] = (float(lo), float(hi), dtype)

    expiry_dates = get_expiry_range(args.start, args.end)
    print(f"\n🔬 Optimization mode: {args.mode}")
    print(f"   Date range: {args.start} → {args.end} ({len(expiry_dates)} dates)")
    print(f"   Params: {list(param_grid.keys()) or list(param_space.keys())}")
    print()

    # ── Progress callback ─────────────────────────────────────────────────────
    def progress(done, total):
        pct = done / total * 100 if total else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"\r  [{bar}] {done}/{total} ({pct:.0f}%)", end="", flush=True)

    result = None

    # ── Grid search ───────────────────────────────────────────────────────────
    if args.mode == "grid":
        if not param_grid:
            print("❌ Grid search requires --param specifications")
            sys.exit(1)

        from backtesting.optimizer.grid_search import GridSearch
        gs = GridSearch(
            param_grid=param_grid,
            expiry_dates=expiry_dates,
            underlying=args.underlying,
            entry_ist_time=args.entry_time,
            slippage_bps=args.slippage,
            initial_margin_usd=args.margin,
            progress_callback=progress,
        )

        n_combos = 1
        for v in param_grid.values():
            n_combos *= len(v)
        print(f"   {n_combos} param combinations × {len(expiry_dates)} dates = {n_combos * len(expiry_dates)} sessions\n")

        portfolio_results = gs.run()
        print(f"\n\n{'='*60}")
        print(f"  TOP {min(args.top_n, len(portfolio_results))} PARAM SETS (by {args.optimize_on}):")
        print(f"{'='*60}")
        for i, pr in enumerate(portfolio_results[:args.top_n]):
            print(f"\n  #{i+1}")
            print(f"  Params: {pr['params']}")
            print(f"  Sharpe:  {pr.get('sharpe_ratio', 0):.4f}")
            print(f"  Win rate: {pr.get('win_rate', 0):.1f}%")
            print(f"  Avg P&L: ${pr.get('avg_net_pnl', 0):>+,.2f}")
            print(f"  Max DD:  ${pr.get('max_drawdown', 0):>,.2f}")

        print(f"\n✅ Best: {portfolio_results[0]['params']}")
        result = {"mode": "grid", "top_results": portfolio_results[:args.top_n]}

    # ── Walk-forward ──────────────────────────────────────────────────────────
    elif args.mode == "walk_forward":
        if not param_grid:
            print("❌ Walk-forward requires --param specifications")
            sys.exit(1)

        from backtesting.optimizer.walk_forward import WalkForwardOptimizer
        wfo = WalkForwardOptimizer(
            param_grid=param_grid,
            start_date=args.start,
            end_date=args.end,
            train_days=args.train_days,
            test_days=args.test_days,
            underlying=args.underlying,
            entry_ist_time=args.entry_time,
            slippage_bps=args.slippage,
            initial_margin_usd=args.margin,
            optimize_on=args.optimize_on,
            progress_callback=progress,
        )
        report = wfo.run()
        print(f"\n\n{'='*60}")
        print(f"  WALK-FORWARD RESULTS")
        print(f"{'='*60}")
        print(f"  Windows:         {report['n_windows']}")
        print(f"  OOS Sharpe:      {report['oos_sharpe']:.4f}")
        print(f"  OOS Win rate:    {report['oos_win_rate']:.1f}%")
        print(f"  OOS Avg P&L:     ${report['oos_avg_pnl']:>+,.2f}")
        print(f"  IS/OOS ratio:    {report['efficiency']:.2f}  {'✅' if report['efficiency'] > 0.7 else '⚠️  (possible overfit)'}")
        result = report

    # ── Bayesian ─────────────────────────────────────────────────────────────
    elif args.mode == "bayesian":
        if not param_space:
            print("❌ Bayesian optimization requires --param-range specifications")
            sys.exit(1)

        from backtesting.optimizer.bayesian_optimizer import BayesianOptimizer
        opt = BayesianOptimizer(
            param_space=param_space,
            expiry_dates=expiry_dates,
            underlying=args.underlying,
            entry_ist_time=args.entry_time,
            slippage_bps=args.slippage,
            initial_margin_usd=args.margin,
            n_calls=args.n_calls,
            optimize_on=args.optimize_on,
            progress_callback=progress,
        )
        report = opt.run()
        print(f"\n\n{'='*60}")
        print(f"  BAYESIAN OPTIMIZATION RESULTS")
        print(f"{'='*60}")
        print(f"  Best params:     {report['best_params']}")
        print(f"  Best {args.optimize_on}: {report['best_score']:.4f}")
        result = report

    # ── Save output ───────────────────────────────────────────────────────────
    if result and args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n💾 Results saved → {args.output}")


if __name__ == "__main__":
    main()
