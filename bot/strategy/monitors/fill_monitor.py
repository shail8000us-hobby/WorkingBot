import asyncio
import time
from typing import Dict, Any, Optional, Callable
from loguru import logger as log

from bot.strategy.monitors.base_monitor import BaseMonitor
from bot.api.async_delta_client import AsyncDeltaClient
from bot.strategy.modules.event_store import EventStore


class FillMonitor(BaseMonitor):
    
    def __init__(
        self,
        api_client: AsyncDeltaClient,
        event_store: EventStore,
        product_id: int,
        check_interval: int = 30,
        verification_delay: int = 30,
        max_age: int = 86400,
        missed_fill_callback: Optional[Callable] = None
    ):
        super().__init__("FillMonitor")
        self.api_client = api_client
        self.event_store = event_store
        self.product_id = product_id
        self.check_interval = check_interval
        self.verification_delay = verification_delay
        self.max_age = max_age
        self.missed_fill_callback = missed_fill_callback
        
        self._tracked_orders: Dict[str, Dict[str, Any]] = {}
        self._verified_orders: Dict[str, float] = {}
        self._max_verified_history = 1000
        
        self._fills_detected = 0
        self._verifications_performed = 0
        self._api_calls = 0
    
    def track_order(
        self,
        order_id: str,
        side: str,
        price: float,
        size: int,
        placed_at: Optional[float] = None
    ) -> None:
        if placed_at is None:
            placed_at = time.time()
        
        self._tracked_orders[str(order_id)] = {
            "order_id": order_id,
            "side": side,
            "price": price,
            "size": size,
            "placed_at": placed_at,
            "last_checked": 0,
            "check_count": 0,
            "status": "pending"
        }
        
        log.debug(f"[{self.name}] Tracking order {order_id}: {side} @ ${price}")
    
    def mark_filled(self, order_id: str, source: str = "websocket") -> None:
        order_id_str = str(order_id)
        
        if order_id_str in self._tracked_orders:
            self._tracked_orders[order_id_str]["status"] = "filled"
            self._tracked_orders[order_id_str]["filled_at"] = time.time()
            self._tracked_orders[order_id_str]["source"] = source
            
            self._verified_orders[order_id_str] = time.time()
            
            log.debug(f"[{self.name}] Order {order_id} marked as filled (source: {source})")
    
    def mark_cancelled(self, order_id: str) -> None:
        order_id_str = str(order_id)
        
        if order_id_str in self._tracked_orders:
            self._tracked_orders[order_id_str]["status"] = "cancelled"
            self._tracked_orders[order_id_str]["cancelled_at"] = time.time()
            
            log.debug(f"[{self.name}] Order {order_id} marked as cancelled")
    
    async def _execute(self) -> None:
        current_time = time.time()
        
        orders_to_verify = []
        for order_id, order_data in list(self._tracked_orders.items()):
            age = current_time - order_data["placed_at"]
            time_since_check = current_time - order_data["last_checked"]
            
            if order_data["status"] == "pending":
                if age >= self.verification_delay and time_since_check >= self.check_interval:
                    orders_to_verify.append(order_id)
        
        if orders_to_verify:
            log.info(f"[{self.name}] Verifying {len(orders_to_verify)} orders")
            
            for order_id in orders_to_verify:
                await self._verify_order(order_id)
                await asyncio.sleep(0.1)
        
        self._cleanup_old_orders(current_time)
        
        await asyncio.sleep(self.check_interval)
    
    async def _verify_order(self, order_id: str) -> None:
        try:
            order_data = self._tracked_orders.get(order_id)
            if not order_data:
                return
            
            order_data["last_checked"] = time.time()
            order_data["check_count"] += 1
            self._verifications_performed += 1
            
            log.debug(f"[{self.name}] Verifying order {order_id} (check #{order_data['check_count']})")
            
            order_info = await self.api_client.get_order(order_id)
            self._api_calls += 1
            
            if not order_info:
                log.warning(f"[{self.name}] Could not get order info for {order_id}")
                return
            
            state = order_info.get("state", "unknown")
            unfilled_size = order_info.get("unfilled_size", 0)
            
            # NOV 19: Comprehensive state interpretation
            # Interpret state using same logic as bot's _interpret_order_state
            if state == "filled":
                status = "FILLED"
            elif state == "closed":
                status = "FILLED" if unfilled_size == 0 else "CANCELLED"
            elif state == "partial_fill":
                status = "FILLED" if unfilled_size == 0 else "PENDING"
            elif state in ["cancelled", "rejected", "expired"]:
                status = "CANCELLED"
            elif state == "open":
                status = "PENDING"
            else:
                status = "UNKNOWN"
            
            log.debug(f"[{self.name}] Order {order_id} state: {state}, unfilled: {unfilled_size}, status: {status}")
            
            if status == "FILLED":
                await self._handle_missed_fill(order_id, order_info, order_data)
            
            elif status == "CANCELLED":
                log.info(f"[{self.name}] Order {order_id} was cancelled/rejected/expired (state: {state})")
                self.mark_cancelled(order_id)
            
            elif status == "PENDING":
                log.debug(f"[{self.name}] Order {order_id} still pending")
            
            elif status == "UNKNOWN":
                log.warning(f"[{self.name}] Order {order_id} unknown state: {state}")
        
        except Exception as e:
            log.error(f"[{self.name}] Error verifying order {order_id}: {e}")
    
    async def _handle_missed_fill(
        self,
        order_id: str,
        order_info: Dict[str, Any],
        order_data: Dict[str, Any]
    ) -> None:
        if order_id in self._verified_orders:
            log.debug(f"[{self.name}] Order {order_id} already processed")
            return
        
        self._fills_detected += 1
        
        fill_price = float(order_info.get("average_fill_price") or order_data["price"])
        fill_size = int(order_info.get("size", order_data["size"]))
        side = order_data["side"]
        
        age = time.time() - order_data["placed_at"]
        
        log.warning(f"🔔 [{self.name}] MISSED FILL DETECTED!")
        log.warning(f"   Order: {order_id}")
        log.warning(f"   Side: {side}, Price: ${fill_price:,.2f}, Size: {fill_size}")
        log.warning(f"   Age: {age:.1f}s (placed {age:.1f}s ago)")
        log.warning(f"   State: {order_info.get('state')}, Unfilled: {order_info.get('unfilled_size', 0)}")
        
        self.mark_filled(order_id, source="fill_monitor")
        
        if self.missed_fill_callback:
            fill_data = {
                "id": order_id,  # Fill Monitor uses order_id, but callback expects 'id'
                "order_id": order_id,
                "side": side,
                "price": fill_price,  # Use 'price' for consistency with WebSocket fills
                "fill_price": fill_price,
                "size": fill_size,  # Use 'size' for consistency
                "fill_size": fill_size,
                "is_complete": True,
                "state": "filled",  # Add state for compatibility
                "unfilled_size": 0,  # Filled completely
                "_detected_via": "fill_monitor",
                "_detection_delay": age
            }
            
            try:
                await self.missed_fill_callback(fill_data)  # Pass only fill_data, not order_id
                log.info(f"[{self.name}] Missed fill processed successfully")
            except Exception as e:
                log.error(f"[{self.name}] Error processing missed fill: {e}")
    
    def _cleanup_old_orders(self, current_time: float) -> None:
        orders_to_remove = []
        
        for order_id, order_data in self._tracked_orders.items():
            age = current_time - order_data["placed_at"]
            
            if order_data["status"] in ["filled", "cancelled"] and age > 3600:
                orders_to_remove.append(order_id)
            
            elif age > self.max_age:
                log.warning(f"[{self.name}] Order {order_id} too old ({age:.0f}s), removing from tracking")
                orders_to_remove.append(order_id)
        
        for order_id in orders_to_remove:
            del self._tracked_orders[order_id]
        
        verified_to_remove = []
        for order_id, timestamp in self._verified_orders.items():
            if current_time - timestamp > 3600:
                verified_to_remove.append(order_id)
        
        for order_id in verified_to_remove:
            del self._verified_orders[order_id]
        
        if len(self._verified_orders) > self._max_verified_history:
            sorted_orders = sorted(self._verified_orders.items(), key=lambda x: x[1])
            to_remove = len(self._verified_orders) - self._max_verified_history
            for order_id, _ in sorted_orders[:to_remove]:
                del self._verified_orders[order_id]
    
    def get_metrics(self) -> Dict[str, Any]:
        return {
            "tracked_orders": len(self._tracked_orders),
            "verified_orders": len(self._verified_orders),
            "fills_detected": self._fills_detected,
            "verifications_performed": self._verifications_performed,
            "api_calls": self._api_calls,
            "pending_orders": sum(1 for o in self._tracked_orders.values() if o["status"] == "pending"),
            "filled_orders": sum(1 for o in self._tracked_orders.values() if o["status"] == "filled"),
            "cancelled_orders": sum(1 for o in self._tracked_orders.values() if o["status"] == "cancelled")
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        base_health = super().get_health_status()
        base_health.update({
            "metrics": self.get_metrics()
        })
        return base_health
