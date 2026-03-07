"""
PnL Attribution by Greek Source  (Feature 4)
=============================================
Fully independent Blueprint — no changes to dashboard.py or sealed code.

Endpoint:
  GET  /api/options/pnl-attribution        Return current attribution vs baseline
  POST /api/options/pnl-attribution/reset  Force-reset the baseline snapshot

Attribution model:
  Delta PnL  = baseline_delta * dS
  Gamma PnL  = 0.5 * baseline_gamma * dS^2
  Theta PnL  = baseline_theta * (elapsed_hours / 24)
  Vega PnL   = baseline_vega * dIV_avg
  Residual   = total_change - sum(above)

All $ values in USD.
"""

import time
import threading
import logging
from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

pnl_attribution_bp = Blueprint('pnl_attribution', __name__, url_prefix='/api/options')

# ---------------------------------------------------------------------------
# Baseline snapshot (in-process state, resets on backend restart)
# ---------------------------------------------------------------------------
_baseline = None
_baseline_lock = threading.Lock()


def _take_snapshot(positions, portfolio_greeks, spot_price):
    """Build a baseline snapshot from current state."""
    iv_values = [
        (p.get('iv') or 0) * (1 if (p.get('iv') or 0) <= 5 else 0.01)  # normalise to decimal
        for p in positions if p.get('iv')
    ]
    iv_avg = sum(iv_values) / len(iv_values) if iv_values else 0.0

    total_pnl = sum(
        (float(p.get('unrealized_pnl') or 0) + float(p.get('partial_realized_pnl') or 0))
        for p in positions
    )
    return {
        'spot': spot_price,
        'iv_avg': iv_avg,
        'delta': float(portfolio_greeks.get('delta', 0)),
        'gamma': float(portfolio_greeks.get('gamma', 0)),
        'theta': float(portfolio_greeks.get('theta', 0)),
        'vega': float(portfolio_greeks.get('vega', 0)),
        'total_pnl': total_pnl,
        'timestamp': time.time(),
    }


def _compute_attribution(baseline, current_spot, current_iv_avg, current_total_pnl):
    # BTC contract multiplier: 1 lot = 0.001 BTC.
    # portfolio_greeks delta/gamma are sum(per_contract_greek * size) — raw contract
    # units.  Theta/vega are already divided by 1000 in calculate_portfolio_greeks().
    CONTRACT_MULT = 0.001

    dS = current_spot - baseline['spot']
    dIV = current_iv_avg - baseline['iv_avg']
    elapsed_hours = (time.time() - baseline['timestamp']) / 3600.0

    delta_pnl = baseline['delta'] * CONTRACT_MULT * dS
    gamma_pnl = 0.5 * baseline['gamma'] * CONTRACT_MULT * dS * dS
    theta_pnl = baseline['theta'] * (elapsed_hours / 24.0)
    vega_pnl = baseline['vega'] * dIV * 100  # vega per vol-pt; dIV in decimal
    total_change = current_total_pnl - baseline['total_pnl']
    residual = total_change - (delta_pnl + gamma_pnl + theta_pnl + vega_pnl)

    return {
        'delta_pnl': round(delta_pnl, 2),
        'gamma_pnl': round(gamma_pnl, 2),
        'theta_pnl': round(theta_pnl, 2),
        'vega_pnl': round(vega_pnl, 2),
        'residual_pnl': round(residual, 2),
        'total_change': round(total_change, 2),
        'spot_change': round(dS, 2),
        'iv_change_pts': round(dIV * 100, 2),  # in vol-points for display
        'elapsed_hours': round(elapsed_hours, 2),
        'baseline_spot': baseline['spot'],
        'baseline_iv_avg_pct': round(baseline['iv_avg'] * 100, 2),
        'baseline_timestamp': baseline['timestamp'],
    }


def _get_spot_price(positions):
    """
    Get BTC spot price from multiple sources in priority order:
    1. Delta price WebSocket (live feed, no REST API call)
    2. Position Greeks data (Delta Exchange includes spot in each position's greeks)
    3. In-process market price cache (populated by /api/market/spot-price calls)
    Returns 0.0 if all sources fail.
    """
    # 1. Delta price WebSocket — live feed, always available
    try:
        from webui.backend.services.delta_price_websocket import get_price_websocket
        ws = get_price_websocket()
        if ws and ws.is_connected():
            price = ws.get_price('BTC')
            if price and price > 0:
                return float(price)
    except Exception:
        pass

    # 2. Extract from position Greeks (Delta Exchange embeds spot in each position)
    for pos in positions:
        try:
            greeks = pos.get('greeks')
            if greeks and isinstance(greeks, dict):
                spot = float(greeks.get('spot', 0) or 0)
                if spot > 0:
                    return spot
        except Exception:
            continue

    # 3. In-process market cache
    try:
        from webui.backend.routes.market import _price_cache
        spot_entry = _price_cache.get('spot_BTC')
        if spot_entry:
            price = float(spot_entry[1])
            if price > 0:
                return price
    except Exception:
        pass

    return 0.0


