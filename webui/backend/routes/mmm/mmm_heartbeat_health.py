"""
MMM Heartbeat Health Tracker

Institutional-grade beat telemetry: latency percentiles, miss counting,
consecutive failure tracking, and an A–F health grade computed from
rolling statistics.

Designed to be attached to one MMMMonitor instance. Zero impact on
trading logic — pure observability layer.

Health Grade Rubric
-------------------
  A  : p95 latency < 80% of interval, miss_rate % < 2%, no failures in last 10 beats
  B  : p95 < interval, miss_rate < 5%, failures in last 10 ≤ 1
  C  : p95 < 1.5× interval, miss_rate < 10%, failures ≤ 3
  D  : p95 < 2× interval, miss_rate < 20%, failures ≤ 5
  F  : anything worse

Created: February 18, 2026
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Dict, Optional

log = logging.getLogger('mmm_heartbeat_health')

# Rolling window sizes
LATENCY_WINDOW = 100          # last N beats kept for percentile math
FAILURE_WINDOW = 10           # last N beats inspected for failure grade
MISS_WINDOW = 50              # window for miss-rate calculation
MAX_STALE_CONSECUTIVE = 3     # how many beats with identical price before stale alarm


@dataclass
class BeatRecord:
    """One heartbeat's outcome record."""
    timestamp: float           # wall-clock seconds (time.monotonic())
    latency_ms: float          # total beat execution time
    outcome: str               # 'ok' | 'partial' | 'miss' | 'error'
    ce_premium: Optional[float] = None
    pe_premium: Optional[float] = None
    error_msg: Optional[str] = None
    circuit_opened: bool = False
    stale_detected: bool = False


