"""
CLI: Collect Historical Options Data
======================================
Fetches historical options data from Delta Exchange India and saves to parquet.

Usage:
    # Collect last 7 days of BTC 0DTE data
    python -m backtesting.scripts.collect_data --days 7

    # Collect specific date
    python -m backtesting.scripts.collect_data --date 08-03-2026

    # Collect a date range
    python -m backtesting.scripts.collect_data --start 01-03-2026 --end 10-03-2026

    # Collect ETH
    python -m backtesting.scripts.collect_data --days 7 --underlying ETH

    # Force re-collect
    python -m backtesting.scripts.collect_data --days 3 --overwrite

    # Check integrity after collecting
    python -m backtesting.scripts.collect_data --days 7 --check
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path so we can import backtesting.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backtesting.data_collector import collect_expiry, collect_date_range
from backtesting.data_collector.expiry_resolver import get_past_expiries
from backtesting.data_store import DataStore, ChainIndex, check_date_range

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("collect_data")


def main():
    parser = argparse.ArgumentParser(
        description="Collect historical options data from Delta Exchange India"
    )

    # Date selection (mutually exclusive)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--date",  type=str, help="Single expiry date: DD-MM-YYYY")
    group.add_argument("--days",  type=int, default=7, help="Number of past days (default: 7)")
    group.add_argument("--start", type=str, help="Start date of range: DD-MM-YYYY")

    parser.add_argument("--end",        type=str, default=None,  help="End date (with --start): DD-MM-YYYY")
    parser.add_argument("--underlying", type=str, default="BTC", help="BTC or ETH (default: BTC)")
    parser.add_argument("--resolution", type=str, default="1m",  help="Candle resolution (default: 1m)")
    parser.add_argument("--overwrite",  action="store_true",     help="Re-collect even if already present")
    parser.add_argument("--check",      action="store_true",     help="Run integrity check after collection")
    parser.add_argument("--status",     action="store_true",     help="Show collection status and exit")
    parser.add_argument("--verbose",    action="store_true",     help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    underlying = args.underlying.upper()

    # ── --status: show index without collecting ────────────────────────────────
    if args.status:
        idx = ChainIndex()
        summary = idx.summary()
        print("\n📊 Collection Index Summary")
        print(f"  Underlying:     {underlying}")
        print(f"  Total expiries: {summary['total_expiries']}")
        print(f"  Collected:      {summary['collected']}")
        print(f"  Failed:         {summary['failed']}")
        print(f"  Total rows:     {summary['total_rows']:,}")

        collected = idx.list_collected(underlying)
        if collected:
            print(f"\n✅ Collected dates ({len(collected)}):")
            for d in collected[:10]:
                rows = idx.get_row_count(d, underlying)
                store = DataStore()
                size_mb = store.file_size_mb(d, underlying)
                print(f"  {d}: {rows:>8,} rows  ({size_mb:.1f} MB)")
            if len(collected) > 10:
                print(f"  ... and {len(collected) - 10} more")

        failed = idx.list_failed(underlying)
        if failed:
            print(f"\n❌ Failed dates: {', '.join(failed)}")

        return

    # ── Determine expiry list ─────────────────────────────────────────────────
    if args.date:
        expiries = [args.date]
        start_date = end_date = args.date
    elif args.start:
        end_date = args.end or datetime.now(timezone.utc).strftime("%d-%m-%Y")
        from backtesting.data_collector.expiry_resolver import get_expiry_range
        expiries = get_expiry_range(args.start, end_date)
        start_date = args.start
    else:
        expiries = get_past_expiries(days_back=args.days, underlying=underlying)
        start_date = expiries[-1] if expiries else ""
        end_date   = expiries[0]  if expiries else ""

    print(f"\n🚀 Collecting {len(expiries)} expiries for {underlying}")
    print(f"   Range: {start_date} → {end_date}")
    print(f"   Resolution: {args.resolution}")
    print(f"   Overwrite: {args.overwrite}")
    print()

    # ── Progress callback ─────────────────────────────────────────────────────
    def progress(expiry, step, done, total):
        bar = "█" * int(20 * done / total) + "░" * (20 - int(20 * done / total)) if total > 0 else ""
        print(f"\r  [{bar}] {done}/{total} {step:<20}", end="", flush=True)

    # ── Run collection ────────────────────────────────────────────────────────
    results = []
    for i, expiry in enumerate(expiries):
        print(f"[{i+1}/{len(expiries)}] {expiry} ...", end="", flush=True)
        result = collect_expiry(
            expiry,
            underlying=underlying,
            resolution=args.resolution,
            overwrite=args.overwrite,
            progress_callback=progress,
        )
        results.append(result)
        if result.success:
            print(f"\r[{i+1}/{len(expiries)}] ✅ {expiry}: {result.row_count:,} rows, {result.strike_count} strikes ({result.duration_sec:.1f}s)")
        else:
            print(f"\r[{i+1}/{len(expiries)}] ❌ {expiry}: {result.error}")

    # ── Summary ───────────────────────────────────────────────────────────────
    ok_count   = sum(1 for r in results if r.success)
    fail_count = sum(1 for r in results if not r.success)
    total_rows = sum(r.row_count for r in results)
    total_time = sum(r.duration_sec for r in results)

    print(f"\n{'='*50}")
    print(f"  ✅ {ok_count} succeeded,  ❌ {fail_count} failed")
    print(f"  Total rows: {total_rows:,}")
    print(f"  Total time: {total_time:.1f}s")
    print(f"{'='*50}")

    # ── Integrity check ────────────────────────────────────────────────────────
    if args.check and ok_count > 0:
        print("\n🔍 Running integrity check...")
        report = check_date_range(start_date, end_date, underlying)
        clean = report["clean"]
        warns = report["with_warnings"]
        errs  = report["with_errors"]
        print(f"  Clean: {clean}, Warnings: {warns}, Errors: {errs}")

        for issue in report["issues"]:
            icon = "✅" if issue.severity == "INFO" else "⚠️" if issue.severity == "WARNING" else "❌"
            print(f"  {icon} {issue}")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
