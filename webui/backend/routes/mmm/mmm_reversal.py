"""
MMM Reversal Detection — Money Mind & Method

Detects direction changes and handles first-reversal P&L calculation.
Also implements cooldown after reversal.

Maps to MONEY_POWER_CALCULATION_LOGIC.md:
  §9: Reversal Logic
  §5.2 Case B: First-reversal formula
  §14.3: Cooldown after reversal

Created: February 15, 2026
Updated: February 16, 2026 — Fix infinite reversal detection loop
"""

import logging
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

from .mmm_trigger import update_trigger_snapshots

log = logging.getLogger('mmm_reversal')


def detect_reversal(session: Dict, current_aggressor: str) -> bool:
    """
    §9: Detect if the market has reversed direction.

    reversal = (last_aggressor == "CE" AND PE is now aggressor)
            OR (last_aggressor == "PE" AND CE is now aggressor)

    Args:
        session: Full session dict
        current_aggressor: 'ce' or 'pe' — who triggered now

    Returns:
        True if this is a reversal
    """
    last = session.get('last_aggressor', 'NONE')

    # First-ever adjustment is NOT a reversal
    # Robust v2 Fix #10: Use .upper() to handle case-insensitive comparison
    # Prevents false positive reversal if last_aggressor stored as lowercase 'none'
    if last is None or (isinstance(last, str) and last.upper() == 'NONE'):
        return False

    # Same aggressor = continuation, not reversal
    if last.lower() == current_aggressor.lower():
        return False

    # Different aggressor = reversal
    log.info(
        f"Reversal detected: last_aggressor={last}, "
        f"current={current_aggressor.upper()}"
    )
    return True


def is_cooldown_active(session: Dict) -> bool:
    """
    §14.3: Check if we're in a cooldown period after reversal.

    Returns:
        True if cooldown is active and we should skip this interval
    """
    if not session.get('cooldown_active', False):
        return False

    cooldown_until = session.get('cooldown_until')
    if cooldown_until is None:
        return False

    try:
        # Fix #14: parse stored timestamp as timezone-aware UTC (handles both
        # naive strings from old sessions and aware strings from new ones).
        until = datetime.fromisoformat(cooldown_until)
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        if now_utc < until:
            log.info(
                f"Cooldown active until {cooldown_until}, "
                f"skipping adjustment"
            )
            return True
        else:
            # Cooldown expired
            session['cooldown_active'] = False
            session['cooldown_until'] = None
            return False
    except (ValueError, TypeError):
        session['cooldown_active'] = False
        return False


def activate_cooldown(session: Dict):
    """
    §14.3: Set a cooldown for one interval after reversal detection.

    Only activates on the FIRST reversal detection of a new direction.
    If cooldown is already active or was recently used for this same
    reversal direction, do NOT re-activate (prevents cooldown spam).
    """
    # Prevent re-activation if already in cooldown
    if session.get('cooldown_active', False):
        log.debug("Cooldown already active, not re-activating")
        return

    params = session.get('params', {})
    interval = params.get('adjustment_interval', 300)

    session['cooldown_active'] = True
    # Fix #14: use timezone-aware UTC
    session['cooldown_until'] = (
        datetime.now(timezone.utc) + timedelta(seconds=interval)
    ).isoformat()

    log.info(f"Cooldown activated for {interval}s")


def should_skip_reversal_adjustment(
    session: Dict,
    adjustment_pnl: float,
) -> Tuple[bool, str]:
    """
    §9: If adjustment positions are STILL NET POSITIVE, skip the adjustment.

    Args:
        session: Full session dict
        adjustment_pnl: Computed P&L of adjustment positions on aggressor side

    Returns:
        (should_skip, reason)
    """
    if adjustment_pnl >= 0:
        return True, (
            f"Reversal detected but adjustments still profitable "
            f"(P&L: ${adjustment_pnl:.2f}). Skipping."
        )
    return False, ''


def record_reversal(session: Dict, from_side: str, to_side: str):
    """
    Record a reversal event in the session history.

    Only records once per actual direction change. If the last recorded
    reversal was in the same direction (from→to), don't duplicate.
    """
    history = session.get('reversal_history', [])

    # Prevent duplicate reversal records for the same direction change
    if history:
        last_entry = history[-1]
        if (last_entry.get('from') == from_side.upper()
                and last_entry.get('to') == to_side.upper()
                and last_entry.get('adjustment_count_at') == session.get('adjustment_count', 0)):
            log.debug(
                f"Reversal {from_side}→{to_side} already recorded at "
                f"adj_count={session.get('adjustment_count', 0)}, skipping duplicate"
            )
            return

    session['reversal_count'] = session.get('reversal_count', 0) + 1
    session.setdefault('reversal_history', []).append({
        'from': from_side.upper(),
        'to': to_side.upper(),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'adjustment_count_at': session.get('adjustment_count', 0),
    })


def handle_reversal_skip_transition(
    session: Dict,
    aggressor: str,
    ce_now: float,
    pe_now: float,
    fetch_premium_fn=None,
):
    """
    §9 / §6.2: After a reversal is detected but SKIPPED (adj P&L ≥ 0),
    transition to standard mode for subsequent intervals.

    Per §9: "After the first reversal adjustment is done: triggers updated,
    last_aggressor set to new direction, all subsequent adjustments use
    standard formula."

    When the reversal is SKIPPED (profitable), the same transition applies:
    - The market HAS reversed direction
    - Adjustment positions are in profit (no hedge needed yet)
    - Set last_aggressor to new direction so next interval uses standard formula
    - Update triggers to current prices (§6.2) so the trigger baseline reflects
      the current market, not a stale value from before the reversal

    This prevents:
    1. Infinite reversal detection loop (same reversal detected every interval)
    2. Stale trigger snapshots that cause perpetual trigger breaches
    3. Cooldown spam from repeated cooldown activations

    Args:
        session: Full session dict (mutated in place)
        aggressor: Current aggressor side ('ce' or 'pe')
        ce_now: Current CE premium
        pe_now: Current PE premium
    """
    old_aggressor = session.get('last_aggressor', 'NONE')

    # §9: Set last_aggressor to new direction → subsequent intervals use
    # standard formula (Case A) instead of reversal detection
    session['last_aggressor'] = aggressor.upper()

    # §6.2: Update BOTH trigger snapshots to current premiums.
    # This resets the baseline so the trigger system works correctly
    # from the new direction.
    update_trigger_snapshots(session, ce_now, pe_now,
                             fetch_premium_fn=fetch_premium_fn)

    log.info(
        f"Reversal skip transition: last_aggressor {old_aggressor} → "
        f"{aggressor.upper()}, triggers updated to current premiums "
        f"(CE={ce_now:.2f}, PE={pe_now:.2f})"
    )

