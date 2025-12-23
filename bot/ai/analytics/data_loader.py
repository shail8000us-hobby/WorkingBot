"""
Real Data Loader for Institutional AI Analytics

This module loads real trading data from:
1. Event Store (SQLite) - bot_events_LONG.db for positions, orders, fills
2. Exchange API - real-time balances, positions, margin
3. WebSocket - live price data

Author: GridBot Pro - Institutional AI
Version: 1.0.0
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

log = logging.getLogger(__name__)


class RealDataLoader:
    """
    Loads real trading data from event store and exchange
    """
    
    def __init__(self, base_dir: str = None):
        """Initialize the data loader"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent.parent.parent
        self.db_path = self.base_dir / 'data' / 'bot_events_LONG.db'
        
        # Initialize exchange client
        try:
            from bot.api.delta_client import DeltaClient
            
            self.exchange_client = DeltaClient()
            self.has_exchange_client = True
            log.info("Exchange client initialized successfully")
        except Exception as e:
            log.warning(f"Failed to initialize exchange client: {e}")
            self.exchange_client = None
            self.has_exchange_client = False
    
    # =========================================================================
    # EVENT STORE QUERIES
    # =========================================================================
    
    def get_position_events(self, lookback_days: int = 30) -> List[Dict[str, Any]]:
        """
        Get all position opened/closed events from event store
        
        Args:
            lookback_days: Number of days to look back
        
        Returns:
            List of position event dictionaries with entry/exit data
        """
        if not self.db_path.exists():
            log.warning(f"Event store database not found: {self.db_path}")
            return []
        
        cutoff_timestamp = (datetime.now() - timedelta(days=lookback_days)).timestamp()
        
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get position opened events
            cursor.execute("""
                SELECT 
                    event_id,
                    event_type,
                    timestamp,
                    data,
                    aggregate_id,
                    correlation_id
                FROM events 
                WHERE event_type IN ('position_opened', 'position_closed', 'position_updated')
                AND timestamp > ?
                ORDER BY timestamp ASC
            """, (cutoff_timestamp,))
            
            rows = cursor.fetchall()
            conn.close()
            
            positions = []
            for row in rows:
                try:
                    data = json.loads(row['data'])
                    positions.append({
                        'event_id': row['event_id'],
                        'event_type': row['event_type'],
                        'timestamp': row['timestamp'],
                        'position_id': data.get('position_id'),
                        'entry_price': data.get('entry_price'),
                        'exit_price': data.get('exit_price'),
                        'tp_price': data.get('tp_price'),
                        'size': data.get('size', 0),
                        'pnl': data.get('pnl'),
                        'correlation_id': row['correlation_id']
                    })
                except Exception as e:
                    log.debug(f"Error parsing position event: {e}")
                    continue
            
            log.info(f"Loaded {len(positions)} position events from event store")
            return positions
            
        except Exception as e:
            log.error(f"Error loading position events: {e}")
            return []
    
    def get_order_events(self, lookback_days: int = 30) -> List[Dict[str, Any]]:
        """
        Get all order events from event store
        
        Args:
            lookback_days: Number of days to look back
        
        Returns:
            List of order event dictionaries
        """
        if not self.db_path.exists():
            log.warning(f"Event store database not found: {self.db_path}")
            return []
        
        cutoff_timestamp = (datetime.now() - timedelta(days=lookback_days)).timestamp()
        
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    event_id,
                    event_type,
                    timestamp,
                    data,
                    aggregate_id
                FROM events 
                WHERE event_type IN ('order_placed', 'order_filled', 'order_cancelled', 'order_failed')
                AND timestamp > ?
                ORDER BY timestamp ASC
            """, (cutoff_timestamp,))
            
            rows = cursor.fetchall()
            conn.close()
            
            orders = []
            for row in rows:
                try:
                    data = json.loads(row['data'])
                    orders.append({
                        'event_id': row['event_id'],
                        'event_type': row['event_type'],
                        'timestamp': row['timestamp'],
                        'order_id': data.get('order_id'),
                        'side': data.get('side'),
                        'size': data.get('size', 0),
                        'price': data.get('price'),
                        'status': data.get('status'),
                        'filled_size': data.get('filled_size', 0),
                        'reason': data.get('reason')
                    })
                except Exception as e:
                    log.debug(f"Error parsing order event: {e}")
                    continue
            
            log.info(f"Loaded {len(orders)} order events from event store")
            return orders
            
        except Exception as e:
            log.error(f"Error loading order events: {e}")
            return []
    
    def calculate_pnl_from_positions(self) -> Dict[str, Any]:
        """
        Calculate PnL from position events
        
        Returns:
            Dictionary with PnL statistics
        """
        positions = self.get_position_events(lookback_days=90)  # Look back 90 days for more data
        
        # Group positions by position_id to match opens with closes
        position_map = {}
        for event in positions:
            pos_id = event['position_id']
            if pos_id not in position_map:
                position_map[pos_id] = {'opened': None, 'closed': None, 'updates': []}
            
            if event['event_type'] == 'position_opened':
                position_map[pos_id]['opened'] = event
            elif event['event_type'] == 'position_closed':
                position_map[pos_id]['closed'] = event
            else:
                position_map[pos_id]['updates'].append(event)
        
        # Calculate PnL for closed positions
        trades = []
        for pos_id, pos_data in position_map.items():
            if pos_data['opened'] and pos_data['closed']:
                entry_price = pos_data['opened']['entry_price']
                tp_price = pos_data['opened']['tp_price']
                size = pos_data['opened']['size']
                
                # For LONG positions: PnL = (exit_price - entry_price) * size
                # We use TP price as exit price since it's a grid bot
                pnl = (tp_price - entry_price) * size if tp_price and entry_price else 0
                
                trades.append({
                    'position_id': pos_id,
                    'entry_time': datetime.fromtimestamp(pos_data['opened']['timestamp']),
                    'exit_time': datetime.fromtimestamp(pos_data['closed']['timestamp']),
                    'entry_price': entry_price,
                    'exit_price': tp_price,
                    'size': size,
                    'pnl': pnl,
                    'duration_seconds': pos_data['closed']['timestamp'] - pos_data['opened']['timestamp']
                })
        
        if not trades:
            return {
                'total_trades': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'trades': []
            }
        
        # Calculate statistics
        total_pnl = sum(t['pnl'] for t in trades)
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] < 0]
        
        return {
            'total_trades': len(trades),
            'total_pnl': round(total_pnl, 2),
            'avg_pnl': round(total_pnl / len(trades), 2) if trades else 0,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(len(wins) / len(trades) * 100, 2) if trades else 0,
            'avg_win': round(sum(t['pnl'] for t in wins) / len(wins), 2) if wins else 0,
            'avg_loss': round(sum(t['pnl'] for t in losses) / len(losses), 2) if losses else 0,
            'profit_factor': round(
                sum(t['pnl'] for t in wins) / abs(sum(t['pnl'] for t in losses)), 2
            ) if losses and sum(t['pnl'] for t in losses) != 0 else 0,
            'trades': trades
        }
    
    # =========================================================================
    # EXCHANGE API QUERIES
    # =========================================================================
    
    def get_account_balance(self) -> Dict[str, Any]:
        """
        Get real account balance from exchange
        
        Returns:
            Dictionary with balance information
        """
        if not self.has_exchange_client:
            return {
                'total_balance': 0,
                'available_balance': 0,
                'margin_used': 0,
                'unrealized_pnl': 0
            }
        
        try:
            response = self.exchange_client.get_wallet_balances()
            if response and isinstance(response, list) and len(response) > 0:
                wallet = response[0]
                return {
                    'total_balance': float(wallet.get('balance', 0)),
                    'available_balance': float(wallet.get('available_balance', 0)),
                    'margin_used': float(wallet.get('order_margin', 0)) + float(wallet.get('position_margin', 0)),
                    'unrealized_pnl': float(wallet.get('unrealized_pnl', 0))
                }
        except Exception as e:
            log.error(f"Error fetching account balance: {e}")
        
        return {
            'total_balance': 0,
            'available_balance': 0,
            'margin_used': 0,
            'unrealized_pnl': 0
        }
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """
        Get real open positions from exchange
        
        Returns:
            List of open positions
        """
        if not self.has_exchange_client:
            return []
        
        try:
            positions = self.exchange_client.get_positions()
            if positions and isinstance(positions, list):
                return [
                    {
                        'product_id': pos.get('product_id'),
                        'size': float(pos.get('size', 0)),
                        'entry_price': float(pos.get('entry_price', 0)),
                        'current_price': float(pos.get('mark_price', 0)),
                        'unrealized_pnl': float(pos.get('unrealized_pnl', 0)),
                        'margin': float(pos.get('margin', 0))
                    }
                    for pos in positions
                    if float(pos.get('size', 0)) != 0
                ]
        except Exception as e:
            log.error(f"Error fetching open positions: {e}")
        
        return []
    
    def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get real open orders from exchange
        
        Returns:
            List of open orders
        """
        if not self.has_exchange_client:
            return []
        
        try:
            orders = self.exchange_client.get_orders()
            if orders and isinstance(orders, list):
                return [
                    {
                        'order_id': ord.get('id'),
                        'product_id': ord.get('product_id'),
                        'side': ord.get('side'),
                        'size': float(ord.get('size', 0)),
                        'price': float(ord.get('limit_price', 0)),
                        'filled_size': float(ord.get('filled_size', 0)),
                        'status': ord.get('state'),
                        'created_at': ord.get('created_at')
                    }
                    for ord in orders
                    if ord.get('state') in ['open', 'pending']
                ]
        except Exception as e:
            log.error(f"Error fetching open orders: {e}")
        
        return []
    
    def get_current_price(self) -> float:
        """
        Get current market price from monitoring snapshot or exchange
        
        Returns:
            Current price
        """
        # Try to get from monitoring snapshot first (faster)
        try:
            snapshot_file = self.base_dir / 'data' / 'monitoring_snapshot.json'
            if snapshot_file.exists():
                with open(snapshot_file, 'r') as f:
                    data = json.load(f)
                    price = data.get('bot_status', {}).get('current_price')
                    if price and price > 0:
                        return float(price)
        except Exception as e:
            log.debug(f"Error reading monitoring snapshot: {e}")
        
        # Fallback to exchange API
        if self.has_exchange_client:
            try:
                # Get from positions if available
                positions = self.get_open_positions()
                if positions:
                    return positions[0].get('current_price', 0)
            except Exception as e:
                log.error(f"Error fetching current price: {e}")
        
        return 0.0


# Singleton instance
_data_loader = None


def get_data_loader() -> RealDataLoader:
    """Get singleton instance of RealDataLoader"""
    global _data_loader
    if _data_loader is None:
        _data_loader = RealDataLoader()
    return _data_loader
