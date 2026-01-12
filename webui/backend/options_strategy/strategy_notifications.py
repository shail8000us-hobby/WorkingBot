"""
Strategy Alerts & Notifications
===============================
Notification system for strategy events.

Notification Channels:
- WebSocket (real-time UI updates)
- Desktop notifications
- Email (optional)
- Webhook (optional)

Events:
- Strategy executed
- Leg filled/partial fill
- Exit condition triggered
- Strategy closed
- Profit target reached
- Stop loss hit
- Days to expiry warning

Created: January 5, 2026
Phase 3: Automation & Monitoring
"""

import sys
import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

log = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationChannel(str, Enum):
    """Notification delivery channels"""
    WEBSOCKET = "websocket"
    DESKTOP = "desktop"
    EMAIL = "email"
    WEBHOOK = "webhook"
    ALL = "all"


@dataclass
class StrategyNotification:
    """Notification data structure"""
    id: str
    timestamp: str
    event_type: str
    strategy_id: Optional[str]
    strategy_name: Optional[str]
    title: str
    message: str
    notification_type: NotificationType
    data: Dict = field(default_factory=dict)
    read: bool = False
    channels: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy_name,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type.value,
            'data': self.data,
            'read': self.read,
            'channels': self.channels
        }


class StrategyNotificationService:
    """
    Notification service for strategy events
    
    Features:
    - Multi-channel delivery (WebSocket, Desktop, Email)
    - Notification history
    - Event-based triggers
    - Configurable alerts
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        
        # Notification history (in-memory, limited)
        self._notifications: List[StrategyNotification] = []
        self._max_history = 100
        
        # WebSocket callbacks
        self._websocket_handlers: List[Callable] = []
        
        # Channel settings
        self._enabled_channels = {
            NotificationChannel.WEBSOCKET: True,
            NotificationChannel.DESKTOP: False,
            NotificationChannel.EMAIL: False,
            NotificationChannel.WEBHOOK: False,
        }
        
        # Email/Webhook settings
        self._email_config: Optional[Dict] = None
        self._webhook_url: Optional[str] = None
        
        # Notification counter for IDs
        self._counter = 0
        
        self._initialized = True
        log.info("🔔 StrategyNotificationService initialized")
    
    # ==================== Configuration ====================
    
    def configure_channel(self, channel: NotificationChannel, enabled: bool):
        """Enable/disable notification channel"""
        self._enabled_channels[channel] = enabled
        log.info(f"Channel {channel.value}: {'enabled' if enabled else 'disabled'}")
    
    def configure_email(self, smtp_config: Dict):
        """Configure email notifications"""
        self._email_config = smtp_config
        self._enabled_channels[NotificationChannel.EMAIL] = True
        log.info("Email notifications configured")
    
    def configure_webhook(self, webhook_url: str):
        """Configure webhook notifications"""
        self._webhook_url = webhook_url
        self._enabled_channels[NotificationChannel.WEBHOOK] = True
        log.info(f"Webhook configured: {webhook_url[:50]}...")
    
    # ==================== WebSocket Registration ====================
    
    def register_websocket_handler(self, handler: Callable):
        """Register handler for WebSocket notifications"""
        if handler not in self._websocket_handlers:
            self._websocket_handlers.append(handler)
            log.debug(f"Registered WebSocket handler: {handler.__name__}")
    
    def unregister_websocket_handler(self, handler: Callable):
        """Unregister WebSocket handler"""
        if handler in self._websocket_handlers:
            self._websocket_handlers.remove(handler)
    
    # ==================== Send Notifications ====================
    
    def notify(
        self,
        event_type: str,
        title: str,
        message: str,
        strategy_id: Optional[str] = None,
        strategy_name: Optional[str] = None,
        notification_type: NotificationType = NotificationType.INFO,
        data: Optional[Dict] = None,
        channels: Optional[List[NotificationChannel]] = None
    ):
        """
        Send notification to configured channels
        
        Args:
            event_type: Event identifier (e.g., 'strategy_executed')
            title: Notification title
            message: Notification body
            strategy_id: Related strategy ID
            strategy_name: Related strategy name
            notification_type: Severity level
            data: Additional data
            channels: Specific channels to send to (or all enabled)
        """
        # Generate notification ID
        self._counter += 1
        notif_id = f"notif_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._counter}"
        
        # Determine channels
        target_channels = channels or [
            ch for ch, enabled in self._enabled_channels.items() 
            if enabled and ch != NotificationChannel.ALL
        ]
        
        # Create notification
        notification = StrategyNotification(
            id=notif_id,
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            title=title,
            message=message,
            notification_type=notification_type,
            data=data or {},
            channels=[ch.value if isinstance(ch, NotificationChannel) else ch for ch in target_channels]
        )
        
        # Add to history
        self._add_to_history(notification)
        
        # Send to channels
        for channel in target_channels:
            if isinstance(channel, str):
                channel = NotificationChannel(channel)
            self._send_to_channel(notification, channel)
        
        log.info(f"📤 Notification sent: {title} ({notification_type.value})")
        
        return notification
    
    def _add_to_history(self, notification: StrategyNotification):
        """Add notification to history"""
        self._notifications.insert(0, notification)
        
        # Trim history
        if len(self._notifications) > self._max_history:
            self._notifications = self._notifications[:self._max_history]
    
    def _send_to_channel(self, notification: StrategyNotification, channel: NotificationChannel):
        """Send notification to specific channel"""
        try:
            if channel == NotificationChannel.WEBSOCKET:
                self._send_websocket(notification)
            elif channel == NotificationChannel.DESKTOP:
                self._send_desktop(notification)
            elif channel == NotificationChannel.EMAIL:
                self._send_email(notification)
            elif channel == NotificationChannel.WEBHOOK:
                self._send_webhook(notification)
        except Exception as e:
            log.error(f"Failed to send to {channel.value}: {e}")
    
    def _send_websocket(self, notification: StrategyNotification):
        """Send via WebSocket handlers"""
        data = {
            'type': 'strategy_notification',
            'notification': notification.to_dict()
        }
        
        for handler in self._websocket_handlers:
            try:
                handler(data)
            except Exception as e:
                log.error(f"WebSocket handler error: {e}")
    
    def _send_desktop(self, notification: StrategyNotification):
        """Send desktop notification"""
        try:
            # macOS notification
            import subprocess
            
            title = notification.title
            message = notification.message
            
            # Use osascript for macOS
            script = f'''
            display notification "{message}" with title "{title}"
            '''
            subprocess.run(['osascript', '-e', script], check=False)
            
        except Exception as e:
            log.warning(f"Desktop notification failed: {e}")
    
    def _send_email(self, notification: StrategyNotification):
        """Send email notification"""
        if not self._email_config:
            log.warning("Email not configured")
            return
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['Subject'] = f"[Strategy Alert] {notification.title}"
            msg['From'] = self._email_config.get('from')
            msg['To'] = self._email_config.get('to')
            
            # HTML body
            body = f"""
            <h2>{notification.title}</h2>
            <p>{notification.message}</p>
            <hr>
            <p><small>
                Strategy: {notification.strategy_name or 'N/A'}<br>
                Event: {notification.event_type}<br>
                Time: {notification.timestamp}
            </small></p>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Send
            with smtplib.SMTP(self._email_config.get('smtp_host'), self._email_config.get('smtp_port', 587)) as server:
                if self._email_config.get('use_tls', True):
                    server.starttls()
                if self._email_config.get('username'):
                    server.login(self._email_config['username'], self._email_config['password'])
                server.send_message(msg)
            
            log.info(f"Email sent: {notification.title}")
            
        except Exception as e:
            log.error(f"Email send failed: {e}")
    
    def _send_webhook(self, notification: StrategyNotification):
        """Send webhook notification"""
        if not self._webhook_url:
            log.warning("Webhook not configured")
            return
        
        try:
            import requests
            
            payload = notification.to_dict()
            
            response = requests.post(
                self._webhook_url,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                log.info(f"Webhook sent: {notification.title}")
            else:
                log.warning(f"Webhook response: {response.status_code}")
                
        except Exception as e:
            log.error(f"Webhook failed: {e}")
    
    # ==================== Convenience Methods ====================
    
    def notify_strategy_created(self, strategy_id: str, strategy_name: str, strategy_type: str):
        """Notify when strategy is created"""
        return self.notify(
            event_type='strategy_created',
            title=f"Strategy Created: {strategy_name}",
            message=f"New {strategy_type} strategy configured and ready for execution.",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            notification_type=NotificationType.INFO,
            data={'strategy_type': strategy_type}
        )
    
    def notify_strategy_executed(self, strategy_id: str, strategy_name: str, total_cost: float):
        """Notify when strategy is executed"""
        return self.notify(
            event_type='strategy_executed',
            title=f"Strategy Executed: {strategy_name}",
            message=f"Strategy executed successfully. Total cost: ${total_cost:,.2f}",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            notification_type=NotificationType.SUCCESS,
            data={'total_cost': total_cost}
        )
    
    def notify_leg_filled(self, strategy_id: str, strategy_name: str, leg_id: int, fill_price: float):
        """Notify when a leg is filled"""
        return self.notify(
            event_type='leg_filled',
            title=f"Leg Filled: {strategy_name}",
            message=f"Leg {leg_id} filled at ${fill_price:,.2f}",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            notification_type=NotificationType.INFO,
            data={'leg_id': leg_id, 'fill_price': fill_price}
        )
    
    def notify_profit_target(self, strategy_id: str, strategy_name: str, pnl: float, pnl_pct: float):
        """Notify when profit target is reached"""
        return self.notify(
            event_type='profit_target_reached',
            title=f"🎯 Profit Target: {strategy_name}",
            message=f"Strategy reached profit target! P&L: +${pnl:,.2f} (+{pnl_pct:.1f}%)",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            notification_type=NotificationType.SUCCESS,
            data={'pnl': pnl, 'pnl_pct': pnl_pct}
        )
    
    def notify_stop_loss(self, strategy_id: str, strategy_name: str, pnl: float, pnl_pct: float):
        """Notify when stop loss is triggered"""
        return self.notify(
            event_type='stop_loss_triggered',
            title=f"🛑 Stop Loss: {strategy_name}",
            message=f"Strategy closed at stop loss. P&L: ${pnl:,.2f} ({pnl_pct:.1f}%)",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            notification_type=NotificationType.WARNING,
            data={'pnl': pnl, 'pnl_pct': pnl_pct}
        )
    
    def notify_dte_warning(self, strategy_id: str, strategy_name: str, dte: int, exit_dte: int):
        """Notify days to expiry warning"""
        return self.notify(
            event_type='dte_warning',
            title=f"📅 Expiry Warning: {strategy_name}",
            message=f"Strategy has {dte} days to expiry (exit at {exit_dte} days)",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            notification_type=NotificationType.WARNING,
            data={'dte': dte, 'exit_dte': exit_dte}
        )
    
    def notify_strategy_closed(
        self, 
        strategy_id: str, 
        strategy_name: str, 
        reason: str,
        pnl: float,
        pnl_pct: float
    ):
        """Notify when strategy is closed"""
        emoji = "🎯" if pnl >= 0 else "🛑"
        notif_type = NotificationType.SUCCESS if pnl >= 0 else NotificationType.WARNING
        pnl_sign = '+' if pnl >= 0 else ''
        
        return self.notify(
            event_type='strategy_closed',
            title=f"{emoji} Strategy Closed: {strategy_name}",
            message=f"Closed ({reason}). Final P&L: {pnl_sign}${pnl:,.2f} ({pnl_sign}{pnl_pct:.1f}%)",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            notification_type=notif_type,
            data={'reason': reason, 'pnl': pnl, 'pnl_pct': pnl_pct}
        )
    
    def notify_error(self, strategy_id: Optional[str], strategy_name: Optional[str], error: str):
        """Notify error condition"""
        return self.notify(
            event_type='strategy_error',
            title=f"❌ Error: {strategy_name or 'Strategy'}",
            message=error,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            notification_type=NotificationType.ERROR,
            data={'error': error}
        )
    
    # ==================== History Management ====================
    
    def get_notifications(
        self, 
        strategy_id: Optional[str] = None,
        event_type: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """Get notification history"""
        notifications = self._notifications
        
        if strategy_id:
            notifications = [n for n in notifications if n.strategy_id == strategy_id]
        
        if event_type:
            notifications = [n for n in notifications if n.event_type == event_type]
        
        if unread_only:
            notifications = [n for n in notifications if not n.read]
        
        return [n.to_dict() for n in notifications[:limit]]
    
    def mark_as_read(self, notification_ids: List[str]):
        """Mark notifications as read"""
        for notif in self._notifications:
            if notif.id in notification_ids:
                notif.read = True
    
    def mark_all_read(self, strategy_id: Optional[str] = None):
        """Mark all notifications as read"""
        for notif in self._notifications:
            if strategy_id is None or notif.strategy_id == strategy_id:
                notif.read = True
    
    def get_unread_count(self, strategy_id: Optional[str] = None) -> int:
        """Get count of unread notifications"""
        if strategy_id:
            return sum(1 for n in self._notifications if not n.read and n.strategy_id == strategy_id)
        return sum(1 for n in self._notifications if not n.read)
    
    def clear_history(self, strategy_id: Optional[str] = None):
        """Clear notification history"""
        if strategy_id:
            self._notifications = [n for n in self._notifications if n.strategy_id != strategy_id]
        else:
            self._notifications = []
        log.info("Notification history cleared")


# Global instance
_notification_service: Optional[StrategyNotificationService] = None


def get_notification_service() -> StrategyNotificationService:
    """Get singleton notification service"""
    global _notification_service
    if _notification_service is None:
        _notification_service = StrategyNotificationService()
    return _notification_service


def send_strategy_notification(
    event_type: str,
    title: str,
    message: str,
    **kwargs
) -> StrategyNotification:
    """Convenience function to send notification"""
    return get_notification_service().notify(
        event_type=event_type,
        title=title,
        message=message,
        **kwargs
    )
