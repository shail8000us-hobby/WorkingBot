"""
Telegram Notifications Module

Provides Telegram integration for the Error Intelligence System:
- Error notifications with escalation policy
- Command handling (/ack, /resolve, /fix, etc.)
- Rate limiting and cooldown management
"""

from .telegram_error_notifier import TelegramErrorNotifier
from .telegram_command_handler import TelegramCommandHandler

__all__ = ["TelegramErrorNotifier", "TelegramCommandHandler"]
