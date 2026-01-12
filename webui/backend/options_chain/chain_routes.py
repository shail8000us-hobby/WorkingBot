"""
Options Chain Routes
====================
API endpoints for options chain data and trading.
Completely isolated from existing options trading module.

Endpoints:
- GET  /api/options-chain/health - Health check
- GET  /api/options-chain/expirations - List available expiry dates
- GET  /api/options-chain/data - Get chain data for specific expiry
- POST /api/options-chain/order - Place buy/sell order from chain
- GET  /api/options-chain/ticker/<symbol> - Get ticker for specific option
"""

import time
import hashlib
from functools import wraps
from flask import jsonify, request
from . import options_chain_bp
import logging

log = logging.getLogger(__name__)

# ============================================================================
# Rate Limiting & Safety
# ============================================================================

_last_order_time = 0
RATE_LIMIT_SECONDS = 2.0

_pending_orders = {}
DUPLICATE_WINDOW_SECONDS = 5.0


def rate_limit(f):
    """Decorator to enforce 2-second cooldown between orders"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        global _last_order_time
        elapsed = time.time() - _last_order_time
        if elapsed < RATE_LIMIT_SECONDS:
            wait_time = RATE_LIMIT_SECONDS - elapsed
            return jsonify({
                'success': False,
                'error': f'Rate limited. Wait {wait_time:.1f}s before next order.'
            }), 429
        return f(*args, **kwargs)
    return decorated_function


def prevent_duplicate(f):
    """Decorator to prevent duplicate orders within 5 seconds"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        global _pending_orders
        
        try:
            data = request.get_json() or {}
            request_str = f"{data.get('symbol')}_{data.get('size')}_{data.get('side')}"
            request_hash = hashlib.md5(request_str.encode()).hexdigest()
        except:
            return f(*args, **kwargs)
        
        now = time.time()
        _pending_orders = {k: v for k, v in _pending_orders.items() 
                          if now - v < DUPLICATE_WINDOW_SECONDS}
        
        if request_hash in _pending_orders:
            elapsed = now - _pending_orders[request_hash]
            log.warning(f"🛑 DUPLICATE ORDER BLOCKED: {request_str}")
            return jsonify({
                'success': False,
                'error': f'Duplicate order blocked. Same order submitted {elapsed:.1f}s ago.'
            }), 429
        
        _pending_orders[request_hash] = now
        return f(*args, **kwargs)
    
    return decorated_function

# ============================================================================
# Health Check
# ============================================================================

@options_chain_bp.route('/health', methods=['GET'])
def health_check():
    """Health check for options chain module"""
    return jsonify({
        'status': 'ok',
        'module': 'options_chain',
        'message': 'Options Chain module is running'
    })


# ============================================================================
# Get Available Expirations
# ============================================================================

@options_chain_bp.route('/expirations', methods=['GET'])
def get_expirations():
    """
    Get available expiry dates for options
    
    Query params:
    - underlying: BTC or ETH (default: BTC)
    
    Returns:
    - List of expiry dates in DDMMYYYY format
    """
    underlying = request.args.get('underlying', 'BTC').upper()
    
    if underlying not in ['BTC', 'ETH']:
        return jsonify({
            'error': 'Invalid underlying. Must be BTC or ETH'
        }), 400
    
    try:
        # Import service (lazy import to avoid circular deps)
        from .chain_service import OptionsChainService
        service = OptionsChainService()
        
        expirations = service.get_expirations(underlying)
        
        return jsonify({
            'underlying': underlying,
            'expirations': expirations,
            'count': len(expirations)
        })
        
    except Exception as e:
        log.error(f"Error fetching expirations: {e}")
        return jsonify({
            'error': str(e),
            'underlying': underlying
        }), 500


# ============================================================================
# Get Options Chain Data
# ============================================================================

@options_chain_bp.route('/data', methods=['GET'])
def get_chain_data():
    """
    Get options chain data for specific underlying and expiry
    
    Query params:
    - underlying: BTC or ETH (default: BTC)
    - expiry: Expiry date in DDMMYYYY format (required)
    
    Returns:
    - Full options chain with calls and puts for all strikes
    """
    underlying = request.args.get('underlying', 'BTC').upper()
    expiry = request.args.get('expiry')
    
    if underlying not in ['BTC', 'ETH']:
        return jsonify({
            'error': 'Invalid underlying. Must be BTC or ETH'
        }), 400
    
    if not expiry:
        return jsonify({
            'error': 'expiry parameter is required (format: DDMMYYYY)'
        }), 400
    
    try:
        # Import service (lazy import)
        from .chain_service import OptionsChainService
        service = OptionsChainService()
        
        chain_data = service.get_chain_data(underlying, expiry)
        
        return jsonify(chain_data)
        
    except Exception as e:
        log.error(f"Error fetching chain data: {e}")
        return jsonify({
            'error': str(e),
            'underlying': underlying,
            'expiry': expiry
        }), 500


