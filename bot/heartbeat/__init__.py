# bot/heartbeat/__init__.py
"""
Heartbeat Management System
Provides dead man's switch functionality to cancel pending BUY orders if bot crashes.
"""

from bot.heartbeat.manager import HeartbeatManager

__all__ = ['HeartbeatManager']

