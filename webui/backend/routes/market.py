"""
Market Data Routes Blueprint

This module handles market data API routes for options and trading.

Routes:
- GET /api/market/spot-price - Get current spot price for an underlying
- GET /api/market/session-anchor - Get 5:30 PM IST anchor price for a session
- GET /api/market/ws-status - Get WebSocket connection status

Created: January 12, 2026
Updated: January 18, 2026 - Added WebSocket support for real-time prices
Purpose: Provide market data endpoints for options strategy builder
"""

import sys
import logging
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from flask import Blueprint, jsonify, request

# Import cache
try:
    from webui.backend.cache import cache, CACHE_TIMEOUTS, make_cache_key
except ImportError:
    from cache import cache, CACHE_TIMEOUTS, make_cache_key

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config, get_api_credentials

# SEALED: get_spot_price — do not remove
try:
    from webui.backend.sealed import sealed
except ImportError:
    from sealed import sealed

log = logging.getLogger(__name__)

# Create blueprint
market_bp = Blueprint('market', __name__)

# Import WebSocket service
try:
    from webui.backend.services import get_price_websocket
except ImportError:
    try:
        from services import get_price_websocket
    except ImportError:
        log.warning("Could not import WebSocket service")
        get_price_websocket = None

# Cache for spot prices (10 second TTL)
_price_cache = {}
_cache_ttl = 10.0

IST_TZ = ZoneInfo('Asia/Kolkata')
SESSION_ANCHOR_HOUR = 17
SESSION_ANCHOR_MINUTE = 30
PERP_SYMBOLS = {
    'BTC': 'BTCUSD',
    'ETH': 'ETHUSD',
}


def _current_session_key_ist() -> str:
    """Return current session key (YYYY-MM-DD) for IST 5:30 PM rollover."""
    now_ist = datetime.now(IST_TZ)
    session_date = now_ist.date()

    if (now_ist.hour, now_ist.minute) < (SESSION_ANCHOR_HOUR, SESSION_ANCHOR_MINUTE):
        session_date = session_date - timedelta(days=1)

    return session_date.strftime('%Y-%m-%d')


def _session_anchor_timestamp(session_key: str) -> int:
    """Convert session key (YYYY-MM-DD) to UTC timestamp of 5:30 PM IST."""
    session_date = datetime.strptime(session_key, '%Y-%m-%d').date()
    anchor_ist = datetime(
        session_date.year,
        session_date.month,
        session_date.day,
        SESSION_ANCHOR_HOUR,
        SESSION_ANCHOR_MINUTE,
        0,
        tzinfo=IST_TZ,
    )
    return int(anchor_ist.astimezone(timezone.utc).timestamp())


def _extract_candles(payload: dict) -> list:
    """Handle Delta candles response variants: result(list) or result.candles(list)."""
    result = payload.get('result')
    if isinstance(result, list):
        return result

    if isinstance(result, dict):
        candles = result.get('candles', [])
        if isinstance(candles, list):
            return candles

    return []


def _select_anchor_candle(candles: list, anchor_ts: int):
    """
    Select the best candle for anchor time.

    Priority:
    1) Exact timestamp match
    2) Earliest candle strictly after anchor timestamp
    3) Nearest candle by absolute distance
    """
    normalized = []
    for candle in candles:
        try:
            ts = int(candle.get('time'))
            close_px = float(candle.get('close'))
            if close_px <= 0:
                continue
            normalized.append((ts, close_px, candle))
        except (TypeError, ValueError):
            continue

    if not normalized:
        return None

    for ts, px, candle in normalized:
        if ts == anchor_ts:
            return ts, px, candle

    future = [item for item in normalized if item[0] > anchor_ts]
    if future:
        return min(future, key=lambda item: item[0])

    return min(normalized, key=lambda item: abs(item[0] - anchor_ts))


