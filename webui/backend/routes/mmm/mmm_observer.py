"""
MMM Strategy Observer — Money Mind & Method

Intercepts every BUY (close) order and validates it against the current strategy
state BEFORE the order reaches the exchange.

This is NOT a safety feature (those guard SELL orders). It guards the LOGIC
of close orders: are they consistent with the strategy's intent?

Two checks (applied to BUY orders only):
  1. Price Consistency:   Is the current premium appropriate for this mechanism?
  2. Ledger Integrity:    Does the position actually exist in the session ledger?

Strategy continuity (hedge integrity) is now handled by MMMGuardian.
Close velocity is now handled by MMMGuardian per-beat lot velocity.

Usage:
    from .mmm_observer import get_observer

    observer = get_observer()
    result = observer.validate_close(
        session, side='pe', lots=30,
        current_premium=58.0, mechanism='close_at_5',
    )
    if not result['allowed']:
        log.warning(f"Observer blocked close: {result['reason']}")
        return {'success': False, 'error': result['reason'], 'observer_blocked': True}

    # ... place order ...

    # Record the close AFTER a successful fill so velocity tracking stays accurate
    observer.record_close(session_id, side='pe', lots=30)

Created: March 2026
"""

import logging
import threading
from collections import deque
from typing import Dict, Any, Optional
from datetime import datetime, timezone

log = logging.getLogger('mmm_observer')

# Mechanisms where price-consistency check applies (hard block)
_PRICE_CHECK_BLOCK_MECHANISMS = ('close_at_5', 'harvest', 'shift_recycle')

# Mechanisms where velocity block is skipped (emergency closes may be large)
_VELOCITY_EXEMPT_MECHANISMS = ('atm_shield', 'wind_down', 'emergency')

# Velocity thresholds
_VELOCITY_ALERT_LOTS = 60    # Alert: > 60 lots on same side in 60s
_VELOCITY_BLOCK_LOTS = 100   # Block: > 100 lots on same side in 60s
_VELOCITY_WINDOW_SECS = 60   # Rolling window size


