"""
MMMX Startup — on_startup() for Flask app initialization.

Spec: MMMX_IMPLEMENTATION_PLAN.md Phase 9 (Fault Tolerance).

Called once when the Flask app starts. Steps:
  1. Load all sessions from DB.
  2. Land RUNNING sessions to PAUSED (manual reconciliation required after restart).
  3. Clear expired _being_closed guards (entries older than BEING_CLOSED_TTL_SECS).
  4. Restore _whipsaw state if present (no mutation needed — persisted in session dict).
  5. Start the global watchdog.

Isolation: ZERO imports from routes.mmm.*.
All timestamps: datetime.now(timezone.utc).isoformat() — never naive utcnow().
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

log = logging.getLogger('init_mmmx')


def on_startup() -> None:
    """
    MMMX startup landing procedure.

    Safe to call multiple times (idempotent per session — already-PAUSED
    sessions are skipped by transition_status).
    """
    from .mmmx_storage import get_storage
    from .mmmx_state import transition_status
    from .mmmx_constants import BEING_CLOSED_TTL_SECS, SessionStatus
    from .mmmx_watchdog import get_watchdog

    log.info("[MMMX][Startup] on_startup() beginning.")
    storage = get_storage()

    try:
        sessions = storage.list_sessions()
    except Exception as exc:
        log.error(f"[MMMX][Startup] Failed to list sessions: {exc}")
        sessions = []

    for session in sessions:
        session_id = session.get('session_id', '')
        status = session.get('status', '')

        # ── Step 2: Land RUNNING → PAUSED ─────────────────────────────────────
        if status == SessionStatus.RUNNING:
            try:
                transition_status(session, SessionStatus.PAUSED, reason='startup_landing')
                current_gen = storage.get_generation(session_id)
                storage.save_session(session, expected_gen=current_gen)
                log.warning(
                    f"[MMMX][Startup] Session {session_id[:8]} landed PAUSED "
                    "(was RUNNING at shutdown — manual reconciliation required)."
                )
                _send_startup_telegram(session_id)
            except ValueError:
                # Already in a state that doesn't allow PAUSED transition (terminal)
                log.debug(
                    f"[MMMX][Startup] Session {session_id[:8]} status={status} "
                    "skipped (no RUNNING→PAUSED transition needed)."
                )
            except Exception as exc:
                log.error(
                    f"[MMMX][Startup] Failed to land session {session_id[:8]}: {exc}"
                )

        # ── Step 3: Clear expired _being_closed guards ─────────────────────────
        try:
            _clear_expired_being_closed(session, BEING_CLOSED_TTL_SECS, session_id, storage)
        except Exception as exc:
            log.error(
                f"[MMMX][Startup] _being_closed cleanup failed for "
                f"{session_id[:8]}: {exc}"
            )

        # ── Step 4: _whipsaw state is already in session dict — no mutation needed

    # ── Step 5: Start watchdog ─────────────────────────────────────────────────
    try:
        watchdog = get_watchdog()
        watchdog.start()
        log.info("[MMMX][Startup] Watchdog started.")
    except Exception as exc:
        log.error(f"[MMMX][Startup] Watchdog start failed: {exc}")

    log.info("[MMMX][Startup] on_startup() complete.")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clear_expired_being_closed(
    session: Dict[str, Any],
    ttl_secs: float,
    session_id: str,
    storage,
) -> None:
    """
    Remove stale entries from session['_being_closed'] (dict of tranche_id → epoch).

    An entry is stale if its timestamp is older than ttl_secs seconds.
    Saves the session only if at least one entry was cleared.
    """
    being_closed: Dict = session.get('_being_closed')
    if not being_closed or not isinstance(being_closed, dict):
        return

    now = time.time()
    expired_keys = [
        k for k, v in being_closed.items()
        if isinstance(v, (int, float)) and (now - float(v)) > ttl_secs
    ]

    if not expired_keys:
        return

    for k in expired_keys:
        del being_closed[k]
        log.info(
            f"[MMMX][Startup] Cleared expired _being_closed guard: "
            f"session={session_id[:8]} tranche={k}"
        )

    # Persist the cleaned session
    try:
        current_gen = storage.get_generation(session_id)
        storage.save_session(session, expected_gen=current_gen)
    except Exception as exc:
        log.error(
            f"[MMMX][Startup] Failed to save after _being_closed cleanup "
            f"for {session_id[:8]}: {exc}"
        )


def _send_startup_telegram(session_id: str) -> None:
    """Send a Telegram alert that a session was landed PAUSED on startup."""
    try:
        from .mmmx_telegram import send_alert
        send_alert(
            f"🔄 MMMX session {session_id[:8]} landed PAUSED on startup. "
            "Manual reconciliation required before resuming.",
            alert_type=f'startup_landing_{session_id[:8]}',
            session_id=session_id,
            dedup_ttl=60,
        )
    except Exception as exc:
        log.debug(f"[MMMX][Startup] Telegram send failed: {exc}")
