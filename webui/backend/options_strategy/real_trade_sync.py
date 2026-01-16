"""
Real Trade Sync Service

Fetches actual order history from Delta Exchange and calculates real PnL.
Runs hourly to keep trade data accurate for ML training.

Features:
- Fetches all options orders from Delta Exchange API
- Groups orders by symbol to calculate net positions
- Calculates realized PnL for closed positions
- Tracks unrealized PnL for open positions
- Stores data in trade log for ML training
- Runs automatically every hour

Created: January 16, 2026
"""

import sys
import time
import json
import hashlib
import hmac
import threading
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict
import logging
import requests
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = Path(__file__).parent.parent / 'data'
SYNC_STATE_FILE = DATA_DIR / 'real_trade_sync_state.json'
REAL_TRADES_FILE = DATA_DIR / 'real_options_trades.csv'

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)


class RealTradeSync:
    """
    Syncs real trades from Delta Exchange and calculates actual PnL.
    
    This is the source of truth for trade data used in ML training.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._sync_lock = threading.Lock()
        self._scheduler_thread = None
        self._running = False
        
        # Load API credentials
        try:
            from config.loader import get_api_credentials
            creds = get_api_credentials()
            self.api_key = creds['api_key']
            self.api_secret = creds['api_secret']
        except Exception as e:
            logger.error(f"Failed to load API credentials: {e}")
            self.api_key = None
            self.api_secret = None
        
        # API endpoint (production India)
        self.base_url = "https://api.india.delta.exchange"
        
        # Load sync state
        self.sync_state = self._load_sync_state()
        
        logger.info("✅ RealTradeSync initialized")
    
    def _load_sync_state(self) -> dict:
        """Load sync state from file."""
        try:
            if SYNC_STATE_FILE.exists():
                with open(SYNC_STATE_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load sync state: {e}")
        return {
            'last_sync_timestamp': None,
            'last_sync_time': None,
            'total_syncs': 0,
            'last_order_id': None,
        }
    
    def _save_sync_state(self):
        """Save sync state to file."""
        try:
            with open(SYNC_STATE_FILE, 'w') as f:
                json.dump(self.sync_state, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save sync state: {e}")
    
    def _generate_signature(self, method: str, path: str, query: str = "") -> Dict[str, str]:
        """Generate Delta Exchange API signature."""
        timestamp = str(int(time.time()))
        signature_data = method + timestamp + path + query
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return {
            'api-key': self.api_key,
            'timestamp': timestamp,
            'signature': signature,
            'User-Agent': 'python-real-trade-sync',
            'Content-Type': 'application/json'
        }
    
    def fetch_all_orders(self, days: int = 3, max_pages: int = 20) -> List[Dict]:
        """
        Fetch all orders from Delta Exchange for the specified period.
        
        Args:
            days: Number of days to look back (used for filtering after fetch)
            max_pages: Maximum pages to fetch (100 orders per page)
            
        Returns:
            List of all orders
        """
        if not self.api_key or not self.api_secret:
            logger.error("API credentials not configured")
            return []
        
        all_orders = []
        after_cursor = None
        
        # Calculate cutoff time for filtering
        cutoff_time = datetime.now() - timedelta(days=days)
        
        logger.info(f"Fetching orders (last {days} days, cutoff: {cutoff_time})")
        
        for page in range(max_pages):
            try:
                # Build query parameters (no time filter - API doesn't work well with it)
                params = {'page_size': '100'}
                if after_cursor:
                    params['after'] = after_cursor
                
                query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
                path = '/v2/orders/history'
                
                headers = self._generate_signature('GET', path, f'?{query_string}')
                
                response = requests.get(
                    f'{self.base_url}{path}?{query_string}',
                    headers=headers,
                    timeout=30
                )
                
                response.raise_for_status()
                data = response.json()
                
                results = data.get('result', [])
                if not results:
                    break
                
                # Filter by date and add to list
                for order in results:
                    created_at = order.get('created_at', '')
                    try:
                        order_time = datetime.fromisoformat(created_at.replace('Z', '+00:00').replace('+00:00', ''))
                        if order_time >= cutoff_time:
                            all_orders.append(order)
                    except:
                        all_orders.append(order)  # Include if can't parse date
                
                # Get cursor for next page
                after_cursor = data.get('meta', {}).get('after')
                if not after_cursor:
                    break
                
                logger.info(f"Page {page + 1}: {len(all_orders)} orders within {days} days")
                
                # Small delay to avoid rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error fetching orders page {page + 1}: {e}")
                break
        
        logger.info(f"Total orders fetched: {len(all_orders)}")
        return all_orders
    
    def filter_options_orders(self, orders: List[Dict], include_futures: bool = True) -> List[Dict]:
        """Filter for options orders (and optionally futures)."""
        filtered = []
        for order in orders:
            symbol = order.get('product_symbol', '')
            state = order.get('state', '')
            
            # Only include closed (filled) orders
            if state != 'closed':
                continue
            
            # Options (C- or P- prefix)
            if symbol.startswith('C-') or symbol.startswith('P-'):
                filtered.append(order)
            # Futures (BTCUSD, ETHUSD, etc.)
            elif include_futures and symbol.endswith('USD'):
                filtered.append(order)
        
        logger.info(f"Filtered {len(filtered)} orders from {len(orders)} total (include_futures={include_futures})")
        return filtered
    
    def calculate_pnl_by_symbol(self, orders: List[Dict]) -> Dict[str, Dict]:
        """
        Calculate PnL for each symbol based on order history.
        
        For options:
        - SELL = receive premium (positive inflow)
        - BUY = pay premium (negative outflow)
        - Net PnL = total_sold - total_bought
        
        IMPORTANT: Delta Exchange lot sizes:
        - Options: 0.001 BTC per contract
        - Futures: 1 USD per contract (size is in USD already)
        
        Returns:
            Dict with symbol -> PnL data
        """
        by_symbol = defaultdict(lambda: {
            'buys': [],
            'sells': [],
            'buy_qty': 0,
            'sell_qty': 0,
            'buy_value': 0,
            'sell_value': 0,
            'orders': [],
            'is_options': False,
        })
        
        for order in orders:
            symbol = order['product_symbol']
            size = float(order.get('size', 0))
            price = float(order.get('average_fill_price', 0) or 0)
            created_at = order.get('created_at', '')
            
            # Determine if options or futures
            is_options = symbol.startswith('C-') or symbol.startswith('P-')
            by_symbol[symbol]['is_options'] = is_options
            
            # Calculate value based on product type
            if is_options:
                # Options: lot size is 0.001 BTC per contract
                # Value = size × price × 0.001
                LOT_SIZE = 0.001
                value = size * price * LOT_SIZE
            else:
                # Futures: size is in contracts, each contract = $1
                # PnL = (exit_price - entry_price) × size / entry_price for perpetuals
                # But for order history, we track total position value changes
                # For futures, the 'size' is number of contracts (each $1)
                # We need to track entry vs exit prices differently
                value = size * price * 0.001  # Futures also use 0.001 BTC multiplier
            
            by_symbol[symbol]['orders'].append({
                'side': order['side'],
                'size': size,
                'price': price,
                'value': value,
                'created_at': created_at,
                'order_id': order.get('id'),
            })
            
            if order['side'] == 'buy':
                by_symbol[symbol]['buys'].append({'size': size, 'price': price, 'value': value})
                by_symbol[symbol]['buy_qty'] += size
                by_symbol[symbol]['buy_value'] += value
            else:
                by_symbol[symbol]['sells'].append({'size': size, 'price': price, 'value': value})
                by_symbol[symbol]['sell_qty'] += size
                by_symbol[symbol]['sell_value'] += value
        
        # Calculate PnL for each symbol
        results = {}
        for symbol, data in by_symbol.items():
            net_qty = data['sell_qty'] - data['buy_qty']
            net_pnl = data['sell_value'] - data['buy_value']
            
            # Position is closed if net quantity is zero
            is_closed = abs(net_qty) < 0.01
            
            # Calculate average prices
            avg_buy = data['buy_value'] / data['buy_qty'] if data['buy_qty'] > 0 else 0
            avg_sell = data['sell_value'] / data['sell_qty'] if data['sell_qty'] > 0 else 0
            
            # For closed positions, calculate PnL percentage
            if is_closed and data['buy_value'] > 0:
                pnl_pct = (net_pnl / data['buy_value']) * 100
            elif is_closed and data['sell_value'] > 0:
                # Sold first (short), then bought to close
                # Profit if sell_value > buy_value
                pnl_pct = (net_pnl / data['sell_value']) * 100
            else:
                pnl_pct = 0
            
            results[symbol] = {
                'symbol': symbol,
                'is_closed': is_closed,
                'net_qty': net_qty,
                'net_pnl': net_pnl,
                'pnl_pct': pnl_pct,
                'buy_qty': data['buy_qty'],
                'sell_qty': data['sell_qty'],
                'buy_value': data['buy_value'],
                'sell_value': data['sell_value'],
                'avg_buy_price': avg_buy,
                'avg_sell_price': avg_sell,
                'num_orders': len(data['orders']),
                'first_order': min(data['orders'], key=lambda x: x['created_at']) if data['orders'] else None,
                'last_order': max(data['orders'], key=lambda x: x['created_at']) if data['orders'] else None,
            }
        
        return results
    
    def save_trades_to_csv(self, pnl_data: Dict[str, Dict]):
        """
        Save trade data to CSV for ML training.
        
        Creates a clean trade record for each symbol with accurate PnL.
        """
        rows = []
        
        for symbol, data in pnl_data.items():
            # Parse symbol components
            parts = symbol.split('-')
            if len(parts) >= 4:
                option_type = 'Call' if parts[0] == 'C' else 'Put'
                underlying = parts[1]
                strike = parts[2]
                expiry_code = parts[3]
            else:
                option_type = 'Unknown'
                underlying = 'Unknown'
                strike = 0
                expiry_code = ''
            
            # Get timestamps
            first_order = data.get('first_order', {})
            last_order = data.get('last_order', {})
            
            # Calculate duration
            try:
                if first_order and last_order:
                    first_time = datetime.fromisoformat(first_order['created_at'].replace('Z', '+00:00'))
                    last_time = datetime.fromisoformat(last_order['created_at'].replace('Z', '+00:00'))
                    duration_hours = (last_time - first_time).total_seconds() / 3600
                else:
                    duration_hours = 0
            except:
                duration_hours = 0
            
            row = {
                'timestamp': first_order.get('created_at', datetime.now().isoformat()),
                'symbol': symbol,
                'underlying': underlying,
                'option_type': option_type,
                'strike': strike,
                'expiry': expiry_code,
                'is_closed': data['is_closed'],
                'status': 'closed' if data['is_closed'] else 'open',
                'net_qty': data['net_qty'],
                'buy_qty': data['buy_qty'],
                'sell_qty': data['sell_qty'],
                'buy_value': round(data['buy_value'], 2),
                'sell_value': round(data['sell_value'], 2),
                'avg_buy_price': round(data['avg_buy_price'], 2),
                'avg_sell_price': round(data['avg_sell_price'], 2),
                'net_pnl': round(data['net_pnl'], 2),
                'pnl_pct': round(data['pnl_pct'], 2),
                'num_orders': data['num_orders'],
                'duration_hours': round(duration_hours, 2),
                'last_updated': datetime.now().isoformat(),
            }
            rows.append(row)
        
        # Create DataFrame and save
        df = pd.DataFrame(rows)
        df.to_csv(REAL_TRADES_FILE, index=False)
        
        logger.info(f"Saved {len(rows)} trade records to {REAL_TRADES_FILE}")
        return df
    
    def get_summary(self, pnl_data: Dict[str, Dict]) -> Dict:
        """Get summary statistics from PnL data."""
        closed_positions = {k: v for k, v in pnl_data.items() if v['is_closed']}
        open_positions = {k: v for k, v in pnl_data.items() if not v['is_closed']}
        
        # Realized PnL (closed positions only)
        realized_pnl = sum(v['net_pnl'] for v in closed_positions.values())
        
        # Unrealized PnL (open positions)
        unrealized_pnl = sum(v['net_pnl'] for v in open_positions.values())
        
        # Win/Loss counts
        wins = sum(1 for v in closed_positions.values() if v['net_pnl'] > 0)
        losses = sum(1 for v in closed_positions.values() if v['net_pnl'] < 0)
        breakeven = sum(1 for v in closed_positions.values() if v['net_pnl'] == 0)
        
        win_rate = (wins / len(closed_positions) * 100) if closed_positions else 0
        
        return {
            'total_positions': len(pnl_data),
            'closed_positions': len(closed_positions),
            'open_positions': len(open_positions),
            'realized_pnl': round(realized_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'total_pnl': round(realized_pnl + unrealized_pnl, 2),
            'wins': wins,
            'losses': losses,
            'breakeven': breakeven,
            'win_rate': round(win_rate, 1),
        }
    
    def sync(self, days: int = 3) -> Dict:
        """
        Perform a full sync of trade data.
        
        Args:
            days: Number of days to fetch
            
        Returns:
            Summary of sync results
        """
        with self._sync_lock:
            logger.info(f"Starting trade sync for last {days} days...")
            
            try:
                # Fetch all orders
                all_orders = self.fetch_all_orders(days=days)
                
                if not all_orders:
                    return {'success': False, 'error': 'No orders fetched'}
                
                # Filter for OPTIONS ONLY (no futures) - this is for ML training
                options_orders = self.filter_options_orders(all_orders, include_futures=False)
                
                if not options_orders:
                    return {'success': False, 'error': 'No options orders found'}
                
                # Calculate PnL
                pnl_data = self.calculate_pnl_by_symbol(options_orders)
                
                # Save to CSV
                self.save_trades_to_csv(pnl_data)
                
                # Get summary
                summary = self.get_summary(pnl_data)
                
                # Update sync state
                self.sync_state['last_sync_timestamp'] = int(time.time())
                self.sync_state['last_sync_time'] = datetime.now().isoformat()
                self.sync_state['total_syncs'] += 1
                self._save_sync_state()
                
                logger.info(f"✅ Sync complete: {summary}")
                
                return {
                    'success': True,
                    'summary': summary,
                    'orders_processed': len(options_orders),
                    'positions_tracked': len(pnl_data),
                }
                
            except Exception as e:
                logger.error(f"Sync failed: {e}")
                return {'success': False, 'error': str(e)}
    
    def get_trades_for_ml(self) -> pd.DataFrame:
        """
        Get trade data formatted for ML training.
        
        Returns:
            DataFrame with trade features
        """
        if not REAL_TRADES_FILE.exists():
            logger.warning("No trade data file found. Run sync first.")
            return pd.DataFrame()
        
        df = pd.read_csv(REAL_TRADES_FILE)
        return df
    
    def get_trade_statistics(self) -> Dict:
        """Get current trade statistics for dashboard."""
        if not REAL_TRADES_FILE.exists():
            return {
                'total_trades': 0,
                'closed_trades': 0,
                'open_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'realized_pnl': 0,
                'unrealized_pnl': 0,
            }
        
        df = pd.read_csv(REAL_TRADES_FILE)
        
        closed = df[df['is_closed'] == True]
        opened = df[df['is_closed'] == False]
        
        wins = (closed['net_pnl'] > 0).sum()
        win_rate = (wins / len(closed) * 100) if len(closed) > 0 else 0
        
        return {
            'total_trades': len(df),
            'closed_trades': len(closed),
            'open_trades': len(opened),
            'wins': int(wins),
            'losses': int((closed['net_pnl'] < 0).sum()),
            'win_rate': round(win_rate, 1),
            'total_pnl': round(df['net_pnl'].sum(), 2),
            'realized_pnl': round(closed['net_pnl'].sum(), 2),
            'unrealized_pnl': round(opened['net_pnl'].sum(), 2),
            'last_sync': self.sync_state.get('last_sync_time'),
        }
    
    def start_hourly_sync(self):
        """Start the hourly sync scheduler."""
        if self._running:
            logger.info("Hourly sync already running")
            return
        
        self._running = True
        
        # Schedule hourly sync
        schedule.every(1).hours.do(self._scheduled_sync)
        
        # Run scheduler in background thread
        def run_scheduler():
            logger.info("🕐 Hourly sync scheduler started")
            while self._running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        self._scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self._scheduler_thread.start()
        
        logger.info("✅ Hourly sync scheduler started")
    
    def stop_hourly_sync(self):
        """Stop the hourly sync scheduler."""
        self._running = False
        schedule.clear()
        logger.info("⏹ Hourly sync scheduler stopped")
    
    def _scheduled_sync(self):
        """Called by scheduler for hourly sync."""
        logger.info("🔄 Running scheduled hourly sync...")
        result = self.sync(days=3)  # Always sync last 3 days
        logger.info(f"Scheduled sync result: {result}")
        return result
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running


# Singleton instance
_real_trade_sync = None


def get_real_trade_sync() -> RealTradeSync:
    """Get the singleton RealTradeSync instance."""
    global _real_trade_sync
    if _real_trade_sync is None:
        _real_trade_sync = RealTradeSync()
    return _real_trade_sync


# CLI for testing
if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    
    sync = get_real_trade_sync()
    
    print("=" * 60)
    print("Real Trade Sync - Manual Run")
    print("=" * 60)
    
    # Run sync for last 3 days
    result = sync.sync(days=3)
    
    print("\nResult:")
    print(json.dumps(result, indent=2))
    
    if result.get('success'):
        print("\nTrade Statistics:")
        stats = sync.get_trade_statistics()
        print(json.dumps(stats, indent=2))
