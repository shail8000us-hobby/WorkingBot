"""
MMM Delta Neutral Engine — Money Mind & Method

Dual-mode delta hedging engine that monitors portfolio delta drift and
hedges aggressively using either:
  - ATM/near-ATM options (collects premium, adds gamma)
  - BTCUSD perpetual futures (zero gamma, no premium)

The operator selects the instrument per-session via the Web UI.
Both modes are OFF by default.

Architecture:
  - Step 5.5 in heartbeat: runs after delta computation (Step 3.5),
    before premium trigger evaluation (Step 9).
  - When the engine fires, it can suppress the premium trigger.
  - Options mode: routes to MMMEngine.execute_adjustment() (same pipeline)
  - Perp mode: routes to mmm_perp_hedge.run_perp_hedge() (existing infra)

Created: April 27, 2026
"""

import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger('mmm_delta_engine')

from .mmm_constants import LOT_SIZE_BTC


# =============================================================================
# State Management
# =============================================================================

def _init_delta_engine_state() -> Dict:
    """Initial blank delta engine state, stored at session['_delta_engine']."""
    return {
        'last_hedge_time': None,         # ISO8601 timestamp
        'total_hedges': 0,               # cumulative hedge count
        'last_drift': 0.0,               # portfolio_delta at last check
        'last_action': 'none',           # 'options_hedge' | 'perp_hedge' | 'none' | 'skipped' | 'cooldown'
        'last_instrument': None,         # 'options' | 'perp'
        'last_hedge_lots': 0,            # lots in last hedge
        'last_hedge_side': None,         # 'ce' or 'pe'
        'cumulative_lots_hedged': 0,     # total lots hedged (options mode)
        'last_hedge_strike': None,       # strike used (options mode)
        'auto_activated': False,         # True if auto-activated by DTE
        'auto_activated_at': None,       # ISO8601 when auto-activated
        '_in_trigger_zone': False,       # hysteresis state for rebalance_band
    }


def _get_engine_state(session: Dict) -> Dict:
    """Get (or create) the delta engine state dict from session."""
    if '_delta_engine' not in session:
        session['_delta_engine'] = _init_delta_engine_state()
    return session['_delta_engine']


def is_delta_engine_enabled(session: Dict) -> bool:
    """Return True if delta neutral engine is enabled."""
    return session.get('params', {}).get('delta_engine_enabled', False)


def get_delta_engine_status(session: Dict) -> Dict:
    """Return status dict for WebSocket / API display."""
    state = _get_engine_state(session)
    params = session.get('params', {})
    portfolio_delta = session.get('portfolio_delta', 0.0)
    threshold = params.get('delta_drift_threshold', 0.01)
    hard_threshold = params.get('delta_drift_hard_threshold', 0.03)
    cooldown_sec = params.get('delta_engine_cooldown_sec', 30)
    abs_delta = abs(portfolio_delta)

    # Drift level classification
    if abs_delta >= hard_threshold:
        drift_level = 'EMERGENCY'
    elif abs_delta >= threshold:
        drift_level = 'DRIFTING'
    elif abs_delta >= threshold * 0.5:
        drift_level = 'WARNING'
    else:
        drift_level = 'NEUTRAL'

    # Compute remaining cooldown for frontend display
    cooldown_remaining = 0.0
    last_time = state.get('last_hedge_time')
    if last_time:
        try:
            last_dt = datetime.fromisoformat(last_time)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            cooldown_remaining = max(0.0, cooldown_sec - elapsed)
        except (ValueError, TypeError):
            pass

    return {
        'enabled': is_delta_engine_enabled(session),
        'instrument': params.get('delta_engine_instrument', 'options'),
        'portfolio_delta': portfolio_delta,
        'abs_delta': abs_delta,
        'drift_level': drift_level,
        'threshold': threshold,
        'hard_threshold': hard_threshold,
        'cooldown_sec': cooldown_sec,
        'cooldown_remaining_sec': round(cooldown_remaining, 1),
        'aggressiveness': params.get('delta_engine_aggressiveness', 1.0),
        'last_action': state.get('last_action', 'none'),
        'last_instrument': state.get('last_instrument'),
        'last_hedge_time': state.get('last_hedge_time'),
        'last_hedge_lots': state.get('last_hedge_lots', 0),
        'last_hedge_side': state.get('last_hedge_side'),
        'total_hedges': state.get('total_hedges', 0),
        'cumulative_lots_hedged': state.get('cumulative_lots_hedged', 0),
        'auto_activated': state.get('auto_activated', False),
        'strike_mode': params.get('delta_engine_strike_mode', 'nearest_atm'),
        'in_trigger_zone': state.get('_in_trigger_zone', False),
    }


