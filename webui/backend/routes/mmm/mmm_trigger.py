"""
MMM Trigger System — Money Mind & Method

Evaluates whether CE or PE premiums have exceeded their trigger snapshots
by more than min_trigger_move (percentage-based), determining if an
adjustment is needed.

min_trigger_move is a PERCENTAGE: e.g. 15 means premium must rise 15%
above the trigger snapshot to fire. This ensures symmetric sensitivity
across CE/PE regardless of premium level, and auto-scales as premiums
decay near expiry.

Maps to MONEY_POWER_CALCULATION_LOGIC.md:
  §7: The Trigger System
  §4: Heartbeat outcomes (A/B/C/D)

Created: February 15, 2026
Updated: February 17, 2026 — Converted min_trigger_move from absolute to percentage
"""

import logging
from typing import Dict, Any, Tuple, Optional

from .mmm_constants import strike_key, LOT_SIZE_BTC
from webui.backend.sealed import sealed

log = logging.getLogger('mmm_trigger')

# Minimum trigger snapshot value for percentage calculation.
# Prevents division-by-zero and wild percentages when snapshot is near-zero.
TRIGGER_PCT_FLOOR = 1.0

# Trigger outcomes (maps to §4.7)
OUTCOME_NONE = 'none'           # A: Neither side triggered — stable market
OUTCOME_CE = 'ce_triggered'     # B: CE aggressor → sell additional PE lots as hedge
OUTCOME_PE = 'pe_triggered'     # C: PE aggressor → sell additional CE lots as hedge
# D: Both sides simultaneously rose above trigger threshold.
# HANDLED in mmm_monitor.py: session paused to BOTH_SIDES_UP status,
# WebSocket alert emitted, human operator must decide which side to hedge.
# NOT dead code — fires in extremely volatile markets (sharp V-shaped reversals
# or correlated gap moves). Algorithm avoids auto-acting to prevent contradictory
# hedges (selling both CE and PE simultaneously would be a straddle).
OUTCOME_BOTH = 'both_triggered'



