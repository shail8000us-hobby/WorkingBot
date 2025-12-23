"""
Guardian Core Orchestrator

Main Guardian Bot - coordinates collectors, engine, and alerts.
NO risk logic - just reads signals and sends Telegram notifications.
"""

from .guardian_bot import GuardianBot

__all__ = [
    'GuardianBot',
]
