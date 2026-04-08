"""
MMMX — Monthly BTC Options Strategy (20–45 DTE)

Blueprint registration and startup session restore.
Spec: MMMX_IMPLEMENTATION_PLAN.md Section 1.

Isolation:
  - Zero runtime imports from routes.mmm.* (read-only adapters for chain service
    and IV rank are introduced in Phase 3 via mmmx_margin_guardian.py and
    mmmx_iv_adapter.py — not here).
  - Separate DB: mmmx_sessions.db (never writes to mmm_sessions.db).
  - All WebSocket events prefixed mmmx_*.

On backend startup:
  1. Blueprint registers at /api/mmmx/*.
  2. init_mmmx() restores RUNNING/PAUSED sessions from DB.
  3. Every restored session lands in PAUSED (never auto-resumed).
  4. Monitor thread is NOT started automatically — operator must reconcile + resume.
"""

import logging

from .mmmx_api import mmmx_bp
from .mmmx_websocket import init_websocket
from .mmmx_monitor import (
    start_session_monitor,
    stop_session_monitor,
    get_monitor,
    get_all_monitors,
)

log = logging.getLogger('mmmx')

__all__ = [
    'mmmx_bp',
    'init_mmmx',
    'init_websocket',
    'start_session_monitor',
    'stop_session_monitor',
    'get_monitor',
    'get_all_monitors',
]


def init_mmmx() -> None:
    """
    Initialize MMMX module on backend startup.

    - Wires storage into activity log and audit log singletons.
    - Loads all RUNNING/PAUSED sessions from DB.
    - Forces each to PAUSED status (never auto-resume after restart).
    - Does NOT start monitor threads (operator must reconcile + resume).

    Call this after registering the blueprint in app.py.
    """
    from .mmmx_storage import get_storage
    from .mmmx_state import apply_session_defaults
    from .mmmx_activity import get_activity_log
    from .mmmx_audit_log import get_audit_log
    from .mmmx_constants import SessionStatus

    storage = get_storage()

    # Wire storage into singletons (breaks circular import at module-load time)
    get_activity_log(storage=storage)
    get_audit_log(storage=storage)

    active_sessions = storage.list_active_sessions()
    total = storage.list_sessions()

    log.info(
        f"[MMMX] init_mmmx: {len(total)} total sessions, "
        f"{len(active_sessions)} RUNNING/PAUSED found."
    )

    for session in active_sessions:
        session_id = session.get('session_id', '?')
        old_status = session.get('status')

        # Apply any new fields added since the session was created
        apply_session_defaults(session)

        # Spec: restart always lands in PAUSED (Section 1.2)
        if old_status == SessionStatus.RUNNING:
            session['status'] = SessionStatus.PAUSED
            log.info(
                f"[MMMX][{session_id[:8]}] Restored from RUNNING → PAUSED "
                "(operator must reconcile + resume)."
            )
        else:
            log.info(
                f"[MMMX][{session_id[:8]}] Restored PAUSED session "
                "(operator must reconcile + resume)."
            )

        # Save the PAUSED status back (no generation check needed — startup path)
        try:
            storage.save_session(session, expected_gen=None)
        except Exception as exc:
            log.error(f"[MMMX][{session_id[:8]}] Failed to save restored session: {exc}")

    if not active_sessions:
        log.info("[MMMX] No active sessions to restore.")
