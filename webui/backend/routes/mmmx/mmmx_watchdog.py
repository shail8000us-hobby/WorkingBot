"""
MMMX Watchdog — Supervisor Thread for Monitor & Listener Health

Spec: MMMX_IMPLEMENTATION_PLAN.md Phase 9 (Fault Tolerance).

Polls _mmmx_monitors and _mmmx_listeners every 30 seconds.
If a RUNNING session has a dead monitor or listener, restarts them.

Invariants:
  - Only restarts sessions whose DB status is RUNNING.
  - PAUSED/COMPLETE/ERROR sessions are left alone — dead threads are intentional.
  - Generation is ALWAYS bumped by start_session_monitor(), never by the watchdog.
  - Telegram alerts are deduped with a 300-second TTL per session.
  - Isolation: ZERO imports from routes.mmm.*.
  - All timestamps: datetime.now(timezone.utc).isoformat() — never naive utcnow().
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger('mmmx_watchdog')

# How often the watchdog polls (seconds)
_POLL_INTERVAL_SECS = 30

# Singleton
_watchdog_instance: Optional['MMMXWatchdog'] = None
_watchdog_lock = threading.Lock()


class MMMXWatchdog:
    """
    Supervisor thread that monitors the health of all MMMX session threads.

    Detects dead monitors/listeners and restarts them for RUNNING sessions.
    """

    def __init__(self):
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_tick_at: Optional[str] = None
        # Track last Telegram alert per session to dedup (session_id -> epoch)
        self._last_alert_at: dict = {}
        self._alert_dedup_ttl = 300  # seconds

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the watchdog daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            log.warning("[MMMX][Watchdog] start() called while thread alive — ignoring")
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="mmmx_watchdog",
            daemon=True,
        )
        self._thread.start()
        log.info("[MMMX][Watchdog] Watchdog started.")

    def stop(self) -> None:
        """Signal the watchdog to stop."""
        self._running = False
        self._stop_event.set()
        log.info("[MMMX][Watchdog] Watchdog stop requested.")

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_tick_at(self) -> Optional[str]:
        return self._last_tick_at

    # ── Run loop ───────────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        """Daemon thread loop — calls tick() every _POLL_INTERVAL_SECS seconds."""
        log.info("[MMMX][Watchdog] Run loop started.")
        while self._running and not self._stop_event.is_set():
            self._stop_event.wait(timeout=_POLL_INTERVAL_SECS)
            if not self._running:
                break
            try:
                self.tick()
            except Exception as exc:
                log.exception(f"[MMMX][Watchdog] tick() crashed: {exc}")
        log.info("[MMMX][Watchdog] Run loop exited.")

    # ── Tick (public for tests) ────────────────────────────────────────────────

    def tick(self) -> None:
        """
        One poll cycle. Checks all registered monitors and listeners.

        For each RUNNING session:
          - If monitor thread is dead → _restart_monitor(session_id)
          - If listener thread is dead → _restart_listener(session_id)
        """
        self._last_tick_at = datetime.now(timezone.utc).isoformat()

        try:
            from .mmmx_monitor import get_all_monitors
            monitors = get_all_monitors()
        except Exception as exc:
            log.error(f"[MMMX][Watchdog] Failed to get monitors: {exc}")
            return

        for session_id, monitor in monitors.items():
            try:
                self._check_session(session_id, monitor)
            except Exception as exc:
                log.error(
                    f"[MMMX][Watchdog] Error checking session {session_id[:8]}: {exc}"
                )

    # ── Per-session check ──────────────────────────────────────────────────────

    def _check_session(self, session_id: str, monitor) -> None:
        """Check one session's monitor and listener health."""
        # Load session to check status
        try:
            from .mmmx_storage import get_storage
            session = get_storage().load_session(session_id)
        except Exception as exc:
            log.error(f"[MMMX][Watchdog] Could not load session {session_id[:8]}: {exc}")
            return

        if session is None:
            return

        status = session.get('status', '')

        # Only watch RUNNING sessions — dead threads in PAUSED/COMPLETE/ERROR are intentional
        if status != 'RUNNING':
            return

        # Check monitor health
        if not monitor.is_alive():
            log.warning(
                f"[MMMX][Watchdog] Dead monitor detected for RUNNING session "
                f"{session_id[:8]} — restarting."
            )
            self._restart_monitor(session_id)

        # Check listener health
        try:
            from .mmmx_premium_listener import get_listener
            listener = get_listener(session_id)
            if listener is None or not listener.is_alive():
                log.warning(
                    f"[MMMX][Watchdog] Dead listener detected for RUNNING session "
                    f"{session_id[:8]} — restarting."
                )
                self._restart_listener(session_id)
        except Exception as exc:
            log.error(
                f"[MMMX][Watchdog] Listener check failed for {session_id[:8]}: {exc}"
            )

    # ── Restart helpers ────────────────────────────────────────────────────────

    def _restart_monitor(self, session_id: str) -> None:
        """
        Restart the monitor for session_id.

        Uses start_session_monitor() which bumps generation — watchdog never
        sets generation manually.
        """
        try:
            from .mmmx_monitor import start_session_monitor
            new_monitor = start_session_monitor(session_id)
            log.warning(
                f"[MMMX][Watchdog] Monitor restarted for {session_id[:8]} "
                f"gen={new_monitor._my_generation}"
            )
            self._send_restart_alert(session_id, 'monitor')
        except Exception as exc:
            log.error(
                f"[MMMX][Watchdog] Failed to restart monitor for {session_id[:8]}: {exc}"
            )

    def _restart_listener(self, session_id: str) -> None:
        """
        Restart the listener for session_id.

        Reads the current generation from storage and co-starts a fresh listener.
        Generation is NOT bumped — listener restarts use the current generation.
        """
        try:
            from .mmmx_storage import get_storage
            from .mmmx_premium_listener import start_session_listener
            from .mmmx_executor import get_executor

            current_gen = get_storage().get_generation(session_id)
            new_listener = start_session_listener(
                session_id=session_id,
                my_generation=current_gen,
                executor=get_executor(),
            )
            log.warning(
                f"[MMMX][Watchdog] Listener restarted for {session_id[:8]} "
                f"gen={current_gen}"
            )
            self._send_restart_alert(session_id, 'listener')
        except Exception as exc:
            log.error(
                f"[MMMX][Watchdog] Failed to restart listener for {session_id[:8]}: {exc}"
            )

    # ── Telegram alert (deduped) ───────────────────────────────────────────────

    def _send_restart_alert(self, session_id: str, component: str) -> None:
        """Send a Telegram WARN on restart with dedup TTL of 300 seconds."""
        now = time.time()
        key = f"{session_id}:{component}"
        last = self._last_alert_at.get(key, 0.0)

        if now - last < self._alert_dedup_ttl:
            log.debug(
                f"[MMMX][Watchdog] Restart alert suppressed (dedup) for "
                f"{session_id[:8]} {component}"
            )
            return

        self._last_alert_at[key] = now

        try:
            from .mmmx_telegram import send_alert
            send_alert(
                f"⚠️ MMMX Watchdog: {component} restarted for session {session_id[:8]}. "
                "Monitor the next few beats carefully.",
                alert_type=f'watchdog_restart_{session_id[:8]}_{component}',
                session_id=session_id,
                dedup_ttl=self._alert_dedup_ttl,
            )
        except Exception as exc:
            log.error(f"[MMMX][Watchdog] Telegram alert failed: {exc}")


# ── Singleton ──────────────────────────────────────────────────────────────────

def get_watchdog() -> MMMXWatchdog:
    """Return the global MMMXWatchdog singleton (creates it on first call)."""
    global _watchdog_instance
    with _watchdog_lock:
        if _watchdog_instance is None:
            _watchdog_instance = MMMXWatchdog()
    return _watchdog_instance
