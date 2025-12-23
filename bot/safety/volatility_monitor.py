"""
Real-Time Volatility Monitor - Live Market Risk Tracking

This module provides production-grade volatility monitoring for trading safety:
- Realized Volatility (RV): Calculated from actual price movements
- Implied Volatility (IV): Estimated from option pricing models
- Real-time tracking using live market data
- Safety thresholds to prevent trading in extreme conditions
- WebSocket integration for sub-second updates

Why Volatility Monitoring Matters:
- High volatility = Higher risk of stop-outs and liquidation
- Prevents trading during market crashes or flash crashes
- Adjusts position sizing based on current market conditions
- Protects capital during turbulent periods

Configuration (from YAML):
- safety.volatility.enabled
- safety.volatility.max_rv
- safety.volatility.check_interval
- safety.volatility.auto_resume

Author: GridBot Pro Risk Management System
Version: 1.0.0
"""

import os
import sys
import time
import json
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from collections import deque
from threading import Thread, Lock
from enum import Enum

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.loader import get_config

log = logging.getLogger("volatility_monitor")


class VolatilityZone(Enum):
    """Volatility risk zones"""
    SAFE = "SAFE"           # Normal volatility - safe to trade
    ELEVATED = "ELEVATED"   # Slightly high - trade with caution
    HIGH = "HIGH"           # High volatility - reduce position size
    EXTREME = "EXTREME"     # Extreme volatility - halt trading


