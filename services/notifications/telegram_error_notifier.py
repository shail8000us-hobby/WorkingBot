"""
Telegram Error Notifier

Sends formatted error notifications to Telegram with:
- Escalation policy (immediate for critical, delayed for lower severity)
- Rich formatting with emojis and markdown
- Rate limiting and cooldown logic
- Command support (/ack, /resolve, /fix)
- Interactive buttons for actions

Environment Variables:
- TELEGRAM_BOT_TOKEN: Bot token from @BotFather
- TELEGRAM_CHAT_ID: Target chat ID
- TELEGRAM_ERROR_NOTIFICATIONS: Enable/disable (true/false)
- TELEGRAM_MIN_SEVERITY: Minimum severity to notify (critical/high/medium/low)
"""

import os
import time
import logging
from typing import Dict, Optional, List

# Load YAML config
from config.loader import get_config
from datetime import datetime, timedelta
import requests
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class TelegramErrorNotifier:
    """Sends error notifications to Telegram with escalation policy"""
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: bool = True,
        min_severity: str = "high"
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = enabled and bool(self.bot_token) and bool(self.chat_id)
        self.min_severity = min_severity
        self.health_lock = Lock()
        self._health = {
            'enabled': self.enabled,
            'connected': False,
            'message': 'Telegram disabled (missing token or chat ID)' if not self.enabled else 'Initializing',
            'last_checked': None,
            'error': None
        }
        
        # Escalation delays (severity -> delay in seconds)
        self.escalation_delays = {
            "critical": 0,  # Immediate
            "high": 600,  # 10 minutes
            "medium": 3600,  # 1 hour
            "low": float('inf')  # Never (unless explicitly requested)
        }
        
        # Rate limiting: max 20 messages per hour
        self.rate_limit_window = 3600  # 1 hour
        self.rate_limit_max = 20
        self.message_timestamps: List[float] = []
        self.lock = Lock()
        
        # Cooldown per error (prevent spam)
        self.error_cooldowns: Dict[str, float] = {}  # error_id -> last_sent_time
        self.cooldown_duration = 300  # 5 minutes
        
        # Thread for delayed notifications
        self.pending_notifications: List[Dict] = []
        self.notifier_thread = None
        self.running = False
        
        if self.enabled:
            logger.info("✅ Telegram Error Notifier initialized")
            logger.info(f"   Bot Token: {self.bot_token[:10]}...")
            logger.info(f"   Chat ID: {self.chat_id}")
            logger.info(f"   Min Severity: {self.min_severity}")
            self.perform_health_check()
        else:
            logger.warning("⚠️ Telegram Error Notifier disabled (missing token or chat ID)")
    
    def start(self):
        """Start background notifier thread"""
        if not self.enabled:
            return
        
        self.perform_health_check()

        self.running = True
        self.notifier_thread = Thread(target=self._notification_worker, daemon=True)
        self.notifier_thread.start()
        logger.info("🚀 Telegram notifier thread started")
    
    def stop(self):
        """Stop background notifier thread"""
        self.running = False
        if self.notifier_thread:
            self.notifier_thread.join(timeout=5)
            logger.info("🛑 Telegram notifier thread stopped")
    
    def notify_error(self, error: Dict) -> bool:
        """
        Queue error notification with escalation policy
        
        Returns:
            True if notification was queued/sent, False if skipped
        """
        if not self.enabled:
            return False
        
        # Check severity threshold
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        min_severity_level = severity_order.get(self.min_severity, 1)
        error_severity_level = severity_order.get(error.get("severity", "low"), 3)
        
        if error_severity_level > min_severity_level:
            logger.debug(f"Skipping notification for {error['id']} (severity too low)")
            return False
        
        # Check cooldown
        error_id = error["id"]
        now = time.time()
        
        with self.lock:
            last_sent = self.error_cooldowns.get(error_id, 0)
            if now - last_sent < self.cooldown_duration:
                logger.debug(f"Skipping notification for {error_id} (cooldown)")
                return False
        
        # Check rate limit
        if not self._check_rate_limit():
            logger.warning("⚠️ Telegram rate limit reached, skipping notification")
            return False
        
        # Get escalation delay
        delay = self.escalation_delays.get(error.get("severity", "low"), 0)
        
        if delay == 0:
            # Send immediately
            self._send_notification(error)
        else:
            # Queue for delayed sending
            with self.lock:
                self.pending_notifications.append({
                    "error": error,
                    "scheduled_time": now + delay
                })
            logger.info(f"📅 Queued notification for {error_id} (delay: {delay}s)")
        
        return True
    
    def _notification_worker(self):
        """Background worker for delayed notifications"""
        while self.running:
            try:
                now = time.time()
                to_send = []
                
                with self.lock:
                    # Find notifications ready to send
                    remaining = []
                    for notification in self.pending_notifications:
                        if notification["scheduled_time"] <= now:
                            to_send.append(notification["error"])
                        else:
                            remaining.append(notification)
                    self.pending_notifications = remaining
                
                # Send notifications
                for error in to_send:
                    self._send_notification(error)
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in notification worker: {e}")
                self._update_health(False, "Notification worker error", str(e))
                self.perform_health_check()
                time.sleep(60)
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        now = time.time()
        
        with self.lock:
            # Remove old timestamps
            self.message_timestamps = [
                ts for ts in self.message_timestamps
                if now - ts < self.rate_limit_window
            ]
            
            # Check limit
            if len(self.message_timestamps) >= self.rate_limit_max:
                return False
            
            return True
    
    def _record_message_sent(self):
        """Record that a message was sent"""
        with self.lock:
            self.message_timestamps.append(time.time())
    
    def _update_health(self, connected: bool, message: str, error: Optional[str] = None):
        """Update internal Telegram health snapshot"""
        with self.health_lock:
            self._health.update({
                'connected': connected,
                'message': message,
                'last_checked': datetime.now().isoformat(),
                'error': error
            })
    
    def perform_health_check(self) -> bool:
        """Probe Telegram API to validate bot connectivity"""
        if not self.enabled:
            return False
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{self.bot_token}/getMe",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    result = data.get('result', {})
                    username = result.get('username') or result.get('first_name') or 'bot'
                    label = f"Connected as @{username}" if username else "Connected"
                    self._update_health(True, label, None)
                    return True
                description = data.get('description') or response.text
                self._update_health(False, "Telegram API error", description)
            else:
                self._update_health(False, "Telegram API error", response.text)
        except Exception as exc:
            self._update_health(False, "Telegram connectivity failed", str(exc))
        return False
    
    def get_status(self) -> Dict[str, Optional[str]]:
        """Return current Telegram connectivity status"""
        with self.health_lock:
            return dict(self._health)
    
    def _send_notification(self, error: Dict):
        """Send formatted error notification to Telegram"""
        try:
            message = self._format_error_message(error)
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"✅ Sent Telegram notification for {error['id']}")

                with self.lock:
                    self.error_cooldowns[error["id"]] = time.time()

                self._record_message_sent()
                self._update_health(True, "Last notification delivered", None)
                return True

            logger.error(f"❌ Failed to send Telegram notification: {response.text}")
            self._update_health(False, "Telegram send failed", response.text)
            return False
        
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            self._update_health(False, "Telegram send failed", str(e))
            return False
    
    def _format_error_message(self, error: Dict) -> str:
        """Format error as rich Telegram message"""
        
        # Severity emoji
        severity_emoji = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "ℹ️",
            "low": "💡"
        }
        emoji = severity_emoji.get(error.get("severity", "low"), "❓")
        
        # Source emoji
        source_emoji = {
            "trading": "🤖",
            "guardian": "🛡️",
            "health": "❤️",
            "system": "⚙️"
        }
        source_icon = source_emoji.get(error.get("source", "system"), "📦")
        
        # Build message
        lines = [
            f"{emoji} *{error.get('severity', 'unknown').upper()} ERROR*",
            f"{source_icon} *Source:* {error.get('source', 'unknown').title()} Bot",
            "",
            f"*Code:* `{error.get('code', 'UNKNOWN')}`",
            f"*Message:* {error.get('message_raw', 'No message')}",
        ]
        
        # Count
        count = error.get("count", 1)
        if count > 1:
            lines.append(f"*Occurrences:* {count}")
        
        # Explanation
        explanation = error.get("explanation")
        if explanation:
            lines.append("")
            lines.append(f"*Explanation:* {explanation}")
        
        # Likely causes
        causes = error.get("likely_causes", [])
        if causes:
            lines.append("")
            lines.append("*Likely Causes:*")
            for cause in causes[:2]:  # Max 2 causes to keep message short
                lines.append(f"  • {cause}")
        
        # Auto-fix available
        if error.get("can_auto_fix"):
            fix_id = error.get("fix_id")
            lines.append("")
            lines.append(f"✅ *Auto-fix available:* `{fix_id}`")
            lines.append(f"Run: `/fix {error['id']} {fix_id}`")
        
        # Timestamps
        first_seen = error.get("first_seen", "")
        last_seen = error.get("last_seen", "")
        if first_seen:
            lines.append("")
            lines.append(f"*First Seen:* {self._format_timestamp(first_seen)}")
        if last_seen and last_seen != first_seen:
            lines.append(f"*Last Seen:* {self._format_timestamp(last_seen)}")
        
        # Actions
        lines.append("")
        lines.append(f"*Quick Actions:*")
        lines.append(f"  `/ack {error['id']}` - Acknowledge")
        lines.append(f"  `/resolve {error['id']}` - Mark Resolved")
        
        # WebUI link (if available)
        cfg = get_config()
        webui_url = cfg.webui.url.default if hasattr(cfg, 'webui') and hasattr(cfg.webui, 'url') else "http://localhost:5555"
        lines.append("")
        lines.append(f"[Open in WebUI]({webui_url})")
        
        return "\n".join(lines)
    
    def _format_timestamp(self, timestamp: str) -> str:
        """Format ISO timestamp for display"""
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return timestamp
    
    def send_custom_message(self, message: str):
        """Send a custom message to Telegram"""
        if not self.enabled:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Sent custom Telegram message")
                self._record_message_sent()
            else:
                logger.error(f"❌ Failed to send custom message: {response.text}")
        
        except Exception as e:
            logger.error(f"Error sending custom message: {e}")
    
    def send_test_notification(self):
        """Send a test notification"""
        test_error = {
            "id": "test-error-123",
            "severity": "medium",
            "source": "system",
            "code": "TEST_ERROR",
            "message_raw": "This is a test error notification from the Error Intelligence System",
            "explanation": "If you can see this, Telegram notifications are working correctly!",
            "likely_causes": [
                "Someone triggered a test notification",
                "The system is verifying Telegram integration"
            ],
            "can_auto_fix": False,
            "count": 1,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat()
        }
        
        self._send_notification(test_error)
