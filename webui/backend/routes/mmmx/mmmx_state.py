"""
MMMX State — Session Factory & Schema Validator

Creates canonical session dicts (schema v1) and provides initialize_* helpers.
Spec: MMMX_COMPLETE.md Section 1.3 (Session Schema), Section 1.4 (Tranche),
      Section 1.5 (Hedge), Section 2 (Capital), MMMX_IMPLEMENTATION_PLAN.md Section 1.

Rules:
  - create_session() is the ONLY place a session dict is constructed from scratch.
  - validate_schema() rejects unknown schema versions.
  - All runtime-only underscore fields survive a save/restore round-trip.
  - Naive utcnow() is banned; always use datetime.now(timezone.utc).
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .mmmx_constants import (
    SCHEMA_VERSION, SessionStatus, CBState,
    LOT_SIZE_BTC, TOTAL_BUDGET_LOTS, RESERVE_LOTS_DEFAULT, TRANCHE_COUNT,
    FEE_RATE_MAKER, FEE_RATE_TAKER,
)

log = logging.getLogger('mmmx_state')


# ── Default params (matches Section 1.3 of plan) ──────────────────────────────
_DEFAULT_PARAMS: Dict[str, Any] = {
    # entry gates (NOT hot-reloadable)
    'entry_dte_min':                  20,
    'entry_dte_max':                  45,
    'entry_iv_rank_min':              50,
    # tranche deployment
    'total_budget_lots':              100,
    'tranche_pct':                    10,
    'otm_distance_pct':               15.0,
    'tranche_deploy_move_pct':        2.0,
    'tranche_deploy_iv_delta':        10,
    'hard_stop_multiplier':           2.0,
    'adjustment_interval_hours':      1,
    # delta gates
    'delta_drift_threshold':          0.35,
    'portfolio_delta_threshold':      0.15,
    'near_itm_delta':                 0.55,
    'emergency_delta':                0.70,
    # IV
    'iv_spike_threshold_pct':         50,
    'iv_catastrophe_pct':             80,
    # ATM shield
    'atm_protect_threshold':          5.0,
    'atm_shield_max_shifts':          3,
    # quality gates
    'fairness_gate_enabled':          True,
    'fairness_threshold_pct':         10.0,
    'max_deployments_per_day':        2,
    # profit booking
    'profit_booking_enabled':         True,
    'profit_booking_targets':         [10, 20, 30, 50],
    # hedging
    'hedging_enabled':                True,
    'hedge_distance_pct':             20.0,
    'hedge_execution_delay_minutes':  15,
    'hedge_capacity_threshold_lots':  50,
    # exit
    'close_at_dte':                   7,      # HARD MIN 7 — enforced in mmmx_config
    'profit_target_pct':              50,
    'profit_target_enabled':          False,
    # whipsaw
    'whipsaw_window_mins':            30,
    'whipsaw_spot_move_pct':          0.3,
    'whipsaw_caution_score':          2,
    'whipsaw_restrict_score':         3,
    'whipsaw_cooldown_score':         4,
    'whipsaw_cooldown_interval_hours': 1,
}


def create_session(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a new MMMX session dict at schema v1.

    All fields are fully populated so callers never need to .get(key, default).
    Runtime-only underscore fields are included so they survive restore round-trips.

    Args:
        params: Operator-supplied overrides merged on top of defaults.
                Must be validated by mmmx_config.validate_params() before passing here.

    Returns:
        Fully populated session dict (status=DRAFT).
    """
    now = datetime.now(timezone.utc).isoformat()
    merged_params = {**_DEFAULT_PARAMS, **(params or {})}
    session_id = str(uuid.uuid4())

    session: Dict[str, Any] = {
        # ── identity ──────────────────────────────────────────────────────────
        '_schema_version':                SCHEMA_VERSION,
        'session_id':                     session_id,
        'symbol_base':                    'BTC',
        'expiry_date':                    None,       # DD-MM-YYYY — set at deploy time
        'expiry_ddmmyy':                  merged_params.pop('target_expiry_ddmmyy', None) or None,  # DDMMYY — populated from params at creation
        'expiry_datetime':                None,       # ISO UTC
        'created_at':                     now,
        'status':                         SessionStatus.DRAFT,
        '_my_generation':                 0,

        # ── parameters ────────────────────────────────────────────────────────
        'params':                         merged_params,

        # ── capital & deployment budgets ──────────────────────────────────────
        'total_budget_lots':              TOTAL_BUDGET_LOTS,
        'ce_reserve_total_lots':          RESERVE_LOTS_DEFAULT,
        'pe_reserve_total_lots':          RESERVE_LOTS_DEFAULT,
        'ce_reserve_remaining':           RESERVE_LOTS_DEFAULT,
        'pe_reserve_remaining':           RESERVE_LOTS_DEFAULT,
        'tranches_deployed':              0,
        'tranches_remaining':             TRANCHE_COUNT,
        'total_deployed_lots':            0,
        'total_premium_collected':        0.0,

        # ── hard stop ─────────────────────────────────────────────────────────
        'hard_stop_usd':                  0.0,
        'last_hard_stop_recalc_at':       None,

        # ── deployment reference baselines ────────────────────────────────────
        'last_deployment_spot':           None,
        'last_deployment_iv_rank':        None,
        'deployment_eligible_tranches':   [],
        'deployment_queue_triggered_at':  None,
        'deployment_queue_triggered_spot': None,
        'deployment_queue_direction':     None,    # 'UP' | 'DOWN'
        'deployments_last_24h':           [],      # rolling list of ISO timestamps

        # ── tranches & hedges ─────────────────────────────────────────────────
        'tranches':                       [],
        'hedges':                         [],
        'hedges_by_parent':               {},
        'total_hedge_cost_paid':          0.0,
        'active_hedges':                  0,

        # ── portfolio risk snapshot ───────────────────────────────────────────
        'portfolio_delta':                0.0,
        'portfolio_pnl':                  0.0,
        'ce_lot_balance': {
            'total_ce_lots':              0,
            'total_pe_lots':              0,
            'imbalance_pct':              0.0,
            'last_rebalance_beat':        0,
        },
        'fees_tracking': {
            'total_maker_fees':           0.0,
            'total_taker_fees':           0.0,
            'fee_rate_maker':             FEE_RATE_MAKER,
            'fee_rate_taker':             FEE_RATE_TAKER,
            'total_fees_paid':            0.0,
            'last_fee_charge':            None,
        },

        # ── whipsaw state ─────────────────────────────────────────────────────
        '_whipsaw_score':                 0,
        '_whipsaw_last_noise_at':         None,
        '_whipsaw_skip_until':            None,
        '_whipsaw_last_checked_idx':      0,
        'shield_event_history':           [],

        # ── runtime / safety flags ────────────────────────────────────────────
        '_force_check':                   False,
        '_pnl_calculation_incomplete':    False,
        '_stale_abort_gen':               None,
        '_naked_positions':               [],
        '_circuit_breaker_state':         CBState.CLOSED,
        '_last_beat_at':                  None,
        '_last_price_update_at':          None,

        # ── profit booking queue ──────────────────────────────────────────────────
        '_profit_booking_queue':          [],   # [{'tranche_id', 'target_pct', 'queued_at'}]

        # ── audit & counters ──────────────────────────────────────────────────
        'beat_number':                    0,
        'adjustment_count':               0,
        'shield_fire_count':              0,
        'profit_booked_total':            0.0,
    }

    return session