def evaluate_triggers(
    session: Dict,
    ce_now: float,
    pe_now: float,
) -> Dict[str, Any]:
    """
    Evaluate whether CE and/or PE premiums have exceeded their triggers.

    §7: triggered = ((premium_now - trigger_snapshot) / trigger_snapshot * 100) > min_trigger_move

    min_trigger_move is a PERCENTAGE (e.g. 15 = 15%).
    This ensures symmetric sensitivity: a 15% threshold means CE@$200
    needs $30 absolute move, while PE@$80 needs only $12 — both equally
    meaningful in proportion to their premium level.

    Args:
        session: Full session dictionary
        ce_now: Current CE premium at active CE strike
        pe_now: Current PE premium at active PE strike

    Returns:
        {
            outcome: 'none'|'ce_triggered'|'pe_triggered'|'both_triggered',
            ce_excess: float,       # Absolute excess above trigger
            pe_excess: float,       # Absolute excess above trigger
            ce_excess_pct: float,   # Percentage excess above trigger
            pe_excess_pct: float,   # Percentage excess above trigger
            ce_triggered: bool,
            pe_triggered: bool,
            ce_trigger: float,      # The trigger level
            pe_trigger: float,
            min_trigger_move: float, # The percentage threshold used
        }
    """
    params = session.get('params', {})
    # Bug #1 fix: prefer ephemeral theta-accelerated value over params
    # Default 10.0 matches DEFAULT_PARAMS in mmm_state.py (T2-1 fix: was 3.0)
    min_trigger_move = session.get(
        '_effective_min_trigger_move',
        params.get('min_trigger_move', 10.0),
    )
    # Dollar floor trigger: fire if active-strike USD loss exceeds this amount.
    # Catches the dead-zone where small % moves below min_trigger_move accumulate
    # real dollar exposure. 0 = disabled (default). OR condition with %-based trigger.
    min_trigger_dollar = params.get('min_trigger_dollar', 0.0)

    ce_side = session.get('ce', {})
    pe_side = session.get('pe', {})

    # Get trigger snapshot at the active strike
    # Robust v2 Fix #13: Use canonical strike_key() for consistent hashing
    ce_active_strike = strike_key(ce_side.get('active_strike', 0))
    pe_active_strike = strike_key(pe_side.get('active_strike', 0))

    ce_trigger = ce_side.get('trigger_snapshot', {}).get(ce_active_strike, 0)
    pe_trigger = pe_side.get('trigger_snapshot', {}).get(pe_active_strike, 0)

    # AUDIT FIX BUG4: Guard against 0/missing trigger snapshots.
    # When trigger is 0, any positive premium produces enormous excess_pct
    # via TRIGGER_PCT_FLOOR, causing false triggers.
    # Each side is validated independently so a missing snapshot on one side
    # does not blind the algo to a valid trigger on the other side.
    # (e.g. right after a CE strike shift, CE snapshot=0 but PE may be triggered)
    ce_valid = ce_trigger > 0
    pe_valid = pe_trigger > 0

    if not ce_valid:
        log.warning(
            f"CE trigger snapshot missing/zero ({ce_trigger}) "
            f"— CE evaluation disabled, PE evaluated independently"
        )
    if not pe_valid:
        log.warning(
            f"PE trigger snapshot missing/zero ({pe_trigger}) "
            f"— PE evaluation disabled, CE evaluated independently"
        )

    if not ce_valid and not pe_valid:
        log.warning("Both trigger snapshots missing/zero — skipping evaluation")
        return {
            'outcome': OUTCOME_NONE,
            'ce_excess': 0, 'pe_excess': 0,
            'ce_excess_pct': 0, 'pe_excess_pct': 0,
            'ce_triggered': False, 'pe_triggered': False,
            'ce_trigger': ce_trigger, 'pe_trigger': pe_trigger,
            'ce_now': ce_now, 'pe_now': pe_now,
            'min_trigger_move': min_trigger_move,
            'ce_dollar_excess': 0.0, 'pe_dollar_excess': 0.0,
            'ce_dollar_triggered': False, 'pe_dollar_triggered': False,
            'min_trigger_dollar': min_trigger_dollar,
        }

    # Calculate absolute excess above trigger (zero for invalid side)
    ce_excess = (ce_now - ce_trigger) if ce_valid else 0.0
    pe_excess = (pe_now - pe_trigger) if pe_valid else 0.0

    # Calculate percentage excess (using floor to prevent div-by-zero)
    ce_base = max(ce_trigger, TRIGGER_PCT_FLOOR)
    pe_base = max(pe_trigger, TRIGGER_PCT_FLOOR)
    ce_excess_pct = ((ce_excess / ce_base) * 100) if ce_valid else 0.0
    pe_excess_pct = ((pe_excess / pe_base) * 100) if pe_valid else 0.0

    # Dollar floor: compute active-strike USD loss for each side.
    # Uses active_lots only (frozen positions are not monitored here).
    # Negative dollar_excess (premium declining) cannot trigger.
    ce_active_lots = ce_side.get('active_lots', 0)
    pe_active_lots = pe_side.get('active_lots', 0)
    ce_dollar_excess = max(ce_excess * ce_active_lots * LOT_SIZE_BTC, 0.0)
    pe_dollar_excess = max(pe_excess * pe_active_lots * LOT_SIZE_BTC, 0.0)
    ce_dollar_triggered = (min_trigger_dollar > 0) and (ce_dollar_excess > min_trigger_dollar)
    pe_dollar_triggered = (min_trigger_dollar > 0) and (pe_dollar_excess > min_trigger_dollar)

    # Apply trigger: percentage-based OR dollar-floor (whichever fires first).
    # Explicit ce_valid/pe_valid guard ensures disabled side never triggers.
    ce_triggered = ce_valid and (ce_excess_pct > min_trigger_move or ce_dollar_triggered)
    pe_triggered = pe_valid and (pe_excess_pct > min_trigger_move or pe_dollar_triggered)

    # Determine outcome (§4.7)
    if ce_triggered and pe_triggered:
        outcome = OUTCOME_BOTH
    elif ce_triggered:
        outcome = OUTCOME_CE
    elif pe_triggered:
        outcome = OUTCOME_PE
    else:
        outcome = OUTCOME_NONE

    return {
        'outcome': outcome,
        'ce_excess': round(ce_excess, 2),
        'pe_excess': round(pe_excess, 2),
        'ce_excess_pct': round(ce_excess_pct, 2),
        'pe_excess_pct': round(pe_excess_pct, 2),
        'ce_triggered': ce_triggered,
        'pe_triggered': pe_triggered,
        'ce_trigger': ce_trigger,
        'pe_trigger': pe_trigger,
        'ce_now': ce_now,
        'pe_now': pe_now,
        'min_trigger_move': min_trigger_move,
        # Dollar floor fields (0 when disabled)
        'ce_dollar_excess': round(ce_dollar_excess, 4),
        'pe_dollar_excess': round(pe_dollar_excess, 4),
        'ce_dollar_triggered': ce_dollar_triggered,
        'pe_dollar_triggered': pe_dollar_triggered,
        'min_trigger_dollar': min_trigger_dollar,
    }


