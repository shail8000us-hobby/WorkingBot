"""
Async GridBot - Main async bot implementation.
Single event loop with actors and saga pattern.
"""

import asyncio
import json
import os
import sys
import signal
import time
import hashlib
from collections import deque
from typing import Dict, Any, Optional, List, Set
from pathlib import Path

import aiofiles

from loguru import logger as log

# Add project root to path for config imports BEFORE any config imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Human-readable logging for traders
from bot.utils.human_logger import human_log

# YAML Configuration System (bot/config renamed to bot/legacy_config to avoid conflict)
from config.loader import get_config
from config.models import RootConfig

from bot.api.unified_api_client import UnifiedAPIClient
from bot.strategy.actors.position_actor import PositionManagerActor
from bot.strategy.actors.order_actor import OrderManagerActor
# VolatilityMonitor REMOVED - Guardian monitors volatility now
from bot.strategy.sagas.saga_coordinator import SagaOrchestrator
from bot.strategy.sagas.fill_processing_saga import (
    create_buy_fill_saga,
    create_sell_fill_saga,
    create_short_entry_saga,
    create_short_tp_saga,
)
from bot.strategy.sagas.position_closing_saga import create_emergency_close_all_saga
from bot.strategy.modules.event_store import EventStore, EventType
from bot.strategy.modules.guardian_handler import GuardianHandler
from bot.strategy.modules.health_monitor import HealthMonitor
from bot.strategy.modules.exchange_sync import ExchangeSync
from bot.strategy.modules.ws_lifecycle import WSLifecycle
from bot.strategy.modules.fill_processor import FillProcessor
from bot.strategy.modules.grid_calculator import GridCalculator
from bot.strategy.modules.mode_state_manager import get_mode_state_manager
from bot.strategy.actors.base_actor import Message

# Recovery System Integration (NOV 20)
from bot.strategy.recovery import StartupRecoveryEngine, GuardianRecoveryEngine, RecoveryStatus

# NOV 13: Comprehensive Monitoring Systems (5 layers of protection)
from bot.monitoring import (
    PriceHealthMonitor,
    PreOrderDecisionLogger,
    TPVerificationSystem,
    AnomalyDetectionSystem,
    PredictiveDecisionDisplay,
)
from bot.monitoring.data_writer import MonitoringDataWriter

# DEC 23: Fill Monitor for exchange maintenance scenarios
from bot.strategy.monitors.fill_monitor import FillMonitor


