"""
MMM Auto-Replenish Leg — re-enter empty side instead of pausing.

When one side (CE or PE) reaches 0 total lots while the other still has
open positions, this module decides whether to automatically sell a new
leg on the empty side.  All functions are pure (no I/O) and sealable.

Integration: called from mmm_monitor.py ONE-SIDE CLOSE GUARD section.
If replenishment is ineligible or fails, the existing PAUSE behavior
activates as fallback.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Tuple

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# §1  Eligibility check (sealed)
# ---------------------------------------------------------------------------

def check_replenish_eligibility(
    session: Dict,
    closed_side: str,
    open_side: str,
) -> Tuple[bool, str]:
    """
    Evaluate all safety gates before attempting a replenish sell.

    Returns:
        (eligible, reason) — reason explains the gate that blocked,
        or 'eligible' if all gates pass.
    """
    params = session.get('params', {})

    # Gate 1: master switch
    if not params.get('replenish_enabled', False):
        return False, 'replenish_enabled=False'

    # Gate 2: session must be RUNNING
    # None is whitelisted for legacy sessions that predate the explicit status field.
    status = session.get('strategy_status', session.get('status', 'RUNNING'))
    if status not in ('RUNNING', 'ACTIVE', None):
        return False, f"session status={status}"

    # Gate 3: wind-down must NOT be active (wind-down intentionally reduces)
    from .mmm_wind_down import is_wind_down_active
    if is_wind_down_active(session):
        return False, 'wind_down_active'

    # Gate 4: no ATM/vol/trend wind-down triggered
    if session.get('_atm_wind_down_triggered'):
        return False, 'atm_wind_down_triggered'
    if session.get('_vol_wind_down_triggered'):
        return False, 'vol_wind_down_triggered'
    if session.get('_trend_wind_down_triggered'):
        return False, 'trend_wind_down_triggered'

    # Gate 5: margin must not block sells
    if session.get('_margin_block_sells'):
        return False, 'margin_block_sells'
    if session.get('_margin_wind_down'):
        return False, 'margin_wind_down'

    # Gate 6: regime must not block all sells
    from .mmm_regime import ACTION_BLOCK_ALL_SELLS
    if session.get('_regime_action') == ACTION_BLOCK_ALL_SELLS:
        return False, 'regime_block_all_sells'

    # Gate 7: replenishment count cap
    max_count = params.get('replenish_max_per_session', 10)
    current_count = session.get('_replenish_count', 0)
    if current_count >= max_count:
        return False, f'max_count_reached ({current_count}/{max_count})'

    # Gate 8: cooldown
    cooldown_sec = params.get('replenish_cooldown_sec', 300)
    last_at = session.get('_last_replenish_at', 0)
    now = time.time()
    elapsed = now - last_at
    if last_at > 0 and elapsed < cooldown_sec:
        return False, f'cooldown ({elapsed:.0f}s < {cooldown_sec}s)'

    # Gate 9: not too close to expiry
    expiry_str = params.get('expiry', '')
    stop_adj_mins = params.get('stop_adjustment_mins', 15)
    if expiry_str:
        try:
            from .mmm_initializer import expiry_to_utc_datetime
            expiry_iso = expiry_to_utc_datetime(expiry_str, params)
            expiry_dt = datetime.fromisoformat(expiry_iso)
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            minutes_remaining = (expiry_dt - datetime.now(timezone.utc)).total_seconds() / 60.0
            if minutes_remaining < stop_adj_mins:
                return False, f'near_expiry ({minutes_remaining:.0f}m < {stop_adj_mins}m)'
        except Exception as _gate9_err:
            log.warning(f"[replenish] Gate 9 expiry parse failed ({expiry_str!r}): "
                        f"{_gate9_err} — near-expiry guard skipped")

    # Gate 10: open side must actually have lots
    open_total = session.get(open_side, {}).get('total_lots', 0)
    if open_total <= 0:
        return False, 'open_side_has_no_lots'

    return True, 'eligible'


# ---------------------------------------------------------------------------
# §2  Lot sizing (sealed)
# ---------------------------------------------------------------------------

def determine_replenish_lots(
    session: Dict,
    closed_side: str,  # reserved — not used in current modes, kept for API stability
    open_side: str,
) -> int:
    """
    Determine how many lots to sell on the empty side.

    Modes:
        'match_active' — match the open side's active_lots (not frozen)
        'initial'      — use the session's initial_lots parameter

    Result is clamped to max_lots_per_side and floored at 1.
    """
    params = session.get('params', {})
    mode = params.get('replenish_lot_mode', 'match_active')
    max_lots = params.get('max_lots_per_side', 100)

    if mode == 'initial':
        lots = params.get('initial_lots', 10)
    else:
        # Default: match_active
        open_state = session.get(open_side, {})
        lots = open_state.get('active_lots', 0)

    # Clamp to max_lots_per_side
    lots = min(lots, max_lots)

    # Floor at 1
    lots = max(lots, 1)

    return lots
