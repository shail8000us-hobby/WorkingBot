"""
Options Dashboard API - Unified Data Endpoint

Phase 2 Optimization: Single endpoint to fetch all dashboard data in one request.
Reduces 4 round-trips to 1, dramatically improving panel load time.

Endpoint:
- GET /api/options/dashboard - Get positions, pending orders, futures, status, and portfolio Greeks

Created: February 4, 2026 (Phase 2 Optimization)
"""

import sys
import time
import hashlib
import logging
import threading
from pathlib import Path
from flask import Blueprint, jsonify

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config, get_api_credentials
from webui.backend.sealed import sealed

log = logging.getLogger(__name__)

# Create blueprint
dashboard_bp = Blueprint('options_dashboard', __name__, url_prefix='/api/options')

# ---------------------------------------------------------------------------
# Dashboard cache — stale-while-revalidate pattern
# ---------------------------------------------------------------------------
# The frontend polls every 5s.  Without caching, each poll fires 5 exchange
# API calls (positions, pending orders, futures, status, margin) taking 3-8s.
# This cache ensures:
#   1. Cached (< FRESH_SECONDS): return immediately
#   2. Stale (FRESH < age < STALE): return cached + refresh in background
#   3. Expired (> STALE): block and fetch fresh
# ---------------------------------------------------------------------------
_dashboard_cache = {'data': None, 'time': 0}
_dashboard_lock = threading.Lock()
_refresh_in_progress = False
DASHBOARD_FRESH_SECONDS = 4.0   # Serve instantly from cache
DASHBOARD_STALE_SECONDS = 30.0  # Serve stale + trigger background refresh


@sealed
def calculate_portfolio_greeks(positions):
    """
    Calculate aggregated portfolio Greeks from positions.
    This offloads calculation from frontend to backend for better performance.

    SEALED — v2.0.0 — March 13, 2026
    Do not modify without UNSEAL command in AI_SEAL.md
    
    Args:
        positions: List of position dicts with greeks data
        
    Returns:
        dict: Aggregated Greeks {delta, gamma, theta, vega, btcDelta, ethDelta}
    """
    greeks = {
        'delta': 0.0,
        'gamma': 0.0,
        'theta': 0.0,
        'vega': 0.0,
        'btcDelta': 0.0,
        'ethDelta': 0.0,
        'count': 0
    }
    
    if not positions:
        return greeks
    
    for pos in positions:
        size = pos.get('size', 0)
        if not size:
            continue
            
        pos_greeks = pos.get('greeks', {})
        if not pos_greeks:
            continue
        
        # Per-contract Greeks
        per_contract_delta = float(pos_greeks.get('delta', 0))
        per_contract_gamma = float(pos_greeks.get('gamma', 0))
        per_contract_theta = float(pos_greeks.get('theta', 0))
        per_contract_vega = float(pos_greeks.get('vega', 0))
        
        # Aggregate position Greeks.
        # 1 lot = 0.001 BTC — API returns greeks per 1 BTC notional, so multiply by 0.001.
        # Theta/vega already divide by 1000 (equivalent to × 0.001) for USD conversion.
        LOT_MULT = 0.001
        greeks['delta'] += per_contract_delta * size * LOT_MULT
        greeks['gamma'] += per_contract_gamma * abs(size) * LOT_MULT
        greeks['theta'] += (per_contract_theta / 1000) * size
        greeks['vega'] += (per_contract_vega / 1000) * abs(size)
        greeks['count'] += 1

        # Separate delta by underlying for futures equivalent
        symbol = pos.get('product_symbol', '')
        parts = symbol.split('-')
        if len(parts) >= 2:
            underlying = parts[1]  # BTC or ETH
            delta_contribution = per_contract_delta * size * LOT_MULT

            if underlying == 'BTC':
                greeks['btcDelta'] += delta_contribution
            elif underlying == 'ETH':
                greeks['ethDelta'] += delta_contribution
    
    return greeks