def _configure_logging():
    """
    Configure loguru logging for PM2 compatibility.
    
    When running under PM2, PM2 adds its own timestamps, so we remove
    loguru timestamps to avoid duplication.
    """
    # Check if running under PM2
    # PM2 sets these environment variables when running processes
    is_pm2 = (
        os.getenv('pm_id') is not None or 
        os.getenv('PM2_HOME') is not None or
        os.getenv('PM2_JSON_PROCESSING') is not None
    )
    
    # Remove default handler
    log.remove()
    
    if is_pm2:
        # Running under PM2 - use format WITHOUT timestamp (PM2 adds it)
        log.add(
            sys.stderr,
            format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO",  # Default level INFO to reduce verbosity
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
        log.info(f"✅ Logging configured for PM2 (no timestamps in output)")
    else:
        # Running standalone - include timestamp
        log.add(
            sys.stderr,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="DEBUG",  # More verbose when running standalone
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
        log.info(f"✅ Logging configured for standalone (with timestamps)")
    
    # Add file handler for detailed logs (always with timestamp)
    log_dir = Path("bot/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log.add(
        log_dir / "gridbot_detailed.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="100 MB",
        retention="7 days",
        compression="zip",
        enqueue=True,
    )


# Configure logging immediately at module load time
_configure_logging()


class AsyncGridBot:
    """
    Async GridBot with actor model and saga pattern.
    
    Features:
    - Single asyncio event loop (no threads)
    - Actor-based state management (no locks)
    - Saga pattern for transactional safety
    - Automatic reconnection
    
    V6.0 MULTI-INSTANCE ARCHITECTURE:
    - Instance = Symbol + Mode (e.g., BTCUSD_LONG, BTCUSD_SHORT)
    - Each instance gets its own database: bot_events_BTCUSD_LONG.db
    - LONG and SHORT can run simultaneously on the same symbol
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        config: Optional[RootConfig] = None,
        instance_name: Optional[str] = None,  # V6.0: Instance-centric (preferred)
        symbol_name: Optional[str] = None,    # V5.0: Multi-symbol (legacy)
        # Backward compatibility: allow manual params
        symbol: Optional[str] = None,
        product_id: Optional[int] = None,
        mode: Optional[str] = None,
        lower_price: Optional[float] = None,
        upper_price: Optional[float] = None,
        grid_step: Optional[float] = None,
        ref_price: Optional[float] = None,
        tp_offset: Optional[float] = None,
        max_positions: Optional[int] = None,
        lot_size: Optional[float] = None,
        testnet: Optional[bool] = None,
        # Safety parameters REMOVED - Guardian monitors all risk
        # Order management parameters
        tag_prefix: Optional[str] = None,
        post_only_mode: Optional[str] = None,
        cancel_all_on_start: Optional[bool] = None,
        cancel_scope: Optional[str] = None,
        adopt_untagged: Optional[bool] = None,
        # Grid behavior parameters
        strict_grid: Optional[bool] = None,
        strict_start: Optional[bool] = None,
        seed_initial_count: Optional[int] = None,
        smart_gap_fill: Optional[bool] = None,
        rung_snap_mode: Optional[str] = None,
        # Timing parameters
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        cooldown_seconds: Optional[int] = None,
        # Conversion rate
        usd_to_inr_rate: Optional[float] = None
    ):
        """
        Initialize async grid bot with YAML configuration.
        
        V6.0 ARCHITECTURE: Instance = Symbol + Mode
        
        Args:
            api_key: Delta Exchange API key (if None, reads from ENV)
            api_secret: Delta Exchange API secret (if None, reads from ENV)
            config: RootConfig object (if None, loads from config.yaml)
            instance_name: Instance key from config.instances (v6.0+) e.g., 'BTCUSD_LONG'
            symbol_name: Symbol key from config.symbols (v5.0+) e.g., 'BTCUSD', 'ETHUSD'
            
            All other params: Optional overrides for YAML config
            If not provided, values are loaded from config.yaml
        """
        # Load YAML config (or use provided config)
        if config is None:
            config = get_config()
        
        self.config = config
        
        # V6.0: Multi-instance support (Instance = Symbol + Mode)
        if instance_name:
            from config.loader import get_instance_config
            
            instance_config = get_instance_config(instance_name)
            if not instance_config:
                available = list(config.instances.keys()) if config.instances else []
                raise ValueError(
                    f"Instance '{instance_name}' not found or disabled in config.yaml\n"
                    f"Available instances: {available}"
                )
            
            # Set instance-specific attributes
            self.instance_name = instance_name
            self.symbol_name = instance_config.symbol
            self.symbol = instance_config.symbol
            self.product_id = instance_config.product_id
            self.mode = instance_config.mode.value
            self.lower_price = instance_config.grid.geometry.lower
            self.upper_price = instance_config.grid.geometry.upper
            self.grid_step = instance_config.grid.geometry.step
            self.ref_price = instance_config.grid.geometry.reference
            self.max_positions = instance_config.grid.limits.max_open_positions
            self.lot_size = instance_config.grid.limits.lot_size
            self.max_qty_per_order = instance_config.grid.limits.max_qty_per_order
            self.strict_grid = instance_config.grid.behavior.strict_grid
            self.rung_snap_mode = instance_config.grid.behavior.rung_snap_mode
            self.seed_initial_count = instance_config.grid.behavior.seed_initial_count
            
            # Instance-specific safety limits
            self.max_account_loss_inr_display = instance_config.safety.max_account_loss_inr
            self.min_liq_distance_pct_display = instance_config.safety.min_liquidation_distance_pct
            
            # Instance RSI config (for logging)
            self.rsi_config = instance_config.get_rsi_config()
            
            # Smart gap fill
            if instance_config.grid.smart_gap_fill:
                self.smart_gap_fill = instance_config.grid.smart_gap_fill.enabled
            else:
                self.smart_gap_fill = False
            
            log.info(f"🎯 Initialized bot for {instance_name} (v6.0 multi-instance)")
            log.info(f"   Symbol: {self.symbol}, Mode: {self.mode}")
            log.info(f"   Product ID: {self.product_id}")
            log.info(f"   Grid: {self.lower_price}-{self.upper_price}, step {self.grid_step}")
            log.info(f"   RSI: stop={self.rsi_config.stop_threshold}, resume={self.rsi_config.resume_threshold}")
            
        elif symbol_name and hasattr(config, 'instances') and config.instances:
            # V6.0: Find instance for this symbol (when symbol_name provided but not instance_name)
            # This allows backward compat: `python async_gridbot.py BTCUSD` finds BTCUSD_LONG automatically
            matching_instance = None
            matching_instance_name = None
            
            for inst_name, inst_config in config.instances.items():
                if inst_config.symbol == symbol_name:
                    matching_instance = inst_config
                    matching_instance_name = inst_name
                    break
            
            if not matching_instance:
                available = sorted(set(inst.symbol for inst in config.instances.values()))
                raise ValueError(
                    f"Symbol '{symbol_name}' not found in any instance in config.yaml\n"
                    f"Available symbols: {available}"
                )
            
            from config.loader import get_instance_config
            instance_config = get_instance_config(matching_instance_name)
            
            # Set instance-specific attributes
            self.instance_name = matching_instance_name
            self.symbol_name = instance_config.symbol
            self.symbol = instance_config.symbol
            self.product_id = instance_config.product_id
            self.mode = instance_config.mode.value
            self.lower_price = instance_config.grid.geometry.lower
            self.upper_price = instance_config.grid.geometry.upper
            self.grid_step = instance_config.grid.geometry.step
            self.ref_price = instance_config.grid.geometry.reference
            self.max_positions = instance_config.grid.limits.max_open_positions
            self.lot_size = instance_config.grid.limits.lot_size
            self.max_qty_per_order = instance_config.grid.limits.max_qty_per_order
            self.strict_grid = instance_config.grid.behavior.strict_grid
            self.rung_snap_mode = instance_config.grid.behavior.rung_snap_mode
            self.seed_initial_count = instance_config.grid.behavior.seed_initial_count
            
            # Instance-specific safety limits
            self.max_account_loss_inr_display = instance_config.safety.max_account_loss_inr
            self.min_liq_distance_pct_display = instance_config.safety.min_liquidation_distance_pct
            
            # Instance RSI config (for logging)
            self.rsi_config = instance_config.get_rsi_config()
            
            # Smart gap fill
            if instance_config.grid.smart_gap_fill:
                self.smart_gap_fill = instance_config.grid.smart_gap_fill.enabled
            else:
                self.smart_gap_fill = False
            
            log.info(f"🎯 Initialized bot for {symbol_name} → {matching_instance_name} (v6.0 symbol→instance lookup)")
            log.info(f"   Symbol: {self.symbol}, Mode: {self.mode}")
            log.info(f"   Product ID: {self.product_id}")
            log.info(f"   Grid: {self.lower_price}-{self.upper_price}, step {self.grid_step}")
            log.info(f"   RSI: stop={self.rsi_config.stop_threshold}, resume={self.rsi_config.resume_threshold}")
            
        elif symbol_name and config.symbols:
            # V5.0: Multi-symbol mode (backward compat)
            if symbol_name not in config.symbols:
                available = list(config.symbols.keys())
                raise ValueError(
                    f"Symbol '{symbol_name}' not found in config.yaml\n"
                    f"Available symbols: {available}"
                )
            
            symbol_config = config.symbols[symbol_name]
            
            # Check if symbol is enabled
            if not symbol_config.enabled:
                raise ValueError(
                    f"Symbol '{symbol_name}' is disabled in config.yaml\n"
                    f"Set symbols.{symbol_name}.enabled=true to enable it"
                )
            
            # Set symbol-specific attributes
            self.instance_name = f"{symbol_name}_{symbol_config.mode.value}"  # v6.0 compat
            self.symbol_name = symbol_name
            self.symbol = symbol_name
            self.product_id = symbol_config.product_id
            self.mode = symbol_config.mode.value
            self.lower_price = symbol_config.grid.geometry.lower
            self.upper_price = symbol_config.grid.geometry.upper
            self.grid_step = symbol_config.grid.geometry.step
            self.ref_price = symbol_config.grid.geometry.reference
            self.max_positions = symbol_config.grid.limits.max_open_positions
            self.lot_size = symbol_config.grid.limits.lot_size
            self.max_qty_per_order = symbol_config.grid.limits.max_qty_per_order
            self.strict_grid = symbol_config.grid.behavior.strict_grid
            self.rung_snap_mode = symbol_config.grid.behavior.rung_snap_mode
            self.seed_initial_count = symbol_config.grid.behavior.seed_initial_count
            
            # Symbol-specific safety limits (for display)
            self.max_account_loss_inr_display = symbol_config.safety.max_account_loss_inr
            self.min_liq_distance_pct_display = symbol_config.safety.min_liquidation_distance_pct
            
            # Smart gap fill
            if symbol_config.grid.smart_gap_fill:
                self.smart_gap_fill = symbol_config.grid.smart_gap_fill.enabled
            else:
                self.smart_gap_fill = False
            
            log.info(f"🎯 Initialized bot for {symbol_name} (v5.0 multi-symbol)")
            log.info(f"   Product ID: {self.product_id}")
            log.info(f"   Mode: {self.mode}")
            log.info(f"   Grid: {self.lower_price}-{self.upper_price}, step {self.grid_step}")
            
        else:
            # V4.0: Backward compatibility - single symbol mode
            if not config.bot:
                raise ValueError(
                    f"Either symbol_name (v5.0) or config.bot (v4.0) must be provided\n"
                    f"To use multi-symbol, run: python async_gridbot.py <SYMBOL>"
                )
            
            self.symbol_name = config.bot.symbol  # For v4.0, symbol_name = symbol
            self.symbol = symbol or config.bot.symbol
            self.product_id = product_id or 27  # Default product ID
            self.mode = mode or config.bot.mode
            self.instance_name = f"{self.symbol}_{self.mode}"  # v6.0 compat
            self.lower_price = lower_price or config.grid.geometry.lower
            self.upper_price = upper_price or config.grid.geometry.upper
            self.grid_step = grid_step or config.grid.geometry.step
            self.ref_price = ref_price or config.grid.geometry.reference
            self.max_positions = max_positions or config.grid.limits.max_open_positions
            self.lot_size = lot_size or config.grid.limits.lot_size
            self.strict_grid = strict_grid if strict_grid is not None else config.grid.behavior.strict_grid
            self.seed_initial_count = seed_initial_count or config.grid.behavior.seed_initial_count
            self.smart_gap_fill = smart_gap_fill if smart_gap_fill is not None else config.grid.smart_gap_fill.enabled
            self.rung_snap_mode = rung_snap_mode or config.grid.behavior.rung_snap_mode
            
            log.info(f"🎯 Initialized bot for {self.instance_name} (v4.0 single-symbol mode)")
        
        # API credentials - load from centralized config loader if not provided
        if api_key and api_secret:
            self.api_key = api_key
            self.api_secret = api_secret
        else:
            from config.loader import get_api_credentials
            credentials = get_api_credentials(config.trading_mode)
            self.api_key = credentials['api_key']
            self.api_secret = credentials['api_secret']
        
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials must be provided or set in secrets/api_keys.env")
        
        # Common parameters (same for v4.0 and v5.0)
        self.testnet = testnet if testnet is not None else (config.trading_mode == 'demo')
        self.tp_offset = tp_offset or 500  # Default TP offset
        
        # Safety parameters REMOVED - Guardian monitors all risk (loss, volatility, liquidation, position size)
        # Trading bot only reads Guardian's GO/STOP signal from SQL
        self.usd_to_inr_rate = usd_to_inr_rate or config.guardian.usd_to_inr_rate
        
        # Order management parameters
        self.tag_prefix = tag_prefix or "GBOT_"
        self.post_only_mode = post_only_mode or "auto"
        self.cancel_all_on_start = cancel_all_on_start if cancel_all_on_start is not None else False
        self.cancel_scope = cancel_scope or "tagged"
        self.adopt_untagged = adopt_untagged if adopt_untagged is not None else False
        
        # Grid behavior parameters (if not set above)
        self.strict_start = strict_start if strict_start is not None else True
        
        # Timing parameters
        self.max_retries = max_retries or config.order_execution.max_retries
        self.retry_delay = retry_delay or config.order_execution.retry_delay
        self.cooldown_seconds = cooldown_seconds or config.order_execution.cooldown_seconds
        
        # Safety state (minimal - Guardian handles most safety)
        # These are kept for status display only, not for checking
        self._account_loss_inr = 0.0  # For display in status endpoint
        self._last_order_time = 0
        self._last_safety_check_time = 0  # For periodic safety gatekeeper
        
        # Log rate limiter - track last log time for frequently occurring messages
        self._log_rate_limiter: Dict[str, float] = {}
        
        log.info("=" * 80)
        log.info("ASYNC GRIDBOT - YAML CONFIGURATION LOADED")
        log.info("=" * 80)
        log.info(f"Config Version: {config.version}")
        log.info(f"Trading Mode: {config.trading_mode.upper()}")
        log.info(f"Symbol: {self.symbol}")
        log.info(f"Product ID: {self.product_id}")
        log.info(f"Mode: {self.mode}")
        log.info(f"Grid Lower: ${self.lower_price:,.2f}")
        log.info(f"Grid Upper: ${self.upper_price:,.2f}")
        log.info(f"Grid Step: ${self.grid_step:,.2f}")
        log.info(f"TP Offset: ${self.tp_offset:,.2f}")
        log.info(f"Max Positions: {self.max_positions}")
        log.info(f"Testnet: {self.testnet}")
        log.info("")
        log.info("SAFETY FEATURES:")
        log.info(f"  Guardian Bot: Monitors all risk (volatility, loss, position, liquidation)")
        log.info("")
        log.info("ORDER MANAGEMENT:")
        log.info(f"  Tag Prefix: {self.tag_prefix}")
        log.info(f"  Post-Only Mode: {self.post_only_mode}")
        log.info(f"  Cancel on Start: {self.cancel_all_on_start}")
        log.info("")
        log.info("GRID BEHAVIOR:")
        log.info(f"  Strict Grid: {self.strict_grid}")
        log.info(f"  Strict Start: {self.strict_start}")
        log.info(f"  Initial Seed: {self.seed_initial_count}")
        log.info(f"  Smart Gap Fill: {self.smart_gap_fill}")
        log.info("=" * 80)
        
        # Initialize event store - Instance-specific database (v6.0)
        # Uses instance_name (e.g., BTCUSD_LONG) for unique database per instance
        db_name = f"data/bot_events_{self.instance_name}.db"
        self.event_store = EventStore(db_name)
        log.info(f"📊 Event Store: {db_name}")
        
        # NOV 20: Initialize Unified API Client (WebSocket PRIMARY + REST fallback)
        # CRITICAL FIX: WebSocket is PRIMARY (require_websocket=True)
        self.api_client = UnifiedAPIClient(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=testnet,
            enable_websocket=True,
            symbol=self.symbol,
            product_id=self.product_id,
            require_websocket=True  # CRITICAL: WebSocket is mandatory for trading bot
        )
        
        log.info(f"✅ Unified API Client initialized (WebSocket + REST with fallback)")
        
        # Initialize actors - CRITICAL: Use instance variables
        self.position_actor = PositionManagerActor(
            event_store=self.event_store,
            max_positions=self.max_positions
        )
        
        log.info(f"Position Actor initialized with max_positions={self.max_positions}")
        
        self.order_actor = OrderManagerActor(
            api_client=self.api_client.rest_client,  # OrderActor uses REST client
            event_store=self.event_store,
            symbol=self.symbol,
            product_id=self.product_id,
            max_retries=self.max_retries,
            tag_prefix=self.tag_prefix,
            post_only_mode=self.post_only_mode
        )
        
        log.info(f"Order Actor initialized for {self.symbol} (Product ID: {self.product_id})")
        
        # VolatilityMonitor initialization REMOVED - Guardian monitors volatility
        # WebSocket manager is now part of UnifiedAPIClient
        
        # Initialize saga orchestrator
        self.saga_orchestrator = SagaOrchestrator(
            event_store=self.event_store,
            max_concurrent_sagas=10
        )
        
        # Grid calculator - CRITICAL: Use instance variables, not hardcoded values
        self.grid_calc = GridCalculator(
            lower=self.lower_price,
            upper=self.upper_price,
            step=self.grid_step,
            ref=self.ref_price,
            tick_size=0.5  # BTC tick size
        )
        
        log.info(f"Grid Calculator initialized: {self.lower_price} to {self.upper_price}, step {self.grid_step}, ref {self.ref_price}")
        
        # Bot state
        self._running = False
        self._started_once = False  # Distinguishes startup (not yet running) from shutdown (was running)
        self._tasks: List[asyncio.Task] = []
        # current_price, _last_price, _last_price_update → owned by WSLifecycle (P4)
        self._initial_order_placed = False
        self._price_stale_threshold = 10  # seconds
        self._order_placement_lock = None  # Created in start() within event loop
        
        # Guardian signal state now owned by self.guardian (GuardianHandler)
        
        # Metrics
        self._start_time = 0
        self._fills_processed = 0
        self._sagas_completed = 0
        self._sagas_failed = 0
        
        # Reconciliation state
        self._last_reconciliation = 0
        self._reconciliation_interval = 300  # 5 minutes
        self._reconciliation_initial_delay = 60  # 1 minute initial delay
        self._reconciliation_errors = 0
        
        # Recovery state (NOV 20) - Symbol-specific (v5.0)
        self._recovery_state = None
        self._recovered_grids = set()  # Grid levels that were recovered
        self._recovery_state_file = Path(f"data/recovery/recovery_state_{self.symbol_name}_{self.mode}.json")
        
        # ========================================================================
        # JAN 29 2026: Initialize Recovery Engines (FIX)
        # ========================================================================
        log.info("🔄 Initializing Recovery Engines...")
        self.startup_recovery = StartupRecoveryEngine(
            bot=self,
            config=config,
            logger=log
        )
        self.guardian_recovery = GuardianRecoveryEngine(
            bot=self,
            config=config,
            logger=log
        )
        log.info("✅ Recovery engines initialized (StartupRecovery + GuardianRecovery)")
        
        # REST API Fallback state → MOVED to WSLifecycle (P4)
        
        # ========================================================================
        # NOV 13: Comprehensive Monitoring Systems (5 Layers of Protection)
        # ========================================================================
        
        log.info("🔍 Initializing Comprehensive Monitoring Systems...")
        
        # Layer 1: Price Health Monitor (prevent stale price orders)
        log.info("   ├─ Layer 1: Price Health Monitor")
        self.price_monitor = PriceHealthMonitor(
            stale_threshold=35.0,      # Warn if price >35s old (Delta heartbeat is 30s)
            critical_threshold=60.0    # Critical if >60s old
        )
        
        # Layer 2: Pre-Order Decision Logger (transparency)
        log.info("   ├─ Layer 2: Pre-Order Decision Logger")
        self.pre_order_logger = PreOrderDecisionLogger()
        
        # Layer 3: TP Verification System (orphan detection)
        log.info("   ├─ Layer 3: TP Verification System")
        self.tp_verifier = TPVerificationSystem(
            delta_client=self.api_client
        )
        
        # Layer 4: Anomaly Detection System (pattern detection)
        log.info("   ├─ Layer 4: Anomaly Detection System")
        self.anomaly_detector = AnomalyDetectionSystem()
        
        # Layer 5: Predictive Decision Display (show next actions)
        log.info("   ├─ Layer 5: Predictive Decision Display")
        self.predictive_display = PredictiveDecisionDisplay()
        
        # Monitoring Data Writer (WebUI integration)
        log.info("   └─ Monitoring Data Writer (WebUI integration)")
        self.monitoring_writer = MonitoringDataWriter()
        self._last_monitoring_write = 0  # Track last write time
        
        log.info("✅ All monitoring systems initialized (5 layers + WebUI writer)")
        
        # ========================================================================
        # DEC 23: Fill Monitor (Exchange Maintenance & Missed Fill Protection)
        # ========================================================================
        
        log.info("🔍 Initializing Fill Monitor (exchange maintenance protection)...")
        self.fill_monitor = FillMonitor(
            api_client=self.api_client.rest_client,  # Use REST client
            event_store=self.event_store,
            product_id=self.product_id,
            check_interval=30,  # Check every 30 seconds
            verification_delay=5,  # Start checking 5 seconds after placement
            max_age=86400,  # Keep orders for 24 hours
            missed_fill_callback=self._process_missed_fill
        )
        log.info("✅ Fill Monitor initialized (30s check interval, 5s initial delay)")
        
        # ========================================================================
        # NOV 17: Volatility tracking REMOVED - Guardian handles this now
        # ========================================================================
        # Guardian monitors IV, RV, spreads and publishes GO/STOP signals
        # Trading bot reads Guardian signal from database (no duplicate checks)
        
        # ========================================================================
        # NOV 13: Event Loop Watchdog (Frozen Loop Detection)
        # ========================================================================
        
        self._last_heartbeat_time = time.time()
        self._watchdog_timeout = 60.0
        self._watchdog_check_interval = 10.0
        self._max_reconciliation_errors = 10
        
        self._seen_fill_ids: Set[str] = set()
        self._fill_id_timestamps: deque = deque(maxlen=1000)
        self._fill_id_cleanup_interval = 300
        self._last_fill_id_cleanup = time.time()
        
        self._last_accepted_order_price: Optional[float] = None
        self._min_price_move_threshold = self.grid_step / 2
        
        self.STATE_VERSION = "1.0"
    
    # Guardian state (transitions, missed orders) now owned by GuardianHandler

        # Phase 1: GuardianHandler module
        self.guardian = GuardianHandler(
            event_store=self.event_store,
            position_actor=self.position_actor,
            order_actor=self.order_actor,
            grid_calc=self.grid_calc,
            mode=self.mode,
            grid_step=self.grid_step,
            max_positions=self.max_positions,
            lot_size=self.lot_size,
            ref_price=self.ref_price,
            should_log_fn=self._should_log,
        )

        # Phase 3: ExchangeSync module
        self.exchange_sync = ExchangeSync(
            api_client=self.api_client,
            position_actor=self.position_actor,
            order_actor=self.order_actor,
            event_store=self.event_store,
            grid_calc=self.grid_calc,
            mode=self.mode,
            symbol=self.symbol,
            product_id=self.product_id,
            grid_step=self.grid_step,
            lot_size=self.lot_size,
            max_positions=self.max_positions,
            tp_offset=self.tp_offset,
            should_log_fn=self._should_log,
        )

        # Phase 2: HealthMonitor module
        self.health_monitor = HealthMonitor(
            position_actor=self.position_actor,
            order_actor=self.order_actor,
            saga_orchestrator=self.saga_orchestrator,
            api_client=self.api_client,
            grid_calc=self.grid_calc,
            price_monitor=self.price_monitor,
            fill_monitor=self.fill_monitor,
            mode=self.mode,
            symbol=self.symbol,
            symbol_name=self.symbol_name,
            max_positions=self.max_positions,
            instance_name=self.instance_name,
            config=self.config,
            should_log_fn=self._should_log,
        )

        # Phase 4: WSLifecycle module
        self.ws_lifecycle = WSLifecycle(
            api_client=self.api_client,
            position_actor=self.position_actor,
            price_monitor=self.price_monitor,
            mode=self.mode,
            symbol=self.symbol,
            product_id=self.product_id,
            max_positions=self.max_positions,
            should_log_fn=self._should_log,
            config=self.config,
        )

        # Phase 5: FillProcessor module
        self.fill_processor = FillProcessor(
            position_actor=self.position_actor,
            order_actor=self.order_actor,
            saga_orchestrator=self.saga_orchestrator,
            grid_calc=self.grid_calc,
            event_store=self.event_store,
            fill_monitor=self.fill_monitor,
            pre_order_logger=self.pre_order_logger,
            anomaly_detector=self.anomaly_detector,
            mode=self.mode,
            product_id=self.product_id,
            lot_size=self.lot_size,
            max_positions=self.max_positions,
            tp_offset=self.tp_offset,
            symbol=self.symbol,
        )

    # ── Property proxies for WSLifecycle-owned state (P4) ─────────────

    @property
    def current_price(self):
        return self.ws_lifecycle.current_price

    @current_price.setter
    def current_price(self, value):
        self.ws_lifecycle.current_price = value

    @property
    def _last_price(self):
        return self.ws_lifecycle._last_price

    @_last_price.setter
    def _last_price(self, value):
        self.ws_lifecycle._last_price = value

    @property
    def _last_price_update(self):
        return self.ws_lifecycle._last_price_update

    @_last_price_update.setter
    def _last_price_update(self, value):
        self.ws_lifecycle._last_price_update = value

    @property
    def _rest_fallback_active(self):
        return self.ws_lifecycle._rest_fallback_active

    @_rest_fallback_active.setter
    def _rest_fallback_active(self, value):
        self.ws_lifecycle._rest_fallback_active = value

    def _should_log(self, log_key: str, interval_seconds: float = 60.0) -> bool:
        """
        Rate limiter for frequent log messages.
        
        Args:
            log_key: Unique identifier for this log message
            interval_seconds: Minimum seconds between logs (default 60s)
            
        Returns:
            True if enough time has passed since last log, False otherwise
        """
        current_time = time.time()
        last_time = self._log_rate_limiter.get(log_key, 0)
        
        if current_time - last_time >= interval_seconds:
            self._log_rate_limiter[log_key] = current_time
            return True
        return False
    
    def _is_cooldown_ready(self) -> bool:
        """
        Check if cooldown period has elapsed since last order.
        
        Returns:
            True if ready to place order, False if in cooldown
        """
        if self.cooldown_seconds <= 0:
            return True
        
        elapsed = time.time() - self._last_order_time
        if elapsed < self.cooldown_seconds:
            remaining = self.cooldown_seconds - elapsed
            log.debug(f"Cooldown active: {remaining:.1f}s remaining")
            return False
        
        return True
    
    # _read_guardian_signal — MOVED to GuardianHandler.read_signal() (P1.2)

    async def _comprehensive_safety_check(self, context: str = "order placement") -> tuple[bool, str]:
        """
        Comprehensive safety check - validates ALL safety mechanisms.
        
        Args:
            context: What action is being checked (for logging)
            
        Returns:
            (can_proceed, reason) - True if safe, False with reason if blocked
        """
        # 0. Early exit: Skip all checks if bot is already shutting down
        # JAN 27, 2026: Prevents Guardian signal errors during graceful shutdown
        if not self._running:
            return False, "Bot is shutting down"
        
        # 1. Check Guardian GO/STOP signal
        signal, reason = await self.guardian.read_signal()
        if signal == 'STOP':
            halt_reason = (
                f"🛑 GUARDIAN HALT: Trading blocked by Guardian\n"
                f"   Reason: {reason}\n"
                f"   ⏰ Waiting for Guardian to publish GO signal..."
            )
            log.warning(halt_reason)
            return False, halt_reason
        
        # 2. Check cooldown period
        if not self._is_cooldown_ready():
            elapsed = time.time() - self._last_order_time
            remaining = self.cooldown_seconds - elapsed
            
            reason = (
                f"⏱️  COOLDOWN: Order placement rate-limited\n"
                f"   Seconds since last order: {elapsed:.1f}s\n"
                f"   Cooldown period: {self.cooldown_seconds:.1f}s\n"
                f"   ⏰ Can place order in: {remaining:.1f}s"
            )
            log.info(reason)
            return False, reason  # Return FULL detailed message
        
        # 3. Check price availability
        if not self.current_price:
            reason = (
                f"📍 NO PRICE DATA: Cannot place orders without current price\n"
                f"   ⏰ Waiting for price update from WebSocket..."
            )
            log.warning(reason)
            log.warning(f"   � Trading BLOCKED for: {context}")
            return False, reason  # Return FULL detailed message
        
        # 5. Check grid bounds
        if not self.grid_calc.is_within_bounds(self.current_price):
            reason = (
                f"📊 PRICE OUT OF GRID: Current price outside trading range\n"
                f"   Current Price: ${self.current_price:,.0f}\n"
                f"   Grid Lower: ${self.grid_calc.lower:,.0f}\n"
                f"   Grid Upper: ${self.grid_calc.upper:,.0f}\n"
                f"   ⏰ Can trade when price enters grid range"
            )
            log.info(reason)
            log.info(f"   � Trading BLOCKED for: {context}")
            return False, reason  # Return FULL detailed message
        
        # 6. Check price health (NOV 13 monitoring system)
        try:
            can_place, health_reason = self.price_monitor.can_place_orders()
            if not can_place:
                reason = (
                    f"🏥 PRICE HEALTH CHECK FAILED: {health_reason}\n"
                    f"   ⏰ Waiting for price data to stabilize..."
                )
                log.warning(reason)
                return False, reason  # Return FULL detailed message
        except Exception as e:
            log.debug(f"Price health check error (proceeding): {e}")
        
        # All checks passed
        return True, "All safety checks passed"
    
    def _update_last_order_time(self, order_price: Optional[float] = None) -> None:
        self._last_order_time = time.time()
        if order_price is not None:
            self._last_accepted_order_price = order_price
    
    # Phase 5 dedup helpers — MOVED to FillProcessor (P5.2)
    # _is_fill_seen, _mark_fill_seen, _is_order_fill_seen, _mark_order_fill_seen, _cleanup_old_fill_ids
    
    # _check_guardian_transition_and_retry — MOVED to GuardianHandler.check_transition_and_retry() (P1.3)

    # _retry_missed_grid_orders — MOVED to GuardianHandler.retry_missed_orders() (P1.4)

    # _fill_multi_step_missed_grids — MOVED to GuardianHandler.fill_multi_step_missed_grids() (P1.5)

    def _should_recalculate_grid_level(self, proposed_price: float) -> bool:
        if self._last_accepted_order_price is None:
            return True
        
        price_diff = abs(self.current_price - self._last_accepted_order_price)
        if price_diff < self._min_price_move_threshold:
            log.debug(f"Price moved only ${price_diff:.2f}, threshold is ${self._min_price_move_threshold:.2f} - skipping recalculation")
            return False
        
        return True

    
    # _reconcile_orphaned_orders — MOVED to ExchangeSync.reconcile_orphaned_orders() (P3.5)

    # _cleanup_misaligned_orders — MOVED to ExchangeSync.cleanup_misaligned_orders() (P3.6)

    # _reconcile_fills_after_reconnect — MOVED to ExchangeSync.reconcile_fills_after_reconnect() (P3.7)
    
    async def seed_missed_grid_levels(self, count: int) -> None:
        """
        Seed missed grid levels - place multiple entry orders at grid intervals.
        
        For LONG mode: Places BUY orders below current price
        For SHORT mode: Places SELL orders above current price
        
        Uses existing order placement logic via OrderManagerActor.
        Bot handles TPs automatically when fills occur.
        
        Args:
            count: Number of grid levels to seed
        """
        if count <= 0:
            return
        
        current_price = self.current_price
        
        log.info("=" * 70)
        log.info(f"🌱 SEEDING {count} MISSED GRID LEVELS ({self.mode} MODE)")
        log.info(f"📍 Current Price: ${current_price:,.0f}")
        log.info("=" * 70)
        
        for i in range(count):
            try:
                if self.mode == 'LONG':
                    # Buy below current price (going down)
                    level = current_price - (i + 1) * self.grid_calc.step
                    
                    if level >= self.grid_calc.lower:
                        # Place order via OrderManagerActor
                        order_resp = await self.order_actor.ask({
                            'action': 'place_buy_order',
                            'price': level,
                            'post_only': True
                        })
                        
                        if order_resp.get('status') == 'success':
                            order_id = order_resp.get('order_id')
                            log.info(f"  ✅ Grid BUY placed @ ${level:,.0f} (ID: {order_id})")
                        else:
                            log.warning(f"  ⚠️  Failed to place BUY @ ${level:,.0f}: {order_resp.get('error')}")
                    else:
                        log.warning(f"  ⚠️  Level ${level:,.0f} below grid lower bound, stopping")
                        break
                
                elif self.mode == 'SHORT':
                    # Sell above current price (going up)
                    level = current_price + (i + 1) * self.grid_calc.step
                    
                    if level <= self.grid_calc.upper:
                        # Place order via OrderManagerActor
                        order_resp = await self.order_actor.ask({
                            'action': 'place_sell_order',
                            'price': level,
                            'post_only': True
                        })
                        
                        if order_resp.get('status') == 'success':
                            order_id = order_resp.get('order_id')
                            log.info(f"  ✅ Grid SELL placed @ ${level:,.0f} (ID: {order_id})")
                        else:
                            log.warning(f"  ⚠️  Failed to place SELL @ ${level:,.0f}: {order_resp.get('error')}")
                    else:
                        log.warning(f"  ⚠️  Level ${level:,.0f} above grid upper bound, stopping")
                        break
                
                # Rate limiting between orders
                await asyncio.sleep(0.2)
                
            except Exception as e:
                log.error(f"❌ Error seeding grid level {i+1}: {e}")
                continue
        
        log.info("=" * 70)
        log.info(f"✅ SEEDING COMPLETE - Bot will manage TPs automatically")
        log.info("=" * 70)
    
    # ========================================================================
    # STARTUP
    # ========================================================================
    
    async def start(self) -> None:
        """Start all async components."""
        # Rich startup banner
        mode_emoji = "🟢" if self.testnet else "🔴"
        mode_text = "DEMO MODE [TESTNET]" if self.testnet else "LIVE MODE [PRODUCTION]"
        
        log.info("=" * 98)
        log.info(f"🎯 ASYNCGRIDBOT v2.0 INITIALIZATION (ASYNC + ACTOR + SAGA)")
        log.info("=" * 98)
        log.info(f"Trading Mode:  {mode_emoji} {mode_text}")
        log.info(f"Symbol:       {self.symbol} (ID: {self.product_id})")
        log.info(f"Grid Mode:    {self.mode} ({'Buy low, sell high' if self.mode == 'LONG' else 'Sell high, buy low'})")
        log.info(f"Grid Bounds:  ${self.grid_calc.lower:,.0f} - ${self.grid_calc.upper:,.0f} (Step: ${self.grid_calc.step:,.0f})")
        log.info(f"Reference:    ${self.grid_calc.ref:,.0f} (First {self.mode} @ ${self.grid_calc.ref - self.grid_calc.step if self.mode == 'LONG' else self.grid_calc.ref + self.grid_calc.step:,.0f})")
        log.info(f"TP Offset:    ${self.tp_offset:,.0f}")
        log.info(f"Max Positions: {self.max_positions}")
        log.info("")
        log.info("🔧 Architecture:")
        log.info("   ├─ Actor Pattern: PositionManagerActor + OrderManagerActor")
        log.info("   ├─ Saga Pattern: Transactional fill processing + emergency close")
        log.info("   ├─ Event Store: Persistent event log for replay")
        log.info("   ├─ Async I/O: Single event loop, no threads")
        log.info("   └─ WebSocket: Real-time price + order updates")
        log.info("")
        log.info("🛡️  Safety Features:")
        log.info(f"   └─ Guardian Bot: Monitors all risk (volatility, loss, position, liquidation)")
        log.info("="  * 98)
        
        # Check Guardian status
        log.info("")
        log.info("🔍 STARTUP CHECKS")
        log.info("=" * 98)
        
        # Initialize State Coordinator (NOV 20)
        from bot.strategy.simple_state_coordinator import SimpleStateCoordinator
        self.state_coordinator = SimpleStateCoordinator(self)
        
        # Run startup sequence (wait for Guardian, check recovery)
        await self.state_coordinator.run_startup_sequence()
        
        # Load recovery state (NOV 20)
        await self._load_recovery_state()
        
        # Sync positions from exchange (NOV 20)
        await self.exchange_sync.sync_positions_from_exchange()
        
        self._running = True
        self._started_once = True
        self._start_time = time.time()

        # Wire GuardianHandler runtime refs
        self.guardian.set_runtime_refs(
            get_running=lambda: self._running,
            get_current_price=lambda: self.current_price,
            set_running=lambda v: setattr(self, '_running', v),
            get_started_once=lambda: self._started_once,
        )
        # cancel_pending_entries + resume_grid now live inside GuardianHandler (P1.7)

        # Wire HealthMonitor runtime refs
        self.health_monitor.set_runtime_refs(
            _get_running=lambda: self._running,
            _get_current_price=lambda: getattr(self, '_last_price', None),
            _get_start_time=lambda: self._start_time,
            _get_fills_processed=lambda: self._fills_processed,
            _get_sagas_completed=lambda: self._sagas_completed,
            _get_sagas_failed=lambda: self._sagas_failed,
            _get_last_price_update=lambda: self._last_price_update,
            _get_initial_order_placed=lambda: self._initial_order_placed,
            _get_last_heartbeat_time=lambda: self._last_heartbeat_time,
            _set_last_heartbeat_time=lambda v: setattr(self, '_last_heartbeat_time', v),
            _get_last_block_reason=lambda: getattr(self, '_last_block_reason', None),
            _set_last_block_reason=lambda v: setattr(self, '_last_block_reason', v),
            _get_tp_offset=lambda: self.tp_offset,
            _get_pre_order_logger=lambda: self.pre_order_logger,
            _get_anomaly_detector=lambda: self.anomaly_detector,
            _log_grid_status_callback=self._log_detailed_grid_status,
            _format_pending_order_callback=self.health_monitor._format_pending_order_info,
            _emergency_stop_callback=self.emergency_stop,
            _check_guardian_transitions_callback=self.guardian.check_transitions,
            _tp_retry_callback=self._process_tp_retry_queue,
        )

        # Wire ExchangeSync runtime refs
        self.exchange_sync.set_runtime_refs(
            _get_running=lambda: self._running,
            _get_current_price=lambda: self.current_price,
            _fetch_current_price_callback=self.ws_lifecycle.fetch_current_price,
            _process_fill_callback=self._process_fill,
        )

        # Create asyncio primitives within event loop
        if self._order_placement_lock is None:
            self._order_placement_lock = asyncio.Lock()
        
        # ========================================================================
        # NOV 13: MODE-ATOMIC STATE MANAGEMENT
        # ========================================================================
        # Mode switch = Fresh start. All existing positions = Manual.
        # Bot never touches manual positions or their TPs.
        
        mode_manager = get_mode_state_manager()
        should_load, state_file, reason = mode_manager.handle_mode_transition()
        
        log.info("=" * 80)
        log.info("🗄️ STATE MANAGEMENT - CLEAN SLATE MODE")
        log.info("=" * 80)
        log.info(f"   Instance: {self.instance_name}")
        log.info(f"   Current Mode: {self.mode}")
        log.info(f"   Storage: SQLite Event Store (data/bot_events_{self.instance_name}.db)")
        log.info(f"   State Loading: DISABLED (Clean Slate - sync from exchange only)")
        log.info(f"   Mode Tracking: {state_file.name if state_file else 'N/A'} (not loaded)")
        log.info(f"   Reason: {reason}")
        log.info("=" * 80)
        
        if not should_load:
            # Mode switch or first run = Log manual position policy
            mode_manager.log_manual_position_policy()
        
        # Volatility halt cleanup REMOVED - Guardian manages all halt state
        
        # Register WebSocket handlers
        self.ws_lifecycle.set_runtime_refs(
            _get_running=lambda: self._running,
            _get_start_time=lambda: self._start_time,
            _on_ticker_callback=self._check_and_place_entry_order,
            _on_order_update_callback=self._handle_order_update,
            _process_fill_callback=self._process_fill,
            _full_exchange_sync_callback=self.exchange_sync.full_exchange_sync,
        )
        self.ws_lifecycle.register_handlers()
        
        # CRITICAL FIX NOV 14: Register reconnection callback for fill reconciliation
        # Reconnection handled by UnifiedAPIClient: self.exchange_sync.reconcile_fills_after_reconnect)
        
        # Start actors FIRST (needed for reconciliation)
        # NOTE: Actor .start() methods return immediately after starting their message loops
        # They manage their own lifecycle, so we don't track them in self._tasks
        log.info("Starting actors...")
        await self.position_actor.start()
        await self.order_actor.start()
        
        # Volatility Monitor startup REMOVED - Guardian monitors volatility
        
        # Wait a moment for actors to be ready
        await asyncio.sleep(0.1)
        
        await self.exchange_sync.reconcile_orphaned_orders()
        
        # DEC 23 Layer 4: Enhanced startup reconciliation
        # Full exchange sync to catch any fills that happened while bot was down
        log.info("🔄 Running enhanced startup reconciliation...")
        try:
            await self.exchange_sync.full_exchange_sync()
            log.info("✅ Enhanced startup reconciliation complete")
        except Exception as sync_error:
            log.warning(f"⚠️ Startup reconciliation had errors: {sync_error}")
            log.warning("   Continuing with basic reconciliation...")
        
        # Connect WebSocket
        log.info("Connecting WebSocket...")
        await self.api_client.connect()
        
        # Subscribe to channels
        await self.ws_lifecycle.subscribe_channels()
        
        # Wait a moment for subscriptions to stabilize
        await asyncio.sleep(1)
        
        # Get current market price
        await self.ws_lifecycle.fetch_current_price()
        
        await self.exchange_sync.cleanup_misaligned_orders()
        
        # Place initial order to start grid strategy
        await self._place_initial_order()
        
        # DEC 23: Start Fill Monitor (creates internal task)
        await self.fill_monitor.start()
        
        # Reset heartbeat so watchdog doesn't trigger from startup delay
        self._last_heartbeat_time = time.time()
        
        # Start async tasks
        log.info("Starting async tasks...")
        async_tasks = [
            asyncio.create_task(self.health_monitor.heartbeat_loop(), name="heartbeat"),
            asyncio.create_task(self.ws_lifecycle.message_loop(), name="websocket"),
            asyncio.create_task(self.health_monitor.monitoring_loop(), name="monitoring"),
            asyncio.create_task(self.health_monitor.health_check_loop(), name="health_check"),
            asyncio.create_task(self._reconciliation_action_processor(), name="reconciliation_actions"),  # NOV 20: Process actions from standalone reconciliation engine
            asyncio.create_task(self.ws_lifecycle.rest_fallback_monitor_loop(), name="rest_fallback"),  # NOV 13: REST fallback
            asyncio.create_task(self.health_monitor.watchdog_loop(), name="watchdog"),  # NOV 13: Event loop watchdog
            asyncio.create_task(self._safety_gatekeeper_loop(), name="safety_gatekeeper"),  # Safety check every 5 min
            asyncio.create_task(self._fill_polling_fallback_loop(), name="fill_polling"),  # JAN 20: Fill polling fallback every 60s
            asyncio.create_task(self.guardian.health_monitor_loop(), name="guardian_monitor"),  # CRITICAL: Guardian health check every 15s
            asyncio.create_task(self.api_client.start_websocket_health_monitor(), name="ws_health_monitor"),  # CRITICAL FIX: WebSocket health monitor (5s checks)
            asyncio.create_task(self.state_coordinator.monitor_guardian(), name="state_guardian_monitor"),  # NOV 20: State coordinator Guardian monitor
            asyncio.create_task(self.state_coordinator.run_reconciliation_loop(), name="state_reconciliation"),  # NOV 20: State coordinator reconciliation
            self.fill_monitor._task,  # DEC 23: Fill Monitor task (already created by start())
            asyncio.create_task(self.exchange_sync.exchange_maintenance_monitor(), name="exchange_maintenance_monitor")  # DEC 23 Layer 3: Exchange state monitoring
        ]
        self._tasks.extend(async_tasks)
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # NOV 13: Wire bot instance to WebUI monitoring routes
        log.info("🌐 Wiring bot instance to WebUI monitoring routes...")
        try:
            from webui.backend.routes.monitoring import set_bot_instance
            set_bot_instance(self)
            log.info("✅ Bot wired to WebUI - monitoring data now accessible via API")
        except ImportError:
            log.warning("⚠️  WebUI monitoring routes not available (import failed)")
        except Exception as e:
            log.warning(f"⚠️  Could not wire to WebUI: {e}")
        
        log.info("✅ AsyncGridBot started successfully")
        
        # NOV 13: Send startup notification
        await self._send_startup_notification()
        
        # Wait for tasks or shutdown signal
        # FIX NOV 14: Periodically check _running flag instead of just waiting for tasks
        try:
            while self._running:
                # Check if any critical task has died
                # Note: WebSocket task can complete during reconnection - this is normal
                done_tasks = [t for t in self._tasks if t.done()]
                if done_tasks:
                    # Filter out websocket task - it can complete during reconnection
                    critical_failures = []
                    for task in done_tasks:
                        task_name = task.get_name() if hasattr(task, 'get_name') else "unknown"
                        # Skip websocket task - reconnection is normal
                        if 'websocket' in task_name.lower() or 'ws' in task_name.lower():
                            # Rate-limited logging for websocket reconnections
                            if self._should_log('websocket_reconnection', interval_seconds=30):
                                log.debug(f"   Task '{task_name}' completed (normal for reconnection)")
                            continue
                        critical_failures.append(task)
                        log.warning(f"   Task '{task_name}' completed unexpectedly")
                        try:
                            exception = task.exception()
                            if exception:
                                log.error(f"   Task '{task_name}' failed with exception: {exception}")
                        except:
                            pass
                    
                    # Only stop if we have critical failures (not websocket)
                    if critical_failures:
                        log.warning(f"⚠️  {len(critical_failures)} critical task(s) failed - stopping bot")
                        break
                    else:
                        # Rate-limited logging for non-critical completions
                        if self._should_log('non_critical_task_completion', interval_seconds=60):
                            log.debug("All completed tasks were non-critical (websocket reconnection)")
                
                # Sleep briefly and check again
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            log.info("Main loop cancelled - shutting down")
        except KeyboardInterrupt:
            log.info("KeyboardInterrupt - shutting down")
        finally:
            # Always call stop() when exiting main loop
            if self._running:
                # stop() wasn't called yet, call it now
                await self.stop()
    
    async def stop(self) -> None:
        """Gracefully stop all components."""
        # Prevent multiple calls to stop()
        if hasattr(self, '_stopping') and self._stopping:
            log.debug("stop() already in progress, skipping duplicate call")
            return
        
        self._stopping = True
        self._running = False
        
        log.info("🛑 Stopping AsyncGridBot...")
        human_log.bot_shutting_down()
        
        # NOV 20: Write shutdown signal for reconciliation (event-driven cleanup)
        await self._write_shutdown_signal()
        
        # NOV 14: Cancel pending entry orders before shutdown
        # This prevents orphaned entry orders while preserving:
        # - Executed positions (in open_tranches)
        # - TP orders (reduce_only orders protecting positions)
        try:
            # CRITICAL: Cancel ONLY pending entry orders (not TP orders!)
            # Delta Exchange takes 5-10s to process, we wait 12s to verify
            # Total time: API call + 12s wait + buffer = 30s
            await asyncio.wait_for(
                self._cancel_pending_orders_on_shutdown(),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            log.warning("⚠️  Order cancellation timed out (30s) - continuing shutdown")
            log.warning("⚠️  PENDING ENTRY ORDERS MAY STILL BE ACTIVE ON EXCHANGE!")
        except Exception as e:
            log.error(f"Failed to cancel pending orders on shutdown: {e}")
        
        # Send shutdown notification
        try:
            await asyncio.wait_for(
                self._send_shutdown_notification(),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            log.debug("Shutdown notification timed out")
        except Exception as e:
            log.debug(f"Shutdown notification failed: {e}")
        
        # Stop saga orchestrator (reduced timeout)
        try:
            await asyncio.wait_for(
                self.saga_orchestrator.stop_all(timeout=2.0),
                timeout=3.0
            )
        except asyncio.TimeoutError:
            log.warning("Saga orchestrator stop timed out")
        
        # Stop actors (parallel for speed)
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    self.position_actor.stop(timeout=2.0),
                    self.order_actor.stop(timeout=2.0),
                    return_exceptions=True
                ),
                timeout=3.0
            )
        except asyncio.TimeoutError:
            log.warning("Actor shutdown timed out")
        
        # Disconnect WebSocket (quick)
        try:
            if hasattr(self, 'api_client') and hasattr(self.api_client, 'ws_manager') and self.api_client.ws_manager:
                await asyncio.wait_for(
                    self.api_client.ws_manager.disconnect(),
                    timeout=2.0
                )
        except asyncio.TimeoutError:
            log.warning("WebSocket disconnect timed out")
        except Exception as e:
            log.debug(f"WebSocket disconnect error: {e}")
        
        # Close API client (if it has close method)
        try:
            if hasattr(self, 'api_client') and hasattr(self.api_client, 'close'):
                await asyncio.wait_for(
                    self.api_client.close(),
                    timeout=1.0
                )
        except asyncio.TimeoutError:
            log.debug("API client close timed out")
        except Exception as e:
            log.debug(f"API client close error: {e}")
        
        # Cancel tasks (quick)
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete (brief)
        if self._tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._tasks, return_exceptions=True),
                    timeout=2.0
                )
            except asyncio.TimeoutError:
                log.debug("Task cleanup timed out")
        
        # Print final metrics (quick)
        uptime = time.time() - self._start_time
        log.info(f"Uptime: {uptime:.0f}s | Fills: {self._fills_processed} | Sagas: {self._sagas_completed}✅ {self._sagas_failed}❌")
        
        log.info("✅ AsyncGridBot stopped")
    
    # ── _register_ws_handlers → MOVED to ws_lifecycle.register_handlers() [P4.3] ──
    # ── _subscribe_channels → MOVED to ws_lifecycle.subscribe_channels() [P4.3] ──
    # ── _ws_message_loop → MOVED to ws_lifecycle.message_loop() [P4.3] ──
    # ── _handle_user_trades → MOVED to ws_lifecycle (disabled) [P4.3] ──
    
    async def _process_fill(self, fill_data: Dict[str, Any]) -> None:
        """
        Process fill via saga.
        
        CRITICAL: Multiple systems can call this (WebSocket, Fill Monitor, Post-Order Verification).
        Deduplication prevents double-processing using BOTH fill_id AND order_id.
        
        Args:
            fill_data: Fill information
        """
        try:
            fill_id = str(fill_data.get('id', ''))
            order_id = str(fill_data.get("order_id", ''))
            
            # CRITICAL: Check BOTH fill_id and order_id for deduplication
            # Fill Monitor creates synthetic fill_ids, so order_id is the true unique key
            if self._is_fill_seen(fill_id):
                log.debug(f"⏭️  Skipping already processed fill: {fill_id}")
                return
            
            if order_id and self._is_order_fill_seen(order_id):
                log.debug(f"⏭️  Skipping already processed order fill: {order_id}")
                return
            
            # Mark BOTH fill_id and order_id as seen
            self._mark_fill_seen(fill_id)
            if order_id:
                self._mark_order_fill_seen(order_id)
                # Mark in Fill Monitor too (prevents Fill Monitor from re-detecting)
                self.fill_monitor.mark_filled(order_id, source="processing")
            
            self._cleanup_old_fill_ids()
            
            fill_product = fill_data.get('product_id')
            if fill_product and fill_product != self.product_id:
                log.debug(f"⏭️  Ignoring fill for different product: {fill_product} (bot trades product_id={self.product_id})")
                return
            
            order_id = fill_data.get("order_id")
            
            self._fills_processed += 1
            
            # Generate correlation ID
            correlation_id = f"fill-{fill_data.get('id', '')}-{int(time.time()*1000)}"
            
            # Prepare fill data
            # CRITICAL FIX NOV 14: Don't default is_complete to True
            # Partial fills must be explicitly marked, otherwise position size will be wrong
            is_complete = fill_data.get("is_complete")
            if is_complete is None:
                # If not provided, check unfilled_size
                unfilled_size = fill_data.get("unfilled_size", 0)
                is_complete = (unfilled_size == 0)
                log.warning(f"⚠️  is_complete not provided in fill data, inferring from unfilled_size: {is_complete}")
            
            processed_fill = {
                "order_id": fill_data.get("order_id"),
                "fill_price": float(fill_data.get("price", 0)),
                "fill_size": int(fill_data.get("size", 0)),
                "side": fill_data.get("side"),
                "is_complete": is_complete
            }
            
            # Enhanced logging (matching old GridBot style)
            log.info(f"🔔 Processing fill: {processed_fill['side'].upper()} {processed_fill['fill_size']} @ ${processed_fill['fill_price']:,.0f}")
            
            # Mark bot as started on first fill
            if not self._initial_order_placed:
                self._initial_order_placed = True
                log.info("✅ Bot marked as ACTIVE (first fill processed)")
            
            # Human-readable narrative logging
            human_log.order_filled(
                processed_fill.get("order_id", "unknown"),
                processed_fill["side"].upper(),
                processed_fill["fill_price"]
            )
            
            # Create appropriate saga based on MODE and SIDE
            if self.mode == "LONG":
                if processed_fill["side"] == "buy":
                    # LONG mode: BUY = Entry
                    # Calculate TP price for new position
                    tp_price = processed_fill['fill_price'] + self.grid_calc.step
                    log.info(f"   💰 New position opened | Entry: ${processed_fill['fill_price']:,.0f} → Target: ${tp_price:,.0f}")
                    
                    # Get current position count
                    state = await self.position_actor.ask("GET_STATE", {})
                    current_positions = len(state.get("open_tranches", []))
                    log.info(f"   📊 Active positions: {current_positions + 1}/{self.max_positions}")
                    
                    # Human-readable position update
                    human_log.position_updated(size=current_positions + 1)
                    
                    # Calculate next buy level
                    next_buy = self.fill_processor.calculate_next_grid_level('BUY', processed_fill['fill_price'])
                    if next_buy:
                        log.info(f"   ⬇️  Next BUY level: ${next_buy:,.0f}")
                    
                    saga = await create_buy_fill_saga(
                        fill_data=processed_fill,
                        correlation_id=correlation_id,
                        position_actor=self.position_actor,
                        order_actor=self.order_actor,
                        grid_calc=self.grid_calc,
                        event_store=self.event_store,
                        mode=self.mode
                    )
                else:  # sell
                    # LONG mode: SELL = TP close
                    # Get position details for profit calculation
                    state = await self.position_actor.ask("GET_STATE", {})
                    positions = state.get("open_tranches", [])
                    
                    # Find the position that was closed
                    order_id = processed_fill.get("order_id")
                    closed_position = None
                    for pos in positions:
                        if pos.get("tp_order_id") == order_id:
                            closed_position = pos
                            break
                    
                    if closed_position:
                        entry_price = closed_position.get("entry_price", 0)
                        exit_price = processed_fill['fill_price']
                        profit = exit_price - entry_price
                        profit_pct = (profit / entry_price * 100) if entry_price > 0 else 0
                        
                        log.info(f"   ✅ Position closed | Entry: ${entry_price:,.0f} → Exit: ${exit_price:,.0f}")
                        log.info(f"   💵 Profit: ${profit:,.0f} ({profit_pct:+.2f}%)")
                    
                    # Get updated position count
                    remaining_positions = len(positions) - 1
                    log.info(f"   📊 Active positions: {remaining_positions}/{self.max_positions}")
                    
                    # Human-readable position update with PnL
                    if closed_position:
                        human_log.position_updated(size=remaining_positions, pnl=profit)
                    else:
                        human_log.position_updated(size=remaining_positions)
                    
                    saga = await create_sell_fill_saga(
                        fill_data=processed_fill,
                        correlation_id=correlation_id,
                        position_actor=self.position_actor,
                        order_actor=self.order_actor,
                        grid_calc=self.grid_calc,
                        event_store=self.event_store,
                        mode=self.mode
                    )
            
            elif self.mode == "SHORT":
                if processed_fill["side"] == "sell":
                    # SHORT mode: SELL = Entry
                    # Calculate TP price for new position (below entry)
                    tp_price = processed_fill['fill_price'] - self.grid_calc.step
                    log.info(f"   💰 New SHORT position opened | Entry: ${processed_fill['fill_price']:,.0f} → Target: ${tp_price:,.0f}")
                    
                    # Get current position count
                    state = await self.position_actor.ask("GET_STATE", {})
                    current_positions = len(state.get("open_tranches", []))
                    log.info(f"   📊 Active positions: {current_positions + 1}/{self.max_positions}")
                    
                    # Human-readable position update
                    human_log.position_updated(size=current_positions + 1)
                    
                    # Calculate next sell level (UP from current)
                    next_sell = self.fill_processor.calculate_next_grid_level('SELL', processed_fill['fill_price'])
                    if next_sell:
                        log.info(f"   ⬆️  Next SELL level: ${next_sell:,.0f}")
                    
                    saga = await create_short_entry_saga(
                        fill_data=processed_fill,
                        correlation_id=correlation_id,
                        position_actor=self.position_actor,
                        order_actor=self.order_actor,
                        grid_calc=self.grid_calc,
                        event_store=self.event_store
                    )
                else:  # buy
                    # SHORT mode: BUY = TP close
                    # Get position details for profit calculation
                    state = await self.position_actor.ask("GET_STATE", {})
                    positions = state.get("open_tranches", [])
                    
                    # Find the position that was closed
                    order_id = processed_fill.get("order_id")
                    closed_position = None
                    for pos in positions:
                        if pos.get("tp_order_id") == order_id:
                            closed_position = pos
                            break
                    
                    if closed_position:
                        entry_price = closed_position.get("entry_price", 0)
                        exit_price = processed_fill['fill_price']
                        profit = entry_price - exit_price  # SHORT profit
                        profit_pct = (profit / entry_price * 100) if entry_price > 0 else 0
                        
                        log.info(f"   ✅ SHORT position closed | Entry: ${entry_price:,.0f} → Exit: ${exit_price:,.0f}")
                        log.info(f"   💵 Profit: ${profit:,.0f} ({profit_pct:+.2f}%)")
                    
                    # Get updated position count
                    remaining_positions = len(positions) - 1
                    log.info(f"   📊 Active positions: {remaining_positions}/{self.max_positions}")
                    
                    # Human-readable position update with PnL
                    if closed_position:
                        human_log.position_updated(size=remaining_positions, pnl=profit)
                    else:
                        human_log.position_updated(size=remaining_positions)
                    
                    saga = await create_short_tp_saga(
                        fill_data=processed_fill,
                        correlation_id=correlation_id,
                        position_actor=self.position_actor,
                        order_actor=self.order_actor,
                        grid_calc=self.grid_calc,
                        event_store=self.event_store
                    )
            else:
                raise ValueError(f"Unknown trading mode: {self.mode}")
            
            # Execute saga
            task = await self.saga_orchestrator.start_saga(saga)
            
            # Track saga completion
            asyncio.create_task(self.fill_processor.track_saga_completion(task, correlation_id))
            
            # Safety check removed - Guardian monitors risk parameters
            # Fill processed successfully
            self._last_safety_check_time = time.time()
        
        except Exception as e:
            log.error(f"Error processing fill: {e}")
    
    # _track_saga_completion — MOVED to FillProcessor.track_saga_completion() (P5.4)
    
    # ========================================================================
    # DEC 23: Fill Monitor Integration (Exchange Maintenance Protection)
    # ========================================================================
    
    async def _process_missed_fill(self, order_data: Dict[str, Any]) -> None:
        """
        Process a fill detected by Fill Monitor (not WebSocket).
        
        This is called when:
        1. Fill happens during WebSocket disconnection
        2. Fill happens during exchange maintenance
        3. WebSocket misses the notification for any reason
        
        Args:
            order_data: Order data from exchange with fill information
        """
        try:
            order_id = str(order_data.get('id') or order_data.get('order_id', ''))
            state = order_data.get('state', '').lower()
            unfilled_size = order_data.get('unfilled_size', 0)
            
            # Verify it's actually filled
            if state != 'closed' or unfilled_size != 0:
                log.warning(f"⚠️ [FillMonitor] Order {order_id} not actually filled (state={state}, unfilled={unfilled_size})")
                return
            
            # Extract fill data
            fill_price = float(order_data.get('average_fill_price') or order_data.get('limit_price', 0))
            fill_size = int(order_data.get('size', 0))
            side = order_data.get('side', '').lower()
            
            log.warning("=" * 80)
            log.warning("🎯 MISSED FILL DETECTED BY FILL MONITOR!")
            log.warning(f"   Order ID: {order_id}")
            log.warning(f"   Side: {side.upper()}")
            log.warning(f"   Price: ${fill_price:,.0f}")
            log.warning(f"   Size: {fill_size}")
            log.warning(f"   Reason: Fill occurred during WebSocket disconnection or exchange maintenance")
            log.warning("=" * 80)
            
            # CRITICAL: Check if already processed (race condition prevention)
            if self._is_order_fill_seen(order_id):
                log.info(f"✓ [FillMonitor] Order {order_id} already processed (WebSocket or other system detected it)")
                return
            
            # Create fill data structure (same format as WebSocket fills)
            fill_data = {
                "id": f"missed-fill-{order_id}-{int(time.time()*1000)}",
                "order_id": order_id,
                "price": fill_price,
                "size": fill_size,
                "side": side,
                "product_id": self.product_id,
                "is_complete": True,  # Fill Monitor only detects completed fills
                "unfilled_size": 0
            }
            
            # Process through normal fill saga
            await self._process_fill(fill_data)
            
            log.info(f"✅ [FillMonitor] Missed fill processed successfully")
            
        except Exception as e:
            log.error(f"❌ [FillMonitor] Error processing missed fill: {e}")
    
    def _track_order_in_fill_monitor(self, order_id: str, side: str, price: float, size: int) -> None:
        """
        Track an order in Fill Monitor after placement.
        
        This enables Fill Monitor to verify the order status and detect fills
        that may have been missed by WebSocket.
        
        Args:
            order_id: Exchange order ID
            side: Order side ('buy' or 'sell')
            price: Order price
            size: Order size
        """
        try:
            self.fill_monitor.track_order(
                order_id=order_id,
                side=side,
                price=price,
                size=size,
                placed_at=time.time()
            )
            log.debug(f"[FillMonitor] Tracking order {order_id}: {side.upper()} @ ${price:,.0f}")
        except Exception as e:
            log.error(f"❌ Error tracking order in Fill Monitor: {e}")
    
    async def _verify_order_after_placement(self, order_id: str, expected_side: str, expected_price: float, timeout: int = 5) -> bool:
        """
        Verify order status immediately after placement (Layer 2).
        
        This catches fills that happen during WebSocket reconnection or exchange maintenance.
        Checks every 1 second for up to 5 seconds.
        
        Args:
            order_id: Order ID to verify
            expected_side: Expected order side ('buy' or 'sell')
            expected_price: Expected order price
            timeout: Maximum time to wait (seconds)
        
        Returns:
            True if order filled immediately, False otherwise
        """
        try:
            start_time = time.time()
            check_count = 0
            
            while time.time() - start_time < timeout:
                await asyncio.sleep(1)
                check_count += 1
                
                # Query exchange for order status
                order = await self.api_client.get_order(order_id)
                
                if not order:
                    log.warning(f"[PostOrderVerification] Order {order_id} not found on exchange")
                    return False
                
                state = order.get('state', '').lower()
                unfilled_size = order.get('unfilled_size', 0)
                
                # Check if filled
                if state == 'closed' and unfilled_size == 0:
                    avg_price = order.get('average_fill_price', expected_price)
                    log.warning("=" * 80)
                    log.warning("⚡ IMMEDIATE FILL DETECTED (Post-Order Verification)!")
                    log.warning(f"   Order ID: {order_id}")
                    log.warning(f"   Side: {expected_side.upper()}")
                    log.warning(f"   Expected Price: ${expected_price:,.0f}")
                    log.warning(f"   Filled Price: ${avg_price:,.0f}")
                    log.warning(f"   Detection Time: {check_count}s after placement")
                    log.warning(f"   Reason: Order filled before WebSocket notification")
                    log.warning("=" * 80)
                    
                    # Create fill data and process
                    fill_data = {
                        'id': f'immediate-fill-{order_id}-{int(time.time()*1000)}',
                        'order_id': str(order_id),
                        'side': expected_side,
                        'price': avg_price,
                        'size': order.get('size', 1),
                        'product_id': self.product_id,
                        'is_complete': True,
                        'unfilled_size': 0
                    }
                    
                    await self._process_fill(fill_data)
                    return True
                
                # Check if cancelled (shouldn't happen but handle it)
                if state == 'cancelled':
                    log.info(f"[PostOrderVerification] Order {order_id} was cancelled")
                    return False
            
            # Timeout - order still open (normal case)
            log.debug(f"[PostOrderVerification] Order {order_id} verified as open after {timeout}s")
            return False
            
        except Exception as e:
            log.error(f"❌ [PostOrderVerification] Error verifying order {order_id}: {e}")
            return False
    
    # ========================================================================
    # DEC 23: Layer 3 - Exchange State Detection
    # ========================================================================
    
    # _detect_exchange_state — MOVED to ExchangeSync.detect_exchange_state() (P3.2)

    # _handle_exchange_maintenance — MOVED to ExchangeSync.handle_exchange_maintenance() (P3.2)

    # _full_exchange_sync — MOVED to ExchangeSync.full_exchange_sync() (P3.8)

    # _ensure_grid_coverage — MOVED to ExchangeSync.ensure_grid_coverage() (P3.7)

    # ========================================================================
    # WebSocket Handlers
    # ========================================================================
    
    async def _handle_order_update(self, message: Dict[str, Any]) -> None:
        """
        Handle order update messages.
        CRITICAL: Delta Exchange sends fill notifications via orders channel!
        """
        try:
            # Log all order updates for debugging
            log.debug(f"📬 Order update received: {message}")
            
            # Check if this is a fill notification or cancellation
            order_data = message if isinstance(message, dict) else {}
            
            # Delta Exchange order status: "open", "pending", "closed" (when filled), "cancelled"
            order_status = order_data.get("state") or order_data.get("status")
            order_reason = order_data.get("reason")
            order_id = order_data.get("id") or order_data.get("order_id")
            
            # Handle cancellation (manual or otherwise)
            if order_status == "cancelled":
                cancellation_reason = order_data.get("cancellation_reason", "unknown")
                log.info(f"📭 Order cancelled: {order_id} (reason: {cancellation_reason})")
                
                # Clear from pending memory
                # FIX MAR 2 2026: pending_buy/pending_sell are DICTS with 'order_id' key,
                # not raw order_id strings. Must compare .get('order_id'), not the dict itself.
                state = await self.position_actor.ask("GET_STATE", {})
                pending_buy = state.get("pending_buy")
                pending_sell = state.get("pending_sell")
                
                pending_buy_id = pending_buy.get("order_id") if isinstance(pending_buy, dict) else pending_buy
                pending_sell_id = pending_sell.get("order_id") if isinstance(pending_sell, dict) else pending_sell
                
                # Convert both to string for safe comparison (API returns int or str)
                order_id_str = str(order_id) if order_id else None
                
                if pending_buy_id and str(pending_buy_id) == order_id_str:
                    await self.position_actor.ask("CLEAR_PENDING_BUY", {"order_id": order_id})
                    log.info(f"✅ Cleared pending buy from memory: {order_id}")
                elif pending_sell_id and str(pending_sell_id) == order_id_str:
                    await self.position_actor.ask("CLEAR_PENDING_SELL", {"order_id": order_id})
                    log.info(f"✅ Cleared pending sell from memory: {order_id}")
                else:
                    log.debug(f"   Cancelled order {order_id} was not in pending memory (buy={pending_buy_id}, sell={pending_sell_id})")
                
                return
            
            # Check if order was filled (status="closed" AND reason="fill")
            if order_status == "closed" and order_reason == "fill":
                # Determine if this is a bot-placed order
                client_order_id = order_data.get("client_order_id", "")
                is_reduce_only = order_data.get("reduce_only", False)
                
                # Bot orders are either:
                # 1. Entry orders with GBOT_ prefix
                # 2. TP orders with reduce_only=True (these don't have client_order_id)
                is_entry_order = client_order_id and (client_order_id.startswith("GBOT_") or client_order_id.startswith("BOT-"))
                is_tp_order = is_reduce_only  # TP orders are always reduce_only
                
                is_bot_order = is_entry_order or is_tp_order
                
                if not is_bot_order:
                    order_id = order_data.get("id") or order_data.get("order_id")
                    log.info(f"ℹ️  Ignoring manual order fill: {order_id} (client_id: {client_order_id or 'None'}, reduce_only: {is_reduce_only})")
                    return
                
                # This is a fill from bot-placed order! Process it immediately
                order_id = order_data.get("id") or order_data.get("order_id")
                fill_price = float(order_data.get("average_fill_price") or order_data.get("price", 0))
                fill_size = int(order_data.get("size") or order_data.get("unfilled_size", 0))
                side = order_data.get("side", "").lower()
                
                # CRITICAL: Use exchange's fill_id for deduplication (not timestamp)
                # Delta Exchange sends duplicate WebSocket messages; proper fill_id prevents double-processing
                exchange_fill_id = order_data.get("fill_id")  # Exchange-provided unique fill ID
                
                log.info(f"🔔 FILL DETECTED via orders channel!")
                log.info(f"   Order ID: {order_id}")
                log.info(f"   Fill ID: {exchange_fill_id}")
                log.info(f"   Side: {side.upper()}")
                log.info(f"   Price: ${fill_price:,.0f}")
                log.info(f"   Size: {fill_size}")
                
                # Create fill data structure
                # Use exchange fill_id if available, otherwise fallback to order_id (without timestamp)
                fill_data = {
                    "id": exchange_fill_id or f"fill-{order_id}",
                    "order_id": str(order_id),
                    "price": fill_price,
                    "size": fill_size,
                    "side": side,
                    "is_complete": True
                }
                
                # Process the fill
                await self._process_fill(fill_data)
                
        except Exception as e:
            log.error(f"Error handling order update: {e}", exc_info=True)
    
    # ── _handle_position_update → MOVED to ws_lifecycle._handle_position_update() [P4.4] ──
    # ── _handle_ticker_update → MOVED to ws_lifecycle._handle_ticker_update() [P4.4] ──

    # get_current_price — MOVED to WSLifecycle.get_current_price() (P4.2)

    async def get_current_price(self) -> float:
        """Delegate to WSLifecycle (kept for external callers like recovery engines)."""
        return await self.ws_lifecycle.get_current_price()

    # _fetch_current_price — MOVED to WSLifecycle.fetch_current_price() (P4.2)
    
    async def _place_initial_order(self) -> None:
        """
        Place initial entry order on startup.
        Only places order if no positions or pending orders exist.
        """
        try:
            log.info("Checking if initial order should be placed...")
            
            # Pre-order volatility check REMOVED - Guardian handles this
            # Guardian publishes GO/STOP signals based on volatility
            # Trading bot will read Guardian signal (Phase 2.6)
            
            # Get current state
            state = await self.position_actor.ask("GET_STATE", {})
            
            # Check if we already have positions or pending orders
            has_positions = len(state.get("open_tranches", [])) > 0
            has_pending = state.get("pending_buy") or state.get("pending_sell")
            
            if has_positions:
                log.info(f"✓ Found {len(state['open_tranches'])} existing position(s) - no initial order needed")
                self._initial_order_placed = True
                return
            
            if has_pending:
                log.info("✓ Pending order already exists in bot state - no initial order needed")
                self._initial_order_placed = True
                return
            
            # CRITICAL: Check exchange for existing open orders BEFORE placing new ones
            log.info("🔍 Checking exchange for existing open orders...")
            try:
                exchange_orders = await self.api_client.rest_client.get_open_orders(product_id=self.product_id)
                
                # CRITICAL FIX: Filter by product_id manually (API returns all products)
                if exchange_orders:
                    exchange_orders = [o for o in exchange_orders if o.get('product_id') == self.product_id]
                
                if exchange_orders and len(exchange_orders) > 0:
                    log.warning(f"⚠️  Found {len(exchange_orders)} existing open order(s) on exchange:")
                    human_log.existing_orders_found(len(exchange_orders))  # Human-readable
                    for order in exchange_orders:
                        order_id = order.get('id')
                        side = order.get('side')
                        price = order.get('limit_price')
                        size = order.get('size')
                        order_type = order.get('order_type', 'UNKNOWN')
                        
                        # Convert price to float for formatting (API might return string)
                        try:
                            price_float = float(price) if price else 0
                            log.warning(f"   Order {order_id}: {side} {size} @ ${price_float:,.2f} [type={order_type}]")
                        except (ValueError, TypeError):
                            log.warning(f"   Order {order_id}: {side} {size} @ {price} [type={order_type}]")
                    
                    # Sync the first relevant order to bot state
                    # CRITICAL: Only sync LIMIT orders, NEVER stop/stop-limit/market orders
                    # This prevents interfering with manual stop losses or other manual trades
                    for order in exchange_orders:
                        order_side = order.get('side')
                        order_type = order.get('order_type', '').lower()
                        bracket_order = order.get('bracket_order')  # Bracket orders (SL/TP) have this field
                        stop_order_type = order.get('stop_order_type')  # Stop orders have this field
                        
                        # Log all order details for debugging
                        log.info(f"   📋 Order details: type={order_type}, bracket={bracket_order}, stop_type={stop_order_type}")
                        
                        # Skip non-limit orders (stop, stop-limit, market, etc.)
                        # Skip bracket orders (user's manual stop-loss/take-profit brackets)
                        if order_type != 'limit_order':
                            log.info(f"   ⏭️  Skipping {order_type} order {order.get('id')} - bot only manages plain limit orders")
                            continue
                        
                        if bracket_order:
                            log.info(f"   ⏭️  Skipping bracket order {order.get('id')} - this is a manual SL/TP order")
                            continue
                        
                        if stop_order_type:
                            log.info(f"   ⏭️  Skipping stop order {order.get('id')} (type={stop_order_type}) - manual stop order")
                            continue
                        
                        if (self.mode == "LONG" and order_side == "buy") or (self.mode == "SHORT" and order_side == "sell"):
                            order_id = order.get('id')
                            order_price = order.get('limit_price')
                            
                            # Convert price to float (API returns string)
                            try:
                                order_price_float = float(order_price) if order_price else 0
                            except (ValueError, TypeError):
                                log.error(f"Invalid price format from exchange: {order_price}")
                                continue
                            
                            log.info(f"✅ Syncing existing LIMIT order {order_id} to bot state @ ${order_price_float:,.2f}")
                            
                            if order_side == "buy":
                                await self.position_actor.tell("SET_PENDING_BUY", {
                                    "order_id": order_id,
                                    "price": order_price_float,  # Store as float
                                    "size": order.get("size", self.lot_size),
                                    "timestamp": time.time()
                                })
                            else:
                                await self.position_actor.tell("SET_PENDING_SELL", {
                                    "order_id": order_id,
                                    "price": order_price_float,  # Store as float
                                    "size": order.get("size", self.lot_size),
                                    "timestamp": time.time()
                                })
                            
                            self._initial_order_placed = True
                            log.info("✅ Existing exchange LIMIT order synced - bot will track it")
                            return
                    
                    log.warning("⚠️  Existing orders found but none are bot-managed LIMIT orders - continuing with new order")
                else:
                    log.info("✅ No existing orders on exchange - safe to place new order")
            except Exception as e:
                log.error(f"❌ Failed to check exchange orders: {e}")
                log.warning("⚠️  Proceeding with caution - may result in duplicate orders")
            
            if not self.current_price:
                log.warning("⚠️  Current price not available - cannot place initial order")
                return
            
            # COMPREHENSIVE SAFETY CHECK before initial order
            can_proceed, reason = await self._comprehensive_safety_check("initial order placement")
            if not can_proceed:
                # Log detailed blocking reason prominently
                log.warning("")
                log.warning("=" * 70)
                log.warning("🚫 TRADING BLOCKED AT STARTUP")
                log.warning("=" * 70)
                for line in reason.split('\n'):
                    if line.strip():
                        log.warning(line)
                log.warning("=" * 70)
                log.warning("💡 Bot will start trading automatically when conditions are met")
                log.warning("=" * 70)
                log.warning("")
                
                # Mark as "placed" so entry order check loop runs and shows updates
                self._initial_order_placed = True
                self._last_block_reason = reason
                self._last_safety_block_log = time.time()
                return
            
            # Check if price is within grid bounds (already checked in comprehensive, but log it)
            if not self.grid_calc.is_within_bounds(self.current_price):
                log.warning(f"⚠️  Current price ${self.current_price:,.2f} outside grid bounds")
                log.info(f"   Grid: ${self.grid_calc.lower:,.0f} - ${self.grid_calc.upper:,.0f}")
                log.info("   Waiting for price to enter grid range...")
                return
            
            # Calculate initial entry level
            positions = state.get("open_tranches", [])
            
            if self.mode == "LONG":
                # Check if we already have a pending buy order
                pending_buy = state.get("pending_buy")
                if pending_buy:
                    log.info(f"ℹ️  Pending BUY order already exists: {pending_buy.get('order_id')} @ ${pending_buy.get('price'):,.0f}")
                    return
                
                if not self._should_recalculate_grid_level(self.current_price):
                    log.debug(f"Price hasn't moved enough to recalculate grid level")
                    return
                
                target = self.grid_calc.compute_next_buy_level(positions, current_price=self.current_price)
                
                # Skip recovered grid levels (NOV 20)
                while target and target in self._recovered_grids:
                    log.info(f"🔄 Skipping recovered grid level: ${target:,.0f}")
                    # Find next level below the recovered one
                    target = target - self.grid_calc.step
                    if not self.grid_calc.is_within_bounds(target):
                        target = None
                        break
                
                if target and self.grid_calc.is_within_bounds(target):
                    log.info(f"📍 Placing initial MAKER BUY order @ ${target:,.2f}")
                    log.info(f"   Current market: ${self.current_price:,.2f}")
                    human_log.initial_order_placed("BUY", target)  # Human-readable
                    
                    # Place order via order actor (timeout=20s to allow for retries)
                    result = await self.order_actor.ask("PLACE_BUY", {
                        "price": target,
                        "size": self.lot_size  # Use configured lot size
                    }, timeout=20.0)
                    
                    if result.get("status") == "ok":
                        order_id = result.get("order_id")
                        
                        self._update_last_order_time(target)
                        
                        await self.position_actor.tell("SET_PENDING_BUY", {
                            "order_id": order_id,
                            "price": target,
                            "size": self.lot_size,
                            "timestamp": time.time()
                        })
                        
                        log.info(f"✅ Initial MAKER BUY placed @ ${target:,.2f} (Order: {order_id})")
                        self._initial_order_placed = True
                    else:
                        log.error(f"❌ Failed to place initial order: {result.get('error')}")
                else:
                    log.warning(f"⚠️  No valid buy level available (target={target})")
                    
            else:  # SHORT mode
                # Check if we already have a pending sell order
                pending_sell = state.get("pending_sell")
                if pending_sell:
                    pending_price = pending_sell.get("price")
                    pending_order_id = pending_sell.get("order_id")
                    log.info(f"✅ Already have pending SELL @ ${pending_price:,.2f} (Order: {pending_order_id})")
                    log.info("   Not placing duplicate order - using existing one")
                    human_log.duplicate_order_detected("SELL", pending_price)
                    self._initial_order_placed = True
                    return
                
                # Calculate next sell level above current price
                target = self.grid_calc.compute_next_sell_level(positions, current_price=self.current_price)
                
                # Skip recovered grid levels (NOV 20)
                while target and target in self._recovered_grids:
                    log.info(f"🔄 Skipping recovered grid level: ${target:,.0f}")
                    # Find next level above the recovered one
                    target = target + self.grid_calc.step
                    if not self.grid_calc.is_within_bounds(target):
                        target = None
                        break
                
                if target and self.grid_calc.is_within_bounds(target):
                    log.info(f"📍 Placing initial MAKER SELL order @ ${target:,.2f}")
                    log.info(f"   Current market: ${self.current_price:,.2f}")
                    
                    # Place order via order actor (timeout=20s to allow for retries)
                    result = await self.order_actor.ask("PLACE_SELL", {
                        "price": target,
                        "size": 1
                    }, timeout=20.0)
                    
                    if result.get("status") == "ok":
                        order_id = result.get("order_id")
                        
                        self._update_last_order_time(target)
                        
                        await self.position_actor.tell("SET_PENDING_SELL", {
                            "order_id": order_id,
                            "price": target,
                            "size": self.lot_size,
                            "timestamp": time.time()
                        })
                        
                        log.info(f"✅ Initial MAKER SELL placed @ ${target:,.2f} (Order: {order_id})")
                        self._initial_order_placed = True
                    else:
                        log.error(f"❌ Failed to place initial order: {result.get('error')}")
                else:
                    log.warning(f"⚠️  No valid sell level available (target={target})")
                    
        except Exception as e:
            log.error(f"Error placing initial order: {e}", exc_info=True)
    
    async def _place_grid_order(self, state: Dict, side: str) -> None:
        # CRITICAL: Need current price to calculate and place orders
        if not self.current_price:
            log.debug(f"Cannot place {side} order - current price not available yet")
            return
        
        pending_key = f"pending_{side}"
        if state.get(pending_key):
            return
        
        if len(state["open_tranches"]) >= self.position_actor.max_positions:
            return
        
        positions = state["open_tranches"]
        
        # FIX MAR 2 2026: Pass current_price to prevent placing above market (BUY)
        # or below market (SELL). Without this, compute_next_buy_level defaults to
        # ref - step when there are no positions, which can be above market price,
        # causing post-only orders to be rejected in an infinite loop.
        calc_method = f"compute_next_{side}_level"
        target = getattr(self.grid_calc, calc_method)(positions, current_price=self.current_price)
        
        if not target:
            log.info(f"⚠️  No {side.upper()} target calculated")
            log.info(f"   Current positions: {len(positions)}/{self.position_actor.max_positions}")
            if self.current_price:
                log.info(f"   Current price: ${self.current_price:,.2f}")
            else:
                log.info(f"   Current price: Not available")
            log.info(f"   Grid bounds: ${self.grid_calc.lower:,.0f} - ${self.grid_calc.upper:,.0f}")
            if positions:
                position_prices = [p.get('entry_price', 0) for p in positions]
                log.info(f"   Position levels: {[f'${p:,.0f}' for p in sorted(position_prices)]}")
            return
        
        if not self.grid_calc.is_within_bounds(target):
            log.debug(f"{side.upper()} target ${target:,.2f} is out of bounds ({self.grid_calc.lower} - {self.grid_calc.upper})")
            return
        
        # FIX MAR 2 2026: Post-only safety guard — prevent placing orders that
        # would cross the spread (BUY above market / SELL below market).
        # These get rejected with immediate_execution_post_only and create
        # an infinite retry loop.
        current_price = self.current_price
        if current_price:
            if side == "buy" and target >= current_price:
                log.debug(f"⏭️  Skipping BUY @ ${target:,.0f} — at/above market ${current_price:,.0f} (would cross spread)")
                return
            elif side == "sell" and target <= current_price:
                log.debug(f"⏭️  Skipping SELL @ ${target:,.0f} — at/below market ${current_price:,.0f} (would cross spread)")
                return
        
        if target:
            try:
                self.pre_order_logger.log_decision(
                    side=side,
                    price=target,
                    current_price=self.current_price,
                    current_positions=len(positions),
                    max_positions=self.position_actor.max_positions,
                    grid_step=self.grid_calc.step,
                    reasons=[f"Grid level placement ({self.mode} mode)"]
                )
            except Exception as e:
                log.warning(f"Pre-order logging failed: {e}")
            
            try:
                anomaly_detected = self.anomaly_detector.check_before_order(
                    side=side,
                    price=target,
                    current_price=self.current_price
                )
            except Exception as e:
                log.warning(f"Anomaly detection failed: {e}")
                anomaly_detected = False
            
            if anomaly_detected:
                log.warning(f"⚠️  Anomaly detected before {side.upper()} order @ ${target:,.2f} - proceeding with caution")
            
            action = f"PLACE_{side.upper()}"
            # CRITICAL FIX (Nov 20, 2025): Use separate lot sizes for LONG/SHORT
            if side == "sell":
                size = getattr(self.config.grid.limits, 'short_lot_size', self.lot_size)
            else:
                size = self.lot_size
            
            result = await self.order_actor.ask(action, {
                "price": target,
                "size": size
            }, timeout=20.0)
            
            if result.get("status") == "ok":
                order_id = result.get("order_id")
                
                self._update_last_order_time(target)
                
                await self.position_actor.tell(f"SET_PENDING_{side.upper()}", {
                    "order_id": order_id,
                    "price": target,
                    "size": self.lot_size,
                    "timestamp": time.time()
                })
                
                log.info(f"✅ {side.upper()} order placed @ ${target:,.2f} (Order: {order_id})")
            else:
                # FIX MAR 2 2026: Log error and apply cooldown to prevent rapid retry spam.
                # Without this, failed orders retry on every ticker update (~1-2s).
                error_msg = result.get("error", "unknown")
                log.warning(f"❌ {side.upper()} order FAILED @ ${target:,.2f}: {error_msg}")
                # Apply cooldown even on failure to prevent hammering the exchange
                self._update_last_order_time(target)
    
    async def _check_and_place_entry_order(self) -> None:
        """Check if we should place a new entry order based on current grid state.
        
        CRITICAL SAFETY INTEGRATION:
        - Calls _comprehensive_safety_check() before EVERY order
        - This includes Guardian signal, account loss limits, margin, and volatility
        - If ANY check fails, order is blocked
        - Ensures grid trading respects ALL safety boundaries
        
        JAN 29 2026: Added recovery_in_progress check to prevent conflicts.
        """
        async with self._order_placement_lock:
            try:
                if not self._initial_order_placed or not self.current_price:
                    return
                
                # Check if recovery is in progress - skip normal order placement
                if hasattr(self, 'state_coordinator') and self.state_coordinator.is_recovery_in_progress():
                    log.debug("Skipping normal order placement - recovery in progress")
                    return
                
                # COMPREHENSIVE SAFETY CHECK before placing any order
                can_proceed, reason = await self._comprehensive_safety_check("entry order placement")
                if not can_proceed:
                    # Mark as halted when blocked
                    self._was_halted = True
                    
                    # Log detailed reason on state change or periodically (every 60s)
                    if not hasattr(self, '_last_block_reason') or self._last_block_reason != reason:
                        # Reason changed - log immediately with full detailed message
                        log.warning("")
                        log.warning("=" * 70)
                        log.warning("🚫 TRADING HALTED")
                        log.warning("=" * 70)
                        # reason is already a multi-line detailed message, log it directly
                        for line in reason.split('\n'):
                            if line.strip():
                                log.warning(line)
                        log.warning("=" * 70)
                        log.warning("")
                        self._last_block_reason = reason
                        self._last_safety_block_log = time.time()
                    elif time.time() - getattr(self, '_last_safety_block_log', 0) > 300:
                        # Same reason but 5 minutes passed - brief reminder
                        first_line = reason.split('\n')[0] if '\n' in reason else reason
                        log.info(f"ℹ️  Still blocked: {first_line}")
                        self._last_safety_block_log = time.time()
                    # Silently skip if same reason and logged recently
                    return
                
                # GUARDIAN RESUME - Reset halt flag
                if hasattr(self, '_was_halted') and self._was_halted:
                    log.info("✅ Guardian resumed trading - resuming normal grid operations")
                    self._was_halted = False  # Reset flag
            
                # Price bounds already checked in comprehensive check
                # Volatility already checked in comprehensive check
                
                # Get current state
                state = await self.position_actor.ask("GET_STATE", {})
                
                # Place grid order based on mode
                side = "buy" if self.mode == "LONG" else "sell"
                await self._place_grid_order(state, side)
                        
            except Exception as e:
                log.error(f"Entry check error: {e}", exc_info=True)
    
    # _format_pending_order_info — MOVED to HealthMonitor._format_pending_order_info() (P2.3)
    
    def _log_detailed_grid_status(
        self,
        positions: list,
        pending_buy: Optional[Dict],
        pending_sell: Optional[Dict],
        current_price: float
    ) -> None:
        """
        Log detailed grid status with timeline for each position/loop.
        Shows mode, grid config, and detailed position info.
        """
        from datetime import datetime
        
        # Header with mode and grid configuration
        log.info("=" * 70)
        log.info(f"📊 GRID STATUS REPORT | Mode: {self.mode}")
        log.info(f"   Reference: ${self.grid_calc.ref:,.0f} | Step: ${self.grid_calc.step:,.0f}")
        log.info(f"   Lower: ${self.grid_calc.lower:,.0f} | Upper: ${self.grid_calc.upper:,.0f}")
        log.info(f"   Current Price: ${current_price:,.0f}")
        log.info("-" * 70)
        
        # Pending order info
        pending_order = pending_buy if self.mode == 'LONG' else pending_sell
        order_type = "BUY" if self.mode == 'LONG' else "SELL"
        
        if pending_order:
            pending_price = pending_order.get('price', 0)
            pending_time = pending_order.get('timestamp', 0)
            pending_order_id = pending_order.get('order_id', 'N/A')
            
            if pending_time:
                pending_dt = datetime.fromtimestamp(pending_time)
                time_str = pending_dt.strftime("%H:%M:%S")
            else:
                time_str = "N/A"
            
            distance = abs(current_price - pending_price)
            distance_pct = (distance / current_price * 100) if current_price > 0 else 0
            
            log.info(f"⏳ PENDING {order_type} ORDER:")
            log.info(f"   Price: ${pending_price:,.0f} | Distance: ${distance:,.0f} ({distance_pct:.2f}%)")
            log.info(f"   Order ID: {pending_order_id} | Placed at: {time_str}")
        else:
            log.info(f"⚠️  NO PENDING {order_type} ORDER")
        
        log.info("-" * 70)
        
        # Position details (Loops)
        if positions:
            log.info(f"📈 ACTIVE POSITIONS ({len(positions)} loops):")
            log.info("")
            
            # Sort positions by entry price (lowest first for LONG, highest first for SHORT)
            sorted_positions = sorted(
                positions,
                key=lambda p: p.get('entry_price', 0),
                reverse=(self.mode == 'SHORT')
            )
            
            for idx, pos in enumerate(sorted_positions, 1):
                entry_price = pos.get('entry_price', 0)
                tp_price = pos.get('tp_price', 0)
                entry_time = pos.get('timestamp', 0)
                position_id = pos.get('position_id', 'N/A')
                tp_order_id = pos.get('tp_order_id', 'N/A')
                entry_order_id = pos.get('entry_order_id', 'N/A')
                
                # Calculate PnL
                if self.mode == 'LONG':
                    pnl = current_price - entry_price
                else:
                    pnl = entry_price - current_price
                pnl_pct = (pnl / entry_price * 100) if entry_price > 0 else 0
                
                # Distance to TP
                tp_distance = abs(tp_price - current_price)
                tp_distance_pct = (tp_distance / current_price * 100) if current_price > 0 else 0
                
                # Format entry time
                if entry_time:
                    entry_dt = datetime.fromtimestamp(entry_time)
                    entry_time_str = entry_dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    entry_time_str = "N/A"
                
                # PnL color
                pnl_color = "\033[32m" if pnl > 0 else "\033[31m" if pnl < 0 else "\033[37m"
                
                log.info(f"   Loop {idx}:")
                log.info(f"      Entry: ${entry_price:,.0f} at {entry_time_str}")
                log.info(f"      TP Order: ${tp_price:,.0f} (ID: {tp_order_id})")
                log.info(f"      PnL: {pnl_color}${pnl:,.0f} ({pnl_pct:+.2f}%)\033[0m | Distance to TP: ${tp_distance:,.0f} ({tp_distance_pct:.2f}%)")
                log.info("")
        else:
            log.info("📭 NO ACTIVE POSITIONS")
        
        # Next grid level
        if self.mode == 'LONG':
            next_level = self.fill_processor.calculate_next_grid_level('BUY', current_price)
            if next_level:
                log.info(f"   → Next BUY level: ${next_level:,.0f}")
        else:
            next_level = self.fill_processor.calculate_next_grid_level('SELL', current_price)
            if next_level:
                log.info(f"   → Next SELL level: ${next_level:,.0f}")
        
        log.info("=" * 70)
    
    # Phase 2 methods MOVED to HealthMonitor: update_external_heartbeat, heartbeat_loop,
    # _format_pending_order_info, monitoring_loop (P2.2-P2.4)
    
    async def _fill_polling_fallback_loop(self) -> None:
        """
        CRITICAL FIX (Jan 20, 2026): Fill polling fallback.
        
        Polls exchange for recent fills every 60 seconds as backup for WebSocket.
        This catches fills that were missed due to:
        - WebSocket message queue overflow
        - WebSocket disconnection
        - WebSocket delivery failures
        
        Uses existing fill deduplication (_seen_fill_ids) to prevent double-processing.
        """
        log.info("🔄 Fill polling fallback started - checking every 60 seconds")
        log.info("   This is a safety backup for WebSocket fill notifications")
        
        await asyncio.sleep(30)  # FIX C5: Reduced from 120s to 30s to minimize blind spot at startup
        
        while self._running:
            try:
                # Query recent fills (last 5 minutes) using /v2/fills endpoint
                current_time_us = int(time.time() * 1_000_000)  # Current time in microseconds
                five_min_ago_us = current_time_us - (5 * 60 * 1_000_000)  # 5 minutes ago
                
                recent_fills = await self.api_client.rest_client.get_fills(
                    product_id=self.product_id,
                    start_time=five_min_ago_us
                )
                
                if recent_fills:
                    # Process only fills we haven't seen via WebSocket
                    new_fills_found = 0
                    
                    for fill in recent_fills:
                        # Fill records have 'id' field directly (not order_id)
                        fill_id = str(fill.get('id'))
                        order_id = str(fill.get('order_id'))
                        
                        # FIX C2: Check BOTH fill_id and order_id for consistent deduplication
                        # WebSocket may have stored fill under exchange_fill_id or order-{order_id}
                        already_seen = (
                            fill_id in self._seen_fill_ids or
                            f"fill-{fill_id}" in self._seen_fill_ids or
                            f"order-{order_id}" in self._seen_fill_ids
                        )
                        
                        if not already_seen:
                            # New fill detected! Process it
                            new_fills_found += 1
                            log.warning("=" * 80)
                            log.warning("⚠️  FILL POLLING FALLBACK: Missed fill detected!")
                            log.warning(f"   Fill ID: {fill_id}")
                            log.warning(f"   Order ID: {order_id}")
                            log.warning(f"   Price: ${float(fill.get('price', 0)):,.2f}")
                            log.warning(f"   Side: {fill.get('side', '').upper()}")
                            log.warning(f"   Size: {fill.get('size')}")
                            log.warning("   This fill was NOT received via WebSocket")
                            log.warning("=" * 80)
                            
                            # Create a fill-like object for processing
                            fill_data = {
                                'id': fill_id,
                                'order_id': order_id,
                                'product_id': fill.get('product_id'),
                                'size': fill.get('size'),
                                'price': fill.get('price'),
                                'side': fill.get('side'),
                                'timestamp': fill.get('created_at')
                            }
                            
                            # Process the fill through normal fill handler
                            await self._process_fill(fill_data)
                    
                    if new_fills_found > 0:
                        log.error(f"🚨 Fill polling found {new_fills_found} missed fill(s)")
                    else:
                        log.debug("✅ Fill polling: No missed fills")
                
                # Wait 60 seconds before next poll
                await asyncio.sleep(60)
                
            except Exception as e:
                log.error(f"Fill polling fallback error: {e}")
                await asyncio.sleep(60)  # Continue despite errors
    
    async def _safety_gatekeeper_loop(self) -> None:
        """
        Periodic safety check loop - runs every 5 minutes.
        Also triggered by state changes (via _process_fill).
        """
        log.info("Safety gatekeeper loop started - checking every 5 minutes")
        human_log.monitoring_active()  # Human-readable
        
        while self._running:
            try:
                current_time = time.time()
                
                # Check if 5 minutes (300 seconds) have elapsed since last check
                if current_time - self._last_safety_check_time >= 300:
                    log.info("🔒 Running periodic safety check (5-minute interval)...")
                    
                    # CRITICAL FIX (Jan 20, 2026): Check for unhedged positions
                    # Detects positions without TP orders (missed fills due to WebSocket drops)
                    await self._check_for_unhedged_positions()
                    
                    # Safety limit checking removed - Guardian monitors all risk parameters
                    self._last_safety_check_time = current_time
                
                # Sleep for 30 seconds, then check again
                await asyncio.sleep(30)
                
            except Exception as e:
                log.error(f"Safety gatekeeper error: {e}")
                await asyncio.sleep(60)  # Back off on error
    
    async def _check_for_unhedged_positions(self) -> None:
        """
        CRITICAL FIX (Jan 20, 2026): Check for unhedged positions.
        
        Detects positions that exist on exchange but don't have TP orders.
        This can happen when:
        - WebSocket fill notification is dropped
        - Bot crashes after fill but before placing TP
        - TP order placement fails during Guardian STOP
        """
        try:
            # Get positions from bot memory
            state = await self.position_actor.ask("GET_STATE", {})
            bot_positions = state.get("open_tranches", [])
            
            # Get all open orders from exchange
            open_orders = await self.api_client.list_orders(symbol=self.symbol, states='open')
            
            # Find positions without TP orders
            unhedged_positions = []
            
            for position in bot_positions:
                tp_order_id = position.get("tp_order_id")
                tp_price = position.get("tp_price")
                entry_price = position.get("entry_price")
                
                if not tp_order_id:
                    # Position has no TP order ID - check if TP exists by price
                    tp_exists = any(
                        abs(float(o.get('limit_price', 0)) - tp_price) < 0.01
                        and o.get('reduce_only', False)
                        and o.get('side', '').lower() == ('sell' if self.mode == 'LONG' else 'buy')
                        for o in open_orders
                    )
                    
                    if not tp_exists:
                        unhedged_positions.append({
                            'position_id': position.get('position_id'),
                            'entry_price': entry_price,
                            'tp_price': tp_price,
                            'size': position.get('size')
                        })
            
            if unhedged_positions:
                log.error("=" * 80)
                log.error("⚠️  CRITICAL: UNHEDGED POSITIONS DETECTED")
                log.error(f"   Found {len(unhedged_positions)} position(s) without TP orders")
                log.error("=" * 80)
                
                for pos in unhedged_positions:
                    log.error(f"   Position: Entry=${pos['entry_price']:,.0f}, Expected TP=${pos['tp_price']:,.0f}, Size={pos['size']}")
                    log.error(f"   Position ID: {pos['position_id']}")
                    log.error(f"   ⚠️  RECOMMENDED: Manually place TP order at ${pos['tp_price']:,.0f} (reduce_only=True)")
                
                log.error("=" * 80)
                
                # Log to human logger for visibility
                human_log.error(f"UNHEDGED POSITIONS: {len(unhedged_positions)} positions without TP orders")
            else:
                log.debug("✅ All positions have TP orders")
                
        except Exception as e:
            log.error(f"Error checking for unhedged positions: {e}")
    
    # _guardian_health_monitor_loop — MOVED to GuardianHandler.health_monitor_loop() (P1.8)
    
    # Phase 2 methods MOVED to HealthMonitor: check_memory_usage, check_websocket_health,
    # health_check_loop (P2.5-P2.6)
    
    # _exchange_maintenance_monitor — MOVED to ExchangeSync.exchange_maintenance_monitor() (P3.3)

    # _check_guardian_transitions — MOVED to GuardianHandler.check_transitions() (P1.6)

    # _cancel_pending_entry_orders — MOVED to GuardianHandler.cancel_pending_entries() (P1.7)
    # _resume_grid_trading — MOVED to GuardianHandler.resume_grid() (P1.7)

    async def _process_tp_retry_queue(self) -> None:
        """
        Process TP retry queue - retry failed TP placements.
        
        Runs every 30s as part of health check loop.
        Retries positions in queue that are due for retry.
        """
        try:
            # Get due retries from position actor
            result = await self.position_actor.ask("GET_DUE_RETRIES", {}, timeout=5.0)
            
            due_retries = result.get("retries", [])
            total_queue_size = result.get("total_queue_size", 0)
            
            if not due_retries:
                if total_queue_size > 0:
                    log.debug(f"TP retry queue: {total_queue_size} pending (none due yet)")
                return
            
            log.info(f"⏰ Processing {len(due_retries)} due TP retries (queue: {total_queue_size})")
            
            for retry_entry in due_retries:
                position = retry_entry.get("position", {})
                retry_count = retry_entry.get("retry_count", 0)
                max_retries = retry_entry.get("max_retries", 5)
                
                position_id = position.get("position_id")
                entry_price = position.get("entry_price")
                tp_price = position.get("tp_price")
                size = position.get("size", 1)
                
                # Check if exhausted
                if retry_count >= max_retries:
                    log.critical(f"🚨 TP retry exhausted for position {position_id} @ ${entry_price:,.0f}")
                    log.critical(f"   Retried {retry_count} times - MANUAL INTERVENTION REQUIRED")
                    
                    # Remove from queue
                    await self.position_actor.tell("REMOVE_FROM_RETRY_QUEUE", {
                        "retry_entry": retry_entry
                    })
                    
                    # Send Telegram alert
                    try:
                        from bot.utils.notifier import TelegramNotifier
                        notifier = TelegramNotifier()
                        notifier.send(
                            f"🚨 TP RETRY EXHAUSTED\n\n"
                            f"Position: {position_id}\n"
                            f"Entry: ${entry_price:,.0f}\n"
                            f"TP: ${tp_price:,.0f}\n"
                            f"Retries: {retry_count}/{max_retries}\n\n"
                            f"⚠️ MANUAL TP PLACEMENT REQUIRED"
                        )
                    except Exception:
                        pass  # Telegram not critical
                    
                    continue
                
                # Attempt TP placement
                log.info(f"⏰ Retrying TP placement (attempt {retry_count + 1}/{max_retries})")
                log.info(f"   Position: {position_id} @ ${entry_price:,.0f} → ${tp_price:,.0f}")
                
                try:
                    # Place TP via order actor
                    result = await self.order_actor.ask("PLACE_TP", {
                        "price": tp_price,
                        "size": size,
                        "position_id": position_id
                    }, timeout=15.0)
                    
                    if result.get("status") == "ok":
                        tp_order_id = result.get("order_id")
                        log.info(f"✅ TP retry successful: Order {tp_order_id}")
                        
                        # Update position with TP order ID
                        await self.position_actor.tell("UPDATE_POSITION", {
                            "position_id": position_id,
                            "tp_order_id": tp_order_id,
                            "tp_price": tp_price
                        })
                        
                        # Remove from retry queue
                        await self.position_actor.tell("REMOVE_FROM_RETRY_QUEUE", {
                            "retry_entry": retry_entry
                        })
                        
                        log.info(f"✅ Position {position_id} protected with TP")
                    else:
                        # Retry failed - reschedule
                        log.warning(f"⚠️ TP retry failed: {result.get('error')}")
                        log.warning(f"   Will retry again in 10 seconds")
                        
                        # Reschedule with incremented retry count
                        await self.position_actor.tell("SCHEDULE_TP_RETRY", {
                            "position": position,
                            "retry_count": retry_count,  # Will be incremented in handler
                            "max_retries": max_retries
                        })
                        
                        # Remove old entry
                        await self.position_actor.tell("REMOVE_FROM_RETRY_QUEUE", {
                            "retry_entry": retry_entry
                        })
                
                except Exception as e:
                    log.error(f"❌ TP retry exception: {e}")
                    log.error(f"   Will retry again in 10 seconds")
                    
                    # Reschedule with incremented retry count
                    await self.position_actor.tell("SCHEDULE_TP_RETRY", {
                        "position": position,
                        "retry_count": retry_count,
                        "max_retries": max_retries
                    })
                    
                    # Remove old entry
                    await self.position_actor.tell("REMOVE_FROM_RETRY_QUEUE", {
                        "retry_entry": retry_entry
                    })
        
        except Exception as e:
            log.error(f"TP retry queue processing error: {e}")
    
    # Phase 2: _watchdog_loop MOVED to HealthMonitor.watchdog_loop() (P2.7)
    
    # ========================================================================
    # NOV 20: Reconciliation Action Queue Processor
    # ========================================================================
    
    async def _reconciliation_action_processor(self) -> None:
        """
        Process actions from standalone reconciliation engine.
        Reads action_queue.json and executes corrections.
        """
        action_queue_file = Path("data/reconciliation/action_queue.json")
        
        log.info("📋 Reconciliation action processor started")
        
        while self._running:
            try:
                # Check if action queue exists
                if not action_queue_file.exists():
                    await asyncio.sleep(10)
                    continue
                
                # Load action queue
                with open(action_queue_file) as f:
                    data = json.load(f)
                    actions = data.get("actions", [])
                
                # Process pending actions
                pending_actions = [a for a in actions if a.get("status") == "pending"]
                
                if pending_actions:
                    log.info(f"📋 Processing {len(pending_actions)} reconciliation action(s)")
                
                for action in pending_actions:
                    try:
                        await self._execute_reconciliation_action(action)
                        
                        # Mark as completed
                        action["status"] = "completed"
                        action["completed_at"] = time.time()
                        
                    except Exception as e:
                        log.error(f"Error executing action {action.get('id')}: {e}")
                        action["status"] = "failed"
                        action["error"] = str(e)
                        action["failed_at"] = time.time()
                
                # Write updated queue
                if pending_actions:
                    temp_file = action_queue_file.with_suffix('.tmp')
                    with open(temp_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    temp_file.replace(action_queue_file)
                
                # Wait before next check
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                log.error(f"Reconciliation action processor error: {e}")
                await asyncio.sleep(30)
    
    async def _execute_reconciliation_action(self, action: Dict):
        """Execute a single reconciliation action"""
        action_type = action.get("type")
        action_id = action.get("id")
        
        log.info(f"🔧 Executing {action_type} (ID: {action_id})")
        
        if action_type == "process_missed_fill":
            # Process missed fill
            await self._process_missed_fill(
                order_id=action["order_id"],
                side=action["side"],
                fill_price=action["fill_price"],
                fill_size=action["fill_size"]
            )
            log.info(f"✅ Processed missed fill for order {action['order_id']}")
        
        elif action_type == "place_emergency_tp":
            # Place emergency TP
            position_id = action["position_id"]
            tp_price = action["tp_price"]
            
            # Get position details
            state = await self.position_actor.ask("GET_STATE", {})
            position = None
            for pos in state.get("open_tranches", []):
                if pos.get("position_id") == position_id:
                    position = pos
                    break
            
            if position:
                await self._place_emergency_tp_for_position(position, tp_price)
                log.info(f"✅ Placed emergency TP for position {position_id}")
            else:
                log.warning(f"⚠️  Position {position_id} not found")
        
        elif action_type == "cancel_orphaned_order":
            # Cancel orphaned order
            order_id = action["order_id"]
            
            try:
                result = await self.order_actor.ask("CANCEL_ORDER", {
                    "order_id": order_id
                }, timeout=10.0)
                
                if result.get("status") == "ok":
                    log.info(f"✅ Cancelled orphaned order {order_id}")
                else:
                    log.warning(f"⚠️  Failed to cancel order {order_id}: {result.get('error')}")
            except Exception as e:
                log.error(f"Error cancelling order {order_id}: {e}")
        
        elif action_type == "flag_corrupted_state":
            # Flag corrupted state (log only)
            position_id = action["position_id"]
            field = action["field"]
            log.critical(f"🚨 CORRUPTED STATE: Position {position_id} has invalid {field}")
            log.critical(f"   Manual intervention required!")
        
        else:
            log.warning(f"⚠️  Unknown action type: {action_type}")
    
    async def _place_emergency_tp_for_position(self, position: Dict, tp_price: float):
        """Place emergency TP for a position"""
        try:
            position_id = position.get("position_id")
            size = position.get("size", self.lot_size)
            
            result = await self.order_actor.ask("PLACE_TP", {
                "price": tp_price,
                "size": size,
                "position_id": position_id
            }, timeout=10.0)
            
            if result.get("status") == "ok":
                tp_order_id = result.get("order_id")
                
                # Update position with TP order ID
                await self.position_actor.tell("UPDATE_POSITION_TP", {
                    "position_id": position_id,
                    "tp_order_id": tp_order_id
                })
                
                log.info(f"✅ Emergency TP placed: {tp_order_id} @ ${tp_price:,.0f}")
            else:
                log.error(f"❌ Emergency TP failed: {result.get('error')}")
        
        except Exception as e:
            log.error(f"Error placing emergency TP: {e}")
    
    async def _process_missed_fill(self, order_id: str, side: str, fill_price: float, fill_size: int) -> None:
        """
        Process a fill that was missed by WebSocket.
        Critical reconciliation mechanism.
        """
        try:
            log.critical("🚨 PROCESSING MISSED FILL (RECONCILIATION)")
            log.critical(f"   Order: {order_id}")
            log.critical(f"   Side: {side}")
            log.critical(f"   Price: {fill_price}")
            log.critical(f"   Size: {fill_size}")
            
            # Prepare fill data
            fill_data = {
                "order_id": order_id,
                "fill_price": fill_price,
                "fill_size": fill_size,
                "side": side,
                "is_complete": True,
                "_detected_via": "reconciliation"
            }
            
            # Process via saga (same as regular fill)
            await self._process_fill(fill_data)
            
            log.critical("✅ [RECONCILIATION] Missed fill processed successfully")
            
        except Exception as e:
            log.critical(f"❌ [RECONCILIATION] FAILED to process missed fill: {e}")
            raise
    
    # ── _rest_fallback_monitor_loop → MOVED to ws_lifecycle.rest_fallback_monitor_loop() [P4.6] ──
    # ── _activate_rest_fallback → MOVED to ws_lifecycle._activate_rest_fallback() [P4.7] ──
    # ── _deactivate_rest_fallback → MOVED to ws_lifecycle._deactivate_rest_fallback() [P4.7] ──
    # ── _rest_polling_loop → MOVED to ws_lifecycle._rest_polling_loop() [P4.8] ──
    # ── _poll_price_via_rest → MOVED to ws_lifecycle._poll_price_via_rest() [P4.8] ──
    # ── _poll_pending_orders_via_rest → MOVED to ws_lifecycle._poll_pending_orders_via_rest() [P4.8] ──
    # ── _check_order_status_rest → MOVED to ws_lifecycle._check_order_status_rest() [P4.8] ──

    # ── _reconnect_websocket → MOVED to ws_lifecycle.reconnect_websocket() [P4.5] ──
    
    # _calculate_next_grid_level — MOVED to FillProcessor.calculate_next_grid_level() (P5.3)
    
    # ========================================================================
    # Telegram Notifications (NOV 13)
    # ========================================================================
    
    async def _send_startup_notification(self) -> None:
        """Send Telegram notification when bot starts."""
        try:
            from bot.utils.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            
            if notifier.enabled:
                mode = "TESTNET" if self.testnet else "LIVE"
                message = (
                    f"🚀 ASYNCGRIDBOT STARTED\n\n"
                    f"Mode: {mode}\n"
                    f"Symbol: {self.symbol}\n"
                    f"Grid: ${self.grid_calc.lower:,.0f} - ${self.grid_calc.upper:,.0f}\n"
                    f"Step: ${self.grid_calc.step:,.0f}\n"
                    f"TP Offset: ${self.tp_offset:,.0f}\n"
                    f"Max Positions: {self.max_positions}\n\n"
                    f"Architecture: Actor + Saga\n"
                    f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                notifier.send(message)
                log.info("📱 Sent startup notification")
                human_log.startup_notification_sent()  # Human-readable
        except Exception as e:
            log.debug(f"Could not send startup notification: {e}")
    
    async def _cancel_pending_orders_on_shutdown(self) -> None:
        """
        Cancel pending entry orders on shutdown.
        
        CRITICAL POLICY (NOV 14):
        -------------------------
        On bot shutdown, we must cancel pending ENTRY orders (BUY/SELL) that haven't filled yet.
        These are stored in position_actor.state["pending_buy"] / ["pending_sell"].
        
        WHY?
        - Pending entry orders are speculative - they may fill after bot stops
        - This creates orphaned positions without TP protection
        - Bot won't be running to place TP orders for these fills
        
        WHAT WE PRESERVE:
        - Executed positions (already in open_tranches) - these stay open
        - TP orders (reduce_only=True) - these protect existing positions
        - Manual positions/orders - never touched by bot
        
        WHAT WE CANCEL:
        - Pending BUY orders (LONG mode entry orders)
        - Pending SELL orders (SHORT mode entry orders)
        
        NOTE: We do NOT cancel TP orders because:
        1. They are reduce_only (can only close positions)
        2. They protect existing positions from loss
        3. User may want to keep positions open with TP protection
        """
        try:
            log.info("=" * 70)
            log.info("🧹 SELECTIVE SHUTDOWN CANCELLATION")
            log.info("=" * 70)
            
            # Get ALL pending orders from exchange
            try:
                all_orders = await self.api_client.list_orders(
                    symbol=self.symbol,
                    states="open,pending"
                )
            except Exception as e:
                log.error(f"❌ Failed to fetch orders: {e}")
                return
            
            if not all_orders:
                log.info("✅ No pending orders")
                return
            
            # Separate orders
            entry_orders = []
            tp_orders = []
            
            for order in all_orders:
                side = order.get("side")
                reduce_only = order.get("reduce_only", False)
                oid = order.get("id")
                price = order.get("limit_price")
                
                # Always preserve reduce_only
                if reduce_only:
                    tp_orders.append(order)
                    log.info(f"   ✅ Keep TP: {side.upper()} @ ${price}")
                    continue
                
                # LONG: cancel BUY, keep SELL
                if self.mode == "LONG":
                    if side == "buy":
                        entry_orders.append(order)
                        log.info(f"   ❌ Cancel: BUY @ ${price}")
                    else:
                        tp_orders.append(order)
                        log.info(f"   ✅ Keep: SELL @ ${price}")
                
                # SHORT: cancel SELL, keep BUY
                elif self.mode == "SHORT":
                    if side == "sell":
                        entry_orders.append(order)
                        log.info(f"   ❌ Cancel: SELL @ ${price}")
                    else:
                        tp_orders.append(order)
                        log.info(f"   ✅ Keep: BUY @ ${price}")
            
            log.info("")
            log.info(f"📊 {len(entry_orders)} to cancel, {len(tp_orders)} to keep")
            log.info("")
            
            # Cancel entry orders
            cancelled = 0
            failed = 0
            
            for order in entry_orders:
                oid = order.get("id")
                price = order.get("limit_price")
                side = order.get("side")
                product_id = order.get("product_id", self.product_id)
                
                try:
                    await self.api_client.cancel_order(oid, product_id=product_id)
                    cancelled += 1
                    log.info(f"   ✅ Cancelled {side.upper()} @ ${price}")
                except Exception as e:
                    failed += 1
                    log.error(f"   ❌ Failed {oid}: {e}")
            
            log.info("")
            log.info(f"✅ Cancelled: {cancelled}, Failed: {failed}, Preserved: {len(tp_orders)}")
            log.info("=" * 70)
        
        except Exception as e:
            log.error(f"❌ Error during pending order cancellation on shutdown: {e}")
            import traceback
            log.error(traceback.format_exc())
    
    async def _write_shutdown_signal(self) -> None:
        """Write shutdown signal for reconciliation engine (event-driven cleanup)"""
        try:
            # Get current pending orders from position actor
            # Use direct state access instead of ask() to avoid actor communication issues during shutdown
            state = {}
            if hasattr(self, 'position_actor') and hasattr(self.position_actor, 'state'):
                state = self.position_actor.state
            
            shutdown_signal = {
                "event": "bot_shutdown",
                "timestamp": time.time(),
                "mode": self.mode,  # CRITICAL FIX: Add mode for mode-aware cleanup
                "pending_buy": state.get("pending_buy"),
                "pending_sell": state.get("pending_sell"),
                "reason": "graceful_shutdown",
                "bot_uptime": time.time() - self._start_time if hasattr(self, '_start_time') else 0
            }
            
            signal_file = Path("data/reconciliation/shutdown_signal.json")
            signal_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(signal_file, 'w') as f:
                json.dump(shutdown_signal, f, indent=2)
            
            log.info("✅ Shutdown signal sent to reconciliation engine")
            log.info(f"   Pending BUY: {shutdown_signal['pending_buy'] is not None}")
            log.info(f"   Pending SELL: {shutdown_signal['pending_sell'] is not None}")
            
        except Exception as e:
            log.error(f"Failed to write shutdown signal: {e}")
    
    async def _send_shutdown_notification(self) -> None:
        """Send Telegram notification when bot stops."""
        try:
            from bot.utils.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            
            if notifier.enabled:
                # Get runtime stats
                runtime = time.time() - self._start_time
                
                # Get final state
                state_response = await self.position_actor.ask("GET_STATE", {})
                if state_response and "state" in state_response:
                    state = state_response["state"]
                    positions = len(state.get("open_tranches", []))
                else:
                    positions = 0
                
                message = (
                    f"🛑 ASYNCGRIDBOT STOPPED\n\n"
                    f"Symbol: {self.symbol}\n"
                    f"Runtime: {runtime/3600:.1f}h\n"
                    f"Final Positions: {positions}/{self.max_positions}\n"
                    f"Fills Processed: {self._fills_processed}\n"
                    f"Sagas: {self._sagas_completed} completed, {self._sagas_failed} failed\n\n"
                    f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                notifier.send(message)
                log.info("📱 Sent shutdown notification")
        except Exception as e:
            log.debug(f"Could not send shutdown notification: {e}")
    
    async def emergency_stop(self) -> None:
        """Emergency stop - close all positions and cancel orders."""
        log.critical("EMERGENCY STOP INITIATED")
        
        try:
            # Create emergency saga
            correlation_id = f"emergency-{int(time.time()*1000)}"
            
            saga = await create_emergency_close_all_saga(
                correlation_id=correlation_id,
                position_actor=self.position_actor,
                order_actor=self.order_actor,
                event_store=self.event_store
            )
            
            # Execute with timeout
            success = await asyncio.wait_for(saga.execute(), timeout=60.0)
            
            if success:
                log.info("Emergency stop completed successfully")
            else:
                log.error("Emergency stop failed - manual intervention required")
        
        except Exception as e:
            log.critical(f"Emergency stop error: {e}")
        
        finally:
            await self.stop()
    
    async def _load_recovery_state(self) -> None:
        """
        Initialize recovery state variables.
        Position replay from event store is handled by sync_positions_from_exchange().
        """
        log.info("🧹 Position state will be replayed from event store")
        self._recovery_state = None
        self._recovered_grids = set()
        return
    
    async def place_recovery_order(self, grid_price: float, tag: str) -> Optional[int]:
        """
        Place a recovery market order at the given grid level.
        
        JAN 29 2026: Added to support opportunistic recovery engines.
        
        This method is called by StartupRecoveryEngine and GuardianRecoveryEngine
        to place market orders for missed grid levels.
        
        Examples:
        LONG mode (halt at 100, current at 81, step 5):
        - Grid 95: Market BUY at 81, TP SELL at 100 (95 + 5)
        - Grid 90: Market BUY at 81, TP SELL at 95 (90 + 5)
        - Grid 85: Market BUY at 81, TP SELL at 90 (85 + 5)
        
        SHORT mode (halt at 100, current at 119, step 5):
        - Grid 105: Market SELL at 119, TP BUY at 100 (105 - 5)
        - Grid 110: Market SELL at 119, TP BUY at 105 (110 - 5)
        - Grid 115: Market SELL at 119, TP BUY at 110 (115 - 5)
        
        Args:
            grid_price: The grid level to recover (for TP calculation)
            tag: Order tag for tracking (e.g., "RECOVERY_abc123")
            
        Returns:
            Order ID if successful, None if failed
        """
        try:
            # Determine order side based on mode
            side = "buy" if self.mode == "LONG" else "sell"
            
            # Calculate TP price (grid-aligned, not fill-price based)
            if self.mode == "LONG":
                tp_price = grid_price + self.grid_calc.step
                tp_side = "sell"
            else:  # SHORT mode
                tp_price = grid_price - self.grid_calc.step
                tp_side = "buy"
            
            log.info(f"[Recovery] 🔄 Grid ${grid_price:,.0f} recovery:")
            log.info(f"  → Market {side.upper()} at current price")
            log.info(f"  → TP {tp_side.upper()} at ${tp_price:,.0f} (grid-aligned)")
            log.info(f"  → Size: {self.lot_size}, Tag: {tag}")
            
            # Place market order
            order_result = await self.api_client.place_order(
                product_id=self.product_id,
                size=self.lot_size,
                side=side,
                order_type="market_order",
                client_order_id=tag
            )
            
            if not order_result or not order_result.get("id"):
                log.error(f"[Recovery] Failed to place market order - no order ID returned")
                return None
            
            order_id = order_result["id"]
            log.info(f"[Recovery] ✅ Entry order placed: {order_id}")
            
            # Wait for fill
            await asyncio.sleep(1)
            
            # FIX A1: Get actual fill price for logging, but use grid_price for registration
            actual_fill_price = None
            try:
                order_info = await self.api_client.get_order(str(order_id))
                if order_info:
                    actual_fill_price = float(order_info.get('average_fill_price', 0))
                    if actual_fill_price:
                        slippage = abs(actual_fill_price - grid_price)
                        log.info(f"[Recovery] 📊 Actual fill price: ${actual_fill_price:,.0f} (grid: ${grid_price:,.0f}, slippage: ${slippage:,.0f} bonus)")
            except Exception as e:
                log.debug(f"[Recovery] Could not get fill price: {e}")
            
            # Place TP order (grid-aligned)
            log.info(f"[Recovery] Placing TP {tp_side.upper()} order @ ${tp_price:,.0f}")
            
            tp_tag = f"{tag}_TP"
            tp_order_id = None
            
            tp_result = await self.api_client.place_order(
                product_id=self.product_id,
                size=self.lot_size,
                side=tp_side,
                limit_price=tp_price,
                order_type="limit_order",
                reduce_only=True,
                client_order_id=tp_tag
            )
            
            if tp_result and tp_result.get("id"):
                tp_order_id = tp_result['id']
                log.info(f"[Recovery] ✅ TP order placed: {tp_order_id} @ ${tp_price:,.0f}")
            else:
                log.warning(f"[Recovery] ⚠️ TP order failed but entry succeeded - saga will handle")
            
            # FIX A1: Register position at GRID PRICE (not fill price) with PositionActor
            # This ensures grid alignment is maintained. The difference between fill price
            # and grid price is bonus profit that gets captured when TP fills.
            from uuid import uuid4
            position_id = f"recovery-{tag}-{uuid4().hex[:8]}"
            
            position_data = {
                "position_id": position_id,
                "entry_order_id": str(order_id),
                "entry_price": grid_price,  # GRID PRICE, not fill price
                "actual_entry": actual_fill_price or grid_price,  # Track real fill for PnL
                "tp_price": tp_price,
                "size": self.lot_size,
                "tp_order_id": str(tp_order_id) if tp_order_id else None,
                "recovered": True,
                "recovery_tag": tag
            }
            
            try:
                await self.position_actor.tell("ADD_POSITION", position_data)
                log.info(f"[Recovery] ✅ Position registered at grid ${grid_price:,.0f} (actual fill: ${actual_fill_price or 0:,.0f})")
            except Exception as e:
                log.error(f"[Recovery] ⚠️ Failed to register position: {e}")
            
            # FIX A1: Mark order as processed to prevent duplicate saga processing
            # When the WebSocket fill event arrives for this order, it will be skipped
            self.fill_processor.mark_fill_seen(f"fill-{order_id}")
            self.fill_processor.mark_order_fill_seen(str(order_id))
            # Also mark in FillMonitor
            self.fill_monitor.mark_filled(str(order_id), source="recovery")
            log.info(f"[Recovery] ✅ Order {order_id} marked as processed (saga dedup)")
            
            # Track as recovered
            self._recovered_grids.add(grid_price)
            
            return order_id
            
        except Exception as e:
            log.error(f"[Recovery] Failed to place recovery order: {e}", exc_info=True)
            return None
    
    async def get_open_orders(self) -> List[Dict]:
        """
        Get list of open orders from exchange.
        
        JAN 29 2026: Added to support recovery engine position checks.
        """
        try:
            orders = await self.api_client.get_open_orders()
            return orders if orders else []
        except Exception as e:
            log.error(f"Error getting open orders: {e}")
            return []
    
    # _sync_positions_from_exchange — MOVED to ExchangeSync.sync_positions_from_exchange() (P3.4)

    def _setup_signal_handlers(self) -> None:
        """
        Setup signal handlers for graceful shutdown.
        
        FIX DEC 24: Ignore SIGHUP (terminal hangup) to survive terminal closure.
        Only shutdown on explicit signals (SIGINT/SIGTERM from user/system).
        
        Signal handlers are synchronous, so we set a flag that the main loop checks.
        """
        def signal_handler(sig, frame):
            log.info(f"Received signal {sig} - initiating graceful shutdown")
            self._running = False
            # Don't try to create task from signal handler - it's synchronous
            # The main loop will see _running=False and exit gracefully
        
        # Ignore SIGHUP (terminal hangup) - bot should survive terminal closure
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        
        # Handle shutdown signals
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # kill command
    
    async def _check_missed_grids(self) -> List[float]:
        try:
            current_price = self.current_price
            if not current_price:
                await self.ws_lifecycle.fetch_current_price()
                current_price = self.current_price
            
            if not current_price:
                log.warning("[Recovery] Cannot check missed grids - no current price")
                return []
            
            missed_grids = []
            ref = self.grid_calc.ref
            step = self.grid_calc.step
            
            log.info(f"[Recovery] Checking missed grids: ref=${ref:,.0f}, current=${current_price:,.0f}, step=${step}, mode={self.mode}")
            
            if self.mode == "LONG":
                if current_price < ref:
                    num_steps_below = int((ref - current_price) / step)
                    log.info(f"[Recovery] Price is {num_steps_below} steps below reference")
                    
                    if num_steps_below > 0:
                        num_missed = min(num_steps_below, 3)
                        for i in range(1, num_missed + 1):
                            grid_price = ref - (i * step)
                            if grid_price > current_price:
                                missed_grids.append(grid_price)
                                log.info(f"[Recovery] Found missed grid at ${grid_price:,.0f}")
            else:
                if current_price > ref:
                    num_steps_above = int((current_price - ref) / step)
                    log.info(f"[Recovery] Price is {num_steps_above} steps above reference")
                    
                    if num_steps_above > 0:
                        num_missed = min(num_steps_above, 3)
                        for i in range(1, num_missed + 1):
                            grid_price = ref + (i * step)
                            if grid_price < current_price:
                                missed_grids.append(grid_price)
                                log.info(f"[Recovery] Found missed grid at ${grid_price:,.0f}")
            
            log.info(f"[Recovery] Total missed grids found: {len(missed_grids)}")
            return missed_grids
            
        except Exception as e:
            log.error(f"[Recovery] Error checking missed grids: {e}", exc_info=True)
            return []
    
    async def _execute_recovery(self) -> None:
        try:
            missed_grids = await self._check_missed_grids()
            if not missed_grids:
                log.info("[Recovery] No missed grids to recover")
                return
            
            log.info(f"[Recovery] Executing recovery for {len(missed_grids)} missed grids: {[f'${g:,.0f}' for g in missed_grids]}")
            
            for grid_price in missed_grids:
                try:
                    side = "buy" if self.mode == "LONG" else "sell"
                    tp_price = grid_price + self.grid_calc.step if self.mode == "LONG" else grid_price - self.grid_calc.step
                    
                    log.info(f"[Recovery] Placing recovery {side.upper()} market order at ${grid_price:,.0f} with TP at ${tp_price:,.0f}")
                    
                    order_result = await self.api_client.place_order(
                        product_id=self.product_id,
                        size=self.lot_size,
                        side=side,
                        order_type="market"
                    )
                    
                    if order_result and order_result.get("id"):
                        log.info(f"[Recovery] ✅ Recovery order placed: {order_result['id']}")
                        await asyncio.sleep(2)
                    else:
                        log.error(f"[Recovery] ❌ Failed to place recovery order at ${grid_price:,.0f}")
                        
                except Exception as e:
                    log.error(f"[Recovery] Error placing recovery order at ${grid_price:,.0f}: {e}")
                    continue
            
            log.info("[Recovery] ✅ Recovery execution complete")
            
        except Exception as e:
            log.error(f"[Recovery] Error executing recovery: {e}", exc_info=True)
    
    async def _run_trading_iteration(self) -> None:
        await asyncio.sleep(0.1)
    
    async def _run_reconciliation_loop(self, state_machine) -> None:
        while self._running:
            try:
                await asyncio.sleep(300)
                
                if state_machine.is_recovery_in_progress():
                    log.info("Skipping reconciliation - recovery in progress")
                    continue
                
                log.debug("Running reconciliation check...")
                
            except Exception as e:
                log.error(f"Reconciliation loop error: {e}", exc_info=True)
                await asyncio.sleep(60)


async def main():
    """Main entry point with multi-symbol support (v5.0+, v6.0+)."""
    import sys
    from config.loader import get_api_credentials
    
    # Parse CLI arguments
    if len(sys.argv) > 1:
        # V5.0+: Multi-symbol mode - python async_gridbot.py BTCUSD
        symbol_name = sys.argv[1].upper()
        log.info(f"🎯 Starting bot for {symbol_name} (multi-symbol mode)")
    else:
        # V4.0: Backward compatibility - No argument, use config.bot.symbol
        symbol_name = None
        log.info(f"🎯 Starting bot in v4.0 single-symbol mode")
    
    # Get configuration from YAML
    config = get_config()
    
    # V5.0/V6.0 validation - support both symbols (v5.0) and instances (v6.0)
    has_symbols = hasattr(config, 'symbols') and config.symbols
    has_instances = hasattr(config, 'instances') and config.instances
    
    if symbol_name and not (has_symbols or has_instances):
        log.error(f"❌ Symbol argument provided but config.yaml is v4.0")
        log.error(f"   Run: python scripts/migrate_config_to_multi_symbol.py")
        sys.exit(1)
    
    # V6.0 instance mode - check if symbol exists in instances
    if symbol_name and has_instances:
        # Find instance for this symbol
        found = False
        for inst_name, inst_config in config.instances.items():
            if inst_config.symbol == symbol_name:
                found = True
                break
        
        if not found:
            available = sorted(set(inst.symbol for inst in config.instances.values()))
            log.error(f"❌ Symbol '{symbol_name}' not found in config.yaml instances")
            log.error(f"   Available symbols: {available}")
            sys.exit(1)
    
    # V5.0 symbol mode - check if symbol exists in symbols
    elif symbol_name and has_symbols:
        if symbol_name not in config.symbols:
            available = list(config.symbols.keys())
            log.error(f"❌ Symbol '{symbol_name}' not found in config.yaml symbols")
            log.error(f"   Available symbols: {available}")
            sys.exit(1)
    
    # Get API credentials from secrets/api_keys.env (via centralized loader)
    credentials = get_api_credentials(config.trading_mode)
    api_key = credentials['api_key']
    api_secret = credentials['api_secret']
    
    # Get testnet mode
    testnet = (config.trading_mode == 'demo')
    
    # Create bot with symbol_name (v5.0+) or without (v4.0)
    bot = AsyncGridBot(
        api_key=api_key,
        api_secret=api_secret,
        symbol_name=symbol_name,  # NEW: Multi-symbol support
        testnet=testnet
    )
    
    try:
        # Start bot
        await bot.start()
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received")
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
