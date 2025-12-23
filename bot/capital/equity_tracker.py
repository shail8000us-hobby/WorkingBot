"""
Equity Tracker - 30-Day Rolling Window Snapshot System

Tracks account equity over time to enable drawdown calculations.
Stores hourly snapshots for the last 30 days.

Key Features:
- Hourly equity snapshots
- 30-day rolling window
- Automatic pruning of old data
- Drawdown calculation from peak
- Protective mode logic
"""

import os
import json
import logging
import time
from pathlib import Path
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

log = logging.getLogger("equity_tracker")

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# YAML Config Integration
try:
    from config.loader import get_config
    YAML_CONFIG_AVAILABLE = True
except Exception:
    YAML_CONFIG_AVAILABLE = False
    def get_config(): return None


class EquityTracker:
    """
    Tracks account equity over time for drawdown monitoring.
    
    Maintains a rolling 30-day window of equity snapshots.
    """
    
    def __init__(self, base_dir: Path, liquidation_monitor=None):
        """
        Initialize equity tracker.
        
        Args:
            base_dir: Base directory for state files
            liquidation_monitor: Optional IntegratedLiquidationMonitor for real-time equity
        """
        self.base_dir = Path(base_dir)
        self.liquidation_monitor = liquidation_monitor
        
        # Load configuration from YAML
        yaml_config = get_config()
        
        # Determine mode from YAML config
        self.mode = yaml_config.trading_mode
        
        # Snapshot file
        self.snapshot_file = self.base_dir / f'equity_snapshots_{self.mode}.json'
        
        # Load drawdown cap configuration from YAML
        self.enabled = yaml_config.capital_protection.drawdown_cap.enabled
        self.max_drawdown_pct = yaml_config.capital_protection.drawdown_cap.max_pct
        self.window_days = yaml_config.capital_protection.drawdown_cap.window_days
        self.hysteresis_pct = yaml_config.capital_protection.drawdown_cap.hysteresis_pct
        
        # Load existing snapshots
        self.snapshots: List[Dict] = self._load_snapshots()
        
        # Protective mode state
        self.protective_mode_active = False
        self._protective_mode_flag = self.base_dir / '.drawdown_protective_mode'
        
        # Check if protective mode flag exists
        if self._protective_mode_flag.exists():
            self.protective_mode_active = True
        
        # Statistics
        self._snapshot_count = len(self.snapshots)
        self._last_snapshot_time = self.snapshots[-1]['timestamp'] if self.snapshots else 0
        
        if self.enabled:
            log.info("=" * 70)
            log.info("📉 EQUITY TRACKER INITIALIZED")
            log.info("=" * 70)
            log.info(f"Mode: {self.mode}")
            log.info(f"Snapshot File: {self.snapshot_file}")
            log.info(f"Max Drawdown: {self.max_drawdown_pct}%")
            log.info(f"Hysteresis: {self.hysteresis_pct}%")
            log.info(f"Window: {self.window_days} days")
            log.info(f"Existing Snapshots: {len(self.snapshots)}")
            log.info(f"Protective Mode: {'ACTIVE' if self.protective_mode_active else 'INACTIVE'}")
            log.info("=" * 70)
    
    def _load_snapshots(self) -> List[Dict]:
        """Load existing snapshots from file"""
        if not self.snapshot_file.exists():
            log.info(f"No existing snapshots found at {self.snapshot_file}, starting fresh")
            return []
        
        try:
            with open(self.snapshot_file, 'r') as f:
                data = json.load(f)
                log.info(f"Loaded {len(data)} equity snapshots from {self.snapshot_file}")
                return data
        except Exception as e:
            log.error(f"Failed to load snapshots: {e}")
            return []
    
    def _save_snapshots(self):
        """Save snapshots to file"""
        try:
            # Ensure directory exists
            self.snapshot_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.snapshot_file, 'w') as f:
                json.dump(self.snapshots, f, indent=2)
            
            log.debug(f"Saved {len(self.snapshots)} snapshots to {self.snapshot_file}")
        except Exception as e:
            log.error(f"Failed to save snapshots: {e}")
    
    def add_snapshot(self, equity_inr: float, force: bool = False) -> bool:
        """
        Add a new equity snapshot.
        
        Args:
            equity_inr: Current total equity in INR
            force: Force snapshot even if within same hour
            
        Returns:
            True if snapshot was added
        """
        if not self.enabled:
            return False
        
        current_time = time.time()
        
        # Check if we should take a snapshot (hourly, or forced)
        if not force and self.snapshots:
            last_snapshot = self.snapshots[-1]
            time_diff = current_time - last_snapshot['timestamp']
            
            # Only snapshot once per hour
            if time_diff < 3600:  # 3600 seconds = 1 hour
                log.debug(f"Skipping snapshot, last one was {time_diff/60:.1f} minutes ago")
                return False
        
        # Create snapshot
        snapshot = {
            'timestamp': current_time,
            'equity_inr': equity_inr,
            'date': datetime.fromtimestamp(current_time).isoformat()
        }
        
        self.snapshots.append(snapshot)
        self._snapshot_count += 1
        self._last_snapshot_time = current_time
        
        log.info(f"📸 Equity snapshot: ₹{equity_inr:,.2f} @ {snapshot['date']}")
        
        # Prune old snapshots (beyond window)
        self._prune_old_snapshots()
        
        # Save to disk
        self._save_snapshots()
        
        return True
    
    def _prune_old_snapshots(self):
        """Remove snapshots older than the configured window"""
        cutoff_time = time.time() - (self.window_days * 86400)  # 86400 seconds = 1 day
        
        original_count = len(self.snapshots)
        self.snapshots = [s for s in self.snapshots if s['timestamp'] >= cutoff_time]
        
        pruned = original_count - len(self.snapshots)
        if pruned > 0:
            log.debug(f"Pruned {pruned} old snapshots (older than {self.window_days} days)")
    
    def calculate_drawdown(self, current_equity: float) -> Tuple[float, float, float]:
        """
        Calculate current drawdown from peak.
        
        Args:
            current_equity: Current total equity in INR
            
        Returns:
            Tuple of (peak_equity, drawdown_pct, drawdown_inr)
        """
        if not self.enabled or not self.snapshots:
            return current_equity, 0.0, 0.0
        
        # Find peak equity in window
        peak_equity = max(s['equity_inr'] for s in self.snapshots)
        
        # Also consider current equity as potential peak
        peak_equity = max(peak_equity, current_equity)
        
        # Calculate drawdown
        if peak_equity > 0:
            drawdown_inr = peak_equity - current_equity
            drawdown_pct = (drawdown_inr / peak_equity) * 100
        else:
            drawdown_inr = 0.0
            drawdown_pct = 0.0
        
        return peak_equity, drawdown_pct, drawdown_inr
    
    def check_drawdown_limit(self, current_equity: float) -> Tuple[bool, Optional[str]]:
        """
        Check if drawdown limit is breached.
        
        Args:
            current_equity: Current total equity in INR
            
        Returns:
            Tuple of (breached: bool, message: Optional[str])
        """
        if not self.enabled:
            return False, None
        
        peak_equity, drawdown_pct, drawdown_inr = self.calculate_drawdown(current_equity)
        
        # Check if we should enter protective mode
        if not self.protective_mode_active and drawdown_pct >= self.max_drawdown_pct:
            self.protective_mode_active = True
            self._protective_mode_flag.touch()
            
            message = (
                f"⚠️ DRAWDOWN LIMIT BREACHED - PROTECTIVE MODE ACTIVATED ⚠️\n\n"
                f"Peak Equity (30-day): ₹{peak_equity:,.2f}\n"
                f"Current Equity: ₹{current_equity:,.2f}\n"
                f"Drawdown: ₹{drawdown_inr:,.2f} ({drawdown_pct:.1f}%)\n"
                f"Limit: {self.max_drawdown_pct}%\n\n"
                f"PROTECTIVE MODE ACTIONS:\n"
                f"• No new BUY orders allowed\n"
                f"• TP (exit) orders still active\n"
                f"• Allow positions to close naturally\n"
                f"• Auto-resume when drawdown < {self.hysteresis_pct}%\n\n"
                f"This is a SOFT STOP to prevent further losses.\n"
                f"Let your positions recover naturally."
            )
            
            log.warning("=" * 70)
            log.warning("⚠️  DRAWDOWN LIMIT BREACHED - PROTECTIVE MODE")
            log.warning("=" * 70)
            log.warning(f"Peak: ₹{peak_equity:,.2f}")
            log.warning(f"Current: ₹{current_equity:,.2f}")
            log.warning(f"Drawdown: {drawdown_pct:.1f}% (limit: {self.max_drawdown_pct}%)")
            log.warning("=" * 70)
            
            return True, message
        
        # Check if we should exit protective mode (hysteresis)
        elif self.protective_mode_active and drawdown_pct < self.hysteresis_pct:
            self.protective_mode_active = False
            
            if self._protective_mode_flag.exists():
                self._protective_mode_flag.unlink()
            
            message = (
                f"✅ DRAWDOWN RECOVERED - PROTECTIVE MODE DEACTIVATED ✅\n\n"
                f"Peak Equity (30-day): ₹{peak_equity:,.2f}\n"
                f"Current Equity: ₹{current_equity:,.2f}\n"
                f"Drawdown: ₹{drawdown_inr:,.2f} ({drawdown_pct:.1f}%)\n"
                f"Hysteresis Threshold: {self.hysteresis_pct}%\n\n"
                f"Bot resuming normal operations.\n"
                f"You can now place BUY orders again."
            )
            
            log.info("=" * 70)
            log.info("✅ DRAWDOWN RECOVERED - RESUMING NORMAL OPERATIONS")
            log.info("=" * 70)
            log.info(f"Drawdown: {drawdown_pct:.1f}% < {self.hysteresis_pct}%")
            log.info("=" * 70)
            
            return False, message
        
        return False, None
    
    def is_protective_mode_active(self) -> bool:
        """Check if protective mode is currently active"""
        return self.protective_mode_active
    
    def get_current_equity(self) -> float:
        """
        Get current equity from liquidation monitor (real-time WebSocket data).
        Falls back to latest snapshot if liquidation monitor not available.
        
        Returns:
            Current equity in INR
        """
        # Try to get real-time equity from liquidation monitor
        if self.liquidation_monitor:
            try:
                liq_status = self.liquidation_monitor.get_status()
                # Balance is at top level, not in 'margin' dict
                total_balance = liq_status.get('total_balance', 0)
                if total_balance > 0:
                    log.debug(f"Got current equity from liquidation monitor: ₹{total_balance:,.2f}")
                    return total_balance
            except Exception as e:
                log.warning(f"Failed to get equity from liquidation monitor: {e}")
        
        # Fallback to latest snapshot
        if self.snapshots:
            log.debug(f"Using latest snapshot for equity: ₹{self.snapshots[-1]['equity_inr']:,.2f}")
            return self.snapshots[-1]['equity_inr']
        
        return 0.0
    
    def get_stats(self) -> Dict:
        """Get tracker statistics"""
        # Get current equity from liquidation monitor (real-time) or snapshots (fallback)
        current_equity = self.get_current_equity()
        
        if not self.snapshots or current_equity == 0:
            return {
                'enabled': self.enabled,
                'snapshot_count': 0,
                'protective_mode': self.protective_mode_active,
                'peak_equity': 0,
                'current_equity': current_equity,
                'current_drawdown_pct': 0,
                'max_drawdown_pct': self.max_drawdown_pct,
                'hysteresis_pct': self.hysteresis_pct
            }
        
        peak_equity, drawdown_pct, drawdown_inr = self.calculate_drawdown(current_equity)
        
        return {
            'enabled': self.enabled,
            'snapshot_count': len(self.snapshots),
            'protective_mode': self.protective_mode_active,
            'window_days': self.window_days,
            'peak_equity': peak_equity,
            'current_equity': current_equity,
            'current_drawdown_pct': drawdown_pct,
            'current_drawdown_inr': drawdown_inr,
            'max_drawdown_pct': self.max_drawdown_pct,
            'hysteresis_pct': self.hysteresis_pct,
            'utilization_pct': (drawdown_pct / self.max_drawdown_pct * 100) if self.max_drawdown_pct > 0 else 0,
            'last_snapshot_time': self._last_snapshot_time
        }
    
    def reset(self):
        """Reset tracker (clear all snapshots)"""
        self.snapshots.clear()
        self._save_snapshots()
        
        self.protective_mode_active = False
        if self._protective_mode_flag.exists():
            self._protective_mode_flag.unlink()
        
        log.warning("Equity tracker reset - cleared all snapshots and protective mode")


# Global singleton instance
_tracker: Optional[EquityTracker] = None


def get_equity_tracker(base_dir: Path = Path('.'), liquidation_monitor=None) -> EquityTracker:
    """Get or create global equity tracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = EquityTracker(base_dir, liquidation_monitor)
    elif liquidation_monitor and not _tracker.liquidation_monitor:
        # Update existing tracker with liquidation monitor
        _tracker.liquidation_monitor = liquidation_monitor
    return _tracker

