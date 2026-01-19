"""
Options Trade Logger

Captures all options trades with full market context for ML learning.
Saves to CSV with features needed for pattern recognition.

Created: January 14, 2026
"""

import os
import csv
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

# Data directory
DATA_DIR = Path(__file__).parent.parent / 'data'
TRADES_FILE = DATA_DIR / 'options_trades.csv'
MARKET_CONTEXT_FILE = DATA_DIR / 'market_context.csv'

# CSV columns for trades
TRADE_COLUMNS = [
    'timestamp',
    'trade_id',
    'symbol',
    'underlying',
    'option_type',  # Call/Put
    'strike',
    'expiry',
    'expiry_date',
    'days_to_expiry',
    'action',  # BUY/SELL
    'side',  # OPEN/CLOSE
    'quantity',
    'price',
    'total_value',
    # Market context at trade time
    'spot_price',
    'spot_change_1h',
    'spot_change_24h',
    'iv',
    'delta',
    'gamma',
    'theta',
    'vega',
    # Position context
    'position_size_before',
    'position_size_after',
    'position_pnl_at_trade',
    'avg_entry_before',
    # Market conditions
    'btc_price',
    'eth_price',
    'market_trend',  # bullish/bearish/neutral
    'volatility_regime',  # low/medium/high
    # Trade outcome (filled later)
    'outcome_pnl',
    'outcome_pnl_pct',
    'outcome_duration_hours',
    'outcome_max_profit',
    'outcome_max_loss',
    'outcome_status',  # open/closed/expired
    # Strategy tags
    'strategy_tag',
    'automation_rule',
    'user_notes',
]


