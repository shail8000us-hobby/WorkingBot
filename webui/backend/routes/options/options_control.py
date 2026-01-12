"""
Options Control Blueprint

This module handles all API routes for options position management.
Completely separate from grid bot routes.

Routes:
- GET  /api/options/positions - Get all options positions
- POST /api/options/close - Close an options position
- POST /api/options/add - Add to an existing options position
- GET  /api/options/ticker/<symbol> - Get ticker for an option

Created: January 4, 2026
Updated: January 4, 2026 - Added smart maker orders
Purpose: Phase 2 - Backend Order Execution for Options

⚠️ COMPLETE SEPARATION FROM GRID BOT
This blueprint only manages options positions, never touches futures/grid bot.
"""

import sys
import time
import asyncio
import logging
from pathlib import Path
from functools import wraps
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config, get_api_credentials
from bot.options.utils.options_helper import (
    enrich_position_data,
    determine_close_side,
)

log = logging.getLogger(__name__)

# Create blueprint
options_bp = Blueprint('options', __name__, url_prefix='/api/options')

# Rate limiting state
# NOTE: These globals work for single-worker Flask. For production with Gunicorn
# multiple workers, consider using Redis for shared state across workers.
_last_order_time = 0
RATE_LIMIT_SECONDS = 2.0

# Duplicate order prevention
# NOTE: In multi-worker environments, this dict won't be shared across workers.
# Use Redis or a shared cache for production deployments with multiple workers.
_pending_orders = {}  # {request_hash: timestamp}
DUPLICATE_WINDOW_SECONDS = 5.0  # Block duplicate requests for 5 seconds

# Guardian cache
_guardian_cache = {'signal': None, 'time': 0}
GUARDIAN_CACHE_SECONDS = 5.0

# Order type options
ORDER_TYPE_MAKER_FIRST = 'maker_first'    # Try limit at mid, fallback to market
ORDER_TYPE_MAKER_ONLY = 'maker_only'      # Only limit orders
ORDER_TYPE_MARKET_ONLY = 'market_only'    # Only market orders (fastest)

# Valid order types set for validation
VALID_ORDER_TYPES = {ORDER_TYPE_MAKER_FIRST, ORDER_TYPE_MAKER_ONLY, ORDER_TYPE_MARKET_ONLY}


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
        
        # Get request data
        try:
            data = request.get_json() or {}
            # Create unique hash from request
            import hashlib
            request_str = f"{data.get('symbol')}_{data.get('size')}_{data.get('side')}"
            request_hash = hashlib.md5(request_str.encode()).hexdigest()
        except:
            return f(*args, **kwargs)  # Continue if we can't hash
        
        now = time.time()
        
        # Clean old entries
        _pending_orders = {k: v for k, v in _pending_orders.items() 
                          if now - v < DUPLICATE_WINDOW_SECONDS}
        
        # Check for duplicate
        if request_hash in _pending_orders:
            elapsed = now - _pending_orders[request_hash]
            log.warning(f"🛑 DUPLICATE ORDER BLOCKED: {request_str} (submitted {elapsed:.1f}s ago)")
            return jsonify({
                'success': False,
                'error': f'Duplicate order blocked. Same order submitted {elapsed:.1f}s ago.'
            }), 429
        
        # Mark as pending
        _pending_orders[request_hash] = now
        
        try:
            result = f(*args, **kwargs)
            return result
        finally:
            # Keep in pending list (will expire after DUPLICATE_WINDOW_SECONDS)
            pass
    
    return decorated_function


def check_guardian_signal():
    """Check if Guardian allows trading (cached for 5 seconds)"""
    global _guardian_cache
    
    now = time.time()
    if now - _guardian_cache['time'] < GUARDIAN_CACHE_SECONDS:
        return _guardian_cache['signal']
    
    try:
        # Read Guardian signal file
        signal_file = Path(__file__).parent.parent.parent.parent / 'data' / 'guardian_signal.json'
        if signal_file.exists():
            import json
            with open(signal_file, 'r') as f:
                data = json.load(f)
                signal = data.get('signal', 'GO')
        else:
            signal = 'GO'  # Default to GO if no file
        
        _guardian_cache = {'signal': signal, 'time': now}
        return signal
    except Exception as e:
        log.warning(f"Failed to read Guardian signal: {e}")
        return 'GO'  # Default to GO on error


