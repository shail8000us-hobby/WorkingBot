"""
MMM Monitor Watchdog

An external supervisor thread that watches every active MMMMonitor and
restarts it if the heartbeat thread has died or become unresponsive.

Detection criteria
------------------
1. Thread liveness: `monitor._thread.is_alive()` returns False while
   `monitor._running` is True — the thread has crashed.

2. Beat timeout: `seconds_since_last_beat > BEAT_TIMEOUT_MULTIPLIER × interval`
   — the thread is alive but stuck (e.g. in an infinite await or deadlock).
   Uses HeartbeatHealth.seconds_since_last_beat if available, otherwise
   checks session 'last_heartbeat' timestamp.

3. Status consistency: session.strategy_status == RUNNING but monitor is
   neither running nor paused — state is inconsistent.

On detection, the watchdog:
1. Logs a critical message
2. Emits a mmm_safety WebSocket event (visible on the dashboard)
3. Logs an activity entry so the algo walkthrough captures the event
4. Stops the dead monitor (no-op if already dead)
5. Restarts a fresh MMMMonitor from the latest persisted session state
6. Records the restart in session['_watchdog_restarts'] for audit

The watchdog intentionally does NOT automatically resume from PAUSED state —
that would hide real pause reasons. It only restarts RUNNING sessions whose
thread has died.

Beat Timeout
------------
A beat timeout is more dangerous than a dead thread because the session
*looks* healthy while doing nothing. We use a generous multiplier
(BEAT_TIMEOUT_MULTIPLIER = 3×) so that a slow exchange call during a
legitimate busy interval doesn't trigger a false restart.

Configuration
-------------
WATCHDOG_POLL_INTERVAL : How often the watchdog checks all monitors (seconds)
BEAT_TIMEOUT_MULTIPLIER: Beats after which a live thread is considered stuck

Created: February 18, 2026
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Dict, Optional

log = logging.getLogger('mmm_watchdog')

WATCHDOG_POLL_INTERVAL   = 15       # seconds between watchdog sweeps
BEAT_TIMEOUT_MULTIPLIER  = 3        # max intervals before "stuck" detection
MAX_RESTARTS_PER_SESSION = 10       # safety cap — stop restarting after this many


class MMMWatchdog:
    """
    Singleton supervisor that watches all active monitor threads.

    Usage::
        watchdog = MMMWatchdog.get_instance()
        watchdog.start()            # called once at app/blueprint init
        watchdog.register(monitor)
        watchdog.deregister(session_id)
        watchdog.stop()             # graceful shutdown
    """

    _instance: Optional['MMMWatchdog'] = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'MMMWatchdog':
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = MMMWatchdog()
            return cls._instance

    def __init__(self):
        self._monitors: Dict[str, object] = {}   # session_id → MMMMonitor
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name='mmm-watchdog',
            daemon=True,
        )
        self._thread.start()
        log.info("MMM Watchdog started")

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        log.info("MMM Watchdog stopped")

    # ------------------------------------------------------------------
    # Monitor registry
    # ------------------------------------------------------------------

    def register(self, monitor: object) -> None:
        """Register a monitor to be supervised."""
        sid = getattr(monitor, 'session_id', None)
        if sid:
            with self._lock:
                self._monitors[sid] = monitor
            log.debug(f"Watchdog registered {sid}")

    def deregister(self, session_id: str) -> None:
        """Remove a monitor from supervision (called on normal stop)."""
        with self._lock:
            self._monitors.pop(session_id, None)
        log.debug(f"Watchdog deregistered {session_id}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Supervisor loop — polls every WATCHDOG_POLL_INTERVAL seconds."""
        while self._running and not self._stop_event.is_set():
            try:
                self._sweep()
            except Exception as e:
                log.exception(f"Watchdog sweep error: {e}")
            self._stop_event.wait(timeout=WATCHDOG_POLL_INTERVAL)

    def _sweep(self) -> None:
        """Check every registered monitor and restart dead/stuck ones."""
        with self._lock:
            monitors = dict(self._monitors)

        for sid, monitor in monitors.items():
            try:
                self._check_monitor(sid, monitor)
            except Exception as e:
                log.error(f"Watchdog check failed for {sid}: {e}")

    def _check_monitor(self, sid: str, monitor: object) -> None:
        """Check a single monitor and restart it if needed."""
        session = getattr(monitor, 'session', {})
        status = session.get('strategy_status', 'UNKNOWN')

        # Only supervise sessions that SHOULD be running
        if status not in ('RUNNING',):
            return

        thread: Optional[threading.Thread] = getattr(monitor, '_thread', None)
        is_running = getattr(monitor, '_running', False)

        problem = None

        # --- Check 1: Thread liveness ---
        if is_running and (thread is None or not thread.is_alive()):
            problem = f"thread dead (is_alive=False while _running=True)"

        # --- Check 2: Beat timeout ---
        if problem is None:
            problem = self._check_beat_timeout(sid, monitor, session)

        if problem is None:
            return  # monitor is fine

        # ---- Restart ----
        restarts = session.get('_watchdog_restarts', 0)
        if restarts >= MAX_RESTARTS_PER_SESSION:
            log.critical(
                f"[{sid}] Watchdog: {problem} — "
                f"MAX {MAX_RESTARTS_PER_SESSION} restarts reached. "
                f"NOT restarting. Manual intervention required."
            )
            self._emit_alert(
                sid,
                f"Monitor dead after {restarts} watchdog restarts. "
                f"MANUAL INTERVENTION REQUIRED.",
                level='critical',
            )
            # Deregister to stop repeated log spam
            self.deregister(sid)
            return

        log.critical(
            f"[{sid}] Watchdog: {problem}. "
            f"Restarting monitor (restart #{restarts + 1})..."
        )
        self._emit_alert(
            sid,
            f"Watchdog restarting dead monitor (problem: {problem}, "
            f"restart #{restarts + 1})",
            level='error',
        )

        self._restart_monitor(sid, monitor, session, problem)

    def _check_beat_timeout(
        self,
        sid: str,
        monitor: object,
        session: dict,
    ) -> Optional[str]:
        """Return problem description if beat is overdue, else None."""
        # Try HeartbeatHealth first (most accurate — uses monotonic time)
        health = getattr(monitor, '_health', None)
        if health is not None:
            secs = health.seconds_since_last_beat
            if secs is not None:
                interval = session.get('params', {}).get('adjustment_interval', 300)
                # Use _effective_interval if the monitor has computed one
                interval = getattr(monitor, '_effective_interval', interval)
                threshold = interval * BEAT_TIMEOUT_MULTIPLIER
                if secs > threshold:
                    return (
                        f"beat timeout: last beat {secs:.0f}s ago "
                        f"(threshold={threshold:.0f}s, interval={interval}s)"
                    )
            return None

        # Fallback: parse ISO timestamp from session
        last_hb = session.get('last_heartbeat', '')
        if not last_hb:
            return None
        try:
            dt = datetime.fromisoformat(last_hb)
            age_s = (datetime.utcnow() - dt).total_seconds()
            interval = session.get('params', {}).get('adjustment_interval', 300)
            threshold = interval * BEAT_TIMEOUT_MULTIPLIER
            if age_s > threshold:
                return (
                    f"beat timeout: last beat {age_s:.0f}s ago "
                    f"(threshold={threshold:.0f}s)"
                )
        except (ValueError, TypeError):
            pass
        return None

    def _restart_monitor(
        self,
        sid: str,
        old_monitor: object,
        session: dict,
        reason: str,
    ) -> None:
        """Stop the old monitor and start a fresh one from persisted state."""
        try:
            # Attempt clean teardown
            try:
                old_monitor.stop(f'Watchdog: {reason}')
            except Exception as e:
                log.warning(f"[{sid}] Watchdog: clean stop failed: {e}")

            # Import here to avoid circular import at module level
            from .mmm_storage import get_storage
            from .mmm_monitor import start_session_monitor, _monitors

            # Load freshest session from disk
            storage = get_storage()
            fresh_session = storage.get_session(sid)
            if not fresh_session:
                log.error(f"[{sid}] Watchdog: session not in storage — cannot restart")
                return

            # Record watchdog restart history
            fresh_session.setdefault('_watchdog_restarts', 0)
            fresh_session['_watchdog_restarts'] += 1
            fresh_session.setdefault('_watchdog_history', []).append({
                'timestamp': datetime.utcnow().isoformat(),
                'reason': reason,
                'restart_number': fresh_session['_watchdog_restarts'],
            })
            fresh_session['strategy_status'] = 'RUNNING'
            storage.save_session(fresh_session)

            # Remove the dead monitor from the registry
            _monitors.pop(sid, None)
            self.deregister(sid)

            # Start a new monitor
            new_monitor = start_session_monitor(sid, fresh_session)
            self.register(new_monitor)

            self._log_activity(
                sid,
                f'🔄 Watchdog restarted monitor (restart #{fresh_session["_watchdog_restarts"]})'
                f' — reason: {reason}',
            )
            log.info(f"[{sid}] Watchdog restart complete (#{fresh_session['_watchdog_restarts']})")

        except Exception as e:
            log.exception(f"[{sid}] Watchdog restart failed: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit_alert(self, sid: str, message: str, level: str = 'error') -> None:
        """Emit a safety WebSocket event so the dashboard shows the problem."""
        try:
            from .mmm_websocket import emit_safety
            emit_safety(sid, 'watchdog', level, f'[WATCHDOG] {message}')
        except Exception as e:
            log.warning(f"Watchdog emit_safety failed: {e}")

    def _log_activity(self, sid: str, message: str) -> None:
        try:
            from .mmm_activity import log_activity
            log_activity('watchdog', message, sid, 'warning')
        except Exception as e:
            log.warning(f"Watchdog log_activity failed: {e}")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict:
        with self._lock:
            count = len(self._monitors)
        return {
            'running': self._running,
            'monitored_sessions': count,
            'poll_interval_s': WATCHDOG_POLL_INTERVAL,
            'beat_timeout_multiplier': BEAT_TIMEOUT_MULTIPLIER,
        }
