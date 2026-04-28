"""
MMM Gamma — Gamma Computation & Regime Controls

Extracted from mmm_monitor.py and mmm_regime.py to give gamma its own
clear entry point and eliminate the side-effect coupling where gamma data
was built inside _calculate_portfolio_delta().

Functions:
  build_position_map(session)              → {(strike, opt): lots}
  compute_gamma_data(ticker_results, ...)  → GammaData
  _update_gamma_cap(session, ...)          → gamma regime string
  compute_projected_gamma(session, ...)    → projected dollar gamma

Created: April 3, 2026
"""

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, TypedDict

from .mmm_constants import LOT_SIZE_BTC
from .mmm_state import record_signal_update

log = logging.getLogger('mmm_gamma')

# Gamma Regime states (canonical source — also re-exported by mmm_regime)
GAMMA_NORMAL = 'NORMAL'
GAMMA_SOFT = 'SOFT'
GAMMA_HARD = 'HARD'
GAMMA_EMERGENCY = 'EMERGENCY'

MAX_GAMMA_HISTORY = 60


# =============================================================================
# GammaData
# =============================================================================

class GammaData(TypedDict):
    portfolio_gamma: float
    positions: List[Tuple[float, int, str]]   # (greek_gamma, lots, 'C' or 'P')
    # ce_dollar_gamma and pe_dollar_gamma are NOT stored here — they depend on
    # spot_price which compute_gamma_data does not receive.  _update_gamma_cap
    # computes them from positions + spot_price and writes them to session state
    # (_ce_dollar_gamma, _pe_dollar_gamma).  Read from session, not from GammaData.


# =============================================================================
# Position Map Builder
# =============================================================================

def build_position_map(session: Dict) -> Dict[Tuple[float, str], int]:
    """Build a map of all open positions from session state.

    Reads ce/pe sides: active_strike + original_lots, adjustment_fills,
    and frozen_positions.

    Returns:
        {(strike, opt): lots} where opt is 'call' or 'put'.
    """
    position_map = {}  # key=(strike, opt_type) -> lots
    for side_key in ['ce', 'pe']:
        side = session.get(side_key, {})
        if not side:
            continue
        opt = 'call' if side_key == 'ce' else 'put'

        # Active strike positions
        active_strike = side.get('active_strike', 0)
        orig_lots = side.get('original_lots', 0)
        if active_strike and orig_lots > 0:
            key = (float(active_strike), opt)
            position_map[key] = position_map.get(key, 0) + orig_lots

        # Adjustment fills
        for fill in side.get('adjustment_fills', []):
            fill_strike = float(fill.get('strike', active_strike) or active_strike)
            fill_lots = fill.get('lots', 0)
            if fill_strike and fill_lots > 0:
                key = (fill_strike, opt)
                position_map[key] = position_map.get(key, 0) + fill_lots

        # Frozen positions
        for frozen in side.get('frozen_positions', []):
            f_strike = float(frozen.get('strike', 0))
            f_lots = frozen.get('lots', 0)
            if f_strike and f_lots > 0:
                key = (f_strike, opt)
                position_map[key] = position_map.get(key, 0) + f_lots

    return position_map


# =============================================================================
# Gamma Data Computation
# =============================================================================