# =============================================================================
# Delta Drift Detection
# =============================================================================

def check_delta_drift(
    session: Dict,
    portfolio_delta: float,
) -> Dict[str, Any]:
    """
    Compare |portfolio_delta| against configured thresholds with hysteresis.

    Hysteresis (Schmitt-trigger pattern):
      - Arms  when abs_delta >= delta_drift_threshold
      - Stays when abs_delta in [rebalance_band, threshold)
      - Disarms when abs_delta < rebalance_band

    This prevents churn: after a partial hedge reduces delta from 0.015 → 0.008
    (still above the 0.005 band) the engine keeps hedging until delta drops below
    the band.  Without this the cooldown is the only anti-churn mechanism.

    State tracked in session['_delta_engine']['_in_trigger_zone'].

    Returns:
        {
            triggered: bool,
            level: 'normal' | 'drift' | 'emergency',
            drift_btc: float,
            threshold_used: float,
            aggressiveness_mult: float,  # 3.0 emergency, 1.0 normal/hysteresis
        }
    """
    params = session.get('params', {})
    threshold = params.get('delta_drift_threshold', 0.01)
    hard_threshold = params.get('delta_drift_hard_threshold', 0.03)
    rebalance_band = params.get('delta_engine_rebalance_band', 0.005)
    abs_delta = abs(portfolio_delta)

    state = _get_engine_state(session)
    in_zone = state.get('_in_trigger_zone', False)

    # Emergency: always fires, sets zone
    if abs_delta >= hard_threshold:
        state['_in_trigger_zone'] = True
        return {
            'triggered': True,
            'level': 'emergency',
            'drift_btc': abs_delta,
            'threshold_used': hard_threshold,
            'aggressiveness_mult': 3.0,
        }

    # Normal trigger: enter zone
    if abs_delta >= threshold:
        state['_in_trigger_zone'] = True
        return {
            'triggered': True,
            'level': 'drift',
            'drift_btc': abs_delta,
            'threshold_used': threshold,
            'aggressiveness_mult': 1.0,
        }

    # Hysteresis: already in zone and still above rebalance band — keep hedging
    if in_zone and abs_delta >= rebalance_band:
        return {
            'triggered': True,
            'level': 'drift',
            'drift_btc': abs_delta,
            'threshold_used': rebalance_band,
            'aggressiveness_mult': 1.0,
        }

    # Below rebalance band — disarm zone, no action
    state['_in_trigger_zone'] = False
    return {
        'triggered': False,
        'level': 'normal',
        'drift_btc': abs_delta,
        'threshold_used': threshold,
        'aggressiveness_mult': 1.0,
    }


# =============================================================================
# Lot Computation (Options Mode)
# =============================================================================

