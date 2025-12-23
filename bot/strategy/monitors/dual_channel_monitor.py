import asyncio
import time
from typing import Dict, Any, Optional, Callable
from loguru import logger as log

from bot.strategy.monitors.base_monitor import BaseMonitor
from bot.api.async_delta_client import AsyncDeltaClient
from bot.strategy.actors.position_actor import PositionManagerActor


class DualChannelMonitor(BaseMonitor):
    """
    Dual-channel fill detection system.
    
    Monitors fills through BOTH WebSocket and REST API simultaneously:
    - Primary: WebSocket (real-time, low latency)
    - Secondary: REST polling (backup, every 10s)
    
    Features:
    - Deduplication (prevents double-processing)
    - Source tracking (WebSocket vs REST)
    - WebSocket health monitoring
    - Automatic failover
    """
    
    def __init__(
        self,
        api_client: AsyncDeltaClient,
        position_actor: PositionManagerActor,
        product_id: int,
        rest_poll_interval: int = 10,
        max_fill_history: int = 1000,
        missed_fill_callback: Optional[Callable] = None
    ):
        super().__init__("DualChannelMonitor")
        self.api_client = api_client
        self.position_actor = position_actor
        self.product_id = product_id
        self.rest_poll_interval = rest_poll_interval
        self.max_fill_history = max_fill_history
        self.missed_fill_callback = missed_fill_callback
        
        # Deduplication: Track processed fills
        self._processed_fills: Dict[str, Dict[str, Any]] = {}
        
        # Metrics
        self._websocket_fills = 0
        self._rest_fills = 0
        self._duplicates_prevented = 0
        self._websocket_misses = 0
        
        # Polling state
        self._last_poll_time = 0
    
    def mark_fill_processed(self, order_id: str, source: str) -> None:
        """
        Mark a fill as processed to prevent duplicate processing.
        
        Args:
            order_id: Order ID that was filled
            source: Source of detection ("websocket" or "rest")
        """
        order_id_str = str(order_id)
        
        self._processed_fills[order_id_str] = {
            "order_id": order_id,
            "source": source,
            "timestamp": time.time()
        }
        
        # Track metrics
        if source == "websocket":
            self._websocket_fills += 1
        elif source == "rest":
            self._rest_fills += 1
            # If REST detected it, WebSocket missed it
            self._websocket_misses += 1
        
        log.debug(f"[{self.name}] Fill processed: {order_id} (source: {source})")
        
        # Cleanup old entries
        self._cleanup_processed_fills()
    
    def is_fill_processed(self, order_id: str) -> tuple[bool, Optional[str]]:
        """
        Check if a fill has already been processed.
        
        Args:
            order_id: Order ID to check
            
        Returns:
            Tuple of (is_processed, source)
        """
        order_id_str = str(order_id)
        
        if order_id_str in self._processed_fills:
            source = self._processed_fills[order_id_str]["source"]
            return (True, source)
        
        return (False, None)
    
    async def _execute(self) -> None:
        """Execute REST polling loop."""
        current_time = time.time()
        
        # Check if it's time to poll
        if current_time - self._last_poll_time < self.rest_poll_interval:
            await asyncio.sleep(1)
            return
        
        self._last_poll_time = current_time
        
        # Poll pending orders
        await self._poll_pending_orders()
        
        await asyncio.sleep(1)
    
    async def _poll_pending_orders(self) -> None:
        """Poll pending orders via REST API."""
        try:
            # Get pending orders from position actor
            state_queue = asyncio.Queue()
            await self.position_actor.mailbox.put(
                {"type": "GET_STATE", "payload": {}, "reply_to": state_queue}
            )
            
            state = await asyncio.wait_for(state_queue.get(), timeout=5.0)
            
            # Check pending buy
            if state.get("pending_buy"):
                order_id = state["pending_buy"].get("order_id")
                if order_id:
                    await self._check_order_via_rest(order_id, "buy")
            
            # Check pending sell
            if state.get("pending_sell"):
                order_id = state["pending_sell"].get("order_id")
                if order_id:
                    await self._check_order_via_rest(order_id, "sell")
        
        except asyncio.TimeoutError:
            log.warning(f"[{self.name}] Timeout getting state from position actor")
        except Exception as e:
            log.error(f"[{self.name}] Error polling pending orders: {e}")
    
    async def _check_order_via_rest(self, order_id: str, expected_side: str) -> None:
        """
        Check order status via REST API.
        
        Args:
            order_id: Order ID to check
            expected_side: Expected side (buy/sell)
        """
        try:
            # Check if already processed
            is_processed, source = self.is_fill_processed(order_id)
            if is_processed:
                log.debug(f"[{self.name}] Order {order_id} already processed by {source}")
                return
            
            # Query exchange
            order_info = await self.api_client.get_order(order_id)
            
            if not order_info:
                return
            
            state = order_info.get("state", "unknown")
            unfilled_size = order_info.get("unfilled_size", 0)
            
            # Interpret state (same logic as bot's helper)
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
            
            # If filled, check if WebSocket already processed it
            if status == "FILLED":
                is_processed, source = self.is_fill_processed(order_id)
                
                if is_processed:
                    # Already processed by WebSocket - good!
                    self._duplicates_prevented += 1
                    log.debug(f"[{self.name}] Duplicate prevented: {order_id} already processed by {source}")
                else:
                    # WebSocket missed it - REST detected it!
                    log.warning(f"🔔 [{self.name}] FILL DETECTED via REST (WebSocket missed it!)")
                    log.warning(f"   Order: {order_id}")
                    log.warning(f"   Side: {expected_side}")
                    log.warning(f"   State: {state}, Unfilled: {unfilled_size}")
                    
                    # Mark as processed by REST
                    self.mark_fill_processed(order_id, source="rest")
                    
                    # Trigger callback
                    if self.missed_fill_callback:
                        fill_data = {
                            "order_id": order_id,
                            "side": expected_side,
                            "fill_price": float(order_info.get("average_fill_price", 0)),
                            "fill_size": int(order_info.get("size", 0)),
                            "is_complete": True,
                            "_detected_via": "dual_channel_rest"
                        }
                        
                        await self.missed_fill_callback(order_id, fill_data)
        
        except Exception as e:
            log.error(f"[{self.name}] Error checking order {order_id}: {e}")
    
    def _cleanup_processed_fills(self) -> None:
        """Cleanup old processed fills."""
        current_time = time.time()
        max_age = 3600  # 1 hour
        
        to_remove = []
        for order_id, data in self._processed_fills.items():
            age = current_time - data["timestamp"]
            if age > max_age:
                to_remove.append(order_id)
        
        for order_id in to_remove:
            del self._processed_fills[order_id]
        
        # Also enforce max history size
        if len(self._processed_fills) > self.max_fill_history:
            sorted_fills = sorted(
                self._processed_fills.items(),
                key=lambda x: x[1]["timestamp"]
            )
            to_remove_count = len(self._processed_fills) - self.max_fill_history
            for order_id, _ in sorted_fills[:to_remove_count]:
                del self._processed_fills[order_id]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get dual-channel metrics."""
        total_fills = self._websocket_fills + self._rest_fills
        websocket_rate = (self._websocket_fills / total_fills * 100) if total_fills > 0 else 0
        rest_rate = (self._rest_fills / total_fills * 100) if total_fills > 0 else 0
        
        return {
            "websocket_fills": self._websocket_fills,
            "rest_fills": self._rest_fills,
            "total_fills": total_fills,
            "websocket_rate": websocket_rate,
            "rest_rate": rest_rate,
            "websocket_misses": self._websocket_misses,
            "duplicates_prevented": self._duplicates_prevented,
            "processed_fills_tracked": len(self._processed_fills)
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status with metrics."""
        base_health = super().get_health_status()
        base_health.update({
            "metrics": self.get_metrics()
        })
        return base_health
