import asyncio
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable
from loguru import logger as log

from bot.strategy.monitors.base_monitor import BaseMonitor


class OrderState(Enum):
    """Order lifecycle states."""
    PLACED = "placed"           # Order just placed
    PENDING = "pending"         # Waiting for fill
    FILLED = "filled"           # Fill detected
    PROTECTED = "protected"     # TP order placed
    CANCELLED = "cancelled"     # Order cancelled
    EXPIRED = "expired"         # Order expired
    ERROR = "error"             # Unexpected state


class OrderTracker(BaseMonitor):
    """
    Order state machine with timeout handling.
    
    Tracks complete order lifecycle:
    PLACED → PENDING → FILLED → PROTECTED
           ↓         ↓
       CANCELLED  EXPIRED
    
    Features:
    - Timeout detection for each state
    - State transition validation
    - Audit trail of state changes
    - Automatic timeout handling
    """
    
    def __init__(
        self,
        pending_timeout: int = 86400,  # 24 hours
        fill_timeout: int = 10,         # 10 seconds for TP placement
        check_interval: int = 30,       # Check every 30 seconds
        timeout_callback: Optional[Callable] = None
    ):
        super().__init__("OrderTracker")
        self.pending_timeout = pending_timeout
        self.fill_timeout = fill_timeout
        self.check_interval = check_interval
        self.timeout_callback = timeout_callback
        
        # Order tracking
        self._orders: Dict[str, Dict[str, Any]] = {}
        
        # Metrics
        self._state_transitions = 0
        self._timeouts_detected = 0
        self._invalid_transitions = 0
    
    def register_order(
        self,
        order_id: str,
        side: str,
        price: float,
        size: int,
        initial_state: OrderState = OrderState.PLACED
    ) -> None:
        """
        Register a new order for tracking.
        
        Args:
            order_id: Order ID
            side: Order side (buy/sell)
            price: Order price
            size: Order size
            initial_state: Initial state (default: PLACED)
        """
        order_id_str = str(order_id)
        
        self._orders[order_id_str] = {
            "order_id": order_id,
            "side": side,
            "price": price,
            "size": size,
            "current_state": initial_state,
            "state_history": [(initial_state, time.time())],
            "registered_at": time.time(),
            "last_transition": time.time(),
            "timeout_count": 0
        }
        
        log.debug(f"[{self.name}] Registered order {order_id}: {side} @ ${price} (state: {initial_state.value})")
    
    def transition(self, order_id: str, new_state: OrderState) -> bool:
        """
        Transition order to new state.
        
        Args:
            order_id: Order ID
            new_state: New state
            
        Returns:
            True if transition successful, False if invalid
        """
        order_id_str = str(order_id)
        
        if order_id_str not in self._orders:
            log.warning(f"[{self.name}] Cannot transition unknown order {order_id}")
            return False
        
        order = self._orders[order_id_str]
        current_state = order["current_state"]
        
        # Validate transition
        if not self._is_valid_transition(current_state, new_state):
            self._invalid_transitions += 1
            log.warning(f"[{self.name}] Invalid transition for {order_id}: {current_state.value} → {new_state.value}")
            return False
        
        # Update state
        order["current_state"] = new_state
        order["last_transition"] = time.time()
        order["state_history"].append((new_state, time.time()))
        self._state_transitions += 1
        
        log.info(f"[{self.name}] Order {order_id} transitioned: {current_state.value} → {new_state.value}")
        
        return True
    
    def _is_valid_transition(self, current: OrderState, new: OrderState) -> bool:
        """
        Check if state transition is valid.
        
        Valid transitions:
        - PLACED → PENDING, CANCELLED
        - PENDING → FILLED, CANCELLED, EXPIRED
        - FILLED → PROTECTED
        - Any → ERROR
        """
        valid_transitions = {
            OrderState.PLACED: [OrderState.PENDING, OrderState.CANCELLED],
            OrderState.PENDING: [OrderState.FILLED, OrderState.CANCELLED, OrderState.EXPIRED],
            OrderState.FILLED: [OrderState.PROTECTED],
            OrderState.PROTECTED: [],  # Terminal state
            OrderState.CANCELLED: [],  # Terminal state
            OrderState.EXPIRED: [],    # Terminal state
            OrderState.ERROR: []       # Terminal state
        }
        
        # Allow transition to ERROR from any state
        if new == OrderState.ERROR:
            return True
        
        return new in valid_transitions.get(current, [])
    
    def get_order_state(self, order_id: str) -> Optional[OrderState]:
        """Get current state of an order."""
        order_id_str = str(order_id)
        
        if order_id_str in self._orders:
            return self._orders[order_id_str]["current_state"]
        
        return None
    
    def get_order_info(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get complete order information."""
        order_id_str = str(order_id)
        
        if order_id_str in self._orders:
            return self._orders[order_id_str].copy()
        
        return None
    
    async def _execute(self) -> None:
        """Execute timeout monitoring loop."""
        await self._check_timeouts()
        await asyncio.sleep(self.check_interval)
    
    async def _check_timeouts(self) -> None:
        """Check for timed out orders."""
        current_time = time.time()
        
        for order_id, order in list(self._orders.items()):
            state = order["current_state"]
            time_in_state = current_time - order["last_transition"]
            
            # Check PENDING timeout
            if state == OrderState.PENDING and time_in_state > self.pending_timeout:
                log.warning(f"⏰ [{self.name}] Order {order_id} timeout in PENDING state ({time_in_state:.0f}s)")
                self._timeouts_detected += 1
                order["timeout_count"] += 1
                
                if self.timeout_callback:
                    await self.timeout_callback(order_id, state, time_in_state)
            
            # Check FILLED timeout (waiting for TP placement)
            elif state == OrderState.FILLED and time_in_state > self.fill_timeout:
                log.warning(f"⏰ [{self.name}] Order {order_id} timeout in FILLED state ({time_in_state:.0f}s)")
                log.warning(f"   TP placement may have failed - triggering TP retry")
                self._timeouts_detected += 1
                order["timeout_count"] += 1
                
                if self.timeout_callback:
                    await self.timeout_callback(order_id, state, time_in_state)
            
            # Cleanup terminal states after 1 hour
            if state in [OrderState.PROTECTED, OrderState.CANCELLED, OrderState.EXPIRED]:
                age = current_time - order["registered_at"]
                if age > 3600:  # 1 hour
                    log.debug(f"[{self.name}] Removing old order {order_id} (age: {age:.0f}s)")
                    del self._orders[order_id]
    
    def get_orders_by_state(self, state: OrderState) -> list[Dict[str, Any]]:
        """Get all orders in a specific state."""
        return [
            order.copy()
            for order in self._orders.values()
            if order["current_state"] == state
        ]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get tracker metrics."""
        state_counts = {}
        for state in OrderState:
            count = sum(1 for o in self._orders.values() if o["current_state"] == state)
            state_counts[state.value] = count
        
        return {
            "tracked_orders": len(self._orders),
            "state_transitions": self._state_transitions,
            "timeouts_detected": self._timeouts_detected,
            "invalid_transitions": self._invalid_transitions,
            "state_counts": state_counts
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status with metrics."""
        base_health = super().get_health_status()
        base_health.update({
            "metrics": self.get_metrics()
        })
        return base_health
