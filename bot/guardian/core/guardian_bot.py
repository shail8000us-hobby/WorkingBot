"""
Guardian Bot - SQL-Based Risk Monitoring System

CLEAN ARCHITECTURE - Single Source of Truth:
- Collectors gather data (position, volatility, liquidation)
- Risk Decision Engine analyzes and publishes GO/STOP signals to SQL database
- Guardian Bot reads its OWN signals from database for alerts
- NO duplicate monitoring logic, NO legacy risk checks

Version: 2.0 (SQL-based)
"""
import os
import sys
import time
import signal
import logging
import asyncio
import threading
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.loader import get_config
from bot.guardian.collectors.position_monitor import PositionMonitor
from bot.guardian.collectors.health_tracker import HealthTracker
from bot.capital.equity_tracker import get_equity_tracker

# SQL-based Guardian Signal System
from bot.strategy.modules.event_store import EventStore, EventType
from bot.guardian.engine.risk_decision_engine import GuardianRiskDecisionEngine

# Telepush import with fallback
try:
    from tools.telepush import send_telegram_alert
except ImportError:
    try:
        from bot.utils.telepush import send_telegram_alert
    except ImportError:
        def send_telegram_alert(msg, config):
            """Fallback if telepush not available"""
            pass


# Global shutdown flag
shutdown_requested = False
logger = None  # Will be initialized by setup_logging()


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global shutdown_requested
    if logger:
        logger.info(f"Received signal {signum} - initiating graceful shutdown...")
    else:
        print(f"Received signal {signum} - initiating graceful shutdown...")
    shutdown_requested = True