@market_bp.route('/api/market/spot-price', methods=['GET'])
@cache.cached(timeout=CACHE_TIMEOUTS['market'], key_prefix=make_cache_key)
@sealed
def get_spot_price():
    """
    Get current spot price for an underlying asset.
    
    Priority order:
    1. WebSocket live price (if connected)
    2. Cache (10 second TTL)
    3. Delta Exchange REST API
    4. Guardian signal file
    5. Fallback static price
    
    Query Parameters:
        symbol: BTC or ETH (default: BTC)
    
    Returns:
        JSON response with current spot price
    
    Example:
        GET /api/market/spot-price?symbol=BTC
        Response: {"symbol": "BTC", "price": 94521.50, "source": "websocket"}
    """
    import time
    
    symbol = request.args.get('symbol', 'BTC').upper()
    
    if symbol not in ['BTC', 'ETH']:
        return jsonify({
            'error': 'Invalid symbol. Must be BTC or ETH'
        }), 400
    
    # 1. Try WebSocket first (real-time, lowest latency)
    if get_price_websocket:
        try:
            price_ws = get_price_websocket()
            if price_ws.is_connected():
                ws_price = price_ws.get_price(symbol)
                if ws_price and ws_price > 0:
                    # Update cache with WebSocket price
                    cache_key = f"spot_{symbol}"
                    _price_cache[cache_key] = (time.time(), ws_price)
                    
                    # Update price alert monitor
                    if symbol == 'BTC':
                        try:
                            # Ensure backend is in path to match alert_routes import context
                            backend_dir = str(Path(__file__).parent.parent)
                            if backend_dir not in sys.path:
                                sys.path.insert(0, backend_dir)
                            from services.price_alert_monitor import get_price_alert_monitor
                            get_price_alert_monitor().update_price(ws_price)
                        except Exception as e:
                            log.debug(f"Failed to update monitor from WS: {e}")
                            
                    return jsonify({
                        'symbol': symbol,
                        'price': ws_price,
                        'source': 'websocket'
                    })
        except Exception as e:
            log.warning(f"WebSocket price fetch failed: {e}")
    
    # 2. Check cache
    cache_key = f"spot_{symbol}"
    if cache_key in _price_cache:
        cached_time, cached_price = _price_cache[cache_key]
        if time.time() - cached_time < _cache_ttl:
            return jsonify({
                'symbol': symbol,
                'price': cached_price,
                'source': 'cache'
            })
    
    try:
        # Try to fetch directly from Delta Exchange REST API
        futures_symbol = f"{symbol}USD"
        api_url = f"https://api.delta.exchange/v2/tickers/{futures_symbol}"
        
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('result'):
                ticker = data['result']
                # Try different price fields
                price = (
                    ticker.get('mark_price') or 
                    ticker.get('spot_price') or 
                    ticker.get('close') or
                    ticker.get('last_price')
                )
                
                if price:
                    price = float(price)
                    price = float(price)
                    _price_cache[cache_key] = (time.time(), price)
                    
                    # Update price alert monitor
                    if symbol == 'BTC':
                        try:
                            # Ensure backend is in path to match alert_routes import context
                            backend_dir = str(Path(__file__).parent.parent)
                            if backend_dir not in sys.path:
                                sys.path.insert(0, backend_dir)
                            from services.price_alert_monitor import get_price_alert_monitor
                            get_price_alert_monitor().update_price(price)
                        except Exception as e:
                            log.debug(f"Failed to update monitor from API: {e}")
                            
                    return jsonify({
                        'symbol': symbol,
                        'price': price,
                        'source': 'delta_api'
                    })
        
        # Fallback: Try to read from guardian signal file
        signal_file = Path(__file__).parent.parent.parent.parent / 'data' / 'guardian_signal.json'
        if signal_file.exists():
            import json
            with open(signal_file, 'r') as f:
                data = json.load(f)
                
                # For BTC, use spot_price directly
                if symbol == 'BTC' and 'spot_price' in data:
                    price = float(data['spot_price'])
                    price = float(data['spot_price'])
                    _price_cache[cache_key] = (time.time(), price)
                    
                    # Update price alert monitor
                    try:
                        # Ensure backend is in path to match alert_routes import context
                        backend_dir = str(Path(__file__).parent.parent)
                        if backend_dir not in sys.path:
                            sys.path.insert(0, backend_dir)
                        from services.price_alert_monitor import get_price_alert_monitor
                        get_price_alert_monitor().update_price(price)
                    except Exception as e:
                        log.debug(f"Failed to update monitor from Guardian: {e}")
                        
                    return jsonify({
                        'symbol': symbol,
                        'price': price,
                        'source': 'guardian'
                    })
                
                # For ETH, calculate from BTC price (approximately 3.7% ratio)
                if symbol == 'ETH' and 'spot_price' in data:
                    btc_price = float(data['spot_price'])
                    eth_price = btc_price * 0.037
                    _price_cache[cache_key] = (time.time(), eth_price)
                    return jsonify({
                        'symbol': symbol,
                        'price': eth_price,
                        'source': 'guardian_calculated'
                    })
        
        # Final fallback - use reasonable defaults
        fallback_prices = {'BTC': 95000, 'ETH': 3500}
        log.warning(f"Using fallback price for {symbol}: {fallback_prices[symbol]}")
        return jsonify({
            'symbol': symbol,
            'price': fallback_prices.get(symbol, 95000),
            'source': 'fallback'
        })
        
    except Exception as e:
        log.error(f"Error fetching spot price for {symbol}: {e}", exc_info=True)
        
        # Return fallback price on error
        fallback_prices = {'BTC': 95000, 'ETH': 3500}
        return jsonify({
            'symbol': symbol,
            'price': fallback_prices.get(symbol, 95000),
            'source': 'fallback_error',
            'error': str(e)
        })


