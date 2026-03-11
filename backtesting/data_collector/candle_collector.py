"""
Candle Collector
=================
Fetches 1-minute OHLCV candles for individual option symbols from Delta India.

Used to populate intraday mark-price data for each strike in a session.
"""

import time
import logging
from typing import List, Dict, Optional

from .delta_client import DeltaClient, DeltaClientError
from .rate_limiter import get_default_limiter
from .expiry_resolver import expiry_to_session_window

log = logging.getLogger("backtesting.candle_collector")

# Delta returns max 2000 candles per call.
# At 1m resolution, 2000 candles = ~33 hours (enough for one full 0DTE day).
MAX_CANDLES_PER_CALL = 2000


def fetch_option_candles(
    symbol: str,
    from_ts: int,
    to_ts: int,
    resolution: str = "1m",
    client: Optional[DeltaClient] = None,
    limiter=None,
) -> List[Dict]:
    """
    Fetch OHLCV candles for one option symbol.

    Args:
        symbol:     Delta Exchange symbol, e.g. "C-BTC-95000-260310"
        from_ts:    Unix timestamp (seconds), inclusive
        to_ts:      Unix timestamp (seconds), exclusive
        resolution: "1m" (default), "5m", "15m", "1h", "1d"
        client:     DeltaClient instance
        limiter:    Rate limiter (uses default if None)

    Returns:
        List of candle dicts: {time, open, high, low, close, volume}
        Returns empty list if symbol has no data for the window.
    """
    if client is None:
        client = DeltaClient()
    if limiter is None:
        limiter = get_default_limiter()

    # Estimate if we need multiple pages (2000-candle limit)
    duration_secs = to_ts - from_ts
    resolution_secs = _resolution_to_seconds(resolution)
    estimated_candles = duration_secs // resolution_secs

    if estimated_candles <= MAX_CANDLES_PER_CALL:
        # Single request — common case for 1-day 0DTE session
        limiter.wait()
        try:
            candles = client.get_candles(symbol, from_ts, to_ts, resolution)
        except DeltaClientError as e:
            log.warning(f"Failed to fetch candles for {symbol}: {e}")
            return []
        return candles
    else:
        # Paginate by splitting the time window
        all_candles = []
        window_size = MAX_CANDLES_PER_CALL * resolution_secs
        current_start = from_ts

        while current_start < to_ts:
            current_end = min(current_start + window_size, to_ts)
            limiter.wait()
            try:
                batch = client.get_candles(symbol, current_start, current_end, resolution)
            except DeltaClientError as e:
                log.warning(f"Failed to fetch candle page for {symbol}: {e}")
                batch = []

            all_candles.extend(batch)
            if len(batch) < MAX_CANDLES_PER_CALL:
                # No more data in this window
                break
            current_start = current_end

        return all_candles


def fetch_all_candles_for_chain(
    chain: List[Dict],
    expiry_date: str,
    resolution: str = "1m",
    client: Optional[DeltaClient] = None,
    progress_callback=None,
) -> List[Dict]:
    """
    Fetch 1-min candles for every strike in the options chain.

    Merges static chain data (Greeks, IV, OI, bid/ask) with intraday candles.

    Args:
        chain:             List of option dicts from chain_collector.fetch_chain_snapshot()
        expiry_date:       "DD-MM-YYYY" — used to determine the session time window
        resolution:        "1m" (default)
        client:            DeltaClient instance
        progress_callback: Optional callable(done, total) for progress reporting

    Returns:
        List of per-candle-per-strike dicts (merged with chain static fields).
    """
    if client is None:
        client = DeltaClient()

    limiter   = get_default_limiter()
    start_ts, end_ts = expiry_to_session_window(expiry_date)

    all_rows = []
    total = len(chain)

    log.info(
        f"Collecting candles for {total} strikes on {expiry_date} "
        f"[{start_ts} → {end_ts}] at {resolution} resolution"
    )

    for idx, option in enumerate(chain):
        symbol   = option.get("symbol", "")
        strike   = option.get("strike")
        opt_type = option.get("option_type", "??")

        if not symbol:
            log.warning(f"Skipping option with no symbol: {option}")
            continue

        candles = fetch_option_candles(
            symbol, start_ts, end_ts, resolution, client, limiter
        )

        for candle in candles:
            row = {
                # Candle data (intraday)
                "timestamp":    int(candle.get("time", 0)),
                "open":         _safe_float(candle.get("open")),
                "high":         _safe_float(candle.get("high")),
                "low":          _safe_float(candle.get("low")),
                "close":        _safe_float(candle.get("close")),
                "volume":       _safe_float(candle.get("volume")),
                # Identification
                "symbol":       symbol,
                "underlying":   option.get("underlying", "BTC"),
                "expiry_date":  expiry_date,
                "strike":       strike,
                "option_type":  opt_type,
                # Chain snapshot (static for the day)
                "best_bid":     option.get("best_bid"),
                "best_ask":     option.get("best_ask"),
                "oi":           option.get("oi"),
                "delta":        option.get("delta"),
                "gamma":        option.get("gamma"),
                "theta":        option.get("theta"),
                "vega":         option.get("vega"),
                "iv":           option.get("iv"),
            }
            all_rows.append(row)

        if progress_callback:
            progress_callback(idx + 1, total)

        log.debug(f"[{idx+1}/{total}] {symbol}: {len(candles)} candles")

    log.info(
        f"Collected {len(all_rows)} total rows for {expiry_date} "
        f"across {total} strikes"
    )
    return all_rows


def fetch_perp_candles(
    underlying: str = "BTC",
    from_ts: int = None,
    to_ts: int = None,
    resolution: str = "1m",
    client: Optional[DeltaClient] = None,
) -> List[Dict]:
    """
    Fetch BTC/ETH perpetual futures candles for delta hedge simulation.

    Args:
        underlying: "BTC" → symbol="BTCUSD", "ETH" → "ETHUSD"
        from_ts:    Unix timestamp (seconds)
        to_ts:      Unix timestamp (seconds)
        resolution: "1m" (default)
        client:     DeltaClient instance

    Returns:
        List of candle dicts: {time, open, high, low, close, volume}
    """
    symbol_map = {"BTC": "BTCUSD", "ETH": "ETHUSD"}
    symbol = symbol_map.get(underlying.upper(), f"{underlying.upper()}USD")

    if client is None:
        client = DeltaClient()

    limiter = get_default_limiter()
    return fetch_option_candles(symbol, from_ts, to_ts, resolution, client, limiter)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _resolution_to_seconds(resolution: str) -> int:
    """Convert resolution string to seconds count."""
    table = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
    return table.get(resolution, 60)


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
