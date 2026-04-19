"""
Notification Services for Price Alerts
Supports: Telegram, ntfy.sh, In-App
"""
import aiohttp
import asyncio
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram Bot API."""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send_price_alert(self, alert: dict, current_price: float) -> bool:
        """Send a formatted price alert message."""
        try:
            pnl_expiry = alert.get('expected_pnl_expiry', 0) or 0
            pnl_target = alert.get('expected_pnl_target', 0) or 0
            
            # Determine emojis
            pnl_emoji = "🟢" if pnl_expiry >= 0 else "🔴"
            direction_emoji = "📈" if alert['direction'] == 'above' else "📉" if alert['direction'] == 'below' else "↔️"
            
            # Format direction text
            direction_text = {
                'above': 'went ABOVE',
                'below': 'dropped BELOW', 
                'cross': 'crossed'
            }.get(alert['direction'], 'hit')
            
            expiry_text = f"📅 Expiry: *{alert.get('expiry_date')}*\n" if alert.get('expiry_date') else ""
            
            message = f"""
{direction_emoji} *PRICE ALERT TRIGGERED!*

🔔 *BTC* {direction_text} *${alert['target_price']:,.0f}*
📊 Current: *${current_price:,.2f}*
{expiry_text}

{pnl_emoji} *Expected P&L:*
├ On Expiry: ${pnl_expiry:+,.2f}
└ Current: ${pnl_target:+,.2f}

📝 {alert.get('note') or 'No note'}

⏰ {datetime.now().strftime('%d %b %Y, %H:%M:%S')}
"""
            success = await self._send_message(message.strip(), parse_mode='Markdown')
            if success:
                logger.info(f"[Telegram] Alert sent for {alert['id']} at ${current_price}")
            return success
            
        except Exception as e:
            logger.error(f"[Telegram] Failed to send alert: {e}")
            return False
    
    async def send_test_message(self) -> tuple[bool, str]:
        """Send a test message to verify configuration."""
        try:
            message = """
🔔 *Test Alert from WorkingBot*

✅ Your Telegram notifications are working!

This is a test message from your Options Trading Bot.
You will receive price alerts here when BTC hits your target prices.

⏰ """ + datetime.now().strftime('%d %b %Y, %H:%M:%S')
            
            success = await self._send_message(message.strip(), parse_mode='Markdown')
            if success:
                return True, "Test message sent successfully!"
            else:
                return False, "Failed to send message. Check bot token and chat ID."
        except Exception as e:
            return False, str(e)
    
    async def _send_message(self, text: str, parse_mode: str = None) -> bool:
        """Send a message via Telegram Bot API."""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "chat_id": self.chat_id,
                    "text": text,
                }
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                
                async with session.post(
                    f"{self.base_url}/sendMessage",
                    json=payload
                ) as response:
                    result = await response.json()
                    if not result.get('ok'):
                        logger.error(f"[Telegram] API error: {result.get('description')}")
                        return False
                    return True
        except Exception as e:
            logger.error(f"[Telegram] Request error: {e}")
            return False
    
    async def get_chat_id(self) -> Optional[str]:
        """Get chat ID from recent messages (for setup helper)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/getUpdates") as response:
                    result = await response.json()
                    if result.get('ok') and result.get('result'):
                        for update in result['result']:
                            if 'message' in update:
                                return str(update['message']['chat']['id'])
        except Exception as e:
            logger.error(f"[Telegram] Failed to get chat ID: {e}")
        return None


