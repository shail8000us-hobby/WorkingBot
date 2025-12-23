# bot/pnl_history.py
"""
PnL History Logger
Tracks position PnL over time for analysis and reporting
"""
from __future__ import annotations

import os
import csv
import logging
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

log = logging.getLogger("runner")


class PnLHistoryLogger:
    """
    Logs PnL history to CSV for analysis
    
    Features:
    - Time-series PnL tracking
    - Position count tracking
    - Margin ratio tracking
    - Risk level tracking
    - Daily rotation
    """
    
    def __init__(self, log_dir: str = "bot/reports"):
        """
        Initialize PnL history logger
        
        Args:
            log_dir: Directory to store CSV files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # CSV file path (rotates daily)
        self.csv_file = self._get_csv_file()
        
        # Ensure headers exist
        self._ensure_headers()
        
        log.info(f"PnL History Logger initialized: {self.csv_file}")
    
    def _get_csv_file(self) -> Path:
        """Get today's CSV file path"""
        today = datetime.now().strftime("%Y%m%d")
        return self.log_dir / f"pnl_history_{today}.csv"
    
    def _ensure_headers(self) -> None:
        """Ensure CSV file has headers"""
        if not self.csv_file.exists():
            try:
                with open(self.csv_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'timestamp',
                        'open_positions',
                        'total_pnl_usd',
                        'total_pnl_inr',
                        'risk_percent',
                        'avg_margin_ratio',
                        'min_margin_ratio',
                        'positions_at_risk',
                        'overall_liq_risk',
                        'status'
                    ])
                log.info(f"Created new PnL history file: {self.csv_file}")
            except Exception as e:
                log.error(f"Failed to create PnL history file: {e}")
    
    def log_snapshot(self, summary: Dict[str, Any]) -> None:
        """
        Log a snapshot of current PnL state
        
        Args:
            summary: Summary dictionary from PositionTracker
        """
        try:
            # Check if we need to rotate to a new file
            current_file = self._get_csv_file()
            if current_file != self.csv_file:
                self.csv_file = current_file
                self._ensure_headers()
            
            # Determine status
            risk_percent = summary.get("risk_percent", 0)
            overall_liq_risk = summary.get("overall_liq_risk", "low")
            
            if overall_liq_risk == "critical" or risk_percent >= 90:
                status = "critical"
            elif overall_liq_risk == "high" or risk_percent >= 75:
                status = "danger"
            elif overall_liq_risk == "medium" or risk_percent >= 50:
                status = "warning"
            else:
                status = "safe"
            
            # Write row
            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    summary.get("total_positions", 0),
                    f"{summary.get('total_pnl_usd', 0):.2f}",
                    f"{summary.get('total_pnl_inr', 0):.2f}",
                    f"{risk_percent:.2f}",
                    f"{summary.get('avg_margin_ratio', 0):.4f}",
                    f"{summary.get('min_margin_ratio', 0):.4f}",
                    summary.get("positions_at_risk", 0),
                    overall_liq_risk,
                    status
                ])
            
            log.debug(f"PnL snapshot logged: {status}")
            
        except Exception as e:
            log.error(f"Failed to log PnL snapshot: {e}")
    
    def get_recent_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent history entries
        
        Args:
            limit: Maximum number of entries to return
        
        Returns:
            List of history entries
        """
        try:
            if not self.csv_file.exists():
                return []
            
            history = []
            with open(self.csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    history.append(row)
            
            # Return most recent entries
            return history[-limit:] if len(history) > limit else history
            
        except Exception as e:
            log.error(f"Failed to read PnL history: {e}")
            return []
    
    def cleanup_old_files(self, days_to_keep: int = 30) -> int:
        """
        Clean up old PnL history files
        
        Args:
            days_to_keep: Number of days to keep
        
        Returns:
            Number of files deleted
        """
        try:
            from datetime import timedelta
            
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            deleted = 0
            
            for file in self.log_dir.glob("pnl_history_*.csv"):
                try:
                    # Extract date from filename
                    date_str = file.stem.split('_')[-1]
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                    
                    if file_date < cutoff_date:
                        file.unlink()
                        deleted += 1
                        log.info(f"Deleted old PnL history: {file.name}")
                        
                except Exception:
                    continue
            
            return deleted
            
        except Exception as e:
            log.error(f"Failed to cleanup old PnL files: {e}")
            return 0


class LiquidationAlertManager:
    """
    Manages Telegram alerts for liquidation risks
    
    Features:
    - Threshold-based alerts
    - Alert deduplication
    - Multi-level warnings
    - Daily summaries
    """
    
    def __init__(self):
        """Initialize alert manager"""
        self.notifier = None
        try:
            from bot.utils.notifier import TelegramNotifier
            self.notifier = TelegramNotifier()
            self.enabled = getattr(self.notifier, "enabled", False)
        except Exception:
            self.enabled = False
        
        # Alert state tracking to prevent spam
        self._last_alert_level = {}  # position_id -> level
        self._last_summary_time = 0
        
        if self.enabled:
            log.info("✅ Liquidation Alert Manager enabled")
        else:
            log.info("Liquidation Alert Manager disabled (Telegram not configured)")
    
    def check_and_alert(self, position, force: bool = False) -> None:
        """
        Check position and send alerts if needed
        
        Args:
            position: Position object
            force: Force send alert even if already sent
        """
        if not self.enabled:
            return
        
        try:
            risk_level = position.liquidation.risk_level
            position_id = position.id
            
            # Check if we've already alerted for this level
            last_level = self._last_alert_level.get(position_id)
            
            # Only alert if:
            # 1. Force flag is set, OR
            # 2. Risk level has worsened, OR
            # 3. We haven't alerted for this position yet
            if not force and last_level == risk_level:
                return
            
            # Prepare alert message
            if risk_level == "critical":
                emoji = "🚨"
                title = "CRITICAL LIQUIDATION RISK"
            elif risk_level == "danger":
                emoji = "🔸"
                title = "DANGER: Liquidation Risk"
            elif risk_level == "warning":
                emoji = "⚠️"
                title = "WARNING: Margin Low"
            else:
                # Don't alert for safe positions
                return
            
            message = (
                f"{emoji} {title}\n"
                f"\n"
                f"Position: {position_id}\n"
                f"Entry: ₹{position.entry_price:,.2f}\n"
                f"Current: ₹{position.current_price:,.2f}\n"
                f"Liquidation: ₹{position.liquidation.liquidation_price:,.2f}\n"
                f"\n"
                f"Distance to Liq: {position.liquidation.distance_to_liq_percent:.2f}%\n"
                f"Margin Ratio: {position.margin.margin_ratio * 100:.0f}%\n"
                f"PnL: ${position.pnl_usd:.2f} / ₹{position.pnl_inr:,.2f}\n"
            )
            
            if position.liquidation.auto_topup_count > 0:
                message += f"\nAuto Top-Ups: {position.liquidation.auto_topup_count}"
            
            self.notifier.send(message)
            self._last_alert_level[position_id] = risk_level
            
            log.info(f"Liquidation alert sent for {position_id}: {risk_level}")
            
        except Exception as e:
            log.error(f"Failed to send liquidation alert: {e}")
    
    def send_daily_summary(self, summary: Dict[str, Any]) -> None:
        """
        Send daily PnL summary
        
        Args:
            summary: Summary dictionary from PositionTracker
        """
        if not self.enabled:
            return
        
        try:
            # Check if we've already sent summary today
            import time
            now = time.time()
            if now - self._last_summary_time < 86400:  # 24 hours
                return
            
            total_pnl_usd = summary.get("total_pnl_usd", 0)
            total_pnl_inr = summary.get("total_pnl_inr", 0)
            total_positions = summary.get("total_positions", 0)
            positions_at_risk = summary.get("positions_at_risk", 0)
            risk_percent = summary.get("risk_percent", 0)
            
            # Determine emoji based on PnL
            if total_pnl_inr >= 1000:
                emoji = "🎉"
            elif total_pnl_inr >= 0:
                emoji = "✅"
            elif total_pnl_inr >= -1000:
                emoji = "⚠️"
            else:
                emoji = "🚨"
            
            message = (
                f"{emoji} Daily PnL Summary\n"
                f"\n"
                f"Total PnL: ${total_pnl_usd:.2f} / ₹{total_pnl_inr:,.2f}\n"
                f"Open Positions: {total_positions}\n"
                f"Positions at Risk: {positions_at_risk}\n"
                f"Risk Level: {risk_percent:.1f}% of limit\n"
            )
            
            self.notifier.send(message)
            self._last_summary_time = now
            
            log.info("Daily summary sent")
            
        except Exception as e:
            log.error(f"Failed to send daily summary: {e}")

