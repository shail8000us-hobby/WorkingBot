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

# Import trade logger for ML learning
try:
    from ...options_strategy.trade_logger import trade_logger
    TRADE_LOGGING_ENABLED = True
except Exception as e:
    print(f"⚠️ Trade logger not available: {e}")
    trade_logger = None
    TRADE_LOGGING_ENABLED = False

log = logging.getLogger(__name__)

# Create blueprint
options_bp = Blueprint('options', __name__, url_prefix='/api/options')

# Rate limiting state
# NOTE: These globals work for single-worker Flask. For production with Gunicorn
# multiple workers, consider using Redis for shared state across workers.
_last_order_time = {}
RATE_LIMIT_SECONDS = 1.0  # Reduced from 2.0 to 1.0 for better UX

# Duplicate order prevention
# NOTE: In multi-worker environments, this dict won't be shared across workers.
# Use Redis or a shared cache for production deployments with multiple workers.
_pending_orders = {}  # {request_hash: timestamp}
DUPLICATE_WINDOW_SECONDS = 3.0  # Reduced from 5.0 to 3.0  # Block duplicate requests for 5 seconds

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
    """Decorator to enforce per-user cooldown between orders"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        global _last_order_time
        
        # Use IP address as user identifier (better than global limit)
        user_id = request.remote_addr or 'unknown'
        now = time.time()
        
        # Clean old entries
        _last_order_time = {k: v for k, v in _last_order_time.items() 
                           if now - v < RATE_LIMIT_SECONDS * 10}
        
        last_time = _last_order_time.get(user_id, 0)
        elapsed = now - last_time
        
        if elapsed < RATE_LIMIT_SECONDS:
            wait_time = RATE_LIMIT_SECONDS - elapsed
            log.warning(f"⏱️ Rate limit for {user_id}: wait {wait_time:.1f}s")
            return jsonify({
                'success': False,
                'error': f'Please wait {wait_time:.1f}s before next order'
            }), 429
        
        _last_order_time[user_id] = now
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
            # Remove from pending on successful execution
            _pending_orders.pop(request_hash, None)
            return result
        except Exception as e:
            # Remove from pending on error too
            _pending_orders.pop(request_hash, None)
            log.error(f"❌ Error in {f.__name__}: {e}")
            raise
    
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


async def with_timeout(coro, timeout_seconds=30):
    """Execute coroutine with timeout to prevent hanging requests"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise Exception(f"Operation timed out after {timeout_seconds}s")


