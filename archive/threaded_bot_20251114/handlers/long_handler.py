"""
LONG Mode Fill Handler

Handles BUY order fills and TP fills for LONG positions.
Supports partial fills with incremental position creation.

✅ NOV 10: Async order replacement - place first, cleanup later
"""

import logging
import time
import threading
from typing import Dict

log = logging.getLogger("runner")


class LongFillHandler:
    """
    Handle LONG mode fills (BUY entry, SELL TP)
    
    ✅ NOV 8: PARTIAL FILL SUPPORT
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
    
    def handle_buy_fill(self, fill_data: Dict):
        """
        Handle BUY order fill (entry order for LONG position)
        
        ✅ PARTIAL FILL SUPPORT:
        - Creates position for INCREMENTAL fill size (not full order size)
        - Places TP for INCREMENTAL fill size
        - Only clears pending_buy and places next grid order when is_complete=True
        
        Example: 100-lot order fills in 3 parts:
          Fill 1: 10 lots → Position 1 (10 lots) + TP 1 (10 lots)
          Fill 2: 47 lots → Position 2 (47 lots) + TP 2 (47 lots)
          Fill 3: 43 lots → Position 3 (43 lots) + TP 3 (43 lots) + Next grid order
        
        Args:
            fill_data: Dict with fill_size, fill_price, is_complete, etc.
        """
        order_id = fill_data.get('order_id')
        fill_price = fill_data.get('fill_price', 0)
        fill_size = fill_data.get('fill_size', 0)  # ← INCREMENTAL size
        is_complete = fill_data.get('is_complete', False)
        cumulative = fill_data.get('cumulative_filled', 0)
        total_size = fill_data.get('total_order_size', 0)
        
        log.info(f"✅ BUY incremental fill: {fill_size} lots @ ${fill_price:,.0f}")
        log.info(f"🔍 [FILL DEBUG] long_handler.handle_buy_fill called with: order_id={order_id}, price={fill_price}, size={fill_size}, is_complete={is_complete}")
        
        # Track order fill for anomaly detection
        if hasattr(self.bot, 'anomaly_detector') and self.bot.anomaly_detector:
            try:
                self.bot.anomaly_detector.track_order_fill(order_id)
            except Exception as e:
                log.debug(f"Error tracking order fill: {e}")
        
        # Calculate TP price for this fill
        tp_price = self.grid_calc.compute_tp_price(fill_price)
        
        # Create position for THIS INCREMENTAL FILL ONLY
        position = {
            'buy_order_id': order_id,
            'entry_price': fill_price,
            'tp_price': tp_price,
            'size': fill_size,  # ← INCREMENTAL size (could be 1, 10, 47 lots)
            'timestamp': time.time(),
            'protected': False,
            'fill_sequence': cumulative  # Track which fill this was (10, 57, 100...)
        }
        
        # Add position to manager
        self.position_mgr.add_position(position)
        
        # 🔥 FIX NOV 9: Use MANDATORY TP placement with retries
        # This will halt bot if TP cannot be placed after all retries
        try:
            tp_order_id = self.order_mgr.place_tp_mandatory(position, max_retries=5)
            
            # ✅ FIX NOV 9: Verify tp_id is set in position after placement
            if not position.get('tp_id'):
                log.critical(f"🚨 CRITICAL: TP placement returned success but tp_id not set in position!")
                log.critical(f"   This indicates a wiring bug in place_tp_mandatory()")
                raise RuntimeError("TP ID not set in position after placement")
            
            if position.get('tp_id') != tp_order_id:
                log.error(f"⚠️  WARNING: TP ID mismatch! Returned: {tp_order_id}, In position: {position.get('tp_id')}")
            
            log.info(f"🛡️ TP placed: {fill_size} lots @ ${tp_price:,.0f} (ID: {tp_order_id})")
            position['protected'] = True
            
            # 🔥 FIX NOV 9: Update fill audit log with TP order ID
            if hasattr(self.bot, 'fill_audit_log'):
                try:
                    self.bot.fill_audit_log.update_fill_record(
                        order_id=order_id,
                        tp_order_placed=True,
                        tp_order_id=tp_order_id,
                        success=True
                    )
                    log.debug(f"📝 Updated audit log with TP: {tp_order_id}")
                except Exception as e:
                    log.error(f"❌ Failed to update audit log: {e}")
            
            # 🔍 LAYER 3: TP Verification (NOV 8)
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
        
        except RuntimeError as e:
            # TP placement failed after all retries - bot will halt
            log.critical("=" * 80)
            log.critical(f"🚨 FATAL: TP PLACEMENT FAILED AFTER RETRIES - BOT HALTED!")
            log.critical(f"   Incremental Fill: {fill_size} lots")
            log.critical(f"   Position Entry: ${fill_price:,.0f}")
            log.critical(f"   Expected TP: ${tp_price:,.0f}")
            log.critical(f"   Error: {e}")
            log.critical("=" * 80)
            
            # Update audit log with failure
            if hasattr(self.bot, 'fill_audit_log'):
                try:
                    self.bot.fill_audit_log.update_fill_record(
                        order_id=order_id,
                        tp_order_placed=False,
                        success=False,
                        error_message=str(e)
                    )
                except Exception:
                    pass
            
            # Re-raise to halt bot
            raise
        
        # ✅ KEY: Only clear pending_buy and place next grid order when ORDER COMPLETE
        if is_complete:
            log.info(f"✅ Order {order_id} FULLY FILLED ({cumulative}/{total_size} lots) - placing next grid order")
            
            # Clear pending buy (order is now complete)
            self.position_mgr.clear_pending_buy()
            
            # Calculate next grid price
            next_buy_price = self.grid_calc.compute_next_level_down(fill_price)
            
            if next_buy_price and self.grid_calc.is_within_bounds(next_buy_price):
                # 🔥 FIX NOV 9: THROTTLE BUG FIX - Use delayed placement instead of skipping
                # OLD BUG: Early return meant next order NEVER placed if throttled
                # NEW FIX: Schedule placement after throttle expires
                time_since_last = None
                wait_time = 0
                
                if self.bot.last_buy_order_time:
                    time_since_last = time.time() - self.bot.last_buy_order_time
                    if time_since_last < self.bot.min_order_gap_seconds:
                        wait_time = self.bot.min_order_gap_seconds - time_since_last
                        log.warning(f"🚦 THROTTLE: Last BUY was {time_since_last:.1f}s ago")
                        log.warning(f"   Will place next order after {wait_time:.1f}s delay")
                
                # Place order (immediately or after delay)
                if wait_time > 0:
                    # Schedule delayed placement in background thread
                    import threading
                    def place_after_delay():
                        time.sleep(wait_time)
                        log.info(f"⏰ Throttle expired - placing delayed grid BUY @ ${next_buy_price:,.0f}")
                        self._place_next_grid_order(next_buy_price, order_id)
                    
                    thread = threading.Thread(target=place_after_delay, daemon=True)
                    thread.start()
                    log.info(f"📅 Scheduled next grid order for {wait_time:.1f}s from now")
                else:
                    # Place immediately
                    self._place_next_grid_order(next_buy_price, order_id)
            else:
                log.warning("⚠️ Cannot place next BUY - price out of grid bounds")
        else:
            log.info(f"⏳ Order {order_id} still filling ({cumulative}/{total_size} lots) - waiting for more fills...")
    
    def _place_next_grid_order(self, next_buy_price: float, filled_order_id: str):
        """
        Helper method to place next grid order
        
        🔥 FIX NOV 9: Extracted for throttle fix - allows delayed placement
        
        Args:
            next_buy_price: Price for next BUY order
            filled_order_id: ID of order that just filled (for audit log)
        """
        try:
            log.info(f"📍 Placing next grid BUY @ ${next_buy_price:,.0f}")
            new_order_id = self.order_mgr.place_buy_order(next_buy_price, post_only=True)
            
            # ✅ FIX NOV 9: CRITICAL - Register order IMMEDIATELY to prevent race condition
            if new_order_id:
                self.position_mgr.set_pending_buy({
                    'order_id': new_order_id,
                    'price': next_buy_price,
                    'timestamp': time.time()
                })
                self.bot.last_buy_order_time = time.time()
                log.info(f"✅ Pending BUY registered: {new_order_id} @ ${next_buy_price:,.0f}")
                
                # 🔥 FIX NOV 9: Update fill audit log with next grid order ID
                if hasattr(self.bot, 'fill_audit_log'):
                    try:
                        self.bot.fill_audit_log.update_fill_record(
                            order_id=filled_order_id,
                            next_grid_placed=True,
                            next_grid_order_id=new_order_id
                        )
                        log.debug(f"📝 Updated audit log with next grid: {new_order_id}")
                    except Exception as e:
                        log.error(f"❌ Failed to update audit log: {e}")
            else:
                log.error(f"❌ Failed to place next grid order @ ${next_buy_price:,.0f}")
                
                # Update audit log with failure
                if hasattr(self.bot, 'fill_audit_log'):
                    try:
                        self.bot.fill_audit_log.update_fill_record(
                            order_id=filled_order_id,
                            next_grid_placed=False,
                            error_message="place_buy_order returned None"
                        )
                    except Exception:
                        pass
        
        except Exception as e:
            log.error(f"❌ Exception placing next grid order: {e}")
            import traceback
            log.debug(traceback.format_exc())
            
            # Update audit log with error
            if hasattr(self.bot, 'fill_audit_log'):
                try:
                    self.bot.fill_audit_log.update_fill_record(
                        order_id=filled_order_id,
                        next_grid_placed=False,
                        error_message=str(e)
                    )
                except Exception:
                    pass
    
    def handle_tp_fill(self, fill_price: float, position: Dict):
        """
        Handle TP fill (SELL order closes LONG position)
        
        ✅ NOV 10 REFACTOR: Async order replacement (place first, cleanup later)
        
        NEW LOGIC:
        1. IMMEDIATELY place new BUY order ONE STEP below filled TP (non-blocking)
        2. ASYNCHRONOUSLY cancel old BUY order TWO STEPS below (background thread)
        3. If cancel fails after 5 minutes, reconciliation absorbs it into grid
        
        Benefits:
        - Zero delay in grid order placement (instant response)
        - Always uses fresh price data (no stale price errors)
        - Fault-tolerant (grid adapts if cancel fails)
        - Better user experience (responsive grid)
        
        Example: Grid step = $500
        - Entry BUY at $105,000 → TP SELL at $105,500 (1 step up)
        - Market moves up, TP fills at $105,500
        - IMMEDIATELY place new BUY at $105,000 (1 step below TP)
        - BACKGROUND: Cancel old BUY at $104,500 (2 steps below TP)
        
        Args:
            fill_price: Price at which TP filled
            position: Position that was closed
        """
        entry = position['entry_price']
        size = position.get('size', self.lot)
        profit = (fill_price - entry) * size
        
        log.info(f"💰 TP FILLED @ ${fill_price:,.0f} - PROFIT: ${profit:.2f}!")
        
        # Track completed loop in predictive display
        # ✅ FIX NOV 12: Use self.bot instead of self.parent (AttributeError fix)
        if hasattr(self.bot, 'predictive_display'):
            self.bot.predictive_display.add_completed_loop(
                entry_price=entry,
                exit_price=fill_price,
                profit=profit,
                grid_mode='LONG'
            )
        
        # Remove position (frees up capacity)
        self.position_mgr.remove_position(position)
        
        # Get old pending order info BEFORE replacing it
        old_pending = self.position_mgr.get_pending_buy()
        old_order_id = old_pending.get('order_id') if old_pending else None
        old_price = old_pending.get('price') if old_pending else None
        
        # ✅ STEP 1: IMMEDIATELY place new order (non-blocking, priority action)
        if self.position_mgr.try_reserve_capacity():
            # Calculate new order price: TP fill price - 1 step
            next_price = self.grid_calc.compute_next_level_down(fill_price)
            
            log.info("=" * 70)
            log.info(f"📍 IMMEDIATE: Placing new grid order (async replacement)")
            log.info(f"   TP filled at: ${fill_price:,.0f}")
            log.info(f"   New BUY target: ${next_price:,.0f} (1 step below TP)")
            
            if self.grid_calc.is_within_bounds(next_price):
                # ✅ Check throttle
                if not self._check_order_throttle('BUY'):
                    self.position_mgr.release_capacity()
                    log.warning("⚠️  Order throttled - will retry on next heartbeat")
                    return
                
                # ✅ Check volatility before placing order
                try:
                    from bot.volatility.iv_rv_tracker import get_volatility_tracker
                    vol_tracker = get_volatility_tracker()
                    
                    if vol_tracker:
                        can_trade, halt_reason = vol_tracker.can_trade()
                        
                        if not can_trade:
                            log.warning(f"🌊 VOLATILITY UNSAFE - BUY order blocked ({halt_reason})")
                            self.position_mgr.release_capacity()
                            return
                except Exception as e:
                    log.debug(f"Volatility check error (non-critical): {e}")
                
                # Place the new order
                order_id = self.order_mgr.place_buy_order(next_price, post_only=True)
                if order_id:
                    # Register immediately to prevent race conditions
                    self.position_mgr.set_pending_buy({
                        'order_id': order_id,
                        'price': next_price,
                        'timestamp': time.time()
                    })
                    self.bot.last_buy_order_time = time.time()
                    
                    log.info(f"✅ New grid order placed instantly @ ${next_price:,.0f}")
                    log.info(f"   Order ID: {order_id}")
                    log.info(f"   Grid continuous - no gaps!")
                    log.info("=" * 70)
                else:
                    log.error(f"❌ Failed to place new BUY order at ${next_price:,.0f}")
                    self.position_mgr.release_capacity()
                    return
                
                self.position_mgr.release_capacity()
            else:
                log.warning(f"⚠️  New order price ${next_price:,.0f} is outside grid bounds")
                self.position_mgr.release_capacity()
                return
        else:
            log.error(f"❌ No capacity available for new grid order (should not happen after TP fill)")
            return
        
        # ✅ STEP 2: ASYNCHRONOUSLY cancel old order (non-blocking, background cleanup)
        if old_order_id and old_price:
            # Calculate distance to verify it's the 2-step stale order
            distance_from_tp = fill_price - old_price
            expected_distance = 2 * self.grid_calc.step
            
            log.info("")
            log.info(f"🔄 BACKGROUND: Scheduling async cancellation of stale order")
            log.info(f"   Old BUY at: ${old_price:,.0f} (Order ID: {old_order_id})")
            log.info(f"   Distance from TP: ${distance_from_tp:,.0f} (expected: ${expected_distance:,.0f})")
            
            # Validation warning (don't block)
            if abs(distance_from_tp - expected_distance) > self.grid_calc.tick_size:
                log.warning(f"⚠️  Stale order distance mismatch - cancelling anyway")
            
            # Schedule background cancellation (non-blocking)
            self._schedule_order_cancellation(
                order_id=old_order_id,
                price=old_price,
                max_retries=5,
                retry_interval=60  # 1 minute between retries
            )
            
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
            thread_name = f"cancel-{order_id[-6:]}"  # Last 6 digits for readability
            
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
                                return  # Fill handler will process it
                            
                            if state in ['cancelled', 'rejected']:
                                log.info(f"✅ [{thread_name}] Order already {state} - cleanup complete")
                                return
                        else:
                            # Order not found (404) - already gone
                            error = order_status.get('error', {})
                            if 'not_found' in str(error).lower() or 'not found' in str(error).lower():
                                log.info(f"✅ [{thread_name}] Order not found (404) - cleanup complete")
                                return
                    except Exception as e:
                        error_msg = str(e).lower()
                        if '404' in error_msg or 'not found' in error_msg:
                            log.info(f"✅ [{thread_name}] Order not found (404) - cleanup complete")
                            return
                    
                    # Attempt cancellation
                    cancel_success = self.order_mgr.cancel_order(order_id, verify=True)
                    
                    if cancel_success:
                        log.info(f"✅ [{thread_name}] Order cancelled successfully @ ${price:,.0f}")
                        return
                    else:
                        log.warning(f"⚠️  [{thread_name}] Cancel failed (attempt {attempt}/{max_retries})")
                        
                        # Wait before retry (except on last attempt)
                        if attempt < max_retries:
                            log.info(f"   Retrying in {retry_interval}s...")
                            time.sleep(retry_interval)
                
                except Exception as e:
                    log.error(f"❌ [{thread_name}] Exception during cancel attempt {attempt}: {e}")
                    
                    # Wait before retry (except on last attempt)
                    if attempt < max_retries:
                        time.sleep(retry_interval)
            
            # All retries exhausted - order persists (likely filled or Delta processing delay)
            log.warning("=" * 70)
            log.warning(f"⚠️  [{thread_name}] CLEANUP TIMEOUT: Order {order_id} still exists after {max_retries} attempts")
            log.warning(f"   Order: BUY @ ${price:,.0f}")
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
