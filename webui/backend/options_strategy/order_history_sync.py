"""
Order History Sync Service

Syncs order history from Delta Exchange to track all trades,
including those made directly on the exchange UI.

Features:
- Fetches order history from Delta Exchange API
- Matches orders to open trades in trade_logger
- Automatically marks trades as closed with PnL
- Runs periodically or on-demand

Created: January 15, 2026
"""

import asyncio
import time
import json
import hashlib
import hmac
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging
import requests

logger = logging.getLogger(__name__)

# Data directory for caching
DATA_DIR = Path(__file__).parent.parent / 'data'
ORDER_HISTORY_CACHE = DATA_DIR / 'order_history_cache.json'
LAST_SYNC_FILE = DATA_DIR / 'last_order_sync.json'


class OrderHistorySync:
    """Syncs order history from Delta Exchange to track trade closes."""
    
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = False):
        """
        Initialize the sync service.
        
        Args:
            api_key: Delta Exchange API key
            api_secret: Delta Exchange API secret
            testnet: Use testnet/demo mode
        """
        # Load credentials from config if not provided
        if not api_key or not api_secret:
            from config.loader import get_api_credentials
            creds = get_api_credentials()
            api_key = creds['api_key']
            api_secret = creds['api_secret']
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # API endpoints
        if testnet:
            self.base_url = "https://cdn-ind.testnet.deltaex.org"
        else:
            self.base_url = "https://api.india.delta.exchange"
        
        # Sync state
        self.last_sync_time = self._load_last_sync_time()
        self.running = False
        self.sync_thread = None
        
        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ OrderHistorySync initialized (testnet={testnet})")
    
    def _load_last_sync_time(self) -> Optional[int]:
        """Load last sync timestamp."""
        try:
            if LAST_SYNC_FILE.exists():
                with open(LAST_SYNC_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get('last_sync_timestamp')
        except Exception as e:
            logger.warning(f"Could not load last sync time: {e}")
        return None
    
    def _save_last_sync_time(self, timestamp: int):
        """Save last sync timestamp."""
        try:
            with open(LAST_SYNC_FILE, 'w') as f:
                json.dump({
                    'last_sync_timestamp': timestamp,
                    'last_sync_time': datetime.fromtimestamp(timestamp).isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save last sync time: {e}")
    
    def _generate_signature(self, method: str, path: str, payload: str = "") -> Dict[str, str]:
        """
        Generate Delta Exchange API signature.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (without base URL)
            payload: Request payload (query string for GET, JSON for POST)
            
        Returns:
            Headers dict with signature
        """
        timestamp = str(int(time.time()))
        
        # Build signature string: method + timestamp + path + payload
        signature_data = method + timestamp + path + payload
        
        # Generate HMAC SHA256 signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return {
            'api-key': self.api_key,
            'timestamp': timestamp,
            'signature': signature,
            'User-Agent': 'python-order-sync',
            'Content-Type': 'application/json'
        }
    
    def get_order_history(
        self,
        product_id: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        page_size: int = 100,
        states: List[str] = None
    ) -> List[Dict]:
        """
        Fetch order history from Delta Exchange.
        
        Args:
            product_id: Filter by product ID (optional)
            start_time: Start timestamp in seconds (optional)
            end_time: End timestamp in seconds (optional)
            page_size: Number of orders per page
            states: Filter by order states (e.g., ['filled', 'cancelled'])
            
        Returns:
            List of order dictionaries
        """
        all_orders = []
        after = None
        
        # Default to filled orders only for trade tracking
        if states is None:
            states = ['filled']
        
        logger.info(f"Fetching order history (product_id={product_id}, states={states})...")
        
        while True:
            # Build query parameters
            params = {
                'page_size': str(page_size),
            }
            
            if product_id:
                params['product_id'] = str(product_id)
            
            if start_time:
                params['start_time'] = str(start_time)
            
            if end_time:
                params['end_time'] = str(end_time)
            
            if after:
                params['after'] = str(after)
            
            if states:
                params['states'] = ','.join(states)
            
            # Build path with query string
            path = "/v2/orders/history"
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            full_path = f"{path}?{query_string}"
            
            # Generate signature
            headers = self._generate_signature("GET", path, f"?{query_string}")
            
            try:
                response = requests.get(
                    f"{self.base_url}{full_path}",
                    headers=headers,
                    timeout=(5, 30)
                )
                
                response.raise_for_status()
                data = response.json()
                
                if 'result' in data and data['result']:
                    orders = data['result']
                    all_orders.extend(orders)
                    logger.info(f"Fetched {len(orders)} orders. Total: {len(all_orders)}")
                    
                    # Check if there are more pages
                    if len(orders) < page_size:
                        break
                    
                    # Set 'after' cursor for next page
                    after = orders[-1]['id']
                else:
                    break
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching order history: {e}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response: {e.response.text}")
                break
        
        logger.info(f"Total orders fetched: {len(all_orders)}")
        return all_orders
    
    def get_options_order_history(
        self,
        days: int = 30,
        underlying: str = None
    ) -> List[Dict]:
        """
        Fetch options order history.
        
        Args:
            days: Number of days to look back
            underlying: Filter by underlying (e.g., 'BTC', 'ETH')
            
        Returns:
            List of options orders
        """
        # Calculate time range
        end_time = int(time.time())
        start_time = end_time - (days * 24 * 60 * 60)
        
        # If we have last sync time, use that instead
        if self.last_sync_time and self.last_sync_time > start_time:
            start_time = self.last_sync_time
            logger.info(f"Using last sync time: {datetime.fromtimestamp(start_time).isoformat()}")
        
        # Fetch all orders
        all_orders = self.get_order_history(
            start_time=start_time,
            end_time=end_time,
            states=['filled']  # Only filled orders count as trades
        )
        
        # Filter options orders (symbols like C-BTC-95000-160126 or P-ETH-3500-160126)
        options_orders = []
        for order in all_orders:
            symbol = order.get('product_symbol', '')
            
            # Check if it's an options symbol
            if symbol.startswith('C-') or symbol.startswith('P-'):
                # Filter by underlying if specified
                if underlying:
                    if f"-{underlying}-" in symbol:
                        options_orders.append(order)
                else:
                    options_orders.append(order)
        
        logger.info(f"Found {len(options_orders)} options orders out of {len(all_orders)} total")
        return options_orders
    
    def sync_trades_from_orders(self, orders: List[Dict] = None, days: int = 30) -> Dict:
        """
        Sync order history with trade_logger to mark closed trades.
        
        This matches orders from Delta Exchange with open trades in our system
        and marks them as closed with the actual PnL.
        
        Args:
            orders: Pre-fetched orders (if None, will fetch from exchange)
            days: Days to look back if fetching orders
            
        Returns:
            Dict with sync statistics
        """
        from .trade_logger import trade_logger
        import pandas as pd
        
        logger.info("Starting trade sync from order history...")
        
        # Fetch orders if not provided
        if orders is None:
            orders = self.get_options_order_history(days=days)
        
        if not orders:
            logger.info("No orders to sync")
            return {'synced': 0, 'errors': 0, 'message': 'No orders found'}
        
        # Get all open trades from trade_logger
        try:
            df = trade_logger.get_all_trades()
            open_trades = df[df['outcome_status'] == 'open'].copy()
        except Exception as e:
            logger.error(f"Failed to get open trades: {e}")
            return {'synced': 0, 'errors': 1, 'message': str(e)}
        
        if len(open_trades) == 0:
            logger.info("No open trades to sync")
            return {'synced': 0, 'errors': 0, 'message': 'No open trades'}
        
        logger.info(f"Found {len(open_trades)} open trades and {len(orders)} orders to match")
        
        # Group orders by symbol
        orders_by_symbol = {}
        for order in orders:
            symbol = order.get('product_symbol', '')
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            orders_by_symbol[symbol].append(order)
        
        # Track stats
        synced_count = 0
        error_count = 0
        already_closed = 0
        
        # Process each symbol with open trades
        for symbol in open_trades['symbol'].unique():
            symbol_trades = open_trades[open_trades['symbol'] == symbol]
            symbol_orders = orders_by_symbol.get(symbol, [])
            
            if not symbol_orders:
                continue
            
            # Analyze orders for this symbol
            # Find BUY and SELL orders to determine if position was opened/closed
            buy_orders = [o for o in symbol_orders if o.get('side') == 'buy']
            sell_orders = [o for o in symbol_orders if o.get('side') == 'sell']
            
            total_buy_qty = sum(float(o.get('size', 0)) for o in buy_orders)
            total_sell_qty = sum(float(o.get('size', 0)) for o in sell_orders)
            
            # Get average prices
            avg_buy_price = 0
            avg_sell_price = 0
            
            if buy_orders:
                total_buy_value = sum(float(o.get('size', 0)) * float(o.get('average_fill_price') or o.get('limit_price', 0)) for o in buy_orders)
                avg_buy_price = total_buy_value / total_buy_qty if total_buy_qty > 0 else 0
            
            if sell_orders:
                total_sell_value = sum(float(o.get('size', 0)) * float(o.get('average_fill_price') or o.get('limit_price', 0)) for o in sell_orders)
                avg_sell_price = total_sell_value / total_sell_qty if total_sell_qty > 0 else 0
            
            # Determine if position is closed
            # For options: if total_buy == total_sell, position is flat (closed)
            net_position = total_buy_qty - total_sell_qty
            
            if abs(net_position) < 0.001:  # Position is closed (flat)
                # Calculate PnL
                # If we SOLD to close a BOUGHT position: PnL = sell_value - buy_value
                # If we BOUGHT to close a SOLD position: PnL = buy_value - sell_value (inverted)
                
                # Check what the original trade was (first order)
                if symbol_orders:
                    first_order = sorted(symbol_orders, key=lambda x: x.get('created_at', ''))[0]
                    first_side = first_order.get('side')
                    
                    if first_side == 'buy':
                        # Bought first, sold to close
                        pnl = (avg_sell_price - avg_buy_price) * total_buy_qty
                    else:
                        # Sold first, bought to close
                        pnl = (avg_sell_price - avg_buy_price) * total_sell_qty
                    
                    pnl_pct = ((avg_sell_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0
                    
                    # Close trades in trade_logger
                    try:
                        closed = trade_logger.close_trades_by_symbol(
                            symbol=symbol,
                            close_price=avg_sell_price if first_side == 'buy' else avg_buy_price,
                            pnl=pnl,
                            pnl_pct=pnl_pct
                        )
                        synced_count += closed
                        logger.info(f"✅ Synced {symbol}: closed {closed} trades, PnL=${pnl:.2f}")
                    except Exception as e:
                        logger.error(f"Failed to close trades for {symbol}: {e}")
                        error_count += 1
            else:
                logger.debug(f"Position {symbol} still open (net: {net_position})")
        
        # Save sync timestamp
        self._save_last_sync_time(int(time.time()))
        
        result = {
            'synced': synced_count,
            'errors': error_count,
            'orders_processed': len(orders),
            'open_trades_checked': len(open_trades),
            'message': f'Synced {synced_count} trades from {len(orders)} orders'
        }
        
        logger.info(f"Sync complete: {result}")
        return result
    
    def auto_detect_closed_positions(self) -> Dict:
        """
        Auto-detect closed positions by comparing current positions with logged trades.
        
        This doesn't need order history - it just checks if positions that were
        logged as open are no longer present in current exchange positions.
        
        Returns:
            Dict with detection results
        """
        from .trade_logger import trade_logger
        import pandas as pd
        
        logger.info("Auto-detecting closed positions...")
        
        # Get current positions from exchange
        try:
            from bot.api.unified_api_client import UnifiedAPIClient
            from config.loader import get_api_credentials
            
            creds = get_api_credentials()
            client = UnifiedAPIClient(
                api_key=creds['api_key'],
                api_secret=creds['api_secret'],
                enable_websocket=False
            )
            
            # Fetch current positions
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            positions_response = loop.run_until_complete(client.get_all_positions_with_options())
            
            current_positions = positions_response.get('options', [])
            current_symbols = {p.get('product_symbol') for p in current_positions if p.get('size', 0) != 0}
            
        except Exception as e:
            logger.error(f"Failed to fetch current positions: {e}")
            return {'detected': 0, 'errors': 1, 'message': str(e)}
        
        # Get open trades from trade_logger
        try:
            df = trade_logger.get_all_trades()
            open_trades = df[df['outcome_status'] == 'open'].copy()
        except Exception as e:
            logger.error(f"Failed to get trades: {e}")
            return {'detected': 0, 'errors': 1, 'message': str(e)}
        
        # Find symbols that have open trades but no current position
        logged_symbols = set(open_trades['symbol'].unique())
        closed_symbols = logged_symbols - current_symbols
        
        logger.info(f"Current positions: {len(current_symbols)}, Logged open: {len(logged_symbols)}, Detected closed: {len(closed_symbols)}")
        
        # Mark those trades as closed
        detected_count = 0
        for symbol in closed_symbols:
            try:
                # Get the last known price from the trade
                symbol_trades = open_trades[open_trades['symbol'] == symbol]
                if len(symbol_trades) > 0:
                    last_price = float(symbol_trades.iloc[-1]['price'])
                    
                    # Close with estimated PnL (we don't know exact close price)
                    closed = trade_logger.close_trades_by_symbol(
                        symbol=symbol,
                        close_price=last_price,  # Use last known price as estimate
                        pnl=0,  # We don't know actual PnL without order history
                        pnl_pct=0
                    )
                    detected_count += closed
                    logger.info(f"✅ Auto-detected closure: {symbol} ({closed} trades)")
            except Exception as e:
                logger.error(f"Failed to mark {symbol} as closed: {e}")
        
        return {
            'detected': detected_count,
            'closed_symbols': list(closed_symbols),
            'current_positions': len(current_symbols),
            'message': f'Detected {detected_count} closed trades from {len(closed_symbols)} symbols'
        }
    
    def start_background_sync(self, interval_minutes: int = 5):
        """Start background sync thread."""
        if self.running:
            logger.warning("Background sync already running")
            return
        
        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, args=(interval_minutes,), daemon=True)
        self.sync_thread.start()
        logger.info(f"Started background sync (interval: {interval_minutes} min)")
    
    def stop_background_sync(self):
        """Stop background sync thread."""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=10)
        logger.info("Stopped background sync")
    
    def _sync_loop(self, interval_minutes: int):
        """Background sync loop."""
        while self.running:
            try:
                # Run sync
                result = self.sync_trades_from_orders(days=7)  # Sync last 7 days
                logger.info(f"Background sync completed: {result}")
            except Exception as e:
                logger.error(f"Background sync error: {e}")
            
            # Wait for next interval
            for _ in range(interval_minutes * 60):
                if not self.running:
                    break
                time.sleep(1)


# Singleton instance
_order_sync = None

def get_order_sync() -> OrderHistorySync:
    """Get singleton OrderHistorySync instance."""
    global _order_sync
    if _order_sync is None:
        _order_sync = OrderHistorySync()
    return _order_sync


def sync_order_history(days: int = 30) -> Dict:
    """Convenience function to sync order history."""
    sync = get_order_sync()
    return sync.sync_trades_from_orders(days=days)


def auto_detect_closures() -> Dict:
    """Convenience function to auto-detect closed positions."""
    sync = get_order_sync()
    return sync.auto_detect_closed_positions()
