"""
sealed.py — Function Sealing Decorator
=======================================
Apply @sealed to any function confirmed working.

What it does:
- Logs CRITICAL if the function raises an unexpected exception
- Re-raises the exception so the bot halts or routes to fallback — it never silently swallows errors
- Is completely transparent when the function works normally (zero overhead)

Usage:
    from webui.backend.sealed import sealed

    @sealed
    def my_stable_function(...):
        ...

Protocol:
- See AI_SEAL.md for the full sealing process
- See AI_ALREADY_SEALED.md for the registry of sealed functions
- Never add @sealed yourself — only add it through the AI_SEAL.md protocol
"""

import functools
import logging

log = logging.getLogger(__name__)


def sealed(func):
    """
    Mark a function as stable and sealed.
    Any unexpected exception triggers a CRITICAL log entry immediately.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log.critical(
                f"SEALED FUNCTION BROKE: {func.__module__}.{func.__name__} "
                f"→ {type(e).__name__}: {e}"
            )
            raise
    return wrapper