class VolatilityMonitor:
    """
    Real-time volatility monitor with live data tracking.
    
    Features:
    - Real-time volatility calculation from price data
    - Rolling window analysis (configurable periods)
    - Multiple volatility metrics (RV, historical, intraday)
    - Safety thresholds and alerts
    - WebSocket-ready for live updates
    - Persistence for monitoring and alerts
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize volatility monitor.
        
        Args:
            config: Configuration dictionary or None to load from YAML
        """
        # Load YAML configuration
        yaml_config = get_config()
        
        # Merge with passed config (passed config takes precedence)
        self.config = config or {}
        
        # Load configuration from YAML with config dict override
        self.enabled = self.config.get('VOLATILITY_MONITOR_ENABLED', yaml_config.safety.volatility.enabled)
        self.rv_window = int(self.config.get('VOLATILITY_RV_WINDOW', 24))  # Hours (default 24)
        self.update_interval = int(self.config.get('VOLATILITY_UPDATE_INTERVAL', yaml_config.safety.volatility.check_interval))
        
        # Safety thresholds (annualized volatility %)
        self.threshold_elevated = float(self.config.get('VOLATILITY_THRESHOLD_ELEVATED', 40))
        self.threshold_high = float(self.config.get('VOLATILITY_THRESHOLD_HIGH', yaml_config.safety.volatility.max_rv))
        self.threshold_extreme = float(self.config.get('VOLATILITY_THRESHOLD_EXTREME', 80))
        
        # Halt trading if volatility exceeds this (use max_rv as baseline)
        self.halt_trading_threshold = float(self.config.get('VOLATILITY_HALT_THRESHOLD', yaml_config.safety.volatility.max_rv * 1.5))
        
        # Data storage
        self.price_history = deque(maxlen=int(self.rv_window * 3600 / 5))  # 5-second intervals
        self.volatility_history = deque(maxlen=1000)  # Last 1000 readings
        
        # Current state
        self.current_rv = 0.0
        self.current_zone = VolatilityZone.SAFE
        self.last_update = None
        self.is_running = False
        self.halt_trading = False
        
        # Thread safety
        self.lock = Lock()
        
        # Status file for persistence
        self.status_file = Path('.volatility_status.json')
        self.history_file = Path('bot/reports/volatility_history.json')
        
        # Ensure reports directory exists
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing history if available
        self._load_history()
        
        # Monitoring thread
        self.monitor_thread = None
        
        log.info(f"Volatility Monitor initialized (enabled={self.enabled})")
        log.info(f"  RV window: {self.rv_window}h")
        log.info(f"  Thresholds: ELEVATED={self.threshold_elevated}%, HIGH={self.threshold_high}%, EXTREME={self.threshold_extreme}%")
        log.info(f"  Halt threshold: {self.halt_trading_threshold}%")
    
    def _load_history(self):
        """Load historical volatility data from file"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    history_data = json.load(f)
                    # Load last 1000 entries into deque
                    for entry in history_data[-1000:]:
                        self.volatility_history.append(entry)
                log.info(f"📊 Loaded {len(self.volatility_history)} volatility history entries")
        except Exception as e:
            log.warning(f"Could not load volatility history: {e}")
    
    def start(self):
        """Start volatility monitoring in background thread"""
        if not self.enabled:
            log.info("Volatility monitor disabled in config")
            return
        
        if self.is_running:
            log.warning("Volatility monitor already running")
            return
        
        self.is_running = True
        self.monitor_thread = Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        log.info("✅ Volatility monitor started")
    
    def stop(self):
        """Stop volatility monitoring"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        log.info("Volatility monitor stopped")
    
    def add_price(self, price: float, timestamp: Optional[float] = None):
        """
        Add a new price point to the history.
        
        Args:
            price: Current price
            timestamp: Unix timestamp (default: now)
        """
        if timestamp is None:
            timestamp = time.time()
        
        with self.lock:
            self.price_history.append({
                'price': float(price),
                'timestamp': timestamp
            })
            
            # Update volatility if enough data
            if len(self.price_history) >= 10:
                self._calculate_volatility()
    
    def _calculate_volatility(self):
        """
        Calculate realized volatility from price history.
        
        Uses logarithmic returns and annualizes the result.
        """
        if len(self.price_history) < 2:
            return
        
        try:
            # Extract prices
            prices = np.array([p['price'] for p in self.price_history])
            
            # Calculate log returns
            returns = np.diff(np.log(prices))
            
            if len(returns) == 0:
                return
            
            # Calculate volatility (standard deviation of returns)
            std_dev = np.std(returns)
            
            # Annualize (assuming 5-second intervals)
            periods_per_year = 365 * 24 * 3600 / 5  # Number of 5-sec periods in a year
            annualized_vol = std_dev * np.sqrt(periods_per_year) * 100
            
            # Update current RV
            self.current_rv = float(annualized_vol)
            self.last_update = datetime.now()
            
            # Update zone
            self._update_zone()
            
            # Try to get IV from volatility tracker if available
            current_iv = None
            try:
                from bot.volatility.iv_rv_tracker import get_volatility_tracker
                vol_tracker = get_volatility_tracker()
                if vol_tracker and vol_tracker.current_iv is not None:
                    current_iv = vol_tracker.current_iv
            except Exception:
                pass  # IV not available, that's okay
            
            # Add to history with timestamp formatted for frontend
            history_entry = {
                'rv': round(self.current_rv, 2),
                'iv': round(current_iv, 2) if current_iv is not None else None,
                'zone': self.current_zone.value,
                'timestamp': time.time(),
                'time': datetime.now().isoformat()
            }
            self.volatility_history.append(history_entry)
            
            # Persist status and history
            self._save_status()
            self._save_history()
            
            # Log if zone changed or high volatility
            if self.current_zone in [VolatilityZone.HIGH, VolatilityZone.EXTREME]:
                log.warning(
                    f"⚠️  {self.current_zone.value} VOLATILITY: {self.current_rv:.1f}% "
                    f"(threshold: {self._get_zone_threshold()}%)"
                )
            
        except Exception as e:
            log.error(f"Error calculating volatility: {e}")
    
    def _update_zone(self):
        """Update volatility zone based on current RV"""
        old_zone = self.current_zone
        
        if self.current_rv >= self.halt_trading_threshold:
            self.current_zone = VolatilityZone.EXTREME
            self.halt_trading = True
        elif self.current_rv >= self.threshold_extreme:
            self.current_zone = VolatilityZone.EXTREME
            self.halt_trading = False
        elif self.current_rv >= self.threshold_high:
            self.current_zone = VolatilityZone.HIGH
            self.halt_trading = False
        elif self.current_rv >= self.threshold_elevated:
            self.current_zone = VolatilityZone.ELEVATED
            self.halt_trading = False
        else:
            self.current_zone = VolatilityZone.SAFE
            self.halt_trading = False
        
        # Log zone changes
        if old_zone != self.current_zone:
            log.info(f"🌊 Volatility zone changed: {old_zone.value} → {self.current_zone.value}")
    
    def _get_zone_threshold(self) -> float:
        """Get threshold for current zone"""
        if self.current_zone == VolatilityZone.EXTREME:
            return self.threshold_extreme
        elif self.current_zone == VolatilityZone.HIGH:
            return self.threshold_high
        elif self.current_zone == VolatilityZone.ELEVATED:
            return self.threshold_elevated
        else:
            return 0.0
    
    def _monitoring_loop(self):
        """Background monitoring loop"""
        log.info("Volatility monitoring loop started")
        
        while self.is_running:
            try:
                # Calculate volatility metrics
                with self.lock:
                    if len(self.price_history) >= 10:
                        self._calculate_volatility()
                
                # Sleep until next update
                time.sleep(self.update_interval)
                
            except Exception as e:
                log.error(f"Error in volatility monitoring loop: {e}")
                time.sleep(10)
        
        log.info("Volatility monitoring loop stopped")
    
    def _save_status(self):
        """Save current status to file for monitoring"""
        try:
            status = {
                'enabled': self.enabled,
                'current_rv': self.current_rv,
                'zone': self.current_zone.value,
                'halt_trading': self.halt_trading,
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'price_points': len(self.price_history),
                'thresholds': {
                    'elevated': self.threshold_elevated,
                    'high': self.threshold_high,
                    'extreme': self.threshold_extreme,
                    'halt': self.halt_trading_threshold
                }
            }
            
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
                
        except Exception as e:
            log.error(f"Error saving volatility status: {e}")
    
    def _save_history(self):
        """Save volatility history to file for charts"""
        try:
            # Convert deque to list for JSON serialization
            history_list = list(self.volatility_history)
            
            with open(self.history_file, 'w') as f:
                json.dump(history_list, f, indent=2)
                
        except Exception as e:
            log.error(f"Error saving volatility history: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current volatility status.
        
        Returns:
            dict: Current status with all metrics
        """
        with self.lock:
            return {
                'enabled': self.enabled,
                'is_running': self.is_running,
                'current_rv': round(self.current_rv, 2),
                'zone': self.current_zone.value,
                'halt_trading': self.halt_trading,
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'data_points': len(self.price_history),
                'window_hours': self.rv_window,
                'thresholds': {
                    'elevated': self.threshold_elevated,
                    'high': self.threshold_high,
                    'extreme': self.threshold_extreme,
                    'halt': self.halt_trading_threshold
                },
                'safety_status': {
                    'can_trade': not self.halt_trading,
                    'message': self._get_safety_message()
                }
            }
    
    def _get_safety_message(self) -> str:
        """Get safety message based on current state"""
        if self.halt_trading:
            return f"🛑 Trading HALTED - Extreme volatility ({self.current_rv:.1f}%)"
        elif self.current_zone == VolatilityZone.EXTREME:
            return f"⚠️  EXTREME volatility ({self.current_rv:.1f}%) - High risk"
        elif self.current_zone == VolatilityZone.HIGH:
            return f"⚠️  HIGH volatility ({self.current_rv:.1f}%) - Reduce exposure"
        elif self.current_zone == VolatilityZone.ELEVATED:
            return f"📊 Elevated volatility ({self.current_rv:.1f}%) - Trade with caution"
        else:
            return f"✅ Normal volatility ({self.current_rv:.1f}%) - Safe to trade"
    
    def get_historical_volatility(self, periods: int = 100) -> List[Dict[str, Any]]:
        """
        Get historical volatility readings.
        
        Args:
            periods: Number of historical periods to return
        
        Returns:
            list: Historical volatility data
        """
        with self.lock:
            return list(self.volatility_history)[-periods:]
    
    def should_halt_trading(self) -> Tuple[bool, str]:
        """
        Check if trading should be halted due to volatility.
        
        Returns:
            tuple: (should_halt, reason)
        """
        with self.lock:
            if not self.enabled:
                return False, "Volatility monitor disabled"
            
            if self.halt_trading:
                return True, f"Extreme volatility: {self.current_rv:.1f}% (threshold: {self.halt_trading_threshold}%)"
            
            return False, "Volatility within acceptable range"
    
    def get_position_size_multiplier(self) -> float:
        """
        Get position size multiplier based on volatility.
        
        Returns:
            float: Multiplier (0.0 to 1.0)
        """
        with self.lock:
            if not self.enabled:
                return 1.0
            
            if self.halt_trading:
                return 0.0  # No trading
            elif self.current_zone == VolatilityZone.EXTREME:
                return 0.3  # 30% of normal size
            elif self.current_zone == VolatilityZone.HIGH:
                return 0.5  # 50% of normal size
            elif self.current_zone == VolatilityZone.ELEVATED:
                return 0.75  # 75% of normal size
            else:
                return 1.0  # Normal size


# Global instance
_volatility_monitor = None


def get_volatility_monitor(config: Optional[Dict[str, Any]] = None) -> VolatilityMonitor:
    """
    Get singleton instance of VolatilityMonitor.
    
    Args:
        config: Configuration dictionary (only used on first call)
    
    Returns:
        VolatilityMonitor: Singleton instance
    """
    global _volatility_monitor
    if _volatility_monitor is None:
        _volatility_monitor = VolatilityMonitor(config=config)
    return _volatility_monitor


def update_volatility_from_price(price: float, timestamp: Optional[float] = None):
    """
    Convenience function to update volatility monitor with new price.
    
    Args:
        price: Current price
        timestamp: Unix timestamp (default: now)
    """
    monitor = get_volatility_monitor()
    if monitor.enabled:
        monitor.add_price(price, timestamp)