def compute_delta_hedge_lots(
    session: Dict,
    portfolio_delta: float,
    per_lot_delta: float = 0.0,
    aggressiveness_override: float = 0.0,
) -> Dict[str, Any]:
    """
    Compute lots needed to neutralize portfolio delta via options.

    Args:
        session: Full session dict
        portfolio_delta: Current portfolio delta in BTC
        per_lot_delta: Actual delta per lot from exchange greeks (>0).
                       If 0, uses approximate 0.5 delta.
        aggressiveness_override: If >0, overrides the param (used for emergency)

    Returns:
        {
            lots: int,
            hedge_side: 'ce' | 'pe',
            reasoning: str,
        }
    """
    params = session.get('params', {})
    aggressiveness = aggressiveness_override or params.get('delta_engine_aggressiveness', 1.0)
    max_lots = params.get('delta_engine_max_lots_per_cycle', 20)
    use_exchange_delta = params.get('delta_engine_use_exchange_delta', True)

    # Direction: positive delta = net long → sell calls (negative delta)
    #            negative delta = net short → sell puts (positive delta)
    if portfolio_delta > 0:
        hedge_side = 'ce'
    else:
        hedge_side = 'pe'

    # Per-lot delta: use exchange greeks if available, else approximate
    if per_lot_delta <= 0 or not use_exchange_delta:
        per_lot_delta = 0.5 * LOT_SIZE_BTC  # ~0.0005 BTC per lot for ATM
        delta_source = 'approx_0.5'
    else:
        delta_source = 'exchange_greeks'

    if per_lot_delta <= 0:
        return {'lots': 0, 'hedge_side': hedge_side, 'reasoning': 'per_lot_delta is zero'}

    # Raw lots to neutralize
    lots_raw = abs(portfolio_delta) / per_lot_delta
    lots_adjusted = lots_raw * aggressiveness
    lots = max(math.ceil(lots_adjusted), 1)

    # Position cap check: respect max_lots_per_side
    max_per_side = params.get('max_lots_per_side', 100)
    current_total = session.get(hedge_side, {}).get('total_lots', 0)
    if current_total + lots > max_per_side:
        lots = max(max_per_side - current_total, 0)
        if lots <= 0:
            return {
                'lots': 0,
                'hedge_side': hedge_side,
                'reasoning': f'Position cap reached: {hedge_side.upper()} at {current_total}/{max_per_side}',
            }

    # Hard cap per cycle
    lots = min(lots, max_lots)

    reasoning = (
        f'Δ={portfolio_delta:+.4f} BTC → sell {lots} {hedge_side.upper()} '
        f'(per_lot_δ={per_lot_delta:.6f} [{delta_source}], '
        f'aggr={aggressiveness:.1f}x, raw={lots_raw:.1f})'
    )

    return {
        'lots': lots,
        'hedge_side': hedge_side,
        'reasoning': reasoning,
    }


# =============================================================================
# Strike Selection (Options Mode)
# =============================================================================

