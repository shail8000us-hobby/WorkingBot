"""
Futures Trading API - SEPARATE MODULE

This is a STANDALONE module for futures trading operations.
Does NOT touch existing trading logic, grid bot, or options systems.

Created: January 18, 2026
Purpose: Provide Buy/Sell/Close endpoints for Futures Panel UI

⚠️ COMPLETE SEPARATION FROM EXISTING TRADING LOGIC
"""

import sys
import logging
import traceback
from pathlib import Path
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

log = logging.getLogger(__name__)

# Create blueprint
futures_trading_bp = Blueprint('futures_trading', __name__, url_prefix='/api/futures/trade')


def _get_delta_client():
    """Get Delta Exchange client instance"""
    try:
        from bot.api.delta_client import DeltaClient
        return DeltaClient()
    except Exception as e:
        log.error(f"Failed to initialize Delta client: {e}")
        log.error(f"Traceback: {traceback.format_exc()}")
        return None


@futures_trading_bp.route('/buy', methods=['POST'])
def buy_futures():
    """
    Place a BUY order for futures position.
    
    Request Body:
        {
            "symbol": "BTCUSD",
            "product_id": 139,
            "size": 10,
            "price": 95000.00,
            "is_market": false
        }
    
    Returns:
        JSON response with order details
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['symbol', 'product_id', 'size']
        for field in required:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        symbol = data['symbol']
        product_id = int(data['product_id'])
        size = int(data['size'])
        price = float(data.get('price', 0))
        is_market = data.get('is_market', False)
        
        # Validate size
        if size <= 0:
            return jsonify({
                'success': False,
                'error': 'Size must be greater than 0'
            }), 400
        
        delta_client = _get_delta_client()
        if not delta_client:
            return jsonify({
                'success': False,
                'error': 'Delta client not available'
            }), 503
        
        # Prepare order parameters
        order_type = 'market_order' if is_market else 'limit_order'
        
        # For market orders, fetch current market price
        if is_market:
            ticker_response = delta_client._req('GET', f'/v2/tickers/{symbol}')
            if ticker_response.get('success'):
                ticker = ticker_response.get('result', {})
                price = float(ticker.get('mark_price', 0))
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to fetch market price'
                }), 502
        
        # Validate price for limit orders
        if not is_market and price <= 0:
            return jsonify({
                'success': False,
                'error': 'Price must be greater than 0 for limit orders'
            }), 400
        
        # Place order via Delta client
        order_response = delta_client.place_order(
            product_id=product_id,
            side='buy',
            size=size,
            limit_price=str(price),
            order_type=order_type,
            time_in_force='gtc'
        )
        
        if not order_response.get('success'):
            error_msg = order_response.get('error', 'Unknown error')
            log.error(f"Failed to place buy order: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 502
        
        order_result = order_response.get('result', {})
        
        log.info(f"✅ BUY order placed: {symbol} size={size} price={price} type={order_type}")
        
        return jsonify({
            'success': True,
            'order': {
                'id': order_result.get('id'),
                'symbol': symbol,
                'side': 'buy',
                'size': size,
                'price': price,
                'order_type': order_type,
                'state': order_result.get('state')
            }
        })
        
    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"Error placing buy order: {e}")
        log.error(f"Traceback:\n{tb}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@futures_trading_bp.route('/sell', methods=['POST'])
def sell_futures():
    """
    Place a SELL order for futures position.
    
    Request Body:
        {
            "symbol": "BTCUSD",
            "product_id": 139,
            "size": 10,
            "price": 95000.00,
            "is_market": false
        }
    
    Returns:
        JSON response with order details
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['symbol', 'product_id', 'size']
        for field in required:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        symbol = data['symbol']
        product_id = int(data['product_id'])
        size = int(data['size'])
        price = float(data.get('price', 0))
        is_market = data.get('is_market', False)
        
        # Validate size
        if size <= 0:
            return jsonify({
                'success': False,
                'error': 'Size must be greater than 0'
            }), 400
        
        delta_client = _get_delta_client()
        if not delta_client:
            return jsonify({
                'success': False,
                'error': 'Delta client not available'
            }), 503
        
        # Prepare order parameters
        order_type = 'market_order' if is_market else 'limit_order'
        
        # For market orders, fetch current market price
        if is_market:
            ticker_response = delta_client._req('GET', f'/v2/tickers/{symbol}')
            if ticker_response.get('success'):
                ticker = ticker_response.get('result', {})
                price = float(ticker.get('mark_price', 0))
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to fetch market price'
                }), 502
        
        # Validate price for limit orders
        if not is_market and price <= 0:
            return jsonify({
                'success': False,
                'error': 'Price must be greater than 0 for limit orders'
            }), 400
        
        # Place order via Delta client
        order_response = delta_client.place_order(
            product_id=product_id,
            side='sell',
            size=size,
            limit_price=str(price),
            order_type=order_type,
            time_in_force='gtc'
        )
        
        if not order_response.get('success'):
            error_msg = order_response.get('error', 'Unknown error')
            log.error(f"Failed to place sell order: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 502
        
        order_result = order_response.get('result', {})
        
        log.info(f"✅ SELL order placed: {symbol} size={size} price={price} type={order_type}")
        
        return jsonify({
            'success': True,
            'order': {
                'id': order_result.get('id'),
                'symbol': symbol,
                'side': 'sell',
                'size': size,
                'price': price,
                'order_type': order_type,
                'state': order_result.get('state')
            }
        })
        
    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"Error placing sell order: {e}")
        log.error(f"Traceback:\n{tb}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@futures_trading_bp.route('/close/<int:product_id>', methods=['POST'])
def close_position(product_id: int):
    """
    Close a futures position by product_id (market order).
    
    Args:
        product_id: Delta Exchange product ID
    
    Returns:
        JSON response with close order details
    """
    try:
        delta_client = _get_delta_client()
        if not delta_client:
            return jsonify({
                'success': False,
                'error': 'Delta client not available'
            }), 503
        
        # Close position using Delta client
        close_response = delta_client.close_position(product_id=product_id)
        
        if not close_response.get('success'):
            error_msg = close_response.get('error', 'Unknown error')
            log.error(f"Failed to close position {product_id}: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 502
        
        log.info(f"✅ Position closed: product_id={product_id}")
        
        return jsonify({
            'success': True,
            'message': f'Position {product_id} closed successfully'
        })
        
    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"Error closing position {product_id}: {e}")
        log.error(f"Traceback:\n{tb}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@futures_trading_bp.route('/close-all', methods=['POST'])
def close_all_positions():
    """
    Close ALL futures positions at once.
    
    Returns:
        JSON response with results for each position
    """
    try:
        delta_client = _get_delta_client()
        if not delta_client:
            return jsonify({
                'success': False,
                'error': 'Delta client not available'
            }), 503
        
        # Fetch all positions
        positions_response = delta_client._req('GET', '/v2/positions/margined')
        
        if not positions_response.get('success'):
            return jsonify({
                'success': False,
                'error': 'Failed to fetch positions'
            }), 502
        
        all_positions = positions_response.get('result', [])
        
        # Filter for futures positions only
        futures_positions = []
        for pos in all_positions:
            product_symbol = pos.get('product_symbol', '')
            size = pos.get('size', 0)
            
            # Check if futures position
            if size != 0 and '-C-' not in product_symbol and '-P-' not in product_symbol:
                futures_positions.append(pos)
        
        if not futures_positions:
            return jsonify({
                'success': True,
                'message': 'No futures positions to close',
                'closed_count': 0
            })
        
        # Close each position
        results = []
        success_count = 0
        
        for pos in futures_positions:
            product_id = pos.get('product_id')
            symbol = pos.get('product_symbol')
            
            try:
                close_response = delta_client.close_position(product_id=product_id)
                
                if close_response.get('success'):
                    success_count += 1
                    results.append({
                        'product_id': product_id,
                        'symbol': symbol,
                        'success': True
                    })
                    log.info(f"✅ Closed position: {symbol}")
                else:
                    results.append({
                        'product_id': product_id,
                        'symbol': symbol,
                        'success': False,
                        'error': close_response.get('error', 'Unknown error')
                    })
                    log.error(f"❌ Failed to close {symbol}: {close_response.get('error')}")
            except Exception as pos_error:
                results.append({
                    'product_id': product_id,
                    'symbol': symbol,
                    'success': False,
                    'error': str(pos_error)
                })
                log.error(f"❌ Error closing {symbol}: {pos_error}")
        
        log.info(f"✅ Close all completed: {success_count}/{len(futures_positions)} positions closed")
        
        return jsonify({
            'success': True,
            'closed_count': success_count,
            'total_count': len(futures_positions),
            'results': results
        })
        
    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"Error closing all positions: {e}")
        log.error(f"Traceback:\n{tb}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
