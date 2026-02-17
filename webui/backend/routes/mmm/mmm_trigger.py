"""
MMM Trigger System — Money Mind & Method

Evaluates whether CE or PE premiums have exceeded their trigger snapshots
by more than min_trigger_move, determining if an adjustment is needed.

Maps to MONEY_POWER_CALCULATION_LOGIC.md:
  §7: The Trigger System
  §4: Heartbeat outcomes (A/B/C/D)

Created: February 15, 2026
"""

import logging
from typing import Dict, Any, Tuple, Optional

log = logging.getLogger('mmm_trigger')


# Trigger outcomes (maps to §4.7)
OUTCOME_NONE = 'none'           # A: Neither triggered
OUTCOME_CE = 'ce_triggered'     # B: CE aggressor → sell PE
OUTCOME_PE = 'pe_triggered'     # C: PE aggressor → sell CE
OUTCOME_BOTH = 'both_triggered' # D: Both → user decides


def evaluate_triggers(
    session: Dict,
    ce_now: float,
    pe_now: float,
) -> Dict[str, Any]:
    """
    Evaluate whether CE and/or PE premiums have exceeded their triggers.

    §7: triggered = (premium_now - trigger_snapshot) > min_trigger_move

    Args:
        session: Full session dictionary
        ce_now: Current CE premium at active CE strike
        pe_now: Current PE premium at active PE strike

    Returns:
        {
            outcome: 'none'|'ce_triggered'|'pe_triggered'|'both_triggered',
            ce_excess: float,       # How far CE is above trigger
            pe_excess: float,       # How far PE is above trigger
            ce_triggered: bool,
            pe_triggered: bool,
            ce_trigger: float,      # The trigger level
            pe_trigger: float,
            min_trigger_move: float,
        }
    """
    params = session.get('params', {})
    # Bug #1 fix: prefer ephemeral theta-accelerated value over params
    min_trigger_move = session.get(
        '_effective_min_trigger_move',
        params.get('min_trigger_move', 3.0),
    )

    ce_side = session.get('ce', {})
    pe_side = session.get('pe', {})

    # Get trigger snapshot at the active strike
    ce_active_strike = str(int(ce_side.get('active_strike', 0)))
    pe_active_strike = str(int(pe_side.get('active_strike', 0)))

    ce_trigger = ce_side.get('trigger_snapshot', {}).get(ce_active_strike, 0)
    pe_trigger = pe_side.get('trigger_snapshot', {}).get(pe_active_strike, 0)

    # Calculate excess above trigger
    ce_excess = ce_now - ce_trigger
    pe_excess = pe_now - pe_trigger

    # Apply minimum trigger move filter
    ce_triggered = ce_excess > min_trigger_move
    pe_triggered = pe_excess > min_trigger_move

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
) -> Dict:
    """
    Update BOTH sides' trigger snapshots after an adjustment.

    §6.2 CRITICAL RULE: Both sides update regardless of which was aggressor.

    Why:
      - Aggressor side: trigger ratchets up → only NEW loss above this level triggers
      - Hedge side: trigger set to current price → detects future erosion

    Args:
        session: Full session dict (mutated in place)
        ce_now: Current CE premium
        pe_now: Current PE premium

    Returns:
        Updated session
    """
    ce_side = session.get('ce', {})
    pe_side = session.get('pe', {})

    ce_active = str(int(ce_side.get('active_strike', 0)))
    pe_active = str(int(pe_side.get('active_strike', 0)))

    # Update snapshots at active strikes
    if 'trigger_snapshot' not in ce_side:
        ce_side['trigger_snapshot'] = {}
    if 'trigger_snapshot' not in pe_side:
        pe_side['trigger_snapshot'] = {}

    ce_side['trigger_snapshot'][ce_active] = ce_now
    pe_side['trigger_snapshot'][pe_active] = pe_now

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
    §14.7: In the last N minutes before expiry, widen triggers to let theta work.

    Returns:
        { accelerated: bool, effective_min_trigger_move: float, effective_interval: int }
    """
    params = session.get('params', {})
    theta_window = params.get('theta_acceleration_window', 120)
    base_trigger_move = params.get('min_trigger_move', 3.0)
    base_interval = params.get('adjustment_interval', 300)

    if minutes_to_expiry <= 0 or minutes_to_expiry > theta_window:
        return {
            'accelerated': False,
            'effective_min_trigger_move': base_trigger_move,
            'effective_interval': base_interval,
        }

    # Double both trigger move and interval in the theta window
    return {
        'accelerated': True,
        'effective_min_trigger_move': base_trigger_move * 2,
        'effective_interval': base_interval * 2,
    }