class HeartbeatHealth:
    """
    Per-session heartbeat telemetry store.

    Thread-safe via a single RLock (writes are fast — just deque appends).
    """

    def __init__(self, session_id: str, base_interval: float):
        self._sid = session_id
        self._base_interval = base_interval      # seconds
        self._lock = threading.RLock()

        # Rolling records
        self._latencies: Deque[float] = deque(maxlen=LATENCY_WINDOW)
        self._records:   Deque[BeatRecord] = deque(maxlen=max(LATENCY_WINDOW, MISS_WINDOW))

        # Absolute counters (never reset)
        self.total_beats:        int = 0
        self.total_ok_beats:     int = 0
        self.total_partial_beats: int = 0
        self.total_miss_beats:   int = 0
        self.total_error_beats:  int = 0

        # Consecutive tracking (reset on success)
        self.consecutive_failures: int = 0
        self.consecutive_ok:       int = 0

        # Stale-price tracking per side
        self._last_ce_price: Optional[float] = None
        self._last_pe_price: Optional[float] = None
        self._ce_unchanged_count: int = 0
        self._pe_unchanged_count: int = 0
        self.stale_ce_detected:   bool = False
        self.stale_pe_detected:   bool = False

        # Session wall time
        self.started_at: float = time.monotonic()
        self.last_beat_at: Optional[float] = None
        self.last_ok_beat_at: Optional[float] = None

    # ------------------------------------------------------------------
    # Public API — called by MMMMonitor
    # ------------------------------------------------------------------

    def record_beat(
        self,
        outcome: str,            # 'ok' | 'partial' | 'miss' | 'error'
        latency_ms: float,
        ce_premium: Optional[float] = None,
        pe_premium: Optional[float] = None,
        error_msg: Optional[str] = None,
        circuit_opened: bool = False,
    ) -> None:
        """Record a single completed heartbeat."""
        stale = self._check_stale(ce_premium, pe_premium)
        rec = BeatRecord(
            timestamp=time.monotonic(),
            latency_ms=latency_ms,
            outcome=outcome,
            ce_premium=ce_premium,
            pe_premium=pe_premium,
            error_msg=error_msg,
            circuit_opened=circuit_opened,
            stale_detected=stale,
        )

        with self._lock:
            self.total_beats += 1
            self._records.append(rec)
            self.last_beat_at = rec.timestamp

            if outcome == 'ok':
                self.total_ok_beats += 1
                self.consecutive_ok += 1
                self.consecutive_failures = 0
                self.last_ok_beat_at = rec.timestamp
                self._latencies.append(latency_ms)

            elif outcome == 'partial':
                self.total_partial_beats += 1
                # partial is half-credit: latency still tracked, failure counter not incremented
                self._latencies.append(latency_ms)
                self.consecutive_failures = 0

            elif outcome == 'miss':
                self.total_miss_beats += 1
                self.consecutive_failures += 1
                self.consecutive_ok = 0

            elif outcome == 'error':
                self.total_error_beats += 1
                self.consecutive_failures += 1
                self.consecutive_ok = 0

        if rec.stale_detected:
            log.warning(
                f"[{self._sid}] ⚠️ STALE PRICE DETECTED: "
                f"CE={'unchanged' if self.stale_ce_detected else 'ok'}, "
                f"PE={'unchanged' if self.stale_pe_detected else 'ok'} "
                f"for {MAX_STALE_CONSECUTIVE}+ consecutive beats"
            )

    def record_miss(self) -> None:
        """Record a missed beat (thread woke but chose to skip)."""
        self.record_beat('miss', latency_ms=0.0)

    # ------------------------------------------------------------------
    # Stale price detection
    # ------------------------------------------------------------------

    def _check_stale(
        self,
        ce_now: Optional[float],
        pe_now: Optional[float],
    ) -> bool:
        """
        Compare new prices against the last recorded price.

        A price is considered "stale" if it's unchanged over
        MAX_STALE_CONSECUTIVE consecutive beats. This catches the
        exchange serving cached/frozen data.
        """
        stale = False

        if ce_now is not None:
            if ce_now == self._last_ce_price:
                self._ce_unchanged_count += 1
            else:
                self._ce_unchanged_count = 0
                self._last_ce_price = ce_now

            if self._ce_unchanged_count >= MAX_STALE_CONSECUTIVE:
                self.stale_ce_detected = True
                stale = True
            else:
                self.stale_ce_detected = False

        if pe_now is not None:
            if pe_now == self._last_pe_price:
                self._pe_unchanged_count += 1
            else:
                self._pe_unchanged_count = 0
                self._last_pe_price = pe_now

            if self._pe_unchanged_count >= MAX_STALE_CONSECUTIVE:
                self.stale_pe_detected = True
                stale = True
            else:
                self.stale_pe_detected = False

        return stale

    # ------------------------------------------------------------------
    # Computed metrics (thread-safe reads)
    # ------------------------------------------------------------------

    @property
    def latency_p50(self) -> Optional[float]:
        with self._lock:
            lats = list(self._latencies)
        if not lats:
            return None
        return statistics.median(lats)

    @property
    def latency_p95(self) -> Optional[float]:
        with self._lock:
            lats = list(self._latencies)
        if len(lats) < 5:  # need at least 5 samples for a meaningful p95
            return None
        lats.sort()
        idx = int(len(lats) * 0.95)
        return lats[min(idx, len(lats) - 1)]

    @property
    def latency_max(self) -> Optional[float]:
        with self._lock:
            lats = list(self._latencies)
        return max(lats) if lats else None

    @property
    def miss_rate_pct(self) -> float:
        """Miss rate over the last MISS_WINDOW beats."""
        with self._lock:
            recent = list(self._records)[-MISS_WINDOW:]
        if not recent:
            return 0.0
        misses = sum(1 for r in recent if r.outcome in ('miss', 'error'))
        return (misses / len(recent)) * 100.0

    @property
    def failure_count_recent(self) -> int:
        """Error/miss count over last FAILURE_WINDOW beats."""
        with self._lock:
            recent = list(self._records)[-FAILURE_WINDOW:]
        return sum(1 for r in recent if r.outcome in ('error', 'miss'))

    @property
    def seconds_since_last_ok(self) -> Optional[float]:
        if self.last_ok_beat_at is None:
            return None
        return time.monotonic() - self.last_ok_beat_at

    @property
    def seconds_since_last_beat(self) -> Optional[float]:
        if self.last_beat_at is None:
            return None
        return time.monotonic() - self.last_beat_at

    # ------------------------------------------------------------------
    # Health Grade Computation
    # ------------------------------------------------------------------

    def grade(self) -> str:
        """
        Compute A–F health grade from rolling statistics.

        Returns:
            'A' | 'B' | 'C' | 'D' | 'F'
        """
        if self.total_beats < 3:
            return 'A'  # not enough data — assume healthy at start

        p95 = self.latency_p95
        miss_pct = self.miss_rate_pct
        failures_recent = self.failure_count_recent
        interval_ms = self._base_interval * 1000

        # Use p50 as fallback if not enough samples for p95
        if p95 is None:
            p95 = self.latency_p50 or 0.0

        stale = self.stale_ce_detected or self.stale_pe_detected

        # --- Grade F: catastrophic
        if (
            failures_recent > 5
            or miss_pct > 20
            or p95 > interval_ms * 2
            or stale
            or self.consecutive_failures >= 5
        ):
            return 'F'

        # --- Grade D: poor
        if (
            failures_recent > 3
            or miss_pct > 10
            or p95 > interval_ms * 1.5
        ):
            return 'D'

        # --- Grade C: marginal
        if (
            failures_recent > 1
            or miss_pct > 5
            or p95 > interval_ms
        ):
            return 'C'

        # --- Grade B: good
        if (
            failures_recent > 0
            or miss_pct > 2
            or p95 > interval_ms * 0.8
        ):
            return 'B'

        # --- Grade A: excellent
        return 'A'

    # ------------------------------------------------------------------
    # Summary dict for API / WebSocket
    # ------------------------------------------------------------------

    def summary(self) -> Dict:
        """Return a JSON-serialisable health snapshot."""
        grade = self.grade()
        p50 = self.latency_p50
        p95 = self.latency_p95
        lat_max = self.latency_max

        with self._lock:
            recent_outcomes = [r.outcome for r in list(self._records)[-20:]]

        return {
            'grade': grade,
            'grade_color': {
                'A': 'success', 'B': 'success', 'C': 'warning',
                'D': 'error', 'F': 'error',
            }.get(grade, 'default'),
            'total_beats': self.total_beats,
            'ok_beats': self.total_ok_beats,
            'partial_beats': self.total_partial_beats,
            'miss_beats': self.total_miss_beats,
            'error_beats': self.total_error_beats,
            'consecutive_failures': self.consecutive_failures,
            'consecutive_ok': self.consecutive_ok,
            'latency_p50_ms': round(p50, 1) if p50 is not None else None,
            'latency_p95_ms': round(p95, 1) if p95 is not None else None,
            'latency_max_ms': round(lat_max, 1) if lat_max is not None else None,
            'miss_rate_pct': round(self.miss_rate_pct, 1),
            'stale_ce': self.stale_ce_detected,
            'stale_pe': self.stale_pe_detected,
            'seconds_since_last_ok': round(self.seconds_since_last_ok, 1)
                                     if self.seconds_since_last_ok is not None else None,
            'seconds_since_last_beat': round(self.seconds_since_last_beat, 1)
                                       if self.seconds_since_last_beat is not None else None,
            'uptime_seconds': round(time.monotonic() - self.started_at, 0),
            'recent_outcomes': recent_outcomes,    # last 20 for sparkline
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
