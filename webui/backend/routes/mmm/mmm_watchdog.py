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
from datetime import datetime, timezone
from typing import Dict, Optional

log = logging.getLogger('mmm_watchdog')

WATCHDOG_POLL_INTERVAL   = 15       # seconds between watchdog sweeps
BEAT_TIMEOUT_MULTIPLIER  = 3        # max intervals before "stuck" detection
MAX_RESTARTS_PER_SESSION = 10       # safety cap — stop restarting after this many

# Exponential backoff settings for restart cooldown
BACKOFF_BASE_SECONDS     = 30       # initial cooldown after restart
BACKOFF_MULTIPLIER       = 2.0      # exponential growth factor
BACKOFF_MAX_SECONDS      = 600      # cap at 10 minutes


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
        # Track last restart times for exponential backoff
        self._last_restart: Dict[str, float] = {}  # session_id → monotonic timestamp
        # F5 fix: deferred restart timestamps — avoids blocking sweep loop for 30s
        self._pending_restart_at: Dict[str, float] = {}  # session_id → wall time to restart

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

        # Supervise RUNNING sessions (normal operation) and EXITING sessions.
        # EXITING was previously invisible to the watchdog — a stuck exit_all
        # would leave positions open on the exchange with no monitor, no alert,
        # and no recovery. If an EXITING session's thread dies or times out,
        # mark it as partial-exit and alert rather than silently leaving it stuck.
        if status not in ('RUNNING', 'EXITING'):
            return

        # For EXITING sessions: a stuck monitor means exit_all is hung.
        # Mark partial and alert — do NOT silently restart (that would re-run
        # the full algo when the user only wanted to exit).
        if status == 'EXITING':
            thread = getattr(monitor, '_thread', None)
            is_running = getattr(monitor, '_running', False)
            # EXITING sessions need extended time: scissor exit is patient by design —
            # up to 10 minutes of limit-order attempts to protect P&L (no market orders).
            # 12-minute (720s) floor covers the 10-minute exit window plus API overhead.
            # Kill switch also benefits: its 3 fast rounds finish well within 720s.
            _beat_problem = self._check_beat_timeout(sid, monitor, session)
            if _beat_problem is not None:
                # Re-check against the 720s floor before declaring stuck.
                health = getattr(monitor, '_health', None)
                secs_since = health.seconds_since_last_beat if health else None
                if secs_since is not None and secs_since < 720:
                    _beat_problem = None  # within 12-minute grace, not stuck yet
            stuck = (is_running and (thread is None or not thread.is_alive())) or \
                    (_beat_problem is not None)
            if stuck:
                log.error(
                    f"[{sid}] Watchdog: EXITING session stuck (beat timeout or dead thread) — "
                    f"exit_all did not complete. Positions may still be open on exchange."
                )
                session['_exit_all_partial'] = True
                if not session.get('_exit_all_failed_positions'):
                    # A7-04 fix: guard _build_failed_list() — if it raises, the alert
                    # and stop must still fire. A failed position list is advisory;
                    # blocking the operator alert on its failure is never acceptable.
                    try:
                        from .mmm_exit_all import _build_failed_list
                        session['_exit_all_failed_positions'] = _build_failed_list(session)
                    except Exception as _bfl_err:
                        log.error(
                            f"[{sid}] Watchdog: _build_failed_list failed (non-critical): {_bfl_err} "
                            f"— operator alert will still fire"
                        )
                        session['_exit_all_failed_positions'] = []
                self._emit_alert(
                    sid,
                    "EXIT STUCK: exit_all timed out. Positions may still be open on exchange. "
                    "Check Delta Exchange and close manually.",
                    level='critical',
                )
                try:
                    from .mmm_storage import get_storage
                    get_storage().update_session(sid, {
                        'strategy_status': 'STOPPED',
                        '_exit_all_partial': True,
                        '_exit_all_failed_positions': session.get('_exit_all_failed_positions', []),
                    })
                except Exception as _se:
                    log.error(f"[{sid}] Watchdog: could not persist EXIT STUCK state: {_se}")
                monitor.stop(f"Watchdog: EXITING session stuck — {self._check_beat_timeout(sid, monitor, session) or 'thread dead'}")
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

        # ---- Check backoff cooldown ----
        restarts = session.get('_watchdog_restarts', 0)
        cooldown_remaining = self._get_cooldown_remaining(sid, restarts)
        if cooldown_remaining > 0:
            log.debug(
                f"[{sid}] Watchdog: {problem} but in cooldown "
                f"({cooldown_remaining:.0f}s remaining)"
            )
            return  # wait for cooldown to expire

        # ---- Restart ----
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
            # Set session to PAUSED so the UI shows the correct state
            # and the user can use the Resume button to revive it.
            try:
                session['strategy_status'] = 'PAUSED'
                from .mmm_storage import get_storage
                get_storage().save_session(session)
                log.info(f"[{sid}] Watchdog: set session to PAUSED for manual resume")
            except Exception as e:
                log.warning(f"[{sid}] Watchdog: failed to set PAUSED status: {e}")
            # Deregister to stop repeated log spam
            self.deregister(sid)
            return

        # F5 fix: deferred restart — first pass schedules settlement wait without
        # blocking the sweep loop; second pass (after delay elapsed) executes restart.
        import time as _time
        if sid not in self._pending_restart_at:
            SETTLEMENT_DELAY_SECS = 30
            self._pending_restart_at[sid] = _time.time() + SETTLEMENT_DELAY_SECS
            log.critical(
                f"[{sid}] Watchdog: {problem}. "
                f"Restart scheduled in {SETTLEMENT_DELAY_SECS}s "
                f"(settlement wait, restart #{restarts + 1})..."
            )
            self._emit_alert(
                sid,
                f"Watchdog restart scheduled (problem: {problem}, "
                f"restart #{restarts + 1}, settling {SETTLEMENT_DELAY_SECS}s)",
                level='error',
            )
            return

        if _time.time() < self._pending_restart_at[sid]:
            log.debug(
                f"[{sid}] Watchdog: waiting for settlement before restart "
                f"({self._pending_restart_at[sid] - _time.time():.0f}s remaining)"
            )
            return

        # Settlement wait elapsed — execute the restart now
        self._pending_restart_at.pop(sid, None)
        log.critical(
            f"[{sid}] Watchdog: {problem}. "
            f"Executing restart (restart #{restarts + 1})..."
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
            # Fix #14: normalize stored timestamp to tz-aware UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_s = (datetime.now(timezone.utc) - dt).total_seconds()
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

            # Wait for old thread to actually finish so an in-flight
            # heartbeat can't overwrite freshly-saved state.  Timeout
            # prevents hanging if the thread is truly stuck.
            old_thread = getattr(old_monitor, '_thread', None)
            if old_thread is not None and old_thread.is_alive():
                log.info(f"[{sid}] Watchdog: waiting for old thread to exit...")
                old_thread.join(timeout=15)
                if old_thread.is_alive():
                    log.warning(
                        f"[{sid}] Watchdog: old thread did not exit within 15s, "
                        f"proceeding with restart anyway"
                    )

            # Fix A4 (March 12 incident): Settlement delay was previously a
            # blocking time.sleep(30) here. Now handled non-blockingly in
            # _check_monitor via _pending_restart_at before calling this method,
            # so in-flight orders have already settled before we reach here.

            # Import here to avoid circular import at module level
            from .mmm_storage import get_storage
            from .mmm_monitor import start_session_monitor, _monitors, _monitors_lock

            # Load freshest session from disk
            storage = get_storage()
            fresh_session = storage.get_session(sid)
            if not fresh_session:
                log.error(f"[{sid}] Watchdog: session not in storage — cannot restart")
                self._emit_alert(
                    sid,
                    f"Watchdog restart FAILED: session {sid} not found in storage. "
                    f"Positions may still be open on exchange. Manual intervention required.",
                    level='critical',
                )
                self._log_activity(sid, f'🚨 Watchdog restart failed: session not found in storage')
                return

            # Record watchdog restart history
            fresh_session.setdefault('_watchdog_restarts', 0)
            fresh_session['_watchdog_restarts'] += 1
            fresh_session.setdefault('_watchdog_history', []).append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'reason': reason,
                'restart_number': fresh_session['_watchdog_restarts'],
            })
            fresh_session['strategy_status'] = 'RUNNING'
            # Clear _save_disabled flag so the new monitor can save
            fresh_session.pop('_save_disabled', None)
            # H-4 fix: increment generation so any stale save from the old
            # monitor thread is rejected by the generation guard in _save_session()
            fresh_session['_monitor_generation'] = fresh_session.get('_monitor_generation', 0) + 1
            storage.save_session(fresh_session)

            # AUDIT FIX (Fix 4): Reconcile in-memory total_lots against session_fills DB.
            # This is the core fix for ghost positions: after a watchdog restart, the
            # persisted session state may show total_lots=0 for a side that actually
            # has open exposure on the exchange (fills recorded in the ledger but the
            # in-memory dict lost them when the thread died).
            #
            # A7-01 fix: also rebuild positions[] when drift is detected so that
            # the first heartbeat's recompute_side_lots() does NOT revert the
            # scalar correction back to the stale in-memory value.
            try:
                from .mmm_ledger import (get_session_lots_by_side,
                                         get_session_open_positions_by_side)
                from .mmm_state import recompute_side_lots
                db_lots = get_session_lots_by_side(sid)
                _any_drift = False
                for side_key in ('ce', 'pe'):
                    mem_total = fresh_session.get(side_key, {}).get('total_lots', 0)
                    db_total = db_lots.get(side_key, 0)
                    if mem_total != db_total:
                        log.critical(
                            f"[{sid}] Watchdog RECONCILIATION DRIFT: "
                            f"{side_key.upper()} memory total_lots={mem_total} "
                            f"but ledger DB={db_total}. Correcting to DB truth."
                        )
                        if side_key in fresh_session:
                            fresh_session[side_key]['total_lots'] = db_total
                            # Recalculate active_lots = total_lots - frozen_total_lots
                            frozen = fresh_session[side_key].get('frozen_total_lots', 0)
                            fresh_session[side_key]['active_lots'] = max(db_total - frozen, 0)
                        fresh_session.setdefault('_watchdog_reconciliation', []).append({
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'side': side_key,
                            'memory_lots': mem_total,
                            'db_lots': db_total,
                        })
                        _any_drift = True

                # A7-01 fix: when any drift was found, rebuild positions[] from ledger
                # fills so recompute_side_lots() on the first heartbeat derives the same
                # total as the DB truth (not the stale in-memory value).
                if _any_drift:
                    db_positions = get_session_open_positions_by_side(sid)
                    for side_key in ('ce', 'pe'):
                        db_pos_list = db_positions.get(side_key, [])
                        if not db_pos_list:
                            continue
                        db_side_total = sum(p['lots'] for p in db_pos_list)
                        mem_side_total = fresh_session.get(side_key, {}).get('total_lots', 0)
                        if db_side_total != mem_side_total:
                            # Full replace: DB is ground truth after drift
                            log.critical(
                                f"[{sid}] A7-01: Rebuilding {side_key.upper()} positions[] "
                                f"from ledger ({db_side_total} lots) — "
                                f"was {len(fresh_session.get(side_key, {}).get('positions', []))} entries"
                            )
                            fresh_session.setdefault(side_key, {})['positions'] = db_pos_list
                            recompute_side_lots(fresh_session[side_key])

                storage.save_session(fresh_session)
            except Exception as recon_err:
                log.error(f"[{sid}] Watchdog reconciliation failed (non-fatal): {recon_err}")

            # Remove the dead monitor from the registry (C-1 fix: use lock)
            with _monitors_lock:
                _monitors.pop(sid, None)
            self.deregister(sid)

            # Start a new monitor — use 'monitor_restore' context so shape
            # violations (e.g. strangle after STRADDLE_WITH_ADJUSTMENT shift) warn
            # but do not hard-block the watchdog restart.
            new_monitor = start_session_monitor(sid, fresh_session, context='monitor_restore')
            self.register(new_monitor)
            
            # Record restart time for exponential backoff
            self._record_restart(sid)

            # Re-assert RUNNING status after new monitor starts —
            # belt-and-suspenders in case the old thread slipped through
            # and overwrote the status between our save above and now.
            fresh_session['strategy_status'] = 'RUNNING'
            fresh_session.pop('_save_disabled', None)
            storage.save_session(fresh_session)

            self._log_activity(
                sid,
                f'🔄 Watchdog restarted monitor (restart #{fresh_session["_watchdog_restarts"]})'
                f' — reason: {reason}',
            )
            log.warning(f"[{sid}] Watchdog restart complete (#{fresh_session['_watchdog_restarts']})")

        except Exception as e:
            log.exception(f"[{sid}] Watchdog restart failed: {e}")
            # Restart failed — set session to PAUSED so the user can resume,
            # and fire alerts so the failure is visible (not a silent STOPPED).
            alert_msg = (
                f"Watchdog restart FAILED for {sid}: {e}. "
                f"Session set to PAUSED — use Resume to revive. "
                f"Positions may still be open on exchange."
            )
            self._emit_alert(sid, alert_msg, level='critical')
            self._log_activity(sid, f'🚨 Watchdog restart failed: {e} — session set to PAUSED')
            try:
                from .mmm_storage import get_storage
                storage = get_storage()
                failed_session = storage.get_session(sid)
                if failed_session:
                    failed_session['strategy_status'] = 'PAUSED'
                    failed_session['_paused_reason'] = f'Watchdog restart failed: {e}'
                    failed_session['_paused_at'] = datetime.now(timezone.utc).isoformat()
                    storage.save_session(failed_session)
                    log.warning(f"[{sid}] Watchdog: set session to PAUSED after restart failure")
            except Exception as save_err:
                log.error(f"[{sid}] Watchdog: could not set PAUSED after restart failure: {save_err}")

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

    def _get_cooldown_remaining(self, sid: str, restart_count: int) -> float:
        """
        Calculate remaining cooldown seconds using exponential backoff.
        
        Returns 0 if cooldown has expired or no restart has occurred.
        """
        with self._lock:
            last_restart_time = self._last_restart.get(sid)
        
        if last_restart_time is None:
            return 0.0
        
        # Calculate required cooldown: base * (multiplier ^ restart_count)
        # Capped at BACKOFF_MAX_SECONDS
        cooldown = min(
            BACKOFF_BASE_SECONDS * (BACKOFF_MULTIPLIER ** restart_count),
            BACKOFF_MAX_SECONDS
        )
        
        elapsed = time.monotonic() - last_restart_time
        remaining = cooldown - elapsed
        return max(0.0, remaining)

    def _record_restart(self, sid: str) -> None:
        """Record the restart time for exponential backoff tracking."""
        with self._lock:
            self._last_restart[sid] = time.monotonic()

    def clear_backoff(self, sid: str) -> None:
        """
        Clear backoff state for a session (e.g., after manual resume or successful period).
        
        This allows immediate restart if needed after user intervention.
        """
        with self._lock:
            self._last_restart.pop(sid, None)
        log.debug(f"[{sid}] Watchdog backoff cleared")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict:
        with self._lock:
            count = len(self._monitors)
            active_cooldowns = {}
            for sid, last_time in self._last_restart.items():
                # We don't have restart count here, use estimate from session
                elapsed = time.monotonic() - last_time
                if elapsed < BACKOFF_MAX_SECONDS:
                    active_cooldowns[sid] = {
                        'elapsed_s': round(elapsed, 1),
                    }
        
        return {
            'running': self._running,
            'monitored_sessions': count,
            'poll_interval_s': WATCHDOG_POLL_INTERVAL,
            'beat_timeout_multiplier': BEAT_TIMEOUT_MULTIPLIER,
            'backoff': {
                'base_s': BACKOFF_BASE_SECONDS,
                'multiplier': BACKOFF_MULTIPLIER,
                'max_s': BACKOFF_MAX_SECONDS,
            },
            'active_cooldowns': active_cooldowns,
        }
