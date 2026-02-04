"""
SSR ALGO Storage - Session Persistence Layer

Provides JSON file-based storage for SSR Algo sessions with:
- Thread-safe file operations using file locking
- CRUD operations for sessions
- Automatic ID generation
- Version tracking for migration support

Created: February 2, 2026
"""

import json
import os
import time
import logging
import fcntl
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

log = logging.getLogger('ssr_algo_storage')

# Storage file path
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
STORAGE_FILE = os.path.join(DATA_DIR, 'ssr_algo_sessions.json')


class SSRAlgoStorage:
    """
    Thread-safe JSON storage for SSR Algo sessions.
    
    Storage format:
    {
        "sessions": {
            "session_id": { ... session data ... }
        },
        "active_session_ids": ["session_id1", "session_id2"],
        "version": 1
    }
    """
    
    def __init__(self, storage_path: str = None):
        """
        Initialize storage with optional custom path.
        
        Args:
            storage_path: Optional path to storage file. Defaults to data/ssr_algo_sessions.json
        """
        self.storage_path = storage_path or STORAGE_FILE
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        """Create storage file and directory if they don't exist."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        if not os.path.exists(self.storage_path):
            initial_data = {
                'sessions': {},
                'active_session_ids': [],
                'version': 1,
                'created_at': datetime.utcnow().isoformat()
            }
            self._write_data(initial_data)
            log.info(f"Created new SSR Algo storage file: {self.storage_path}")
    
    def _read_data(self) -> Dict:
        """Read storage file with shared lock."""
        try:
            with open(self.storage_path, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return data
        except json.JSONDecodeError as e:
            log.error(f"JSON decode error in storage file: {e}")
            return {'sessions': {}, 'active_session_ids': [], 'version': 1}
        except Exception as e:
            log.error(f"Error reading storage file: {e}")
            return {'sessions': {}, 'active_session_ids': [], 'version': 1}
    
    def _write_data(self, data: Dict):
        """Write to storage file with exclusive lock."""
        try:
            with open(self.storage_path, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2, default=str)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception as e:
            log.error(f"Error writing storage file: {e}")
            raise
    
    def _generate_session_id(self, underlying: str, expiry: str) -> str:
        """
        Generate unique session ID.
        
        Format: ssr_{sequence}_{expiry}_{underlying}_{short_uuid}
        Example: ssr_001_060226_btc_a1b2
        """
        data = self._read_data()
        session_count = len(data.get('sessions', {})) + 1
        short_uuid = uuid.uuid4().hex[:4]
        
        session_id = f"ssr_{session_count:03d}_{expiry}_{underlying.lower()}_{short_uuid}"
        return session_id
    
    def create_session(self, 
                       underlying: str,
                       expiry: str,
                       auto_loop_rounds: int = 2,
                       order_type: str = 'ssr',
                       start_time: str = '15:00',
                       end_time: str = '21:00',
                       strike_config: Dict = None,
                       circuit_breaker_config: Dict = None,
                       greeks_limits: Dict = None,
                       dwell_time_minutes: int = 10,
                       price_tolerance: int = 100) -> Dict:
        """
        Create a new SSR Algo session.
        
        Args:
            underlying: BTC or ETH
            expiry: Expiry in DDMMYY format
            auto_loop_rounds: Number of rounds per trigger (default 2)
            order_type: Order execution type (ssr, limit, market)
            start_time: Trading window start (IST)
            end_time: Trading window end (IST)
            strike_config: Premium percentage configuration
            circuit_breaker_config: Safety limits configuration
            greeks_limits: Greeks exposure limits
            dwell_time_minutes: Time price must stay in zone before adjustment (default 10)
            price_tolerance: Price tolerance around max loss points (default 100)
        
        Returns:
            Created session data with session_id
        """
        # Validate inputs
        underlying = underlying.upper()
        if underlying not in ['BTC', 'ETH']:
            raise ValueError(f"Invalid underlying: {underlying}. Must be BTC or ETH")
        
        if not expiry or len(expiry) not in [6, 8]:
            raise ValueError(f"Invalid expiry format: {expiry}. Must be DDMMYY or DDMMYYYY")
        
        if auto_loop_rounds < 1 or auto_loop_rounds > 10:
            raise ValueError(f"Invalid auto_loop_rounds: {auto_loop_rounds}. Must be 1-10")
        
        # Default strike config
        if strike_config is None:
            strike_config = {
                'otm_buy_percent_min': 45,
                'otm_buy_percent_max': 49,
                'far_otm_percent_min': 20,
                'far_otm_percent_max': 30
            }
        
        # Validate strike config
        required_keys = ['otm_buy_percent_min', 'otm_buy_percent_max', 
                         'far_otm_percent_min', 'far_otm_percent_max']
        for key in required_keys:
            if key not in strike_config:
                raise ValueError(f"Missing required strike_config key: {key}")
            val = strike_config[key]
            if not isinstance(val, (int, float)) or val < 1 or val > 99:
                raise ValueError(f"Invalid {key}: {val}. Must be 1-99")
        
        session_id = self._generate_session_id(underlying, expiry)
        
        # Default circuit breaker config - SAFETY LIMITS
        if circuit_breaker_config is None:
            circuit_breaker_config = {
                'max_adjustments_per_day': 10,      # Max adjustments before auto-stop
                'max_adjustments_per_session': 20,  # Lifetime max for session
                'max_daily_loss_usd': 5000,         # Daily loss limit in USD
                'cooldown_minutes': 5,              # Minimum time between adjustments
                'enabled': True                     # Enable/disable circuit breakers
            }
        
        # Default Greeks limits - EXPOSURE CONTROL
        if greeks_limits is None:
            greeks_limits = {
                'max_delta_exposure': 5.0,   # Max absolute delta
                'max_gamma_exposure': 2.0,   # Max absolute gamma
                'max_vega_exposure': 1000,   # Max vega exposure in USD
                'enabled': False             # Disabled by default (advanced feature)
            }
        
        session = {
            'session_id': session_id,
            'underlying': underlying,
            'expiry': expiry,
            'auto_loop_rounds': auto_loop_rounds,
            'order_type': order_type,
            'start_time': start_time,
            'end_time': end_time,
            'strike_config': strike_config,
            'circuit_breaker_config': circuit_breaker_config,
            'greeks_limits': greeks_limits,
            'dwell_time_minutes': dwell_time_minutes,
            'price_tolerance': price_tolerance,
            'status': 'IDLE',
            'trigger_count': 0,
            'rounds_completed': 0,  # Track completed rounds
            'rounds_placed': 0,     # Track rounds with orders placed (may not be filled)
            'pending_orders': [],   # Track pending order IDs
            'filled_orders': [],    # Track filled order details with actual prices
            'daily_adjustments': 0,
            'daily_pnl_usd': 0.0,
            'last_adjustment_time': None,
            'circuit_breaker_triggered': False,
            'circuit_breaker_reason': None,
            'started_at': None,
            'positions': [],
            'closed_positions': [],
            'max_loss_upper': None,
            'max_loss_lower': None,
            'zone_entry_time': None,
            'logs': [],  # Activity logs for user visibility
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Save to storage
        data = self._read_data()
        data['sessions'][session_id] = session
        self._write_data(data)
        
        log.info(f"Created SSR Algo session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Get a session by ID.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Session data or None if not found
        """
        data = self._read_data()
        return data.get('sessions', {}).get(session_id)
    
    def list_sessions(self, active_only: bool = False) -> List[Dict]:
        """
        List all sessions.
        
        Args:
            active_only: If True, only return sessions in active states
        
        Returns:
            List of session objects
        """
        data = self._read_data()
        sessions = list(data.get('sessions', {}).values())
        
        if active_only:
            active_states = {'IDLE', 'SELECTING_STRIKES', 'EXECUTING_AUTO_LOOP', 
                            'MONITORING', 'PAUSED', 'ERROR'}
            sessions = [s for s in sessions if s.get('status') in active_states]
        
        # Sort by created_at descending
        sessions.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return sessions
    
    def update_session(self, session_id: str, updates: Dict) -> Optional[Dict]:
        """
        Update a session with partial data.
        
        Args:
            session_id: Session identifier
            updates: Dictionary of fields to update
        
        Returns:
            Updated session data or None if not found
        """
        data = self._read_data()
        
        if session_id not in data.get('sessions', {}):
            log.warning(f"Session not found for update: {session_id}")
            return None
        
        # Apply updates
        session = data['sessions'][session_id]
        session.update(updates)
        session['updated_at'] = datetime.utcnow().isoformat()
        
        # Update active_session_ids based on status
        active_states = {'SELECTING_STRIKES', 'EXECUTING_AUTO_LOOP', 'MONITORING', 'PAUSED'}
        active_ids = set(data.get('active_session_ids', []))
        
        if session.get('status') in active_states:
            active_ids.add(session_id)
        else:
            active_ids.discard(session_id)
        
        data['active_session_ids'] = list(active_ids)
        data['sessions'][session_id] = session
        
        self._write_data(data)
        log.debug(f"Updated session {session_id}: {list(updates.keys())}")
        
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session by ID.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if deleted, False if not found
        """
        data = self._read_data()
        
        if session_id not in data.get('sessions', {}):
            log.warning(f"Session not found for deletion: {session_id}")
            return False
        
        del data['sessions'][session_id]
        
        # Remove from active list
        if session_id in data.get('active_session_ids', []):
            data['active_session_ids'].remove(session_id)
        
        self._write_data(data)
        log.info(f"Deleted session: {session_id}")
        
        return True
    
    def get_active_sessions(self) -> List[Dict]:
        """
        Get all sessions that are currently active (running or monitoring).
        
        Returns:
            List of active session objects
        """
        data = self._read_data()
        active_ids = data.get('active_session_ids', [])
        
        sessions = []
        for session_id in active_ids:
            session = data.get('sessions', {}).get(session_id)
            if session:
                sessions.append(session)
        
        return sessions
    
    def add_position_group(self, session_id: str, position_group: Dict) -> Optional[Dict]:
        """
        Add a new position group (trigger) to a session.
        
        Args:
            session_id: Session identifier
            position_group: Position data for this trigger
        
        Returns:
            Updated session or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        positions = session.get('positions', [])
        positions.append(position_group)
        
        trigger_count = session.get('trigger_count', 0) + 1
        
        return self.update_session(session_id, {
            'positions': positions,
            'trigger_count': trigger_count
        })
    
    def add_closed_position(self, session_id: str, closed_position: Dict) -> Optional[Dict]:
        """
        Add a closed position (from limit order fill).
        
        Args:
            session_id: Session identifier
            closed_position: Closed position data with realized PnL
        
        Returns:
            Updated session or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        closed = session.get('closed_positions', [])
        closed.append(closed_position)
        
        return self.update_session(session_id, {'closed_positions': closed})
    
    def add_log(self, session_id: str, message: str, level: str = 'info', data: Dict = None) -> Optional[Dict]:
        """
        Add a log entry to a session.
        
        Args:
            session_id: Session identifier
            message: Log message
            level: Log level (info, warn, error, success)
            data: Optional additional data
        
        Returns:
            Updated session or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        logs = session.get('logs', [])
        
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',  # Add Z to mark as UTC for JavaScript parsing
            'message': message,
            'level': level
        }
        if data:
            log_entry['data'] = data
        
        logs.append(log_entry)
        
        # Keep only last 100 logs to prevent unbounded growth
        if len(logs) > 100:
            logs = logs[-100:]
        
        return self.update_session(session_id, {'logs': logs})
    
    def increment_rounds_completed(self, session_id: str) -> Optional[Dict]:
        """
        Increment the rounds_completed counter for a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Updated session or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        rounds_completed = session.get('rounds_completed', 0) + 1
        return self.update_session(session_id, {'rounds_completed': rounds_completed})
    
    def add_pending_orders(self, session_id: str, orders: List[Dict]) -> Optional[Dict]:
        """
        Add pending orders to track.
        
        Args:
            session_id: Session identifier
            orders: List of order info {'order_id': str, 'symbol': str, 'side': str, 'size': int}
        
        Returns:
            Updated session or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        pending = session.get('pending_orders', [])
        for order in orders:
            order['placed_at'] = datetime.utcnow().isoformat()
            order['status'] = 'pending'
            pending.append(order)
        
        return self.update_session(session_id, {
            'pending_orders': pending,
            'rounds_placed': session.get('rounds_placed', 0) + 1
        })
    
    def update_order_filled(self, session_id: str, order_id: str, fill_price: float) -> Optional[Dict]:
        """
        Mark an order as filled with actual fill price.
        
        Args:
            session_id: Session identifier
            order_id: The order ID that was filled
            fill_price: Actual fill price from exchange
        
        Returns:
            Updated session or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        pending = session.get('pending_orders', [])
        filled = session.get('filled_orders', [])
        
        # Find and move order from pending to filled
        updated_pending = []
        for order in pending:
            if order.get('order_id') == order_id:
                order['status'] = 'filled'
                order['fill_price'] = fill_price
                order['filled_at'] = datetime.utcnow().isoformat()
                filled.append(order)
            else:
                updated_pending.append(order)
        
        # Check if all orders for a round are filled
        rounds_completed = session.get('rounds_completed', 0)
        if len(updated_pending) == 0 and len(filled) > 0:
            # All orders filled - round is truly complete
            rounds_completed = session.get('rounds_placed', 0)
        
        return self.update_session(session_id, {
            'pending_orders': updated_pending,
            'filled_orders': filled,
            'rounds_completed': rounds_completed
        })
    
    def get_pending_order_count(self, session_id: str) -> int:
        """Get count of pending (unfilled) orders."""
        session = self.get_session(session_id)
        if not session:
            return 0
        return len(session.get('pending_orders', []))


# Singleton instance
_storage = None

def get_storage() -> SSRAlgoStorage:
    """Get the singleton storage instance."""
    global _storage
    if _storage is None:
        _storage = SSRAlgoStorage()
    return _storage
