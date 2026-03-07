"""
GridBot - Main Orchestrator (Refactored Architecture)

This is the NEW thin orchestrator that replaces the 3,492-line GridBotWebSocket God Class.
It delegates all business logic to specialized domain modules.

CRITICAL: This is PURE ORCHESTRATION - NO business logic here!

Architecture:
    GridBot (this file) - 200-300 lines
        ↓ delegates to ↓
    7 Domain Modules:
        - GridCalculator (pure logic)
        - PositionManager (state + lock)
        - OrderManager (order operations)
        - FillDetector (fill processing)
        - Reconciliation (exchange sync)
        - VolatilityHandler (recovery logic)
        - WebSocketHandler (event routing)
"""

import os
import gc
import time
import signal
import atexit
import logging
import psutil
import threading
from datetime import datetime
from typing import Optional, Dict, Any

from bot.strategy.modules import (
    GridCalculator,
    WebSocketHandler,
    FillDetector,
    PositionManager,
    OrderManager,
    Reconciliation,
    VolatilityHandler
)
from bot.strategy.handlers import LongFillHandler, ShortFillHandler

# ✅ NOV 8: Comprehensive Monitoring Systems (5 layers of protection)
from bot.monitoring import (
    PriceHealthMonitor,       # Layer 1: Prevent orders with stale price
    PreOrderDecisionLogger,   # Layer 2: Transparency before every order
    TPVerificationSystem,     # Layer 3: Detect orphaned positions
    AnomalyDetectionSystem,   # Layer 4: Alert on dangerous patterns
    PredictiveDecisionDisplay # Layer 5: Show next actions
)

log = logging.getLogger("runner")

# Constants
TICK_SIZE = float(os.getenv("GRIDBOT_TICK_SIZE", "0.5"))