def pick_hedge_strike(
    session: Dict,
    hedge_side: str,
    spot_price: float,
    initializer=None,
    fetch_premium_fn=None,
) -> Optional[Dict[str, Any]]:
    """
    Select the best ATM/near-ATM strike for delta hedging.

    Strategy depends on delta_engine_strike_mode:
      - 'nearest_atm': closest OTM strike to spot (max delta efficiency)
      - 'session_active': use session's current active_strike (simpler)
      - 'auto': nearest_atm if active_strike >5% from spot, else active

    Args:
        session: Full session dict
        hedge_side: 'ce' or 'pe'
        spot_price: Current BTC spot price
        initializer: MMMInitializer for chain access
        fetch_premium_fn: callable(strike, option_type) → premium

    Returns:
        {strike, premium, symbol, delta_per_lot} or None
    """
    params = session.get('params', {})
    strike_mode = params.get('delta_engine_strike_mode', 'nearest_atm')
    expiry = params.get('expiry', '')
    option_type = 'call' if hedge_side == 'ce' else 'put'

    # ── Mode: session_active ──
    active_strike = session.get(hedge_side, {}).get('active_strike', 0)

    if strike_mode == 'session_active' and active_strike > 0:
        premium = None
        if fetch_premium_fn:
            try:
                premium = fetch_premium_fn(active_strike, option_type)
            except Exception:
                pass
        return {
            'strike': active_strike,
            'premium': premium or 0.0,
            'symbol': None,  # Will be built by execute_adjustment
            'delta_per_lot': 0.5 * LOT_SIZE_BTC,  # approximate
            'source': 'session_active',
        }

    # ── Mode: 'auto' — decide between nearest_atm and session_active ──
    if strike_mode == 'auto' and active_strike > 0:
        dist_pct = abs(active_strike - spot_price) / spot_price * 100 if spot_price > 0 else 999
        if dist_pct <= 5.0:
            # Active strike is close enough to ATM — use it
            premium = None
            if fetch_premium_fn:
                try:
                    premium = fetch_premium_fn(active_strike, option_type)
                except Exception:
                    pass
            return {
                'strike': active_strike,
                'premium': premium or 0.0,
                'symbol': None,
                'delta_per_lot': 0.5 * LOT_SIZE_BTC,
                'source': 'auto_active',
            }
        # Fall through to nearest_atm

    # ── Mode: nearest_atm (default) — scan chain for closest OTM strike ──
    if not initializer or not expiry:
        # Fallback: use active_strike if chain not available
        if active_strike > 0:
            premium = None
            if fetch_premium_fn:
                try:
                    premium = fetch_premium_fn(active_strike, option_type)
                except Exception:
                    pass
            return {
                'strike': active_strike,
                'premium': premium or 0.0,
                'symbol': None,
                'delta_per_lot': 0.5 * LOT_SIZE_BTC,
                'source': 'fallback_active',
            }
        return None

    try:
        chain_result = initializer.get_full_chain(expiry)
        if not chain_result or not chain_result.get('success'):
            log.warning('Delta engine: failed to fetch chain for strike selection')
            if active_strike > 0:
                return {
                    'strike': active_strike,
                    'premium': 0.0,
                    'symbol': None,
                    'delta_per_lot': 0.5 * LOT_SIZE_BTC,
                    'source': 'fallback_chain_error',
                }
            return None

        chain_list = chain_result.get('chain', [])
        if not chain_list:
            return None

        # Scan for nearest OTM strike with meaningful premium
        min_premium = 5.0  # Don't hedge at worthless strikes
        candidates = []

        for row in chain_list:
            strike = row.get('strike', 0)
            option_data = row.get(option_type, {})
            if not option_data:
                continue

            mark = float(option_data.get('mark_price', 0) or 0)
            bid = float(option_data.get('bid', 0) or 0)
            ask = float(option_data.get('ask', 0) or 0)
            symbol = option_data.get('symbol', '')

            # Best available price
            if mark > 0:
                premium = mark
            elif bid > 0 and ask > 0:
                premium = (bid + ask) / 2
            elif bid > 0:
                premium = bid
            else:
                continue

            if premium < min_premium:
                continue

            # Must be OTM (or exactly ATM)
            if option_type == 'call' and strike < spot_price:
                continue
            if option_type == 'put' and strike > spot_price:
                continue

            # Extract delta: top-level field per _enrich_option in mmm_initializer.py
            greek_delta = abs(float(option_data.get('delta', 0) or 0))

            candidates.append({
                'strike': strike,
                'premium': premium,
                'symbol': symbol,
                'distance': abs(strike - spot_price),
                'delta_per_lot': (greek_delta * LOT_SIZE_BTC) if greek_delta > 0 else (0.5 * LOT_SIZE_BTC),
                'greek_delta': greek_delta,
            })

        if not candidates:
            log.warning(f'Delta engine: no suitable {option_type} strikes found near spot {spot_price}')
            if active_strike > 0:
                return {
                    'strike': active_strike,
                    'premium': 0.0,
                    'symbol': None,
                    'delta_per_lot': 0.5 * LOT_SIZE_BTC,
                    'source': 'fallback_no_candidates',
                }
            return None

        # Sort by distance to spot (nearest first)
        candidates.sort(key=lambda c: c['distance'])
        best = candidates[0]

        log.info(
            f'Delta engine: selected {option_type.upper()} @ {best["strike"]:.0f} '
            f'(premium={best["premium"]:.2f}, dist={best["distance"]:.0f}, '
            f'δ={best["greek_delta"]:.4f}, {len(candidates)} candidates)'
        )

        return {
            'strike': best['strike'],
            'premium': best['premium'],
            'symbol': best['symbol'],
            'delta_per_lot': best['delta_per_lot'],
            'source': 'nearest_atm',
        }

    except Exception as e:
        log.exception(f'Delta engine strike selection error: {e}')
        if active_strike > 0:
            return {
                'strike': active_strike,
                'premium': 0.0,
                'symbol': None,
                'delta_per_lot': 0.5 * LOT_SIZE_BTC,
                'source': 'fallback_exception',
            }
        return None


