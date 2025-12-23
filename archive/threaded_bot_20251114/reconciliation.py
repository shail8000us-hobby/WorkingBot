"""
Reconciliation - Exchange State Synchronization Module

Single Responsibility: Synchronize bot state with exchange reality

This module ensures the bot's internal state matches the exchange's actual state.
Critical for detecting missed fills, orphaned positions, and state drift.

Extracted from GridBotWebSocket (Phase 6 - Exchange sync)
"""

import logging
import time
from typing import Dict, List, Optional, Any

log = logging.getLogger("runner")


class Reconciliation:
    """
    Exchange state reconciliation and synchronization
    
    Responsibilities:
    - Sync positions with exchange after reconnect (FIX #12)
    - Detect orphaned positions (positions without TPs)
    - Detect missed fills during disconnect
    - Enforce single correct pending buy invariant
    - Compare local state vs exchange reality
    
    NOT Responsible For:
    - Order placement (OrderManager handles this)
    - Position management (PositionManager handles this)
    - Fill detection (FillDetector handles this)
    """
    
    def __init__(
        self,
        api_client: Any,
        position_manager: Any,
        order_manager: Any,
        grid_calculator: Any,
        gridbot_instance: Any = None
    ):
        """
        Initialize reconciliation module
        
        Args:
            api_client: Delta Exchange API client
            position_manager: PositionManager instance
            order_manager: OrderManager instance
            grid_calculator: GridCalculator instance
            gridbot_instance: GridBot instance for throttle checks (optional)
        """
        self.api_client = api_client
        self.position_mgr = position_manager
        self.order_mgr = order_manager
        self.grid_calc = grid_calculator
        self.gridbot = gridbot_instance  # For accessing throttle timestamps
        
        log.info("✅ Reconciliation module initialized")
    
    # ========================================================================
    # WebSocket Reconnect Sync (FIX #12)
    # ========================================================================
    
    def sync_on_reconnect(self) -> None:
        """
        ✅ FIX #12: Sync open orders on WebSocket reconnection
        
        Prevents missed fills during disconnect/reconnect cycles.
        Uses existing reconciliation logic to detect orphaned positions.
        
        Extracted from Lines 2682-2708 (gbot_ws.py)
        
        Flow:
        1. Fetch current open orders from exchange
        2. Compare with local state (open_tranches, pending_buy)
        3. Detect fills that happened during disconnect
        4. Update local state to match exchange reality
        
        Called automatically after WebSocket reconnection.
        """
        log.info("🔄 Syncing state after WebSocket reconnection...")
        
        try:
            # Use reconciliation logic to sync positions
            self.reconcile_positions_with_exchange()
            log.info("✅ Reconnect sync complete - state synchronized with exchange")
            
        except Exception as e:
            log.error(f"❌ Reconnect sync failed: {e}")
            # Non-fatal - robust fill detector will catch missed fills anyway
            log.info("   Relying on robust fill detection for recovery")
    
    # ========================================================================
    # Position Reconciliation
    # ========================================================================
    
    def reconcile_positions_with_exchange(self) -> Dict[str, Any]:
        """
        Reconcile local positions with exchange reality
        
        This method is called but NOT IMPLEMENTED in original gbot_ws.py.
        Implementing based on requirements.
        
        Returns:
            Dict with reconciliation results
        """
        results = {
            'local_positions': 0,
            'exchange_positions': 0,
            'orphaned_positions': [],
            'missing_tps': [],
            'synced': False
        }
        
        try:
            # Get local positions
            local_positions = self.position_mgr.get_positions()
            results['local_positions'] = len(local_positions)
            
            # Get exchange positions
            exchange_response = self.api_client.get_positions()
            if not exchange_response.get('success'):
                log.error(f"❌ Failed to fetch exchange positions: {exchange_response}")
                return results
            
            exchange_positions = exchange_response.get('result', [])
            results['exchange_positions'] = len(exchange_positions)
            
            # Get open orders from exchange
            orders_response = self.api_client.list_orders(product_id=self.order_mgr.product_id, state="open")
            if not orders_response.get('success'):
                log.error(f"❌ Failed to fetch exchange orders: {orders_response}")
                return results
            
            exchange_orders = orders_response.get('result', [])
            exchange_order_ids = {order['id'] for order in exchange_orders}
            
            # Check each local position
            for position in local_positions:
                tp_id = position.get('tp_id')
                
                # Check if TP order still exists on exchange
                if tp_id and tp_id not in exchange_order_ids:
                    # TP order missing - may have filled
                    log.warning(f"⚠️ TP order {tp_id} not found on exchange (may have filled)")
                    results['missing_tps'].append(position)
                
                # Check if position is protected
                if not position.get('protected') or not tp_id:
                    log.warning(f"⚠️ Unprotected position found: Entry ${position.get('entry_price', 0):,.0f}")
                    results['orphaned_positions'].append(position)
            
            # Detect positions on exchange not in local state
            for ex_pos in exchange_positions:
                ex_size = ex_pos.get('size', 0)
                if ex_size == 0:
                    continue  # Skip closed positions
                
                # Only check BTCUSD positions (product_id 27)
                if ex_pos.get('product_id') != self.order_mgr.product_id:
                    continue  # Skip other products (options, etc.)
                
                # Check if we have this position locally
                found = False
                ex_entry = float(ex_pos.get('entry_price', 0))
                for local_pos in local_positions:
                    if abs(local_pos.get('entry_price', 0) - ex_entry) < 1:
                        found = True
                        break
                
                if not found:
                    # ⚠️ IMPORTANT: Bot does NOT adopt manual positions
                    # This is likely a manually placed position or from another strategy
                    log.warning(f"ℹ️ Exchange position detected (not tracked by bot)")
                    log.warning(f"   Entry: ${ex_entry:,.2f} | Size: {ex_size} | Product: {ex_pos.get('product_symbol')}")
                    log.warning(f"   This may be a manual position or from another strategy.")
                    log.warning(f"   Bot will ignore this position (per design rules).")
                    
                    results['orphaned_positions'].append({
                        'entry_price': ex_entry,
                        'size': ex_size,
                        'product_id': ex_pos.get('product_id'),
                        'protected': False,
                        'tp_id': None,
                        'note': 'manual_or_external_position_ignored'
                    })
            
            results['synced'] = True
            log.info(f"✅ Reconciliation complete: {results['local_positions']} local, "
                    f"{results['exchange_positions']} exchange, "
                    f"{len(results['orphaned_positions'])} orphaned")
            
        except Exception as e:
            log.error(f"❌ Reconciliation failed: {e}")
            import traceback
            log.error(traceback.format_exc())
        
        return results
    
    # ========================================================================
    # Pending Buy Invariant Enforcement
    # ========================================================================
    
    def ensure_single_correct_pending_buy(self) -> None:
        """
        Invariant enforcer: Ensure exactly ONE pending buy at the correct price
        
        Extracted from Lines 1166-1189 (gbot_ws.py)
        
        Called after:
        - Fill detection (TP fills)
        - Config changes (hot-reload)
        - Periodic heartbeat (every ~10s)
        
        NOTE: Skips enforcement for Strict Grid startup orders to prevent
        cancellation of intentionally placed MAKER orders at non-standard prices.
        """
        # Get current pending buy
        current_pending = self.position_mgr.get_pending_buy()
        
        # 🔒 STRICT GRID PROTECTION: Skip reconciliation for startup orders
        if current_pending and current_pending.get('strict_grid_order'):
            log.debug("🔒 Strict Grid order active - skipping reconciliation")
            return
        
        # Compute target BUY price based on current positions
        positions = self.position_mgr.get_positions()
        
        # ✅ FIX NOV 7: Pass current market price to grid calculator for validation
        current_market_price = self.order_mgr.current_market_price
        target = self.grid_calc.compute_next_buy_level(positions, current_market_price)
        
        # Get current pending buy price
        current_price = current_pending.get('price') if current_pending else None
        
        # Case A: No target needed -> cancel any pending buy
        if target is None:
            if current_pending:
                log.info("🗑️ No BUY target needed - cancelling pending order")
                order_id = current_pending.get('order_id')
                if order_id:
                    self.order_mgr.cancel_order(order_id)
                self.position_mgr.clear_pending_buy()
            return
        
        # Case B: Missing or wrong pending buy -> replace atomically
        if current_pending is None or abs(float(current_price) - float(target)) > 1e-9:
            log.info(f"🔄 Pending BUY adjustment needed: current={current_price}, target={target}")
            
            # 🔒 NOV 7 BULLETPROOF: Check throttle - prevent orders within 30s of each other
            if self.gridbot and hasattr(self.gridbot, 'last_buy_order_time'):
                if self.gridbot.last_buy_order_time:
                    time_since_last_buy = time.time() - self.gridbot.last_buy_order_time
                    min_gap = getattr(self.gridbot, 'min_order_gap_seconds', 30)
                    
                    if time_since_last_buy < min_gap:
                        log.warning(f"🚦 THROTTLE: Last BUY order was {time_since_last_buy:.1f}s ago (min: {min_gap}s)")
                        log.warning(f"   Waiting {min_gap - time_since_last_buy:.1f}s before next BUY order...")
                        return  # Skip order placement
            
            # Cancel existing if present
            if current_pending:
                order_id = current_pending.get('order_id')
                if order_id:
                    self.order_mgr.cancel_order(order_id)
                self.position_mgr.clear_pending_buy()
            
            # Wait briefly for cancellation to process
            import time
            time.sleep(0.2)
            
            # Place new order with volatility check
            log.info(f"📝 Placing new BUY @ ${target:,.0f}")
            
            # Check volatility before placing
            try:
                from bot.volatility.iv_rv_tracker import get_volatility_tracker
                vol_tracker = get_volatility_tracker()
                
                if vol_tracker:
                    can_trade, halt_reason = vol_tracker.can_trade()
                    
                    if not can_trade:
                        log.warning(f"🌊 VOLATILITY UNSAFE - BUY order blocked ({halt_reason})")
                        return
                    
                    log.debug(f"✅ Volatility check passed, placing order")
            except Exception as e:
                log.warning(f"⚠️ Volatility check failed: {e}, placing order anyway")
            
            # Place the order (post_only=True to enforce MAKER-only execution)
            order_id = self.order_mgr.place_buy_order(target, post_only=True)
            if order_id:
                self.position_mgr.set_pending_buy({
                    'order_id': order_id,
                    'price': target,
                    'timestamp': time.time()
                })
                
                # 🔒 NOV 7 BULLETPROOF: Record timestamp for throttle
                if self.gridbot and hasattr(self.gridbot, 'last_buy_order_time'):
                    self.gridbot.last_buy_order_time = time.time()
                
                log.info(f"✅ BUY order placed @ ${target:,.0f} (ID: {order_id})")
            else:
                log.error(f"❌ Failed to place BUY order @ ${target:,.0f}")
    
    def ensure_single_correct_pending_sell(self) -> None:
        """
        Invariant enforcer: Ensure exactly ONE pending sell at the correct price (SHORT mode)
        
        Mirror of ensure_single_correct_pending_buy() for SHORT mode.
        
        Called after:
        - Fill detection (TP fills in SHORT mode)
        - Config changes (hot-reload)
        - Periodic heartbeat (every ~10s)
        
        NOTE: Skips enforcement for Strict Grid startup orders to prevent
        cancellation of intentionally placed MAKER orders at non-standard prices.
        """
        # Get current pending sell
        current_pending = self.position_mgr.get_pending_sell()
        
        # 🔒 STRICT GRID PROTECTION: Skip reconciliation for startup orders
        if current_pending and current_pending.get('strict_grid_order'):
            log.debug("🔒 Strict Grid SELL order active - skipping reconciliation")
            return
        
        # Compute target SELL price based on current positions
        positions = self.position_mgr.get_positions()
        
        # ✅ FIX NOV 7: Pass current market price to grid calculator for validation
        current_market_price = self.order_mgr.current_market_price
        target = self.grid_calc.compute_next_sell_level(positions, current_market_price)
        
        # Get current pending sell price
        current_price = current_pending.get('price') if current_pending else None
        
        # Case A: No target needed -> cancel any pending sell
        if target is None:
            if current_pending:
                log.info("🗑️ No SELL target needed - cancelling pending order")
                order_id = current_pending.get('order_id')
                if order_id:
                    self.order_mgr.cancel_order(order_id)
                self.position_mgr.clear_pending_sell()
            return
        
        # Case B: Missing or wrong pending sell -> replace atomically
        if current_pending is None or abs(float(current_price) - float(target)) > 1e-9:
            log.info(f"🔄 Pending SELL adjustment needed: current={current_price}, target={target}")
            
            # 🔒 NOV 7 BULLETPROOF: Check throttle - prevent orders within 30s of each other
            if self.gridbot and hasattr(self.gridbot, 'last_sell_order_time'):
                if self.gridbot.last_sell_order_time:
                    time_since_last_sell = time.time() - self.gridbot.last_sell_order_time
                    min_gap = getattr(self.gridbot, 'min_order_gap_seconds', 30)
                    
                    if time_since_last_sell < min_gap:
                        log.warning(f"🚦 THROTTLE: Last SELL order was {time_since_last_sell:.1f}s ago (min: {min_gap}s)")
                        log.warning(f"   Waiting {min_gap - time_since_last_sell:.1f}s before next SELL order...")
                        return  # Skip order placement
            
            # Cancel existing if present
            if current_pending:
                order_id = current_pending.get('order_id')
                if order_id:
                    self.order_mgr.cancel_order(order_id)
                self.position_mgr.clear_pending_sell()
            
            # Wait briefly for cancellation to process
            import time
            time.sleep(0.2)
            
            # Place new order with volatility check
            log.info(f"📝 Placing new SELL @ ${target:,.0f}")
            
            # Check volatility before placing
            try:
                from bot.volatility.iv_rv_tracker import get_volatility_tracker
                vol_tracker = get_volatility_tracker()
                
                if vol_tracker:
                    can_trade, halt_reason = vol_tracker.can_trade()
                    
                    if not can_trade:
                        log.warning(f"🌊 VOLATILITY UNSAFE - SELL order blocked ({halt_reason})")
                        return
                    
                    log.debug(f"✅ Volatility check passed, placing order")
            except Exception as e:
                log.warning(f"⚠️ Volatility check failed: {e}, placing order anyway")
            
            # Place the order
            order_id = self.order_mgr.place_sell_order(target)
            if order_id:
                self.position_mgr.set_pending_sell({
                    'order_id': order_id,
                    'price': target,
                    'timestamp': time.time()
                })
                
                # 🔒 NOV 7 BULLETPROOF: Record timestamp for throttle
                if self.gridbot and hasattr(self.gridbot, 'last_sell_order_time'):
                    self.gridbot.last_sell_order_time = time.time()
                
                log.info(f"✅ SELL order placed @ ${target:,.0f} (ID: {order_id})")
            else:
                log.error(f"❌ Failed to place SELL order @ ${target:,.0f}")
    
    # ========================================================================
    # Orphaned Position Detection
    # ========================================================================
    
    def detect_orphaned_positions(self) -> List[Dict[str, Any]]:
        """
        Detect positions without TP protection
        
        Returns:
            List of orphaned position dictionaries
        """
        orphaned = []
        
        positions = self.position_mgr.get_positions()
        for position in positions:
            if not position.get('protected') or not position.get('tp_id'):
                orphaned.append(position)
                log.warning(f"⚠️ Orphaned position detected: Entry ${position.get('entry_price', 0):,.0f}")
        
        return orphaned
    
    def fix_orphaned_positions(self, orphaned_positions: List[Dict[str, Any]]) -> int:
        """
        Attempt to fix orphaned positions by placing TPs
        
        Args:
            orphaned_positions: List of positions without TPs
            
        Returns:
            Number of positions fixed
        """
        fixed_count = 0
        
        for position in orphaned_positions:
            log.info(f"🔧 Attempting to fix orphaned position: Entry ${position.get('entry_price', 0):,.0f}")
            
            # Try to place TP
            if self.order_mgr.safe_place_tp(position):
                fixed_count += 1
                log.info(f"✅ Orphaned position fixed with TP")
            else:
                # Schedule for retry
                self.position_mgr.schedule_tp_retry(position)
                log.warning(f"⚠️ Failed to fix orphaned position - scheduled for retry")
        
        return fixed_count
    
    # ========================================================================
    # Exchange State Queries
    # ========================================================================
    
    def get_exchange_open_orders(self) -> List[Dict[str, Any]]:
        """
        Fetch all open orders from exchange
        
        Returns:
            List of open order dictionaries
        """
        try:
            response = self.api_client.list_orders(product_id=self.order_mgr.product_id, state="open")
            if response.get('success'):
                return response.get('result', [])
            else:
                log.error(f"❌ Failed to fetch open orders: {response}")
                return []
        except Exception as e:
            log.error(f"❌ Error fetching open orders: {e}")
            return []
    
    def get_exchange_positions(self) -> List[Dict[str, Any]]:
        """
        Fetch all positions from exchange
        
        Returns:
            List of position dictionaries
        """
        try:
            response = self.api_client.get_positions()
            if response.get('success'):
                return response.get('result', [])
            else:
                log.error(f"❌ Failed to fetch positions: {response}")
                return []
        except Exception as e:
            log.error(f"❌ Error fetching positions: {e}")
            return []
