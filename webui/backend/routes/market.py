"""
Market Data Routes Blueprint

This module handles market data API routes for options and trading.

Routes:
- GET /api/market/spot-price - Get current spot price for an underlying

Created: January 12, 2026
Purpose: Provide market data endpoints for options strategy builder
"""

import sys
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config, get_api_credentials

log = logging.getLogger(__name__)

# Create blueprint
market_bp = Blueprint('market', __name__)

# Cache for spot prices (1 second TTL)
_price_cache = {}
_cache_ttl = 1.0


def _get_api_client():
    """Get or create API client for market data"""
    try:
        from bot.api.unified_api_client import UnifiedAPIClient
        creds = get_api_credentials()
        client = UnifiedAPIClient(
            api_key=creds['api_key'],
            api_secret=creds['api_secret'],
            symbol='BTCUSD',
            enable_websocket=False
        )
        return client
    except Exception as e:
        log.error(f"Failed to create API client: {e}")
        return None


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
        Response: {"symbol": "BTC", "price": 94521.50, "source": "api"}
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
        # Try to get price from Delta Exchange
        client = _get_api_client()
        if client:
            # Use the perpetual futures symbol to get current price
            futures_symbol = f"{symbol}USD"
            ticker = client.rest_client.get_ticker(futures_symbol)
            
            if ticker and 'mark_price' in ticker:
                price = float(ticker['mark_price'])
                _price_cache[cache_key] = (time.time(), price)
                return jsonify({
                    'symbol': symbol,
                    'price': price,
                    'source': 'api'
                })
        
        # Fallback: Try to read from guardian signal file which has spot price
        signal_file = Path(__file__).parent.parent.parent.parent / 'data' / 'guardian_signal.json'
        if signal_file.exists():
            import json
            with open(signal_file, 'r') as f:
                data = json.load(f)
                if 'spot_price' in data:
                    price = float(data['spot_price'])
                    _price_cache[cache_key] = (time.time(), price)
                    return jsonify({
                        'symbol': symbol,
                        'price': price,
                        'source': 'guardian'
                    })
        
        # Final fallback - use reasonable defaults
        fallback_prices = {'BTC': 95000, 'ETH': 3500}
        return jsonify({
            'symbol': symbol,
            'price': fallback_prices.get(symbol, 95000),
            'source': 'fallback'
        })
        
    except Exception as e:
        log.error(f"Error fetching spot price for {symbol}: {e}")
        
        # Return fallback price on error
        fallback_prices = {'BTC': 95000, 'ETH': 3500}
        return jsonify({
            'symbol': symbol,
            'price': fallback_prices.get(symbol, 95000),
            'source': 'fallback',
            'error': str(e)
        })
