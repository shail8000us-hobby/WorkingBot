"""
MMMX Param Audit — Hot-Reload Parameter Change Logger

Every hot-reload param change is logged with a before/after diff.
Spec: MMMX_IMPLEMENTATION_PLAN.md Section 1 (mmmx_param_audit.py).

Usage:
    from .mmmx_param_audit import record_param_change
    record_param_change(session_id, old_params, new_params, changed_by='operator')
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

log = logging.getLogger('mmmx_param_audit')


def record_param_change(
    session_id: str,
    old_params: Dict[str, Any],
    new_params: Dict[str, Any],
    changed_by: str = 'operator',
    storage=None,
) -> Dict[str, Any]:
    """
    Compute diff between old and new params and persist it.

    Args:
        session_id: MMMX session ID.
        old_params: Previous params dict.
        new_params: New (patched) params dict.
        changed_by: Who triggered the change ('operator', 'api', 'system').
        storage: MMMXStorage instance. If None, falls back to get_storage().

    Returns:
        The diff dict (keys: {param_name: {old, new}}).
    """
    from .mmmx_config import diff_params

    diff = diff_params(old_params, new_params)
    if not diff:
        log.debug(f"param_audit: no changes detected for session {session_id}")
        return {}

    if storage is None:
        try:
            from .mmmx_storage import get_storage
            storage = get_storage()
        except Exception as exc:
            log.error(f"param_audit: cannot get storage: {exc}")
            return diff

    try:
        storage.append_param_audit(
            session_id=session_id,
            diff=diff,
            changed_by=changed_by,
        )
        log.info(
            f"[MMMX][{session_id[:8]}] Param change by {changed_by}: "
            + ", ".join(
                f"{k}: {v['old']!r} → {v['new']!r}"
                for k, v in diff.items()
            )
        )
    except Exception as exc:
        log.error(f"param_audit: failed to persist diff: {exc}")

    return diff


def get_param_history(session_id: str, limit: int = 50, storage=None):
    """Return param change history for a session."""
    if storage is None:
        from .mmmx_storage import get_storage
        storage = get_storage()
    return storage.get_param_audit(session_id, limit=limit)