# ============================================================================
# Force Refresh Chain Data
# ============================================================================

@options_chain_bp.route('/refresh', methods=['POST'])
def refresh_chain():
    """
    Force refresh chain data (invalidate cache)
    
    Query params:
    - underlying: BTC or ETH (default: BTC)
    - expiry: Optional expiry date
    """
    underlying = request.args.get('underlying', 'BTC').upper()
    expiry = request.args.get('expiry')
    
    try:
        from .chain_service import OptionsChainService
        service = OptionsChainService()
        
        service.invalidate_cache(underlying, expiry)
        
        return jsonify({
            'status': 'ok',
            'message': f'Cache invalidated for {underlying}' + (f' expiry {expiry}' if expiry else '')
        })
        
    except Exception as e:
        log.error(f"Error refreshing cache: {e}")
        return jsonify({
            'error': str(e)
        }), 500


# ============================================================================
# Get Option Ticker
# ============================================================================

@options_chain_bp.route('/ticker/<symbol>', methods=['GET'])
def get_option_ticker(symbol):
    """
    Get current ticker data for a specific option
    
    Args:
        symbol: Option symbol (e.g., C-BTC-95000-060126)
        
    Returns:
        Ticker data including bid/ask, IV, Greeks
    """
    try:
        from .chain_service import OptionsChainService
        service = OptionsChainService()
        
        ticker = service.get_option_ticker(symbol)
        
        if not ticker:
            return jsonify({
                'success': False,
                'error': f'Ticker not found for {symbol}'
            }), 404
        
        return jsonify({
            'success': True,
            'symbol': symbol,
            'ticker': ticker
        })
        
    except Exception as e:
        log.error(f"Error fetching ticker for {symbol}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Place Order from Chain
# ============================================================================

@options_chain_bp.route('/order', methods=['POST'])
@rate_limit
@prevent_duplicate
def place_chain_order():
    """
    Place buy/sell order from options chain
    
    Request body:
    {
        "symbol": "C-BTC-95000-060126",  # Option symbol
        "side": "buy" | "sell",          # Order side
        "size": 1,                        # Quantity (contracts)
        "order_type": "market" | "limit", # Order type
        "limit_price": 1500.00            # Required for limit orders
    }
    
    Returns:
        Order result with execution details
    """
    global _last_order_time
    
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Request body is required'
        }), 400
    
    # Validate required fields
    symbol = data.get('symbol')
    side = data.get('side', '').lower()
    size = data.get('size')
    order_type = data.get('order_type', 'market').lower()
    limit_price = data.get('limit_price')
    
    if not symbol:
        return jsonify({
            'success': False,
            'error': 'symbol is required'
        }), 400
    
    if side not in ['buy', 'sell']:
        return jsonify({
            'success': False,
            'error': 'side must be "buy" or "sell"'
        }), 400
    
    if not size or int(size) <= 0:
        return jsonify({
            'success': False,
            'error': 'size must be a positive integer'
        }), 400
    
    if order_type == 'limit' and not limit_price:
        return jsonify({
            'success': False,
            'error': 'limit_price is required for limit orders'
        }), 400
    
    try:
        import asyncio
        from .order_service import OptionsChainOrderService
        
        order_service = OptionsChainOrderService()
        
        # Run async order placement
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                order_service.place_order(
                    symbol=symbol,
                    side=side,
                    size=int(size),
                    order_type=order_type,
                    limit_price=float(limit_price) if limit_price else None
                )
            )
        finally:
            loop.close()
        
        # Update rate limit time on success
        if result.get('success'):
            _last_order_time = time.time()
        
        return jsonify(result), 200 if result.get('success') else 400
        
    except Exception as e:
        log.error(f"Error placing order: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Cancel Order
# ============================================================================

@options_chain_bp.route('/order/<order_id>', methods=['DELETE'])
def cancel_order(order_id):
    """
    Cancel an open order
    
    Args:
        order_id: Order ID to cancel
        
    Returns:
        Cancellation result
    """
    try:
        import asyncio
        from .order_service import OptionsChainOrderService
        
        order_service = OptionsChainOrderService()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                order_service.cancel_order(order_id)
            )
        finally:
            loop.close()
        
        return jsonify(result), 200 if result.get('success') else 400
        
    except Exception as e:
        log.error(f"Error cancelling order {order_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Get Open Orders
# ============================================================================

@options_chain_bp.route('/orders', methods=['GET'])
def get_open_orders():
    """
    Get all open options orders
    
    Returns:
        List of open orders
    """
    try:
        import asyncio
        from .order_service import OptionsChainOrderService
        
        order_service = OptionsChainOrderService()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                order_service.get_open_orders()
            )
        finally:
            loop.close()
        
        return jsonify(result)
        
    except Exception as e:
        log.error(f"Error fetching open orders: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'orders': []
        }), 500
