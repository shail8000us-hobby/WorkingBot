from __future__ import annotations

import logging
import os
from collections import Counter
from functools import lru_cache
from typing import Dict

from config.loader import get_config

logger = logging.getLogger("refactor_compat")


def get_compat_config():
    """Get compatibility configuration from YAML with fallback to env"""
    try:
        cfg = get_config()
        return cfg.refactor_compat
    except Exception:
        # Fallback to env if config not available
        return None


_compat_cfg = get_compat_config()

WARNING_THRESHOLD = _compat_cfg.warn_threshold if _compat_cfg else int(os.getenv("REFACTOR_COMPAT_WARN", "1"))
ERROR_THRESHOLD = _compat_cfg.fail_threshold if _compat_cfg else int(os.getenv("REFACTOR_COMPAT_FAIL", "2"))

_legacy_usage: Counter[str] = Counter()


@lru_cache(maxsize=1)
def compat_env_flag() -> str:
    """
    Return the raw compatibility flag value.

    Environment variable defaults to ``\"1\"`` to keep the compatibility layer
    active unless operators explicitly disable it.
    """
    if _compat_cfg:
        return "1" if _compat_cfg.enabled else "0"
    return os.getenv("REFACTOR_COMPAT", "1").strip()


def is_enabled() -> bool:
    """Return ``True`` when the compatibility layer should be active."""
    value = compat_env_flag().lower()
    return value not in {"0", "false", "off", ""}


def record_usage(key: str) -> None:
    if not is_enabled():
        return
    _legacy_usage[key] += 1
    count = _legacy_usage[key]
    if count == WARNING_THRESHOLD:
        logger.warning("Legacy configuration key '%s' accessed %s times", key, count)
    if count == ERROR_THRESHOLD:
        logger.error("Legacy configuration key '%s' reached error threshold (%s)", key, count)


def usage_snapshot() -> Dict[str, int]:
    return dict(_legacy_usage)
