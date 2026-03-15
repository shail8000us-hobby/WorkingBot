"""
MMM Guardian — Heartbeat-Level Strategy Integrity Monitor

Prevents cascading failures by enforcing invariants that no single mechanism
can violate, even when mechanisms interact unexpectedly.

Four invariant checks:
  G1. Hedge Integrity:    Block any close that wipes one side to 0 while other has lots
  G2. Lot Velocity:       Max lots bought back per single heartbeat (all mechanisms)
  G3. Side Balance:       Detect one side going from many lots to 0 in a single beat
  G4. Beat Duration:      Enforce wall-clock deadline on heartbeat execution

The guardian is NOT a per-order validator (observer does that). It checks the
AGGREGATE effect of each heartbeat — total lots closed across close_at_5,
shift_recycle, harvest, wind_down, and any future close mechanism combined.

Architecture: One MMMGuardian instance per session, stored in a module-level
registry keyed by session_id. The monitor creates it; close_position() and
other standalone functions look it up via get_guardian(session_id).

Created: March 2026 — response to March 12 proactive-shift cascade incident.
Rewired: March 2026 — fixed broken singleton wiring (G2/G3 were dead code).
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

log = logging.getLogger('mmm_guardian')

# =========================================================================
# Per-session guardian registry
# =========================================================================

_guardians: Dict[str, 'MMMGuardian'] = {}
_guardians_lock = threading.Lock()


def get_guardian(session_id: str) -> Optional['MMMGuardian']:
    """Look up the guardian for a session. Returns None if not registered."""
    with _guardians_lock:
        return _guardians.get(session_id)


def register_guardian(session_id: str, guardian: 'MMMGuardian') -> None:
    """Register a guardian instance for a session (called by monitor __init__)."""
    with _guardians_lock:
        _guardians[session_id] = guardian
    log.debug(f"[{session_id}] Guardian registered")


def deregister_guardian(session_id: str) -> None:
    """Remove a guardian from the registry (called on session stop)."""
    with _guardians_lock:
        _guardians.pop(session_id, None)
    log.debug(f"[{session_id}] Guardian deregistered")


class MMMGuardian:
    """
    Called synchronously within the heartbeat loop.
    No separate thread. No exchange calls. Read-only checks + PAUSE action.

    One instance per session. Retrieved via get_guardian(session_id).
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        # Per-beat counter: tracks lots closed across ALL mechanisms this beat
        self._beat_closed_lots: Dict[str, int] = {'ce': 0, 'pe': 0}

    # =========================================================================
    # Pre-beat snapshot
    # =========================================================================

    def pre_beat_snapshot(self, session: Dict) -> Dict:
        """Capture state BEFORE heartbeat runs. Called at start of _beat()."""
        self._beat_closed_lots = {'ce': 0, 'pe': 0}
        return {
            'ce_total_lots': session.get('ce', {}).get('total_lots', 0),
            'pe_total_lots': session.get('pe', {}).get('total_lots', 0),
            'ce_active_lots': session.get('ce', {}).get('active_lots', 0),
            'pe_active_lots': session.get('pe', {}).get('active_lots', 0),
            'beat_start': time.monotonic(),
        }

    # =========================================================================
    # G1: Hedge Integrity Gate (pre-close check)
    # =========================================================================

    def check_close_allowed(
        self,
        session: Dict,
        side: str,
        lots: int,
        mechanism: str = 'close_at_5',
        both_sides_closing: bool = False,
    ) -> Tuple[bool, str]:
        """
        Check if closing `lots` on `side` would violate hedge integrity.

        Returns:
            (allowed, reason) — reason is empty string if allowed.
        """
        params = session.get('params', {})
        if not params.get('guardian_enabled', True):
            return True, ''

        # Emergency, both-sides-closing, and close-at-5 are always allowed.
        # close_at_5 buys back short options — it reduces risk unconditionally.
        # No velocity or hedge-integrity guard should block a buyback at threshold.
        if both_sides_closing or mechanism in ('emergency', 'both_sides_close', 'close_at_5'):
            return True, ''

        sid = session.get('session_id', '?')

        # G2 mid-beat check: block if aggregate closes already exceeded cap
        velocity_violation = self.check_beat_velocity(session)
        if velocity_violation:
            log.warning(f"[{sid}] {velocity_violation} [mechanism={mechanism}]")
            return False, velocity_violation

        # G1: hedge integrity
        side_state = session.get(side, {})
        side_total = side_state.get('total_lots', 0)
        remaining = side_total - lots

        other_side = 'pe' if side == 'ce' else 'ce'
        other_total = session.get(other_side, {}).get('total_lots', 0)

        if remaining <= 0 and other_total > 0:
            reason = (
                f'Guardian G1: closing {lots} {side.upper()} would '
                f'reduce to {remaining} lots while {other_side.upper()} '
                f'has {other_total} lots — one-sided exposure blocked'
            )
            log.warning(f"[{sid}] {reason}")
            return False, reason

        return True, ''

    # =========================================================================
    # G2: Per-Beat Lot Velocity
    # =========================================================================

    def record_close(self, side: str, lots: int) -> None:
        """Called after each successful close within the current heartbeat."""
        self._beat_closed_lots[side] = self._beat_closed_lots.get(side, 0) + lots

    def check_beat_velocity(self, session: Dict) -> Optional[str]:
        """
        Check if total lots closed this heartbeat exceeds the per-beat cap.
        Called mid-heartbeat, before placing the next close order.

        Returns:
            Violation reason string, or None if OK.
        """
        params = session.get('params', {})
        if not params.get('guardian_enabled', True):
            return None

        max_per_beat = params.get('guardian_max_close_per_beat', 50)
        total_closed = sum(self._beat_closed_lots.values())

        if total_closed >= max_per_beat:
            return (
                f'Guardian G2: {total_closed} lots closed this heartbeat '
                f'(limit {max_per_beat}) — deferring remaining closes to next beat'
            )
        return None

    # =========================================================================
    # G3: Side Balance Integrity (post-beat check)
    # =========================================================================

    def _check_side_balance(
        self, session: Dict, snapshot: Dict,
    ) -> Optional[str]:
        """Detect one side going from many lots to 0 in a single heartbeat."""
        params = session.get('params', {})
        floor = params.get('guardian_side_wipeout_floor', 10)

        for side in ('ce', 'pe'):
            before = snapshot.get(f'{side}_total_lots', 0)
            after = session.get(side, {}).get('total_lots', 0)
            other = 'pe' if side == 'ce' else 'ce'
            other_now = session.get(other, {}).get('total_lots', 0)

            if before > floor and after <= 0 and other_now > 0:
                return (
                    f'Guardian G3: {side.upper()} went from {before} to '
                    f'{after} lots in single heartbeat while {other.upper()} '
                    f'has {other_now} lots — side wipeout detected'
                )
        return None

    # =========================================================================
    # G4: Beat Duration Guard
    # =========================================================================

    def get_beat_deadline(self, session: Dict, beat_start: float) -> float:
        """Return absolute monotonic deadline for this heartbeat."""
        params = session.get('params', {})
        max_sec = params.get('guardian_max_beat_sec', 120)
        return beat_start + max_sec

    def is_deadline_exceeded(self, deadline: float) -> bool:
        """Check if the heartbeat has exceeded its wall-clock deadline."""
        return time.monotonic() > deadline

    # =========================================================================
    # Post-beat validation
    # =========================================================================

    def post_beat_check(
        self, session: Dict, snapshot: Dict,
    ) -> List[str]:
        """
        Run all post-beat invariant checks. Returns list of violation strings.
        Empty list = all OK.
        """
        params = session.get('params', {})
        if not params.get('guardian_enabled', True):
            return []

        violations = []

        # G2: Aggregate velocity — WARNING only, not a hard invariant.
        # The mid-beat check in check_close_allowed() is the real gate.
        # Post-beat overshoot is normal boundary behavior (e.g. 49 closed,
        # then a 5-lot close is allowed because 49 < 50, total becomes 54).
        # Logging for audit — NOT added to violations (would cause PAUSE).
        max_per_beat = params.get('guardian_max_close_per_beat', 50)
        total_closed = sum(self._beat_closed_lots.values())
        if total_closed > max_per_beat:
            sid = session.get('session_id', '?')
            log.warning(
                f'[{sid}] Guardian G2 post-beat: {total_closed} lots closed '
                f'this heartbeat (soft limit {max_per_beat}) — logged for audit'
            )

        # G3: Side balance — HARD invariant. If one side goes from many
        # lots to 0 in a single beat, something catastrophic happened.
        balance_issue = self._check_side_balance(session, snapshot)
        if balance_issue:
            violations.append(balance_issue)

        return violations

    def handle_violations(
        self, monitor, violations: List[str],
    ) -> None:
        """Pause the monitor and emit alerts for each violation."""
        sid = getattr(monitor, 'session_id', '?')
        for v in violations:
            log.critical(f"[{sid}] GUARDIAN VIOLATION: {v}")

        try:
            from .mmm_activity import log_activity
            from .mmm_websocket import emit_safety
            for v in violations:
                log_activity(
                    'guardian_violation', f'🛡️ {v}',
                    sid, 'error', {'violation': v},
                )
                emit_safety(sid, 'guardian', 'critical', v)
        except Exception as e:
            log.warning(f"[{sid}] Guardian alert emit failed: {e}")

        try:
            monitor.pause(
                f'Guardian violations: {len(violations)} invariant(s) breached'
            )
        except Exception as e:
            log.error(f"[{sid}] Guardian pause failed: {e}")
