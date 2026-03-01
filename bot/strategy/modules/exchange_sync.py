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
