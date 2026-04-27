"""
MMM Auto-Replenish Leg — re-enter empty side instead of pausing.

When one side (CE or PE) reaches 0 total lots while the other still has
open positions, this module decides whether to automatically sell a new
leg on the empty side.  All functions are pure (no I/O) and sealable.

Integration: called from mmm_monitor.py ONE-SIDE CLOSE GUARD section.
If replenishment is ineligible or fails, the existing PAUSE behavior
activates as fallback.

HEDGE RESTORATION PRINCIPLE (2026-04-02, updated 2026-04-12):
  Replenish is a defensive hedge-restoration action, not an offensive
  sell.  Hedging always takes priority over rate-limiting.

  Gates that DO NOT apply to replenish:
    - Gate 3  (wind-down active): replenish overrides wind-down.
    - Gate 4  (wind-down flags): same.
    - Gate 6  (regime BLOCK_ALL_SELLS): regime blocks speculative sells,
              not hedge restoration.
    - Gate 7  (max replenish count): no per-session cap on hedge restores.
    - Gate 8  (cooldown): no cooldown between replenishes — an unhedged
              position cannot wait for a timer to expire.
    - Gate 9  (near expiry): if one side is exposed even near expiry, the
              hedge must be restored — the alternative (staying unhedged
              through expiry) is always worse.
    - Gate 11 (lot velocity): velocity limits protect against speculative
              over-selling; they must not block hedge restoration.

  Gates that survive (hard financial constraints only):
    - Gate 1  (replenish_enabled): master switch — user has explicitly
              disabled replenish.
    - Gate 2  (session STOPPED): user has explicitly stopped the session
              and will handle it manually.  PAUSED is always allowed —
              an unhedged position while paused is more dangerous than
              the pause intent.
    - Gate 5  (margin block / wind-down): adding positions when margin
              is critical can trigger liquidation, which is worse than
              being temporarily unhedged.
    - Gate 10 (open side has no active lots): nothing to hedge.

  OCS emergency (ocs_emergency=True): additionally bypasses Gate 1 and
  allows STOPPED sessions.  Used when closed_side.total_lots==0 and the
  position is actively unhedged.
"""

import logging
from typing import Dict, Tuple

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# §1  Eligibility check (sealed)
# ---------------------------------------------------------------------------

