"""
mmm_api_budget.py — A11-02 fix: API rate-limit budget tracker.

Shared token-bucket singleton that tracks Delta Exchange API call consumption
across all MMM sessions.  Prevents aggregate multi-session traffic from hitting
the exchange's per-minute rate limit during volatile price moves.

Usage (in mmm_executor.py or any API call site):
    from .mmm_api_budget import api_budget

    if not api_budget.consume(priority='normal'):
        log.warning("Rate budget exhausted — deferring non-critical API call")
        return None  # caller decides how to handle

    # ... make the API call ...

Priority levels:
    'critical' — order placement/cancellation; always allowed, counts against budget
    'normal'   — premium fetch, fill polling; blocked when budget is exhausted
"""
import threading
import time
import logging

from webui.backend.sealed import sealed

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Delta Exchange published rate limits (verify against current exchange docs)
# ---------------------------------------------------------------------------
_CALLS_PER_MINUTE = 60   # conservative — actual limit may be higher per endpoint

# Warn when budget drops below this fraction of the per-minute allowance
_WARN_THRESHOLD_PCT = 0.20


class APIRateBudget:
    """
    Token-bucket rate limiter.  Thread-safe, shared across all MMM sessions.

    One token = one API call.  Tokens refill linearly at CALLS_PER_MINUTE / 60
    per second.  The bucket is capped at CALLS_PER_MINUTE tokens.

    critical vs normal priority:
    - 'critical': order placement / cancellation — always consumes a token but
      is never blocked (we must not refuse to place hedges due to rate limits).
    - 'normal': premium fetch, fill polling — blocked when budget < count.
    """

    def __init__(self, calls_per_minute: int = _CALLS_PER_MINUTE):
        self._calls_per_minute = calls_per_minute
        self._tokens: float = float(calls_per_minute)
        self._last_refill: float = time.monotonic()
        self._lock = threading.Lock()
        self._total_consumed: int = 0
        self._total_blocked: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @sealed
    def consume(self, count: int = 1, priority: str = 'normal') -> bool:
        """
        Attempt to consume `count` tokens.

        Args:
            count:    Number of API calls to reserve (default 1).
            priority: 'critical' (order ops) or 'normal' (data fetches).

        Returns:
            True  — tokens consumed; caller may proceed with the API call.
            False — budget exhausted; caller should defer or skip (normal only).
                    Critical calls always return True.
        """
        with self._lock:
            self._refill()

            if priority == 'critical':
                # Always allow; consume but never block.
                self._tokens = max(0.0, self._tokens - count)
                self._total_consumed += count
                if self._tokens < self._calls_per_minute * _WARN_THRESHOLD_PCT:
                    log.warning(
                        "APIRateBudget: critical call consumed token but budget low "
                        f"({self._tokens:.1f}/{self._calls_per_minute} remaining). "
                        "Consider reducing non-critical polling frequency."
                    )
                return True

            # Normal priority: block if insufficient tokens.
            if self._tokens >= count:
                self._tokens -= count
                self._total_consumed += count
                return True

            self._total_blocked += count
            log.debug(
                f"APIRateBudget: normal call blocked "
                f"({self._tokens:.1f} tokens, need {count})"
            )
            return False

    def remaining(self) -> float:
        """Return current token count (approximate — not locked)."""
        return self._tokens

    def stats(self) -> dict:
        """Return consumption statistics for monitoring / Telegram alerts."""
        with self._lock:
            self._refill()
            return {
                'remaining': round(self._tokens, 1),
                'capacity': self._calls_per_minute,
                'total_consumed': self._total_consumed,
                'total_blocked': self._total_blocked,
                'utilization_pct': round(
                    100.0 * (1.0 - self._tokens / max(self._calls_per_minute, 1)), 1
                ),
            }

    def reset(self) -> None:
        """Reset bucket to full capacity (used in tests and on session start)."""
        with self._lock:
            self._tokens = float(self._calls_per_minute)
            self._last_refill = time.monotonic()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        """Refill tokens based on elapsed wall-clock time. Must be called under lock."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            refill_amount = elapsed * self._calls_per_minute / 60.0
            self._tokens = min(
                float(self._calls_per_minute),
                self._tokens + refill_amount,
            )
            self._last_refill = now


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly
# ---------------------------------------------------------------------------
api_budget = APIRateBudget(calls_per_minute=_CALLS_PER_MINUTE)