def _safe_greek(val) -> float:
    """Safely convert a greek value to float (exchange may return str/None/list)."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0
    return 0.0


def compute_gamma_data(
    ticker_results: list,
    position_map: Dict[Tuple[float, str], int],
) -> GammaData:
    """Compute raw gamma metrics from ticker results and position map.

    This is the SINGLE canonical location for the 'call'→'C' / 'put'→'P'
    opt_char mapping used by the regime engine.

    Does NOT compute dollar gamma (requires spot_price).  Dollar gamma values
    (_ce_dollar_gamma, _pe_dollar_gamma, _portfolio_dollar_gamma) are derived
    by _update_gamma_cap() which has spot_price in scope.

    Args:
        ticker_results: List of ((strike, opt), response) tuples from API.
        position_map: {(strike, opt): lots} from build_position_map().

    Returns:
        GammaData with portfolio_gamma and positions list.
    """
    portfolio_gamma = 0.0
    gamma_positions = []

    for (strike, opt), resp in ticker_results:
        if isinstance(resp, Exception):
            continue

        result = resp.get('result', resp) if isinstance(resp, dict) else {}
        if isinstance(result, list):
            result = result[0] if result else {}
        greeks = result.get('greeks', {}) or {}
        greek_gamma = _safe_greek(greeks.get('gamma', 0))

        lots = int(position_map.get((strike, opt), 0))

        # Gamma: accumulate absolute gamma exposure (short options = negative gamma)
        position_gamma = greek_gamma * lots * LOT_SIZE_BTC
        portfolio_gamma += position_gamma
        if greek_gamma:
            # Store canonical 'C'/'P' (regime engine filters on these, not 'call'/'put')
            opt_char = 'C' if opt == 'call' else 'P'
            gamma_positions.append((greek_gamma, lots, opt_char))

    return GammaData(
        portfolio_gamma=portfolio_gamma,
        positions=gamma_positions,
    )


# =============================================================================
# Section B: Portfolio Gamma Cap (moved from mmm_regime.py)
# =============================================================================

def _update_gamma_cap(
    session: Dict,
    gamma_data: Dict,
    spot_price: float,
    minutes_to_expiry: Optional[float] = None,
) -> str:
    """
    Update portfolio gamma cap regime.

    Args:
        session: MMM session dict (mutated in place)
        gamma_data: {
            'positions': [(gamma_per_contract, lots, option_type), ...],
            'portfolio_gamma': float,  # raw portfolio gamma
        }
        spot_price: Current BTC spot price
        minutes_to_expiry: Minutes to expiry (for near-expiry multiplier)

    Returns:
        Current gamma regime: NORMAL / SOFT / HARD / EMERGENCY
    """
    params = session.get('params', {})
    if not params.get('gamma_cap_enabled', True):
        session['_gamma_regime'] = GAMMA_NORMAL
        return GAMMA_NORMAL

    now = datetime.now(timezone.utc).isoformat()

    # ── Get raw portfolio gamma ──
    portfolio_gamma = gamma_data.get('portfolio_gamma', 0)

    if portfolio_gamma == 0 and not gamma_data.get('positions'):
        # No gamma data available (Section E.4)
        session['_gamma_data_incomplete'] = True
        # Don't change regime on missing data — use last known
        return session.get('_gamma_regime', GAMMA_NORMAL)

    session['_gamma_data_incomplete'] = False

    # ── Compute dollar gamma (Section B.1.3) ──
    # $Γ = |Γ_portfolio| × S² × 0.01
    # This is the change in dollar-delta for a 1% spot move:
    #   d(delta_BTC × S) / dS × (S × 0.01) ≈ Γ_portfolio × S² × 0.01
    # NOT gamma P&L (which would be ½ × Γ × (0.01S)² = Γ × S² × 0.00005).
    # Limits (soft/hard/emergency) are calibrated to this formula.
    if spot_price > 0:
        dollar_gamma = abs(portfolio_gamma) * (spot_price ** 2) * 0.01
    else:
        dollar_gamma = 0

    session['_portfolio_gamma'] = round(portfolio_gamma, 8)
    session['_portfolio_dollar_gamma'] = round(dollar_gamma, 2)

    # ── Tier B: Per-side dollar gamma ──
    # Separate CE (call 'C') and PE (put 'P') gamma contributions.
    # The side closer to ATM has higher gamma per contract — that is the danger
    # side.  Used by _compute_regime_action to block only the aggressor side
    # instead of blindly blocking all sells when gamma=HARD.
    positions = gamma_data.get('positions', [])
    if spot_price > 0 and positions:
        ce_raw = sum(g * lots * LOT_SIZE_BTC for g, lots, opt in positions if opt == 'C')
        pe_raw = sum(g * lots * LOT_SIZE_BTC for g, lots, opt in positions if opt == 'P')
        ce_dollar_gamma = abs(ce_raw) * (spot_price ** 2) * 0.01
        pe_dollar_gamma = abs(pe_raw) * (spot_price ** 2) * 0.01
    else:
        ce_dollar_gamma = 0.0
        pe_dollar_gamma = 0.0
    session['_ce_dollar_gamma'] = round(ce_dollar_gamma, 2)
    session['_pe_dollar_gamma'] = round(pe_dollar_gamma, 2)

    # ── Update gamma history ──
    # L-5 fix: deque with maxlen replaces manual slicing
    raw_gamma = session.get('_gamma_history')
    gamma_history = raw_gamma if isinstance(raw_gamma, deque) \
        else deque(raw_gamma or [], maxlen=MAX_GAMMA_HISTORY)
    gamma_history.append((now, dollar_gamma))
    session['_gamma_history'] = list(gamma_history)  # Back to list for JSON safety

    # ── Get limits — position-size-aware + DTE-aware (Section B.3) ──
    # A6-11 derived these from initial_lots at session creation.  Here we re-scale
    # dynamically if active_lots grew beyond initial_lots via harvester/adjustments.
    soft_limit = params.get('gamma_soft_limit', 2500.0)
    hard_limit = params.get('gamma_hard_limit', 5000.0)
    emergency_limit = params.get('gamma_emergency_limit', 10000.0)

    # Dynamic lot scaling: use max(ce, pe) active lots — the larger live side drives
    # real gamma exposure.  Only scales UP; never tightens when lots temporarily dip.
    _initial_lots = max(int(params.get('initial_lots', 10)), 1)
    _ce_lots = session.get('ce', {}).get('active_lots', 0)
    _pe_lots = session.get('pe', {}).get('active_lots', 0)
    _effective_lots = max(_initial_lots, _ce_lots, _pe_lots)
    if _effective_lots > _initial_lots:
        _lot_scale = _effective_lots / _initial_lots
        soft_limit *= _lot_scale
        hard_limit *= _lot_scale
        emergency_limit *= _lot_scale
    session['_gamma_effective_lots'] = _effective_lots

    # ── DTE Relax Ladder (Phase 3 fix, 2026-04-28) ──────────────────────────
    # Phase 1 audit (audit/mmm/coordination/04_gamma_engine_audit.md) confirmed
    # user complaint: engine treated 5-DTE same as 1-DTE, despite γ_per_contract
    # being structurally lower at 5-DTE. Engine had only 2 DTE bands (≤30 min
    # tighten + ≤2 hr hedge-relax). Far-from-expiry sessions had no relaxation.
    #
    # New graduated ladder (TUNABLE — defaults are starting points):
    #   > 5 days     → 1.5×   (γ structurally low; relax)
    #   1–5 days     → 1.25×  (light relax)
    #   2 hr – 1 day → 1.0×   (baseline)
    #   30 min – 2 hr → 1.0×  (Tier C hedge-relax handles reactive hedges)
    #   ≤ 30 min     → 0.5×   (existing tighten — keep per Rule 5 cool-down doctrine)
    #
    # Multipliers compose: ladder factor first, then near-expiry override.
    # Ladder values are params so operators can tune without code changes.
    if minutes_to_expiry is not None:
        if minutes_to_expiry > 5 * 24 * 60:
            ladder_mult = params.get('gamma_dte_ladder_far_mult', 1.5)
        elif minutes_to_expiry > 24 * 60:
            ladder_mult = params.get('gamma_dte_ladder_multi_mult', 1.25)
        else:
            ladder_mult = 1.0
        if ladder_mult != 1.0:
            soft_limit *= ladder_mult
            hard_limit *= ladder_mult
            emergency_limit *= ladder_mult

    # Near-expiry ×0.5 tightening: applied AFTER lot scaling so the regime label
    # correctly reflects danger level, but the hedge limit (Tier C below) then
    # re-relaxes via dte_hedge_mult so reactive hedges are not blocked.
    if minutes_to_expiry is not None and minutes_to_expiry <= 30:
        multiplier = params.get('gamma_near_expiry_multiplier', 0.5)
        soft_limit *= multiplier
        hard_limit *= multiplier
        emergency_limit *= multiplier

    # ── Tier C: DTE-aware relaxed hedge limit ──
    # Near expiry gamma is structurally elevated from existing positions —
    # the algo cannot avoid breaching the hard limit simply by doing nothing.
    # When in the DTE relax window, hedge sells (the non-aggressor side) are
    # evaluated against a relaxed limit so the algo can continue to hedge.
    # The standard limits (above) still govern the regime label and emergency.
    dte_relax_hours = params.get('gamma_dte_relax_hours', 2.0)
    dte_hedge_mult = params.get('gamma_dte_hedge_multiplier', 2.0)
    if dte_relax_hours > 0 and minutes_to_expiry is not None and minutes_to_expiry <= dte_relax_hours * 60:
        hard_limit_hedge = hard_limit * dte_hedge_mult
        session['_gamma_dte_relax_active'] = True
    else:
        hard_limit_hedge = hard_limit
        session['_gamma_dte_relax_active'] = False
    session['_gamma_hard_limit_hedge_effective'] = round(hard_limit_hedge, 2)

    # ── Determine gamma regime ──
    if dollar_gamma >= emergency_limit:
        new_regime = GAMMA_EMERGENCY
    elif dollar_gamma >= hard_limit:
        new_regime = GAMMA_HARD
    elif dollar_gamma >= soft_limit:
        new_regime = GAMMA_SOFT
    else:
        new_regime = GAMMA_NORMAL

    current_regime = session.get('_gamma_regime', GAMMA_NORMAL)
    if new_regime != current_regime:
        session['_gamma_regime_since'] = now
        log.info(
            f"Gamma regime transition: {current_regime} → {new_regime} "
            f"($Γ={dollar_gamma:.2f}, CE=$Γ{ce_dollar_gamma:.0f}, "
            f"PE=$Γ{pe_dollar_gamma:.0f}, "
            f"soft={soft_limit:.0f}, hard={hard_limit:.0f}, "
            f"emergency={emergency_limit:.0f}, hedge_hard={hard_limit_hedge:.0f})"
        )

    session['_gamma_regime'] = new_regime
    session['_gamma_soft_limit_effective'] = round(soft_limit, 2)
    session['_gamma_hard_limit_effective'] = round(hard_limit, 2)
    session['_gamma_emergency_limit_effective'] = round(emergency_limit, 2)

    # Phase 3 Rule 6: timestamp gamma_regime for arbiter stale-detection
    record_signal_update(session, 'gamma_regime')
    return new_regime


# =============================================================================
# Projected Gamma (moved from mmm_regime.py)
# =============================================================================

def compute_projected_gamma(
    session: Dict,
    new_strike_gamma: float,
    new_lots: int,
    spot_price: float,
) -> float:
    """
    Compute projected portfolio dollar gamma if a new position were added.
    Used for pre-trade gamma check (Section B.4.1).

    Args:
        session: MMM session dict
        new_strike_gamma: Gamma per contract of the new strike
        new_lots: Number of lots to add
        spot_price: Current spot price

    Returns:
        Projected dollar gamma after adding the position
    """
    current_gamma = session.get('_portfolio_gamma', 0)
    # New position gamma (short, so adds to absolute exposure)
    added_gamma = new_strike_gamma * new_lots * LOT_SIZE_BTC
    projected_gamma = abs(current_gamma) + abs(added_gamma)
    projected_dollar_gamma = projected_gamma * (spot_price ** 2) * 0.01
    return projected_dollar_gamma