def check_frozen_pnl_trigger(
    session: Dict,
    fetch_premium_fn,
    ce_now: float = 0.0,
    pe_now: float = 0.0,
) -> Dict[str, Any]:
    """
    Phase 2: Fallback trigger — fires when frozen positions at old strikes
    accumulate unrealized losses exceeding min_frozen_trigger_dollar.

    MUST only be called when evaluate_triggers() returned OUTCOME_NONE.
    This prevents same-beat double-hedging: active and frozen triggers
    cannot fire in the same heartbeat.

    Uses trigger_snapshot as baseline for each frozen position (same as
    calculate_standard_loss), so already-hedged losses are never re-counted.
    Falls back to entry_premium only when no snapshot exists yet (first hedge
    cycle for that position).

    Args:
        session: Full session dict
        fetch_premium_fn: sync callable(strike, option_type) → float|None
                          Backed by _premium_cache (populated by heartbeat prefetch).
        ce_now: Active CE strike price (for return dict compatibility with evaluate_triggers)
        pe_now: Active PE strike price

    Returns:
        Same structure as evaluate_triggers() so monitor can use it as a
        drop-in replacement for trigger_result.
        Additional fields: frozen_triggered, ce_frozen_loss, pe_frozen_loss,
        min_frozen_trigger_dollar.
    """
    params = session.get('params', {})
    min_frozen = params.get('min_frozen_trigger_dollar', 0.0)

    _base_result = {
        'outcome': OUTCOME_NONE,
        'ce_excess': 0.0, 'pe_excess': 0.0,
        'ce_excess_pct': 0.0, 'pe_excess_pct': 0.0,
        'ce_triggered': False, 'pe_triggered': False,
        'ce_trigger': 0.0, 'pe_trigger': 0.0,
        'ce_now': ce_now, 'pe_now': pe_now,
        'min_trigger_move': params.get('min_trigger_move', 10.0),
        'frozen_triggered': False,
        'ce_frozen_loss': 0.0,
        'pe_frozen_loss': 0.0,
        'min_frozen_trigger_dollar': min_frozen,
    }

    if min_frozen <= 0:
        return _base_result

    def _compute_frozen_loss(side_key: str) -> float:
        side_state = session.get(side_key, {})
        option_type = 'call' if side_key == 'ce' else 'put'
        trigger_snapshots = side_state.get('trigger_snapshot', {})
        total = 0.0

        for pos in side_state.get('frozen_positions', []):
            p_strike = pos.get('strike', 0)
            p_lots = pos.get('lots', 0)
            if p_lots <= 0 or p_strike <= 0 or pos.get('_being_closed'):
                continue

            # Use trigger_snapshot as baseline — prevents double-counting
            # losses that were already covered by a previous hedge.
            # Fall back to entry_premium only when no snapshot exists yet.
            p_key = strike_key(p_strike)
            baseline = trigger_snapshots.get(p_key)
            if baseline is None or baseline <= 0:
                baseline = pos.get('entry_premium', 0)
            if baseline <= 0:
                continue

            try:
                current = fetch_premium_fn(p_strike, option_type)
            except Exception:
                continue
            if current is None or current <= 0:
                continue

            # Only count loss (premium rising above baseline), not gain
            pos_loss = max((current - baseline) * p_lots * LOT_SIZE_BTC, 0.0)
            total += pos_loss

        return total

    ce_frozen_loss = _compute_frozen_loss('ce')
    pe_frozen_loss = _compute_frozen_loss('pe')

    ce_triggered = ce_frozen_loss > min_frozen
    pe_triggered = pe_frozen_loss > min_frozen

    if ce_triggered and pe_triggered:
        outcome = OUTCOME_BOTH
    elif ce_triggered:
        outcome = OUTCOME_CE
    elif pe_triggered:
        outcome = OUTCOME_PE
    else:
        outcome = OUTCOME_NONE

    if outcome != OUTCOME_NONE:
        log.info(
            f"Frozen PnL trigger fired: CE_loss=${ce_frozen_loss:.4f}, "
            f"PE_loss=${pe_frozen_loss:.4f}, threshold=${min_frozen:.2f} → {outcome}"
        )

    return {
        'outcome': outcome,
        'ce_excess': round(ce_frozen_loss, 4),
        'pe_excess': round(pe_frozen_loss, 4),
        'ce_excess_pct': 0.0,
        'pe_excess_pct': 0.0,
        'ce_triggered': ce_triggered,
        'pe_triggered': pe_triggered,
        'ce_trigger': 0.0,
        'pe_trigger': 0.0,
        'ce_now': ce_now,
        'pe_now': pe_now,
        'min_trigger_move': params.get('min_trigger_move', 10.0),
        'frozen_triggered': True,
        'ce_frozen_loss': round(ce_frozen_loss, 4),
        'pe_frozen_loss': round(pe_frozen_loss, 4),
        'min_frozen_trigger_dollar': min_frozen,
    }


