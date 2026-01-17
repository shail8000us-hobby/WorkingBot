"""
Futures API Blueprint

This module handles all API routes for futures position management.
Completely separate from options and grid bot routes.

Routes:
- GET  /api/futures/positions - Get all futures positions from Delta Exchange
- GET  /api/futures/orders - Get pending futures orders from Delta Exchange

Created: January 17, 2026
Purpose: Phase 1 - Backend API for Futures Panel in WebUI

⚠️ COMPLETE SEPARATION FROM OPTIONS AND GRID BOT
This blueprint only manages futures position display, never touches options or grid bot logic.
"""

import sys
import time
import logging
import traceback
from pathlib import Path
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from config.loader import get_config, get_api_credentials

log = logging.getLogger(__name__)

# Create blueprint
futures_bp = Blueprint('futures', __name__, url_prefix='/api/futures')

# Cache for positions (to avoid too many API calls)
_positions_cache = {'data': None, 'time': 0}
_orders_cache = {'data': None, 'time': 0}
CACHE_SECONDS = 3.0  # Cache for 3 seconds

# Product IDs for futures (perpetuals)
FUTURES_PRODUCT_IDS = {
    'BTCUSD': 139,   # Live BTCUSD perpetual
    'ETHUSD': 3136,  # Live ETHUSD perpetual
}

# Demo product IDs
DEMO_FUTURES_PRODUCT_IDS = {
    'BTCUSD': 27,    # Demo BTCUSD perpetual
    'ETHUSD': 84,    # Demo ETHUSD perpetual (if available)
}


def _get_delta_client():
    """Get Delta Exchange client instance"""
    try:
        from bot.api.delta_client import DeltaClient
        return DeltaClient()
    except Exception as e:
        log.error(f"Failed to initialize Delta client: {e}")
        return None


def _is_futures_position(product_symbol: str) -> bool:
    """
    Check if a product symbol is a futures (perpetual) position.
    
    Futures symbols: BTCUSD, ETHUSD, etc.
    Options symbols contain: -C- (call) or -P- (put)
    """
    if not product_symbol:
        return False
    
    # Options contain -C- or -P-
    if '-C-' in product_symbol or '-P-' in product_symbol:
        return False
    
    # Known futures symbols
    futures_symbols = ['BTCUSD', 'ETHUSD', 'SOLUSD', 'BNBUSD', 'XRPUSD', 'DOGEUSD']
    return product_symbol in futures_symbols


@futures_bp.route('/positions', methods=['GET'])
def get_futures_positions():
    """
    Get all futures (perpetual) positions from Delta Exchange.
    
    Returns only FUTURES positions, not options.
    
    Returns:
        JSON response with positions list and summary
        
    Example Response:
        {
            "success": true,
            "positions": [
                {
                    "symbol": "BTCUSD",
                    "product_id": 139,
                    "size": 10,
                    "side": "long",
                    "entry_price": 94500.00,
                    "mark_price": 95000.00,
                    "unrealized_pnl": 5.00,
                    "realized_pnl": 0.00,
                    "liquidation_price": 85000.00,
                    "margin": 50.00
                }
            ],
            "summary": {
                "total_positions": 1,
                "total_unrealized_pnl": 5.00,
                "total_realized_pnl": 0.00
            }
        }
    """
    global _positions_cache
    
    try:
        # Check cache
        now = time.time()
        if _positions_cache['data'] and (now - _positions_cache['time']) < CACHE_SECONDS:
            log.debug("Returning cached futures positions")
            return jsonify(_positions_cache['data'])
        
        delta_client = _get_delta_client()
        if not delta_client:
            return jsonify({
                'success': False,
                'error': 'Delta client not available',
                'positions': [],
                'summary': {'total_positions': 0, 'total_unrealized_pnl': 0, 'total_realized_pnl': 0}
            }), 503
        
        # Fetch all margined positions
        response = delta_client._req('GET', '/v2/positions/margined')
        
        if not response.get('success'):
            log.error(f"Delta API error: {response.get('error', 'Unknown error')}")
            return jsonify({
                'success': False,
                'error': 'Failed to fetch positions from Delta Exchange',
                'positions': [],
                'summary': {'total_positions': 0, 'total_unrealized_pnl': 0, 'total_realized_pnl': 0}
            }), 502
        
        # Filter for futures positions only
        all_positions = response.get('result', [])
        futures_positions = []
        total_unrealized_pnl = 0
        total_realized_pnl = 0
        
        for pos in all_positions:
            try:
                product_symbol = pos.get('product_symbol', '')
                
                # Skip if not a futures position
                if not _is_futures_position(product_symbol):
                    continue
                
                # Safely convert size, handling None
                size_raw = pos.get('size')
                if size_raw is None:
                    continue
                size = int(size_raw)
                
                # Skip if size is 0
                if size == 0:
                    continue
                
                # Safely convert values, handling None
                entry_price = float(pos.get('entry_price') or 0)
                mark_price = float(pos.get('mark_price') or 0)
                realized_pnl = float(pos.get('realized_pnl') or 0)
                liquidation_price = float(pos.get('liquidation_price') or 0)
                margin = float(pos.get('margin') or 0)
                product_id = int(pos.get('product_id') or 0)
                
                # Calculate unrealized PnL
                # For perpetuals: (mark_price - entry_price) * size * contract_multiplier
                CONTRACT_MULTIPLIER = 0.001  # Standard for Delta Exchange
                unrealized_pnl = (mark_price - entry_price) * size * CONTRACT_MULTIPLIER
                
                futures_positions.append({
                    'symbol': product_symbol,
                    'product_id': product_id,
                    'size': size,
                    'side': 'long' if size > 0 else 'short',
                    'entry_price': round(entry_price, 2),
                    'mark_price': round(mark_price, 2),
                    'unrealized_pnl': round(unrealized_pnl, 4),
                    'realized_pnl': round(realized_pnl, 4),
                    'liquidation_price': round(liquidation_price, 2),
                    'margin': round(margin, 4),
                    'created_at': pos.get('created_at', ''),
                    'updated_at': pos.get('updated_at', ''),
                })
                
                total_unrealized_pnl += unrealized_pnl
                total_realized_pnl += realized_pnl
                
            except Exception as pos_error:
                log.warning(f"Skipping position due to error: {pos_error} - {pos.get('product_symbol', 'unknown')}")
                continue
        
        result = {
            'success': True,
            'positions': futures_positions,
            'summary': {
                'total_positions': len(futures_positions),
                'total_unrealized_pnl': round(total_unrealized_pnl, 4),
                'total_realized_pnl': round(total_realized_pnl, 4),
            },
            'timestamp': now
        }
        
        # Update cache
        _positions_cache = {'data': result, 'time': now}
        
        log.info(f"📊 Fetched {len(futures_positions)} futures positions from Delta Exchange")
        return jsonify(result)
        
    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"Error fetching futures positions: {e}")
        log.error(f"Traceback:\n{tb}")
        print(f"ERROR in futures API: {e}\n{tb}")
        return jsonify({
            'success': False,
            'error': str(e),
            'positions': [],
            'summary': {'total_positions': 0, 'total_unrealized_pnl': 0, 'total_realized_pnl': 0}
        }), 500