class GuardianBot:
    """
    Guardian Bot - Clean SQL-Based Architecture
    
    SINGLE RESPONSIBILITY: Monitor risk and publish signals
    
    Architecture:
    1. Data Collectors → Gather market/position data
    2. Risk Decision Engine → Analyzes data, publishes GO/STOP to SQL
    3. Guardian Bot → Reads SQL signals, sends Telegram alerts
    
    NO legacy monitoring loops, NO duplicate risk checks!
    
    Multi-Symbol Support (v5.0):
    - Can be started with --symbol BTCUSD to monitor a specific symbol
    - Each symbol gets its own Guardian process and database
    - Uses symbol-specific config from config.yaml symbols section
    """
    
    VERSION = "2.1-SQL-MULTISYMBOL"
    
    def __init__(self, symbol_name: str = None):
        """
        Initialize Guardian Bot
        
        Args:
            symbol_name: Optional symbol to monitor (e.g., "BTCUSD", "ETHUSD")
                        If provided, monitors only this symbol
                        If None, uses global config (v4.0 single-symbol mode)
        """
        self.base_dir = Path.cwd()
        self.symbol_name = symbol_name  # v5.0 multi-symbol support
        self.config = None
        self.exchange = None
        self.position_monitor = None
        self.health_tracker = None
        self.equity_tracker = None
        self.check_interval = 10
        
        # Liquidation protection monitor
        self.liquidation_monitor = None
        
        # SQL-based Guardian Signal System
        self.event_store = None
        self.risk_decision_engine = None
        self._risk_engine_thread = None
        
        # Alert tracking (prevent spam)
        self._last_signal = None
        self._last_alert_time = 0
        self._alert_cooldown = 300  # 5 minutes between similar alerts
        
        # Initialize logging first
        self.setup_logging()
        
        # Load configuration
        self.load_configuration()
        
        # Setup exchange connection
        self.setup_exchange()
        
        # Initialize components
        self.initialize_components()
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = self.base_dir / 'bot' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        cfg = get_config()
        log_file = log_dir / cfg.logging.guardian_log_file
        log_level = cfg.logging.guardian_log_level.upper()
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        global logger
        logger = logging.getLogger(__name__)
        
        # Suppress noisy library loggers
        for lib in ["urllib3", "requests", "websocket", "ccxt", "asyncio"]:
            logging.getLogger(lib).setLevel(logging.WARNING)
        
        logger.info(f"Logging initialized: {log_file}")
        logger.info("✅ Noisy library loggers suppressed")
    
    def load_configuration(self):
        """Load configuration from YAML"""
        from config.loader import get_api_credentials
        from bot.utils.env_loader import get_mode_display_info
        
        logger.info("Loading configuration from config.yaml...")
        
        # Load YAML configuration
        self.config = get_config()
        logger.info("✅ Loaded config.yaml")
        
        # Load API credentials from secrets/api_keys.env (security best practice)
        credentials = get_api_credentials(self.config.trading_mode)
        if credentials['api_key']:
            os.environ['DELTA_API_KEY'] = credentials['api_key']
            os.environ['DELTA_API_SECRET'] = credentials['api_secret']
            logger.info(f"✅ Loaded API credentials from secrets/api_keys.env")
        else:
            logger.warning("⚠️  API credentials not found in secrets/api_keys.env")
        
        # Display trading mode
        try:
            mode_info = get_mode_display_info()
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"{mode_info['emoji']} GUARDIAN - TRADING MODE: {mode_info['description']}")
            logger.info(f"API URL: {mode_info['api_url']}")
            logger.info(f"Risk Level: {mode_info['risk_level']}")
            logger.info(f"Funds: {mode_info['funds_type']}")
            logger.info("=" * 80)
            logger.info("")
        except Exception as e:
            logger.error(f"❌ Failed to load trading mode: {e}")
            raise
        
        # Extract guardian config
        self.check_interval = self.config.guardian.check_interval
        logger.info(f"✅ Configuration loaded from YAML")
        logger.info(f"Check interval: {self.check_interval}s")
        logger.info(f"Max loss: ₹{self.config.guardian.max_account_loss_inr}")
    
    def setup_exchange(self):
        """Setup exchange connection"""
        import ccxt
        
        logger.info("Setting up exchange connection...")
        
        # Circuit breaker for API protection
        from bot.safety.circuit_breaker import CircuitBreaker
        circuit_breaker = CircuitBreaker(
            name='delta_api',
            failure_threshold=3,
            timeout=60,
            half_open_max_calls=2
        )
        logger.info(f"Circuit Breaker initialized for Delta API (threshold=3, timeout=60s)")
        
        # Initialize exchange
        # Get API credentials from environment (set by load_configuration)
        api_key = os.getenv('DELTA_API_KEY')
        api_secret = os.getenv('DELTA_API_SECRET')
        
        self.exchange = ccxt.delta({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'rateLimit': 100,
            'urls': {
                'api': {
                    'public': self.config.api.live.base_url if self.config.trading_mode == 'live' else self.config.api.demo.base_url,
                    'private': self.config.api.live.base_url if self.config.trading_mode == 'live' else self.config.api.demo.base_url,
                }
            },
            'options': {
                'defaultType': 'future',
            }
        })
        
        # Test connection
        balance = self.exchange.fetch_balance()
        logger.info(f"✅ Exchange connected: Delta India")
        logger.info(f"Account balance fetched successfully")
    
    def initialize_components(self):
        """Initialize all guardian components"""
        logger.info("Initializing components...")
        
        # Data collectors
        self.position_monitor = PositionMonitor(self.exchange, self.config)
        self.health_tracker = HealthTracker(self.config, self.base_dir)
        
        # RSI collector (Layer 6) - with multi-symbol support
        try:
            from bot.guardian.collectors.rsi_collector import RSICollector
            self.rsi_collector = RSICollector(self.exchange, self.config, symbol_name=self.symbol_name)
            symbol_info = f" for {self.symbol_name}" if self.symbol_name else ""
            logger.info(f"✅ RSI Collector initialized (Layer 6){symbol_info}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize RSI collector: {e}")
            logger.debug(f"Error details: {e}", exc_info=True)
            self.rsi_collector = None
        
        # Liquidation protection
        if getattr(self.config.guardian, 'liquidation_protection_enabled', True):
            try:
                from bot.liquidation.integrated_monitor import IntegratedLiquidationMonitor
                
                logger.info("🛡️  Initializing liquidation protection...")
                
                # IntegratedLiquidationMonitor takes config and creates its own DeltaClient
                # It loads API credentials from environment variables
                self.liquidation_monitor = IntegratedLiquidationMonitor(
                    config=self.config
                )
                logger.info("✅ Integrated Liquidation Monitor initialized")
                logger.info("✅ Liquidation protection active in Guardian")
            except Exception as e:
                logger.error(f"❌ Failed to start liquidation monitor: {e}")
                logger.debug(f"Error details: {e}", exc_info=True)
                self.liquidation_monitor = None
        
        # Equity tracker
        self.equity_tracker = get_equity_tracker()
        
        # ✅ SQL-BASED GUARDIAN SIGNAL SYSTEM
        logger.info("💾 Initializing Guardian Signal System (SQL-based)...")
        
        # Initialize EventStore (SQL database)
        # Use symbol-specific database if in multi-symbol mode (v5.0/v6.0)
        # Otherwise use global mode (v4.0)
        if self.symbol_name:
            # v6.0+ multi-instance mode - get symbol config from instances
            symbol_config = None
            if hasattr(self.config, 'instances') and self.config.instances:
                # Try to find instance for this symbol
                for inst_name, inst_config in self.config.instances.items():
                    if inst_config.symbol == self.symbol_name:
                        symbol_config = inst_config
                        break
            # Fallback to v5.0 symbols section if it exists
            elif hasattr(self.config, 'symbols') and self.config.symbols:
                symbol_config = self.config.symbols.get(self.symbol_name)
            
            mode = symbol_config.mode.value if symbol_config and hasattr(symbol_config.mode, 'value') else (symbol_config.mode if symbol_config else self.config.bot.mode)
            db_name = f"bot_events_{self.symbol_name}_{mode}.db"
            logger.info(f"🔧 Multi-symbol mode: Monitoring {self.symbol_name} ({mode})")
        else:
            # v4.0 single-symbol mode
            mode = self.config.bot.mode
            db_name = f"bot_events_{mode}.db"
        
        db_path = self.base_dir / 'data' / db_name
        self.event_store = EventStore(str(db_path))
        logger.info(f"✅ EventStore initialized: {db_path}")
        
        # Initialize Risk Decision Engine
        self.risk_decision_engine = GuardianRiskDecisionEngine(self.event_store)
        logger.info("✅ Guardian Risk Decision Engine initialized")
        
        # Inject data collectors into risk engine
        volatility_collector = self._get_volatility_collector()
        self.risk_decision_engine.set_components(
            volatility_collector=volatility_collector,
            position_monitor=self.position_monitor,
            liquidation_monitor=self.liquidation_monitor,
            rsi_collector=self.rsi_collector
        )
        logger.info("✅ Risk engine components injected (volatility + position monitor + liquidation monitor + RSI collector)")
        logger.info("📡 Guardian will publish signals to database every 5 seconds")
        logger.info("🔄 Config file watcher active - will detect WebUI parameter changes")
        
        # Create PID file
        pid_file = self.base_dir / '.guardian.pid'
        pid_file.write_text(str(os.getpid()))
        logger.info(f"PID file created: {pid_file}")
        
        logger.info("✅ All components initialized")
    
    def _get_volatility_collector(self):
        """Get or create volatility collector"""
        try:
            from bot.volatility.delta_volatility_collector import DeltaVolatilityCollector
            
            # Create new instance with db_path
            # DeltaVolatilityCollector has its own defaults for API base URL and symbol
            db_path = str(self.base_dir / 'data' / 'volatility.db')
            collector = DeltaVolatilityCollector(db_path=db_path)
            logger.info(f"✅ Volatility collector initialized: {db_path}")
            return collector
        except Exception as e:
            logger.error(f"Failed to initialize volatility collector: {e}")
            logger.debug(f"Error details: {e}", exc_info=True)
            return None
    
    def send_alert(self, message: str, urgent: bool = False):
        """Send Telegram alert"""
        try:
            # Check cooldown
            current_time = time.time()
            if not urgent and (current_time - self._last_alert_time) < self._alert_cooldown:
                logger.debug(f"Alert cooldown active - skipping non-urgent alert")
                return
            
            prefix = "🚨 URGENT: " if urgent else "📊 Guardian Alert: "
            send_telegram_alert(prefix + message, self.config)
            self._last_alert_time = current_time
            logger.info(f"✅ Alert sent: {message[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    async def run(self):
        """Main Guardian loop - Read SQL signals and send alerts"""
        logger.info("=" * 70)
        logger.info("🛡️ Guardian Bot v{} Starting...".format(self.VERSION))
        logger.info("=" * 70)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # SIGUSR1 for config reload (hot reload)
        def reload_config_handler(signum, frame):
            logger.info("📝 SIGUSR1 received - Triggering config reload...")
            if hasattr(self, 'risk_engine') and self.risk_engine:
                self.risk_engine._on_config_changed()
        
        signal.signal(signal.SIGUSR1, reload_config_handler)
        
        # Start Risk Decision Engine in background
        logger.info("")
        logger.info("=" * 70)
        logger.info("🔄 Starting monitoring loop...")
        logger.info("=" * 70)
        
        # Start risk engine in separate thread
        self._risk_engine_thread = threading.Thread(
            target=self._run_risk_engine_sync,
            daemon=True,
            name="GuardianRiskEngine"
        )
        self._risk_engine_thread.start()
        logger.info("✅ Guardian Risk Decision Engine running in background")
        logger.info("📡 Publishing GO/STOP signals to database every 5s")
        
        # Give risk engine time to publish first signal
        await asyncio.sleep(2)
        
        # Main loop: Read signals from database and send alerts
        while not shutdown_requested:
            try:
                # Read latest signal from OUR OWN database
                signal_data = self._read_latest_signal()
                
                if signal_data:
                    # Check if signal changed
                    current_signal = signal_data['signal']
                    
                    if self._last_signal != current_signal:
                        # Signal changed - send alert
                        self._handle_signal_change(signal_data)
                        self._last_signal = current_signal
                
                # Update health file
                self._update_health_status(signal_data)
                
                # Store PnL history to SQL database (for WebUI chart)
                self._store_pnl_history()
                
                # Sleep until next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(5)
        
        logger.info("=" * 70)
        logger.info("🛡️ Guardian Bot shutting down...")
        logger.info("=" * 70)
        
        # Cleanup
        self.cleanup()
    
    def _run_risk_engine_sync(self):
        """Run risk engine in background thread (blocking asyncio loop)"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            logger.info("🚀 Starting continuous risk monitoring (5s interval)")
            loop.run_until_complete(self.risk_decision_engine.run_continuous_monitoring())
        except Exception as e:
            logger.error(f"Risk engine crashed: {e}", exc_info=True)
        finally:
            loop.close()
    
    def _read_latest_signal(self) -> Optional[Dict]:
        """
        Read latest Guardian signal from database
        
        Returns:
            Dict with signal data or None
        """
        try:
            events = self.event_store.get_events_by_type(
                [EventType.GUARDIAN_SIGNAL_GO, EventType.GUARDIAN_SIGNAL_STOP],
                limit=1
            )
            
            if not events:
                return None
            
            latest = events[0]
            return {
                'signal': 'GO' if latest.event_type == EventType.GUARDIAN_SIGNAL_GO else 'STOP',
                'reason': latest.data.get('reason', 'Unknown'),
                'timestamp': latest.timestamp,
                'details': latest.data.get('details', {})
            }
        except Exception as e:
            logger.error(f"Failed to read signal from database: {e}")
            return None
    
    def _handle_signal_change(self, signal_data: Dict):
        """Handle signal state change and send alert"""
        signal = signal_data['signal']
        reason = signal_data['reason']
        details = signal_data['details']
        
        if signal == 'STOP':
            # Trading halted
            alert_msg = (
                f"🔴 TRADING HALTED\n\n"
                f"Reason: {reason}\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
            )
            
            # Add details
            if 'iv' in details:
                alert_msg += f"IV: {details['iv']:.1f}\n"
            if 'rv' in details:
                alert_msg += f"RV: {details['rv']:.1f}\n"
            if 'spread' in details:
                alert_msg += f"Spread: {details['spread']}\n"
            if 'pnl_inr' in details:
                alert_msg += f"PnL: ₹{details['pnl_inr']:,.0f}\n"
            
            alert_msg += "\n⚠️ Trading bot will pause until conditions improve"
            
            self.send_alert(alert_msg, urgent=True)
            logger.warning(f"🔴 Signal: STOP - {reason}")
            
        else:
            # Trading allowed
            alert_msg = (
                f"🟢 TRADING RESUMED\n\n"
                f"All safety checks passed\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"Trading bot can resume operations"
            )
            
            self.send_alert(alert_msg, urgent=False)
            logger.info(f"🟢 Signal: GO - All clear")
    
    def _update_health_status(self, signal_data: Optional[Dict]):
        """Update health status file with position and liquidation metrics"""
        try:
            # Get position and liquidation metrics from monitor_cycle
            monitoring_result = None
            if hasattr(self, 'position_monitor') and self.position_monitor:
                try:
                    monitoring_result = self.position_monitor.monitor_cycle()
                except Exception as e:
                    logger.debug(f"Could not get monitor_cycle data: {e}")
            
            # Base health data
            health_data = {
                'guardian_version': self.VERSION,
                'last_check': datetime.now().isoformat(),
                'signal': signal_data['signal'] if signal_data else 'UNKNOWN',
                'reason': signal_data['reason'] if signal_data else 'No signal',
                'check_interval': self.check_interval,
                'status': 'running',
                'pid': os.getpid()
            }
            
            # Add position and liquidation metrics if available
            if monitoring_result:
                health_data['positions'] = {
                    'count': len(monitoring_result.get('positions', [])),
                    'current_price': monitoring_result.get('current_price'),
                    'total_pnl_inr': monitoring_result.get('total_summary', {}).get('total_pnl_inr', 0),
                }
                
                # Add liquidation metrics (Delta Exchange India improvements)
                health_data['liquidation'] = {
                    'distance': monitoring_result.get('liquidation_distance', 100.0),
                    'critical': monitoring_result.get('liquidation_critical', False),
                    'warning': monitoring_result.get('liquidation_warning', False),
                    'details_count': len(monitoring_result.get('liquidation_details', [])),
                }
                
                # Add bankruptcy distance if available
                if hasattr(self.position_monitor, 'get_bankruptcy_distance'):
                    try:
                        health_data['liquidation']['bankruptcy_distance'] = self.position_monitor.get_bankruptcy_distance()
                    except Exception:
                        pass
            
            self.health_tracker.update_health_data(health_data)
        except Exception as e:
            logger.error(f"Failed to update health status: {e}")
    
    def _store_pnl_history(self):
        """Store PnL history to SQL database for WebUI chart"""
        try:
            # Use liquidation_monitor for consistent PnL values (same source as risk engine)
            if hasattr(self, 'liquidation_monitor') and self.liquidation_monitor:
                status = self.liquidation_monitor.get_status()
                total_pnl_inr = status.get('total_unrealized_pnl', 0)  # UPNL in INR
                position_count = status.get('total_positions', 0)
            else:
                # Fallback to position_monitor if liquidation_monitor not available
                monitoring_result = self.position_monitor.monitor_cycle()
                
                if not monitoring_result:
                    logger.debug("No monitoring_result from monitor_cycle()")
                    return
                
                summary = monitoring_result.get('total_summary', {})
                total_pnl_inr = summary.get('total_pnl_inr', 0)
                position_count = summary.get('position_count', 0)
            
            import sqlite3
            db_path = self.base_dir / 'bot' / 'state' / 'events.db'
            
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pnl_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_pnl_inr REAL NOT NULL,
                    position_count INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                INSERT INTO pnl_history (timestamp, total_pnl_inr, position_count)
                VALUES (?, ?, ?)
            ''', (datetime.now().isoformat(), total_pnl_inr, position_count))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"PnL history stored: ₹{total_pnl_inr:.2f}, {position_count} positions")
            
        except Exception as e:
            logger.debug(f"Error storing PnL history: {e}")
    
    def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up resources...")
        
        # Stop risk engine
        if self.risk_decision_engine:
            try:
                if hasattr(self.risk_decision_engine, 'config_observer'):
                    self.risk_decision_engine.config_observer.stop()
                logger.info("✅ Risk engine stopped")
            except Exception as e:
                logger.error(f"Error stopping risk engine: {e}")
        
        # Remove PID file
        try:
            pid_file = self.base_dir / '.guardian.pid'
            if pid_file.exists():
                pid_file.unlink()
                logger.info("✅ PID file removed")
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")
        
        logger.info("✅ Cleanup complete")


def main():
    """Main entry point with v6.0 multi-instance CLI support
    
    V6.0 ARCHITECTURE: Instance = Symbol + Mode
    
    Examples:
      python start_guardian.py --instance BTCUSD_LONG   # Monitor BTCUSD LONG instance
      python start_guardian.py --instance BTCUSD_SHORT  # Monitor BTCUSD SHORT instance
      python start_guardian.py -i ETHUSD_LONG          # Short form
      python start_guardian.py --symbol BTCUSD         # Legacy v5.0 mode
    """
    import argparse
    from config.loader import get_instance_config, get_all_instances, make_instance_name
    
    parser = argparse.ArgumentParser(
        description='Guardian Bot - Risk Monitoring System (v6.0 Multi-Instance)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
V6.0 Instance-Centric Architecture:
  Instance = Symbol + Mode (e.g., BTCUSD_LONG, BTCUSD_SHORT)
  
  Each instance has its own RSI thresholds:
  - LONG: stops at RSI <= 30 (oversold)
  - SHORT: stops at RSI >= 70 (overbought)

Examples:
  python start_guardian.py --instance BTCUSD_LONG   Monitor BTCUSD LONG instance
  python start_guardian.py --instance BTCUSD_SHORT  Monitor BTCUSD SHORT instance
  python start_guardian.py -i ETHUSD_LONG           Short form

Legacy (v5.0):
  python start_guardian.py --symbol BTCUSD          Uses mode from config
        '''
    )
    parser.add_argument(
        '--instance', '-i',
        type=str,
        default=None,
        help='Instance to monitor (e.g., BTCUSD_LONG, BTCUSD_SHORT). Format: SYMBOL_MODE'
    )
    parser.add_argument(
        '--symbol', '-s',
        type=str,
        default=None,
        help='[LEGACY] Symbol to monitor. Uses mode from config. Prefer --instance.'
    )
    
    args = parser.parse_args()
    
    # Resolve instance name
    instance_name = None
    symbol_name = None
    
    if args.instance:
        instance_name = args.instance.upper()
        # Parse symbol from instance name
        parts = instance_name.rsplit('_', 1)
        if len(parts) == 2:
            symbol_name = parts[0]
    elif args.symbol:
        # Legacy mode: find instance for symbol
        symbol_name = args.symbol.upper()
        config = get_config()
        if config.instances:
            for name, inst in config.instances.items():
                if inst.symbol == symbol_name and inst.enabled:
                    instance_name = name
                    print(f"⚠️  Legacy mode: Using instance {instance_name} for symbol {symbol_name}")
                    break
        if not instance_name and config.symbols and symbol_name in config.symbols:
            mode = config.symbols[symbol_name].mode.value
            instance_name = make_instance_name(symbol_name, mode)
            print(f"⚠️  Legacy mode: Constructed instance {instance_name}")
    else:
        # No arguments - use first enabled instance
        enabled = get_all_instances(enabled_only=True)
        if enabled:
            instance_name = list(enabled.keys())[0]
            symbol_name = enabled[instance_name].symbol
            print(f"📌 No instance specified, using: {instance_name}")
    
    try:
        guardian = GuardianBot(symbol_name=symbol_name)
        # Store instance_name for future use
        guardian.instance_name = instance_name
        asyncio.run(guardian.run())
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt - shutting down...")
    except Exception as e:
        if logger:
            logger.critical(f"Fatal error: {e}", exc_info=True)
        else:
            print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

