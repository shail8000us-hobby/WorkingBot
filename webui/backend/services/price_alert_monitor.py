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

try:
    from webui.backend.sealed import sealed
except ImportError:
    def sealed(f): return f

logger = logging.getLogger(__name__)


class PriceAlertMonitor:
    """
    Background service that monitors prices and triggers alerts.
    """
    
    def __init__(self, check_interval: int = 5):
        """
        Initialize the price alert monitor.
        
        Args:
            check_interval: Seconds between price checks (default: 5)
        """
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_price: Optional[float] = None
        self._previous_price: Optional[float] = None
        self._last_check: Optional[datetime] = None
        
        # Load notification settings from database
        settings = AlertsDB.get_settings()
        self._notification_service = NotificationService(settings)
        logger.info(f"[PriceAlertMonitor] Initialized with Telegram: {bool(settings.get('telegram_bot_token'))}, Ntfy: {bool(settings.get('ntfy_topic'))}")
        
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
        if self._current_price != price:
            logger.debug(f"Price updated in monitor: ${price:,.2f}")
        self._previous_price = self._current_price
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
                    # Cross alerts trigger when price moves through the target level
                    if self._previous_price is not None:
                        prev_below = self._previous_price < target_price
                        curr_below = self._current_price < target_price
                        should_trigger = prev_below != curr_below  # True only on actual crossing
                    
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
            
    @sealed
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

        # F5: Execute conditional action if configured
        action_type = alert.get('action_type', 'none')
        if action_type and action_type != 'none':
            self._execute_action(alert, action_type)
        
    def _send_notifications(self, alert: dict, channels: str):
        """Send notifications for a triggered alert."""
        # Run async notification in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Use the unified send_alert method which handles logic internally
            results = loop.run_until_complete(
                self._notification_service.send_alert(alert, self._current_price)
            )
            
            # Analyze results to see if any notification was sent successfully
            success = False
            errors = []
            
            if results:
                for channel, result in results.items():
                    if result is True:
                        success = True
                    elif result is False:
                        errors.append(f"{channel} failed")
            
            error_msg = ", ".join(errors) if errors else None
            
            # Update history with outcome
            AlertsDB.update_alert_history(alert['id'], success, error_msg)
            
        except Exception as e:
            logger.error("Error sending notification: %s", e)
            # Log the crash to DB history too
            AlertsDB.update_alert_history(alert['id'], False, f"System Error: {str(e)}")
            
    def _execute_action(self, alert: dict, action_type: str):
        """F5: Execute a conditional action when an alert fires."""
        import json
        try:
            config = json.loads(alert.get('action_config') or '{}')
        except Exception:
            config = {}

        logger.info("[AlertAction] Executing action '%s' for alert %s", action_type, alert['id'])

        if action_type == 'close_position':
            symbol = config.get('symbol')
            if symbol:
                try:
                    from webui.backend.routes.options.options_control import _close_position_by_symbol
                    _close_position_by_symbol(symbol)
                    logger.info("[AlertAction] Closed position %s", symbol)
                except Exception as e:
                    logger.error("[AlertAction] Failed to close position %s: %s", symbol, e)

        elif action_type == 'log':
            logger.info("[AlertAction] Log-only action: alert %s at $%.2f",
                        alert['id'], self._current_price)
        # 'notify' is handled by _send_notifications — nothing extra needed

    @sealed
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