@futures_bp.route('/orders', methods=['GET'])
def get_futures_orders():
    """
    Get all pending futures orders from Delta Exchange.
    
    Returns only FUTURES orders (open/pending), not options.
    
    Returns:
        JSON response with orders list
        
    Example Response:
        {
            "success": true,
            "orders": [
                {
                    "id": "123456",
                    "symbol": "BTCUSD",
                    "side": "buy",
                    "size": 5,
                    "price": 94500.00,
                    "order_type": "limit_order",
                    "state": "open",
                    "created_at": "2026-01-17T12:00:00Z"
                }
            ],
            "count": 1
        }
    """
    global _orders_cache
    
    try:
        # Check cache
        now = time.time()
        if _orders_cache['data'] and (now - _orders_cache['time']) < CACHE_SECONDS:
            log.debug("Returning cached futures orders")
            return jsonify(_orders_cache['data'])
        
        delta_client = _get_delta_client()
        if not delta_client:
            return jsonify({
                'success': False,
                'error': 'Delta client not available',
                'orders': [],
                'count': 0
            }), 503
        
        # Fetch open orders
        response = delta_client._req('GET', '/v2/orders', params={'state': 'open'})
        
        if not response.get('success'):
            log.error(f"Delta API error: {response.get('error', 'Unknown error')}")
            return jsonify({
                'success': False,
                'error': 'Failed to fetch orders from Delta Exchange',
                'orders': [],
                'count': 0
            }), 502
        
        # Filter for futures orders only
        all_orders = response.get('result', [])
        futures_orders = []
        
        for order in all_orders:
            product_symbol = order.get('product_symbol', '')
            
            # Skip if not a futures order
            if not _is_futures_position(product_symbol):
                continue
            
            futures_orders.append({
                'id': order.get('id'),
                'symbol': product_symbol,
                'product_id': order.get('product_id'),
                'side': order.get('side'),
                'size': order.get('size'),
                'unfilled_size': order.get('unfilled_size'),
                'price': float(order.get('limit_price', 0)),
                'order_type': order.get('order_type'),
                'state': order.get('state'),
                'created_at': order.get('created_at'),
                'reduce_only': order.get('reduce_only', False),
            })
        
        result = {
            'success': True,
            'orders': futures_orders,
            'count': len(futures_orders),
            'timestamp': now
        }
        
        # Update cache
        _orders_cache = {'data': result, 'time': now}
        
        log.info(f"📋 Fetched {len(futures_orders)} pending futures orders from Delta Exchange")
        return jsonify(result)
        
    except Exception as e:
        log.error(f"Error fetching futures orders: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'orders': [],
            'count': 0
        }), 500


@futures_bp.route('/ticker/<symbol>', methods=['GET'])
def get_futures_ticker(symbol: str):
    """
    Get ticker data for a futures symbol.
    
    Args:
        symbol: Futures symbol (e.g., BTCUSD, ETHUSD)
    
    Returns:
        JSON response with ticker data
    """
    try:
        delta_client = _get_delta_client()
        if not delta_client:
            return jsonify({
                'success': False,
                'error': 'Delta client not available'
            }), 503
        
        response = delta_client._req('GET', f'/v2/tickers/{symbol}')
        
        if not response.get('success'):
            return jsonify({
                'success': False,
                'error': f'Failed to fetch ticker for {symbol}'
            }), 502
        
        ticker = response.get('result', {})
        
        return jsonify({
            'success': True,
            'ticker': {
                'symbol': ticker.get('symbol'),
                'mark_price': float(ticker.get('mark_price', 0)),
                'spot_price': float(ticker.get('spot_price', 0)),
                'last_price': float(ticker.get('close', 0)),
                'high_24h': float(ticker.get('high', 0)),
                'low_24h': float(ticker.get('low', 0)),
                'volume_24h': float(ticker.get('volume', 0)),
                'open_interest': float(ticker.get('open_interest', 0)),
                'funding_rate': float(ticker.get('funding_rate', 0)),
            }
        })
        
    except Exception as e:
        log.error(f"Error fetching ticker for {symbol}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
