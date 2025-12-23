"""Compatibility facade generated during refactor dedupe."""
from __future__ import annotations

from bot.refactor import is_enabled as _refactor_enabled

if _refactor_enabled():
    from bot._package_facade import *  # noqa: F401,F403
