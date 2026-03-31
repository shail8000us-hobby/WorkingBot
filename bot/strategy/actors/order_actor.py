"""
Order Manager Actor for handling order placement and management.
Uses async Delta client for all order operations.
"""

import asyncio
import time
from typing import Dict, Any, Optional
from uuid import uuid4

from loguru import logger as log

# Human-readable logging for traders
from bot.utils.human_logger import human_log

from bot.strategy.actors.base_actor import Actor
from bot.api.async_delta_client import AsyncDeltaClient
from bot.strategy.modules.event_store import EventStore, Event, EventType


class OrderManagerActor(Actor):
    """
    Actor for managing order placement and cancellation.
    
    Features:
    - Async order placement with retry
    - Order validation before placement
    - Event logging for audit trail
    - Automatic retry with exponential backoff
    """
    
    def __init__(
        self,
        api_client: AsyncDeltaClient,
        event_store: EventStore,
        symbol: str = "BTCUSD",
        product_id: int = 27,
        max_retries: int = 3,
        tag_prefix: str = "GBOT_",
        post_only_mode: str = "auto"
    ):
        """
        Initialize order manager actor.
        
        Args:
            api_client: Async Delta API client
            event_store: Event store for persistence
            symbol: Trading symbol
            product_id: Delta Exchange product ID
            max_retries: Maximum retry attempts
            tag_prefix: Order tag prefix for identification
            post_only_mode: Post-only mode (auto/always/never)
        """
        super().__init__("OrderManager")
        self.api_client = api_client
        self.event_store = event_store
        self.symbol = symbol
        self.product_id = product_id
        self.max_retries = max_retries
        self.tag_prefix = tag_prefix
        self.post_only_mode = post_only_mode
        
        # Order tracking
        self._active_orders: Dict[str, Dict] = {}
        self._order_history: list = []
        self._max_history = 100
        
        # Deduplication tracking
        self._last_order_timestamps: Dict[str, float] = {}
        
        # Metrics
        self._total_orders_placed = 0
        self._total_orders_cancelled = 0
        self._total_order_failures = 0
    
    def _generate_order_tag(self, side: str, price: float) -> str:
        """
        Generate order tag for identification.
        
        Format: {prefix}{side}_{price}_{timestamp}
        Example: GBOT_BUY_99000_1699876543
        
        Args:
            side: Order side (buy/sell)
            price: Order price
            
        Returns:
            Order tag string
        """
        timestamp = int(time.time())
        price_int = int(price)
        return f"{self.tag_prefix}{side.upper()}_{price_int}_{timestamp}"
    
    def _should_use_post_only(self, side: str, order_type: str = "entry") -> bool:
        """
        Determine if order should be post-only.
        
        Args:
            side: Order side (buy/sell)
            order_type: Order type (entry/tp)
            
        Returns:
            True if post-only, False otherwise
        """
        if self.post_only_mode == "always":
            return True
        elif self.post_only_mode == "never":
            return False
        else:  # "auto"
            # BUY orders: maker (post-only=True)
            # TP/SELL orders: taker (post-only=False)
            return side.lower() == "buy" and order_type == "entry"
    
    async def _handle_place_buy(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Place BUY order with retry.
        
        Args:
            payload: Order details (price, size, post_only optional)
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Order placement result
        """
        price = payload["price"]
        size = payload["size"]
        order_type = payload.get("order_type", "limit")  # "limit" or "market"
        
        # =====================================================================
        # CRITICAL FIX (Dec 12, 2025): Prevent duplicate BUY orders at same price
        # This prevents race conditions where two sagas try to place orders simultaneously
        # =====================================================================
        
        # Check 1: Timestamp-based deduplication (prevent rapid-fire duplicates)
        current_time = time.time()
        last_buy_key = f"buy_{int(price)}"
        
        if not hasattr(self, '_last_order_timestamps'):
            self._last_order_timestamps = {}
        
        last_buy_time = self._last_order_timestamps.get(last_buy_key, 0)
        if current_time - last_buy_time < 5.0:  # 5 second cooldown per price level
            log.warning(f"⚠️ [DEDUP] BUY @ ${price:,.0f} blocked - duplicate within 5s (last: {current_time - last_buy_time:.1f}s ago)")
            return {"status": "skipped", "reason": "duplicate_within_cooldown", "price": price}
        
        # Check 2: Query exchange for existing order at this price
        try:
            existing_orders = await self.api_client.get_open_orders(self.product_id)
            for order in existing_orders:
                if order.get("side") == "buy" and order.get("state") == "open":
                    order_price = float(order.get("limit_price", 0))
                    is_reduce_only = order.get("reduce_only", False)
                    
                    # Skip TP orders
                    if is_reduce_only:
                        continue
                    
                    # Check if order already exists at this price
                    if abs(order_price - price) < 0.01:
                        log.warning(f"⚠️ [DEDUP] BUY @ ${price:,.0f} already exists on exchange (order #{order.get('id')}) - skipping")
                        return {"status": "skipped", "reason": "order_exists_on_exchange", "existing_order_id": order.get("id")}
        except Exception as e:
            log.warning(f"⚠️ [DEDUP] Could not verify exchange orders: {e} - proceeding with placement")
        
        # =====================================================================
        
        # Validate order BEFORE setting timestamp (prevent failed validations from blocking future orders)
        validation = self._validate_order(price, size, "buy")
        if validation["status"] == "error":
            log.error(f"Order validation failed: {validation['error']}")
            return validation
        
        # Mark timestamp for this price level AFTER validation passes
        self._last_order_timestamps[last_buy_key] = current_time
        
        # Generate order tag
        order_tag = self._generate_order_tag("buy", price)
        
        # Determine post-only mode (allow override, but NEVER for market orders)
        if order_type == "market":
            post_only = False  # Market orders cannot be post-only
        else:
            post_only = payload.get("post_only", self._should_use_post_only("buy", "entry"))
        
        # Retry loop
        for attempt in range(self.max_retries):
            try:
                log.info(f"Placing BUY {order_type.upper()} order: {size} @ {price} (tag: {order_tag}, post_only: {post_only}, attempt {attempt + 1})")
                
                # Prepare order params based on type
                if order_type == "market":
                    result = await self.api_client.place_order(
                        product_id=self.product_id,
                        side="buy",
                        size=size,
                        order_type="market_order",
                        client_order_id=order_tag,
                        post_only=False
                    )
                else:
                    result = await self.api_client.place_order(
                        product_id=self.product_id,
                        side="buy",
                        price=price,
                        size=size,
                        order_type="limit_order",
                        post_only=post_only,
                        client_order_id=order_tag
                    )
                
                # Extract order ID from Delta Exchange response structure
                order_id = result.get("result", {}).get("id") or result.get("id") or result.get("order_id")
                if not order_id:
                    raise ValueError(f"No order ID in response: {result}")
                
                # Track order
                order_data = {
                    "order_id": order_id,
                    "side": "buy",
                    "price": price,
                    "size": size,
                    "status": "pending",
                    "placed_at": time.time(),
                    "correlation_id": correlation_id,
                    "tag": order_tag,
                    "post_only": post_only
                }
                self._active_orders[order_id] = order_data
                self._total_orders_placed += 1
                
                # Log event
                event = Event(
                    event_id=str(uuid4()),
                    event_type=EventType.ORDER_PLACED,
                    timestamp=time.time(),
                    correlation_id=correlation_id,
                    aggregate_id=order_id,
                    data=order_data,
                    metadata={"actor": self.name, "attempt": attempt + 1}
                )
                self.event_store.append_event(event)
                
                # Enhanced logging (matching old GridBot style)
                log.info(f"✅ BUY order placed: {order_id}")
                log.info(f"   📍 Entry: ${price:,.0f} | Size: {size} | Post-Only: {post_only}")
                human_log.order_placed(order_id, "BUY", price)  # Trader-friendly
                
                return {"status": "ok", "order_id": order_id, "result": result}
            
            except Exception as e:
                log.error(f"Order placement failed (attempt {attempt + 1}): {e}")
                human_log.api_error("order_placement", str(e))  # Trader-friendly alert
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    log.info(f"Retrying in {wait_time}s...")
                    human_log.retry_attempt("order placement", attempt + 2)  # Trader-friendly
                    await asyncio.sleep(wait_time)
                else:
                    self._total_order_failures += 1
                    
                    # Log failure event
                    event = Event(
                        event_id=str(uuid4()),
                        event_type=EventType.ORDER_FAILED,
                        timestamp=time.time(),
                        correlation_id=correlation_id,
                        aggregate_id=order_tag,
                        data={
                            "side": "buy",
                            "price": price,
                            "size": size,
                            "error": str(e)
                        },
                        metadata={"actor": self.name, "attempts": self.max_retries}
                    )
                    self.event_store.append_event(event)
                    
                    return {"status": "error", "error": str(e)}
        
        return {"status": "error", "error": "Max retries exceeded"}
    
    async def _handle_place_sell(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Place SELL order with retry.
        
        Args:
            payload: Order details (price, size, post_only optional)
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Order placement result
        """
        price = payload["price"]
        size = payload["size"]
        order_purpose = payload.get("order_purpose", "tp")  # "tp", "entry", "recovery"
        order_type = payload.get("order_type", "limit")  # "limit" or "market"
        
        # =====================================================================
        # CRITICAL FIX (Dec 12, 2025): Prevent duplicate ENTRY SELL orders (SHORT mode)
        # Only applies to entry orders, not TP orders
        # =====================================================================
        if order_purpose == "entry":
            current_time = time.time()
            last_sell_key = f"sell_{int(price)}"
            
            if not hasattr(self, '_last_order_timestamps'):
                self._last_order_timestamps = {}
            
            last_sell_time = self._last_order_timestamps.get(last_sell_key, 0)
            if current_time - last_sell_time < 5.0:  # 5 second cooldown per price level
                log.warning(f"⚠️ [DEDUP] SELL ENTRY @ ${price:,.0f} blocked - duplicate within 5s")
                return {"status": "skipped", "reason": "duplicate_within_cooldown", "price": price}
            
            # Check exchange for existing entry SELL order at this price
            try:
                existing_orders = await self.api_client.get_open_orders(self.product_id)
                for order in existing_orders:
                    if order.get("side") == "sell" and order.get("state") == "open":
                        order_price = float(order.get("limit_price", 0))
                        is_reduce_only = order.get("reduce_only", False)
                        
                        # Skip TP orders (reduce_only=True)
                        if is_reduce_only:
                            continue
                        
                        # Check if entry order already exists at this price
                        if abs(order_price - price) < 0.01:
                            log.warning(f"⚠️ [DEDUP] SELL ENTRY @ ${price:,.0f} already exists (order #{order.get('id')}) - skipping")
                            return {"status": "skipped", "reason": "order_exists_on_exchange", "existing_order_id": order.get("id")}
            except Exception as e:
                log.warning(f"⚠️ [DEDUP] Could not verify exchange orders: {e} - proceeding with placement")
        # =====================================================================
        
        # Validate order BEFORE setting timestamp (prevent failed validations from blocking future orders)
        validation = self._validate_order(price, size, "sell")
        if validation["status"] == "error":
            log.error(f"Order validation failed: {validation['error']}")
            return validation
        
        # Mark timestamp AFTER validation passes (only for entry orders)
        if order_purpose == "entry":
            self._last_order_timestamps[last_sell_key] = current_time
        
        # Generate order tag
        order_tag = self._generate_order_tag("sell", price)
        
        # Determine post-only mode (NEVER for market orders)
        if order_type == "market":
            post_only = False
        else:
            post_only = payload.get("post_only", self._should_use_post_only("sell", order_purpose))
        
        # Retry loop
        for attempt in range(self.max_retries):
            try:
                log.info(f"Placing SELL {order_type.upper()} order: {size} @ {price} (tag: {order_tag}, post_only: {post_only}, attempt {attempt + 1})")
                
                # Prepare order params based on type
                if order_type == "market":
                    result = await self.api_client.place_order(
                        product_id=self.product_id,
                        side="sell",
                        size=size,
                        order_type="market_order",
                        client_order_id=order_tag,
                        post_only=False
                    )
                else:
                    result = await self.api_client.place_order(
                        product_id=self.product_id,
                        side="sell",
                        price=price,
                        size=size,
                        order_type="limit_order",
                        post_only=post_only,
                        client_order_id=order_tag
                    )
                
                # Extract order ID from Delta Exchange response structure
                order_id = result.get("result", {}).get("id") or result.get("id") or result.get("order_id")
                if not order_id:
                    raise ValueError(f"No order ID in response: {result}")
                
                # Track order
                order_data = {
                    "order_id": order_id,
                    "side": "sell",
                    "price": price,
                    "size": size,
                    "status": "pending",
                    "placed_at": time.time(),
                    "correlation_id": correlation_id,
                    "tag": order_tag,
                    "post_only": post_only,
                    "order_type": order_type
                }
                self._active_orders[order_id] = order_data
                self._total_orders_placed += 1
                
                # Log event
                event = Event(
                    event_id=str(uuid4()),
                    event_type=EventType.ORDER_PLACED,
                    timestamp=time.time(),
                    correlation_id=correlation_id,
                    aggregate_id=order_id,
                    data=order_data,
                    metadata={"actor": self.name, "attempt": attempt + 1}
                )
                self.event_store.append_event(event)
                
                log.info(f"✅ SELL order placed: {order_id}")
                human_log.order_placed(order_id, "SELL", price)  # Trader-friendly
                
                return {"status": "ok", "order_id": order_id, "result": result}
            
            except Exception as e:
                log.error(f"Order placement failed (attempt {attempt + 1}): {e}")
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    log.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    self._total_order_failures += 1
                    
                    # Log failure event
                    event = Event(
                        event_id=str(uuid4()),
                        event_type=EventType.ORDER_FAILED,
                        timestamp=time.time(),
                        correlation_id=correlation_id,
                        aggregate_id=order_tag,
                        data={
                            "side": "sell",
                            "price": price,
                            "size": size,
                            "error": str(e)
                        },
                        metadata={"actor": self.name, "attempts": self.max_retries}
                    )
                    self.event_store.append_event(event)
                    
                    return {"status": "error", "error": str(e)}
        
        return {"status": "error", "error": "Max retries exceeded"}
    
    async def _handle_place_tp(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Place Take Profit (TP) order.
        
        Args:
            payload: TP details (price, size, position_id)
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            TP order placement result
        """
        price = payload["price"]
        size = payload["size"]
        position_id = payload.get("position_id", "")
        # LONG mode TPs are SELL (close long); SHORT mode TPs are BUY (close short)
        side = payload.get("side", "sell")

        log.info(f"Placing TP {side.upper()} order for position {position_id}: {size} @ {price}")

        # Validate order
        validation = self._validate_order(price, size, side)
        if validation["status"] == "error":
            log.error(f"TP order validation failed: {validation['error']}")
            return validation

        # Retry loop
        for attempt in range(self.max_retries):
            try:
                result = await self.api_client.place_order(
                    product_id=self.product_id,
                    side=side,
                    price=price,
                    size=size,
                    post_only=False,  # TP orders should not be post-only
                    reduce_only=True   # TP orders should be reduce-only
                )

                # Extract order ID from Delta Exchange response structure
                order_id = result.get("result", {}).get("id") or result.get("id") or result.get("order_id")
                if not order_id:
                    raise ValueError(f"No order ID in response: {result}")

                # Track order
                order_data = {
                    "order_id": order_id,
                    "side": side,
                    "type": "tp",
                    "price": price,
                    "size": size,
                    "position_id": position_id,
                    "status": "pending",
                    "placed_at": time.time(),
                    "correlation_id": correlation_id
                }
                self._active_orders[order_id] = order_data
                self._total_orders_placed += 1
                
                # Log event
                event = Event(
                    event_id=str(uuid4()),
                    event_type=EventType.TP_ORDER_PLACED,
                    timestamp=time.time(),
                    correlation_id=correlation_id,
                    aggregate_id=order_id,
                    data=order_data,
                    metadata={"actor": self.name, "attempt": attempt + 1}
                )
                self.event_store.append_event(event)
                
                log.info(f"✅ TP order placed: {order_id} for position {position_id}")
                
                return {"status": "ok", "order_id": order_id, "result": result}
            
            except Exception as e:
                log.error(f"TP order placement failed (attempt {attempt + 1}): {e}")
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    log.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    self._total_order_failures += 1
                    
                    failure_aggregate_id = f"tp_failed_{position_id}_{int(time.time())}"
                    event = Event(
                        event_id=str(uuid4()),
                        event_type=EventType.ORDER_FAILED,
                        timestamp=time.time(),
                        correlation_id=correlation_id,
                        aggregate_id=failure_aggregate_id,
                        data={
                            "type": "tp",
                            "price": price,
                            "size": size,
                            "position_id": position_id,
                            "error": str(e)
                        },
                        metadata={"actor": self.name, "attempts": self.max_retries}
                    )
                    self.event_store.append_event(event)
                    
                    return {"status": "error", "error": str(e)}
        
        return {"status": "error", "error": "Max retries exceeded"}
    
    async def _handle_cancel_order(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Cancel order by ID.
        
        Args:
            payload: Dict with order_id
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Cancellation result
        """
        order_id = payload["order_id"]
        
        try:
            log.info(f"Cancelling order: {order_id}")
            
            # VERIFY ORDER EXISTS FIRST (avoid 404 on already-gone orders)
            try:
                order_details = await self.api_client.get_order(order_id)
                order_state = order_details.get("state")
                
                # If order is already closed/cancelled, don't try to cancel
                if order_state in ["closed", "cancelled"]:
                    log.info(f"Order {order_id} already {order_state}, skipping cancel")
                    human_log.order_already_gone(order_id)
                    return {"status": "ok", "order_id": order_id, "already_gone": True, "state": order_state}
                    
                log.debug(f"Order {order_id} verified as {order_state}, proceeding with cancel")
                
            except Exception as verify_error:
                # If we can't verify, check if it's a 404 (order doesn't exist)
                if "404" in str(verify_error):
                    log.info(f"Order {order_id} not found on exchange (404), already gone")
                    human_log.order_already_gone(order_id)
                    return {"status": "ok", "order_id": order_id, "already_gone": True, "verify_failed": True}
                else:
                    # Other verification errors - log but try to cancel anyway
                    log.warning(f"Could not verify order {order_id} status: {verify_error}, attempting cancel anyway")
            
            result = await self.api_client.cancel_order(order_id, self.product_id)
            
            # Update tracking
            if order_id in self._active_orders:
                order = self._active_orders[order_id]
                order["status"] = "cancelled"
                order["cancelled_at"] = time.time()
                
                # Move to history
                self._order_history.append(order)
                if len(self._order_history) > self._max_history:
                    self._order_history.pop(0)
                
                del self._active_orders[order_id]
            
            self._total_orders_cancelled += 1
            
            # Log event
            event = Event(
                event_id=str(uuid4()),
                event_type=EventType.ORDER_CANCELLED,
                timestamp=time.time(),
                correlation_id=correlation_id,
                aggregate_id=order_id,
                data={"order_id": order_id, "result": result},
                metadata={"actor": self.name}
            )
            self.event_store.append_event(event)
            
            log.info(f"✅ Order cancelled: {order_id}")
            
            # Send notification (don't let Telegram errors interfere with result)
            try:
                human_log.order_cancelled(order_id)  # Human-readable (may trigger Telegram)
            except Exception as notif_error:
                log.warning(f"Notification failed for cancelled order {order_id}: {notif_error}")
            
            return {"status": "ok", "order_id": order_id, "result": result}
        
        except Exception as e:
            error_str = str(e)
            error_type = type(e).__name__
            
            # Log full error details for debugging
            log.error(f"❌ Exception during cancel_order({order_id}): {error_type}: {error_str}")
            
            # 404 means order already filled/cancelled - not an error
            if "404" in error_str or "Not Found" in error_str or "not_found" in error_str.lower():
                log.debug(f"Order {order_id} already gone (filled or cancelled)")
                human_log.order_already_gone(order_id)  # Human-readable
                return {"status": "ok", "order_id": order_id, "already_gone": True}
            
            # Real errors - DO NOT CLAIM SUCCESS
            log.error(f"⚠️  REAL CANCELLATION FAILURE for order {order_id}: {error_type}: {error_str}")
            human_log.order_cancel_failed(order_id, error_str)  # Human-readable
            
            # Return error status so shutdown knows it failed
            return {"status": "error", "error": error_str, "error_type": error_type}
    
    # ============================================================================
    # SINGLE WRITER PATTERN (Dec 19, 2025) - Institutional Grade Solution
    # ============================================================================
    # These methods implement atomic order replacement to prevent race conditions
    # when multiple concurrent sagas try to place orders simultaneously.
    #
    # Key Features:
    # - Mailbox provides natural serialization (no locks needed)
    # - In-memory state tracking (no exchange fetches in critical path)
    # - Single responsibility: OrderActor owns all order state changes
    # - Fast: Cancellation + placement happens atomically without blocking other actors
    #
    # This follows the "Single Writer Pattern" used by institutional trading systems:
    # Only ONE component (OrderActor) can modify order state, ensuring consistency.
    # ============================================================================
    
    async def _handle_replace_pending_buy_order(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Atomically replace pending BUY order with new one at target price.
        
        This ensures the "Single Pending Order Rule": only ONE pending BUY order exists.
        
        Process:
        1. Cancel ALL existing pending BUY orders (bot-placed, not manual)
        2. Check Guardian signal (optional, based on payload flag)
        3. Place new BUY order at target price
        4. Update internal state
        
        This method is called by sagas after TP fills to move the pending order
        to the new grid level. The mailbox ensures only ONE saga can execute
        this at a time, preventing race conditions.
        
        Args:
            payload: {
                "price": float,           # Target price for new order
                "size": float,            # Order size
                "check_guardian": bool,   # Whether to check Guardian signal (default: True)
                "skip_cancel": bool       # Skip cancellation phase (default: False)
            }
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            {
                "status": "ok" | "skipped" | "error",
                "order_id": str,          # New order ID (if placed)
                "cancelled_orders": list, # List of cancelled order IDs
                "reason": str             # Reason for skip/error
            }
        """
        target_price = payload["price"]
        size = payload["size"]
        check_guardian = payload.get("check_guardian", True)
        skip_cancel = payload.get("skip_cancel", False)
        
        log.info(f"[OrderActor] REPLACE_PENDING_BUY: target=${target_price:,.0f}, size={size}")
        
        cancelled_order_ids = []
        
        # PHASE 1: Cancel pending BUY order by known ID (deterministic) + orphan sweep
        if not skip_cancel:
            known_pending_id = payload.get("known_pending_id")

            # PHASE 1a: Cancel by known order ID — eliminates exchange propagation lag.
            # This is the authoritative step. If the known order cannot be confirmed
            # cancelled, placement is ABORTED to preserve the single-entry-order invariant.
            if known_pending_id:
                log.info(f"[OrderActor] Phase 1a: cancelling known pending BUY #{known_pending_id}")
                cancel_result = await self._handle_cancel_order(
                    {"order_id": known_pending_id},
                    None,
                    correlation_id
                )
                if cancel_result.get("status") == "ok":
                    cancelled_order_ids.append(known_pending_id)
                    log.info(f"[OrderActor] Known pending BUY #{known_pending_id} confirmed cancelled")
                else:
                    # Real failure (not already-gone) — abort to prevent two live entry orders
                    log.error(
                        f"[OrderActor] CANCEL FAILED for known BUY #{known_pending_id}: "
                        f"{cancel_result.get('error')} — aborting placement to preserve "
                        f"single-entry-order invariant"
                    )
                    return {
                        "status": "error",
                        "reason": "cancel_failed",
                        "order_id": known_pending_id,
                        "error": cancel_result.get("error"),
                        "cancelled_orders": cancelled_order_ids,
                    }

            # PHASE 1b: Best-effort orphan sweep — catches stale orders from bot restarts.
            # Non-blocking: a failure here does NOT abort placement. Phase 1a was authoritative.
            try:
                orders = await self.api_client.get_open_orders(self.product_id)

                for order in orders:
                    if order.get("side") == "buy" and order.get("state") == "open":
                        order_price = float(order.get("limit_price", 0))
                        oid = str(order.get("id"))
                        is_reduce_only = order.get("reduce_only", False)
                        client_order_id = order.get("client_order_id", "")

                        # Skip TP orders (reduce_only closes a long position)
                        if is_reduce_only:
                            continue

                        # Skip manual/external orders
                        if not client_order_id.startswith(self.tag_prefix):
                            log.debug(f"[OrderActor] Preserving manual order #{oid} @ ${order_price}")
                            continue

                        # Skip already cancelled in Phase 1a
                        if oid in cancelled_order_ids:
                            continue

                        # Skip target price itself (dedup in _handle_place_buy will catch it)
                        if abs(order_price - target_price) < 0.01:
                            continue

                        log.info(f"[OrderActor] Orphan sweep: cancelling BUY #{oid} @ ${order_price:,.0f}")
                        sweep_result = await self._handle_cancel_order(
                            {"order_id": oid}, None, correlation_id
                        )
                        if sweep_result.get("status") == "ok":
                            cancelled_order_ids.append(oid)
                        else:
                            log.warning(
                                f"[OrderActor] Orphan sweep cancel failed for #{oid}: "
                                f"{sweep_result.get('error')} (non-fatal — Phase 1a was authoritative)"
                            )

                        await asyncio.sleep(0.05)

                log.info(f"[OrderActor] Phase 1 complete: {len(cancelled_order_ids)} BUY order(s) cancelled")

            except Exception as e:
                log.warning(f"[OrderActor] Orphan sweep failed (non-fatal): {e}")
                # Non-fatal: Phase 1a (known ID) was the authoritative cancel step
        
        # PHASE 2: Check Guardian signal (if requested)
        if check_guardian:
            try:
                from bot.strategy.modules.event_store import EventType
                
                guardian_events = self.event_store.get_events_by_type(
                    [EventType.GUARDIAN_SIGNAL_GO, EventType.GUARDIAN_SIGNAL_STOP],
                    limit=1
                )
                
                if guardian_events:
                    latest_guardian = guardian_events[0]
                    signal = 'GO' if latest_guardian.event_type == EventType.GUARDIAN_SIGNAL_GO else 'STOP'
                    
                    if signal == 'STOP':
                        reason = latest_guardian.data.get('reason', 'No reason provided')
                        log.warning(f"[OrderActor] Guardian STOP - cannot place BUY @ ${target_price:,.0f}")
                        return {
                            "status": "skipped",
                            "reason": f"guardian_stop: {reason}",
                            "cancelled_orders": cancelled_order_ids,
                            "missed_order": {"price": target_price, "side": "buy"}
                        }
                else:
                    log.warning(f"[OrderActor] No Guardian signal found")
                    return {
                        "status": "skipped",
                        "reason": "no_guardian_signal",
                        "cancelled_orders": cancelled_order_ids
                    }
            
            except Exception as guardian_error:
                log.error(f"[OrderActor] Guardian check failed: {guardian_error}")
                return {
                    "status": "skipped",
                    "reason": f"guardian_check_error: {str(guardian_error)}",
                    "cancelled_orders": cancelled_order_ids
                }
        
        # PHASE 3: Place new BUY order
        placement_result = await self._handle_place_buy(
            {"price": target_price, "size": size},
            None,
            correlation_id
        )
        
        if placement_result["status"] != "ok":
            log.error(f"[OrderActor] Failed to place new BUY @ ${target_price:,.0f}: {placement_result.get('error')}")
            return {
                "status": "error",
                "error": placement_result.get("error"),
                "cancelled_orders": cancelled_order_ids
            }
        
        order_id = placement_result["order_id"]
        log.info(f"[OrderActor] ✅ Successfully replaced pending BUY: {len(cancelled_order_ids)} cancelled, new order #{order_id} @ ${target_price:,.0f}")
        
        return {
            "status": "ok",
            "order_id": order_id,
            "cancelled_orders": cancelled_order_ids,
            "price": target_price
        }
    
    async def _handle_replace_pending_sell_order(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Atomically replace pending SELL order with new one at target price.
        
        This ensures the "Single Pending Order Rule": only ONE pending SELL order exists.
        
        Same as REPLACE_PENDING_BUY_ORDER but for SELL side (SHORT mode).
        
        Args:
            payload: {
                "price": float,           # Target price for new order
                "size": float,            # Order size
                "check_guardian": bool,   # Whether to check Guardian signal (default: True)
                "skip_cancel": bool       # Skip cancellation phase (default: False)
            }
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            {
                "status": "ok" | "skipped" | "error",
                "order_id": str,          # New order ID (if placed)
                "cancelled_orders": list, # List of cancelled order IDs
                "reason": str             # Reason for skip/error
            }
        """
        target_price = payload["price"]
        size = payload["size"]
        check_guardian = payload.get("check_guardian", True)
        skip_cancel = payload.get("skip_cancel", False)
        
        log.info(f"[OrderActor] REPLACE_PENDING_SELL: target=${target_price:,.0f}, size={size}")
        
        cancelled_order_ids = []
        
        # PHASE 1: Cancel pending SELL order by known ID (deterministic) + orphan sweep
        if not skip_cancel:
            known_pending_id = payload.get("known_pending_id")

            # PHASE 1a: Cancel by known order ID — eliminates exchange propagation lag.
            # This is the authoritative step. If the known order cannot be confirmed
            # cancelled, placement is ABORTED to preserve the single-entry-order invariant.
            if known_pending_id:
                log.info(f"[OrderActor] Phase 1a: cancelling known pending SELL #{known_pending_id}")
                cancel_result = await self._handle_cancel_order(
                    {"order_id": known_pending_id},
                    None,
                    correlation_id
                )
                if cancel_result.get("status") == "ok":
                    cancelled_order_ids.append(known_pending_id)
                    log.info(f"[OrderActor] Known pending SELL #{known_pending_id} confirmed cancelled")
                else:
                    # Real failure (not already-gone) — abort to prevent two live entry orders
                    log.error(
                        f"[OrderActor] CANCEL FAILED for known SELL #{known_pending_id}: "
                        f"{cancel_result.get('error')} — aborting placement to preserve "
                        f"single-entry-order invariant"
                    )
                    return {
                        "status": "error",
                        "reason": "cancel_failed",
                        "order_id": known_pending_id,
                        "error": cancel_result.get("error"),
                        "cancelled_orders": cancelled_order_ids,
                    }

            # PHASE 1b: Best-effort orphan sweep — catches stale orders from bot restarts.
            # Non-blocking: a failure here does NOT abort placement. Phase 1a was authoritative.
            try:
                orders = await self.api_client.get_open_orders(self.product_id)

                for order in orders:
                    if order.get("side") == "sell" and order.get("state") == "open":
                        order_price = float(order.get("limit_price", 0))
                        oid = str(order.get("id"))
                        is_reduce_only = order.get("reduce_only", False)
                        client_order_id = order.get("client_order_id", "")

                        # Skip TP orders (reduce_only closes a short position)
                        if is_reduce_only:
                            continue

                        # Skip manual/external orders
                        if not client_order_id.startswith(self.tag_prefix):
                            log.debug(f"[OrderActor] Preserving manual order #{oid} @ ${order_price}")
                            continue

                        # Skip already cancelled in Phase 1a
                        if oid in cancelled_order_ids:
                            continue

                        # Skip target price itself (dedup in _handle_place_sell will catch it)
                        if abs(order_price - target_price) < 0.01:
                            continue

                        log.info(f"[OrderActor] Orphan sweep: cancelling SELL #{oid} @ ${order_price:,.0f}")
                        sweep_result = await self._handle_cancel_order(
                            {"order_id": oid}, None, correlation_id
                        )
                        if sweep_result.get("status") == "ok":
                            cancelled_order_ids.append(oid)
                        else:
                            log.warning(
                                f"[OrderActor] Orphan sweep cancel failed for #{oid}: "
                                f"{sweep_result.get('error')} (non-fatal — Phase 1a was authoritative)"
                            )

                        await asyncio.sleep(0.05)

                log.info(f"[OrderActor] Phase 1 complete: {len(cancelled_order_ids)} SELL order(s) cancelled")

            except Exception as e:
                log.warning(f"[OrderActor] Orphan sweep failed (non-fatal): {e}")
                # Non-fatal: Phase 1a (known ID) was the authoritative cancel step
        
        # PHASE 2: Check Guardian signal (if requested)
        if check_guardian:
            try:
                from bot.strategy.modules.event_store import EventType
                
                guardian_events = self.event_store.get_events_by_type(
                    [EventType.GUARDIAN_SIGNAL_GO, EventType.GUARDIAN_SIGNAL_STOP],
                    limit=1
                )
                
                if guardian_events:
                    latest_guardian = guardian_events[0]
                    signal = 'GO' if latest_guardian.event_type == EventType.GUARDIAN_SIGNAL_GO else 'STOP'
                    
                    if signal == 'STOP':
                        reason = latest_guardian.data.get('reason', 'No reason provided')
                        log.warning(f"[OrderActor] Guardian STOP - cannot place SELL @ ${target_price:,.0f}")
                        return {
                            "status": "skipped",
                            "reason": f"guardian_stop: {reason}",
                            "cancelled_orders": cancelled_order_ids,
                            "missed_order": {"price": target_price, "side": "sell"}
                        }
                else:
                    log.warning(f"[OrderActor] No Guardian signal found")
                    return {
                        "status": "skipped",
                        "reason": "no_guardian_signal",
                        "cancelled_orders": cancelled_order_ids
                    }
            
            except Exception as guardian_error:
                log.error(f"[OrderActor] Guardian check failed: {guardian_error}")
                return {
                    "status": "skipped",
                    "reason": f"guardian_check_error: {str(guardian_error)}",
                    "cancelled_orders": cancelled_order_ids
                }
        
        # PHASE 3: Place new SELL order
        # order_purpose="entry" re-enables the per-price timestamp cooldown and
        # the exchange-level dedup check in _handle_place_sell — second safety layer.
        placement_result = await self._handle_place_sell(
            {"price": target_price, "size": size, "order_purpose": "entry"},
            None,
            correlation_id
        )

        if placement_result["status"] != "ok":
            log.error(f"[OrderActor] Failed to place new SELL @ ${target_price:,.0f}: {placement_result.get('error')}")
            return {
                "status": "error",
                "error": placement_result.get("error"),
                "cancelled_orders": cancelled_order_ids
            }
        
        order_id = placement_result["order_id"]
        log.info(f"[OrderActor] ✅ Successfully replaced pending SELL: {len(cancelled_order_ids)} cancelled, new order #{order_id} @ ${target_price:,.0f}")
        
        return {
            "status": "ok",
            "order_id": order_id,
            "cancelled_orders": cancelled_order_ids,
            "price": target_price
        }
    
    async def _handle_get_open_orders(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Get open orders from exchange.
        
        Args:
            payload: Empty
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            List of open orders
        """
        try:
            orders = await self.api_client.get_open_orders(self.product_id)
            
            # Update tracking
            exchange_order_ids = {o.get("id", o.get("order_id")) for o in orders}
            
            # Mark filled/cancelled orders with proper state tracking
            for order_id, order in list(self._active_orders.items()):
                if order_id not in exchange_order_ids:
                    # Query individual order to get exact state (Delta Exchange specs)
                    try:
                        order_details = await self.api_client.get_order(order_id)
                        if order_details:
                            final_state = order_details.get("state", "unknown")
                            order["final_state"] = final_state
                            order["filled_size"] = order_details.get("filled_size", 0)
                            order["unfilled_size"] = order_details.get("unfilled_size", 0)
                            
                            # Log state transition for debugging
                            log.debug(f"Order {order_id} state transition: open → {final_state}")
                            
                            # Handle specific states per Delta Exchange specs
                            if final_state == "filled":
                                order["status"] = "filled"
                            elif final_state == "cancelled":
                                order["status"] = "cancelled"
                            elif final_state == "rejected":
                                order["status"] = "rejected"
                            else:
                                order["status"] = "unknown"
                        else:
                            order["status"] = "query_failed"
                    except Exception as e:
                        log.warning(f"Failed to query order {order_id} state: {e}")
                        order["status"] = "filled_or_cancelled"  # Fallback
                    
                    self._order_history.append(order)
                    if len(self._order_history) > self._max_history:
                        self._order_history.pop(0)
                    del self._active_orders[order_id]
            
            return {"status": "ok", "orders": orders}
        
        except Exception as e:
            log.error(f"Failed to get open orders: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _handle_get_order_status(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Get order status by ID.
        
        Args:
            payload: Dict with order_id
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Order status
        """
        order_id = payload["order_id"]
        
        # Check local tracking first
        if order := self._active_orders.get(order_id):
            return {"status": "ok", "order": order}
        
        # Check history
        for order in reversed(self._order_history):
            if order["order_id"] == order_id:
                return {"status": "ok", "order": order}
        
        return {"status": "error", "error": "Order not found"}
    
    async def _handle_get_metrics(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Get order metrics.
        
        Args:
            payload: Empty
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Order metrics
        """
        return {
            "active_orders": len(self._active_orders),
            "total_placed": self._total_orders_placed,
            "total_cancelled": self._total_orders_cancelled,
            "total_failures": self._total_order_failures,
            "success_rate": (
                self._total_orders_placed / 
                max(self._total_orders_placed + self._total_order_failures, 1)
            ),
            "active_order_ids": list(self._active_orders.keys())
        }
    
    def _validate_order(self, price: float, size: int, side: str) -> Dict[str, Any]:
        """
        Validate order parameters.
        
        Args:
            price: Order price
            size: Order size
            side: Order side (buy/sell)
            
        Returns:
            Validation result
        """
        if price <= 0:
            return {"status": "error", "error": "Invalid price: must be positive"}
        
        if size <= 0:
            return {"status": "error", "error": "Invalid size: must be positive"}
        
        if side not in ["buy", "sell"]:
            return {"status": "error", "error": f"Invalid side: {side}"}
        
        # Price sanity checks (Bitcoin specific)
        if price < 1000:  # Below $1k
            return {"status": "error", "error": f"Price too low: {price}"}
        
        if price > 1000000:  # Above $1M
            return {"status": "error", "error": f"Price too high: {price}"}
        
        return {"status": "ok"}
