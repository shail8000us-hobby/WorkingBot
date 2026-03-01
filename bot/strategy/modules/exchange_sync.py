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