class MMMStrategyObserver:
    """
    Strategy Logic Observer — validates every BUY (close) order against the
    current session state before it is submitted to the exchange.

    Thread-safe singleton (see get_observer()).
    Velocity state is stored per (session_id, side) and cleaned up on session stop.
    """

    def __init__(self):
        # Velocity tracking: {(session_id, side): deque of (timestamp, lots)}
        self._velocity: Dict[tuple, deque] = {}
        self._lock = threading.Lock()

    # =========================================================================
    # Public API
    # =========================================================================

    def validate_close(
        self,
        session: Dict,
        side: str,
        lots: int,
        current_premium: float,
        mechanism: str = 'close_at_5',
        entry_premium: Optional[float] = None,
        both_sides_closing: bool = False,
    ) -> Dict[str, Any]:
        """
        Validate a close (BUY) order against strategy logic.

        Args:
            session:           Full session dict (read-only here)
            side:              'ce' or 'pe'
            lots:              Number of lots to close
            current_premium:   Current mark/bid premium of the position
            mechanism:         Why this close is being requested:
                               'close_at_5'  — premium decayed to threshold
                               'harvest'     — frozen position profit harvest (M1)
                               'recycler'    — M2 emergency lot recycling
                               'atm_shield'  — approaching ATM, repositioning
                               'wind_down'   — time/regime based gradual exit
                               'both_sides_close' — clean session exit
                               'emergency'   — any other emergency close
            entry_premium:     Original entry premium (used for harvest check)
            both_sides_closing: True when both sides are being closed together
                               (clean session end — strategy continuity exempt)

        Returns:
            {
              'allowed': bool,
              'reason':  str or None,
              'block_type': str or None,  # 'continuity' | 'price' | 'velocity' | 'ledger'
              'details': dict,
            }
        """
        checks = [
            lambda: self._check_price_consistency(session, side, current_premium, mechanism, entry_premium),
            lambda: self._check_ledger_integrity(session, side, lots),
        ]

        for check in checks:
            result = check()
            if not result['allowed']:
                sid = session.get('session_id', '?')
                log.warning(
                    f"[{sid}] OBSERVER BLOCK [{result['block_type']}]: "
                    f"{lots} {side.upper()} {mechanism} — {result['reason']}"
                )
                return result

        return {'allowed': True, 'reason': None, 'block_type': None, 'details': {}}

    def record_close(self, session_id: str, side: str, lots: int) -> None:
        """
        Record a successfully placed close order in the velocity window.
        Call this AFTER the exchange order is placed (not before).
        """
        key = (session_id, side)
        now = datetime.now(timezone.utc).timestamp()
        with self._lock:
            if key not in self._velocity:
                self._velocity[key] = deque()
            self._velocity[key].append((now, lots))

    def clear_session(self, session_id: str) -> None:
        """Free velocity state for a stopped/completed session."""
        with self._lock:
            for side in ('ce', 'pe'):
                self._velocity.pop((session_id, side), None)

    # =========================================================================
    # CHECK 1 — Price Consistency
    # =========================================================================

    def _check_price_consistency(
        self,
        session: Dict,
        side: str,
        current_premium: float,
        mechanism: str,
        entry_premium: Optional[float],
    ) -> Dict[str, Any]:
        """
        Validate that the current premium is appropriate for the stated mechanism.

        - close_at_5: block if current_premium > close_at_threshold × 2.0
          (2× allows for mark/bid spread and minor slippage — any more is wrong)
        - harvest:    block if current_premium > entry_premium × (1 - profit_pct/100)
          (position hasn't decayed enough for the harvest strategy to apply)
        - All others: warn only via log (no block — emergency closes may be high)
        """
        if current_premium is None or current_premium <= 0:
            return {'allowed': True, 'reason': None, 'block_type': None, 'details': {}}

        params = session.get('params', {})
        sid = session.get('session_id', '?')

        if mechanism == 'close_at_5':
            threshold = params.get('close_at_threshold', 5.0)
            limit = threshold * 2.0
            if current_premium > limit:
                return {
                    'allowed': False,
                    'reason': (
                        f"close_at_5: current premium ${current_premium:.2f} > "
                        f"${limit:.2f} (threshold ${threshold:.2f} × 2.0). "
                        f"Position not yet cheap enough to close via this mechanism."
                    ),
                    'block_type': 'price',
                    'details': {
                        'mechanism': mechanism,
                        'current_premium': current_premium,
                        'close_at_threshold': threshold,
                        'limit': limit,
                        'session_id': sid,
                    },
                }

        elif mechanism == 'harvest':
            if entry_premium and entry_premium > 0:
                profit_pct = params.get('harvest_profit_pct', 70.0)
                # Position is harvest-eligible only when it has decayed by profit_pct
                max_close_premium = entry_premium * (1.0 - profit_pct / 100.0)
                if current_premium > max_close_premium:
                    return {
                        'allowed': False,
                        'reason': (
                            f"harvest: current premium ${current_premium:.2f} > "
                            f"${max_close_premium:.2f} "
                            f"(entry ${entry_premium:.2f} × {(1 - profit_pct/100):.2f}). "
                            f"Position has not decayed {profit_pct:.0f}% from entry."
                        ),
                        'block_type': 'price',
                        'details': {
                            'mechanism': mechanism,
                            'current_premium': current_premium,
                            'entry_premium': entry_premium,
                            'harvest_profit_pct': profit_pct,
                            'max_close_premium': round(max_close_premium, 2),
                            'session_id': sid,
                        },
                    }

        elif mechanism == 'shift_recycle':
            # Shift-recycle should only close positions below premium_floor.
            # Block if premium has risen above the floor since the scan.
            premium_floor = params.get('shift_recycle_premium_floor', 60.0)
            # Allow 1.5× headroom for bid-ask spread and premium movement
            limit = premium_floor * 1.5
            if current_premium > limit:
                return {
                    'allowed': False,
                    'reason': (
                        f"shift_recycle: current premium ${current_premium:.2f} > "
                        f"${limit:.2f} (floor ${premium_floor:.2f} × 1.5). "
                        f"Premium rose since scan — too expensive to recycle."
                    ),
                    'block_type': 'price',
                    'details': {
                        'mechanism': mechanism,
                        'current_premium': current_premium,
                        'shift_recycle_premium_floor': premium_floor,
                        'limit': limit,
                        'session_id': sid,
                    },
                }

        elif mechanism not in _PRICE_CHECK_BLOCK_MECHANISMS:
            # Warn if unexpectedly high, but don't block emergency/shield/wind-down
            threshold = params.get('close_at_threshold', 5.0)
            warn_limit = threshold * 5.0
            if current_premium > warn_limit:
                log.warning(
                    f"[{sid}] OBSERVER PRICE WARN [{mechanism}]: {side.upper()} "
                    f"premium ${current_premium:.2f} >> threshold ${threshold:.2f}. "
                    f"High-premium emergency close — not blocked."
                )

        return {'allowed': True, 'reason': None, 'block_type': None, 'details': {}}

    # =========================================================================
    # CHECK 2 — Ledger Integrity
    # =========================================================================

    def _check_ledger_integrity(
        self,
        session: Dict,
        side: str,
        lots: int,
    ) -> Dict[str, Any]:
        """
        Verify the position being closed actually exists in the session ledger
        with the expected lot count.  Prevents phantom closes.

        We check that the side's total_lots >= lots (i.e. there IS something to close).
        We do NOT require an exact position match here — close_position() already does
        the fine-grained position lookup.  This check catches the case where the ledger
        shows 0 lots but a close is still requested (e.g. stale loop iteration).
        """
        side_total = session.get(side, {}).get('total_lots', 0)

        if side_total <= 0:
            sid = session.get('session_id', '?')
            return {
                'allowed': False,
                'reason': (
                    f"Ledger integrity: {side.upper()} shows {side_total} lots in session "
                    f"but close of {lots} lots requested. Nothing to close."
                ),
                'block_type': 'ledger',
                'details': {
                    'side': side,
                    'side_total': side_total,
                    'lots_requested': lots,
                    'session_id': sid,
                },
            }

        if lots > side_total:
            sid = session.get('session_id', '?')
            return {
                'allowed': False,
                'reason': (
                    f"Ledger integrity: Attempting to close {lots} lots but "
                    f"{side.upper()} only has {side_total} lots in ledger."
                ),
                'block_type': 'ledger',
                'details': {
                    'side': side,
                    'side_total': side_total,
                    'lots_requested': lots,
                    'session_id': sid,
                },
            }

        return {'allowed': True, 'reason': None, 'block_type': None, 'details': {}}


# =============================================================================
# Singleton
# =============================================================================

_observer_instance: Optional[MMMStrategyObserver] = None
_observer_lock = threading.Lock()


def get_observer() -> MMMStrategyObserver:
    """Return the singleton MMMStrategyObserver (created on first call)."""
    global _observer_instance
    if _observer_instance is None:
        with _observer_lock:
            if _observer_instance is None:
                _observer_instance = MMMStrategyObserver()
    return _observer_instance
