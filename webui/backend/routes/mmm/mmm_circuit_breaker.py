"""
MMM Circuit Breaker — Exchange API Fault Isolation

Implements a standard three-state circuit breaker for the exchange API layer
used by the heartbeat loop:

  CLOSED  (nominal)  → requests pass through
  OPEN    (tripped)  → requests fast-fail immediately; no exchange calls
  HALF_OPEN (probe)  → one trial request allowed; success → CLOSED, fail → OPEN

State transitions
-----------------
  CLOSED  → OPEN      : failure_count reaches FAILURE_THRESHOLD
  OPEN    → HALF_OPEN : after RESET_TIMEOUT seconds
  HALF_OPEN → CLOSED  : trial request succeeds
  HALF_OPEN → OPEN    : trial request fails

Graduated response in the heartbeat loop
-----------------------------------------
  CLOSED,  any failures      : heartbeat runs normally (may be partial-beat)
  OPEN (backoff 1-3)         : heartbeat skips trigger/adjustment, runs close-at-5+safety
                               using cached prices only (PARTIAL BEAT)
  OPEN (backoff 4+)          : heartbeat skips entirely → monitor healthy, algo paused
  HALF_OPEN probe fails      : back to OPEN; consecutive_opens triggers PAUSE

Unlike the old `error_count >= 5 → hard stop`, the circuit breaker NEVER
terminates the session. It isolates the fault, waits for recovery, and
self-heals.

Created: February 18, 2026
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Optional

log = logging.getLogger('mmm_circuit_breaker')

# Number of consecutive failures that trips the breaker
FAILURE_THRESHOLD = 3

# Seconds to wait in OPEN state before probing
RESET_TIMEOUT = 30.0

# After this many successive OPEN→HALF_OPEN probe failures, emit a safety event
CONSECUTIVE_OPEN_ALERT_THRESHOLD = 3


class CircuitState(str, Enum):
    CLOSED    = 'CLOSED'
    OPEN      = 'OPEN'
    HALF_OPEN = 'HALF_OPEN'


class CircuitBreaker:
    """
    Thread-safe circuit breaker for one session's exchange API calls.

    Usage in MMMMonitor::
        self._circuit = CircuitBreaker(session_id)

        # Before any exchange call:
        if not self._circuit.allow_request():
            # breaker is OPEN — use cached data / partial-beat
            ...

        try:
            result = await exchange_call(...)
            self._circuit.record_success()
        except Exception as e:
            self._circuit.record_failure(str(e))
    """

    def __init__(self, session_id: str):
        self._sid = session_id
        self._lock = threading.RLock()

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._consecutive_successes: int = 0
        self._last_open_at: Optional[float] = None
        self._consecutive_opens: int = 0     # OPEN episodes without full recovery

        # Backoff depth — increases each time breaker re-opens
        self._open_depth: int = 0

        # Stats
        self.total_trips: int = 0
        self.total_probes: int = 0
        self.total_recoveries: int = 0
        self.last_error: Optional[str] = None
        self.last_error_time: Optional[float] = None
        self.last_recovery_time: Optional[float] = None

    # ------------------------------------------------------------------
    # Core State Machine
    # ------------------------------------------------------------------

    def allow_request(self) -> bool:
        """
        Return True if an exchange request should be attempted.

        CLOSED    → True  (always allow)
        OPEN      → False (unless reset timeout elapsed → go HALF_OPEN → True once)
        HALF_OPEN → True  (exactly one probe allowed, further calls → False)
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - (self._last_open_at or 0)
                # Exponential backoff on reset timeout based on open depth
                timeout = min(RESET_TIMEOUT * (2 ** (self._open_depth - 1)), 300.0)
                if elapsed >= timeout:
                    log.info(
                        f"[{self._sid}] Circuit → HALF_OPEN "
                        f"(was OPEN {elapsed:.0f}s, depth={self._open_depth})"
                    )
                    self._state = CircuitState.HALF_OPEN
                    self.total_probes += 1
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                return True

        return False  # unreachable

    def record_success(self) -> None:
        """Call after a successful exchange response."""
        with self._lock:
            self._failure_count = 0
            self._consecutive_successes += 1

            if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                log.info(
                    f"[{self._sid}] Circuit → CLOSED after successful probe "
                    f"(depth was {self._open_depth})"
                )
                self._state = CircuitState.CLOSED
                self._open_depth = 0
                self._consecutive_opens = 0
                self.total_recoveries += 1
                self.last_recovery_time = time.monotonic()

    def record_failure(self, error: str = '') -> None:
        """Call after an exchange call fails."""
        with self._lock:
            self.last_error = error
            self.last_error_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Probe failed — deepen backoff
                self._open_depth += 1
                self._consecutive_opens += 1
                self._trip('probe failed')
                return

            self._failure_count += 1
            self._consecutive_successes = 0

            if (
                self._state == CircuitState.CLOSED
                and self._failure_count >= FAILURE_THRESHOLD
            ):
                self._open_depth = max(1, self._open_depth + 1)
                self._trip('failure threshold reached')

    def _trip(self, reason: str) -> None:
        """Transition to OPEN state. Caller must hold _lock."""
        self._state = CircuitState.OPEN
        self._failure_count = 0
        self._last_open_at = time.monotonic()
        self.total_trips += 1
        log.warning(
            f"[{self._sid}] 🔴 Circuit OPEN — {reason} "
            f"(depth={self._open_depth}, trips={self.total_trips})"
        )

    # ------------------------------------------------------------------
    # State Queries
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_open(self) -> bool:
        return self._state in (CircuitState.OPEN, CircuitState.HALF_OPEN)

    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED

    @property
    def should_alert(self) -> bool:
        """True if circuit has been OPEN too long and needs a safety event."""
        return (
            self._state == CircuitState.OPEN
            and self._consecutive_opens >= CONSECUTIVE_OPEN_ALERT_THRESHOLD
        )

    @property
    def partial_beat_allowed(self) -> bool:
        """
        During an OPEN circuit, whether a partial beat (close-at-5 + safety
        using cached prices) should still run.

        Allows partial execution for the first few OPEN episodes to protect
        existing positions. After deep backoff, skip entirely to save resources.
        """
        return self._open_depth <= 2

    @property
    def open_depth(self) -> int:
        return self._open_depth

    @property
    def reset_timeout(self) -> float:
        """Current reset timeout in seconds (exponential backoff)."""
        return min(RESET_TIMEOUT * (2 ** (self._open_depth - 1)), 300.0)

    @property
    def seconds_until_probe(self) -> Optional[float]:
        """Seconds remaining before next probe attempt (only when OPEN)."""
        if self._state != CircuitState.OPEN or self._last_open_at is None:
            return None
        timeout = self.reset_timeout
        elapsed = time.monotonic() - self._last_open_at
        return max(0.0, timeout - elapsed)

    # ------------------------------------------------------------------
    # Summary for API / WebSocket
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        return {
            'state': self._state.value,
            'is_open': self.is_open,
            'open_depth': self._open_depth,
            'consecutive_failures': self._failure_count,
            'consecutive_opens': self._consecutive_opens,
            'total_trips': self.total_trips,
            'total_recoveries': self.total_recoveries,
            'reset_timeout_s': self.reset_timeout,
            'seconds_until_probe': self.seconds_until_probe,
            'last_error': self.last_error,
            'should_alert': self.should_alert,
        }