# =============================================================================
# Cooldown Guard
# =============================================================================

def _check_cooldown(session: Dict) -> bool:
    """Return True if cooldown period has elapsed (OK to trade)."""
    params = session.get('params', {})
    cooldown_sec = params.get('delta_engine_cooldown_sec', 30)
    state = _get_engine_state(session)
    last_time = state.get('last_hedge_time')

    if not last_time:
        return True

    try:
        last_dt = datetime.fromisoformat(last_time)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        elapsed = (now - last_dt).total_seconds()
        return elapsed >= cooldown_sec
    except (ValueError, TypeError):
        return True


# =============================================================================
# Main Entry Point
# =============================================================================

async def run_delta_engine(
    session: Dict,
    portfolio_delta: float,
    spot_price: float,
    executor=None,
    fetch_premium_fn=None,
    minutes_to_expiry: float = None,
    initializer=None,
    ce_now: float = 0.0,
    pe_now: float = 0.0,
) -> Dict[str, Any]:
    """
    Main delta engine entry point. Called from heartbeat Step 5.5.

    Routes to options or perp based on delta_engine_instrument param.

    Args:
        session: Full session dict (mutated in place)
        portfolio_delta: Net delta from _calculate_portfolio_delta()
        spot_price: Current BTC spot price
        executor: MMMExecutor instance
        fetch_premium_fn: Premium fetch callback for options mode
        minutes_to_expiry: Minutes to expiry (for logging)
        initializer: MMMInitializer (for chain access in options mode)
        ce_now: Current CE active-strike premium (from heartbeat's local scope)
        pe_now: Current PE active-strike premium (from heartbeat's local scope)

    Returns:
        {
            action: 'options_hedge' | 'perp_hedge' | 'none' | 'skipped' | 'cooldown',
            lots: int,
            hedge_side: str,
            instrument: str,
            reasoning: str,
            ...
        }
    """
    params = session.get('params', {})
    state = _get_engine_state(session)
    sid = session.get('session_id', '???')

    if not is_delta_engine_enabled(session):
        state['last_action'] = 'none'
        return {'action': 'none', 'reasoning': 'delta_engine_disabled'}

    # Update last drift for status display
    state['last_drift'] = portfolio_delta

    # Check delta drift
    drift = check_delta_drift(session, portfolio_delta)
    if not drift['triggered']:
        state['last_action'] = 'none'
        log.debug(
            f'[{sid}] Delta engine: |Δ|={drift["drift_btc"]:.4f} < '
            f'threshold={drift["threshold_used"]:.4f} — no action'
        )
        return {
            'action': 'none',
            'drift': drift,
            'reasoning': f'Delta within band: |Δ|={drift["drift_btc"]:.4f}',
        }

    # Cooldown check
    if not _check_cooldown(session):
        state['last_action'] = 'cooldown'
        log.debug(f'[{sid}] Delta engine: cooldown active — skipping')
        return {
            'action': 'cooldown',
            'drift': drift,
            'reasoning': 'Cooldown active',
        }

    # Reverse mode isolation — do not hedge when reverse mode is active
    if session.get('_reverse', {}).get('active', False):
        state['last_action'] = 'skipped'
        log.info(f'[{sid}] Delta engine: reverse mode active — skipping')
        return {
            'action': 'skipped',
            'drift': drift,
            'reasoning': 'Reverse mode active',
        }

    # Strategy integration — resolve handler flags once
    try:
        from .mmm_strategy_dispatch import get_strategy_handler, resolve_strategy_type
        _handler = get_strategy_handler(resolve_strategy_type(session))
        _bypass_gamma = _handler.bypass_gamma_guards
        _options_ok = _handler.delta_engine_options_enabled
    except Exception:
        _bypass_gamma = False
        _options_ok = True

    # Route to instrument
    instrument = params.get('delta_engine_instrument', 'options')
    aggressiveness_mult = drift['aggressiveness_mult']

    # For strategies where execute_adjustment is disabled (STRADDLE_ROLL), options
    # mode would bypass that invariant — downgrade to perp silently.
    if instrument == 'options' and not _options_ok:
        log.info(
            f'[{sid}] Delta engine: options mode not available for strategy '
            f'{_handler.strategy_type} — falling back to perp'
        )
        instrument = 'perp'

    log.info(
        f'[{sid}] Delta engine TRIGGERED: |Δ|={drift["drift_btc"]:.4f} BTC, '
        f'level={drift["level"]}, instrument={instrument}, '
        f'aggr_mult={aggressiveness_mult:.1f}x'
    )

    if instrument == 'perp':
        result = await _execute_via_perp(
            session, portfolio_delta, spot_price, executor,
            aggressiveness_mult=aggressiveness_mult,
        )
    else:  # 'options'
        result = await _execute_via_options(
            session, portfolio_delta, spot_price, executor,
            fetch_premium_fn=fetch_premium_fn,
            initializer=initializer,
            aggressiveness_mult=aggressiveness_mult,
            ce_now=ce_now,
            pe_now=pe_now,
            bypass_gamma=_bypass_gamma,
        )

    result['drift'] = drift
    return result