def update_trigger_snapshots(
    session: Dict,
    ce_now: float,
    pe_now: float,
    fetch_premium_fn=None,
) -> Dict:
    """
    Update BOTH sides' trigger snapshots after an adjustment.

    §6.2 CRITICAL RULE: Both sides update regardless of which was aggressor.
    Also snapshots ALL strikes with open frozen positions so that frozen
    position loss calculation is INCREMENTAL (since last hedge) not LIFETIME
    (since entry). This prevents double-counting already-hedged losses.

    Why:
      - Aggressor side: trigger ratchets up → only NEW loss above this level triggers
      - Hedge side: trigger set to current price → detects future erosion
      - Frozen positions: trigger ratchets up → prevents re-hedging same loss

    Args:
        session: Full session dict (mutated in place)
        ce_now: Current CE premium
        pe_now: Current PE premium
        fetch_premium_fn: Optional callable(strike, option_type) → current_premium
                          Used to snapshot frozen positions at old strikes.

    Returns:
        Updated session
    """
    ce_side = session.get('ce', {})
    pe_side = session.get('pe', {})

    ce_active = strike_key(ce_side.get('active_strike', 0))
    pe_active = strike_key(pe_side.get('active_strike', 0))

    # Update snapshots at active strikes
    if 'trigger_snapshot' not in ce_side:
        ce_side['trigger_snapshot'] = {}
    if 'trigger_snapshot' not in pe_side:
        pe_side['trigger_snapshot'] = {}

    # OPERATOR PIN: skip ratchet if operator has manually locked this side's trigger.
    # Soft expiry: auto-clear after MAX_PIN_ADJ adjustments so the algo self-heals
    # if the operator walks away with the pin active.
    _MAX_PIN_ADJ = 3

    if not ce_side.get('_trigger_pinned', False):
        ce_side['trigger_snapshot'][ce_active] = ce_now
    else:
        ce_side['_pin_adj_count'] = ce_side.get('_pin_adj_count', 0) + 1
        if ce_side['_pin_adj_count'] >= _MAX_PIN_ADJ:
            ce_side.pop('_trigger_pinned', None)
            ce_side.pop('_pinned_trigger_value', None)
            ce_side.pop('_pin_adj_count', None)
            ce_side['trigger_snapshot'][ce_active] = ce_now
            log.warning(
                f"CE trigger pin auto-expired after {_MAX_PIN_ADJ} adjustments — "
                f"ratchet resumed at {ce_now:.2f}"
            )

    if not pe_side.get('_trigger_pinned', False):
        pe_side['trigger_snapshot'][pe_active] = pe_now
    else:
        pe_side['_pin_adj_count'] = pe_side.get('_pin_adj_count', 0) + 1
        if pe_side['_pin_adj_count'] >= _MAX_PIN_ADJ:
            pe_side.pop('_trigger_pinned', None)
            pe_side.pop('_pinned_trigger_value', None)
            pe_side.pop('_pin_adj_count', None)
            pe_side['trigger_snapshot'][pe_active] = pe_now
            log.warning(
                f"PE trigger pin auto-expired after {_MAX_PIN_ADJ} adjustments — "
                f"ratchet resumed at {pe_now:.2f}"
            )

    # §6.2: Also snapshot ALL strikes with open frozen positions.
    # This makes frozen position loss INCREMENTAL (since last hedge)
    # instead of lifetime (since entry), preventing double-counting.
    # AUDIT FIX: Skip frozen strikes that match THIS SIDE's active strike (prevents overwrite).
    # Use side-local active key only — a CE frozen position at PE's active strike
    # is in a different trigger_snapshot dict and must NOT be skipped.
    # AUDIT FIX: Validate fetch_premium_fn return value (skip 0/None/negative)
    if fetch_premium_fn:
        for side_key, side_state, option_type, side_active in [
            ('ce', ce_side, 'call', ce_active),
            ('pe', pe_side, 'put', pe_active),
        ]:
            for frozen_pos in side_state.get('frozen_positions', []):
                f_strike = frozen_pos.get('strike', 0)
                if f_strike <= 0 or frozen_pos.get('lots', 0) <= 0:
                    continue
                f_strike_key = strike_key(f_strike)
                # Don't overwrite this side's own active strike trigger
                if f_strike_key == side_active:
                    continue
                try:
                    f_current = fetch_premium_fn(f_strike, option_type)
                    # AUDIT FIX BUG3: Validate return value
                    if f_current is None or f_current <= 0:
                        log.debug(
                            f"Skipping frozen snapshot {side_key.upper()}@{f_strike_key}: "
                            f"invalid premium {f_current}"
                        )
                        continue
                    old_snap = side_state['trigger_snapshot'].get(f_strike_key)
                    side_state['trigger_snapshot'][f_strike_key] = f_current
                    if old_snap is not None:
                        log.debug(
                            f"Frozen trigger updated: {side_key.upper()}[{f_strike_key}] "
                            f"{old_snap:.2f} → {f_current:.2f}"
                        )
                except Exception as e:
                    log.warning(
                        f"Failed to snapshot frozen {side_key.upper()}@{f_strike_key}: {e}"
                    )

    # ── Prune stale snapshot entries (HID-2 fix) ─────────────────────────────
    # trigger_snapshot accumulates entries for every strike ever active.
    # In long-running sessions with many rolls/adjustments this dict grows
    # unboundedly.  A stale entry at a re-opened strike would use an old
    # (incorrect) baseline for incremental loss calculation.
    # Keep: active strike + any strike with at least one open position.
    # Remove: strikes with no open positions and not the current active strike.
    for side_key, side_state, active_sk in [
        ('ce', ce_side, ce_active),
        ('pe', pe_side, pe_active),
    ]:
        snap = side_state.get('trigger_snapshot')
        if not snap:
            continue
        # Build set of all strikes that still have open lots.
        # Check both positions[] (canonical UPL) and frozen_positions[] (derived
        # view) so the pruning is correct whether or not recompute_side_lots()
        # has been called yet this beat.
        _open_strikes: set = {active_sk}
        for pos in side_state.get('positions', []):
            if (
                pos.get('status') in ('active', 'shifted')
                and int(pos.get('lots', 0)) > 0
            ):
                _open_strikes.add(strike_key(pos.get('strike', 0)))
        for pos in side_state.get('frozen_positions', []):
            if int(pos.get('lots', 0)) > 0:
                _open_strikes.add(strike_key(pos.get('strike', 0)))
        # Prune entries not in open set
        stale_keys = [k for k in list(snap.keys()) if k not in _open_strikes]
        for k in stale_keys:
            del snap[k]
        if stale_keys:
            log.debug(
                f"Pruned {len(stale_keys)} stale trigger_snapshot entries "
                f"for {side_key.upper()}: {stale_keys}"
            )

    session['ce'] = ce_side
    session['pe'] = pe_side

    log.info(
        f"Triggers updated: CE[{ce_active}]={ce_now:.2f}, "
        f"PE[{pe_active}]={pe_now:.2f}"
    )

    return session