class TradeLogger:
    """Singleton trade logger for options trades."""
    
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
        self._file_lock = threading.Lock()
        
        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Initialize CSV if not exists
        if not TRADES_FILE.exists():
            self._create_csv()
        
        # Trade ID counter
        self._trade_counter = self._get_last_trade_id()
        
        print(f"✅ TradeLogger initialized. Trades file: {TRADES_FILE}")
    
    def _create_csv(self):
        """Create CSV file with headers."""
        with open(TRADES_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=TRADE_COLUMNS)
            writer.writeheader()
    
    def _get_last_trade_id(self) -> int:
        """Get the last trade ID from the file."""
        try:
            df = pd.read_csv(TRADES_FILE)
            if len(df) > 0 and 'trade_id' in df.columns:
                last_id = df['trade_id'].str.extract(r'T(\d+)').astype(float).max()[0]
                return int(last_id) if not pd.isna(last_id) else 0
        except Exception:
            pass
        return 0
    
    def _generate_trade_id(self) -> str:
        """Generate unique trade ID."""
        self._trade_counter += 1
        return f"T{self._trade_counter:06d}"
    
    def _parse_symbol(self, symbol: str) -> dict:
        """Parse option symbol into components."""
        # Format: C-BTC-95000-170126 or P-ETH-3500-170126
        try:
            parts = symbol.split('-')
            if len(parts) >= 4:
                option_type = 'Call' if parts[0] == 'C' else 'Put'
                underlying = parts[1]
                strike = int(parts[2])
                expiry_code = parts[3]
                
                # Parse expiry date
                day = int(expiry_code[:2])
                month = int(expiry_code[2:4])
                year = 2000 + int(expiry_code[4:6])
                expiry_date = datetime(year, month, day, 8, 30, 0)
                
                days_to_expiry = (expiry_date - datetime.now()).total_seconds() / 86400
                
                return {
                    'option_type': option_type,
                    'underlying': underlying,
                    'strike': strike,
                    'expiry': expiry_code,
                    'expiry_date': expiry_date.isoformat(),
                    'days_to_expiry': round(days_to_expiry, 2),
                }
        except Exception as e:
            print(f"Error parsing symbol {symbol}: {e}")
        
        return {
            'option_type': 'Unknown',
            'underlying': 'Unknown',
            'strike': 0,
            'expiry': '',
            'expiry_date': '',
            'days_to_expiry': 0,
        }
    
    def _determine_market_trend(self, spot_change_24h: float) -> str:
        """Determine market trend from 24h change."""
        if spot_change_24h > 2:
            return 'bullish'
        elif spot_change_24h < -2:
            return 'bearish'
        return 'neutral'
    
    def _determine_volatility_regime(self, iv: float) -> str:
        """Determine volatility regime from IV."""
        if iv < 40:
            return 'low'
        elif iv > 70:
            return 'high'
        return 'medium'
    
    def log_trade(
        self,
        symbol: str,
        action: str,  # BUY/SELL
        quantity: int,
        price: float,
        side: str = 'OPEN',  # OPEN/CLOSE
        position_before: dict = None,
        market_data: dict = None,
        greeks: dict = None,
        strategy_tag: str = '',
        automation_rule: str = '',
        user_notes: str = '',
    ) -> str:
        """
        Log an options trade with full context.
        
        Returns: trade_id
        """
        trade_id = self._generate_trade_id()
        timestamp = datetime.now().isoformat()
        
        # Parse symbol
        parsed = self._parse_symbol(symbol)
        
        # Market data defaults
        market_data = market_data or {}
        greeks = greeks or {}
        position_before = position_before or {}
        
        spot_price = market_data.get('spot_price', 0)
        spot_change_1h = market_data.get('spot_change_1h', 0)
        spot_change_24h = market_data.get('spot_change_24h', 0)
        btc_price = market_data.get('btc_price', 0)
        eth_price = market_data.get('eth_price', 0)
        
        # Calculate position after
        pos_size_before = position_before.get('size', 0)
        if action == 'BUY':
            pos_size_after = pos_size_before + quantity
        else:  # SELL
            pos_size_after = pos_size_before - quantity
        
        trade_record = {
            'timestamp': timestamp,
            'trade_id': trade_id,
            'symbol': symbol,
            'underlying': parsed['underlying'],
            'option_type': parsed['option_type'],
            'strike': parsed['strike'],
            'expiry': parsed['expiry'],
            'expiry_date': parsed['expiry_date'],
            'days_to_expiry': parsed['days_to_expiry'],
            'action': action,
            'side': side,
            'quantity': quantity,
            'price': price,
            'total_value': round(quantity * price, 4),
            # Market context
            'spot_price': spot_price,
            'spot_change_1h': spot_change_1h,
            'spot_change_24h': spot_change_24h,
            'iv': greeks.get('iv', 0),
            'delta': greeks.get('delta', 0),
            'gamma': greeks.get('gamma', 0),
            'theta': greeks.get('theta', 0),
            'vega': greeks.get('vega', 0),
            # Position context
            'position_size_before': pos_size_before,
            'position_size_after': pos_size_after,
            'position_pnl_at_trade': position_before.get('unrealized_pnl', 0),
            'avg_entry_before': position_before.get('entry_price', 0),
            # Market conditions
            'btc_price': btc_price,
            'eth_price': eth_price,
            'market_trend': self._determine_market_trend(spot_change_24h),
            'volatility_regime': self._determine_volatility_regime(greeks.get('iv', 50)),
            # Outcomes (to be filled later)
            'outcome_pnl': '',
            'outcome_pnl_pct': '',
            'outcome_duration_hours': '',
            'outcome_max_profit': '',
            'outcome_max_loss': '',
            'outcome_status': 'open',
            # Strategy
            'strategy_tag': strategy_tag,
            'automation_rule': automation_rule,
            'user_notes': user_notes,
        }
        
        # Write to CSV
        with self._file_lock:
            with open(TRADES_FILE, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=TRADE_COLUMNS)
                writer.writerow(trade_record)
        
        print(f"📝 Logged trade {trade_id}: {action} {quantity}x {symbol} @ ${price}")
        return trade_id
    
    def update_trade_outcome(
        self,
        trade_id: str,
        pnl: float,
        pnl_pct: float,
        duration_hours: float,
        max_profit: float,
        max_loss: float,
        status: str = 'closed',
    ):
        """Update trade outcome when position is closed."""
        try:
            with self._file_lock:
                df = pd.read_csv(TRADES_FILE)
                
                mask = df['trade_id'] == trade_id
                if mask.any():
                    df.loc[mask, 'outcome_pnl'] = pnl
                    df.loc[mask, 'outcome_pnl_pct'] = pnl_pct
                    df.loc[mask, 'outcome_duration_hours'] = duration_hours
                    df.loc[mask, 'outcome_max_profit'] = max_profit
                    df.loc[mask, 'outcome_max_loss'] = max_loss
                    df.loc[mask, 'outcome_status'] = status
                    
                    df.to_csv(TRADES_FILE, index=False)
                    print(f"✅ Updated outcome for trade {trade_id}: PnL ${pnl:.2f} ({pnl_pct:.1f}%)")
        except Exception as e:
            print(f"❌ Error updating trade outcome: {e}")
    
    def get_all_trades(self) -> pd.DataFrame:
        """Get all trades as DataFrame."""
        try:
            return pd.read_csv(TRADES_FILE)
        except Exception:
            return pd.DataFrame(columns=TRADE_COLUMNS)
    
    def get_recent_trades(self, days: int = 7) -> pd.DataFrame:
        """Get trades from last N days."""
        df = self.get_all_trades()
        if len(df) == 0:
            return df
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        cutoff = datetime.now() - timedelta(days=days)
        return df[df['timestamp'] >= cutoff]
    
    def get_trades_by_symbol(self, symbol: str) -> pd.DataFrame:
        """Get all trades for a specific symbol."""
        df = self.get_all_trades()
        return df[df['symbol'] == symbol]
    
    def get_trade_statistics(self) -> dict:
        """Get overall trade statistics."""
        df = self.get_all_trades()
        
        if len(df) == 0:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'avg_pnl': 0,
                'total_pnl': 0,
                'avg_duration_hours': 0,
            }
        
        # BUG FIX (Jan 14, 2026 - v2): Show trade count AND unrealized PnL
        # When all trades are open, show current unrealized PnL from positions
        
        # Only consider closed trades with outcomes for PnL calculations
        closed = df[df['outcome_status'] == 'closed'].copy()
        
        if len(closed) == 0:
            # No closed trades yet - calculate unrealized PnL from open positions
            open_trades = df[df['outcome_status'] == 'open'].copy()
            
            # Use position_pnl_at_trade as proxy for current unrealized PnL
            # This is updated when user refreshes positions
            open_pnl = pd.to_numeric(open_trades['position_pnl_at_trade'], errors='coerce').fillna(0).sum()
            
            return {
                'total_trades': len(df),  # ✅ Show total trades even if none closed
                'closed_trades': 0,
                'open_trades': len(df),
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,  # Can't calculate win rate without closed trades
                'avg_pnl': 0,
                'total_pnl': float(open_pnl),  # ✅ Show unrealized PnL for open trades
                'unrealized': True,  # Flag that this is unrealized PnL
            }
        
        # Convert outcome columns to numeric, handling empty strings
        closed['outcome_pnl'] = pd.to_numeric(closed['outcome_pnl'], errors='coerce').fillna(0)
        
        winning = closed[closed['outcome_pnl'] > 0]
        losing = closed[closed['outcome_pnl'] < 0]
        
        return {
            'total_trades': len(df),  # ✅ Total trades including open
            'closed_trades': len(closed),  # ✅ Only closed trades
            'open_trades': len(df) - len(closed),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': len(winning) / len(closed) * 100 if len(closed) > 0 else 0,
            'avg_pnl': float(closed['outcome_pnl'].mean()),
            'total_pnl': float(closed['outcome_pnl'].sum()),
            'avg_duration_hours': float(pd.to_numeric(closed['outcome_duration_hours'], errors='coerce').mean()) if len(closed) > 0 else 0,
        }
    
    def export_for_ml(self, output_file: str = None) -> str:
        """Export trades in ML-ready format."""
        if output_file is None:
            output_file = str(DATA_DIR / 'ml_trades_export.csv')
        
        df = self.get_all_trades()
        
        # Add derived features for ML
        if len(df) > 0:
            df['hour_of_day'] = pd.to_datetime(df['timestamp']).dt.hour
            df['day_of_week'] = pd.to_datetime(df['timestamp']).dt.dayofweek
            df['is_call'] = (df['option_type'] == 'Call').astype(int)
            df['is_buy'] = (df['action'] == 'BUY').astype(int)
            df['moneyness'] = df.apply(
                lambda r: (r['spot_price'] - r['strike']) / r['strike'] if r['strike'] > 0 else 0,
                axis=1
            )
        
        df.to_csv(output_file, index=False)
        return output_file
    
    def reconcile_trades(self) -> dict:
        """
        Reconcile open SELL/BUY trades to calculate realized PnL.
        Matches trades by symbol and calculates outcomes.
        Returns summary of reconciliation.
        """
        df = self.get_all_trades()
        
        if len(df) == 0:
            return {'success': False, 'message': 'No trades to reconcile'}
        
        updated_count = 0
        
        # Group by symbol
        for symbol in df['symbol'].unique():
            symbol_trades = df[df['symbol'] == symbol].copy()
            symbol_trades['timestamp'] = pd.to_datetime(symbol_trades['timestamp'])
            symbol_trades = symbol_trades.sort_values('timestamp')
            
            # Match SELL OPEN with BUY CLOSE
            sells = symbol_trades[symbol_trades['action'] == 'SELL'].copy()
            buys = symbol_trades[symbol_trades['action'] == 'BUY'].copy()
            
            for idx, sell in sells.iterrows():
                # Find corresponding buy (after sell timestamp)
                matching_buys = buys[buys['timestamp'] > sell['timestamp']]
                
                if len(matching_buys) > 0:
                    buy = matching_buys.iloc[0]
                    
                    # Calculate PnL (SELL price - BUY price) * quantity
                    qty = min(abs(sell['quantity']), abs(buy['quantity']))
                    pnl = (sell['price'] - buy['price']) * qty
                    pnl_pct = (pnl / (sell['price'] * qty)) * 100 if sell['price'] > 0 else 0
                    
                    # Calculate duration
                    duration = (buy['timestamp'] - sell['timestamp']).total_seconds() / 3600
                    
                    # FIX: Only assign PnL to SELL trade to avoid double-counting
                    # Update sell trade outcome (opening trade gets the PnL)
                    df.loc[df['trade_id'] == sell['trade_id'], 'outcome_pnl'] = pnl
                    df.loc[df['trade_id'] == sell['trade_id'], 'outcome_pnl_pct'] = pnl_pct
                    df.loc[df['trade_id'] == sell['trade_id'], 'outcome_duration_hours'] = duration
                    df.loc[df['trade_id'] == sell['trade_id'], 'outcome_status'] = 'closed'
                    
                    # Update buy trade outcome (closing trade gets 0 to avoid double-count)
                    df.loc[df['trade_id'] == buy['trade_id'], 'outcome_pnl'] = 0
                    df.loc[df['trade_id'] == buy['trade_id'], 'outcome_pnl_pct'] = 0
                    df.loc[df['trade_id'] == buy['trade_id'], 'outcome_duration_hours'] = duration
                    df.loc[df['trade_id'] == buy['trade_id'], 'outcome_status'] = 'paired'  # Mark as paired
                    
                    updated_count += 2
        
        # Save reconciled trades
        if updated_count > 0:
            df.to_csv(TRADES_FILE, index=False)
        
        return {
            'success': True,
            'updated_count': updated_count,
            'message': f'Reconciled {updated_count} trades'
        }


# Singleton instance
trade_logger = TradeLogger()