def make_tranche(
    tranche_id,
    entry_spot: float,
    entry_dvol: float,
    entry_iv_rank: float,
    ce_symbol: str,
    ce_strike: float,
    ce_lots: int,
    ce_premium: float,
    ce_delta: float,
    pe_symbol: str,
    pe_strike: float,
    pe_lots: int,
    pe_premium: float,
    pe_delta: float,
    tranche_type: str = 'deployment',
    parent_tranche_id=None,
    shield_event=None,
) -> Dict[str, Any]:
    """
    Create a tranche dict (deployment or recovery). Schema per Section 1.4.

    tranche_id: int for deployment, str like "2A" for recovery.
    """
    import secrets
    now = datetime.now(timezone.utc).isoformat()
    premium_collected = (ce_premium + pe_premium) * ce_lots * LOT_SIZE_BTC

    def _make_leg(symbol, strike, lots, premium, delta):
        return {
            '_pos_id':         secrets.token_hex(4),   # 8-char hex
            'symbol':          symbol,
            'strike':          strike,
            'lots':            lots,
            'entry_premium':   premium,
            'entry_delta':     delta,
            'current_premium': None,
            'current_delta':   None,
            'unrealized_pnl':  0.0,
            'realized_pnl':    0.0,
            'fees_paid':       0.0,
            'status':          TrncStatusLocal.ACTIVE,
            'shift_count':     0,
            '_being_closed':   False,
            '_being_closed_at': None,
            'shield_history':  [],
        }

    return {
        'tranche_id':        tranche_id,
        'parent_tranche_id': parent_tranche_id,
        'type':              tranche_type,
        'shield_event':      shield_event,
        'deployed_at':       now,
        'entry_spot':        entry_spot,
        'entry_dvol':        entry_dvol,
        'entry_iv_rank':     entry_iv_rank,
        'ce':                _make_leg(ce_symbol, ce_strike, ce_lots, ce_premium, ce_delta),
        'pe':                _make_leg(pe_symbol, pe_strike, pe_lots, pe_premium, pe_delta),
        'premium_collected': premium_collected,
        'status':            TrncStatusLocal.ACTIVE,
        'close_reason':      None,
        'closed_at':         None,
    }


