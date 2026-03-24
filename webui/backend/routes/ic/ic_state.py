"""
IC State Management — Iron Condor

Defines the complete state model for the IC algorithm:
- Session state (top-level)
- Cycle state (per-cycle)
- Leg state (per-leg within cycle)
- Cycle history

Created: 2026-03-24
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from .ic_constants import (
    LOT_SIZE_BTC,
    LEG_SP, LEG_LP, LEG_SC, LEG_LC, ALL_LEGS,
    STATUS_IDLE, STRATEGY_IDLE,
    LEG_OPEN, FILL_PENDING,
)
from .ic_config import DEFAULT_PARAMS

log = logging.getLogger('ic_state')


# =============================================================================
# Leg State
# =============================================================================

def create_leg_state(
    leg_key: str,
    strike: float,
    lots: int,
    side: str,         # 'put' or 'call'
    action: str,       # 'sell' or 'buy'
    entry_premium: float = 0.0,
    order_id: str = None,
) -> Dict[str, Any]:
    """
    Create the state for a single IC leg.

    Args:
        leg_key: LEG_SP, LEG_LP, LEG_SC, or LEG_LC
        strike: Strike price in USD
        lots: Number of lots
        side: 'put' or 'call'
        action: 'sell' (short) or 'buy' (long/wing)
        entry_premium: Premium in USD/BTC at fill
        order_id: Exchange order ID
    """
    now = datetime.now(timezone.utc).isoformat()
    return {
        'leg_key': leg_key,
        'strike': strike,
        'lots': lots,
        'order_id': order_id or '',
        'entry_premium': entry_premium,
        'mark_premium': entry_premium,    # Updated every heartbeat
        'side': side,
        'action': action,
        'status': LEG_OPEN,
        'fill_status': FILL_PENDING,
        'fill_time': now if entry_premium > 0 else None,
        'close_premium': None,
        'close_time': None,

        # Greeks (updated every heartbeat from exchange data)
        'mark_delta': 0.0,
        'mark_gamma': 0.0,
        'mark_theta': 0.0,
        'mark_vega': 0.0,
    }


# =============================================================================
# Cycle State
# =============================================================================

def create_cycle_state(
    cycle_number: int,
    expiry: str,
    lots: int,
    legs: Dict[str, Dict] = None,
) -> Dict[str, Any]:
    """
    Create the state for a single IC cycle.

    Args:
        cycle_number: The cycle number (e.g., 1, 2, 3...)
        expiry: Expiry date string (e.g., '2026-03-28')
        lots: Lots per leg
        legs: Pre-constructed leg dictionaries (optional)
    """
    now = datetime.now(timezone.utc).isoformat()
    cycle_id = f"cyc_{cycle_number:03d}"

    return {
        # Identity
        'cycle_id': cycle_id,
        'cycle_number': cycle_number,
        'opened_at': now,
        'closed_at': None,
        'expiry': expiry,

        # Entry premiums (set after all fills)
        'entry_net_credit': 0.0,          # USD per BTC
        'entry_net_credit_usd': 0.0,      # entry_net_credit × lots × LOT_SIZE_BTC
        'cumulative_roll_credit': 0.0,    # Accumulated roll credits/debits

        # 4 legs
        'legs': legs or {},

        # Computed values (updated every heartbeat)
        'spot_price': 0.0,
        'max_profit_usd': 0.0,
        'max_loss_usd': 0.0,
        'unrealized_pnl_usd': 0.0,
        'pnl_as_pct_of_max_profit': 0.0,

        # Strikes summary (for quick access)
        'short_put_strike': 0,
        'long_put_strike': 0,
        'short_call_strike': 0,
        'long_call_strike': 0,
        'wing_width_put': 0,
        'wing_width_call': 0,

        # Portfolio Greeks
        'portfolio_greeks': {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
        },

        # Adjustment history
        'adjustments': [],
        'adjustment_count': 0,

        # Exit tracking
        'exit_reason': None,
        'exit_pnl_usd': None,
        'max_adverse_excursion_usd': 0.0,
    }


def compute_cycle_strikes(cycle: Dict) -> None:
    """
    Compute and cache strike summary fields from legs.
    Called after entry or roll to update quick-access fields.
    """
    legs = cycle.get('legs', {})
    if LEG_SP in legs:
        cycle['short_put_strike'] = legs[LEG_SP].get('strike', 0)
    if LEG_LP in legs:
        cycle['long_put_strike'] = legs[LEG_LP].get('strike', 0)
    if LEG_SC in legs:
        cycle['short_call_strike'] = legs[LEG_SC].get('strike', 0)
    if LEG_LC in legs:
        cycle['long_call_strike'] = legs[LEG_LC].get('strike', 0)

    cycle['wing_width_put'] = cycle['short_put_strike'] - cycle['long_put_strike']
    cycle['wing_width_call'] = cycle['long_call_strike'] - cycle['short_call_strike']


def compute_entry_credit(cycle: Dict, lots: int) -> None:
    """
    Compute and store the net credit at entry from all 4 legs.
    Call after all legs are filled.
    """
    legs = cycle.get('legs', {})
    if not legs:
        return

    # Net credit = sell premiums - buy premiums
    credit = 0.0
    for leg_key, leg in legs.items():
        if leg.get('action') == 'sell':
            credit += leg.get('entry_premium', 0.0)
        elif leg.get('action') == 'buy':
            credit -= leg.get('entry_premium', 0.0)

    cycle['entry_net_credit'] = credit
    cycle['entry_net_credit_usd'] = credit * lots * LOT_SIZE_BTC
    cycle['max_profit_usd'] = cycle['entry_net_credit_usd']


# =============================================================================
# Session State
# =============================================================================

def create_session(
    session_id: str = None,
    name: str = 'BTC IC Weekly',
    symbol: str = 'BTCUSD',
    params: Dict = None,
) -> Dict[str, Any]:
    """
    Create a new IC session with full state.

    Args:
        session_id: Optional session ID (auto-generated if None)
        name: Human-readable session name
        symbol: Underlying symbol
        params: User-provided parameters (merged with defaults)

    Returns:
        Complete session dictionary
    """
    now = datetime.now(timezone.utc).isoformat()

    # Merge params with defaults
    merged_params = {**DEFAULT_PARAMS}
    if params:
        merged_params.update(params)

    if not session_id:
        date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
        short_uuid = uuid.uuid4().hex[:6]
        session_id = f"ic_{date_part}_{short_uuid}"

    return {
        # Identity
        'session_id': session_id,
        'name': name,
        'created_at': now,
        'updated_at': now,
        'symbol': symbol,

        # Lifecycle
        'status': STATUS_IDLE,
        'strategy_status': STRATEGY_IDLE,

        # Cycle tracking
        'cycle_number': 0,
        'cycles_completed': 0,
        'total_realized_pnl': 0.0,

        # Current cycle (null if no active cycle)
        'current_cycle': None,

        # Cycle history
        'cycle_history': [],

        # Params
        'params': merged_params,

        # Safety
        'safety_events': [],
        'daily_loss_usd': 0.0,
        'max_daily_loss_hit': False,
        'daily_loss_reset_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),

        # Metadata
        'expiry': '',
        'last_heartbeat': None,
        'heartbeat_count': 0,
        'last_adjustment_time': None,

        # Circuit breaker tracking
        'recent_adjustment_times': [],  # timestamps of recent adjustments for circuit breaker
        'circuit_breaker_active': False,
        'circuit_breaker_until': None,

        # Data confidence
        'consecutive_fetch_failures': 0,
    }


def reset_daily_loss(session: Dict) -> None:
    """Reset daily loss counter if date has changed (UTC midnight)."""
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if session.get('daily_loss_reset_date') != today:
        session['daily_loss_usd'] = 0.0
        session['max_daily_loss_hit'] = False
        session['daily_loss_reset_date'] = today
        log.info(f"[{session.get('session_id', '?')}] Daily loss reset for {today}")


def archive_cycle(session: Dict) -> None:
    """
    Move current_cycle to cycle_history and clear it.
    Called after a cycle is closed.
    """
    cycle = session.get('current_cycle')
    if not cycle:
        return

    history_entry = {
        'cycle_id': cycle.get('cycle_id'),
        'cycle_number': cycle.get('cycle_number'),
        'opened_at': cycle.get('opened_at'),
        'closed_at': cycle.get('closed_at'),
        'expiry': cycle.get('expiry'),
        'entry_net_credit_usd': cycle.get('entry_net_credit_usd', 0),
        'exit_pnl_usd': cycle.get('exit_pnl_usd', 0),
        'exit_reason': cycle.get('exit_reason'),
        'adjustment_count': cycle.get('adjustment_count', 0),
        'max_adverse_excursion_usd': cycle.get('max_adverse_excursion_usd', 0),
        'short_put_strike': cycle.get('short_put_strike', 0),
        'short_call_strike': cycle.get('short_call_strike', 0),
    }

    if 'cycle_history' not in session:
        session['cycle_history'] = []
    session['cycle_history'].append(history_entry)

    session['current_cycle'] = None