@dashboard_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """
    Unified dashboard endpoint - returns all data in one response.
    
    Phase 2 Optimization: Replaces 4 separate API calls with 1.
    Phase 15: Stale-while-revalidate cache — first load is slow, all
    subsequent loads are instant (<5ms).
    
    Returns:
        {
            "success": true,
            "positions": [...],
            "pending_orders": [...],
            "futures_positions": [...],
            "status": {...},
            "portfolio_greeks": {...},
            "last_modified": timestamp,
            "response_time_ms": float
        }
    """
    global _dashboard_cache, _refresh_in_progress
    
    now = time.time()
    age = now - _dashboard_cache['time']
    cached = _dashboard_cache['data']
    
    # 1) FRESH cache — return instantly
    if cached is not None and age < DASHBOARD_FRESH_SECONDS:
        return jsonify(cached), 200
    
    # 2) STALE cache — return stale + trigger background refresh
    if cached is not None and age < DASHBOARD_STALE_SECONDS:
        if not _refresh_in_progress:
            _refresh_in_progress = True
            from flask import current_app
            app = current_app._get_current_object()
            t = threading.Thread(target=_refresh_dashboard_cache, args=(app,), daemon=True)
            t.start()
        return jsonify(cached), 200
    
    # 3) EXPIRED / first call — block and fetch
    return _fetch_dashboard_fresh()


def _refresh_dashboard_cache(app=None):
    """Background thread: refresh the dashboard cache."""
    global _refresh_in_progress
    try:
        if app is not None:
            # Use test_request_context to provide both app AND request context
            # (service functions call Flask route handlers that use request.args)
            with app.test_request_context('/api/options/dashboard'):
                _fetch_dashboard_fresh(is_background=True)
        else:
            _fetch_dashboard_fresh(is_background=True)
    except Exception as e:
        log.warning(f"Background dashboard refresh failed: {e}")
    finally:
        _refresh_in_progress = False


def _fetch_dashboard_fresh(is_background=False):
    """Fetch fresh dashboard data, update cache, return jsonify response."""
    global _dashboard_cache
    start_time = time.time()
    
    try:
        # ARCH-3 FIX: use service layer functions that return plain dicts
        from .dashboard_service import (
            fetch_options_positions_data,
            fetch_pending_orders_data,
            fetch_futures_positions_data,
            fetch_options_status_data,
            fetch_margin_data,
        )
        
        positions_data = fetch_options_positions_data()
        pending_data = fetch_pending_orders_data()
        futures_data = fetch_futures_positions_data()
        status_data = fetch_options_status_data()
        margin_data = fetch_margin_data()
        
        # Extract positions for Greeks calculation
        positions = positions_data.get('positions', [])

        # Calculate portfolio Greeks server-side (Phase 2 optimization)
        portfolio_greeks = calculate_portfolio_greeks(positions)

        # Phase 5 Optimization: Use content-based last_modified
        pos_fingerprint = '|'.join(
            f"{p.get('product_symbol','')},{p.get('size',0)},{p.get('best_bid',0)},{p.get('best_ask',0)},{p.get('unrealized_pnl',0)}"
            for p in positions
        )
        pending_orders_list = pending_data.get('orders', []) if isinstance(pending_data, dict) else []
        content_hash = hashlib.md5(
            (pos_fingerprint + str(len(pending_orders_list))).encode()
        ).hexdigest()

        response_time_ms = (time.time() - start_time) * 1000

        response = {
            'success': True,
            'positions': positions,
            'pending_orders': pending_orders_list,
            'futures_positions': futures_data.get('positions', []) if isinstance(futures_data, dict) else [],
            'status': status_data if isinstance(status_data, dict) else {},
            'portfolio_greeks': portfolio_greeks,
            'margin': margin_data,
            'last_modified': content_hash,
            'server_timestamp': int(time.time() * 1000),
            'response_time_ms': round(response_time_ms, 2),
            'optimization': 'phase_15_swr_cache'
        }
        
        # Update cache
        with _dashboard_lock:
            _dashboard_cache = {'data': response, 'time': time.time()}
        
        log.info(f"Dashboard data fetched in {response_time_ms:.0f}ms ({len(positions)} positions)")
        
        if is_background:
            return response  # background thread doesn't need jsonify
        return jsonify(response), 200
        
    except Exception as e:
        log.error(f"Dashboard fetch error: {e}", exc_info=True)
        
        # On error, extend stale cache lifetime if available
        if _dashboard_cache['data'] is not None:
            _dashboard_cache['time'] = time.time()  # Extend TTL
            if is_background:
                return _dashboard_cache['data']
            return jsonify(_dashboard_cache['data']), 200
        
        if is_background:
            return {'success': False, 'error': str(e)}
        return jsonify({
            'success': False,
            'error': str(e),
            'response_time_ms': (time.time() - start_time) * 1000
        }), 500