@market_bp.route('/api/market/session-anchor', methods=['GET'])
@cache.cached(timeout=CACHE_TIMEOUTS['market'], key_prefix=make_cache_key)
def get_session_anchor_price():
    """
    Get session anchor price at 5:30 PM IST for BTC/ETH.

    Query params:
      - symbol: BTC or ETH (default BTC)
      - session: YYYY-MM-DD session-start date in IST (optional)

    If session is omitted, current session key is used.
    """
    symbol = request.args.get('symbol', 'BTC').upper()
    if symbol not in PERP_SYMBOLS:
        return jsonify({
            'error': 'Invalid symbol. Must be BTC or ETH'
        }), 400

    session_key = request.args.get('session', '').strip()
    if not session_key:
        session_key = _current_session_key_ist()

    try:
        datetime.strptime(session_key, '%Y-%m-%d')
    except ValueError:
        return jsonify({
            'error': 'Invalid session format. Use YYYY-MM-DD'
        }), 400

    anchor_ts = _session_anchor_timestamp(session_key)
    perp_symbol = PERP_SYMBOLS[symbol]
    candle_url = 'https://api.india.delta.exchange/v2/history/candles'

    candles = []
    source = 'delta_candles'

    try:
        # Prefer candles at/after anchor in a narrow forward window.
        primary_params = {
            'symbol': perp_symbol,
            'resolution': '1m',
            'start': anchor_ts,
            'end': anchor_ts + 300,
        }
        primary_resp = requests.get(candle_url, params=primary_params, timeout=6)
        if primary_resp.status_code == 200:
            primary_data = primary_resp.json()
            if primary_data.get('success'):
                candles = _extract_candles(primary_data)

        # Fallback: wider symmetric window if no forward candles were found.
        if not candles:
            secondary_params = {
                'symbol': perp_symbol,
                'resolution': '1m',
                'start': anchor_ts - 300,
                'end': anchor_ts + 300,
            }
            secondary_resp = requests.get(candle_url, params=secondary_params, timeout=6)
            if secondary_resp.status_code == 200:
                secondary_data = secondary_resp.json()
                if secondary_data.get('success'):
                    candles = _extract_candles(secondary_data)

        selected = _select_anchor_candle(candles, anchor_ts)
        if selected:
            selected_ts, selected_price, _ = selected
            if selected_ts == anchor_ts:
                source = 'delta_candles_exact'
            elif selected_ts > anchor_ts:
                source = 'delta_candles_after'
            else:
                source = 'delta_candles_nearest'

            anchor_dt_utc = datetime.fromtimestamp(anchor_ts, tz=timezone.utc)
            anchor_dt_ist = anchor_dt_utc.astimezone(IST_TZ)

            return jsonify({
                'symbol': symbol,
                'session': session_key,
                'anchor_ts': anchor_ts,
                'anchor_time_utc': anchor_dt_utc.isoformat().replace('+00:00', 'Z'),
                'anchor_time_ist': anchor_dt_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
                'price': selected_price,
                'source': source,
            })

        # Last resort: use latest ticker price if candles are unavailable.
        ticker_url = f'https://api.india.delta.exchange/v2/tickers/{perp_symbol}'
        ticker_resp = requests.get(ticker_url, timeout=5)
        if ticker_resp.status_code == 200:
            ticker_data = ticker_resp.json()
            ticker = ticker_data.get('result') if ticker_data.get('success') else None
            if ticker:
                fallback_price = (
                    ticker.get('mark_price')
                    or ticker.get('spot_price')
                    or ticker.get('close')
                    or ticker.get('last_price')
                )
                if fallback_price:
                    fallback_price = float(fallback_price)
                    anchor_dt_utc = datetime.fromtimestamp(anchor_ts, tz=timezone.utc)
                    anchor_dt_ist = anchor_dt_utc.astimezone(IST_TZ)
                    return jsonify({
                        'symbol': symbol,
                        'session': session_key,
                        'anchor_ts': anchor_ts,
                        'anchor_time_utc': anchor_dt_utc.isoformat().replace('+00:00', 'Z'),
                        'anchor_time_ist': anchor_dt_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
                        'price': fallback_price,
                        'source': 'delta_ticker_fallback',
                    })

    except Exception as e:
        log.error(
            f"Error fetching session anchor for {symbol} session={session_key}: {e}",
            exc_info=True,
        )

    # Final static fallback (rare)
    fallback_prices = {'BTC': 95000, 'ETH': 3500}
    anchor_dt_utc = datetime.fromtimestamp(anchor_ts, tz=timezone.utc)
    anchor_dt_ist = anchor_dt_utc.astimezone(IST_TZ)
    return jsonify({
        'symbol': symbol,
        'session': session_key,
        'anchor_ts': anchor_ts,
        'anchor_time_utc': anchor_dt_utc.isoformat().replace('+00:00', 'Z'),
        'anchor_time_ist': anchor_dt_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
        'price': fallback_prices[symbol],
        'source': 'fallback_static',
    })
        

@market_bp.route('/api/market/ws-status', methods=['GET'])
def get_ws_status():
    """
    Get WebSocket connection status and current prices
    
    Returns:
        JSON response with WebSocket status and latest prices
    
    Example:
        GET /api/market/ws-status
        Response: {
            "connected": true,
            "running": true,
            "prices": {"BTC": 95174.50, "ETH": 3312.44},
            "last_update": {"BTC": 1705612800.123, "ETH": 1705612800.456}
        }
    """
    if not get_price_websocket:
        return jsonify({
            'error': 'WebSocket service not available',
            'connected': False,
            'running': False
        }), 503
    
    try:
        price_ws = get_price_websocket()
        status = price_ws.get_status()
        return jsonify(status)
    except Exception as e:
        log.error(f"Error getting WebSocket status: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'connected': False,
            'running': False
        }), 500

