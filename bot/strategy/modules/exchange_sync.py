"""
Exchange Sync & Reconciliation — extracted from async_gridbot.py Phase 3

Responsibilities:
- Reconcile orphaned orders at startup
- Clean up misaligned grid orders
- Reconcile fills after WebSocket reconnect
- Full exchange sync (8-step orphan/TP recovery)
- Ensure grid coverage
- Detect and handle exchange maintenance
- Sync positions from exchange on startup

NOT Responsible For:
- Order placement logic (→ GridEngine, Phase 6)
- Fill processing (→ FillProcessor, Phase 5)
- Guardian signal reading (→ GuardianHandler, Phase 1)
- Health monitoring (→ HealthMonitor, Phase 2)
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from loguru import logger as log


class ExchangeSync:
    """Exchange state synchronization and reconciliation."""

    def __init__(
        self,
        api_client,
        position_actor,
        order_actor,
        event_store,
        grid_calc,
        mode: str,
        symbol: str,
        product_id: int,
        grid_step: float,
        lot_size: float,
        max_positions: int,
        tp_offset: float,
        should_log_fn: Callable,
    ):
        self.api_client = api_client
        self.position_actor = position_actor
        self.order_actor = order_actor
        self.event_store = event_store
        self.grid_calc = grid_calc
        self.mode = mode
        self.symbol = symbol
        self.product_id = product_id
        self.grid_step = grid_step
        self.lot_size = lot_size
        self.max_positions = max_positions
        self.tp_offset = tp_offset
        self._should_log = should_log_fn

        # Runtime references (set by orchestrator via set_runtime_refs)
        self._get_running: Callable = lambda: False
        self._get_current_price: Callable = lambda: None
        self._fetch_current_price_callback: Optional[Callable] = None
        self._process_fill_callback: Optional[Callable] = None

    def set_runtime_refs(self, **kwargs):
        """Wire runtime references after construction."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    # ========================================================================
    # P3.2: Exchange State Detection + Maintenance Handling
    # ========================================================================

    async def detect_exchange_state(self) -> str:
        """
        Detect if exchange is in maintenance mode.
        
        Returns:
            'online' | 'maintenance' | 'error'
        """
        try:
            # Try to get server time (lightest API call)
            response = await self.api_client.rest_client.get_server_time()
            
            if response:
                return 'online'
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for maintenance indicators
            if 'maintenance' in error_msg or 'scheduled' in error_msg:
                return 'maintenance'
            elif '503' in error_msg or 'unavailable' in error_msg:
                return 'maintenance'
            elif '502' in error_msg or 'bad gateway' in error_msg:
                return 'maintenance'
            else:
                log.debug(f"Exchange state detection error: {error_msg}")
                return 'error'
        
        return 'error'
    
    async def handle_exchange_maintenance(self):
        """
        Handle exchange coming back from maintenance.
        
        1. Detect when exchange is back online
        2. Sync all positions and orders from exchange
        3. Process any fills that happened during downtime
        4. Resume normal trading
        """
        log.warning("=" * 80)
        log.warning("🏗️ EXCHANGE IN MAINTENANCE MODE")
        log.warning("   Bot entering safe state - pausing trading")
        log.warning("   Will automatically resume when exchange is back online")
        log.warning("=" * 80)
        
        maintenance_start = time.time()
        check_count = 0
        
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds
            check_count += 1
            
            state = await self.detect_exchange_state()
            
            if state == 'online':
                downtime = time.time() - maintenance_start
                log.info("=" * 80)
                log.info(f"✅ EXCHANGE BACK ONLINE (downtime: {downtime/60:.1f} minutes)")
                log.info("   Starting full state synchronization...")
                log.info("=" * 80)
                
                # CRITICAL: Full reconciliation after maintenance
                try:
                    await self.full_exchange_sync()
                    log.info("✅ State sync complete - resuming normal trading")
                except Exception as sync_error:
                    log.error(f"❌ Error during post-maintenance sync: {sync_error}")
                    log.warning("⚠️ Continuing with partial sync - manual review recommended")
                
                break
            elif state == 'maintenance':
                log.info(f"🏗️ Exchange still in maintenance (check #{check_count})")
            else:
                # State is likely 'unknown' during transition - this is normal
                log.debug(f"Exchange state: {state} (check #{check_count}) - continuing to monitor")

    # ========================================================================
    # P3.3: Exchange Maintenance Monitor Loop
    # ========================================================================

    async def exchange_maintenance_monitor(self) -> None:
        """
        DEC 23 Layer 3: Monitor for exchange maintenance.
        
        Detects when exchange goes into maintenance mode and handles recovery.
        Checks every 60 seconds during normal operation.
        """
        log.info("Exchange maintenance monitor started")
        
        consecutive_errors = 0
        max_errors_before_maintenance = 3  # 3 consecutive errors = likely maintenance
        
        while self._get_running():
            try:
                await asyncio.sleep(60)  # Check every minute during normal operation
                
                state = await self.detect_exchange_state()
                
                if state == 'online':
                    consecutive_errors = 0
                    # log.debug("Exchange state: online")
                elif state == 'maintenance':
                    log.warning("🏗️ Exchange maintenance detected!")
                    await self.handle_exchange_maintenance()
                    consecutive_errors = 0
                else:  # error
                    consecutive_errors += 1
                    log.debug(f"Exchange state check error ({consecutive_errors}/{max_errors_before_maintenance})")
                    
                    if consecutive_errors >= max_errors_before_maintenance:
                        log.warning(f"⚠️ {consecutive_errors} consecutive exchange errors - possible maintenance")
                        await self.handle_exchange_maintenance()
                        consecutive_errors = 0
            
            except Exception as e:
                log.error(f"Exchange maintenance monitor error: {e}")
                await asyncio.sleep(60)

    # ========================================================================
    # P3.4: Sync Positions from Exchange
    # ========================================================================

    async def sync_positions_from_exchange(self) -> None:
        """
        Sync positions from exchange on startup.
        This detects recovery positions and other external positions.
        """
        try:
            log.info("🔄 Syncing positions from exchange...")
            
            # Get all positions from exchange
            positions = await self.api_client.get_positions()
            
            if not positions:
                log.info("✅ No positions found on exchange")
                return
            
            # Handle case where API returns string instead of list
            if isinstance(positions, str):
                log.info("✅ No positions found on exchange (empty response)")
                return
            
            # Ensure positions is a list
            if not isinstance(positions, list):
                log.warning(f"⚠️  Unexpected positions format: {type(positions)}")
                return
            
            # Filter for BTCUSD positions
            btc_positions = [p for p in positions if isinstance(p, dict) and p.get('product_symbol') == 'BTCUSD']
            
            if not btc_positions:
                log.info("✅ No BTCUSD positions found on exchange")
                return
            
            log.info(f"📊 Found {len(btc_positions)} BTCUSD position(s) on exchange")
            
            # Process each position
            for position in btc_positions:
                size = float(position.get('size', 0))
                entry_price = float(position.get('entry_price', 0))
                mark_price = float(position.get('mark_price', 0))
                
                if size == 0:
                    continue
                
                log.info(f"   Position: {size} @ ${entry_price:,.0f} (mark: ${mark_price:,.0f})")
                
                # Add to position manager
                position_data = {
                    'size': size,
                    'entry_price': entry_price,
                    'mark_price': mark_price,
                    'is_recovery': True,  # Mark as recovery position
                    'grid_level': entry_price  # Use entry price as grid level
                }
                
                # Send to position actor
                await self.position_actor.ask("ADD_POSITION", position_data)
                
            log.info(f"✅ Synced {len(btc_positions)} position(s) from exchange")
            
        except Exception as e:
            log.warning(f"⚠️  Could not sync positions from exchange: {e}")
            log.warning("   Continuing with normal startup...")

    # ========================================================================
    # P3.5: Reconcile Orphaned Orders
    # ========================================================================

    async def reconcile_orphaned_orders(self) -> None:
        """
        Reconcile orphaned bot orders on startup.
        
        Queries the exchange for any open orders placed by the bot
        (identified by client_order_id starting with "BOT-") and adopts
        them into the pending order tracker.
        
        Prevents leaving orders orphaned after bot restarts/crashes.
        """
        try:
            log.info("🔄 Reconciling orphaned orders from exchange...")
            
            # Check if we already have pending state loaded from actors
            existing_pending = None
            pending_resp = await self.position_actor.ask(
                "GET_STATE",
                {}
            )
            
            if pending_resp:
                # Extract pending buy or sell from state
                existing_pending = pending_resp.get('pending_buy' if self.mode == 'LONG' else 'pending_sell')
            
            if existing_pending:
                existing_order_id = existing_pending.get('order_id')
                existing_price = existing_pending.get('price')
                log.info(f"ℹ️  State already loaded: pending_{self.mode.lower()} = {existing_order_id} @ ${existing_price:,.0f}")
                log.info(f"   Verifying this order still exists on exchange...")
                
                # Verify the loaded order still exists on exchange
                try:
                    order_check = await self.api_client.get_order(existing_order_id)
                    if order_check and order_check.get('state', '').lower() == 'open':
                        log.info(f"✅ Loaded pending order verified on exchange - no reconciliation needed")
                        return  # State is valid, skip reconciliation
                    else:
                        log.warning(f"⚠️  Loaded pending order NOT found or not open on exchange")
                        log.warning(f"   Will search for other orphaned orders...")
                        # Clear invalid state
                        if self.mode == 'LONG':
                            await self.position_actor.ask("CLEAR_PENDING_BUY", {})
                        else:
                            await self.position_actor.ask("CLEAR_PENDING_SELL", {})
                except Exception as e:
                    log.warning(f"⚠️  Could not verify loaded pending order: {e}")
                    log.warning(f"   Continuing with reconciliation...")
            
            # Query exchange for all open orders
            all_orders = await self.api_client.list_orders(
                symbol=self.symbol, 
                states="open"
            )
            
            if not all_orders:
                log.info("ℹ️  No open orders found on exchange")
                return
            
            # Determine target side based on grid mode
            target_side = 'buy' if self.mode == 'LONG' else 'sell'
            
            bot_orders = []
            
            # Find orders placed by bot (client_order_id starts with "BOT-")
            for order in all_orders:
                side = order.get('side', '').lower()
                state = order.get('state', '').lower()
                client_id = order.get('client_order_id', '')
                is_reduce_only = order.get('reduce_only', False)
                
                if (state == 'open' and 
                    side == target_side and 
                    not is_reduce_only and 
                    client_id.startswith('BOT-')):
                    bot_orders.append(order)
            
            if not bot_orders:
                log.info(f"✅ No orphaned bot {target_side.upper()} orders found on exchange")
                
                # BUT - check if bot memory has a stale pending order
                if existing_pending:
                    log.warning(f"⚠️  Bot memory has pending order but exchange has NONE!")
                    log.warning(f"   Clearing stale order {existing_pending.get('order_id')} from memory...")
                    if self.mode == 'LONG':
                        await self.position_actor.ask("CLEAR_PENDING_BUY", {"order_id": existing_pending.get('order_id')})
                    else:
                        await self.position_actor.ask("CLEAR_PENDING_SELL", {"order_id": existing_pending.get('order_id')})
                    log.info(f"✅ Stale pending order cleared from memory")
                
                return
            
            # We should only have 1 pending order at a time
            if len(bot_orders) == 1:
                order = bot_orders[0]
                order_id = str(order.get('id'))
                price = float(order.get('limit_price', 0))
                
                # Adopt into pending tracker (mode-aware)
                await self.position_actor.ask({
                    'action': 'set_pending_buy' if self.mode == 'LONG' else 'set_pending_sell',
                    'data': {
                        'order_id': order_id,
                        'price': price,
                        'timestamp': time.time(),
                        'reconciled': True  # Mark as reconciled for tracking
                    }
                })
                
                log.info(f"✅ Adopted orphaned {target_side.upper()} order: ID {order_id} @ ${price:,.0f}")
                log.info(f"   This order was placed in a previous session")
                
            elif len(bot_orders) > 1:
                # Multiple bot orders - this shouldn't happen in normal operation
                log.warning(f"⚠️ Found {len(bot_orders)} orphaned bot {target_side.upper()} orders (expected 0-1)")
                log.warning(f"   Cancelling all except the most recent...")
                
                # Sort by creation time (most recent first)
                bot_orders.sort(key=lambda o: o.get('created_at', ''), reverse=True)
                
                # Keep the most recent, cancel the rest
                most_recent = bot_orders[0]
                order_id = str(most_recent.get('id'))
                price = float(most_recent.get('limit_price', 0))
                
                # Adopt most recent order (mode-aware)
                await self.position_actor.ask({
                    'action': 'set_pending_buy' if self.mode == 'LONG' else 'set_pending_sell',
                    'data': {
                        'order_id': order_id,
                        'price': price,
                        'timestamp': time.time(),
                        'reconciled': True
                    }
                })
                
                log.info(f"✅ Adopted most recent order: ID {order_id} @ ${price:,.0f}")
                
                # Cancel older orders
                for old_order in bot_orders[1:]:
                    old_id = old_order.get('id')
                    old_price = old_order.get('limit_price', 0)
                    log.info(f"🗑️ Cancelling older orphaned order: ID {old_id} @ ${old_price}")
                    
                    cancel_resp = await self.order_actor.ask({
                        'action': 'cancel_order',
                        'order_id': old_id
                    })
                    
                    await asyncio.sleep(0.2)  # Rate limiting
        
        except Exception as e:
            log.error(f"❌ Error during orphaned order reconciliation: {e}")
            import traceback
            log.error(traceback.format_exc())

    # ── Misaligned Order Cleanup ──────────────────────────────────────

    async def cleanup_misaligned_orders(self) -> None:
        """Cancel grid buy orders that are too far below the current grid."""
        try:
            log.info("🔄 Checking for misaligned grid orders...")

            orders_response = await self.order_actor.ask("GET_OPEN_ORDERS", {}, timeout=5.0)
            if orders_response.get("status") != "ok":
                log.warning(f"⚠️  Could not fetch orders for cleanup")
                return

            open_orders = orders_response.get("orders", [])
            if not open_orders:
                log.info("ℹ️  No open orders - skipping cleanup")
                return

            state = await self.position_actor.ask("GET_STATE", {})
            positions = state.get("positions", []) if state else []

            if self.mode == "LONG":
                if positions:
                    highest_tp = max(pos.get("tp_price", 0) for pos in positions)
                    threshold = highest_tp - (2 * self.grid_step)
                else:
                    threshold = self._get_current_price() - (2 * self.grid_step)

                for order in open_orders:
                    if order.get("side") == "buy" and order.get("state") == "open":
                        order_price = float(order.get("limit_price", 0))
                        order_id = str(order.get("id"))
                        client_id = order.get("client_order_id") or ""
                        is_reduce_only = order.get("reduce_only", False)

                        if is_reduce_only:
                            continue

                        if client_id and client_id.startswith("GBOT_") and order_price < threshold:
                            log.info(f"🗑️  Cancelling misaligned BUY order #{order_id} @ ${order_price:,.0f} (threshold: ${threshold:,.0f})")
                            await self.order_actor.ask("CANCEL_ORDER", {"order_id": order_id}, timeout=5.0)
                            await asyncio.sleep(0.2)

            log.info("✅ Misaligned order cleanup complete")

        except Exception as e:
            log.error(f"❌ Error during misaligned order cleanup: {e}")