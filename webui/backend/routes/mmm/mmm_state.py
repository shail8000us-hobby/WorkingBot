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
    'max_adjustments': 500,             # maximum adjustment events
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
    'wind_down_hours_before_expiry': 2.0,  # activate wind-down N hours before expiry
    'wind_down_buyback_pct': 0.25,         # fraction of lots to buy back per trigger
    'wind_down_close_threshold': 20.0,     # elevated close-at-5 during wind-down
    'wind_down_min_lots_to_keep': 0,       # never go below this many lots per side (0 = full unwind allowed)
    'wind_down_floor_action': 'skip',      # what to do at floor: skip|normal|pause
    'wind_down_on_atm': False,             # auto-activate wind-down when original strike goes ATM

    # Margin Guardian (P1 safety layer)
    'margin_monitor_enabled': False,       # disabled until user opts in
    'margin_green_pct': 50.0,             # below this = normal operation
    'margin_yellow_pct': 60.0,            # caution — block new sells
    'margin_orange_pct': 75.0,            # auto wind-down (aggressive buyback)
    'margin_red_pct': 85.0,              # emergency reduce (taker orders)
    'margin_critical_pct': 90.0,          # survival — close ALL, stop session
    'margin_target_pct': 50.0,            # target utilization to wind down to

    # Regime Controls — pre-adjustment risk intelligence
    'regime_enabled': False,                 # MASTER switch for ALL regime controls (vol/gamma/trend)
    # Section A: Volatility Regime Filter
    'vol_regime_enabled': True,            # per-subsystem switch for vol regime filter
    'vol_iv_spike_pct': 30,               # IV change % threshold to trigger ELEVATED/HIGH
    'vol_rv_threshold': 80,               # annualized RV % threshold
    'vol_lookback_beats': 5,              # beats for IV rate calculation
    'vol_rv_window': 20,                  # beats for RV window
    'vol_regime_action': 'block_sells',   # action: block_sells / pause / wind_down
    'vol_regime_cooldown_beats': 10,      # beats below threshold before NORMAL

    # Section B: Portfolio Gamma Cap
    'gamma_cap_enabled': True,             # master switch for gamma cap
    'gamma_soft_limit': 2500.0,           # dollar gamma soft limit (warning) — BTC-scaled
    'gamma_hard_limit': 5000.0,           # dollar gamma hard limit (block sells) — BTC-scaled
    'gamma_emergency_limit': 10000.0,     # dollar gamma emergency (force reduce) — BTC-scaled
    'gamma_near_expiry_multiplier': 0.5,  # tighten limits by this factor in last 30 min

    # Section C: Trend Detection Guard
    'trend_enabled': True,                 # master switch for trend guard
    'trend_move_pct': 1.5,               # % move from anchor to trigger
    'trend_retrace_pct': 30,             # % retracement required to reset
    'trend_ema_period': 10,              # EMA period in beats
    'trend_ema_slope_threshold': 25,     # EMA slope threshold
    'trend_action': 'block_sells',       # action: block_sells / pause / wind_down
    'trend_reset_beats': 5,              # beats calm required before reset
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
    'wind_down_on_atm',
    # Margin Guardian
    'margin_monitor_enabled', 'margin_green_pct', 'margin_yellow_pct',
    'margin_orange_pct', 'margin_red_pct', 'margin_critical_pct',
    'margin_target_pct',
    # Regime Controls
    'regime_enabled',
    'vol_regime_enabled', 'vol_iv_spike_pct', 'vol_rv_threshold',
    'vol_lookback_beats', 'vol_rv_window', 'vol_regime_action',
    'vol_regime_cooldown_beats',
    'gamma_cap_enabled', 'gamma_soft_limit', 'gamma_hard_limit',
    'gamma_emergency_limit', 'gamma_near_expiry_multiplier',
    'trend_enabled', 'trend_move_pct', 'trend_retrace_pct',
    'trend_ema_period', 'trend_ema_slope_threshold', 'trend_action',
    'trend_reset_beats',
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
    merged_params = {**DEFAULT_PARAMS}
    if params:
        merged_params.update(params)
    
    if session_id is None:
        # Generate informative session ID: mmm18feb26-1
        expiry = merged_params.get('expiry', '')
        if expiry:
            # Parse expiry: 19022026 → 19feb26
            try:
                day = expiry[:2]
                month_num = expiry[2:4]
                year = expiry[6:8] if len(expiry) >= 8 else expiry[4:6]
                month_names = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                             'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
                month = month_names[int(month_num) - 1]
                expiry_str = f"{day}{month}{year}"
            except (ValueError, IndexError):
                # Fallback to old format if parsing fails
                expiry_str = uuid.uuid4().hex[:6]
            
            # Count existing sessions for this expiry (to get next sequence number)
            # CRITICAL: Must guarantee unique ID — never overwrite an existing session
            from .mmm_storage import get_storage
            storage = get_storage()
            try:
                all_sessions = storage.list_sessions()
                same_expiry = [s for s in all_sessions if s.get('params', {}).get('expiry') == expiry]
                count = len(same_expiry) + 1
            except Exception as e:
                log.warning(f"Failed to count existing sessions for expiry {expiry}: {e}")
                count = 1
            
            # Collision guard: keep incrementing until we find an unused ID
            candidate_id = f"mmm{expiry_str}-{count}"
            try:
                existing = storage.get_session(candidate_id)
                while existing is not None:
                    count += 1
                    candidate_id = f"mmm{expiry_str}-{count}"
                    existing = storage.get_session(candidate_id)
            except Exception as e:
                log.warning(f"Collision check failed: {e}, using uuid fallback")
                candidate_id = f"mmm{expiry_str}-{uuid.uuid4().hex[:4]}"
            
            session_id = candidate_id
        else:
            # No expiry provided, fallback to random
            short_uuid = uuid.uuid4().hex[:6]
            session_id = f"mmm_{short_uuid}"

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

        # Manual position reductions (user-triggered buybacks)
        'manual_reductions': [],     # [{side, lots, strike, avg_price, realized_pnl, timestamp}]
        'manual_reduction_pnl': 0.0, # cumulative realized P&L from manual reductions

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

        # Regime Controls — runtime state (persisted for crash recovery)
        '_vol_regime': 'NORMAL',
        '_vol_regime_since': None,
        '_vol_iv_history': [],       # ring buffer [(timestamp, iv_avg), ...]
        '_vol_spot_history': [],     # ring buffer [(timestamp, spot), ...]
        '_vol_regime_beats_below': 0,
        '_vol_iv_change_pct': 0.0,
        '_vol_rv_annualized': 0.0,
        '_vol_regime_score': 0.0,

        '_portfolio_gamma': 0.0,
        '_portfolio_dollar_gamma': 0.0,
        '_gamma_regime': 'NORMAL',
        '_gamma_history': [],        # ring buffer [(timestamp, dollar_gamma), ...]
        '_gamma_blocked_count': 0,
        '_gamma_data_incomplete': False,

        '_trend_regime': 'NORMAL',
        '_trend_since': None,
        '_trend_anchor_spot': 0.0,
        '_trend_high': 0.0,
        '_trend_low': 0.0,
        '_trend_calm_beats': 0,
        '_trend_ema': 0.0,
        '_trend_ema_prev': 0.0,
        '_trend_ema_slope': 0.0,
        '_trend_move_pct': 0.0,

        '_regime_action': 'NORMAL',

        # Session Analytics (institutional-level exposure tracking)
        'analytics': {
            'session_start_time': None,
            'session_end_time': None,
            'session_duration_seconds': 0,
            
            # Initial exposure
            'initial_ce_lots': 0,
            'initial_pe_lots': 0,
            
            # Peak exposure (maximum at any point)
            'max_ce_lots': 0,
            'max_pe_lots': 0,
            'max_combined_lots': 0,
            'peak_risk_timestamp': None,
            
            # Cumulative trading volume
            'total_ce_lots_traded': 0,  # Total CE lots sold (initial + all adjustments)
            'total_pe_lots_traded': 0,  # Total PE lots sold (initial + all adjustments)
            'total_combined_lots_traded': 0,
            
            # Exit statistics
            'auto_close_events': [],  # [{timestamp, side, strike, lots, reason}]
            'auto_close_total_lots': 0,
            'manual_close_events': [],  # [{timestamp, side, strike, lots}]
            'manual_close_total_lots': 0,
            
            # Adjustment breakdown
            'adjustment_events_by_side': {'ce': 0, 'pe': 0},
            'adjustment_events_by_type': {
                'standard': 0,
                'reversal': 0,
                'first_reversal': 0,
            },
            
            # Risk events
            'reversal_timestamps': [],
            'shift_timestamps': [],
            'both_sides_up_timestamps': [],
            'safety_trigger_events': [],  # [{timestamp, type, level}]
            
            # P&L milestones
            'time_to_first_profit': None,  # seconds from start
            'time_to_peak_pnl': None,      # seconds from start
            'max_drawdown_from_peak': 0,
            'max_drawdown_timestamp': None,
            
            # Greeks tracking
            'max_abs_delta': 0,
            'max_abs_delta_timestamp': None,
        },
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
