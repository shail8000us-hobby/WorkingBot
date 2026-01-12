"""
Orders Routes Blueprint

This module handles all API routes related to order retrieval and management.

Routes:
- GET /api/orders - Get current orders from Delta Exchange

Dependencies:
- bot.api.delta_client (DeltaClient)

Refactored from app.py (8,850 lines)
Date: 2025-10-31
"""

import logging
import sys
from pathlib import Path
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

log = logging.getLogger(__name__)

# Create blueprint
orders_bp = Blueprint('orders', __name__)

# ============================================================================
# Route Handlers
# ============================================================================

@orders_bp.route('/api/orders', methods=['GET'])
def get_orders():
    """
    Get current orders from Delta Exchange
    
    v6.0: Supports per-instance order filtering
    
    Query Parameters:
        state (str): Filter by order state - 'all', 'open', 'filled', 'cancelled' (default: 'all')
        product_id (int): Filter by product ID
        limit (int): Maximum number of orders to return (default: 100)
        instance (str): Optional instance name (e.g., BTCUSD_LONG) for filtering
    
    Returns:
        JSON response with orders list
    
    Example:
        GET /api/orders?state=open&limit=50&instance=BTCUSD_LONG
        Response: {
            "orders": [
                {
                    "id": 123456,
                    "product_id": 27,
                    "side": "buy",
                    "order_type": "limit_order",
                    "size": 10.0,
                    "price": 50000.0,
                    "state": "open",
                    ...
                },
                ...
            ],
            "total": 15,
            "filters": {
                "state": "open",
                "product_id": null,
                "limit": 50,
                "instance": "BTCUSD_LONG"
            }
        }
    """
    try:
        # Get query parameters
        state = request.args.get('state', 'all')  # all, open, filled, cancelled
        product_id = request.args.get('product_id', None)
        limit = int(request.args.get('limit', 100))
        instance = request.args.get('instance')  # v6.0: Instance parameter
        
        # Import DeltaClient
        from bot.api.delta_client import DeltaClient
        
        # Create Delta client
        client = DeltaClient()
        
        # Get orders from exchange
        response = client.list_orders(
            product_id=int(product_id) if product_id else None,
            state=state if state != 'all' else None
        )
        
        # Handle response format
        if isinstance(response, dict) and 'result' in response:
            orders = response['result']
        elif isinstance(response, list):
            orders = response
        else:
            orders = []
        
        # Format orders for frontend
        formatted_orders = []
        for order in orders:
            formatted_orders.append({
                'id': order.get('id'),
                'client_order_id': order.get('client_order_id'),  # AsyncBot order tags (GBOT_BUY_99000_timestamp)
                'product_id': order.get('product_id'),
                'side': order.get('side'),
                'order_type': order.get('order_type'),
                'size': float(order.get('size', 0)),
                'price': float(order.get('price', 0)) if order.get('price') else None,
                'state': order.get('state'),
                'created_at': order.get('created_at'),
                'updated_at': order.get('updated_at'),
                'filled_size': float(order.get('filled_size', 0)),
                'remaining_size': float(order.get('remaining_size', 0)),
                'time_in_force': order.get('time_in_force'),
                'reduce_only': order.get('reduce_only', False),
                'post_only': order.get('post_only', False)
            })
        
        return jsonify({
            'orders': formatted_orders,
            'total': len(formatted_orders),
            'filters': {
                'state': state,
                'product_id': product_id,
                'limit': limit
            }
        }), 200
        
    except Exception as e:
        log.error(f"Error fetching orders: {e}")
        return jsonify({'error': str(e)}), 500
