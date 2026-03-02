"""
Position Manager Actor for managing grid bot positions.
Single-threaded actor with zero locks for state management.
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import uuid4
import asyncio

from loguru import logger as log

from bot.strategy.actors.base_actor import Actor, Message
from bot.strategy.modules.event_store import EventStore, Event, EventType
from bot.utils.human_logger import human_log


class PositionManagerActor(Actor):
    """
    Actor for managing grid bot positions.
    
    State managed:
    - open_tranches: List of open positions
    - pending_buy: Current pending buy order
    - pending_sell: Current pending sell order
    - last_buy_order_time: Timestamp of last buy order
    - last_sell_order_time: Timestamp of last sell order
    
    All state modifications are single-threaded - NO LOCKS NEEDED!
    """
    
    def __init__(self, event_store: EventStore, max_positions: int = 5):
        """
        Initialize position manager actor.
        
        Args:
            event_store: Event store for persistence
            max_positions: Maximum allowed open positions
        """
        super().__init__("PositionManager")
        self.event_store = event_store
        self.max_positions = max_positions
        
        # Initialize state (no locks needed - single threaded!)
        self.state = {
            "open_tranches": [],
            "pending_buy": None,
            "pending_sell": None,
            "last_buy_order_time": 0,
            "last_sell_order_time": 0,
            "total_positions_opened": 0,
            "total_positions_closed": 0,
            "tp_retry_queue": [],  # TP retry queue for failed TP placements
            # Opportunistic recovery statistics
            "opportunistic_recovery_stats": {
                "total_recoveries": 0,          # Total recovery events
                "total_positions_recovered": 0,  # Total positions filled via recovery
                "total_capital_saved": 0.0,      # Total $ saved from better entries
                "last_recovery_time": 0,         # Timestamp of last recovery
                "startup_recoveries": 0,         # Count of startup recoveries
                "volatility_recoveries": 0       # Count of volatility recoveries (future)
            }
        }
        
        # Position index for fast lookup
        self._position_index: Dict[str, Dict] = {}
        
        # Initialize empty state (all state stored in SQL event store)
        # JSON files removed - WebUI reads from SQL database via data_writer.py

    def replay_own_positions(self) -> int:
        """
        Replay POSITION_OPENED and POSITION_CLOSED events from the event store
        to rebuild the bot's own position state on startup.
        
        This ensures the bot only tracks positions IT created — not manual trades
        or positions from other algos on the same exchange account.
        
        Returns:
            Number of open positions restored
        """
        log.info("🔄 Replaying position events from event store...")
        
        # Get all position events from event store
        try:
            opened_events = self.event_store.get_events_by_type(
                EventType.POSITION_OPENED, limit=50000
            )
            closed_events = self.event_store.get_events_by_type(
                EventType.POSITION_CLOSED, limit=50000
            )
        except Exception as e:
            log.error(f"❌ Failed to read events from event store: {e}")
            return 0
        
        # Build set of closed position IDs
        closed_ids = set()
        for event in closed_events:
            closed_ids.add(event.aggregate_id)
        
        # Find positions that were opened but never closed = still open
        open_positions = []
        seen_ids = set()  # Deduplicate (same position_id can have multiple OPENED events)
        
        for event in sorted(opened_events, key=lambda e: e.timestamp):
            pid = event.aggregate_id
            
            # Skip if already closed or already seen
            if pid in closed_ids or pid in seen_ids:
                continue
            
            seen_ids.add(pid)
            
            position = {
                "position_id": pid,
                "entry_price": event.data.get("entry_price", 0),
                "tp_price": event.data.get("tp_price", 0),
                "size": event.data.get("size", 0),
                "correlation_id": event.correlation_id,
                "timestamp": event.timestamp,
            }
            
            # Preserve optional fields
            for key in ("entry_order_id", "tp_order_id", "is_opportunistic",
                        "actual_entry", "saved_capital"):
                if key in event.data:
                    position[key] = event.data[key]
            
            open_positions.append(position)
        
        # Load into state
        self.state["open_tranches"] = open_positions
        self._position_index = {p["position_id"]: p for p in open_positions}
        self.state["total_positions_opened"] = len(opened_events)
        self.state["total_positions_closed"] = len(closed_events)
        
        log.info(f"✅ Replayed {len(opened_events)} opens + {len(closed_events)} closes")
        log.info(f"   → {len(open_positions)} position(s) still open (bot's own)")
        
        for p in open_positions:
            log.info(f"   📍 {p['position_id']}: entry=${p['entry_price']:,.0f}, tp=${p['tp_price']:,.0f}")
        
        return len(open_positions)

    async def _handle_replay_positions(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """Handle REPLAY_POSITIONS message — triggers event replay."""
        count = self.replay_own_positions()
        return {"status": "ok", "positions_restored": count}

    async def _handle_close_stale_position(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Close a position that the bot thinks is open but exchange says is not.
        Records a POSITION_CLOSED event so it stays closed across future restarts.
        
        Args:
            payload: Dict with position_id and reason
        """
        position_id = payload["position_id"]
        reason = payload.get("reason", "stale_position")
        
        position = self._position_index.get(position_id)
        if not position:
            return {"status": "ok", "already_closed": True}
        
        # Remove from state
        self.state["open_tranches"].remove(position)
        del self._position_index[position_id]
        self.state["total_positions_closed"] += 1
        
        # Record POSITION_CLOSED event so it doesn't reappear on next restart
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.POSITION_CLOSED,
            timestamp=time.time(),
            correlation_id=correlation_id,
            aggregate_id=position_id,
            data={
                "position_id": position_id,
                "closed_at": time.time(),
                "reason": reason,
                "entry_price": position.get("entry_price", 0),
                "tp_price": position.get("tp_price", 0),
            },
            metadata={"actor": self.name, "auto_closed": True}
        )
        self.event_store.append_event(event)
        
        log.info(f"🗑️  Stale position closed: {position_id} (reason: {reason})")
        
        return {"status": "ok", "position": position}

    async def _handle_add_position(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Add new position.
        
        Args:
            payload: Position data (position_id, entry_price, tp_price, size)
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status response
        """
        # CRITICAL FIX NOV 19: Validate position_id is not None
        position_id = payload.get("position_id")
        if not position_id or position_id == "None" or str(position_id).lower() == "none":
            log.error(f"❌ REJECTED position with invalid ID: {position_id}")
            log.error(f"   Payload: {payload}")
            return {"status": "error", "error": "Invalid position_id - cannot be None"}
        
        position = {
            "position_id": position_id,
            "entry_price": payload["entry_price"],
            "tp_price": payload["tp_price"],
            "size": payload["size"],
            "correlation_id": correlation_id,
            "timestamp": time.time()
        }
        
        # Add entry_order_id and tp_order_id if provided (for reconciliation)
        if "entry_order_id" in payload:
            position["entry_order_id"] = payload["entry_order_id"]
        if "tp_order_id" in payload:
            position["tp_order_id"] = payload["tp_order_id"]
        
        # Preserve opportunistic recovery fields if present
        if "is_opportunistic" in payload:
            position["is_opportunistic"] = payload["is_opportunistic"]
            position["actual_entry"] = payload.get("actual_entry", payload["entry_price"])
            position["saved_capital"] = payload.get("saved_capital", 0.0)
            
            # Update opportunistic recovery statistics
            stats = self.state["opportunistic_recovery_stats"]
            stats["total_positions_recovered"] += 1
            stats["total_capital_saved"] += position["saved_capital"]
            stats["last_recovery_time"] = time.time()
            
            log.info(f"Opportunistic position tracked: ${position['saved_capital']:.2f} saved")
            
            # Log opportunistic position event to SQL
            opp_event = Event(
                event_id=str(uuid4()),
                event_type=EventType.OPPORTUNISTIC_POSITION_OPENED,
                timestamp=time.time(),
                correlation_id=correlation_id,
                aggregate_id=position["position_id"],
                data={
                    "position_id": position["position_id"],
                    "grid_entry": position["entry_price"],
                    "actual_entry": position["actual_entry"],
                    "saved_capital": position["saved_capital"],
                    "tp_price": position["tp_price"],
                    "size": position["size"]
                },
                metadata={"actor": self.name, "is_opportunistic": True}
            )
            self.event_store.append_event(opp_event)
        
        # Check for duplicate position (idempotent operation)
        if position["position_id"] in self._position_index:
            log.warning(f"Position {position['position_id']} already exists - skipping duplicate add")
            return {"status": "ok", "position_id": position["position_id"]}
        
        # Check capacity
        if len(self.state["open_tranches"]) >= self.max_positions:
            log.warning(f"Cannot add position - at max capacity {self.max_positions}")
            return {"status": "error", "error": "Max positions reached"}
        
        # Add position (no lock needed!)
        self.state["open_tranches"].append(position)
        self._position_index[position["position_id"]] = position
        self.state["total_positions_opened"] += 1
        
        # Log event
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.POSITION_OPENED,
            timestamp=time.time(),
            correlation_id=correlation_id,
            aggregate_id=position["position_id"],
            data=position,
            metadata={"actor": self.name}
        )
        self.event_store.append_event(event)
        
        log.info(f"Position added: {position['position_id']} @ {position['entry_price']}")
        
        return {"status": "ok", "position_id": position["position_id"]}
    
    async def _handle_remove_position(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Remove position by ID.
        
        Args:
            payload: Dict with position_id
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status response
        """
        position_id = payload["position_id"]
        
        # Find and remove position (no lock needed!)
        position = self._position_index.get(position_id)
        if not position:
            log.warning(f"Position not found: {position_id}")
            return {"status": "error", "error": "Position not found"}
        
        # Remove from state
        self.state["open_tranches"].remove(position)
        del self._position_index[position_id]
        self.state["total_positions_closed"] += 1
        
        # Log event
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.POSITION_CLOSED,
            timestamp=time.time(),
            correlation_id=correlation_id,
            aggregate_id=position_id,
            data={"position_id": position_id, "closed_at": time.time()},
            metadata={"actor": self.name}
        )
        self.event_store.append_event(event)
        
        log.info(f"Position removed: {position_id}")
        
        return {"status": "ok", "position": position}
    
    async def _handle_set_pending_buy(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Set pending buy order.
        
        Args:
            payload: Order data (order_id, price, size)
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status response
        """
        order = {
            "order_id": payload["order_id"],
            "price": payload["price"],
            "size": payload["size"],
            "timestamp": time.time()
        }
        
        # Update state (no lock needed!)
        old_pending = self.state["pending_buy"]
        self.state["pending_buy"] = order
        self.state["last_buy_order_time"] = time.time()
        
        # Log event
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.PENDING_BUY_SET,
            timestamp=time.time(),
            correlation_id=correlation_id,
            aggregate_id=order["order_id"],
            data=order,
            metadata={"actor": self.name, "old_pending": old_pending}
        )
        self.event_store.append_event(event)
        
        size = order.get('size', 'unknown')
        log.info(f"Pending buy set: {order['order_id']} @ {order['price']} ({size} lots)")
        
        return {"status": "ok", "order_id": order["order_id"]}
    
    async def _handle_clear_pending_buy(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Clear pending buy order.
        
        Args:
            payload: Optional dict with order_id to verify
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status response
        """
        # Verify order_id if provided
        if order_id := payload.get("order_id"):
            if self.state["pending_buy"] and self.state["pending_buy"]["order_id"] != order_id:
                log.warning(f"Pending buy mismatch: expected {self.state['pending_buy']['order_id']}, got {order_id}")
                return {"status": "error", "error": "Order ID mismatch"}
        
        # Clear pending (no lock needed!)
        old_pending = self.state["pending_buy"]
        self.state["pending_buy"] = None
        
        # Log event
        if old_pending:
            event = Event(
                event_id=str(uuid4()),
                event_type=EventType.PENDING_BUY_CLEARED,
                timestamp=time.time(),
                correlation_id=correlation_id,
                aggregate_id=old_pending["order_id"],
                data={"cleared_order": old_pending},
                metadata={"actor": self.name}
            )
            self.event_store.append_event(event)
            
            log.info(f"Pending buy cleared from memory: {old_pending['order_id']} (order already processed by exchange)")
        
        return {"status": "ok", "cleared": old_pending is not None}
    
    async def _handle_set_pending_sell(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Set pending sell order.
        
        Args:
            payload: Order data (order_id, price, size)
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status response
        """
        order = {
            "order_id": payload["order_id"],
            "price": payload["price"],
            "size": payload["size"],
            "timestamp": time.time()
        }
        
        # Update state (no lock needed!)
        old_pending = self.state["pending_sell"]
        self.state["pending_sell"] = order
        self.state["last_sell_order_time"] = time.time()
        
        # Log event
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.PENDING_SELL_SET,
            timestamp=time.time(),
            correlation_id=correlation_id,
            aggregate_id=order["order_id"],
            data=order,
            metadata={"actor": self.name, "old_pending": old_pending}
        )
        self.event_store.append_event(event)
        
        size = order.get('size', 'unknown')
        log.info(f"Pending sell set: {order['order_id']} @ {order['price']} ({size} lots)")
        
        return {"status": "ok", "order_id": order["order_id"]}
    
    async def _handle_clear_pending_sell(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Clear pending sell order.
        
        Args:
            payload: Optional dict with order_id to verify
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status response
        """
        # Verify order_id if provided
        if order_id := payload.get("order_id"):
            if self.state["pending_sell"] and self.state["pending_sell"]["order_id"] != order_id:
                log.warning(f"Pending sell mismatch: expected {self.state['pending_sell']['order_id']}, got {order_id}")
                return {"status": "error", "error": "Order ID mismatch"}
        
        # Clear pending (no lock needed!)
        old_pending = self.state["pending_sell"]
        self.state["pending_sell"] = None
        
        # Log event
        if old_pending:
            event = Event(
                event_id=str(uuid4()),
                event_type=EventType.PENDING_SELL_CLEARED,
                timestamp=time.time(),
                correlation_id=correlation_id,
                aggregate_id=old_pending["order_id"],
                data={"cleared_order": old_pending},
                metadata={"actor": self.name}
            )
            self.event_store.append_event(event)
            
            log.info(f"Pending sell cleared from memory: {old_pending['order_id']} (order already processed by exchange)")
        
        return {"status": "ok", "cleared": old_pending is not None}
    
    # NOTE: _handle_recovery_started is defined later (line ~497) with EventStore logging
    # Duplicate definition was removed on Dec 12, 2025
    
    async def _handle_get_state(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Get current state (read-only).
        
        Args:
            payload: Empty
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Current state copy
        """
        # Return copy of state (no lock needed for read!)
        return self.state.copy()
    
    async def _handle_get_open_positions(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get list of open positions.
        
        Args:
            payload: Empty
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            List of open positions
        """
        # Return copy of positions (no lock needed for read!)
        return self.state["open_tranches"].copy()
    
    async def _handle_get_position_by_tp(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find position by TP price.
        
        Args:
            payload: Dict with tp_price
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Position if found, None otherwise
        """
        tp_price = payload["tp_price"]
        
        # Find position with matching TP (no lock needed for read!)
        for position in self.state["open_tranches"]:
            if abs(position["tp_price"] - tp_price) < 0.01:  # Float comparison tolerance
                return position.copy()
        
        return None
    
    async def _handle_recovery_started(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Record that an opportunistic recovery event started.
        
        Args:
            payload: Dict with recovery_type ('startup' or 'volatility')
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status response
        """
        recovery_type = payload.get("recovery_type", "startup")
        stats = self.state["opportunistic_recovery_stats"]
        stats["total_recoveries"] += 1
        
        if recovery_type == "startup":
            stats["startup_recoveries"] += 1
        elif recovery_type == "volatility":
            stats["volatility_recoveries"] += 1
        
        # Log event to EventStore
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.OPPORTUNISTIC_RECOVERY_STARTED,
            timestamp=time.time(),
            correlation_id=correlation_id,
            aggregate_id=f"recovery_{recovery_type}_{int(time.time())}",
            data={
                "recovery_type": recovery_type,
                "is_opportunistic_recovery": True
            },
            metadata={"actor": self.name, "event": "recovery_started"}
        )
        self.event_store.append_event(event)
        
        log.info(f"Opportunistic recovery started: {recovery_type}")
        return {"status": "ok"}
    
    async def _handle_update_position(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Update existing position.
        
        Args:
            payload: Position updates (position_id required)
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status response
        """
        position_id = payload.get("position_id")
        if not position_id:
            return {"status": "error", "error": "position_id required"}
        
        # Find position (no lock needed!)
        position = self._position_index.get(position_id)
        if not position:
            return {"status": "error", "error": "Position not found"}
        
        # Update fields
        old_position = position.copy()
        for key, value in payload.items():
            if key != "position_id":
                position[key] = value
        
        # Log event
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.POSITION_UPDATED,
            timestamp=time.time(),
            correlation_id=correlation_id,
            aggregate_id=position_id,
            data={"old": old_position, "new": position},
            metadata={"actor": self.name}
        )
        self.event_store.append_event(event)
        
        log.info(f"Position updated: {position_id}")
        
        return {"status": "ok", "position": position}
    
    async def _handle_check_capacity(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Check if there's capacity for new positions.
        
        Args:
            payload: Empty
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Capacity status
        """
        current_count = len(self.state["open_tranches"])
        has_capacity = current_count < self.max_positions
        
        return {
            "has_capacity": has_capacity,
            "current_count": current_count,
            "max_positions": self.max_positions,
            "available_slots": self.max_positions - current_count
        }
    
    async def _handle_get_metrics(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Get position metrics.
        
        Args:
            payload: Empty
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Position metrics
        """
        open_positions = self.state["open_tranches"]
        
        if open_positions:
            entry_prices = [p["entry_price"] for p in open_positions]
            sizes = [p["size"] for p in open_positions]
            
            metrics = {
                "open_count": len(open_positions),
                "total_opened": self.state["total_positions_opened"],
                "total_closed": self.state["total_positions_closed"],
                "avg_entry_price": sum(entry_prices) / len(entry_prices),
                "total_size": sum(sizes),
                "oldest_position_age": time.time() - min(p["timestamp"] for p in open_positions),
                "has_pending_buy": self.state["pending_buy"] is not None,
                "has_pending_sell": self.state["pending_sell"] is not None
            }
        else:
            metrics = {
                "open_count": 0,
                "total_opened": self.state["total_positions_opened"],
                "total_closed": self.state["total_positions_closed"],
                "avg_entry_price": 0,
                "total_size": 0,
                "oldest_position_age": 0,
                "has_pending_buy": self.state["pending_buy"] is not None,
                "has_pending_sell": self.state["pending_sell"] is not None
            }
        
        return metrics
    
    async def _handle_schedule_tp_retry(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Schedule position for TP retry after placement failure.
        
        Args:
            payload: Position data and retry config
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status response
        """
        position = payload["position"]
        retry_count = payload.get("retry_count", 0)
        max_retries = payload.get("max_retries", 5)
        
        # Create retry entry
        retry_entry = {
            "position": position,
            "retry_count": retry_count + 1,
            "next_retry": time.time() + 10,  # Retry in 10 seconds
            "max_retries": max_retries,
            "scheduled_at": time.time(),
            "correlation_id": correlation_id
        }
        
        # Add to queue (no lock needed!)
        self.state["tp_retry_queue"].append(retry_entry)
        
        # Log event
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.TP_RETRY_SCHEDULED,
            timestamp=time.time(),
            correlation_id=correlation_id,
            aggregate_id=position.get("position_id", "unknown"),
            data=retry_entry,
            metadata={"actor": self.name}
        )
        self.event_store.append_event(event)
        
        log.info(
            f"⏰ Scheduled for TP retry: Entry ${position.get('entry_price', 0):,.0f} "
            f"(retry {retry_entry['retry_count']}/{max_retries}, queue size: {len(self.state['tp_retry_queue'])})"
        )
        
        return {"status": "ok", "queue_size": len(self.state["tp_retry_queue"])}
    
    async def _handle_get_due_retries(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Get positions ready for TP retry.
        
        Args:
            payload: Empty
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            List of due retry entries
        """
        current_time = time.time()
        
        # Find due retries (no lock needed for read!)
        due_retries = [
            r for r in self.state["tp_retry_queue"] 
            if r["next_retry"] <= current_time
        ]
        
        return {
            "retries": due_retries,
            "total_queue_size": len(self.state["tp_retry_queue"]),
            "due_count": len(due_retries)
        }
    
    async def _handle_remove_from_retry_queue(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Remove entry from retry queue after successful TP placement.
        
        Args:
            payload: Dict with retry_entry to remove
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status response
        """
        retry_entry = payload["retry_entry"]
        
        # Remove from queue (no lock needed!)
        try:
            # Find matching entry by position_id
            position_id = retry_entry.get("position", {}).get("position_id")
            
            for i, entry in enumerate(self.state["tp_retry_queue"]):
                if entry.get("position", {}).get("position_id") == position_id:
                    removed_entry = self.state["tp_retry_queue"].pop(i)
                    
                    # Log event
                    event = Event(
                        event_id=str(uuid4()),
                        event_type=EventType.TP_RETRY_COMPLETED,
                        timestamp=time.time(),
                        correlation_id=correlation_id,
                        aggregate_id=position_id,
                        data={"removed_entry": removed_entry},
                        metadata={"actor": self.name}
                    )
                    self.event_store.append_event(event)
                    
                    log.info(f"✅ Removed from TP retry queue: {position_id}")
                    
                    return {"status": "ok", "removed": True, "queue_size": len(self.state["tp_retry_queue"])}
            
            log.warning(f"⚠️ Retry entry not found in queue: {position_id}")
            return {"status": "error", "error": "Entry not found", "removed": False}
            
        except Exception as e:
            log.error(f"❌ Failed to remove from retry queue: {e}")
            return {"status": "error", "error": str(e), "removed": False}
    
    async def _handle_get_retry_queue_size(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Get current retry queue size.
        
        Args:
            payload: Empty
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Queue size
        """
        return {"queue_size": len(self.state["tp_retry_queue"])}
    
    async def validate_state_against_exchange(
        self,
        api_client,
        product_id: str
    ) -> Dict[str, Any]:
        """
        Validate reconstructed state against actual exchange data.
        Remove stale positions/orders that don't exist on exchange anymore.
        
        CRITICAL: This fixes "weak bot memory" issue by cleaning up:
        - Pending orders that were manually cancelled
        - Positions that were manually closed
        - Stale data from previous runs
        
        Args:
            api_client: Delta Exchange API client
            product_id: Product ID to validate (e.g., "BTCUSD")
            
        Returns:
            Dict with validation results
        """
        try:
            log.info(f"🔍 Validating bot state against exchange for {product_id}...")
            
            # Convert product_id to int (API expects int, not string)
            product_id_int = int(product_id) if isinstance(product_id, str) else product_id
            
            # Get actual exchange data
            exchange_orders = await api_client.get_open_orders(product_id=product_id_int)
            exchange_positions = await api_client.get_positions(product_id=product_id_int)
            
            # Validate response types and normalize to lists
            # Delta Exchange API returns a dict (single position) when filtering by product_id
            # and a list when querying all positions
            if not isinstance(exchange_orders, list):
                log.error(f"❌ get_open_orders returned {type(exchange_orders)}: {exchange_orders}")
                exchange_orders = []
            
            if isinstance(exchange_positions, dict):
                # Single position returned - wrap in list
                exchange_positions = [exchange_positions] if exchange_positions else []
            elif not isinstance(exchange_positions, list):
                log.error(f"❌ get_positions returned {type(exchange_positions)}: {exchange_positions}")
                exchange_positions = []
            
            validation_result = {
                "pending_buy_cleared": False,
                "pending_sell_cleared": False,
                "positions_removed": 0,
                "exchange_orders_count": len(exchange_orders),
                "exchange_positions_count": len(exchange_positions)
            }
            
            log.info(f"📊 Exchange data: {len(exchange_orders)} orders, {len(exchange_positions)} positions")
            log.info(f"🔍 Bot state: pending_buy={self.state.get('pending_buy')}, pending_sell={self.state.get('pending_sell')}")
            
            # Validate pending BUY order
            if self.state['pending_buy']:
                order_id = self.state['pending_buy']['order_id']
                price = self.state['pending_buy'].get('price', 'unknown')
                
                # Check if this order exists on exchange AND matches our product_id
                matching_order = None
                for o in exchange_orders:
                    if (o.get('id') == order_id or o.get('order_id') == order_id):
                        # Found the order - check if it's for our product
                        order_product_id = o.get('product_id')
                        if order_product_id == product_id_int:
                            matching_order = o
                        else:
                            log.warning(
                                f"⚠️  Pending BUY {order_id} @ ${price} exists but is for DIFFERENT product "
                                f"({order_product_id}, expected {product_id_int}) - clearing from memory"
                            )
                        break
                
                if matching_order:
                    log.info(f"✅ Pending BUY {order_id} @ ${price} verified on exchange")
                elif not matching_order and not any(o.get('id') == order_id or o.get('order_id') == order_id for o in exchange_orders):
                    log.warning(f"⚠️  Pending BUY {order_id} @ ${price} NOT on exchange - clearing from memory")
                    self.state['pending_buy'] = None
                    validation_result['pending_buy_cleared'] = True
                elif not matching_order:
                    # Order exists but different product_id (already logged above)
                    self.state['pending_buy'] = None
                    validation_result['pending_buy_cleared'] = True
            
            # Validate pending SELL order
            if self.state['pending_sell']:
                order_id = self.state['pending_sell']['order_id']
                price = self.state['pending_sell'].get('price', 'unknown')
                
                # Check if this order exists on exchange AND matches our product_id
                matching_order = None
                for o in exchange_orders:
                    if (o.get('id') == order_id or o.get('order_id') == order_id):
                        # Found the order - check if it's for our product
                        order_product_id = o.get('product_id')
                        if order_product_id == product_id_int:
                            matching_order = o
                        else:
                            log.warning(
                                f"⚠️  Pending SELL {order_id} @ ${price} exists but is for DIFFERENT product "
                                f"({order_product_id}, expected {product_id_int}) - clearing from memory"
                            )
                        break
                
                if matching_order:
                    log.info(f"✅ Pending SELL {order_id} @ ${price} verified on exchange")
                elif not matching_order and not any(o.get('id') == order_id or o.get('order_id') == order_id for o in exchange_orders):
                    log.warning(f"⚠️  Pending SELL {order_id} @ ${price} NOT on exchange - clearing from memory")
                    self.state['pending_sell'] = None
                    validation_result['pending_sell_cleared'] = True
                elif not matching_order:
                    # Order exists but different product_id (already logged above)
                    self.state['pending_sell'] = None
                    validation_result['pending_sell_cleared'] = True
            
            # Validate open positions
            # FIX M7: Use tolerance-based matching instead of exact entry_price match
            # This handles cases where two positions at same price or slight price discrepancy
            exchange_entry_prices = [
                float(p.get('entry_price', 0)) 
                for p in exchange_positions
            ]
            
            valid_tranches = []
            removed_count = 0
            price_tolerance = 1.0  # $1 tolerance for entry price matching
            
            # Track which exchange prices have been claimed (prevents double-counting)
            claimed_exchange_prices = []
            
            for tranche in self.state['open_tranches']:
                entry_price = tranche.get('entry_price')
                
                # Find matching exchange price (with tolerance, unclaimed)
                matched = False
                for i, ex_price in enumerate(exchange_entry_prices):
                    if i not in claimed_exchange_prices and abs(entry_price - ex_price) < price_tolerance:
                        matched = True
                        claimed_exchange_prices.append(i)
                        break
                
                if matched:
                    valid_tranches.append(tranche)
                else:
                    log.warning(
                        f"⚠️  Position @ ${entry_price:,.0f} NOT on exchange - removing from memory"
                    )
                    removed_count += 1
            
            if removed_count > 0:
                self.state['open_tranches'] = valid_tranches
                # Update position index
                self._position_index = {
                    p['position_id']: p 
                    for p in valid_tranches
                }
                validation_result['positions_removed'] = removed_count
            
            # CRITICAL FIX NOV 19: Remove positions with None IDs
            broken_positions = [p for p in valid_tranches if not p.get('position_id') or str(p.get('position_id')).lower() == 'none']
            if broken_positions:
                log.critical(f"🚨 Found {len(broken_positions)} positions with None IDs - REMOVING THEM")
                for broken_pos in broken_positions:
                    log.critical(f"   Removing broken position: {broken_pos}")
                    valid_tranches.remove(broken_pos)
                    removed_count += 1
                
                # Update state and index
                self.state['open_tranches'] = valid_tranches
                self._position_index = {
                    p['position_id']: p 
                    for p in valid_tranches
                }
                validation_result['broken_positions_removed'] = len(broken_positions)
            
            # Log summary
            log.info(
                f"✅ State validation complete: "
                f"{len(valid_tranches)} positions kept, "
                f"{removed_count} removed, "
                f"pending_buy={'cleared' if validation_result['pending_buy_cleared'] else 'ok'}, "
                f"pending_sell={'cleared' if validation_result['pending_sell_cleared'] else 'ok'}"
            )
            
            return validation_result
            
        except Exception as e:
            log.error(f"❌ State validation error: {e}")
            return {
                "error": str(e),
                "pending_buy_cleared": False,
                "pending_sell_cleared": False,
                "positions_removed": 0
            }

    async def _handle_validate_single_pending_order(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Validate that single pending order rule is maintained.
        
        This checks:
        1. At most one pending_buy exists
        2. At most one pending_sell exists
        3. Pending orders match expected state
        
        Args:
            payload: Contains 'exchange_orders' list from order actor
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Validation result with any violations found
        """
        try:
            exchange_orders = payload.get("exchange_orders", [])
            violations = []
            
            # Count pending orders by side (excluding reduce_only TPs)
            pending_buys = []
            pending_sells = []
            
            for order in exchange_orders:
                if order.get("state") == "open" and not order.get("reduce_only", False):
                    if order.get("side") == "buy":
                        pending_buys.append({
                            "order_id": order.get("id"),
                            "price": float(order.get("limit_price", 0)),
                            "size": float(order.get("size", 0))
                        })
                    elif order.get("side") == "sell":
                        pending_sells.append({
                            "order_id": order.get("id"),
                            "price": float(order.get("limit_price", 0)),
                            "size": float(order.get("size", 0))
                        })
            
            # Check SINGLE PENDING ORDER RULE violations
            if len(pending_buys) > 1:
                violations.append({
                    "type": "multiple_pending_buys",
                    "count": len(pending_buys),
                    "orders": pending_buys,
                    "message": f"VIOLATION: {len(pending_buys)} pending BUY orders found (should be max 1)"
                })
            
            if len(pending_sells) > 1:
                violations.append({
                    "type": "multiple_pending_sells", 
                    "count": len(pending_sells),
                    "orders": pending_sells,
                    "message": f"VIOLATION: {len(pending_sells)} pending SELL orders found (should be max 1)"
                })
            
            # Check state consistency
            tracked_buy = self.state.get("pending_buy")
            tracked_sell = self.state.get("pending_sell")
            
            if tracked_buy and len(pending_buys) == 0:
                violations.append({
                    "type": "tracked_buy_missing",
                    "tracked": tracked_buy,
                    "message": "Bot tracks pending BUY but none found on exchange"
                })
            
            if tracked_sell and len(pending_sells) == 0:
                violations.append({
                    "type": "tracked_sell_missing",
                    "tracked": tracked_sell,
                    "message": "Bot tracks pending SELL but none found on exchange"
                })
            
            # Log results
            if violations:
                log.warning(f"⚠️  SINGLE PENDING ORDER RULE VIOLATIONS DETECTED:")
                for violation in violations:
                    log.warning(f"   - {violation['message']}")
            else:
                log.debug("✅ Single pending order rule validation passed")
            
            return {
                "status": "ok",
                "violations_found": len(violations),
                "violations": violations,
                "pending_buys_count": len(pending_buys),
                "pending_sells_count": len(pending_sells),
                "rule_compliant": len(violations) == 0
            }
            
        except Exception as e:
            log.error(f"❌ Single pending order validation error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "violations_found": 0,
                "rule_compliant": False
            }

    async def _handle_update_position_tp(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Update TP order information for an existing position.
        Used by reconciliation system to fix position state.
        
        Args:
            payload: Dict with position_id, tp_order_id, and optionally tp_price
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status response
        """
        try:
            position_id = payload["position_id"]
            tp_order_id = payload["tp_order_id"]
            tp_price = payload.get("tp_price")
            
            # Find position in state
            position = self._position_index.get(position_id)
            if not position:
                log.warning(f"Position not found for TP update: {position_id}")
                return {"status": "error", "error": "Position not found"}
            
            # Update TP information
            old_tp_order_id = position.get("tp_order_id")
            position["tp_order_id"] = tp_order_id
            
            if tp_price:
                position["tp_price"] = tp_price
            
            log.info(f"Updated position {position_id} TP: {old_tp_order_id} -> {tp_order_id}")
            
            # Log event for audit trail
            event = Event(
                event_id=str(uuid4()),
                event_type=EventType.POSITION_UPDATED,
                timestamp=time.time(),
                correlation_id=correlation_id,
                aggregate_id=position_id,
                data={
                    "position_id": position_id,
                    "old_tp_order_id": old_tp_order_id,
                    "new_tp_order_id": tp_order_id,
                    "tp_price": tp_price,
                    "updated_by": "reconciliation"
                },
                metadata={"actor": self.name, "operation": "tp_update"}
            )
            self.event_store.append_event(event)
            
            return {"status": "ok", "position_id": position_id}
            
        except Exception as e:
            log.error(f"❌ Error updating position TP: {e}")
            return {"status": "error", "error": str(e)}

    # State.json file export removed - WebUI now reads directly from SQL event store database
    # All state is persisted via EventStore.append_event() calls above