class GridBot:
    """
    Thin orchestrator - delegates to domain modules
    
    Responsibilities (ORCHESTRATION ONLY):
    - Initialize modules in dependency order
    - Wire up callbacks between modules
    - Run main event loop (heartbeat)
    - Handle shutdown gracefully
    
    NOT Responsible For (delegated to modules):
    - Grid calculations → GridCalculator
    - Fill detection → FillDetector
    - Order placement → OrderManager
    - State management → PositionManager
    - Volatility handling → VolatilityHandler
    - Exchange sync → Reconciliation
    - WebSocket events → WebSocketHandler
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        symbol: str,
        lower: float,
        upper: float,
        step: float,
        ref: float,
        lot: int,
        max_open: int = 5,
        hb_sec: int = 15
    ):
        """
        Initialize GridBot with all modules
        
        Modules are initialized in dependency order:
        1. GridCalculator (no dependencies)
        2. PositionManager (uses GridCalculator, owns lock)
        3. FillDetector (uses PositionManager's lock)
        4. OrderManager (uses GridCalculator, PositionManager)
        5. Reconciliation (uses OrderManager, PositionManager, GridCalculator)
        6. VolatilityHandler (uses all above)
        7. WebSocketHandler (routes to all above)
        """
        log.info("=" * 80)
        log.info("🚀 GRIDBOT - REFACTORED ARCHITECTURE")
        log.info("=" * 80)
        
        # Store configuration
        self.symbol = symbol
        self.api_key = api_key
        self.api_secret = api_secret
        self.product_id = int(os.getenv('DELTA_PRODUCT_ID', '27'))
        self.lot = lot
        self.max_open = max_open
        self.hb_sec = hb_sec
        
        # Grid mode (LONG or SHORT)
        self.grid_mode = os.getenv('GRIDBOT_GRID_MODE', 'LONG').upper()
        log.info(f"🎯 Grid Mode: {self.grid_mode}")
        
        # Session tracking
        self.session_tag = f"GBOT_{int(time.time())}"
        
        # Current price (updated by WebSocket)
        self.current_price: Optional[float] = None
        self.previous_price: Optional[float] = None
        self.last_price_update: Optional[float] = None  # Timestamp of last price update
        self.last_ws_price_time: Optional[float] = None  # ✅ FIX NOV 10: Track WebSocket-only updates
        self.price_staleness_threshold: int = 30  # Seconds before triggering REST API fallback
        
        # 🔒 NOV 7: Order throttling to prevent race conditions (bulletproof)
        self.last_buy_order_time: Optional[float] = None  # Timestamp of last BUY order placement
        self.last_sell_order_time: Optional[float] = None  # Timestamp of last SELL order placement
        self.min_order_gap_seconds: int = 30  # Minimum gap between consecutive orders (same side)
        
        # Shutdown management
        self._shutdown_requested = False
        self.stop_event = threading.Event()  # ✅ FIX NOV 12: Added missing stop_event for reconciliation loop
        
        # 🔥 FIX NOV 9: Heartbeat watchdog
        self._last_heartbeat_time = time.time()
        self._watchdog_timeout = 60  # Seconds before watchdog triggers
        self._watchdog_thread = None
        
        # 🧠 FIX NOV 9 PHASE 2: Memory leak prevention
        self._process = psutil.Process()
        self._last_memory_check = time.time()
        self._memory_check_interval = 300  # Check every 5 minutes
        self._memory_threshold_mb = 500  # Alert threshold
        self._memory_critical_mb = 800  # Critical threshold (force GC)
        
        # ================================================================
        # MODULE INITIALIZATION (Dependency Order)
        # ================================================================
        
        # 1. GridCalculator (pure logic, no dependencies)
        log.info("📐 Initializing GridCalculator...")
        self.grid_calc = GridCalculator(
            lower=lower,
            upper=upper,
            step=step,
            ref=ref,
            tick_size=TICK_SIZE
        )
        
        # 2. PositionManager (owns state lock)
        log.info("📊 Initializing PositionManager...")
        self.position_mgr = PositionManager(
            max_open=max_open,
            grid_calculator=self.grid_calc,
            session_tag=self.session_tag
        )
        
        # 3. FillDetector (uses position manager's lock)
        log.info("🎯 Initializing FillDetector...")
        self.fill_detector = FillDetector(
            state_lock=self.position_mgr.state_lock,
            dedup_size=5000
        )
        
        # 4. Initialize API client
        from bot.api.delta_client import DeltaClient
        self.delta_client = DeltaClient()
        
        # 5. OrderManager (uses GridCalc, PositionMgr, API)
        log.info("📝 Initializing OrderManager...")
        self.order_mgr = OrderManager(
            api_client=self.delta_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=self.product_id,
            lot_size=lot,
            tick_size=TICK_SIZE
        )
        
        # 6. Reconciliation (uses OrderMgr, PositionMgr, GridCalc)
        log.info("🔄 Initializing Reconciliation...")
        self.reconciler = Reconciliation(
            api_client=self.delta_client,
            position_manager=self.position_mgr,
            order_manager=self.order_mgr,
            grid_calculator=self.grid_calc,
            gridbot_instance=self  # Pass self for throttle access
        )
        
        # 7. VolatilityHandler (uses all above)
        log.info("🌊 Initializing VolatilityHandler...")
        self.volatility = VolatilityHandler(
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            order_manager=self.order_mgr,
            config={}
        )
        
        # 8. WebSocketManager
        log.info("🔌 Initializing WebSocketManager...")
        from bot.delta_websocket.ws_manager import WebSocketManager
        self.ws_manager = WebSocketManager(
            api_key=api_key,
            api_secret=api_secret,
            symbol=symbol
        )
        
        # 9. WebSocketHandler (routes events)
        log.info("📡 Initializing WebSocketHandler...")
        self.ws_handler = WebSocketHandler(
            ws_manager=self.ws_manager,
            liquidation_monitor=None  # Optional
        )
        
        # 10. Fill Handlers (LONG and SHORT modes with partial fill support)
        log.info("🎯 Initializing Fill Handlers...")
        self.long_handler = LongFillHandler(self)
        self.short_handler = ShortFillHandler(self)
        
        # ================================================================
        # 🔍 MONITORING SYSTEMS (5 Layers of Protection - NOV 8)
        # ================================================================
        
        log.info("🔍 Initializing Comprehensive Monitoring Systems...")
        
        # Layer 1: Price Health Monitor (prevent stale price orders)
        log.info("   ├─ Layer 1: Price Health Monitor")
        self.price_monitor = PriceHealthMonitor(
            stale_threshold=10.0,      # Warn if price >10s old
            critical_threshold=30.0    # Critical if >30s old
        )
        
        # Layer 2: Pre-Order Decision Logger (transparency)
        log.info("   ├─ Layer 2: Pre-Order Decision Logger")
        self.pre_order_logger = PreOrderDecisionLogger()
        
        # Layer 3: TP Verification System (orphan detection)
        log.info("   ├─ Layer 3: TP Verification System")
        self.tp_verifier = TPVerificationSystem(
            delta_client=self.delta_client
        )
        
        # Layer 4: Anomaly Detection System (pattern detection)
        log.info("   ├─ Layer 4: Anomaly Detection System")
        self.anomaly_detector = AnomalyDetectionSystem()
        
        # Layer 5: Predictive Decision Display (show next actions)
        log.info("   ├─ Layer 5: Predictive Decision Display")
        self.predictive_display = PredictiveDecisionDisplay()
        
        # Monitoring Data Writer (WebUI integration for standalone bot)
        log.info("   └─ Monitoring Data Writer (WebUI integration)")
        from bot.monitoring.data_writer import MonitoringDataWriter
        self.monitoring_writer = MonitoringDataWriter()
        self.last_monitoring_write = 0  # Track last write time
        
        log.info("✅ All monitoring systems initialized (5 layers + WebUI writer)")
        
        # ================================================================
        # REST API FALLBACK (NOV 8 - WebSocket Starvation Protection)
        # ================================================================
        
        log.info("🔄 Initializing REST API Fallback System...")
        self.rest_fallback_active = False
        self.rest_fallback_thread: Optional[threading.Thread] = None
        self.rest_fallback_interval = 5.0  # Poll every 5s when active
        
        # ✅ NOV 9 FIX: Adjusted per Delta Exchange official documentation
        # Delta ticker updates every 5s, server heartbeat every 30s
        # Threshold set to 35s (30s heartbeat + 5s buffer) to prevent false alarms
        self.ws_starvation_threshold = 35.0  # Was 30.0, adjusted for Delta's timing
        log.info(f"   ├─ Starvation threshold: {self.ws_starvation_threshold}s (aligned with Delta heartbeat)")
        log.info(f"   └─ Polling interval: {self.rest_fallback_interval}s")
        
        # ================================================================
        # CALLBACK WIRING
        # ================================================================
        
        log.info("🔗 Wiring callbacks...")
        
        # Setup WebSocket callbacks
        self.ws_handler.setup_callbacks(
            on_price_update=self._on_price_update,
            on_fill=self.fill_detector.process_websocket_fill
        )
        
        # Setup fill detector callback
        self.fill_detector.set_fill_callback(self._on_fill_processed)
        
        # 🔍 NOV 8: Wire monitoring systems into OrderManager
        log.info("🔗 Wiring monitoring systems into OrderManager...")
        self.order_mgr.set_monitoring_systems(
            price_monitor=self.price_monitor,
            pre_order_logger=self.pre_order_logger,
            anomaly_detector=self.anomaly_detector
        )
        
        # ✅ FIX NOV 9: Wire fill callback to OrderManager for aggressive polling
        log.info("🔗 Wiring fill callback to OrderManager for aggressive polling...")
        self.order_mgr.set_fill_callback(self.fill_detector.process_websocket_fill)
        log.info("✅ Aggressive polling enabled - will detect fills within 2s if WebSocket fails")
        
        # ✅ NOV 8: Start fill processing queue (sequential processing)
        self.fill_detector.start_processing()
        log.info("✅ Fill processor started - sequential processing active")
        
        # ✅ NOV 8: Wire bot instance to WebUI monitoring routes
        log.info("🌐 Wiring bot instance to WebUI monitoring routes...")
        try:
            from webui.backend.routes.monitoring import set_bot_instance
            set_bot_instance(self)
            log.info("✅ Bot wired to WebUI - monitoring data now accessible via API")
        except ImportError:
            log.warning("⚠️  WebUI monitoring routes not available (import failed)")
        except Exception as e:
            log.warning(f"⚠️  Could not wire to WebUI: {e}")
        
        # Register shutdown handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        atexit.register(self._emergency_cleanup)
        
        # ================================================================
        # 🔄 MODE-ATOMIC STATE MANAGEMENT (NEW NOV 10)
        # ================================================================
        # Mode switch = Fresh start. All existing positions = Manual.
        # Bot never touches manual positions or their TPs.
        
        from bot.strategy.modules.mode_state_manager import get_mode_state_manager
        
        mode_manager = get_mode_state_manager()
        should_load, state_file, reason = mode_manager.handle_mode_transition()
        
        log.info("=" * 80)
        log.info("🔄 STATE LOADING DECISION")
        log.info("=" * 80)
        log.info(f"   Current Mode: {self.grid_mode}")
        log.info(f"   Decision: {'LOAD STATE' if should_load else 'FRESH START'}")
        log.info(f"   Reason: {reason}")
        log.info(f"   State File: {state_file.name}")
        log.info("=" * 80)
        
        if not should_load:
            # Mode switch or first run = Log manual position policy
            mode_manager.log_manual_position_policy()
        
        # Load state if appropriate
        state_loaded = False
        if should_load:
            # Use default mode-specific state file (position_mgr handles it)
            state_loaded = self.position_mgr.load_runtime_state_with_recovery()
        
        if state_loaded:
            log.info("✅ State recovered successfully!")
            log.info(f"   📊 Recovered Positions: {len(self.position_mgr.open_tranches)}")
            log.info(f"   📝 Recovered Pending Buy: {'Yes' if self.position_mgr.pending_buy else 'No'}")
            log.info(f"   🏷️  Session Tag: {self.position_mgr.session_tag}")
            
            # Log recovered positions
            if self.position_mgr.open_tranches:
                log.info("   📍 Recovered position details:")
                for pos in self.position_mgr.open_tranches:
                    log.info(f"      - {pos.get('id', 'N/A')}: {pos.get('quantity', 0)} @ {pos.get('entry', 0)} (TP: {pos.get('target', 'N/A')})")
            
            # Log recovered pending buy order
            if self.position_mgr.pending_buy:
                log.info("   📋 Recovered pending buy order:")
                log.info(f"      - Order ID: {self.position_mgr.pending_buy.get('order_id', 'N/A')}")
                log.info(f"      - Price: {self.position_mgr.pending_buy.get('price', 'N/A')}")
            
            # 🛡️ RECOVERY: Place missing TPs (if position loaded without TP)
            log.info("🔍 Checking for positions without TPs...")
            missing_tp_count = 0
            for pos in self.position_mgr.open_tranches:
                if not pos.get('tp_id') and not pos.get('protected', False):
                    missing_tp_count += 1
                    log.warning(f"⚠️ Position missing TP: entry=${pos['entry_price']} side={pos.get('side', 'long')}")
                    log.warning(f"   Placing recovery TP @ ${pos['tp_price']}")
                    
                    # Place TP using order manager
                    tp_success = self.order_mgr.safe_place_tp(pos, check_collisions=True)
                    if tp_success:
                        log.info(f"✅ Recovery TP placed successfully")
                        pos['protected'] = True
                    else:
                        log.error(f"❌ Recovery TP placement failed - adding to retry queue")
                        self.position_mgr.schedule_tp_retry(pos)
            
            if missing_tp_count > 0:
                log.warning(f"🛡️ Attempted to recover {missing_tp_count} missing TP(s)")
                # Persist state with updated tp_ids
                self.position_mgr.persist_runtime_state()
            else:
                log.info("✅ All positions have TPs - no recovery needed")
            
            # Exchange reconciliation will verify state on first heartbeat
            log.info("   ⚠️  Exchange reconciliation will verify state on startup")
            
        else:
            log.info("⚠️  No persisted state found - starting fresh")
            log.info("   Exchange reconciliation will sync positions on startup")
        
        log.info("=" * 80)
        log.info("✅ GridBot initialized - All modules ready")
        log.info(f"   Grid: ${lower:,.0f} - ${upper:,.0f}, Step: ${step:,.0f}")
        log.info(f"   Lot: {lot}, Max Open: {max_open}")
        log.info("=" * 80)
        
        # Start REST fallback monitor
        self._start_rest_fallback_monitor()
        
        # ✅ FIX NOV 11: Start exchange reconciliation system
        self._start_reconciliation_system()
    
    # ========================================================================
    # Exchange Reconciliation System (NOV 11 - Fill Detection Safety Net)
    # ========================================================================
    
    def _start_reconciliation_system(self):
        """
        Start periodic reconciliation with exchange to catch missed fills.
        
        This is the CRITICAL SAFETY NET that prevents unprotected positions.
        Runs every 5 minutes to verify bot state matches exchange reality.
        """
        log.info("=" * 80)
        log.info("🔍 STARTING EXCHANGE RECONCILIATION SYSTEM")
        log.info("=" * 80)
        log.info("   Purpose: Catch missed fills and verify TP protection")
        log.info("   Frequency: Every 5 minutes")
        log.info("   Actions: Detect missed fills, verify TPs exist, emergency TP placement")
        log.info("=" * 80)
        
        # Initialize reconciliation state
        self._last_reconciliation_time = 0
        self._reconciliation_interval = 300  # 5 minutes
        self._reconciliation_errors = 0
        self._max_reconciliation_errors = 10
        
        # Start background thread
        reconciliation_thread = threading.Thread(
            target=self._reconciliation_loop,
            daemon=True,
            name="ExchangeReconciliation"
        )
        reconciliation_thread.start()
        log.info("✅ Exchange reconciliation system started")
    
    def _reconciliation_loop(self):
        """
        Main reconciliation loop - runs every 5 minutes.
        
        ✅ FIX NOV 11: Critical safety net for missed fills
        """
        log.info("🔍 [RECONCILIATION] Loop started")
        
        while not self.stop_event.is_set():
            try:
                # Sleep in small intervals to allow quick shutdown
                for _ in range(self._reconciliation_interval):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)
                
                if self.stop_event.is_set():
                    break
                
                # Run reconciliation
                log.info("=" * 80)
                log.info("🔍 [RECONCILIATION] Starting periodic check...")
                log.info("=" * 80)
                
                self._perform_reconciliation()
                
                self._last_reconciliation_time = time.time()
                self._reconciliation_errors = 0  # Reset error counter on success
                
                log.info("✅ [RECONCILIATION] Check complete")
                log.info("=" * 80)
                
            except Exception as e:
                self._reconciliation_errors += 1
                log.error(f"❌ [RECONCILIATION] Error: {e}")
                import traceback
                log.error(traceback.format_exc())
                
                if self._reconciliation_errors >= self._max_reconciliation_errors:
                    log.critical(f"🚨 [RECONCILIATION] Too many errors ({self._reconciliation_errors}), stopping reconciliation")
                    break
        
        log.info("🔍 [RECONCILIATION] Loop exited")
    
    def _perform_reconciliation(self):
        """
        Perform complete reconciliation between bot state and exchange.
        
        Steps:
        1. Get all open orders from exchange
        2. Get bot's pending orders
        3. Detect orders that bot thinks are pending but are actually filled
        4. Process missed fills
        5. Verify all filled positions have TP protection
        6. Emergency TP placement if needed
        """
        try:
            # Step 1: Get exchange state
            log.info("📡 [RECONCILIATION] Querying exchange for open orders...")
            exchange_orders_resp = self.delta_client.list_orders(self.product_id, state='open')
            
            if not isinstance(exchange_orders_resp, list):
                log.error(f"❌ [RECONCILIATION] Invalid response from list_orders: {type(exchange_orders_resp)}")
                return
            
            exchange_order_ids = {str(o['id']) for o in exchange_orders_resp if 'id' in o}
            log.info(f"   Found {len(exchange_order_ids)} open orders on exchange")
            
            # Step 2: Get bot's pending orders
            pending_buy = self.position_mgr.get_pending_buy()
            pending_sell = self.position_mgr.get_pending_sell()
            
            bot_pending_ids = set()
            if pending_buy:
                bot_pending_ids.add(str(pending_buy.get('order_id')))
            if pending_sell:
                bot_pending_ids.add(str(pending_sell.get('order_id')))
            
            log.info(f"   Bot thinks {len(bot_pending_ids)} orders are pending")
            
            # Step 3: Detect missed fills (bot thinks pending, but not on exchange)
            potentially_filled = bot_pending_ids - exchange_order_ids
            
            if potentially_filled:
                log.warning(f"⚠️ [RECONCILIATION] Found {len(potentially_filled)} orders that may have filled without detection!")
                for order_id in potentially_filled:
                    log.warning(f"   Investigating order {order_id}...")
                    self._investigate_missing_order(order_id)
            else:
                log.info(f"✅ [RECONCILIATION] All pending orders verified on exchange")
            
            # Step 4: Verify TP protection for all positions
            log.info("🛡️ [RECONCILIATION] Verifying TP protection...")
            self._verify_tp_protection(exchange_orders_resp)
            
        except Exception as e:
            log.error(f"❌ [RECONCILIATION] Failed: {e}")
            raise
    
    def _investigate_missing_order(self, order_id: str):
        """
        Investigate an order that bot thinks is pending but isn't on exchange.
        Could be filled, cancelled, or rejected.
        """
        try:
            log.info(f"🔍 [RECONCILIATION] Querying status of order {order_id}...")
            
            # Query order details
            order_resp = self.delta_client.get_order(order_id)
            
            if not order_resp.get('success') or 'result' not in order_resp:
                log.error(f"❌ [RECONCILIATION] Failed to query order {order_id}")
                return
            
            order = order_resp['result']
            state = order.get('state', 'unknown')
            side = order.get('side', 'unknown')
            price = float(order.get('limit_price', 0))
            size = float(order.get('size', 0))
            avg_fill_price = float(order.get('average_fill_price') or price)
            
            log.info(f"   Order {order_id}: state={state}, side={side}, price=${price:,.0f}")
            
            if state == 'filled':
                log.warning(f"🚨 [RECONCILIATION] MISSED FILL DETECTED!")
                log.warning(f"   Order {order_id} is FILLED but bot didn't process it")
                log.warning(f"   Side: {side}, Price: ${avg_fill_price:,.0f}, Size: {size}")
                
                # Process the missed fill
                self._process_missed_fill(order_id, side, avg_fill_price, size)
                
            elif state in ['cancelled', 'rejected']:
                log.warning(f"⚠️ [RECONCILIATION] Order {order_id} was {state}")
                # Clear from bot's pending orders
                if side == 'buy':
                    self.position_mgr.clear_pending_buy()
                elif side == 'sell':
                    self.position_mgr.clear_pending_sell()
                log.info(f"   Cleared {state} order from bot memory")
                
            else:
                log.warning(f"⚠️ [RECONCILIATION] Order {order_id} state: {state}")
                
        except Exception as e:
            log.error(f"❌ [RECONCILIATION] Failed to investigate order {order_id}: {e}")
    
    def _process_missed_fill(self, order_id: str, side: str, fill_price: float, fill_size: float):
        """
        Process a fill that was completely missed by WebSocket and polling.
        
        ✅ FIX NOV 11: Recovery mechanism for missed fills
        """
        try:
            log.critical("=" * 80)
            log.critical("🚨 PROCESSING MISSED FILL (RECONCILIATION RECOVERY)")
            log.critical("=" * 80)
            log.critical(f"   Order ID: {order_id}")
            log.critical(f"   Side: {side}")
            log.critical(f"   Price: ${fill_price:,.0f}")
            log.critical(f"   Size: {fill_size}")
            log.critical("=" * 80)
            
            # Create fill data structure
            fill_data = {
                'order_id': str(order_id),
                'fill_price': fill_price,
                'fill_size': fill_size,
                'is_complete': True,
                'cumulative_filled': fill_size,
                'total_order_size': fill_size,
                'side': side,
                '_detected_via': 'reconciliation_recovery',
                '_recovery_timestamp': time.time()
            }
            
            # Send to fill detector for processing
            log.critical("📥 Sending missed fill to fill_detector...")
            self.fill_detector.process_websocket_fill(fill_data)
            
            log.critical("✅ Missed fill queued for processing")
            log.critical("   Fill detector will handle TP placement")
            log.critical("=" * 80)
            
            # Send critical alert
            try:
                from bot.utils.notifier import TelegramNotifier
                notifier = TelegramNotifier()
                notifier.send(
                    f"🚨 CRITICAL: Missed Fill Recovered\n\n"
                    f"Order {order_id} filled but not detected.\n"
                    f"Reconciliation system caught it and triggered processing.\n\n"
                    f"Side: {side}\n"
                    f"Price: ${fill_price:,.0f}\n"
                    f"Size: {fill_size}\n\n"
                    f"TP placement in progress..."
                )
            except Exception:
                pass
                
        except Exception as e:
            log.critical(f"❌ FAILED TO PROCESS MISSED FILL: {e}")
            import traceback
            log.critical(traceback.format_exc())
            
            # Emergency alert
            try:
                from bot.utils.notifier import TelegramNotifier
                notifier = TelegramNotifier()
                notifier.send(
                    f"🚨🚨 EMERGENCY: Missed Fill Recovery FAILED\n\n"
                    f"Order {order_id} is filled but processing failed.\n"
                    f"MANUAL INTERVENTION REQUIRED\n\n"
                    f"Error: {e}\n\n"
                    f"Action: Place TP manually for this position"
                )
            except Exception:
                pass
    
    def _verify_tp_protection(self, exchange_orders: list):
        """
        Verify all open positions have TP orders on exchange.
        
        ✅ FIX NOV 11: Final safety check for unprotected positions
        """
        try:
            # Get all open positions from bot
            positions = self.position_mgr.get_open_positions()
            
            if not positions:
                log.info("   No open positions to verify")
                return
            
            log.info(f"   Verifying {len(positions)} positions have TPs...")
            
            # Get all open SELL orders from exchange (potential TPs)
            exchange_tps = [o for o in exchange_orders if o.get('side') == 'sell']
            exchange_tp_ids = {str(o['id']) for o in exchange_tps if 'id' in o}
            
            log.info(f"   Found {len(exchange_tp_ids)} SELL orders on exchange")
            
            # Check each position
            unprotected_positions = []
            for pos in positions:
                tp_id = pos.get('tp_id') or pos.get('tp_order_id')
                entry_order_id = pos.get('buy_order_id') or pos.get('order_id')
                entry_price = pos.get('entry_price', 0)
                tp_price = pos.get('tp_price', 0)
                
                if not tp_id:
                    log.error(f"❌ Position {entry_order_id} has NO tp_id in bot memory!")
                    unprotected_positions.append(pos)
                elif str(tp_id) not in exchange_tp_ids:
                    log.error(f"❌ Position {entry_order_id}: TP {tp_id} NOT FOUND on exchange!")
                    unprotected_positions.append(pos)
                else:
                    log.debug(f"✅ Position {entry_order_id}: TP {tp_id} verified on exchange")
            
            if unprotected_positions:
                log.critical("=" * 80)
                log.critical(f"🚨 FOUND {len(unprotected_positions)} UNPROTECTED POSITIONS!")
                log.critical("=" * 80)
                
                for pos in unprotected_positions:
                    log.critical(f"   Position: {pos.get('buy_order_id')}")
                    log.critical(f"   Entry: ${pos.get('entry_price', 0):,.0f}")
                    log.critical(f"   Expected TP: ${pos.get('tp_price', 0):,.0f}")
                    log.critical(f"   TP ID in memory: {pos.get('tp_id', 'MISSING')}")
                    
                    # Emergency TP placement
                    log.critical(f"   🚨 EMERGENCY: Placing TP NOW...")
                    try:
                        self._emergency_tp_placement(pos)
                    except Exception as e:
                        log.critical(f"   ❌ EMERGENCY TP FAILED: {e}")
                
                log.critical("=" * 80)
            else:
                log.info(f"✅ All {len(positions)} positions verified protected")
                
        except Exception as e:
            log.error(f"❌ [RECONCILIATION] TP verification failed: {e}")
            raise
    
    def _emergency_tp_placement(self, position: dict):
        """
        Emergency TP placement during reconciliation.
        
        ✅ FIX NOV 11: Last resort protection for unprotected positions
        """
        try:
            entry_price = position.get('entry_price')
            tp_price = position.get('tp_price')
            size = position.get('size', self.lot_size)
            entry_order_id = position.get('buy_order_id') or position.get('order_id')
            
            if not entry_price or not tp_price:
                raise ValueError(f"Missing entry_price or tp_price in position")
            
            log.critical(f"🚨 [EMERGENCY TP] Placing TP for position {entry_order_id}")
            log.critical(f"   Entry: ${entry_price:,.0f} → TP: ${tp_price:,.0f}")
            
            # Place TP using mandatory placement (with retries)
            tp_order_id = self.order_mgr.place_tp_mandatory(position, max_retries=5)
            
            log.critical(f"✅ [EMERGENCY TP] Placed: ID {tp_order_id}")
            
            # Send alert
            try:
                from bot.utils.notifier import TelegramNotifier
                notifier = TelegramNotifier()
                notifier.send(
                    f"🚨 EMERGENCY TP PLACED\n\n"
                    f"Reconciliation found unprotected position.\n"
                    f"Emergency TP placed successfully.\n\n"
                    f"Position: {entry_order_id}\n"
                    f"Entry: ${entry_price:,.0f}\n"
                    f"TP: ${tp_price:,.0f} (ID: {tp_order_id})\n\n"
                    f"Position is now protected."
                )
            except Exception:
                pass
                
        except Exception as e:
            log.critical(f"❌ [EMERGENCY TP] FAILED: {e}")
            
            # Critical alert - manual intervention needed
            try:
                from bot.utils.notifier import TelegramNotifier
                notifier = TelegramNotifier()
                notifier.send(
                    f"🚨🚨🚨 CRITICAL EMERGENCY\n\n"
                    f"UNPROTECTED POSITION - TP PLACEMENT FAILED\n\n"
                    f"Position: {entry_order_id}\n"
                    f"Entry: ${entry_price:,.0f}\n"
                    f"TP Target: ${tp_price:,.0f}\n\n"
                    f"Error: {e}\n\n"
                    f"IMMEDIATE MANUAL ACTION REQUIRED:\n"
                    f"1. Stop bot\n"
                    f"2. Manually place SELL order @ ${tp_price:,.0f}\n"
                    f"3. Verify on exchange\n"
                )
            except Exception:
                pass
            
            raise
    
    # ========================================================================
    # REST API Fallback System (NOV 8 - WebSocket Starvation Protection)
    # ========================================================================
    
    def _start_rest_fallback_monitor(self):
        """Start background thread to monitor WebSocket health"""
        log.info("🔄 Starting REST API fallback monitor...")
        monitor_thread = threading.Thread(target=self._rest_fallback_monitor_loop, daemon=True, name="RestFallbackMonitor")
        monitor_thread.start()
        log.info("✅ REST fallback monitor started")
    
    def _rest_fallback_monitor_loop(self):
        """
        Background loop that monitors WebSocket health and activates REST fallback.
        
        ✅ FIX NOV 11: Added automatic WebSocket reconnection when critically stale
        
        Activates REST polling when:
        - WebSocket has not sent price update for > ws_starvation_threshold seconds
        - No price data received at all (last_ws_price_time is None)
        
        Deactivates REST polling when:
        - WebSocket recovers (fresh price update received)
        
        Triggers WebSocket reconnection when:
        - Price is critically stale (>300s / 5 minutes)
        """
        log.info("🔄 [REST FALLBACK MONITOR] Loop started")
        last_reconnect_attempt = 0
        reconnect_cooldown = 60.0  # Wait 60s between reconnection attempts
        
        while not self._shutdown_requested:
            try:
                # ✅ FIX NOV 10: Handle case where last_ws_price_time is None (no data yet)
                if self.last_ws_price_time is None:
                    # No WebSocket data received yet - check how long we've been waiting
                    if hasattr(self, '_ws_connect_time'):
                        wait_time = time.time() - self._ws_connect_time
                        if wait_time > 15 and not self.rest_fallback_active:
                            log.warning(f"🚨 [REST FALLBACK] No WebSocket data for {wait_time:.1f}s since connect")
                            log.warning(f"   Activating REST fallback to get initial price...")
                            self._activate_rest_fallback()
                    
                elif self.last_ws_price_time:
                    age = time.time() - self.last_ws_price_time
                    
                    # ✅ FIX NOV 11: Attempt WebSocket reconnection if critically stale
                    if age > 300.0:  # 5 minutes without price update = dead connection
                        time_since_last_reconnect = time.time() - last_reconnect_attempt
                        
                        if time_since_last_reconnect > reconnect_cooldown:
                            log.critical("=" * 80)
                            log.critical(f"🚨 CRITICAL: WebSocket DEAD for {age:.1f}s (>5 minutes)")
                            log.critical("   Attempting automatic reconnection...")
                            log.critical("=" * 80)
                            
                            try:
                                # Attempt to reconnect WebSocket
                                self._reconnect_websocket()
                                last_reconnect_attempt = time.time()
                                
                                # Send alert
                                try:
                                    from bot.utils.notifier import TelegramNotifier
                                    notifier = TelegramNotifier()
                                    notifier.send(
                                        f"🔄 WebSocket Reconnection\n\n"
                                        f"Price was stale for {age:.1f}s\n"
                                        f"Automatic reconnection triggered\n\n"
                                        f"Monitoring for recovery..."
                                    )
                                except Exception:
                                    pass
                            except Exception as e:
                                log.error(f"❌ WebSocket reconnection failed: {e}")
                                import traceback
                                log.error(traceback.format_exc())
                    
                    # Activate fallback if WebSocket starved
                    if age > self.ws_starvation_threshold and not self.rest_fallback_active:
                        log.warning(f"🚨 [REST FALLBACK] WebSocket starved for {age:.1f}s > {self.ws_starvation_threshold}s threshold")
                        self._activate_rest_fallback()
                    
                    # Deactivate fallback if WebSocket recovered
                    elif age < 10 and self.rest_fallback_active:
                        log.info(f"✅ [REST FALLBACK] WebSocket recovered (age: {age:.1f}s)")
                        self._deactivate_rest_fallback()
                
                time.sleep(1.0)  # Check every second
                
            except Exception as e:
                log.error(f"❌ [REST FALLBACK MONITOR] Error: {e}", exc_info=True)
                import traceback
                log.error(traceback.format_exc())
                time.sleep(5.0)  # Back off on error
    
    def _activate_rest_fallback(self):
        """Activate REST API polling as fallback for WebSocket"""
        if self.rest_fallback_active:
            return  # Already active
        
        log.warning("=" * 80)
        log.warning("🔄 ACTIVATING REST API FALLBACK - WebSocket Starvation Detected")
        log.warning(f"   Last WebSocket update: {time.time() - self.last_ws_price_time:.1f}s ago")
        log.warning(f"   Polling interval: {self.rest_fallback_interval}s")
        log.warning("=" * 80)
        
        self.rest_fallback_active = True
        
        # Start polling thread
        self.rest_fallback_thread = threading.Thread(
            target=self._rest_polling_loop,
            daemon=True,
            name="RestFallbackPoller"
        )
        self.rest_fallback_thread.start()
        
        log.info("✅ [REST FALLBACK] Polling thread started")
    
    def _deactivate_rest_fallback(self):
        """Deactivate REST API fallback when WebSocket recovers"""
        if not self.rest_fallback_active:
            return  # Already inactive
        
        log.info("=" * 80)
        log.info("✅ DEACTIVATING REST API FALLBACK - WebSocket Recovered")
        log.info("=" * 80)
        
        self.rest_fallback_active = False
        
        # Thread will exit on next iteration when it checks rest_fallback_active
        if self.rest_fallback_thread and self.rest_fallback_thread.is_alive():
            log.info("⏳ [REST FALLBACK] Waiting for polling thread to exit...")
            self.rest_fallback_thread.join(timeout=10.0)
        
        self.rest_fallback_thread = None
        log.info("✅ [REST FALLBACK] Deactivated successfully")
    
    def _rest_polling_loop(self):
        """
        Background loop that polls REST API for price and order updates.
        
        Runs while rest_fallback_active == True.
        Polls every rest_fallback_interval seconds.
        """
        log.info("🔄 [REST FALLBACK] Polling loop started")
        
        while self.rest_fallback_active and not self._shutdown_requested:
            try:
                # Poll current price
                self._poll_price_via_rest()
                
                # Poll pending orders for fill detection
                self._poll_pending_orders_via_rest()
                
                time.sleep(self.rest_fallback_interval)
                
            except Exception as e:
                log.error(f"❌ [REST FALLBACK] Polling error: {e}", exc_info=True)
                time.sleep(self.rest_fallback_interval)
        
        log.info("✅ [REST FALLBACK] Polling loop exited")
    
    def _poll_price_via_rest(self):
        """
        Poll current price via REST API and update last_price_update
        
        ✅ FIX NOV 11: Improved error handling and price monitor update
        """
        try:
            ticker = self.delta_client.get_ticker_by_product_id(self.product_id)
            
            if ticker and 'close' in ticker:
                price = float(ticker['close'])
                
                # ✅ FIX NOV 10: Update current_price properly
                self.previous_price = self.current_price
                self.current_price = price
                self.last_price_update = time.time()
                # NOTE: Do NOT update last_ws_price_time - this is REST data!
                
                # ✅ FIX NOV 10: Sync market price to order manager
                self.order_mgr.update_market_price(self.current_price)
                
                # ✅ FIX NOV 11: Update price health monitor with REST source
                if hasattr(self, 'price_monitor') and self.price_monitor:
                    self.price_monitor.update_price(self.current_price, source="REST_API")
                
                log.debug(f"📊 [REST FALLBACK] Price update: ${price:,.2f}")
                
                # ✅ FIX NOV 11: Volatility handler doesn't have update_price() method
                # Volatility is calculated on-demand in check_pending_order_safety()
                # No need to explicitly update it here - it reads self.current_price
                # Removed: self.volatility.update_price(price) - method doesn't exist
                
            else:
                log.warning(f"⚠️ [REST FALLBACK] Invalid ticker response: {ticker}")
                
        except Exception as e:
            log.error(f"❌ [REST FALLBACK] Failed to poll price: {e}")
            import traceback
            log.debug(traceback.format_exc())
    
    def _poll_pending_orders_via_rest(self):
        """
        Poll pending orders via REST API to detect fills.
        
        Checks pending_buy and all open_tranches for filled orders.
        When fill detected, sends to fill_detector for processing.
        """
        try:
            # Check pending buy order
            if self.position_mgr.pending_buy:
                order_id = self.position_mgr.pending_buy.get('order_id')
                if order_id:
                    self._check_order_status(order_id, 'buy')
            
            # Check all open tranche TP orders
            for tranche in self.position_mgr.open_tranches:
                tp_order_id = tranche.get('tp_order_id')
                if tp_order_id:
                    self._check_order_status(tp_order_id, 'sell')
        
        except Exception as e:
            log.error(f"❌ [REST FALLBACK] Failed to poll pending orders: {e}")
    
    def _check_order_status(self, order_id: str, expected_side: str):
        """
        Check order status via REST API and process if filled.
        
        Args:
            order_id: Order ID to check
            expected_side: 'buy' or 'sell' for validation
        """
        try:
            order = self.delta_client.get_order(order_id)
            
            if not order:
                return
            
            state = order.get('state', '').lower()
            
            # If order filled, construct fill event and send to fill_detector
            if state == 'filled':
                fill_event = {
                    'order_id': str(order_id),
                    'fill_price': float(order.get('average_fill_price', order.get('limit_price', 0))),
                    'fill_size': float(order.get('size', 0)),
                    'side': expected_side,
                    'role': 'taker',  # Conservative assumption for REST-detected fills
                    'timestamp': order.get('updated_at', order.get('created_at', '')),
                    'detection_source': 'rest_fallback',
                    'cumulative_filled': float(order.get('size', 0)),
                    'total_order_size': float(order.get('size', 0)),
                    'unfilled_size': 0.0,
                    'is_complete': True
                }
                
                log.info(f"✅ [REST FALLBACK] Detected fill: {expected_side} order {order_id} @ ${fill_event['fill_price']:,.2f}")
                
                # Send to fill detector (same path as WebSocket fills)
                self.fill_detector.process_websocket_fill(fill_event)
        
        except Exception as e:
            log.error(f"❌ [REST FALLBACK] Failed to check order {order_id}: {e}")
    
    # ========================================================================
    # WebSocket Reconnection (NOV 11 FIX)
    # ========================================================================
    
    def _reconnect_websocket(self):
        """
        Attempt to reconnect WebSocket when connection is dead.
        
        ✅ FIX NOV 11: Automatic reconnection for stale WebSocket connections
        ✅ ENHANCED (Delta Exchange AI): Reconnect ws_manager and re-subscribe to channels
        
        Strategy:
        1. Disconnect existing WebSocket connection
        2. Reconnect ws_manager (this re-subscribes to all channels)
        3. Re-initialize WebSocket handler
        4. Update reconnection timestamp
        5. Reset reconnection attempt counter on success
        
        This method is called by the REST fallback monitor when price age
        exceeds critical threshold (5 minutes).
        """
        log.warning("=" * 80)
        log.warning("🔄 INITIATING WEBSOCKET RECONNECTION")
        log.warning("=" * 80)
        
        try:
            # Step 1: Disconnect existing WebSocket (if connected)
            try:
                if hasattr(self, 'ws_manager') and self.ws_manager:
                    log.info("   Step 1: Disconnecting existing WebSocket...")
                    self.ws_manager.disconnect()
                    log.info("   ✅ Disconnected")
            except Exception as e:
                log.warning(f"   ⚠️ Could not disconnect WebSocket: {e}")
            
            # Step 2: Reconnect WebSocket manager (re-subscribes to all channels)
            log.info("   Step 2: Reconnecting WebSocket manager...")
            # ✅ CRITICAL FIX (Delta Exchange AI): Must call connect() to re-subscribe
            # connect() method handles:
            # - Re-establishing WebSocket connection
            # - Re-subscribing to v2/user_trades (fills)
            # - Re-subscribing to orders, positions, margins
            # - Re-subscribing to v2/ticker (price updates)
            self.ws_manager.connect()
            log.info("   ✅ WebSocket manager reconnected and re-subscribed")
            
            # Step 3: Re-initialize WebSocket handler (routes events)
            log.info("   Step 3: Re-initializing WebSocket handler...")
            # Use same signature as initial setup at line 225
            self.ws_handler = WebSocketHandler(
                ws_manager=self.ws_manager,
                liquidation_monitor=None  # Optional
            )
            log.info("   ✅ WebSocket handler re-initialized")
            
            # Step 4: Mark as reconnected (for REST fallback monitor)
            self._ws_connect_time = time.time()
            log.info("   Step 4: Updated reconnection timestamp")
            
            # Step 5: Reset reconnection attempt counter (for exponential backoff)
            if hasattr(self, '_reconnection_attempts'):
                log.info(f"   Step 5: Reset reconnection attempts (was {self._reconnection_attempts})")
                self._reconnection_attempts = 0
            
            log.warning("=" * 80)
            log.warning("✅ WEBSOCKET RECONNECTION COMPLETE")
            log.warning("   ✅ WebSocket manager reconnected")
            log.warning("   ✅ All channels re-subscribed")
            log.warning("   ✅ Event routing re-established")
            log.warning("   Monitoring for price updates...")
            log.warning("=" * 80)
            
        except Exception as e:
            log.critical(f"❌ WEBSOCKET RECONNECTION FAILED: {e}")
            import traceback
            log.error(traceback.format_exc())
            
            # ✅ ENHANCEMENT (Delta Exchange AI): Exponential backoff retry
            self._schedule_reconnection_retry()
            
            # Send critical alert
            try:
                from bot.utils.notifier import TelegramNotifier
                notifier = TelegramNotifier()
                
                retry_info = ""
                if hasattr(self, '_reconnection_attempts'):
                    retry_info = f"Attempt #{self._reconnection_attempts}\n"
                
                notifier.send(
                    f"🚨 CRITICAL: WebSocket Reconnection FAILED\n\n"
                    f"{retry_info}"
                    f"Error: {e}\n\n"
                    f"Will retry with exponential backoff.\n"
                    f"REST fallback continues providing prices."
                )
            except Exception:
                pass
    
    def _schedule_reconnection_retry(self):
        """
        Schedule WebSocket reconnection retry with exponential backoff.
        
        ✅ NEW (Delta Exchange AI): Automatic retry on reconnection failure
        
        Backoff schedule:
        - Attempt 1: 5 seconds
        - Attempt 2: 10 seconds
        - Attempt 3: 20 seconds
        - Attempt 4: 40 seconds
        - Attempt 5+: 300 seconds (5 minutes max)
        """
        if not hasattr(self, '_reconnection_attempts'):
            self._reconnection_attempts = 0
        
        self._reconnection_attempts += 1
        
        # Exponential backoff with 5-minute cap
        delay = min(300, 5 * (2 ** self._reconnection_attempts))
        
        log.warning("=" * 80)
        log.warning(f"🔄 SCHEDULING RECONNECTION RETRY")
        log.warning(f"   Attempt: #{self._reconnection_attempts}")
        log.warning(f"   Delay: {delay} seconds")
        log.warning(f"   Next retry at: {time.strftime('%H:%M:%S', time.localtime(time.time() + delay))}")
        log.warning("=" * 80)
        
        # Schedule retry using threading.Timer
        import threading
        timer = threading.Timer(delay, self._reconnect_websocket)
        timer.daemon = True  # Don't block shutdown
        timer.start()
    
    # ========================================================================
    # Telegram Notifications
    # ========================================================================
    
    def _send_startup_notification(self):
        """Send Telegram notification when bot starts"""
        try:
            from bot.utils.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            
            if notifier.enabled:
                mode = os.getenv('TRADING_MODE', 'demo').upper()
                message = (
                    f"🚀 GRIDBOT STARTED\n\n"
                    f"Mode: {mode}\n"
                    f"Symbol: {self.symbol}\n"
                    f"Grid: ${self.lower:,.0f} - ${self.upper:,.0f}\n"
                    f"Step: ${self.step:,.0f}\n"
                    f"Lot: {self.lot}\n"
                    f"Max Positions: {self.max_open}\n\n"
                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                notifier.send(message)
                log.info("📱 Sent startup notification")
        except Exception as e:
            log.debug(f"Could not send startup notification: {e}")
    
    def _send_shutdown_notification(self):
        """Send Telegram notification when bot stops"""
        try:
            from bot.utils.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            
            if notifier.enabled:
                # Get runtime stats
                capacity = self.position_mgr.get_capacity_status()
                runtime = time.time() - getattr(self, '_start_time', time.time())
                
                message = (
                    f"🛑 GRIDBOT STOPPED\n\n"
                    f"Symbol: {self.symbol}\n"
                    f"Runtime: {runtime/3600:.1f}h\n"
                    f"Final Positions: {capacity['open']}/{capacity['max_open']}\n\n"
                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                notifier.send(message)
                log.info("📱 Sent shutdown notification")
        except Exception as e:
            log.debug(f"Could not send shutdown notification: {e}")
    
    # ========================================================================
    # Simple Grid Seeding (NEW!)
    # ========================================================================
    
    def seed_missed_grid_levels(self, count: int):
        """
        Simple grid seeding - Fill missed grid levels using existing order functions
        
        For LONG: Place BUY orders below current price
        For SHORT: Place SELL orders above current price
        
        No new modules needed - reuses existing place_buy_order()/place_sell_order()
        Bot handles TPs automatically using existing fill detection logic
        """
        if count <= 0:
            return
        
        current_price = self.current_price
        mode = os.getenv('GRIDBOT_GRID_MODE', 'LONG').upper()
        
        log.info("=" * 70)
        log.info(f"🌱 SEEDING {count} MISSED GRID LEVELS ({mode} MODE)")
        log.info(f"📍 Current Price: ${current_price:,.0f}")
        log.info("=" * 70)
        
        for i in range(count):
            if mode == 'LONG':
                # Buy below current price (going down)
                level = current_price - (i + 1) * self.grid_calc.step
                
                if level >= self.grid_calc.lower:
                    order_id = self.order_mgr.place_buy_order(price=level, post_only=True)
                    if order_id:
                        log.info(f"  ✅ Grid BUY placed @ ${level:,.0f}")
                else:
                    log.warning(f"  ⚠️  Level ${level:,.0f} below grid lower bound, stopping")
                    break
            
            elif mode == 'SHORT':
                # Sell above current price (going up)
                level = current_price + (i + 1) * self.grid_calc.step
                
                if level <= self.grid_calc.upper:
                    order_id = self.order_mgr.place_sell_order(price=level, post_only=True)
                    if order_id:
                        log.info(f"  ✅ Grid SELL placed @ ${level:,.0f}")
                else:
                    log.warning(f"  ⚠️  Level ${level:,.0f} above grid upper bound, stopping")
                    break
        
        log.info("=" * 70)
        log.info(f"✅ SEEDING COMPLETE - Bot will manage TPs automatically")
        log.info("=" * 70)
    
    # ========================================================================
    # Event Handlers (Thin wrappers - delegate to modules)
    # ========================================================================
    
    def _on_price_update(self, ticker_data: Dict):
        """
        Handle price update from WebSocket
        
        Delegates to VolatilityHandler for safety checks.
        🔍 NOV 8: Now includes comprehensive price health monitoring
        """
        try:
            # Update price tracking
            self.previous_price = self.current_price
            self.current_price = ticker_data.get('last', 0)
            self.last_price_update = time.time()  # Record timestamp
            self.last_ws_price_time = time.time()  # ✅ FIX NOV 10: Track WebSocket update separately
            
            # ✅ FIX NOV 10: Sync market price to order manager for reconciliation validation
            self.order_mgr.update_market_price(self.current_price)
            
            # 🔍 LAYER 1: Price Health Monitoring (NOV 8)
            self.price_monitor.update_price(self.current_price, source="WebSocket")
            self.price_monitor.check_and_log_health(verbose=False)  # Log warnings if stale
            
            # 🔒 PROACTIVE VOLATILITY MONITORING on every price update
            try:
                from bot.volatility.iv_rv_tracker import get_volatility_tracker
                vol_tracker = get_volatility_tracker()
                
                if vol_tracker:
                    # Check if pending order needs to be cancelled (unsafe)
                    # or if we should place order after recovery (became safe)
                    was_halted = self.volatility.volatility_halted
                    
                    self.volatility.check_pending_order_safety(vol_tracker, self.current_price)
                    
                    # If volatility just became safe (was halted, now not), place pending order
                    if was_halted and not self.volatility.volatility_halted:
                        # Mode-aware recovery: LONG uses pending_buy, SHORT uses pending_sell
                        if self.grid_mode == 'LONG':
                            pending_order = self.position_mgr.get_pending_buy()
                            
                            # Only place if no pending order exists
                            if not pending_order and self.position_mgr.try_reserve_capacity():
                                positions = self.position_mgr.get_positions()
                                target = self.grid_calc.compute_next_buy_level(positions)
                                
                                if target and self.grid_calc.is_within_bounds(target):
                                    order_id = self.order_mgr.place_buy_order(target, post_only=True)
                                    if order_id:
                                        self.position_mgr.set_pending_buy({
                                            'order_id': order_id,
                                            'price': target,
                                            'timestamp': time.time()
                                        })
                                        log.info(f"✅ BUY order placed @ ${target:,.0f} after volatility recovery")
                                
                                self.position_mgr.release_capacity()
                        else:  # SHORT mode
                            pending_order = self.position_mgr.get_pending_sell()
                            
                            # Only place if no pending order exists
                            if not pending_order and self.position_mgr.try_reserve_capacity():
                                positions = self.position_mgr.get_positions()
                                target = self.grid_calc.compute_next_sell_level(positions)
                                
                                if target and self.grid_calc.is_within_bounds(target):
                                    order_id = self.order_mgr.place_sell_order(target)
                                    if order_id:
                                        self.position_mgr.set_pending_sell({
                                            'order_id': order_id,
                                            'price': target,
                                            'timestamp': time.time()
                                        })
                                        log.info(f"✅ SELL order placed @ ${target:,.0f} after volatility recovery")
                                
                                self.position_mgr.release_capacity()
                            
            except Exception as e:
                # Don't let volatility check errors crash price updates
                log.debug(f"Volatility check error in price update: {e}")
            
            # 🔍 LAYER 4: Anomaly Detection (NOV 8)
            # Check for dangerous patterns (price jumps, WebSocket staleness)
            try:
                anomalies = self.anomaly_detector.run_all_checks(
                    current_price=self.current_price,
                    previous_price=self.previous_price,
                    last_ws_update=self.last_price_update
                )
                # Anomalies are logged automatically with Telegram alerts
            except Exception as e:
                log.debug(f"Anomaly detection error: {e}")
            
        except Exception as e:
            log.error(f"Error handling price update: {e}")
    
    def _fetch_price_via_rest_api(self) -> Optional[float]:
        """
        Fetch current price via REST API fallback
        
        Called when WebSocket price updates are stale (>30 seconds old).
        Uses Delta Exchange REST API to get ticker data.
        
        Returns:
            Current market price or None if fetch fails
        """
        try:
            log.warning("⚠️  WebSocket price stale - fetching via REST API fallback...")
            
            ticker_data = self.delta_client.get_ticker_by_product_id(self.product_id)
            
            # ✅ DEBUG: Log raw ticker response to diagnose $1.75 bug
            log.debug(f"📊 [DEBUG] Raw REST ticker data: {ticker_data}")
            
            if ticker_data and 'mark_price' in ticker_data:
                mark_price_raw = ticker_data['mark_price']
                log.debug(f"📊 [DEBUG] mark_price raw value: {mark_price_raw} (type: {type(mark_price_raw).__name__})")
                
                price = float(mark_price_raw)
                log.info(f"✅ REST API fallback: Got price ${price:,.2f}")
                
                # Update price tracking (simulate WebSocket update)
                self.previous_price = self.current_price
                self.current_price = price
                self.last_price_update = time.time()
                
                # ✅ FIX NOV 10: Sync market price to order manager
                self.order_mgr.update_market_price(self.current_price)
                
                return price
            else:
                log.error(f"❌ REST API returned invalid ticker data: {ticker_data}")
                return None
                
        except Exception as e:
            log.error(f"❌ REST API fallback failed: {e}")
            log.exception("Full traceback:")
            return None
    
    def _on_fill_processed(self, fill_data: Dict):
        """
        Handle processed fill
        
        ✅ NOV 8: PARTIAL FILL SUPPORT
        This is called for EACH incremental fill (not just complete orders).
        Each partial fill gets its own position and TP order immediately.
        Next grid order placed only when original order is 100% filled.
        
        Example: 100-lot order fills in 3 parts:
          Fill 1: 10 lots → Create position + TP for 10 lots
          Fill 2: 47 lots → Create position + TP for 47 lots  
          Fill 3: 43 lots → Create position + TP for 43 lots + Place next grid order
        
        🔒 CRITICAL: Uses position manager's state lock to prevent race conditions
        with reconciliation/heartbeat that could cause duplicate order placement.
        """
        # ✅ PHASE 0 FIX: Add lock acquisition logging (NOV 9)
        log.debug(f"🔒 [LOCK] Attempting to acquire state_lock (thread={threading.current_thread().name})")
        # 🔒 Acquire lock to prevent concurrent reconciliation during fill processing
        with self.position_mgr.state_lock:
            log.debug(f"🔒 [LOCK] Acquired state_lock")
            try:
                order_id = fill_data.get('order_id')
                fill_price = fill_data.get('fill_price', 0)
                fill_size = fill_data.get('fill_size', 0)  # ← INCREMENTAL size (10, 47, 43...)
                side = fill_data.get('side', '').lower()
                is_complete = fill_data.get('is_complete', False)  # ← Order 100% filled?
                cumulative = fill_data.get('cumulative_filled', 0)
                total_size = fill_data.get('total_order_size', 0)
                
                log.info(f"🎯 Processing incremental fill: {side} {fill_size} lots @ ${fill_price:,.0f} (total: {cumulative}/{total_size})")
                
                # Check if this is our pending buy (LONG mode)
                pending_buy = self.position_mgr.get_pending_buy()
                log.info(f"🔍 [FILL DEBUG] order_id={order_id}, pending_buy={pending_buy}")
                
                if pending_buy and order_id == pending_buy.get('order_id'):
                    log.info(f"✅ [FILL DEBUG] MATCH! Delegating to long_handler.handle_buy_fill()")
                    # Delegate to LONG handler
                    self.long_handler.handle_buy_fill(fill_data)
                    return
                else:
                    log.warning(f"❌ [FILL DEBUG] NO MATCH! pending_buy={pending_buy}, order_id={order_id}")
                
                # Check if this is our pending sell (SHORT mode)
                pending_sell = self.position_mgr.get_pending_sell()
                if pending_sell and order_id == pending_sell.get('order_id'):
                    # Delegate to SHORT handler
                    self.short_handler.handle_sell_fill(fill_data)
                    return
                
                # Check if TP fill
                position = self.position_mgr.find_position_by_order_id(order_id)
                if position and position.get('tp_id') == order_id:
                    # Route to correct TP handler based on position side
                    if position.get('side') == 'short':
                        self.short_handler.handle_tp_fill_short(fill_price, position)
                    else:
                        # Default to LONG mode
                        self.long_handler.handle_tp_fill(fill_price, position)
                    return
                
                # ✅ PHASE 0 FIX (NOV 9): Upgrade unknown order ID to CRITICAL + trigger reconciliation
                # If we reach here, the order_id doesn't match any tracked order
                side = fill_data.get('side', 'unknown')
                log.critical("=" * 80)
                log.critical(f"🚨 FILL FOR UNKNOWN ORDER ID - TRIGGERING RECONCILIATION")
                log.critical(f"   Order ID: {order_id}")
                log.critical(f"   Side: {side}, Size: {fill_size}, Price: ${fill_price:,.0f}")
                log.critical(f"   NOT in pending_buy, pending_sell, or open positions")
                log.critical(f"   Possible causes:")
                log.critical(f"     - Order placed manually outside bot")
                log.critical(f"     - Order from previous session (crash recovery gap)")
                log.critical(f"     - Order placed by another bot instance")
                log.critical(f"     - Reconciliation not capturing this order")
                log.critical("=" * 80)
                
                # ✅ PHASE 0 FIX (NOV 9): Trigger full reconciliation
                try:
                    log.critical("🔄 Triggering full reconciliation to sync with exchange...")
                    self.reconciler.reconcile_positions_with_exchange()
                    log.info("✅ Reconciliation completed")
                except Exception as recon_error:
                    log.error(f"❌ Reconciliation failed: {recon_error}")
                
                # Send Telegram alert for investigation
                try:
                    from bot.utils.notifier import TelegramNotifier
                    notifier = TelegramNotifier()
                    if notifier.enabled:
                        notifier.send(
                            f"⚠️ Unknown Fill Detected!\n\n"
                            f"Order: {order_id}\n"
                            f"Side: {side}\n"
                            f"Size: {fill_size}\n"
                            f"Price: ${fill_price:,.0f}\n\n"
                            f"Not tracked by bot - please investigate!"
                        )
                except Exception as e:
                    log.debug(f"Could not send Telegram alert: {e}")
                
            # 🛡️ FIX NOV 9 PHASE 2: Enhanced exception handling
            except ConnectionError as e:
                log.error(f"🌐 Connection error during fill processing: {e}")
                log.warning("   Will not requeue fill - reconciliation will sync state")
                # Don't raise - let reconciliation fix any inconsistencies
            
            except TimeoutError as e:
                log.error(f"⏱️  Timeout during fill processing: {e}")
                log.warning("   Fill may need reprocessing - adding back to queue")
                # Requeue the fill for retry
                try:
                    self.fill_detector.requeue_fill(fill_data)
                    log.info("   ✅ Fill requeued for processing")
                except Exception as requeue_error:
                    log.error(f"   ❌ Failed to requeue fill: {requeue_error}")
            
            except ValueError as e:
                log.error(f"📊 Invalid data in fill processing: {e}")
                log.error(f"   Fill data: {fill_data}")
                log.warning("   Skipping bad fill - will not requeue")
                # Don't raise or requeue - data is corrupted
            
            except Exception as e:
                log.error(f"❌ Unexpected error processing fill: {e}")
                import traceback
                log.error(traceback.format_exc())
                # Let the error propagate to main loop error tracking
                raise
            
            finally:
                # ✅ PHASE 0 FIX: Log lock release (NOV 9)
                log.debug(f"🔓 [LOCK] Releasing state_lock")
    
    # ========================================================================
    # Startup Reconciliation
    # ========================================================================
    
    def _reconcile_orphaned_orders(self):
        """
        Reconcile orphaned bot orders on startup
        
        Queries the exchange for any open BUY orders placed by the bot
        (identified by client_order_id starting with "BOT-") and adopts
        them into the pending_buy tracker.
        
        🔒 CRITICAL FIX NOV 8: Skip reconciliation if state already loaded from disk
        This prevents duplicate order placement on restart.
        
        This prevents leaving orders orphaned after bot restarts/crashes.
        """
        try:
            log.info("🔄 Reconciling orphaned orders from exchange...")
            
            # 🔒 CRITICAL CHECK: If state was already loaded from disk, verify it matches exchange
            existing_pending = None
            if self.grid_mode == 'LONG':
                existing_pending = self.position_mgr.get_pending_buy()
            else:
                existing_pending = self.position_mgr.get_pending_sell()
            
            if existing_pending:
                existing_order_id = existing_pending.get('order_id')
                existing_price = existing_pending.get('price')
                log.info(f"ℹ️  State already loaded: pending_{self.grid_mode.lower()} = {existing_order_id} @ ${existing_price:,.0f}")
                log.info(f"   Verifying this order still exists on exchange...")
                
                # Verify the loaded order still exists on exchange
                try:
                    order_check = self.delta_client.get_order(existing_order_id)
                    if order_check and order_check.get('state', '').lower() == 'open':
                        log.info(f"✅ Loaded pending order verified on exchange - no reconciliation needed")
                        return  # State is valid, skip reconciliation
                    else:
                        log.warning(f"⚠️  Loaded pending order NOT found or not open on exchange")
                        log.warning(f"   Will search for other orphaned orders...")
                        # Clear invalid state and continue reconciliation
                        if self.grid_mode == 'LONG':
                            self.position_mgr.clear_pending_buy()
                        else:
                            self.position_mgr.clear_pending_sell()
                except Exception as e:
                    log.warning(f"⚠️  Could not verify loaded pending order: {e}")
                    log.warning(f"   Continuing with reconciliation...")
            
            # Query exchange for all open orders
            orders_response = self.delta_client.list_orders(product_id=self.product_id, state="open")
            
            if not orders_response.get('success'):
                log.warning(f"⚠️ Failed to query exchange for reconciliation: {orders_response}")
                return
            
            all_orders = orders_response.get('result', [])
            
            # Determine target side based on grid mode
            target_side = 'buy' if self.grid_mode == 'LONG' else 'sell'
            
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
                return
            
            # We should only have 1 pending order at a time
            if len(bot_orders) == 1:
                order = bot_orders[0]
                order_id = str(order.get('id'))
                price = float(order.get('limit_price', 0))
                
                # Adopt into pending tracker (mode-aware)
                if self.grid_mode == 'LONG':
                    self.position_mgr.set_pending_buy({
                        'order_id': order_id,
                        'price': price,
                        'timestamp': time.time(),
                        'reconciled': True  # Mark as reconciled for tracking
                    })
                else:
                    self.position_mgr.set_pending_sell({
                        'order_id': order_id,
                        'price': price,
                        'timestamp': time.time(),
                        'reconciled': True  # Mark as reconciled for tracking
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
                if self.grid_mode == 'LONG':
                    self.position_mgr.set_pending_buy({
                        'order_id': order_id,
                        'price': price,
                        'timestamp': time.time(),
                        'reconciled': True
                    })
                else:
                    self.position_mgr.set_pending_sell({
                        'order_id': order_id,
                        'price': price,
                        'timestamp': time.time(),
                        'reconciled': True
                    })
                
                log.info(f"✅ Adopted most recent order: ID {order_id} @ ${price:,.0f}")
                
                # Cancel older orders
                for old_order in bot_orders[1:]:
                    old_id = old_order.get('id')
                    old_price = old_order.get('limit_price', 0)
                    log.info(f"🗑️ Cancelling older orphaned order: ID {old_id} @ ${old_price}")
                    self.order_mgr.cancel_order(old_id, verify=False)
                    time.sleep(0.2)  # Rate limiting
        
        except Exception as e:
            log.error(f"❌ Error during orphaned order reconciliation: {e}")
            import traceback
            log.error(traceback.format_exc())
    
    def _cleanup_stale_halt_state(self) -> None:
        """
        ✅ IMPROVEMENT #4: Clean up stale halt states on startup
        
        If the bot crashed or was stopped while halted, .volatility_halt.json remains.
        On restart, if volatility is now safe, clear the stale file to allow trading.
        
        This prevents the bot from staying unnecessarily halted after a restart.
        """
        import os
        import json
        from datetime import datetime
        
        halt_file = '.volatility_halt.json'
        
        if not os.path.exists(halt_file):
            return  # No halt file, nothing to clean
        
        try:
            # Load halt state
            with open(halt_file, 'r') as f:
                halt_state = json.load(f)
            
            if not halt_state.get('active'):
                log.debug("Halt state already inactive, skipping cleanup")
                return
            
            # Check current volatility
            from bot.volatility.iv_rv_tracker import get_volatility_tracker
            vol_tracker = get_volatility_tracker()
            
            if not vol_tracker:
                log.debug("Volatility tracker not available, skipping halt cleanup")
                return
            
            can_trade, halt_reason = vol_tracker.can_trade()
            
            if can_trade:
                # Volatility is safe but halt file exists - this is stale
                log.info("=" * 70)
                log.info("🧹 STALE HALT STATE DETECTED")
                log.info(f"   Halt was triggered in previous session")
                log.info(f"   Current volatility: SAFE (IV={vol_tracker.current_iv:.1f}%, RV={vol_tracker.current_rv:.1f}%)")
                log.info(f"   Clearing stale halt state...")
                
                # Archive the stale file
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                archive_name = f'.volatility_halt_stale_{timestamp}.json'
                os.rename(halt_file, archive_name)
                
                log.info(f"   ✅ Stale halt state archived to: {archive_name}")
                log.info(f"   ✅ Bot will resume normal trading")
                log.info("=" * 70)
            else:
                # Volatility still unsafe - keep halt state
                log.info("=" * 70)
                log.info("🌊 PREVIOUS HALT STATE STILL VALID")
                log.info(f"   Halt reason: {halt_reason}")
                log.info(f"   Bot will remain halted until volatility normalizes")
                log.info("=" * 70)
                # Ensure volatility handler knows about the halt
                self.volatility.volatility_halted = True
        
        except Exception as e:
            log.error(f"❌ Error cleaning stale halt state: {e}")
            import traceback
            log.error(traceback.format_exc())
    
    # ========================================================================
    # Main Loop
    # ========================================================================
    
    def run(self, duration_seconds: Optional[int] = None):
        """
        Run the GridBot
        
        Args:
            duration_seconds: Run for specific duration (None = run forever)
        """
        log.info("🚀 Starting GridBot...")
        
        # Track start time for shutdown notification
        self._start_time = time.time()
        
        # Send startup notification
        self._send_startup_notification()
        
        # 🔥 FIX NOV 9: Start heartbeat watchdog
        self._start_heartbeat_watchdog()
        
        # 🏥 FIX NOV 9 PHASE 3: Start health check server
        if os.getenv('ENABLE_HEALTH_CHECK', 'true').lower() == 'true':
            try:
                from bot.monitoring.health_check import HealthCheckServer
                health_port = int(os.getenv('HEALTH_CHECK_PORT', '8080'))
                self._health_server = HealthCheckServer(self, port=health_port)
                self._health_server.start()
            except Exception as e:
                log.error(f"Failed to start health check server: {e}")
        
        # Connect WebSocket
        self._ws_connect_time = time.time()  # Track connection time for REST fallback monitor
        self.ws_manager.connect()
        
        # Sync on connect
        try:
            self.reconciler.sync_on_reconnect()
        except Exception as e:
            log.warning(f"⚠️ Initial sync failed (non-fatal): {e}")
        
        # Wait for initial price
        log.info("⏳ Waiting for initial price...")
        timeout = 10
        start = time.time()
        while self.current_price is None and time.time() - start < timeout:
            time.sleep(0.5)
        
        if self.current_price:
            log.info(f"✅ Got price: ${self.current_price:,.0f}")
            # Set initial timestamp if not already set by WebSocket
            if self.last_price_update is None:
                self.last_price_update = time.time()
            # ✅ FIX NOV 10: Initialize WebSocket timestamp if we got price from WS
            if self.last_ws_price_time is None:
                self.last_ws_price_time = time.time()
        else:
            # Timeout - try REST API fallback
            log.warning("⚠️  WebSocket price timeout - trying REST API fallback...")
            self._fetch_price_via_rest_api()
            # ✅ FIX NOV 10: Initialize WebSocket timestamp even if we got price from REST
            # (to prevent immediate REST fallback activation)
            if self.last_ws_price_time is None:
                self.last_ws_price_time = time.time()
        
        if self.current_price:
            log.info(f"✅ Got price: ${self.current_price:,.0f}")
            
            # 🔄 STARTUP RECONCILIATION: Adopt orphaned bot orders from previous session
            self._reconcile_orphaned_orders()
            
            # 🧹 CLEANUP STALE HALT STATE: Clear old halt files if volatility is safe
            self._cleanup_stale_halt_state()
            
            # ================================================================
            # 🌱 SIMPLE GRID SEEDING (if enabled and no positions exist)
            # ================================================================
            positions = self.position_mgr.get_positions()
            seed_count = int(os.getenv('GRIDBOT_SEED_INITIAL_COUNT', '0'))

            if not positions and seed_count > 0:
                self.seed_missed_grid_levels(count=seed_count)
                # Seeding placed orders, they'll fill and trigger normal grid logic
                log.info("ℹ️  Grid seeding active - bot will continue normally")
                # Skip placing initial order since we just seeded multiple orders
            else:
                # ================================================================
                # NORMAL GRID STARTUP (traditional one-order-at-a-time)
                # ================================================================
                
                # 🔒 CRITICAL SAFETY CHECK: Check volatility BEFORE placing initial order
                try:
                    from bot.volatility.iv_rv_tracker import get_volatility_tracker
                    vol_tracker = get_volatility_tracker()
                    
                    log.info(f"🔍 DEBUG: vol_tracker = {vol_tracker}")
                    
                    if vol_tracker:
                        can_trade, halt_reason = vol_tracker.can_trade()
                        
                        log.info(f"🔍 DEBUG: can_trade={can_trade}, halt_reason={halt_reason}")
                        log.info(f"🔍 DEBUG: vol_tracker.is_safe={vol_tracker.is_safe}, enabled={vol_tracker.enabled}")
                        log.info(f"🔍 DEBUG: IV={vol_tracker.current_iv}, RV={vol_tracker.current_rv}")
                        
                        if not can_trade:
                            log.warning("=" * 70)
                            log.warning("🌊 VOLATILITY UNSAFE AT STARTUP")
                            log.warning(f"⚠️  Reason: {halt_reason}")
                            log.warning("⏳ Bot will NOT place initial order until volatility normalizes")
                            log.warning("🔄 Proactive monitoring enabled - will auto-place when safe")
                            log.warning("=" * 70)
                            # Don't place order, let the price update handler place it when safe
                        else:
                            # 🔒 CRITICAL CHECK: Don't place initial order if pending order already exists
                            existing_pending = None
                            if self.grid_mode == 'LONG':
                                existing_pending = self.position_mgr.get_pending_buy()
                            else:
                                existing_pending = self.position_mgr.get_pending_sell()
                            
                            if existing_pending:
                                order_id = existing_pending.get('order_id')
                                price = existing_pending.get('price')
                                log.info("=" * 70)
                                log.info(f"ℹ️  PENDING ORDER ALREADY EXISTS")
                                log.info(f"   Order ID: {order_id}")
                                log.info(f"   Price: ${price:,.0f}")
                                log.info(f"   Skipping initial order placement")
                                log.info("=" * 70)
                            else:
                                # Volatility safe - place initial BUY with Strict Grid check
                                positions = self.position_mgr.get_positions()
                                
                                # 🎯 STARTUP ONLY: Use Strict Grid to ensure MAKER order (LONG mode only)
                                # After first fill, normal grid logic resumes
                                log.info(f"🎯 Calculating initial order (Strict Grid enabled for {self.grid_mode} mode)...")
                                
                                if self.current_price:
                                    target = self.grid_calc.get_startup_maker_buy_level(
                                        current_price=self.current_price,
                                        open_positions=positions,
                                        grid_mode=self.grid_mode
                                    )
                                    
                                    if target:
                                        log.info(f"📍 Placing initial MAKER BUY @ ${target:,.0f}")
                                        log.info(f"   Current Market: ${self.current_price:,.0f}")
                                        log.info(f"   This is a ONE-TIME startup optimization")
                                        log.info(f"   After fill, normal grid logic will resume")
                                        
                                        order_id = self.order_mgr.place_buy_order(target, post_only=True)
                                        if order_id:
                                            self.position_mgr.set_pending_buy({
                                                'order_id': order_id,
                                                'price': target,
                                                'timestamp': time.time(),
                                                'strict_grid_order': True  # 🔒 Protect from reconciliation
                                            })
                                            log.info(f"✅ Initial MAKER BUY placed @ ${target:,.0f} (Volatility: SAFE)")
                                            log.info(f"🔒 Protected from reconciliation until fill")
                                    else:
                                        log.warning("⚠️ No valid MAKER BUY level available at startup")
                                        log.info(f"   Market: ${self.current_price:,.0f}")
                                        log.info(f"   Grid: ${self.grid_calc.lower:,.0f} - ${self.grid_calc.upper:,.0f}")
                                        log.info(f"   Bot will wait for market to enter grid range...")
                                else:
                                    log.warning("⚠️ Current price not available, using fallback")
                                    target = self.grid_calc.compute_next_buy_level(positions)
                                    if target:
                                        order_id = self.order_mgr.place_buy_order(target, post_only=True)
                                        if order_id:
                                            self.position_mgr.set_pending_buy({
                                                'order_id': order_id,
                                                'price': target,
                                                'timestamp': time.time()
                                            })
                                            log.info(f"✅ Initial BUY placed @ ${target:,.0f} (Volatility: SAFE)")
                    else:
                        log.warning("⚠️ Volatility tracker not available, placing order with Strict Grid check")
                        
                        # 🔒 CRITICAL CHECK: Don't place initial order if pending order already exists
                        existing_pending = None
                        if self.grid_mode == 'LONG':
                            existing_pending = self.position_mgr.get_pending_buy()
                        else:
                            existing_pending = self.position_mgr.get_pending_sell()
                        
                        if existing_pending:
                            order_id = existing_pending.get('order_id')
                            price = existing_pending.get('price')
                            log.info("=" * 70)
                            log.info(f"ℹ️  PENDING ORDER ALREADY EXISTS (Fallback Path)")
                            log.info(f"   Order ID: {order_id}")
                            log.info(f"   Price: ${price:,.0f}")
                            log.info(f"   Skipping initial order placement")
                            log.info("=" * 70)
                        else:
                            # Fallback: place order with Strict Grid anyway
                            positions = self.position_mgr.get_positions()
                            
                            if self.current_price:
                                target = self.grid_calc.get_startup_maker_buy_level(
                                    current_price=self.current_price,
                                    open_positions=positions,
                                    grid_mode=self.grid_mode
                                )
                            else:
                                log.warning("⚠️ Current price not available, using fallback")
                                target = self.grid_calc.compute_next_buy_level(positions)
                            
                            if target:
                                order_id = self.order_mgr.place_buy_order(target, post_only=True)
                                if order_id:
                                    self.position_mgr.set_pending_buy({
                                        'order_id': order_id,
                                        'price': target,
                                        'timestamp': time.time(),
                                        'strict_grid_order': True  # 🔒 Protect from reconciliation
                                    })
                except Exception as e:
                    log.error(f"❌ Error checking volatility at startup: {e}")
                    import traceback
                    log.error(traceback.format_exc())
                    
                    # 🔒 CRITICAL CHECK: Don't place initial order if pending order already exists
                    existing_pending = None
                    if self.grid_mode == 'LONG':
                        existing_pending = self.position_mgr.get_pending_buy()
                    else:
                        existing_pending = self.position_mgr.get_pending_sell()
                    
                    if existing_pending:
                        order_id = existing_pending.get('order_id')
                        price = existing_pending.get('price')
                        log.info("=" * 70)
                        log.info(f"ℹ️  PENDING ORDER ALREADY EXISTS (Exception Path)")
                        log.info(f"   Order ID: {order_id}")
                        log.info(f"   Price: ${price:,.0f}")
                        log.info(f"   Skipping initial order placement")
                        log.info("=" * 70)
                    else:
                        # Fallback: place order with Strict Grid anyway
                        positions = self.position_mgr.get_positions()
                        
                        if self.current_price:
                            target = self.grid_calc.get_startup_maker_buy_level(
                                current_price=self.current_price,
                                open_positions=positions,
                                grid_mode=self.grid_mode
                            )
                        else:
                            log.warning("⚠️ Current price not available, using fallback")
                            target = self.grid_calc.compute_next_buy_level(positions)
                        
                        if target:
                            order_id = self.order_mgr.place_buy_order(target, post_only=True)
                            if order_id:
                                self.position_mgr.set_pending_buy({
                                    'order_id': order_id,
                                    'price': target,
                                    'timestamp': time.time(),
                                    'strict_grid_order': True  # 🔒 Protect from reconciliation
                                })
        
        # 🔥 FIX NOV 9: Hardened main loop with error tracking
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        try:
            last_hb = time.time()
            elapsed = 0
            
            while True:
                try:
                    # ✅ NOV 11 FIX: Check if fill processor requested shutdown
                    if self.fill_detector.shutdown_event.is_set():
                        log.critical("🚨 Fill processor requested shutdown - halting bot")
                        self._shutdown_requested = True
                        break
                    
                    # Check shutdown
                    if self._shutdown_requested:
                        log.info("🛑 Shutdown requested")
                        break
                    
                    time.sleep(1)
                    elapsed += 1
                    
                    # Duration check
                    if duration_seconds and elapsed >= duration_seconds:
                        log.info(f"⏰ Duration {duration_seconds}s reached")
                        break
                    
                    # Heartbeat every 15s
                    if time.time() - last_hb >= 15:
                        self._heartbeat()
                        last_hb = time.time()
                        consecutive_errors = 0  # Reset on successful heartbeat
                
                except Exception as e:
                    consecutive_errors += 1
                    log.error(f"❌ Main loop error ({consecutive_errors}/{max_consecutive_errors}): {e}")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        log.critical(f"🚨 FATAL: {consecutive_errors} consecutive errors in main loop - halting bot")
                        log.critical(f"   Last error: {e}")
                        
                        # Send alert
                        try:
                            from bot.utils.notifier import TelegramNotifier
                            notifier = TelegramNotifier()
                            notifier.send(
                                f"🚨 BOT HALTED\n"
                                f"{consecutive_errors} consecutive main loop errors\n"
                                f"Last error: {e}"
                            )
                        except Exception:
                            pass
                        
                        break
                    
                    # Sleep longer after error
                    time.sleep(5)
        
        except KeyboardInterrupt:
            log.info("⚠️ Interrupted by user")
        
        finally:
            self.cleanup()
    
    def _heartbeat(self):
        """Periodic heartbeat tasks"""
        # 🔥 FIX NOV 9: Update heartbeat timestamp for watchdog
        self._last_heartbeat_time = time.time()
        
        try:
            # 🧠 FIX NOV 9 PHASE 2: Memory leak prevention
            self._check_memory_usage()
            # � FIX NOV 9: WebSocket health check
            try:
                self._check_websocket_health()
            except Exception as e:
                log.error(f"WebSocket health check failed: {e}")
            
            # �🔒 PERIODIC VOLATILITY SAFETY CHECK (backup to catch any missed transitions)
            try:
                from bot.volatility.iv_rv_tracker import get_volatility_tracker
                vol_tracker = get_volatility_tracker()
                
                if vol_tracker:
                    self.volatility.check_pending_order_safety(vol_tracker, self.current_price)
            except Exception as e:
                log.debug(f"Heartbeat volatility check error: {e}")
            
            # 📊 WRITE MONITORING SNAPSHOT (for WebUI - every 10s)
            try:
                current_time = time.time()
                if current_time - self.last_monitoring_write >= 10:
                    self.monitoring_writer.write_snapshot(self)
                    self.last_monitoring_write = current_time
            except Exception as e:
                log.debug(f"Monitoring snapshot write error: {e}")
            
            # Persist state
            self.position_mgr.persist_runtime_state()
            
            # Process TP retry queue
            pending_retries = self.position_mgr.get_pending_retries()
            for retry_entry in pending_retries:
                position = retry_entry['position']
                if self.order_mgr.safe_place_tp(position):
                    self.position_mgr.remove_from_retry_queue(retry_entry)
                else:
                    if retry_entry['attempts'] >= retry_entry['max_attempts']:
                        self.position_mgr.remove_from_retry_queue(retry_entry)
                        log.critical(f"🚨 TP retry exhausted for position ${position.get('entry_price', 0):,.0f}")
                    else:
                        self.position_mgr.update_retry_entry(retry_entry)
            
            # Enforce pending order invariant (mode-aware)
            try:
                if self.grid_mode == 'LONG':
                    self.reconciler.ensure_single_correct_pending_buy()
                else:
                    self.reconciler.ensure_single_correct_pending_sell()
            except Exception as e:
                log.warning(f"Invariant enforcement failed: {e}")
            
            # 🔄 CHECK PRICE STALENESS - Trigger REST API fallback if needed
            if self.last_price_update:
                time_since_update = time.time() - self.last_price_update
                if time_since_update > self.price_staleness_threshold:
                    log.warning(f"⚠️  Price stale for {time_since_update:.1f}s (threshold: {self.price_staleness_threshold}s)")
                    self._fetch_price_via_rest_api()
            elif self.current_price is None:
                # No price received yet - try REST API
                log.warning("⚠️  No price received from WebSocket - trying REST API...")
                self._fetch_price_via_rest_api()
            
            # 🚨 CRITICAL NOV 7: Check pending orders via REST API for missed fills
            # This ensures fills are NEVER missed even if WebSocket fails
            try:
                # Check pending BUY order (LONG mode)
                pending_buy = self.position_mgr.get_pending_buy()
                if pending_buy and pending_buy.get('order_id'):
                    # Check if this order still exists on exchange via REST API
                    order_id = pending_buy['order_id']
                    order_check = self.delta_client.get_order_by_id(order_id)
                    
                    if order_check and order_check.get('success'):
                        order_state = order_check['result'].get('state', 'unknown')
                        
                        # If order filled but we didn't catch it via WebSocket
                        if order_state == 'filled':
                            log.error(f"🚨 CRITICAL: Missed BUY fill detected via REST API!")
                            log.error(f"   Order {order_id} @ ${pending_buy.get('price')} is FILLED but not processed!")
                            
                            # Manually trigger fill processing
                            fill_data = {
                                'order_id': order_id,
                                'fill_price': pending_buy.get('price'),
                                'fill_size': order_check['result'].get('size', 1),
                                'side': order_check['result'].get('side', 'buy'),
                                'detection_source': 'heartbeat_rest_api'
                            }
                            self.fill_detector.process_websocket_fill(fill_data)
                            log.info("✅ Missed BUY fill recovered via REST API fallback!")
                            
                        elif order_state == 'cancelled':
                            log.warning(f"⚠️ Pending BUY order {order_id} was cancelled externally!")
                            self.position_mgr.clear_pending_buy()
                
                # Check pending SELL order (SHORT mode)
                pending_sell = self.position_mgr.get_pending_sell()
                if pending_sell and pending_sell.get('order_id'):
                    # Check if this order still exists on exchange via REST API
                    order_id = pending_sell['order_id']
                    order_check = self.delta_client.get_order_by_id(order_id)
                    
                    if order_check and order_check.get('success'):
                        order_state = order_check['result'].get('state', 'unknown')
                        
                        # If order filled but we didn't catch it via WebSocket
                        if order_state == 'filled':
                            log.error(f"🚨 CRITICAL: Missed SELL fill detected via REST API!")
                            log.error(f"   Order {order_id} @ ${pending_sell.get('price')} is FILLED but not processed!")
                            
                            # Manually trigger fill processing
                            fill_data = {
                                'order_id': order_id,
                                'fill_price': pending_sell.get('price'),
                                'fill_size': order_check['result'].get('size', 1),
                                'side': order_check['result'].get('side', 'sell'),
                                'detection_source': 'heartbeat_rest_api'
                            }
                            self.fill_detector.process_websocket_fill(fill_data)
                            log.info("✅ Missed SELL fill recovered via REST API fallback!")
                            
                        elif order_state == 'cancelled':
                            log.warning(f"⚠️ Pending SELL order {order_id} was cancelled externally!")
                            self.position_mgr.clear_pending_sell()
                            
            except Exception as e:
                log.debug(f"Pending order check failed (non-critical): {e}")
            
            # 🔍 LAYER 5: Predictive Decision Display (NOV 8)
            # Show what bot will do next based on price movement
            try:
                positions = self.position_mgr.get_positions()
                pending_order = (self.position_mgr.get_pending_buy() if self.grid_mode == 'LONG' 
                                else self.position_mgr.get_pending_sell())
                
                self.predictive_display.display_decision_map(
                    current_price=self.current_price,
                    grid_mode=self.grid_mode,
                    grid_step=self.grid_calc.step,
                    lower_bound=self.grid_calc.lower,
                    upper_bound=self.grid_calc.upper,
                    current_positions=len(positions),
                    max_positions=self.max_open,
                    open_tranches=positions,
                    pending_order=pending_order,
                    volatility_halted=self.volatility.volatility_halted
                )
            except Exception as e:
                log.debug(f"Predictive display error: {e}")
            
            # Log status with bid/ask
            capacity = self.position_mgr.get_capacity_status()
            
            if self.current_price:
                # Try to get bid/ask from WebSocket manager
                bid_price = None
                ask_price = None
                spread = None
                
                try:
                    ticker_data = getattr(self.ws_manager, 'ticker_data', None)
                    if ticker_data:
                        bid_price = ticker_data.get('bid')
                        ask_price = ticker_data.get('ask')
                        if bid_price and ask_price and bid_price > 0 and ask_price > 0:
                            spread = ask_price - bid_price
                except Exception as e:
                    log.debug(f"Could not fetch bid/ask: {e}")
                
                # Get pending order info
                pending_info = ""
                if self.grid_mode == 'LONG':
                    pending = self.position_mgr.get_pending_buy()
                    if pending and pending.get('price'):
                        pending_price = pending['price']
                        # Color: green if below market (good for long), red if above (shouldn't happen)
                        color = "\033[32m" if pending_price < self.current_price else "\033[31m"
                        pending_info = f" | {color}Pending BUY: ${pending_price:,.0f}\033[0m"
                else:
                    pending = self.position_mgr.get_pending_sell()
                    if pending and pending.get('price'):
                        pending_price = pending['price']
                        # Color: green if above market (good for short), red if below (shouldn't happen)
                        color = "\033[32m" if pending_price > self.current_price else "\033[31m"
                        pending_info = f" | {color}Pending SELL: ${pending_price:,.0f}\033[0m"
                
                # Format log message with bid/ask if available
                if bid_price and ask_price:
                    # Colors: cyan for positions, yellow for price, magenta for bid/ask
                    positions_str = f"\033[36m{capacity['open']}/{capacity['max_open']}\033[0m"  # Cyan
                    
                    # Price change indicator (green up, red down, white unchanged)
                    if hasattr(self, '_last_hb_price'):
                        if self.current_price > self._last_hb_price:
                            price_color = "\033[32m"  # Green up
                        elif self.current_price < self._last_hb_price:
                            price_color = "\033[31m"  # Red down
                        else:
                            price_color = "\033[37m"  # White unchanged
                    else:
                        price_color = "\033[33m"  # Yellow for first time
                    
                    log.info(f"[HB] Positions: {positions_str}, "
                            f"Price: {price_color}${self.current_price:,.0f}\033[0m | "
                            f"\033[35mBid: ${bid_price:,.1f} | Ask: ${ask_price:,.1f}\033[0m | "
                            f"Spread: ${spread:.1f}{pending_info}")
                    
                    # Store for next comparison
                    self._last_hb_price = self.current_price
                else:
                    positions_str = f"\033[36m{capacity['open']}/{capacity['max_open']}\033[0m"  # Cyan
                    log.info(f"[HB] Positions: {positions_str}, "
                            f"Price: \033[33m${self.current_price:,.0f}\033[0m{pending_info}")
            else:
                log.info("[HB] Waiting for price...")
        
        except Exception as e:
            log.error(f"Heartbeat error: {e}")
    
    def _check_websocket_health(self):
        """
        🔥 FIX NOV 9: Check WebSocket connection health
        
        Validates:
        - Price data freshness (< 120s)
        - WebSocket connection status
        """
        # Check price staleness
        if self.last_price_update:
            time_since_update = time.time() - self.last_price_update
            
            if time_since_update > 120:  # 2 minutes
                log.warning(f"⚠️ WebSocket price VERY STALE: {time_since_update:.1f}s old")
                log.warning("   Attempting REST API fallback...")
                self._fetch_price_via_rest_api()
                
                # If still no price, trigger reconnect
                if not self.current_price:
                    log.error("❌ REST API fallback failed - no current price")
            
            elif time_since_update > 30:  # 30 seconds
                log.debug(f"⚠️ WebSocket price stale: {time_since_update:.1f}s old")
        
        # Check WebSocket connection (NOV 13: Fixed to use proper is_connected property)
        try:
            if hasattr(self.ws_manager, 'is_connected'):
                if not self.ws_manager.is_connected:
                    log.warning("⚠️ WebSocket disconnected - reconnection should be automatic")
        except Exception as e:
            log.debug(f"WebSocket status check error: {e}")
    
    def _start_heartbeat_watchdog(self):
        """
        🔥 FIX NOV 9: Start watchdog thread to detect frozen heartbeat
        
        Monitors heartbeat execution and triggers shutdown if heartbeat stops
        """
        import threading
        
        def watchdog_monitor():
            log.info(f"🐕 Watchdog started (timeout: {self._watchdog_timeout}s)")
            
            while not self._shutdown_requested:
                time.sleep(10)  # Check every 10s
                
                if self._shutdown_requested:
                    break
                
                time_since_heartbeat = time.time() - self._last_heartbeat_time
                
                if time_since_heartbeat > self._watchdog_timeout:
                    log.critical("=" * 80)
                    log.critical(f"🚨 WATCHDOG TRIGGERED: Heartbeat frozen for {time_since_heartbeat:.1f}s")
                    log.critical(f"   Last heartbeat: {time_since_heartbeat:.1f}s ago")
                    log.critical(f"   Timeout threshold: {self._watchdog_timeout}s")
                    log.critical(f"   Bot appears to be frozen - triggering shutdown")
                    log.critical("=" * 80)
                    
                    # Send alert
                    try:
                        from bot.utils.notifier import TelegramNotifier
                        notifier = TelegramNotifier()
                        notifier.send(
                            f"🚨 WATCHDOG ALERT\n"
                            f"Heartbeat frozen for {time_since_heartbeat:.1f}s\n"
                            f"Bot shutting down"
                        )
                    except Exception:
                        pass
                    
                    # Trigger shutdown
                    self._shutdown_requested = True
                    break
            
            log.info("🐕 Watchdog stopped")
        
        self._watchdog_thread = threading.Thread(target=watchdog_monitor, daemon=True)
        self._watchdog_thread.start()
    
    def _check_memory_usage(self):
        """
        🧠 FIX NOV 9 PHASE 2: Memory leak prevention
        
        Monitors process memory usage and triggers garbage collection
        if thresholds are exceeded
        """
        current_time = time.time()
        
        # Only check every 5 minutes
        if current_time - self._last_memory_check < self._memory_check_interval:
            return
        
        self._last_memory_check = current_time
        
        try:
            # Get memory usage in MB
            mem_info = self._process.memory_info()
            rss_mb = mem_info.rss / 1024 / 1024  # Resident Set Size in MB
            
            log.info(f"🧠 Memory check: {rss_mb:.1f} MB used")
            
            # Critical threshold - force garbage collection
            if rss_mb > self._memory_critical_mb:
                log.warning(f"⚠️  Memory usage critical ({rss_mb:.1f} MB > {self._memory_critical_mb} MB)")
                log.warning("   Forcing garbage collection...")
                
                # Force full GC
                gc.collect()
                
                # Check again after GC
                mem_info_after = self._process.memory_info()
                rss_mb_after = mem_info_after.rss / 1024 / 1024
                freed_mb = rss_mb - rss_mb_after
                
                log.info(f"   Memory after GC: {rss_mb_after:.1f} MB (freed {freed_mb:.1f} MB)")
                
                # Send alert
                try:
                    from bot.utils.notifier import TelegramNotifier
                    notifier = TelegramNotifier()
                    notifier.send(
                        f"🧠 Memory Alert\n"
                        f"Before GC: {rss_mb:.1f} MB\n"
                        f"After GC: {rss_mb_after:.1f} MB\n"
                        f"Freed: {freed_mb:.1f} MB"
                    )
                except Exception:
                    pass
            
            # Warning threshold - log but don't force GC
            elif rss_mb > self._memory_threshold_mb:
                log.warning(f"⚠️  Memory usage high ({rss_mb:.1f} MB > {self._memory_threshold_mb} MB)")
                log.warning("   Monitoring for memory leaks...")
        
        except Exception as e:
            log.error(f"Memory check failed: {e}")
    
    # ========================================================================
    # Shutdown Management
    # ========================================================================
    
    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signals"""
        log.warning("⚠️ Shutdown signal received")
        self._shutdown_requested = True
        self.stop_event.set()  # ✅ FIX NOV 12: Signal reconciliation thread to stop
    
    def _emergency_cleanup(self):
        """Emergency cleanup via atexit - runs if process exits abnormally"""
        if not self._shutdown_requested and not getattr(self, '_cleanup_done', False):
            log.warning("⚠️ Emergency cleanup (abnormal exit)")
            self.cleanup()
    
    def _cleanup_long_mode(self):
        """
        Cleanup for LONG mode grid trading
        
        Strategy:
        - Cancel ONLY pending BUY orders (prevent new LONG positions)
        - Preserve TP SELL orders (protect existing LONG positions)
        - Do NOT disturb executed orders
        """
        log.info("📊 LONG MODE CLEANUP:")
        log.info("  ✅ Cancel pending BUY orders (prevent new positions)")
        log.info("  ✅ Preserve TP SELL orders (protect LONG positions)")
        log.info("")
        
        # 🔒 CRITICAL: Cancel ONLY the pending BUY order placed by bot
        pending_buy = self.position_mgr.get_pending_buy()
        
        if pending_buy:
            order_id = pending_buy.get('order_id')
            price = pending_buy.get('price', 0)
            log.info(f"🎯 Found pending BUY @ ${price:,.0f} (ID: {order_id})")
            
            # Use bulk cancel API (only cancels non-reduce-only orders = BUY orders in LONG mode)
            log.info("🔄 Using bulk cancel API (Delta recommendation)...")
            if self.order_mgr.cancel_all_orders_bulk(timeout=15.0):
                self.position_mgr.clear_pending_buy()
                log.info("✅ Bulk cancellation successful")
                
                log.info("🔍 Running final verification to ensure all bot BUY orders cancelled...")
                if self.order_mgr._final_verification_all_cancelled():
                    log.info("✅ Final verification passed - zero bot BUY orders remain")
                else:
                    log.critical("🚨 ALERT: Final verification found remaining bot BUY orders!")
            else:
                # Fallback to individual cancel
                log.warning("⚠️ Bulk cancel failed, trying individual cancel...")
                if self.order_mgr.cancel_order(order_id, verify=True, max_retries=3):
                    self.position_mgr.clear_pending_buy()
                    log.info("✅ Individual cancellation successful")
                else:
                    log.error("❌ Both methods failed!")
        else:
            log.warning("⚠️ No pending_buy tracked - using bulk cancel as safety check...")
            
            log.info("🔄 Running bulk cancel API...")
            if self.order_mgr.cancel_all_orders_bulk(timeout=15.0):
                log.info("✅ Bulk cancel completed")
                
                log.info("🔍 Running final verification to ensure all bot BUY orders cancelled...")
                if self.order_mgr._final_verification_all_cancelled():
                    log.info("✅ Final verification passed - zero bot BUY orders remain")
                else:
                    log.critical("🚨 ALERT: Final verification found remaining bot BUY orders!")
            else:
                log.warning("⚠️ Bulk cancel inconclusive, checking individually...")
            
            # Double-check for orphaned BUY orders
            try:
                orders_response = self.delta_client.list_orders(product_id=self.product_id, state="open")
                
                if orders_response.get('success'):
                    all_orders = orders_response.get('result', [])
                    bot_buy_orders = []
                    
                    # Find BUY orders placed by bot
                    for order in all_orders:
                        side = order.get('side', '').lower()
                        state = order.get('state', '').lower()
                        client_id = order.get('client_order_id', '')
                        is_reduce_only = order.get('reduce_only', False)
                        
                        if (state == 'open' and 
                            side == 'buy' and 
                            not is_reduce_only and 
                            client_id.startswith('BOT-')):
                            bot_buy_orders.append(order)
                    
                    if bot_buy_orders:
                        log.warning(f"🚨 Found {len(bot_buy_orders)} orphaned bot BUY orders!")
                        for order in bot_buy_orders:
                            order_id = order.get('id')
                            price = order.get('limit_price', 0)
                            log.info(f"🗑️ Cancelling orphaned BUY: ID {order_id} @ ${price}")
                            self.order_mgr.cancel_order(order_id, verify=True)
                    else:
                        log.info("✅ No orphaned bot BUY orders found")
                else:
                    log.error(f"❌ Failed to query exchange for orphaned orders")
            except Exception as e:
                log.error(f"❌ Error checking for orphaned BUY orders: {e}")
    
    def _cleanup_short_mode(self):
        """
        Cleanup for SHORT mode grid trading
        
        Strategy:
        - Cancel ONLY pending SELL orders (prevent new SHORT positions)
        - Preserve TP BUY orders (protect existing SHORT positions)
        - Do NOT disturb executed orders
        """
        log.info("📊 SHORT MODE CLEANUP:")
        log.info("  ✅ Cancel pending SELL orders (prevent new positions)")
        log.info("  ✅ Preserve TP BUY orders (protect SHORT positions)")
        log.info("")
        
        # 🔒 CRITICAL: Cancel ONLY the pending SELL order placed by bot
        pending_sell = self.position_mgr.get_pending_sell()
        
        if pending_sell:
            order_id = pending_sell.get('order_id')
            price = pending_sell.get('price', 0)
            log.info(f"🎯 Found pending SELL @ ${price:,.0f} (ID: {order_id})")
            
            # For SHORT mode: Cancel individual SELL order
            log.info("🔄 Cancelling pending SELL order...")
            if self.order_mgr.cancel_order(order_id, verify=True, max_retries=3):
                self.position_mgr.clear_pending_sell()
                log.info("✅ SELL order cancelled successfully")
            else:
                log.error("❌ Failed to cancel SELL order!")
        else:
            log.warning("⚠️ No pending_sell tracked - checking for orphaned SELL orders...")
        
        # Double-check for orphaned SELL orders
        try:
            orders_response = self.delta_client.list_orders(product_id=self.product_id, state="open")
            
            if orders_response.get('success'):
                all_orders = orders_response.get('result', [])
                bot_sell_orders = []
                
                # Find SELL orders placed by bot (not reduce-only = not TP orders)
                for order in all_orders:
                    side = order.get('side', '').lower()
                    state = order.get('state', '').lower()
                    client_id = order.get('client_order_id', '')
                    is_reduce_only = order.get('reduce_only', False)
                    
                    if (state == 'open' and 
                        side == 'sell' and 
                        not is_reduce_only and 
                        client_id.startswith('BOT-')):
                        bot_sell_orders.append(order)
                
                if bot_sell_orders:
                    log.warning(f"🚨 Found {len(bot_sell_orders)} orphaned bot SELL orders!")
                    for order in bot_sell_orders:
                        order_id = order.get('id')
                        price = order.get('limit_price', 0)
                        log.info(f"🗑️ Cancelling orphaned SELL: ID {order_id} @ ${price}")
                        self.order_mgr.cancel_order(order_id, verify=True)
                else:
                    log.info("✅ No orphaned bot SELL orders found")
            else:
                log.error(f"❌ Failed to query exchange for orphaned orders")
        except Exception as e:
            log.error(f"❌ Error checking for orphaned SELL orders: {e}")
    
    def cleanup(self):
        """Graceful cleanup - cancel pending orders (mode-aware)"""
        # Prevent double cleanup
        if getattr(self, '_cleanup_done', False):
            log.info("⚠️ Cleanup already executed, skipping")
            return
        
        self._cleanup_done = True
        
        log.info("=" * 70)
        log.info("🧹 GRACEFUL SHUTDOWN")
        log.info("=" * 70)
        log.info(f"⚙️ Grid Mode: {self.grid_mode}")
        log.info("")
        
        # Send shutdown notification
        self._send_shutdown_notification()
        
        try:
            # Execute mode-specific cleanup
            if self.grid_mode == 'LONG':
                # LONG MODE: Cancel ONLY pending BUY orders
                # Preserve TP SELL orders (protect LONG positions)
                self._cleanup_long_mode()
            elif self.grid_mode == 'SHORT':
                # SHORT MODE: Cancel ONLY pending SELL orders
                # Preserve TP BUY orders (protect SHORT positions)
                self._cleanup_short_mode()
            else:
                log.warning(f"⚠️ Unknown grid mode: {self.grid_mode}, defaulting to LONG cleanup")
                self._cleanup_long_mode()
            
            # Persist final state
            self.position_mgr.persist_runtime_state()
            log.info("✅ Final state persisted")
            
            # 🏥 FIX NOV 9 PHASE 3: Stop health check server
            if hasattr(self, '_health_server') and self._health_server:
                try:
                    self._health_server.stop()
                except Exception as e:
                    log.error(f"Error stopping health server: {e}")
            
            # Log preserved TP orders
            try:
                open_tranches = self.position_mgr.get_open_tranches()
                if open_tranches:
                    log.info("")
                    log.info("=" * 70)
                    if self.grid_mode == 'LONG':
                        log.info(f"✅ PRESERVED {len(open_tranches)} TP SELL ORDERS (Protecting LONG Positions):")
                    else:
                        log.info(f"✅ PRESERVED {len(open_tranches)} TP BUY ORDERS (Protecting SHORT Positions):")
                    log.info("=" * 70)
                    for i, tranche in enumerate(open_tranches, 1):
                        entry = tranche.get('entry_price', 0)
                        tp_price = tranche.get('tp_price', 0)
                        order_id = tranche.get('tp_order_id', 'N/A')
                        side = tranche.get('side', 'long')
                        
                        if side == 'short':
                            # SHORT position: profit when price goes down
                            profit = ((entry - tp_price) / entry * 100) if entry else 0
                        else:
                            # LONG position: profit when price goes up
                            profit = ((tp_price - entry) / entry * 100) if entry else 0
                        
                        log.info(f"   {i}. TP @ ${tp_price:,.1f} (entry: ${entry:,.1f}, +{profit:.2f}%) - Order ID: {order_id}")
                    log.info("=" * 70)
                    log.info("⚠️ IMPORTANT: These TP orders were NOT cancelled - they protect your positions!")
                    log.info("=" * 70)
                    log.info("")
                else:
                    log.info("")
                    log.info("📍 No open positions with TP orders")
                    log.info("")
            except Exception as e:
                log.warning(f"⚠️ Could not log preserved TP orders: {e}")
            
            # Clear fill cache
            self.fill_detector.clear_processed_fills()
            
            # ✅ NOV 8: Stop fill processing queue gracefully
            log.info("🛑 Stopping fill processor...")
            self.fill_detector.stop_processing()
            
            # Log queue statistics
            queue_stats = self.fill_detector.get_queue_stats()
            log.info(f"📊 Fill Queue Stats: {queue_stats}")
            
            # Disconnect WebSocket
            self.ws_manager.disconnect()
            log.info("✅ WebSocket disconnected")
        
        except Exception as e:
            log.error(f"❌ Cleanup error: {e}")
        
        log.info("=" * 70)
        log.info("✅ GridBot stopped")
        log.info("=" * 70)


# ========================================================================
# Entry Point (Backward Compatible)
# ========================================================================

def run_grid_strategy(dc, symbol: str, lower: float, upper: float, step: float,
                      ref: float, lot, max_open: int = 5, hb_sec: int = 10):
    """
    Entry point for GridBot (backward compatible with old interface)
    
    This matches the old GridBotWebSocket signature but uses new architecture.
    """
    api_key = os.getenv('DELTA_API_KEY')
    api_secret = os.getenv('DELTA_API_SECRET')
    
    if not api_key or not api_secret:
        raise RuntimeError("❌ API credentials not found!")
    
    # Convert lot to int
    lot = int(float(lot))
    
    # Convert symbol format if needed
    if '/' in symbol:
        parts = symbol.split('/')
        if len(parts) == 2:
            base = parts[0]
            quote = parts[1].split(':')[0]
            symbol = base + quote
    
    try:
        bot = GridBot(
            api_key=api_key,
            api_secret=api_secret,
            symbol=symbol,
            lower=lower,
            upper=upper,
            step=step,
            ref=ref,
            lot=lot,
            max_open=max_open,
            hb_sec=hb_sec
        )
        
        bot.run(duration_seconds=None)
    
    except Exception as e:
        log.critical(f"GridBot failed: {e}")
        raise
