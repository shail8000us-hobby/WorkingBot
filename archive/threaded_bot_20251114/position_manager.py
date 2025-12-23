"""
PositionManager - Position and State Management Module

Single Responsibility: Manage all position state with thread-safe access

This module OWNS the critical _state_lock that all other modules need.
It manages open positions, pending orders, retry queues, and state persistence.

Extracted from GridBotWebSocket (Phase 4 - State management)
CRITICAL: This module owns the state lock - all other modules depend on it
"""

import json
import time
import logging
import threading
import hashlib
import os
import uuid
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime, timezone

# ✅ PHASE 1: Event sourcing imports
try:
    from bot.strategy.modules.event_store import EventStore, Event, EventType
except ImportError:
    # Fallback for backward compatibility if event store not yet deployed
    EventStore = None
    Event = None
    EventType = None

log = logging.getLogger("runner")


class PositionManager:
    """
    Thread-safe position and state management
    
    Responsibilities:
    - Manage open positions (open_tranches)
    - Manage pending orders (pending_buy)
    - Manage TP retry queue (async protection)
    - Provide thread-safe state access (OWNS _state_lock)
    - Persist runtime state to disk (FIX #13)
    - Track order capacity reservations
    
    NOT Responsible For:
    - Order placement (OrderManager handles this)
    - Grid calculations (GridCalculator handles this)
    - Fill detection (FillDetector handles this)
    """
    
    def __init__(
        self,
        max_open: int,
        grid_calculator: Any = None,
        session_tag: str = "",
        event_store: Optional[Any] = None,
        legacy_mode: bool = True
    ):
        """
        Initialize position manager
        
        Args:
            max_open: Maximum number of open positions allowed
            grid_calculator: Optional GridCalculator instance for grid alignment
            session_tag: Session identifier for logging
        """
        # Critical: Create and own the state lock (RLock allows reentrant acquisition)
        self._state_lock = threading.RLock()
        
        # Position tracking
        self.open_tranches: List[Dict[str, Any]] = []
        self.pending_buy: Optional[Dict[str, Any]] = None
        
        # ✅ NEW NOV 10: SHORT mode support
        self.pending_sell: Optional[Dict[str, Any]] = None
        
        # TP retry queue for async retry processing
        self._tp_retry_queue: List[Dict[str, Any]] = []
        
        # Capacity management
        self.max_open = max_open
        self._reserved_capacity = 0
        
        # Persistence debouncing (prevent excessive disk writes)
        self._last_persist_time = 0
        self._min_persist_interval = 1.0  # Min 1 second between persists
        
        # ✅ NEW NOV 10: Mode-specific state file
        import os
        self.grid_mode = os.getenv('GRIDBOT_GRID_MODE', 'LONG').upper()
        self.default_state_file = f'runtime_state_{self.grid_mode}.json'
        
        # Configuration
        self.grid_calc = grid_calculator
        self.session_tag = session_tag
        
        # ✅ PHASE 1: Event sourcing integration
        self.event_store = event_store
        self.legacy_mode = legacy_mode  # Dual-write flag for safety
        
        # Initialize event store if not provided and module available
        if self.event_store is None and EventStore is not None:
            try:
                db_path = f"bot_events_{self.grid_mode}.db"
                self.event_store = EventStore(db_path)
                log.info(f"✅ EventStore initialized: {db_path}")
            except Exception as e:
                log.warning(f"⚠️ Could not initialize EventStore: {e}")
                self.event_store = None
        
        log.info(f"✅ PositionManager initialized (max_open={max_open}, mode={self.grid_mode}, event_store={self.event_store is not None})")
    
    @property
    def state_lock(self) -> threading.Lock:
        """
        Expose state lock for other modules
        
        Other modules should request this lock for thread-safe operations.
        
        Returns:
            The shared threading.Lock instance
        """
        return self._state_lock
    
    # ========================================================================
    # Position Management (Thread-Safe)
    # ========================================================================
    
    def add_position(self, position: Dict[str, Any]) -> None:
        """
        Add new position (thread-safe)
        
        ✅ FIX NOV 6: Validate entry_price is grid-aligned before adding
        ✅ PHASE 0 FIX (NOV 9): Force immediate persistence after position add
        
        Args:
            position: Position dictionary with entry_price, tp_price, etc.
        """
        with self._state_lock:
            # ✅ FIX NOV 6: Validate entry price is grid-aligned BEFORE adding
            entry_price = position.get('entry_price')
            
            log.info(f"🔍 [POS DEBUG] Adding position: entry=${entry_price}, size={position.get('size')}")
            
            if entry_price and hasattr(self, 'grid_calc') and self.grid_calc:
                if not self.grid_calc.is_price_grid_aligned(entry_price):
                    log.error(f"🚨 CRITICAL: Attempted to add position @ ${entry_price:,.2f} (OFF-GRID!)")
                    log.error(f"   Grid Step: {self.grid_calc.step}")
                    log.error(f"   Snapping to nearest grid level...")
                    
                    # Snap to nearest grid level (includes quantization)
                    corrected_price = self.grid_calc.find_nearest_grid_level(entry_price)
                    log.warning(f"   Corrected from ${entry_price:,.2f} to ${corrected_price:,.2f}")
                    position['entry_price'] = corrected_price
                else:
                    # ✅ FIX NOV 10: Even if grid-aligned, ensure proper quantization
                    # This prevents floating-point drift in subsequent calculations
                    position['entry_price'] = self.grid_calc.quantize_price(entry_price)
            
            self.open_tranches.append(position)
            log.info(f"✅ [POS DEBUG] Position added. Total positions: {len(self.open_tranches)}")
            log.debug(f"Position added: Entry ${position.get('entry_price', 0):,.0f}")
            
            # ✅ PHASE 1: Append event to event store
            if self.event_store and Event and EventType:
                try:
                    correlation_id = position.get('correlation_id', str(uuid.uuid4()))
                    position_id = position.get('position_id') or position.get('buy_order_id', str(uuid.uuid4()))
                    
                    event = Event(
                        event_id=str(uuid.uuid4()),
                        event_type=EventType.POSITION_OPENED,
                        timestamp=time.time(),
                        correlation_id=correlation_id,
                        aggregate_id=position_id,
                        data=position.copy(),
                        metadata={
                            "bot_version": "2.0",
                            "mode": self.grid_mode,
                            "session_tag": self.session_tag
                        }
                    )
                    self.event_store.append_event(event)
                    log.debug(f"✅ Event logged: POSITION_OPENED for {position_id}")
                except Exception as e:
                    log.warning(f"⚠️ Failed to log event: {e}")
        
        # ✅ PHASE 0 FIX (NOV 9): Force immediate persistence (remove debouncing)
        # ✅ PHASE 1: Dual-write mode (events + legacy JSON for safety)
        if self.legacy_mode:
            self.persist_runtime_state(force=True)
            log.info(f"✅ Position added + persisted: {position.get('entry_price')}")
    
    def remove_position(self, position: Dict[str, Any]) -> bool:
        """
        Remove position from tracking (thread-safe)
        
        Args:
            position: Position dict to remove
            
        Returns:
            True if position was found and removed, False otherwise
        """
        with self._state_lock:
            if position in self.open_tranches:
                self.open_tranches.remove(position)
                log.info(f"✅ Position removed: Entry ${position.get('entry_price', 0):,.0f}")
                
                # ✅ PHASE 1: Append POSITION_CLOSED event
                if self.event_store and Event and EventType:
                    try:
                        position_id = position.get('position_id') or position.get('buy_order_id', str(uuid.uuid4()))
                        
                        event = Event(
                            event_id=str(uuid.uuid4()),
                            event_type=EventType.POSITION_CLOSED,
                            timestamp=time.time(),
                            correlation_id=position.get('correlation_id', str(uuid.uuid4())),
                            aggregate_id=position_id,
                            data={
                                "position_id": position_id,
                                "exit_price": position.get('tp_price', 0),
                                "entry_price": position.get('entry_price', 0),
                                "close_reason": "TP_HIT"
                            },
                            metadata={
                                "bot_version": "2.0",
                                "mode": self.grid_mode
                            }
                        )
                        self.event_store.append_event(event)
                        log.debug(f"✅ Event logged: POSITION_CLOSED for {position_id}")
                    except Exception as e:
                        log.warning(f"⚠️ Failed to log event: {e}")
                
                # ✅ NEW: Persist immediately after critical state change
                if self.legacy_mode:
                    self.persist_if_needed()
                return True
            else:
                # ✅ FIX NOV 9: Log when removal fails (copy bug detection)
                log.error(f"❌ FAILED to remove position: Entry ${position.get('entry_price', 0):,.0f}")
                log.error(f"   Position not found in open_tranches (possible copy bug)")
                log.error(f"   Current positions: {[p.get('entry_price') for p in self.open_tranches]}")
                return False
    
    def remove_position_by_order_id(self, order_id: str) -> bool:
        """
        Remove position by order ID (thread-safe fallback method)
        
        ✅ FIX NOV 9: Fallback method to remove by ID instead of reference
        
        Args:
            order_id: Order ID to search for (buy_order_id or tp_id)
            
        Returns:
            True if position was found and removed, False otherwise
        """
        with self._state_lock:
            for i, position in enumerate(self.open_tranches):
                if (position.get('buy_order_id') == order_id or 
                    position.get('tp_id') == order_id):
                    removed = self.open_tranches.pop(i)
                    log.info(f"✅ Position removed by order_id: Entry ${removed.get('entry_price', 0):,.0f}")
                    
                    # ✅ PHASE 1: Log POSITION_CLOSED event
                    if self.event_store and Event and EventType:
                        try:
                            position_id = removed.get('position_id') or order_id
                            
                            event = Event(
                                event_id=str(uuid.uuid4()),
                                event_type=EventType.POSITION_CLOSED,
                                timestamp=time.time(),
                                correlation_id=removed.get('correlation_id', str(uuid.uuid4())),
                                aggregate_id=position_id,
                                data={
                                    "position_id": position_id,
                                    "exit_price": removed.get('tp_price', 0),
                                    "entry_price": removed.get('entry_price', 0),
                                    "close_reason": "TP_HIT_BY_ID"
                                },
                                metadata={
                                    "bot_version": "2.0",
                                    "mode": self.grid_mode
                                }
                            )
                            self.event_store.append_event(event)
                            log.debug(f"✅ Event logged: POSITION_CLOSED for {position_id}")
                        except Exception as e:
                            log.warning(f"⚠️ Failed to log event: {e}")
                    
                    if self.legacy_mode:
                        self.persist_if_needed()
                    return True
            log.warning(f"⚠️  Position not found for order_id: {order_id}")
            return False
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get copy of all positions (thread-safe)
        
        Returns:
            Copy of open_tranches list
        """
        with self._state_lock:
            return self.open_tranches.copy()
    
    def get_position_count(self) -> int:
        """
        Get number of open positions (thread-safe)
        
        Returns:
            Number of open positions
        """
        with self._state_lock:
            return len(self.open_tranches)
    
    def find_position_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Find position by order ID (thread-safe)
        
        ✅ FIX NOV 9: Returns reference (not copy) to allow proper removal
        
        Args:
            order_id: Order ID to search for (buy_order_id or tp_id)
            
        Returns:
            Position dict reference if found, None otherwise
        
        IMPORTANT: Caller must hold state_lock or not modify returned dict
        """
        with self._state_lock:
            for position in self.open_tranches:
                if (position.get('buy_order_id') == order_id or 
                    position.get('tp_id') == order_id):
                    return position  # ✅ FIX: Return reference, not copy
            return None
    
    # ========================================================================
    # Pending Order Management (Thread-Safe)
    # ========================================================================
    
    def set_pending_buy(self, order: Optional[Dict[str, Any]]) -> None:
        """
        Set pending buy order (thread-safe)
        
        Args:
            order: Order dictionary or None to clear
        """
        with self._state_lock:
            self.pending_buy = order
            if order:
                order_id = order.get('order_id', 'unknown')
                price = order.get('price', 0)
                reconciled = ' (reconciled from exchange)' if order.get('reconciled') else ''
                log.info(f"📌 Pending BUY tracked: ID {order_id} @ ${price:,.0f}{reconciled}")
                
                # ✅ PHASE 1: Log ORDER_PLACED event
                if self.event_store and Event and EventType:
                    try:
                        event = Event(
                            event_id=str(uuid.uuid4()),
                            event_type=EventType.ORDER_PLACED,
                            timestamp=time.time(),
                            correlation_id=order.get('correlation_id', str(uuid.uuid4())),
                            aggregate_id=order_id,
                            data={
                                "order_id": order_id,
                                "side": "buy",
                                "price": price,
                                "size": order.get('size', 1),
                                "order_type": "limit_order"
                            },
                            metadata={
                                "bot_version": "2.0",
                                "mode": self.grid_mode,
                                "reconciled": order.get('reconciled', False)
                            }
                        )
                        self.event_store.append_event(event)
                        self.last_buy_order_time = time.time()
                        log.debug(f"✅ Event logged: ORDER_PLACED (buy) for {order_id}")
                    except Exception as e:
                        log.warning(f"⚠️ Failed to log event: {e}")
            else:
                log.info("📍 Pending BUY cleared from tracker")
        
        # ✅ NEW: Persist immediately after critical state change
        if self.legacy_mode:
            self.persist_if_needed()
    
    def get_pending_buy(self) -> Optional[Dict[str, Any]]:
        """
        Get pending buy order (thread-safe)
        
        Returns:
            Copy of pending_buy dict or None
        """
        with self._state_lock:
            return self.pending_buy.copy() if self.pending_buy else None
    
    def clear_pending_buy(self) -> None:
        """Clear pending buy order (thread-safe)"""
        # ✅ PHASE 1: Log ORDER_FILLED event if there was a pending buy
        with self._state_lock:
            if self.pending_buy and self.event_store and Event and EventType:
                try:
                    order_id = self.pending_buy.get('order_id', 'unknown')
                    event = Event(
                        event_id=str(uuid.uuid4()),
                        event_type=EventType.ORDER_FILLED,
                        timestamp=time.time(),
                        correlation_id=self.pending_buy.get('correlation_id', str(uuid.uuid4())),
                        aggregate_id=order_id,
                        data={
                            "order_id": order_id,
                            "side": "buy",
                            "fill_price": self.pending_buy.get('price', 0),
                            "fill_size": self.pending_buy.get('size', 1)
                        },
                        metadata={
                            "bot_version": "2.0",
                            "mode": self.grid_mode
                        }
                    )
                    self.event_store.append_event(event)
                    log.debug(f"✅ Event logged: ORDER_FILLED (buy) for {order_id}")
                except Exception as e:
                    log.warning(f"⚠️ Failed to log event: {e}")
        
        self.set_pending_buy(None)
    
    # SHORT mode pending sell management
    def set_pending_sell(self, order: Optional[Dict[str, Any]]) -> None:
        """
        Set pending sell order for SHORT mode (thread-safe)
        
        Args:
            order: Order dictionary or None to clear
        """
        with self._state_lock:
            if not hasattr(self, 'pending_sell'):
                self.pending_sell = None
            self.pending_sell = order
            if order:
                order_id = order.get('order_id', 'unknown')
                price = order.get('price', 0)
                reconciled = ' (reconciled from exchange)' if order.get('reconciled') else ''
                log.info(f"📌 Pending SELL tracked: ID {order_id} @ ${price:,.0f}{reconciled}")
                
                # ✅ PHASE 1: Log ORDER_PLACED event
                if self.event_store and Event and EventType:
                    try:
                        event = Event(
                            event_id=str(uuid.uuid4()),
                            event_type=EventType.ORDER_PLACED,
                            timestamp=time.time(),
                            correlation_id=order.get('correlation_id', str(uuid.uuid4())),
                            aggregate_id=order_id,
                            data={
                                "order_id": order_id,
                                "side": "sell",
                                "price": price,
                                "size": order.get('size', 1),
                                "order_type": "limit_order"
                            },
                            metadata={
                                "bot_version": "2.0",
                                "mode": self.grid_mode,
                                "reconciled": order.get('reconciled', False)
                            }
                        )
                        self.event_store.append_event(event)
                        self.last_sell_order_time = time.time()
                        log.debug(f"✅ Event logged: ORDER_PLACED (sell) for {order_id}")
                    except Exception as e:
                        log.warning(f"⚠️ Failed to log event: {e}")
            else:
                log.info("📍 Pending SELL cleared from tracker")
        
        # ✅ NEW: Persist immediately after critical state change
        if self.legacy_mode:
            self.persist_if_needed()
    
    def get_pending_sell(self) -> Optional[Dict[str, Any]]:
        """
        Get pending sell order for SHORT mode (thread-safe)
        
        Returns:
            Copy of pending_sell dict or None
        """
        with self._state_lock:
            if not hasattr(self, 'pending_sell'):
                self.pending_sell = None
            return self.pending_sell.copy() if self.pending_sell else None
    
    def clear_pending_sell(self) -> None:
        """Clear pending sell order for SHORT mode (thread-safe)"""
        # ✅ PHASE 1: Log ORDER_FILLED event if there was a pending sell
        with self._state_lock:
            if self.pending_sell and self.event_store and Event and EventType:
                try:
                    order_id = self.pending_sell.get('order_id', 'unknown')
                    event = Event(
                        event_id=str(uuid.uuid4()),
                        event_type=EventType.ORDER_FILLED,
                        timestamp=time.time(),
                        correlation_id=self.pending_sell.get('correlation_id', str(uuid.uuid4())),
                        aggregate_id=order_id,
                        data={
                            "order_id": order_id,
                            "side": "sell",
                            "fill_price": self.pending_sell.get('price', 0),
                            "fill_size": self.pending_sell.get('size', 1)
                        },
                        metadata={
                            "bot_version": "2.0",
                            "mode": self.grid_mode
                        }
                    )
                    self.event_store.append_event(event)
                    log.debug(f"✅ Event logged: ORDER_FILLED (sell) for {order_id}")
                except Exception as e:
                    log.warning(f"⚠️ Failed to log event: {e}")
        
        self.set_pending_sell(None)
    
    # ========================================================================
    # Capacity Management (Atomic Reservation System)
    # ========================================================================
    
    def try_reserve_capacity(self) -> bool:
        """
        Atomically check if capacity available and reserve it
        
        RACE CONDITION PROTECTION:
        - Checks open_tranches + pending_buy + reserved vs max_open
        - Reserves capacity INSIDE lock (atomic with check)
        - Prevents concurrent fills from both seeing "under limit"
        
        Extracted from Lines 432-461 (gbot_ws.py)
        
        Returns:
            True if capacity reserved, False if at limit
        """
        with self._state_lock:
            # Calculate total capacity in use
            current_open = len(self.open_tranches)
            current_pending = 1 if self.pending_buy else 0
            reserved = self._reserved_capacity
            
            total_committed = current_open + current_pending + reserved
            
            if total_committed >= self.max_open:
                log.debug(f"⚠️ Capacity check failed: {total_committed}/{self.max_open} "
                         f"(open={current_open}, pending={current_pending}, reserved={reserved})")
                return False
            
            # Reserve capacity atomically
            self._reserved_capacity += 1
            log.debug(f"✅ Capacity reserved: {total_committed + 1}/{self.max_open} "
                     f"(open={current_open}, pending={current_pending}, reserved={reserved + 1})")
            return True
    
    def release_capacity(self) -> None:
        """
        Release reserved order capacity
        
        Called when:
        - Order placement fails
        - Order successfully placed (reservation becomes pending_buy)
        
        Extracted from Lines 463-474 (gbot_ws.py)
        """
        with self._state_lock:
            if self._reserved_capacity > 0:
                self._reserved_capacity -= 1
                log.debug(f"♻️ Capacity released: reservations={self._reserved_capacity}")
    
    def get_capacity_status(self) -> Dict[str, int]:
        """
        Get current capacity status (thread-safe)
        
        Returns:
            Dict with open, pending, reserved, total, max_open
        """
        with self._state_lock:
            current_open = len(self.open_tranches)
            current_pending = 1 if self.pending_buy else 0
            reserved = self._reserved_capacity
            total = current_open + current_pending + reserved
            
            return {
                'open': current_open,
                'pending': current_pending,
                'reserved': reserved,
                'total': total,
                'max_open': self.max_open,
                'available': max(0, self.max_open - total)
            }
    
    # ========================================================================
    # TP Retry Queue Management
    # ========================================================================
    
    def schedule_tp_retry(self, position: Dict[str, Any]) -> None:
        """
        Schedule position for async TP retry (non-blocking)
        
        Extracted from Lines 1792-1806 (gbot_ws.py)
        
        Args:
            position: Position dictionary with failed TP
        """
        with self._state_lock:
            self._tp_retry_queue.append({
                'position': position,
                'attempts': 0,
                'next_retry': time.time() + 5,  # 5s initial delay
                'max_attempts': 10
            })
        
        log.info(f"⏰ Scheduled for TP retry: Entry ${position.get('entry_price', 0):,.0f} "
                f"(queue size: {len(self._tp_retry_queue)})")
    
    def get_retry_queue_size(self) -> int:
        """Get number of positions in retry queue (thread-safe)"""
        with self._state_lock:
            return len(self._tp_retry_queue)
    
    def get_pending_retries(self, current_time: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Get retry entries ready for processing (thread-safe)
        
        Args:
            current_time: Current timestamp (defaults to time.time())
            
        Returns:
            List of retry entries ready for processing
        """
        if current_time is None:
            current_time = time.time()
        
        with self._state_lock:
            return [r for r in self._tp_retry_queue if r['next_retry'] <= current_time]
    
    def remove_from_retry_queue(self, retry_entry: Dict[str, Any]) -> bool:
        """
        Remove entry from retry queue (thread-safe)
        
        Args:
            retry_entry: Retry entry to remove
            
        Returns:
            True if removed, False if not found
        """
        with self._state_lock:
            if retry_entry in self._tp_retry_queue:
                self._tp_retry_queue.remove(retry_entry)
                return True
            return False
    
    def update_retry_entry(self, retry_entry: Dict[str, Any], backoff_multiplier: int = 2) -> None:
        """
        Update retry entry with exponential backoff (thread-safe)
        
        Args:
            retry_entry: Retry entry to update (updated in place)
            backoff_multiplier: Multiplier for exponential backoff
        """
        retry_entry['attempts'] += 1
        backoff_delay = 5 * (backoff_multiplier ** retry_entry['attempts'])  # 10s, 20s, 40s, 80s...
        backoff_delay = min(backoff_delay, 80)  # Cap at 80s
        retry_entry['next_retry'] = time.time() + backoff_delay
        
        log.debug(f"Retry updated: attempt {retry_entry['attempts']}, next in {backoff_delay}s")
    
    # ========================================================================
    # Runtime State Persistence (FIX #13)
    # ========================================================================
    
    def persist_runtime_state(self, filename: str = None, force: bool = False) -> None:
        """
        ✅ FIX #13: Persist critical runtime state to disk for crash recovery
        ✅ ENHANCED: Added metadata, checksums, and integrity validation
        ✅ NOV 8: Added backup before overwrite for recovery
        ✅ PHASE 0 FIX (NOV 9): Added force parameter for immediate persistence
        ✅ NOV 10: Mode-atomic state (uses mode-specific filename by default)
        
        Saves current bot state to runtime_state_{MODE}.json every heartbeat (10s).
        Enables recovery after unexpected crashes/restarts without losing position data.
        
        Extracted from Lines 2740-2785 (gbot_ws.py)
        
        State saved:
        - open_tranches: All open positions with entry/TP prices
        - pending_buy: Current pending order details (LONG mode)
        - pending_sell: Current pending order details (SHORT mode)
        - tp_retry_queue: Positions awaiting TP retry
        - timestamp: Last save time for staleness detection
        - metadata: Version, checksum, PID for integrity checking
        
        Args:
            filename: Filename for state file (default: mode-specific file)
            force: Force immediate persistence (ignore debouncing)
        """
        # Use mode-specific filename if not provided
        if filename is None:
            filename = self.default_state_file
        try:
            # ✅ NEW NOV 8: Create backup before overwriting
            if Path(filename).exists():
                backup_file = f"{filename}.backup"
                try:
                    import shutil
                    shutil.copy2(filename, backup_file)
                    log.debug(f"💾 Backup created: {backup_file}")
                except Exception as e:
                    log.warning(f"⚠️ Failed to create backup (non-fatal): {e}")
            
            with self._state_lock:
                # Build core state data
                data = {
                    'timestamp': time.time(),
                    'session_tag': self.session_tag,
                    'open_tranches': self.open_tranches.copy(),
                    'pending_buy': self.pending_buy.copy() if self.pending_buy else None,
                    'pending_sell': self.pending_sell.copy() if self.pending_sell else None,  # ✅ NEW NOV 10
                    'tp_retry_queue': [r.copy() for r in self._tp_retry_queue],
                    'reserved_capacity': self._reserved_capacity,
                    'max_open': self.max_open,
                    'grid_mode': self.grid_mode  # ✅ NEW NOV 10: Track mode in state
                }
            
            # Wrap with metadata for integrity checking
            state_with_metadata = {
                'version': '2.0',
                'schema_version': 1,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'bot_pid': os.getpid(),
                'checksum': None,  # Will be calculated
                'data': data
            }
            
            # Calculate checksum (serialize data only, not full object)
            data_json = json.dumps(data, sort_keys=True)
            checksum = hashlib.sha256(data_json.encode()).hexdigest()[:16]
            state_with_metadata['checksum'] = checksum
            
            # Write atomically (write to temp file, then rename)
            temp_file = f'{filename}.tmp'
            with open(temp_file, 'w') as f:
                json.dump(state_with_metadata, f, indent=2)
            
            # Atomic rename (prevents corruption if interrupted)
            os.replace(temp_file, filename)
            
            # Log state persistence with details (GREEN for easy spotting)
            pending_info = ""
            if self.pending_buy:
                pending_info = f", pending_buy: ID {self.pending_buy.get('order_id', 'unknown')}"
            
            if len(self.open_tranches) > 0 or self.pending_buy or len(self._tp_retry_queue) > 0:
                log.info(f"\033[32m💾 State persisted: {len(self.open_tranches)} positions{pending_info}, "
                         f"{len(self._tp_retry_queue)} retries [checksum: {checksum}]\033[0m")
        
        except Exception as e:
            # Non-fatal - don't crash bot if persistence fails
            log.warning(f"⚠️ Failed to persist runtime state (non-fatal): {e}")
    
    def persist_if_needed(self, force: bool = False) -> None:
        """
        ✅ NEW: Persist state with debouncing to prevent excessive disk I/O
        
        Only persists if:
        - force=True, OR
        - At least 1 second has passed since last persist
        
        Args:
            force: Force immediate persistence (ignore debouncing)
        """
        now = time.time()
        if force or (now - self._last_persist_time >= self._min_persist_interval):
            self.persist_runtime_state()
            self._last_persist_time = now
    
    def load_runtime_state_with_recovery(self, filename: str = None) -> bool:
        """
        ✅ NEW NOV 8: Load state with automatic recovery fallback chain
        ✅ NOV 10: Mode-atomic state (uses mode-specific filename by default)
        
        Recovery chain:
        1. Try primary state file
        2. Try backup file
        3. Start fresh (reconciliation handled by caller)
        
        Args:
            filename: Primary state filename (default: mode-specific file)
            
        Returns:
            True if state loaded successfully, False if starting fresh
        """
        # Use mode-specific filename if not provided
        if filename is None:
            filename = self.default_state_file
        # Try primary state file
        log.info("🔄 Attempting crash recovery from runtime state...")
        if self.load_runtime_state(filename):
            log.info("✅ State recovered from primary file")
            return True
        
        # Try backup file
        backup_file = f"{filename}.backup"
        if Path(backup_file).exists():
            log.warning("⚠️ Primary state failed, trying backup...")
            if self.load_runtime_state(backup_file):
                log.info("✅ State recovered from backup file")
                # Copy backup to primary for future use
                try:
                    import shutil
                    shutil.copy2(backup_file, filename)
                    log.info("📋 Restored backup to primary state file")
                except Exception as e:
                    log.warning(f"⚠️ Could not restore backup to primary: {e}")
                return True
        
        # All recovery attempts failed
        log.warning("⚠️ All state recovery attempts failed - starting fresh")
        log.info("   Reconciliation from exchange will be performed")
        return False
    
    def _validate_state_schema(self, state: Dict) -> tuple:
        """
        ✅ NEW NOV 8: Validate state conforms to expected schema
        
        Args:
            state: State dictionary to validate
            
        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        # Required fields
        required_fields = ['timestamp', 'session_tag', 'open_tranches', 
                          'pending_buy', 'tp_retry_queue', 'reserved_capacity', 'max_open']
        
        for field in required_fields:
            if field not in state:
                return False, f"Missing required field: {field}"
        
        # Type validation
        if not isinstance(state['open_tranches'], list):
            return False, f"open_tranches must be list, got {type(state['open_tranches'])}"
        
        if state['pending_buy'] is not None and not isinstance(state['pending_buy'], dict):
            return False, f"pending_buy must be dict or None, got {type(state['pending_buy'])}"
        
        if not isinstance(state['tp_retry_queue'], list):
            return False, f"tp_retry_queue must be list, got {type(state['tp_retry_queue'])}"
        
        # Timestamp sanity check
        current_time = time.time()
        if state['timestamp'] > current_time + 60:  # Future timestamp
            return False, f"Timestamp is in the future (clock skew?)"
        
        # Version compatibility (for future-proofing)
        schema_version = state.get('schema_version', 1)
        if schema_version > 1:  # Current supported version is 1
            return False, f"Incompatible schema version: {schema_version} (expected <= 1)"
        
        return True, "Valid"
    
    def load_runtime_state(self, filename: str = None) -> bool:
        """
        Load runtime state from disk (for crash recovery)
        ✅ ENHANCED: Added checksum validation and backward compatibility
        ✅ NOV 8: Added schema validation
        ✅ NOV 10: Mode-atomic state (uses mode-specific filename by default)
        
        Args:
            filename: Filename to load from (default: mode-specific file)
            
        Returns:
            True if state loaded successfully, False otherwise
        """
        # Use mode-specific filename if not provided
        if filename is None:
            filename = self.default_state_file
        try:
            if not Path(filename).exists():
                log.info(f"No runtime state file found: {filename}")
                return False
            
            with open(filename, 'r') as f:
                state_file = json.load(f)
            
            # Check if this is new format (with metadata) or legacy format
            if 'version' in state_file and 'data' in state_file:
                # New format with metadata
                log.info(f"Loading state file version {state_file.get('version', 'unknown')}")
                
                # Verify checksum
                stored_checksum = state_file.get('checksum')
                data = state_file['data']
                
                if stored_checksum:
                    # Recalculate checksum to verify integrity
                    data_json = json.dumps(data, sort_keys=True)
                    calculated_checksum = hashlib.sha256(data_json.encode()).hexdigest()[:16]
                    
                    if stored_checksum != calculated_checksum:
                        log.error(f"❌ State file checksum mismatch - CORRUPTED!")
                        log.error(f"   Expected: {stored_checksum}, Got: {calculated_checksum}")
                        return False
                    else:
                        log.info(f"✅ Checksum validated: {stored_checksum}")
                
                state = data  # Extract actual state data
            else:
                # Legacy format (backward compatibility)
                log.warning("⚠️ Loading legacy state file format (no metadata)")
                state = state_file
            
            # ✅ NEW NOV 8: Validate schema
            is_valid, error_msg = self._validate_state_schema(state)
            if not is_valid:
                log.error(f"❌ State file schema validation failed: {error_msg}")
                return False
            else:
                log.info(f"✅ Schema validated successfully")
            
            # Check staleness
            timestamp = state.get('timestamp', 0)
            age_seconds = time.time() - timestamp
            
            if age_seconds > 300:  # ✅ FIXED: Older than 5 minutes (was 1 hour)
                log.warning(f"⚠️ Runtime state is stale ({age_seconds/60:.1f} minutes old), not loading")
                return False
            
            # Load state
            with self._state_lock:
                self.open_tranches = state.get('open_tranches', [])
                self.pending_buy = state.get('pending_buy')
                self.pending_sell = state.get('pending_sell')  # ✅ NEW NOV 10
                self._tp_retry_queue = state.get('tp_retry_queue', [])
                self._reserved_capacity = state.get('reserved_capacity', 0)
                
                # ✅ NEW NOV 10: Validate loaded mode matches current mode
                saved_mode = state.get('grid_mode', 'LONG')
                if saved_mode != self.grid_mode:
                    log.warning(f"⚠️  State file mode ({saved_mode}) differs from current mode ({self.grid_mode})")
                    log.warning(f"   This should not happen with mode-atomic state!")
            
            log.info(f"✅ Runtime state loaded: {len(self.open_tranches)} positions, "
                    f"{len(self._tp_retry_queue)} retries (age: {age_seconds:.0f}s)")
            return True
        
        except Exception as e:
            log.error(f"❌ Failed to load runtime state: {e}")
            import traceback
            log.error(traceback.format_exc())
            return False
    
    # ========================================================================
    # Grid Alignment (for Recovery)
    # ========================================================================
    
    def realign_positions_to_grid(self) -> int:
        """
        Realign all position entry prices to nearest grid level
        
        Used after opportunistic recovery to fix grid drift.
        Requires grid_calculator to be set.
        
        Returns:
            Number of positions realigned
        """
        if not self.grid_calc:
            log.warning("⚠️ Cannot realign - no GridCalculator available")
            return 0
        
        realigned_count = 0
        
        with self._state_lock:
            for pos in self.open_tranches:
                original_entry = pos.get('entry_price')
                
                if original_entry:
                    # Round to nearest grid level
                    aligned = self.grid_calc.find_nearest_grid_level(original_entry)
                    
                    # Check if adjustment needed
                    if abs(aligned - original_entry) > 0.01:
                        log.info(f"⚙️ Realigning position: ${original_entry:,.2f} → ${aligned:,.0f}")
                        pos['entry_price'] = aligned
                        pos['grid_aligned'] = True
                        realigned_count += 1
                    else:
                        # Already aligned
                        pos['grid_aligned'] = True
        
        if realigned_count > 0:
            log.info(f"✅ Grid realignment complete: {realigned_count} position(s) adjusted")
        
        return realigned_count
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get summary of current state (thread-safe)
        
        Returns:
            Dict with state summary for logging/monitoring
        """
        with self._state_lock:
            capacity = self.get_capacity_status()
            
            return {
                'open_positions': len(self.open_tranches),
                'pending_buy': self.pending_buy is not None,
                'retry_queue_size': len(self._tp_retry_queue),
                'capacity': capacity,
                'positions': [
                    {
                        'entry': p.get('entry_price'),
                        'tp': p.get('tp_price'),
                        'protected': p.get('protected', False)
                    }
                    for p in self.open_tranches
                ]
            }
