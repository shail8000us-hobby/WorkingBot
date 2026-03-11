"""
Session Orchestrator
=====================
Orchestrates the complete data collection for a single 0DTE expiry date:
  1. Fetch chain snapshot (all strikes, Greeks, OI, bid/ask)
  2. Fetch 1-min candles for each strike
  3. Fetch perp candles (BTC/ETH spot proxy for delta hedge)
  4. Merge and write to parquet via data_store

Also supports batch collection across a date range.
"""

import logging
import time
from pathlib import Path
from typing import List, Optional, Callable

from .delta_client import DeltaClient
from .chain_collector import fetch_chain_snapshot
from .candle_collector import fetch_all_candles_for_chain, fetch_perp_candles
from .expiry_resolver import expiry_to_session_window

log = logging.getLogger("backtesting.collect_session")


class CollectionResult:
    """Result from collecting one expiry's data."""

    def __init__(self, expiry_date: str, underlying: str):
        self.expiry_date  = expiry_date
        self.underlying   = underlying
        self.success      = False
        self.row_count    = 0
        self.strike_count = 0
        self.error        = None
        self.duration_sec = 0.0

    def __repr__(self):
        status = "OK" if self.success else f"FAILED: {self.error}"
        return f"CollectionResult({self.expiry_date}, {status}, {self.row_count} rows)"


def collect_expiry(
    expiry_date: str,
    underlying: str = "BTC",
    resolution: str = "1m",
    client: Optional[DeltaClient] = None,
    store=None,
    overwrite: bool = False,
    progress_callback: Optional[Callable] = None,
) -> CollectionResult:
    """
    Collect all options data for a single 0DTE expiry date and write to parquet.

    Args:
        expiry_date:       "DD-MM-YYYY"
        underlying:        "BTC" or "ETH"
        resolution:        Candle resolution, default "1m"
        client:            DeltaClient (creates default if None)
        store:             DataStore instance (from data_store.store) — imports lazily
        overwrite:         If True, re-collect even if parquet file already exists
        progress_callback: Optional callable(expiry, step, done, total) for progress UI

    Returns:
        CollectionResult with success flag + stats
    """
    # Lazy import to avoid circular dependency
    from ..data_store.store import DataStore
    from ..data_store.chain_index import ChainIndex

    result = CollectionResult(expiry_date, underlying)
    t_start = time.monotonic()

    if client is None:
        client = DeltaClient()

    if store is None:
        store = DataStore()

    chain_index = ChainIndex()

    # ── Check if already collected ─────────────────────────────────────────
    if not overwrite and chain_index.is_collected(expiry_date, underlying):
        log.info(f"Skipping {expiry_date} {underlying} — already in index (use overwrite=True)")
        result.success   = True
        result.row_count = chain_index.get_row_count(expiry_date, underlying)
        return result

    log.info(f"Starting collection for {expiry_date} {underlying}")

    try:
        # ── Step 1: Fetch chain snapshot ──────────────────────────────────
        if progress_callback:
            progress_callback(expiry_date, "chain_snapshot", 0, 1)

        chain = fetch_chain_snapshot(expiry_date, underlying, client)
        result.strike_count = len(chain)

        if not chain:
            raise ValueError(f"Empty chain for {expiry_date} {underlying}")

        if progress_callback:
            progress_callback(expiry_date, "chain_snapshot", 1, 1)

        # ── Step 2: Fetch 1-min candles for every strike ──────────────────
        def _candle_progress(done, total):
            if progress_callback:
                progress_callback(expiry_date, "candles", done, total)

        rows = fetch_all_candles_for_chain(
            chain, expiry_date, resolution, client, _candle_progress
        )

        if not rows:
            raise ValueError(f"No candle data returned for {expiry_date} {underlying}")

        # ── Step 3: Fetch perp candles (for spot price + delta hedge) ─────
        start_ts, end_ts = expiry_to_session_window(expiry_date)

        if progress_callback:
            progress_callback(expiry_date, "perp_candles", 0, 1)

        perp_candles = fetch_perp_candles(underlying, start_ts, end_ts, resolution, client)

        # ── Step 4: Write to parquet ─────────────────────────────────────
        if progress_callback:
            progress_callback(expiry_date, "writing", 0, 1)

        store.write_options_data(rows, expiry_date, underlying)
        store.write_perp_data(perp_candles, expiry_date, underlying)

        if progress_callback:
            progress_callback(expiry_date, "writing", 1, 1)

        # ── Step 5: Update index ─────────────────────────────────────────
        chain_index.mark_collected(
            expiry_date, underlying,
            row_count=len(rows),
            strike_count=len(chain),
        )

        result.success   = True
        result.row_count = len(rows)
        log.info(
            f"Collected {expiry_date} {underlying}: "
            f"{len(chain)} strikes, {len(rows)} rows, {len(perp_candles)} perp candles"
        )

    except Exception as e:
        result.error = str(e)
        log.error(f"Failed to collect {expiry_date} {underlying}: {e}", exc_info=True)
        chain_index.mark_failed(expiry_date, underlying, str(e))

    result.duration_sec = time.monotonic() - t_start
    return result


def collect_date_range(
    start_date: str,
    end_date: str,
    underlying: str = "BTC",
    resolution: str = "1m",
    overwrite: bool = False,
    delay_between_expiries: float = 1.0,
    progress_callback: Optional[Callable] = None,
) -> List[CollectionResult]:
    """
    Collect data for all past 0DTE expiries in a date range.

    Args:
        start_date:                  "DD-MM-YYYY" (oldest)
        end_date:                    "DD-MM-YYYY" (newest)
        underlying:                  "BTC" or "ETH"
        resolution:                  Candle resolution, default "1m"
        overwrite:                   Re-collect even if already present
        delay_between_expiries:      Seconds to sleep between each expiry collection
        progress_callback:           Optional callable for progress reporting

    Returns:
        List of CollectionResult, one per calendar day in the range.
    """
    from .expiry_resolver import get_expiry_range
    from ..data_store.store import DataStore

    expiries = get_expiry_range(start_date, end_date)
    store    = DataStore()
    client   = DeltaClient()
    results  = []

    log.info(f"Collecting {len(expiries)} expiries for {underlying}: {start_date} → {end_date}")

    for i, expiry_date in enumerate(expiries):
        log.info(f"[{i+1}/{len(expiries)}] Processing {expiry_date}")

        result = collect_expiry(
            expiry_date,
            underlying=underlying,
            resolution=resolution,
            client=client,
            store=store,
            overwrite=overwrite,
            progress_callback=progress_callback,
        )
        results.append(result)

        if i < len(expiries) - 1:
            time.sleep(delay_between_expiries)

    # Summary
    ok_count   = sum(1 for r in results if r.success)
    fail_count = sum(1 for r in results if not r.success)
    log.info(
        f"Collection complete: {ok_count} succeeded, {fail_count} failed "
        f"out of {len(results)} total expiries"
    )

    return results
