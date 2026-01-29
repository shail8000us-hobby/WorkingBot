"""
Price Alert Monitor Service

This service runs in the background and monitors BTC price against active alerts.
When an alert condition is met, it triggers notifications via configured channels.
"""

import asyncio
import logging
import threading
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Ensure proper import path
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

try:
    from db.alerts_db import AlertsDB
    from services.notifications import NotificationService
except ImportError:
    from ..db.alerts_db import AlertsDB
    from .notifications import NotificationService

logger = logging.getLogger(__name__)


class PriceAlertMonitor:
    """
    Background service that monitors prices and triggers alerts.
    """
    
    def __init__(self, check_interval: int = 30):
        """
        Initialize the price alert monitor.
        
        Args:
            check_interval: Seconds between price checks (default: 30)
        """
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_price: Optional[float] = None
        self._last_check: Optional[datetime] = None
        self._notification_service = NotificationService()
        
    def start(self):
        """Start the background monitoring thread."""
        if self._running:
            logger.warning("Price alert monitor already running")
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("✅ Price Alert Monitor started (checking every %d seconds)", self.check_interval)
        
    def stop(self):
        """Stop the background monitoring thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("⏹️ Price Alert Monitor stopped")
        
    def update_price(self, price: float):
        """
        Update the current price. Called by external price feeds.
        
        Args:
            price: Current BTC price
        """
        self._current_price = price
        
    def get_status(self) -> dict:
        """Get current monitor status."""
        return {
            'running': self._running,
            'current_price': self._current_price,
            'last_check': self._last_check.isoformat() if self._last_check else None,
            'check_interval': self.check_interval,
        }
        
    def _run_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                self._check_alerts()
                self._last_check = datetime.now()
            except Exception as e:
                logger.error("Error checking alerts: %s", e)
            
            time.sleep(self.check_interval)
            
    def _check_alerts(self):
        """Check all active alerts against current price."""
        if self._current_price is None:
            logger.debug("No current price available, skipping alert check")
            return
            
        # Get all active alerts
        alerts = AlertsDB.get_all_alerts(status='active')
        
        if not alerts:
            return
            
        triggered_count = 0
        
        for alert in alerts:
            try:
                target_price = float(alert['target_price'])
                direction = alert['direction']
                
                # Check if alert should trigger
                should_trigger = False
                
                if direction == 'above' and self._current_price >= target_price:
                    should_trigger = True
                elif direction == 'below' and self._current_price <= target_price:
                    should_trigger = True
                elif direction == 'cross':
                    # Cross alerts trigger on any crossing
                    should_trigger = True  # Simplified for now
                    
                if should_trigger:
                    # Check cooldown
                    if self._is_in_cooldown(alert):
                        logger.debug("Alert %s is in cooldown, skipping", alert['id'])
                        continue
                        
                    # Trigger the alert
                    self._trigger_alert(alert)
                    triggered_count += 1
                    
            except Exception as e:
                logger.error("Error processing alert %s: %s", alert.get('id'), e)
                
        if triggered_count > 0:
            logger.info("🔔 Triggered %d alert(s)", triggered_count)
            
    def _is_in_cooldown(self, alert: dict) -> bool:
        """Check if alert is still in cooldown period."""
        last_triggered = alert.get('last_triggered_at')
        cooldown_minutes = alert.get('cooldown_minutes', 60)
        
        if not last_triggered:
            return False
            
        try:
            last_time = datetime.fromisoformat(last_triggered)
            cooldown_end = last_time + timedelta(minutes=cooldown_minutes)
            return datetime.now() < cooldown_end
        except:
            return False
            
    def _trigger_alert(self, alert: dict):
        """Trigger a single alert - update DB and send notifications."""
        alert_id = alert['id']
        target_price = float(alert['target_price'])
        direction = alert['direction']
        note = alert.get('note', '')
        expiry_date = alert.get('expiry_date')
        expected_pnl = alert.get('expected_pnl_expiry')
        channels = alert.get('notification_channels', 'telegram,in_app')
        is_repeating = alert.get('is_repeating', False)
        
        logger.info("🔔 Triggering alert %s: BTC %s $%.2f (current: $%.2f)",
                   alert_id, direction, target_price, self._current_price)
        
        # Update alert status using existing trigger method
        AlertsDB.trigger_alert(alert_id, self._current_price)
        
        # Send notifications
        self._send_notifications(alert, channels)
        
    def _send_notifications(self, alert: dict, channels: str):
        """Send notifications for a triggered alert."""
        target_price = float(alert['target_price'])
        direction = alert['direction']
        note = alert.get('note', '')
        expiry_date = alert.get('expiry_date')
        expected_pnl = alert.get('expected_pnl_expiry')
        
        # Run async notification in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if 'telegram' in channels:
                loop.run_until_complete(
                    self._notification_service.send_alert_notification(
                        alert_type='price_alert',
                        message=self._format_alert_message(alert),
                        price=self._current_price,
                        target_price=target_price,
                        direction=direction,
                        expiry_date=expiry_date,
                        expected_pnl=expected_pnl,
                        note=note,
                        channels=['telegram']
                    )
                )
                
            if 'ntfy' in channels:
                loop.run_until_complete(
                    self._notification_service.send_alert_notification(
                        alert_type='price_alert',
                        message=self._format_alert_message(alert),
                        price=self._current_price,
                        target_price=target_price,
                        direction=direction,
                        expiry_date=expiry_date,
                        expected_pnl=expected_pnl,
                        note=note,
                        channels=['ntfy']
                    )
                )
        except Exception as e:
            logger.error("Error sending notification: %s", e)
        finally:
            loop.close()
            
    def _format_alert_message(self, alert: dict) -> str:
        """Format a human-readable alert message."""
        target_price = float(alert['target_price'])
        direction = alert['direction']
        note = alert.get('note', '')
        expiry_date = alert.get('expiry_date')
        expected_pnl = alert.get('expected_pnl_expiry')
        
        msg = f"🔔 BTC Price Alert!\n\n"
        msg += f"Price crossed {'above' if direction == 'above' else 'below'} ${target_price:,.0f}\n"
        msg += f"Current: ${self._current_price:,.2f}\n"
        
        if expiry_date:
            msg += f"Expiry: {expiry_date}\n"
            
        if expected_pnl is not None:
            pnl_sign = '+' if expected_pnl >= 0 else ''
            msg += f"Expected P&L: {pnl_sign}${expected_pnl:.2f}\n"
            
        if note:
            msg += f"\n📝 {note}"
            
        return msg


# Global instance
_price_alert_monitor: Optional[PriceAlertMonitor] = None


def get_price_alert_monitor() -> PriceAlertMonitor:
    """Get or create the global price alert monitor instance."""
    global _price_alert_monitor
    if _price_alert_monitor is None:
        _price_alert_monitor = PriceAlertMonitor()
    return _price_alert_monitor


def start_price_alert_monitor():
    """Start the global price alert monitor."""
    monitor = get_price_alert_monitor()
    monitor.start()
    return monitor


def stop_price_alert_monitor():
    """Stop the global price alert monitor."""
    global _price_alert_monitor
    if _price_alert_monitor:
        _price_alert_monitor.stop()
