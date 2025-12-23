"""
State Projector Module - Rebuilds current state from event stream.
Supports time-travel queries and idempotent state reconstruction.
"""

import logging
from typing import Dict, List, Any, Optional
from copy import deepcopy

from bot.strategy.modules.event_store import EventStore, Event, EventType

# Configure module logger
log = logging.getLogger("state_projector")


class StateProjector:
    """
    Projects current state from event stream using event sourcing pattern.
    Supports rebuilding state at any point in time.
    """
    
    def __init__(self, event_store: EventStore):
        """
        Initialize state projector with event store.
        
        Args:
            event_store: EventStore instance for reading events
        """
        self.event_store = event_store
        log.info("StateProjector initialized")
    
    def project_current_state(self) -> Dict[str, Any]:
        """
        Rebuild complete state from all events in the store.
        
        Returns:
            Dictionary containing current state with:
                - open_tranches: List of open positions
                - pending_buy: Current pending buy order or None
                - pending_sell: Current pending sell order or None
                - last_buy_order_time: Timestamp of last buy order
                - last_sell_order_time: Timestamp of last sell order
                - tp_orders: Map of position_id to TP order_id
        """
        log.info("Projecting current state from all events")
        
        # Get all events sorted by timestamp
        events = self.event_store.get_all_events()
        
        # Process events to build state
        state = self._process_events(events)
        
        log.info(f"State projection complete: {len(state['open_tranches'])} positions, "
                f"pending_buy={state['pending_buy'] is not None}, "
                f"pending_sell={state['pending_sell'] is not None}")
        
        return state
    
    def project_state_at(self, timestamp: float) -> Dict[str, Any]:
        """
        Rebuild state at a specific point in time (time-travel query).
        
        Args:
            timestamp: Unix timestamp to project state at
            
        Returns:
            State dictionary as it was at the specified timestamp
        """
        log.info(f"Projecting state at timestamp: {timestamp}")
        
        # Get events up to the specified timestamp
        all_events = self.event_store.get_all_events()
        events = [e for e in all_events if e.timestamp <= timestamp]
        
        # Process events to build historical state
        state = self._process_events(events)
        
        log.info(f"Historical state projection complete: {len(events)} events processed")
        
        return state
    
    def _process_events(self, events: List[Event]) -> Dict[str, Any]:
        """
        Process a list of events to build state.
        
        Args:
            events: List of events to process (should be time-ordered)
            
        Returns:
            Reconstructed state dictionary
        """
        # Initialize clean state
        state = self._get_clean_state()
        
        # Sort events by timestamp to ensure correct ordering
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        # Process each event
        for event in sorted_events:
            try:
                self._apply_event(state, event)
            except Exception as e:
                log.warning(f"Failed to apply event {event.event_id}: {e}")
                # Continue processing other events
                continue
        
        return state
    
    def _get_clean_state(self) -> Dict[str, Any]:
        """
        Get a clean/empty state structure.
        
        Returns:
            Empty state dictionary with all required fields
        """
        return {
            "open_tranches": [],
            "pending_buy": None,
            "pending_sell": None,
            "last_buy_order_time": 0,
            "last_sell_order_time": 0,
            "tp_orders": {}
        }
    
    def _apply_event(self, state: Dict[str, Any], event: Event) -> None:
        """
        Apply a single event to the state (mutates state in-place).
        
        Args:
            state: Current state dictionary to modify
            event: Event to apply
        """
        event_type = event.event_type
        data = event.data
        
        if event_type == EventType.POSITION_OPENED:
            self._handle_position_opened(state, event)
            
        elif event_type == EventType.POSITION_CLOSED:
            self._handle_position_closed(state, event)
            
        elif event_type == EventType.ORDER_PLACED:
            self._handle_order_placed(state, event)
            
        elif event_type == EventType.ORDER_FILLED:
            self._handle_order_filled(state, event)
            
        elif event_type == EventType.ORDER_CANCELLED:
            self._handle_order_cancelled(state, event)
            
        elif event_type == EventType.TP_PLACED:
            self._handle_tp_placed(state, event)
            
        else:
            log.debug(f"Unknown event type: {event_type}")
    
    def _handle_position_opened(self, state: Dict[str, Any], event: Event) -> None:
        """
        Handle POSITION_OPENED event - add position to open_tranches.
        
        Args:
            state: State to modify
            event: Position opened event
        """
        position = deepcopy(event.data)
        
        # Ensure position has required fields
        if 'position_id' not in position:
            position['position_id'] = event.aggregate_id
        
        # Check for duplicate (idempotency)
        existing = next((p for p in state['open_tranches'] 
                        if p.get('position_id') == position['position_id']), None)
        
        if not existing:
            state['open_tranches'].append(position)
            log.debug(f"Position opened: {position['position_id']}")
        else:
            log.debug(f"Position already exists (idempotent): {position['position_id']}")
    
    def _handle_position_closed(self, state: Dict[str, Any], event: Event) -> None:
        """
        Handle POSITION_CLOSED event - remove position from open_tranches.
        
        Args:
            state: State to modify
            event: Position closed event
        """
        position_id = event.aggregate_id
        
        # Remove position from open_tranches
        state['open_tranches'] = [
            p for p in state['open_tranches'] 
            if p.get('position_id') != position_id
        ]
        
        # Clean up any associated TP orders
        if position_id in state['tp_orders']:
            del state['tp_orders'][position_id]
            
        log.debug(f"Position closed: {position_id}")
    
    def _handle_order_placed(self, state: Dict[str, Any], event: Event) -> None:
        """
        Handle ORDER_PLACED event - update pending orders and timestamps.
        
        Args:
            state: State to modify
            event: Order placed event
        """
        order = deepcopy(event.data)
        side = order.get('side', '').lower()
        
        if side == 'buy':
            state['pending_buy'] = order
            state['last_buy_order_time'] = event.timestamp
            log.debug(f"Buy order placed: {order.get('order_id')}")
            
        elif side == 'sell':
            state['pending_sell'] = order
            state['last_sell_order_time'] = event.timestamp
            log.debug(f"Sell order placed: {order.get('order_id')}")
            
        else:
            log.warning(f"Unknown order side: {side}")
    
    def _handle_order_filled(self, state: Dict[str, Any], event: Event) -> None:
        """
        Handle ORDER_FILLED event - clear pending orders.
        
        Args:
            state: State to modify
            event: Order filled event
        """
        order_id = event.data.get('order_id', event.aggregate_id)
        side = event.data.get('side', '').lower()
        
        # Clear pending order if it matches
        if side == 'buy' and state['pending_buy']:
            if state['pending_buy'].get('order_id') == order_id:
                state['pending_buy'] = None
                log.debug(f"Buy order filled: {order_id}")
                
        elif side == 'sell' and state['pending_sell']:
            if state['pending_sell'].get('order_id') == order_id:
                state['pending_sell'] = None
                log.debug(f"Sell order filled: {order_id}")
        
        # Check if this was a TP order
        for position_id, tp_order_id in list(state['tp_orders'].items()):
            if tp_order_id == order_id:
                # TP filled, remove from tracking
                del state['tp_orders'][position_id]
                log.debug(f"TP order filled for position: {position_id}")
                break
    
    def _handle_order_cancelled(self, state: Dict[str, Any], event: Event) -> None:
        """
        Handle ORDER_CANCELLED event - clean up cancelled orders.
        
        Args:
            state: State to modify
            event: Order cancelled event
        """
        order_id = event.data.get('order_id', event.aggregate_id)
        
        # Clear pending buy if it matches
        if state['pending_buy'] and state['pending_buy'].get('order_id') == order_id:
            state['pending_buy'] = None
            log.debug(f"Pending buy order cancelled: {order_id}")
        
        # Clear pending sell if it matches
        if state['pending_sell'] and state['pending_sell'].get('order_id') == order_id:
            state['pending_sell'] = None
            log.debug(f"Pending sell order cancelled: {order_id}")
        
        # Check if this was a TP order
        for position_id, tp_order_id in list(state['tp_orders'].items()):
            if tp_order_id == order_id:
                del state['tp_orders'][position_id]
                log.debug(f"TP order cancelled for position: {position_id}")
                break
    
    def _handle_tp_placed(self, state: Dict[str, Any], event: Event) -> None:
        """
        Handle TP_PLACED event - track TP orders for positions.
        
        Args:
            state: State to modify
            event: TP placed event
        """
        position_id = event.data.get('position_id')
        order_id = event.data.get('order_id')
        
        if position_id and order_id:
            state['tp_orders'][position_id] = order_id
            log.debug(f"TP placed for position {position_id}: {order_id}")
        else:
            log.warning(f"TP_PLACED event missing position_id or order_id: {event.data}")
    
    def validate_state(self, state: Dict[str, Any]) -> List[str]:
        """
        Validate a projected state for consistency.
        
        Args:
            state: State dictionary to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check required fields exist
        required_fields = ['open_tranches', 'pending_buy', 'pending_sell', 
                          'last_buy_order_time', 'last_sell_order_time', 'tp_orders']
        for field in required_fields:
            if field not in state:
                errors.append(f"Missing required field: {field}")
        
        # Check data types
        if not isinstance(state.get('open_tranches', None), list):
            errors.append("open_tranches must be a list")
            
        if not isinstance(state.get('tp_orders', None), dict):
            errors.append("tp_orders must be a dict")
        
        # Check timestamps are non-negative
        if state.get('last_buy_order_time', -1) < 0:
            errors.append("last_buy_order_time must be non-negative")
            
        if state.get('last_sell_order_time', -1) < 0:
            errors.append("last_sell_order_time must be non-negative")
        
        # Check position consistency
        position_ids = set()
        for position in state.get('open_tranches', []):
            if 'position_id' not in position:
                errors.append(f"Position missing position_id: {position}")
            else:
                pid = position['position_id']
                if pid in position_ids:
                    errors.append(f"Duplicate position_id: {pid}")
                position_ids.add(pid)
        
        # Check TP orders reference valid positions
        for position_id in state.get('tp_orders', {}).keys():
            if position_id not in position_ids:
                errors.append(f"TP order for non-existent position: {position_id}")
        
        return errors
    
    def get_state_summary(self, state: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of the state.
        
        Args:
            state: State dictionary to summarize
            
        Returns:
            Summary string
        """
        num_positions = len(state.get('open_tranches', []))
        has_pending_buy = state.get('pending_buy') is not None
        has_pending_sell = state.get('pending_sell') is not None
        num_tp_orders = len(state.get('tp_orders', {}))
        
        total_exposure = sum(p.get('size', 0) for p in state.get('open_tranches', []))
        
        return (f"State Summary: {num_positions} positions, "
                f"exposure={total_exposure}, "
                f"pending_buy={has_pending_buy}, "
                f"pending_sell={has_pending_sell}, "
                f"tp_orders={num_tp_orders}")
