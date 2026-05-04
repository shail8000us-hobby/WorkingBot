"""
Positions Routes Blueprint

This module handles all API routes related to position retrieval and management.

Routes:
- GET  /api/positions - Get current positions with liquidation info and Greeks
- POST /api/positions/resync - Manually resync positions from reconciliation
- GET  /api/state - Get current bot runtime state

Dependencies:
- bot.api.delta_client (DeltaClient)
- bot.state.store (position/state loading)
- bot.reconciliation (resync)
- utils.response_helpers (numpy conversion)

Refactored from app.py (8,850 lines)
Date: 2025-10-31
Enhanced with circuit breaker: 2025-11-12
Updated for v6.0 instance support: 2026-01-01
Phase 3 caching added: 2026-03-01
"""

import os
import sys
import copy
import json
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request

# Import cache
try:
    from webui.backend.cache import cache, CACHE_TIMEOUTS, make_cache_key
except ImportError:
    from cache import cache, CACHE_TIMEOUTS, make_cache_key


def get_instance_from_request():
    """
    Extract instance from request, supporting both v5.0 and v6.0 formats.
    
    Returns:
        tuple: (instance_name, symbol, mode)
               instance_name: "BTCUSD_LONG" format
               symbol: "BTCUSD"
               mode: "LONG"
    """
    # v6.0: Check for instance parameter first
    instance = request.args.get('instance')
    if instance:
        parts = instance.rsplit('_', 1)
        if len(parts) == 2:
            return instance, parts[0], parts[1]
        return instance, instance, 'LONG'  # Fallback for malformed instance
    
    # v5.0 backward compat: symbol + mode separate params
    symbol = request.args.get('symbol', 'BTCUSD')
    mode = request.args.get('mode', 'LONG')
    return f"{symbol}_{mode}", symbol, mode


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config

def get_config_value(yaml_path: str, env_var: str = None, default: any = None):
    """Get config value from YAML using dot notation"""
    try:
        cfg = get_config()
        value = cfg
        for key in yaml_path.split('.'):
            value = getattr(value, key)
        return value
    except (AttributeError, KeyError):
        return default

try:
    from webui.backend.utils.response_helpers import convert_numpy_types
    NUMPY_CONVERSION_AVAILABLE = True
except ImportError:
    NUMPY_CONVERSION_AVAILABLE = False
    def convert_numpy_types(obj):
        return obj

# Import circuit breakers
from webui.backend.utils.circuit_breaker import delta_api_breaker, bot_file_breaker
from webui.backend.sealed import sealed

log = logging.getLogger(__name__)