# =============================================================================
# Options Mode Execution
# =============================================================================

async def _execute_via_options(
    session: Dict,
    portfolio_delta: float,
    spot_price: float,
    executor=None,
    fetch_premium_fn=None,
    initializer=None,
    aggressiveness_mult: float = 1.0,
    ce_now: float = 0.0,
    pe_now: float = 0.0,
    bypass_gamma: bool = False,
) -> Dict[str, Any]:
    """
    Execute delta hedge by selling ATM/near-ATM options.
    Routes through MMMEngine.execute_adjustment() for full state tracking.
    ce_now / pe_now must come from the heartbeat's local scope (passed in from
    run_delta_engine).  They are used to keep trigger snapshots valid after the
    adjustment — passing 0 would wipe both snapshots and blind the premium trigger.
    """
    sid = session.get('session_id', '???')
    state = _get_engine_state(session)
    params = session.get('params', {})
    aggressiveness = params.get('delta_engine_aggressiveness', 1.0) * aggressiveness_mult

    # 1. Pick strike
    hedge_side = 'ce' if portfolio_delta > 0 else 'pe'
    strike_info = pick_hedge_strike(
        session, hedge_side, spot_price,
        initializer=initializer,
        fetch_premium_fn=fetch_premium_fn,
    )

    if not strike_info:
        state['last_action'] = 'skipped'
        log.warning(f'[{sid}] Delta engine: no suitable strike found for {hedge_side.upper()}')
        return {
            'action': 'skipped',
            'instrument': 'options',
            'reasoning': f'No suitable {hedge_side.upper()} strike found',
        }

    strike = strike_info['strike']
    per_lot_delta = strike_info.get('delta_per_lot', 0.5 * LOT_SIZE_BTC)
    premium_at_strike = strike_info.get('premium', 0)

    # 2. Compute lots
    lot_result = compute_delta_hedge_lots(
        session, portfolio_delta,
        per_lot_delta=per_lot_delta,
        aggressiveness_override=aggressiveness,
    )

    lots = lot_result['lots']
    if lots <= 0:
        state['last_action'] = 'skipped'
        log.info(f'[{sid}] Delta engine: 0 lots computed — {lot_result["reasoning"]}')
        return {
            'action': 'skipped',
            'instrument': 'options',
            'lots': 0,
            'hedge_side': hedge_side,
            'reasoning': lot_result['reasoning'],
        }

    # 3. Gamma guard: check if selling these lots would breach gamma limits.
    # Bypassed for strategies where gamma guards are structurally inappropriate
    # (e.g. STRADDLE_WITH_ADJUSTMENT where ATM gamma is always elevated by design).
    if params.get('gamma_cap_enabled', True) and not bypass_gamma:
        gamma_data = session.get('_gamma_result', {})
        gamma_zone = gamma_data.get('gamma_zone', 'SAFE')
        if gamma_zone == 'DANGER':
            # In DANGER zone, reduce lots to half, don't fully block
            original_lots = lots
            lots = max(math.ceil(lots * 0.5), 1)
            log.warning(
                f'[{sid}] Delta engine: gamma DANGER zone — '
                f'lots reduced {original_lots} → {lots}'
            )

    # 4. Execute via MMMEngine.execute_adjustment()
    try:
        from .mmm_engine import MMMEngine

        engine = MMMEngine(executor=executor, initializer=initializer)

        # ce_now / pe_now are passed in from the heartbeat's local scope.
        # Allow fetch_premium_fn to refresh them if provided (e.g., in tests).
        if fetch_premium_fn:
            try:
                ce_active = session.get('ce', {}).get('active_strike', 0)
                pe_active = session.get('pe', {}).get('active_strike', 0)
                if ce_active:
                    ce_now = fetch_premium_fn(ce_active, 'call') or ce_now
                if pe_active:
                    pe_now = fetch_premium_fn(pe_active, 'put') or pe_now
            except Exception:
                pass

        adj_result = await engine.execute_adjustment(
            session=session,
            hedge_side=hedge_side,
            hedge_strike=strike,
            lots_to_sell=lots,
            ce_now=ce_now or 0,
            pe_now=pe_now or 0,
            adj_type='delta_hedge',
            fetch_premium_fn=fetch_premium_fn,
        )

        if adj_result.get('success'):
            now_str = datetime.now(timezone.utc).isoformat()
            filled_lots = adj_result.get('lots_sold', lots)
            state['last_hedge_time'] = now_str
            state['total_hedges'] = state.get('total_hedges', 0) + 1
            state['last_action'] = 'options_hedge'
            state['last_instrument'] = 'options'
            state['last_hedge_lots'] = filled_lots
            state['last_hedge_side'] = hedge_side
            state['last_hedge_strike'] = strike
            state['cumulative_lots_hedged'] = state.get('cumulative_lots_hedged', 0) + filled_lots

            log.info(
                f'[{sid}] Delta engine OPTIONS HEDGE: SELL {filled_lots} '
                f'{hedge_side.upper()} @ {strike:.0f} '
                f'(fill={adj_result.get("fill_price", 0):.2f}, '
                f'Δ_before={portfolio_delta:+.4f})'
            )

            return {
                'action': 'options_hedge',
                'instrument': 'options',
                'lots': filled_lots,
                'hedge_side': hedge_side,
                'strike': strike,
                'fill_price': adj_result.get('fill_price', 0),
                'premium_collected': adj_result.get('premium_collected', 0),
                'reasoning': lot_result['reasoning'],
                'success': True,
            }
        else:
            state['last_action'] = 'skipped'
            log.warning(
                f'[{sid}] Delta engine: options execution FAILED — '
                f'{adj_result.get("error", "unknown")}'
            )
            return {
                'action': 'skipped',
                'instrument': 'options',
                'lots': lots,
                'hedge_side': hedge_side,
                'reasoning': f'Execution failed: {adj_result.get("error", "unknown")}',
                'success': False,
            }

    except Exception as e:
        state['last_action'] = 'skipped'
        log.exception(f'[{sid}] Delta engine options execution error: {e}')
        return {
            'action': 'skipped',
            'instrument': 'options',
            'reasoning': f'Exception: {e}',
            'success': False,
        }