def check_replenish_eligibility(
    session: Dict,
    closed_side: str,
    open_side: str,
    ocs_emergency: bool = False,
) -> Tuple[bool, str]:
    """
    Evaluate safety gates before attempting a replenish sell.

    Args:
        ocs_emergency: True when the closed side is completely empty
            (total_lots=0) while the open side still has active lots.
            Additionally bypasses Gate 1 (master switch) so that the hedge
            is restored even if replenish_enabled=False.  STOPPED is still
            respected — the user chose to stop the session.

    Returns:
        (eligible, reason) — reason names the blocking gate, or 'eligible'.
    """
    params = session.get('params', {})

    # OCS EMERGENCY: additionally bypass master switch.
    # All other surviving gates (margin, open-side-empty) apply normally.
    if not ocs_emergency:
        # Gate 1: master switch
        if not params.get('replenish_enabled', False):
            return False, 'replenish_enabled=False'

    # Gate 2: STOPPED blocks (user will handle manually).
    # PAUSED always allows — an unhedged position while paused is more
    # dangerous than the pause intent.  None / RUNNING / ACTIVE: allowed.
    status = session.get('strategy_status', session.get('status', 'RUNNING'))
    if status == 'STOPPED':
        return False, 'session status=STOPPED'

    # Gate 3 (wind-down active): REMOVED — hedge restoration overrides.
    # Gate 4 (wind-down flags):   REMOVED — same.
    # Gate 5: margin — hard financial constraint.  Adding lots when margin
    # is critical can trigger liquidation, worse than being unhedged.
    if session.get('_margin_block_sells'):
        return False, 'margin_block_sells'
    if session.get('_margin_wind_down'):
        return False, 'margin_wind_down'

    # Gate 6  (regime BLOCK_ALL_SELLS): REMOVED — hedge restoration overrides.
    # Gate 7  (max replenish count):    REMOVED — no cap on hedge restores.
    # Gate 8  (cooldown):               REMOVED — unhedged cannot wait for timer.

    # Gate 9b (AUDIT FIX: near-expiry kill switch):
    # Prevents the replenish ↔ close-at-5 infinite cycle observed in session
    # mmm26apr26-2 (23 cycles in 30 minutes).  Within the cutoff window,
    # close-at-5 will drain lots faster than replenish can restore them,
    # causing machine-gun selling with zero net benefit.  The alternative
    # (staying unhedged for the last N minutes) is less destructive than
    # the fee/slippage burn of the infinite loop.
    replenish_expiry_cutoff_mins = params.get('replenish_expiry_cutoff_mins', 30)
    minutes_to_expiry = session.get('_minutes_to_expiry')
    if minutes_to_expiry is not None and minutes_to_expiry < replenish_expiry_cutoff_mins:
        return False, f'near_expiry_cutoff ({minutes_to_expiry:.0f}min < {replenish_expiry_cutoff_mins}min)'

    # Gate 10: open side must have something to hedge.
    # Normal path: check active_lots only (frozen lots mid-close may not persist).
    # OCS emergency: frozen lots are real open positions — if active=0 but
    # total_lots > 0 (frozen), restoring the hedge is still justified.
    # Blocking here would leave a straddle unhedged because one side has
    # frozen-only exposure, which is strictly worse than the alternative.
    open_active = session.get(open_side, {}).get('active_lots', 0)
    if open_active <= 0:
        if ocs_emergency:
            open_total = session.get(open_side, {}).get('total_lots', 0)
            if open_total <= 0:
                return False, 'open_side_has_no_lots'
            # open_total > 0: frozen lots present — real exposure → allow
        else:
            return False, 'open_side_has_no_lots'

    # Gate 11 (lot velocity): REMOVED — hedging is more important than
    #                                    respecting velocity limits.

    if ocs_emergency:
        return True, 'eligible:ocs_emergency'
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
        # Default: match_active — use active_lots; fall back to total_lots when
        # active_lots=0 but frozen lots remain (OCS emergency with frozen
        # exposure).  Frozen lots are real open positions, so the hedge size
        # must reflect total exposure, not just the active portion.
        open_state = session.get(open_side, {})
        lots = open_state.get('active_lots', 0)
        if lots == 0:
            lots = open_state.get('total_lots', 0)

    # Clamp to max_lots_per_side
    lots = min(lots, max_lots)

    # Floor at 1
    lots = max(lots, 1)

    return lots


# ---------------------------------------------------------------------------
# §3  AUDIT FIX: Cap-aware lot clamping (Fix 2)
# ---------------------------------------------------------------------------

def clamp_replenish_to_cap(
    session: Dict,
    closed_side: str,
    lots: int,
) -> int:
    """
    AUDIT FIX (session mmm26apr26-2): Clamp replenish lots against
    the ACTUAL current total_lots on the closed side.

    Without this, determine_replenish_lots only clamps to max_lots_per_side
    without checking how many lots are already open on that side. After a
    watchdog restart + state drift, the in-memory total_lots can read 0
    while exchange reality is much higher, causing unbounded accumulation.

    This function reads from in-memory state (same source as the engine's
    HARD CAP GUARD). For full DB-truth reconciliation, see Fix 4
    (watchdog restart reconciliation) which ensures in-memory state is
    correct before this function ever runs.

    Returns clamped lot count (may be 0 if at cap).
    """
    params = session.get('params', {})
    max_lots = params.get('max_lots_per_side', 100)
    current_total = session.get(closed_side, {}).get('total_lots', 0)
    remaining_capacity = max(max_lots - current_total, 0)

    if lots > remaining_capacity:
        log.warning(
            f"Replenish cap clamp: {closed_side.upper()} requested {lots} lots "
            f"but only {remaining_capacity} capacity remaining "
            f"(current={current_total}, max={max_lots})"
        )
        lots = remaining_capacity

    return lots