def get_unified_client():
    """Get UnifiedAPIClient with credentials from config"""
    from bot.api.unified_api_client import UnifiedAPIClient
    
    creds = get_api_credentials()
    return UnifiedAPIClient(
        api_key=creds['api_key'],
        api_secret=creds['api_secret'],
        symbol='BTCUSD',
        enable_websocket=False
    )


async def place_options_order(client, product_symbol: str, size: int, side: str, 
                              order_type: str = 'limit_order', limit_price: float = None,
                              reduce_only: bool = False):
    """
    Place order on options contract using product_symbol.
    
    Delta Exchange API supports product_symbol for options contracts.
    This bypasses the need for product_id lookup.
    
    Args:
        client: UnifiedAPIClient instance (for rate limiting)
        product_symbol: Options symbol (e.g., C-BTC-113000-300126)
        size: Order size (positive integer)
        side: 'buy' or 'sell'
        order_type: 'limit_order' or 'market_order'
        limit_price: Price for limit orders
        reduce_only: If True, only reduces position
        
    Returns:
        dict: Order response
    """
    # Build order data using product_symbol (works for options)
    data = {
        "product_symbol": product_symbol,
        "side": side,
        "order_type": order_type,
        "size": int(size)
    }
    
    # Market orders don't use limit_price, post_only, or time_in_force
    if order_type == 'market_order':
        if reduce_only:
            data["reduce_only"] = "true"
    else:
        # Limit order
        if limit_price is not None:
            data["limit_price"] = str(limit_price)
        data["time_in_force"] = "gtc"
        data["post_only"] = "false"  # Allow taker for better fill
        if reduce_only:
            data["reduce_only"] = "true"
    
    log.info(f"📊 Placing {order_type}: {side} {size} {product_symbol} @ {limit_price or 'market'}")
    
    # Make direct API call
    response = await client.rest_client._request_with_retry(
        method="POST",
        path="/v2/orders",
        data=data
    )
    
    result = response.get('result', response)
    log.info(f"✅ Order placed: {result.get('id', 'unknown')}")
    return result


