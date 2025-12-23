"""Legacy configuration alias helpers.

This module centralises the handling of deprecated ``GRID_*`` style keys.
Legacy reads route through here so that we can increment the refactor
compatibility counters and emit a single deprecation warning per key.  All
callers are expected to migrate to the canonical ``GRIDBOT_*`` variants and
should rely on :func:`upgrade_mapping` when loading external dictionaries.

Writes to legacy keys are implicitly blocked by migrating the payload to the
canonical key and removing the legacy entry.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, MutableMapping, Tuple

from bot.refactor.compat import record_usage

ALIAS_TO_CANONICAL: Dict[str, str] = {
    "GRID_LOWER": "GRIDBOT_LOWER",
    "GRID_UPPER": "GRIDBOT_UPPER",
    "GRID_STEP": "GRIDBOT_STEP",
    "REFERENCE_LEVEL": "GRIDBOT_REF",
    "LOT": "GRIDBOT_LOT",
    "MAX_OPEN": "GRIDBOT_MAX_OPEN",
}

CANONICAL_TO_ALIAS: Dict[str, str] = {
    canonical: legacy for legacy, canonical in ALIAS_TO_CANONICAL.items()
}

_warned_keys: set[str] = set()
_logger = logging.getLogger("config.aliases")


def legacy_key_used(key: str) -> None:
    """Record and warn when a legacy key is accessed."""
    record_usage(key)
    if key not in _warned_keys:
        canonical = ALIAS_TO_CANONICAL.get(key)
        if canonical:
            _logger.warning(
                "Deprecated config key '%s' accessed; use '%s' instead.",
                key,
                canonical,
            )
        else:
            _logger.warning("Deprecated config key '%s' accessed.", key)
        _warned_keys.add(key)


def upgrade_mapping(
    mapping: MutableMapping[str, Any], *, record: bool = True
) -> Tuple[set[str], Iterable[str]]:
    """Move legacy keys to their canonical counterparts.

    Returns a tuple ``(migrated_keys, skipped_keys)``. ``skipped_keys`` is kept for
    forward compatibility should we ever need to report disallowed writes.
    """

    migrated: set[str] = set()
    for legacy, canonical in ALIAS_TO_CANONICAL.items():
        if legacy not in mapping:
            continue
        value = mapping.pop(legacy)
        if record:
            legacy_key_used(legacy)
        mapping.setdefault(canonical, value)
        migrated.add(legacy)
    return migrated, ()


def strip_legacy_keys(mapping: MutableMapping[str, Any]) -> None:
    """Remove legacy keys from a mapping without migrating."""
    for legacy in list(ALIAS_TO_CANONICAL.keys()):
        if legacy in mapping:
            mapping.pop(legacy, None)
            legacy_key_used(legacy)


__all__ = [
    "ALIAS_TO_CANONICAL",
    "CANONICAL_TO_ALIAS",
    "legacy_key_used",
    "upgrade_mapping",
    "strip_legacy_keys",
]
