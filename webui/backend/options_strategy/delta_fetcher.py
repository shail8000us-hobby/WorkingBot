"""
Delta Exchange Trade History Fetcher

Fetches trade history (fills) from Delta Exchange India for accurate PnL/win rate.
This provides real broker data for ML model training.

Created: January 18, 2026
"""

import hashlib
import hmac
import requests
import time
import json
import math
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# Try to get API credentials from config
try:
    import sys
    _project_root = str(Path(__file__).parent.parent.parent.parent)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from config.loader import get_api_credentials
    _creds = get_api_credentials()
    DEFAULT_API_KEY = _creds.get('api_key', '') or ''
    DEFAULT_API_SECRET = _creds.get('api_secret', '') or ''
except Exception:
    DEFAULT_API_KEY = ''
    DEFAULT_API_SECRET = ''


@dataclass
class DeltaTrade:
    """Represents a single trade from Delta Exchange"""
    
    id: str = ""
    order_id: str = ""
    product_id: int = 0
    product_symbol: str = ""
    size: float = 0.0
    side: str = ""  # buy or sell
    price: float = 0.0
    fill_type: str = ""  # normal, adl, liquidation, settlement, otc
    role: str = ""  # taker or maker
    commission: float = 0.0
    realized_pnl: float = 0.0
    created_at: str = ""
    
    # Parsed fields
    option_type: str = ""  # call or put (extracted from symbol)
    strike: float = 0.0
    expiry: str = ""
    is_option: bool = False
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        # Sanitize NaN values
        for key, value in result.items():
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                result[key] = 0.0
        return result