async def cancel_order_with_verification(client, order_id, max_retries=3):
    """
    Cancel order with verification to prevent race conditions.
    
    Returns:
        dict: {'state': 'cancelled'|'filled'|'unknown', 'safe_to_place_market': bool}
    """
    for attempt in range(max_retries):
        try:
            # Check current state first
            status = await client.rest_client.get_order(order_id)
            current_state = status.get('state', '')
            
            if current_state == 'filled':
                log.info(f"✅ Order {order_id} already filled")
                return {'state': 'filled', 'safe_to_place_market': False}
            
            if current_state == 'cancelled':
                log.info(f"✅ Order {order_id} already cancelled")
                return {'state': 'cancelled', 'safe_to_place_market': True}
            
            # Attempt cancellation
            await client.rest_client.cancel_order(order_id)
            await asyncio.sleep(0.3)
            
            # Verify cancellation
            verify_status = await client.rest_client.get_order(order_id)
            verify_state = verify_status.get('state', '')
            
            if verify_state == 'cancelled':
                log.info(f"✅ Order {order_id} successfully cancelled")
                return {'state': 'cancelled', 'safe_to_place_market': True}
            elif verify_state == 'filled':
                log.info(f"✅ Order {order_id} filled during cancellation")
                return {'state': 'filled', 'safe_to_place_market': False}
            
            # Still open, retry
            log.warning(f"⚠️ Order {order_id} still {verify_state}, retry {attempt + 1}/{max_retries}")
            
        except Exception as e:
            log.error(f"Cancel attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                # Last attempt failed - assume unsafe to place market order
                log.error(f"❌ All cancel attempts failed for {order_id}")
                return {'state': 'unknown', 'safe_to_place_market': False}
    
    # If we get here, cancellation uncertain - DO NOT place market order
    log.warning(f"⚠️ Cannot confirm cancellation of {order_id}, NOT safe for market order")
    return {'state': 'unknown', 'safe_to_place_market': False}


async def validate_order_size(client, symbol, requested_size, side, is_close=False):
    """
    Validate order size against position and exchange limits.
    
    Raises:
        ValueError: If order size is invalid
    """
    if requested_size <= 0:
        raise ValueError(f"Order size must be positive, got {requested_size}")
    
    if requested_size > 10000:
        raise ValueError(f"Order size {requested_size} exceeds maximum (10000)")
    
    if is_close:
        # Verify we have a position to close
        positions = await client.get_all_positions_with_options()
        position = next((p for p in positions.get('options', []) 
                        if p.get('product_symbol') == symbol), None)
        
        if not position:
            raise ValueError(f"Cannot close non-existent position: {symbol}")
        
        position_size = abs(float(position.get('size', 0)))
        if requested_size > position_size:
            raise ValueError(
                f"Close size {requested_size} exceeds position size {position_size}"
            )
    
    return True


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
            
            # Use verified cancellation to prevent race conditions
            cancel_result = await cancel_order_with_verification(client, order_id)
            
            if cancel_result['state'] == 'filled':
                # Order filled during cancellation - don't place market order!
                log.info(f"✅ Limit order filled during cancellation at ${mid_price:.2f}")
                limit_order['execution_type'] = 'limit_filled_late'
                limit_order['fill_price'] = mid_price
                return limit_order
            
            elif cancel_result['safe_to_place_market']:
                # Safely cancelled, place market order
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
                # Could not confirm cancellation - DO NOT place market order for safety
                log.warning(f"⚠️ Cannot confirm cancellation, NOT placing market order for safety")
                limit_order['execution_type'] = 'limit_cancel_unconfirmed'
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
        log.error(f"Failed to fetch options positions: {e}")  # Single line error
        
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
        
        # Get current position with timeout
        async def get_position():
            positions = await with_timeout(
                client.get_all_positions_with_options(),
                timeout_seconds=15
            )
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
        
        # Validate close size
        try:
            async def validate():
                await validate_order_size(client, symbol, close_size, side, is_close=True)
            asyncio.run(validate())
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid order size: {str(e)}'
            }), 400
        
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
        
        # Execute close order using smart order with timeout
        async def place_close_order():
            return await with_timeout(
                place_smart_order(
                    client=client,
                    symbol=symbol,
                    size=close_size,
                    side=side,
                    order_preference=order_preference,
                    reduce_only=True
                ),
                timeout_seconds=30
            )
        
        result = asyncio.run(place_close_order())
        # Note: _last_order_time is managed by the @rate_limit decorator
        
        execution_type = result.get('execution_type', 'unknown')
        fill_price = result.get('fill_price') or result.get('average_fill_price') or 0
        
        # Log trade for ML learning
        if TRADE_LOGGING_ENABLED and trade_logger:
            try:
                trade_logger.log_trade(
                    symbol=symbol,
                    action='SELL' if side == 'sell' else 'BUY',
                    quantity=int(close_size),
                    price=float(fill_price),
                    side='CLOSE',
                    position_before={
                        'size': position_size,
                        'entry_price': position.get('entry_price', 0),
                        'unrealized_pnl': position.get('unrealized_pnl', 0),
                    },
                    market_data={
                        'spot_price': position.get('greeks', {}).get('spot', 0),
                    },
                    greeks=position.get('greeks', {}),
                    strategy_tag='manual_close',
                )
            except Exception as e:
                log.warning(f"Failed to log trade: {e}")
        
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
        log.error(f"Failed to close options position: {e}")
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
        
        # Validate order size first
        try:
            async def validate():
                await validate_order_size(client, symbol, float(size), side, is_close=False)
            asyncio.run(validate())
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid order size: {str(e)}'
            }), 400
        
        # Get ticker for liquidity check and mid-price display with timeout
        async def check_liquidity():
            ticker = await with_timeout(
                client.get_option_ticker(symbol),
                timeout_seconds=10
            )
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
        
        # Execute add order using smart order with timeout
        async def place_add_order():
            return await with_timeout(
                place_smart_order(
                    client=client,
                    symbol=symbol,
                    size=float(size),
                    side=side,
                    order_preference=order_preference
                ),
                timeout_seconds=30
            )
        
        result = asyncio.run(place_add_order())
        # Note: _last_order_time is managed by the @rate_limit decorator
        
        execution_type = result.get('execution_type', 'unknown')
        fill_price = result.get('fill_price') or result.get('limit_price') or result.get('average_fill_price')
        
        # Log trade for ML learning
        if TRADE_LOGGING_ENABLED and trade_logger:
            try:
                # Get current position for context
                async def get_position():
                    positions = await client.get_all_positions_with_options()
                    for pos in positions['options']:
                        if pos.get('product_symbol') == symbol:
                            return pos
                    return {}
                
                position = asyncio.run(get_position())
                
                trade_logger.log_trade(
                    symbol=symbol,
                    action=side.upper(),
                    quantity=int(size),
                    price=float(fill_price) if fill_price else float(mid_price),
                    side='OPEN',
                    position_before={
                        'size': position.get('size', 0) - (int(size) if side == 'buy' else -int(size)),
                        'entry_price': position.get('entry_price', 0),
                        'unrealized_pnl': 0,
                    },
                    market_data={
                        'spot_price': position.get('greeks', {}).get('spot', 0),
                    },
                    greeks=position.get('greeks', {}),
                    strategy_tag='manual_add',
                )
            except Exception as e:
                log.warning(f"Failed to log trade: {e}")
        
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
        log.error(f"Failed to add to options position: {e}")
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


