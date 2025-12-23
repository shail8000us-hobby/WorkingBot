"""
Utilities to coordinate refactor compatibility toggles.

Modules that provide transitional facades or compatibility shims should rely on
``is_enabled()`` so that the migration path can be toggled via the
``REFACTOR_COMPAT`` environment variable.
"""

from __future__ import annotations

from .compat import is_enabled, compat_env_flag

__all__ = ["is_enabled", "compat_env_flag"]