class DeltaExchangeFetcher:
    """
    Fetches trade history from Delta Exchange India.
    
    Uses the /v2/fills API with pagination support.
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.base_url = 'https://api.india.delta.exchange'
        self.api_key = api_key or DEFAULT_API_KEY
        self.api_secret = api_secret or DEFAULT_API_SECRET
        
        # Data storage
        self.data_dir = Path(__file__).parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        self.trades_file = self.data_dir / 'delta_trades.json'
        self.sync_status_file = self.data_dir / 'delta_sync_status.json'
        
        # Cache
        self._trades_cache: List[DeltaTrade] = []
        self._last_sync: Optional[datetime] = None
        
        # Load existing data
        self._load_trades()
    
    def _generate_signature(self, message: str) -> str:
        """Generate HMAC SHA256 signature for authentication"""
        message_bytes = bytes(message, 'utf-8')
        secret_bytes = bytes(self.api_secret, 'utf-8')
        return hmac.new(secret_bytes, message_bytes, hashlib.sha256).hexdigest()
    
    def _make_authenticated_request(
        self, 
        method: str, 
        path: str, 
        query_params: Dict = None,
        body: Dict = None
    ) -> Dict:
        """Make authenticated request to Delta Exchange API"""
        
        if not self.api_key or not self.api_secret:
            return {'error': 'API credentials not configured'}
        
        timestamp = str(int(time.time()))
        
        # Build query string
        query_string = ""
        if query_params:
            query_string = "&".join(f"{k}={v}" for k, v in sorted(query_params.items()) if v is not None)
        
        # Build signature payload
        if method == 'GET':
            signature_payload = f"{method}{timestamp}{path}"
            if query_string:
                signature_payload += f"?{query_string}"
        else:
            body_str = json.dumps(body) if body else ""
            signature_payload = f"{method}{timestamp}{path}{body_str}"
        
        signature = self._generate_signature(signature_payload)
        
        headers = {
            'api-key': self.api_key,
            'signature': signature,
            'timestamp': timestamp,
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}{path}"
        if query_string:
            url += f"?{query_string}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            else:
                response = requests.post(url, headers=headers, json=body, timeout=30)
            
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def fetch_trades(
        self,
        product_ids: str = None,
        contract_types: str = None,
        start_time: int = None,
        end_time: int = None,
        page_size: int = 100
    ) -> List[DeltaTrade]:
        """
        Fetch trade history with pagination support.
        
        Args:
            product_ids: Comma-separated product IDs
            contract_types: e.g., "call_options,put_options"
            start_time: Microseconds since epoch
            end_time: Microseconds since epoch
            page_size: Records per page (max 100)
            
        Returns:
            List of DeltaTrade objects
        """
        
        all_trades = []
        after_cursor = None
        page_count = 0
        max_pages = 100  # Safety limit
        
        while page_count < max_pages:
            page_count += 1
            
            query_params = {
                'page_size': page_size
            }
            
            if product_ids:
                query_params['product_ids'] = product_ids
            if contract_types:
                query_params['contract_types'] = contract_types
            if start_time:
                query_params['start_time'] = start_time
            if end_time:
                query_params['end_time'] = end_time
            if after_cursor:
                query_params['after'] = after_cursor
            
            result = self._make_authenticated_request('GET', '/v2/fills', query_params)
            
            if 'error' in result:
                print(f"Error fetching trades: {result['error']}")
                break
            
            fills = result.get('result', [])
            
            if not fills:
                break
            
            # Parse trades
            for fill in fills:
                trade = self._parse_fill(fill)
                all_trades.append(trade)
            
            # Check for more pages
            meta = result.get('meta', {})
            after_cursor = meta.get('after')
            
            if not after_cursor:
                break
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)
        
        return all_trades
    
    def _parse_fill(self, fill: Dict) -> DeltaTrade:
        """Parse API response into DeltaTrade object"""
        
        symbol = fill.get('product', {}).get('symbol', fill.get('product_symbol', ''))
        
        # Parse option info from symbol
        # Format: C-BTC-96000-180126 or P-BTC-96000-180126
        option_type = ""
        strike = 0.0
        expiry = ""
        is_option = False
        
        if symbol:
            parts = symbol.split('-')
            if len(parts) >= 4:
                if parts[0] in ('C', 'P'):
                    option_type = 'call' if parts[0] == 'C' else 'put'
                    is_option = True
                    try:
                        strike = float(parts[2])
                    except:
                        pass
                    expiry = parts[3] if len(parts) > 3 else ""
        
        # Get realized PnL from meta_data
        meta = fill.get('meta_data', {})
        realized_pnl = 0.0
        if isinstance(meta, dict):
            realized_pnl = float(meta.get('pnl', 0) or 0)
        
        return DeltaTrade(
            id=str(fill.get('id', '')),
            order_id=str(fill.get('order_id', '')),
            product_id=fill.get('product_id', 0),
            product_symbol=symbol,
            size=float(fill.get('size', 0) or 0),
            side=fill.get('side', ''),
            price=float(fill.get('price', 0) or 0),
            fill_type=fill.get('fill_type', ''),
            role=fill.get('role', ''),
            commission=float(fill.get('commission', 0) or 0),
            realized_pnl=realized_pnl,
            created_at=fill.get('created_at', ''),
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            is_option=is_option
        )
    
    def fetch_options_trades(
        self,
        days_back: int = 30,
        underlying: str = "BTC"
    ) -> List[DeltaTrade]:
        """
        Fetch only options trades for a specific period.
        
        Args:
            days_back: Number of days to look back
            underlying: BTC or ETH
            
        Returns:
            List of options trades
        """
        
        # Calculate time range
        end_time = int(datetime.now().timestamp() * 1_000_000)  # Microseconds
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1_000_000)
        
        # Fetch with options contract types
        all_trades = self.fetch_trades(
            contract_types="call_options,put_options",
            start_time=start_time,
            end_time=end_time
        )
        
        # Filter by underlying if specified
        if underlying:
            all_trades = [t for t in all_trades if underlying in t.product_symbol]
        
        return all_trades
    
    def sync_trades(self, days_back: int = 90) -> Dict:
        """
        Sync trades from Delta Exchange.
        
        Args:
            days_back: How many days to sync
            
        Returns:
            Sync result with stats
        """
        
        try:
            print(f"Syncing trades from Delta Exchange (last {days_back} days)...")
            
            # Fetch options trades
            trades = self.fetch_options_trades(days_back=days_back)
            
            # Merge with existing
            existing_ids = {t.id for t in self._trades_cache}
            new_trades = [t for t in trades if t.id not in existing_ids]
            
            self._trades_cache.extend(new_trades)
            
            # Save
            self._save_trades()
            self._last_sync = datetime.now()
            self._save_sync_status()
            
            # Calculate stats
            options_trades = [t for t in self._trades_cache if t.is_option]
            winning = [t for t in options_trades if t.realized_pnl > 0]
            losing = [t for t in options_trades if t.realized_pnl < 0]
            total_pnl = sum(t.realized_pnl for t in options_trades)
            
            return {
                'success': True,
                'total_trades': len(self._trades_cache),
                'new_trades': len(new_trades),
                'options_trades': len(options_trades),
                'winning_trades': len(winning),
                'losing_trades': len(losing),
                'win_rate': len(winning) / len(options_trades) if options_trades else 0,
                'total_pnl': total_pnl,
                'last_sync': self._last_sync.isoformat() if self._last_sync else None
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_trades_for_ml(self) -> pd.DataFrame:
        """
        Get trades formatted for ML model training.
        
        Returns:
            DataFrame with features suitable for ML
        """
        
        options_trades = [t for t in self._trades_cache if t.is_option]
        
        if not options_trades:
            return pd.DataFrame()
        
        # Build DataFrame
        data = []
        for trade in options_trades:
            # Parse timestamp
            try:
                ts = datetime.fromisoformat(trade.created_at.replace('Z', '+00:00'))
                hour = ts.hour
                day_of_week = ts.weekday()
            except:
                hour = 0
                day_of_week = 0
            
            data.append({
                'id': trade.id,
                'symbol': trade.product_symbol,
                'option_type': trade.option_type,
                'strike': trade.strike,
                'expiry': trade.expiry,
                'side': trade.side,
                'size': trade.size,
                'price': trade.price,
                'realized_pnl': trade.realized_pnl,
                'commission': trade.commission,
                'fill_type': trade.fill_type,
                'role': trade.role,
                'created_at': trade.created_at,
                'hour': hour,
                'day_of_week': day_of_week,
                'is_win': 1 if trade.realized_pnl > 0 else 0
            })
        
        return pd.DataFrame(data)
    
    def get_sync_status(self) -> Dict:
        """Get current sync status"""
        
        options_trades = [t for t in self._trades_cache if t.is_option]
        
        return {
            'total_trades': len(self._trades_cache),
            'options_trades': len(options_trades),
            'last_sync': self._last_sync.isoformat() if self._last_sync else None,
            'api_configured': bool(self.api_key and self.api_secret)
        }
    
    def get_daily_summary(self, date: str = None) -> Dict:
        """
        Get trading summary for a specific date.
        
        Args:
            date: Date string YYYY-MM-DD (default: today)
            
        Returns:
            Summary with trades, PnL, win rate
        """
        
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # Filter trades for the date
        day_trades = []
        for trade in self._trades_cache:
            try:
                trade_date = trade.created_at[:10]
                if trade_date == date and trade.is_option:
                    day_trades.append(trade)
            except:
                pass
        
        if not day_trades:
            return {
                'date': date,
                'trades': 0,
                'pnl': 0.0,
                'win_rate': 0.0,
                'winners': 0,
                'losers': 0
            }
        
        winners = [t for t in day_trades if t.realized_pnl > 0]
        losers = [t for t in day_trades if t.realized_pnl < 0]
        total_pnl = sum(t.realized_pnl for t in day_trades)
        
        return {
            'date': date,
            'trades': len(day_trades),
            'pnl': round(total_pnl, 2),
            'win_rate': round(len(winners) / len(day_trades) * 100, 1) if day_trades else 0,
            'winners': len(winners),
            'losers': len(losers),
            'details': [t.to_dict() for t in day_trades[:20]]  # Last 20 trades
        }
    
    def get_paired_trades_for_ml(self) -> pd.DataFrame:
        """
        Pair buy/sell trades by symbol to calculate actual PnL.
        Returns trades suitable for ML training with calculated outcomes.
        """
        options_trades = [t for t in self._trades_cache if t.is_option]
        
        if not options_trades:
            return pd.DataFrame()
        
        # Group trades by symbol
        from collections import defaultdict
        trades_by_symbol = defaultdict(list)
        for t in options_trades:
            trades_by_symbol[t.product_symbol].append(t)
        
        # Calculate PnL for each symbol (short strangle style - sells are openings)
        paired_data = []
        for symbol, trades in trades_by_symbol.items():
            # Sort by time
            trades.sort(key=lambda x: x.created_at)
            
            # Calculate net position and PnL
            total_sell_value = sum(t.size * t.price for t in trades if t.side == 'sell')
            total_buy_value = sum(t.size * t.price for t in trades if t.side == 'buy')
            total_sell_qty = sum(t.size for t in trades if t.side == 'sell')
            total_buy_qty = sum(t.size for t in trades if t.side == 'buy')
            total_commission = sum(t.commission for t in trades)
            
            # Net PnL (for options selling strategy: sell high, buy low = profit)
            net_pnl = total_sell_value - total_buy_value - total_commission
            
            # Check if position is closed (sells == buys approximately)
            is_closed = abs(total_sell_qty - total_buy_qty) < 0.1 * max(total_sell_qty, total_buy_qty, 1)
            
            if total_sell_qty > 0:  # Only include symbols we traded
                first_trade = trades[0]
                try:
                    ts = datetime.fromisoformat(first_trade.created_at.replace('Z', '+00:00'))
                    hour = ts.hour
                    day_of_week = ts.weekday()
                except:
                    hour = 0
                    day_of_week = 0
                
                paired_data.append({
                    'symbol': symbol,
                    'option_type': first_trade.option_type,
                    'strike': first_trade.strike,
                    'expiry': first_trade.expiry,
                    'total_sell_qty': total_sell_qty,
                    'total_buy_qty': total_buy_qty,
                    'avg_sell_price': total_sell_value / total_sell_qty if total_sell_qty > 0 else 0,
                    'avg_buy_price': total_buy_value / total_buy_qty if total_buy_qty > 0 else 0,
                    'net_pnl': net_pnl,
                    'total_commission': total_commission,
                    'is_closed': is_closed,
                    'is_win': 1 if net_pnl > 0 else 0,
                    'hour': hour,
                    'day_of_week': day_of_week,
                    'num_trades': len(trades),
                    'is_call': 1 if first_trade.option_type == 'call' else 0,
                    'is_net_buyer': 1 if total_buy_qty > total_sell_qty else 0
                })
        
        return pd.DataFrame(paired_data)
    
    def _save_trades(self):
        """Save trades to file"""
        try:
            data = [t.to_dict() for t in self._trades_cache]
            with open(self.trades_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving trades: {e}")
    
    def _load_trades(self):
        """Load trades from file"""
        if self.trades_file.exists():
            try:
                with open(self.trades_file) as f:
                    data = json.load(f)
                self._trades_cache = [DeltaTrade(**t) for t in data]
                print(f"Loaded {len(self._trades_cache)} trades from {self.trades_file}")
            except Exception as e:
                print(f"Error loading trades from {self.trades_file}: {e}")
                self._trades_cache = []
        else:
            print(f"Trades file not found: {self.trades_file}")
        
        # Load sync status
        if self.sync_status_file.exists():
            try:
                with open(self.sync_status_file) as f:
                    status = json.load(f)
                if status.get('last_sync'):
                    self._last_sync = datetime.fromisoformat(status['last_sync'])
            except:
                pass
    
    def _save_sync_status(self):
        """Save sync status"""
        try:
            status = {
                'last_sync': self._last_sync.isoformat() if self._last_sync else None,
                'total_trades': len(self._trades_cache)
            }
            with open(self.sync_status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except:
            pass


# Singleton instance
delta_fetcher = DeltaExchangeFetcher()
