"""
Guardian Bot - Always-On Safety Monitor

Main entry point for the Guardian Bot.
Monitors open positions 24/7 and enforces risk limits.
Auto-closes positions if loss exceeds thresholds.
"""
import os
import sys
import time
import signal
import logging
from pathlib import Path
from typing import Dict, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.loader import get_config
from bot.guardian.position_monitor import PositionMonitor
from bot.guardian.risk_enforcer import RiskEnforcer
# Emergency actions now handled by centralized emergency kill system
from bot.emergency_kill import emergency_kill_all
from bot.guardian.health_tracker import HealthTracker
from bot.capital.equity_tracker import get_equity_tracker
from bot.utils.colors import Colors

# SQL-based Guardian Signal System (Phase 1)
from bot.strategy.modules.event_store import EventStore
from bot.guardian.risk_decision_engine import GuardianRiskDecisionEngine

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
    """Main Guardian Bot class"""
    
    VERSION = "1.0.0"
    
    def __init__(self):
        """Initialize Guardian Bot"""
        self.base_dir = Path.cwd()
        self.config = {}
        self.exchange = None
        self.position_monitor = None
        self.risk_enforcer = None
        self.emergency_actions = None
        self.health_tracker = None
        self.equity_tracker = None
        self.check_interval = 10
        self._last_equity_snapshot_time = 0
        
        # Liquidation protection monitors
        self.margin_monitor = None
        self.distance_monitor = None
        self.mtm_tracker = None
        
        # SQL-based Guardian Signal System (Phase 1)
        self.event_store = None
        self.risk_decision_engine = None
        self._risk_engine_thread = None
        
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
        
        # Suppress noisy library loggers (same as main bot)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("websocket").setLevel(logging.WARNING)
        logging.getLogger("ccxt").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        
        logger.info(f"Logging initialized: {log_file}")
        logger.info("✅ Noisy library loggers suppressed")
    
    def load_configuration(self):
        """Load configuration from YAML"""
        from dotenv import load_dotenv
        from bot.utils.env_loader import load_trading_mode_config, get_mode_display_info
        
        logger.info("Loading configuration from config.yaml...")
        
        # Load API credentials from secrets (security best practice)
        secrets_path = self.base_dir / 'secrets' / 'api_keys.env'
        if secrets_path.exists():
            load_dotenv(secrets_path, verbose=False)
            logger.info(f"✅ Loaded API credentials from {secrets_path}")
        
        # Load YAML configuration
        cfg = get_config()
        logger.info("✅ Loaded config.yaml")
        
        # Load and configure trading mode
        try:
            trading_mode = load_trading_mode_config()
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
        
        # Convert YAML config to flat dict for backward compatibility with existing code
        def flatten_config(data, prefix=''):
            """Flatten nested config to ENV-style keys"""
            flat = {}
            for key, value in data.items():
                full_key = f"{prefix}_{key}".upper() if prefix else key.upper()
                if isinstance(value, dict):
                    flat.update(flatten_config(value, full_key))
                elif isinstance(value, (list, tuple)):
                    # Skip lists for now
                    pass
                else:
                    flat[full_key] = str(value) if value is not None else ''
            return flat
        
        # Create flattened config dict for backward compatibility
        self.config = flatten_config(cfg.model_dump())
        
        # Add unprefixed keys for sections that need them (backward compatibility)
        # liquidation_protection values without LIQUIDATION_PROTECTION_ prefix
        if hasattr(cfg, 'liquidation_protection'):
            lp = cfg.liquidation_protection.model_dump()
            for key, value in lp.items():
                unprefixed_key = key.upper()
                if value is not None and not isinstance(value, (dict, list)):
                    self.config[unprefixed_key] = str(value)
        
        # guardian values without GUARDIAN_ prefix (some code expects both)
        if hasattr(cfg, 'guardian'):
            g = cfg.guardian.model_dump()
            for key, value in g.items():
                unprefixed_key = key.upper()
                if value is not None and not isinstance(value, (dict, list)):
                    self.config[unprefixed_key] = str(value)
        
        # Add API credentials from environment
        self.config['DELTA_API_KEY'] = os.getenv('DELTA_API_KEY')
        self.config['DELTA_API_SECRET'] = os.getenv('DELTA_API_SECRET')
        self.config['TELEGRAM_BOT_TOKEN'] = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.config['TELEGRAM_CHAT_ID'] = os.getenv('TELEGRAM_CHAT_ID', '')
        
        # Guardian-specific settings from YAML
        self.check_interval = cfg.guardian.check_interval
        
        # Hot reload tracking for risk parameters
        self._last_risk_check = 0
        self._last_risk_params = {
            'max_loss': cfg.guardian.max_account_loss_inr,
            'check_interval': self.check_interval
        }
        
        # Check if guardian is enabled
        if not cfg.guardian.enabled:
            logger.warning("⚠️ guardian.enabled=false in config.yaml!")
            logger.warning("Guardian will start anyway (manual start)")
        
        logger.info(f"✅ Configuration loaded from YAML")
        logger.info(f"Check interval: {self.check_interval}s")
        logger.info(f"Max loss: ₹{cfg.guardian.max_account_loss_inr}")
    
    def setup_exchange(self):
        """Initialize exchange connection"""
        logger.info("Setting up exchange connection...")
        
        # Use our DeltaClient instead of ccxt.delta directly
        from bot.api.delta_client import DeltaClient
        
        self.exchange = DeltaClient()
        logger.info(f"✅ DeltaClient initialized: {self.exchange.base}")
        
        # For compatibility with existing code, also set up ccxt client
        import ccxt
        
        api_key = self.config.get('DELTA_API_KEY')
        api_secret = self.config.get('DELTA_API_SECRET')
        
        if not api_key or not api_secret:
            raise ValueError("Missing DELTA_API_KEY or DELTA_API_SECRET")
        
        self.ccxt_exchange = ccxt.delta({
            'apiKey': api_key,
            'secret': api_secret,
            'urls': {
                'api': {
                    'public': self.config.get('DELTA_PUBLIC_BASE_URL', 'https://api.india.delta.exchange'),
                    'private': self.config.get('DELTA_PRIVATE_BASE_URL', 'https://api.india.delta.exchange'),
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
        
        self.position_monitor = PositionMonitor(self.exchange, self.config)
        self.risk_enforcer = RiskEnforcer(self.config)
        # Emergency actions now use centralized system
        # self.emergency_actions = EmergencyActions(self.exchange, self.config, self.base_dir)
        self.health_tracker = HealthTracker(self.config, self.base_dir)
        
        # ✅ FIX #11: Initialize IP monitoring for Guardian
        # Ensures Guardian can detect IP changes and alert on API connectivity issues
        try:
            from bot.network.ip_monitor import IPMonitor
            
            # Only enable if main bot has IP monitoring enabled
            ip_monitor_enabled = self.config.get('IP_MONITOR_ENABLED', 'true').lower() == 'true'
            
            if ip_monitor_enabled:
                logger.info("🌐 Initializing IP monitoring for Guardian...")
                self.ip_monitor = IPMonitor(
                    check_interval=300,  # Check every 5 minutes
                    alert_callback=self._handle_ip_change
                )
                self.ip_monitor.start()
                logger.info("✅ Guardian IP monitoring active")
            else:
                self.ip_monitor = None
                logger.info("🌐 IP monitoring disabled in config")
        except ImportError:
            logger.warning("⚠️ IP monitoring module not available")
            self.ip_monitor = None
        except Exception as e:
            logger.warning(f"⚠️ IP monitoring initialization failed: {e}")
            self.ip_monitor = None
        
        # Initialize liquidation protection monitors FIRST (needed by equity tracker)
        if self.config.get('LIQUIDATION_PROTECTION_ENABLED', 'true').lower() == 'true':
            try:
                from bot.liquidation.integrated_monitor import IntegratedLiquidationMonitor
                
                logger.info("🛡️  Initializing liquidation protection...")
                
                # Create a simple exchange wrapper for the monitors
                class ExchangeWrapper:
                    def __init__(self, exchange):
                        self.exchange = exchange
                    
                    def fetch_portfolio_margin(self):
                        """Fetch portfolio margin from Delta Exchange"""
                        try:
                            # Delta Exchange API endpoint
                            balance = self.exchange.fetch_balance()
                            info = balance.get('info', {})
                            
                            # Delta returns data in result array
                            if 'result' in info and len(info['result']) > 0:
                                return info['result'][0]
                            
                            # Fallback to root info
                            return info
                        except Exception as e:
                            logger.error(f"Error fetching portfolio margin: {e}")
                            return {}
                    
                    def fetch_positions(self):
                        """Fetch open positions"""
                        return self.exchange.fetch_positions()
                    
                    def fetch_open_orders(self):
                        """Fetch open orders"""
                        return self.exchange.fetch_open_orders()
                    
                    def cancel_order(self, order_id):
                        """Cancel an order"""
                        return self.exchange.cancel_order(order_id)
                    
                    def cancel_all_orders(self):
                        """Cancel all orders"""
                        return self.exchange.cancel_all_orders()
                    
                    def place_market_order(self, symbol, side, size, reduce_only=False):
                        """Place market order"""
                        params = {'reduce_only': reduce_only} if reduce_only else {}
                        return self.exchange.create_order(symbol, 'market', side, size, params=params)
                
                ex_wrapper = ExchangeWrapper(self.exchange)
                
                # Use integrated liquidation monitor instead of separate components
                self.liquidation_monitor = IntegratedLiquidationMonitor(config=self.config)
                self.margin_monitor = self.liquidation_monitor
                self.distance_monitor = self.liquidation_monitor
                self.mtm_tracker = self.liquidation_monitor
                
                logger.info("✅ Liquidation protection active in Guardian")
                logger.info(f"   Integrated liquidation monitor initialized")
                
            except Exception as e:
                logger.warning(f"⚠️  Liquidation protection init failed: {e}")
                self.margin_monitor = None
                self.distance_monitor = None
                self.mtm_tracker = None
                self.liquidation_monitor = None
        
        # Initialize equity tracker with liquidation monitor for real-time data
        self.equity_tracker = get_equity_tracker(self.base_dir, self.liquidation_monitor)
        
        # ===== SQL-BASED GUARDIAN SIGNAL SYSTEM (Phase 1) =====
        # Initialize EventStore (same database as trading bot)
        logger.info("💾 Initializing Guardian Signal System (SQL-based)...")
        try:
            db_path = self.base_dir / 'gridbot_events.db'
            self.event_store = EventStore(str(db_path))
            logger.info(f"✅ EventStore initialized: {db_path}")
            
            # Initialize Risk Decision Engine
            self.risk_decision_engine = GuardianRiskDecisionEngine(self.event_store)
            logger.info("✅ Guardian Risk Decision Engine initialized")
            
            # Inject dependencies into risk engine
            # Note: We'll need to get the volatility collector reference
            try:
                from bot.volatility.delta_volatility_collector import get_collector
                vol_collector = get_collector()
                self.risk_decision_engine.set_components(
                    volatility_collector=vol_collector,
                    position_monitor=self.position_monitor
                )
                logger.info("✅ Risk engine components injected (volatility + position monitor)")
            except Exception as e:
                logger.warning(f"⚠️  Could not inject volatility collector: {e}")
                logger.warning("   Risk engine will operate with limited data")
                self.risk_decision_engine.set_components(
                    volatility_collector=None,
                    position_monitor=self.position_monitor
                )
            
            logger.info("📡 Guardian will publish signals to database every 5 seconds")
            logger.info("🔄 Config file watcher active - will detect WebUI parameter changes")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Guardian Signal System: {e}")
            logger.error("   Guardian will continue with existing monitoring only")
            self.event_store = None
            self.risk_decision_engine = None
        
        # Write PID file
        self.health_tracker.write_pid_file()
        
        logger.info("✅ All components initialized")
    
    def _save_pnl_history(self, result, liquidation_data):
        """Save PnL snapshot to daily CSV file for WebUI charts"""
        try:
            from pathlib import Path
            from datetime import datetime
            import csv
            
            # Ensure reports directory exists
            reports_dir = Path('bot/reports')
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            # Daily CSV file
            today = datetime.now().strftime("%Y%m%d")
            csv_file = reports_dir / f"pnl_history_{today}.csv"
            
            # Prepare data row
            total_pnl_inr = result.get('total_summary', {}).get('total_pnl_inr', 0)
            position_count = result.get('total_summary', {}).get('position_count', 0)
            
            # Get unrealized PnL from liquidation data if available
            unrealized_pnl = 0
            if liquidation_data:
                unrealized_pnl = liquidation_data.get('margin', {}).get('unrealized_pnl', 0)
            
            row = {
                'timestamp': datetime.now().isoformat(),
                'time': datetime.now().strftime('%H:%M:%S'),
                'total_pnl': round(total_pnl_inr, 2),
                'unrealized_pnl': round(unrealized_pnl, 2),
                'position_count': position_count
            }
            
            # Write to CSV (append mode)
            file_exists = csv_file.exists()
            with open(csv_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
                
        except Exception as e:
            logger.debug(f"Error saving PnL history: {e}")  # Debug level, not critical
    
    def _check_risk_config_changes(self):
        """
        Check for risk parameter changes (hot reload for Guardian)
        Enables changing max loss limits without restarting Guardian Bot
        """
        now = time.time()
        if now - self._last_risk_check < 5:  # Check every 5 seconds
            return
        
        self._last_risk_check = now
        
        try:
            # Reload YAML config for hot-reload support
            cfg = get_config()
            
            # Check for changes in risk parameters
            changes_detected = []
            
            # Check max loss limit
            new_max_loss = cfg.guardian.max_account_loss_inr
            if new_max_loss != self._last_risk_params['max_loss']:
                changes_detected.append(f"MAX_ACCOUNT_LOSS: ₹{self._last_risk_params['max_loss']:.2f} → ₹{new_max_loss:.2f}")
                self._last_risk_params['max_loss'] = new_max_loss
                
                # Update risk enforcer
                self.risk_enforcer.max_account_loss_inr = new_max_loss
            
            # Check interval
            new_interval = cfg.guardian.check_interval
            if new_interval != self._last_risk_params['check_interval']:
                changes_detected.append(f"CHECK_INTERVAL: {self._last_risk_params['check_interval']}s → {new_interval}s")
                self._last_risk_params['check_interval'] = new_interval
                self.check_interval = new_interval
            
            if changes_detected:
                logger.warning(Colors.colorize("=" * 70, Colors.CYAN))
                logger.warning(Colors.info("🔄 GUARDIAN CONFIGURATION CHANGES DETECTED (Hot Reload from YAML)"))
                logger.warning(Colors.colorize("=" * 70, Colors.CYAN))
                for change in changes_detected:
                    logger.warning(Colors.colorize(f"   • {change}", Colors.YELLOW))
                logger.warning(Colors.colorize("=" * 70, Colors.CYAN))
                logger.info(Colors.success("✅ Risk parameters updated from config.yaml without restart"))
                
        except Exception as e:
            logger.debug(f"Config check error: {e}")
    
    def _handle_ip_change(self, old_ip: str, new_ip: str):
        """
        Handle IP address change detected by IP monitor
        
        ✅ FIX #11: IP change handler for Guardian bot
        
        Args:
            old_ip: Previous IP address
            new_ip: New IP address
        """
        try:
            logger.critical("=" * 70)
            logger.critical(f"🌐 IP ADDRESS CHANGED (Guardian Detected)")
            logger.critical("=" * 70)
            logger.critical(f"Old IP: {old_ip}")
            logger.critical(f"New IP: {new_ip}")
            logger.critical("=" * 70)
            logger.critical("⚠️ Guardian may need API key re-whitelisting")
            logger.critical("⚠️ Loss limit enforcement may be compromised if API fails")
            logger.critical("=" * 70)
            
            # Send Telegram alert
            alert_message = (
                f"🚨 GUARDIAN IP CHANGED\n\n"
                f"Old IP: {old_ip}\n"
                f"New IP: {new_ip}\n\n"
                f"⚠️ Verify API keys are whitelisted for new IP!\n"
                f"⚠️ Guardian protection may be compromised until verified."
            )
            self.send_alert(alert_message, urgent=True)
            
            # Test API connectivity immediately
            logger.info("🧪 Testing Guardian API connectivity after IP change...")
            try:
                balance = self.exchange.fetch_balance()
                logger.info("✅ API connectivity OK after IP change")
                logger.info(f"   Successfully fetched account balance")
                
                # Send success notification
                self.send_alert(
                    "✅ Guardian API connectivity verified after IP change - protection ACTIVE",
                    urgent=False
                )
            except Exception as api_error:
                logger.critical(f"❌ API FAILED after IP change: {api_error}")
                logger.critical("🛑 Guardian protection may be COMPROMISED!")
                logger.critical("🛑 Bot loss limits may NOT be enforced!")
                logger.critical("=" * 70)
                logger.critical("IMMEDIATE ACTION REQUIRED:")
                logger.critical("1. Whitelist new IP on Delta Exchange")
                logger.critical("2. Restart Guardian Bot")
                logger.critical("3. Verify API connectivity")
                logger.critical("=" * 70)
                
                # Send critical failure notification
                self.send_alert(
                    f"🚨🚨 CRITICAL: Guardian API FAILED after IP change\n\n"
                    f"Error: {api_error}\n\n"
                    f"Guardian CANNOT enforce loss limits!\n"
                    f"Whitelist {new_ip} on Delta Exchange IMMEDIATELY!",
                    urgent=True
                )
                
        except Exception as e:
            logger.error(f"❌ Error handling IP change in Guardian: {e}")
    
    def send_alert(self, message: str, urgent: bool = False):
        """
        Send Telegram alert
        
        Args:
            message: Alert message
            urgent: If True, marks as urgent
        """
        try:
            prefix = "🚨 URGENT: " if urgent else "🛡️ Guardian: "
            send_telegram_alert(prefix + message, self.config)
        except Exception as e:
            # Suppress telegram errors in demo mode (invalid token expected)
            logger.debug(f"Telegram alert not sent (demo mode): {e}")
    
    def monitoring_cycle(self):
        """Execute one monitoring cycle
        
        🚨 EMERGENCY OVERRIDE: Liquidation monitoring can be disabled via WebUI
        """
        try:
            # Check for risk parameter changes (hot reload)
            self._check_risk_config_changes()
            
            # Import emergency override check
            try:
                from bot.safety.emergency_override import should_check_liquidation, should_check_risk_management
                liquidation_enabled = should_check_liquidation()
                risk_mgmt_enabled = should_check_risk_management()
            except ImportError:
                # Fallback: always monitor if import fails
                liquidation_enabled = True
                risk_mgmt_enabled = True
            
            # Monitor positions - Use liquidation monitor MTM instead of position_monitor
            # Position monitor is deprecated in favor of liquidation monitor with accurate MTM
            total_loss_inr = 0  # Will be calculated from liquidation monitor MTM
            
            # Create result dict for health tracker compatibility
            result = {
                'current_price': 0,
                'positions': [],
                'positions_pnl': [],
                'total_summary': {
                    'total_pnl_usd': 0,
                    'total_pnl_inr': 0,
                    'total_loss_inr': 0,
                    'position_count': 0,
                    'profitable_count': 0,
                    'losing_count': 0,
                }
            }
            
            # CRITICAL CHECK 0: Liquidation Protection (Margin & Distance)
            # 🚨 Can be overridden via WebUI in emergency situations
            # Store liquidation data for health export
            liquidation_data = None
            if self.margin_monitor and self.distance_monitor and self.mtm_tracker:
                try:
                    logger.debug("Starting liquidation data collection...")
                    # Get integrated liquidation status
                    liq_status = self.liquidation_monitor.get_status()
                    
                    # Extract margin data
                    utilization = liq_status.get('margin_utilization', 0)
                    margin_zone = liq_status.get('margin_zone', 'UNKNOWN')
                    logger.debug(f"Margin: {utilization}% [{margin_zone}]")
                    
                    # Extract distance data
                    distance = liq_status.get('liquidation_distance', 100)
                    distance_zone = liq_status.get('distance_zone', 'SAFE')
                    
                    # Extract MTM data (already in INR from manual calculation)
                    current_mtm = liq_status.get('total_unrealized_pnl', 0)
                    
                    # Calculate total loss from MTM (if MTM is negative, that's the loss)
                    total_loss_inr = abs(min(0, current_mtm))
                    
                    # Update result dict with actual data
                    result['total_summary']['total_pnl_inr'] = current_mtm
                    result['total_summary']['total_loss_inr'] = total_loss_inr
                    result['total_summary']['position_count'] = liq_status.get('total_positions', 0)
                    
                    # Balance data is already in INR from liquidation monitor (no conversion needed)
                    total_balance = liq_status.get('total_balance', 0)
                    available_balance = liq_status.get('available_balance', 0)
                    blocked_margin = liq_status.get('blocked_balance', 0)
                    unrealized_pnl = liq_status.get('total_unrealized_pnl', 0)
                    maintenance_margin = liq_status.get('maintenance_margin', 0)
                    
                    # Store for health file export (already in INR)
                    liquidation_data = {
                        'margin': {
                            'utilization': utilization,
                            'zone': margin_zone,
                            'can_open_positions': utilization < 80,
                            'total_balance': round(total_balance, 2),
                            'available_balance': round(available_balance, 2),
                            'blocked_margin': round(blocked_margin, 2),
                            'unrealized_pnl': round(unrealized_pnl, 2)
                        },
                        'distance': {
                            'distance': distance,
                            'zone': distance_zone,
                            'maintenance_margin': round(maintenance_margin, 2)
                        },
                        'mtm': {
                            'current_mtm_inr': current_mtm,
                            'trend': 'STABLE'
                        }
                    }
                    logger.debug(f"Liquidation data collected successfully: {liquidation_data}")
                    
                    # Log liquidation metrics
                    if margin_zone != 'GREEN' or distance_zone not in ['SAFE', 'ACCEPTABLE']:
                        logger.warning(
                            f"💰 Margin: {utilization:.1f}% [{margin_zone}] | "
                            f"🛡️ Distance: {distance:.1f}% [{distance_zone}] | "
                            f"📊 MTM: ₹{current_mtm:,.0f}"
                        )
                    
                    # CRITICAL: Liquidation distance too low
                    # 🚨 Check override status before taking action
                    if distance < 40:
                        if not liquidation_enabled:
                            logger.warning("⚠️" * 20)
                            logger.warning(f"🚨 LIQUIDATION MONITOR OVERRIDDEN!")
                            logger.warning(f"   Distance: {distance:.1f}% < 40% (CRITICAL)")
                            logger.warning(f"   Margin: {utilization:.1f}%")
                            logger.warning(f"   Alerts and emergency actions are DISABLED")
                            logger.warning("⚠️" * 20)
                        else:
                            logger.critical(f"🚨 CRITICAL LIQUIDATION RISK: Distance {distance:.1f}% < 40%")
                            self.send_alert(
                                f"🚨 CRITICAL LIQUIDATION RISK\n\n"
                                f"Liquidation Distance: {distance:.1f}%\n"
                                f"Margin Utilization: {utilization:.1f}%\n"
                                f"MTM: ₹{current_mtm:,.0f}\n\n"
                                f"URGENT: Add margin or close positions immediately!",
                                urgent=True
                            )
                            
                            # If distance < 30%, trigger emergency
                            if distance < 30:
                                logger.critical("🚨 EMERGENCY: Liquidation distance < 30% - positions at risk")
                                logger.critical("⚠️  Use Emergency Kill button in WebUI to close positions")
                                # Emergency actions now handled via WebUI or manual intervention
                                # emergency_kill_all() can be called manually if needed
                    
                    # CRITICAL: Margin utilization too high
                    if utilization >= 90:
                        if not liquidation_enabled:
                            logger.warning(f"⚠️ LIQUIDATION MONITOR OVERRIDDEN: Margin {utilization:.1f}% >= 90% (no action taken)")
                        else:
                            logger.critical(f"🚨 CRITICAL MARGIN UTILIZATION: {utilization:.1f}% >= 90%")
                        self.send_alert(
                            f"🚨 CRITICAL MARGIN UTILIZATION\n\n"
                            f"Utilization: {utilization:.1f}%\n"
                            f"Liquidation Distance: {distance:.1f}%\n"
                            f"MTM: ₹{current_mtm:,.0f}\n\n"
                            f"URGENT: Emergency action required!",
                            urgent=True
                        )
                        
                except Exception as e:
                    logger.error(f"Liquidation check error: {e}", exc_info=True)
            
            # CRITICAL CHECK 1: Equity Floor (Hard Stop)
            # Get current equity from liquidation monitor (real-time WebSocket data)
            current_equity = 0
            if self.liquidation_monitor:
                try:
                    liq_status = self.liquidation_monitor.get_status()
                    # Get total balance (already in INR, converted from USD × 85)
                    current_equity = liq_status.get('total_balance', 0)
                except Exception as e:
                    logger.error(f"Failed to get equity from liquidation monitor: {e}")
            
            if current_equity > 0:  # Only check if we have equity data
                equity_breached, equity_message = self.risk_enforcer.check_equity_floor(current_equity)
                if equity_breached:
                    logger.critical("🚨 EQUITY FLOOR BREACHED - INITIATING EMERGENCY PROTOCOL")
                    
                    # Create equity floor breach flag
                    equity_flag_file = self.base_dir / '.equity_floor_breach'
                    equity_flag_file.touch()
                    logger.critical(f"Created equity floor breach flag: {equity_flag_file}")
                    
                    # Send urgent alert
                    self.send_alert(equity_message, urgent=True)
                    
                    # Emergency protocol now handled via WebUI
                    logger.critical("⚠️  Use Emergency Kill button in WebUI to close positions")
                    # emergency_result = self.emergency_actions.execute_emergency_protocol(
                    #     result['positions'], 
                    #     cancel_tps=False  # Keep TP orders active
                    # )
                    
                    # DON'T STOP - continue monitoring for recovery (infinite uptime mode)
                    logger.critical("=" * 70)
                    logger.critical("🚨 EQUITY FLOOR BREACH - MONITORING PAUSED")
                    logger.critical("Guardian will resume normal checks when equity recovers")
                    logger.critical("Emergency flag active - Trading bot is blocked")
                    logger.critical("=" * 70)
                    
                    # Don't exit - just pause aggressive monitoring
                    # Guardian continues to monitor for recovery
            
            # CRITICAL CHECK 2: Drawdown Cap (30-Day Rolling Window)
            if self.equity_tracker and self.equity_tracker.enabled:
                # Take hourly equity snapshot
                current_time = time.time()
                if current_time - self._last_equity_snapshot_time >= 3600:  # Every hour
                    self.equity_tracker.add_snapshot(current_equity)
                    self._last_equity_snapshot_time = current_time
                
                # Check drawdown limit
                drawdown_breached, drawdown_message = self.equity_tracker.check_drawdown_limit(current_equity)
                if drawdown_message:  # Either breach or recovery
                    self.send_alert(drawdown_message, urgent=drawdown_breached)
            
            # Check risk thresholds (PnL-based)
            risk_level, should_take_action, alert_message = self.risk_enforcer.check_loss_threshold(total_loss_inr)
            
            # Send alert if needed
            if alert_message:
                urgent = risk_level == 'emergency'
                self.send_alert(alert_message, urgent=urgent)
            
            # Take emergency action if needed
            if should_take_action:
                logger.critical("🚨 EMERGENCY ACTION REQUIRED!")
                
                # Emergency protocol now handled via WebUI
                logger.critical("⚠️  Use Emergency Kill button in WebUI to close positions")
                
                # Send detailed alert
                alert = (
                    f"🚨 EMERGENCY ALERT - MANUAL ACTION REQUIRED\n\n"
                    f"Use WebUI Emergency Kill button to close positions\n\n"
                    f"Total Loss: ₹{total_loss_inr:,.2f}\n"
                    f"Max Limit: ₹{self.risk_enforcer.max_account_loss_inr:,.2f}\n\n"
                    f"⚠️  Guardian monitoring paused - manual intervention required."
                )
                self.send_alert(alert, urgent=True)
            
            # Add liquidation data to result before updating health
            if liquidation_data:
                result['liquidation'] = liquidation_data
                logger.debug("Added liquidation data to health result")
            else:
                logger.debug("No liquidation data to add to health")
            
            # Update health file
            self.health_tracker.update_health(result)
            
            # Save PnL history for WebUI charts
            self._save_pnl_history(result, liquidation_data)
            
            # Log status (only if risk is elevated OR it's been 5 minutes since last log)
            current_time = time.time()
            if not hasattr(self, 'last_safe_log_time'):
                self.last_safe_log_time = 0
            if not hasattr(self, 'last_risk_level'):
                self.last_risk_level = 'safe'
            
            # Log if: risk changed, risk is not safe, or it's been 5 minutes
            should_log = (
                risk_level != self.last_risk_level or  # Risk level changed
                risk_level != 'safe' or                # Risk is elevated
                (current_time - self.last_safe_log_time) >= 300  # 5 minutes elapsed
            )
            
            # Get position count from liquidation status
            position_count = liq_status.get('total_positions', 0)
            
            if should_log and position_count > 0:
                # Colorize based on risk level
                if risk_level == 'safe':
                    risk_color = Colors.success(f"✅ Risk: {risk_level.upper()}")
                elif risk_level == 'warning':
                    risk_color = Colors.warning(f"⚠️  Risk: {risk_level.upper()}")
                else:  # emergency
                    risk_color = Colors.error(f"🚨 Risk: {risk_level.upper()}")
                
                # Colorize MTM (positive = green, negative = red)
                if current_mtm >= 0:
                    mtm_text = Colors.money_positive(f"₹{current_mtm:.2f}")
                else:
                    mtm_text = Colors.money_negative(f"₹{current_mtm:.2f}")
                
                # Colorize loss (more loss = more red)
                loss_pct = (total_loss_inr / self.risk_enforcer.max_account_loss_inr * 100) if self.risk_enforcer.max_account_loss_inr > 0 else 0
                if loss_pct < 50:
                    loss_text = Colors.colorize(f"₹{total_loss_inr:.2f}", Colors.GREEN)
                elif loss_pct < 80:
                    loss_text = Colors.colorize(f"₹{total_loss_inr:.2f}", Colors.YELLOW)
                else:
                    loss_text = Colors.colorize(f"₹{total_loss_inr:.2f}", Colors.RED, bold=True)
                
                logger.info(
                    f"{risk_color} | "
                    f"{Colors.colorize(str(position_count), Colors.CYAN)} positions | "
                    f"MTM: {mtm_text} | "
                    f"Loss: {loss_text} / {Colors.colorize(f'₹{self.risk_enforcer.max_account_loss_inr:.2f}', Colors.BRIGHT_BLACK)}"
                )
                if risk_level == 'safe':
                    self.last_safe_log_time = current_time
                self.last_risk_level = risk_level
            
        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}", exc_info=True)
    
    def run(self):
        """Main run loop"""
        global shutdown_requested
        
        try:
            # Setup logging first (using default config from env)
            self.setup_logging()
            
            logger.info("=" * 70)
            logger.info(f"🛡️ Guardian Bot v{self.VERSION} Starting...")
            logger.info("=" * 70)
            
            # Load configuration from YAML
            self.load_configuration()
            
            # Setup exchange
            self.setup_exchange()
            
            # Initialize components
            self.initialize_components()
            
            # Send startup alert
            cfg = get_config()
            self.send_alert(
                f"🛡️ Guardian Bot v{self.VERSION} Started\n\n"
                f"Max Loss: ₹{cfg.guardian.max_account_loss_inr}\n"
                f"Check Interval: {self.check_interval}s\n"
                f"Symbol: {cfg.bot.symbol}\n\n"
                f"Config Source: config.yaml ✅\n"
                f"Monitoring active 24/7"
            )
            
            logger.info("=" * 70)
            logger.info("🔄 Starting monitoring loop...")
            logger.info("=" * 70)
            
            # Start Guardian Risk Decision Engine (Phase 1)
            if self.risk_decision_engine:
                import threading
                import asyncio
                
                def run_risk_engine():
                    """Run risk engine in separate thread with its own event loop"""
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        logger.info("🚀 Guardian Risk Decision Engine starting...")
                        loop.run_until_complete(self.risk_decision_engine.run_continuous_monitoring())
                    except Exception as e:
                        logger.error(f"Risk engine error: {e}", exc_info=True)
                
                self._risk_engine_thread = threading.Thread(
                    target=run_risk_engine,
                    name="GuardianRiskEngine",
                    daemon=True
                )
                self._risk_engine_thread.start()
                logger.info("✅ Guardian Risk Decision Engine running in background")
                logger.info("📡 Publishing GO/STOP signals to database every 5s")
            else:
                logger.warning("⚠️  Risk Decision Engine not available - using legacy monitoring only")
            
            # Main monitoring loop
            while not shutdown_requested:
                self.monitoring_cycle()
                
                # Sleep in small intervals to check shutdown flag frequently
                for _ in range(self.check_interval):
                    if shutdown_requested:
                        break
                    time.sleep(1)
            
            if logger:
                logger.info("Shutdown requested, cleaning up...")
            else:
                print("Shutdown requested, cleaning up...")
            
        except KeyboardInterrupt:
            if logger:
                logger.info("Received KeyboardInterrupt")
            else:
                print("Received KeyboardInterrupt")
        except Exception as e:
            if logger:
                logger.critical(f"Fatal error: {e}", exc_info=True)
            else:
                print(f"Fatal error: {e}")
                import traceback
                traceback.print_exc()
            try:
                self.send_alert(f"🚨 Guardian crashed: {e}", urgent=True)
            except Exception:
                pass  # Ignore errors during error handling
            raise
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup on shutdown"""
        global logger
        if logger:
            logger.info("Cleaning up...")
        else:
            print("Cleaning up...")
        
        # Shutdown risk decision engine
        if self.risk_decision_engine:
            try:
                logger.info("Stopping Guardian Risk Decision Engine...")
                self.risk_decision_engine.shutdown()
                logger.info("✅ Risk engine stopped")
            except Exception as e:
                logger.error(f"Error stopping risk engine: {e}")
        
        if self.health_tracker:
            self.health_tracker.remove_pid_file()
            self.health_tracker.remove_health_file()
        
        # Send shutdown alert
        try:
            self.send_alert("🛡️ Guardian Bot Stopped", urgent=False)
        except Exception:
            pass  # Ignore errors during shutdown
        
        if logger:
            logger.info("=" * 70)
            logger.info("🛡️ Guardian Bot Stopped")
            logger.info("=" * 70)
        else:
            print("=" * 70)
            print("🛡️ Guardian Bot Stopped")
            print("=" * 70)


def main():
    """Main entry point"""
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run guardian bot
    guardian = GuardianBot()
    guardian.run()


if __name__ == '__main__':
    main()

