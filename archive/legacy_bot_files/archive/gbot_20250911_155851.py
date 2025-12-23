"""Compatibility facade for legacy gridbot snapshot."""

from __future__ import annotations

from bot.refactor import is_enabled as _refactor_enabled

if _refactor_enabled():
    from bot.strategy.archive.gbot_v1_7_3 import *  # noqa: F401,F403
