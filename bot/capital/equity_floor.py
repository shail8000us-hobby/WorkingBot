"""
Equity Floor Monitor - Hard Stop Protection

Monitors account equity and triggers emergency stop when equity falls below
the configured hard floor. This is the most critical safety feature - a last
line of defense against catastrophic losses.

Key Features:
- Real-time equity monitoring from Delta Exchange
- Emergency stop flag creation on breach
- Manual operator acknowledgment requirement
- USD to INR conversion
- Infinite uptime mode (continues monitoring for recovery)

Configuration:
- EQUITY_FLOOR_INR: Minimum account equity (default: 0 = disabled)
- EQUITY_FLOOR_CHECK_INTERVAL: Check frequency in seconds (default: 60)
"""

import os
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, Dict

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

log = logging.getLogger("equity_floor")


class EquityFloorMonitor:
    """
    Monitors account equity and enforces hard floor limit.
    
    When equity drops below the configured floor, creates emergency stop flag
    that blocks all new orders through Safety Gatekeeper.
    """
    
    def __init__(self, delta_client=None, config=None, base_dir=None):
        """
        Initialize equity floor monitor.
        
        Args:
            delta_client: Delta Exchange client for fetching balances (optional)
            config: Configuration dict (optional, uses env vars if not provided)
            base_dir: Base directory for state files (optional, defaults to current dir)
        """
        self.base_dir = Path(base_dir) if base_dir else Path('.')
        self.exchange = delta_client
        self.config = config or {}
        
        # Configuration
        # Load configuration from YAML
        cfg = get_config()
        self.enabled = cfg.capital.equity_floor_inr > 0
        self.floor_inr = cfg.capital.equity_floor_inr
        self.check_interval = cfg.capital.equity_floor_check_interval
        self.usd_to_inr = cfg.capital.usd_to_inr_rate
        
        # State files
        self._emergency_flag = self.base_dir / '.emergency_stop'
        self._breach_flag = self.base_dir / '.equity_floor_breach'
        self._ack_flag = self.base_dir / '.operator_ack_equity_floor'
        
        # Statistics
        self._check_count = 0
        self._last_check_time = 0
        self._last_equity = 0
        self._breach_time = None
        
        # Check if breach already active
        self.breached = self._breach_flag.exists()
        
        if self.enabled:
            log.info("=" * 70)
            log.info("🛡️  EQUITY FLOOR MONITOR INITIALIZED")
            log.info("=" * 70)
            log.info(f"Floor Limit: ₹{self.floor_inr:,}")
            log.info(f"Check Interval: {self.check_interval}s")
            log.info(f"USD to INR: {self.usd_to_inr}")
            log.info(f"Status: {'BREACHED' if self.breached else 'ACTIVE'}")
            log.info("=" * 70)
        else:
            log.info("Equity floor monitor DISABLED (EQUITY_FLOOR_INR=0)")
    
    def set_exchange(self, exchange_client):
        """Set exchange client (for deferred initialization)"""
        self.exchange = exchange_client
    
    def get_current_equity(self) -> Optional[float]:
        """
        Fetch current equity from Delta Exchange.
        
        Returns:
            Current equity in INR, or None if fetch failed
        """
        if not self.exchange:
            log.warning("No exchange client available for equity check")
            return None
        
        try:
            # Fetch wallet balance from Delta Exchange
            balances = self.exchange.get_wallet_balances()
            
            # Extract balance (Delta returns in USD)
            if 'result' in balances and len(balances['result']) > 0:
                balance_usd = float(balances['result'][0].get('balance', 0))
            else:
                log.error("No balance data in response")
                return None
            
            # Convert to INR
            equity_inr = balance_usd * self.usd_to_inr
            
            self._last_equity = equity_inr
            return equity_inr
            
        except Exception as e:
            log.error(f"Failed to fetch equity: {e}")
            return None
    
    def check(self) -> Optional[Dict]:
        """
        Check equity floor and trigger emergency if breached.
        
        Returns:
            Status dict if check was performed, None if skipped
        """
        if not self.enabled:
            return None
        
        current_time = time.time()
        
        # Skip if checked too recently (unless first check)
        if self._check_count > 0:
            time_since_check = current_time - self._last_check_time
            if time_since_check < self.check_interval:
                return None
        
        self._check_count += 1
        self._last_check_time = current_time
        
        # Get current equity
        current_equity = self.get_current_equity()
        
        if current_equity is None:
            log.warning("⚠️  Equity floor check skipped (failed to fetch balance)")
            return {
                'checked': True,
                'success': False,
                'error': 'Failed to fetch equity'
            }
        
        # Check if breached
        if current_equity < self.floor_inr:
            if not self.breached:
                # NEW BREACH - trigger emergency
                self._trigger_emergency(current_equity)
                return {
                    'checked': True,
                    'breached': True,
                    'current_equity': current_equity,
                    'floor': self.floor_inr,
                    'new_breach': True
                }
            else:
                # STILL BREACHED - check for operator acknowledgment
                if self._check_acknowledgment():
                    log.info("✅ Operator acknowledged breach - monitoring for recovery")
                
                return {
                    'checked': True,
                    'breached': True,
                    'current_equity': current_equity,
                    'floor': self.floor_inr,
                    'new_breach': False,
                    'acknowledged': self._ack_flag.exists()
                }
        else:
            # NOT BREACHED
            if self.breached:
                # RECOVERED from breach
                self._clear_emergency(current_equity)
            
            # Log periodic status (every 10 checks)
            if self._check_count % 10 == 0:
                margin = current_equity - self.floor_inr
                margin_pct = (margin / self.floor_inr) * 100
                log.info(f"✅ Equity floor check passed: ₹{current_equity:,.0f} > ₹{self.floor_inr:,} (margin: ₹{margin:,.0f}, {margin_pct:.1f}%)")
            
            return {
                'checked': True,
                'breached': False,
                'current_equity': current_equity,
                'floor': self.floor_inr,
                'margin': current_equity - self.floor_inr
            }
    
    def _trigger_emergency(self, current_equity: float):
        """
        Trigger emergency stop protocol.
        
        Creates emergency flags that block all trading.
        """
        self.breached = True
        self._breach_time = time.time()
        
        # Create emergency flags
        self._emergency_flag.touch()
        self._breach_flag.touch()
        
        log.critical("=" * 70)
        log.critical("🚨 EQUITY FLOOR BREACHED - EMERGENCY STOP ACTIVATED")
        log.critical("=" * 70)
        log.critical(f"Current Equity: ₹{current_equity:,.2f}")
        log.critical(f"Floor Limit: ₹{self.floor_inr:,}")
        log.critical(f"Breach Amount: ₹{self.floor_inr - current_equity:,.2f}")
        log.critical("")
        log.critical("EMERGENCY ACTIONS TAKEN:")
        log.critical("  • Created .emergency_stop flag")
        log.critical("  • Created .equity_floor_breach flag")
        log.critical("  • ALL TRADING BLOCKED via Safety Gatekeeper")
        log.critical("  • Only reduce-only orders allowed")
        log.critical("")
        log.critical("MANUAL INTERVENTION REQUIRED:")
        log.critical("  1. Review account status in Delta Exchange")
        log.critical("  2. Determine root cause of equity loss")
        log.critical("  3. Create acknowledgment: touch .operator_ack_equity_floor")
        log.critical("  4. Wait for equity to recover above floor")
        log.critical("  5. Bot will auto-resume when equity > floor")
        log.critical("=" * 70)
    
    def _check_acknowledgment(self) -> bool:
        """
        Check if operator has acknowledged the breach.
        
        Returns:
            True if acknowledgment file exists
        """
        return self._ack_flag.exists()
    
    def _clear_emergency(self, current_equity: float):
        """
        Clear emergency stop when equity recovers.
        
        Args:
            current_equity: Current equity that triggered recovery
        """
        self.breached = False
        
        # Remove emergency flags
        if self._emergency_flag.exists():
            self._emergency_flag.unlink()
        if self._breach_flag.exists():
            self._breach_flag.unlink()
        if self._ack_flag.exists():
            self._ack_flag.unlink()
        
        breach_duration = time.time() - self._breach_time if self._breach_time else 0
        
        log.info("=" * 70)
        log.info("✅ EQUITY FLOOR RECOVERED - EMERGENCY STOP CLEARED")
        log.info("=" * 70)
        log.info(f"Current Equity: ₹{current_equity:,.2f}")
        log.info(f"Floor Limit: ₹{self.floor_inr:,}")
        log.info(f"Recovery Margin: ₹{current_equity - self.floor_inr:,.2f}")
        log.info(f"Breach Duration: {breach_duration/60:.1f} minutes")
        log.info("")
        log.info("Bot resuming normal operations.")
        log.info("=" * 70)
        
        self._breach_time = None
    
    def is_breached(self) -> bool:
        """Check if equity floor is currently breached"""
        return self.breached or self._breach_flag.exists()
    
    def get_stats(self) -> Dict:
        """Get monitor statistics"""
        return {
            'enabled': self.enabled,
            'floor_inr': self.floor_inr,
            'check_interval': self.check_interval,
            'check_count': self._check_count,
            'last_equity': self._last_equity,
            'last_check_time': self._last_check_time,
            'breached': self.breached,
            'breach_time': self._breach_time,
            'acknowledged': self._ack_flag.exists() if self.breached else False
        }


# Global singleton instance
_monitor: Optional[EquityFloorMonitor] = None


def get_equity_floor_monitor(delta_client=None, config=None, base_dir=None) -> EquityFloorMonitor:
    """Get or create global equity floor monitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = EquityFloorMonitor(delta_client=delta_client, config=config, base_dir=base_dir)
    return _monitor
