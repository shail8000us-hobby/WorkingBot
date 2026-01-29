"""
Ticker API Routes Blueprint

This module proxies Delta Exchange ticker API requests for options Greeks data.
The frontend calls this endpoint to fetch real-time Greeks for option positions.

Routes:
- GET /api/ticker/<symbol> - Get ticker data including Greeks for an option symbol

Created: January 24, 2026
Purpose: Provide Greeks data from Delta Exchange API for options positions
"""

import sys
import logging
import requests
from pathlib import Path
from flask import Blueprint, jsonify, request
from functools import lru_cache
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

log = logging.getLogger(__name__)

# Create blueprint
ticker_bp = Blueprint('ticker', __name__)

# Cache for ticker data (5 second TTL to match frontend cache)
_ticker_cache = {}
_cache_ttl = 5.0

# Price alert monitor hook
_price_alert_monitor = None

def set_price_alert_monitor(monitor):
    """Set the price alert monitor to receive price updates."""
    global _price_alert_monitor
    _price_alert_monitor = monitor

def _update_price_monitor(price: float):
    """Update price alert monitor with latest price."""
    if _price_alert_monitor and price:
        try:
            _price_alert_monitor.update_price(price)
        except Exception as e:
            log.debug(f"Failed to update price monitor: {e}")


@ticker_bp.route('/api/ticker/<symbol>', methods=['GET'])
def get_ticker(symbol):
    """
    Get ticker data from Delta Exchange API for an option symbol.
    
    This endpoint fetches real-time ticker data including Greeks for options.
    It acts as a proxy to Delta Exchange's ticker API to avoid CORS issues
    and to centralize API call management.
    
    Args:
        symbol: Option symbol (e.g., "C-BTC-95000-310125" for Call, "P-BTC-90000-270226" for Put)
    
    Returns:
        JSON response with ticker data including Greeks
    
    Example:
        GET /api/ticker/C-BTC-95000-310125
        Response: {
            "symbol": "C-BTC-95000-310125",
            "mark_price": 1250.5,
            "spot_price": 94500.0,
            "greeks": {
                "delta": 0.65,
                "gamma": 0.00012,
                "theta": -45.2,
                "vega": 120.5,
                "rho": 15.3
            }
        }
    """
    
    # Check cache first
    cache_key = f"ticker_{symbol}"
    if cache_key in _ticker_cache:
        cached_time, cached_data = _ticker_cache[cache_key]
        if time.time() - cached_time < _cache_ttl:
            return jsonify(cached_data)
    
    try:
        # Fetch from Delta Exchange API
        api_url = f"https://api.india.delta.exchange/v2/tickers/{symbol}"
        
        log.info(f"Fetching ticker for {symbol} from Delta Exchange")
        
        response = requests.get(api_url, timeout=5)
        
        if response.status_code == 404:
            log.warning(f"Ticker not found for symbol: {symbol}")
            return jsonify({
                'error': 'Ticker not found',
                'symbol': symbol,
                'message': f'No ticker data available for {symbol}. Symbol may be expired or invalid.'
            }), 404
        
        if response.status_code != 200:
            log.error(f"Delta Exchange API error: {response.status_code}")
            return jsonify({
                'error': 'API error',
                'status_code': response.status_code,
                'message': 'Failed to fetch ticker data from Delta Exchange'
            }), response.status_code
        
        data = response.json()
        
        if not data.get('success'):
            log.error(f"Delta Exchange API returned error: {data}")
            return jsonify({
                'error': 'API returned error',
                'message': data.get('error', 'Unknown error')
            }), 500
        
        result = data.get('result')
        
        if result is None:
            log.error(f"No result data returned for {symbol}")
            return jsonify({
                'error': 'No data',
                'message': f'No ticker data available for {symbol}'
            }), 404
        
        # Extract ticker data
        ticker_data = {
            'symbol': result.get('symbol', symbol),
            'mark_price': result.get('mark_price'),
            'spot_price': result.get('spot_price'),
            'close': result.get('close'),
            'high': result.get('high'),
            'low': result.get('low'),
            'volume': result.get('volume'),
            'turnover': result.get('turnover'),
            'open_interest': result.get('open_interest'),
            'timestamp': result.get('timestamp', int(time.time() * 1000)),
        }
        
        # Extract Greeks if available (for options)
        if result.get('greeks'):
            ticker_data['greeks'] = {
                'delta': result['greeks'].get('delta'),
                'gamma': result['greeks'].get('gamma'),
                'theta': result['greeks'].get('theta'),
                'vega': result['greeks'].get('vega'),
                'rho': result['greeks'].get('rho'),
            }
        
        # Cache the result
        _ticker_cache[cache_key] = (time.time(), ticker_data)
        
        # Update price alert monitor with spot price (for BTC symbols)
        if ticker_data.get('spot_price') and 'BTC' in symbol.upper():
            _update_price_monitor(float(ticker_data['spot_price']))
        
        return jsonify(ticker_data)
        
    except requests.exceptions.Timeout:
        log.error(f"Timeout fetching ticker for {symbol}")
        return jsonify({
            'error': 'Timeout',
            'message': 'Delta Exchange API request timed out'
        }), 504
        
    except requests.exceptions.RequestException as e:
        log.error(f"Request error fetching ticker for {symbol}: {e}")
        return jsonify({
            'error': 'Request failed',
            'message': str(e)
        }), 500
        
    except Exception as e:
        log.error(f"Unexpected error fetching ticker for {symbol}: {e}", exc_info=True)
        return jsonify({
            'error': 'Internal error',
            'message': str(e)
        }), 500