# =============================================================================
# STOP-LOSS / TAKE-PROFIT API ENDPOINTS
# =============================================================================

from webui.backend.options_strategy.sl_tp_manager import get_sl_tp_manager
from webui.backend.options_strategy.sl_tp_monitor import get_sl_tp_monitor
from webui.backend.options_strategy.max_loss_manager import get_max_loss_manager

@options_bp.route('/sl-tp/test-tp-order/<symbol>', methods=['POST'])
def test_tp_order(symbol):
    """
    TEST ENDPOINT: Debug TP order placement for a specific symbol.
    
    Request Body:
        {
            "take_profit_price": 1.0
        }
    """
    try:
        data = request.get_json() or {}
        take_profit_price = data.get('take_profit_price', 1.0)
        
        log.info(f"🧪 TEST: Starting TP order test for {symbol} @ ${take_profit_price}")
        
        async def test_place_tp():
            try:
                client = get_unified_client()
                log.info(f"✅ Client created: {type(client).__name__}")
                
                # Step 1: Fetch positions
                log.info(f"🔍 Step 1: Fetching positions...")
                positions_response = await client.get_all_positions_with_options()
                log.info(f"✅ Positions fetched: {type(positions_response)}")
                log.info(f"📊 Keys in response: {list(positions_response.keys()) if isinstance(positions_response, dict) else 'NOT A DICT'}")
                
                if isinstance(positions_response, dict):
                    options_list = positions_response.get('options', [])
                    log.info(f"📊 Found {len(options_list)} options positions")
                    
                    # Step 2: Find the specific position
                    log.info(f"🔍 Step 2: Looking for position {symbol}...")
                    position = None
                    for idx, pos in enumerate(options_list):
                        pos_symbol = pos.get('product_symbol')
                        log.info(f"  Position {idx}: {pos_symbol} (size: {pos.get('size')})")
                        if pos_symbol == symbol:
                            position = pos
                            log.info(f"✅ Found target position at index {idx}")
                            break
                    
                    if not position:
                        return {
                            'success': False,
                            'error': f'Position {symbol} not found',
                            'available_symbols': [p.get('product_symbol') for p in options_list[:5]]
                        }
                    
                    # Step 3: Determine order parameters
                    position_size = position.get('size', 0)
                    close_side = 'sell' if position_size > 0 else 'buy'
                    order_size = abs(position_size)
                    
                    log.info(f"📊 Step 3: Order params - size={order_size}, side={close_side}")
                    
                    # Step 4: Check for existing TP orders
                    log.info(f"🔍 Step 4: Checking for existing TP orders...")
                    try:
                        open_orders = await client.rest_client.get_open_orders_by_symbol(symbol)
                        log.info(f"📊 Found {len(open_orders)} open orders")
                        for order in open_orders:
                            log.info(f"  Order: {order.get('id')} - {order.get('side')} @ {order.get('limit_price')} (reduce_only: {order.get('reduce_only')})")
                    except Exception as e:
                        log.warning(f"⚠️ Could not fetch open orders: {e}")
                    
                    # Step 5: Place TP order
                    log.info(f"🎯 Step 5: Placing TP order: {close_side} {order_size} @ ${take_profit_price}")
                    order_result = await place_options_order(
                        client=client,
                        product_symbol=symbol,
                        size=order_size,
                        side=close_side,
                        order_type='limit_order',
                        limit_price=take_profit_price,
                        reduce_only=True
                    )
                    
                    log.info(f"✅ TP order placed! Order ID: {order_result.get('id')}")
                    
                    return {
                        'success': True,
                        'order_id': order_result.get('id'),
                        'side': close_side,
                        'size': order_size,
                        'price': take_profit_price,
                        'position': position
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Invalid response type from get_all_positions_with_options',
                        'response_type': str(type(positions_response))
                    }
                    
            except Exception as e:
                log.error(f"❌ Test failed: {e}", exc_info=True)
                return {
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
        
        result = asyncio.run(test_place_tp())
        return jsonify(result)
        
    except Exception as e:
        log.error(f"❌ Test endpoint error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@options_bp.route('/sl-tp/set', methods=['POST'])
def set_sl_tp():
    """
    Set stop-loss and take-profit for an options position.
    
    ⚠️ CRITICAL: When take_profit_price is set, this will IMMEDIATELY place a 
    reduce-only LIMIT order on the exchange at that price.
    
    Any existing TP orders for this symbol will be cancelled first.
    
    Request Body:
        {
            "symbol": "P-BTC-94000-140126",
            "stop_loss_pct": -20,          // % loss to trigger (negative)
            "stop_loss_price": 30.0,       // Or absolute price
            "take_profit_pct": 50,         // % profit to trigger
            "take_profit_price": 100.0,    // Or absolute price - PLACES IMMEDIATE ORDER
            "trailing_stop_enabled": false,
            "trailing_stop_pct": 10,       // Trail by this %
            "auto_execute": true,          // Auto-close when triggered
            "alert_only": false            // Only alert, don't execute
        }
    """
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        
        if not symbol:
            return jsonify({"success": False, "error": "Symbol required"}), 400
        
        # Get take profit price if specified
        take_profit_price = data.get('take_profit_price')
        
        # Store SL/TP settings in database
        manager = get_sl_tp_manager()
        result = manager.set_sl_tp(
            symbol=symbol,
            stop_loss_price=data.get('stop_loss_price'),
            stop_loss_pct=data.get('stop_loss_pct'),
            take_profit_price=take_profit_price,
            take_profit_pct=data.get('take_profit_pct'),
            trailing_stop_enabled=data.get('trailing_stop_enabled', False),
            trailing_stop_pct=data.get('trailing_stop_pct'),
            auto_execute=data.get('auto_execute', True),
            alert_only=data.get('alert_only', False)
        )
        
        log.info(f"SL/TP set for {symbol}: {result}")
        
        # If take_profit_price is set and alert_only is False, place limit order immediately
        if take_profit_price and not data.get('alert_only', False):
            tp_order_placed = False
            try:
                # Get current position to determine size and side
                async def place_tp_order():
                    try:
                        client = get_unified_client()
                        
                        # Get current position
                        log.info(f"🔍 Fetching positions to place TP order for {symbol}...")
                        positions_response = await client.get_all_positions_with_options()
                        
                        if not positions_response or not isinstance(positions_response, dict):
                            log.error(f"❌ Invalid positions response: {type(positions_response)}")
                            raise Exception("Failed to fetch positions: Invalid response format")
                        
                        # Find the position (uses 'options' key from the response)
                        position = None
                        options_list = positions_response.get('options', [])
                        log.info(f"📊 Found {len(options_list)} total options positions")
                        
                        for pos in options_list:
                            if pos.get('product_symbol') == symbol:
                                position = pos
                                break
                        
                        if not position:
                            log.error(f"❌ Position {symbol} not found in {len(options_list)} positions")
                            raise Exception(f"Position not found for symbol {symbol}")
                    
                    except Exception as fetch_error:
                        log.error(f"❌ Error in position fetch: {fetch_error}", exc_info=True)
                        raise
                    
                    # Determine order size and side
                    position_size = position.get('size', 0)
                    if position_size == 0:
                        raise Exception("Position size is zero")
                    
                    # For closing: if we have positive size (bought), we SELL to close
                    # If we have negative size (sold), we BUY to close
                    close_side = 'sell' if position_size > 0 else 'buy'
                    order_size = abs(position_size)
                    
                    # Cancel any existing TP orders for this symbol first
                    log.info(f"🔍 Checking for existing TP orders for {symbol}...")
                    try:
                        open_orders = await client.rest_client.get_open_orders_by_symbol(symbol)
                        cancelled_orders = []
                        
                        for order in open_orders:
                            # Check if it's a reduce-only order (likely a TP order)
                            if order.get('reduce_only'):
                                order_id = order.get('id')
                                log.info(f"🗑️  Cancelling existing TP order: {order_id}")
                                try:
                                    await client.rest_client.cancel_order(order_id)
                                    cancelled_orders.append(order_id)
                                except Exception as e:
                                    log.warning(f"Failed to cancel order {order_id}: {e}")
                        
                        if cancelled_orders:
                            log.info(f"✅ Cancelled {len(cancelled_orders)} existing TP order(s)")
                    except Exception as e:
                        log.warning(f"Failed to check/cancel existing orders: {e}")
                    
                    log.info(f"🎯 Placing TP limit order: {close_side} {order_size} {symbol} @ ${take_profit_price}")
                    
                    # Place reduce-only limit order at take profit price
                    order_result = await place_options_order(
                        client=client,
                        product_symbol=symbol,
                        size=order_size,
                        side=close_side,
                        order_type='limit_order',
                        limit_price=take_profit_price,
                        reduce_only=True
                    )
                    
                    order_id = order_result.get('id')
                    log.info(f"✅ TP order placed successfully: {order_id}")
                    
                    return {
                        'success': True,
                        'order_id': order_id,
                        'side': close_side,
                        'size': order_size,
                        'price': take_profit_price
                    }
                
                # Execute the async order placement with timeout
                tp_order_result = asyncio.run(with_timeout(place_tp_order(), timeout_seconds=30))
                result['tp_order'] = tp_order_result
                tp_order_placed = True
                log.info(f"✅ Take profit order placed on exchange: {tp_order_result}")
                
            except Exception as e:
                log.error(f"❌ CRITICAL: Failed to place TP order on exchange: {e}", exc_info=True)
                
                # ROLLBACK: Remove settings from database to prevent inconsistency
                if not tp_order_placed:
                    log.warning(f"🔄 Rolling back SL/TP settings for {symbol} due to TP order failure")
                    try:
                        manager.remove_sl_tp(symbol)
                        log.info(f"✅ Successfully rolled back SL/TP settings")
                    except Exception as rollback_err:
                        log.error(f"❌ Rollback failed: {rollback_err}")
                
                return jsonify({
                    'success': False,
                    'error': f'Failed to place TP order on exchange: {str(e)}',
                    'rollback': 'SL/TP settings were not saved (rollback performed)'
                }), 500
        
        return jsonify(result)
    
    except Exception as e:
        log.error(f"Error setting SL/TP: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/sl-tp/get/<symbol>', methods=['GET'])
def get_sl_tp(symbol):
    """Get SL/TP settings for a specific symbol"""
    try:
        manager = get_sl_tp_manager()
        settings = manager.get_sl_tp(symbol)
        
        return jsonify({
            "success": True,
            "settings": settings
        })
    
    except Exception as e:
        log.error(f"Error getting SL/TP: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/sl-tp/remove/<symbol>', methods=['DELETE'])
def remove_sl_tp(symbol):
    """
    Remove SL/TP settings for a symbol.
    
    This will also cancel any existing TP orders on the exchange.
    """
    try:
        # Cancel any existing TP orders first
        async def cancel_tp_orders():
            client = get_unified_client()
            
            try:
                log.info(f"🔍 Checking for TP orders to cancel for {symbol}...")
                open_orders = await client.rest_client.get_open_orders_by_symbol(symbol)
                cancelled_orders = []
                
                for order in open_orders:
                    # Check if it's a reduce-only order (likely a TP order)
                    if order.get('reduce_only'):
                        order_id = order.get('id')
                        product_id = order.get('product_id')
                        order_side = order.get('side', 'unknown')
                        order_price = order.get('limit_price', 'N/A')
                        log.info(f"🗑️  Cancelling TP order: {order_id} ({order_side} @ ${order_price})")
                        try:
                            # Cancel order requires both order_id and product_id
                            await client.rest_client.cancel_order(order_id, product_id)
                            cancelled_orders.append({
                                'id': order_id,
                                'side': order_side,
                                'price': order_price
                            })
                            log.info(f"✅ Successfully cancelled TP order {order_id}")
                        except Exception as e:
                            log.error(f"❌ Failed to cancel order {order_id}: {e}")
                
                if cancelled_orders:
                    log.info(f"✅ Cancelled {len(cancelled_orders)} TP order(s)")
                
                return {
                    'cancelled_orders': cancelled_orders,
                    'count': len(cancelled_orders)
                }
            except Exception as e:
                log.warning(f"Failed to cancel TP orders: {e}")
                return {'error': str(e)}
        
        # Execute cancellation
        cancel_result = asyncio.run(cancel_tp_orders())
        
        # Remove from database
        manager = get_sl_tp_manager()
        result = manager.remove_sl_tp(symbol)
        
        # Add cancellation info to result
        if 'cancelled_orders' in cancel_result:
            result['cancelled_tp_orders'] = cancel_result['cancelled_orders']
        
        return jsonify(result)
    
    except Exception as e:
        log.error(f"Error removing SL/TP: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/max-loss/strike/all', methods=['GET'])
def get_all_max_loss():
    """Get max loss settings for all strikes."""
    try:
        manager = get_max_loss_manager()
        settings = manager.get_all_strike_max_loss()
        return jsonify({
            'success': True,
            'settings': settings
        })
    except Exception as e:
        log.error(f"Error getting max loss settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/max-loss/strike/set', methods=['POST'])
def set_strike_max_loss():
    """Set max loss for a specific strike."""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        max_loss = data.get('max_loss')
        
        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        if not max_loss or max_loss <= 0:
            return jsonify({'success': False, 'error': 'Valid max_loss required (positive number)'}), 400
        
        manager = get_max_loss_manager()
        result = manager.set_strike_max_loss(symbol, float(max_loss))
        
        if result.get('success'):
            log.info(f"✅ Max loss set for {symbol}: ${max_loss}")
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        log.error(f"Error setting strike max loss: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/max-loss/strike/remove/<path:symbol>', methods=['DELETE'])
def remove_strike_max_loss(symbol):
    """Remove max loss setting for a specific strike."""
    try:
        manager = get_max_loss_manager()
        result = manager.remove_strike_max_loss(symbol)
        
        if result.get('success'):
            log.info(f"✅ Max loss removed for {symbol}")
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        log.error(f"Error removing strike max loss: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/max-loss/expiry/all', methods=['GET'])
def get_all_max_loss_by_expiry():
    """Get max loss settings for all expiries."""
    try:
        manager = get_max_loss_manager()
        settings = manager.get_all_expiry_max_loss()
        return jsonify({
            'success': True,
            'settings': settings
        })
    except Exception as e:
        log.error(f"Error getting expiry max loss settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/max-loss/expiry/set', methods=['POST'])
def set_expiry_max_loss():
    """Set max loss for a specific expiry."""
    try:
        data = request.get_json()
        expiry_code = data.get('expiry_code')
        max_loss = data.get('max_loss')
        
        if not expiry_code:
            return jsonify({'success': False, 'error': 'expiry_code required'}), 400
        if not max_loss or max_loss <= 0:
            return jsonify({'success': False, 'error': 'Valid max_loss required (positive number)'}), 400
        
        manager = get_max_loss_manager()
        result = manager.set_expiry_max_loss(expiry_code, float(max_loss))
        
        if result.get('success'):
            log.info(f"✅ Expiry max loss set for {expiry_code}: ${max_loss}")
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        log.error(f"Error setting expiry max loss: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/max-loss/expiry/remove/<expiry_code>', methods=['DELETE'])
def remove_expiry_max_loss(expiry_code):
    """Remove max loss setting for a specific expiry."""
    try:
        manager = get_max_loss_manager()
        result = manager.remove_expiry_max_loss(expiry_code)
        
        if result.get('success'):
            log.info(f"✅ Expiry max loss removed for {expiry_code}")
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        log.error(f"Error removing expiry max loss: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/sl-tp/all', methods=['GET'])
def get_all_sl_tp():
    """Get all active SL/TP settings"""
    try:
        manager = get_sl_tp_manager()
        settings = manager.get_all_active_sl_tp()
        return jsonify({
            "success": True,
            "settings": settings,
            "count": len(settings)
        })
    
    except Exception as e:
        log.error(f"Error getting all SL/TP: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/sl-tp/history', methods=['GET'])
def get_sl_tp_history():
    """Get SL/TP trigger history"""
    try:
        limit = request.args.get('limit', 50, type=int)
        symbol = request.args.get('symbol')
        
        manager = get_sl_tp_manager()
        history = manager.get_history(limit=limit, symbol=symbol)
        
        return jsonify({
            "success": True,
            "history": history,
            "count": len(history)
        })
    
    except Exception as e:
        log.error(f"Error getting SL/TP history: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/sl-tp/monitor/status', methods=['GET'])
def get_monitor_status():
    """Get SL/TP monitor status"""
    try:
        monitor = get_sl_tp_monitor()
        return jsonify({
            "success": True,
            "status": monitor.get_status()
        })
    
    except Exception as e:
        log.error(f"Error getting monitor status: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/sl-tp/monitor/start', methods=['POST'])
def start_monitor():
    """Start SL/TP monitor service"""
    try:
        from webui.backend.options_strategy.sl_tp_monitor import init_sl_tp_monitoring
        from bot.api.unified_api_client import UnifiedAPIClient
        
        # Get credentials properly
        creds = get_api_credentials()
        log.info(f"Starting SL/TP monitor with API key: {creds['api_key'][:8]}...")
        
        api_client = UnifiedAPIClient(
            api_key=creds['api_key'],
            api_secret=creds['api_secret'],
            symbol='BTCUSD',
            enable_websocket=False
        )
        manager = get_sl_tp_manager()
        
        monitor = init_sl_tp_monitoring(api_client, manager, auto_start=True)
        
        return jsonify({
            "success": True,
            "message": "SL/TP monitor started",
            "status": monitor.get_status()
        })
    
    except Exception as e:
        log.error(f"Error starting monitor: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
    
    except Exception as e:
        log.error(f"Error starting monitor: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/sl-tp/monitor/stop', methods=['POST'])
def stop_monitor():
    """Stop SL/TP monitor service"""
    try:
        monitor = get_sl_tp_monitor()
        monitor.stop()
        
        return jsonify({
            "success": True,
            "message": "SL/TP monitor stopped"
        })
    
    except Exception as e:
        log.error(f"Error stopping monitor: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


def execute_close_order(symbol: str, order_preference: str = 'market_only') -> dict:
    """
    Execute close order - used by SL/TP monitor.
    
    Args:
        symbol: Option symbol to close
        order_preference: Order type preference
        
    Returns:
        dict with success status and order info
    """
    try:
        client = get_unified_client()
        
        # Async wrapper to fetch position and execute close
        async def fetch_and_close():
            # Get current position (proper async call)
            positions_response = await client.get_all_positions_with_options()
            
            if not positions_response or not isinstance(positions_response, dict):
                raise Exception("Failed to fetch positions")
            
            # Find the position (uses 'options' key from the response)
            positions = positions_response.get('options', [])
            position = next((p for p in positions if p.get('product_symbol') == symbol), None)
            
            if not position:
                raise Exception(f'Position {symbol} not found')
            
            size = abs(position.get('size', 0))
            
            if size == 0:
                raise Exception('Position size is 0')
            
            close_side = determine_close_side(position.get('size', 0))
            
            log.info(f"🔄 SL/TP Monitor: Executing close for {symbol} - size={size} side={close_side}")
            
            # Execute close order with reduce_only flag for safety
            result = await place_smart_order(
                client=client,
                symbol=symbol,
                size=float(size),
                side=close_side,
                order_preference=order_preference,
                reduce_only=True  # Safety flag to prevent opening new positions
            )
            
            return {
                'success': True,
                'order_id': result.get('id'),  # Correct key from place_options_order response
                'execution_type': result.get('execution_type'),
                'fill_price': result.get('fill_price') or result.get('average_fill_price'),
                'size': size,
                'side': close_side,
                'symbol': symbol
            }
        
        # Execute async operation
        result = asyncio.run(fetch_and_close())
        log.info(f"✅ SL/TP close executed successfully: {result}")
        return result
        
    except Exception as e:
        log.error(f"❌ Error executing SL/TP close order for {symbol}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'symbol': symbol
        }

