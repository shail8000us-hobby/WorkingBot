"""
MMMX Circuit Breaker — 3-State Fault Isolator

States: CLOSED → HALF_OPEN → OPEN
  CLOSED:    Normal operation. N consecutive failures → HALF_OPEN.
  HALF_OPEN: One probe request allowed.
               Success → CLOSED. Failure → OPEN.
  OPEN:      All requests blocked. After 5s cooldown → HALF_OPEN for probe.

Per-session state (dict keyed by session_id). Thread-safe with a lock.

Spec: MMMX_IMPLEMENTATION_PLAN.md Section 4 Phase 2.
"""

import threading
import time
from typing import Dict

from .mmmx_constants import CBState

# Number of consecutive failures to trip CLOSED → HALF_OPEN
_FAILURE_THRESHOLD: int = 3
# Seconds to wait in OPEN state before allowing a probe
_OPEN_COOLDOWN_SECS: float = 5.0


class _CircuitState:
    __slots__ = ('state', 'consecutive_failures', 'opened_at')

    def __init__(self) -> None:
        self.state: str = CBState.CLOSED
        self.consecutive_failures: int = 0
        self.opened_at: float = 0.0


# Per-session state store
_states: Dict[str, _CircuitState] = {}
_lock = threading.Lock()


def _get_or_create(session_id: str) -> _CircuitState:
    """Return existing state or create a fresh CLOSED one. Called under _lock."""
    if session_id not in _states:
        _states[session_id] = _CircuitState()
    return _states[session_id]


def record_success(session_id: str) -> None:
    """Record a successful operation.  HALF_OPEN or CLOSED → CLOSED, resets counter."""
    with _lock:
        s = _get_or_create(session_id)
        s.consecutive_failures = 0
        s.state = CBState.CLOSED


def record_failure(session_id: str) -> None:
    """
    Record a failed operation.

    Transitions:
      CLOSED    + Nth failure → HALF_OPEN
      HALF_OPEN + failure     → OPEN (latches, starts cooldown clock)
      OPEN                    → stays OPEN (counters irrelevant)
    """
    with _lock:
        s = _get_or_create(session_id)
        s.consecutive_failures += 1

        if s.state == CBState.CLOSED:
            if s.consecutive_failures >= _FAILURE_THRESHOLD:
                s.state = CBState.HALF_OPEN
        elif s.state == CBState.HALF_OPEN:
            # Probe failed → fully open
            s.state = CBState.OPEN
            s.opened_at = time.time()
        # If already OPEN, no state change needed


def get_state(session_id: str) -> str:
    """
    Return the current state for session_id.

    Side-effect: if OPEN and cooldown has elapsed, transitions to HALF_OPEN
    so the next allow_request() can probe.
    """
    with _lock:
        s = _get_or_create(session_id)
        if s.state == CBState.OPEN:
            if time.time() - s.opened_at >= _OPEN_COOLDOWN_SECS:
                s.state = CBState.HALF_OPEN
        return s.state


def allow_request(session_id: str) -> bool:
    """
    Returns True if a request should be allowed for this session.

    CLOSED    → True  (normal operation)
    HALF_OPEN → True  (one probe request let through)
    OPEN      → False (all blocked until cooldown expires)
    """
    state = get_state(session_id)  # also handles OPEN→HALF_OPEN transition
    return state in (CBState.CLOSED, CBState.HALF_OPEN)


def reset(session_id: str) -> None:
    """Hard reset — returns session to CLOSED state. Useful for tests / manual recovery."""
    with _lock:
        _states.pop(session_id, None)