async def place_smart_order(client, symbol: str, size: float, side: str, 
                           order_preference: str = ORDER_TYPE_MAKER_FIRST,
                           reduce_only: bool = False):
    """
    Place order with smart execution strategy.
    
    Maker First: Place limit at mid-price, wait 2s, fallback to market if not filled
    Maker Only: Only limit orders (may not fill)
    Market Only: Immediate market order (highest fees)
    
    Args:
        client: UnifiedAPIClient instance
        symbol: Options symbol (e.g., C-BTC-113000-300126)
        size: Order size (positive number)
        side: 'buy' or 'sell'
        order_preference: ORDER_TYPE_MAKER_FIRST, ORDER_TYPE_MAKER_ONLY, ORDER_TYPE_MARKET_ONLY
        reduce_only: If True, only reduces position
        
    Returns:
        dict: Order result with execution details
    """
    size = int(abs(float(size)))
    
    # Market only - fastest execution
    if order_preference == ORDER_TYPE_MARKET_ONLY:
        log.info(f"📊 MARKET order: {side} {size} {symbol}")
        order = await place_options_order(
            client, symbol, size, side,
            order_type='market_order',
            reduce_only=reduce_only
        )
        order['execution_type'] = 'market'
        return order
    
    # Get current ticker for mid-price calculation
    try:
        ticker = await client.get_option_ticker(symbol)
        # Quotes can be in ticker.quotes or ticker.raw.quotes
        quotes = ticker.get('quotes', {})
        if not quotes and 'raw' in ticker:
            quotes = ticker.get('raw', {}).get('quotes', {})
        best_bid = float(quotes.get('best_bid') or 0)
        best_ask = float(quotes.get('best_ask') or 0)
        
        if best_bid == 0 or best_ask == 0:
            log.warning(f"No quotes for {symbol}, using market order")
            order = await place_options_order(
                client, symbol, size, side,
                order_type='market_order',
                reduce_only=reduce_only
            )
            order['execution_type'] = 'market_fallback_no_quotes'
            return order
        
        # Calculate mid-price
        mid_price = (best_bid + best_ask) / 2
        
        # Get tick size for rounding
        # Try to get from ticker, fallback to 0.01 for BTC options
        tick_size = float(ticker.get('tick_size') or ticker.get('raw', {}).get('tick_size') or 0.01)
        mid_price = round(mid_price / tick_size) * tick_size
        
        log.info(f"📊 LIMIT order at mid ${mid_price:.2f} (bid: ${best_bid:.2f}, ask: ${best_ask:.2f})")
        
        # Place limit order at mid-price
        limit_order = await place_options_order(
            client, symbol, size, side,
            order_type='limit_order',
            limit_price=mid_price,
            reduce_only=reduce_only
        )
        
        order_id = limit_order.get('id')
        
        if order_preference == ORDER_TYPE_MAKER_ONLY:
            # Return immediately, don't wait for fill
            limit_order['execution_type'] = 'limit_maker'
            limit_order['limit_price'] = mid_price
            return limit_order
        
        # MAKER_FIRST: Wait 2 seconds for fill
        await asyncio.sleep(2)
        
        # Check if filled
        try:
            order_status = await client.rest_client.get_order(order_id)
            state = order_status.get('state', '')
            
            if state == 'filled':
                log.info(f"✅ Limit order filled at ${mid_price:.2f}")
                limit_order['execution_type'] = 'limit_filled'
                limit_order['fill_price'] = mid_price
                return limit_order
            
            if state == 'cancelled':
                log.info(f"⚠️ Limit order was cancelled")
                limit_order['execution_type'] = 'limit_cancelled'
                return limit_order
            
            # Not filled - cancel and use market order
            log.warning(f"⏱️ Limit order not filled in 2s, cancelling and using market")
            
            # Flag to track if we should place market order
            should_place_market = False
            
            try:
                await client.rest_client.cancel_order(order_id)
                log.info(f"📤 Cancel request sent for order {order_id}")
                
                # Wait briefly then check if cancel succeeded
                await asyncio.sleep(0.5)
                
                # Verify the order was actually cancelled (not filled during cancel)
                final_status = await client.rest_client.get_order(order_id)
                final_state = final_status.get('state', '')
                log.info(f"📊 Final order state after cancel: {final_state}")
                
                if final_state == 'filled':
                    # Order filled during cancellation - don't place market order!
                    log.info(f"✅ Limit order filled during cancellation at ${mid_price:.2f}")
                    limit_order['execution_type'] = 'limit_filled_late'
                    limit_order['fill_price'] = mid_price
                    return limit_order
                
                elif final_state == 'cancelled':
                    # Successfully cancelled, safe to place market order
                    log.info(f"✅ Limit order successfully cancelled")
                    should_place_market = True
                    
                else:
                    # Order still open or in unknown state - try to cancel again
                    log.warning(f"⚠️ Order state is {final_state}, attempting force cancel")
                    try:
                        await client.rest_client.cancel_order(order_id)
                        await asyncio.sleep(0.5)
                        
                        # Check one more time
                        recheck_status = await client.rest_client.get_order(order_id)
                        recheck_state = recheck_status.get('state', '')
                        log.info(f"📊 Recheck order state: {recheck_state}")
                        
                        if recheck_state == 'filled':
                            log.info(f"✅ Limit order filled on recheck")
                            limit_order['execution_type'] = 'limit_filled_late'
                            limit_order['fill_price'] = mid_price
                            return limit_order
                        elif recheck_state == 'cancelled':
                            should_place_market = True
                    except Exception as recheck_err:
                        log.error(f"❌ Recheck failed: {recheck_err}, NOT placing market order for safety")
                        limit_order['execution_type'] = 'limit_unknown_state'
                        return limit_order
                
            except Exception as cancel_err:
                log.warning(f"Cancel failed: {cancel_err}")
                # Check if it was filled
                try:
                    check_status = await client.rest_client.get_order(order_id)
                    check_state = check_status.get('state', '')
                    log.info(f"📊 Order state after cancel exception: {check_state}")
                    
                    if check_state == 'filled':
                        log.info(f"✅ Limit order was filled (cancel failed because already filled)")
                        limit_order['execution_type'] = 'limit_filled_on_cancel'
                        limit_order['fill_price'] = mid_price
                        return limit_order
                    elif check_state == 'cancelled':
                        should_place_market = True
                except Exception as check_err:
                    log.error(f"❌ Cannot verify order state: {check_err}, NOT placing market order for safety")
                    limit_order['execution_type'] = 'limit_unknown_state'
                    return limit_order
            
            # Only place market order if explicitly flagged as safe
            if should_place_market:
                log.info(f"🔄 Placing market order as fallback (confirmed safe)")
                market_order = await place_options_order(
                    client, symbol, size, side,
                    order_type='market_order',
                    reduce_only=reduce_only
                )
                market_order['execution_type'] = 'market_fallback'
                market_order['original_limit_price'] = mid_price
                return market_order
            else:
                log.warning(f"⚠️ NOT placing market order - could not confirm limit order was cancelled")
                limit_order['execution_type'] = 'limit_not_confirmed_cancelled'
                return limit_order
            
        except Exception as status_err:
            log.error(f"Failed to check order status: {status_err}")
            # Assume filled if we can't check
            limit_order['execution_type'] = 'limit_unknown'
            return limit_order
        
    except Exception as e:
        log.exception(f"Smart order failed, falling back to market")  # Full traceback
        order = await place_options_order(
            client, symbol, size, side,
            order_type='market_order',
            reduce_only=reduce_only
        )
        order['execution_type'] = 'market_fallback_error'
        order['error'] = str(e)
        return order


