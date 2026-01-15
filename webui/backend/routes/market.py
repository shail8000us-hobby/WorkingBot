"""
Market Data Routes Blueprint

This module handles market data API routes for options and trading.

Routes:
- GET /api/market/spot-price - Get current spot price for an underlying

Created: January 12, 2026
Updated: January 13, 2026 - Fixed async/await issues and improved price fetching
Purpose: Provide market data endpoints for options strategy builder
"""

import sys
import logging
import requests
from pathlib import Path
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config, get_api_credentials

log = logging.getLogger(__name__)

# Create blueprint
market_bp = Blueprint('market', __name__)

# Cache for spot prices (10 second TTL)
_price_cache = {}
_cache_ttl = 10.0


@market_bp.route('/api/market/spot-price', methods=['GET'])
def get_spot_price():
    """
    Get current spot price for an underlying asset.
    
    Query Parameters:
        symbol: BTC or ETH (default: BTC)
    
    Returns:
        JSON response with current spot price
    
    Example:
        GET /api/market/spot-price?symbol=BTC
        Response: {"symbol": "BTC", "price": 94521.50, "source": "delta_api"}
    """
    import time
    
    symbol = request.args.get('symbol', 'BTC').upper()
    
    if symbol not in ['BTC', 'ETH']:
        return jsonify({
            'error': 'Invalid symbol. Must be BTC or ETH'
        }), 400
    
    # Check cache first
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
                    _price_cache[cache_key] = (time.time(), price)
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
                    _price_cache[cache_key] = (time.time(), price)
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