# =============================================================================
# Perp Mode Execution
# =============================================================================

async def _execute_via_perp(
    session: Dict,
    portfolio_delta: float,
    spot_price: float,
    executor=None,
    aggressiveness_mult: float = 1.0,
) -> Dict[str, Any]:
    """
    Execute delta hedge via perpetual futures.
    Routes to existing run_perp_hedge() with tighter thresholds.
    """
    sid = session.get('session_id', '???')
    state = _get_engine_state(session)
    params = session.get('params', {})

    try:
        from .mmm_perp_hedge import run_perp_hedge

        # Override perp params with delta engine's tighter thresholds
        # Temporarily tighten rebalance band for aggressive hedging
        original_band = params.get('perp_hedge_rebalance_band', 0.005)
        original_threshold = params.get('perp_hedge_delta_threshold', 0.02)

        # Use delta engine thresholds (typically tighter)
        engine_threshold = params.get('delta_drift_threshold', 0.01)
        engine_band = params.get('delta_engine_rebalance_band', 0.005)

        # Temporarily override for this execution
        params['perp_hedge_delta_threshold'] = engine_threshold
        params['perp_hedge_rebalance_band'] = engine_band

        # Ensure perp_hedge is enabled for this call
        was_perp_enabled = params.get('perp_hedge_enabled', False)
        params['perp_hedge_enabled'] = True

        try:
            result = await run_perp_hedge(
                session, executor, portfolio_delta, spot_price,
            )
        finally:
            # Restore original values
            params['perp_hedge_rebalance_band'] = original_band
            params['perp_hedge_delta_threshold'] = original_threshold
            params['perp_hedge_enabled'] = was_perp_enabled

        action = result.get('action', 'none')

        if action not in ('none', 'skipped'):
            now_str = datetime.now(timezone.utc).isoformat()
            state['last_hedge_time'] = now_str
            state['total_hedges'] = state.get('total_hedges', 0) + 1
            state['last_action'] = 'perp_hedge'
            state['last_instrument'] = 'perp'
            state['last_hedge_lots'] = result.get('lots_traded', 0)
            state['last_hedge_side'] = 'long' if action == 'buy' else 'short'

            log.info(
                f'[{sid}] Delta engine PERP HEDGE: {action.upper()} '
                f'{result.get("lots_traded", 0)} lots @ '
                f'{result.get("fill_price", 0):.2f} '
                f'(Δ_before={portfolio_delta:+.4f})'
            )

        return {
            'action': 'perp_hedge' if action not in ('none', 'skipped') else action,
            'instrument': 'perp',
            'lots': result.get('lots_traded', 0),
            'hedge_side': state.get('last_hedge_side'),
            'fill_price': result.get('fill_price', 0),
            'reasoning': result.get('reason', ''),
            'perp_result': result,
            'success': action not in ('none', 'skipped'),
        }

    except Exception as e:
        state['last_action'] = 'skipped'
        log.exception(f'[{sid}] Delta engine perp execution error: {e}')
        return {
            'action': 'skipped',
            'instrument': 'perp',
            'reasoning': f'Exception: {e}',
            'success': False,
        }


# =============================================================================
# Auto-Activation Helper
# =============================================================================

def check_auto_activation(
    session: Dict,
    minutes_to_expiry: Optional[float],
) -> bool:
    """
    Check if delta engine should be auto-activated based on time to expiry.

    Returns True if auto-activation fired this call (one-shot).
    """
    params = session.get('params', {})
    auto_mins = params.get('delta_engine_auto_minutes', 0)

    if auto_mins <= 0:
        return False

    if is_delta_engine_enabled(session):
        return False  # Already enabled

    if minutes_to_expiry is None:
        return False

    if minutes_to_expiry <= auto_mins:
        state = _get_engine_state(session)
        if not state.get('auto_activated'):
            params['delta_engine_enabled'] = True
            state['auto_activated'] = True
            state['auto_activated_at'] = datetime.now(timezone.utc).isoformat()
            log.info(
                f'[{session.get("session_id", "?")}] Delta engine AUTO-ACTIVATED: '
                f'{minutes_to_expiry:.0f} min to expiry <= {auto_mins} min threshold'
            )
            return True

    return False
