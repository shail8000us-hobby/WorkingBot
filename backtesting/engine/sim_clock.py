"""
Simulation Clock
=================
Virtual clock that iterates minute-by-minute through parquet data.

Provides a controlled timeline for the simulation, supporting:
  - Sequential tick iteration
  - Jump-to-timestamp (for late-entry simulation)
  - Adaptive heartbeat interval (skip ticks to match MMM's 60–1200s intervals)
  - Expiry detection (auto-stop at session end)
"""

import logging
from typing import Iterator, List, Optional, Tuple
import pandas as pd

log = logging.getLogger("backtesting.sim_clock")


class SimClock:
    """
    Virtual clock over parquet candle data.

    Usage:
        clock = SimClock(df, expiry_date="10-03-2026")
        clock.jump_to_time("09:15")   # IST time
        for ts, df_slice in clock.ticks():
            chain = sim_chain.get_chain_at(ts)
            algo_adapter.on_heartbeat(ts, chain)
    """

    def __init__(
        self,
        df: pd.DataFrame,
        expiry_date: str = "",
        heartbeat_interval_sec: int = 60,
    ):
        """
        Args:
            df:                     Options candle DataFrame (from DataStore.read_options_data)
            expiry_date:            "DD-MM-YYYY" — used for display only
            heartbeat_interval_sec: How many seconds between ticks (default: 60 = every minute).
                                    The MMM adapter will override this dynamically.
        """
        self.expiry_date = expiry_date
        self.heartbeat_interval_sec = heartbeat_interval_sec

        # Build sorted list of unique timestamps (Unix ms)
        if df.empty:
            raise ValueError("SimClock received empty DataFrame — no candle data")

        all_ts = sorted(df["timestamp"].dropna().unique().tolist())
        self._timestamps: List[int] = [int(t) for t in all_ts]
        self._current_idx: int = 0

        log.info(
            f"SimClock initialized: {expiry_date}, "
            f"{len(self._timestamps)} timestamps, "
            f"range [{self._timestamps[0]} → {self._timestamps[-1]}]"
        )

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def current_ts(self) -> int:
        """Current timestamp in Unix milliseconds."""
        if self._current_idx >= len(self._timestamps):
            return self._timestamps[-1]
        return self._timestamps[self._current_idx]

    @property
    def current_ts_sec(self) -> int:
        """Current timestamp in Unix seconds."""
        return self.current_ts // 1000

    @property
    def is_done(self) -> bool:
        """Return True when there are no more ticks."""
        return self._current_idx >= len(self._timestamps)

    @property
    def progress_pct(self) -> float:
        """Progress through the session (0.0 to 1.0)."""
        if not self._timestamps:
            return 1.0
        return self._current_idx / len(self._timestamps)

    def total_ticks(self) -> int:
        """Total number of available ticks."""
        return len(self._timestamps)

    def ticks_remaining(self) -> int:
        """Number of ticks remaining."""
        return max(0, len(self._timestamps) - self._current_idx)

    # ── Navigation ────────────────────────────────────────────────────────────

    def jump_to_index(self, idx: int):
        """Jump to a specific index in the timestamp list."""
        self._current_idx = max(0, min(idx, len(self._timestamps) - 1))

    def jump_to_ts(self, target_ts_ms: int):
        """
        Jump to the first timestamp >= target_ts_ms.

        Args:
            target_ts_ms: Target timestamp in Unix milliseconds.
        """
        for i, ts in enumerate(self._timestamps):
            if ts >= target_ts_ms:
                self._current_idx = i
                log.debug(f"Clock jumped to index {i}, ts={ts}")
                return
        # If target is beyond all data, jump to end
        self._current_idx = len(self._timestamps)
        log.warning(f"jump_to_ts({target_ts_ms}) is beyond all available data")

    def jump_to_ist_time(self, ist_time_str: str):
        """
        Jump to the first candle at or after a given IST time on the expiry date.

        Args:
            ist_time_str: "HH:MM" in IST, e.g. "09:15"

        Note: IST = UTC + 5:30, so 09:15 IST = 03:45 UTC
        """
        from datetime import datetime, timezone, timedelta

        expiry_dt = datetime.strptime(self.expiry_date, "%d-%m-%Y").replace(tzinfo=timezone.utc)
        hour, minute = map(int, ist_time_str.split(":"))

        # Convert IST to UTC
        ist_offset = timedelta(hours=5, minutes=30)
        target_utc = expiry_dt.replace(hour=hour, minute=minute) - ist_offset
        target_ms  = int(target_utc.timestamp() * 1000)

        log.info(f"Jumping to IST {ist_time_str} = UTC {target_utc.strftime('%H:%M')} (ts_ms={target_ms})")
        self.jump_to_ts(target_ms)

    def find_index_of_ts(self, target_ts_ms: int) -> int:
        """Return the index of the first timestamp >= target_ts_ms, or -1 if not found."""
        for i, ts in enumerate(self._timestamps):
            if ts >= target_ts_ms:
                return i
        return -1

    # ── Tick iterator ────────────────────────────────────────────────────────

    def ticks(
        self,
        interval_sec: Optional[int] = None,
    ) -> Iterator[int]:
        """
        Yield timestamps one by one, respecting the heartbeat interval.

        If interval_sec > 60, skips intermediate 1-min candles to simulate
        the MMM adaptive heartbeat (60–1200s).

        Usage:
            for ts_ms in clock.ticks(interval_sec=300):
                chain = sim_chain.at(ts_ms)
                do_heartbeat(ts_ms, chain)

        Args:
            interval_sec: Override for this iteration (None uses self.heartbeat_interval_sec)

        Yields:
            Unix timestamps in milliseconds.
        """
        if interval_sec is None:
            interval_sec = self.heartbeat_interval_sec

        interval_ms = interval_sec * 1000
        last_yielded_ts = None

        while not self.is_done:
            ts = self._timestamps[self._current_idx]

            # First tick is always yielded
            if last_yielded_ts is None or ts - last_yielded_ts >= interval_ms:
                yield ts
                last_yielded_ts = ts

            self._current_idx += 1

    def advance_by_interval(self, interval_sec: int):
        """
        Advance the clock by approximately interval_sec from the current position.

        Used by the MMM adapter to simulate adaptive heartbeat jumps without
        iterating every minute.
        """
        interval_ms = interval_sec * 1000
        target_ts = self.current_ts + interval_ms
        self.jump_to_ts(target_ts)

    def peek_next_ts(self, offset: int = 1) -> Optional[int]:
        """Return the timestamp at current_idx + offset without advancing."""
        idx = self._current_idx + offset
        if idx < len(self._timestamps):
            return self._timestamps[idx]
        return None
