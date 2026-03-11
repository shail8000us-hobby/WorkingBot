"""
Session Runner
===============
Generic backtest session loop, algo-agnostic.

Orchestrates:
  1. Clock initialization from parquet data
  2. Chain + broker + margin setup
  3. Algo adapter setup (entry)
  4. Tick-by-tick heartbeat loop
  5. Session result collection
  6. Trade log + metrics computation

Used by:
  - scripts/run_backtest.py (CLI)
  - ui/backend/api_backtest.py (Web UI)
"""

import logging
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone

from .sim_clock import SimClock
from .sim_chain import SimChain
from .sim_broker import SimBroker
from .sim_margin import MarginState
from .base_algo_adapter import BaseAlgoAdapter

log = logging.getLogger("backtesting.session_runner")


class SessionRunnerError(Exception):
    """Raised when the session runner encounters an unrecoverable error."""
    pass


def run_session(
    df,                              # Options candle DataFrame
    algo_adapter: BaseAlgoAdapter,
    params: Dict[str, Any],
    entry_ist_time: str = "09:15",   # "HH:MM" IST
    expiry_date: str = "",
    underlying: str = "BTC",
    slippage_bps: float = 2.0,
    min_oi_lots: float = 50.0,
    initial_margin_usd: float = 500_000.0,
    perp_df=None,                    # Optional perp candle DataFrame
    progress_callback: Optional[Callable] = None,
    on_tick_callback: Optional[Callable] = None,
    max_runtime_sec: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run a complete backtest session.

    Args:
        df:                  Options candle DataFrame from DataStore.read_options_data()
        algo_adapter:        Strategy adapter implementing BaseAlgoAdapter
        params:              Algo-specific parameters (e.g., MMM params dict)
        entry_ist_time:      Entry time in IST "HH:MM" format (default: 09:15)
        expiry_date:         "DD-MM-YYYY" for display/logging
        underlying:          "BTC" or "ETH"
        slippage_bps:        Slippage in basis points (default: 2)
        min_oi_lots:         Minimum OI required for execution (default: 50)
        initial_margin_usd:  Starting margin balance
        perp_df:             Optional perp candles for spot price / delta hedge
        progress_callback:   Optional callable(pct_done, current_ts_ms) for progress UI
        on_tick_callback:    Optional callable(ts_ms, session_state_snapshot) for live feed
        max_runtime_sec:     Hard wall-clock limit (safety, default: None = unlimited)

    Returns:
        Session result dict (see BaseAlgoAdapter.get_session_result() for schema).
    """
    t_start = time.monotonic()

    log.info(
        f"Starting session: {expiry_date} {underlying}, "
        f"entry={entry_ist_time} IST, "
        f"algo={algo_adapter.get_algo_name()}"
    )

    # ── 1. Build simulation components ────────────────────────────────────────
    clock  = SimClock(df, expiry_date=expiry_date)
    chain  = SimChain(df)
    broker = SimBroker(
        slippage_bps=slippage_bps,
        min_oi_lots=min_oi_lots,
        initial_margin_usd=initial_margin_usd,
    )
    margin = MarginState(initial_balance_usd=initial_margin_usd)

    # Load perp data for spot price queries
    if perp_df is not None and not perp_df.empty:
        chain.load_perp_data(perp_df)

    # ── 2. Jump to entry time ─────────────────────────────────────────────────
    clock.jump_to_ist_time(entry_ist_time)
    entry_ts_ms = clock.current_ts

    if clock.is_done:
        log.error(f"Clock is done after jump to {entry_ist_time} IST — entry time is after all data")
        return _error_result(expiry_date, entry_ts_ms, "Entry time is after all available candle data")

    log.info(
        f"Clock jumped to {entry_ist_time} IST: "
        f"ts={entry_ts_ms}, {clock.ticks_remaining()} ticks remaining"
    )

    # ── 3. Setup the algo ─────────────────────────────────────────────────────
    try:
        algo_adapter.setup(params, chain, broker, margin, entry_ts_ms)
    except Exception as e:
        log.error(f"Algo setup failed: {e}", exc_info=True)
        return _error_result(expiry_date, entry_ts_ms, f"Setup failed: {e}")

    # ── 4. Heartbeat loop ─────────────────────────────────────────────────────
    tick_count = 0
    last_ts_ms = entry_ts_ms

    try:
        for ts_ms in clock.ticks(interval_sec=1):  # 1-sec tick granularity; adapter controls actual pacing
            tick_count += 1

            # Check for done condition BEFORE heartbeat
            if algo_adapter.is_done():
                log.info(f"Algo finished at ts={ts_ms} (tick {tick_count})")
                break

            # Progress callback
            if progress_callback:
                progress_callback(clock.progress_pct, ts_ms)

            # Wall-clock time limit
            if max_runtime_sec and (time.monotonic() - t_start) > max_runtime_sec:
                log.warning(f"Max runtime reached ({max_runtime_sec}s). Stopping session.")
                break

            # Run heartbeat
            try:
                algo_adapter.on_heartbeat(ts_ms, chain)
            except Exception as e:
                log.error(f"Heartbeat error at ts={ts_ms}: {e}", exc_info=True)
                # Heartbeat errors are non-fatal — log and continue
                continue

            # Per-tick callback for live UI streaming
            if on_tick_callback:
                try:
                    on_tick_callback(ts_ms, broker.fills_as_df())
                except Exception:
                    pass  # Suppress callback errors

            # Advance clock by the adapter's desired interval
            interval_sec = algo_adapter.get_heartbeat_interval_sec()
            if interval_sec > 60:
                clock.advance_by_interval(interval_sec)
                # Sync the iterator by jumping
                # (the for loop will naturally skip ahead after advance_by_interval
                #  modifies _current_idx)

            last_ts_ms = ts_ms

    except Exception as e:
        log.error(f"Fatal session error: {e}", exc_info=True)

    # ── 5. Session end hook ───────────────────────────────────────────────────
    try:
        algo_adapter.on_session_end()
    except Exception as e:
        log.warning(f"on_session_end() error: {e}")

    # ── 6. Collect result ─────────────────────────────────────────────────────
    try:
        result = algo_adapter.get_session_result()
    except Exception as e:
        log.error(f"get_session_result() failed: {e}", exc_info=True)
        result = _error_result(expiry_date, entry_ts_ms, f"Result collection failed: {e}")

    # Enrich result with runner metadata
    wall_clock_duration = time.monotonic() - t_start
    result.update({
        "expiry_date":        expiry_date,
        "underlying":         underlying,
        "entry_ist_time":     entry_ist_time,
        "entry_ts_ms":        entry_ts_ms,
        "end_ts_ms":          last_ts_ms,
        "total_slippage_usd": broker.total_slippage_usd(),
        "total_fees_usd":     broker.total_fees_usd,
        "tick_count":         tick_count,
        "wall_clock_sec":     round(wall_clock_duration, 2),
        "fills":              broker.fills_as_df().to_dict(orient="records") if hasattr(broker.fills_as_df(), 'to_dict') else [],
        "final_margin":       margin.to_dict(),
    })

    log.info(
        f"Session complete: {expiry_date}, "
        f"{tick_count} ticks, "
        f"P&L={result.get('total_pnl', 0):.2f}, "
        f"wall_clock={wall_clock_duration:.1f}s"
    )

    return result


def _error_result(expiry_date: str, entry_ts_ms: int, error_msg: str) -> Dict:
    """Return a minimal error result dict."""
    return {
        "expiry_date":      expiry_date,
        "strategy_status":  "ERROR",
        "error":            error_msg,
        "total_pnl":        0.0,
        "realized_pnl":     0.0,
        "unrealized_pnl":   0.0,
        "total_fees":       0.0,
        "adjustment_count": 0,
        "entry_ts_ms":      entry_ts_ms,
        "end_ts_ms":        entry_ts_ms,
    }
