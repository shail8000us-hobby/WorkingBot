"""
MMM State Management — Money Mind & Method

Defines the complete state model for the MMM algorithm as specified in
MONEY_POWER_CALCULATION_LOGIC.md Section 2 (State) and Section 19 (Parameters).

Per-side state (CE/PE), global state, and session dataclass.

Created: February 15, 2026
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from copy import deepcopy

log = logging.getLogger('mmm_state')


# =============================================================================
# Section 2: Per-Side State
# =============================================================================

def create_side_state(
    side: str,
    original_lots: int = 0,
    original_premium: float = 0.0,
    original_strike: float = 0.0,
) -> Dict[str, Any]:
    """
    Create initial per-side state for CE or PE.

    Maps to MONEY_POWER_CALCULATION_LOGIC.md Section 2: Per-Side State.

    Args:
        side: 'CE' or 'PE'
        original_lots: Lots sold at entry
        original_premium: Premium per lot at entry
        original_strike: Strike price at entry

    Returns:
        Dictionary with all per-side state fields
    """
    return {
        'side': side,

        # Entry positions
        'original_lots': original_lots,
        'original_premium': original_premium,
        'original_strike': original_strike,

        # Active strike tracking (starts as original, changes on shift)
        'active_strike': original_strike,

        # Adjustment fills at the ACTIVE strike
        # Each: {lots, premium, strike, timestamp}
        'adjustment_fills': [],
        'adjustment_total_lots': 0,
        'adjustment_avg': 0.0,

        # Frozen positions at OLD strikes after shift
        # Each: {strike, lots, entry_premium, timestamp}
        'frozen_positions': [],
        'frozen_total_lots': 0,

        # Computed lots
        'active_lots': original_lots,  # original_lots + adjustment_total_lots
        'total_lots': original_lots,   # active_lots + frozen_total_lots

        # Trigger snapshot: {strike: premium_at_last_trigger_update}
        'trigger_snapshot': {},
    }


def recompute_side_lots(side_state: Dict) -> Dict:
    """
    Recompute active_lots and total_lots from source data.
    Call this after any change to adjustment_fills or frozen_positions.

    Args:
        side_state: The per-side state dictionary

    Returns:
        Updated side_state (mutated in place and returned)
    """
    # Adjustment totals at active strike
    adj_fills = side_state.get('adjustment_fills', [])
    side_state['adjustment_total_lots'] = sum(f.get('lots', 0) for f in adj_fills)

    if side_state['adjustment_total_lots'] > 0:
        total_prem = sum(f.get('lots', 0) * f.get('premium', 0) for f in adj_fills)
        side_state['adjustment_avg'] = total_prem / side_state['adjustment_total_lots']
    else:
        side_state['adjustment_avg'] = 0.0

    # Frozen totals
    frozen = side_state.get('frozen_positions', [])
    side_state['frozen_total_lots'] = sum(f.get('lots', 0) for f in frozen)

    # Active = original + adjustment at active strike
    side_state['active_lots'] = (
        side_state.get('original_lots', 0) + side_state['adjustment_total_lots']
    )

    # Total = active + frozen
    side_state['total_lots'] = side_state['active_lots'] + side_state['frozen_total_lots']

    return side_state


# =============================================================================
# Section 2: Global State + Section 19: Parameters → MMMSession
# =============================================================================

# Default parameter values from Section 19
DEFAULT_PARAMS = {
    'desired_ce_premium': 100.0,
    'desired_pe_premium': 100.0,
    'initial_lots': 10,
    'expiry': '',                       # Set at entry

    # Hot-reloadable parameters
    'adjustment_interval': 300,         # seconds between checks
    'min_trigger_move': 3.0,            # minimum premium move above trigger
    'shift_threshold': 50.0,            # min premium to sell at current strike
    'shift_target_premium': 100.0,      # target premium for new strike on shift
    'close_at_threshold': 5.0,          # close positions at this premium or below
    'premium_buffer_pct': 0.05,         # 5% extra lots for slippage
    'max_lots_per_side': 100,           # maximum total lots per CE or PE
    'max_adjustments': 100,              # maximum adjustment events
    'max_loss_amount': 5000.0,          # hard stop P&L threshold
    'stop_adjustment_mins': 15,         # stop adjusting N mins before expiry
    'auto_close_mins': 5,              # auto-close all N mins before expiry
    'cooldown_on_reversal': True,       # skip 1 interval on reversal
    'whipsaw_limit': 3,                 # max alternating adjustments before pause
    'trailing_stop_pct': 0.50,          # protect profit at N% of peak
    'theta_acceleration_window': 120,   # minutes before expiry to widen triggers
    'shift_threshold_pct': 0.0,            # dynamic shift: max(shift_threshold, hedge_premium * pct). 0 = disabled

    # Adaptive interval
    'adaptive_interval_enabled': True,     # auto-scale heartbeat frequency based on time-to-expiry

    # Wind-down mode
    'wind_down_enabled': False,            # reduce positions instead of adding near expiry
    'wind_down_hours_before_expiry': 4.0,  # activate wind-down N hours before expiry
    'wind_down_buyback_pct': 0.25,         # fraction of lots to buy back per trigger
    'wind_down_close_threshold': 20.0,     # elevated close-at-5 during wind-down
    'wind_down_min_lots_to_keep': 1,       # never go below this many lots per side
    'wind_down_floor_action': 'skip',      # what to do at floor: skip|normal|pause
}

# Which parameters can be changed while algo is running
HOT_RELOAD_PARAMS = {
    'adjustment_interval', 'min_trigger_move', 'shift_threshold',
    'shift_threshold_pct', 'shift_target_premium', 'close_at_threshold',
    'premium_buffer_pct', 'max_lots_per_side',
    'max_adjustments', 'max_loss_amount', 'stop_adjustment_mins',
    'auto_close_mins', 'cooldown_on_reversal', 'whipsaw_limit',
    'trailing_stop_pct', 'theta_acceleration_window',
    'adaptive_interval_enabled',
    'wind_down_enabled', 'wind_down_hours_before_expiry',
    'wind_down_buyback_pct', 'wind_down_close_threshold',
    'wind_down_min_lots_to_keep', 'wind_down_floor_action',
}


def create_session(
    session_id: str = None,
    mode: str = 'fresh',
    params: Dict = None,
) -> Dict[str, Any]:
    """
    Create a new MMM session with full state.

    Maps to MONEY_POWER_CALCULATION_LOGIC.md:
      - Section 2: State
      - Section 3: Initialization
      - Section 19: User Parameters

    Args:
        session_id: Optional session ID (auto-generated if None)
        mode: 'fresh' (auto-find strikes) or 'import' (existing positions)
        params: User-provided parameters (merged with defaults)

    Returns:
        Complete session dictionary
    """
    if session_id is None:
        short_uuid = uuid.uuid4().hex[:6]
        session_id = f"mmm_{short_uuid}"

    merged_params = {**DEFAULT_PARAMS}
    if params:
        merged_params.update(params)

    session = {
        'session_id': session_id,
        'mode': mode,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),

        # Per-side state (initialized empty, populated on entry)
        'ce': create_side_state('CE'),
        'pe': create_side_state('PE'),

        # Global state (Section 2)
        'last_aggressor': 'NONE',
        'adjustment_count': 0,
        'adjustment_history': [],   # [{side, lots_sold, premium, strike, timestamp, type}]
        'realized_pnl': 0.0,
        'total_premium_collected': 0.0,
        'total_fees': 0.0,
        'strategy_status': 'IDLE',  # IDLE → RUNNING → PAUSED/BOTH_SIDES_UP → STOPPED

        # P&L tracking
        'unrealized_pnl': 0.0,
        'peak_pnl': 0.0,

        # Reversal tracking
        'reversal_count': 0,
        'cooldown_active': False,
        'cooldown_until': None,

        # Strike shift tracking
        'shift_count': 0,
        'close_at_5_count': 0,

        # Timing
        'entry_time': None,
        'last_heartbeat': None,
        'next_heartbeat': None,
        'expiry_time': None,

        # Parameters
        'params': merged_params,

        # Heartbeat history for P&L chart
        'pnl_history': [],  # [{timestamp, total_pnl, realized, unrealized, ce_premium, pe_premium}]

        # Error tracking
        'last_error': None,
        'error_count': 0,
    }

    return session


def initialize_side_from_entry(
    session: Dict,
    side: str,
    strike: float,
    premium: float,
    lots: int,
) -> Dict:
    """
    Initialize a side with entry data (after auto-find or import).

    Maps to MONEY_POWER_CALCULATION_LOGIC.md Section 3: Initial State After Entry.

    Args:
        session: The session dictionary
        side: 'ce' or 'pe'
        strike: Entry strike price
        premium: Fill premium per lot
        lots: Number of lots sold

    Returns:
        Updated session (mutated in place)
    """
    side_key = side.lower()
    session[side_key] = create_side_state(
        side=side.upper(),
        original_lots=lots,
        original_premium=premium,
        original_strike=strike,
    )
    session[side_key]['trigger_snapshot'] = {str(int(strike)): premium}
    session[side_key] = recompute_side_lots(session[side_key])

    return session


def get_session_summary(session: Dict) -> Dict:
    """
    Get a compact summary of the session for WebUI display.

    Returns:
        Summary dictionary with key metrics
    """
    ce = session.get('ce', {})
    pe = session.get('pe', {})

    return {
        'session_id': session.get('session_id'),
        'status': session.get('strategy_status', 'IDLE'),
        'mode': session.get('mode', 'fresh'),
        'created_at': session.get('created_at'),
        'entry_time': session.get('entry_time'),

        # CE summary
        'ce_strike': ce.get('active_strike', 0),
        'ce_original_lots': ce.get('original_lots', 0),
        'ce_active_lots': ce.get('active_lots', 0),
        'ce_total_lots': ce.get('total_lots', 0),
        'ce_frozen_lots': ce.get('frozen_total_lots', 0),

        # PE summary
        'pe_strike': pe.get('active_strike', 0),
        'pe_original_lots': pe.get('original_lots', 0),
        'pe_active_lots': pe.get('active_lots', 0),
        'pe_total_lots': pe.get('total_lots', 0),
        'pe_frozen_lots': pe.get('frozen_total_lots', 0),

        # Globals
        'last_aggressor': session.get('last_aggressor', 'NONE'),
        'adjustment_count': session.get('adjustment_count', 0),
        'reversal_count': session.get('reversal_count', 0),
        'shift_count': session.get('shift_count', 0),
        'close_at_5_count': session.get('close_at_5_count', 0),

        # P&L
        'total_premium_collected': session.get('total_premium_collected', 0),
        'realized_pnl': session.get('realized_pnl', 0),
        'unrealized_pnl': session.get('unrealized_pnl', 0),
        'total_fees': session.get('total_fees', 0),
        'net_pnl': session.get('realized_pnl', 0) + session.get('unrealized_pnl', 0) - session.get('total_fees', 0),
        'peak_pnl': session.get('peak_pnl', 0),

        # Params (hot-reload visible)
        'adjustment_interval': session.get('params', {}).get('adjustment_interval', 300),
        'last_heartbeat': session.get('last_heartbeat'),
        'next_heartbeat': session.get('next_heartbeat'),

        # Expiry info
        'expiry': session.get('params', {}).get('expiry', ''),   # DDMMYYYY
        'expiry_time': session.get('expiry_time'),                # ISO UTC string
    }
