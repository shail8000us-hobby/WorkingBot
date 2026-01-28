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
"""

import os
import sys
import copy
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request


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

log = logging.getLogger(__name__)

# Create blueprint
positions_bp = Blueprint('positions', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
POSITIONS_FILE = BASE_DIR / "bot" / "reports" / "positions.json"
STATE_FILE = BASE_DIR / "bot" / "reports" / "state.json"

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
            'total_all_symbols': len(all_positions)  # v5.0: Total before filtering
        }
    }
    
    return filtered_data

# ============================================================================
# Route Handlers
# ============================================================================

@positions_bp.route('/api/positions', methods=['GET'])
def get_positions():
    """
    Get current positions with liquidation info and Greeks
    
    Query Parameters:
        symbol (optional): Filter positions by symbol (e.g., "BTCUSD", "ETHUSD")
                          If provided, only returns positions for that symbol.
                          If omitted, returns all positions (v4.0 backward compat).
    
    Tries multiple strategies:
    1. Delta Exchange API (real-time with Greeks)
    2. Positions file (if bot is running)
    3. Guardian data (fallback)
    
    Returns:
        JSON response with positions and summary
    
    Example:
        GET /api/positions
        GET /api/positions?symbol=BTCUSD
        Response: {
            "positions": [
                {
                    "symbol": "BTCUSD",
                    "product_id": 27,
                    "type": "FUTURE",
                    "size": 10,
                    "side": "long",
                    "entry_price": 50000.0,
                    "current_price": 51000.0,
                    "unrealized_pnl": 10.0,
                    "delta": 0.5,
                    "vega": 0.01,
                    "theta": -0.05,
                    "notional_deployed": 425000.0
                },
                ...
            ],
            "summary": {
                "total_positions": 5,
                "total_pnl": 1234.56,
                "portfolio_delta": 2.5,
                "portfolio_vega": 0.05,
                "portfolio_theta": -0.25,
                "total_notional_deployed": 2125000.0,
                "data_source": "delta_exchange",
                "filtered_by_symbol": "BTCUSD"  # v5.0: If filtering applied
            }
        }
    """
    try:
        from flask import request
        
        # v6.0: Get instance filter (supports both ?instance= and ?symbol= formats)
        instance_name, filter_symbol, filter_mode = get_instance_from_request()
        
        # Strategy 1: Try Delta Exchange API
        positions_data = _get_positions_from_delta()
        if positions_data:
            # v6.0: Apply symbol filter if requested
            if filter_symbol:
                positions_data = _filter_positions_by_symbol(positions_data, filter_symbol)
            return jsonify(positions_data), 200
        
        # Strategy 2: Try positions file
        positions_data = _get_positions_from_file()
        if positions_data:
            # v5.0: Apply symbol filter if requested
            if filter_symbol:
                positions_data = _filter_positions_by_symbol(positions_data, filter_symbol)
            return jsonify(positions_data), 200
        
        # Strategy 3: Try guardian
        positions_data = _get_positions_from_guardian()
        if positions_data:
            # v5.0: Apply symbol filter if requested
            if filter_symbol:
                positions_data = _filter_positions_by_symbol(positions_data, filter_symbol)
            return jsonify(positions_data), 200
        
        # No positions found
        return jsonify({
            'positions': [],
            'summary': {
                'total_positions': 0,
                'total_pnl_usd': 0,
                'total_pnl_inr': 0,
                'risk_percent': 0,
                'total_notional_deployed': 0,
                'filtered_by_symbol': filter_symbol  # v5.0
            }
        }), 200
        
    except Exception as e:
        log.error(f"Error fetching positions: {e}")
        return jsonify({'error': str(e)}), 500


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

def _get_positions_from_delta():
    """
    Get ALL positions directly from Delta Exchange API (with circuit breaker protection)
    
    Fetches COMPLETE portfolio including:
    - Futures positions (BTCUSD, ETHUSD, etc.)
    - Options positions (calls and puts)
    - All underlying assets
    
    Returns position data with Greeks (delta, vega, theta) and PnL.
    Greeks are fetched from ticker endpoint as they're not available in positions endpoint.
    """
    try:
        from bot.api.delta_client import DeltaClient
        
        def _fetch_from_delta():
            """Inner function wrapped by circuit breaker"""
            delta_client = DeltaClient()
            # Use /v2/positions/margined to get ALL positions (futures + options)
            response = delta_client._req('GET', '/v2/positions/margined')
            
            if not response.get('success'):
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
        log.info(f"📊 Fetched {len(pos_list)} positions from Delta Exchange (futures + options)")
        
        # Initialize Delta client for ticker requests
        delta_client = DeltaClient()
        
        for pos_data in pos_list:
            size = int(pos_data.get('size', 0))
            if size == 0:
                continue
            
            entry_price = float(pos_data.get('entry_price', 0))
            mark_price = float(pos_data.get('mark_price', 0))
            product_symbol = pos_data.get('product_symbol', 'UNKNOWN')
            product_id = int(pos_data.get('product_id', 0))
            
            # Calculate PnL: (Mark - Entry) × Size × Contract Multiplier
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
            
            # Initialize Greeks
            delta = 0
            vega = 0
            theta = 0
            gamma = 0
            
            if position_type == "FUTURE":
                # Futures always have delta = +1 (long) or -1 (short)
                # Position delta = size (positive for long, negative for short)
                delta = float(size)
                # Futures have no vega, theta, gamma
                vega = 0
                theta = 0
                gamma = 0
            else:
                # Fetch Greeks from ticker endpoint for options
                try:
                    ticker_response = delta_client._req('GET', f'/v2/tickers/{product_symbol}')
                    if ticker_response.get('success'):
                        ticker_data = ticker_response.get('result', {})
                        greeks = ticker_data.get('greeks', {})
                        if greeks:
                            # Return PER-CONTRACT Greeks (frontend handles position scaling)
                            # Delta Exchange API returns per-contract values
                            delta = float(greeks.get('delta', 0))
                            vega = float(greeks.get('vega', 0))
                            theta = float(greeks.get('theta', 0))
                            gamma = float(greeks.get('gamma', 0))
                            
                            log.debug(f"Greeks (per-contract) for {product_symbol}: delta={delta:.4f}, vega={vega:.4f}, theta={theta:.4f}")
                except Exception as e:
                    log.debug(f"Could not fetch Greeks for {product_symbol}: {e}")
            
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
            # - position theta = +0.31 * (-1) = -0.31 ❌ WRONG!
            # - We want: position theta = +0.31 (you earn $0.31/day) ✅
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
        
        return {
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
                'data_source': 'delta_exchange'
            }
        }
        
    except Exception as e:
        log.debug(f"Delta API positions fetch failed: {e}")
        return None


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
        
        data['summary']['total_notional_deployed'] = round(total_notional_deployed, 2)
        data['summary']['portfolio_delta'] = sum(p.get('delta', 0) for p in data['positions'])
        data['summary']['portfolio_vega'] = sum(p.get('vega', 0) for p in data['positions'])
        data['summary']['portfolio_theta'] = sum(p.get('theta', 0) for p in data['positions'])
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
def get_pending_orders():
    """
    Get all pending/open orders from Delta Exchange
    
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
            
            if not response.get('success'):
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
