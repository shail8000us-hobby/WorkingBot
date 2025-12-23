"""
SHORT Mode Fill Handler

Handles SELL order fills and TP fills for SHORT positions.
Supports partial fills with incremental position creation.
"""

import logging
import threading
import time
from typing import Dict

log = logging.getLogger("runner")


class ShortFillHandler:
    """
    Handle SHORT mode fills (SELL entry, BUY TP)
    
    ✅ NOV 8: PARTIAL FILL SUPPORT - NEW IMPLEMENTATION
    - Each partial fill creates separate position
    - Each partial fill gets its own TP order
    - Next grid order placed only when order 100% filled
    """
    
    def __init__(self, bot):
        """
        Initialize handler with bot reference
        
        Args:
            bot: GridBot instance (provides access to managers)
        """
        self.bot = bot
        self.order_mgr = bot.order_mgr
        self.position_mgr = bot.position_mgr
        self.grid_calc = bot.grid_calc
        self.lot = bot.lot
        self.last_sell_order_time = getattr(bot, 'last_sell_order_time', 0)
    
    def _check_order_throttle(self, order_type: str) -> bool:
        """
        ✅ FIX NOV 9: Extracted throttle check to helper method
        
        Args:
            order_type: 'BUY' or 'SELL'
            
        Returns:
            True if order can be placed, False if throttled
        """
        last_order_time = self.bot.last_buy_order_time if order_type == 'BUY' else self.bot.last_sell_order_time
        
        if last_order_time:
            time_since_last = time.time() - last_order_time
            if time_since_last < self.bot.min_order_gap_seconds:
                log.warning(f"🚦 THROTTLE: Last {order_type} was {time_since_last:.1f}s ago (min: {self.bot.min_order_gap_seconds}s)")
                log.warning(f"   Skipping order to prevent duplicate")
                return False
        
        return True
    
    def handle_sell_fill(self, fill_data: Dict):
        """
        Handle SELL order fill (entry order for SHORT position)
        
        ✅ PARTIAL FILL SUPPORT:
        - Creates position for INCREMENTAL fill size (not full order size)
        - Places TP (BUY back) for INCREMENTAL fill size
        - Only clears pending_sell and places next grid order when is_complete=True
        
        Example: 100-lot SHORT order fills in 3 parts:
          Fill 1: 10 lots → Position 1 (10 lots SHORT) + TP 1 (BUY 10 lots)
          Fill 2: 47 lots → Position 2 (47 lots SHORT) + TP 2 (BUY 47 lots)
          Fill 3: 43 lots → Position 3 (43 lots SHORT) + TP 3 (BUY 43 lots) + Next grid SELL
        
        Args:
            fill_data: Dict with fill_size, fill_price, is_complete, etc.
        """
        order_id = fill_data.get('order_id')
        fill_price = fill_data.get('fill_price', 0)
        fill_size = fill_data.get('fill_size', 0)  # ← INCREMENTAL size
        is_complete = fill_data.get('is_complete', False)
        cumulative = fill_data.get('cumulative_filled', 0)
        total_size = fill_data.get('total_order_size', 0)
        
        log.info(f"✅ SELL incremental fill: {fill_size} lots @ ${fill_price:,.0f}")
        
        # Track order fill for anomaly detection
        if hasattr(self.bot, 'anomaly_detector') and self.bot.anomaly_detector:
            try:
                self.bot.anomaly_detector.track_order_fill(order_id)
            except Exception as e:
                log.debug(f"Error tracking order fill: {e}")
        
        # Calculate TP price (BUY back at lower price for profit)
        tp_price = self.grid_calc.compute_tp_price_short(fill_price)
        
        # Create position for THIS INCREMENTAL FILL ONLY
        position = {
            'sell_order_id': order_id,
            'entry_price': fill_price,
            'tp_price': tp_price,
            'size': fill_size,  # ← INCREMENTAL size
            'timestamp': time.time(),
            'protected': False,
            'side': 'short',  # Mark as SHORT position
            'fill_sequence': cumulative  # Track which fill this was
        }
        
        # Add position to manager
        self.position_mgr.add_position(position)
        
        # Place TP (BUY order to close SHORT) for THIS INCREMENTAL FILL ONLY
        tp_success = self.order_mgr.safe_place_tp(position)
        
        # 🔍 LAYER 3: TP Verification (NOV 8)
        # Verify TP was placed correctly and track for anomaly detection
        try:
            self.bot.tp_verifier.verify_tp_placement(position, check_exchange=False)
            
            # Track TP placement for anomaly detection
            if position.get('tp_order_id'):
                self.bot.anomaly_detector.track_tp_placement(
                    position_order_id=order_id,
                    tp_order_id=position['tp_order_id']
                )
        except Exception as e:
            log.debug(f"TP verification error: {e}")
        
        if tp_success:
            log.info(f"🛡️ TP (BUY) placed: {fill_size} lots @ ${tp_price:,.0f}")
            position['protected'] = True
        else:
            # 🚨 CRITICAL: TP placement failed!
            log.critical("=" * 80)
            log.critical(f"🚨 CRITICAL: TP PLACEMENT FAILED (SHORT)!")
            log.critical(f"   Incremental Fill: {fill_size} lots")
            log.critical(f"   SHORT Entry: ${fill_price:,.0f}")
            log.critical(f"   Expected TP (BUY): ${tp_price:,.0f}")
            log.critical(f"   STATUS: UNPROTECTED - NO STOP LOSS!")
            log.critical("=" * 80)
            
            # Schedule retry
            self.position_mgr.schedule_tp_retry(position)
            
            # Send Telegram alert
            try:
                from bot.utils.notifier import TelegramNotifier
                notifier = TelegramNotifier()
                alert_msg = (
                    f"🚨 CRITICAL: TP PLACEMENT FAILED (SHORT)!\n\n"
                    f"Incremental Fill: {fill_size} lots\n"
                    f"SHORT Entry: ${fill_price:,.0f}\n"
                    f"Expected TP (BUY): ${tp_price:,.0f}\n"
                    f"Status: UNPROTECTED\n\n"
                    f"⚠️ MANUAL INTERVENTION REQUIRED!"
                )
                notifier.send(alert_msg)
            except Exception as e:
                log.error(f"Failed to send Telegram alert: {e}")
        
        # ✅ KEY: Only clear pending_sell and place next grid order when ORDER COMPLETE
        if is_complete:
            log.info(f"✅ Order {order_id} FULLY FILLED ({cumulative}/{total_size} lots) - placing next grid order")
            
            # 🔒 BULLETPROOF NOV 8: Check throttle BEFORE clearing pending_sell
            # This prevents race condition where:
            # 1. Clear pending_sell
            # 2. Heartbeat sees no pending → places duplicate
            # 3. Handler places order
            time_since_last = None
            if self.bot.last_sell_order_time:
                time_since_last = time.time() - self.bot.last_sell_order_time
                if time_since_last < self.bot.min_order_gap_seconds:
                    log.warning(f"🚦 THROTTLE: Last SELL was {time_since_last:.1f}s ago (min: {self.bot.min_order_gap_seconds}s)")
                    log.warning(f"   Skipping next grid order to prevent duplicate")
                    # Don't clear pending_sell yet - let reconciliation handle it after throttle expires
                    return
            
            # Clear pending sell (order is now complete)
            self.position_mgr.clear_pending_sell()
            
            # Place next SELL if capacity available AND volatility is safe
            if self.position_mgr.try_reserve_capacity():
                next_price = self.grid_calc.compute_next_level_up(fill_price)
                if self.grid_calc.is_within_bounds(next_price):
                    # 🔒 BULLETPROOF NOV 8: Check throttle before placing order
                    time_since_last = None
                    if self.bot.last_sell_order_time:
                        time_since_last = time.time() - self.bot.last_sell_order_time
                        if time_since_last < self.bot.min_order_gap_seconds:
                            log.warning(f"🚦 THROTTLE: Last SELL was {time_since_last:.1f}s ago (min: {self.bot.min_order_gap_seconds}s)")
                            log.warning(f"   Skipping order after fill to prevent duplicate")
                            self.position_mgr.release_capacity()  # Release reserved capacity
                            return
                    
                    # Check volatility BEFORE placing next order
                    try:
                        from bot.volatility.iv_rv_tracker import get_volatility_tracker
                        vol_tracker = get_volatility_tracker()
                        
                        if vol_tracker:
                            can_trade, halt_reason = vol_tracker.can_trade()
                            
                            if can_trade:
                                # Volatility safe - place order
                                order_id = self.order_mgr.place_sell_order(next_price)
                                if order_id:
                                    self.position_mgr.set_pending_sell({
                                        'order_id': order_id,
                                        'price': next_price,
                                        'timestamp': time.time()
                                    })
                                    # ✅ FIX NOV 8: Record timestamp
                                    self.bot.last_sell_order_time = time.time()
                                    log.info(f"✅ Next SELL placed @ ${next_price:,.0f} (Volatility: SAFE)")
                            else:
                                log.warning(f"🌊 VOLATILITY UNSAFE - SELL order blocked ({halt_reason})")
                        else:
                            # No tracker - place order anyway (fallback)
                            order_id = self.order_mgr.place_sell_order(next_price)
                            if order_id:
                                self.position_mgr.set_pending_sell({
                                    'order_id': order_id,
                                    'price': next_price,
                                    'timestamp': time.time()
                                })
                                # ✅ FIX NOV 8: Record timestamp
                                self.bot.last_sell_order_time = time.time()
                    except Exception as e:
                        log.error(f"Error checking volatility: {e}")
                        # Fallback: place order anyway
                        order_id = self.order_mgr.place_sell_order(next_price)
                        if order_id:
                            self.position_mgr.set_pending_sell({
                                'order_id': order_id,
                                'price': next_price,
                                'timestamp': time.time()
                            })
                            # Record timestamp for throttle
                            self.bot.last_sell_order_time = time.time()
        else:
            log.info(f"⏳ Order {order_id} still filling ({cumulative}/{total_size} lots) - waiting for more fills...")
    
    def handle_tp_fill_short(self, fill_price: float, position: Dict):
        """
        Handle TP fill for SHORT position (BUY order closes SHORT)
        
        ✅ NOV 10: ASYNC ORDER REPLACEMENT ARCHITECTURE
        
        CRITICAL LOGIC:
        When a SHORT TP fills (market moved DOWN and hit lower grid level):
        1. IMMEDIATELY place new SELL order ONE STEP above filled TP (non-blocking)
        2. ASYNCHRONOUSLY cancel the old pending SELL order in background thread
        
        This reversal prevents price staleness issues:
        - Old approach: Cancel first (blocks 43s on retries) → Place later (price stale ❌)
        - New approach: Place first (instant ✅) → Cancel later (async, non-blocking)
        
        Example: Grid step = $500
        - Entry SELL at $101,000 → TP BUY at $100,500 (1 step down)
        - Market moves down, TP fills at $100,500
        - IMMEDIATELY place new SELL at $101,000 (1 step above TP)
        - BACKGROUND: Cancel old SELL at $101,500 (2 steps above TP)
        
        Edge cases handled:
        - If old order already filled: Fill handler processes it normally
        - If cancel fails after 5 mins: Reconciliation absorbs as valid grid order
        - If new placement fails: Error logged, reconciliation will fix on next cycle
        
        Args:
            fill_price: Price at which TP filled (BUY price)
            position: SHORT position that was closed
        """
        entry = position['entry_price']
        size = position.get('size', self.lot)
        profit = (entry - fill_price) * size
        
        log.info(f"💰 SHORT TP FILLED @ ${fill_price:,.0f} - PROFIT: ${profit:.2f}!")
        
        # Track completed loop in predictive display
        # ✅ FIX NOV 12: Use self.bot instead of self.parent (AttributeError fix)
        if hasattr(self.bot, 'predictive_display'):
            self.bot.predictive_display.add_completed_loop(
                entry_price=entry,
                exit_price=fill_price,
                profit=profit,
                grid_mode='SHORT'
            )
        
        # Remove position
        self.position_mgr.remove_position(position)
        
        # ✅ STEP 1: IMMEDIATELY place new SELL order (non-blocking)
        if self.position_mgr.try_reserve_capacity():
            next_price = self.grid_calc.compute_next_level_up(fill_price)
            
            log.info("")
            log.info(f"📍 IMMEDIATE: Placing new SELL order:")
            log.info(f"   TP filled at: ${fill_price:,.0f}")
            log.info(f"   New SELL target: ${next_price:,.0f} (1 step above TP)")
            
            if self.grid_calc.is_within_bounds(next_price):
                # Check throttle
                if not self._check_order_throttle('SELL'):
                    self.position_mgr.release_capacity()
                    log.warning("⚠️  Order throttled - will retry on next heartbeat")
                    return
                
                # Check volatility before placing order
                try:
                    from bot.volatility.iv_rv_tracker import get_volatility_tracker
                    vol_tracker = get_volatility_tracker()
                    
                    if vol_tracker:
                        can_trade, halt_reason = vol_tracker.can_trade()
                        
                        if not can_trade:
                            log.warning(f"🌊 VOLATILITY UNSAFE - SELL order blocked ({halt_reason})")
                            self.position_mgr.release_capacity()
                            return
                except Exception as e:
                    log.debug(f"Volatility check error (non-critical): {e}")
                
                # Place the new order IMMEDIATELY
                order_id = self.order_mgr.place_sell_order(next_price)
                if order_id:
                    # Register immediately to prevent race conditions
                    self.position_mgr.set_pending_sell({
                        'order_id': order_id,
                        'price': next_price,
                        'timestamp': time.time()
                    })
                    self.bot.last_sell_order_time = time.time()
                    
                    log.info("=" * 70)
                    log.info(f"✅ NEW ORDER PLACED IMMEDIATELY @ ${next_price:,.0f}")
                    log.info(f"   Order ID: {order_id}")
                    log.info(f"   Price: ${next_price:,.0f} (1 step above TP @ ${fill_price:,.0f})")
                    log.info(f"   This order is LIVE and ready to catch market moves")
                    log.info("=" * 70)
                else:
                    log.error(f"❌ Failed to place new SELL order at ${next_price:,.0f}")
                
                self.position_mgr.release_capacity()
            else:
                log.warning(f"⚠️  Cannot place new SELL at ${next_price:,.0f} - price out of grid bounds")
                log.info(f"   Grid range: ${self.grid_calc.lower:,.0f} - ${self.grid_calc.upper:,.0f}")
                self.position_mgr.release_capacity()
        else:
            log.warning("⚠️  Cannot place new order - max capacity reached")
        
        # ✅ STEP 2: ASYNCHRONOUSLY cancel old stale order (non-blocking background)
        old_pending = self.position_mgr.get_pending_sell()
        if old_pending:
            old_order_id = old_pending.get('order_id')
            old_price = old_pending.get('price')
            
            distance_from_tp = old_price - fill_price
            expected_distance = 2 * self.grid_calc.step
            
            log.info("")
            log.info("=" * 70)
            log.info(f"� BACKGROUND: Scheduling old order cancellation:")
            log.info(f"   TP filled at: ${fill_price:,.0f}")
            log.info(f"   Old SELL at: ${old_price:,.0f} (Order ID: {old_order_id})")
            log.info(f"   Distance: ${distance_from_tp:,.0f} (Expected 2-step: ${expected_distance:,.0f})")
            
            # Validation warning (non-blocking)
            if abs(distance_from_tp - expected_distance) > self.grid_calc.tick_size:
                log.warning(f"⚠️  WARNING: Stale order distance mismatch!")
                log.warning(f"   Expected: ${expected_distance:,.0f}, Got: ${distance_from_tp:,.0f}")
                log.warning(f"   Will cancel anyway to maintain grid integrity")
            
            # Schedule async cancellation (5 retries, 60s interval)
            self._schedule_order_cancellation(
                order_id=old_order_id,
                price=old_price,
                max_retries=5,
                retry_interval=60
            )
            
            # Optimistically clear from state (reconciliation will fix if cancel fails)
            self.position_mgr.clear_pending_sell()
            
            log.info(f"   Scheduled 5-minute background cleanup (1 retry/minute)")
            log.info(f"   If cancel fails, reconciliation will absorb into grid")
        else:
            log.info("")
            log.info(f"ℹ️  No old pending order to cancel (might have been cancelled already)")
    
    def _schedule_order_cancellation(self, order_id: str, price: float, max_retries: int, retry_interval: int):
        """
        Schedule background order cancellation with retries
        
        ✅ NOV 10: Async cleanup worker for stale orders
        
        Runs in background thread and retries cancellation every minute for up to 5 minutes.
        If order still exists after all retries, reconciliation will absorb it into the grid
        as a valid (though misplaced) grid order.
        
        Edge case handling:
        - If order fills during cancellation: Fill handler processes it normally
        - If order doesn't exist (404): Success - exit immediately
        - If API errors persist: Give up after max_retries, let reconciliation handle
        
        Args:
            order_id: Order ID to cancel
            price: Order price (for logging)
            max_retries: Maximum number of cancel attempts (default: 5)
            retry_interval: Seconds between retries (default: 60)
        """
        def cancel_worker():
            """Background worker thread for order cancellation"""
            thread_name = f"cancel-{order_id[-6:]}"
            
            for attempt in range(1, max_retries + 1):
                try:
                    log.info(f"🔄 [{thread_name}] Cancellation attempt {attempt}/{max_retries} for order {order_id}")
                    
                    # Check if order still exists before attempting cancel
                    try:
                        order_status = self.order_mgr.api_client.get_order(order_id)
                        
                        if order_status.get('success'):
                            state = order_status.get('result', {}).get('state', '').lower()
                            
                            if state == 'filled':
                                log.info(f"✅ [{thread_name}] Order filled during cleanup - processing via fill handler")
                                return
                            
                            if state in ['cancelled', 'rejected']:
                                log.info(f"✅ [{thread_name}] Order already {state} - cleanup complete")
                                return
                        else:
                            error = order_status.get('error', {})
                            if 'not_found' in str(error).lower() or 'not found' in str(error).lower():
                                log.info(f"✅ [{thread_name}] Order not found (404) - cleanup complete")
                                return
                    except Exception as e:
                        error_msg = str(e).lower()
                        if '404' in error_msg or 'not found' in error_msg:
                            log.info(f"✅ [{thread_name}] Order not found (404) - cleanup complete")
                            return
                    
                    # Attempt cancellation (verify=True uses 10s timeout per Delta guidance)
                    cancel_success = self.order_mgr.cancel_order(order_id, verify=True)
                    
                    if cancel_success:
                        log.info(f"✅ [{thread_name}] Order cancelled successfully @ ${price:,.0f}")
                        return
                    else:
                        log.warning(f"⚠️  [{thread_name}] Cancel failed (attempt {attempt}/{max_retries})")
                        log.warning(f"   Delta Exchange async processing may need more time")
                        
                        if attempt < max_retries:
                            log.info(f"   ⏳ Retrying in {retry_interval}s...")
                            time.sleep(retry_interval)
                
                except Exception as e:
                    log.error(f"❌ [{thread_name}] Exception during cancel attempt {attempt}: {e}")
                    
                    if attempt < max_retries:
                        time.sleep(retry_interval)
            
            # All retries exhausted - order persists (likely filled or Delta processing delay)
            log.warning("=" * 70)
            log.warning(f"⚠️  [{thread_name}] CLEANUP TIMEOUT: Order {order_id} still exists after {max_retries} attempts")
            log.warning(f"   Order: SELL @ ${price:,.0f}")
            log.warning(f"   Tried {max_retries} times over {max_retries * retry_interval // 60} minutes")
            log.warning(f"   Possible reasons:")
            log.warning(f"   1. Order was filled during cleanup (check fill logs)")
            log.warning(f"   2. Delta Exchange async processing delay (3-6s typical)")
            log.warning(f"   3. High volume causing matching engine queue delays")
            log.warning(f"   Reconciliation will detect and absorb this as valid grid order")
            log.warning(f"   This is SAFE - order is on-grid and will function normally")
            log.warning("=" * 70)
        
        # Launch worker thread (daemon=True so it doesn't block shutdown)
        worker_thread = threading.Thread(
            target=cancel_worker,
            daemon=True,
            name=f"cancel-{order_id[-6:]}"
        )
        worker_thread.start()
        
        log.debug(f"✅ Background cancellation thread started: {worker_thread.name}")
