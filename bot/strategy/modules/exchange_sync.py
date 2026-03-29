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
    # P3.4: Replay own positions on startup (pre-actor-start)
    # ========================================================================

    async def sync_positions_from_exchange(self) -> None:
        """
        Startup Step 1: Replay bot's own position events from event store.
        
        Called BEFORE actors start, so we call replay_own_positions() directly
        on the position_actor (synchronous SQLite read — no message passing needed).
        
        Exchange validation happens later in full_exchange_sync() after actors start.
        
        PRINCIPLE: The bot only manages positions IT created.
        """
        try:
            log.info("🔄 POSITION SYNC: Replaying bot's own trade history...")
            
            # Direct call — no message passing (actors not started yet)
            positions_restored = self.position_actor.replay_own_positions()
            
            log.info(f"✅ Replayed {positions_restored} position(s) from event store")
            log.info("   Exchange validation will happen in full_exchange_sync() after actors start")
            
        except Exception as e:
            log.warning(f"⚠️  Position replay error: {e}")
            import traceback
            log.warning(traceback.format_exc())
            log.warning("   Continuing with empty state...")

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

    # ── Reconnect Fill Reconciliation ─────────────────────────────────

    async def reconcile_fills_after_reconnect(self) -> None:
        """
        CRITICAL FIX NOV 14: Reconcile missed fills after WebSocket reconnect.

        After WebSocket reconnection, we may have missed fill notifications.
        This method fetches recent fills via REST API and processes any that
        occurred during the disconnection period.

        Prevents state desync and orphaned positions.
        """
        try:
            log.info("🔄 Reconciling missed fills after WebSocket reconnect...")

            # Calculate time window - check last 5 minutes
            end_time = int(time.time() * 1000)
            start_time = end_time - (5 * 60 * 1000)

            # Fetch fills from REST API
            try:
                fills_response = await self.api_client.get_fills(
                    product_id=self.product_id,
                    start_time=start_time,
                    end_time=end_time
                )
            except Exception as e:
                log.error(f"❌ Failed to fetch fills from REST API: {e}")
                return

            if not fills_response:
                log.info("✅ No recent fills found - no reconciliation needed")
                return

            # Extract fills array from response
            fills = fills_response.get('result', []) if isinstance(fills_response, dict) else fills_response

            if not fills:
                log.info("✅ No recent fills found - no reconciliation needed")
                return

            log.info(f"📋 Found {len(fills)} recent fill(s) - checking for missed ones...")

            # Get current state to check which fills we already processed
            state = await self.position_actor.ask("GET_STATE", {})
            open_tranches = state.get("open_tranches", [])

            # Track which fills we've already processed
            processed_order_ids = set()

            # Add order IDs from open positions
            for tranche in open_tranches:
                if 'order_id' in tranche:
                    processed_order_ids.add(str(tranche['order_id']))

            # Process each fill
            missed_count = 0
            for fill in fills:
                order_id = str(fill.get('order_id', ''))
                fill_id = fill.get('id', '')
                side = fill.get('side', '').lower()
                price = float(fill.get('price', 0))
                size = int(fill.get('size', 0))

                # Skip if we already processed this order
                if order_id in processed_order_ids:
                    continue

                # Check if this is a bot order
                client_id = fill.get('client_order_id', '')
                if not client_id.startswith('BOT-'):
                    log.debug(f"Skipping non-bot fill: {fill_id}")
                    continue

                # This is a missed fill - process it now
                log.warning(f"⚠️  MISSED FILL DETECTED: {side.upper()} {size} @ ${price:,.0f} (Order: {order_id})")
                missed_count += 1

                # Create fill data structure matching WebSocket format
                fill_data = {
                    'order_id': order_id,
                    'price': price,
                    'size': size,
                    'side': side,
                    'is_complete': True,
                    'fill_id': fill_id,
                    'reconciled': True
                }

                # Process the fill through normal saga flow
                try:
                    await self._process_fill_callback(fill_data)
                    log.info(f"✅ Reconciled fill: {side.upper()} @ ${price:,.0f}")
                    processed_order_ids.add(order_id)
                except Exception as e:
                    log.error(f"❌ Failed to reconcile fill {fill_id}: {e}")
                    import traceback
                    log.error(traceback.format_exc())

            if missed_count == 0:
                log.info("✅ All fills were already processed - state is in sync")
            else:
                log.warning(f"⚠️  Reconciled {missed_count} missed fill(s)")
                log.warning(f"   Bot state is now synchronized with exchange")

        except Exception as e:
            log.error(f"❌ Error during fill reconciliation: {e}")
            import traceback
            log.error(traceback.format_exc())

    # ── Grid Coverage ─────────────────────────────────────────────────

    async def ensure_grid_coverage(self):
        """
        Ensure there's a buy order covering the next grid level.

        Called after exchange maintenance to fill any gaps in grid coverage.
        """
        if self.mode == 'SHORT':
            # In SHORT mode, entries are SELLs (not BUYs).
            # place_initial_order handles the pending SELL. BUYs are TP-only (placed after fill).
            return
        try:
            # Get current state
            state = await self.position_actor.ask("GET_STATE", {})
            positions = state.get("open_tranches", [])

            current_price = self._get_current_price()
            if not current_price:
                await self._fetch_current_price_callback()
                current_price = self._get_current_price()

            # Calculate next buy level
            next_buy = self.grid_calc.compute_next_buy_level(positions, current_price=current_price)

            if next_buy:
                # FIX MAR 2 2026: Post-only safety guard — don't place BUY at/above
                # market price. This would get rejected with immediate_execution_post_only
                # and cause the order actor to retry for 15s, freezing the heartbeat.
                if current_price and next_buy >= current_price:
                    log.info(f"⏭️  Grid coverage: BUY @ ${next_buy:,.0f} >= market ${current_price:,.0f} — skipping (would cross spread)")
                    return
                
                # Check if order already exists
                orders = await self.api_client.list_orders(symbol=self.symbol, states='open')

                order_exists = any(
                    abs(float(o.get('limit_price', 0)) - next_buy) < 0.01
                    and o.get('side', '').lower() == 'buy'
                    and not o.get('reduce_only', False)
                    for o in orders
                )

                if not order_exists:
                    log.info(f"📍 Placing missing grid buy order at ${next_buy:,.0f}")

                    await self.order_actor.tell('PLACE_BUY', {
                        'price': next_buy,
                        'size': self.lot_size
                    })
                else:
                    log.debug(f"✅ Grid buy order already exists at ${next_buy:,.0f}")

        except Exception as e:
            log.error(f"❌ Error ensuring grid coverage: {e}")

    # ── Full Exchange Sync ────────────────────────────────────────────

    async def full_exchange_sync(self):
        """
        Periodic reconciliation after exchange maintenance or reconnection.
        
        PRINCIPLE: Only manage positions the bot created. Never adopt external
        positions. Use event store as source of truth, exchange as validation.
        
        Steps:
        1. Get current bot state (already in memory from startup replay)
        2. Get exchange positions and open orders
        3. Validate bot's positions still exist on exchange
        4. Close stale positions (TP hit while maintenance)
        5. Ensure TP orders exist for valid positions
        6. Ensure grid coverage (next buy order)
        """
        log.info("🔄 Starting full exchange sync (own positions only)...")

        try:
            # Step 1: Get current bot state
            bot_state = await self.position_actor.ask("GET_STATE", {})
            bot_positions = bot_state.get("open_tranches", [])
            bot_total_size = sum(float(p.get('size', 0)) for p in bot_positions)

            # Step 2: Get exchange state
            exchange_positions_raw = await self.api_client.get_positions()

            if isinstance(exchange_positions_raw, dict):
                if float(exchange_positions_raw.get('size', 0)) != 0:
                    exchange_positions = [exchange_positions_raw]
                else:
                    exchange_positions = []
            elif isinstance(exchange_positions_raw, list):
                exchange_positions = exchange_positions_raw
            else:
                exchange_positions = []

            exchange_orders = await self.api_client.list_orders(
                symbol=self.symbol,
                states='open'
            )
            if not isinstance(exchange_orders, list):
                exchange_orders = []

            # Calculate exchange total for our product
            exchange_total_size = 0
            for ex_pos in exchange_positions:
                if isinstance(ex_pos, dict) and (
                    ex_pos.get('product_symbol') == 'BTCUSD' or
                    ex_pos.get('product_id') == self.product_id
                ):
                    exchange_total_size += abs(float(ex_pos.get('size', 0)))

            log.info(f"   Bot: {len(bot_positions)} positions ({bot_total_size} contracts)")
            log.info(f"   Exchange: {exchange_total_size} contracts, {len(exchange_orders)} orders")

            # Step 3-4: Validate bot positions against exchange
            stale_count = 0
            if exchange_total_size == 0 and bot_total_size > 0:
                # All positions were closed
                log.warning(f"   ⚠️  Exchange has 0 contracts — closing all {len(bot_positions)} bot positions")
                for pos in list(bot_positions):
                    await self.position_actor.ask("CLOSE_STALE_POSITION", {
                        "position_id": pos["position_id"],
                        "reason": "no_exchange_position_during_sync"
                    })
                    stale_count += 1
                bot_positions = []
            elif exchange_total_size < bot_total_size:
                # Some positions were closed
                excess = bot_total_size - exchange_total_size
                log.warning(f"   ⚠️  Exchange has {exchange_total_size} < bot {bot_total_size} — closing excess")
                sorted_positions = sorted(bot_positions, key=lambda p: p.get('timestamp', 0), reverse=True)
                contracts_to_close = excess
                remaining = []
                for pos in sorted_positions:
                    if contracts_to_close > 0:
                        pos_size = float(pos.get('size', 0))
                        await self.position_actor.ask("CLOSE_STALE_POSITION", {
                            "position_id": pos["position_id"],
                            "reason": f"exchange_size_mismatch_sync ({exchange_total_size} < {bot_total_size})"
                        })
                        contracts_to_close -= pos_size
                        stale_count += 1
                    else:
                        remaining.append(pos)
                bot_positions = remaining

            # Step 5: Ensure TP orders exist for valid positions
            tp_placed = 0
            for pos in bot_positions:
                tp_price = float(pos.get('tp_price', 0))
                pos_size = float(pos.get('size', 0))
                
                if tp_price <= 0:
                    continue
                
                tp_exists = any(
                    abs(float(o.get('limit_price', 0)) - tp_price) < 0.01
                    and o.get('side', '').lower() == 'sell'
                    and o.get('reduce_only', False)
                    for o in exchange_orders
                )
                
                if not tp_exists:
                    log.warning(f"   ⚠️  Missing TP for {pos['position_id']} @ ${tp_price:,.0f} — placing")
                    await self.order_actor.tell('PLACE_SELL', {
                        'price': tp_price,
                        'size': pos_size,
                        'reduce_only': True
                    })
                    tp_placed += 1

            # Step 6: Ensure grid coverage
            await self.ensure_grid_coverage()

            log.info(f"✅ Full exchange sync complete:")
            log.info(f"   - {stale_count} stale positions closed")
            log.info(f"   - {tp_placed} missing TP orders placed")
            log.info(f"   - Grid coverage verified")

        except Exception as e:
            log.error(f"❌ Error during full exchange sync: {e}")
            raise