def apply_theta_acceleration(
    session: Dict,
    minutes_to_expiry: float,
) -> Dict[str, Any]:
    """
    §14.7: Near expiry, widen triggers to let theta work AND speed up heartbeats.

    Trigger widening: doubles min_trigger_move percentage so algo doesn't
    fight theta decay (e.g. 15% → 30%).
    Interval reduction: FASTER heartbeats as expiry nears so decisions aren't delayed.

    Only handles the LAST theta_acceleration_window minutes (trigger widening +
    sub-30s intervals). Longer-range interval scaling is handled by
    compute_adaptive_interval().

    Tiered schedule (minutes to expiry):
        > theta_window  : no acceleration
        30-window min   : base / 2  (min 30s)
        15-30 min       : 20s
        5-15 min        : 10s
        0-5 min         : 5s

    Returns:
        { accelerated: bool, effective_min_trigger_move: float, effective_interval: int }
    """
    params = session.get('params', {})
    theta_window = params.get('theta_acceleration_window', 120)
    base_trigger_move = params.get('min_trigger_move', 10.0)
    base_interval = params.get('adjustment_interval', 300)

    if minutes_to_expiry <= 0 or minutes_to_expiry > theta_window:
        return {
            'accelerated': False,
            'effective_min_trigger_move': base_trigger_move,
            'effective_interval': base_interval,
        }

    # Tiered interval: faster as expiry approaches
    if minutes_to_expiry <= 5:
        effective_interval = 5
    elif minutes_to_expiry <= 15:
        effective_interval = 10
    elif minutes_to_expiry <= 30:
        effective_interval = 20
    else:
        # Within theta window but > 30 min: halve the base (min 30s)
        effective_interval = max(30, base_interval // 2)

    return {
        'accelerated': True,
        # Robust v2 Fix #21: Cap effective min_trigger_move at 80% to prevent
        # triggers from becoming unfireable near expiry
        'effective_min_trigger_move': min(base_trigger_move * 2, 80.0),
        'effective_interval': effective_interval,
    }


# =========================================================================
# Adaptive Interval — Auto-scale heartbeat frequency by time-to-expiry
# =========================================================================

# Tier table: (min_hours, max_hours, multiplier_of_base)
# Applied in order; first match wins.
# Rationale: market-making desks universally speed up monitoring as expiry
# approaches because gamma increases and theta decay accelerates.
ADAPTIVE_INTERVAL_TIERS = [
    # (hours_lower, hours_upper, multiplier, label)
    (30,    float('inf'), 1.00,  '>30h'),       # Distant: full base interval
    (20,    30,           0.83,  '20-30h'),      # Slight pickup
    (10,    20,           0.50,  '10-20h'),      # Mid-session, premiums moving
    (5,     10,           0.30,  '5-10h'),       # Active decay begins
    (3,     5,            0.20,  '3-5h'),        # Gamma acceleration
    (1,     3,            0.10,  '1-3h'),        # Rapid decay, fast checks
    (0.5,   1,            None,  '30m-1h'),      # Fixed 30s floor
    (0,     0.5,          None,  '<30m'),         # Handed off to theta_acceleration
]

# Absolute floor — adaptive interval never goes below this.
# Below 30s is theta_acceleration territory.
ADAPTIVE_INTERVAL_FLOOR = 30


@sealed
def compute_adaptive_interval(
    base_interval: int,
    hours_to_expiry: float,
    enabled: bool = True,
) -> Dict[str, Any]:
    """
    Auto-scale heartbeat interval based on hours remaining to expiry.

    The base_interval (user's configured value) is the SLOWEST rate.
    As expiry approaches, the interval shrinks via multipliers.

    The adaptive system handles hours-scale scaling (>30min to expiry).
    For the final 30 minutes, theta_acceleration takes over with its
    own sub-30s tiers.

    Args:
        base_interval: User's configured adjustment_interval in seconds
        hours_to_expiry: Hours remaining until expiry
        enabled: If False, returns base_interval unchanged

    Returns:
        {
            adaptive: bool,          # Whether adaptive scaling was applied
            effective_interval: int,  # The computed interval in seconds
            tier_label: str,         # Human-readable tier name
            multiplier: float,       # The multiplier applied (1.0 if not adaptive)
        }
    """
    if not enabled or hours_to_expiry is None or hours_to_expiry <= 0:
        return {
            'adaptive': False,
            'effective_interval': base_interval,
            'tier_label': 'manual',
            'multiplier': 1.0,
        }

    for h_lower, h_upper, multiplier, label in ADAPTIVE_INTERVAL_TIERS:
        if h_lower <= hours_to_expiry < h_upper:
            if multiplier is not None:
                effective = max(ADAPTIVE_INTERVAL_FLOOR, int(base_interval * multiplier))
            else:
                # Fixed floor zone (30m-1h)
                effective = ADAPTIVE_INTERVAL_FLOOR

            return {
                'adaptive': True,
                'effective_interval': effective,
                'tier_label': label,
                'multiplier': multiplier if multiplier is not None else 0,
            }

    # Fallback (shouldn't happen)
    return {
        'adaptive': False,
        'effective_interval': base_interval,
        'tier_label': 'unknown',
        'multiplier': 1.0,
    }


# =========================================================================
# Multi-Expiry v2 Functions — Percentage-Based Scaling
# =========================================================================
# These functions use percentage-of-total-DTE instead of absolute hours.
# Used for 5DTE+ sessions. 0DTE continues using the original functions.

# v2 Tier table: (pct_lower, pct_upper, multiplier, label)
ADAPTIVE_INTERVAL_V2_TIERS = [
    (0.80, float('inf'), 1.50,  '>80% remaining'),    # First 80% of life — relaxed
    (0.50, 0.80,         1.00,  '50-80% remaining'),   # Normal
    (0.20, 0.50,         0.70,  '20-50% remaining'),   # Faster
    (0.05, 0.20,         0.50,  '5-20% remaining'),    # Rapid
    (0.00, 0.05,         0.30,  '<5% remaining'),      # Very rapid (last 5%)
]


@sealed
def compute_adaptive_interval_v2(
    base_interval: int,
    hours_to_expiry: float,
    total_dte_hours: float,
    enabled: bool = True,
) -> Dict[str, Any]:
    """
    Multi-DTE adaptive interval: scales based on % of total DTE remaining.

    For 0DTE (24h total), this produces similar behavior to v1.
    For 5DTE (120h), intervals stay relaxed for the first ~96h, then
    gradually accelerate as expiry approaches.

    The key difference from v1: a 20DTE session won't be stuck in the
    ">30h" tier for its entire life.

    Args:
        base_interval: User's configured adjustment_interval in seconds
        hours_to_expiry: Hours remaining until expiry
        total_dte_hours: Total hours from session creation to expiry
        enabled: If False, returns base_interval unchanged

    Returns:
        Same format as compute_adaptive_interval()
    """
    if not enabled or hours_to_expiry is None or hours_to_expiry <= 0:
        return {
            'adaptive': False,
            'effective_interval': base_interval,
            'tier_label': 'manual',
            'multiplier': 1.0,
        }

    # Guard against zero total hours
    if total_dte_hours <= 0:
        total_dte_hours = max(hours_to_expiry, 24.0)

    pct_remaining = hours_to_expiry / total_dte_hours

    # For the last 30 minutes, hand off to theta_acceleration (same as v1)
    if hours_to_expiry < 0.5:
        return {
            'adaptive': True,
            'effective_interval': ADAPTIVE_INTERVAL_FLOOR,
            'tier_label': '<30m (theta zone)',
            'multiplier': 0,
        }

    for pct_lower, pct_upper, multiplier, label in ADAPTIVE_INTERVAL_V2_TIERS:
        if pct_lower <= pct_remaining < pct_upper:
            effective = max(ADAPTIVE_INTERVAL_FLOOR, int(base_interval * multiplier))
            return {
                'adaptive': True,
                'effective_interval': effective,
                'tier_label': label,
                'multiplier': multiplier,
            }

    return {
        'adaptive': False,
        'effective_interval': base_interval,
        'tier_label': 'unknown',
        'multiplier': 1.0,
    }


def apply_theta_acceleration_v2(
    session: Dict,
    minutes_to_expiry: float,
    total_dte_mins: float = None,
) -> Dict[str, Any]:
    """
    Multi-DTE theta acceleration: scales the acceleration window with DTE.

    Interval acceleration in the last 30 minutes is kept universal (gamma
    protection applies regardless of DTE).

    Trigger widening scales with a configurable percentage of total DTE
    instead of a fixed minute window.

    Args:
        session: Session dict with params
        minutes_to_expiry: Minutes remaining until expiry
        total_dte_mins: Total minutes from creation to expiry. If None,
                        falls back to params['theta_acceleration_window']

    Returns:
        Same format as apply_theta_acceleration()
    """
    params = session.get('params', {})
    base_trigger_move = params.get('min_trigger_move', 10.0)
    base_interval = params.get('adjustment_interval', 300)

    if minutes_to_expiry <= 0:
        return {
            'accelerated': False,
            'effective_min_trigger_move': base_trigger_move,
            'effective_interval': base_interval,
        }

    # Compute the theta acceleration window based on DTE
    if total_dte_mins and total_dte_mins > 0:
        theta_accel_window_pct = 0.02  # last 2% of total DTE
        theta_window = max(30, total_dte_mins * theta_accel_window_pct)
        # Cap at reasonable maximum (4 hours)
        theta_window = min(theta_window, 240)
    else:
        theta_window = params.get('theta_acceleration_window', 120)

    if minutes_to_expiry > theta_window:
        return {
            'accelerated': False,
            'effective_min_trigger_move': base_trigger_move,
            'effective_interval': base_interval,
        }

    # Interval tiers (universal — gamma protection near expiry)
    if minutes_to_expiry <= 5:
        effective_interval = 5
    elif minutes_to_expiry <= 15:
        effective_interval = 10
    elif minutes_to_expiry <= 30:
        effective_interval = 20
    else:
        effective_interval = max(30, base_interval // 2)

    return {
        'accelerated': True,
        'effective_min_trigger_move': min(base_trigger_move * 2, 80.0),
        'effective_interval': effective_interval,
    }

