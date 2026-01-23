"""
Guardian Risk Decision Engine - The Traffic Light Controller

SINGLE RESPONSIBILITY: Decide if trading is safe right now

Features:
- Writes to EventStore (SQL database with ACID guarantees)
- Keeps full signal history for debugging and audit trail
- Watches config.yaml for live parameter changes (WebUI integration)
- Trading bot queries latest signal from database

Output: EventStore events with GO/STOP signal every 5 seconds
"""

import asyncio
import hashlib
import time
import uuid
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
from datetime import datetime

# Watchdog for config file monitoring
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logging.warning("watchdog not installed - config auto-reload disabled. Install: pip install watchdog")

from bot.strategy.modules.event_store import EventStore, Event, EventType
from config.loader import get_config
from bot.guardian.health.health_tracker import SystemHealthTracker

# Configure module logger
log = logging.getLogger("guardian.risk_engine")


class ConfigChangeHandler(FileSystemEventHandler):
    """Watch config.yaml for changes from WebUI"""
    def __init__(self, callback):
        self.callback = callback
        self.last_modified = 0
        self._callback_in_progress = False  # Re-entrancy guard
        
    def on_modified(self, event):
        # Debounce - only trigger if >2 seconds since last change
        if event.src_path.endswith('config.yaml'):
            log.debug(f"Config file modified detected: {event.src_path}")
            now = time.time()
            
            # RE-ENTRANCY GUARD: Prevent recursive callback amplification
            if self._callback_in_progress:
                log.debug(f"Config callback already in progress, skipping")
                return
            
            if now - self.last_modified > 2:
                self.last_modified = now
                log.info(f"📝 Triggering config reload (debounced)")
                self._callback_in_progress = True
                try:
                    self.callback()
                finally:
                    self._callback_in_progress = False
            else:
                log.debug(f"Config change ignored (debounce: {now - self.last_modified:.1f}s < 2s)")


