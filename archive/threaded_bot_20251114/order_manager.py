"""
OrderManager - Order Placement and Management Module

Single Responsibility: Handle all order placement, cancellation, and verification

This module manages the complete order lifecycle including:
- BUY order placement with safety checks
- TP order placement with collision detection (FIX #8)
- Order cancellation with exchange verification
- Retry mechanisms for critical operations

Extracted from GridBotWebSocket (Phase 5 - Order operations)
"""

import time
import logging
import threading
from typing import Dict, Optional, Any, Set, Callable

log = logging.getLogger("runner")


class OrderManager:
    """
    Order placement and lifecycle management
    
    Responsibilities:
    - Place BUY orders (market maker)
    - Place TP orders (with collision avoidance - FIX #8)
    - Cancel orders (cleanup, volatility halt)
    - Verify order state on exchange
    - Generate unique client order IDs
    - Handle order capacity checks
    
    NOT Responsible For:
    - Position tracking (PositionManager handles this)
    - Grid calculations (GridCalculator handles this)
    - State persistence (PositionManager handles this)
    """
    
    # ✅ FIX #10: Configuration constants (instead of magic numbers)
    MAX_TP_OFFSET_DOLLARS = 100  # Maximum price offset for TP collision avoidance
    RATE_LIMIT_DELAY = 0.2       # Delay between API calls (seconds)
    VERIFY_TIMEOUT = 10.0         # Order verification timeout (seconds) - Delta Exchange async processing
    
    def __init__(
        self,
        api_client: Any,
        grid_calculator: Any,
        position_manager: Any,
        product_id: int,
        lot_size: int,
        tick_size: float = 0.5
    ):
        """
        Initialize order manager
        
        Args:
            api_client: Delta Exchange API client
            grid_calculator: GridCalculator instance for price calculations
            position_manager: PositionManager instance for state access
            product_id: Exchange product ID
            lot_size: Order lot size
            tick_size: Price tick size for quantization
        
        Raises:
            ValueError: If dependencies don't have required attributes/methods
        """
        # ✅ FIX #4: Validate lot_size is positive integer
        if not isinstance(lot_size, int) or lot_size <= 0:
            raise ValueError(f"lot_size must be a positive integer, got: {lot_size}")
        
        # ✅ FIX (Round 3): Validate product_id is positive integer
        if not isinstance(product_id, int) or product_id <= 0:
            raise ValueError(f"product_id must be a positive integer, got: {product_id}")
        
        # ✅ FIX (Round 3): Validate tick_size is positive
        if tick_size <= 0:
            raise ValueError(f"tick_size must be positive, got: {tick_size}")
        
        # ✅ FIX #9: Validate API client has required methods
        required_api_methods = ['place_order', 'cancel_order', 'get_order', 'list_orders']
        for method in required_api_methods:
            if not hasattr(api_client, method):
                raise ValueError(f"API client must have '{method}' method")
        
        # ✅ FIX #2: Validate position manager has state_lock
        if not hasattr(position_manager, 'state_lock'):
            raise ValueError("PositionManager must have 'state_lock' attribute")
        
        # ✅ FIX #3: Validate grid calculator has quantize_price method
        if not hasattr(grid_calculator, 'quantize_price'):
            raise ValueError("GridCalculator must have 'quantize_price' method")
        
        self.api_client = api_client
        self.grid_calc = grid_calculator
        self.position_mgr = position_manager
        self.product_id = product_id
        self.lot_size = lot_size
        self.tick_size = tick_size
        
        # ✅ FIX #8: Order logging integration with enhanced validation
        try:
            from bot.reconciliation.order_logger import log_order_placed, log_order_update
            # Validate both functions are callable
            if not callable(log_order_placed) or not callable(log_order_update):
                raise ImportError("Order logger functions not callable")
            self.order_logger_available = True
            self._log_order_placed = log_order_placed
            self._log_order_update = log_order_update
        except (ImportError, AttributeError) as e:
            log.debug(f"Order logger not available: {e}")
            self.order_logger_available = False
            self._log_order_placed = lambda *args, **kwargs: None
            self._log_order_update = lambda *args, **kwargs: None
        
        # ✅ FIX NOV 6: Add order placement lock to prevent race conditions
        self._order_lock = threading.RLock()  # Reentrant lock (same thread can re-acquire)
        log.info("✅ OrderManager: Order placement lock initialized")
        
        # ✅ FIX NOV 7: Store current market price for validation
        self.current_market_price: Optional[float] = None
        
        # ✅ FIX NOV 8: Order ID deduplication - track recently placed orders
        # Format: {order_id: timestamp}
        self._recent_orders: Dict[str, float] = {}
        self._recent_orders_lock = threading.Lock()
        self._recent_orders_ttl = 60.0  # Track for 60 seconds
        log.info("✅ OrderManager: Order deduplication tracking initialized")
        
        # 🔍 NOV 8: Monitoring systems (optional - set via set_monitoring_systems)
        self.price_monitor = None
        self.pre_order_logger = None
        self.anomaly_detector = None
        
        log.info("✅ OrderManager initialized")
    
    # ========================================================================
    # Monitoring Integration (NOV 8)
    # ========================================================================
    
    def set_monitoring_systems(self, price_monitor=None, pre_order_logger=None, anomaly_detector=None):
        """
        Set monitoring systems for comprehensive logging
        
        🔍 NOV 8: Allows GridBot to inject monitoring systems after initialization
        
        Args:
            price_monitor: PriceHealthMonitor instance
            pre_order_logger: PreOrderDecisionLogger instance
            anomaly_detector: AnomalyDetectionSystem instance
        """
        self.price_monitor = price_monitor
        self.pre_order_logger = pre_order_logger
        self.anomaly_detector = anomaly_detector
        log.info("✅ Monitoring systems attached to OrderManager")
    
    # ========================================================================
    # Market Price Update (NOV 7 FIX)
    # ========================================================================
    
    def update_market_price(self, price: float) -> None:
        """
        Update current market price for order validation
        
        ✅ FIX NOV 7: Store market price to validate BUY/SELL orders
        are placed as MAKER (below/above market), not TAKER (at market)
        
        Args:
            price: Current market price from WebSocket ticker
        """
        self.current_market_price = price
    
    # ========================================================================
    # Order Deduplication (NOV 8 FIX)
    # ========================================================================
    
    def _cleanup_recent_orders(self) -> None:
        """
        Remove expired entries from recent orders tracking
        
        ✅ FIX NOV 8: Keep tracking dict small by removing old entries
        ⚠️  MUST be called while holding self._recent_orders_lock!
        """
        now = time.time()
        expired = [
            order_id for order_id, timestamp in self._recent_orders.items()
            if now - timestamp > self._recent_orders_ttl
        ]
        for order_id in expired:
            del self._recent_orders[order_id]
    
    def _is_duplicate_order(self, order_id: str) -> bool:
        """
        Check if order ID was recently placed
        
        ✅ FIX NOV 8: Prevent duplicate order placement by tracking recent order IDs
        
        Args:
            order_id: Order ID to check
            
        Returns:
            True if order was placed within TTL window, False otherwise
        """
        with self._recent_orders_lock:
            # Cleanup old entries first
            self._cleanup_recent_orders()
            
            # Check if this order was recently placed
            if order_id in self._recent_orders:
                age = time.time() - self._recent_orders[order_id]
                log.warning(f"🚨 DUPLICATE ORDER DETECTED: {order_id} (placed {age:.1f}s ago)")
                return True
            
            return False
    
    def _record_order_placement(self, order_id: str) -> None:
        """
        Record order ID as recently placed
        
        ✅ FIX NOV 8: Track order placement for deduplication
        
        Args:
            order_id: Order ID that was just placed
        """
        with self._recent_orders_lock:
            self._recent_orders[order_id] = time.time()
            log.debug(f"📝 Recorded order placement: {order_id}")
    
    # ========================================================================
    # Client Order ID Generation
    # ========================================================================
    
    def generate_client_order_id(self, order_type: str = 'grid', side: str = 'buy') -> str:
        """
        Generate unique client order ID with BOT- prefix
        
        Format: BOT-{type}-{timestamp}-{side}
        
        Extracted from Lines 2253-2271 (gbot_ws.py)
        
        Args:
            order_type: Type of order ('grid', 'tp', 'opportunistic')
            side: Order side ('buy', 'sell', 'tp')
            
        Returns:
            Unique client order ID string
        """
        timestamp = int(time.time())
        return f"BOT-{order_type}-{timestamp}-{side}"
    
    # ========================================================================
    # Grid Alignment Validation (NOV 3 INCIDENT FIX)
    # ========================================================================
    
    def _is_price_grid_aligned(self, price: float) -> bool:
        """
        Verify that price aligns with configured grid step
        
        This prevents Smart Gap Fill or other features from placing
        orders at market prices that don't match the grid structure.
        
        Example:
            Grid: Lower=105k, Step=1000
            Valid: 105000, 106000, 107000, 108000, etc.
            Invalid: 106375.5, 107291.5 (market prices)
        
        Args:
            price: Price to validate
            
        Returns:
            True if price aligns with grid, False otherwise
        """
        lower = self.grid_calc.lower
        step = self.grid_calc.step
        
        # Calculate offset from lower boundary
        offset = (price - lower) % step
        
        # Allow tolerance for tick size (0.5)
        # Price is aligned if offset is very small or very close to step
        tolerance = max(self.tick_size, 1.0)
        
        is_aligned = offset < tolerance or (step - offset) < tolerance
        
        return is_aligned
    
    def _get_valid_grid_levels(self) -> list:
        """
        Get all valid grid levels for reference
        
        Returns:
            List of valid grid prices
        """
        levels = []
        price = self.grid_calc.lower
        
        while price <= self.grid_calc.upper:
            levels.append(f"${price:,.0f}")
            price += self.grid_calc.step
            
            # Safety: prevent infinite loop
            if len(levels) > 1000:
                break
        
        return levels
    
    # ========================================================================
    # BUY Order Placement
    # ========================================================================
    
    def place_buy_order(
        self,
        price: float,
        post_only: bool = False,
        emergency_stop_check: Optional[Callable[[], bool]] = None,
        volatility_check: Optional[Callable[[], tuple]] = None,
        liquidation_check: Optional[Callable[[], tuple]] = None
    ) -> Optional[str]:
        """
        Place BUY order with safety checks
        
        ✅ FIX #12: Added post_only parameter for consistency with place_sell_order
        ✅ FIX NOV 6: Added function-level lock to prevent race conditions
        Extracted from Lines 2277-2463 (gbot_ws.py)
        
        Args:
            price: Limit price for BUY order
            emergency_stop_check: Optional callback to check emergency stop
            volatility_check: Optional callback to check volatility
            liquidation_check: Optional callback to check liquidation risk
            
        Returns:
            Order ID if successful, None if failed
        """
        
        # ✅ FIX NOV 6: Acquire lock before ANY logic to prevent race conditions
        with self._order_lock:
            
            # Safety check: Price validation
            if not price or price <= 0:
                log.error(f"❌ Invalid price: {price} - must be positive")
                return None
            
            # Safety check: Quantity validation
            if not self.lot_size or self.lot_size <= 0:
                log.error(f"❌ Invalid lot size: {self.lot_size} - must be positive")
                return None
            
            # Quantize price first (for duplicate check)
            price = self.grid_calc.quantize_price(price)
            
            # ✅ FIX NOV 6: Check if order already pending at this price (while holding lock)
            current_pending = self.position_mgr.get_pending_buy()
            if current_pending:
                pending_price = current_pending.get('price')
                if pending_price and abs(float(pending_price) - float(price)) < 1e-6:
                    log.warning(f"⚠️ BUY order already pending @ ${price:,.0f} - skipping duplicate")
                    return current_pending.get('order_id')
            
            # ✅ FIX NOV 3 INCIDENT: Validate grid alignment BEFORE placing order
            if not self._is_price_grid_aligned(price):
                log.error("=" * 80)
                log.error(f"❌ REJECTED: Price {price:,.2f} is NOT grid-aligned!")
                log.error(f"   Grid Configuration:")
                log.error(f"   - Lower Boundary: {self.grid_calc.lower:,.0f}")
                log.error(f"   - Upper Boundary: {self.grid_calc.upper:,.0f}")
                log.error(f"   - Grid Step: {self.grid_calc.step:,.0f}")
                log.error(f"   Valid Prices: {self._get_valid_grid_levels()}")
                log.error("=" * 80)
                
                # Send alert
                try:
                    from bot.utils.notifier import TelegramNotifier
                    notifier = TelegramNotifier()
                    alert_msg = (
                        f"⚠️ Grid Alignment Violation!\n\n"
                        f"Attempted Price: {price:,.2f}\n"
                        f"Grid Step: {self.grid_calc.step:,.0f}\n"
                        f"This order was BLOCKED.\n\n"
                        f"Check bot configuration!"
                    )
                    notifier.send(alert_msg)
                except Exception:
                    pass
                
                return None
            
            
            # ✅ FIX NOV 7: Validate BUY price is BELOW market (prevent TAKER execution)
            current_market_price = self.current_market_price
            
            if current_market_price and price >= current_market_price:
                log.error("=" * 80)
                log.error(f"❌ REJECTED: BUY price {price:,.2f} is AT or ABOVE market {current_market_price:,.2f}!")
                log.error(f"   This would execute as TAKER at market price (off-grid)!")
                log.error(f"   BUY orders must be placed BELOW market for MAKER execution.")
                log.error(f"   Suggested: Place at nearest grid level below market")
                log.error("=" * 80)
                
                # Send alert
                try:
                    from bot.utils.notifier import TelegramNotifier
                    notifier = TelegramNotifier()
                    alert_msg = (
                        f"🚨 Market Price Violation!\n\n"
                        f"Attempted BUY: ${price:,.2f}\n"
                        f"Market Price: ${current_market_price:,.2f}\n"
                        f"This order was BLOCKED to prevent TAKER execution!\n\n"
                        f"Bot logic needs adjustment."
                    )
                    notifier.send(alert_msg)
                except Exception:
                    pass
                
                return None
        
            
            # Safety check: Emergency stop
            if emergency_stop_check and emergency_stop_check():
                log.warning("🛑 Emergency stop active - skipping BUY placement")
                return None
            
            # Safety check: Volatility
            if volatility_check:
                can_trade, reason = volatility_check()
                if not can_trade:
                    log.warning(f"⚠️ Volatility check failed: {reason}")
                    return None
            
            # Safety check: Liquidation
            if liquidation_check:
                can_trade, reason = liquidation_check()
                if not can_trade:
                    log.warning(f"⚠️ Liquidation check failed: {reason}")
                    return None
            
            try:
                # Generate client order ID
                client_order_id = self.generate_client_order_id('grid', 'buy')
                
                # ✅ FIX NOV 8: Check for duplicate order placement
                is_dup = self._is_duplicate_order(client_order_id)
                if is_dup:
                    log.error(f"❌ DUPLICATE ORDER BLOCKED: {client_order_id}")
                    # Return existing order ID if still in pending
                    if current_pending:
                        return current_pending.get('order_id')
                    return None
                
                log.info(f"📝 Placing BUY @ ${price:,.0f}, size: {self.lot_size}")
                
                # 🔍 LAYER 2: Pre-Order Decision Logger (NOV 8)
                # CRITICAL: Monitors are REQUIRED for order placement
                # FAIL-SAFE: Cannot place orders without full monitoring stack
                if not self.pre_order_logger:
                    log.error("❌ CRITICAL: Pre-order logger not available - cannot validate order safety")
                    log.error("❌ Order rejected - monitoring is mandatory for safe trading")
                    return None
                
                if not self.price_monitor:
                    log.error("❌ CRITICAL: Price monitor not available - cannot validate price freshness")
                    log.error("❌ Order rejected - price monitoring is mandatory for safe trading")
                    return None
                
                # Log complete decision context before placing order
                # CRITICAL: Fail-safe behavior - reject order if validation fails for ANY reason
                try:
                    price_age = self.price_monitor.get_price_age()
                    positions = self.position_mgr.get_positions()
                    
                    # Get actual market price from price monitor
                    market_price = self.price_monitor.last_price
                    
                    # Check if order should be approved
                    decision_approved = self.pre_order_logger.log_buy_decision(
                        target_price=price,
                        current_price=market_price,
                        price_age=price_age,
                        grid_aligned=self._is_price_grid_aligned(price),
                        current_positions=len(positions),
                        max_positions=self.position_mgr.max_open,
                        volatility_safe=(not volatility_check or volatility_check()[0]),
                        grid_step=self.grid_calc.step
                    )
                    
                    if not decision_approved:
                        log.error("❌ Pre-order validation FAILED - order rejected by logger")
                        return None
                except Exception as e:
                    # FAIL-SAFE: If validation crashes, REJECT the order
                    log.error(f"❌ Pre-order validation CRASHED - order rejected for safety: {e}")
                    return None
                
                # Check price freshness before placing order
                # CRITICAL: Fail-safe behavior - reject order if price check fails
                if self.price_monitor:
                    try:
                        can_place, reason = self.price_monitor.can_place_orders()
                        if not can_place:
                            log.error(f"❌ Cannot place order: {reason}")
                            return None
                    except Exception as e:
                        # FAIL-SAFE: If price check crashes, REJECT the order
                        log.error(f"❌ Price health check CRASHED - order rejected for safety: {e}")
                        return None
                
                # Place order via API (protected by lock)
                response = self.api_client.place_order(
                    product_id=self.product_id,
                    side='buy',
                    size=self.lot_size,
                    limit_price=str(price),
                    order_type='limit_order',
                    time_in_force='gtc',
                    post_only=post_only,  # ✅ FIX #12: Support post_only for grid seeding
                    client_order_id=client_order_id
                )
                
                # ✅ FIX #5: Validate API response structure before accessing nested keys
                if response.get('success') and 'result' in response and 'id' in response['result']:
                    order_id = str(response['result']['id'])
                    
                    # ✅ FIX NOV 8: Record order placement for deduplication
                    self._record_order_placement(order_id)
                    
                    log.info(f"✅ BUY order placed: ID {order_id}")
                    
                    # 🔍 LAYER 4: Track order placement for anomaly detection (NOV 8)
                    if self.anomaly_detector:
                        try:
                            self.anomaly_detector.track_order_placement(order_id, price)
                        except Exception as e:
                            log.debug(f"Anomaly tracking error: {e}")
                    
                    # ✅ FIX NOV 9: START AGGRESSIVE POLLING IMMEDIATELY AFTER ORDER PLACEMENT
                    # WebSocket fill detection is UNRELIABLE - poll aggressively for 30s
                    if hasattr(self, '_start_order_polling'):
                        try:
                            self._start_order_polling(order_id, 'buy', price)
                            log.info(f"🔄 Started aggressive polling for order {order_id}")
                        except Exception as e:
                            log.error(f"❌ Failed to start order polling: {e}")
                    
                    # Log for reconciliation with verification
                    if self.order_logger_available:
                        try:
                            log_success = self._log_order_placed(
                                order_id=order_id,
                                client_order_id=client_order_id,
                                side='buy',
                                price=price,
                                size=self.lot_size,
                                symbol=f"PRODUCT_{self.product_id}",
                                status='open',
                                metadata={'strategy': 'grid', 'order_type': 'buy'}
                            )
                            
                            # ✅ FIX NOV 3: Verify logging succeeded
                            if log_success is False:
                                log.critical(f"🚨 ORDER LOGGING FAILED for BUY order {order_id}")
                                try:
                                    from bot.utils.notifier import TelegramNotifier
                                    notifier = TelegramNotifier()
                                    notifier.send(f"⚠️ Order logging failed for BUY {order_id} @ ${price:,.0f}")
                                except Exception:
                                    pass
                        except Exception as log_err:
                            log.critical(f"🚨 EXCEPTION in order logging: {log_err}")
                            try:
                                from bot.utils.notifier import TelegramNotifier
                                notifier = TelegramNotifier()
                                notifier.send(f"⚠️ Order logging exception: {log_err}")
                            except Exception:
                                pass
                    
                    return order_id
                else:
                    log.error(f"❌ BUY order placement failed - invalid response structure: {response}")
                    return None
            
            except Exception as e:
                log.error(f"❌ Error placing BUY order: {e}")
                import traceback
                log.error(traceback.format_exc())
                return None
        # Lock released here
    
    def place_sell_order(
        self,
        price: float,
        post_only: bool = False,
        emergency_stop_check: Optional[Callable[[], bool]] = None,
        volatility_check: Optional[Callable[[], tuple]] = None,
        liquidation_check: Optional[Callable[[], tuple]] = None
    ) -> Optional[str]:
        """
        Place SELL order with safety checks (for SHORT mode)
        
        ✅ FIX NOV 6: Added function-level lock to prevent race conditions
        Mirrors place_buy_order() but for SHORT grid trading.
        
        Args:
            price: Limit price for SELL order
            post_only: If True, only post maker orders
            emergency_stop_check: Optional callback to check emergency stop
            volatility_check: Optional callback to check volatility
            liquidation_check: Optional callback to check liquidation risk
            
        Returns:
            Order ID if successful, None if failed
        """
        # ✅ FIX NOV 6: Acquire lock before ANY logic to prevent race conditions
        with self._order_lock:
            # Safety check: Price validation
            if not price or price <= 0:
                log.error(f"❌ Invalid price: {price} - must be positive")
                return None
            
            # Safety check: Quantity validation
            if not self.lot_size or self.lot_size <= 0:
                log.error(f"❌ Invalid lot size: {self.lot_size} - must be positive")
                return None
            
            # Quantize price first (for duplicate check)
            price = self.grid_calc.quantize_price(price)
            
            # ✅ FIX NOV 6: Check if order already pending at this price (while holding lock)
            current_pending = self.position_mgr.get_pending_sell()
            if current_pending:
                pending_price = current_pending.get('price')
                if pending_price and abs(float(pending_price) - float(price)) < 1e-6:
                    log.warning(f"⚠️ SELL order already pending @ ${price:,.0f} - skipping duplicate")
                    return current_pending.get('order_id')
            
            # ✅ FIX NOV 7: Validate SELL price is ABOVE market (prevent TAKER execution)
            current_market_price = self.current_market_price
            
            if current_market_price and price <= current_market_price:
                log.error("=" * 80)
                log.error(f"❌ REJECTED: SELL price {price:,.2f} is AT or BELOW market {current_market_price:,.2f}!")
                log.error(f"   This would execute as TAKER at market price (off-grid)!")
                log.error(f"   SELL orders must be placed ABOVE market for MAKER execution.")
                log.error(f"   Suggested: Place at nearest grid level above market")
                log.error("=" * 80)
                
                # Send alert
                try:
                    from bot.utils.notifier import TelegramNotifier
                    notifier = TelegramNotifier()
                    alert_msg = (
                        f"🚨 Market Price Violation!\n\n"
                        f"Attempted SELL: ${price:,.2f}\n"
                        f"Market Price: ${current_market_price:,.2f}\n"
                        f"This order was BLOCKED to prevent TAKER execution!\n\n"
                        f"Bot logic needs adjustment."
                    )
                    notifier.send(alert_msg)
                except Exception:
                    pass
                
                return None
        
            # Safety check: Emergency stop
            if emergency_stop_check and emergency_stop_check():
                log.warning("🛑 Emergency stop active - skipping SELL placement")
                return None
            
            # Safety check: Volatility
            if volatility_check:
                can_trade, reason = volatility_check()
                if not can_trade:
                    log.warning(f"⚠️ Volatility check failed: {reason}")
                    return None
            
            # Safety check: Liquidation
            if liquidation_check:
                can_trade, reason = liquidation_check()
                if not can_trade:
                    log.warning(f"⚠️ Liquidation check failed: {reason}")
                    return None
            
            try:
                # Generate client order ID
                client_order_id = self.generate_client_order_id('grid', 'sell')
                
                # ✅ FIX NOV 8: Check for duplicate order placement
                if self._is_duplicate_order(client_order_id):
                    log.error(f"❌ DUPLICATE ORDER BLOCKED: {client_order_id}")
                    # Return existing order ID if still in pending
                    if current_pending:
                        return current_pending.get('order_id')
                    return None
                
                log.info(f"📝 Placing SELL @ ${price:,.0f}, size: {self.lot_size}")
                
                # 🔍 LAYER 2: Pre-Order Decision Logger (NOV 8)
                # CRITICAL: Monitors are REQUIRED for order placement
                # FAIL-SAFE: Cannot place orders without full monitoring stack
                if not self.pre_order_logger:
                    log.error("❌ CRITICAL: Pre-order logger not available - cannot validate order safety")
                    log.error("❌ Order rejected - monitoring is mandatory for safe trading")
                    return None
                
                if not self.price_monitor:
                    log.error("❌ CRITICAL: Price monitor not available - cannot validate price freshness")
                    log.error("❌ Order rejected - price monitoring is mandatory for safe trading")
                    return None
                
                # Log complete decision context before placing order
                # CRITICAL: Fail-safe behavior - reject order if validation fails for ANY reason
                try:
                    price_age = self.price_monitor.get_price_age()
                    positions = self.position_mgr.get_positions()
                    
                    # Get actual market price from price monitor
                    market_price = self.price_monitor.last_price
                    
                    # Check if order should be approved
                    decision_approved = self.pre_order_logger.log_sell_decision(
                        target_price=price,
                        current_price=market_price,
                        price_age=price_age,
                        grid_aligned=self._is_price_grid_aligned(price),
                        current_positions=len(positions),
                        max_positions=self.position_mgr.max_open,
                        volatility_safe=(not volatility_check or volatility_check()[0]),
                        grid_step=self.grid_calc.step
                    )
                    
                    if not decision_approved:
                        log.error("❌ Pre-order validation FAILED - order rejected by logger")
                        return None
                except Exception as e:
                    # FAIL-SAFE: If validation crashes, REJECT the order
                    log.error(f"❌ Pre-order validation CRASHED - order rejected for safety: {e}")
                    return None
                
                # Check price freshness before placing order
                # CRITICAL: Fail-safe behavior - reject order if price check fails
                if self.price_monitor:
                    try:
                        can_place, reason = self.price_monitor.can_place_orders()
                        if not can_place:
                            log.error(f"❌ Cannot place order: {reason}")
                            return None
                    except Exception as e:
                        # FAIL-SAFE: If price check crashes, REJECT the order
                        log.error(f"❌ Price health check CRASHED - order rejected for safety: {e}")
                        return None
                
                # Place order via API (protected by lock)
                response = self.api_client.place_order(
                    product_id=self.product_id,
                    side='sell',
                    size=self.lot_size,
                    limit_price=str(price),
                    order_type='limit_order',
                    time_in_force='gtc',
                    post_only=post_only,
                    client_order_id=client_order_id
                )
                
                # Validate API response
                if response.get('success') and 'result' in response and 'id' in response['result']:
                    order_id = str(response['result']['id'])
                    
                    # ✅ FIX NOV 8: Record order placement for deduplication
                    self._record_order_placement(order_id)
                    log.info(f"✅ SELL order placed: ID {order_id}")
                    
                    # 🔍 LAYER 4: Track order placement for anomaly detection (NOV 8)
                    if self.anomaly_detector:
                        try:
                            self.anomaly_detector.track_order_placement(order_id, price)
                        except Exception as e:
                            log.debug(f"Anomaly tracking error: {e}")
                    
                    # Log for reconciliation
                    if self.order_logger_available:
                        self._log_order_placed(
                            order_id=order_id,
                            client_order_id=client_order_id,
                            side='sell',
                            price=price,
                            size=self.lot_size,
                            symbol=f"PRODUCT_{self.product_id}",
                            status='open',
                            metadata={'strategy': 'grid', 'order_type': 'sell'}
                        )
                    
                    return order_id
                else:
                    log.error(f"❌ SELL order placement failed - invalid response structure: {response}")
                    return None
            
            except Exception as e:
                log.error(f"❌ Error placing SELL order: {e}")
                import traceback
                log.error(traceback.format_exc())
                return None
        # Lock released here
    
    # ========================================================================
    # TP Order Placement with Collision Detection (FIX #8)
    # ========================================================================
    
    def find_safe_tp_price(self, desired_tp: float, occupied_levels: Set[float]) -> float:
        """
        Find nearest available price level above desired_tp to avoid collisions
        
        ✅ FIX #8: Collision detection for TP orders
        ✅ FIX #7: Respect tick_size for price offsets (not $1 increments)
        ✅ FIX (Round 3): Prevent division by zero if tick_size is invalid
        
        Extracted from Lines 1710-1728 (gbot_ws.py)
        
        Args:
            desired_tp: Target TP price
            occupied_levels: Set of price levels already occupied by position entries
            
        Returns:
            Collision-free TP price (may be offset from desired)
            
        Raises:
            ValueError: If tick_size is invalid (should never happen due to constructor validation)
        """
        # Defensive check (should be caught in constructor, but double-check)
        if self.tick_size <= 0:
            raise ValueError(f"tick_size must be positive, got: {self.tick_size}")
        
        offset_ticks = 0
        max_offset_ticks = int(self.MAX_TP_OFFSET_DOLLARS / self.tick_size)
        
        while (desired_tp + offset_ticks * self.tick_size) in occupied_levels:
            offset_ticks += 1
            if offset_ticks >= max_offset_ticks:
                log.error(f"⚠️ Cannot find safe TP price within ${self.MAX_TP_OFFSET_DOLLARS} of ${desired_tp:,.0f}")
                break
        
        return desired_tp + offset_ticks * self.tick_size
    
    def safe_place_tp(
        self,
        position: Dict[str, Any],
        check_collisions: bool = True
    ) -> bool:
        """
        Place TP order with collision detection and automatic offsetting
        
        ✅ FIX #8: Collision-safe TP placement
        ✅ FIX #11: Dynamic TP side detection (BUY for SHORT, SELL for LONG)
        Extracted from Lines 1730-1790 (gbot_ws.py)
        
        COLLISION PREVENTION:
        - Checks if TP price conflicts with existing position entry levels
        - Automatically offsets TP by $1+ to find safe price level
        - Updates position metadata with actual TP price used
        
        THREAD SAFETY:
        - All state reads/writes happen inside state_lock
        - Prevents race conditions during collision detection
        
        Args:
            position: Position dictionary (must already be in open_tranches)
            check_collisions: Whether to check for price collisions
            
        Returns:
            True if TP placed successfully, False otherwise
        """
        # ✅ FIX: Validate position structure before proceeding
        required_fields = ['tp_price', 'size', 'entry_price']
        if not all(field in position for field in required_fields):
            log.error(f"❌ Invalid position structure: missing required fields {required_fields}")
            return False
        
        tp_price = position['tp_price']
        
        # ✅ FIX: Check for conflicts with existing grid levels (thread-safe)
        if check_collisions:
            with self.position_mgr.state_lock:
                occupied_levels = {p['entry_price'] for p in self.position_mgr.open_tranches if p != position}
                
                original_tp = tp_price
                if tp_price in occupied_levels:
                    # Find collision-free price
                    tp_price = self.find_safe_tp_price(tp_price, occupied_levels)
                    log.warning(f"⚠️ TP collision detected: ${original_tp:,.0f} → ${tp_price:,.0f} "
                               f"(offset ${tp_price - original_tp:,.0f})")
                    # ✅ FIX: Update position while still holding lock (prevents race condition)
                    position['tp_price'] = tp_price  # Update metadata
                    position['tp_offset'] = tp_price - original_tp  # Track deviation
        
        # Place TP order
        try:
            client_order_id = self.generate_client_order_id('grid', 'tp')
            
            # ✅ FIX #11: Determine TP side based on position side
            # SHORT positions: Close with BUY (buy back at lower price)
            # LONG positions: Close with SELL (sell at higher price)
            if position.get('side') == 'short':
                tp_side = 'buy'  # Close SHORT with BUY
            else:
                tp_side = 'sell'  # Close LONG with SELL (default)
            
            # ✅ FIX: Use place_order (not create_order), add client_order_id, convert limit_price to string
            tp_order = self.api_client.place_order(
                product_id=self.product_id,
                size=position['size'],
                side=tp_side,  # ✅ FIX #11: Dynamic side based on position type
                limit_price=str(tp_price),  # ✅ FIX: Convert to string for API consistency
                order_type='limit_order',
                reduce_only=True,  # Critical: TP orders must be reduce_only
                time_in_force='gtc',
                client_order_id=client_order_id  # ✅ FIX: Add client_order_id for tracking
            )
            
            # ✅ FIX #5: Validate API response structure
            if tp_order.get('success') and 'result' in tp_order and 'id' in tp_order['result']:
                tp_id = str(tp_order['result']['id'])
                
                # ✅ FIX #6: Update position with proper error handling
                # If state update fails, don't return False since order was placed successfully
                try:
                    with self.position_mgr.state_lock:
                        position['tp_id'] = tp_id
                        position['protected'] = True  # Mark as protected
                except Exception as e:
                    log.error(f"❌ Error updating position state: {e}")
                    log.critical(f"⚠️ CRITICAL: TP order {tp_id} placed successfully but state update failed!")
                    log.critical(f"⚠️ Manual reconciliation needed - order exists on exchange but not in local state")
                    # Don't return False - order was successfully placed
                
                profit = tp_price - position.get('actual_entry', position.get('entry_price'))
                log.info(f"✅ TP placed @ ${tp_price:,.0f} (ID: {tp_id}, profit: ${profit:,.0f})")
                
                # ✅ NOV 11 FIX: Verify TP order actually exists on exchange
                log.info(f"   Verifying TP order {tp_id} on exchange...")
                time.sleep(0.5)  # Brief delay for exchange to process
                
                try:
                    verify_response = self.api_client.get_order(tp_id)
                    
                    if not verify_response or not verify_response.get('success'):
                        log.error("=" * 80)
                        log.error(f"❌ TP order {tp_id} placement confirmed but NOT found on exchange!")
                        log.error(f"   Verification response: {verify_response}")
                        log.error(f"   This is a critical bug - order may not actually exist")
                        log.error("=" * 80)
                        
                        # Remove tp_id from position (it doesn't actually exist)
                        try:
                            with self.position_mgr.state_lock:
                                position.pop('tp_id', None)
                                position['protected'] = False
                        except Exception:
                            pass
                        
                        return False
                    
                    # Verify order is actually a reduce-only limit order
                    order_data = verify_response.get('result', {})
                    is_reduce_only = order_data.get('reduce_only', False)
                    order_state = order_data.get('state', '').lower()
                    
                    if not is_reduce_only:
                        log.error("=" * 80)
                        log.error(f"❌ TP order {tp_id} is NOT reduce-only!")
                        log.error(f"   This is dangerous - order could open new position instead of closing")
                        log.error(f"   Order data: {order_data}")
                        log.error("=" * 80)
                        # Don't return False - order exists, just misconfigured (API issue)
                    
                    if order_state != 'open':
                        log.warning(f"⚠️  TP order {tp_id} state is '{order_state}' (expected 'open')")
                        log.warning(f"   Order may have filled immediately or been rejected")
                    
                    log.info(f"   ✅ TP order {tp_id} verified on exchange (reduce_only={is_reduce_only}, state={order_state})")
                    
                except Exception as verify_err:
                    log.error(f"❌ TP verification failed: {verify_err}")
                    log.warning(f"   Assuming order is valid (verification error may be transient)")
                    import traceback
                    log.debug(traceback.format_exc())
                
                # ✅ FIX NOV 9: START AGGRESSIVE POLLING FOR TP ORDERS TOO
                if hasattr(self, '_start_order_polling'):
                    try:
                        self._start_order_polling(tp_id, tp_side, tp_price)
                        log.info(f"🔄 Started aggressive polling for TP order {tp_id}")
                    except Exception as e:
                        log.error(f"❌ Failed to start TP polling: {e}")
                
                # ✅ FIX NOV 3 INCIDENT: Log TP orders for audit trail
                if self.order_logger_available:
                    try:
                        log_success = self._log_order_placed(
                            order_id=tp_id,
                            client_order_id=client_order_id,
                            side=tp_side,
                            price=tp_price,
                            size=position['size'],
                            symbol=f"PRODUCT_{self.product_id}",
                            status='open',
                            metadata={
                                'strategy': 'grid',
                                'order_type': 'tp',
                                'entry_price': position.get('entry_price'),
                                'expected_profit': profit
                            }
                        )
                        
                        # Verify logging succeeded
                        if log_success is False:
                            log.critical(f"🚨 TP ORDER LOGGING FAILED for order {tp_id}")
                            try:
                                from bot.utils.notifier import TelegramNotifier
                                notifier = TelegramNotifier()
                                notifier.send(
                                    f"⚠️ TP order logging failed!\n"
                                    f"TP ID: {tp_id}\n"
                                    f"Price: ${tp_price:,.0f}\n"
                                    f"Order placed but NOT logged!"
                                )
                            except Exception:
                                pass
                    except Exception as log_err:
                        log.critical(f"🚨 EXCEPTION logging TP order: {log_err}")
                
                return True
            else:
                error_msg = tp_order.get('error', {}).get('message', 'Unknown error')
                log.error(f"❌ TP placement failed - invalid response: {error_msg}")
                log.debug(f"Full response: {tp_order}")
                return False
        
        except Exception as e:
            log.error(f"❌ Error placing TP: {e}")
            import traceback
            log.debug(traceback.format_exc())
            return False
    
    def place_tp_with_retry(
        self,
        position: Dict[str, Any],
        max_retries: int = 3,
        retry_delay: float = 2.0
    ) -> bool:
        """
        Place TP order with retry mechanism
        
        Args:
            position: Position dictionary
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries (seconds)
            
        Returns:
            True if TP placed successfully, False if all retries failed
        """
        for attempt in range(max_retries):
            if attempt > 0:
                log.warning(f"⚠️ TP retry attempt {attempt + 1}/{max_retries}")
                time.sleep(retry_delay * attempt)  # Exponential backoff
            
            if self.safe_place_tp(position):
                if attempt > 0:
                    log.info(f"✅ TP placement succeeded on retry {attempt + 1}")
                return True
        
        log.error(f"❌ ALL {max_retries} TP PLACEMENT ATTEMPTS FAILED!")
        return False
    
    def place_tp_mandatory(
        self,
        position: Dict[str, Any],
        max_retries: int = 5,
        retry_delay: float = 3.0
    ) -> str:
        """
        Place TP order with MANDATORY success - halts bot if all retries fail
        
        🚨 CRITICAL FIX: Ensures TP orders are ALWAYS placed
        - Used for filled buy orders that MUST have protection
        - Retries with exponential backoff
        - Raises exception (halts bot) if all retries fail
        
        Args:
            position: Position dictionary (must be in open_tranches)
            max_retries: Maximum retry attempts (default: 5)
            retry_delay: Base delay between retries (default: 3s)
            
        Returns:
            TP order ID (string)
            
        Raises:
            RuntimeError: If TP placement fails after all retries
        """
        entry_price = position.get('entry_price', 0)
        tp_price = position.get('tp_price', 0)
        size = position.get('size', 0)
        
        for attempt in range(max_retries):
            if attempt > 0:
                delay = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                log.warning(f"⚠️ TP RETRY {attempt + 1}/{max_retries} "
                           f"(wait {delay:.1f}s) - Entry: ${entry_price:,.2f}")
                time.sleep(delay)
            
            try:
                if self.safe_place_tp(position, check_collisions=True):
                    # Verify TP was actually set
                    tp_id = position.get('tp_id')
                    if tp_id:
                        if attempt > 0:
                            log.info(f"✅ TP MANDATORY SUCCESS on retry {attempt + 1}")
                        return str(tp_id)
                    else:
                        # ✅ NOV 11 FIX: Enhanced logging when tp_id is missing
                        log.error("=" * 80)
                        log.error(f"❌ TP returned success but no tp_id in position!")
                        log.error(f"   Attempt: {attempt + 1}/{max_retries}")
                        log.error(f"   Position keys: {list(position.keys())}")
                        log.error(f"   Position: {position}")
                        log.error(f"   This indicates a wiring bug in safe_place_tp()")
                        log.error("=" * 80)
                        
                        # Check API connectivity
                        try:
                            log.info("   Testing API connectivity...")
                            test_response = self.api_client.get_product(self.product_id)
                            if test_response.get('success'):
                                log.info(f"   ✅ API is responsive: {test_response.get('result', {}).get('symbol', 'N/A')}")
                            else:
                                log.error(f"   ❌ API error: {test_response.get('error', 'Unknown error')}")
                        except Exception as api_err:
                            log.error(f"   ❌ API exception: {api_err}")
                            import traceback
                            log.error(traceback.format_exc())
                else:
                    # ✅ NOV 11 FIX: Enhanced logging when safe_place_tp returns False
                    log.error("=" * 80)
                    log.error(f"❌ safe_place_tp() returned False on attempt {attempt + 1}/{max_retries}")
                    log.error(f"   Entry: ${entry_price:,.2f}, TP: ${tp_price:,.2f}, Size: {size}")
                    log.error("=" * 80)
                    
                    # Check API connectivity
                    try:
                        log.info("   Testing API connectivity...")
                        test_response = self.api_client.get_product(self.product_id)
                        if test_response.get('success'):
                            log.info(f"   ✅ API is responsive: {test_response.get('result', {}).get('symbol', 'N/A')}")
                        else:
                            log.error(f"   ❌ API error: {test_response.get('error', 'Unknown error')}")
                    except Exception as api_err:
                        log.error(f"   ❌ API exception: {api_err}")
            
            except Exception as e:
                log.error(f"❌ TP placement exception on attempt {attempt + 1}: {e}")
                import traceback
                log.error(traceback.format_exc())
        
        # ALL RETRIES FAILED - CRITICAL ERROR
        error_msg = (
            f"🚨 CRITICAL: TP PLACEMENT FAILED AFTER {max_retries} RETRIES\n"
            f"Position: Entry=${entry_price:,.2f}, TP=${tp_price:,.2f}, Size={size}\n"
            f"BOT HALTED - Manual intervention required!\n"
            f"ACTION: Check exchange connectivity, verify position exists, place TP manually"
        )
        log.critical(error_msg)
        
        # Send alert if notifier available
        try:
            from bot.utils.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            notifier.send(error_msg)
        except Exception:
            pass
        
        # HALT BOT - Raise exception to stop execution
        raise RuntimeError(f"TP placement failed after {max_retries} retries - bot halted")
    
    # ========================================================================
    # Order Cancellation
    # ========================================================================
    
    def verify_order_cancelled(self, order_id: str, timeout: float = None) -> bool:
        """
        Verify order was actually cancelled on the exchange
        
        ✅ NOV 10 FIX: Increased timeout to 10s based on Delta Exchange guidance
        Delta processes cancellations asynchronously - 3-6 seconds typical delay
        
        Queries exchange API to confirm order is no longer active
        
        Args:
            order_id: Order ID to verify
            timeout: Maximum wait time for verification (default: 10s per Delta guidance)
            
        Returns:
            True if order confirmed cancelled/filled/rejected, False if still active
        """
        if timeout is None:
            timeout = self.VERIFY_TIMEOUT  # Now 10.0 seconds per Delta Exchange
        
        deadline = time.time() + timeout
        check_count = 0
        
        while time.time() < deadline:
            check_count += 1
            try:
                # Query current order status from exchange
                order_status = self.api_client.get_order(order_id)
                
                if order_status.get('success'):
                    result = order_status.get('result', {})
                    state = result.get('state', '').lower()
                    
                    if state in ['cancelled', 'rejected']:
                        log.debug(f"✅ [{check_count} checks, {timeout:.1f}s] Order {order_id} confirmed {state}")
                        return True
                    elif state == 'filled':
                        log.info(f"✅ [{check_count} checks] Order {order_id} was filled (not cancelled, but no longer pending)")
                        return True
                    elif state in ['open', 'pending']:
                        log.debug(f"⏳ Check {check_count}/{int(timeout/1.0)}: Order {order_id} still {state} (Delta async processing)")
                    else:
                        log.warning(f"⚠️ Unknown order state: {state}")
                else:
                    # API returned error - check if it's a 404 (order not found)
                    error_data = order_status.get('error', {})
                    error_msg = str(error_data.get('message', '')).lower()
                    
                    if 'not found' in error_msg or 'not_found' in str(error_data.get('code', '')).lower():
                        log.info(f"✅ Order {order_id} not found (404) - already cancelled/filled")
                        return True
            
            except Exception as e:
                # Check if exception message indicates 404
                error_msg = str(e).lower()
                if '404' in error_msg or 'not found' in error_msg:
                    log.info(f"✅ Order {order_id} not found (404 exception) - already cancelled/filled")
                    return True
                log.debug(f"Error verifying order (attempt {check_count}): {e}")
            
            time.sleep(1.0)  # ✅ NOV 11 FIX: Increased from 0.5s to 1.0s per Delta guidance (gentler on rate limits)
        
        log.error(f"❌ Timeout after {check_count} checks ({timeout:.1f}s): Order {order_id} still active")
        log.error(f"   Delta Exchange async processing may need more time")
        return False
    
    def cancel_order(
        self,
        order_id: str,
        verify: bool = True,
        max_retries: int = 5
    ) -> bool:
        """
        Cancel order with aggressive retry and verification
        
        ✅ FIX NOV 6: Added pre-check to avoid 404 cascade
        
        Uses exponential backoff to retry cancellation until verified.
        This handles cases where Delta Exchange accepts the cancel but
        doesn't actually cancel the order immediately.
        
        Args:
            order_id: Order ID to cancel
            verify: Whether to verify cancellation on exchange
            max_retries: Maximum number of cancel attempts (default: 5)
            
        Returns:
            True if cancelled successfully (and verified), False otherwise
        """
        # ✅ FIX NOV 6: Pre-check order state to avoid 404 errors
        try:
            log.debug(f"🔍 Pre-checking order {order_id} state before cancel...")
            order_state = self.api_client.get_order(order_id)
            
            if order_state.get('success'):
                state = order_state.get('result', {}).get('state', '').lower()
                
                if state in ['filled', 'closed']:
                    log.info(f"✅ Order {order_id} already FILLED - skipping cancel")
                    return True
                    
                elif state in ['cancelled', 'rejected']:
                    log.info(f"✅ Order {order_id} already CANCELLED - skipping cancel")
                    return True
            else:
                # Order not found - already gone
                error = order_state.get('error', {})
                if 'not_found' in str(error).lower() or 'not found' in str(error).lower():
                    log.info(f"✅ Order {order_id} not found - already processed")
                    return True
        except Exception as e:
            # Pre-check failed, continue with cancel attempt anyway
            log.warning(f"⚠️ Pre-check failed: {e}, proceeding with cancel...")
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # Exponential backoff: 1s, 2s, 4s, 8s
                    delay = min(2 ** attempt, 8)
                    log.warning(f"🔄 Retry {attempt}/{max_retries} after {delay}s delay...")
                    time.sleep(delay)
                
                log.info(f"🗑️ Cancelling order {order_id} (attempt {attempt + 1}/{max_retries})")
                resp = self.api_client.cancel_order(order_id=order_id, product_id=self.product_id)
                
                # Log full response for debugging (as recommended by Delta AI)
                log.debug(f"Cancel API full response: {resp}")
                
                # Check cancellation API response
                if not resp.get('success'):
                    error_data = resp.get('error', {})
                    error_msg = str(error_data.get('message', 'Unknown error'))
                    error_code = str(error_data.get('code', ''))
                    
                    log.warning(f"⚠️ Cancel API response: {error_msg} (code: {error_code})")
                    
                    # Handle specific error cases
                    if any(keyword in error_msg.lower() for keyword in ['filled', 'fill']):
                        log.info(f"✅ Order already filled - will be processed by fill handler")
                        return True
                    
                    elif any(keyword in error_msg.lower() for keyword in ['not found', 'cancelled', 'does not exist', 'already processed']):
                        log.info(f"✅ Order already cancelled or not found - safe to proceed")
                        return True
                    
                    elif error_code == 'order_not_found':
                        log.info(f"✅ Order not found (error code: order_not_found) - safe to proceed")
                        return True
                    
                    # Unknown error - continue to next retry
                    continue
                
                # API succeeded - verify if requested
                if verify:
                    log.debug(f"Cancel API succeeded, verifying on exchange...")
                    # ✅ NOV 11 FIX: Increase timeout from 3s to 15s per Delta Exchange guidance
                    # Delta processes cancellations asynchronously (5-10s typical delay)
                    verified = self.verify_order_cancelled(order_id, timeout=15.0)
                    
                    if verified:
                        log.info(f"✅ Order cancellation verified by exchange")
                        return True
                    else:
                        log.warning(f"⚠️ Cancel API succeeded but order still active after 15s, will retry...")
                        # Continue to next attempt
                        continue
                else:
                    # No verification requested, trust API response
                    return True
            
            except Exception as e:
                log.error(f"❌ Exception during cancel attempt {attempt + 1}: {e}")
                # Continue to next retry
                continue
        
        # All retries exhausted
        log.critical(f"🚨 CRITICAL: Failed to cancel order {order_id} after {max_retries} attempts!")
        
        # Final verification check with extended timeout
        try:
            log.info(f"🔍 Final verification with 10s timeout (order may have cancelled during retries)...")
            final_check = self.verify_order_cancelled(order_id, timeout=10.0)  # ✅ NOV 11 FIX: Increased from 2s to 10s
            if final_check:
                log.info(f"✅ Final check: Order {order_id} is cancelled")
                return True
        except Exception as e:
            log.error(f"❌ Final verification failed: {e}")
        
        return False
    
    def cancel_all_buy_orders(self) -> Dict[str, int]:
        """
        Cancel all open BUY orders (not reduce_only)
        
        Returns:
            Dict with 'cancelled' and 'failed' counts
        """
        try:
            orders_response = self.api_client.list_orders(product_id=self.product_id, state="open")
            
            if not orders_response.get('success'):
                log.error(f"❌ Could not fetch orders: {orders_response}")
                return {'cancelled': 0, 'failed': 0}
            
            all_orders = orders_response.get('result', [])
            buy_orders = []
            
            # Find BUY orders (not reduce_only)
            for order in all_orders:
                side = order.get('side', '').lower()
                state = order.get('state', '').lower()
                is_reduce_only = order.get('close_on_trigger', False) or order.get('reduce_only', False)
                
                if state not in ['filled', 'cancelled', 'rejected'] and side == 'buy' and not is_reduce_only:
                    buy_orders.append(order)
            
            log.info(f"🔍 Found {len(buy_orders)} BUY orders to cancel")
            
            cancelled_count = 0
            failed_count = 0
            
            for order in buy_orders:
                order_id = order.get('id')
                if self.cancel_order(order_id, verify=False):
                    cancelled_count += 1
                else:
                    failed_count += 1
                
                time.sleep(self.RATE_LIMIT_DELAY)  # Rate limiting using class constant
            
            log.info(f"✅ Cancelled {cancelled_count} BUY orders, {failed_count} failed")
            return {'cancelled': cancelled_count, 'failed': failed_count}
        
        except Exception as e:
            log.error(f"❌ Error cancelling BUY orders: {e}")
            return {'cancelled': 0, 'failed': 0}
    
    # ========================================================================
    # Bulk Cancellation (for Graceful Shutdown)
    # ========================================================================
    
    def cancel_all_orders_bulk(self, timeout: float = 15.0) -> bool:
        """
        Cancel all orders using Delta's bulk cancel API (recommended for shutdown)
        
        This uses the /orders/all endpoint which is optimized for bulk cancellation
        scenarios like graceful shutdown. More reliable than individual cancellations.
        
        Based on Delta Exchange recommendation for shutdown scenarios.
        
        ⚠️ CRITICAL: Only cancels BUY orders (limit/stop), NOT reduce-only orders (TP/SL)
        This preserves target price orders to protect existing positions.
        
        NOTE: Delta Exchange processes cancellations asynchronously. The API returns
        success=True immediately, but actual order state update may be delayed.
        Extended timeout to 15s to account for processing delays.
        
        Args:
            timeout: Maximum time to wait for verification (seconds, default: 15)
            
        Returns:
            True if all orders cancelled successfully, False otherwise
        """
        try:
            log.info("🗑️ Initiating bulk cancellation (cancel_all API)...")
            log.info("⚠️ IMPORTANT: Canceling only BUY orders, preserving TP/SELL orders")
            
            # Call Delta's bulk cancel API
            # ✅ CRITICAL FIX: Set cancel_reduce_only_orders="false" to preserve TP orders
            cancel_resp = self.api_client.cancel_all_orders(
                product_id=self.product_id,
                cancel_limit_orders="true",
                cancel_stop_orders="true",
                cancel_reduce_only_orders="false"  # ✅ DO NOT cancel TP orders!
            )
            
            # Log full response for debugging
            log.debug(f"Bulk cancel API response: {cancel_resp}")
            
            if not cancel_resp.get('success'):
                log.error(f"❌ Bulk cancel failed: {cancel_resp}")
                return False
            
            log.info("✅ Bulk cancel API call successful, verifying...")
            log.info(f"⏳ Waiting up to {timeout}s for async processing (checking every 500ms)")
            
            # Wait for orders to be cancelled (with extended timeout for async processing)
            deadline = time.time() + timeout
            check_count = 0
            
            while time.time() < deadline:
                check_count += 1
                time.sleep(0.5)  # Check every 500ms
                
                try:
                    # Query open orders
                    orders_resp = self.api_client.list_orders(
                        product_id=self.product_id, 
                        state="open"
                    )
                    
                    if orders_resp.get('success'):
                        open_orders = orders_resp.get('result', [])
                        
                        if not open_orders:
                            log.info(f"✅ All orders cancelled (verified after {check_count} checks)")
                            return True
                        
                        # Filter for non-reduce-only orders (our BUY orders)
                        non_tp_orders = [
                            o for o in open_orders 
                            if not o.get('reduce_only', False)
                        ]
                        
                        if not non_tp_orders:
                            log.info(f"✅ All BUY orders cancelled (only TP orders remain)")
                            return True
                        
                        log.debug(f"⏳ Check {check_count}: {len(non_tp_orders)} orders still open")
                    
                except Exception as e:
                    log.warning(f"⚠️ Error during verification (check {check_count}): {e}")
            
            # Timeout reached - do final check
            log.warning(f"⏱️ Verification timeout after {timeout}s ({check_count} checks)")
            
            final_resp = self.api_client.list_orders(product_id=self.product_id, state="open")
            if final_resp.get('success'):
                remaining = final_resp.get('result', [])
                non_tp = [o for o in remaining if not o.get('reduce_only', False)]
                
                if not non_tp:
                    log.info("✅ Final check: All BUY orders cancelled")
                    return True
                else:
                    log.error(f"❌ Final check: {len(non_tp)} orders still open")
                    for order in non_tp[:3]:  # Log first 3
                        log.error(f"   - Order ID: {order.get('id')}, Side: {order.get('side')}")
                    return False
            
            return False
            
        except Exception as e:
            log.error(f"❌ Bulk cancellation exception: {e}")
            import traceback
            log.error(traceback.format_exc())
            return False
    
    def _final_verification_all_cancelled(self) -> bool:
        """
        ✅ IMPROVEMENT #2: Final verification after bulk cancel
        
        Extra safety layer: Query exchange one final time to confirm
        absolutely zero bot BUY orders remain on the exchange.
        
        This catches edge cases where async processing delays or
        API inconsistencies might leave orphaned orders.
        
        Returns:
            True if confirmed zero bot orders, False if any remain
        """
        try:
            log.info("🔍 Final verification: Confirming zero bot orders on exchange...")
            
            # Query all open orders
            orders_resp = self.api_client.list_orders(
                product_id=self.product_id,
                state="open"
            )
            
            if not orders_resp.get('success'):
                log.warning(f"⚠️ Final verification failed to query orders: {orders_resp}")
                return False  # Conservative: assume orders may remain
            
            all_orders = orders_resp.get('result', [])
            
            # Find bot BUY orders (client_order_id starts with "BOT-" and not reduce_only)
            bot_buy_orders = [
                o for o in all_orders
                if (o.get('side', '').lower() == 'buy' and
                    not o.get('reduce_only', False) and
                    o.get('client_order_id', '').startswith('BOT-'))
            ]
            
            if not bot_buy_orders:
                log.info("✅ Final verification PASSED: Zero bot BUY orders on exchange")
                return True
            else:
                log.error("=" * 70)
                log.error(f"🚨 FINAL VERIFICATION FAILED: {len(bot_buy_orders)} bot BUY orders still on exchange!")
                for order in bot_buy_orders:
                    order_id = order.get('id')
                    price = order.get('limit_price', 0)
                    client_id = order.get('client_order_id', '')
                    log.error(f"   - Order ID: {order_id}, Price: ${price}, Client ID: {client_id}")
                log.error("   These orders were NOT cancelled by bulk cancel!")
                log.error("   Manual intervention may be required.")
                log.error("=" * 70)
                
                return False
        except Exception as e:
            log.error(f"❌ Final verification exception: {e}")
            return False  # Conservative: assume orders may remain
    
    # ========================================================================
    # ✅ FIX NOV 9: Aggressive Order Polling for Fill Detection
    # ========================================================================
    
    def _start_order_polling(self, order_id: str, side: str, price: float):
        """
        Start continuous polling thread to detect fills with guaranteed detection.
        
        ✅ FIX NOV 11: Changed from 30-second polling to continuous monitoring
        - Polls every 3 seconds until fill detected or order cancelled
        - Maximum 10 minutes (200 checks) to prevent infinite loops
        - Includes exponential backoff on errors
        - Guaranteed to catch fills even if they happen hours later
        
        Args:
            order_id: Order ID to monitor
            side: 'buy' or 'sell'
            price: Order price (for logging)
        """
        if not hasattr(self, '_polling_threads'):
            self._polling_threads = {}
        if not hasattr(self, '_polling_stop_flags'):
            self._polling_stop_flags = {}
        
        # Don't start duplicate polling
        if order_id in self._polling_threads:
            log.debug(f"Polling already active for order {order_id}")
            return
        
        def polling_loop():
            """Continuous polling with exponential backoff on errors"""
            log.info(f"🔄 [POLLING] Started continuous monitoring for {side.upper()} order {order_id} @ ${price:,.0f}")
            log.info(f"   Will poll every 3s until filled, cancelled, or max 10 minutes")
            
            checks = 0
            max_checks = 200  # 200 checks * 3s = 10 minutes max
            consecutive_errors = 0
            max_consecutive_errors = 10
            last_partial_fill_size = 0  # Track last reported partial fill to avoid spam
            
            while checks < max_checks:
                # Check stop flag
                if order_id in self._polling_stop_flags and self._polling_stop_flags[order_id]:
                    log.info(f"🛑 [POLLING] Stop requested for order {order_id}")
                    break
                
                checks += 1
                
                # Exponential backoff: 3s normal, up to 10s if errors
                poll_interval = min(3.0 + (consecutive_errors * 0.5), 10.0)
                time.sleep(poll_interval)
                
                try:
                    # Query order status from exchange
                    order_resp = self.api_client.get_order(order_id)
                    
                    if not order_resp.get('success') or 'result' not in order_resp:
                        consecutive_errors += 1
                        log.warning(f"[POLLING] Check {checks}/{max_checks}: Failed to query order {order_id} (errors: {consecutive_errors})")
                        
                        if consecutive_errors >= max_consecutive_errors:
                            log.error(f"❌ [POLLING] Too many errors ({consecutive_errors}), stopping polling for {order_id}")
                            break
                        continue
                    
                    # Reset error counter on success
                    consecutive_errors = 0
                    
                    order = order_resp['result']
                    state = order.get('state', '')
                    filled_size = float(order.get('size', 0) or 0)
                    unfilled_size = float(order.get('unfilled_size', 0) or 0)
                    
                    # Log every 20 checks (every minute) to avoid spam
                    if checks % 20 == 0:
                        log.debug(f"[POLLING] Check {checks}/{max_checks}: Order {order_id} state={state}, filled={filled_size}, unfilled={unfilled_size}")
                    
                    # Check if fully filled
                    if state == 'filled':
                        log.info(f"🎯 [POLLING] FILL DETECTED! Order {order_id} is FULLY FILLED")
                        log.info(f"   Took {checks * poll_interval:.0f}s ({checks} checks) to detect")
                        
                        # Get fill details
                        avg_price = float(order.get('average_fill_price') or order.get('limit_price') or price)
                        fill_size = float(order.get('size', self.lot_size))
                        
                        # Trigger fill detection manually since WebSocket may have missed it
                        fill_data = {
                            'order_id': order_id,
                            'fill_price': avg_price,
                            'fill_size': fill_size,
                            'is_complete': True,
                            'cumulative_filled': fill_size,
                            'total_order_size': fill_size,
                            'side': side,
                            '_detected_via': 'continuous_polling',
                            '_poll_checks': checks
                        }
                        
                        # Send to fill detector via gridbot's process_fill
                        if hasattr(self, 'bot') and hasattr(self.bot, 'fill_detector'):
                            try:
                                log.info(f"📥 [POLLING] Sending fill to fill_detector queue...")
                                self.bot.fill_detector.process_websocket_fill(fill_data)
                                log.info(f"✅ [POLLING] Fill queued for processing")
                            except Exception as e:
                                log.error(f"❌ [POLLING] Fill processing failed: {e}")
                                import traceback
                                log.error(traceback.format_exc())
                        else:
                            log.error(f"❌ [POLLING] Cannot access fill_detector!")
                        
                        # Stop polling - fill detected
                        break
                    
                    # Check for partial fills
                    elif state == 'open' and filled_size > 0:
                        total_size = filled_size + unfilled_size
                        
                        # Only log if:
                        # 1. Order is for multiple lots (total_size > 1)
                        # 2. Partial fill size has changed (not spam from same status)
                        if total_size > 1 and filled_size != last_partial_fill_size:
                            log.info(f"⚠️ [POLLING] Partial fill detected: {filled_size}/{total_size} filled")
                            last_partial_fill_size = filled_size
                        # Continue polling for full fill
                    
                    # Check if cancelled or rejected
                    elif state in ['cancelled', 'rejected']:
                        log.info(f"⚠️ [POLLING] Order {order_id} is {state} - stopping polling")
                        break
                
                except Exception as e:
                    consecutive_errors += 1
                    log.error(f"❌ [POLLING] Error checking order {order_id}: {e}")
                    if consecutive_errors >= max_consecutive_errors:
                        log.error(f"❌ [POLLING] Too many consecutive errors, stopping polling")
                        break
            
            # Check if max time reached
            if checks >= max_checks:
                log.warning(f"⚠️ [POLLING] Max polling time (10 min) reached for order {order_id}")
                log.warning(f"   Order may still be pending. Reconciliation system will catch it.")
            
            # Cleanup
            log.info(f"✅ [POLLING] Stopped for order {order_id} after {checks} checks")
            if order_id in self._polling_threads:
                del self._polling_threads[order_id]
            if order_id in self._polling_stop_flags:
                del self._polling_stop_flags[order_id]
            
            log.info(f"✅ [POLLING] Stopped for order {order_id} after {checks} checks")
        
        # Start polling thread
        thread = threading.Thread(
            target=polling_loop,
            name=f"OrderPolling-{order_id}",
            daemon=True
        )
        self._polling_threads[order_id] = thread
        self._polling_stop_flags[order_id] = False  # ✅ FIX NOV 11: Initialize stop flag
        thread.start()
    
    def stop_order_polling(self, order_id: str):
        """
        Stop polling for a specific order.
        ✅ FIX NOV 11: Added method to gracefully stop polling
        
        Args:
            order_id: Order ID to stop polling for
        """
        if order_id in self._polling_stop_flags:
            self._polling_stop_flags[order_id] = True
            log.info(f"🛑 Requested stop for polling thread: {order_id}")
    
    def set_fill_callback(self, callback: Callable):
        """Set callback function to trigger when fill is detected via polling"""
        self._fill_callback = callback
        log.info(f"✅ Fill callback registered for aggressive polling")
