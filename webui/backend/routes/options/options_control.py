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

from __future__ import annotations

import sys
import time
import asyncio
from typing import Optional
import logging
import threading
from pathlib import Path
from functools import wraps
from flask import Blueprint, jsonify, request, make_response
from webui.backend.sealed import sealed


# ---------------------------------------------------------------------------
# Infrastructure: event loop, client singleton, async helpers
# ---------------------------------------------------------------------------
# Moved to options_client.py — re-exported here for backward compatibility.
# DO NOT remove these re-exports until all callers are updated (Phase 6).
# ---------------------------------------------------------------------------
from .options_client import _run_async, get_unified_client, with_timeout

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config, get_api_credentials
from bot.options.utils.options_helper import (
    enrich_position_data,
    determine_close_side,
)

# Import options notifier for Telegram alerts
try:
    from bot.options.notifications.options_notifier import get_options_notifier
    NOTIFICATIONS_ENABLED = True
except Exception as e:
    print(f"⚠️ Options notifier not available: {e}")
    get_options_notifier = None
    NOTIFICATIONS_ENABLED = False

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

# ---------------------------------------------------------------------------
# Order execution: constants + functions
# ---------------------------------------------------------------------------
# Moved to order_executor.py — re-exported here for backward compatibility.
# DO NOT remove these re-exports until all callers are updated (Phase 6).
# ---------------------------------------------------------------------------
from .order_executor import (
    ORDER_TYPE_MAKER_FIRST, ORDER_TYPE_MAKER_ONLY, ORDER_TYPE_MARKET_ONLY,
    ORDER_TYPE_SSR, VALID_ORDER_TYPES,
    cancel_order_with_verification, validate_order_size,
    place_options_order, modify_order_price, fetch_fresh_orderbook_quotes,
    place_smart_order,
)

# ---------------------------------------------------------------------------
# SSR monitoring: registry + monitoring threads + order placement
# ---------------------------------------------------------------------------
# Moved to ssr_monitor.py — re-exported here for backward compatibility.
# DO NOT remove these re-exports until all callers are updated (Phase 6).
# ---------------------------------------------------------------------------
from .ssr_monitor import (
    place_ssr_order, place_ssr_order_with_margin,
    get_active_ssr_orders, _active_ssr_orders, _ssr_lock,
)

