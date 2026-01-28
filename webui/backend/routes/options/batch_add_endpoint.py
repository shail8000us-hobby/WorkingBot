"""
Batch Add Endpoint for Options

This endpoint accepts multiple orders and executes them concurrently using asyncio.gather()
to minimize execution time and reduce market movement risk.

Created: January 28, 2026
Purpose: Fast batch order execution for options positions
"""

import asyncio
import time
import logging
from flask import jsonify, request

log = logging.getLogger(__name__)


async def execute_single_order(client, order_data, order_preference, index):
    """
    Execute a single order from the batch.
    
    Args:
        client: UnifiedAPIClient instance
        order_data: Dict with symbol, size, side
        order_preference: Order execution preference
        index: Order index for logging
        
    Returns:
        dict: Result with success status and details
    """
    from .options_control import place_smart_order, with_timeout, validate_order_size
    
    symbol = order_data.get('symbol')
    size = float(order_data.get('size'))
    side = order_data.get('side')
    
    try:
        # Validate order size
        await validate_order_size(client, symbol, size, side, is_close=False)
        
        # Place order with timeout
        result = await with_timeout(
            place_smart_order(
                client=client,
                symbol=symbol,
                size=size,
                side=side,
                order_preference=order_preference,
                limit_price=None
            ),
            timeout_seconds=30
        )
        
        execution_type = result.get('execution_type', 'unknown')
        fill_price = result.get('fill_price') or result.get('limit_price') or result.get('average_fill_price')
        
        log.info(f"✅ Batch order {index + 1}: {symbol} {side} {size} - {execution_type} @ {fill_price}")
        
        return {
            'success': True,
            'symbol': symbol,
            'size': size,
            'side': side,
            'execution_type': execution_type,
            'fill_price': fill_price,
            'order_id': result.get('id'),
            'index': index
        }
        
    except Exception as e:
        log.error(f"❌ Batch order {index + 1} failed: {symbol} {side} {size} - {str(e)}")
        return {
            'success': False,
            'symbol': symbol,
            'size': size,
            'side': side,
            'error': str(e),
            'index': index
        }


def create_batch_add_route(options_bp, get_unified_client, check_guardian_signal, 
                           ORDER_TYPE_MAKER_FIRST, VALID_ORDER_TYPES):
    """
    Create the batch_add route with proper dependencies.
    
    This function is called from options_control.py to inject dependencies.
    """
    
    @options_bp.route('/batch_add', methods=['POST'])
    def batch_add_to_options():
        """
        Add to multiple options positions concurrently.
        
        Request Body:
            {
                orders: [
                    {symbol: str, size: float, side: str},
                    ...
                ],
                order_preference: str,  # 'maker_first', 'maker_only', 'market_only'
                confirm: bool
            }
            
        Returns:
            JSON: Results for all orders
        """
        
        # Check Guardian signal
        guardian_signal = check_guardian_signal()
        if guardian_signal != 'GO':
            return jsonify({
                'success': False,
                'error': f'Guardian signal is {guardian_signal}. Trading disabled.'
            }), 403
        
        try:
            data = request.get_json()
            orders = data.get('orders', [])
            confirm = data.get('confirm', False)
            order_preference = data.get('order_preference', ORDER_TYPE_MAKER_FIRST)
            
            if not orders:
                return jsonify({
                    'success': False,
                    'error': 'No orders provided'
                }), 400
            
            if len(orders) > 50:
                return jsonify({
                    'success': False,
                    'error': 'Maximum 50 orders per batch'
                }), 400
            
            # Validate order_preference
            if order_preference not in VALID_ORDER_TYPES:
                return jsonify({
                    'success': False,
                    'error': f'Invalid order_preference "{order_preference}". Must be one of: {list(VALID_ORDER_TYPES)}'
                }), 400
            
            # Validate all orders have required fields
            for i, order in enumerate(orders):
                if not all([order.get('symbol'), order.get('size'), order.get('side')]):
                    return jsonify({
                        'success': False,
                        'error': f'Order {i + 1} missing required fields: symbol, size, side'
                    }), 400
                
                if order.get('side') not in ['buy', 'sell']:
                    return jsonify({
                        'success': False,
                        'error': f'Order {i + 1} has invalid side: must be "buy" or "sell"'
                    }), 400
            
            # If not confirmed, return summary
            if not confirm:
                return jsonify({
                    'success': True,
                    'action': 'confirm_required',
                    'order_count': len(orders),
                    'order_preference': order_preference,
                    'orders_summary': [
                        {
                            'symbol': o.get('symbol'),
                            'size': o.get('size'),
                            'side': o.get('side')
                        } for o in orders
                    ],
                    'message': f'Confirm batch of {len(orders)} orders? Set confirm=true to execute.'
                })
            
            # Execute all orders concurrently
            client = get_unified_client()
            
            async def execute_batch():
                start_time = time.time()
                
                log.info(f"🚀 Starting batch execution: {len(orders)} orders with {order_preference}")
                
                # Execute all orders concurrently
                tasks = [
                    execute_single_order(client, order, order_preference, i)
                    for i, order in enumerate(orders)
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=False)
                
                elapsed = time.time() - start_time
                successful = sum(1 for r in results if r.get('success'))
                failed = len(results) - successful
                
                log.info(f"✅ Batch complete: {successful} success, {failed} failed in {elapsed:.2f}s")
                
                return results, elapsed, successful, failed
            
            results, elapsed, successful, failed = asyncio.run(execute_batch())
            
            return jsonify({
                'success': True,
                'action': 'batch_executed',
                'order_count': len(orders),
                'successful': successful,
                'failed': failed,
                'execution_time': f"{elapsed:.2f}s",
                'order_preference': order_preference,
                'results': results
            })
            
        except Exception as e:
            log.error(f"Batch add failed: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return batch_add_to_options