def _get_current_state():
    """
    Read current state from the already-populated dashboard cache.
    This avoids making any additional API calls to Delta Exchange,
    preventing extra load that can trip the circuit breaker.
    """
    try:
        from .dashboard import _dashboard_cache, calculate_portfolio_greeks

        cached = _dashboard_cache.get('data')
        if not cached:
            return [], {}, 0.0, 0.0, 0.0

        positions = cached.get('positions', [])
        # Prefer pre-computed portfolio greeks from dashboard cache if available
        portfolio_greeks = cached.get('portfolio_greeks') or calculate_portfolio_greeks(positions)

        spot = _get_spot_price(positions)

        iv_values = [
            (p.get('iv') or 0) if (p.get('iv') or 0) <= 5 else (p.get('iv') or 0) / 100
            for p in positions if p.get('iv')
        ]
        iv_avg = sum(iv_values) / len(iv_values) if iv_values else 0.0

        total_pnl = sum(
            (float(p.get('unrealized_pnl') or 0) + float(p.get('partial_realized_pnl') or 0))
            for p in positions
        )
        return positions, portfolio_greeks, spot, iv_avg, total_pnl

    except Exception as e:
        log.error(f"PnL attribution: failed to fetch state: {e}", exc_info=True)
        return [], {}, 0.0, 0.0, 0.0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@pnl_attribution_bp.route('/pnl-attribution', methods=['GET'])
def get_pnl_attribution():
    """
    Return PnL attribution broken down by Greek source vs baseline.
    Auto-initialises baseline on first call.
    """
    global _baseline
    try:
        positions, portfolio_greeks, spot, iv_avg, total_pnl = _get_current_state()

        with _baseline_lock:
            if _baseline is None:
                if spot <= 0:
                    # Don't set baseline with zero spot — wait for price cache
                    return jsonify({
                        'success': True,
                        'status': 'waiting_for_spot',
                        'attribution': {
                            'delta_pnl': 0.0, 'gamma_pnl': 0.0, 'theta_pnl': 0.0,
                            'vega_pnl': 0.0, 'residual_pnl': 0.0, 'total_change': 0.0,
                            'spot_change': 0.0, 'iv_change_pts': 0.0, 'elapsed_hours': 0.0,
                            'baseline_spot': 0, 'baseline_iv_avg_pct': 0,
                            'baseline_timestamp': time.time(),
                        },
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    })
                # First call with valid spot — take snapshot and return zeros
                _baseline = _take_snapshot(positions, portfolio_greeks, spot)
                return jsonify({
                    'success': True,
                    'status': 'baseline_set',
                    'attribution': {
                        'delta_pnl': 0.0, 'gamma_pnl': 0.0, 'theta_pnl': 0.0,
                        'vega_pnl': 0.0, 'residual_pnl': 0.0, 'total_change': 0.0,
                        'spot_change': 0.0, 'iv_change_pts': 0.0, 'elapsed_hours': 0.0,
                        'baseline_spot': spot,
                        'baseline_iv_avg_pct': round(iv_avg * 100, 2),
                        'baseline_timestamp': _baseline['timestamp'],
                    },
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                })
            # Auto-heal: if baseline was taken with spot=0 (e.g. race condition or
            # reset called before positions were ready), silently refresh it now.
            if _baseline.get('spot', 0) <= 0 and spot > 0:
                log.info(f"PnL attribution: auto-healing baseline — spot was 0, now {spot}")
                _baseline = _take_snapshot(positions, portfolio_greeks, spot)
                return jsonify({
                    'success': True,
                    'status': 'baseline_set',
                    'attribution': {
                        'delta_pnl': 0.0, 'gamma_pnl': 0.0, 'theta_pnl': 0.0,
                        'vega_pnl': 0.0, 'residual_pnl': 0.0, 'total_change': 0.0,
                        'spot_change': 0.0, 'iv_change_pts': 0.0, 'elapsed_hours': 0.0,
                        'baseline_spot': spot,
                        'baseline_iv_avg_pct': round(iv_avg * 100, 2),
                        'baseline_timestamp': _baseline['timestamp'],
                    },
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                })
            attribution = _compute_attribution(_baseline, spot, iv_avg, total_pnl)

        return jsonify({
            'success': True,
            'status': 'ok',
            'attribution': attribution,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        })

    except Exception as e:
        log.error(f"Error computing PnL attribution: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@pnl_attribution_bp.route('/pnl-attribution/reset', methods=['POST'])
def reset_pnl_attribution():
    """Manually reset the PnL attribution baseline to current state."""
    global _baseline
    try:
        positions, portfolio_greeks, spot, iv_avg, total_pnl = _get_current_state()
        if spot <= 0:
            return jsonify({'success': False, 'error': 'Cannot reset baseline: spot price unavailable'}), 400
        with _baseline_lock:
            _baseline = _take_snapshot(positions, portfolio_greeks, spot)
        return jsonify({
            'success': True,
            'message': 'Baseline reset',
            'new_baseline': {
                'spot': spot,
                'iv_avg_pct': round(iv_avg * 100, 2),
                'timestamp': _baseline['timestamp'],
            },
        })
    except Exception as e:
        log.error(f"Error resetting PnL attribution baseline: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