# Avoid circular import — mirror the string locally
class TrncStatusLocal:
    ACTIVE       = 'ACTIVE'
    CLOSED       = 'CLOSED'
    REPOSITIONED = 'REPOSITIONED'
    REDUCED      = 'REDUCED'


def make_hedge(
    parent_tranche_id: int,
    entry_spot: float,
    hedge_distance_pct: float,
    ce_symbol: str,
    ce_strike: float,
    ce_lots: int,
    ce_premium: float,
    ce_delta: float,
    pe_symbol: str,
    pe_strike: float,
    pe_lots: int,
    pe_premium: float,
    pe_delta: float,
    ce_spread_width: float,
    pe_spread_width: float,
) -> Dict[str, Any]:
    """Create a hedge dict. Schema per Section 1.5."""
    import secrets
    now = datetime.now(timezone.utc).isoformat()
    hedge_premium_paid = (ce_premium + pe_premium) * ce_lots * LOT_SIZE_BTC
    max_loss = (ce_spread_width + pe_spread_width) * ce_lots * LOT_SIZE_BTC

    def _make_hedge_leg(symbol, strike, lots, premium, delta, pos_id=None):
        return {
            'symbol':          symbol,
            'strike':          strike,
            'lots':            lots,
            'entry_premium':   premium,
            'entry_delta':     delta,
            'current_premium': None,
            'current_delta':   None,
            'position_type':   'LONG',
            'unrealized_pnl':  0.0,
            'realized_pnl':    0.0,
            'fees_paid':       0.0,
            'status':          'ACTIVE',
            '_being_closed':   False,
            '_being_closed_at': None,
        }

    return {
        'hedge_id':                  f'H-Tr{parent_tranche_id}',
        'parent_tranche_id':         parent_tranche_id,
        'type':                      'hedge',
        'deployed_at':               now,      # parent deploy time (filled by caller)
        'hedge_executed_at':         now,      # 15 min later (filled at execution)
        'entry_spot':                entry_spot,
        'hedge_distance_pct':        hedge_distance_pct,
        'ce':                        _make_hedge_leg(ce_symbol, ce_strike, ce_lots, ce_premium, ce_delta),
        'pe':                        _make_hedge_leg(pe_symbol, pe_strike, pe_lots, pe_premium, pe_delta),
        'hedge_premium_paid':        hedge_premium_paid,
        'spread_width_ce':           ce_spread_width,
        'spread_width_pe':           pe_spread_width,
        'max_loss_if_spreads_hit':   max_loss,
        'status':                    'ACTIVE',
        'displaced_from_parent_at':  None,
    }


def validate_schema(session: Dict[str, Any]) -> None:
    """
    Validate session schema version. Raises ValueError on unknown version.

    Called during session restore. Unknown versions are rejected
    (never silently migrated) to catch schema mismatches early.
    """
    version = session.get('_schema_version')
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"Unknown MMMX session schema version: {version!r}. "
            f"Expected {SCHEMA_VERSION}. Cannot restore."
        )


