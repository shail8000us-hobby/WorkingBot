"""
Bot State Reader - Read bot state from SQL Event Store

Reads current bot state from SQLite event store database instead of JSON files.
This works even when bot is started independently of WebUI.

Author: AI Assistant
Date: November 16, 2025
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent.parent


class BotStateReader:
    """
    Read bot state from SQL event store database
    
    Reconstructs current state by reading latest events:
    - pending_buy_set/cleared
    - pending_sell_set/cleared  
    - position_opened/closed
    - order_placed/filled/cancelled
    """
    
    def __init__(self, mode: str = "LONG"):
        """
        Initialize state reader
        
        Args:
            mode: Trading mode (LONG/SHORT) to determine database file
        """
        self.mode = mode
        self.db_path = BASE_DIR / f"bot_events_{mode}.db"
        
        if not self.db_path.exists():
            log.warning(f"Database not found: {self.db_path}")
            self.db_path = None
    
    def _get_connection(self) -> Optional[sqlite3.Connection]:
        """Get database connection"""
        if not self.db_path:
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Access columns by name
            return conn
        except Exception as e:
            log.error(f"Failed to connect to database: {e}")
            return None
    
    def get_current_pending_buy(self) -> Optional[Dict[str, Any]]:
        """
        Get current pending BUY order from latest events
        
        Returns:
            Pending buy order dict or None if cleared/doesn't exist
        """
        conn = self._get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            
            # Get latest pending_buy event (either set or cleared)
            cursor.execute("""
                SELECT event_type, data, timestamp
                FROM events
                WHERE event_type IN ('pending_buy_set', 'pending_buy_cleared')
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if not row:
                return None
            
            event_type = row['event_type']
            
            # If latest event is cleared, no pending order exists
            if event_type == 'pending_buy_cleared':
                return None
            
            # Parse the set event
            data = json.loads(row['data'])
            return {
                'order_id': data.get('order_id'),
                'price': data.get('price'),
                'size': data.get('size'),
                'timestamp': data.get('timestamp')
            }
            
        except Exception as e:
            log.error(f"Failed to get pending buy: {e}")
            return None
        finally:
            conn.close()
    
    def get_current_pending_sell(self) -> Optional[Dict[str, Any]]:
        """
        Get current pending SELL order from latest events
        
        Returns:
            Pending sell order dict or None if cleared/doesn't exist
        """
        conn = self._get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            
            # Get latest pending_sell event (either set or cleared)
            cursor.execute("""
                SELECT event_type, data, timestamp
                FROM events
                WHERE event_type IN ('pending_sell_set', 'pending_sell_cleared')
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if not row:
                return None
            
            event_type = row['event_type']
            
            # If latest event is cleared, no pending order exists
            if event_type == 'pending_sell_cleared':
                return None
            
            # Parse the set event
            data = json.loads(row['data'])
            return {
                'order_id': data.get('order_id'),
                'price': data.get('price'),
                'size': data.get('size'),
                'timestamp': data.get('timestamp')
            }
            
        except Exception as e:
            log.error(f"Failed to get pending sell: {e}")
            return None
        finally:
            conn.close()
    
    def get_open_positions(self, current_price: Optional[float] = None, grid_lower: Optional[float] = None, grid_upper: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Get current open positions by reconstructing from events
        
        Args:
            current_price: Optional current price to filter out positions that should have closed
            grid_lower: Optional grid lower bound to filter out-of-bounds positions
            grid_upper: Optional grid upper bound to filter out-of-bounds positions
        
        Returns:
            List of open position dicts
        """
        conn = self._get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            # Get all position events ordered by time
            cursor.execute("""
                SELECT event_type, data, timestamp
                FROM events
                WHERE event_type IN ('position_opened', 'position_closed')
                ORDER BY timestamp ASC
            """)
            
            rows = cursor.fetchall()
            
            # Reconstruct current positions
            positions = {}  # position_id -> position_data
            
            for row in rows:
                event_type = row['event_type']
                data = json.loads(row['data'])
                
                if event_type == 'position_opened':
                    position_id = data.get('position_id')
                    positions[position_id] = {
                        'position_id': position_id,
                        'entry_price': data.get('entry_price'),
                        'tp_price': data.get('tp_price'),
                        'size': data.get('size'),
                        'opened_at': data.get('timestamp')
                    }
                
                elif event_type == 'position_closed':
                    position_id = data.get('position_id')
                    if position_id in positions:
                        del positions[position_id]
            
            # CRITICAL FIX: Filter out positions where TP should have filled
            # This handles cases where position_closed events are missing
            valid_positions = []
            for pos in positions.values():
                entry = pos.get('entry_price')
                tp = pos.get('tp_price')
                
                # Filter by grid bounds if provided
                if grid_lower is not None and grid_upper is not None:
                    if entry < grid_lower:
                        log.warning(f"Filtering below-bounds position: entry ${entry:,.0f} (lower bound: ${grid_lower:,.0f})")
                        continue
                    # Allow positions at upper bound, but filter if significantly above
                    if entry > grid_upper + (grid_upper - grid_lower) * 0.05:  # 5% tolerance
                        log.warning(f"Filtering above-bounds position: entry ${entry:,.0f} (upper bound: ${grid_upper:,.0f})")
                        continue
                
                # CRITICAL: In LONG mode, positions should be BELOW current price
                # In SHORT mode, positions should be ABOVE current price
                if current_price:
                    if self.mode == 'LONG' and entry > current_price:
                        log.warning(f"Filtering invalid LONG position: entry ${entry:,.0f} above current price ${current_price:,.0f}")
                        continue
                    elif self.mode == 'SHORT' and entry < current_price:
                        log.warning(f"Filtering invalid SHORT position: entry ${entry:,.0f} below current price ${current_price:,.0f}")
                        continue
                
                # Filter by TP status
                if current_price and tp:
                    # LONG mode: position closes when price >= TP
                    # SHORT mode: position closes when price <= TP
                    if self.mode == 'LONG' and current_price >= tp:
                        log.warning(f"Filtering stale position: entry ${entry:,.0f}, TP ${tp:,.0f} (price={current_price})")
                        continue  # Skip this position - it should have closed
                    elif self.mode == 'SHORT' and current_price <= tp:
                        log.warning(f"Filtering stale position: entry ${entry:,.0f}, TP ${tp:,.0f} (price={current_price})")
                        continue
                
                valid_positions.append(pos)
            
            return valid_positions
            
        except Exception as e:
            log.error(f"Failed to get open positions: {e}")
            return []
        finally:
            conn.close()
    
    def get_bot_state(self, current_price: Optional[float] = None, grid_lower: Optional[float] = None, grid_upper: Optional[float] = None) -> Dict[str, Any]:
        """
        Get complete bot state from database
        
        Args:
            current_price: Optional current price to filter stale positions
            grid_lower: Optional grid lower bound
            grid_upper: Optional grid upper bound
        
        Returns:
            Dict with pending orders and positions
        """
        return {
            'pending_buy': self.get_current_pending_buy(),
            'pending_sell': self.get_current_pending_sell(),
            'positions': self.get_open_positions(current_price=current_price, grid_lower=grid_lower, grid_upper=grid_upper),
            'timestamp': datetime.now().isoformat()
        }
    
    def is_available(self) -> bool:
        """Check if database is available"""
        return self.db_path is not None and self.db_path.exists()


def get_bot_state_from_db(mode: str = "LONG", current_price: Optional[float] = None, grid_lower: Optional[float] = None, grid_upper: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """
    Convenience function to get bot state from database
    
    Args:
        mode: Trading mode (LONG/SHORT)
        current_price: Optional current price to filter stale positions
        grid_lower: Optional grid lower bound
        grid_upper: Optional grid upper bound
        
    Returns:
        Bot state dict or None if database unavailable
    """
    reader = BotStateReader(mode=mode)
    if not reader.is_available():
        return None
    
    return reader.get_bot_state(current_price=current_price, grid_lower=grid_lower, grid_upper=grid_upper)