# ---------------------------------------------------------------------------
# Delta Hedge — moved to delta_hedge.py
# ---------------------------------------------------------------------------
# Routes are registered below after blueprint creation.
# Hedge events accessor imported for activity-log route.
from .delta_hedge import get_hedge_events_snapshot, register_delta_hedge_routes


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
    """Decorator to prevent duplicate orders within 3 seconds"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        global _pending_orders
        
        # Get request data
        try:
            data = request.get_json() or {}
            # Create unique hash from request - INCLUDE order_preference to differentiate market vs limit
            import hashlib
            order_pref = data.get('order_preference', 'maker_first')
            request_str = f"{data.get('symbol')}_{data.get('size')}_{data.get('side')}_{order_pref}"
            request_hash = hashlib.md5(request_str.encode()).hexdigest()
            
            # Also create a simpler hash for market orders specifically (more strict)
            if order_pref == 'market_only':
                market_str = f"MARKET_{data.get('symbol')}_{data.get('size')}_{data.get('side')}"
                market_hash = hashlib.md5(market_str.encode()).hexdigest()
            else:
                market_hash = None
        except:
            return f(*args, **kwargs)  # Continue if we can't hash
        
        now = time.time()
        
        # Clean old entries
        _pending_orders = {k: v for k, v in _pending_orders.items() 
                          if now - v < DUPLICATE_WINDOW_SECONDS}
        
        # Check for duplicate (regular hash)
        if request_hash in _pending_orders:
            elapsed = now - _pending_orders[request_hash]
            log.warning(f"🛑 DUPLICATE ORDER BLOCKED: {request_str} (submitted {elapsed:.1f}s ago)")
            return jsonify({
                'success': False,
                'error': f'Duplicate order blocked. Same order submitted {elapsed:.1f}s ago.'
            }), 429
        
        # EXTRA CHECK: For market orders, also check the market-specific hash
        if market_hash and market_hash in _pending_orders:
            elapsed = now - _pending_orders[market_hash]
            log.warning(f"🛑 DUPLICATE MARKET ORDER BLOCKED: {request_str} (submitted {elapsed:.1f}s ago)")
            return jsonify({
                'success': False,
                'error': f'Duplicate market order blocked. Same market order submitted {elapsed:.1f}s ago.'
            }), 429
        
        # Mark as pending (both hashes for market orders)
        _pending_orders[request_hash] = now
        if market_hash:
            _pending_orders[market_hash] = now
        
        try:
            result = f(*args, **kwargs)
            # Remove from pending on successful execution
            _pending_orders.pop(request_hash, None)
            if market_hash:
                _pending_orders.pop(market_hash, None)
            return result
        except Exception as e:
            # Remove from pending on error too
            _pending_orders.pop(request_hash, None)
            if market_hash:
                _pending_orders.pop(market_hash, None)
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






# Position cache to prevent repeated failures
_positions_cache = {'data': None, 'time': 0, 'error': None}
POSITIONS_CACHE_SECONDS = 10.0  # Cache positions for 10 seconds (was 3s — too short)

# Bulk tickers cache — one /v2/tickers call enriches ALL positions (vs 45 individual calls)
# This prevents circuit-breaker trips from concurrent per-symbol API hammering.
_tickers_cache = {'data': None, 'time': 0}
TICKERS_CACHE_SECONDS = 8.0  # Slightly shorter than positions cache so it stays fresh

# One-at-a-time fetch lock — prevents concurrent greenlets from each launching
# their own _run_async(fetch()) when the cache expires simultaneously.
# With eventlet's patched Lock, waiting greenlets yield (don't block the worker).
import threading as _threading
_positions_fetch_lock = _threading.Lock()


def get_cached_positions(max_age=30.0):
    """Return cached positions for internal background monitors (no HTTP self-call).

    Background monitors (sl_tp_monitor, take_profit_manager, max_loss_manager)
    previously called http://localhost:5555/api/options/positions which could
    deadlock the single eventlet worker. This function reads the shared cache
    directly — zero network overhead, zero deadlock risk.

    Returns list of enriched position dicts, or None if cache is too stale.
    """
    if _positions_cache['data'] is not None:
        age = time.time() - _positions_cache['time']
        if age < max_age:
            return list(_positions_cache['data'])
    return None


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
    
    # Fast path: return cached data without acquiring the lock
    now = time.time()
    if now - _positions_cache['time'] < POSITIONS_CACHE_SECONDS and _positions_cache['data'] is not None:
        return jsonify({
            'success': True,
            'positions': _positions_cache['data'],
            'count': len(_positions_cache['data']),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'cached': True
        })
    
    # Slow path: acquire lock so only ONE greenlet fetches at a time.
    # Other greenlets that arrive while the fetch is in progress will wait here
    # (eventlet's patched Lock yields cooperatively), then see the fresh cache
    # on the second check below and return without re-fetching.
    with _positions_fetch_lock:
        # Double-check: another greenlet may have refreshed the cache while
        # we were waiting to acquire the lock.
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
            
            # Run async code using ONE bulk tickers call instead of N individual calls.
            # This is the key fix: /v2/tickers returns ALL 1000+ tickers in a single request,
            # completely eliminating the 45-concurrent-request storm that trips the circuit breaker.
            async def fetch():
                global _tickers_cache

                positions_result = await client.get_all_positions_with_options()
                options = positions_result['options']

                # Fetch ALL tickers in one API call (1 call vs 45 individual calls)
                tickers_age = time.time() - _tickers_cache['time']
                if _tickers_cache['data'] is not None and tickers_age < TICKERS_CACHE_SECONDS:
                    all_tickers = _tickers_cache['data']
                else:
                    all_tickers = await client.rest_client.get_all_tickers()
                    _tickers_cache['data'] = all_tickers
                    _tickers_cache['time'] = time.time()

                # Build symbol→ticker lookup map once
                ticker_map = {t.get('symbol'): t for t in all_tickers if t.get('symbol')}

                # Enrich each position from the map — zero additional API calls
                enriched = []
                for pos in options:
                    symbol = pos.get('product_symbol', '')
                    raw_ticker = ticker_map.get(symbol)
                    if raw_ticker:
                        # Wrap raw ticker into the shape enrich_position_data expects
                        quotes = raw_ticker.get('quotes', {})
                        best_bid = float(quotes.get('best_bid') or 0)
                        best_ask = float(quotes.get('best_ask') or 0)
                        spread_pct = 0
                        if best_bid > 0 and best_ask > 0:
                            spread_pct = ((best_ask - best_bid) / best_bid) * 100
                        ticker = {
                            'symbol': symbol,
                            'mark_price': float(raw_ticker.get('mark_price') or 0),
                            'spot_price': float(raw_ticker.get('spot_price') or 0),
                            'strike_price': float(raw_ticker.get('strike_price') or 0),
                            'bid': best_bid,
                            'ask': best_ask,
                            'spread_pct': spread_pct,
                            'greeks': raw_ticker.get('greeks', {}),
                            'quotes': quotes,
                            'volume': float(raw_ticker.get('volume') or 0),
                            'open_interest': raw_ticker.get('open_interest', 0),
                            'mark_vol': float(raw_ticker.get('mark_vol') or 0),
                            'raw': raw_ticker,
                        }
                        enriched.append(enrich_position_data(pos, ticker))
                    else:
                        log.debug(f"No bulk ticker found for {symbol}, using raw position")
                        enriched.append(pos)

                return enriched
            
            options = _run_async(fetch())
            
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


@options_bp.route('/ssr-status', methods=['GET'])
def get_ssr_status():
    """
    Get status of active SSR orders being monitored in background.

    Returns:
        JSON: List of active SSR orders with their current status
    """
    active_orders = get_active_ssr_orders()

    return jsonify({
        'success': True,
        'active_ssr_orders': active_orders,
        'count': len(active_orders),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    })


@options_bp.route('/activity-log', methods=['GET'])
def get_options_activity_log():
    """
    Get comprehensive options trading activity including SSR orders, positions, P&L, and max loss.
    Uses cached positions data for efficiency.
    
    Returns:
        JSON: {
            success: bool,
            ssrOrders: [...],           # Active SSR orders with tracking
            recentOrders: [...],         # Last 20 orders from all sources
            positions: [...],            # Current positions with P&L
            maxLoss: float,              # Total max loss across all positions
            totalPnL: float,             # Unrealized P&L
            recentLogs: [...],           # Last 50 log entries
            timestamp: str
        }
    """
    global _positions_cache
    from pathlib import Path

    try:
        # Get active SSR orders
        raw_ssr = get_active_ssr_orders()
        ssr_orders = [
            {
                'orderId': entry['order_id'],
                'symbol': entry.get('symbol'),
                'side': entry.get('side'),
                'size': entry.get('size'),
                'currentPrice': entry.get('current_price'),
                'adjustments': entry.get('adjustments', 0),
                'status': entry.get('status', 'unknown'),
                'elapsedSeconds': entry.get('elapsed_seconds', 0),
                'ssrMode': entry.get('ssr_mode', 'standard'),
                'marginPercent': entry.get('margin_percent', 0),
            }
            for entry in raw_ssr
        ]
        
        # Get current positions from cache or fetch fresh
        positions_data = []
        total_pnl = 0
        max_loss = 0
        position_count = 0
        
        try:
            # Use cached positions if available (updated by /positions endpoint)
            if _positions_cache['data'] is not None:
                positions = _positions_cache['data']
            else:
                # Fetch positions fresh if no cache
                import asyncio
                client = get_unified_client()
                
                async def fetch_positions():
                    all_pos = await client.get_all_positions_with_options()
                    return all_pos.get('options', [])
                
                positions = _run_async(fetch_positions())
                _positions_cache['data'] = positions
                _positions_cache['time'] = time.time()
            
            for pos in positions:
                size = pos.get('size', 0)
                if size == 0:
                    continue
                    
                position_count += 1
                entry_price = pos.get('entry_price', 0)
                mark_price = pos.get('mark_price', 0)
                unrealized_pnl = pos.get('unrealized_pnl', 0)
                
                # Use pre-calculated PnL if available
                if unrealized_pnl == 0 and entry_price and mark_price:
                    if size > 0:  # Long position
                        unrealized_pnl = (mark_price - entry_price) * size
                    else:  # Short position
                        unrealized_pnl = (entry_price - mark_price) * abs(size)
                
                total_pnl += unrealized_pnl
                
                # Max loss calculation (for long options = premium paid)
                position_max_loss = 0
                if size > 0:
                    position_max_loss = entry_price * size
                    max_loss += position_max_loss
                
                positions_data.append({
                    'symbol': pos.get('product_symbol', 'N/A'),
                    'size': size,
                    'entryPrice': round(entry_price, 2),
                    'markPrice': round(mark_price, 2),
                    'unrealizedPnL': round(unrealized_pnl, 2),
                    'maxLoss': round(position_max_loss, 2)
                })
        except Exception as e:
            log.warning(f"Could not fetch positions for activity log: {e}")
        
        # Get recent orders from order history file if available
        recent_orders = []
        try:
            order_history_file = Path('/Users/ssr/Projects/WorkingBot/data/order_history.json')
            if order_history_file.exists():
                import json
                with open(order_history_file, 'r') as f:
                    history = json.load(f)
                    orders = history if isinstance(history, list) else history.get('orders', [])
                    for order in orders[-20:]:
                        recent_orders.append({
                            'id': order.get('id', order.get('order_id')),
                            'symbol': order.get('symbol', order.get('product_symbol', 'N/A')),
                            'side': order.get('side'),
                            'size': order.get('size', order.get('quantity')),
                            'fillPrice': order.get('fill_price', order.get('price')),
                            'state': order.get('state', order.get('status', 'filled')),
                            'createdAt': order.get('created_at', order.get('timestamp'))
                        })
        except Exception as e:
            log.debug(f"Order history not available: {e}")
        
        # Read recent log entries from correct log file location
        recent_logs = []
        try:
            log_file = Path('/Users/ssr/Projects/WorkingBot/logs/launchagent_webui.log')
            if log_file.exists():
                with open(log_file, 'r', errors='ignore') as f:
                    # Read last 50KB of file for efficiency
                    f.seek(0, 2)  # Go to end
                    file_size = f.tell()
                    read_size = min(50000, file_size)
                    f.seek(max(0, file_size - read_size))
                    content = f.read()
                    lines = content.split('\n')
                    
                    # Get lines that contain relevant keywords
                    relevant_lines = [
                        line.strip() for line in lines
                        if line.strip() and any(keyword in line.lower() for keyword in 
                            ['ssr', 'order', 'filled', 'placed', 'position', 'trade', 'max loss', 'sl/tp', 'close'])
                    ]
                    recent_logs = relevant_lines[-30:]  # Last 30 relevant entries
            else:
                recent_logs = ["📋 Log file not found - check backend logs"]
        except Exception as e:
            log.warning(f"Could not read log file: {e}")
            recent_logs = [f"⚠️ Log unavailable: {str(e)}"]
        
        return jsonify({
            'success': True,
            'ssrOrders': ssr_orders,
            'ssrCount': len(ssr_orders),
            'recentOrders': recent_orders,
            'positions': positions_data,
            'positionCount': position_count,
            'maxLoss': round(max_loss, 2),
            'totalPnL': round(total_pnl, 2),
            'recentLogs': recent_logs,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        log.error(f"❌ Activity log error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'ssrOrders': [],
            'ssrCount': 0,
            'recentOrders': [],
            'positions': [],
            'positionCount': 0,
            'maxLoss': 0,
            'totalPnL': 0,
            'recentLogs': [f"❌ Error: {str(e)}"],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }), 500


@options_bp.route('/ssr-order', methods=['POST'])
def place_ssr_order_endpoint():
    """
    Place SSR (Stealth Sniper Repricing) order with different pricing strategies.
    
    Request body:
        {
            "symbol": "C-BTC-113000-300126",
            "side": "buy" or "sell",
            "quantity": 1,
            "ssrMode": "standard" | "aggressive" | "conservative"
        }
    
    SSR Modes:
        - standard: 2 ticks below/above 2nd best (default SSR behavior)
        - aggressive: Premium-based dynamic margin (3-8% below/above 2nd best)
        - conservative: 1-2% margin below/above 2nd best
    
    Response:
        {
            "success": true,
            "order": {...},
            "ssrTracking": {
                "orderId": 123456,
                "mode": "aggressive",
                "margin": 5.0
            }
        }
    """
    import asyncio
    
    try:
        data = request.json
        log.info(f"🏎️ Options SSR order request: {data}")
        
        symbol = data.get('symbol')
        side = data.get('side')
        quantity = data.get('quantity', 1)
        ssr_mode = data.get('ssrMode', 'standard')
        
        if not symbol:
            return jsonify({"success": False, "error": "Missing required parameter: symbol"}), 400
        
        if not side or side not in ['buy', 'sell']:
            return jsonify({"success": False, "error": "Invalid side (must be buy or sell)"}), 400
        
        # Calculate tick offset and margin based on SSR mode
        if ssr_mode == 'aggressive':
            # Premium-based aggressive: 3-8% margin
            tick_offset = None  # Use percentage-based pricing
            margin_percent = 5.0  # 5% default for aggressive
        elif ssr_mode == 'conservative':
            # Conservative: 1-2% margin
            tick_offset = None
            margin_percent = 1.5  # 1.5% default for conservative
        else:  # standard
            # Standard: 2 ticks
            tick_offset = 2
            margin_percent = None
        
        # Get client and place SSR order
        client = get_unified_client()
        
        if tick_offset is not None:
            # Standard mode: use tick-based offset
            result = _run_async(
                place_ssr_order(
                    client=client,
                    symbol=symbol,
                    size=quantity,
                    side=side,
                    tick_offset=tick_offset
                )
            )
        else:
            # Percentage-based mode: use margin pricing
            result = _run_async(
                place_ssr_order_with_margin(
                    client=client,
                    symbol=symbol,
                    size=quantity,
                    side=side,
                    margin_percent=margin_percent,
                    ssr_mode=ssr_mode
                )
            )
        
        if result and result.get('id'):
            order_id = result.get('id')
            return jsonify({
                "success": True,
                "order": result,
                "ssrTracking": {
                    "orderId": order_id,
                    "mode": ssr_mode,
                    "margin": margin_percent or 0,
                    "tickOffset": tick_offset or 0
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Failed to place SSR order')
            }), 400
            
    except Exception as e:
        log.error(f"❌ SSR order error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
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
        
        ticker = _run_async(client.get_option_ticker(symbol))
        
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


def _close_position_by_symbol(symbol: str):
    """Programmatic position close (used by alert actions). Raises on failure."""
    client = get_unified_client()

    async def _do_close():
        positions = await with_timeout(client.get_all_positions_with_options(), timeout_seconds=15)
        for pos in positions['options']:
            if pos.get('product_symbol') == symbol:
                position_size = float(pos.get('size', 0))
                side = determine_close_side(position_size)
                return await with_timeout(
                    place_smart_order(
                        client=client,
                        symbol=symbol,
                        size=abs(position_size),
                        side=side,
                        order_preference=ORDER_TYPE_MARKET_ONLY,
                        reduce_only=True,
                    ),
                    timeout_seconds=30,
                )
        raise ValueError(f"Position not found: {symbol}")

    result = _run_async(_do_close())
    log.info("_close_position_by_symbol: closed %s -> %s", symbol, result.get('execution_type', '?'))
    return result


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
        
        position = _run_async(get_position())
        
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
            _run_async(validate())
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
        
        result = _run_async(place_close_order())
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
        
        # Send Telegram notification for position close
        if NOTIFICATIONS_ENABLED and get_options_notifier:
            try:
                cfg = get_config()
                options_token = cfg.telegram.options_bot_token if hasattr(cfg.telegram, 'options_bot_token') else None
                options_chat = cfg.telegram.options_chat_id if hasattr(cfg.telegram, 'options_chat_id') else cfg.telegram.live_chat_id
                
                if options_token and options_chat:
                    notifier = get_options_notifier(token=options_token, chat_id=options_chat)
                    
                    # Calculate hold time
                    from datetime import datetime, timedelta
                    # Estimate hold time (would need to track open time in production)
                    hold_time = "Unknown"
                    
                    # Calculate P&L
                    entry_price = position.get('entry_price', 0)
                    pnl = (fill_price - entry_price) * float(close_size) if side == 'sell' else (entry_price - fill_price) * float(close_size)
                    pnl_pct = ((fill_price - entry_price) / entry_price * 100) if entry_price else 0
                    
                    notifier.notify_position_closed(
                        symbol=symbol,
                        entry_price=entry_price,
                        exit_price=fill_price,
                        size=int(close_size),
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        hold_time=hold_time,
                        side=side,
                        order_type=order_preference,
                        greeks=position.get('greeks', {}),
                        spot_price=position.get('greeks', {}).get('spot', 0)
                    )
            except Exception as e:
                log.warning(f"Failed to send close notification: {e}")
        
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
        limit_price = data.get('limit_price')  # Optional custom limit price
        
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
            _run_async(validate())
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
        
        ticker = _run_async(check_liquidity())
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
                    order_preference=order_preference,
                    limit_price=float(limit_price) if limit_price else None
                ),
                timeout_seconds=30
            )
        
        result = _run_async(place_add_order())
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
                
                position = _run_async(get_position())
                
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
        
        # Send Telegram notification for position opened/added
        if NOTIFICATIONS_ENABLED and get_options_notifier:
            try:
                cfg = get_config()
                options_token = cfg.telegram.options_bot_token if hasattr(cfg.telegram, 'options_bot_token') else None
                options_chat = cfg.telegram.options_chat_id if hasattr(cfg.telegram, 'options_chat_id') else cfg.telegram.live_chat_id
                
                if options_token and options_chat:
                    notifier = get_options_notifier(token=options_token, chat_id=options_chat)
                    
                    # Get updated position for notification
                    async def get_updated_position():
                        positions = await client.get_all_positions_with_options()
                        for pos in positions['options']:
                            if pos.get('product_symbol') == symbol:
                                return pos
                        return None
                    
                    updated_pos = _run_async(get_updated_position())
                    
                    if updated_pos:
                        new_size = updated_pos.get('size', 0)
                        avg_entry = updated_pos.get('entry_price', 0)
                        current_pnl = updated_pos.get('unrealized_pnl', 0)
                        pnl_pct = ((updated_pos.get('mark_price', fill_price) - avg_entry) / avg_entry * 100) if avg_entry else 0
                        
                        # Check if this is a new position or addition
                        old_size = new_size - (int(size) if side == 'buy' else -int(size))
                        
                        if old_size == 0:
                            # New position
                            notifier.notify_position_opened(
                                position=updated_pos,
                                fill_price=fill_price if fill_price else mid_price,
                                size=int(size),
                                side=side,
                                order_type=order_preference
                            )
                        else:
                            # Addition to existing
                            notifier.notify_position_added(
                                symbol=symbol,
                                added_size=int(size) if side == 'buy' else -int(size),
                                fill_price=fill_price if fill_price else mid_price,
                                old_size=old_size,
                                new_size=new_size,
                                avg_entry=avg_entry,
                                current_pnl=current_pnl,
                                pnl_pct=pnl_pct,
                                order_type=order_preference
                            )
            except Exception as e:
                log.warning(f"Failed to send options notification: {e}")
        
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
        
        result = _run_async(test_place_tp())
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
            "take_profit_quantity": 10,    // Number of contracts to exit (optional, defaults to full position)
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
        
        # Get take profit price and quantity if specified
        take_profit_price = data.get('take_profit_price')
        take_profit_quantity = data.get('take_profit_quantity')  # Optional: number of contracts to exit
        
        # Store SL/TP settings in database
        manager = get_sl_tp_manager()
        result = manager.set_sl_tp(
            symbol=symbol,
            stop_loss_price=data.get('stop_loss_price'),
            stop_loss_pct=data.get('stop_loss_pct'),
            take_profit_price=take_profit_price,
            take_profit_pct=data.get('take_profit_pct'),
            take_profit_quantity=take_profit_quantity,
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
                    
                    # Use specified quantity if provided, otherwise use full position
                    if take_profit_quantity and take_profit_quantity > 0:
                        order_size = min(take_profit_quantity, abs(position_size))
                        log.info(f"📊 Using specified quantity: {order_size} (position size: {abs(position_size)})")
                    else:
                        order_size = abs(position_size)
                        log.info(f"📊 Using full position size: {order_size}")
                    
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
                tp_order_result = _run_async(with_timeout(place_tp_order(), timeout_seconds=30))
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
                
                # Extract exchange error details if available
                exchange_detail = ''
                if hasattr(e, 'response'):
                    try:
                        err_body = e.response.json()
                        exchange_detail = err_body.get('error', {}).get('message', '') or str(err_body)
                    except Exception:
                        exchange_detail = getattr(e.response, 'text', '')[:200]
                
                error_msg = f'Failed to place TP order on exchange: {str(e)}'
                if exchange_detail:
                    error_msg += f' — Exchange: {exchange_detail}'
                
                return jsonify({
                    'success': False,
                    'error': error_msg,
                    'rollback': 'SL/TP settings were not saved (rollback performed)'
                }), 422
        
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
        cancel_result = _run_async(cancel_tp_orders())
        
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


@options_bp.route('/monitoring-activity', methods=['GET'])
def get_monitoring_activity():
    """
    Get real-time monitoring activity log.
    Shows background operations like max loss checks, warnings, and actions.
    
    Query params:
        limit (int): Max events to return (default 50)
        type (str): Filter by event type (optional)
    
    Returns:
        JSON: {
            success: bool,
            events: [...],     # Activity events with timestamp, type, message, details
            monitor_status: {...},  # Current monitor status
            timestamp: str
        }
    """
    try:
        from webui.backend.options_strategy.max_loss_manager import get_activity_log, get_max_loss_monitor
        
        limit = request.args.get('limit', 50, type=int)
        event_type = request.args.get('type', None)
        
        # Get activity events
        events = get_activity_log(limit=limit, event_type=event_type)
        
        # Get monitor status
        monitor = get_max_loss_monitor()
        monitor_status = None
        if monitor:
            monitor_status = monitor.get_status()
        
        # Get current max loss limits for context
        manager = get_max_loss_manager()
        strike_limits = manager.get_all_strike_max_loss()
        expiry_limits = manager.get_all_expiry_max_loss()
        
        hedge_events_snapshot = get_hedge_events_snapshot(20)

        return jsonify({
            'success': True,
            'events': events,
            'eventCount': len(events),
            'monitorStatus': monitor_status,
            'activeLimits': {
                'strike': len(strike_limits),
                'expiry': len(expiry_limits),
                'total': len(strike_limits) + len(expiry_limits)
            },
            'strikeLimits': strike_limits[:10],  # First 10 for display
            'expiryLimits': expiry_limits[:10],
            'hedgeEvents': hedge_events_snapshot,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        log.error(f"Error getting monitoring activity: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'events': [],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }), 500


@options_bp.route('/monitoring-activity/export', methods=['GET'])
def export_monitoring_activity_csv():
    """
    Export the last 24 h of monitoring activity as a CSV file.
    Independent from the in-memory buffer — reads from SQLite.
    """
    try:
        from webui.backend.db.activity_log_db import export_csv_string
        hours = request.args.get('hours', 24, type=float)
        csv_data = export_csv_string(hours=hours)
        filename = f"activity_log_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        log.error(f"Error exporting activity log: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# IV RANK / IV PERCENTILE ROUTES  (Feature 2 — fully independent)
# =============================================================================

@options_bp.route('/iv-stats', methods=['GET'])
def get_iv_stats():
    """
    Return IV Rank and IV Percentile per position symbol.
    Also triggers a background IV snapshot recording (rate-limited internally).

    Returns:
        { success, iv_stats: {symbol: {ivr, ivp, high_52w, low_52w, current_iv_pct}}, ... }
    """
    try:
        from webui.backend.db.iv_history_db import get_iv_stats_batch, record_iv_snapshot
        from .dashboard_service import fetch_options_positions_data
        from webui.backend.routes.market import _price_cache

        positions_data = fetch_options_positions_data()
        positions = positions_data.get('positions', [])
        symbols = [p.get('product_symbol', '') for p in positions if p.get('product_symbol')]

        spot_entry = _price_cache.get('spot_BTC')
        spot = float(spot_entry[1]) if spot_entry else 0.0
        record_iv_snapshot(positions, spot_price=spot)

        iv_stats = get_iv_stats_batch(symbols)

        return jsonify({
            'success': True,
            'iv_stats': iv_stats,
            'total_symbols': len(symbols),
            'symbols_with_history': len(iv_stats),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        })

    except Exception as e:
        log.error(f"Error fetching IV stats: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# PER-POSITION GREEKS ROUTE  (Feature 3 — fully independent)
# =============================================================================

@options_bp.route('/position-greeks', methods=['GET'])
def get_position_greeks():
    """
    Return per-position Black-Scholes Greeks and DTE for all current positions.
    Independent of the sealed dashboard / portfolio-greeks pipeline.

    Query params:
        spot (float): BTC spot price override. If omitted, fetched from cache.

    Returns:
        {
          success: bool,
          position_greeks: { "<symbol>": {dte, delta, gamma, theta, vega} },
          expiry_subtotals: { "<YYYY-MM-DD>": {delta, gamma, theta, vega, count} },
          spot_used: float,
          timestamp: str
        }
    """
    import concurrent.futures as _cf

    # Maximum seconds to wait for a fresh positions fetch before falling back
    # to stale cache.  This is shorter than the exchange-client inner timeout
    # (60 s) so we never block the HTTP worker for excessive time.
    _GREEKS_FETCH_TIMEOUT = 12

    try:
        from webui.backend.options_strategy.position_greeks import (
            enrich_positions_with_greeks,
            compute_expiry_subtotals,
        )
        from .dashboard_service import fetch_options_positions_data

        # Get spot price — caller may pass override; else use market data cache
        spot = request.args.get('spot', None, type=float)
        if spot is None:
            try:
                # Read from the market module's in-process price cache (avoids HTTP round-trip)
                from webui.backend.routes.market import _price_cache
                cache_entry = _price_cache.get('spot_BTC')
                spot = float(cache_entry[1]) if cache_entry else 0.0
            except Exception:
                spot = 0.0

        # Fetch positions with a bounded timeout.  If the exchange is slow or
        # unreachable the call can hang; cap it here and fall back to whatever
        # stale data was cached by get_options_positions().
        stale_warning = None
        with _cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix='pos-greeks') as _pool:
            _fut = _pool.submit(fetch_options_positions_data)
            try:
                positions_data = _fut.result(timeout=_GREEKS_FETCH_TIMEOUT)
            except _cf.TimeoutError:
                log.warning("position-greeks: positions fetch timed out, using stale cache")
                stale_warning = 'Exchange unavailable — using cached positions'
                # Fall back to whatever the positions cache holds
                positions_data = {
                    'success': bool(_positions_cache['data']),
                    'positions': _positions_cache['data'] or [],
                }

        positions = positions_data.get('positions', [])

        enriched = enrich_positions_with_greeks(positions, spot_price=spot)

        # Build compact lookup map for frontend: symbol -> pos_greeks
        greeks_map = {
            p.get('product_symbol', ''): p.get('pos_greeks', {})
            for p in enriched
        }
        subtotals = compute_expiry_subtotals(enriched)

        response = {
            'success': True,
            'position_greeks': greeks_map,
            'expiry_subtotals': subtotals,
            'spot_used': spot,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        if stale_warning:
            response['warning'] = stale_warning
        return jsonify(response)

    except Exception as e:
        log.error(f"Error computing position Greeks: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# TAKE PROFIT ROUTES (Per-Strike TP Management)
# =============================================================================

@options_bp.route('/take-profit/strike/all', methods=['GET'])
def get_all_take_profit_by_strike():
    """Get take profit settings for all strikes."""
    try:
        from webui.backend.options_strategy.take_profit_manager import get_take_profit_manager
        manager = get_take_profit_manager()
        settings = manager.get_all_strike_take_profit()
        return jsonify({
            'success': True,
            'settings': settings
        })
    except Exception as e:
        log.error(f"Error getting strike take profit settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/take-profit/strike/get', methods=['GET'])
def get_strike_take_profit():
    """Get take profit setting for a specific strike."""
    try:
        from webui.backend.options_strategy.take_profit_manager import get_take_profit_manager
        symbol = request.args.get('symbol')
        
        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        
        manager = get_take_profit_manager()
        setting = manager.get_strike_take_profit(symbol)
        
        return jsonify({
            'success': True,
            'setting': setting
        })
    except Exception as e:
        log.error(f"Error getting strike take profit: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/take-profit/strike/set', methods=['POST'])
def set_strike_take_profit():
    """Set take profit for a specific strike."""
    try:
        from webui.backend.options_strategy.take_profit_manager import get_take_profit_manager
        data = request.get_json()
        symbol = data.get('symbol')
        target_profit = data.get('target_profit')
        exit_quantity = data.get('exit_quantity')
        
        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        if not target_profit or target_profit == 0:
            return jsonify({'success': False, 'error': 'Valid target_profit required (non-zero number, positive for profit, negative for loss)'}), 400
        if not exit_quantity or exit_quantity <= 0:
            return jsonify({'success': False, 'error': 'Valid exit_quantity required (positive integer)'}), 400
        
        manager = get_take_profit_manager()
        result = manager.set_strike_take_profit(symbol, float(target_profit), int(exit_quantity))
        
        if result.get('success'):
            log.info(f"✅ Take profit set for {symbol}: ${target_profit} -> exit {exit_quantity} lots")
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        log.error(f"Error setting strike take profit: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/take-profit/strike/remove', methods=['POST'])
def remove_strike_take_profit():
    """Remove take profit setting for a specific strike."""
    try:
        from webui.backend.options_strategy.take_profit_manager import get_take_profit_manager
        data = request.get_json()
        symbol = data.get('symbol')
        
        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        
        manager = get_take_profit_manager()
        result = manager.remove_strike_take_profit(symbol)
        
        if result.get('success'):
            log.info(f"✅ Take profit removed for {symbol}")
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        log.error(f"Error removing strike take profit: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/take-profit/history', methods=['GET'])
def get_take_profit_history():
    """Get take profit trigger history."""
    try:
        from webui.backend.options_strategy.take_profit_manager import get_take_profit_manager
        limit = request.args.get('limit', 50, type=int)
        
        manager = get_take_profit_manager()
        history = manager.get_history(limit=limit)
        
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history)
        })
    except Exception as e:
        log.error(f"Error getting take profit history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/take-profit/monitor/status', methods=['GET'])
def get_take_profit_monitor_status():
    """Get Take Profit Monitor status"""
    try:
        from webui.backend.options_strategy.take_profit_manager import get_take_profit_monitor
        monitor = get_take_profit_monitor()
        
        if monitor is None:
            return jsonify({
                'success': False,
                'running': False,
                'error': 'Monitor not initialized'
            })
        
        is_running = monitor.is_running() if hasattr(monitor, 'is_running') else False
        metrics = monitor.get_metrics() if hasattr(monitor, 'get_metrics') else {}
        
        return jsonify({
            'success': True,
            'running': is_running,
            'metrics': metrics
        })
    except Exception as e:
        log.error(f"Error getting monitor status: {e}")
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
        result = _run_async(fetch_and_close())
        log.info(f"✅ SL/TP close executed successfully: {result}")
        return result
        
    except Exception as e:
        log.error(f"❌ Error executing SL/TP close order for {symbol}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'symbol': symbol
        }


# ================================================================
# BATCH ORDER ENDPOINT - JAN 28, 2026
# Execute multiple orders concurrently to minimize time and market risk
# ================================================================

from .batch_add_endpoint import create_batch_add_route, create_batch_order_status_route

# Register batch_add route with all required dependencies
create_batch_add_route(
    options_bp=options_bp,
    get_unified_client=get_unified_client,
    check_guardian_signal=check_guardian_signal,
    ORDER_TYPE_MAKER_FIRST=ORDER_TYPE_MAKER_FIRST,
    VALID_ORDER_TYPES=VALID_ORDER_TYPES
)

# Register batch_order_status route for auto-loop functionality
create_batch_order_status_route(
    options_bp=options_bp,
    get_api_client=get_unified_client
)


# ================================================================
# LIMIT ORDER ENDPOINT - FEB 2, 2026
# Place individual limit orders (used by SSR Algo for exit orders at $3)
# ================================================================

@options_bp.route('/limit_order', methods=['POST'])
def place_limit_order():
    """
    Place a single limit order.
    
    Request body:
        {
            symbol: str,        # Option symbol (e.g., "C-BTC-76000-060226")
            size: int,          # Order size (always positive)
            side: str,          # 'buy' or 'sell'
            price: float,       # Limit price
        }
    
    Returns:
        {success: bool, order_id: str, message: str}
    """
    try:
        data = request.get_json()
        
        symbol = data.get('symbol')
        size = abs(int(data.get('size', 1)))
        side = data.get('side', 'buy').lower()
        price = float(data.get('price', 0))
        
        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol is required'}), 400
        
        if price <= 0:
            return jsonify({'success': False, 'error': 'Price must be positive'}), 400
        
        if side not in ['buy', 'sell']:
            return jsonify({'success': False, 'error': 'Side must be buy or sell'}), 400
        
        # Get API client
        api_client = get_unified_client()
        if not api_client:
            return jsonify({'success': False, 'error': 'API client not available'}), 503
        
        # Get product ID for symbol
        try:
            product = api_client.get_product_by_symbol(symbol)
            if not product:
                return jsonify({'success': False, 'error': f'Product not found: {symbol}'}), 404
            product_id = product.get('id')
        except Exception as e:
            log.error(f"Failed to get product for {symbol}: {e}")
            return jsonify({'success': False, 'error': f'Failed to resolve symbol: {e}'}), 400
        
        # Place limit order
        try:
            result = api_client.place_order(
                product_id=product_id,
                side=side,
                size=size,
                limit_price=price,
                order_type='limit_order',
                time_in_force='gtc'
            )
            
            if result.get('success') or result.get('id'):
                order_id = result.get('id') or result.get('order_id')
                log.info(f"Placed limit order: {symbol} {side} {size} @ {price} -> {order_id}")
                return jsonify({
                    'success': True,
                    'order_id': str(order_id),
                    'symbol': symbol,
                    'side': side,
                    'size': size,
                    'price': price,
                    'message': f'Limit order placed: {order_id}'
                })
            else:
                error = result.get('error') or result.get('message') or 'Unknown error'
                log.error(f"Limit order failed: {error}")
                return jsonify({'success': False, 'error': error}), 400
                
        except Exception as e:
            log.exception(f"Limit order placement failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        
    except Exception as e:
        log.exception("Limit order endpoint error")
        return jsonify({'success': False, 'error': str(e)}), 500

# ================================================================
# CONDITIONAL EXIT ENDPOINTS - FEB 25, 2026
# BTC price-triggered partial position exits
# ================================================================

from webui.backend.services.conditional_exit_monitor import get_conditional_exit_monitor


def _get_btc_price_for_monitor() -> float:
    """Fetch BTC spot price for the conditional exit monitor.
    
    Priority: WebSocket → REST API fallback
    """
    import requests as req_lib
    
    # Try WebSocket first
    try:
        from webui.backend.services.delta_price_websocket import get_price_websocket
        ws = get_price_websocket()
        if ws and ws.is_connected():
            price = ws.get_price('BTC')
            if price and price > 0:
                return float(price)
    except Exception:
        pass
    
    # Fallback to REST
    try:
        resp = req_lib.get('http://127.0.0.1:5000/api/market/spot-price?symbol=BTC', timeout=5)
        data = resp.json()
        if data.get('price'):
            return float(data['price'])
    except Exception:
        pass
    
    return 0.0


@options_bp.route('/conditional-exit/status', methods=['GET'])
def conditional_exit_status():
    """Get conditional exit monitor status and all rules."""
    try:
        monitor = get_conditional_exit_monitor()
        return jsonify({
            "success": True,
            "monitor": monitor.get_status(),
            "rules": monitor.get_all_rules(),
        })
    except Exception as e:
        log.error(f"conditional-exit status error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/conditional-exit/start', methods=['POST'])
def conditional_exit_start():
    """Start the conditional exit monitor."""
    try:
        monitor = get_conditional_exit_monitor()
        
        # Set dependencies if not already set
        if not monitor._api_client:
            api_client = get_unified_client()
            monitor.set_dependencies(api_client, _get_btc_price_for_monitor)
        
        started = monitor.start()
        return jsonify({
            "success": True,
            "message": "Monitor started" if started else "Monitor already running",
            "monitor": monitor.get_status(),
        })
    except Exception as e:
        log.error(f"conditional-exit start error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/conditional-exit/stop', methods=['POST'])
def conditional_exit_stop():
    """Stop the conditional exit monitor."""
    try:
        monitor = get_conditional_exit_monitor()
        monitor.stop()
        return jsonify({"success": True, "message": "Monitor stopped"})
    except Exception as e:
        log.error(f"conditional-exit stop error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/conditional-exit/rule', methods=['POST'])
def conditional_exit_add_rule():
    """
    Add a conditional exit rule.
    
    Request body:
    {
        trigger_type: "lower" | "upper",
        trigger_price: float,
        exit_pct: int (1-100),
        exit_mode: "fixed" | "proportional",   // optional, default "fixed"
        symbols: [str],                         // optional, empty = all positions
        name: str,                              // optional
        order_preference: str                   // optional, default "maker_first"
    }
    """
    try:
        data = request.get_json()
        monitor = get_conditional_exit_monitor()
        
        # Auto-start monitor if not running
        if not monitor.running:
            if not monitor._api_client:
                api_client = get_unified_client()
                monitor.set_dependencies(api_client, _get_btc_price_for_monitor)
            monitor.start()
        
        rule = monitor.add_rule(
            trigger_type=data.get('trigger_type', 'lower'),
            trigger_price=float(data.get('trigger_price', 0)),
            exit_pct=int(data.get('exit_pct', 50)),
            exit_mode=data.get('exit_mode', 'fixed'),
            symbols=data.get('symbols', []),
            name=data.get('name', ''),
            order_preference=data.get('order_preference', 'maker_first'),
        )
        
        return jsonify({"success": True, "rule": rule})
    except (ValueError, TypeError) as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        log.error(f"conditional-exit add rule error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/conditional-exit/rule/<rule_id>', methods=['DELETE'])
def conditional_exit_remove_rule(rule_id):
    """Remove/cancel a conditional exit rule."""
    try:
        monitor = get_conditional_exit_monitor()
        removed = monitor.remove_rule(rule_id)
        if removed:
            return jsonify({"success": True, "message": f"Rule {rule_id} removed"})
        return jsonify({"success": False, "error": "Rule not found"}), 404
    except Exception as e:
        log.error(f"conditional-exit remove rule error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/conditional-exit/rule/<rule_id>/cancel', methods=['POST'])
def conditional_exit_cancel_rule(rule_id):
    """Cancel an executing rule (stops gracefully)."""
    try:
        monitor = get_conditional_exit_monitor()
        cancelled = monitor.cancel_rule(rule_id)
        if cancelled:
            return jsonify({"success": True, "message": f"Rule {rule_id} cancelled"})
        return jsonify({"success": False, "error": "Rule not found"}), 404
    except Exception as e:
        log.error(f"conditional-exit cancel error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/conditional-exit/clear', methods=['POST'])
def conditional_exit_clear():
    """Clear all completed/cancelled rules."""
    try:
        monitor = get_conditional_exit_monitor()
        count = monitor.clear_completed()
        return jsonify({"success": True, "cleared": count})
    except Exception as e:
        log.error(f"conditional-exit clear error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════
# AUTO-LOOP (SERVER-SIDE) ROUTES
# Runs auto-loop in a backend thread so it survives page refreshes.
# ═══════════════════════════════════════════════════════════════════════


def _ensure_auto_loop_deps():
    """Lazy-init dependencies for the auto-loop service."""
    from webui.backend.services.auto_loop_service import get_auto_loop_service
    svc = get_auto_loop_service()
    if svc._api_client_factory is None:
        svc.set_dependencies(
            api_client_factory=get_unified_client,
            check_guardian_fn=check_guardian_signal,
        )
    return svc


@options_bp.route('/auto-loop/start', methods=['POST'])
def auto_loop_start():
    """
    Start a server-side auto-loop.

    Body: {
        loop_id: str (default 'main'),
        orders: [{symbol, size, side}, ...],
        total_rounds: int,
        order_preference: str ('maker_first' | 'market_only')
    }
    """
    try:
        data = request.get_json()
        loop_id = data.get('loop_id', 'main')
        orders = data.get('orders', [])
        total_rounds = int(data.get('total_rounds', 1))
        order_preference = data.get('order_preference', ORDER_TYPE_MAKER_FIRST)

        if not orders:
            return jsonify({"success": False, "error": "No orders provided"}), 400
        if total_rounds < 1:
            return jsonify({"success": False, "error": "total_rounds must be >= 1"}), 400

        # Validate order fields
        for i, o in enumerate(orders):
            if not all([o.get('symbol'), o.get('size'), o.get('side')]):
                return jsonify({"success": False, "error": f"Order {i+1} missing required fields"}), 400

        # Guardian check
        signal = check_guardian_signal()
        if signal != 'GO':
            return jsonify({"success": False, "error": f"Guardian signal is {signal}. Trading disabled."}), 403

        svc = _ensure_auto_loop_deps()
        state = svc.start_loop(loop_id, orders, total_rounds, order_preference)
        return jsonify({"success": True, "loop": state})

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 409
    except Exception as e:
        log.error(f"auto-loop start error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/auto-loop/stop', methods=['POST'])
def auto_loop_stop():
    """Stop a running server-side auto-loop."""
    try:
        data = request.get_json() or {}
        loop_id = data.get('loop_id', 'main')
        svc = _ensure_auto_loop_deps()
        stopped = svc.stop_loop(loop_id)
        return jsonify({"success": True, "stopped": stopped})
    except Exception as e:
        log.error(f"auto-loop stop error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/auto-loop/status', methods=['GET'])
def auto_loop_status():
    """
    Get auto-loop status. Optional ?loop_id=main (default returns all loops).
    """
    try:
        loop_id = request.args.get('loop_id')
        svc = _ensure_auto_loop_deps()
        status = svc.get_status(loop_id)
        return jsonify({"success": True, "loops": status if not loop_id else {loop_id: status}})
    except Exception as e:
        log.error(f"auto-loop status error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_bp.route('/auto-loop/clear', methods=['POST'])
def auto_loop_clear():
    """Clear finished loops. Pass {"force": true} to also stop and remove running loops."""
    try:
        data = request.get_json() or {}
        force = bool(data.get('force', False))
        loop_id = data.get('loop_id')  # optional: target a specific loop
        svc = _ensure_auto_loop_deps()
        if force:
            count = svc.force_clear(loop_id)
        else:
            count = svc.clear_finished()
        return jsonify({"success": True, "cleared": count})
    except Exception as e:
        log.error(f"auto-loop clear error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# Register delta-hedge routes on the blueprint
register_delta_hedge_routes(options_bp)


# ================================================================
# CIRCUIT BREAKER RESET ENDPOINT
# Allows manual recovery when the API circuit breaker gets stuck open
# after a burst of failures on backend startup.
# ================================================================

@options_bp.route('/circuit-breaker/reset', methods=['POST'])
def reset_circuit_breaker():
    """Reset BOTH circuit breakers (outer UnifiedAPIClient + inner AsyncDeltaClient)."""
    try:
        client = get_unified_client()

        # Outer circuit breaker (UnifiedAPIClient)
        cb = client.circuit_breaker
        outer_state = cb.state
        outer_failures = cb.failures
        cb.failures = 0
        cb.state = 'closed'
        cb.last_failure_time = 0

        # Inner circuit breaker (AsyncDeltaClient)
        inner_cb = client.rest_client._circuit_breaker
        inner_open = inner_cb.is_open
        inner_failures = inner_cb.failures
        inner_cb.failures = 0
        inner_cb.is_open = False
        inner_cb.last_failure = 0

        log.info(f"Circuit breakers manually reset: outer={outer_state}/{outer_failures}, inner={'open' if inner_open else 'closed'}/{inner_failures}")
        return jsonify({
            'success': True,
            'message': 'Both circuit breakers reset to closed',
            'outer': {'previous_state': outer_state, 'previous_failures': outer_failures},
            'inner': {'was_open': inner_open, 'previous_failures': inner_failures},
        })
    except Exception as e:
        log.error(f"Failed to reset circuit breaker: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@options_bp.route('/circuit-breaker/status', methods=['GET'])
def get_circuit_breaker_status():
    """Return current state of BOTH circuit breakers."""
    try:
        client = get_unified_client()
        cb = client.circuit_breaker
        inner_cb = client.rest_client._circuit_breaker
        return jsonify({
            'success': True,
            'outer': {
                'state': cb.state,
                'failures': cb.failures,
                'failure_threshold': cb.failure_threshold,
                'timeout_seconds': cb.timeout,
                'seconds_since_last_failure': round(time.time() - cb.last_failure_time, 1) if cb.last_failure_time else None,
            },
            'inner': {
                'is_open': inner_cb.is_open,
                'failures': inner_cb.failures,
                'failure_threshold': inner_cb.failure_threshold,
                'reset_after_seconds': inner_cb.reset_after,
                'seconds_since_last_failure': round(time.time() - inner_cb.last_failure, 1) if inner_cb.last_failure else None,
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500