def initialize_whipsaw_state(session: Dict[str, Any]) -> None:
    """Ensure whipsaw fields exist (idempotent — safe to call on old sessions)."""
    session.setdefault('_whipsaw_score', 0)
    session.setdefault('_whipsaw_last_noise_at', None)
    session.setdefault('_whipsaw_skip_until', None)
    session.setdefault('_whipsaw_last_checked_idx', 0)
    session.setdefault('shield_event_history', [])


def initialize_reserve(session: Dict[str, Any]) -> None:
    """Ensure reserve fields exist (idempotent)."""
    session.setdefault('ce_reserve_total_lots', RESERVE_LOTS_DEFAULT)
    session.setdefault('pe_reserve_total_lots', RESERVE_LOTS_DEFAULT)
    session.setdefault('ce_reserve_remaining', RESERVE_LOTS_DEFAULT)
    session.setdefault('pe_reserve_remaining', RESERVE_LOTS_DEFAULT)


def initialize_fees_tracking(session: Dict[str, Any]) -> None:
    """Ensure fees_tracking sub-dict exists (idempotent)."""
    session.setdefault('fees_tracking', {
        'total_maker_fees': 0.0,
        'total_taker_fees': 0.0,
        'fee_rate_maker':   FEE_RATE_MAKER,
        'fee_rate_taker':   FEE_RATE_TAKER,
        'total_fees_paid':  0.0,
        'last_fee_charge':  None,
    })


def initialize_deployment_queue(session: Dict[str, Any]) -> None:
    """Ensure deployment queue fields exist (idempotent)."""
    session.setdefault('deployment_eligible_tranches', [])
    session.setdefault('deployment_queue_triggered_at', None)
    session.setdefault('deployment_queue_triggered_spot', None)
    session.setdefault('deployment_queue_direction', None)
    session.setdefault('deployments_last_24h', [])


def apply_session_defaults(session: Dict[str, Any]) -> None:
    """
    Idempotently apply all initialize_* helpers.
    Called after restore to ensure old sessions have all new fields.
    """
    initialize_whipsaw_state(session)
    initialize_reserve(session)
    initialize_fees_tracking(session)
    initialize_deployment_queue(session)

    # Ensure runtime flags exist
    session.setdefault('_force_check', False)
    session.setdefault('_pnl_calculation_incomplete', False)
    session.setdefault('_stale_abort_gen', None)
    session.setdefault('_naked_positions', [])
    session.setdefault('_circuit_breaker_state', CBState.CLOSED)
    session.setdefault('_last_beat_at', None)
    session.setdefault('_last_price_update_at', None)
    session.setdefault('_my_generation', 0)

    # Ensure hedge fields exist
    session.setdefault('hedges', [])
    session.setdefault('hedges_by_parent', {})
    session.setdefault('total_hedge_cost_paid', 0.0)
    session.setdefault('active_hedges', 0)

    session.setdefault('portfolio_delta', 0.0)
    session.setdefault('portfolio_pnl', 0.0)
    session.setdefault('beat_number', 0)
    session.setdefault('adjustment_count', 0)
    session.setdefault('shield_fire_count', 0)
    session.setdefault('profit_booked_total', 0.0)
    session.setdefault('_profit_booking_queue', [])
    session.setdefault('hard_stop_usd', 0.0)
    session.setdefault('last_hard_stop_recalc_at', None)


def transition_status(session: Dict[str, Any], new_status: str, reason: str = '') -> None:
    """
    Transition session['status'] with legality check.

    Raises ValueError if the transition is not in LEGAL_TRANSITIONS.
    Caller is responsible for persisting after calling this.
    """
    from .mmmx_constants import LEGAL_TRANSITIONS
    old = session.get('status', SessionStatus.DRAFT)
    if new_status not in LEGAL_TRANSITIONS.get(old, set()):
        raise ValueError(
            f"Illegal MMMX session status transition: {old!r} → {new_status!r}"
            + (f" ({reason})" if reason else "")
        )
    session['status'] = new_status
