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
from .mmm_constants import strike_key

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

    Audit fix: Returns False during wind-down mode. Wind-down changes the
    aggressor side as part of the buy-back logic, which can look like a
    direction change. Treating it as a reversal would fire a false reversal
    event and incorrectly reset the cooldown / trigger snapshots.
    """
    # Audit fix: no reversal detection during wind-down
    from .mmm_wind_down import is_wind_down_active
    if is_wind_down_active(session):
        log.debug(
            f"detect_reversal: wind-down active — suppressing reversal check "
            f"(aggressor={current_aggressor.upper()})"
        )
        return False

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
        # cooldown_active=True but no expiry — invalid state; clear so activate_cooldown can re-arm
        session['cooldown_active'] = False
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
            session.pop('_cooldown_block_logged', None)
            return False
    except (ValueError, TypeError):
        session['cooldown_active'] = False
        session.pop('_cooldown_block_logged', None)
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
    # P1-B: configurable cooldown — if reversal_cooldown_seconds > 0 use it,
    # otherwise fall back to legacy formula: 1 × adjustment_interval.
    cooldown_secs = params.get('reversal_cooldown_seconds', 0)
    if cooldown_secs and cooldown_secs > 0:
        duration = cooldown_secs
    else:
        duration = params.get('adjustment_interval', 300)

    session['cooldown_active'] = True
    # Fix #14: use timezone-aware UTC
    session['cooldown_until'] = (
        datetime.now(timezone.utc) + timedelta(seconds=duration)
    ).isoformat()

    log.info(f"Cooldown activated for {duration}s (reversal_cooldown_seconds={cooldown_secs})")


def should_skip_reversal_adjustment(
    session: Dict,
    active_strike_pnl: float,
    total_adj_pnl: float,
) -> Tuple[bool, str]:
    """
    §9: If ACTIVE-STRIKE adjustment positions are still net positive, skip.

    FM2 fix: skip gate uses active_strike_pnl only (fills at the current
    active strike). Profitable frozen positions at old strikes must not
    be able to mask a genuine loss at the current active strike — their
    profit comes from a different price regime and is not a valid offset.

    Args:
        session: Full session dict
        active_strike_pnl: P&L of adjustment fills at the current active strike
        total_adj_pnl: Full P&L including frozen positions (for logging only)

    Returns:
        (should_skip, reason)
    """
    if active_strike_pnl >= 0 and total_adj_pnl >= 0:
        return True, (
            f"Reversal detected but all adjustment positions profitable "
            f"(active=${active_strike_pnl:.2f}, total=${total_adj_pnl:.2f}). Skipping."
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
    history = session.setdefault('reversal_history', [])
    history.append({
        'from': from_side.upper(),
        'to': to_side.upper(),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'adjustment_count_at': session.get('adjustment_count', 0),
    })
    # Audit fix: cap reversal_history to prevent unbounded memory growth
    # in long-running sessions (100s of reversals in volatile markets).
    # Keep the most recent 50 for display — older history isn't actionable.
    _MAX_REVERSAL_HISTORY = 50
    if len(history) > _MAX_REVERSAL_HISTORY:
        del history[:-_MAX_REVERSAL_HISTORY]


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

    # AUDIT CONFLICT-3 FIX: Record reversal-skip as a direction change in
    # adjustment_history so the whipsaw detector can see the alternation.
    # Without this, rapid reversal-skips (profitable) are invisible to
    # whipsaw tracking, allowing unlimited oscillation.
    session.setdefault('adjustment_history', []).append({
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'aggressor': aggressor.upper(),
        'type': 'reversal_skip',
        'spot': session.get('_regime_spot_price', 0),
    })
    _hist = session['adjustment_history']
    if len(_hist) > 200:
        del _hist[:-200]

    # FM3 fix: Consecutive reversal-skip counter for circuit breaker.
    # Incremented here so the monitor can detect when too many skips
    # have accumulated without a real hedge executing.
    session['_consecutive_reversal_skip_count'] = (
        session.get('_consecutive_reversal_skip_count', 0) + 1
    )

    # FM3 fix: Capture aggressor trigger BEFORE the full snapshot update.
    # After a reversal skip (no hedge placed), the aggressor-side trigger
    # must NOT ratchet upward — that would permanently forgive accumulated
    # losses from entry. The trigger baseline can only move DOWN or stay
    # the same after a skip, so the next standard-formula beat captures
    # the full loss from the original entry, not just the increment from
    # the skipped level.
    _agg_side = session.get(aggressor, {})
    _agg_active_key = strike_key(_agg_side.get('active_strike', 0))
    _agg_now = ce_now if aggressor == 'ce' else pe_now
    _old_agg_trigger = _agg_side.get('trigger_snapshot', {}).get(_agg_active_key, float('inf'))

    # §6.2: Update BOTH trigger snapshots to current premiums.
    # This resets the baseline so the trigger system works correctly
    # from the new direction.
    update_trigger_snapshots(session, ce_now, pe_now,
                             fetch_premium_fn=fetch_premium_fn)

    # FM3 fix: Undo upward ratchet on the aggressor side.
    # update_trigger_snapshots set it to agg_now; if agg_now > old trigger
    # that would erase the accumulated loss. Restore old value in that case.
    if _agg_now > _old_agg_trigger:
        _agg_side_post = session.get(aggressor, {})
        _agg_side_post.setdefault('trigger_snapshot', {})[_agg_active_key] = _old_agg_trigger
        log.info(
            f"Reversal skip: {aggressor.upper()} trigger NOT ratcheted up "
            f"({_old_agg_trigger:.2f} → {_agg_now:.2f} suppressed — "
            f"accumulated loss preserved for next hedge)"
        )

    log.info(
        f"Reversal skip transition: last_aggressor {old_aggressor} → "
        f"{aggressor.upper()}, skip_count={session['_consecutive_reversal_skip_count']}, "
        f"triggers updated (CE={ce_now:.2f}, PE={pe_now:.2f})"
    )