@ticker_bp.route('/api/ticker/batch', methods=['POST'])
def get_batch_tickers():
    """
    Get ticker data for multiple symbols in a single request.
    
    This is more efficient than making individual requests for each symbol.
    
    Request Body:
        {
            "symbols": ["C-BTC-95000-310125", "P-BTC-90000-270226", ...]
        }
    
    Returns:
        JSON response with ticker data for all symbols
        {
            "results": {
                "C-BTC-95000-310125": { ... ticker data ... },
                "P-BTC-90000-270226": { ... ticker data ... },
                ...
            },
            "errors": {
                "INVALID-SYMBOL": "Ticker not found"
            }
        }
    """
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        
        if not symbols:
            return jsonify({
                'error': 'No symbols provided',
                'message': 'Request body must include "symbols" array'
            }), 400
        
        if len(symbols) > 50:
            return jsonify({
                'error': 'Too many symbols',
                'message': 'Maximum 50 symbols per batch request'
            }), 400
        
        results = {}
        errors = {}
        
        # Fetch each symbol (could be parallelized for better performance)
        for symbol in symbols:
            cache_key = f"ticker_{symbol}"
            
            # Check cache
            if cache_key in _ticker_cache:
                cached_time, cached_data = _ticker_cache[cache_key]
                if time.time() - cached_time < _cache_ttl:
                    results[symbol] = cached_data
                    continue
            
            try:
                api_url = f"https://api.india.delta.exchange/v2/tickers/{symbol}"
                response = requests.get(api_url, timeout=5)
                
                if response.status_code == 404:
                    errors[symbol] = "Ticker not found"
                    continue
                
                if response.status_code != 200:
                    errors[symbol] = f"API error: {response.status_code}"
                    continue
                
                data = response.json()
                if not data.get('success'):
                    errors[symbol] = data.get('error', 'Unknown error')
                    continue
                
                result = data.get('result', {})
                ticker_data = {
                    'symbol': result.get('symbol', symbol),
                    'mark_price': result.get('mark_price'),
                    'spot_price': result.get('spot_price'),
                }
                
                if 'greeks' in result:
                    ticker_data['greeks'] = {
                        'delta': result['greeks'].get('delta'),
                        'gamma': result['greeks'].get('gamma'),
                        'theta': result['greeks'].get('theta'),
                        'vega': result['greeks'].get('vega'),
                        'rho': result['greeks'].get('rho'),
                    }
                
                _ticker_cache[cache_key] = (time.time(), ticker_data)
                results[symbol] = ticker_data
                
                # Update price alert monitor with spot price (for BTC symbols)
                if ticker_data.get('spot_price') and 'BTC' in symbol.upper():
                    _update_price_monitor(float(ticker_data['spot_price']))
                
            except Exception as e:
                log.error(f"Error fetching {symbol}: {e}")
                errors[symbol] = str(e)
        
        return jsonify({
            'results': results,
            'errors': errors if errors else None
        })
        
    except Exception as e:
        log.error(f"Batch ticker request error: {e}", exc_info=True)
        return jsonify({
            'error': 'Internal error',
            'message': str(e)
        }), 500
