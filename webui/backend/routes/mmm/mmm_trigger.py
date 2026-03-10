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

from .mmm_constants import strike_key

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

    ce_side = session.get('ce', {})
    pe_side = session.get('pe', {})

    # Get trigger snapshot at the active strike
    # Robust v2 Fix #13: Use canonical strike_key() for consistent hashing
    ce_active_strike = strike_key(ce_side.get('active_strike', 0))
    pe_active_strike = strike_key(pe_side.get('active_strike', 0))

    ce_trigger = ce_side.get('trigger_snapshot', {}).get(ce_active_strike, 0)
    pe_trigger = pe_side.get('trigger_snapshot', {}).get(pe_active_strike, 0)

    # Calculate absolute excess above trigger
    ce_excess = ce_now - ce_trigger
    pe_excess = pe_now - pe_trigger

    # Calculate percentage excess (using floor to prevent div-by-zero)
    ce_base = max(ce_trigger, TRIGGER_PCT_FLOOR)
    pe_base = max(pe_trigger, TRIGGER_PCT_FLOOR)
    ce_excess_pct = (ce_excess / ce_base) * 100
    pe_excess_pct = (pe_excess / pe_base) * 100

    # Apply percentage-based minimum trigger move filter
    ce_triggered = ce_excess_pct > min_trigger_move
    pe_triggered = pe_excess_pct > min_trigger_move

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

    ce_side['trigger_snapshot'][ce_active] = ce_now
    pe_side['trigger_snapshot'][pe_active] = pe_now

    # §6.2: Also snapshot ALL strikes with open frozen positions.
    # This makes frozen position loss INCREMENTAL (since last hedge)
    # instead of lifetime (since entry), preventing double-counting.
    if fetch_premium_fn:
        for side_key, side_state, option_type in [
            ('ce', ce_side, 'call'),
            ('pe', pe_side, 'put'),
        ]:
            for frozen_pos in side_state.get('frozen_positions', []):
                f_strike = frozen_pos.get('strike', 0)
                if f_strike <= 0 or frozen_pos.get('lots', 0) <= 0:
                    continue
                f_strike_key = strike_key(f_strike)
                try:
                    f_current = fetch_premium_fn(f_strike, option_type)
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
