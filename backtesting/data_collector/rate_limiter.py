"""
Rate Limiter
=============
Token-bucket rate limiter to respect Delta Exchange India API limits.

Delta India public REST API: ~30 req/sec.
We cap at 20 req/sec to stay well within limits.
"""

import time
import threading
import logging

log = logging.getLogger("backtesting.rate_limiter")


class TokenBucketRateLimiter:
    """
    Thread-safe token bucket rate limiter.

    Usage:
        limiter = TokenBucketRateLimiter(rate=20)   # 20 req/sec
        for symbol in symbols:
            limiter.wait()   # blocks until a token is available
            client.get_candles(symbol, ...)
    """

    def __init__(self, rate: float = 20.0, burst: float = 30.0):
        """
        Args:
            rate:  Steady-state requests per second
            burst: Maximum burst tokens (bucket capacity)
        """
        self.rate   = rate
        self.burst  = burst
        self._tokens = burst
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self):
        """Add tokens proportional to elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed * self.rate
        self._tokens = min(self.burst, self._tokens + new_tokens)
        self._last_refill = now

    def wait(self, tokens: float = 1.0):
        """
        Block until the requested number of tokens are available, then consume them.

        Args:
            tokens: Number of tokens to consume (default: 1 per request)
        """
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                # Calculate wait time needed
                deficit = tokens - self._tokens
                wait_time = deficit / self.rate

            time.sleep(wait_time)

    def available(self) -> float:
        """Return the current number of available tokens (thread-safe snapshot)."""
        with self._lock:
            self._refill()
            return self._tokens


# ── Singleton instance ────────────────────────────────────────────────────────
# Shared across all collectors to enforce the global rate limit
_default_limiter: TokenBucketRateLimiter = None


def get_default_limiter(rate: float = 20.0) -> TokenBucketRateLimiter:
    """
    Get or create the module-level default rate limiter.

    Call this from each collector to share a single limiter instance.
    """
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = TokenBucketRateLimiter(rate=rate)
        log.info(f"Created default rate limiter: {rate} req/sec")
    return _default_limiter


def reset_limiter():
    """Reset the singleton (used in tests)."""
    global _default_limiter
    _default_limiter = None