# Position cache to prevent repeated failures
_positions_cache = {'data': None, 'time': 0, 'error': None}
POSITIONS_CACHE_SECONDS = 3.0  # Cache positions for 3 seconds


@options_bp.route('/positions', methods=['GET'])
def get_options_positions():
    """
    Get all options positions with enriched data.
    
    Returns:
        JSON: {
            success: bool,
            positions: [...],  # Enriched options positions
            count: int,
            timestamp: str
        }
    """
    global _positions_cache
    
    # Return cached data if still fresh
    now = time.time()
    if now - _positions_cache['time'] < POSITIONS_CACHE_SECONDS and _positions_cache['data'] is not None:
        return jsonify({
            'success': True,
            'positions': _positions_cache['data'],
            'count': len(_positions_cache['data']),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'cached': True
        })
    
    try:
        import asyncio
        client = get_unified_client()
        
        # Run async code with concurrent ticker fetching
        async def fetch():
            positions = await client.get_all_positions_with_options()
            options = positions['options']
            
            # Fetch all tickers concurrently for faster loading
            async def enrich_single(pos):
                symbol = pos.get('product_symbol')
                try:
                    ticker = await client.get_option_ticker(symbol)
                    return enrich_position_data(pos, ticker)
                except Exception as e:
                    log.warning(f"Failed to get ticker for {symbol}: {e}")
                    return pos
            
            # Run all enrichments concurrently
            enriched = await asyncio.gather(*[enrich_single(pos) for pos in options])
            return list(enriched)
        
        options = asyncio.run(fetch())
        
        # Cache the successful result
        _positions_cache['data'] = options
        _positions_cache['time'] = time.time()
        _positions_cache['error'] = None
        
        return jsonify({
            'success': True,
            'positions': options,
            'count': len(options),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        log.exception("Failed to fetch options positions")  # Full traceback
        
        # Return cached data if available during errors
        if _positions_cache['data'] is not None:
            log.info("Returning cached positions due to API error")
            return jsonify({
                'success': True,
                'positions': _positions_cache['data'],
                'count': len(_positions_cache['data']),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'cached': True,
                'warning': f'Using cached data: {str(e)}'
            })
        
        # First request failed with no cache - provide helpful error
        return jsonify({
            'success': False,
            'error': 'Failed to fetch positions. Please try again.',
            'details': str(e),
            'suggestion': 'Check API connectivity and credentials'
        }), 500


@options_bp.route('/ticker/<symbol>', methods=['GET'])
def get_option_ticker(symbol):
    """
    Get ticker data for a specific option.
    
    Args:
        symbol: Options symbol (e.g., C-BTC-113000-300126)
        
    Returns:
        JSON: Ticker data with mark price, Greeks, spread
    """
    try:
        import asyncio
        client = get_unified_client()
        
        ticker = asyncio.run(client.get_option_ticker(symbol))
        
        return jsonify({
            'success': True,
            'ticker': ticker
        })
        
    except Exception as e:
        log.error(f"Failed to get ticker for {symbol}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@options_bp.route('/close', methods=['POST'])
@rate_limit
@prevent_duplicate
def close_options_position():
    """
    Close an options position.
    
    Request Body:
        {
            symbol: str,              # Options symbol
            size: float,              # Size to close (optional, defaults to full)
            confirm: bool,            # Must be true to execute
            order_preference: str     # 'maker_first', 'maker_only', 'market_only'
        }
        
    Returns:
        JSON: Order result or confirmation request
    """
    global _last_order_time
    
    # Check Guardian signal
    guardian_signal = check_guardian_signal()
    if guardian_signal != 'GO':
        return jsonify({
            'success': False,
            'error': f'Guardian signal is {guardian_signal}. Trading disabled.'
        }), 403
    
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        confirm = data.get('confirm', False)
        order_preference = data.get('order_preference', ORDER_TYPE_MARKET_ONLY)  # Close uses market by default for speed
        
        if not symbol:
            return jsonify({
                'success': False,
                'error': 'Missing symbol'
            }), 400
        
        # Validate order_preference
        if order_preference not in VALID_ORDER_TYPES:
            return jsonify({
                'success': False,
                'error': f'Invalid order_preference "{order_preference}". Must be one of: {list(VALID_ORDER_TYPES)}'
            }), 400
        
        client = get_unified_client()
        
        # Get current position
        async def get_position():
            positions = await client.get_all_positions_with_options()
            for pos in positions['options']:
                if pos.get('product_symbol') == symbol:
                    return pos
            return None
        
        position = asyncio.run(get_position())
        
        if not position:
            return jsonify({
                'success': False,
                'error': f'Position not found: {symbol}'
            }), 404
        
        position_size = float(position.get('size', 0))
        close_size = data.get('size', abs(position_size))
        side = determine_close_side(position_size)
        
        # If not confirmed, return confirmation request
        if not confirm:
            return jsonify({
                'success': True,
                'action': 'confirm_required',
                'symbol': symbol,
                'position_size': position_size,
                'close_size': close_size,
                'side': side,
                'order_preference': order_preference,
                'message': f'Confirm close {close_size} {symbol}? Set confirm=true to execute.'
            })
        
        # Execute close order using smart order
        async def place_close_order():
            return await place_smart_order(
                client=client,
                symbol=symbol,
                size=close_size,
                side=side,
                order_preference=order_preference,
                reduce_only=True
            )
        
        result = asyncio.run(place_close_order())
        _last_order_time = time.time()
        
        execution_type = result.get('execution_type', 'unknown')
        log.info(f"📉 OPTIONS CLOSE: {symbol} size={close_size} side={side} exec={execution_type}")
        
        return jsonify({
            'success': True,
            'action': 'closed',
            'symbol': symbol,
            'size': close_size,
            'side': side,
            'execution_type': execution_type,
            'order': result
        })
        
    except Exception as e:
        log.exception("Failed to close options position")  # Full traceback
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@options_bp.route('/add', methods=['POST'])
@rate_limit
@prevent_duplicate
def add_to_options_position():
    """
    Add to an existing options position (same strike).
    
    Request Body:
        {
            symbol: str,              # Options symbol
            size: float,              # Size to add
            side: str,                # 'buy' or 'sell'
            confirm: bool,            # Must be true to execute
            order_preference: str     # 'maker_first', 'maker_only', 'market_only'
        }
        
    Returns:
        JSON: Order result or confirmation request
    """
    global _last_order_time
    
    # Check Guardian signal
    guardian_signal = check_guardian_signal()
    if guardian_signal != 'GO':
        return jsonify({
            'success': False,
            'error': f'Guardian signal is {guardian_signal}. Trading disabled.'
        }), 403
    
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        size = data.get('size')
        side = data.get('side')
        confirm = data.get('confirm', False)
        order_preference = data.get('order_preference', ORDER_TYPE_MAKER_FIRST)  # Add uses maker_first by default
        
        if not all([symbol, size, side]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: symbol, size, side'
            }), 400
        
        if side not in ['buy', 'sell']:
            return jsonify({
                'success': False,
                'error': 'Side must be "buy" or "sell"'
            }), 400
        
        # Validate order_preference
        if order_preference not in VALID_ORDER_TYPES:
            return jsonify({
                'success': False,
                'error': f'Invalid order_preference "{order_preference}". Must be one of: {list(VALID_ORDER_TYPES)}'
            }), 400
        
        client = get_unified_client()
        
        # Get ticker for liquidity check and mid-price display
        async def check_liquidity():
            ticker = await client.get_option_ticker(symbol)
            return ticker
        
        ticker = asyncio.run(check_liquidity())
        spread_pct = float(ticker.get('spread_pct') or 0)
        quotes = ticker.get('quotes', {})
        best_bid = float(quotes.get('best_bid') or 0)
        best_ask = float(quotes.get('best_ask') or 0)
        mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
        
        # Warn if illiquid
        if spread_pct > 10:
            if not confirm:
                return jsonify({
                    'success': True,
                    'action': 'confirm_required',
                    'warning': f'High spread: {spread_pct:.1f}%. Position may be illiquid.',
                    'symbol': symbol,
                    'size': size,
                    'side': side,
                    'mid_price': mid_price,
                    'order_preference': order_preference,
                    'message': f'Confirm add {size} {symbol}? Set confirm=true to execute.'
                })
        
        # If not confirmed, return confirmation request
        if not confirm:
            return jsonify({
                'success': True,
                'action': 'confirm_required',
                'symbol': symbol,
                'size': size,
                'side': side,
                'spread_pct': spread_pct,
                'mid_price': mid_price,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'order_preference': order_preference,
                'message': f'Confirm add {size} {symbol} ({side})? Set confirm=true to execute.'
            })
        
        # Execute add order using smart order
        async def place_add_order():
            return await place_smart_order(
                client=client,
                symbol=symbol,
                size=float(size),
                side=side,
                order_preference=order_preference
            )
        
        result = asyncio.run(place_add_order())
        _last_order_time = time.time()
        
        execution_type = result.get('execution_type', 'unknown')
        fill_price = result.get('fill_price') or result.get('limit_price') or result.get('average_fill_price')
        
        log.info(f"📈 OPTIONS ADD: {symbol} size={size} side={side} exec={execution_type} price={fill_price}")
        
        return jsonify({
            'success': True,
            'action': 'added',
            'symbol': symbol,
            'size': size,
            'side': side,
            'execution_type': execution_type,
            'fill_price': fill_price,
            'order': result
        })
        
    except Exception as e:
        log.exception("Failed to add to options position")  # Full traceback
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@options_bp.route('/status', methods=['GET'])
def get_options_status():
    """
    Get options module status including index prices.
    
    Returns:
        JSON: Module status including Guardian signal and BTC/ETH index prices
    """
    guardian_signal = check_guardian_signal()
    
    # Fetch index prices - simplified implementation
    index_prices = {'BTC': 0, 'ETH': 0}
    
    return jsonify({
        'success': True,
        'enabled': True,
        'guardian_signal': guardian_signal,
        'trading_allowed': guardian_signal == 'GO',
        'rate_limit_seconds': RATE_LIMIT_SECONDS,
        'index_prices': index_prices,  # Will be populated by frontend from positions
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    })
