"""
Telegram Bot Command Handler

Handles incoming Telegram commands:
- /ack <error_id> - Acknowledge an error
- /resolve <error_id> [notes] - Resolve an error
- /fix <error_id> <fix_id> [--dry-run] - Execute a fix
- /errors [status] [severity] - List errors
- /status - Get system status
- /help - Show command help

Integrates with ErrorIntelligenceManager to perform actions
"""

import os
import logging
from typing import Optional, Dict, Any
import requests
from threading import Thread, Lock
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class TelegramCommandHandler:
    """Handles Telegram bot commands for error management"""
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        error_manager=None
    ):
        # Secrets from ENV
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        
        # Settings from YAML
        try:
            config = get_config()
            self.enabled = config.telegram.enabled
        except:
            self.enabled = True  # Default enabled for backward compatibility
        self.error_manager = error_manager
        self.enabled = bool(self.bot_token)
        
        self.last_update_id = 0
        self.running = False
        self.polling_thread = None
        self.health_lock = Lock()
        self._health = {
            'enabled': self.enabled,
            'connected': False,
            'message': 'Telegram commands disabled (missing token)' if not self.enabled else 'Initializing',
            'last_checked': None,
            'error': None
        }
        
        if self.enabled:
            logger.info("✅ Telegram Command Handler initialized")
            self.perform_health_check()
        else:
            logger.warning("⚠️ Telegram Command Handler disabled (missing token)")
    
    def start(self):
        """Start polling for commands"""
        if not self.enabled:
            return
        
        self.perform_health_check()
        self.running = True
        self.polling_thread = Thread(target=self._polling_worker, daemon=True)
        self.polling_thread.start()
        logger.info("🚀 Telegram command polling started")
    
    def stop(self):
        """Stop polling for commands"""
        self.running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
            logger.info("🛑 Telegram command polling stopped")
    
    def _polling_worker(self):
        """Background worker for polling updates"""
        while self.running:
            try:
                updates = self._get_updates()
                
                for update in updates:
                    try:
                        self._handle_update(update)
                    except Exception as e:
                        logger.error(f"Error handling update: {e}")
                
                time.sleep(1)  # Poll every second
                
            except Exception as e:
                logger.error(f"Error in polling worker: {e}")
                time.sleep(5)
    
    def _update_health(self, connected: bool, message: str, error: Optional[str] = None):
        """Update cached Telegram command handler health"""
        with self.health_lock:
            self._health.update({
                'connected': connected,
                'message': message,
                'last_checked': datetime.now().isoformat(),
                'error': error
            })
    
    def perform_health_check(self) -> bool:
        """Validate bot token with Telegram API"""
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
                    info = data.get('result', {})
                    username = info.get('username') or info.get('first_name') or 'bot'
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
        """Expose current health status"""
        with self.health_lock:
            return dict(self._health)
    
    def _get_updates(self):
        """Get updates from Telegram API"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {
                "offset": self.last_update_id + 1,
                "timeout": 30,
                "allowed_updates": ["message"]
            }
            
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code == 200:
                data = response.json()
                updates = data.get("result", [])
                
                if updates:
                    self.last_update_id = updates[-1]["update_id"]
                self._update_health(True, "Polling OK", None)
                
                return updates
            else:
                logger.error(f"Failed to get updates: {response.text}")
                self._update_health(False, "Telegram polling failed", response.text)
                return []
        
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            self._update_health(False, "Telegram polling failed", str(e))
            return []
    
    def _handle_update(self, update: Dict):
        """Handle a single update"""
        message = update.get("message")
        if not message:
            return
        
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        user = message.get("from", {}).get("username", "unknown")
        
        if not text.startswith("/"):
            return
        
        logger.info(f"📥 Received command from {user}: {text}")
        
        # Parse command
        parts = text.split()
        command = parts[0].lower()
        args = parts[1:]
        
        # Route to handler
        if command == "/ack":
            self._handle_ack(chat_id, args, user)
        elif command == "/resolve":
            self._handle_resolve(chat_id, args, user)
        elif command == "/fix":
            self._handle_fix(chat_id, args, user)
        elif command == "/errors":
            self._handle_errors(chat_id, args)
        elif command == "/status":
            self._handle_status(chat_id)
        elif command == "/help":
            self._handle_help(chat_id)
        else:
            self._send_message(chat_id, f"Unknown command: {command}\nUse /help for available commands")
    
    def _handle_ack(self, chat_id: int, args: list, user: str):
        """Handle /ack <error_id>"""
        if not args:
            self._send_message(chat_id, "Usage: /ack <error_id>")
            return
        
        error_id = args[0]
        
        if not self.error_manager:
            self._send_message(chat_id, "❌ Error manager not available")
            return
        
        try:
            result = self.error_manager.acknowledge_error(error_id, user)
            
            if result:
                self._send_message(chat_id, f"✅ Error `{error_id}` acknowledged by {user}")
            else:
                self._send_message(chat_id, f"❌ Failed to acknowledge error `{error_id}`")
        
        except Exception as e:
            self._send_message(chat_id, f"❌ Error: {str(e)}")
    
    def _handle_resolve(self, chat_id: int, args: list, user: str):
        """Handle /resolve <error_id> [notes]"""
        if not args:
            self._send_message(chat_id, "Usage: /resolve <error_id> [notes]")
            return
        
        error_id = args[0]
        notes = " ".join(args[1:]) if len(args) > 1 else "Resolved via Telegram"
        
        if not self.error_manager:
            self._send_message(chat_id, "❌ Error manager not available")
            return
        
        try:
            result = self.error_manager.resolve_error(error_id, user, notes)
            
            if result:
                self._send_message(chat_id, f"✅ Error `{error_id}` resolved by {user}")
            else:
                self._send_message(chat_id, f"❌ Failed to resolve error `{error_id}`")
        
        except Exception as e:
            self._send_message(chat_id, f"❌ Error: {str(e)}")
    
    def _handle_fix(self, chat_id: int, args: list, user: str):
        """Handle /fix <error_id> <fix_id> [--dry-run]"""
        if len(args) < 2:
            self._send_message(chat_id, "Usage: /fix <error_id> <fix_id> [--dry-run]")
            return
        
        error_id = args[0]
        fix_id = args[1]
        dry_run = "--dry-run" in args
        
        if not self.error_manager:
            self._send_message(chat_id, "❌ Error manager not available")
            return
        
        try:
            result = self.error_manager.run_fix(error_id, fix_id, dry_run, user)
            
            if result.get("success"):
                mode = "dry-run" if dry_run else "executed"
                message = f"✅ Fix `{fix_id}` {mode} successfully"
                
                if result.get("result", {}).get("preview"):
                    message += f"\n\n```\n{result['result']['preview']}\n```"
                
                self._send_message(chat_id, message)
            else:
                self._send_message(chat_id, f"❌ Fix failed: {result.get('message', 'Unknown error')}")
        
        except Exception as e:
            self._send_message(chat_id, f"❌ Error: {str(e)}")
    
    def _handle_errors(self, chat_id: int, args: list):
        """Handle /errors [status] [severity]"""
        if not self.error_manager:
            self._send_message(chat_id, "❌ Error manager not available")
            return
        
        # Parse filters
        status = args[0] if len(args) > 0 else "open"
        severity = args[1] if len(args) > 1 else None
        
        try:
            filters = {"status": status}
            if severity:
                filters["severity"] = severity
            
            errors = self.error_manager.get_errors(filters)
            
            if not errors:
                self._send_message(chat_id, f"No errors with status '{status}'")
                return
            
            # Format error list
            lines = [f"*Errors (status={status})*"]
            lines.append("")
            
            for i, error in enumerate(errors[:10]):  # Limit to 10
                severity_emoji = {
                    "critical": "🚨",
                    "high": "⚠️",
                    "medium": "ℹ️",
                    "low": "💡"
                }
                emoji = severity_emoji.get(error.get("severity", "low"), "❓")
                
                lines.append(
                    f"{i+1}. {emoji} `{error['code']}` "
                    f"({error.get('severity', 'unknown')}) - "
                    f"{error.get('source', 'unknown')} bot"
                )
                lines.append(f"   ID: `{error['id']}`")
                lines.append("")
            
            if len(errors) > 10:
                lines.append(f"... and {len(errors) - 10} more")
            
            self._send_message(chat_id, "\n".join(lines))
        
        except Exception as e:
            self._send_message(chat_id, f"❌ Error: {str(e)}")
    
    def _handle_status(self, chat_id: int):
        """Handle /status"""
        if not self.error_manager:
            self._send_message(chat_id, "❌ Error manager not available")
            return
        
        try:
            # Get error statistics
            errors = self.error_manager.get_errors()
            
            by_status = {}
            by_severity = {}
            
            for error in errors:
                status = error.get("status", "unknown")
                severity = error.get("severity", "unknown")
                
                by_status[status] = by_status.get(status, 0) + 1
                by_severity[severity] = by_severity.get(severity, 0) + 1
            
            # Format status message
            lines = [
                "*🔍 Error Intelligence System Status*",
                "",
                "*By Status:*"
            ]
            
            for status, count in sorted(by_status.items()):
                lines.append(f"  • {status}: {count}")
            
            lines.append("")
            lines.append("*By Severity:*")
            
            for severity, count in sorted(by_severity.items()):
                emoji = {
                    "critical": "🚨",
                    "high": "⚠️",
                    "medium": "ℹ️",
                    "low": "💡"
                }.get(severity, "❓")
                lines.append(f"  • {emoji} {severity}: {count}")
            
            lines.append("")
            lines.append(f"*Total Errors:* {len(errors)}")
            
            self._send_message(chat_id, "\n".join(lines))
        
        except Exception as e:
            self._send_message(chat_id, f"❌ Error: {str(e)}")
    
    def _handle_help(self, chat_id: int):
        """Handle /help"""
        help_text = """
*🤖 Error Intelligence Bot Commands*

*Error Management:*
`/ack <error_id>` - Acknowledge an error
`/resolve <error_id> [notes]` - Mark error as resolved
`/fix <error_id> <fix_id> [--dry-run]` - Execute a fix

*Query:*
`/errors [status] [severity]` - List errors
`/status` - Get system status

*Examples:*
`/errors open critical` - List critical open errors
`/fix error-123 sync_gridbot_params --dry-run` - Preview fix
`/fix error-123 sync_gridbot_params` - Execute fix
`/ack error-123` - Acknowledge error
`/resolve error-123 Fixed manually` - Resolve with notes

Use `/status` to see current error counts.
"""
        self._send_message(chat_id, help_text)
    
    def _send_message(self, chat_id: int, text: str):
        """Send a message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                self._update_health(True, "Command response delivered", None)
            else:
                logger.error(f"Failed to send message: {response.text}")
                self._update_health(False, "Telegram send failed", response.text)
                return False
        
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self._update_health(False, "Telegram send failed", str(e))
            return False
        return True