# Create blueprint
positions_bp = Blueprint('positions', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
POSITIONS_FILE = BASE_DIR / "bot" / "reports" / "positions.json"
STATE_FILE = BASE_DIR / "bot" / "reports" / "state.json"

# Positions cache (TTL-based to avoid hammering Delta Exchange API)
_positions_cache = {
    'data': None,
    'timestamp': 0,
    'lock': threading.Lock()
}
_POSITIONS_CACHE_TTL = 15.0  # 15 seconds - avoids hammering Delta API

# SWR cache for the /api/positions route (stale-while-revalidate)
_route_cache = {
    'data': None,        # Cached JSON response dict
    'timestamp': 0,
    'lock': threading.Lock()
}
_ROUTE_FRESH_SECONDS = 5.0    # Return instantly if < 5s old
_ROUTE_STALE_SECONDS = 60.0   # Return stale + background refresh if < 60s old
_route_refresh_in_progress = False

# Margin cache (avoid fetching wallet on every poll)
_margin_cache = {
    'data': None,
    'timestamp': 0,
}
_MARGIN_CACHE_TTL = 15.0  # 15 seconds

# Thread pool for concurrent API calls (reuse across requests)
_ticker_pool = ThreadPoolExecutor(max_workers=8)

# ============================================================================
# Helper Functions
# ============================================================================

def _filter_positions_by_symbol(positions_data, filter_symbol):
    """
    Filter positions data by symbol (v5.0 multi-symbol support)
    
    Args:
        positions_data: Dict with 'positions' list and 'summary' dict
        filter_symbol: Symbol name to filter by (e.g., "BTCUSD")
    
    Returns:
        Filtered positions_data with recalculated summary
    """
    if not positions_data or not filter_symbol:
        return positions_data
    
    # Filter positions list
    all_positions = positions_data.get('positions', [])
    filtered_positions = [
        pos for pos in all_positions 
        if pos.get('symbol', '').startswith(filter_symbol)
    ]
    
    # Recalculate summary for filtered positions
    total_pnl = sum(pos.get('unrealized_pnl', 0) for pos in filtered_positions)
    total_delta = sum(pos.get('delta', 0) for pos in filtered_positions)
    total_vega = sum(pos.get('vega', 0) for pos in filtered_positions)
    total_theta = sum(pos.get('theta', 0) for pos in filtered_positions)
    total_notional = sum(pos.get('notional_deployed', 0) for pos in filtered_positions)
    
    usd_to_inr_rate = 85  # Default, should come from config
    try:
        usd_to_inr_rate = float(get_config_value('market.usd_to_inr_rate', 'USD_TO_INR_RATE', 85))
    except:
        pass
    
    # Build filtered response
    filtered_data = {
        'positions': filtered_positions,
        'summary': {
            'total_positions': len(filtered_positions),
            'total_pnl': round(total_pnl, 2),
            'total_pnl_usd': round(total_pnl, 2),
            'total_pnl_inr': round(total_pnl * usd_to_inr_rate, 2),
            'portfolio_delta': round(total_delta, 2),
            'portfolio_vega': round(total_vega, 2),
            'portfolio_theta': round(total_theta, 2),
            'total_notional_deployed': round(total_notional, 2),
            'data_source': positions_data.get('summary', {}).get('data_source', 'unknown'),
            'filtered_by_symbol': filter_symbol,  # v5.0: Indicate filtering applied
            'total_all_symbols': len(all_positions),  # v5.0: Total before filtering
            # ✅ FIX: Preserve account-level margin fields when filtering by symbol
            'blocked_margin_usd': positions_data.get('summary', {}).get('blocked_margin_usd', 0),
            'blocked_margin_inr': positions_data.get('summary', {}).get('blocked_margin_inr', 0),
        }
    }
    
    return filtered_data

# ============================================================================
# Route Handlers
# ============================================================================

@positions_bp.route('/api/positions', methods=['GET'])
def get_positions():
    """
    Get current positions with liquidation info and Greeks.
    Uses Stale-While-Revalidate (SWR) caching for instant responses.
    """
    global _route_refresh_in_progress
    
    now = time.time()
    age = now - _route_cache['timestamp']
    
    # FRESH: return cached data instantly
    if _route_cache['data'] is not None and age < _ROUTE_FRESH_SECONDS:
        return jsonify(_route_cache['data']), 200
    
    # STALE: return cached data + trigger background refresh
    if _route_cache['data'] is not None and age < _ROUTE_STALE_SECONDS:
        if not _route_refresh_in_progress:
            _route_refresh_in_progress = True
            # Get current request args for background thread
            req_args = dict(request.args)
            from flask import current_app
            app = current_app._get_current_object()
            t = threading.Thread(target=_refresh_positions_cache, args=(app, req_args), daemon=True)
            t.start()
        return jsonify(_route_cache['data']), 200
    
    # EXPIRED: fetch fresh (blocking)
    result = _fetch_positions_fresh()
    if result:
        return jsonify(result), 200
    
    return jsonify({'positions': [], 'summary': {'total_positions': 0, 'data_source': 'none'}}), 200


def _fetch_positions_fresh():
    """Fetch fresh positions data and update the SWR route cache."""
    global _route_refresh_in_progress
    try:
        # Get filter params from request context (if available)
        try:
            instance_name, filter_symbol, filter_mode = get_instance_from_request()
        except RuntimeError:
            filter_symbol = None
        
        # Fetch margin (with its own cache)
        margin_data = _fetch_blocked_margin_cached()
        
        # Try strategies in order
        positions_data = _get_positions_from_delta()
        if not positions_data:
            positions_data = _get_positions_from_file()
        if not positions_data:
            positions_data = _get_positions_from_guardian()
        
        if positions_data:
            positions_data['summary'].update(margin_data)
            if filter_symbol:
                positions_data = _filter_positions_by_symbol(positions_data, filter_symbol)
            
            # Update SWR cache
            with _route_cache['lock']:
                _route_cache['data'] = positions_data
                _route_cache['timestamp'] = time.time()
            
            _route_refresh_in_progress = False
            return positions_data
        
        _route_refresh_in_progress = False
        return None
    except Exception as e:
        log.error(f"Error fetching positions: {e}")
        _route_refresh_in_progress = False
        # Extend stale cache on error
        if _route_cache['data'] is not None:
            _route_cache['timestamp'] = time.time() - _ROUTE_FRESH_SECONDS - 1
        return None


def _refresh_positions_cache(app, req_args):
    """Background thread to refresh positions cache (SWR pattern)."""
    global _route_refresh_in_progress
    try:
        with app.test_request_context('/api/positions', query_string=req_args):
            _fetch_positions_fresh()
    except Exception as e:
        log.error(f"Background positions refresh failed: {e}")
        _route_refresh_in_progress = False


def _fetch_blocked_margin_cached():
    """Fetch blocked margin with TTL cache to avoid extra API call on every poll."""
    now = time.time()
    if _margin_cache['data'] is not None and (now - _margin_cache['timestamp']) < _MARGIN_CACHE_TTL:
        return _margin_cache['data']
    
    data = _fetch_blocked_margin()
    _margin_cache['data'] = data
    _margin_cache['timestamp'] = time.time()
    return data


@positions_bp.route('/api/positions/resync', methods=['POST'])
def api_resync_positions():
    """
    Manually resync positions from reconciliation engine
    
    Forces a refresh of position data from the exchange.
    
    Returns:
        JSON response with success status
    
    Example:
        POST /api/positions/resync
        Response: {"success": true, "message": "Positions resynced successfully"}
    """
    try:
        ok, msg = _resync_positions_from_reconciliation()
        status = 200 if ok else 500
        return jsonify({
            'success': ok,
            'message': msg
        }), status
        
    except Exception as e:
        log.error(f"Error resyncing positions: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@positions_bp.route('/api/state', methods=['GET'])
def get_state():
    """
    Get current bot runtime state
    
    Returns the bot's current runtime state including open positions,
    pending orders, and internal state.
    
    Returns:
        JSON response with bot state
    
    Example:
        GET /api/state
        Response: {
            "open_positions": [...],
            "pending_buy": {...},
            "last_update": "2025-10-31T14:30:00"
        }
    """
    try:
        data = _load_state_data()
        return jsonify(data or {}), 200
        
    except Exception as e:
        log.error(f"Error getting state: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Helper Functions - Position Data Sources
# ============================================================================

def _fetch_ticker_greeks(delta_client, product_symbol):
    """Fetch Greeks for a single option symbol. Used by thread pool."""
    try:
        ticker_response = delta_client._req('GET', f'/v2/tickers/{product_symbol}')
        if ticker_response.get('success'):
            ticker_data = ticker_response.get('result', {})
            greeks = ticker_data.get('greeks', {})
            if greeks:
                return product_symbol, {
                    'delta': float(greeks.get('delta', 0)),
                    'vega': float(greeks.get('vega', 0)),
                    'theta': float(greeks.get('theta', 0)),
                    'gamma': float(greeks.get('gamma', 0)),
                }
    except Exception as e:
        log.debug(f"Could not fetch Greeks for {product_symbol}: {e}")
    return product_symbol, {'delta': 0, 'vega': 0, 'theta': 0, 'gamma': 0}


def _get_positions_from_delta():
    """
    Get ALL positions directly from Delta Exchange API (with circuit breaker protection)

    Fetches COMPLETE portfolio including:
    - Futures positions (BTCUSD, ETHUSD, etc.)
    - Options positions (calls and puts)
    - All underlying assets

    Returns position data with Greeks (delta, vega, theta) and PnL.
    Greeks are fetched from ticker endpoint as they're not available in positions endpoint.

    Performance: Uses TTL cache (5s) + concurrent Greeks fetching via thread pool.
    Before: N+1 sequential API calls (5-11s for 10 positions)
    After:  1 positions call + parallel Greeks calls (~500ms-1s total)
    """
    # Check cache first (avoids hammering Delta API on every frontend poll)
    now = time.time()
    with _positions_cache['lock']:
        if _positions_cache['data'] is not None and (now - _positions_cache['timestamp']) < _POSITIONS_CACHE_TTL:
            log.debug("Returning cached positions data")
            return copy.deepcopy(_positions_cache['data'])

    try:
        from bot.api.delta_client import DeltaClient

        def _fetch_from_delta():
            """Inner function wrapped by circuit breaker"""
            delta_client = DeltaClient()
            # Use /v2/positions/margined to get ALL positions (futures + options)
            response = delta_client._req('GET', '/v2/positions/margined')

            # Check for circuit breaker fallback: _req returns {"success": False, ...} when CB is open
            # Normal API responses don't have 'success' field; only check explicit failure
            if isinstance(response, dict) and response.get('success') == False:
                raise Exception("Delta API returned unsuccessful response")

            return response

        # Call through circuit breaker (fail fast if Delta API is down)
        response = delta_api_breaker.call(_fetch_from_delta, fallback=None)

        if not response:
            log.warning("Delta API circuit breaker open - falling back to other sources")
            return None

        positions_data = []
        total_pnl = 0
        total_delta = 0
        total_vega = 0
        total_theta = 0
        total_notional_deployed = 0
        usd_to_inr_rate = float(get_config_value('market.usd_to_inr_rate', 'USD_TO_INR_RATE', 85))

        pos_list = response.get('result', [])
        log.info(f"Fetched {len(pos_list)} positions from Delta Exchange (futures + options)")

        # Separate options that need Greeks fetching
        delta_client = DeltaClient()
        option_symbols = []
        for pos_data in pos_list:
            size = int(pos_data.get('size', 0))
            if size == 0:
                continue
            product_symbol = pos_data.get('product_symbol', 'UNKNOWN')
            if any(x in product_symbol for x in ['C-', 'P-']):
                option_symbols.append(product_symbol)

        # Fetch ALL option Greeks concurrently (instead of N sequential calls)
        greeks_map = {}
        if option_symbols:
            unique_symbols = list(set(option_symbols))
            log.info(f"Fetching Greeks for {len(unique_symbols)} options concurrently")
            futures = {
                _ticker_pool.submit(_fetch_ticker_greeks, delta_client, sym): sym
                for sym in unique_symbols
            }
            for future in as_completed(futures, timeout=10):
                try:
                    symbol, greeks = future.result()
                    greeks_map[symbol] = greeks
                except Exception as e:
                    log.debug(f"Greeks fetch failed for {futures[future]}: {e}")

        for pos_data in pos_list:
            size = int(pos_data.get('size', 0))
            if size == 0:
                continue

            entry_price = float(pos_data.get('entry_price', 0))
            mark_price = float(pos_data.get('mark_price', 0))
            product_symbol = pos_data.get('product_symbol', 'UNKNOWN')
            product_id = int(pos_data.get('product_id', 0))

            # Calculate PnL: (Mark - Entry) x Size x Contract Multiplier
            # Contract sizes per Delta Exchange India:
            # - BTC: 1 lot = 0.001 BTC (multiplier = 0.001)
            # - ETH: 1 lot = 0.01 ETH (multiplier = 0.01)
            if 'ETH' in product_symbol.upper():
                CONTRACT_MULTIPLIER = 0.01
            else:
                CONTRACT_MULTIPLIER = 0.001  # BTC and other assets default to 0.001
            unrealized_pnl = (mark_price - entry_price) * size * CONTRACT_MULTIPLIER

            # Determine type
            position_type = "OPTION" if any(x in product_symbol for x in ['C-', 'P-']) else "FUTURE"

            # Get Greeks (from concurrent fetch for options, defaults for futures)
            if position_type == "FUTURE":
                delta = float(size)
                vega = 0
                theta = 0
                gamma = 0
            else:
                g = greeks_map.get(product_symbol, {})
                delta = g.get('delta', 0)
                vega = g.get('vega', 0)
                theta = g.get('theta', 0)
                gamma = g.get('gamma', 0)

            # Notional
            notional_usd = abs(size * mark_price * CONTRACT_MULTIPLIER)
            notional_deployed = notional_usd * usd_to_inr_rate

            # Calculate position-level Greeks for summary (multiply per-contract by size)
            #
            # CRITICAL THETA LOGIC (Fixed Jan 14, 2026 - v2):
            # - Delta Exchange returns theta as "daily P&L contribution from time decay"
            # - Theta convention: POSITIVE = earning money, NEGATIVE = losing money
            # - For LONG positions (size > 0): theta is NEGATIVE (option decays, you lose)
            # - For SHORT positions (size < 0): theta is POSITIVE (option decays, you earn)
            #
            # Example:
            # - SHORT Call: size = -1, per-contract theta = +0.31
            # - position theta = +0.31 * (-1) = -0.31 -- WRONG!
            # - We want: position theta = +0.31 (you earn $0.31/day)
            #
            # The cashflow display shows POSITIVE values (0.36 USD, 0.26 USD) for short positions
            # This means Delta API already returns theta from seller's perspective
            # So we should just multiply by abs(size) to get total earning rate
            #
            pos_delta = delta * size  # Delta direction same as position
            pos_gamma = gamma * abs(size)  # Gamma always positive magnitude
            pos_theta = theta * abs(size)  # Theta * absolute size (preserve sign from API)
            pos_vega = vega * abs(size)  # Vega always positive magnitude

            positions_data.append({
                'symbol': product_symbol,
                'product_id': product_id,
                'type': position_type,
                'size': size,
                'side': 'long' if size > 0 else 'short',
                'entry_price': entry_price,
                'current_price': mark_price,
                'unrealized_pnl': unrealized_pnl,
                'delta': pos_delta,
                'vega': pos_vega,
                'theta': pos_theta,
                'gamma': pos_gamma,
                # Also include per-contract Greeks for frontend calculations
                'greeks': {
                    'delta': delta,
                    'vega': vega,
                    'theta': theta,
                    'gamma': gamma
                },
                'notional_deployed': round(notional_deployed, 2),
                'exchange': 'delta_exchange'
            })

            total_pnl += unrealized_pnl
            total_delta += pos_delta  # Use position-level delta
            total_vega += pos_vega    # Use position-level vega
            total_theta += pos_theta  # Use position-level theta
            total_notional_deployed += notional_deployed

        # NOTE: blocked_margin is fetched centrally in get_positions() and injected into summary
        # This ensures fresh margin data even when positions are cached
        result = {
            'positions': positions_data,
            'summary': {
                'total_positions': len(positions_data),
                'total_pnl': round(total_pnl, 2),
                'total_pnl_usd': round(total_pnl, 2),
                'total_pnl_inr': round(total_pnl * usd_to_inr_rate, 2),
                'portfolio_delta': round(total_delta, 2),
                'portfolio_vega': round(total_vega, 2),
                'portfolio_theta': round(total_theta, 2),
                'total_notional_deployed': round(total_notional_deployed, 2),
                'blocked_margin_usd': 0.0,  # Will be overwritten by get_positions()
                'blocked_margin_inr': 0.0,  # Will be overwritten by get_positions()
                'data_source': 'delta_exchange'
            }
        }

        # Update cache
        with _positions_cache['lock']:
            _positions_cache['data'] = result
            _positions_cache['timestamp'] = time.time()

        return result

    except Exception as e:
        log.error(f"Delta API positions fetch failed: {e}")
        return None


def _fetch_blocked_margin():
    """
    Fetch account-level blocked_margin from Delta Exchange wallet API.
    Uses the same DeltaClient._req() approach that works in liquidation.py.
    
    Returns:
        dict with keys: blocked_margin_usd, blocked_margin_inr
    """
    try:
        from bot.api.delta_client import DeltaClient
        delta_client = DeltaClient()
        wallet_response = delta_client._req('GET', '/v2/wallet/balances')
        
        if wallet_response and wallet_response.get('success'):
            wallets = wallet_response.get('result', [])
            # Find USD wallet specifically
            wallet_data = None
            for wallet in wallets:
                if wallet.get('asset_symbol') == 'USD':
                    wallet_data = wallet
                    break
            if not wallet_data and wallets:
                wallet_data = wallets[0]
            
            if wallet_data:
                blocked_margin_usd = float(wallet_data.get('blocked_margin', 0) or 0)
                if blocked_margin_usd == 0:
                    blocked_margin_usd = float(wallet_data.get('portfolio_margin', 0) or 0)
                if blocked_margin_usd == 0:
                    blocked_margin_usd = float(wallet_data.get('order_margin', 0) or 0) + float(wallet_data.get('position_margin', 0) or 0)
                
                usd_to_inr_rate = float(get_config_value('market.usd_to_inr_rate', 'USD_TO_INR_RATE', 85))
                return {
                    'blocked_margin_usd': round(blocked_margin_usd, 2),
                    'blocked_margin_inr': round(blocked_margin_usd * usd_to_inr_rate, 2)
                }
    except Exception as e:
        log.error(f"Failed to fetch blocked_margin from wallet API: {e}")
    
    return {'blocked_margin_usd': 0.0, 'blocked_margin_inr': 0.0}


def _get_positions_from_file():
    """Get positions from bot's positions file"""
    try:
        from webui.backend.utils.process_helpers import is_bot_running
        
        # Only use file if bot is running
        if not is_bot_running():
            return None
        
        if not POSITIONS_FILE.exists():
            return None
        
        import json
        with open(POSITIONS_FILE, 'r') as f:
            raw_positions = json.load(f)
        
        if not raw_positions or not raw_positions.get('positions'):
            return None
        
        data = copy.deepcopy(raw_positions)
        usd_to_inr_rate = float(get_config_value('market.usd_to_inr_rate', 'USD_TO_INR_RATE', 85))
        total_notional_deployed = 0
        
        for position in data['positions']:
            notional_slab = position.get('notional', 0)
            notional_deployed = notional_slab * usd_to_inr_rate
            position['notional_deployed'] = round(notional_deployed, 2)
            total_notional_deployed += notional_deployed
            
            # Add default Greek values if not present
            if 'delta' not in position:
                position['delta'] = 0
            if 'vega' not in position:
                position['vega'] = 0
            if 'theta' not in position:
                position['theta'] = 0
        
        if 'summary' not in data:
            data['summary'] = {}
        
        # NOTE: blocked_margin is fetched centrally in get_positions() and injected into summary
        usd_to_inr_rate = float(get_config_value('market.usd_to_inr_rate', 'USD_TO_INR_RATE', 85))
        
        data['summary']['total_notional_deployed'] = round(total_notional_deployed, 2)
        data['summary']['portfolio_delta'] = sum(p.get('delta', 0) for p in data['positions'])
        data['summary']['portfolio_vega'] = sum(p.get('vega', 0) for p in data['positions'])
        data['summary']['portfolio_theta'] = sum(p.get('theta', 0) for p in data['positions'])
        data['summary']['blocked_margin_usd'] = 0.0  # Will be overwritten by get_positions()
        data['summary']['blocked_margin_inr'] = 0.0    # Will be overwritten by get_positions()
        data['summary']['data_source'] = 'positions_file'
        
        return data
        
    except Exception as e:
        log.debug(f"Positions file read failed: {e}")
        return None


def _get_positions_from_guardian():
    """Get positions from Guardian health data (fallback)"""
    try:
        from webui.backend.utils.process_helpers import is_bot_running
        
        if not is_bot_running():
            return None
        
        # Try to get guardian health
        health_file = BASE_DIR / '.guardian_health.json'
        if not health_file.exists():
            return None
        
        import json
        with open(health_file, 'r') as f:
            health = json.load(f)
        
        if health.get('status') != 'ok':
            return None
        
        monitoring = health.get('monitoring', {})
        position_count = monitoring.get('position_count', 0)
        
        if position_count == 0:
            return None
        
        total_pnl_inr = monitoring.get('total_pnl_inr', 0.0)
        total_pnl_usd = monitoring.get('total_pnl_usd', 0.0)
        usd_to_inr_rate = float(get_config_value('market.usd_to_inr_rate', 'USD_TO_INR_RATE', 85))
        notional_slab = monitoring.get('total_notional_usd', 0)
        notional_deployed = notional_slab * usd_to_inr_rate
        
        return {
            'positions': [{
                'id': 'guardian_monitored',
                'size': position_count,
                'entry_price': 0,
                'current_price': monitoring.get('last_price', 0),
                'pnl_inr': total_pnl_inr,
                'pnl_usd': total_pnl_usd,
                'notional': notional_slab,
                'notional_deployed': round(notional_deployed, 2)
            }],
            'summary': {
                'total_positions': position_count,
                'total_pnl_usd': total_pnl_usd,
                'total_pnl_inr': total_pnl_inr,
                'total_notional_deployed': round(notional_deployed, 2),
                'blocked_margin_usd': 0.0,  # Will be overwritten by get_positions()
                'blocked_margin_inr': 0.0,  # Will be overwritten by get_positions()
                'data_source': 'guardian'
            },
            'source': 'guardian'
        }
        
    except Exception as e:
        log.debug(f"Guardian positions fetch failed: {e}")
        return None


def _load_state_data():
    """Load bot runtime state from state file"""
    try:
        if not STATE_FILE.exists():
            return {}
        
        import json
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
            
    except Exception as e:
        log.error(f"Error loading state: {e}")
        return {}


def _resync_positions_from_reconciliation():
    """Resync positions from reconciliation engine"""
    try:
        from bot.reconciliation import get_reconciliation_engine
        
        engine = get_reconciliation_engine()
        if not engine:
            return False, "Reconciliation engine not available"
        
        # Get latest open positions from exchange
        open_positions = engine.get_open_positions()
        
        # Save to positions file
        import json
        positions_data = {
            'positions': open_positions,
            'last_update': str(datetime.utcnow()),
            'source': 'reconciliation'
        }
        
        with open(POSITIONS_FILE, 'w') as f:
            json.dump(positions_data, f, indent=2)
        
        return True, f"Resynced {len(open_positions)} positions successfully"
        
    except Exception as e:
        log.error(f"Resync failed: {e}")
        return False, str(e)


# ============================================================================
# WebUI v3 Additional Endpoints (JAN 2026)
# ============================================================================

@positions_bp.route('/api/positions/analysis', methods=['GET'])
def get_position_analysis():
    """Get position analysis and distribution for WebUI v3"""
    try:
        import sqlite3
        conn = sqlite3.connect('trading_bot.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get open positions
        cursor.execute('''
            SELECT symbol, mode, COUNT(*) as count, 
                   SUM(quantity) as total_qty,
                   AVG(entry_price) as avg_entry,
                   SUM(unrealized_pnl) as total_pnl
            FROM positions 
            WHERE status = 'OPEN'
            GROUP BY symbol, mode
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        analysis = {
            'by_symbol': {},
            'by_mode': {},
            'total_positions': 0,
            'total_unrealized_pnl': 0,
            'distribution': []
        }
        
        for row in rows:
            symbol = row['symbol']
            mode = row['mode']
            count = row['count']
            total_pnl = float(row['total_pnl']) if row['total_pnl'] else 0
            
            # By symbol
            if symbol not in analysis['by_symbol']:
                analysis['by_symbol'][symbol] = {
                    'count': 0,
                    'total_pnl': 0,
                    'avg_entry': 0
                }
            analysis['by_symbol'][symbol]['count'] += count
            analysis['by_symbol'][symbol]['total_pnl'] += total_pnl
            analysis['by_symbol'][symbol]['avg_entry'] = float(row['avg_entry']) if row['avg_entry'] else 0
            
            # By mode
            if mode not in analysis['by_mode']:
                analysis['by_mode'][mode] = {
                    'count': 0,
                    'total_pnl': 0
                }
            analysis['by_mode'][mode]['count'] += count
            analysis['by_mode'][mode]['total_pnl'] += total_pnl
            
            analysis['total_positions'] += count
            analysis['total_unrealized_pnl'] += total_pnl
            
            # Distribution
            analysis['distribution'].append({
                'symbol': symbol,
                'mode': mode,
                'count': count,
                'percentage': 0  # Will calculate after
            })
        
        # Calculate percentages
        if analysis['total_positions'] > 0:
            for item in analysis['distribution']:
                item['percentage'] = (item['count'] / analysis['total_positions']) * 100
        
        return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@positions_bp.route('/api/positions/pending-orders', methods=['GET'])
@sealed
def get_pending_orders():
    """
    Get all pending/open orders from Delta Exchange

    SEALED — v1.0.0 — March 4, 2026
    Do not modify without UNSEAL command in AI_SEAL.md
    
    Returns:
        {
            "success": true,
            "orders": [
                {
                    "id": 12345,
                    "symbol": "C-BTC-100000-140126",
                    "side": "buy",
                    "size": 1,
                    "price": 2500.0,
                    "order_type": "limit_order",
                    "state": "open",
                    "created_at": "2026-01-14T10:30:00Z",
                    "product_id": 123456
                }
            ],
            "count": 1
        }
    """
    try:
        from bot.api.delta_client import DeltaClient
        
        def _fetch_pending_orders():
            """Inner function wrapped by circuit breaker"""
            delta_client = DeltaClient()
            # Get all open orders (no product_id filter = all products)
            response = delta_client._req('GET', '/v2/orders', params={'state': 'open'})

            # Check for circuit breaker fallback: _req returns {"success": False, ...} when CB is open
            # Normal API responses don't have 'success' field; only check explicit failure
            if isinstance(response, dict) and response.get('success') == False:
                raise Exception("Delta API returned unsuccessful response")

            return response
        
        # Call through circuit breaker
        response = delta_api_breaker.call(_fetch_pending_orders, fallback=None)
        
        if not response:
            log.warning("Delta API circuit breaker open - cannot fetch pending orders")
            return jsonify({
                'success': False,
                'error': 'Delta API temporarily unavailable',
                'orders': [],
                'count': 0
            }), 503
        
        orders_list = response.get('result', [])
        
        # Format orders for frontend
        formatted_orders = []
        for order in orders_list:
            # Handle None values for limit_price (market orders, stop orders, etc.)
            limit_price = order.get('limit_price')
            price_value = float(limit_price) if limit_price is not None else 0.0
            
            formatted_orders.append({
                'id': order.get('id'),
                'symbol': order.get('product', {}).get('symbol', 'UNKNOWN'),
                'product_id': order.get('product_id'),
                'side': order.get('side'),
                'size': order.get('size'),
                'unfilled_size': order.get('unfilled_size'),
                'price': price_value,
                'order_type': order.get('order_type'),
                'state': order.get('state'),
                'created_at': order.get('created_at'),
                'client_order_id': order.get('client_order_id'),
            })
        
        log.info(f"📊 Fetched {len(formatted_orders)} pending orders from Delta Exchange")
        
        return jsonify({
            'success': True,
            'orders': formatted_orders,
            'count': len(formatted_orders)
        }), 200
        
    except Exception as e:
        log.error(f"Error getting pending orders: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'orders': [],
            'count': 0
        }), 500
