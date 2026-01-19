"""
Options Chain Order Service
===========================
Handles order placement for options from the chain viewer.
Integrates with Delta Exchange API through UnifiedAPIClient.

Created: January 5, 2026
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config, get_api_credentials

log = logging.getLogger(__name__)


class OptionsChainOrderService:
    """Service for placing options orders from chain viewer"""
    
    def __init__(self):
        self._client = None
    
    def _get_client(self):
        """Get or create UnifiedAPIClient"""
        if self._client is None:
            from bot.api.unified_api_client import UnifiedAPIClient
            
            creds = get_api_credentials()
            self._client = UnifiedAPIClient(
                api_key=creds['api_key'],
                api_secret=creds['api_secret'],
                symbol='BTCUSD',
                enable_websocket=False
            )
        return self._client
    
    async def place_order(self, symbol: str, side: str, size: int, 
                         order_type: str = 'market', limit_price: float = None) -> dict:
        """
        Place an options order
        
        Args:
            symbol: Option symbol (e.g., C-BTC-95000-060126)
            side: 'buy' or 'sell'
            size: Number of contracts
            order_type: 'market' or 'limit'
            limit_price: Price for limit orders
            
        Returns:
            dict with success status and order details
        """
        client = self._get_client()
        
        log.info(f"📊 Options Chain Order: {side.upper()} {size} {symbol} @ {order_type}")
        
        # Build order data
        data = {
            "product_symbol": symbol,
            "side": side,
            "size": int(size)
        }
        
        if order_type == 'market':
            data["order_type"] = "market_order"
        else:
            data["order_type"] = "limit_order"
            if limit_price:
                data["limit_price"] = str(limit_price)
            data["time_in_force"] = "gtc"
            data["post_only"] = "false"
        
        try:
            # Place order via REST API
            response = await client.rest_client._request_with_retry(
                method="POST",
                path="/v2/orders",
                data=data
            )
            
            result = response.get('result', response)
            order_id = result.get('id', 'unknown')
            
            log.info(f"✅ Order placed: {order_id}")
            
            return {
                'success': True,
                'order_id': order_id,
                'symbol': symbol,
                'side': side,
                'size': size,
                'order_type': order_type,
                'limit_price': limit_price,
                'status': result.get('state', 'pending'),
                'message': f'Order {order_id} placed successfully',
                'raw': result
            }
            
        except Exception as e:
            log.error(f"❌ Order failed: {e}")
            error_msg = str(e)
            
            # Extract meaningful error message
            if 'insufficient' in error_msg.lower():
                error_msg = 'Insufficient margin/balance'
            elif 'invalid' in error_msg.lower():
                error_msg = f'Invalid order: {error_msg}'
            
            return {
                'success': False,
                'error': error_msg,
                'symbol': symbol,
                'side': side,
                'size': size
            }
    
    async def cancel_order(self, order_id: str, product_id: int) -> dict:
        """
        Cancel an open order
        
        Args:
            order_id: Order ID to cancel
            product_id: Product ID for the order
            
        Returns:
            dict with success status
        """
        client = self._get_client()
        
        log.info(f"📤 Cancelling order: {order_id} (product_id: {product_id})")
        
        try:
            result = await client.rest_client.cancel_order(order_id, product_id)
            
            log.info(f"✅ Order {order_id} cancelled")
            
            return {
                'success': True,
                'order_id': order_id,
                'message': f'Order {order_id} cancelled',
                'raw': result
            }
            
        except Exception as e:
            log.error(f"❌ Cancel failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'order_id': order_id
            }
    
    async def get_open_orders(self) -> dict:
        """
        Get all open options orders
        
        Returns:
            dict with list of open orders
        """
        client = self._get_client()
        
        try:
            # Get open orders
            response = await client.rest_client._request_with_retry(
                method="GET",
                path="/v2/orders",
                params={"state": "open"}
            )
            
            orders = response.get('result', [])
            
            # Filter to options only (symbols starting with C- or P-)
            options_orders = [
                o for o in orders 
                if o.get('product_symbol', '').startswith(('C-', 'P-'))
            ]
            
            return {
                'success': True,
                'orders': options_orders,
                'count': len(options_orders)
            }
            
        except Exception as e:
            log.error(f"❌ Get open orders failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'orders': []
            }
    
    async def get_option_ticker(self, symbol: str) -> dict:
        """
        Get current ticker for an option
        
        Args:
            symbol: Option symbol
            
        Returns:
            Ticker data with bid/ask, IV, etc.
        """
        client = self._get_client()
        
        try:
            ticker = await client.get_option_ticker(symbol)
            return ticker
        except Exception as e:
            log.error(f"Failed to get ticker for {symbol}: {e}")
            return None
