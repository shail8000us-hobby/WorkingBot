"""
Position Synchronization System for Delta Exchange
Ensures bot position tracking matches exchange reality
Works on both testnet and live trading environments
"""

import time
import logging
import threading
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

log = logging.getLogger(__name__)

@dataclass
class Position:
    """Position information"""
    symbol: str
    size: float  # Positive for long, negative for short
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    last_updated: datetime

class PositionSynchronizer:
    """
    Position synchronization system for Delta Exchange
    Keeps bot position tracking in sync with exchange
    """
    
    def __init__(self, delta_client, sync_interval: float = 30.0):
        """
        Initialize position synchronizer
        
        Args:
            delta_client: Delta Exchange client instance
            sync_interval: Sync interval in seconds (default: 30s)
        """
        self.delta_client = delta_client
        self.sync_interval = sync_interval
        self.running = False
        self.sync_thread = None
        self.positions: Dict[str, Position] = {}
        self.lock = threading.RLock()
        
        # File paths for persistence (using project root)
        self.base_dir = PROJECT_ROOT
        self.positions_file = self.base_dir / 'bot' / 'state' / 'positions.json'
        self.state_file = self.base_dir / 'bot' / 'state' / 'state.json'
        
        # Ensure directories exist
        self.positions_file.parent.mkdir(parents=True, exist_ok=True)
        
        log.info(f"✅ Position Synchronizer initialized (interval: {sync_interval}s)")
    
    def start_sync(self):
        """Start the synchronization thread"""
        if self.running:
            log.warning("Position synchronization already running")
            return
        
        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        log.info("🔄 Position synchronization started")
    
    def stop_sync(self):
        """Stop the synchronization thread"""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=2)
        log.info("⏹️ Position synchronization stopped")
    
    def _sync_loop(self):
        """Main synchronization loop"""
        while self.running:
            try:
                self.sync_positions()
                time.sleep(self.sync_interval)
            except Exception as e:
                log.error(f"Error in position synchronization: {e}")
                time.sleep(self.sync_interval)
    
    def sync_positions(self):
        """Synchronize positions with exchange"""
        try:
            log.debug("🔄 Starting position synchronization...")
            
            # Get positions from exchange
            exchange_positions = self._get_exchange_positions()
            
            # Get current bot positions
            bot_positions = self._get_bot_positions()
            
            # Compare and sync
            self._compare_and_sync(exchange_positions, bot_positions)
            
            # Save updated positions
            self._save_positions()
            
            log.debug("✅ Position synchronization completed")
            
        except Exception as e:
            log.error(f"Error synchronizing positions: {e}")
    
    def _get_exchange_positions(self) -> Dict[str, Position]:
        """Get current positions from exchange"""
        try:
            if hasattr(self.delta_client, 'fetch_positions'):
                positions_data = self.delta_client.fetch_positions()
            else:
                # Fallback to direct API call
                positions_data = self._fetch_positions_via_api()
            
            positions = {}
            for pos_data in positions_data:
                symbol = pos_data.get('symbol', '')
                if symbol and float(pos_data.get('size', 0)) != 0:
                    position = Position(
                        symbol=symbol,
                        size=float(pos_data.get('size', 0)),
                        entry_price=float(pos_data.get('entry_price', 0)),
                        current_price=float(pos_data.get('mark_price', 0)),
                        unrealized_pnl=float(pos_data.get('unrealized_pnl', 0)),
                        realized_pnl=float(pos_data.get('realized_pnl', 0)),
                        last_updated=datetime.now(timezone.utc)
                    )
                    positions[symbol] = position
            
            log.debug(f"📊 Retrieved {len(positions)} positions from exchange")
            return positions
            
        except Exception as e:
            log.error(f"Error getting exchange positions: {e}")
            return {}
    
    def _fetch_positions_via_api(self) -> List[Dict]:
        """Fetch positions via direct API call (fallback)"""
        try:
            # This would need proper authentication
            # For now, return empty list
            log.warning("Direct API fallback for positions not implemented yet")
            return []
        except Exception as e:
            log.error(f"Error in positions API fallback: {e}")
            return []
    
    def _get_bot_positions(self) -> Dict[str, Position]:
        """Get current bot positions from file"""
        try:
            if not self.positions_file.exists():
                return {}
            
            with open(self.positions_file, 'r') as f:
                data = json.load(f)
            
            positions = {}
            for symbol, pos_data in data.items():
                if isinstance(pos_data, dict) and float(pos_data.get('size', 0)) != 0:
                    position = Position(
                        symbol=symbol,
                        size=float(pos_data.get('size', 0)),
                        entry_price=float(pos_data.get('entry_price', 0)),
                        current_price=float(pos_data.get('current_price', 0)),
                        unrealized_pnl=float(pos_data.get('unrealized_pnl', 0)),
                        realized_pnl=float(pos_data.get('realized_pnl', 0)),
                        last_updated=datetime.fromisoformat(pos_data.get('last_updated', datetime.now(timezone.utc).isoformat()))
                    )
                    positions[symbol] = position
            
            return positions
            
        except Exception as e:
            log.error(f"Error reading bot positions: {e}")
            return {}
    
    def _compare_and_sync(self, exchange_positions: Dict[str, Position], bot_positions: Dict[str, Position]):
        """Compare exchange and bot positions and sync differences"""
        try:
            with self.lock:
                # Check for discrepancies
                discrepancies = []
                
                # Check all exchange positions
                for symbol, exchange_pos in exchange_positions.items():
                    bot_pos = bot_positions.get(symbol)
                    
                    if bot_pos is None:
                        # New position on exchange, not in bot
                        discrepancies.append(f"NEW: {symbol} {exchange_pos.size} @ {exchange_pos.entry_price}")
                        self.positions[symbol] = exchange_pos
                    else:
                        # Compare existing positions
                        if (abs(exchange_pos.size - bot_pos.size) > 0.001 or 
                            abs(exchange_pos.entry_price - bot_pos.entry_price) > 0.01):
                            discrepancies.append(f"DIFF: {symbol} - Exchange: {exchange_pos.size}@{exchange_pos.entry_price}, Bot: {bot_pos.size}@{bot_pos.entry_price}")
                            self.positions[symbol] = exchange_pos
                        else:
                            # Positions match, update with latest data
                            self.positions[symbol] = exchange_pos
                
                # Check for positions in bot but not on exchange
                for symbol, bot_pos in bot_positions.items():
                    if symbol not in exchange_positions and abs(bot_pos.size) > 0.001:
                        discrepancies.append(f"MISSING: {symbol} {bot_pos.size} @ {bot_pos.entry_price} (not on exchange)")
                        # Remove from bot positions
                        if symbol in self.positions:
                            del self.positions[symbol]
                
                # Log discrepancies
                if discrepancies:
                    log.warning("🚨 Position discrepancies detected:")
                    for disc in discrepancies:
                        log.warning(f"  - {disc}")
                else:
                    log.debug("✅ Positions in sync")
                
                # Update positions
                self.positions.update(exchange_positions)
                
        except Exception as e:
            log.error(f"Error comparing positions: {e}")
    
    def _save_positions(self):
        """Save positions to file"""
        try:
            with self.lock:
                positions_data = {}
                for symbol, position in self.positions.items():
                    positions_data[symbol] = {
                        'size': position.size,
                        'entry_price': position.entry_price,
                        'current_price': position.current_price,
                        'unrealized_pnl': position.unrealized_pnl,
                        'realized_pnl': position.realized_pnl,
                        'last_updated': position.last_updated.isoformat()
                    }
                
                with open(self.positions_file, 'w') as f:
                    json.dump(positions_data, f, indent=2)
                
                log.debug(f"💾 Saved {len(positions_data)} positions to file")
                
        except Exception as e:
            log.error(f"Error saving positions: {e}")
    
    def get_positions(self) -> Dict[str, Position]:
        """Get current positions"""
        with self.lock:
            return self.positions.copy()
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for specific symbol"""
        with self.lock:
            return self.positions.get(symbol)
    
    def force_sync(self):
        """Force immediate position synchronization"""
        log.info("🔄 Forcing position synchronization...")
        self.sync_positions()
    
    def get_stats(self) -> Dict:
        """Get synchronization statistics"""
        with self.lock:
            total_positions = len(self.positions)
            total_size = sum(abs(pos.size) for pos in self.positions.values())
            total_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
            
            return {
                'total_positions': total_positions,
                'total_size': total_size,
                'total_unrealized_pnl': total_pnl,
                'sync_interval': self.sync_interval,
                'running': self.running
            }


# Global synchronizer instance
_position_sync = None

def get_position_synchronizer(delta_client=None, sync_interval: float = 30.0) -> PositionSynchronizer:
    """Get or create global position synchronizer instance"""
    global _position_sync
    
    if _position_sync is None and delta_client is not None:
        _position_sync = PositionSynchronizer(delta_client, sync_interval)
        log.info("🌐 Global position synchronizer created")
    
    return _position_sync

def start_position_sync(delta_client, sync_interval: float = 30.0):
    """Start global position synchronization"""
    global _position_sync
    
    if _position_sync is None:
        _position_sync = PositionSynchronizer(delta_client, sync_interval)
    
    _position_sync.start_sync()
    return _position_sync

def stop_position_sync():
    """Stop global position synchronization"""
    global _position_sync
    
    if _position_sync:
        _position_sync.stop_sync()

def force_position_sync():
    """Force immediate position synchronization"""
    global _position_sync
    
    if _position_sync:
        _position_sync.force_sync()