class NtfyNotifier:
    """Send push notifications via ntfy.sh (free, no account needed)."""
    
    def __init__(self, topic: str, server: str = "https://ntfy.sh"):
        self.topic = topic
        self.server = server.rstrip('/')
    
    async def send_price_alert(self, alert: dict, current_price: float) -> bool:
        """Send a push notification for price alert."""
        try:
            pnl = alert.get('expected_pnl_expiry', 0) or 0
            direction_text = {
                'above': 'above',
                'below': 'below',
                'cross': 'at'
            }.get(alert['direction'], 'at')
            
            # Priority: high if P&L significant
            priority = "high" if abs(pnl) > 50 else "default"
            tags = "chart,warning" if pnl < 0 else "chart,moneybag"
            
            url = f"{self.server}/{self.topic}"
            title = f"BTC {direction_text} ${alert['target_price']:,.0f}!"
            body = f"Current: ${current_price:,.2f}\nExpiry: {alert.get('expiry_date') or 'N/A'}\nP&L: ${pnl:+,.2f}\n{alert.get('note') or ''}"
            
            logger.info(f"[ntfy] Sending to {url} with topic '{self.topic}'")
            logger.info(f"[ntfy] Title: {title}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers={
                        "Title": title,
                        "Priority": priority,
                        "Tags": tags,
                    },
                    data=body
                ) as response:
                    response_text = await response.text()
                    success = response.status == 200
                    if success:
                        logger.info(f"[ntfy] ✅ Alert sent successfully for {alert['id']} (status: {response.status})")
                        logger.info(f"[ntfy] Response: {response_text}")
                    else:
                        logger.error(f"[ntfy] ❌ Failed with status {response.status}")
                        logger.error(f"[ntfy] Response: {response_text}")
                    return success
                    
        except Exception as e:
            logger.error(f"[ntfy] ❌ Exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def send_test_message(self) -> tuple[bool, str]:
        """Send a test notification."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server}/{self.topic}",
                    headers={
                        "Title": "Test Alert from WorkingBot",
                        "Priority": "default",
                        "Tags": "white_check_mark",
                    },
                    data="Your ntfy.sh notifications are working!\nYou will receive price alerts here."
                ) as response:
                    if response.status == 200:
                        return True, f"Test sent! Check the ntfy app for topic: {self.topic}"
                    else:
                        return False, f"Failed with status {response.status}"
        except Exception as e:
            return False, str(e)


class NotificationService:
    """Unified notification service that handles multiple channels."""
    
    def __init__(self, settings: dict = None):
        self.settings = settings or {}
        self._telegram: Optional[TelegramNotifier] = None
        self._ntfy: Optional[NtfyNotifier] = None
        
        self._init_notifiers()
    
    def _init_notifiers(self):
        """Initialize configured notifiers."""
        if self.settings.get('telegram_bot_token') and self.settings.get('telegram_chat_id'):
            self._telegram = TelegramNotifier(
                self.settings['telegram_bot_token'],
                self.settings['telegram_chat_id']
            )
        
        if self.settings.get('ntfy_topic'):
            self._ntfy = NtfyNotifier(
                self.settings['ntfy_topic'],
                self.settings.get('ntfy_server', 'https://ntfy.sh')
            )
    
    def update_settings(self, settings: dict):
        """Update settings and reinitialize notifiers."""
        self.settings = settings
        self._init_notifiers()
    
    async def send_alert(self, alert: dict, current_price: float) -> dict:
        """Send alert through all enabled channels."""
        results = {
            'telegram': None,
            'ntfy': None,
        }

        channels = alert.get('notification_channels', 'telegram,in_app').split(',')
        enabled = self.settings.get('enabled_channels', 'telegram').split(',')

        # in_app channel: record delivery only if it was actually requested
        if 'in_app' in channels:
            results['in_app'] = True

        # Send to Telegram
        if 'telegram' in channels and 'telegram' in enabled and self._telegram:
            results['telegram'] = await self._telegram.send_price_alert(alert, current_price)

        # Send to ntfy
        if 'ntfy' in channels and 'ntfy' in enabled and self._ntfy:
            results['ntfy'] = await self._ntfy.send_price_alert(alert, current_price)

        return results
    
    async def test_telegram(self) -> tuple[bool, str]:
        """Test Telegram notifications."""
        if not self._telegram:
            return False, "Telegram not configured. Set bot token and chat ID first."
        return await self._telegram.send_test_message()
    
    async def test_ntfy(self) -> tuple[bool, str]:
        """Test ntfy.sh notifications."""
        if not self._ntfy:
            return False, "ntfy not configured. Set topic first."
        return await self._ntfy.send_test_message()