class GuardianRiskDecisionEngine:
    """
    The Brain: Monitors all risk factors and outputs events to SQL database
    
    Features:
    - Writes to EventStore (SQL with ACID guarantees)
    - Keeps full signal history (debugging & audit)
    - Watches config.yaml for live parameter changes (WebUI integration)
    - Trading Bot queries latest signal from database
    """
    
    def __init__(self, event_store: EventStore):
        """
        Initialize Risk Decision Engine
        
        Args:
            event_store: EventStore instance for database operations
        """
        self.event_store = event_store
        self.config = get_config()
        self.config_hash = self._calculate_config_hash()
        
        # Components will be injected
        self.volatility_collector = None
        self.position_monitor = None
        self.rsi_collector = None
        
        # Initialize health tracker for Layer 5
        self.health_tracker = SystemHealthTracker(config=self.config)
        
        # Setup config file watcher (WebUI changes)
        # Config is at project root, not in config/ subdirectory
        self.config_path = Path.cwd() / 'config.yaml'
        self.config_observer = None
        
        if WATCHDOG_AVAILABLE:
            self._setup_config_watcher()
        else:
            log.warning("⚠️  Config auto-reload disabled - watchdog not installed")
        
        log.info("✅ Guardian Risk Decision Engine initialized")
        log.info(f"   Config hash: {self.config_hash}")
    
    def set_components(self, volatility_collector, position_monitor, liquidation_monitor=None, rsi_collector=None):
        """
        Inject dependencies (called by GuardianBot)
        
        Args:
            volatility_collector: Volatility data collector
            position_monitor: Position monitoring component
            liquidation_monitor: Liquidation monitor (for total account PnL)
            rsi_collector: RSI collector (Layer 6)
        """
        self.volatility_collector = volatility_collector
        self.position_monitor = position_monitor
        self.liquidation_monitor = liquidation_monitor  # For total account PnL
        self.rsi_collector = rsi_collector  # For RSI monitoring (Layer 6)
        log.info("✅ Risk engine components injected")
    
    def _setup_config_watcher(self):
        """Setup file system watcher for config.yaml"""
        try:
            self.config_observer = Observer()
            config_handler = ConfigChangeHandler(self._on_config_changed)
            self.config_observer.schedule(
                config_handler, 
                str(self.config_path.parent), 
                recursive=False
            )
            self.config_observer.start()
            log.info("📁 Config file watcher started - will detect WebUI parameter changes")
            log.info(f"   Watching: {self.config_path}")
        except Exception as e:
            log.error(f"Failed to start config watcher: {e}")
            log.error(f"   Config path: {self.config_path}")
            import traceback
            log.error(traceback.format_exc())
    
    def _calculate_config_hash(self) -> str:
        try:
            risk_params = {
                'max_iv': getattr(self.config.safety.volatility, 'max_iv', 0),
                'max_rv': getattr(self.config.safety.volatility, 'max_rv', 0),
                'max_spread': getattr(self.config.safety.volatility, 'max_spread', 0),
                'max_loss': getattr(self.config.guardian, 'max_account_loss_inr', 0),
                'max_position': getattr(self.config.grid.limits, 'max_open_positions', 0),
                'min_liq_distance': getattr(self.config.liquidation_protection, 'liquidation_distance_min', 0),
                'opportunistic_recovery_enabled': getattr(self.config.safety.volatility.opportunistic_recovery, 'enabled', False),
                'opportunistic_iv_threshold': getattr(self.config.safety.volatility.opportunistic_recovery, 'iv_threshold', 0),
                'opportunistic_rv_threshold': getattr(self.config.safety.volatility.opportunistic_recovery, 'rv_threshold', 0)
            }
            config_str = str(sorted(risk_params.items()))
            return hashlib.md5(config_str.encode()).hexdigest()[:8]
        except Exception as e:
            log.error(f"Error calculating config hash: {e}")
            return "error"
    
    def _on_config_changed(self):
        log.info("📝 Config file changed - reloading risk parameters...")
        
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    time.sleep(retry_delay)
                    log.debug(f"Retry attempt {attempt + 1}/{max_retries}")
                
                from config.loader import reload_config
                self.config = reload_config()
                new_hash = self._calculate_config_hash()
                
                # HOT RELOAD: Update RSI collector thresholds
                if self.rsi_collector:
                    try:
                        self.rsi_collector.reload_thresholds(self.config)
                    except Exception as e:
                        log.error(f"Failed to reload RSI thresholds: {e}")
                
                if new_hash != self.config_hash:
                    log.warning(f"⚠️  RISK PARAMETERS CHANGED (WebUI update detected)")
                    log.warning(f"   Old config: {self.config_hash} → New config: {new_hash}")
                    log.warning(f"   IV Limit: {self.config.safety.volatility.max_iv}%")
                    log.warning(f"   RV Limit: {self.config.safety.volatility.max_rv}%")
                    log.warning(f"   Spread Limit: {self.config.safety.volatility.max_spread}%")
                    if hasattr(self.config.safety, 'rsi'):
                        log.warning(f"   RSI Long Threshold: {self.config.safety.rsi.long_threshold}")
                        log.warning(f"   RSI Short Threshold: {self.config.safety.rsi.short_threshold}")
                    
                    old_hash = self.config_hash
                    self.config_hash = new_hash
                    
                    self._log_config_change_event(old_hash, new_hash)
                else:
                    log.debug("Config reloaded but risk parameters unchanged")
                
                return
                
            except Exception as e:
                if attempt < max_retries - 1:
                    log.warning(f"Config reload attempt {attempt + 1} failed: {e}, retrying...")
                else:
                    log.error(f"Error reloading config after {max_retries} attempts: {e}")
    
    def _check_config_changes(self):
        """
        Periodic check for config changes (backup to file watcher)
        Called every 60 seconds from main loop
        """
        try:
            from config.loader import reload_config
            self.config = reload_config()
            new_hash = self._calculate_config_hash()
            
            if new_hash != self.config_hash:
                log.warning(f"⚠️  RISK PARAMETERS CHANGED (Periodic check detected)")
                log.warning(f"   Old config: {self.config_hash} → New config: {new_hash}")
                log.warning(f"   IV Limit: {self.config.safety.volatility.max_iv}%")
                log.warning(f"   RV Limit: {self.config.safety.volatility.max_rv}%")
                log.warning(f"   Spread Limit: {self.config.safety.volatility.max_spread}%")
                
                old_hash = self.config_hash
                self.config_hash = new_hash
                
                self._log_config_change_event(old_hash, new_hash)
            
        except Exception as e:
            log.debug(f"Periodic config check error: {e}")
    
    def _log_config_change_event(self, old_hash: str, new_hash: str):
        try:
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.GUARDIAN_CONFIG_CHANGED,
                timestamp=time.time(),
                correlation_id=f"config_change_{int(time.time())}",
                aggregate_id="guardian",
                data={
                    'old_config_version': old_hash,
                    'new_config_version': new_hash,
                    'max_iv': getattr(self.config.safety.volatility, 'max_iv', 0),
                    'max_rv': getattr(self.config.safety.volatility, 'max_rv', 0),
                    'max_spread': getattr(self.config.safety.volatility, 'max_spread', 0),
                    'max_loss_inr': getattr(self.config.guardian, 'max_account_loss_inr', 0),
                    'max_position_size': getattr(self.config.grid.limits, 'max_open_positions', 0),
                    'min_liquidation_distance': getattr(self.config.liquidation_protection, 'liquidation_distance_min', 0),
                    'opportunistic_recovery_enabled': getattr(self.config.safety.volatility.opportunistic_recovery, 'enabled', False),
                    'opportunistic_iv_threshold': getattr(self.config.safety.volatility.opportunistic_recovery, 'iv_threshold', 0),
                    'opportunistic_rv_threshold': getattr(self.config.safety.volatility.opportunistic_recovery, 'rv_threshold', 0)
                },
                metadata={
                    'source': 'guardian_risk_engine',
                    'reason': 'webui_parameter_update',
                    'guardian_version': '1.0.0'
                }
            )
            self.event_store.append_event(event)
            log.info("✅ Config change logged to database for audit trail")
        except Exception as e:
            log.error(f"Failed to log config change: {e}")
    
    async def run_continuous_monitoring(self):
        """
        Main loop - The heartbeat of risk monitoring
        Runs every 5 seconds, forever
        Writes to SQL database (EventStore) instead of JSON
        """
        log.info("🚀 Starting continuous risk monitoring (5s interval)")
        
        iteration = 0
        while True:
            try:
                signal_data = self._generate_signal()
                self._publish_signal_to_database(signal_data)
                
                # Periodic config check (every 60 seconds = 12 iterations)
                # This is a backup to file watcher in case it stops working
                iteration += 1
                if iteration % 12 == 0:
                    self._check_config_changes()
                
                await asyncio.sleep(5)
            except Exception as e:
                log.error(f"Signal engine error: {e}", exc_info=True)
                # On error, publish STOP signal (fail-safe)
                self._publish_stop_signal_to_database("guardian_error")
                await asyncio.sleep(5)
    
    def _generate_signal(self) -> Dict:
        """
        The Core Logic: Evaluate all risk factors
        
        Returns simple GO/STOP signal with reason
        This is the ONLY place that decides if trading is safe!
        """
        
        # Check 1: Volatility too high?
        if self._is_volatility_too_high():
            return self._make_stop_signal(
                reason="High volatility detected",
                details=self._get_volatility_details()
            )
        
        # Check 2: Loss limit exceeded?
        if self._is_loss_limit_exceeded():
            return self._make_stop_signal(
                reason="Loss limit exceeded",
                details=self._get_pnl_details()
            )
        
        # Check 3: Position too large?
        if self._is_position_too_large():
            return self._make_stop_signal(
                reason="Position limit exceeded",
                details=self._get_position_details()
            )
        
        # Check 4: Too close to liquidation?
        if self._is_liquidation_risk():
            return self._make_stop_signal(
                reason="Liquidation risk too high",
                details=self._get_liquidation_details()
            )
        
        # Check 5: System health issues?
        if self._has_system_issues():
            return self._make_stop_signal(
                reason="System health issue",
                details=self._get_health_details()
            )
        
        # Check 6: RSI threshold (mode-specific)
        if self._is_rsi_overbought():
            # Get mode-specific reason with actual threshold from config
            bot_mode = getattr(self.config.bot, 'mode', 'LONG').upper()
            if bot_mode == "LONG":
                threshold = self.config.safety.rsi.long_threshold
                reason = f"RSI <= {threshold} (oversold) - market too weak for LONG positions"
            else:
                threshold = self.config.safety.rsi.short_threshold
                reason = f"RSI >= {threshold} (overbought) - market too strong for SHORT positions"
            return self._make_stop_signal(
                reason=reason,
                details=self._get_rsi_details()
            )
        
        # All clear! Green light 🟢
        return self._make_go_signal()
    
    def _is_volatility_too_high(self) -> bool:
        """Check if market volatility exceeds safety thresholds"""
        if not self.volatility_collector:
            log.debug("Volatility collector not available")
            return False
        
        try:
            vol_data = self.volatility_collector.get_latest_values()
            
            # Record data update for freshness tracking
            if hasattr(self, 'health_tracker') and self.health_tracker:
                self.health_tracker.record_data_update('volatility')
            
            iv = vol_data.get('iv', {}).get('value', 0)
            rv = vol_data.get('rv', {}).get('value', 0)
            spread = vol_data.get('spread', 0)
            
            cfg = self.config.safety.volatility
            
            return (
                iv > cfg.max_iv or 
                rv > cfg.max_rv or 
                spread > cfg.max_spread
            )
        except Exception as e:
            log.error(f"Error checking volatility: {e}")
            return False
    
    def _is_loss_limit_exceeded(self) -> bool:
        """Check if account loss exceeds configured limit"""
        try:
            pnl_details = self._get_pnl_details()
            pnl = pnl_details['pnl_inr']
            max_loss = pnl_details['max_loss_limit']
            
            if max_loss > 0 and pnl < -max_loss:
                return True
            return False
        except Exception as e:
            log.error(f"Error checking loss limit: {e}")
            return False
    
    def _is_position_too_large(self) -> bool:
        """Check if position size exceeds limit"""
        if not self.position_monitor:
            log.debug("Position monitor not available")
            return False
        
        try:
            position = self.position_monitor.get_position()
            
            # Record data update for freshness tracking
            if hasattr(self, 'health_tracker') and self.health_tracker:
                self.health_tracker.record_data_update('positions')
            
            max_size = getattr(self.config.safety, 'max_position_size', None)
            if max_size and position:
                return abs(position.size) > max_size
            return False
        except Exception as e:
            log.error(f"Error checking position size: {e}")
            return False
    
    def _is_liquidation_risk(self) -> bool:
        """Check if we're too close to liquidation price"""
        if not self.position_monitor:
            log.debug("Position monitor not available")
            return False
        
        try:
            liq_distance = self.position_monitor.get_liquidation_distance()
            
            # Record data update for freshness tracking
            if hasattr(self, 'health_tracker') and self.health_tracker:
                self.health_tracker.record_data_update('liquidation')
            
            min_distance = getattr(self.config.safety, 'min_liquidation_distance_pct', None)
            if min_distance:
                return liq_distance < min_distance
            return False
        except Exception as e:
            log.error(f"Error checking liquidation risk: {e}")
            return False
    
    def _has_system_issues(self) -> bool:
        """Check for API connectivity or other system issues"""
        if not hasattr(self, 'health_tracker') or not self.health_tracker:
            return False  # No tracker = assume healthy (fail-safe)
        
        # Use health tracker's critical issue detection
        return self.health_tracker.has_critical_issues()
    
    def _is_rsi_overbought(self) -> bool:
        """
        Check if RSI should stop trading (Layer 6).
        Uses mode-specific thresholds with hysteresis.
        
        LONG mode: STOP when RSI <= long_threshold (oversold - market too weak)
        SHORT mode: STOP when RSI >= short_threshold (overbought - market too strong)
        """
        if not self.rsi_collector:
            log.debug("RSI collector not available")
            return False  # Fail-safe: assume healthy if RSI unavailable
        
        try:
            # Get RSI config
            rsi_config = getattr(self.config.safety, 'rsi', None)
            if not rsi_config or not getattr(rsi_config, 'enabled', False):
                log.debug("RSI monitoring disabled")
                return False
            
            # Use the collector's mode-aware logic with hysteresis
            return self.rsi_collector.should_stop_trading()
            
        except Exception as e:
            log.error(f"Error checking RSI: {e}")
            return False  # Fail-safe: assume healthy on error
    
    def _make_go_signal(self) -> Dict:
        """Create a GO signal - all systems nominal"""
        volatility = self._get_volatility_details()
        pnl = self._get_pnl_details()
        position = self._get_position_details()
        liquidation = self._get_liquidation_details()
        health = self._get_health_details()
        rsi = self._get_rsi_details()
        
        # Log comprehensive safety metrics - SHOW EVERYTHING FOR TRANSPARENCY
        log.info("="*80)
        log.info("✅ ALL SAFETY CHECKS PASSED - TRADING ALLOWED")
        log.info(f"   ⏰ Time: {datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')}")
        log.info("="*80)
        
        # 1. VOLATILITY SAFETY SYSTEM
        log.info("   🌡️  VOLATILITY SAFETY SYSTEM: ✅ PASS")
        log.info(f"      IV: {volatility.get('iv', 0):.1f}% / {volatility.get('iv_threshold', 0):.1f}% limit")
        log.info(f"      RV: {volatility.get('rv', 0):.1f}% / {volatility.get('rv_threshold', 0):.1f}% limit")
        log.info(f"      Spread: {volatility.get('spread', 0):.1f}% / {volatility.get('spread_threshold', 0):.1f}% limit")
        log.info(f"      Status: {volatility.get('status', 'UNKNOWN')}")
        
        # 2. PnL/LOSS LIMIT SAFETY SYSTEM
        current_pnl = pnl.get('pnl_inr', 0)
        pnl_emoji = "💚" if current_pnl >= 0 else "💔"
        log.info(f"   {pnl_emoji} PnL/LOSS LIMIT SAFETY SYSTEM: ✅ PASS")
        log.info(f"      Current PnL: ₹{current_pnl:.2f}")
        log.info(f"      Max Loss Allowed: ₹{pnl.get('max_loss_limit', 0):.2f}")
        log.info(f"      Utilization: {pnl.get('utilization_pct', 0):.1f}%")
        log.info(f"      Breach Amount: ₹{pnl.get('breach_amount', 0):.2f}")
        log.info(f"      Status: {pnl.get('status', 'UNKNOWN')}")
        
        # 3. POSITION SIZE SAFETY SYSTEM
        log.info("   📈 POSITION SIZE SAFETY SYSTEM: ✅ PASS")
        log.info(f"      Total Position: {position.get('position_size', 0):.0f} contracts ({position.get('num_positions', 0)} positions)")
        
        # Show individual position breakdown
        breakdown = position.get('breakdown', [])
        if breakdown:
            log.info("      Position Breakdown:")
            for pos in breakdown:
                emoji = "🟢" if pos['side'] == 'LONG' else "🔴"
                log.info(f"        {emoji} {pos['symbol']}: {pos['size']:+.0f} contracts @ ₹{pos['mark']:.2f} (PnL: ₹{pos['pnl']:+.2f})")
        
        log.info(f"      Max Position Allowed: {position.get('max_size', 0)} contracts")
        log.info(f"      Utilization: {position.get('utilization_pct', 0):.1f}%")
        log.info(f"      Status: {position.get('status', 'UNKNOWN')}")
        
        # 4. LIQUIDATION SAFETY SYSTEM
        log.info("   🛡️  LIQUIDATION SAFETY SYSTEM: ✅ PASS")
        log.info(f"      Liquidation Distance: {liquidation.get('liquidation_distance', 0):.1f}%")
        log.info(f"      Min Distance Required: {liquidation.get('min_distance', 0):.2f}%")
        log.info(f"      Safety Buffer: {liquidation.get('buffer', 0):.1f}%")
        log.info(f"      Safety Margin: {liquidation.get('safety_margin_pct', 0):.1f}%")
        log.info(f"      Status: {liquidation.get('status', 'UNKNOWN')}")
        
        # 5. SYSTEM HEALTH CHECK
        health_emoji = "✅" if health.get('system_healthy', True) else "⚠️"
        maintenance_mode = health.get('exchange_in_maintenance', False)
        
        if maintenance_mode:
            log.info(f"   💻 SYSTEM HEALTH CHECK: 🔴 MAINTENANCE MODE")
            log.info(f"      Exchange Status: IN MAINTENANCE")
        else:
            log.info(f"   💻 SYSTEM HEALTH CHECK: {health_emoji} {'PASS' if health.get('system_healthy', True) else 'DEGRADED'}")
        
        if health.get('enabled', False):
            log.info(f"      API Health: {'✅' if health.get('api_healthy', True) else '❌'} (Success rate: {health.get('api_success_rate', 100):.1f}%)")
            log.info(f"      WebSocket: {'✅ Connected' if health.get('websocket_connected', True) else '❌ Disconnected'} (Stale: {health.get('websocket_stale_seconds', 0):.0f}s)")
            log.info(f"      Data Freshness: {'✅' if health.get('data_healthy', True) else '❌'}")
            log.info(f"      Event Store: {'✅ Connected' if health.get('event_store_connected', True) else '❌ Disconnected'}")
            log.info(f"      Exchange Status: {'🔴 MAINTENANCE' if maintenance_mode else '🟢 OPERATIONAL'}")
            
            if health.get('maintenance_scheduled', False):
                log.info(f"      ⚠️ Maintenance scheduled")
            
            if health.get('issues'):
                log.info(f"      Issues: {', '.join(health['issues'])}")
        else:
            log.info("      Status: Monitoring disabled")
        
        # 6. RSI SAFETY SYSTEM (Layer 6)
        rsi_status = rsi.get('status', 'UNKNOWN')
        bot_mode = rsi.get('bot_mode', 'LONG')
        rsi_emoji = "✅" if rsi_status == 'GO' else "⚠️"
        log.info(f"   📊 RSI SAFETY SYSTEM (Layer 6): {rsi_emoji} PASS")
        if rsi.get('enabled', False):
            log.info(f"      Bot Mode: {bot_mode}")
            log.info(f"      Current RSI: {rsi.get('rsi', 0):.2f}")
            if bot_mode == "LONG":
                log.info(f"      Long Threshold: {rsi.get('long_threshold'):.1f} (STOP when RSI <= this)")
            else:
                log.info(f"      Short Threshold: {rsi.get('short_threshold'):.1f} (STOP when RSI >= this)")
            log.info(f"      Period: {rsi.get('period', 14)}")
            log.info(f"      Timeframe: {rsi.get('timeframe', '1h')}")
            log.info(f"      Status: {rsi_status}")
            if rsi.get('hysteresis_active', False):
                log.info(f"      Hysteresis: Active ({rsi.get('hysteresis_seconds', 60)}s delay at threshold)")
        else:
            log.info("      Status: Monitoring disabled")
        
        log.info("="*80)
        
        return {
            'signal': 'GO',
            'reason': 'All safety checks passed',
            'timestamp': time.time(),
            'details': {
                **volatility,
                **pnl,
                **position,
                **liquidation,
                **health,
                **rsi
            }
        }
    
    def _make_stop_signal(self, reason: str, details: Dict) -> Dict:
        """Create a STOP signal with explanation - SHOW ALL SAFETY METRICS"""
        
        # Get ALL safety metrics for complete transparency
        volatility = self._get_volatility_details()
        pnl = self._get_pnl_details()
        position = self._get_position_details()
        liquidation = self._get_liquidation_details()
        health = self._get_health_details()
        rsi = self._get_rsi_details()
        
        # Log which safety system blocked trading
        log.warning("="*80)
        log.warning("🚨 TRADING BLOCKED BY SAFETY SYSTEM")
        log.warning(f"   🚫 PRIMARY BLOCKING REASON: {reason}")
        log.warning(f"   ⏰ Time: {datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')}")
        log.warning("="*80)
        
        # Show ALL systems - mark which one(s) blocked
        
        # 1. VOLATILITY SAFETY SYSTEM
        vol_status = "❌ BLOCKED" if 'iv' in details or 'rv' in details else "✅ PASS"
        log.warning(f"   🌡️  VOLATILITY SAFETY SYSTEM: {vol_status}")
        log.warning(f"      IV: {volatility.get('iv', 0):.1f}% / {volatility.get('iv_threshold', 0):.1f}% limit")
        log.warning(f"      RV: {volatility.get('rv', 0):.1f}% / {volatility.get('rv_threshold', 0):.1f}% limit")
        log.warning(f"      Spread: {volatility.get('spread', 0):.1f}% / {volatility.get('spread_threshold', 0):.1f}% limit")
        log.warning(f"      Status: {volatility.get('status', 'UNKNOWN')}")
        
        # 2. PnL/LOSS LIMIT SAFETY SYSTEM
        current_pnl = pnl.get('pnl_inr', 0)
        pnl_status = "❌ BLOCKED" if 'pnl_inr' in details else "✅ PASS"
        log.warning(f"   💸 PnL/LOSS LIMIT SAFETY SYSTEM: {pnl_status}")
        log.warning(f"      Current PnL: ₹{current_pnl:.2f}")
        log.warning(f"      Max Loss Allowed: ₹{pnl.get('max_loss_limit', 0):.2f}")
        log.warning(f"      Utilization: {pnl.get('utilization_pct', 0):.1f}%")
        log.warning(f"      Breach Amount: ₹{pnl.get('breach_amount', 0):.2f}")
        log.warning(f"      Status: {pnl.get('status', 'UNKNOWN')}")
        
        # 3. POSITION SIZE SAFETY SYSTEM
        pos_status = "❌ BLOCKED" if 'position_size' in details else "✅ PASS"
        log.warning(f"   📈 POSITION SIZE SAFETY SYSTEM: {pos_status}")
        log.warning(f"      Total Position: {position.get('position_size', 0):.0f} contracts ({position.get('num_positions', 0)} positions)")
        
        # Show individual position breakdown
        breakdown = position.get('breakdown', [])
        if breakdown:
            log.warning("      Position Breakdown:")
            for pos in breakdown:
                emoji = "🟢" if pos['side'] == 'LONG' else "🔴"
                log.warning(f"        {emoji} {pos['symbol']}: {pos['size']:+.0f} contracts @ ₹{pos['mark']:.2f} (PnL: ₹{pos['pnl']:+.2f})")
        
        log.warning(f"      Max Position Allowed: {position.get('max_size', 0)} contracts")
        log.warning(f"      Utilization: {position.get('utilization_pct', 0):.1f}%")
        log.warning(f"      Status: {position.get('status', 'UNKNOWN')}")
        
        # 4. LIQUIDATION SAFETY SYSTEM
        liq_status = "❌ BLOCKED" if 'liquidation_distance' in details else "✅ PASS"
        log.warning(f"   🛡️  LIQUIDATION SAFETY SYSTEM: {liq_status}")
        log.warning(f"      Liquidation Distance: {liquidation.get('liquidation_distance', 0):.1f}%")
        log.warning(f"      Min Distance Required: {liquidation.get('min_distance', 0):.2f}%")
        log.warning(f"      Safety Buffer: {liquidation.get('buffer', 0):.1f}%")
        log.warning(f"      Safety Margin: {liquidation.get('safety_margin_pct', 0):.1f}%")
        log.warning(f"      Status: {liquidation.get('status', 'UNKNOWN')}")
        
        # 5. SYSTEM HEALTH
        health_blocked = "System health issue" in reason
        sys_status = "❌ BLOCKED" if health_blocked else "✅ PASS"
        log.warning(f"   💻 SYSTEM HEALTH CHECK: {sys_status}")
        
        if health.get('enabled', False):
            log.warning(f"      API Health: {'❌' if health_blocked and 'API' in health.get('issues', []) else '✅'}")
            log.warning(f"      WebSocket: {'❌' if health_blocked and 'WebSocket' in str(health.get('issues', [])) else '✅'}")
            log.warning(f"      Data Freshness: {'❌' if health_blocked and 'Data' in str(health.get('issues', [])) else '✅'}")
            if health.get('issues'):
                log.warning(f"      Issues: {', '.join(health['issues'])}")
        else:
            log.warning("      Status: Monitoring disabled")
        
        # 6. RSI SAFETY SYSTEM (Layer 6)
        rsi_blocked = "RSI" in reason
        rsi_status = "❌ BLOCKED" if rsi_blocked else "✅ PASS"
        bot_mode = rsi.get('bot_mode', 'LONG')
        log.warning(f"   📊 RSI SAFETY SYSTEM (Layer 6): {rsi_status}")
        if rsi.get('enabled', False):
            log.warning(f"      Bot Mode: {bot_mode}")
            log.warning(f"      Current RSI: {rsi.get('rsi', 0):.2f}")
            if bot_mode == "LONG":
                log.warning(f"      Long Threshold: {rsi.get('long_threshold'):.1f} (STOP when RSI <= this)")
            else:
                log.warning(f"      Short Threshold: {rsi.get('short_threshold'):.1f} (STOP when RSI >= this)")
            log.warning(f"      Period: {rsi.get('period', 14)}")
            log.warning(f"      Timeframe: {rsi.get('timeframe', '1h')}")
            log.warning(f"      Status: {rsi.get('status', 'UNKNOWN')}")
            if rsi_blocked:
                log.warning(f"      Breach Amount: {rsi.get('breach_amount', 0):.2f}")
            if rsi.get('hysteresis_active', False):
                log.warning(f"      Hysteresis: Active ({rsi.get('hysteresis_seconds', 60)}s delay at threshold)")
        else:
            log.warning("      Status: Monitoring disabled")
        
        log.warning("="*80)
        
        return {
            'signal': 'STOP',
            'reason': reason,
            'timestamp': time.time(),
            'details': details
        }
    
    def _publish_signal_to_database(self, signal_data: Dict):
        """Write signal to SQL database via EventStore"""
        try:
            # Determine event type based on signal
            event_type = (
                EventType.GUARDIAN_SIGNAL_GO if signal_data['signal'] == 'GO' 
                else EventType.GUARDIAN_SIGNAL_STOP
            )
            
            # Create event for EventStore
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                timestamp=signal_data['timestamp'],
                correlation_id=f"guardian_signal_{int(time.time())}",
                aggregate_id="guardian",
                data=signal_data,
                metadata={
                    'guardian_version': '1.0.0',
                    'config_version': self.config_hash,
                    'source': 'guardian_risk_engine'
                }
            )
            
            # Append to EventStore (SQL database)
            self.event_store.append_event(event)
            
            # Log status
            emoji = "🟢" if signal_data['signal'] == 'GO' else "🔴"
            log.info(f"{emoji} Signal: {signal_data['signal']} - {signal_data['reason']}")
            log.debug(f"   Event ID: {event.event_id}")
            
        except Exception as e:
            log.error(f"Failed to publish signal to database: {e}", exc_info=True)
    
    def _publish_stop_signal_to_database(self, reason: str):
        """Emergency STOP signal to database (used on errors)"""
        signal = self._make_stop_signal(reason, {})
        self._publish_signal_to_database(signal)
    
    # Helper methods to gather details for signal
    
    def _get_volatility_details(self) -> Dict:
        """Get current volatility metrics with thresholds from config.yaml"""
        if not self.volatility_collector:
            log.debug("Volatility collector not available - returning zeros")
            return {
                'iv': 0, 'rv': 0, 'spread': 0,
                'iv_threshold': getattr(self.config.safety.volatility, 'max_iv', 35),
                'rv_threshold': getattr(self.config.safety.volatility, 'max_rv', 40),
                'spread_threshold': getattr(self.config.safety.volatility, 'max_spread', 10)
            }
        
        try:
            vol_data = self.volatility_collector.get_latest_values()
            
            # Record data update for freshness tracking
            if hasattr(self, 'health_tracker') and self.health_tracker:
                self.health_tracker.record_data_update('volatility')
            
            # IV is direct value
            iv = vol_data.get('iv', {}).get('value', 0) if vol_data.get('iv') else 0
            
            # RV is nested by timeframe - use 1d (daily) as default
            rv_data = vol_data.get('rv', {})
            rv = rv_data.get('1d', {}).get('value', 0) if rv_data.get('1d') else 0
            
            # Spread from bid-ask (if available)
            spread = vol_data.get('spread', 0)
            
            # Get thresholds from config.yaml safety.volatility section (SINGLE SOURCE)
            iv_threshold = float(getattr(self.config.safety.volatility, 'max_iv', 35))
            rv_threshold = float(getattr(self.config.safety.volatility, 'max_rv', 40))
            spread_threshold = float(getattr(self.config.safety.volatility, 'max_spread', 10))
            
            return {
                'iv': iv,
                'rv': rv,
                'spread': spread,
                'iv_threshold': iv_threshold,
                'rv_threshold': rv_threshold,
                'spread_threshold': spread_threshold,
                'status': 'OK' if (iv <= iv_threshold and rv <= rv_threshold) else 'BREACH'
            }
        except Exception as e:
            log.error(f"❌ Error getting volatility details: {e}", exc_info=True)
            return {
                'iv': 0, 'rv': 0, 'spread': 0,
                'iv_threshold': 0, 'rv_threshold': 0, 'spread_threshold': 0,
                'error': str(e)
            }
    
    def _get_pnl_details(self) -> Dict:
        """Get MTM (Mark-to-Market) from liquidation monitor - SINGLE SOURCE OF TRUTH"""
        max_loss = getattr(self.config.guardian, 'max_account_loss_inr', 0)
        
        try:
            # ✅ ONLY SOURCE: Get status from liquidation monitor which calculates MTM
            mtm_inr = 0
            
            if hasattr(self, 'liquidation_monitor') and self.liquidation_monitor:
                status = self.liquidation_monitor.get_status()
                mtm_inr = status.get('total_unrealized_pnl', 0)  # MTM in INR (key: total_unrealized_pnl)
                
                # Record data update for freshness tracking (liquidation monitor also provides positions data)
                if hasattr(self, 'health_tracker') and self.health_tracker:
                    self.health_tracker.record_data_update('positions')
                    self.health_tracker.record_data_update('liquidation')
                
                log.debug(f"✅ MTM from liquidation monitor: ₹{mtm_inr:.2f}")
            else:
                log.warning("⚠️ Liquidation monitor not available - MTM = 0")
            
            return {
                'pnl_inr': mtm_inr,
                'max_loss_limit': max_loss,
                'breach_amount': abs(mtm_inr) - max_loss if mtm_inr < -max_loss else 0,
                'utilization_pct': (abs(mtm_inr) / max_loss * 100) if max_loss > 0 else 0,
                'status': 'BREACH' if mtm_inr < -max_loss else 'OK'
            }
        except Exception as e:
            log.error(f"❌ Error getting MTM: {e}", exc_info=True)
            return {'pnl_inr': 0, 'max_loss_limit': max_loss, 'error': str(e)}
    
    def _get_position_details(self) -> Dict:
        """Get ALL Delta Exchange positions from liquidation monitor (REAL-TIME API)"""
        max_size = getattr(self.config.safety, 'max_position_size', 0)
        
        try:
            # ✅ ONLY SOURCE: Get ALL positions from Delta Exchange API via liquidation monitor
            total_size = 0
            total_value = 0
            positions_breakdown = []
            
            if hasattr(self, 'liquidation_monitor') and self.liquidation_monitor:
                positions = self.liquidation_monitor.fetch_positions()
                
                # Record data update for freshness tracking
                if hasattr(self, 'health_tracker') and self.health_tracker:
                    self.health_tracker.record_data_update('positions')
                    self.health_tracker.record_data_update('liquidation')
                
                # Calculate totals and build breakdown
                for pos in positions:
                    abs_size = abs(pos.size)
                    total_size += abs_size
                    total_value += abs_size
                    
                    # Track each position for detailed logging
                    positions_breakdown.append({
                        'symbol': pos.symbol,
                        'size': pos.size,
                        'abs_size': abs_size,
                        'entry': pos.entry_price,
                        'mark': pos.mark_price,
                        'pnl': pos.unrealized_pnl,
                        'side': 'LONG' if pos.size > 0 else 'SHORT'
                    })
                
                log.debug(f"✅ Fetched {len(positions)} live positions from Delta Exchange API")
                log.debug(f"   Total position size: {total_size} contracts")
            else:
                log.warning("⚠️ Liquidation monitor not available - position = 0")
            
            return {
                'position_size': total_size,
                'position_value': total_value,
                'max_size': max_size,
                'utilization_pct': (total_size / max_size * 100) if max_size > 0 else 0,
                'status': 'BREACH' if (max_size > 0 and total_size > max_size) else 'OK',
                'breakdown': positions_breakdown,  # NEW: Individual position details
                'num_positions': len(positions_breakdown)
            }
        except Exception as e:
            log.error(f"❌ Error getting positions: {e}", exc_info=True)
            return {'position_size': 0, 'position_value': 0, 'max_size': max_size, 'error': str(e), 'breakdown': []}
    
    def _get_liquidation_details(self) -> Dict:
        """Get REAL liquidation distance from liquidation monitor"""
        min_distance = getattr(self.config.guardian, 'liquidation_critical', 60.0)
        
        try:
            # ✅ ONLY SOURCE: Get status from liquidation monitor
            distance_pct = 0
            
            if hasattr(self, 'liquidation_monitor') and self.liquidation_monitor:
                status = self.liquidation_monitor.get_status()
                distance_pct = status.get('liquidation_distance', 0)  # Key: liquidation_distance (already in %)
                
                # Record data update for freshness tracking
                if hasattr(self, 'health_tracker') and self.health_tracker:
                    self.health_tracker.record_data_update('liquidation')
                
                log.debug(f"✅ Liquidation distance: {distance_pct:.1f}%")
            else:
                log.warning("⚠️ Liquidation monitor not available - distance = 0")
            
            return {
                'liquidation_distance': distance_pct,
                'min_distance': min_distance,
                'buffer': distance_pct - min_distance,
                'safety_margin_pct': distance_pct,
                'status': 'BREACH' if distance_pct < min_distance else 'OK'
            }
        except Exception as e:
            log.error(f"❌ Error getting liquidation distance: {e}", exc_info=True)
            return {'liquidation_distance': 0, 'min_distance': min_distance, 'error': str(e)}
    
    def _get_health_details(self) -> Dict:
        """Get system health information"""
        if not hasattr(self, 'health_tracker') or not self.health_tracker:
            return {
                'enabled': False,
                'status': 'unavailable',
                'message': 'Health tracker not initialized'
            }
        
        health = self.health_tracker.get_health_status()
        
        # Check if exchange is in maintenance
        maintenance_mode = health.get('exchange_in_maintenance', False)
        maintenance_status = health.get('maintenance_status', {})
        
        return {
            'enabled': health.get('enabled', False),
            'system_healthy': health.get('system_healthy', True),
            'api_healthy': health.get('api', {}).get('healthy', True),
            'api_success_rate': health.get('api', {}).get('success_rate', 100.0),
            'websocket_connected': health.get('websocket', {}).get('connected', True),
            'websocket_stale_seconds': health.get('websocket', {}).get('stale_seconds', 0),
            'data_healthy': health.get('data_freshness', {}).get('healthy', True),
            'event_store_connected': health.get('event_store_connected', True),
            'exchange_in_maintenance': maintenance_mode,
            'maintenance_scheduled': maintenance_status.get('maintenance_scheduled', False) if maintenance_status else False,
            'issues': health.get('issues', []),
            'status': 'MAINTENANCE' if maintenance_mode else ('OK' if health.get('system_healthy', True) else 'UNHEALTHY'),
            'message': health.get('message', 'Unknown')
        }
    
    def _get_rsi_details(self) -> Dict:
        """Get RSI metrics for Layer 6 (mode-specific)"""
        rsi_config = getattr(self.config.safety, 'rsi', None)
        bot_mode = getattr(self.config.bot, 'mode', 'LONG').upper()
        
        if not rsi_config:
            return {
                'rsi': 0,
                'long_threshold': 0,
                'short_threshold': 0,
                'period': 14,
                'timeframe': '1h',
                'bot_mode': bot_mode,
                'status': 'DISABLED',
                'enabled': False
            }
        
        try:
            # No defaults - fail loudly if missing
            if not hasattr(rsi_config, 'long_threshold'):
                raise ValueError("safety.rsi.long_threshold missing in config.yaml")
            if not hasattr(rsi_config, 'short_threshold'):
                raise ValueError("safety.rsi.short_threshold missing in config.yaml")
            
            long_threshold = rsi_config.long_threshold
            short_threshold = rsi_config.short_threshold
            period = getattr(rsi_config, 'period', 14)
            timeframe = getattr(rsi_config, 'timeframe', '1h')
            enabled = getattr(rsi_config, 'enabled', True)
            hysteresis_seconds = getattr(rsi_config, 'hysteresis_seconds', 60)
            
            # Get current RSI
            rsi = None
            current_signal = None
            hysteresis_active = False
            if self.rsi_collector:
                rsi = self.rsi_collector.get_latest_rsi()
                current_signal = getattr(self.rsi_collector, '_current_signal', None)
                hysteresis_start = getattr(self.rsi_collector, '_hysteresis_start_time', None)
                if hysteresis_start is not None:
                    import time
                    elapsed = time.time() - hysteresis_start
                    hysteresis_active = elapsed < hysteresis_seconds
            
            if rsi is None:
                return {
                    'rsi': 0,
                    'long_threshold': long_threshold,
                    'short_threshold': short_threshold,
                    'period': period,
                    'timeframe': timeframe,
                    'bot_mode': bot_mode,
                    'status': 'UNAVAILABLE',
                    'enabled': enabled,
                    'message': 'RSI data unavailable'
                }
            
            # Determine status based on mode
            if bot_mode == "LONG":
                threshold = long_threshold
                if rsi >= threshold:
                    status = 'STOP'  # Overbought for LONG
                    breach_amount = rsi - threshold
                else:
                    status = 'GO'
                    breach_amount = 0
            else:  # SHORT mode
                threshold = short_threshold
                if rsi <= threshold:
                    status = 'STOP'  # Oversold for SHORT
                    breach_amount = threshold - rsi
                else:
                    status = 'GO'
                    breach_amount = 0
            
            return {
                'rsi': rsi,
                'long_threshold': long_threshold,
                'short_threshold': short_threshold,
                'threshold': threshold,  # Current mode's threshold
                'period': period,
                'timeframe': timeframe,
                'bot_mode': bot_mode,
                'status': status,
                'enabled': enabled,
                'breach_amount': breach_amount,
                'current_signal': current_signal,
                'hysteresis_active': hysteresis_active,
                'hysteresis_seconds': hysteresis_seconds
            }
        except Exception as e:
            log.error(f"❌ Error getting RSI details: {e}", exc_info=True)
            return {
                'rsi': 0,
                'long_threshold': 75.0,
                'short_threshold': 25.0,
                'status': 'ERROR',
                'error': str(e)
            }
    
    def shutdown(self):
        """Cleanup resources"""
        if self.config_observer:
            try:
                self.config_observer.stop()
                self.config_observer.join()
                log.info("Config watcher stopped")
            except Exception as e:
                log.error(f"Error stopping config watcher: {e}")
