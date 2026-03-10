"""
MMM Monitor — Background Heartbeat Loop

The central orchestration loop that runs every `adjustment_interval` seconds.
Coordinates all algorithm phases:
  §4 Heartbeat: Fetch premiums → close-at-5 → safety → triggers → adjustment
  §8 Both-sides-up detection
  §9 Reversal integration
  §10 Strike shift integration
  §11 Close-at-5 integration
  §13-14 Safety checks

Maps to MONEY_POWER_CALCULATION_LOGIC.md §4: The Heartbeat

Created: February 15, 2026
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta, timezone

import random

from .mmm_state import recompute_side_lots, get_session_summary
from .mmm_trigger import (
    evaluate_triggers, update_trigger_snapshots,
    apply_theta_acceleration, compute_adaptive_interval,
    OUTCOME_NONE, OUTCOME_CE,
    OUTCOME_PE, OUTCOME_BOTH,
)
from .mmm_heartbeat_health import HeartbeatHealth
from .mmm_circuit_breaker import CircuitBreaker
from .mmm_engine import get_engine
from .mmm_reversal import (
    detect_reversal, is_cooldown_active, activate_cooldown,
    should_skip_reversal_adjustment, record_reversal,
    handle_reversal_skip_transition,
)
from .mmm_strike_shift import (
    check_shift_needed, freeze_current_positions,
    find_new_strike, activate_new_strike,
)
from .mmm_wind_down import (
    is_wind_down_active, compute_wind_down_action,
    get_lifo_close_fills, apply_lifo_removals,
    get_wind_down_close_threshold, get_wind_down_status,
)
from .mmm_close_at_5 import (
    scan_closeable_positions, close_position,
    check_side_fully_closed, check_both_sides_closed,
)
from .mmm_analytics_storage import get_analytics_storage
from .mmm_safety import (
    get_safety, should_block_adjustment, get_block_action, should_pause,
    update_peak_pnl, reset_peak_pnl_on_reversal,
)
from .mmm_pending_orders import (
    register_pending, clear_pending, get_pending,
    check_and_resolve_pending, clear_all as clear_all_pending,
)
from .mmm_websocket import (
    emit_heartbeat, emit_adjustment, emit_reversal,
    emit_strike_shift, emit_close_at_5, emit_both_sides_alert,
    emit_safety, emit_pnl_update, emit_status_change,
    emit_harvest, emit_recycle,
)
from .mmm_harvester import scan_harvestable_positions
from .mmm_recycler import execute_lot_recycling
from .mmm_perp_hedge import (
    run_perp_hedge, close_all_perp, get_perp_summary,
    is_perp_hedge_enabled,
)
from .mmm_storage import get_storage
from .mmm_constants import LOT_SIZE_BTC, strike_key as _strike_key, _D, _LOT
from .mmm_margin_guardian import MarginGuardian, TIER_GREEN, TIER_YELLOW, TIER_ORANGE, TIER_RED, TIER_CRITICAL
from .mmm_regime import MMMRegimeEngine, ACTION_NORMAL, ACTION_WARN, ACTION_BLOCK_CE_SELLS, ACTION_BLOCK_PE_SELLS, ACTION_BLOCK_ALL_SELLS, ACTION_FORCE_REDUCE, ACTION_PAUSE
from .mmm_telegram import (
    alert_margin_tier_change, alert_emergency_close,
    alert_session_stopped, alert_rapid_check_activated,
    alert_max_loss_breach,
)

# L-2 fix: module-level import removes per-call import-lock overhead on every heartbeat.
# Wrapped in try/except to avoid blocking startup if the activity module fails.
try:
    from .mmm_activity import log_activity
except ImportError:
    def log_activity(*args, **kwargs):  # noqa: E306 — fallback no-op
        pass

log = logging.getLogger('mmm_monitor')


class MMMMonitor:
    """
    Background heartbeat monitor for an MMM session.

    Runs in a separate thread, executing the heartbeat loop every interval.
    Each heartbeat:
      1. Fetch CE and PE premiums (mark price for monitoring)
      2. Run close-at-5 scan
      3. Run all safety checks
      4. Evaluate triggers
      5. Process outcome (none / CE / PE / both)
      6. Execute adjustment if needed
      7. Update P&L and emit WebSocket events
      8. Save state to storage
    """

    def __init__(self, session_id: str, session: Dict):
        self.session_id = session_id
        self.session = session
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._force_event = threading.Event()   # Force-heartbeat signal
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # C-2 fix: protects self.session pointer swap in the heartbeat thread
        # against concurrent API reads from Flask request threads.
        self._session_lock = threading.Lock()

        # H-4 fix: generation stamp set in start(); saves are rejected if a
        # newer monitor has already claimed a higher generation number.
        self._my_generation = 0

        self._engine = get_engine()
        self._safety = get_safety()

        # Institutional heartbeat infrastructure
        base_interval = session.get('params', {}).get('adjustment_interval', 300)
        self._health = HeartbeatHealth(session_id, base_interval)
        cb_threshold = session.get('params', {}).get('circuit_breaker_threshold', None)
        self._circuit = CircuitBreaker(session_id, failure_threshold=cb_threshold)

        # Margin Guardian (P1 safety layer)
        self._margin_guardian = MarginGuardian(session_id)

        # Regime Engine (pre-adjustment risk controls)
        self._regime_engine = MMMRegimeEngine()
        self._last_iv_data = {}   # Populated by _fetch_premiums
        self._last_gamma_data = {}  # Populated by _calculate_portfolio_delta

        # Lazy-loaded
        self._executor = None
        self._initializer = None

    @property
    def executor(self):
        if self._executor is None:
            from .mmm_executor import get_executor
            self._executor = get_executor()
        return self._executor

    @property
    def initializer(self):
        if self._initializer is None:
            from .mmm_initializer import get_initializer
            self._initializer = get_initializer()
        return self._initializer

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start(self):
        """Start the heartbeat monitor in a background thread."""
        if self._running:
            log.warning(f"Monitor already running for {self.session_id}")
            return

        self._running = True
        self._stop_event.clear()

        # Respect stored PAUSED status on restore (e.g. after backend restart).
        # If the session was PAUSED by safety (trailing stop, gamma emergency),
        # keep it paused — don't silently unpause and start trading.
        stored_status = self.session.get('strategy_status', 'RUNNING')
        if stored_status == 'PAUSED':
            self._paused = True
            log.info(f"[{self.session_id}] Restoring in PAUSED state (reason: {self.session.get('_paused_reason', 'unknown')})")
        else:
            self._paused = False
            self.session['strategy_status'] = 'RUNNING'

        # H-4 fix: increment generation counter so stale old-thread saves are rejected
        self.session['_monitor_generation'] = self.session.get('_monitor_generation', 0) + 1
        self._my_generation = self.session['_monitor_generation']
        log.debug(f"[{self.session_id}] Monitor generation={self._my_generation}")
        self.session['entry_time'] = (
            self.session.get('entry_time') or datetime.now(timezone.utc).isoformat()
        )
        self.session['updated_at'] = datetime.now(timezone.utc).isoformat()

        # Analytics: Track session start time
        analytics = self.session.setdefault('analytics', {})
        if not analytics.get('session_start_time'):
            analytics['session_start_time'] = datetime.now(timezone.utc).isoformat()
            # Capture initial lots from session
            # M-4 fix: guard against ce/pe being None
            ce_state = self.session.get('ce') or {}
            pe_state = self.session.get('pe') or {}
            analytics['initial_ce_lots'] = ce_state.get('original_lots', 0) if isinstance(ce_state, dict) else 0
            analytics['initial_pe_lots'] = pe_state.get('original_lots', 0) if isinstance(pe_state, dict) else 0
            # Initialize cumulative traded volume with initial position
            analytics['total_ce_lots_traded'] = analytics['initial_ce_lots']
            analytics['total_pe_lots_traded'] = analytics['initial_pe_lots']
            analytics['total_combined_lots_traded'] = analytics['initial_ce_lots'] + analytics['initial_pe_lots']

        # T4-2: Clear any stale in-memory pending order registry entries from a
        # previous monitor run on this same session_id (within the same process).
        # The in-memory _registry in mmm_pending_orders survives process-internal
        # restarts (e.g., watchdog re-instantiating a MMMMonitor without a full
        # process restart).  Without this, an in-flight order registered by the
        # previous monitor instance could block the new monitor's first adjustment
        # cycle indefinitely.  Clearing at start() gives every new monitor instance
        # a clean slate while preserving the registry for all other sessions.
        try:
            clear_all_pending(self.session_id)
            log.debug(f"[{self.session_id}] Pending order registry cleared at start")
        except Exception as _pend_e:
            log.warning(f"[{self.session_id}] Failed to clear pending order registry at start: {_pend_e}")

        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"mmm-monitor-{self.session_id}",
            daemon=True,
        )
        self._thread.start()

        # M-3 fix: emit correct restored status, not always 'RUNNING'
        restored_status = 'PAUSED' if self._paused else 'RUNNING'
        emit_status_change(
            self.session_id, 'IDLE', restored_status,
            f'Monitor started (restored: {restored_status})',
        )
        log.warning(f"[{self.session_id}] Monitor started (status: {restored_status})")

        # Register with watchdog supervisor
        try:
            from .mmm_watchdog import MMMWatchdog
            MMMWatchdog.get_instance().register(self)
        except Exception as _we:
            log.error(f"[{self.session_id}] Watchdog registration failed — session may not auto-restart: {_we}")  # L-1 fix

        # Audit fix: emit WebSocket safety alert if storage detected a checksum mismatch
        # on load. This makes data corruption visible to the operator in the UI.
        if self.session.get('_checksum_warning'):
            try:
                emit_safety(
                    self.session_id, 'data_integrity', 'critical',
                    f'[{self.session_id}] Checksum mismatch on session load — '
                    f'data may have been corrupted or manually edited. '
                    f'Verify positions match exchange before trading.',
                    {'session_id': self.session_id},
                )
                log_activity(
                    'safety_warning',
                    f'⚠️ Data integrity: Checksum mismatch on session load — '
                    f'verify positions before trading.',
                    self.session_id, 'error',
                )
            except Exception:
                pass


    def stop(self, reason: str = 'User requested'):
        """Stop the heartbeat monitor."""
        if not self._running:
            return

        old_status = self.session.get('strategy_status', 'RUNNING')
        self._running = False
        self._stop_event.set()
        self.session['strategy_status'] = 'STOPPED'
        self.session['updated_at'] = datetime.now(timezone.utc).isoformat()
        self.session['_stopped_reason'] = reason

        # Clear any pause metadata
        self.session.pop('_paused_reason', None)
        self.session.pop('_paused_at', None)
        self.session.pop('_paused_resume_at', None)

        # Analytics: Track session end time and duration
        analytics = self.session.setdefault('analytics', {})
        analytics['session_end_time'] = datetime.now(timezone.utc).isoformat()
        start_time = analytics.get('session_start_time')
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
                # Fix #14: normalize naive stored timestamp to tz-aware UTC
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                end_dt = datetime.now(timezone.utc)
                analytics['session_duration_seconds'] = (end_dt - start_dt).total_seconds()
            except (ValueError, TypeError):
                pass

        # Log activity BEFORE disabling save so it's visible in the feed
        try:
            log_activity('session_stopped',
                        f'\u23f9 Session stopped: {reason}',
                        self.session_id, 'warning',
                        {'reason': reason, 'old_status': old_status})
        except Exception:
            pass

        self._save_my_session()

        # AFTER our own save, mark save-disabled so that any in-flight
        # heartbeat completing after this point cannot overwrite the
        # session status.  This prevents the watchdog restart race
        # condition where an old heartbeat saves stale STOPPED status
        # over the watchdog's freshly-saved RUNNING status.
        self.session['_save_disabled'] = True
        
        # Persist analytics to separate storage (survives session deletion)
        try:
            analytics_storage = get_analytics_storage()
            analytics_storage.save_session_analytics(self.session)
            log.info(f"Saved analytics for {self.session_id} to persistent storage")
        except Exception as e:
            log.error(f"Failed to save analytics to persistent storage: {e}")

        emit_status_change(
            self.session_id, old_status, 'STOPPED', reason
        )
        log.warning(f"[{self.session_id}] Monitor stopped: {reason}")

        # Clear any pending orders from the guard registry
        try:
            clear_all_pending(self.session_id)
        except Exception:
            pass

        # Deregister from watchdog
        try:
            from .mmm_watchdog import MMMWatchdog
            MMMWatchdog.get_instance().deregister(self.session_id)
        except Exception as _we:
            pass

    def pause(self, reason: str = 'User requested', resume_at: str = None):
        """Pause the heartbeat (monitoring continues but no adjustments).

        Args:
            reason: Human-readable reason for the pause.
            resume_at: Optional ISO timestamp of expected auto-resume time.
        """
        old_status = self.session.get('strategy_status', 'RUNNING')
        self._paused = True
        # C-2 fix: write critical status fields under lock
        with self._session_lock:
            self.session['strategy_status'] = 'PAUSED'
            self.session['updated_at'] = datetime.now(timezone.utc).isoformat()
            self.session['_paused_reason'] = reason
            self.session['_paused_at'] = datetime.now(timezone.utc).isoformat()
            if resume_at:
                self.session['_paused_resume_at'] = resume_at
            else:
                self.session.pop('_paused_resume_at', None)

        self._save_my_session()

        emit_status_change(
            self.session_id, old_status, 'PAUSED', reason
        )
        log.info(f"Monitor paused for {self.session_id}: {reason}")

    def resume(self, reason: str = 'User requested'):
        """Resume from paused state.

        BUG-3 FIX: If whipsaw cooldown is still active, log a warning.
        The heartbeat's Step 4.5 whipsaw gate will still block adjustments
        even after resume, so the resume is safe — but the operator should
        know the cooldown is still enforced.
        """
        old_status = self.session.get('strategy_status', 'PAUSED')
        self._paused = False
        # C-2 fix: write critical status fields under lock
        with self._session_lock:
            self.session['strategy_status'] = 'RUNNING'
            self.session['updated_at'] = datetime.now(timezone.utc).isoformat()
            # Clear pause metadata
            self.session.pop('_paused_reason', None)
            self.session.pop('_paused_at', None)
            self.session.pop('_paused_resume_at', None)
            # Force immediate reconciliation on next heartbeat
            self.session['_recon_counter'] = 0
            self.session['_force_recon'] = True

        self._save_my_session()

        emit_status_change(
            self.session_id, old_status, 'RUNNING', reason
        )
        log.info(f"Monitor resumed for {self.session_id}: {reason}")

        # BUG-3 FIX: Warn if whipsaw cooldown is still active after resume.
        # Adjustments will still be blocked by Step 4.5 whipsaw gate.
        _whipsaw_at = self.session.get('_whipsaw_paused_at')
        if _whipsaw_at:
            try:
                _wp = datetime.fromisoformat(_whipsaw_at)
                if _wp.tzinfo is None:
                    _wp = _wp.replace(tzinfo=timezone.utc)
                _interval = self.session.get('params', {}).get('adjustment_interval', 300)
                _remaining = (_interval * 2) - (datetime.now(timezone.utc) - _wp).total_seconds()
                if _remaining > 0:
                    log.warning(
                        f"[{self.session_id}] BUG-3: Session resumed but whipsaw "
                        f"cooldown still active ({_remaining:.0f}s remaining). "
                        f"Adjustments will remain blocked until cooldown expires."
                    )
                    log_activity('info',
                                f'⚠️ Whipsaw cooldown still active ({_remaining:.0f}s remaining). '
                                f'Heartbeat resumed but adjustments blocked until cooldown expires.',
                                self.session_id, 'warning',
                                {'whipsaw_remaining': round(_remaining)})
            except (ValueError, TypeError):
                pass

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def get_session_snapshot(self) -> Dict:
        """Return a deep copy of session under lock — safe for API reads.

        C-2 fix: API endpoints must call this instead of accessing monitor.session
        directly to avoid torn reads during the heartbeat's session pointer swap.

        Audit fix: Previously used copy.copy() (shallow), which still shared nested
        dict references (ce, pe, positions[]) with the heartbeat thread. A concurrent
        heartbeat modifying session['ce']['total_lots'] while an API thread reads the
        snapshot would cause a torn read. deepcopy() eliminates this race entirely.
        The cost (~0.5ms for <50KB session dict) is negligible vs the data integrity
        guarantee.
        """
        import copy
        with self._session_lock:
            return copy.deepcopy(self.session)

    def _save_my_session(self, session: Dict = None):
        """Convenience wrapper that passes this monitor's generation to _save_session.

        H-4 fix: all heartbeat-path saves go through here so that stale saves
        from old monitor threads (after a watchdog restart) are automatically rejected.
        
        Also persists health telemetry so it's available even when monitor is stopped.
        """
        target = session if session is not None else self.session
        
        # Persist health grade and summary to session
        if self._health is not None:
            try:
                health_summary = self._health.summary()
                target['_health_grade'] = health_summary.get('grade', 'N/A')
                target['_health_summary'] = {
                    'grade': health_summary.get('grade'),
                    'latency_p50_ms': health_summary.get('latency_p50_ms'),
                    'latency_p95_ms': health_summary.get('latency_p95_ms'),
                    'miss_rate_pct': health_summary.get('miss_rate_pct'),
                    'total_beats': health_summary.get('total_beats'),
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }
            except Exception as e:
                log.debug(f"[{self.session_id}] Failed to persist health: {e}")
        
        _save_session(target, self._my_generation)

    def _should_stop(self) -> bool:
        """Bug #11 fix: check if stop has been requested (use in long operations)."""
        return self._stop_event.is_set() or not self._running

    def force_heartbeat(self) -> bool:
        """Force the next heartbeat to run immediately (skip wait timer).

        Sets a threading event that interrupts the inter-heartbeat wait.
        The heartbeat itself is identical to a normal one — same trigger
        evaluation, safety checks, and guards.  After the forced beat
        the loop resumes its default interval-based schedule.

        Returns True if force was accepted, False if monitor is not running.
        """
        if not self._running:
            return False
        self._force_event.set()
        log.info(f"[{self.session_id}] ⚡ Force heartbeat requested")
        return True

    def _wait_for_next_cycle(self, timeout: float):
        """Wait for next heartbeat cycle, interruptible by stop or force.

        Polls every 0.5s so a force_heartbeat() call triggers within 500ms.
        After a force, the event is cleared and the loop proceeds normally.
        """
        end_time = time.monotonic() + timeout
        while time.monotonic() < end_time:
            if self._stop_event.is_set():
                return
            if self._force_event.is_set():
                self._force_event.clear()
                log_activity('force_heartbeat',
                            '⚡ Force Heartbeat — running immediately',
                            self.session_id, 'info')
                return
            remaining = end_time - time.monotonic()
            self._stop_event.wait(timeout=min(0.5, max(0, remaining)))

    # =========================================================================
    # Main Loop
    # =========================================================================

    def _run_loop(self):
        """Main heartbeat loop (runs in background thread)."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            while self._running and not self._stop_event.is_set():
                # RELOAD session from storage to pick up hot-reload params
                storage = get_storage()
                try:
                    fresh_session = storage.get_session(self.session_id)
                except Exception as e:
                    log.critical("Storage read failed — aborting heartbeat: %s", e)
                    self._interruptible_sleep(
                        self.session.get('params', {}).get('adjustment_interval', 300)
                    )
                    continue
                if fresh_session:
                    old_params = self.session.get('params', {})
                    new_params = fresh_session.get('params', {})
                    
                    # Clear _save_disabled from freshly loaded session so
                    # this monitor instance can save normally.
                    fresh_session.pop('_save_disabled', None)
                    # C-2 fix: swap session pointer under lock so API threads
                    # reading self.session see a consistent snapshot.
                    with self._session_lock:
                        self.session = fresh_session
                    
                    # Log ALL hot-reloaded parameter changes
                    for pkey in new_params:
                        old_val = old_params.get(pkey)
                        new_val = new_params.get(pkey)
                        if old_val is not None and old_val != new_val:
                            log_activity('info',
                                        f'🔄 Hot Reload: {pkey} updated {old_val} → {new_val}',
                                        self.session_id, 'success',
                                        {'param': pkey, 'old_value': old_val, 'new_value': new_val})
                else:
                    log.error(f"Session {self.session_id} not found in storage, stopping monitor")
                    self.stop('Session not found')
                    break

                params = self.session.get('params', {})
                interval = params.get('adjustment_interval', 300)

                # Layer 1: Adaptive interval scaling (hours-to-expiry)
                minutes_to_expiry = self._get_minutes_to_expiry()
                hours_to_expiry = minutes_to_expiry / 60.0 if minutes_to_expiry is not None else None
                adaptive_enabled = params.get('adaptive_interval_enabled', True)

                adaptive_result = compute_adaptive_interval(
                    interval, hours_to_expiry, enabled=adaptive_enabled,
                )
                if adaptive_result['adaptive']:
                    interval = adaptive_result['effective_interval']
                    self.session['_adaptive_tier'] = adaptive_result['tier_label']
                    self.session['_adaptive_interval'] = interval
                else:
                    self.session.pop('_adaptive_tier', None)
                    self.session.pop('_adaptive_interval', None)

                # Layer 2: Theta acceleration (last N minutes — trigger widening + sub-30s)
                # Can only make interval SHORTER, never longer
                if minutes_to_expiry is not None:
                    accel = apply_theta_acceleration(
                        self.session, minutes_to_expiry
                    )
                    if accel.get('accelerated'):
                        interval = accel['effective_interval']
                        # Store effective trigger move in ephemeral session key
                        # so evaluate_triggers reads it WITHOUT corrupting params.
                        # (Bug #1 fix: never modify params['min_trigger_move'])
                        self.session['_effective_min_trigger_move'] = accel['effective_min_trigger_move']
                        self.session['_theta_accelerated'] = True
                    elif self.session.pop('_theta_accelerated', False):
                        # Restore: remove ephemeral override
                        self.session.pop('_effective_min_trigger_move', None)

                # Layer 3: Margin Guardian rapid-check mode
                # When margin is elevated (YELLOW+), shrink interval to 15s
                # for faster detection and response.
                margin_tier = self._margin_guardian.last_tier
                if margin_tier in (TIER_YELLOW, TIER_ORANGE, TIER_RED, TIER_CRITICAL):
                    RAPID_CHECK_INTERVAL = 15  # seconds
                    if interval > RAPID_CHECK_INTERVAL:
                        interval = RAPID_CHECK_INTERVAL
                        self.session['_margin_rapid_check'] = True
                elif self.session.pop('_margin_rapid_check', None):
                    pass  # cleared — back to normal interval

                # Store effective interval so _heartbeat() can log it
                self._effective_interval = interval

                # Record next heartbeat time
                self.session['next_heartbeat'] = (
                    datetime.now(timezone.utc) + timedelta(seconds=interval)
                ).isoformat()

                hb_start = time.monotonic()
                try:
                    self._loop.run_until_complete(self._heartbeat())
                except Exception as e:
                    log.exception(f"Heartbeat error for {self.session_id}: {e}")
                    self.session['last_error'] = str(e)

                    # Circuit breaker: record failure (not a blunt stop)
                    self._circuit.record_failure(str(e))

                    # H-16 fix: best-effort state preservation after heartbeat crash
                    try:
                        current_pnl = self.session.get('unrealized_pnl', 0) + self.session.get('realized_pnl', 0) - self.session.get('total_fees', 0)
                        update_peak_pnl(self.session, current_pnl)
                        self._save_my_session(self.session)
                    except Exception as save_err:
                        log.error(f"Failed to save state after heartbeat crash: {save_err}")

                    # Graduated response: only hard-stop on truly unrecoverable errors
                    # (e.g. programming bugs), not exchange connectivity issues
                    unrecoverable = any(kw in str(e).lower() for kw in (
                        'typeerror', 'attributeerror', 'nameerror', 'assertionerror',
                    ))
                    if unrecoverable:
                        log.critical(
                            f"[{self.session_id}] Unrecoverable error, stopping: {e}"
                        )
                        self.stop(f'Unrecoverable error: {type(e).__name__}')
                        break

                    if self._circuit.should_alert:
                        from .mmm_websocket import emit_safety
                        emit_safety(
                            self.session_id, 'circuit_breaker', 'critical',
                            f'Exchange API unreachable — circuit breaker OPEN '
                            f'(depth {self._circuit.open_depth}). '
                            f'Using cached prices for safety checks.',
                            self._circuit.summary(),
                        )

                    # Health record the error beat
                    self._health.record_beat(
                        'error',
                        latency_ms=(time.monotonic() - hb_start) * 1000,
                        error_msg=str(e),
                    )

                # Cycle-based wait: subtract heartbeat execution time so total
                # cycle ≈ interval, not interval + execution_time.
                # ± 2s jitter to desync sessions from each other.
                elapsed = time.monotonic() - hb_start
                jitter = random.uniform(-2.0, 2.0)
                remaining = max(0, interval - elapsed + jitter)
                if elapsed > interval:
                    log.warning(
                        f"[{self.session_id}] Heartbeat took {elapsed:.1f}s "
                        f"(exceeds {interval}s interval) — running next immediately"
                    )
                self._wait_for_next_cycle(remaining)

        except Exception as e:
            log.exception(f"Monitor loop crashed for {self.session_id}: {e}")
            self.session['strategy_status'] = 'ERROR'
            self.session['last_error'] = str(e)
            self._save_my_session()
        finally:
            # §26.10: Close perp position on session stop/crash
            # The event loop is still open here, so run_until_complete works.
            try:
                perp_lots = self.session.get('perp_hedge', {}).get('lots', 0)
                if perp_lots != 0 and is_perp_hedge_enabled(self.session):
                    reason = self.session.get('_stopped_reason', 'session_stop')
                    log.warning(
                        f"[{self.session_id}] Closing perp position "
                        f"({perp_lots:+d} lots) on stop: {reason}"
                    )
                    self._loop.run_until_complete(
                        close_all_perp(self.session, self.executor, reason)
                    )
            except Exception as perp_e:
                log.error(
                    f"[{self.session_id}] Failed to close perp on stop: {perp_e}"
                )
            self._loop.close()
            self._loop = None

    # =========================================================================
    # §4: Single Heartbeat
    # =========================================================================

    async def _heartbeat(self):
        """Execute one heartbeat cycle.

        NOTE (M-2): _session_lock is NOT held during heartbeat field updates.
        API threads calling get_session_snapshot() (which acquires the lock)
        may see torn state mid-heartbeat. This is an accepted trade-off:
        acquiring the lock for the entire heartbeat (~1-5s) would block all
        API reads. API consumers should treat snapshot data as eventually
        consistent (may lag up to one heartbeat interval).
        """
        session = self.session
        sid = self.session_id
        safety_events = []  # Initialize here so it's always defined even on early returns

        # H-10 fix: Reload params from storage at heartbeat start to pick up
        # hot-reload changes (max_loss_amount, gamma_cap_enabled, etc.)
        try:
            from .mmm_storage import get_storage
            fresh = get_storage().get_session(sid)
            if fresh and isinstance(fresh.get('params'), dict):
                session['params'].update(fresh['params'])
        except Exception as params_e:
            log.warning(f"[{sid}] Failed to reload params from storage: {params_e}")

        session['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
        # NOTE: error_count is reset at the END of a successful heartbeat,
        # not here at the start. This ensures consecutive errors accumulate.

        # Fix #23 + #24: Always recompute derived fields from positions[] at heartbeat
        # start. This also auto-migrates old sessions to the Unified Position Ledger
        # format (adds positions[] key if not present) and ensures _pos_id is present
        # in all backward-compat views so ID-based removal works correctly.
        for _ck_side in ('ce', 'pe'):
            _ck_state = session.get(_ck_side, {})
            if not isinstance(_ck_state, dict):
                continue
            _ck_stored = _ck_state.get('total_lots', 0)
            recompute_side_lots(_ck_state)
            session[_ck_side] = _ck_state
            _ck_new = _ck_state.get('total_lots', 0)
            if _ck_stored != _ck_new:
                log.critical(
                    f"[{sid}] CONSISTENCY CHECK: {_ck_side.upper()} "
                    f"total_lots corrected from {_ck_stored} → {_ck_new} "
                    f"(positions[] recompute fixed stale derived value)"
                )

        # Heartbeat counter (no activity log — summary emitted at end)
        session['_heartbeat_counter'] = session.get('_heartbeat_counter', 0) + 1

        beat_start_mono = time.monotonic()

        # Generate entry walkthrough on first heartbeat
        if session['_heartbeat_counter'] == 1:
            try:
                from .mmm_walkthrough import generate_entry_walkthrough
                entry_wt = generate_entry_walkthrough(session)
                session.setdefault('_walkthrough_log', []).append(entry_wt)
            except Exception as e:
                log.warning(f'Entry walkthrough generation failed: {e}')

        # Initialize walkthrough tracking for this heartbeat
        self._hb_wt = {
            'outcome': 'none',
            'adjustment': None,
            'reversal': None,
            'shift': None,
            'close_at_5': [],
            'safety_events': [],
            'pnl': None,
        }

        # Step 0: Reconcile with exchange positions (§14.5 — exchange reality check)
        # H-9 fix: skip reconciliation while paused so user can investigate mismatches
        if not self._paused:
            await self._reconcile_exchange_positions()
        else:
            session.setdefault('_force_recon', True)

        # Step 0.5: Margin Guardian — real-time margin utilization check
        margin_result = await self._check_margin_guardian()
        # Store margin snapshot for heartbeat WS emission
        if margin_result and margin_result.get('checked'):
            self._last_margin_snapshot = {
                'tier': margin_result['tier'],
                'utilization_pct': round(margin_result.get('utilization_pct', 0), 1),
                'enabled': True,
            }
        else:
            self._last_margin_snapshot = None

        if margin_result and margin_result.get('checked'):
            if margin_result['tier'] in (TIER_RED, TIER_CRITICAL):
                # RED/CRITICAL: emergency close already handled inside _check_margin_guardian
                # C-1 fix: run cleanup before returning so peak P&L, session save,
                # heartbeat emit, and health telemetry are not skipped.
                try:
                    current_pnl = session.get('unrealized_pnl', 0) + session.get('realized_pnl', 0) - session.get('total_fees', 0)
                    update_peak_pnl(session, current_pnl)
                    self._emit_heartbeat_data(0, 0)
                    self._save_my_session(session)
                    latency_ms = (time.monotonic() - beat_start_mono) * 1000
                    self._health.record_beat('ok', latency_ms=latency_ms)
                except Exception as _cleanup_err:
                    log.error(f"[{sid}] Cleanup after margin emergency failed: {_cleanup_err}")
                return
            if margin_result['tier'] == TIER_ORANGE:
                # ORANGE: flag for aggressive buyback (used later in heartbeat)
                session['_margin_wind_down'] = True
            elif margin_result['tier'] == TIER_YELLOW:
                # YELLOW: block new sells (checked by adjustment logic)
                session['_margin_block_sells'] = True
            else:
                # GREEN: clear any stale flags
                session.pop('_margin_wind_down', None)
                session.pop('_margin_block_sells', None)

        # Step 1: Fetch current premiums — with circuit breaker + fallback
        ce_now, pe_now, fetch_ok = await self._fetch_premiums_with_fallback()

        if not fetch_ok:
            # ----------------------------------------------------------------
            # PARTIAL BEAT: premium fetch failed.
            # Instead of silently aborting (the old behaviour which skipped
            # close-at-5 and safety), run critical safety tasks using the
            # last cached prices.  This ensures positions get closed and
            # max-loss is enforced even during exchange outages.
            # ----------------------------------------------------------------
            cached_ce = (getattr(self, '_premium_cache', {}) or {}).get(
                (float(session.get('ce', {}).get('active_strike', 0)), 'call'), None
            )
            cached_pe = (getattr(self, '_premium_cache', {}) or {}).get(
                (float(session.get('pe', {}).get('active_strike', 0)), 'put'), None
            )

            if cached_ce is not None and cached_pe is not None:
                # Run close-at-5 + safety using stale cached prices
                log.warning(
                    f"[{sid}] PARTIAL BEAT: using cached prices "
                    f"CE={cached_ce:.2f} PE={cached_pe:.2f} "
                    f"(circuit={self._circuit.state.value})"
                )
                log_activity('heartbeat_partial',
                            f'⚠️ Partial Beat: Exchange unreachable — '
                            f'running safety checks with cached prices '
                            f'(CE={cached_ce:.2f}, PE={cached_pe:.2f})',
                            sid, 'warning',
                            {'circuit_state': self._circuit.state.value,
                             'cached_ce': cached_ce, 'cached_pe': cached_pe})
                await self._process_close_at_5(cached_ce, cached_pe)
                fresh_unrealized = self._engine.compute_unrealized_pnl(
                    session, self._make_fetch_fn()
                )
                session['unrealized_pnl'] = fresh_unrealized
                minutes_to_expiry = self._get_minutes_to_expiry()
                safety_events = self._safety.run_all_checks(session, minutes_to_expiry)
                # Process safety events on partial beat — not just resume,
                # also auto_close and stop (critical safety actions like
                # max_loss must fire even during exchange outages).
                for event in safety_events:
                    if event.get('action') == 'resume' and self._paused:
                        log_activity('session_resumed',
                                    f'Auto-resumed (partial beat): {event.get("message", "")}',
                                    sid, 'success')
                        self.resume(event.get('message', 'Auto-resume'))
                if should_block_adjustment(safety_events):
                    reason, action_type = get_block_action(safety_events)
                    if action_type == 'auto_close':
                        log.critical(
                            f"[{sid}] SAFETY AUTO-CLOSE on partial beat: {reason}"
                        )
                        await self._auto_close_all(reason, emergency=True)
                        self._save_my_session(session)
                        return
                    elif action_type == 'stop':
                        log.critical(
                            f"[{sid}] SAFETY STOP on partial beat: {reason}"
                        )
                        self.stop(reason)
                        self._save_my_session(session)
                        return
                self._save_my_session(session)
                latency_ms = (time.monotonic() - beat_start_mono) * 1000
                self._health.record_beat(
                    'partial', latency_ms=latency_ms,
                    ce_premium=cached_ce, pe_premium=cached_pe,
                )
            else:
                log.warning(f"[{sid}] MISS BEAT: no cached prices available, skipping entirely")
                log_activity('heartbeat_miss',
                            f'💤 Miss Beat: No cached prices — skipping heartbeat '
                            f'(circuit={self._circuit.state.value})',
                            sid, 'warning',
                            {'circuit_state': self._circuit.state.value})
                latency_ms = (time.monotonic() - beat_start_mono) * 1000
                self._health.record_beat('miss', latency_ms=latency_ms)

            # BUG FIX: Even on miss/partial beats, run safety checks that
            # don't require prices (e.g. whipsaw auto-resume, time-based
            # events).  Without this, sessions paused by whipsaw can never
            # auto-resume when exchange is unreachable.
            try:
                minutes_to_expiry = self._get_minutes_to_expiry()
                safety_events = self._safety.run_all_checks(session, minutes_to_expiry)
                # Process all critical safety events on miss beat — auto_close
                # and stop must fire even when exchange is unreachable.
                for event in safety_events:
                    if event.get('action') == 'resume' and self._paused:
                        log_activity('session_resumed',
                                    f'Auto-resumed (miss beat): {event.get("message", "")}',
                                    sid, 'success')
                        self.resume(event.get('message', 'Auto-resume'))
                if should_block_adjustment(safety_events):
                    reason, action_type = get_block_action(safety_events)
                    if action_type == 'auto_close':
                        log.critical(
                            f"[{sid}] SAFETY AUTO-CLOSE on miss beat: {reason}"
                        )
                        await self._auto_close_all(reason, emergency=True)
                        self._save_my_session(session)
                        return
                    elif action_type == 'stop':
                        log.critical(
                            f"[{sid}] SAFETY STOP on miss beat: {reason}"
                        )
                        self.stop(reason)
                        self._save_my_session(session)
                        return
                self._save_my_session(session)
            except Exception as safety_e:
                log.warning(f"[{sid}] Safety check during miss beat failed: {safety_e}")

            # H-4 fix: Update peak P&L even on miss/partial beats using cached value
            try:
                cached_pnl = session.get('unrealized_pnl', 0) or 0
                realized = session.get('realized_pnl', 0) or 0
                fees = session.get('total_fees', 0) or 0
                current_total = cached_pnl + realized - fees
                update_peak_pnl(session, current_total)
                self._save_my_session(session)
            except Exception as peak_e:
                log.warning(f"[{sid}] Peak P&L update during miss/partial beat failed: {peak_e}")

            return

        # Premium values (logged in heartbeat summary, not as separate activity)
        ce_strike = session.get('ce', {}).get('active_strike', 'N/A')
        pe_strike = session.get('pe', {}).get('active_strike', 'N/A')

        # Stale-price guard: warn if HeartbeatHealth detects frozen exchange data
        if self._health.stale_ce_detected or self._health.stale_pe_detected:
            stale_sides = []
            if self._health.stale_ce_detected:
                stale_sides.append('CE')
            if self._health.stale_pe_detected:
                stale_sides.append('PE')
            stale_msg = (
                f"Stale price detected for {'/'.join(stale_sides)}: "
                f"mark_price unchanged for {3}+ consecutive beats. "
                f"Exchange may be serving cached data."
            )
            log_activity('stale_price_warning', f'⚠️ STALE PRICE: {stale_msg}',
                        sid, 'warning',
                        {'stale_ce': self._health.stale_ce_detected,
                         'stale_pe': self._health.stale_pe_detected})
            emit_safety(sid, 'stale_price', 'alert', stale_msg,
                       {'stale_ce': self._health.stale_ce_detected,
                        'stale_pe': self._health.stale_pe_detected})

        # Wind-down status included in heartbeat summary (no per-heartbeat activity)

        # Populate premium cache for sync engine calls (_make_fetch_fn)
        await self._prefetch_all_premiums(ce_now, pe_now)

        # ATM Auto-Close Check: if enabled, close all when spot ≈ ORIGINAL strike
        # CRITICAL: Must use original_strike (entry strike), NOT active_strike.
        # active_strike changes on shifts/reversals — using it would falsely
        # trigger when the algo has shifted closer to spot (normal operation).
        # The purpose of close_at_atm is to protect when spot reaches the
        # ORIGINAL entry strike — real danger territory.
        params = session.get('params', {})

        # ATM Wind-Down Trigger: if enabled, activate wind-down mode when spot ≈ ORIGINAL strike.
        # This is a GENTLER alternative to close_at_atm — instead of closing all positions
        # immediately, it switches the algo into wind-down mode (gradual LIFO buyback).
        # Uses the same 0.5% proximity threshold as close_at_atm.
        # CRITICAL: checks original_strike only on sides with open positions (same guard
        # as close_at_atm — prevents stale zero-lot sides from falsely triggering).
        if params.get('wind_down_on_atm', False):
            if session.get('_atm_wind_down_triggered'):
                log.debug(f"[{sid}] ATM wind-down already triggered, skipping check")
            else:
                _wd_spot = await self._fetch_spot_price()
                if _wd_spot > 0:
                    _wd_atm_threshold = _wd_spot * 0.005  # 0.5% of spot (same as close_at_atm)
                    _ce_orig = session.get('ce', {}).get('original_strike', 0)
                    _pe_orig = session.get('pe', {}).get('original_strike', 0)
                    _ce_lots = session.get('ce', {}).get('total_lots', 0)
                    _pe_lots = session.get('pe', {}).get('total_lots', 0)
                    _atm_wd_side = None

                    if _ce_orig and _ce_lots > 0 and abs(_wd_spot - _ce_orig) <= _wd_atm_threshold:
                        _atm_wd_side = 'CE'
                    elif _pe_orig and _pe_lots > 0 and abs(_wd_spot - _pe_orig) <= _wd_atm_threshold:
                        _atm_wd_side = 'PE'

                    if _atm_wd_side:
                        _triggered_strike = _ce_orig if _atm_wd_side == 'CE' else _pe_orig
                        # Save original wind_down_enabled so it can be restored when positions close
                        session['_atm_prev_wind_down_enabled'] = params.get('wind_down_enabled', False)
                        # Set guard flag BEFORE any state changes to prevent re-entry
                        session['_atm_wind_down_triggered'] = True
                        # Auto-enable the wind_down_enabled master switch so is_wind_down_active()
                        # returns True. wind_down_on_atm is the user's explicit opt-in — the ATM
                        # trigger should activate wind-down without requiring the manual toggle.
                        params['wind_down_enabled'] = True
                        # Persist the change to params_json immediately to survive hot-reload
                        self._save_my_session(session)
                        log.warning(
                            f"[{sid}] ATM WIND-DOWN TRIGGERED: Spot ${_wd_spot:.0f} within "
                            f"0.5% of {_atm_wd_side} ORIGINAL strike ${_triggered_strike:.0f}. "
                            f"Switching to wind-down mode (gradual LIFO buyback)."
                        )
                        log_activity('atm_wind_down',
                                     f'🌙 ATM WIND-DOWN: Spot ${_wd_spot:.0f} reached '
                                     f'{_atm_wd_side} ORIGINAL strike ${_triggered_strike:.0f} '
                                     f'— activating wind-down mode (gradual buyback)',
                                     sid, 'warning',
                                     {'spot': _wd_spot,
                                      'ce_original_strike': _ce_orig,
                                      'pe_original_strike': _pe_orig,
                                      'triggered_side': _atm_wd_side,
                                      'triggered_strike': _triggered_strike})
                        emit_safety(
                            sid, 'atm_wind_down', 'warning',
                            f'ATM WIND-DOWN: Spot ${_wd_spot:.0f} reached {_atm_wd_side} '
                            f'ORIGINAL strike ${_triggered_strike:.0f}. Wind-down mode activated.',
                            {'spot': _wd_spot, 'triggered_side': _atm_wd_side,
                             'triggered_strike': _triggered_strike}
                        )

        if params.get('close_at_atm', False):
            # Guard: skip if already triggered this session (prevent repeat fires)
            if session.get('_atm_close_triggered'):
                log.debug(f"[{sid}] ATM auto-close already triggered, skipping")
            else:
                spot_price = await self._fetch_spot_price()
                if spot_price > 0:
                    atm_threshold_pct = 0.005  # 0.5% of spot
                    atm_threshold = spot_price * atm_threshold_pct
                    # Use ORIGINAL strike (entry strike), not active_strike
                    ce_original_strike = session.get('ce', {}).get('original_strike', 0)
                    pe_original_strike = session.get('pe', {}).get('original_strike', 0)
                    # CRITICAL: Only check sides that HAVE open positions.
                    # After close-at-5 or shift, original_strike remains set
                    # even when total_lots = 0 (no positions). Without this
                    # guard, a stale original_strike on a fully-closed side
                    # could falsely trigger ATM auto-close and kill the
                    # other side's perfectly safe positions.
                    ce_total_lots = session.get('ce', {}).get('total_lots', 0)
                    pe_total_lots = session.get('pe', {}).get('total_lots', 0)
                    atm_triggered_side = None

                    if ce_original_strike and ce_total_lots > 0 and abs(spot_price - ce_original_strike) <= atm_threshold:
                        atm_triggered_side = 'CE'
                    elif pe_original_strike and pe_total_lots > 0 and abs(spot_price - pe_original_strike) <= atm_threshold:
                        atm_triggered_side = 'PE'

                    if atm_triggered_side:
                        triggered_strike = ce_original_strike if atm_triggered_side == 'CE' else pe_original_strike
                        # Set guard flag BEFORE close to prevent re-entry
                        session['_atm_close_triggered'] = True
                        log.critical(
                            f"[{sid}] ATM AUTO-CLOSE: Spot ${spot_price:.0f} within "
                            f"0.5% of {atm_triggered_side} ORIGINAL strike "
                            f"${triggered_strike:.0f}. CLOSING ALL."
                        )
                        log_activity('atm_auto_close',
                                    f'🛑 ATM AUTO-CLOSE: Spot ${spot_price:.0f} is at '
                                    f'{atm_triggered_side} ORIGINAL strike ${triggered_strike:.0f} '
                                    f'— closing all positions',
                                    sid, 'error',
                                    {'spot': spot_price,
                                     'ce_original_strike': ce_original_strike,
                                     'pe_original_strike': pe_original_strike,
                                     'triggered_side': atm_triggered_side,
                                     'triggered_strike': triggered_strike})
                        emit_safety(
                            sid, 'atm_auto_close', 'critical',
                            f'ATM AUTO-CLOSE: Spot ${spot_price:.0f} reached {atm_triggered_side} '
                            f'ORIGINAL strike ${triggered_strike:.0f}. Closing all positions.',
                            {'spot': spot_price, 'triggered_side': atm_triggered_side,
                             'triggered_strike': triggered_strike}
                        )
                        await self._auto_close_all(
                            f'ATM auto-close: Spot ${spot_price:.0f} at {atm_triggered_side} '
                            f'original strike ${triggered_strike:.0f}',
                            emergency=True,
                        )
                        # C-2 fix: run cleanup before returning
                        try:
                            current_pnl = session.get('unrealized_pnl', 0) + session.get('realized_pnl', 0) - session.get('total_fees', 0)
                            update_peak_pnl(session, current_pnl)
                            self._emit_heartbeat_data(ce_now, pe_now)
                            self._save_my_session(session)
                            latency_ms = (time.monotonic() - beat_start_mono) * 1000
                            self._health.record_beat('ok', latency_ms=latency_ms)
                        except Exception as _cleanup_err:
                            log.error(f"[{sid}] Cleanup after ATM auto-close failed: {_cleanup_err}")
                        return

        # Step 2: Close-at-5 scan (§11)
        # Fix #11: capture which sides had positions closed so we can re-evaluate
        # triggers before executing any adjustment on the same side.
        _close_at_5_sides = await self._process_close_at_5(ce_now, pe_now)

        # Step 2.1: Profit Harvesting (M1) — proactive frozen position cleanup
        # Runs after close-at-5, before safety checks, so freed capacity is
        # visible to safety. Disabled during wind-down (wind-down has own logic).
        if not is_wind_down_active(session):
            await self._process_harvest()

        # Check if both sides fully closed
        if check_both_sides_closed(session):
            # P1-C fix: clear ATM wind-down flag so a re-initialized round starts clean.
            # When the ATM trigger fired it auto-set wind_down_enabled=True and stored
            # the original value in _atm_prev_wind_down_enabled.  We pop the trigger
            # flag here; the save path (below) uses _atm_prev_wind_down_enabled to
            # restore wind_down_enabled to its original value before writing to DB.
            if session.get('_atm_wind_down_triggered'):
                session.pop('_atm_wind_down_triggered', None)
                log.info(f"[{session.get('session_id')}] Cleared _atm_wind_down_triggered "
                         f"on both-sides-closed — next round will start without ATM wind-down.")
            # §26.10: Close perp before stopping when options are fully closed
            if is_perp_hedge_enabled(session):
                perp_lots = session.get('perp_hedge', {}).get('lots', 0)
                if perp_lots != 0:
                    await close_all_perp(
                        session, self.executor,
                        'both_sides_closed — options expired worthless'
                    )
            self.stop('Both sides fully closed — strategy complete!')
            # H-2 fix: emit final heartbeat data and save before returning
            try:
                current_pnl = session.get('unrealized_pnl', 0) + session.get('realized_pnl', 0) - session.get('total_fees', 0)
                update_peak_pnl(session, current_pnl)
                self._emit_heartbeat_data(ce_now, pe_now)
                self._save_my_session(session)
                latency_ms = (time.monotonic() - beat_start_mono) * 1000
                self._health.record_beat('ok', latency_ms=latency_ms)
            except Exception as _cleanup_err:
                log.error(f"[{sid}] Cleanup after both-sides-closed failed: {_cleanup_err}")
            return

        # ── ONE-SIDE CLOSE GUARD ──────────────────────────────────────────────
        # If one side is fully closed while the other still has open positions,
        # the strategy is imbalanced — one side has no hedge for the other.
        # This violates the core MMM strategy (both sides must be able to offset
        # each other).  PAUSE immediately and alert the user.
        #
        # Use a session flag (_one_side_closed_<side>) to avoid re-pausing on
        # every heartbeat once the session is already in this state.  The flag is
        # cleared as soon as the closed side regains any lots (via adjustment or
        # strike shift on the next trigger cycle).
        for _cs in ['ce', 'pe']:
            _os = 'pe' if _cs == 'ce' else 'ce'
            _ocs_flag = f'_one_side_closed_{_cs}'
            if check_side_fully_closed(session, _cs) and not check_side_fully_closed(session, _os):
                _os_lots = session.get(_os, {}).get('total_lots', 0)
                if not session.get(_ocs_flag):
                    session[_ocs_flag] = True
                    _ocs_msg = (
                        f'{_cs.upper()} fully closed (all positions at or below threshold) '
                        f'but {_os.upper()} has {_os_lots} lot(s) still open — '
                        f'one-sided exposure detected. Session PAUSED. '
                        f'Action required: close {_os.upper()} positions or '
                        f're-enter {_cs.upper()} at a new strike.'
                    )
                    log.error(f"[{sid}] ONE-SIDE CLOSE: {_ocs_msg}")
                    log_activity(
                        'safety_block',
                        f'⛔ ONE-SIDE CLOSE: {_cs.upper()}=0 lots, '
                        f'{_os.upper()}={_os_lots} lots open — unhedged. PAUSED.',
                        sid, 'error',
                        {'closed_side': _cs, 'open_side': _os, 'open_lots': _os_lots},
                    )
                    emit_safety(
                        sid, 'one_side_closed', 'critical', _ocs_msg,
                        {'closed_side': _cs, 'open_side': _os, 'open_lots': _os_lots},
                    )
                    self.pause(f'{_cs.upper()} fully closed — {_os.upper()} unhedged')
                    try:
                        _ocs_pnl = (session.get('unrealized_pnl', 0)
                                    + session.get('realized_pnl', 0)
                                    - session.get('total_fees', 0))
                        update_peak_pnl(session, _ocs_pnl)
                        self._emit_heartbeat_data(ce_now, pe_now)
                        self._save_my_session(session)
                        latency_ms = (time.monotonic() - beat_start_mono) * 1000
                        self._health.record_beat('ok', latency_ms=latency_ms)
                    except Exception as _ocs_err:
                        log.error(f"[{sid}] Cleanup after one-side-close pause failed: {_ocs_err}")
                    return
                # Flag already set (user resumed or subsequent heartbeat) — let run continue
                break
            else:
                # Clear flag when the closed side has regained lots
                session.pop(_ocs_flag, None)
        # ── END ONE-SIDE CLOSE GUARD ──────────────────────────────────────────

        # NOTE: Proactive wind-down (buying back on every heartbeat) was removed.
        # Wind-down now only acts when triggers fire (trigger-based path in the
        # adjustment section below handles this correctly — see OUTCOME_CE/PE branch).
        # Proactive buyback was a bug: it reduced positions on every heartbeat
        # regardless of trigger status, causing unintended position erosion.

        # Bug #7 fix: compute FRESH unrealized P&L before safety checks
        # so that check_max_loss uses current prices, not stale values.
        # Robust v2 Fix #1: P&L is computed AFTER close-at-5 so safety checks
        # use position state that reflects any closed positions. This ensures
        # max-loss and trailing-stop operate on consistent data.
        fresh_unrealized = self._engine.compute_unrealized_pnl(
            session, self._make_fetch_fn()
        )
        session['unrealized_pnl'] = fresh_unrealized

        # Robust v2 Fix #2: If >50% of P&L positions failed to fetch, pause
        if session.get('_pnl_calculation_incomplete'):
            log.error(
                f"[{sid}] P&L CALCULATION INCOMPLETE — >50% of positions "
                f"failed premium fetch. PAUSING session for safety."
            )
            emit_safety(
                sid, 'calculation_incomplete', 'critical',
                'P&L calculation incomplete: >50% of position premium fetches failed. '
                'Session paused to prevent trading with unreliable data.',
                {'fetch_errors': session.get('_pnl_fetch_errors', 0)}
            )
            log_activity('safety_block',
                        f'⛔ P&L calculation incomplete — pausing session',
                        sid, 'error',
                        {'fetch_errors': session.get('_pnl_fetch_errors', 0)})
            self.pause('P&L calculation incomplete — data unreliable')
            # H-3 fix: update peak P&L even when pausing for incomplete data
            current_pnl = session.get('unrealized_pnl', 0) + session.get('realized_pnl', 0) - session.get('total_fees', 0)
            update_peak_pnl(session, current_pnl)
            self._emit_heartbeat_data(ce_now, pe_now)
            self._save_my_session(session)
            return

        # Step 3: Safety checks (§13-14)
        minutes_to_expiry = self._get_minutes_to_expiry()
        safety_events = self._safety.run_all_checks(
            session, minutes_to_expiry
        )

        # Log safety events only when there are actionable ones (not "all clear")
        if safety_events:
            safety_summary = ', '.join([f"{e['type']} ({e['level']})" for e in safety_events])
            log_activity('safety_warning',
                        f'⚠️ Safety: {len(safety_events)} event(s) — {safety_summary}',
                        sid, 'warning',
                        {'event_count': len(safety_events), 'events': [e['type'] for e in safety_events]})

        for event in safety_events:
            emit_safety(
                sid, event['type'], event['level'], event['message'],
                event.get('details')
            )

        # Track safety events for walkthrough
        self._hb_wt['safety_events'] = safety_events

        # Handle safety actions
        _skip_to_pnl = False  # Flag: skip triggers/adjustments but finish heartbeat
        if should_block_adjustment(safety_events):
            reason, action_type = get_block_action(safety_events)
            if action_type == 'auto_close':
                await self._auto_close_all(reason, emergency=True)
                # H-5 fix: run cleanup before returning
                try:
                    current_pnl = session.get('unrealized_pnl', 0) + session.get('realized_pnl', 0) - session.get('total_fees', 0)
                    update_peak_pnl(session, current_pnl)
                    self._emit_heartbeat_data(ce_now, pe_now)
                    self._save_my_session(session)
                    latency_ms = (time.monotonic() - beat_start_mono) * 1000
                    self._health.record_beat('ok', latency_ms=latency_ms)
                except Exception as _cleanup_err:
                    log.error(f"[{sid}] Cleanup after safety auto_close failed: {_cleanup_err}")
                return
            elif action_type == 'stop':
                self.stop(reason)
                # H-5 fix: emit and save before returning
                try:
                    current_pnl = session.get('unrealized_pnl', 0) + session.get('realized_pnl', 0) - session.get('total_fees', 0)
                    update_peak_pnl(session, current_pnl)
                    self._emit_heartbeat_data(ce_now, pe_now)
                    self._save_my_session(session)
                    latency_ms = (time.monotonic() - beat_start_mono) * 1000
                    self._health.record_beat('ok', latency_ms=latency_ms)
                except Exception as _cleanup_err:
                    log.error(f"[{sid}] Cleanup after safety stop failed: {_cleanup_err}")
                return
            else:
                # stop_adjustments: block new adjustments but keep heartbeat
                # running so close-at-5 continues AND peak_pnl decays
                # (preventing permanent trailing-stop lockout).
                # BUG FIX: Previously this returned early, which skipped
                # update_peak_pnl(), _save_my_session(), and record_beat().
                # The decaying peak never ran, so the trailing stop fired
                # permanently once breached.
                log_activity('adjustments_stopped',
                             f'⛔ Adjustments blocked: {reason}',
                             sid, 'warning',
                             {'reason': reason, 'action_type': action_type})
                _skip_to_pnl = True

        pause_needed, pause_reason = should_pause(safety_events)
        if pause_needed:
            pause_event = next(
                (e for e in safety_events if e.get('action') == 'pause'), {}
            )
            # Extract auto-resume time from event details (e.g. whipsaw cooldown)
            resume_at = pause_event.get('details', {}).get('resume_at')
            resume_info = ''
            if resume_at:
                resume_info = f' Will auto-resume at {resume_at[:19]}.'
            log_activity('session_paused',
                        f'Auto-paused by safety: {pause_reason}{resume_info}',
                        sid, 'warning',
                        {'reason': pause_reason, 'trigger': pause_event.get('type', 'unknown'),
                         'resume_at': resume_at})
            self.pause(pause_reason, resume_at=resume_at)

        # Handle auto-resume events (whipsaw timeout, max_adjustments limit raised, etc.)
        for event in safety_events:
            if event.get('action') == 'resume' and self._paused:
                log_activity('session_resumed',
                            f'Auto-resumed: {event.get("message", "")}',
                            sid, 'success')
                self.resume(event.get('message', 'Auto-resume'))

        # ────────────────── NEW: Regime Controls ──────────────────
        # Step 3.5: Portfolio Delta/Gamma + Volatility Regime + Trend Detection
        # Runs AFTER safety (safety hard stops always fire first)
        # Runs BEFORE trigger evaluation (gates adjustment engine)
        # Risk-reducing trades (close-at-5, wind-down) already ran above — immune to regime blocks

        # Fetch portfolio delta + gamma EARLY — outside try so crash doesn't kill regime
        # This populates self._last_gamma_data for the regime engine
        portfolio_delta = await self._calculate_portfolio_delta()
        session['portfolio_delta'] = portfolio_delta

        # Fetch spot price for regime controls (reused by trend guard)
        regime_spot_price = await self._fetch_spot_price()
        session['_regime_spot_price'] = regime_spot_price

        # MASTER SWITCH: skip all regime checks when disabled
        regime_master = params.get('regime_enabled', False)
        if not regime_master:
            session['_regime_action'] = ACTION_NORMAL
            # Still emit regime data (observation mode) but don't gate adjustments
            try:
                spot_price = regime_spot_price
                iv_data = self._last_iv_data
                gamma_data = self._last_gamma_data
                self._regime_engine.update_vol_regime(session, iv_data, spot_price)
                self._regime_engine.update_gamma_cap(
                    session, gamma_data, spot_price, minutes_to_expiry,
                )
                self._regime_engine.update_trend_guard(session, spot_price)
                # Compute but DON'T enforce — observation only
                self._regime_engine.compute_regime_action(session)
                regime_status = self._regime_engine.get_regime_status(session)
                regime_status['observation_mode'] = True
                from .mmm_websocket import emit_regime
                emit_regime(sid, regime_status)
            except Exception as e:
                log.error("Regime engine error — failing closed: %s", e, exc_info=True)
                session['_regime_action'] = ACTION_BLOCK_ALL_SELLS
            # Fall through to normal trigger evaluation
        else:
            # Regime is ENABLED — enforce regime actions
            try:
                spot_price = regime_spot_price
                iv_data = self._last_iv_data
                gamma_data = self._last_gamma_data

                self._regime_engine.update_vol_regime(session, iv_data, spot_price)
                self._regime_engine.update_gamma_cap(
                    session, gamma_data, spot_price, minutes_to_expiry,
                )
                self._regime_engine.update_trend_guard(session, spot_price)
                regime_action = self._regime_engine.compute_regime_action(session)

                # Emit regime status via WebSocket (included in heartbeat, low overhead)
                regime_status = self._regime_engine.get_regime_status(session)
                from .mmm_websocket import emit_regime
                emit_regime(sid, regime_status)

                # Log regime state
                if regime_action != ACTION_NORMAL:
                    vol_r = session.get('_vol_regime', 'NORMAL')
                    gamma_r = session.get('_gamma_regime', 'NORMAL')
                    trend_r = session.get('_trend_regime', 'NORMAL')
                    trend_tier = session.get('_trend_tier', 0)
                    tier_names = {0: 'NONE', 1: 'ALERT', 2: 'GUARD', 3: 'BLOCK', 4: 'WIND_DOWN'}
                    tier_name = tier_names.get(trend_tier, str(trend_tier))
                    log_activity('regime_control',
                                f'Regime: {regime_action} '
                                f'(vol={vol_r}, gamma={gamma_r}, trend={trend_r}, '
                                f'trend_tier={tier_name})',
                                sid, 'warning' if trend_tier < 3 else 'error',
                                regime_status)
                    emit_safety(
                        sid, 'regime', 'alert' if 'BLOCK' in regime_action else 'warning',
                        f'Regime controls active: {regime_action}',
                        regime_status,
                    )
                else:
                    pass  # Regime normal — included in heartbeat summary

                # Handle FORCE_REDUCE (gamma emergency — Priority 2)
                # NOTE: only PAUSEs and warns — does NOT auto-wind-down
                if regime_action == ACTION_FORCE_REDUCE:
                    log_activity('regime_emergency',
                                f'GAMMA EMERGENCY: $Gamma={session.get("_portfolio_dollar_gamma", 0):.2f} '
                                f'exceeds emergency limit. Session PAUSED for manual review.',
                                sid, 'error',
                                {'dollar_gamma': session.get('_portfolio_dollar_gamma', 0)})
                    emit_safety(
                        sid, 'regime', 'critical',
                        f'⚠️ GAMMA EMERGENCY: $Γ={session.get("_portfolio_dollar_gamma", 0):.2f} — session paused. '
                        f'Review positions and manually wind down if needed.',
                        {'dollar_gamma': session.get('_portfolio_dollar_gamma', 0)},
                    )
                    self.pause('Gamma emergency — manual review required')
                    _skip_to_pnl = True

                # Handle ACTION_PAUSE — vol_regime_action='pause' or
                # trend_action='pause' requested explicit session pause.
                if not _skip_to_pnl and regime_action == ACTION_PAUSE:
                    vol_r = session.get('_vol_regime', 'NORMAL')
                    trend_r = session.get('_trend_regime', 'NORMAL')
                    trend_tier = session.get('_trend_tier', 0)
                    log_activity('regime_pause',
                                f'Regime PAUSE: session paused by regime controls '
                                f'(vol={vol_r}, trend={trend_r}, tier={trend_tier})',
                                sid, 'error',
                                {'vol_regime': vol_r, 'trend_regime': trend_r,
                                 'trend_tier': trend_tier})
                    emit_safety(
                        sid, 'regime', 'critical',
                        f'⚠️ Regime PAUSE: Session paused — '
                        f'vol={vol_r}, trend={trend_r}. Manual review required.',
                        {'vol_regime': vol_r, 'trend_regime': trend_r,
                         'trend_tier': trend_tier},
                    )
                    self.pause(f'Regime pause — vol={vol_r}, trend={trend_r}')
                    _skip_to_pnl = True

                # Handle BLOCK_ALL_SELLS — skip trigger evaluation entirely
                if not _skip_to_pnl and regime_action == ACTION_BLOCK_ALL_SELLS:
                    log_activity('regime_block',
                                f'All sells blocked by regime controls — skipping trigger evaluation',
                                sid, 'warning')
                    _skip_to_pnl = True

            except Exception as e:
                log.warning(f"[{sid}] Regime check failed (non-fatal): {e}")
                # Regime failure is non-fatal — continue with normal heartbeat
                session['_regime_action'] = ACTION_NORMAL
        # ────────────────── END Regime Controls ──────────────────

        # Step 4: If paused, check for both-sides-up auto-decision (30s timeout)
        if self._paused:
            status = session.get('strategy_status', '')
            if status == 'BOTH_SIDES_UP':
                both_up_at = session.get('both_sides_up_at', '')
                if both_up_at:
                    try:
                        up_time = datetime.fromisoformat(both_up_at)
                        # Fix #14: normalize to tz-aware UTC before subtraction
                        if up_time.tzinfo is None:
                            up_time = up_time.replace(tzinfo=timezone.utc)
                        elapsed = (datetime.now(timezone.utc) - up_time).total_seconds()
                        if elapsed >= 30:
                            # Fix #18: Re-fetch premiums before auto-decision.
                            # The original ce_now/pe_now are 30+ seconds stale.
                            try:
                                fresh_ce, fresh_pe, fresh_ok = await self._fetch_premiums_with_fallback()
                                if fresh_ok:
                                    ce_now_decision = fresh_ce
                                    pe_now_decision = fresh_pe
                                    log.info(f"[{sid}] Both-sides auto-decision using FRESH premiums: "
                                             f"CE={fresh_ce:.2f}, PE={fresh_pe:.2f}")
                                else:
                                    ce_now_decision = ce_now
                                    pe_now_decision = pe_now
                                    log.warning(f"[{sid}] Both-sides re-fetch failed, using stale premiums")
                            except Exception as e:
                                ce_now_decision = ce_now
                                pe_now_decision = pe_now
                                log.warning(f"[{sid}] Both-sides re-fetch error: {e}, using stale premiums")

                            # Auto-decide: hedge whichever side has loss
                            decision = self._auto_decide_both_sides(
                                session, ce_now_decision, pe_now_decision
                            )
                            log_activity('both_sides_auto_decision',
                                        f'⏱️ Auto-decision after {elapsed:.0f}s: {decision} '
                                        f'(no user response within 30s)',
                                        sid, 'warning',
                                        {'decision': decision, 'elapsed_seconds': elapsed})
                            # Apply decision
                            session['both_sides_decision'] = decision
                            session['both_sides_decided_at'] = datetime.now(timezone.utc).isoformat()
                            session['both_sides_auto'] = True
                            adj_history = session.get('adjustment_history', [])
                            adj_history.append({
                                'type': 'both_sides_decision',
                                'decision': decision,
                                'auto': True,
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                            })
                            session['adjustment_history'] = adj_history
                            # Resume
                            self._paused = False
                            session['strategy_status'] = 'RUNNING'
                            emit_status_change(
                                sid, 'BOTH_SIDES_UP', 'RUNNING',
                                f'Auto-decision: {decision} (30s timeout)'
                            )
                            # Process the chosen adjustment directly
                            # (skip trigger evaluation — it would hit BOTH again)
                            # Fix #18: Use fresh premiums for the actual adjustment execution
                            if decision == 'adjust_pe':
                                await self._process_adjustment(
                                    'ce', 'pe', ce_now_decision, pe_now_decision,
                                    ce_now_decision, pe_now_decision
                                )
                            elif decision == 'adjust_ce':
                                await self._process_adjustment(
                                    'pe', 'ce', pe_now_decision, ce_now_decision,
                                    ce_now_decision, pe_now_decision
                                )
                            # else 'skip' — just resume, no adjustment needed
                        else:
                            log_activity('info',
                                        f'BOTH SIDES UP - Waiting for user decision '
                                        f'({30 - elapsed:.0f}s remaining)',
                                        sid, 'warning')
                            _skip_to_pnl = True
                    except (ValueError, TypeError):
                        pass

            if self._paused and not _skip_to_pnl:
                # Paused status shown in live heartbeat summary
                _skip_to_pnl = True

        # Step 4.5 (BUG-3 FIX): Whipsaw cooldown gate — independent of _paused.
        # If user manually resumes during whipsaw cooldown, _paused becomes False
        # but _whipsaw_paused_at is still active. We must respect the cooldown
        # regardless of how the session got unpaused.
        if not _skip_to_pnl:
            _whipsaw_paused_at = session.get('_whipsaw_paused_at')
            if _whipsaw_paused_at:
                try:
                    _wp_time = datetime.fromisoformat(_whipsaw_paused_at)
                    if _wp_time.tzinfo is None:
                        _wp_time = _wp_time.replace(tzinfo=timezone.utc)
                    _wp_interval = params.get('adjustment_interval', 300)
                    _wp_resume_after = _wp_interval * 2
                    _wp_elapsed = (datetime.now(timezone.utc) - _wp_time).total_seconds()
                    if _wp_elapsed < _wp_resume_after:
                        _wp_remaining = _wp_resume_after - _wp_elapsed
                        log.info(
                            f"[{sid}] BUG-3: Whipsaw cooldown still active "
                            f"({_wp_elapsed:.0f}s / {_wp_resume_after}s) — "
                            f"{_wp_remaining:.0f}s remaining. Blocking adjustments."
                        )
                        log_activity('adjustment_skipped',
                                    f'⏸️ Whipsaw cooldown active — {_wp_remaining:.0f}s remaining. '
                                    f'Adjustments blocked.',
                                    sid, 'warning',
                                    {
                                        'reason': 'whipsaw_cooldown',
                                        'elapsed': round(_wp_elapsed),
                                        'remaining': round(_wp_remaining),
                                        'resume_after': _wp_resume_after,
                                    })
                        _skip_to_pnl = True
                    else:
                        # Cooldown expired — clean up the flag
                        session.pop('_whipsaw_paused_at', None)
                        log.info(
                            f"[{sid}] Whipsaw cooldown expired "
                            f"({_wp_elapsed:.0f}s >= {_wp_resume_after}s) — "
                            f"adjustments re-enabled"
                        )
                except (ValueError, TypeError):
                    # Corrupted timestamp — clear it
                    session.pop('_whipsaw_paused_at', None)

        # Step 5: Cooldown check (§14.3)
        if not _skip_to_pnl and is_cooldown_active(session):
            # Cooldown status shown in live heartbeat summary
            _skip_to_pnl = True

        # ── Skip trigger evaluation + adjustments when safety blocks ──
        # When trailing stop (or other stop_adjustments safety) fires,
        # skip directly to P&L update so peak_pnl decays and session saves.
        if _skip_to_pnl:
            self._emit_heartbeat_data(ce_now, pe_now)
            # Fall through to Step 7.5 (perp hedge) + Step 8 (P&L) + save + record_beat

        if not _skip_to_pnl:
            # Step 6: Evaluate triggers (§7)
            # Robust v2 Fix #6: Validate trigger_snapshot has active strike key.
            # If missing (e.g. after restart, adoption, or strike key mismatch),
            # initialize it with the CURRENT premium to avoid false trigger (baseline=0).
            for _side_key in ('ce', 'pe'):
                _side = session.get(_side_key, {})
                _active_strike = _side.get('active_strike', 0)
                if _active_strike > 0:
                    from .mmm_constants import strike_key as _sk
                    _strike_key = _sk(_active_strike)
                    _snap = _side.get('trigger_snapshot', {})
                    if _strike_key not in _snap or _snap.get(_strike_key, 0) == 0:
                        _current_prem = ce_now if _side_key == 'ce' else pe_now
                        if 'trigger_snapshot' not in _side:
                            _side['trigger_snapshot'] = {}
                        _side['trigger_snapshot'][_strike_key] = _current_prem
                        session[_side_key] = _side
                        log.warning(
                            f"[{sid}] Robust v2 Fix #6: Initialized missing trigger_snapshot "
                            f"for {_side_key.upper()}[{_strike_key}] = {_current_prem:.2f}"
                        )
                        log_activity('trigger_stale',
                                    f'⚠️ Trigger snapshot initialized for {_side_key.upper()} '
                                    f'@ {_strike_key} = ${_current_prem:.2f} (was missing/zero)',
                                    sid, 'warning',
                                    {'side': _side_key, 'strike': _strike_key, 'premium': _current_prem})

            trigger_result = evaluate_triggers(session, ce_now, pe_now)
            outcome = trigger_result['outcome']

            # Store trigger data for heartbeat summary (no separate activity)
            params = session.get('params', {})
            min_trigger = trigger_result.get('min_trigger_move', params.get('min_trigger_move', 10.0))
            ce_excess_pct = trigger_result.get('ce_excess_pct', 0)
            pe_excess_pct = trigger_result.get('pe_excess_pct', 0)
            session['_last_trigger_result'] = {
                'ce_excess_pct': round(ce_excess_pct, 2),
                'pe_excess_pct': round(pe_excess_pct, 2),
                'min_trigger_move': min_trigger,
                'outcome': outcome,
            }

            # Step 7: Process outcome (§4.7)
            if outcome == OUTCOME_NONE:
                pass  # Stable — included in heartbeat summary

            elif outcome == OUTCOME_BOTH:
                # §8: Both sides up — pause and alert user
                log_activity('warning',
                            f'⚠️ BOTH SIDES UP! CE and PE both triggered - Pausing for manual decision',
                            sid, 'error',
                            {
                                'ce_premium': ce_now,
                                'pe_premium': pe_now,
                                'ce_excess': trigger_result.get('ce_excess', 0),
                                'pe_excess': trigger_result.get('pe_excess', 0)
                            })
                self.pause('Both sides triggered')
                session['strategy_status'] = 'BOTH_SIDES_UP'
                session['both_sides_up_at'] = datetime.now(timezone.utc).isoformat()
            
                # Analytics: Track both_sides_up event (no trading logic impact)
                analytics = session.setdefault('analytics', {})
                analytics.setdefault('both_sides_up_timestamps', []).append(datetime.now(timezone.utc).isoformat())
                if len(analytics['both_sides_up_timestamps']) > 200:
                    analytics['both_sides_up_timestamps'] = analytics['both_sides_up_timestamps'][-200:]

                emit_both_sides_alert(
                    sid, ce_now, pe_now,
                    trigger_result['ce_trigger'],
                    trigger_result['pe_trigger'],
                    trigger_result['ce_excess'],
                    trigger_result['pe_excess'],
                )

            elif outcome in (OUTCOME_CE, OUTCOME_PE):
                self._hb_wt['outcome'] = 'ce_triggered' if outcome == OUTCOME_CE else 'pe_triggered'
                aggressor = 'ce' if outcome == OUTCOME_CE else 'pe'
                hedge = 'pe' if aggressor == 'ce' else 'ce'
                premium_now = ce_now if aggressor == 'ce' else pe_now
                hedge_premium = pe_now if aggressor == 'ce' else ce_now

                # Regime-based directional blocking (Section C.4 / D.4)
                # Check BEFORE wind-down/margin — regime controls gate sells
                regime_action = session.get('_regime_action', ACTION_NORMAL)
                blocked, block_reason = self._regime_engine.should_block_sell(session, hedge)
                if blocked and regime_action != ACTION_FORCE_REDUCE:
                    # Regime blocks this sell, but risk-reducing trades continue
                    log_activity('regime_block',
                                f'Regime blocked {hedge.upper()} sell: {block_reason}',
                                sid, 'warning',
                                {'hedge': hedge, 'aggressor': aggressor, 'reason': block_reason})
                    emit_safety(
                        sid, 'regime', 'alert',
                        f'Sell blocked: {block_reason}',
                        {'hedge': hedge, 'aggressor': aggressor},
                    )
                    # Still allow wind-down buybacks if wind-down is active
                    if is_wind_down_active(session) or session.get('_gamma_emergency_wind_down'):
                        await self._process_wind_down_buyback(aggressor, ce_now, pe_now)
                # Wind-down mode: reduce instead of adding positions
                elif is_wind_down_active(session):
                    session['_wind_down_mode'] = True
                    log_activity('wind_down',
                                f'🌙 Wind-Down Active: {aggressor.upper()} triggered — '
                                f'reducing positions instead of hedging',
                                sid, 'info',
                                {'aggressor': aggressor.upper(), 'premium': premium_now})

                    await self._process_wind_down_buyback(
                        aggressor, ce_now, pe_now,
                    )
                elif session.get('_margin_block_sells') or session.get('_margin_wind_down'):
                    # Margin Guardian: block new sells when YELLOW+, force buyback when ORANGE+
                    margin_tier = self._margin_guardian.last_tier
                    margin_util = self._margin_guardian.last_utilization
                    if session.get('_margin_wind_down'):
                        # ORANGE tier: force aggressive buyback instead of hedging
                        log_activity('margin_wind_down',
                                    f'🟠 MARGIN WIND-DOWN ({margin_util:.1f}%): '
                                    f'{aggressor.upper()} triggered — reducing positions '
                                    f'instead of adding (tier: {margin_tier})',
                                    sid, 'warning',
                                    {'margin_tier': margin_tier, 'utilization': margin_util})
                        await self._process_wind_down_buyback(
                            aggressor, ce_now, pe_now,
                        )
                    else:
                        # YELLOW tier: just block new sells
                        log_activity('margin_block_sells',
                                    f'🟡 MARGIN SELLS BLOCKED ({margin_util:.1f}%): '
                                    f'{aggressor.upper()} triggered but new sells blocked '
                                    f'(tier: {margin_tier})',
                                    sid, 'warning',
                                    {'margin_tier': margin_tier, 'utilization': margin_util})
                else:
                    session.pop('_wind_down_mode', None)

                    # Fix #11: If close-at-5 closed positions on the aggressor side
                    # during this same heartbeat, re-evaluate the trigger now that
                    # the position state has changed.  Close-at-5 may have removed
                    # positions whose realized loss already reduces the net exposure —
                    # re-evaluation prevents unnecessary over-hedging.
                    if aggressor in _close_at_5_sides:
                        log.info(
                            f"[{sid}] Fix #11: close-at-5 closed {aggressor.upper()} positions "
                            f"this heartbeat — re-evaluating trigger before adjustment"
                        )
                        re_trigger = evaluate_triggers(session, ce_now, pe_now)
                        if re_trigger['outcome'] not in (OUTCOME_CE, OUTCOME_PE, OUTCOME_BOTH):
                            log_activity('trigger_cleared_by_close_at_5',
                                        f'✅ Trigger re-evaluation: {aggressor.upper()} trigger '
                                        f'no longer active after close-at-5 — skipping adjustment',
                                        sid, 'info',
                                        {'aggressor': aggressor, 'original_outcome': outcome,
                                         're_outcome': re_trigger['outcome']})
                            # Trigger cleared — skip the adjustment
                        else:
                            log_activity('adjustment_triggered',
                                        f'🎯 Adjustment Triggered: {aggressor.upper()} side breached trigger '
                                        f'(${premium_now:.2f}), hedging with {hedge.upper()} (${hedge_premium:.2f})'
                                        f' [trigger confirmed after close-at-5 re-check]',
                                        sid, 'info',
                                        {
                                            'aggressor': aggressor.upper(),
                                            'aggressor_premium': premium_now,
                                            'hedge': hedge.upper(),
                                            'hedge_premium': hedge_premium,
                                            'close_at_5_ran_on_aggressor': True,
                                        })
                            await self._process_adjustment(
                                aggressor, hedge, premium_now, hedge_premium,
                                ce_now, pe_now,
                            )
                    else:
                        log_activity('adjustment_triggered',
                                    f'🎯 Adjustment Triggered: {aggressor.upper()} side breached trigger '
                                    f'(${premium_now:.2f}), hedging with {hedge.upper()} (${hedge_premium:.2f})',
                                    sid, 'info',
                                    {
                                        'aggressor': aggressor.upper(),
                                        'aggressor_premium': premium_now,
                                        'hedge': hedge.upper(),
                                        'hedge_premium': hedge_premium
                                    })

                        await self._process_adjustment(
                            aggressor, hedge, premium_now, hedge_premium,
                            ce_now, pe_now,
                        )

        # Step 7.5: Perp Delta Hedge (Fix #26)
        # Runs after adjustments, before P&L — uses cached portfolio_delta from Step 3.5
        # BTC mark price is also cached in _regime_spot_price (no extra API call needed)
        if is_perp_hedge_enabled(session):
            perp_btc_mark = session.get('_regime_spot_price', 0.0)
            perp_delta = session.get('portfolio_delta', 0.0)
            if perp_btc_mark > 0:
                # Fix #26.2: ATM-only mode — only hedge when ORIGINAL strike is near ATM
                # Uses the same original_strike concept as wind_down_on_atm / close_at_atm:
                # original_strike is set once at session creation and never changes on shifts.
                perp_mode = params.get('perp_hedge_mode', 'atm_only')
                atm_gate_passed = True  # default: always hedge in 'full' mode
                if perp_mode == 'atm_only':
                    atm_gate_passed = False
                    atm_threshold_pct = params.get('perp_hedge_atm_threshold_pct', 1.5)
                    # Check ORIGINAL entry strikes against spot (not active/shifted strikes)
                    ce_orig_strike = float(session.get('ce', {}).get('original_strike', 0) or 0)
                    pe_orig_strike = float(session.get('pe', {}).get('original_strike', 0) or 0)
                    ce_total_lots = session.get('ce', {}).get('total_lots', 0)
                    pe_total_lots = session.get('pe', {}).get('total_lots', 0)
                    atm_triggered_side = None

                    if ce_orig_strike > 0 and ce_total_lots > 0 and perp_btc_mark > 0:
                        dist_pct = abs(ce_orig_strike - perp_btc_mark) / perp_btc_mark * 100
                        if dist_pct <= atm_threshold_pct:
                            atm_gate_passed = True
                            atm_triggered_side = 'CE'
                            log.info(
                                f"[{sid}] Perp ATM gate: CE ORIGINAL strike "
                                f"{ce_orig_strike:.0f} is {dist_pct:.1f}% "
                                f"from spot {perp_btc_mark:.0f} (threshold {atm_threshold_pct}%)"
                            )

                    if not atm_gate_passed and pe_orig_strike > 0 and pe_total_lots > 0 and perp_btc_mark > 0:
                        dist_pct = abs(pe_orig_strike - perp_btc_mark) / perp_btc_mark * 100
                        if dist_pct <= atm_threshold_pct:
                            atm_gate_passed = True
                            atm_triggered_side = 'PE'
                            log.info(
                                f"[{sid}] Perp ATM gate: PE ORIGINAL strike "
                                f"{pe_orig_strike:.0f} is {dist_pct:.1f}% "
                                f"from spot {perp_btc_mark:.0f} (threshold {atm_threshold_pct}%)"
                            )

                    if not atm_gate_passed:
                        log.debug(
                            f"[{sid}] Perp ATM-only mode: original strikes "
                            f"CE={ce_orig_strike:.0f} PE={pe_orig_strike:.0f} not within "
                            f"{atm_threshold_pct}% of spot {perp_btc_mark:.0f} — skipping hedge"
                        )

                if atm_gate_passed:
                    # T4-3: Pass projected delta from the just-executed adjustment.
                    # The cached portfolio_delta is from Step 3.5 and doesn't yet
                    # reflect any adjustment that ran this heartbeat.
                    # If an adjustment ran, project its delta impact so the hedge
                    # accounts for combined (current + just-traded) exposure.
                    _proj_lots = 0
                    _proj_side = ''
                    if params.get('perp_hedge_project_adjustment', True):
                        _adj_info = self._hb_wt.get('adjustment', {})
                        if _adj_info and _adj_info.get('lots', 0) > 0:
                            _proj_lots = _adj_info['lots']
                            _proj_side = _adj_info.get('side', '')  # 'ce' or 'pe'

                    perp_result = await run_perp_hedge(
                        session, self.executor, perp_delta, perp_btc_mark,
                        projected_lots=_proj_lots,
                        projected_side=_proj_side,
                    )
                    if perp_result.get('action') not in ('none', 'skipped'):
                        log_activity(
                            'perp_hedge',
                            f"Perp hedge: {perp_result.get('action', '?').upper()} "
                            f"{perp_result.get('lots_traded', 0)} lots @ "
                            f"{perp_result.get('fill_price', 0):.2f} — "
                            f"{perp_result.get('reason', '')}",
                            sid, 'info',
                            {
                                'action': perp_result.get('action'),
                                'lots': perp_result.get('lots_traded', 0),
                                'fill_price': perp_result.get('fill_price', 0),
                                'realized_pnl': perp_result.get('realized_pnl', 0),
                            },
                        )
                else:
                    # Still update mark P&L for display even when ATM gate blocks
                    from .mmm_perp_hedge import update_perp_mark_pnl
                    update_perp_mark_pnl(session, perp_btc_mark)
            else:
                log.debug(f"[{sid}] Perp hedge skipped: BTC mark price not available")

        # Step 8: Update P&L
        pnl = self._engine.compute_total_pnl(
            session, self._make_fetch_fn()
        )
        session['unrealized_pnl'] = pnl['unrealized']
        update_peak_pnl(session, pnl['net_pnl'])

        # Track P&L for walkthrough
        self._hb_wt['pnl'] = pnl

        # P&L and delta are included in heartbeat summary (no separate activity)

        # Step 9: Portfolio Delta (already computed in Step 3.5 for regime checks)
        # Reuse cached value — no duplicate API call
        portfolio_delta = session.get('portfolio_delta', 0)

        # Update analytics tracking (zero impact on trading logic)
        self._update_analytics_exposure()
        self._update_analytics_pnl_milestones(pnl)
        self._update_analytics_delta(portfolio_delta)

        # P&L history for chart
        session.setdefault('pnl_history', []).append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_pnl': pnl['net_pnl'],
            'realized': pnl['realized'],
            'unrealized': pnl['unrealized'],
            'ce_premium': ce_now,
            'pe_premium': pe_now,
        })

        # Keep history manageable (last 500 points)
        if len(session['pnl_history']) > 500:
            session['pnl_history'] = session['pnl_history'][-500:]

        # Emit updates
        self._emit_heartbeat_data(ce_now, pe_now)
        emit_pnl_update(
            sid, pnl['net_pnl'], pnl['realized'],
            pnl['unrealized'], pnl['fees'], pnl['total_premium_collected'],
        )

        # §13.3 POST-UPDATE MAX LOSS CHECK: Immediate enforcement
        # Safety checks in Step 3 use previous heartbeat's P&L.
        # This check catches max_loss breach on the SAME heartbeat.
        max_loss_amount = session.get('params', {}).get('max_loss_amount', 5000.0)
        current_total_pnl = pnl['net_pnl']
        if max_loss_amount > 0 and current_total_pnl <= -max_loss_amount:
            log.critical(
                f"[{sid}] MAX LOSS BREACHED (post-update): "
                f"P&L ${current_total_pnl:.2f} <= -${max_loss_amount:.2f}. "
                f"CLOSING ALL POSITIONS IMMEDIATELY."
            )
            log_activity('max_loss_breach',
                        f'🚨 MAX LOSS BREACHED: P&L ${current_total_pnl:.2f} exceeds '
                        f'-${max_loss_amount:.2f} limit. CLOSING ALL POSITIONS.',
                        sid, 'error',
                        {'total_pnl': current_total_pnl, 'max_loss': max_loss_amount})
            emit_safety(
                sid, 'max_loss', 'critical',
                f'MAX LOSS BREACHED: P&L ${current_total_pnl:.2f} exceeds '
                f'-${max_loss_amount:.2f}. CLOSING ALL.',
                {'total_pnl': current_total_pnl, 'max_loss': max_loss_amount}
            )
            # Telegram alert for max loss breach
            try:
                await alert_max_loss_breach(sid, current_total_pnl, max_loss_amount)
            except Exception:
                pass
            await self._auto_close_all(
                f'Max loss breached: P&L ${current_total_pnl:.2f} <= -${max_loss_amount:.2f}',
                emergency=True,
            )
            # C-3 fix: run cleanup before returning
            try:
                update_peak_pnl(session, current_total_pnl)
                self._emit_heartbeat_data(ce_now, pe_now)
                self._save_my_session(session)
                latency_ms = (time.monotonic() - beat_start_mono) * 1000
                self._health.record_beat('ok', latency_ms=latency_ms)
            except Exception as _cleanup_err:
                log.error(f"[{sid}] Cleanup after max loss breach failed: {_cleanup_err}")
            return

        # Periodic reconciliation (§14.5)
        adj_count = session.get('adjustment_count', 0)
        if adj_count > 0 and adj_count % 5 == 0:
            self._engine.reconcile_pnl(
                session, self._make_fetch_fn()
            )

        # Step 9: Generate walkthrough entry and store in session
        try:
            from .mmm_walkthrough import generate_heartbeat_walkthrough
            wt_entry = generate_heartbeat_walkthrough(
                session,
                heartbeat_num=session.get('_heartbeat_counter', 0),
                ce_now=ce_now,
                pe_now=pe_now,
                outcome=self._hb_wt.get('outcome', 'none'),
                adjustment_info=self._hb_wt.get('adjustment'),
                reversal_info=self._hb_wt.get('reversal'),
                shift_info=self._hb_wt.get('shift'),
                close_at_5_info=self._hb_wt.get('close_at_5'),
                safety_events=self._hb_wt.get('safety_events'),
                pnl_info=self._hb_wt.get('pnl'),
            )
            session.setdefault('_walkthrough_log', []).append(wt_entry)
            # Keep walkthrough manageable (last 200 entries)
            if len(session['_walkthrough_log']) > 200:
                session['_walkthrough_log'] = session['_walkthrough_log'][-200:]

            # Emit walkthrough via WebSocket
            from .mmm_websocket import _emit
            _emit('mmm_walkthrough', {
                'session_id': sid,
                'entry': wt_entry,
            })
        except Exception as e:
            log.warning(f'Walkthrough generation failed: {e}')

        # Save state
        self._save_my_session(session)
        
        # Periodically persist analytics (every 10 heartbeats or ~5min for 30s intervals)
        heartbeat_counter = session.get('_heartbeat_counter', 0)
        if heartbeat_counter % 10 == 0:
            try:
                analytics_storage = get_analytics_storage()
                analytics_storage.save_session_analytics(session)
            except Exception as e:
                log.error(f"Failed to persist analytics: {e}")

        # Reset error count AFTER successful heartbeat completion
        session['error_count'] = 0
        # Circuit breaker: record success to heal open/half-open state
        self._circuit.record_success()

        # Record beat telemetry
        beat_latency_ms = (time.monotonic() - beat_start_mono) * 1000
        self._health.record_beat(
            'ok',
            latency_ms=beat_latency_ms,
            ce_premium=ce_now,
            pe_premium=pe_now,
        )
        # Persist health summary into session for API/UI access
        session['_beat_health'] = self._health.summary()
        session['_circuit_state'] = self._circuit.summary()

        # Emit structured heartbeat summary for frontend live monitor
        effective_iv = getattr(self, '_effective_interval', session.get('params', {}).get('adjustment_interval', 300))
        trigger_data = session.get('_last_trigger_result', {})
        try:
            from .mmm_websocket import emit_heartbeat_summary
            emit_heartbeat_summary(sid, {
                'heartbeat_num': session.get('_heartbeat_counter', 0),
                'latency_ms': round(beat_latency_ms, 1),
                'health_grade': self._health.grade(),
                'status': session.get('strategy_status', 'UNKNOWN'),
                'ce_strike': session.get('ce', {}).get('active_strike', 0),
                'ce_premium': ce_now,
                'ce_trigger_pct': trigger_data.get('ce_excess_pct', 0),
                'pe_strike': session.get('pe', {}).get('active_strike', 0),
                'pe_premium': pe_now,
                'pe_trigger_pct': trigger_data.get('pe_excess_pct', 0),
                'min_trigger_pct': trigger_data.get('min_trigger_move', session.get('params', {}).get('min_trigger_move_pct', 3)),
                'trigger_outcome': trigger_data.get('outcome', 'none'),
                'net_pnl': round(pnl['net_pnl'], 2) if pnl else 0,
                'realized_pnl': round(pnl['realized'], 2) if pnl else 0,
                'unrealized_pnl': round(pnl['unrealized'], 2) if pnl else 0,
                'fees': round(pnl.get('fees', 0), 2) if pnl else 0,
                'portfolio_delta': round(session.get('portfolio_delta', 0), 4),
                'next_interval': effective_iv,
                'next_heartbeat': session.get('next_heartbeat', ''),
                'wind_down_active': is_wind_down_active(session),
                'regime_action': session.get('_regime_action', 'NORMAL'),
                'margin_tier': getattr(self._margin_guardian, 'last_tier', 'GREEN') if hasattr(self, '_margin_guardian') else 'GREEN',
                'margin_util': getattr(self._margin_guardian, 'last_utilization', 0) if hasattr(self, '_margin_guardian') else 0,
                'adaptive_tier': session.get('_adaptive_tier', ''),
                'circuit_state': self._circuit.state.value if hasattr(self._circuit, 'state') else 'CLOSED',
                'ce_total_lots': session.get('ce', {}).get('total_lots', 0),
                'pe_total_lots': session.get('pe', {}).get('total_lots', 0),
                'ce_active_lots': session.get('ce', {}).get('active_lots', 0),
                'pe_active_lots': session.get('pe', {}).get('active_lots', 0),
                'ce_frozen_lots': session.get('ce', {}).get('frozen_total_lots', 0),
                'pe_frozen_lots': session.get('pe', {}).get('frozen_total_lots', 0),
                'adjustment_count': session.get('adjustment_count', 0),
                'safety_event_count': len(safety_events),
            })
        except Exception as e:
            log.warning(f"[{sid}] Heartbeat summary emit failed: {e}")

    # =========================================================================
    # §5: Process Adjustment
    # =========================================================================

    # =========================================================================
    # Wind-Down: Buy back aggressor instead of selling hedge
    # =========================================================================

    async def _process_proactive_wind_down(
        self,
        ce_now: float,
        pe_now: float,
    ):
        """
        Proactive wind-down: every heartbeat while wind-down is active,
        attempt to reduce BOTH sides (not just triggered side).

        This is separate from the trigger-based path so positions are
        reduced even when no trigger fires (e.g. premiums falling quietly).
        Uses LIFO order + wind_down_buyback_pct per call.
        """
        session = self.session
        sid = self.session_id

        reduced_any = False
        for side in ['ce', 'pe']:
            # Check stop before processing each side — each side may take minutes
            if self._should_stop():
                log.info(f"[{sid}] Proactive wind-down: stop requested, aborting")
                break

            side_state = session.get(side, {})
            active_lots = side_state.get('active_lots', 0)
            params = session.get('params', {})
            min_keep = params.get('wind_down_min_lots_to_keep', 0)

            if active_lots <= min_keep:
                log.debug(f"[{sid}] Proactive wind-down: {side.upper()} at floor "
                          f"({active_lots} lots, min_keep={min_keep}) — skipping")
                continue

            wd_action = compute_wind_down_action(session, side, ce_now, pe_now)
            if wd_action['action'] != 'buyback' or wd_action['lots_to_close'] <= 0:
                log.debug(f"[{sid}] Proactive wind-down: {side.upper()} skipped — "
                          f"action={wd_action['action']}")
                continue

            log_activity('wind_down',
                         f'🌙 Proactive Wind-Down: reducing {side.upper()} by '
                         f'{wd_action["lots_to_close"]} lots',
                         sid, 'info',
                         {'side': side.upper(), 'lots': wd_action['lots_to_close'],
                          'active_lots': active_lots})
            await self._process_wind_down_buyback(side, ce_now, pe_now)
            reduced_any = True

        if not reduced_any:
            params = session.get('params', {})
            log.debug(f"[{sid}] Proactive wind-down: no sides eligible for reduction this heartbeat")

    async def _process_wind_down_buyback(
        self,
        aggressor: str,
        ce_now: float,
        pe_now: float,
    ):
        """
        Wind-down mode: buy back a portion of the aggressor side's lots
        instead of selling more on the hedge side.

        Uses LIFO order: closes newest adjustment fills first (highest cost/risk),
        then original lots as last resort.
        """
        session = self.session
        sid = self.session_id


        wd_action = compute_wind_down_action(session, aggressor, ce_now, pe_now)

        if wd_action['action'] == 'skip':
            log_activity('wind_down',
                        f'🌙 Wind-Down: {wd_action["reason"]} — skipping (let theta work)',
                        sid, 'info', {'action': 'skip', 'side': aggressor.upper()})
            return

        if wd_action['action'] == 'pause':
            log_activity('wind_down',
                        f'🌙 Wind-Down: {wd_action["reason"]} — pausing for user decision',
                        sid, 'warning', {'action': 'pause', 'side': aggressor.upper()})
            self.pause(f'Wind-down floor reached: {wd_action["reason"]}')
            return

        if wd_action['action'] == 'normal':
            # Fall back to normal adjustment
            hedge = 'pe' if aggressor == 'ce' else 'ce'
            premium_now = ce_now if aggressor == 'ce' else pe_now
            hedge_premium = pe_now if aggressor == 'ce' else ce_now
            log_activity('wind_down',
                        f'🌙 Wind-Down: {wd_action["reason"]} — falling back to normal adjustment',
                        sid, 'info', {'action': 'normal', 'side': aggressor.upper()})
            await self._process_adjustment(
                aggressor, hedge, premium_now, hedge_premium, ce_now, pe_now,
            )
            return

        # action == 'buyback'
        lots_to_close = wd_action['lots_to_close']
        side_state = session.get(aggressor, {})
        option_type = 'call' if aggressor == 'ce' else 'put'
        active_strike = side_state.get('active_strike', 0)
        expiry = session.get('params', {}).get('expiry', '')

        # Get LIFO fill records
        close_records = get_lifo_close_fills(side_state, lots_to_close)
        if not close_records:
            log_activity('wind_down',
                        f'🌙 Wind-Down: No fills to close on {aggressor.upper()}',
                        sid, 'warning')
            return

        actual_lots = sum(r['lots'] for r in close_records)

        # -----------------------------------------------------------------
        # CRITICAL FIX: Group records by their ACTUAL strike and place a
        # separate buy order per strike.
        # LIFO fills span multiple strikes when the algo has shifted.
        # Placing one order at active_strike would buy the WRONG contract
        # for fills that belong to a shifted (old) strike.
        # -----------------------------------------------------------------
        from collections import defaultdict
        # Map: strike → {'lots': int, 'records': list, 'weighted_premium_sum': float}
        by_strike: Dict[float, Dict] = defaultdict(lambda: {'lots': 0, 'records': [], 'wp_sum': 0.0})
        for rec in close_records:
            # resolve the actual strike for this fill
            rec_strike = rec.get('strike') or active_strike
            if rec_strike == 0:
                rec_strike = active_strike
            by_strike[rec_strike]['lots'] += rec['lots']
            by_strike[rec_strike]['records'].append(rec)
            by_strike[rec_strike]['wp_sum'] += rec.get('premium', 0) * rec['lots']

        total_realized = 0.0
        any_failed = False

        for strike_val, group in by_strike.items():
            # Check if monitor was stopped while we were executing buybacks
            if self._should_stop():
                log.info(f"[{sid}] Wind-down buyback: stop requested, aborting remaining strikes")
                break

            group_lots = group['lots']
            group_records = group['records']
            group_wp_sum = group['wp_sum']
            group_avg_entry = group_wp_sum / group_lots if group_lots > 0 else 0

            symbol = self.initializer.build_symbol(
                option_type, 'BTC', strike_val, expiry,
            )

            log.info(
                f"[{sid}] Wind-down buyback: BUY {group_lots} {aggressor.upper()} "
                f"@ {strike_val} ({symbol})"
            )

            log_activity('wind_down',
                        f'🌙 Wind-Down: Placing BUY {group_lots} {aggressor.upper()} @ {strike_val}',
                        sid, 'info',
                        {'side': aggressor.upper(), 'strike': strike_val, 'lots': group_lots})

            try:
                _reprice_max = self.session.get('params', {}).get('max_reprice_attempts', None)
                result = await self.executor.smart_execute(
                    symbol=symbol,
                    side='buy',
                    size=group_lots,
                    reduce_only=True,
                    max_reprice_attempts=_reprice_max,
                )

                if not result.get('success'):
                    log_activity('wind_down',
                                f'🌙 Wind-Down FAILED: Could not buy back {group_lots} '
                                f'{aggressor.upper()} @ {strike_val} — {result.get("error", "unknown")}',
                                sid, 'error',
                                {'error': result.get('error'), 'lots': group_lots, 'strike': strike_val})
                    any_failed = True
                    continue

                close_price = result.get('fill_price', 0)

                # Apply LIFO removals for this strike's records only
                avg_entry = apply_lifo_removals(side_state, group_records)
                session[aggressor] = side_state

                # Realized P&L for this strike group
                group_realized = (avg_entry - close_price) * group_lots * LOT_SIZE_BTC
                total_realized += group_realized
                session['realized_pnl'] = session.get('realized_pnl', 0) + group_realized

                log_activity('wind_down',
                            f'🌙 Wind-Down leg: Bought back {group_lots} {aggressor.upper()} '
                            f'@ {strike_val} fill ${close_price:.2f} '
                            f'(avg entry ${avg_entry:.2f}, P&L ${group_realized:.2f})',
                            sid, 'success',
                            {'side': aggressor.upper(), 'strike': strike_val,
                             'lots': group_lots, 'close_price': close_price,
                             'avg_entry': round(avg_entry, 2),
                             'realized_pnl': round(group_realized, 2)})

            except Exception as e:
                log.exception(f"[{sid}] Wind-down buyback @ {strike_val} failed: {e}")
                log_activity('wind_down',
                            f'🌙 Wind-Down ERROR @ {strike_val}: {str(e)}',
                            sid, 'error', {'error': str(e), 'strike': strike_val})
                any_failed = True

        if not any_failed:
            # Update triggers only on full success
            update_trigger_snapshots(
                session, ce_now, pe_now,
                fetch_premium_fn=self._make_fetch_fn(),
            )

        # Record in wind-down history
        remaining = session.get(aggressor, {}).get('active_lots', 0)
        session.setdefault('_wind_down_history', []).append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'side': aggressor.upper(),
            'lots_closed': actual_lots,
            'total_realized_pnl': round(total_realized, 2),
            'remaining_active_lots': remaining,
            'remaining_total_lots': session.get(aggressor, {}).get('total_lots', 0),
            'strikes_closed': list(by_strike.keys()),
            'any_failed': any_failed,
        })
        if len(session['_wind_down_history']) > 200:
            session['_wind_down_history'] = session['_wind_down_history'][-200:]

        remaining = session.get(aggressor, {}).get('active_lots', 0)
        session['updated_at'] = datetime.now(timezone.utc).isoformat()
        log_activity('wind_down',
                    f'🌙 Wind-Down Complete: {aggressor.upper()} '
                    f'closed {actual_lots} lots across {len(by_strike)} strike(s), '
                    f'P&L ${total_realized:.2f}. Remaining: {remaining} lots.',
                    sid, 'success' if not any_failed else 'warning',
                    {
                        'side': aggressor.upper(),
                        'lots_closed': actual_lots,
                        'total_realized_pnl': round(total_realized, 2),
                        'remaining_lots': remaining,
                        'strikes': list(by_strike.keys()),
                        'any_failed': any_failed,
                    })

    # =========================================================================
    # Pending Order Fill Recorder
    # =========================================================================

    def _record_fill_from_pending(
        self,
        session: Dict,
        side: str,
        strike: float,
        lots: int,
        fill_price: float,
        adj_type: str = 'standard',
    ) -> None:
        """
        Record a confirmed fill for a pending order into session state.

        Called by the pending order guard when it discovers a previously
        un-recorded fill on the exchange.  Mirrors the state update that
        would have been done by _update_state_after_adjustment() had
        smart_execute returned success.

        Note: Does NOT update trigger_snapshots (no live premiums available
        here).  The normal heartbeat will refresh snapshots on next cycle.
        """
        from .mmm_state import recompute_side_lots

        side_state = session.setdefault(side, {})
        aggressor_side = 'pe' if side == 'ce' else 'ce'

        # Fix #23: Record fill in positions[] (Unified Ledger)
        now = datetime.now(timezone.utc).isoformat()
        counter = side_state.get('_pos_counter', 0) + 1
        side_state['_pos_counter'] = counter
        side_state.setdefault('positions', []).append({
            'id': f"{side}_adj_{counter:03d}",
            'strike': strike,
            'lots': lots,
            'entry_premium': fill_price,
            'premium': fill_price,
            'type': adj_type or 'adjustment',
            'status': 'active',
            'created_at': now,
            'shifted_at': None,
            'closed_at': None,
            'realized_pnl': None,
            'timestamp': now,
            'source': 'pending_order_recovery',
        })
        recompute_side_lots(side_state)
        session[side] = side_state

        # Update tracking
        session['last_aggressor'] = aggressor_side.upper()
        session['adjustment_count'] = session.get('adjustment_count', 0) + 1
        premium_collected = fill_price * lots * LOT_SIZE_BTC
        session['total_premium_collected'] = (
            session.get('total_premium_collected', 0) + premium_collected
        )

        session.setdefault('adjustment_history', []).append({
            'side': side.upper(),
            'aggressor': aggressor_side.upper(),
            'lots_sold': lots,
            'premium': fill_price,
            'strike': strike,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'type': adj_type,
            'premium_collected': premium_collected,
            'adjustment_number': session['adjustment_count'],
            'source': 'pending_order_recovery',
        })
        if len(session['adjustment_history']) > 200:
            session['adjustment_history'] = session['adjustment_history'][-200:]

        session['updated_at'] = datetime.now(timezone.utc).isoformat()

        log.info(
            f"[{self.session_id}] Pending fill recorded: "
            f"{side.upper()} {lots} lots @ {strike} fill_price={fill_price:.2f} "
            f"(adj #{session['adjustment_count']})"
        )
        log_activity('pending_fill_recorded',
                     f'📋 Pending fill recovered: SELL {lots} lots {side.upper()} @ {strike} '
                     f'for ${fill_price:.2f} (recorded from exchange verification)',
                     self.session_id, 'info',
                     {'side': side.upper(), 'strike': strike, 'lots': lots,
                      'fill_price': fill_price, 'adj_type': adj_type})

        # Save to storage immediately
        self._save_my_session(session)

    # =========================================================================
    # §5: Process Adjustment (Standard / Reversal)
    # =========================================================================

    async def _process_adjustment(
        self,
        aggressor: str,
        hedge: str,
        premium_now: float,
        hedge_premium: float,
        ce_now: float,
        pe_now: float,
    ):
        """
        Process a triggered adjustment.

        Handles standard, reversal, and first-reversal cases.
        Also checks for strike shift before executing.
        """
        session = self.session
        sid = self.session_id

        # ── PENDING ORDER GUARD ───────────────────────────────────────────────
        # Before firing ANY new order, verify whether a pending adjustment order
        # from a previous heartbeat is still open on the exchange.  If it is,
        # skip this heartbeat to avoid position accumulation.  If it was filled
        # but not recorded (e.g. executor timed out), record the fill now so
        # calculations stay accurate.
        try:
            rest_for_guard = self._create_heartbeat_rest_client()
            guard_result = await check_and_resolve_pending(
                session_id=sid,
                side=hedge,
                session=session,
                rest_client=rest_for_guard,
                record_fill_fn=self._record_fill_from_pending,
            )

            if guard_result == 'filled':
                log_activity('pending_order_resolved',
                         f'✅ Pending {hedge.upper()} order confirmed FILLED (recorded from exchange). '
                         f'Skipping duplicate order this heartbeat.',
                         sid, 'success',
                         {'side': hedge, 'guard_result': guard_result})
                log.info(
                    f"[{sid}] Pending {hedge.upper()} order was filled — "
                    f"fill recorded, skipping new order"
                )
                return

            elif guard_result in ('open', 'error'):
                log_activity('pending_order_active',
                         f'⏳ Pending {hedge.upper()} order still OPEN on exchange — '
                         f'skipping duplicate order (guard_result={guard_result})',
                         sid, 'warning',
                         {'side': hedge, 'guard_result': guard_result})
                log.warning(
                    f"[{sid}] Pending {hedge.upper()} order still open/unverifiable — "
                    f"skipping this heartbeat to prevent accumulation"
                )
                return

            # 'none', 'dead', 'stale' → proceed normally

        except Exception as _guard_err:
            log.warning(
                f"[{sid}] Pending order guard failed: {_guard_err} — proceeding with caution"
            )
        # ── END PENDING ORDER GUARD ───────────────────────────────────────────

        # §9: Check for reversal
        is_reversal = detect_reversal(session, aggressor)

        if is_reversal:
            record_reversal(session, session.get('last_aggressor', 'NONE'), aggressor)

            # Robust v2 Fix #7: Reset peak P&L on reversal — new profit phase begins
            current_total = session.get('realized_pnl', 0) + session.get('unrealized_pnl', 0)
            reset_peak_pnl_on_reversal(session, current_total)
            
            # Analytics: Track reversal event (no trading logic impact)
            analytics = session.setdefault('analytics', {})
            analytics.setdefault('reversal_timestamps', []).append(datetime.now(timezone.utc).isoformat())
            if len(analytics['reversal_timestamps']) > 200:
                analytics['reversal_timestamps'] = analytics['reversal_timestamps'][-200:]

            # First reversal: use adjustment P&L formula
            loss, adj_pnl, _rev_incomplete = self._engine.calculate_reversal_loss(
                session, aggressor, self._make_fetch_fn()
            )

            # Robust v2 Fix #2: Warn if reversal calculation was incomplete
            if _rev_incomplete:
                log.warning(
                    f"[{sid}] Reversal loss calculation INCOMPLETE — "
                    f"some premium fetches failed. P&L may be inaccurate."
                )
                emit_safety(
                    sid, 'calculation_incomplete', 'warning',
                    'Reversal loss calculation incomplete: some premium fetches failed. '
                    'Hedge quantity may be understated.',
                    {'type': 'reversal', 'side': aggressor}
                )

            # §9: If adjustments still profitable, skip
            skip, skip_reason = should_skip_reversal_adjustment(session, adj_pnl)
            if skip:
                log.info(f"[{sid}] {skip_reason}")
                emit_reversal(
                    sid, session.get('last_aggressor', ''),
                    aggressor.upper(), adj_pnl, 'skip_profitable',
                )

                # Track reversal skip for walkthrough
                self._hb_wt['reversal'] = {
                    'detected': True, 'skipped': True,
                    'prev_aggressor': session.get('last_aggressor', ''),
                    'new_aggressor': aggressor,
                    'adj_pnl': adj_pnl,
                    'reason': skip_reason,
                }
                self._hb_wt['outcome'] = 'reversal_skip'

                # Do NOT update last_aggressor when skipping — the original
                # aggressor direction is still the dominant one until an
                # actual adjustment is executed

                # Bug #2 fix: Transition triggers/last_aggressor so NEXT
                # interval uses standard formula instead of re-detecting
                # the same reversal (infinite loop prevention).
                handle_reversal_skip_transition(
                    session, aggressor, ce_now, pe_now,
                    fetch_premium_fn=self._make_fetch_fn(),
                )

                # Activate cooldown if configured
                params = session.get('params', {})
                if params.get('cooldown_on_reversal', True):
                    activate_cooldown(session)
                    emit_reversal(
                        sid, '', aggressor.upper(), adj_pnl, 'cooldown',
                    )

                return

            adj_type = 'first_reversal'
            emit_reversal(
                sid, session.get('last_aggressor', ''),
                aggressor.upper(), adj_pnl, 'hedge',
            )

            # Track reversal execution for walkthrough
            self._hb_wt['reversal'] = {
                'detected': True, 'skipped': False,
                'prev_aggressor': session.get('last_aggressor', ''),
                'new_aggressor': aggressor,
                'adj_pnl': adj_pnl,
                'loss_to_cover': loss,
            }

            # Cooldown after reversal
            params = session.get('params', {})
            if params.get('cooldown_on_reversal', True):
                activate_cooldown(session)
        else:
            # Standard or continuation — include frozen position losses
            loss, _std_incomplete = self._engine.calculate_standard_loss(
                session, aggressor, premium_now,
                fetch_premium_fn=self._make_fetch_fn(),
            )
            adj_type = 'standard'

            # Robust v2 Fix #2: Warn if standard loss calculation was incomplete
            if _std_incomplete:
                log.warning(
                    f"[{sid}] Standard loss calculation INCOMPLETE — "
                    f"some premium fetches failed. Hedge may be understated."
                )
                emit_safety(
                    sid, 'calculation_incomplete', 'warning',
                    'Standard loss calculation incomplete: some premium fetches failed. '
                    'Hedge quantity may be understated.',
                    {'type': 'standard', 'side': aggressor}
                )

        if loss <= 0:
            # BUG-2 FIX: Log when trigger fires but loss is zero/negative
            log_activity('adjustment_skipped',
                        f'⏭️ Adjustment skipped: {aggressor.upper()} triggered but '
                        f'calculated loss ≤ 0 (${loss:.2f}) — no hedge needed',
                        sid, 'info',
                        {
                            'reason': 'loss_zero_or_negative',
                            'aggressor': aggressor.upper(),
                            'hedge': hedge.upper(),
                            'loss': loss,
                            'adj_type': adj_type,
                        })
            return

        # §10: Check if strike shift needed on hedge side
        if check_shift_needed(session, hedge, hedge_premium):
            self._hb_wt['shift'] = {
                'side': hedge,
                'reason': 'hedge_premium_too_low',
                'hedge_premium': hedge_premium,
                'loss': loss,
            }
            await self._process_strike_shift(
                hedge, loss, ce_now, pe_now,
            )
            return

        # §5.4: Calculate lots to sell
        # ITM Guard: NEVER sell ITM options for adjustment (unless disabled by user).
        # CE is ITM when strike <= spot. PE is ITM when strike >= spot.
        itm_guard_on = session.get('params', {}).get('itm_guard_enabled', True)
        hedge_strike = session.get(hedge, {}).get('active_strike', 0)
        if hedge_strike:
            spot_price = await self._fetch_spot_price()
            if spot_price > 0:
                is_itm = False
                if hedge == 'ce' and hedge_strike <= spot_price:
                    is_itm = True
                elif hedge == 'pe' and hedge_strike >= spot_price:
                    is_itm = True

                if is_itm:
                    if itm_guard_on:
                        log.warning(
                            f"[{sid}] ITM GUARD: {hedge.upper()} strike {hedge_strike} is ITM "
                            f"(spot=${spot_price:.0f}). Refusing to sell ITM for adjustment."
                        )
                        log_activity('itm_guard_blocked',
                                    f'🚫 ITM GUARD: {hedge.upper()} @ {hedge_strike} is ITM '
                                    f'(spot ${spot_price:.0f}). Auto-shifting to OTM strike.',
                                    sid, 'error',
                                    {'hedge': hedge.upper(), 'strike': hedge_strike, 'spot': spot_price})
                        emit_safety(
                            sid, 'itm_guard', 'critical',
                            f'ITM GUARD: Cannot sell {hedge.upper()} @ {hedge_strike} — '
                            f'strike is ITM (spot ${spot_price:.0f}). Triggering auto-shift.',
                            {'hedge': hedge.upper(), 'strike': hedge_strike, 'spot': spot_price}
                        )
                        # Auto-trigger strike shift instead of deadlocking.
                        # The normal shift check (above) only fires when premium
                        # drops below shift_threshold.  ITM strikes need to shift
                        # regardless of premium level — sitting on an ITM strike
                        # and refusing to sell is a deadlock.
                        log.info(
                            f"[{sid}] ITM GUARD → AUTO-SHIFT: forcing strike shift "
                            f"for {hedge.upper()} (ITM @ {hedge_strike}, spot=${spot_price:.0f})"
                        )
                        self._hb_wt['shift'] = {
                            'side': hedge,
                            'reason': 'itm_guard_auto_shift',
                            'hedge_premium': hedge_premium,
                            'loss': loss,
                            'spot': spot_price,
                        }
                        await self._process_strike_shift(
                            hedge, loss, ce_now, pe_now,
                        )
                        return
                    else:
                        # ITM guard disabled — user explicitly allows ITM selling
                        log.warning(
                            f"[{sid}] ITM GUARD OFF: {hedge.upper()} strike {hedge_strike} is ITM "
                            f"(spot=${spot_price:.0f}). Proceeding with adjustment (user disabled guard)."
                        )
                        log_activity('itm_guard_bypassed',
                                    f'⚠️ ITM GUARD OFF: {hedge.upper()} @ {hedge_strike} is ITM '
                                    f'(spot ${spot_price:.0f}). Proceeding — guard disabled by user.',
                                    sid, 'warning',
                                    {'hedge': hedge.upper(), 'strike': hedge_strike, 'spot': spot_price})

        lots, constraint_msg, is_position_cap = self._engine.calculate_lots_to_sell(
            session, hedge, loss, hedge_premium,
        )

        if lots <= 0:
            # BUG-2 FIX: Always log when trigger fires but lots=0
            skip_reason = constraint_msg or 'lot_calculation_zero'
            # Fix F1.6: Use returned is_position_cap flag instead of string matching
            # is_position_cap = bool(constraint_msg and 'Position cap reached' in constraint_msg)  # OLD

            # §4: M2 Lot Recycling — attempt before giving up
            # Only fires for position cap (not other lot=0 reasons), and only
            # when regime and margin allow sells.
            if is_position_cap:
                recycled = await self._process_lot_recycling(
                    aggressor, hedge, loss, hedge_premium, ce_now, pe_now,
                )
                if recycled:
                    return  # Recycling handled the adjustment

            log_activity('adjustment_skipped',
                        f'⏭️ Adjustment skipped: {hedge.upper()} lots=0 — {skip_reason}',
                        sid, 'warning',
                        {
                            'reason': 'position_cap' if is_position_cap else 'lot_calculation_zero',
                            'aggressor': aggressor.upper(),
                            'hedge': hedge.upper(),
                            'loss': loss,
                            'hedge_premium': hedge_premium,
                            'constraint_msg': constraint_msg,
                        })
            if is_position_cap:
                emit_safety(
                    sid, 'position_cap', 'alert', constraint_msg,
                )
            return

        # §5.5: Execute the adjustment
        hedge_strike = session.get(hedge, {}).get('active_strike', 0)
        result = await self._engine.execute_adjustment(
            session, hedge, hedge_strike, lots,
            ce_now, pe_now, adj_type,
            fetch_premium_fn=self._make_fetch_fn(),
        )

        if result.get('success'):
            fill_price = result['fill_price']

            # Analytics: Track adjustment event (no trading logic impact)
            analytics = session.setdefault('analytics', {})
            analytics.setdefault('adjustment_events_by_side', {}).setdefault(hedge, 0)
            analytics['adjustment_events_by_side'][hedge] += 1
            analytics.setdefault('adjustment_events_by_type', {}).setdefault(adj_type, 0)
            analytics['adjustment_events_by_type'][adj_type] += 1
            # Track cumulative traded volume
            analytics['total_{}_lots_traded'.format(hedge)] = analytics.get('total_{}_lots_traded'.format(hedge), 0) + lots
            analytics['total_combined_lots_traded'] = analytics.get('total_combined_lots_traded', 0) + lots

            # Track adjustment for walkthrough
            self._hb_wt['adjustment'] = {
                'side': hedge,
                'strike': hedge_strike,
                'lots': lots,
                'fill_price': fill_price,
                'loss': loss,
                'adj_type': adj_type,
                'constraint_msg': constraint_msg,
                'hedge_premium': hedge_premium,
                'adjustment_number': session.get('adjustment_count', 0),
            }

            log_activity('adjustment_complete',
                        f'✓ Adjustment Complete: SELL {lots} lots {hedge.upper()} @ {hedge_strike} '
                        f'for ${fill_price:.2f} (Type: {adj_type})',
                        sid, 'success',
                        {
                            'side': hedge.upper(),
                            'strike': hedge_strike,
                            'lots': lots,
                            'fill_price': fill_price,
                            'type': adj_type,
                            'adjustment_number': session.get('adjustment_count', 0)
                        })
            emit_adjustment(
                sid, hedge.upper(), lots,
                result['fill_price'], hedge_strike,
                loss, adj_type,
                session.get('adjustment_count', 0),
            )
        else:
            # BUG-2 FIX: Log when adjustment execution fails
            error_msg = result.get('error', 'unknown') if result else 'no result'
            log.error(
                f"[{sid}] Adjustment execution FAILED: "
                f"SELL {lots} {hedge.upper()} @ {hedge_strike}: {error_msg}"
            )
            log_activity('adjustment_skipped',
                        f'❌ Adjustment Failed: SELL {lots} {hedge.upper()} @ {hedge_strike} '
                        f'— execution error: {error_msg}',
                        sid, 'error',
                        {
                            'reason': 'execution_error',
                            'aggressor': aggressor.upper(),
                            'hedge': hedge.upper(),
                            'strike': hedge_strike,
                            'lots': lots,
                            'adj_type': adj_type,
                            'error': error_msg,
                        })

    # =========================================================================
    # §10: Strike Shift
    # =========================================================================

    async def _process_strike_shift(
        self,
        side: str,
        loss: float,
        ce_now: float,
        pe_now: float,
    ):
        """Handle a strike shift for the given side."""
        session = self.session
        sid = self.session_id

        old_strike = session.get(side, {}).get('active_strike', 0)
        hedge_premium = ce_now if side == 'ce' else pe_now

        # Find new strike FIRST — do NOT freeze positions until we confirm
        # a viable new strike exists. If we freeze first and find_new_strike
        # fails, positions get stuck at active_lots=0 with no active strike.
        spot_price = await self._fetch_spot_price()
        new_strike_info = find_new_strike(
            self.initializer, session, side, spot_price,
        )

        if not new_strike_info:
            shift_threshold = session.get('params', {}).get('shift_threshold', 50.0)
            log.warning(
                f"[{sid}] SHIFT FAILED: No OTM {side.upper()} strike with "
                f"premium >= ${shift_threshold:.0f} found. "
                f"Falling back to current strike {old_strike} "
                f"(premium ${hedge_premium:.2f})."
            )
            log_activity('shift_fallback',
                        f'⚠️ Strike Shift Failed: No {side.upper()} strike with premium '
                        f'>= ${shift_threshold:.0f} found. Selling at current strike '
                        f'{old_strike} (${hedge_premium:.2f}) instead.',
                        sid, 'warning',
                        {
                            'side': side.upper(),
                            'current_strike': old_strike,
                            'current_premium': hedge_premium,
                            'shift_threshold': shift_threshold,
                            'reason': 'no_suitable_strike',
                        })
            emit_safety(
                sid, 'no_strike', 'alert',
                f"No suitable strike found for {side.upper()} shift "
                f"(need premium >= ${shift_threshold:.0f}). "
                f"Falling back to selling at current strike {old_strike} "
                f"(${hedge_premium:.2f}).",
            )
            # Fall back: sell at current strike instead of doing nothing.
            # The shift_threshold is a best-effort preference — failing to
            # hedge at all is worse than hedging at a lower premium.
            await self._process_shift_fallback(
                side, loss, hedge_premium, ce_now, pe_now,
            )
            return

        # New strike found — NOW freeze current positions
        freeze_result = freeze_current_positions(session, side)

        # ── Split Ledger Phase 2: Shift-Time Recycle ─────────────────────────
        shift_recycle_buyback = 0.0
        _sr_params = session.get('params', {})
        if _sr_params.get('shift_recycle_enabled', False):
            shift_recycle_buyback = await self._shift_time_recycle(
                side, new_strike_info,
            )
        # ─────────────────────────────────────────────────────────────────────

        # Sell at new strike
        new_strike = new_strike_info['strike']
        hedge_premium = new_strike_info['premium']

        # Fold buyback cost so extra lots at new strike recover it
        total_loss_to_cover = loss + shift_recycle_buyback

        lots, _, _ = self._engine.calculate_lots_to_sell(
            session, side, total_loss_to_cover, hedge_premium,
        )

        if lots <= 0:
            return

        # Execute sell at new strike
        expiry = session.get('params', {}).get('expiry', '')
        option_type = 'call' if side == 'ce' else 'put'
        symbol = self.initializer.build_symbol(
            option_type, 'BTC', new_strike, expiry,
        )

        # Register pending order before strike shift execution
        try:
            register_pending(
                session_id=sid,
                side=side,
                order_id='pending',
                symbol=symbol,
                lots=lots,
                strike=new_strike,
                adj_type='strike_shift',
            )
        except Exception as _pe:
            log.warning(f"[{sid}] Failed to register pending order for strike shift: {_pe}")

        _reprice_max = self.session.get('params', {}).get('max_reprice_attempts', None)
        result = await self.executor.smart_execute(
            symbol=symbol,
            side='sell',
            size=lots,
            max_reprice_attempts=_reprice_max,
        )

        # Update pending registry with real order ID
        try:
            real_oid = result.get('order_id', '')
            if real_oid and result.get('success'):
                register_pending(
                    session_id=sid, side=side,
                    order_id=str(real_oid), symbol=symbol,
                    lots=lots, strike=new_strike, adj_type='strike_shift',
                )
            elif not result.get('success'):
                clear_pending(sid, side)
        except Exception as _pe:
            log.warning(f"[{sid}] Failed to update pending registry for strike shift: {_pe}")

        if result.get('success'):
            fill_price = result.get('fill_price', 0)

            # BUG-1 FIX: Wrap entire post-fill sequence in try/except.
            # Each step is individually exception-safe so a failure in one
            # (e.g. frozen position snapshot) cannot abort the critical
            # trigger snapshot update or adjustment_complete event.
            _shift_errors = []

            # Step 1: Activate new strike (sets trigger_snapshot to fill_price)
            try:
                activate_new_strike(
                    session, side, new_strike, fill_price, lots,
                )
            except Exception as _e:
                _shift_errors.append(f'activate_new_strike: {_e}')
                log.exception(f"[{sid}] CRITICAL: activate_new_strike failed after strike shift fill: {_e}")

            # Step 2: Clear pending after state is updated
            try:
                clear_pending(sid, side)
            except Exception:
                pass

            # Step 3: Update triggers (frozen positions etc.)
            try:
                update_trigger_snapshots(session, ce_now, pe_now,
                                         fetch_premium_fn=self._make_fetch_fn())
            except Exception as _e:
                _shift_errors.append(f'update_trigger_snapshots: {_e}')
                log.exception(f"[{sid}] update_trigger_snapshots failed after strike shift: {_e}")

            # BUG-1 FIX: After update_trigger_snapshots, FORCE the new strike's
            # trigger snapshot to fill_price. update_trigger_snapshots uses the
            # stale ce_now/pe_now (fetched for the OLD strike), which overwrites
            # the correct fill_price that activate_new_strike set. This caused
            # PE[new_strike] trigger to be wrong, leading to false triggers.
            try:
                side_state = session.get(side, {})
                side_state.setdefault('trigger_snapshot', {})[_strike_key(new_strike)] = fill_price
                session[side] = side_state
                log.info(
                    f"[{sid}] Trigger snapshot force-set: {side.upper()}[{_strike_key(new_strike)}] = "
                    f"${fill_price:.2f} (fill price after strike shift)"
                )
            except Exception as _e:
                _shift_errors.append(f'trigger_snapshot_force_set: {_e}')
                log.exception(f"[{sid}] CRITICAL: Failed to force trigger snapshot after shift: {_e}")

            # Step 4: Update tracking fields (Bug #8 fix)
            try:
                premium_collected = fill_price * lots * LOT_SIZE_BTC
                aggressor_side = 'pe' if side == 'ce' else 'ce'
                session['last_aggressor'] = aggressor_side.upper()
                session['adjustment_count'] = session.get('adjustment_count', 0) + 1
                session['shift_count'] = session.get('shift_count', 0) + 1
                session['total_premium_collected'] = (
                    session.get('total_premium_collected', 0) + premium_collected
                )
            except Exception as _e:
                _shift_errors.append(f'tracking_update: {_e}')
                log.exception(f"[{sid}] tracking update failed after strike shift: {_e}")
                # Ensure these exist for downstream code
                premium_collected = fill_price * lots * LOT_SIZE_BTC
                aggressor_side = 'pe' if side == 'ce' else 'ce'

            # Step 5: Analytics
            try:
                analytics = session.setdefault('analytics', {})
                analytics.setdefault('shift_timestamps', []).append({
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'side': side.upper(),
                    'old_strike': old_strike,
                    'new_strike': new_strike,
                    'frozen_lots': freeze_result['frozen_lots'],
                })
                if len(analytics['shift_timestamps']) > 200:
                    analytics['shift_timestamps'] = analytics['shift_timestamps'][-200:]
            except Exception as _e:
                _shift_errors.append(f'analytics: {_e}')
                log.warning(f"[{sid}] analytics tracking failed after strike shift: {_e}")

            # Step 6: Adjustment history
            try:
                session.setdefault('adjustment_history', []).append({
                    'side': side.upper(),
                    'aggressor': aggressor_side.upper(),
                    'lots_sold': lots,
                    'premium': fill_price,
                    'strike': new_strike,
                    'old_strike': old_strike,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'type': 'strike_shift',
                    'premium_collected': premium_collected,
                    'adjustment_number': session.get('adjustment_count', 0),
                })
                if len(session['adjustment_history']) > 200:
                    session['adjustment_history'] = session['adjustment_history'][-200:]
                session['updated_at'] = datetime.now(timezone.utc).isoformat()
            except Exception as _e:
                _shift_errors.append(f'adjustment_history: {_e}')
                log.warning(f"[{sid}] adjustment_history append failed: {_e}")

            # Step 7: Emit events
            try:
                emit_strike_shift(
                    sid, side.upper(), old_strike, new_strike,
                    freeze_result['frozen_lots'], fill_price,
                )
            except Exception as _e:
                _shift_errors.append(f'emit_strike_shift: {_e}')
                log.warning(f"[{sid}] emit_strike_shift failed: {_e}")

            # BUG-1 & BUG-4 FIX: Log strike_shift event for observability
            log_activity('strike_shift',
                        f'🔀 Strike Shift: {side.upper()} {old_strike} → {new_strike} '
                        f'(frozen {freeze_result["frozen_lots"]} lots at old strike)',
                        sid, 'info',
                        {
                            'side': side.upper(),
                            'old_strike': old_strike,
                            'new_strike': new_strike,
                            'frozen_lots': freeze_result['frozen_lots'],
                            'fill_price': fill_price,
                        })

            # BUG-1 FIX: Log adjustment_complete — this was MISSING for strike
            # shifts, causing the trigger snapshot update + history record to
            # appear incomplete in the activity log.
            log_activity('adjustment_complete',
                        f'✓ Strike Shift Complete: SELL {lots} lots {side.upper()} @ {new_strike} '
                        f'for ${fill_price:.2f} (shifted from {old_strike})',
                        sid, 'success',
                        {
                            'side': side.upper(),
                            'strike': new_strike,
                            'old_strike': old_strike,
                            'lots': lots,
                            'fill_price': fill_price,
                            'type': 'strike_shift',
                            'adjustment_number': session.get('adjustment_count', 0),
                        })

            # BUG-1 FIX: If any step failed, log explicitly so failures are
            # never silent. The fill itself succeeded — state may be partially
            # updated but the operator has full visibility.
            if _shift_errors:
                log.error(
                    f"[{sid}] Strike shift post-fill had {len(_shift_errors)} error(s): "
                    f"{'; '.join(_shift_errors)}"
                )
                log_activity('shift_post_fill_error',
                            f'⚠️ Strike shift {side.upper()} {old_strike}→{new_strike} '
                            f'filled OK but post-fill had {len(_shift_errors)} error(s): '
                            f'{"; ".join(_shift_errors)}',
                            sid, 'warning',
                            {'errors': _shift_errors, 'side': side.upper(),
                             'old_strike': old_strike, 'new_strike': new_strike})

            log.info(
                f"Strike shift complete: {side.upper()} "
                f"{old_strike} → {new_strike}"
            )
        else:
            # Strike shift order FAILED — log explicitly for observability
            error_msg = result.get('error', 'unknown')
            log.error(
                f"[{sid}] Strike shift order FAILED: {side.upper()} "
                f"{old_strike} → {new_strike}: {error_msg}"
            )
            log_activity('adjustment_skipped',
                        f'❌ Strike Shift Failed: {side.upper()} {old_strike} → {new_strike} '
                        f'order not filled: {error_msg}',
                        sid, 'error',
                        {
                            'reason': 'execution_error',
                            'side': side.upper(),
                            'old_strike': old_strike,
                            'new_strike': new_strike,
                            'error': error_msg,
                        })

    # =========================================================================
    # §10b: Strike Shift Fallback — sell at current strike when no new strike
    # =========================================================================

    async def _process_shift_fallback(
        self,
        side: str,
        loss: float,
        hedge_premium: float,
        ce_now: float,
        pe_now: float,
    ):
        """
        Fallback when strike shift fails (no suitable new strike found).

        Instead of silently doing nothing (which leaves the position unhedged),
        sell at the current active strike even though its premium is below
        shift_threshold. A sub-optimal hedge is better than no hedge.
        """
        session = self.session
        sid = self.session_id

        lots, constraint_msg, _ = self._engine.calculate_lots_to_sell(
            session, side, loss, hedge_premium,
        )

        if lots <= 0:
            if constraint_msg:
                emit_safety(sid, 'position_cap', 'alert', constraint_msg)
            return

        hedge_strike = session.get(side, {}).get('active_strike', 0)

        # ITM Guard check (same as normal adjustment)
        itm_guard_on = session.get('params', {}).get('itm_guard_enabled', True)
        if hedge_strike:
            spot_price = await self._fetch_spot_price()
            if spot_price > 0:
                is_itm = False
                if side == 'ce' and hedge_strike <= spot_price:
                    is_itm = True
                elif side == 'pe' and hedge_strike >= spot_price:
                    is_itm = True

                if is_itm and itm_guard_on:
                    log.warning(
                        f"[{sid}] ITM GUARD (shift fallback): {side.upper()} "
                        f"{hedge_strike} is ITM (spot=${spot_price:.0f})."
                    )
                    log_activity('itm_guard_blocked',
                                f'🚫 ITM GUARD: {side.upper()} @ {hedge_strike} is ITM '
                                f'(spot ${spot_price:.0f}). Shift fallback blocked.',
                                sid, 'error',
                                {'hedge': side.upper(), 'strike': hedge_strike,
                                 'spot': spot_price, 'context': 'shift_fallback'})
                    return

        result = await self._engine.execute_adjustment(
            session, side, hedge_strike, lots,
            ce_now, pe_now, 'shift_fallback',
            fetch_premium_fn=self._make_fetch_fn(),
        )

        if result.get('success'):
            fill_price = result['fill_price']

            # Analytics tracking
            analytics = session.setdefault('analytics', {})
            analytics.setdefault('adjustment_events_by_side', {}).setdefault(side, 0)
            analytics['adjustment_events_by_side'][side] += 1
            analytics.setdefault('adjustment_events_by_type', {}).setdefault('shift_fallback', 0)
            analytics['adjustment_events_by_type']['shift_fallback'] += 1

            self._hb_wt['adjustment'] = {
                'side': side,
                'strike': hedge_strike,
                'lots': lots,
                'fill_price': fill_price,
                'loss': loss,
                'adj_type': 'shift_fallback',
                'hedge_premium': hedge_premium,
                'adjustment_number': session.get('adjustment_count', 0),
            }

            log_activity('adjustment_complete',
                        f'✓ Shift Fallback: SELL {lots} lots {side.upper()} @ {hedge_strike} '
                        f'for ${fill_price:.2f} (no better strike available)',
                        sid, 'success',
                        {
                            'side': side.upper(),
                            'strike': hedge_strike,
                            'lots': lots,
                            'fill_price': fill_price,
                            'type': 'shift_fallback',
                            'adjustment_number': session.get('adjustment_count', 0),
                        })
            emit_adjustment(
                sid, side.upper(), lots,
                fill_price, hedge_strike,
                loss, 'shift_fallback',
                session.get('adjustment_count', 0),
            )

    # =========================================================================
    # §11: Close-at-5 Processing
    # =========================================================================

    # Maximum positions to close per heartbeat to prevent heartbeat stalling.
    # Each close involves smart_execute (up to 60s wait + reprices), so
    # closing N positions can block the heartbeat for N * 60+ seconds.
    MAX_CLOSES_PER_HEARTBEAT = 3

    # =========================================================================
    # §3: M1 Profit Harvesting
    # =========================================================================

    async def _process_harvest(self) -> int:
        """
        §3: Proactive frozen position cleanup via profit harvesting (M1).

        Scans frozen positions for harvest eligibility and closes up to
        harvest_max_per_beat per heartbeat. Respects capacity pressure and
        minimum profit thresholds. M3 asymmetry modifier relaxes thresholds
        on the dominant side when one-sidedness is extreme.

        Returns:
            Number of positions successfully harvested this heartbeat.
        """
        session = self.session
        sid = self.session_id
        params = session.get('params', {})
        harvest_max = params.get('harvest_max_per_beat', 3)

        harvestable = scan_harvestable_positions(
            session, self._make_fetch_fn(),
        )
        if not harvestable:
            return 0

        harvested_count = 0
        # Track which sides already emitted a rebalance_boost log this heartbeat
        # so we fire at most once per side even if multiple positions are harvested.
        _boost_logged: set = set()

        for pos in harvestable:
            if harvested_count >= harvest_max:
                break
            if self._should_stop():
                break

            # Fix F1.2: Pre-mark _being_closed BEFORE await to prevent M2 race condition.
            # If M2 runs concurrently, it will see this flag and skip this position.
            pos_id = pos.get('_pos_id')
            pos_side = pos.get('side', '')
            if pos_id and pos_side:
                for p in session.get(pos_side, {}).get('positions', []):
                    if p.get('id') == pos_id:
                        p['_being_closed'] = True
                        break

            result = await close_position(
                self.executor, self.initializer, session, pos,
            )

            if result.get('success'):
                harvested_count += 1
                session['harvest_count'] = session.get('harvest_count', 0) + 1
                session['harvest_lots_freed'] = (
                    session.get('harvest_lots_freed', 0) + result.get('lots_closed', 0)
                )
                profit_pct = pos.get('_profit_pct', 0)
                harvest_score = pos.get('_harvest_score', 0)
                asymmetry_boosted = pos.get('_asymmetry_boosted', False)

                emit_harvest(
                    sid,
                    pos['side'].upper(),
                    pos['strike'],
                    result['lots_closed'],
                    result['realized_pnl'],
                    result['close_premium'],
                    profit_pct,
                    harvest_score,
                    asymmetry_boosted,
                )

                log_activity(
                    'harvest',
                    f'🌾 Harvested {result["lots_closed"]} lots '
                    f'{pos["side"].upper()} @ {pos["strike"]} '
                    f'({profit_pct:.0f}% profit, '
                    f'P&L: ${result["realized_pnl"]:.4f}'
                    + (' [asymmetry boost]' if asymmetry_boosted else '') + ')',
                    sid, 'success',
                    {
                        'side': pos['side'].upper(),
                        'strike': pos['strike'],
                        'lots': result['lots_closed'],
                        'realized_pnl': result['realized_pnl'],
                        'close_premium': result['close_premium'],
                        'profit_pct': profit_pct,
                        'harvest_score': harvest_score,
                        'asymmetry_boosted': asymmetry_boosted,
                    },
                )

                # Log rebalance boost once per side per heartbeat for activity feed clarity
                if asymmetry_boosted and pos['side'] not in _boost_logged:
                    _boost_logged.add(pos['side'])
                    boost_level = pos.get('_boost_level', '')
                    ce_lots = session.get('ce', {}).get('total_lots', 0)
                    pe_lots = session.get('pe', {}).get('total_lots', 0)
                    log_activity(
                        'rebalance_boost',
                        f'⚖️ Asymmetry boost ({boost_level}): '
                        f'CE={ce_lots} vs PE={pe_lots} — '
                        f'harvest thresholds relaxed on {pos["side"].upper()}',
                        sid, 'info',
                        {
                            'side': pos['side'].upper(),
                            'boost_level': boost_level,
                            'ce_lots': ce_lots,
                            'pe_lots': pe_lots,
                        },
                    )
            else:
                # Fix F1.2: Clear pre-marked _being_closed flag on failure so position can be retried
                if pos_id and pos_side:
                    for p in session.get(pos_side, {}).get('positions', []):
                        if p.get('id') == pos_id:
                            p.pop('_being_closed', None)
                            break
                log.debug(
                    f"[{sid}] Harvest: close failed for "
                    f"{pos['side'].upper()} @ {pos['strike']}: "
                    f"{result.get('error', 'unknown')}"
                )

        if harvested_count > 0:
            log.info(
                f"[{sid}] Harvest complete: {harvested_count} position(s) "
                f"closed this heartbeat"
            )

        return harvested_count

    # =========================================================================
    # §4: M2 Lot Recycling
    # =========================================================================

    async def _process_lot_recycling(
        self,
        aggressor: str,
        hedge: str,
        loss: float,
        hedge_premium: float,
        ce_now: float,
        pe_now: float,
    ) -> bool:
        """
        §4: Attempt lot recycling when max lots blocks an adjustment (M2).

        Called from _process_adjustment() when calculate_lots_to_sell() returns 0
        due to position cap. Checks regime/margin safety guards before attempting.

        Returns:
            True if recycling succeeded and the adjustment was handled.
            False if recycling is not viable or not allowed.
        """
        session = self.session
        sid = self.session_id
        params = session.get('params', {})

        if not params.get('recycle_enabled', True):
            return False

        # §4.2: Regime guard — recycling involves a sell (Phase B)
        regime_action = session.get('_regime_action', 'NORMAL')
        if regime_action == ACTION_BLOCK_ALL_SELLS:
            log.info(
                f"[{sid}] Recycle skipped: regime action is "
                f"{regime_action} — sells blocked"
            )
            return False

        # §4.2: Directional regime block check
        try:
            blocked, block_reason = self._regime_engine.should_block_sell(
                session, hedge,
            )
            if blocked:
                log.info(
                    f"[{sid}] Recycle skipped: regime blocks "
                    f"{hedge.upper()} sells — {block_reason}"
                )
                return False
        except Exception as _re:
            log.warning(f"[{sid}] Recycle regime check failed: {_re}")

        # §4.2: Margin guard — don't recycle when margin is ORANGE+
        margin_tier = getattr(self._margin_guardian, 'last_tier', TIER_GREEN)
        if margin_tier not in (TIER_GREEN, TIER_YELLOW):
            log.info(
                f"[{sid}] Recycle skipped: margin tier "
                f"{margin_tier} — too elevated for new sells"
            )
            return False

        # Fetch spot price for find_new_strike
        try:
            spot_price = await self._fetch_spot_price()
        except Exception as e:
            log.warning(f"[{sid}] Recycle: spot price fetch failed: {e}")
            return False

        log.info(
            f"[{sid}] Attempting lot recycling: "
            f"{hedge.upper()} capped, loss={loss:.4f}, "
            f"premium={hedge_premium:.2f}"
        )

        result = await execute_lot_recycling(
            session=session,
            aggressor=aggressor,
            hedge_side=hedge,
            loss_to_hedge=loss,
            fetch_premium_fn=self._make_fetch_fn(),
            initializer=self.initializer,
            executor=self.executor,
            spot_price=spot_price,
            engine=self._engine,
            ce_now=ce_now,
            pe_now=pe_now,
        )

        if result.get('success'):
            emit_recycle(
                sid,
                hedge.upper(),
                result['recycled_lots'],
                result['new_lots_sold'],
                0,  # old_strike — set to 0 (multiple positions recycled)
                result['new_strike'],
                result['new_premium'],
                result['net_lot_gain'],
                result['buyback_cost'],
                result['phase_a_pnl'],
            )
            log_activity(
                'recycle',
                f'♻️ Recycled {result["recycled_lots"]} lots → sold '
                f'{result["new_lots_sold"]} @ {result["new_strike"]} '
                f'(premium: ${result["new_premium"]:.2f}, '
                f'net gain: {result["net_lot_gain"]} lots)',
                sid, 'success',
                {
                    'hedge_side': hedge.upper(),
                    'recycled_lots': result['recycled_lots'],
                    'new_lots_sold': result['new_lots_sold'],
                    'new_strike': result['new_strike'],
                    'new_premium': result['new_premium'],
                    'net_lot_gain': result['net_lot_gain'],
                    'recycle_count': session.get('recycle_count', 0),
                },
            )
            return True

        # Recycling failed or not viable — log and let caller handle
        log.info(
            f"[{sid}] Lot recycling not viable: {result.get('error', 'unknown')}"
        )
        log_activity(
            'adjustment_skipped',
            f'⏭️ Lot recycling not viable: {result.get("error", "unknown")}',
            sid, 'info',
            {
                'reason': 'recycle_not_viable',
                'recycle_error': result.get('error', ''),
                'hedge': hedge.upper(),
            },
        )
        return False

    async def _shift_time_recycle(
        self,
        side: str,
        new_strike_info: Dict,
    ) -> float:
        """
        Split Ledger Phase 2: At shift time, close cheap frozen positions
        on `side` to free capacity. Returns total buyback cost in USD so
        the caller can fold it into the new sell lot calculation.

        Only closes frozen positions with live premium BELOW shift_recycle_premium_floor.
        Respects shift_recycle_max_pct limit on frozen lots closed per shift.
        Default: shift_recycle_enabled=False — this method is never called unless enabled.

        Returns:
            Total buyback cost in USD. 0.0 if nothing closed.
        """
        from .mmm_close_at_5 import close_position

        session = self.session
        sid = self.session_id
        params = session.get('params', {})
        premium_floor = params.get('shift_recycle_premium_floor', 60.0)
        if premium_floor <= 0:
            # Dynamic mode: close frozen if cheaper than N% of new strike premium
            dynamic_ratio = params.get('shift_recycle_floor_ratio', 0.40)
            premium_floor = new_strike_info.get('premium', 100.0) * dynamic_ratio
        max_pct = params.get('shift_recycle_max_pct', 1.0)

        side_state = session.get(side, {})
        frozen_positions = side_state.get('frozen_positions', [])

        if not frozen_positions:
            return 0.0

        # Respect max_pct: limit total lots we can close this shift
        total_frozen = sum(f.get('lots', 0) for f in frozen_positions)
        max_closeable_lots = int(total_frozen * max_pct)
        if max_closeable_lots <= 0:
            return 0.0

        option_type = 'call' if side == 'ce' else 'put'
        fetch_fn = self._make_fetch_fn()
        total_buyback = 0.0
        closed_lots = 0

        priced_frozen = []
        for fpos in frozen_positions:
            strike = fpos.get('strike', 0)
            lots = fpos.get('lots', 0)
            pos_id = fpos.get('_pos_id', '')
            if strike <= 0 or lots <= 0:
                continue
            try:
                live_premium = fetch_fn(strike, option_type)
            except Exception as e:
                log.warning(f"[{sid}] Shift recycle: premium fetch failed for {strike}: {e}")
                continue
            if live_premium is None or live_premium <= 0:
                continue
            if live_premium > premium_floor:
                continue  # Too expensive — leave for M1 / close-at-5
            priced_frozen.append({
                'side': side,
                'strike': strike,
                'lots': lots,
                'entry_premium': fpos.get('entry_premium', 0),
                'current_premium': live_premium,
                'type': 'frozen',
                '_pos_id': pos_id,
            })

        # Sort cheapest first to maximise freed lots per dollar spent
        priced_frozen.sort(key=lambda p: p.get('current_premium', 0))

        for close_payload in priced_frozen:
            if closed_lots >= max_closeable_lots:
                break
            lots = close_payload['lots']
            live_premium = close_payload['current_premium']
            try:
                result = await close_position(
                    self.executor, self.initializer, session, close_payload,
                )
            except Exception as e:
                log.warning(
                    f"[{sid}] Shift recycle: close failed for "
                    f"{side.upper()} @ {close_payload['strike']}: {e}"
                )
                continue
            if result.get('success'):
                cost = float(_D(live_premium) * _D(lots) * _LOT)
                total_buyback += cost
                actual_closed = result.get('lots_closed', lots)
                closed_lots += actual_closed
                log.info(
                    f"[{sid}] Shift recycle: closed {actual_closed} "
                    f"{side.upper()} lots @ {close_payload['strike']} "
                    f"(premium ${live_premium:.2f}, cost ${cost:.4f})"
                )
            else:
                log.warning(
                    f"[{sid}] Shift recycle: close rejected for "
                    f"{side.upper()} @ {close_payload['strike']}: "
                    f"{result.get('error', 'unknown')}"
                )

        if closed_lots > 0:
            # Suggestion 3: Shift-time recycle ROI tracking
            stats = session.setdefault(
                'shift_recycle_stats',
                {'total_buyback': 0.0, 'total_lots_freed': 0, 'total_shifts': 0},
            )
            stats['total_buyback'] += total_buyback
            stats['total_lots_freed'] += closed_lots
            stats['total_shifts'] += 1

            log_activity(
                'shift_recycle',
                f'♻️ Shift-Time Recycle: closed {closed_lots} frozen '
                f'{side.upper()} lots, buyback ${total_buyback:.4f}',
                sid, 'success',
                {
                    'side': side.upper(),
                    'closed_lots': closed_lots,
                    'buyback_cost': round(total_buyback, 4),
                    'premium_floor': premium_floor,
                },
            )
            try:
                emit_recycle(
                    sid, side.upper(), closed_lots, 0,
                    0, 0, 0,
                    closed_lots,        # net_gain = lots freed
                    total_buyback,      # buyback_cost
                    0,                  # phase_a_pnl (already recorded by close_position)
                )
            except Exception as _e:
                log.warning(f"[{sid}] Shift recycle: emit_recycle failed: {_e}")

        return total_buyback

    async def _process_close_at_5(
        self,
        ce_now: float,
        pe_now: float,
    ) -> set:
        """Scan and close positions at or below threshold.
        During wind-down, uses elevated threshold from wind_down_close_threshold
        to harvest opportunity (close positions that have decayed significantly).

        Caps at MAX_CLOSES_PER_HEARTBEAT per heartbeat to prevent the heartbeat
        from hanging for 10+ minutes when many positions are eligible.
        Remaining positions will be closed in subsequent heartbeats.

        Returns:
            Set of side keys ('ce', 'pe') that had at least one successful close
            this heartbeat.  Used by Fix #11 to decide if trigger re-evaluation
            is needed before executing an adjustment on the same side.
        """
        session = self.session
        sid = self.session_id

        # During wind-down, elevate the close threshold for opportunity harvest
        wd_threshold = get_wind_down_close_threshold(session)
        normal_threshold = session.get('params', {}).get('close_at_threshold', 5.0)
        using_elevated = wd_threshold > normal_threshold

        # Use bid price for close_at_5 checks if enabled (more accurate for illiquid options)
        use_bid = session.get('params', {}).get('close_at_use_bid', True)
        fetch_fn = self._make_bid_fetch_fn() if use_bid else self._make_fetch_fn()

        closeable = scan_closeable_positions(
            session, fetch_fn,
            threshold_override=wd_threshold if using_elevated else None,
        )

        if closeable:
            threshold_note = f' (wind-down elevated threshold: {wd_threshold})' if using_elevated else ''
            bid_note = ' [using bid price]' if use_bid else ''
            closeable_summary = ', '.join([f"{p['side'].upper()} @ {p['strike']}" for p in closeable])
            capped_note = ''
            if len(closeable) > self.MAX_CLOSES_PER_HEARTBEAT:
                capped_note = (f' [processing {self.MAX_CLOSES_PER_HEARTBEAT} of '
                              f'{len(closeable)} this heartbeat]')
            log_activity('info',
                        f'Close-at-5 Scan: {len(closeable)} position(s) ready to close'
                        f'{threshold_note}{bid_note}{capped_note} - {closeable_summary}',
                        sid, 'info',
                        {'closeable_count': len(closeable), 'positions': closeable_summary,
                         'wind_down_elevated': using_elevated,
                         'using_bid_price': use_bid,
                         'threshold_used': wd_threshold if using_elevated else normal_threshold,
                         'capped_at': self.MAX_CLOSES_PER_HEARTBEAT})

        closed_count = 0
        sides_closed: set = set()  # Fix #11: track which sides had successful closes
        for pos in closeable:
            # Cap: don't process more than MAX_CLOSES_PER_HEARTBEAT per beat
            if closed_count >= self.MAX_CLOSES_PER_HEARTBEAT:
                log.info(
                    f"[{sid}] Close-at-5: capped at {self.MAX_CLOSES_PER_HEARTBEAT} "
                    f"closes this heartbeat ({len(closeable) - closed_count} deferred)"
                )
                break

            # Check if monitor was stopped while we were executing closes
            if self._should_stop():
                log.info(f"[{sid}] Close-at-5: stop requested, aborting remaining closes")
                break

            # ── SHIFT-BEFORE-CLOSE GUARD ──────────────────────────────────────
            # In normal (non-wind-down) mode, do NOT close an ACTIVE position
            # whose mark premium is below shift_threshold while the other side
            # still has open lots.
            #
            # Rationale: when a position's mark premium is below shift_threshold,
            # it means that if the other side triggers an adjustment, a strike
            # SHIFT will fire — moving this side to a fresh OTM strike with
            # better premium and restoring full hedge coverage.  Closing the
            # position first eliminates that hedge opportunity and leaves the
            # other side exposed.
            #
            # Using MARK price (ce_now/pe_now) is intentional — it is also what
            # check_shift_needed uses inside _process_adjustment, so the guard
            # fires under exactly the same conditions as a real shift would.
            #
            # Does NOT apply to:
            #   - frozen positions (already shifted away; not the active hedge)
            #   - wind-down mode (using_elevated = True) — wind-down has its own
            #     close/buyback logic; the one-side guard handles asymmetry there
            if not using_elevated and pos.get('type') in ('original', 'adjustment', 'strike_shift'):
                _sbc_pos_side = pos['side']
                _sbc_other_side = 'pe' if _sbc_pos_side == 'ce' else 'ce'
                _sbc_other_lots = session.get(_sbc_other_side, {}).get('total_lots', 0)
                _sbc_mark = ce_now if _sbc_pos_side == 'ce' else pe_now
                if _sbc_other_lots > 0 and check_shift_needed(session, _sbc_pos_side, _sbc_mark):
                    log.info(
                        f"[{sid}] SHIFT-GUARD: Holding {_sbc_pos_side.upper()} "
                        f"@ {pos['strike']} (mark ${_sbc_mark:.2f} < shift_threshold — "
                        f"{_sbc_other_side.upper()} has {_sbc_other_lots} lots open). "
                        f"Preserving for trigger-based shift."
                    )
                    log_activity(
                        'close_skipped',
                        f'⏸️ SHIFT-GUARD: Held {_sbc_pos_side.upper()} @ {pos["strike"]} '
                        f'— mark ${_sbc_mark:.2f} < shift_threshold. '
                        f'{_sbc_other_side.upper()} has {_sbc_other_lots} lots: '
                        f'preserving for strike shift.',
                        sid, 'info',
                        {
                            'side': _sbc_pos_side,
                            'strike': pos['strike'],
                            'mark_premium': _sbc_mark,
                            'other_side': _sbc_other_side,
                            'other_lots': _sbc_other_lots,
                        },
                    )
                    continue
            # ── END SHIFT-BEFORE-CLOSE GUARD ─────────────────────────────────

            result = await close_position(
                self.executor, self.initializer, session, pos,
            )

            if result.get('success'):
                closed_count += 1
                sides_closed.add(pos['side'])  # Fix #11: record side
                emit_close_at_5(
                    sid, pos['side'].upper(), pos['strike'],
                    result['lots_closed'], result['realized_pnl'],
                    result['close_premium'],
                )
                # Track for walkthrough
                self._hb_wt['close_at_5'].append({
                    'side': pos['side'],
                    'strike': pos['strike'],
                    'lots_closed': result['lots_closed'],
                    'realized_pnl': result['realized_pnl'],
                    'close_premium': result['close_premium'],
                    'scan_premium': pos.get('current_premium', 0),    # mid at scan time
                    'threshold_used': pos.get('threshold_used', 5.0),  # actual threshold
                })

                # Check if side fully closed — heartbeat will detect and PAUSE
                # (one-side close guard runs after _process_close_at_5 returns)
                if check_side_fully_closed(session, pos['side']):
                    log.info(
                        f"[{sid}] {pos['side'].upper()} fully closed — "
                        f"one-side guard in heartbeat will evaluate."
                    )

        return sides_closed  # Fix #11

    # =========================================================================
    # §8: Both-Sides-Up Auto-Decision (30s timeout)
    # =========================================================================

    def _auto_decide_both_sides(
        self,
        session: Dict,
        ce_now: float,
        pe_now: float,
    ) -> str:
        """
        Auto-decide when both sides are up and user hasn't responded in 30s.

        Logic:
        - Compute unrealized P&L for CE side and PE side (including frozen)
        - If CE side has loss (premium rose → short is losing): hedge by selling PE → 'adjust_pe'
        - If PE side has loss: hedge by selling CE → 'adjust_ce'
        - If both have loss: hedge the bigger loser
        - If neither has loss (both profitable): skip — no action needed
        """
        ce_state = session.get('ce', {})
        pe_state = session.get('pe', {})

        # CE P&L: sold at entry premium, current premium is ce_now
        # If ce_now > entry → CE short is losing (negative P&L)
        ce_active_lots = ce_state.get('active_lots', 0)
        pe_active_lots = pe_state.get('active_lots', 0)

        # Use trigger snapshot as reference (that's the "covered up to" level)
        ce_trigger_strike = _strike_key(ce_state.get('active_strike', 0))
        pe_trigger_strike = _strike_key(pe_state.get('active_strike', 0))
        ce_trigger = ce_state.get('trigger_snapshot', {}).get(ce_trigger_strike, 0)
        pe_trigger = pe_state.get('trigger_snapshot', {}).get(pe_trigger_strike, 0)

        # Active excess = how much premium rose above the covered level
        ce_excess = (ce_now - ce_trigger) * ce_active_lots if ce_active_lots > 0 else 0
        pe_excess = (pe_now - pe_trigger) * pe_active_lots if pe_active_lots > 0 else 0

        # Bug #10 fix: include frozen position losses in the decision
        fetch_fn = self._make_fetch_fn()
        for frozen in ce_state.get('frozen_positions', []):
            f_strike = frozen.get('strike', 0)
            f_entry = frozen.get('entry_premium', 0)
            f_lots = frozen.get('lots', 0)
            if f_lots > 0 and f_strike > 0:
                try:
                    f_current = fetch_fn(f_strike, 'call')
                    frozen_loss = (f_current - f_entry) * f_lots
                    if frozen_loss > 0:
                        ce_excess += frozen_loss
                except Exception:
                    pass

        for frozen in pe_state.get('frozen_positions', []):
            f_strike = frozen.get('strike', 0)
            f_entry = frozen.get('entry_premium', 0)
            f_lots = frozen.get('lots', 0)
            if f_lots > 0 and f_strike > 0:
                try:
                    f_current = fetch_fn(f_strike, 'put')
                    frozen_loss = (f_current - f_entry) * f_lots
                    if frozen_loss > 0:
                        pe_excess += frozen_loss
                except Exception:
                    pass

        log.info(
            f"Auto-decide both-sides: CE excess={ce_excess:.2f} "
            f"(now={ce_now:.2f}, trigger={ce_trigger:.2f}, lots={ce_active_lots}, "
            f"incl. frozen), "
            f"PE excess={pe_excess:.2f} "
            f"(now={pe_now:.2f}, trigger={pe_trigger:.2f}, lots={pe_active_lots}, "
            f"incl. frozen)"
        )

        if ce_excess <= 0 and pe_excess <= 0:
            # Neither has uncovered loss → skip
            return 'skip'
        elif ce_excess > pe_excess:
            # CE has bigger uncovered loss → CE is aggressor → sell PE to hedge
            return 'adjust_pe'
        elif pe_excess > ce_excess:
            # PE has bigger uncovered loss → PE is aggressor → sell CE to hedge
            return 'adjust_ce'
        else:
            # Equal → skip (don't add risk on both sides)
            return 'skip'

    # =========================================================================
    # Auto-Close All (Near Expiry)
    # =========================================================================

    async def _auto_close_all(self, reason: str, emergency: bool = False):
        """Close all open positions (near-expiry safety / max-loss / margin breach).

        Closes each position at its own strike:
        - Active positions (original + adjustment) at active_strike
        - Each frozen position at its own frozen strike

        Args:
            reason: Human-readable reason for the close
            emergency: If True, uses emergency_execute (taker IOC orders) and
                       closes both sides in parallel for maximum speed.
                       If False, uses smart_execute (maker orders) sequentially.

        Bug #9 fix: retry failed closes up to MAX_CLOSE_RETRIES times.
        Bug #13 fix: clear lot counts and position arrays after closes.
        Bug #16 fix: always call self.stop() even if exceptions occur.
        """
        session = self.session
        sid = self.session_id
        MAX_CLOSE_RETRIES = 3
        RETRY_DELAY = 0.5 if emergency else 2  # Faster retries in emergency

        mode_label = "🚨 EMERGENCY" if emergency else "🔄 Normal"
        log.info(f"[{sid}] {mode_label} auto-closing all positions: {reason}")

        log_activity('auto_close_all',
                     f'{mode_label} close-all initiated: {reason}',
                     sid, 'critical' if emergency else 'warning',
                     {'reason': reason, 'emergency': emergency})

        failed_closes = []

        try:
            # §26.10: Close perp FIRST before options (reduces delta risk
            # during the window when options positions are still open)
            if is_perp_hedge_enabled(session):
                perp_close = await close_all_perp(session, self.executor, reason)
                if not perp_close.get('success') and perp_close.get('lots_closed', 0) == 0:
                    # Only fail if there was actually a position to close
                    perp_lots = session.get('perp_hedge', {}).get('lots', 0)
                    if perp_lots != 0:
                        log.error(
                            f"[{sid}] Perp close failed ({perp_lots} lots remain). "
                            f"Continuing with options close."
                        )

            if emergency:
                # PARALLEL close: both sides simultaneously for speed
                ce_task = self._close_one_side(
                    'ce', MAX_CLOSE_RETRIES, RETRY_DELAY, emergency=True)
                pe_task = self._close_one_side(
                    'pe', MAX_CLOSE_RETRIES, RETRY_DELAY, emergency=True)
                ce_fails, pe_fails = await asyncio.gather(
                    ce_task, pe_task, return_exceptions=False)
                failed_closes.extend(ce_fails)
                failed_closes.extend(pe_fails)
            else:
                # SEQUENTIAL close: one side at a time (original behavior)
                for side_key in ['ce', 'pe']:
                    if self._should_stop():
                        log.warning(f"[{sid}] Stop requested during auto-close, aborting")
                        break
                    side_fails = await self._close_one_side(
                        side_key, MAX_CLOSE_RETRIES, RETRY_DELAY, emergency=False)
                    failed_closes.extend(side_fails)

            if failed_closes:
                log.error(
                    f"[{sid}] Auto-close completed with FAILURES: {failed_closes}. "
                    f"Manual intervention may be needed."
                )
                log_activity('auto_close_failures',
                             f'{mode_label} close-all had failures: {failed_closes}',
                             sid, 'error',
                             {'failures': failed_closes, 'emergency': emergency})

        except Exception as e:
            log.exception(f"[{sid}] CRITICAL: _auto_close_all crashed: {e}")
        finally:
            # Bug #16 fix: ALWAYS stop the session, even if close orders failed
            self.stop(reason)

    async def _close_one_side(
        self,
        side_key: str,
        max_retries: int,
        retry_delay: float,
        emergency: bool = False,
    ) -> list:
        """Close all positions on one side (active + frozen).

        Returns a list of failure descriptions (empty = all success).
        Extracted from _auto_close_all to enable parallel execution.
        """
        session = self.session
        sid = self.session_id
        failed_closes = []

        side_state = session.get(side_key, {})
        option_type = 'call' if side_key == 'ce' else 'put'
        active_strike = side_state.get('active_strike', 0)
        expiry = session.get('params', {}).get('expiry', '')

        # Choose executor method
        async def _execute_close(symbol, lots):
            if emergency:
                return await self.executor.emergency_execute(
                    symbol=symbol, side='buy', size=lots,
                    reduce_only=True, session_id=sid,
                )
            else:
                _reprice_max = self.session.get('params', {}).get('max_reprice_attempts', None)
                return await self.executor.smart_execute(
                    symbol=symbol, side='buy', size=lots,
                    reduce_only=True,
                    max_reprice_attempts=_reprice_max,
                )

        # Close active lots (original + adjustment) at active strike
        active_lots = side_state.get('active_lots', 0)
        if active_lots > 0 and active_strike > 0:
            closed = False
            for attempt in range(1, max_retries + 1):
                try:
                    symbol = self.initializer.build_symbol(
                        option_type, 'BTC', active_strike, expiry,
                    )
                    result = await _execute_close(symbol, active_lots)
                    if result.get('success'):
                        close_price = result.get('fill_price', 0)
                        # Bug #3 fix: weighted avg entry across original + adj fills
                        orig_lots = side_state.get('original_lots', 0)
                        orig_prem = side_state.get('original_premium', 0)
                        weighted_sum = orig_prem * orig_lots
                        weighted_lots = orig_lots
                        for fill in side_state.get('adjustment_fills', []):
                            f_lots = fill.get('lots', 0)
                            f_prem = fill.get('premium', 0)
                            f_strike = fill.get('strike', active_strike)
                            if f_strike == active_strike:
                                weighted_sum += f_prem * f_lots
                                weighted_lots += f_lots
                        avg_entry = weighted_sum / weighted_lots if weighted_lots > 0 else 0
                        pnl = (avg_entry - close_price) * active_lots * LOT_SIZE_BTC
                        session['realized_pnl'] = (
                            session.get('realized_pnl', 0) + pnl
                        )
                        log.info(
                            f"[{sid}] Closed {active_lots} active "
                            f"{side_key.upper()} @ {active_strike}, "
                            f"avg_entry: {avg_entry:.2f}, P&L: {pnl:.2f}"
                        )
                        # Fix #23: Mark all active positions as closed in positions[]
                        _now = datetime.now(timezone.utc).isoformat()
                        for _pos in side_state.get('positions', []):
                            if _pos.get('status') == 'active':
                                _pos['status'] = 'closed'
                                _pos['closed_at'] = _now
                        closed = True
                        break
                    else:
                        log.warning(
                            f"[{sid}] Auto-close active {side_key.upper()} "
                            f"attempt {attempt}/{max_retries} failed: "
                            f"{result.get('error', 'unknown')}"
                        )
                except Exception as e:
                    log.error(
                        f"[{sid}] Auto-close active {side_key.upper()} "
                        f"attempt {attempt}/{max_retries} error: {e}"
                    )
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)
            if not closed:
                failed_closes.append(f"{side_key.upper()} active @ {active_strike}")

        # Close each frozen position at its OWN strike
        closed_frozen_indices = []
        for fi, frozen in enumerate(side_state.get('frozen_positions', [])):
            frozen_strike = frozen.get('strike', 0)
            frozen_lots = frozen.get('lots', 0)
            frozen_entry = frozen.get('entry_premium', 0)

            if frozen_lots > 0 and frozen_strike > 0:
                closed = False
                for attempt in range(1, max_retries + 1):
                    try:
                        symbol = self.initializer.build_symbol(
                            option_type, 'BTC', frozen_strike, expiry,
                        )
                        result = await _execute_close(symbol, frozen_lots)
                        if result.get('success'):
                            close_price = result.get('fill_price', 0)
                            pnl = (frozen_entry - close_price) * frozen_lots * LOT_SIZE_BTC
                            session['realized_pnl'] = (
                                session.get('realized_pnl', 0) + pnl
                            )
                            log.info(
                                f"[{sid}] Closed {frozen_lots} frozen "
                                f"{side_key.upper()} @ {frozen_strike}, P&L: {pnl:.2f}"
                            )
                            closed_frozen_indices.append(fi)
                            closed = True
                            break
                        else:
                            log.warning(
                                f"[{sid}] Auto-close frozen {side_key.upper()} @ {frozen_strike} "
                                f"attempt {attempt}/{max_retries} failed"
                            )
                    except Exception as e:
                        log.error(
                            f"Failed to auto-close frozen {side_key.upper()} "
                            f"@ {frozen_strike}, attempt {attempt}: {e}"
                        )
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                if not closed:
                    failed_closes.append(f"{side_key.upper()} frozen @ {frozen_strike}")

        # Fix #23: Mark successfully closed frozen positions as 'closed' in positions[]
        # Use _pos_id from computed frozen_positions view for O(1) lookup
        if closed_frozen_indices:
            _now = datetime.now(timezone.utc).isoformat()
            frozen_view = side_state.get('frozen_positions', [])
            closed_ids = {
                frozen_view[fi].get('_pos_id')
                for fi in closed_frozen_indices
                if fi < len(frozen_view)
            }
            for _pos in side_state.get('positions', []):
                if _pos.get('id') in closed_ids:
                    _pos['status'] = 'closed'
                    _pos['closed_at'] = _now

        # Recompute lots after clearing
        recompute_side_lots(side_state)
        session[side_key] = side_state

        return failed_closes

    # =========================================================================
    # Helpers
    # =========================================================================

    # =========================================================================
    # §14.5: Exchange Position Reconciliation
    # =========================================================================

    async def _check_margin_guardian(self):
        """
        Run the Margin Guardian check. Called at the start of every heartbeat
        (Step 0.5, after reconcile, before premium fetch).

        Returns the margin result dict, or None if skipped/disabled.
        On RED/CRITICAL, triggers emergency close and session stop.
        """
        sid = self.session_id
        session = self.session

        try:
            rest = self._create_heartbeat_rest_client()
            hb_num = session.get('_heartbeat_counter', 0)

            result = await self._margin_guardian.check(session, rest, hb_num)

            if not result.get('checked'):
                return result

            util = result['utilization_pct']
            tier = result['tier']
            margin_data = result.get('margin_data', {})

            # Always log margin status on tier change
            if result.get('tier_changed'):
                log_activity(
                    'margin_tier_change',
                    f'⚠️ MARGIN TIER: {result["prev_tier"]} → {tier} '
                    f'(utilization: {util:.1f}%, '
                    f'equity: ${margin_data.get("net_equity", 0):.2f})',
                    sid, 'warning' if tier in (TIER_YELLOW, TIER_ORANGE) else 'error',
                    {'tier': tier, 'prev_tier': result['prev_tier'],
                     'utilization_pct': util,
                     'net_equity': margin_data.get('net_equity', 0),
                     'position_margin': margin_data.get('position_margin', 0)},
                )
                emit_safety(
                    sid, 'margin_tier_change', 'critical' if tier in (TIER_RED, TIER_CRITICAL) else 'alert',
                    f'Margin {result["prev_tier"]} → {tier}: {util:.1f}% utilization',
                    {'tier': tier, 'utilization_pct': util},
                )
                # Telegram alert for tier change
                try:
                    await alert_margin_tier_change(
                        sid, result['prev_tier'], tier, util,
                        margin_data.get('net_equity', 0),
                        margin_data.get('position_margin', 0),
                    )
                except Exception:
                    pass  # non-fatal

            # Handle critical tiers
            if tier == TIER_CRITICAL:
                log.critical(
                    f"[{sid}] MARGIN CRITICAL ({util:.1f}%) — "
                    f"SURVIVAL MODE: closing ALL positions and stopping session"
                )
                log_activity(
                    'margin_critical',
                    f'🚨 MARGIN CRITICAL: {util:.1f}% utilization — '
                    f'SURVIVAL MODE — closing all + stopping session',
                    sid, 'error',
                    {'utilization_pct': util,
                     'net_equity': margin_data.get('net_equity', 0)},
                )
                # Telegram alerts for CRITICAL
                try:
                    await alert_emergency_close(sid, f'MARGIN CRITICAL: {util:.1f}%', tier, util)
                except Exception:
                    pass
                await self._auto_close_all(
                    f'MARGIN CRITICAL: {util:.1f}% utilization — survival mode',
                    emergency=True,
                )
                self.stop(f'MARGIN CRITICAL: {util:.1f}% utilization — session stopped for safety')
                try:
                    await alert_session_stopped(sid, f'MARGIN CRITICAL: {util:.1f}% utilization')
                except Exception:
                    pass
                return result

            if tier == TIER_RED:
                lots = result.get('lots_to_close', {'ce': 0, 'pe': 0})
                log.critical(
                    f"[{sid}] MARGIN RED ({util:.1f}%) — "
                    f"emergency reducing: CE={lots['ce']}, PE={lots['pe']} lots"
                )
                log_activity(
                    'margin_red',
                    f'🔴 MARGIN RED: {util:.1f}% — emergency reduce '
                    f'(closing CE={lots["ce"]}, PE={lots["pe"]} lots)',
                    sid, 'error',
                    {'utilization_pct': util, 'lots_to_close': lots},
                )
                # Telegram alert for RED
                try:
                    await alert_emergency_close(sid, f'MARGIN RED: {util:.1f}%', tier, util)
                except Exception:
                    pass
                # Emergency close all positions to reduce margin quickly
                await self._auto_close_all(
                    f'MARGIN RED: {util:.1f}% utilization — emergency reduce',
                    emergency=True,
                )
                return result

            # For YELLOW/ORANGE tiers — send rapid-check alert on tier change
            if result.get('tier_changed') and tier in (TIER_YELLOW, TIER_ORANGE):
                try:
                    await alert_rapid_check_activated(
                        sid,
                        f'Margin tier elevated to {tier}',
                        util,
                    )
                except Exception:
                    pass

            return result

        except Exception as e:
            log.error(f"[{sid}] Margin guardian check failed: {e}")
            # L-2: Intentional fail-open design — if margin check crashes,
            # heartbeat continues normally. Rationale: a transient API error
            # should not halt the entire strategy. The next heartbeat will
            # retry the margin check.
            return None

    def _get_other_sessions_lots_at_symbol(self, symbol: str) -> int:
        """
        Return the total lots that OTHER active MMM sessions claim at a
        given exchange symbol.  Used during reconciliation to avoid
        auto-syncing positions that belong to a different session.
        """
        total = 0
        for other_sid, other_mon in get_all_monitors().items():
            if other_sid == self.session_id:
                continue
            other = other_mon.session
            other_expiry = other.get('params', {}).get('expiry', '')
            for side_key in ['ce', 'pe']:
                side = other.get(side_key, {})
                opt = 'call' if side_key == 'ce' else 'put'

                # Active strike lots
                active_strike = side.get('active_strike', 0)
                if active_strike > 0:
                    asym = self.initializer.build_symbol(opt, 'BTC', active_strike, other_expiry)
                    if asym == symbol:
                        total += side.get('original_lots', 0)
                        for fill in side.get('adjustment_fills', []):
                            if fill.get('strike', active_strike) == active_strike:
                                total += fill.get('lots', 0)

                # Frozen position lots
                for frozen in side.get('frozen_positions', []):
                    f_strike = frozen.get('strike', 0)
                    if f_strike > 0:
                        fsym = self.initializer.build_symbol(opt, 'BTC', f_strike, other_expiry)
                        if fsym == symbol:
                            total += frozen.get('lots', 0)
        return total

    # =========================================================================
    # Auto-Correction Helpers for Exchange Reconciliation
    # =========================================================================

    def _auto_correct_missing_positions(
        self, side_state: Dict, strike: float, reason: str
    ):
        """
        Mark ALL positions at a given strike as closed/expired in the
        Unified Position Ledger. Called when exchange shows 0 lots at a
        strike the session thinks it owns.
        """
        from .mmm_state import recompute_side_lots
        now = datetime.now(timezone.utc).isoformat()
        removed_lots = 0
        strike_tol = 1.0  # float tolerance for strike comparison

        for pos in side_state.get('positions', []):
            if pos.get('status') in ('active', 'shifted'):
                pos_strike = pos.get('strike', 0)
                if abs(pos_strike - strike) < strike_tol:
                    removed_lots += pos.get('lots', 0)
                    pos['status'] = 'closed'
                    pos['closed_at'] = now
                    pos['close_reason'] = f'exchange_reconciliation:{reason}'

        if removed_lots > 0:
            recompute_side_lots(side_state)
            log.warning(
                f"[{self.session_id}] AUTO-CORRECT: Removed {removed_lots} phantom "
                f"{side_state.get('side', '?').upper()} lots @ {strike} "
                f"(reason: {reason}, exchange=0)"
            )
            log_activity('reconciliation_autocorrect',
                f'🔧 Auto-corrected: removed {removed_lots} phantom '
                f'{side_state.get("side", "?").upper()} lots @ {strike} '
                f'(exchange shows 0)',
                self.session_id, 'warning',
                {'strike': strike, 'removed_lots': removed_lots, 'reason': reason})

    def _auto_correct_lot_mismatch(
        self, side_state: Dict, strike: float, target_lots: int, reason: str
    ):
        """
        Trim active positions at a strike to match exchange reality.
        Removes excess lots in LIFO order (most recently added first).
        """
        from .mmm_state import recompute_side_lots
        now = datetime.now(timezone.utc).isoformat()
        strike_tol = 1.0

        # Gather active positions at this strike, sorted by creation (LIFO)
        active_at_strike = [
            p for p in side_state.get('positions', [])
            if p.get('status') == 'active'
            and abs(p.get('strike', 0) - strike) < strike_tol
        ]
        # Sort by creation time descending (newest first for LIFO removal)
        active_at_strike.sort(
            key=lambda p: p.get('created_at', ''),
            reverse=True,
        )

        current_lots = sum(p.get('lots', 0) for p in active_at_strike)
        excess = current_lots - target_lots
        removed = 0

        for pos in active_at_strike:
            if excess <= 0:
                break
            pos_lots = pos.get('lots', 0)
            if pos_lots <= excess:
                # Close entire position
                pos['status'] = 'closed'
                pos['closed_at'] = now
                pos['close_reason'] = f'exchange_reconciliation:{reason}'
                excess -= pos_lots
                removed += pos_lots
            else:
                # Partial close — reduce lots
                pos['lots'] = pos_lots - excess
                removed += excess
                excess = 0

        if removed > 0:
            recompute_side_lots(side_state)
            log.warning(
                f"[{self.session_id}] AUTO-CORRECT: Trimmed {removed} excess "
                f"{side_state.get('side', '?').upper()} lots @ {strike} "
                f"(session had {current_lots}, exchange has {target_lots})"
            )
            log_activity('reconciliation_autocorrect',
                f'🔧 Auto-corrected: trimmed {removed} excess '
                f'{side_state.get("side", "?").upper()} lots @ {strike} '
                f'(session={current_lots} → {target_lots})',
                self.session_id, 'warning',
                {'strike': strike, 'removed': removed,
                 'old_lots': current_lots, 'new_lots': target_lots, 'reason': reason})

    def _auto_correct_frozen_mismatch(
        self, side_state: Dict, strike: float, target_lots: int, reason: str
    ):
        """
        Trim frozen (shifted) positions at a strike to match exchange reality.
        Removes excess in LIFO order.
        """
        from .mmm_state import recompute_side_lots
        now = datetime.now(timezone.utc).isoformat()
        strike_tol = 1.0

        shifted_at_strike = [
            p for p in side_state.get('positions', [])
            if p.get('status') == 'shifted'
            and abs(p.get('strike', 0) - strike) < strike_tol
        ]
        shifted_at_strike.sort(
            key=lambda p: p.get('shifted_at', p.get('created_at', '')),
            reverse=True,
        )

        current_lots = sum(p.get('lots', 0) for p in shifted_at_strike)
        excess = current_lots - target_lots
        removed = 0

        for pos in shifted_at_strike:
            if excess <= 0:
                break
            pos_lots = pos.get('lots', 0)
            if pos_lots <= excess:
                pos['status'] = 'closed'
                pos['closed_at'] = now
                pos['close_reason'] = f'exchange_reconciliation:{reason}'
                excess -= pos_lots
                removed += pos_lots
            else:
                pos['lots'] = pos_lots - excess
                removed += excess
                excess = 0

        if removed > 0:
            recompute_side_lots(side_state)
            log.warning(
                f"[{self.session_id}] AUTO-CORRECT (frozen): Trimmed {removed} excess "
                f"{side_state.get('side', '?').upper()} lots @ {strike} "
                f"(session had {current_lots}, exchange has {target_lots})"
            )
            log_activity('reconciliation_autocorrect',
                f'🔧 Auto-corrected (frozen): trimmed {removed} excess '
                f'{side_state.get("side", "?").upper()} lots @ {strike} '
                f'(session={current_lots} → {target_lots})',
                self.session_id, 'warning',
                {'strike': strike, 'removed': removed,
                 'old_lots': current_lots, 'new_lots': target_lots,
                 'reason': reason, 'position_type': 'frozen'})

    async def _reconcile_exchange_positions(self):
        """
        Query actual exchange positions and compare with session state.

        ISOLATION: Only checks symbols that THIS session manages.
        Does NOT look at or interfere with positions from other algos,
        manual trades, or other MMM sessions.

        Detects discrepancies like:
        - Session thinks position is open but exchange shows 0
        - Lot count mismatch between session state and exchange

        AUTO-CORRECTS when session > exchange (phantom positions):
        - MISSING_ON_EXCHANGE: marks all session positions at that strike as expired
        - SIZE_MISMATCH (exchange < session): trims session to match exchange
        - FROZEN_MISSING / FROZEN_MISMATCH: same for frozen positions

        Does NOT auto-add positions from exchange → session (could be from
        other algos, manual trades, or other MMM sessions).
        """
        session = self.session
        sid = self.session_id

        # Only reconcile every Nth heartbeat to avoid API spam
        # Exception: force reconciliation on resume or first heartbeat
        force_recon = session.pop('_force_recon', False)
        recon_counter = session.get('_recon_counter', 0) + 1
        session['_recon_counter'] = recon_counter
        if not force_recon and recon_counter % 5 != 1:  # Every 5th heartbeat (first, 6th, 11th, ...)
            return

        # ── One-time cleanup: remove ALL exchange_sync frozen positions.
        #    Auto-sync is now disabled — these are artifacts from the old
        #    code that imported other sessions'/algos' positions. ──
        if not session.get('_exchange_sync_cleaned_v2'):
            session['_exchange_sync_cleaned_v2'] = True
            for side_key in ['ce', 'pe']:
                side = session.get(side_key, {})
                original = side.get('frozen_positions', [])
                removed_lots = sum(
                    fp.get('lots', 0) for fp in original if fp.get('type') == 'exchange_sync'
                )
                if removed_lots > 0:
                    log.warning(
                        f"[{sid}] Cleanup: removing {removed_lots} exchange_sync "
                        f"{side_key.upper()} frozen lots from positions[] (auto-sync disabled)"
                    )
                    # Fix #23: Remove exchange_sync positions from positions[] (Unified Ledger)
                    _now = datetime.now(timezone.utc).isoformat()
                    exchange_sync_ids = {
                        fp.get('_pos_id')
                        for fp in original
                        if fp.get('type') == 'exchange_sync' and fp.get('_pos_id')
                    }
                    for _pos in side.get('positions', []):
                        if _pos.get('id') in exchange_sync_ids or _pos.get('type') == 'exchange_sync':
                            _pos['status'] = 'closed'
                            _pos['closed_at'] = _now
                    from .mmm_state import recompute_side_lots
                    recompute_side_lots(side)

        # ── Build the set of symbols THIS session owns ──
        session_symbols = set()
        expiry = session.get('params', {}).get('expiry', '')

        for side_key in ['ce', 'pe']:
            side = session.get(side_key, {})
            opt = 'call' if side_key == 'ce' else 'put'

            # Active symbol (from side state — may be stale if symbol wasn't updated)
            sym = side.get('symbol', '')
            if sym:
                session_symbols.add(sym)

            # CRITICAL FIX: Always include the CURRENT active strike symbol.
            # The symbol field may be stale (pointing to original entry strike)
            # if it wasn't updated during strike shifts. Build dynamically.
            active_strike = side.get('active_strike', 0)
            if active_strike > 0:
                active_sym = self.initializer.build_symbol(opt, 'BTC', active_strike, expiry)
                session_symbols.add(active_sym)
                # Update stale symbol field while we're at it
                if sym and sym != active_sym:
                    log.info(f"[{sid}] Reconciliation: fixing stale symbol {sym} → {active_sym}")
                    side['symbol'] = active_sym

            # Include ALL adjustment fill strikes (may differ from active strike)
            for fill in side.get('adjustment_fills', []):
                fill_strike = fill.get('strike', 0)
                if fill_strike > 0:
                    fill_sym = self.initializer.build_symbol(opt, 'BTC', fill_strike, expiry)
                    session_symbols.add(fill_sym)

            # Frozen positions may be at different strikes
            for frozen in side.get('frozen_positions', []):
                frozen_strike = frozen.get('strike', 0)
                if frozen_strike > 0:
                    fsym = self.initializer.build_symbol(opt, 'BTC', frozen_strike, expiry)
                    session_symbols.add(fsym)

        if not session_symbols:
            return

        try:
            rest = self._create_heartbeat_rest_client()

            # Fetch all open positions from the exchange
            resp = await rest._request_with_retry(
                method="GET",
                path="/v2/positions/margined",
            )

            positions = resp.get('result', [])
            if not isinstance(positions, list):
                positions = []

            # Build a map ONLY for symbols this session manages
            exchange_positions = {}
            for pos in positions:
                symbol = pos.get('product', {}).get('symbol', '') or pos.get('symbol', '')
                if symbol not in session_symbols:
                    continue  # ISOLATION: skip positions not owned by this session
                size = abs(float(pos.get('size', 0)))
                if size > 0:
                    exchange_positions[symbol] = {
                        'size': size,
                        'entry_price': float(pos.get('entry_price', 0)),
                        'side': 'short' if float(pos.get('size', 0)) < 0 else 'long',
                        'unrealized_pnl': float(pos.get('unrealized_pnl', 0)),
                    }

            # Compare with session state — per-symbol comparison
            discrepancies = []

            for side_key in ['ce', 'pe']:
                side = session.get(side_key, {})
                option_type = 'call' if side_key == 'ce' else 'put'
                active_strike = side.get('active_strike', 0)

                # CRITICAL FIX: Use symbol built from current active_strike,
                # not the stale side['symbol'] which may point to original entry.
                if active_strike > 0:
                    active_symbol = self.initializer.build_symbol(
                        option_type, 'BTC', active_strike, expiry)
                else:
                    active_symbol = side.get('symbol', '')

                if not active_symbol:
                    continue

                # Bug #6 fix: Compare active symbol lots (original + adj at active strike)
                # separately from frozen position lots at their own strikes.
                active_lots = side.get('original_lots', 0)
                for fill in side.get('adjustment_fills', []):
                    f_strike = fill.get('strike', active_strike)
                    if f_strike == active_strike:
                        active_lots += fill.get('lots', 0)

                exchange_pos = exchange_positions.get(active_symbol, {})
                exchange_size = exchange_pos.get('size', 0)

                # Subtract lots owned by other sessions at the same symbol
                # to avoid false discrepancy reports.
                other_lots_at_active = self._get_other_sessions_lots_at_symbol(active_symbol)
                effective_exchange_size = max(exchange_size - other_lots_at_active, 0)

                if active_lots > 0 and effective_exchange_size == 0 and exchange_size == 0:
                    discrepancies.append({
                        'side': side_key.upper(),
                        'type': 'MISSING_ON_EXCHANGE',
                        'detail': f"{side_key.upper()} active @ {active_strike}: session has {active_lots} lots but exchange shows 0",
                        'symbol': active_symbol,
                        'session_lots': active_lots,
                        'exchange_size': 0,
                        'auto_corrected': True,
                    })

                    # AUTO-CORRECT: Mark all session positions at this strike as
                    # expired/settled. Exchange has 0 → these are phantom positions
                    # (likely expired OTM or auto-settled by exchange).
                    self._auto_correct_missing_positions(
                        side_state=side,
                        strike=active_strike,
                        reason='exchange_shows_zero',
                    )

                elif abs(active_lots - effective_exchange_size) > 0.1 and active_lots > 0:
                    # Session has MORE than exchange (phantom lots)
                    if active_lots > effective_exchange_size:
                        discrepancies.append({
                            'side': side_key.upper(),
                            'type': 'SIZE_MISMATCH',
                            'detail': (
                                f"{side_key.upper()} active @ {active_strike}: session={active_lots} "
                                f"vs exchange={exchange_size} (other sessions={other_lots_at_active})"
                            ),
                            'symbol': active_symbol,
                            'session_lots': active_lots,
                            'exchange_size': exchange_size,
                            'auto_corrected': True,
                        })

                        # AUTO-CORRECT: Trim session lots to match exchange.
                        # Exchange is the source of truth.
                        target_lots = int(effective_exchange_size)
                        self._auto_correct_lot_mismatch(
                            side_state=side,
                            strike=active_strike,
                            target_lots=target_lots,
                            reason='exchange_has_fewer',
                        )
                    else:
                        # Exchange has MORE than session — do NOT auto-add
                        # (could be from other sources)
                        discrepancies.append({
                            'side': side_key.upper(),
                            'type': 'SIZE_MISMATCH',
                            'detail': (
                                f"{side_key.upper()} active @ {active_strike}: session={active_lots} "
                                f"vs exchange={exchange_size} (other sessions={other_lots_at_active})"
                            ),
                            'symbol': active_symbol,
                            'session_lots': active_lots,
                            'exchange_size': exchange_size,
                            'auto_corrected': False,
                        })

                # Check frozen positions at their own strikes
                # Aggregate frozen lots per strike first (multiple fills at same strike)
                frozen_by_strike = {}
                for frozen in side.get('frozen_positions', []):
                    f_strike = frozen.get('strike', 0)
                    f_lots = frozen.get('lots', 0)
                    if f_lots > 0 and f_strike > 0:
                        frozen_by_strike[f_strike] = frozen_by_strike.get(f_strike, 0) + f_lots

                for f_strike, total_frozen_lots in frozen_by_strike.items():
                    fsym = self.initializer.build_symbol(option_type, 'BTC', f_strike, expiry)
                    f_exchange = exchange_positions.get(fsym, {})
                    f_ex_size = f_exchange.get('size', 0)

                    # Subtract other sessions' lots at this frozen strike
                    other_frozen = self._get_other_sessions_lots_at_symbol(fsym)
                    effective_frozen_ex = max(f_ex_size - other_frozen, 0)

                    if total_frozen_lots > 0 and effective_frozen_ex == 0 and f_ex_size == 0:
                        discrepancies.append({
                            'side': side_key.upper(),
                            'type': 'FROZEN_MISSING',
                            'detail': f"{side_key.upper()} frozen @ {f_strike}: session={total_frozen_lots} but exchange=0",
                            'symbol': fsym,
                            'session_lots': total_frozen_lots,
                            'exchange_size': 0,
                            'auto_corrected': True,
                        })

                        # AUTO-CORRECT: Mark frozen positions at this strike as
                        # expired/settled (exchange shows 0).
                        self._auto_correct_missing_positions(
                            side_state=side,
                            strike=f_strike,
                            reason='frozen_exchange_shows_zero',
                        )

                    elif abs(total_frozen_lots - effective_frozen_ex) > 0.1:
                        if total_frozen_lots > effective_frozen_ex:
                            discrepancies.append({
                                'side': side_key.upper(),
                                'type': 'FROZEN_MISMATCH',
                                'detail': f"{side_key.upper()} frozen @ {f_strike}: session={total_frozen_lots} vs exchange={f_ex_size}",
                                'symbol': fsym,
                                'session_lots': total_frozen_lots,
                                'exchange_size': f_ex_size,
                                'auto_corrected': True,
                            })

                            # AUTO-CORRECT: Trim frozen lots to match exchange
                            target_frozen = int(effective_frozen_ex)
                            self._auto_correct_frozen_mismatch(
                                side_state=side,
                                strike=f_strike,
                                target_lots=target_frozen,
                                reason='frozen_exchange_has_fewer',
                            )
                        else:
                            # Exchange has more — do NOT auto-add
                            discrepancies.append({
                                'side': side_key.upper(),
                                'type': 'FROZEN_MISMATCH',
                                'detail': f"{side_key.upper()} frozen @ {f_strike}: session={total_frozen_lots} vs exchange={f_ex_size}",
                                'symbol': fsym,
                                'session_lots': total_frozen_lots,
                                'exchange_size': f_ex_size,
                                'auto_corrected': False,
                            })

                # Also check for exchange positions at strikes the session
                # doesn't know about at all (completely untracked)
                known_strikes = set()
                if active_strike > 0:
                    known_strikes.add(active_strike)
                known_strikes.update(frozen_by_strike.keys())
                for fill in side.get('adjustment_fills', []):
                    fs = fill.get('strike', 0)
                    if fs > 0:
                        known_strikes.add(fs)

                for sym, epos in exchange_positions.items():
                    # Check if this is our option type symbol
                    prefix = 'C-BTC-' if option_type == 'call' else 'P-BTC-'
                    if not sym.startswith(prefix):
                        continue
                    # Extract strike from symbol (e.g., C-BTC-68000-210226 → 68000)
                    try:
                        parts = sym.split('-')
                        ex_strike = float(parts[2])
                    except (IndexError, ValueError):
                        continue

                    if ex_strike not in known_strikes:
                        ex_size = epos.get('size', 0)
                        if ex_size > 0:
                            # Before auto-syncing, check if other sessions own
                            # these lots — avoid cross-session position adoption.
                            other_lots = self._get_other_sessions_lots_at_symbol(sym)
                            unowned = ex_size - other_lots

                            discrepancies.append({
                                'side': side_key.upper(),
                                'type': 'UNTRACKED_EXCHANGE_POSITION',
                                'detail': (
                                    f"{side_key.upper()} @ {ex_strike}: exchange has {ex_size} lots "
                                    f"but session has NO record (other sessions own {other_lots})"
                                ),
                                'symbol': sym,
                                'session_lots': 0,
                                'exchange_size': ex_size,
                                'other_sessions_lots': other_lots,
                            })

                            # NOTE: Auto-sync DISABLED for untracked positions.
                            # The exchange may hold positions from other algos,
                            # manual trades, or other MMM sessions. Log only.

            # §26.10: Orphan perp check — detect BTCUSD position on exchange
            # that the session doesn't know about (crash recovery).
            if is_perp_hedge_enabled(session):
                from .mmm_perp_hedge import BTCUSD_SYMBOL
                session_perp_lots = session.get('perp_hedge', {}).get('lots', 0)
                exchange_perp_size = 0
                exchange_perp_signed = 0
                for pos in positions:
                    sym = pos.get('product', {}).get('symbol', '') or pos.get('symbol', '')
                    if sym == BTCUSD_SYMBOL:
                        exchange_perp_signed = int(float(pos.get('size', 0)))
                        exchange_perp_size = abs(exchange_perp_signed)
                        break

                if exchange_perp_size > 0 and session_perp_lots == 0:
                    # Orphan detected: exchange has position, session doesn't
                    log.warning(
                        f"[{sid}] ORPHAN PERP DETECTED: Exchange has "
                        f"{exchange_perp_signed:+d} BTCUSD lots but session "
                        f"shows 0. Closing orphan position."
                    )
                    discrepancies.append({
                        'side': 'PERP',
                        'type': 'ORPHAN_PERP_POSITION',
                        'detail': (
                            f"BTCUSD orphan: exchange={exchange_perp_signed:+d} lots, "
                            f"session=0. Auto-closing."
                        ),
                        'symbol': BTCUSD_SYMBOL,
                        'session_lots': 0,
                        'exchange_size': exchange_perp_size,
                    })
                    try:
                        close_result = await close_all_perp(
                            session, self.executor,
                            f'orphan_cleanup (exchange had {exchange_perp_signed:+d} lots)'
                        )
                        # Force session to reflect what we just found+closed
                        if not close_result.get('success'):
                            log.error(
                                f"[{sid}] Orphan perp close FAILED: "
                                f"{close_result.get('reason', 'unknown')}"
                            )
                    except Exception as oe:
                        log.error(f"[{sid}] Orphan perp close exception: {oe}")

                elif exchange_perp_size == 0 and session_perp_lots != 0:
                    # Session thinks it has a position but exchange disagrees
                    log.warning(
                        f"[{sid}] PERP STATE MISMATCH: Session shows "
                        f"{session_perp_lots:+d} lots but exchange has 0. "
                        f"Resetting session perp state."
                    )
                    discrepancies.append({
                        'side': 'PERP',
                        'type': 'PHANTOM_PERP_POSITION',
                        'detail': (
                            f"BTCUSD phantom: session={session_perp_lots:+d} lots, "
                            f"exchange=0. Resetting state."
                        ),
                        'symbol': BTCUSD_SYMBOL,
                        'session_lots': session_perp_lots,
                        'exchange_size': 0,
                    })
                    perp = session.get('perp_hedge', {})
                    perp['lots'] = 0
                    perp['avg_entry'] = 0.0
                    perp['unrealized_pnl'] = 0.0
                    perp['target_lots'] = 0

            # Store last reconciliation result (only our symbols)
            session['last_reconciliation'] = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'session_symbols': list(session_symbols),
                'exchange_positions': {k: v for k, v in exchange_positions.items()},
                'discrepancies': discrepancies,
                'matched_count': len(exchange_positions),
            }

            # Count auto-corrected discrepancies
            auto_corrected = [d for d in discrepancies if d.get('auto_corrected')]

            if discrepancies:
                for d in discrepancies:
                    severity = 'error' if d.get('auto_corrected') else 'warning'
                    prefix = '🔧 AUTO-CORRECTED' if d.get('auto_corrected') else '⚠️ MISMATCH'
                    log.warning(f"[{sid}] RECONCILIATION: {prefix} — {d['detail']}")
                    log_activity('reconciliation_warning',
                        f"Position reconciliation: {prefix} — {d['detail']}",
                        session_id=sid, severity=severity,
                        details=d)

                # If any auto-corrections happened, persist the updated state
                if auto_corrected:
                    log.warning(
                        f"[{sid}] RECONCILIATION: {len(auto_corrected)} discrepancies "
                        f"auto-corrected — saving updated session state"
                    )
                    self._save_my_session(session)
            else:
                log.debug(f"[{sid}] Reconciliation OK — {len(exchange_positions)} matched positions")

        except Exception as e:
            log.warning(f"[{sid}] Reconciliation failed: {e}")

    # =========================================================================
    # §6: Premium Fetching
    # =========================================================================

    async def _fetch_premiums(self) -> tuple:
        """
        Fetch current CE and PE premiums at active strikes.
        Uses mark price for monitoring (§15.5).
        Creates a FRESH REST client per heartbeat to avoid event loop binding issues.

        T4-4 PRICE BASIS AUDIT: mark price is intentional here.
        - Trigger detection uses mark price (conservative: fires only when market consensus moves)
        - P&L computation uses mark price (matches exchange settlement value)
        - close-at-5 uses BID price (see _make_bid_fetch_fn) — more accurate for
          determining what the market will actually pay for a buyback at near-zero premium
        - Shift detection uses the ce_now/pe_now values from this function (i.e. mark price)
          which is correct: we want to shift when mark price drops below threshold, not just
          when bid drops (bid can temporarily lag mark in illiquid options)
        This separation (mark for signaling, bid for close execution) is intentional and correct.
        """
        try:
            ce_state = self.session.get('ce', {})
            pe_state = self.session.get('pe', {})
            ce_strike = ce_state.get('active_strike', 0)
            pe_strike = pe_state.get('active_strike', 0)

            if ce_strike == 0 or pe_strike == 0:
                return None, None

            expiry = self.session.get('params', {}).get('expiry', '')

            # Use initializer's chain service for premium data
            ce_symbol = self.initializer.build_symbol(
                'call', 'BTC', ce_strike, expiry,
            )
            pe_symbol = self.initializer.build_symbol(
                'put', 'BTC', pe_strike, expiry,
            )

            # Create a FRESH REST client for this heartbeat cycle
            # (httpx.AsyncClient binds to one event loop; can't reuse across loops)
            rest = self._create_heartbeat_rest_client()

            # Fetch option tickers for mark prices
            ce_resp = await rest._request_with_retry(
                method="GET", path=f"/v2/tickers/{ce_symbol}",
            )
            pe_resp = await rest._request_with_retry(
                method="GET", path=f"/v2/tickers/{pe_symbol}",
            )

            ce_data = ce_resp.get('result', ce_resp)
            pe_data = pe_resp.get('result', pe_resp)

            ce_mark = float(ce_data.get('mark_price', 0) or 0)
            pe_mark = float(pe_data.get('mark_price', 0) or 0)

            # Extract IV data for regime controls (zero extra API calls)
            # Delta Exchange returns IV as:
            #   - 'mark_vol' (top level, decimal, e.g. 0.3664 = 36.64%)
            #   - quotes.mark_iv (string, same value)
            # Convert to percentage for regime engine.
            try:
                ce_iv_raw = ce_data.get('mark_vol') or ce_data.get('quotes', {}).get('mark_iv') or 0
                ce_iv = float(ce_iv_raw) * 100  # 0.3664 → 36.64
            except (ValueError, TypeError):
                ce_iv = 0.0
            try:
                pe_iv_raw = pe_data.get('mark_vol') or pe_data.get('quotes', {}).get('mark_iv') or 0
                pe_iv = float(pe_iv_raw) * 100  # 0.3664 → 36.64
            except (ValueError, TypeError):
                pe_iv = 0.0
            self._last_iv_data = {'ce_iv': ce_iv, 'pe_iv': pe_iv}

            # Store the rest client for prefetch to reuse in this heartbeat
            self._heartbeat_rest = rest

            return ce_mark, pe_mark

        except Exception as e:
            log.error(f"Error fetching premiums: {e}")
            return None, None

    async def _fetch_premiums_with_fallback(self):
        """
        Circuit-breaker-aware premium fetch with per-side fallback (Fix #12).

        If CE fetches OK but PE fails (or vice versa), the healthy side gets fresh
        data and the failed side falls back to cache (marked as stale).
        This prevents a single-side network issue from blocking heartbeat processing
        for the healthy side.

        Returns:
            (ce_premium, pe_premium, ok: bool)
            ok=False only when BOTH sides have no usable price (miss beat).
            ok=True with a stale flag on session means partial per-side data.
        """
        sid = self.session_id
        session = self.session

        # Clear stale flags from previous heartbeat
        session.pop('_ce_premium_stale', None)
        session.pop('_pe_premium_stale', None)

        # --- Check circuit breaker ---
        if not self._circuit.allow_request():
            log.warning(
                f"[{sid}] Circuit OPEN (depth={self._circuit.open_depth}) — "
                f"skipping exchange call, returning cached"
            )
            return None, None, False

        try:
            ce_now, pe_now = await self._fetch_premiums()
            if ce_now is not None and pe_now is not None and ce_now > 0 and pe_now > 0:
                self._circuit.record_success()
                return ce_now, pe_now, True

            # Primary ticker API returned partial or zero values.
            # Fix #12: handle per-side — try order-book fallback for each side separately.
            ce_fb, pe_fb = await self._fetch_premiums_orderbook_fallback()

            # Resolve CE price
            if ce_now is not None and ce_now > 0:
                ce_final = ce_now
            elif ce_fb is not None and ce_fb > 0:
                ce_final = ce_fb
            else:
                ce_final = None  # need cache

            # Resolve PE price
            if pe_now is not None and pe_now > 0:
                pe_final = pe_now
            elif pe_fb is not None and pe_fb > 0:
                pe_final = pe_fb
            else:
                pe_final = None  # need cache

            # Both resolved freshly
            if ce_final is not None and pe_final is not None:
                self._circuit.record_success()
                return ce_final, pe_final, True

            # One side failed: fall back to cache for that side
            cache = getattr(self, '_premium_cache', {}) or {}
            ce_strike = float(session.get('ce', {}).get('active_strike', 0))
            pe_strike = float(session.get('pe', {}).get('active_strike', 0))

            if ce_final is None:
                cached_ce = cache.get((ce_strike, 'call'))
                if cached_ce:
                    log.warning(
                        f"[{sid}] Fix #12: CE premium fetch failed — using cached "
                        f"price {cached_ce:.2f} (stale). PE fresh: "
                        f"{pe_final:.2f if pe_final else 'N/A'}"
                    )
                    session['_ce_premium_stale'] = True
                    ce_final = cached_ce

            if pe_final is None:
                cached_pe = cache.get((pe_strike, 'put'))
                if cached_pe:
                    log.warning(
                        f"[{sid}] Fix #12: PE premium fetch failed — using cached "
                        f"price {cached_pe:.2f} (stale). CE fresh: "
                        f"{ce_final:.2f if ce_final else 'N/A'}"
                    )
                    session['_pe_premium_stale'] = True
                    pe_final = cached_pe

            if ce_final is not None and pe_final is not None:
                # At least partial fresh data — record circuit as success for
                # the side that worked, but don't reset failure count fully.
                self._circuit.record_success()
                return ce_final, pe_final, True

            # Both sources failed entirely
            self._circuit.record_failure('all premium sources returned invalid data')
            return None, None, False

        except Exception as e:
            self._circuit.record_failure(str(e))
            log.error(f"[{sid}] Premium fetch exception: {e}")
            return None, None, False

    async def _fetch_premiums_orderbook_fallback(self):
        """
        Fallback: derive CE and PE premiums from order-book mid-price
        when the mark-price ticker returns zero or is unavailable.

        Order-book mid = (best_bid + best_ask) / 2
        Returns (ce_mid, pe_mid) or (None, None) on failure.
        """
        try:
            ce_state = self.session.get('ce', {})
            pe_state = self.session.get('pe', {})
            ce_strike = ce_state.get('active_strike', 0)
            pe_strike = pe_state.get('active_strike', 0)
            expiry = self.session.get('params', {}).get('expiry', '')

            if not ce_strike or not pe_strike:
                return None, None

            ce_symbol = self.initializer.build_symbol('call', 'BTC', ce_strike, expiry)
            pe_symbol = self.initializer.build_symbol('put', 'BTC', pe_strike, expiry)

            rest = getattr(self, '_heartbeat_rest', None) or self._create_heartbeat_rest_client()

            async def _mid(symbol):
                try:
                    resp = await rest._request_with_retry(
                        method="GET", path=f"/v2/orderbook/{symbol}",
                        params={"depth": 1},
                    )
                    data = resp.get('result', resp)
                    bids = data.get('buy', [])
                    asks = data.get('sell', [])
                    best_bid = float(bids[0][0]) if bids else 0.0
                    best_ask = float(asks[0][0]) if asks else 0.0
                    if best_bid > 0 and best_ask > 0:
                        return (best_bid + best_ask) / 2.0
                    elif best_bid > 0:
                        return best_bid
                    elif best_ask > 0:
                        return best_ask
                    return None
                except Exception:
                    return None

            import asyncio as _asyncio
            ce_mid, pe_mid = await _asyncio.gather(_mid(ce_symbol), _mid(pe_symbol))
            return ce_mid, pe_mid

        except Exception as e:
            log.warning(f"[{self.session_id}] Order-book fallback failed: {e}")
            return None, None

    def _create_heartbeat_rest_client(self):
        """Create a fresh AsyncDeltaClient bound to the monitor's event loop."""
        from bot.api.async_delta_client import AsyncDeltaClient
        from config.loader import get_api_credentials

        creds = get_api_credentials()
        testnet = creds.get('testnet', False) or False

        return AsyncDeltaClient(
            api_key=creds.get('api_key', ''),
            api_secret=creds.get('api_secret', ''),
            testnet=testnet,
        )

    async def _prefetch_all_premiums(self, ce_now: float, pe_now: float):
        """Pre-fetch mark prices for all strikes the engine may query.

        Caches them so that _make_fetch_fn can return a sync lookup
        without needing to call async API methods.
        """
        session = self.session
        cache: Dict[tuple, float] = {}
        expiry = session.get('params', {}).get('expiry', '')

        # Collect all unique (strike, option_type) pairs from session
        strike_pairs = set()
        for side_key in ['ce', 'pe']:
            side = session.get(side_key, {})
            opt = 'call' if side_key == 'ce' else 'put'
            active = side.get('active_strike', 0)
            if active:
                strike_pairs.add((float(active), opt))
            for fill in side.get('adjustment_fills', []):
                s = fill.get('strike', active)
                if s:
                    strike_pairs.add((float(s), opt))
            for frozen in side.get('frozen_positions', []):
                s = frozen.get('strike', 0)
                if s:
                    strike_pairs.add((float(s), opt))

        # Seed the cache with already-fetched active-strike premiums
        ce_state = session.get('ce', {})
        pe_state = session.get('pe', {})
        if ce_state.get('active_strike'):
            cache[(float(ce_state['active_strike']), 'call')] = ce_now
        if pe_state.get('active_strike'):
            cache[(float(pe_state['active_strike']), 'put')] = pe_now

        # Fetch any remaining strikes not yet in cache — Bug #12 fix: parallel
        rest = getattr(self, '_heartbeat_rest', None) or self._create_heartbeat_rest_client()
        to_fetch = [(s, o) for s, o in strike_pairs if (s, o) not in cache]

        bid_cache: Dict[tuple, float] = {}
        if to_fetch:
            async def _fetch_one(strike, opt):
                try:
                    symbol = self.initializer.build_symbol(
                        opt, 'BTC', strike, expiry,
                    )
                    # Fetch both ticker (mark) and orderbook (bid/ask) for close_at_5 accuracy
                    resp = await rest._request_with_retry(
                        method="GET", path=f"/v2/tickers/{symbol}",
                    )
                    data = resp.get('result', resp)
                    mark_price = float(data.get('mark_price', 0))
                    
                    # Also fetch orderbook for bid price (used by close_at_5)
                    bid_price = 0.0
                    try:
                        ob_resp = await rest._request_with_retry(
                            method="GET", path=f"/v2/orderbook/{symbol}",
                            params={"depth": 1},
                        )
                        ob_data = ob_resp.get('result', ob_resp)
                        bids = ob_data.get('buy', [])
                        if bids:
                            bid_price = float(bids[0][0])
                    except Exception:
                        pass  # Bid fetch failure is non-critical, use mark as fallback
                    
                    return (strike, opt), mark_price, bid_price
                except Exception as e:
                    log.warning(f"Prefetch failed for {opt}@{strike}: {e}")
                    return (strike, opt), 0, 0

            results = await asyncio.gather(
                *[_fetch_one(s, o) for s, o in to_fetch],
                return_exceptions=True,
            )

            for r in results:
                if isinstance(r, Exception):
                    continue
                key, mark_price, bid_price = r
                cache[key] = mark_price
                # Store bid price: use bid if available, else fall back to mark
                bid_cache[key] = bid_price if bid_price > 0 else mark_price

        self._premium_cache = cache
        self._bid_cache = getattr(self, '_bid_cache', {})
        self._bid_cache.update(bid_cache)

    async def _fetch_spot_price(self) -> float:
        """Fetch current BTC spot price."""
        try:
            return self.initializer.get_spot_price()
        except Exception:
            return 0.0

    def _make_fetch_fn(self):
        """Create a premium fetch function for engine/safety calls.

        Uses the premium cache populated by _prefetch_all_premiums() at the
        start of each heartbeat so that engine code (which expects a sync
        callback) doesn't need to await async API calls.
        """
        cache = getattr(self, '_premium_cache', {})

        def fetch(strike, option_type):
            key = (float(strike), option_type)
            if key in cache:
                return cache[key]
            # Bug #14 fix: cache miss should be rare after Bug #12 parallel prefetch.
            # Instead of creating a disposable event loop (which risks conflicts
            # with the main loop), log a warning and attempt a sync fallback
            # only once, caching the result to avoid repeat misses.
            log.warning(
                f"Premium cache miss for {option_type}@{strike}. "
                f"This should not happen — check _prefetch_all_premiums coverage."
            )
            try:
                expiry = self.session.get('params', {}).get('expiry', '')
                symbol = self.initializer.build_symbol(
                    option_type, 'BTC', strike, expiry,
                )
                # Use a fresh, isolated loop for the one-off fetch
                loop = asyncio.new_event_loop()
                try:
                    from bot.api.async_delta_client import AsyncDeltaClient
                    from config.loader import get_api_credentials
                    creds = get_api_credentials()
                    rest = AsyncDeltaClient(
                        api_key=creds.get('api_key', ''),
                        api_secret=creds.get('api_secret', ''),
                        testnet=creds.get('testnet', False) or False,
                    )
                    resp = loop.run_until_complete(
                        rest._request_with_retry(
                            method="GET", path=f"/v2/tickers/{symbol}",
                        )
                    )
                    data = resp.get('result', resp)
                    mark = float(data.get('mark_price', 0))
                    cache[key] = mark
                    return mark
                finally:
                    loop.close()
            except Exception as e:
                log.error(f"Cache miss fallback fetch failed for {option_type}@{strike}: {e}")
                cache[key] = 0  # Cache the failure to prevent repeated attempts
                return 0
        return fetch

    def _make_bid_fetch_fn(self):
        """Create a bid-price fetch function for close_at_5 decisions.

        Uses bid prices from _bid_cache (populated by _prefetch_all_premiums).
        Bid price is more accurate for determining if a position is "cheap"
        because it represents what the market is willing to pay, not a
        theoretical mark price that can lag reality.

        Falls back to mark price if bid not available.
        """
        bid_cache = getattr(self, '_bid_cache', {})
        mark_cache = getattr(self, '_premium_cache', {})

        def fetch(strike, option_type):
            key = (float(strike), option_type)
            # Prefer bid price, fall back to mark
            if key in bid_cache and bid_cache[key] > 0:
                return bid_cache[key]
            if key in mark_cache:
                return mark_cache[key]
            # If neither cache has it, return 0 (position won't qualify for close)
            log.warning(f"Bid cache miss for {option_type}@{strike}, skipping close check")
            return 0
        return fetch

    def _get_minutes_to_expiry(self) -> Optional[float]:
        """Calculate minutes remaining until expiry (5:30 PM IST = 12:00 UTC)."""
        expiry_time = self.session.get('expiry_time')
        if not expiry_time:
            # Fallback: compute from DDMMYYYY expiry date if expiry_time not set
            expiry_date = self.session.get('expiry') or self.session.get('params', {}).get('expiry', '')
            if expiry_date:
                try:
                    from .mmm_initializer import expiry_to_utc_datetime
                    expiry_time = expiry_to_utc_datetime(expiry_date)
                    self.session['expiry_time'] = expiry_time  # cache for future beats
                except (ValueError, TypeError):
                    return None
            else:
                return None
        try:
            exp = datetime.fromisoformat(expiry_time)
            # Fix #14: normalize expiry to timezone-aware UTC before comparison.
            # Handles both old naive UTC strings and new timezone-aware strings.
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = (exp - now).total_seconds() / 60
            return max(delta, 0)
        except (ValueError, TypeError):
            return None

    def _update_analytics_exposure(self):
        """Update analytics tracking for exposure metrics (no trading logic impact)."""
        session = self.session
        analytics = session.setdefault('analytics', {})
        
        # Current exposure
        ce_lots = session.get('ce', {}).get('total_lots', 0)
        pe_lots = session.get('pe', {}).get('total_lots', 0)
        combined_lots = ce_lots + pe_lots
        
        # Track peak exposure
        if ce_lots > analytics.get('max_ce_lots', 0):
            analytics['max_ce_lots'] = ce_lots
            analytics['peak_risk_timestamp'] = datetime.now(timezone.utc).isoformat()
        
        if pe_lots > analytics.get('max_pe_lots', 0):
            analytics['max_pe_lots'] = pe_lots
            if not analytics.get('peak_risk_timestamp'):
                analytics['peak_risk_timestamp'] = datetime.now(timezone.utc).isoformat()
        
        if combined_lots > analytics.get('max_combined_lots', 0):
            analytics['max_combined_lots'] = combined_lots
            analytics['peak_risk_timestamp'] = datetime.now(timezone.utc).isoformat()

    def _update_analytics_pnl_milestones(self, pnl: Dict):
        """Update P&L milestone tracking (no trading logic impact)."""
        session = self.session
        analytics = session.setdefault('analytics', {})
        
        net_pnl = pnl.get('net_pnl', 0)
        
        # Track time to first profit
        if net_pnl > 0 and analytics.get('time_to_first_profit') is None:
            start_time = analytics.get('session_start_time')
            if start_time:
                try:
                    start_dt = datetime.fromisoformat(start_time)
                    if start_dt.tzinfo is None:  # Fix #14: normalize naive → aware
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - start_dt).total_seconds()
                    analytics['time_to_first_profit'] = elapsed
                except (ValueError, TypeError):
                    pass

        # Track time to peak P&L
        peak = session.get('peak_pnl', 0)
        if net_pnl >= peak and peak > 0:
            start_time = analytics.get('session_start_time')
            if start_time:
                try:
                    start_dt = datetime.fromisoformat(start_time)
                    if start_dt.tzinfo is None:  # Fix #14: normalize naive → aware
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - start_dt).total_seconds()
                    analytics['time_to_peak_pnl'] = elapsed
                except (ValueError, TypeError):
                    pass
        
        # Track max drawdown from peak
        if peak > 0:
            drawdown = peak - net_pnl
            if drawdown > analytics.get('max_drawdown_from_peak', 0):
                analytics['max_drawdown_from_peak'] = drawdown
                analytics['max_drawdown_timestamp'] = datetime.now(timezone.utc).isoformat()

    def _update_analytics_delta(self, portfolio_delta: float):
        """Update delta tracking (no trading logic impact)."""
        session = self.session
        analytics = session.setdefault('analytics', {})
        
        abs_delta = abs(portfolio_delta)
        if abs_delta > analytics.get('max_abs_delta', 0):
            analytics['max_abs_delta'] = abs_delta
            analytics['max_abs_delta_timestamp'] = datetime.now(timezone.utc).isoformat()

    async def _calculate_portfolio_delta(self) -> float:
        """Calculate current portfolio delta from all positions.
        
        Portfolio delta = sum of (position_lots × greek_delta × LOT_SIZE_BTC × multiplier)
        multiplier: short CE = -1, short PE = +1
        
        Returns:
            float: Portfolio delta (positive = net long, negative = net short)
        """
        session = self.session
        expiry = session.get('params', {}).get('expiry', '')
        if not expiry:
            return 0.0
        
        try:
            from .mmm_initializer import get_initializer
            from config.loader import get_api_credentials
            from bot.api.async_delta_client import AsyncDeltaClient
            import asyncio
            
            initializer = get_initializer()
            
            # Collect all positions
            position_map = {}  # key=(strike, opt_type) -> lots
            for side_key in ['ce', 'pe']:
                side = session.get(side_key, {})
                if not side:
                    continue
                opt = 'call' if side_key == 'ce' else 'put'
                
                # Active strike positions
                active_strike = side.get('active_strike', 0)
                orig_lots = side.get('original_lots', 0)
                if active_strike and orig_lots > 0:
                    key = (float(active_strike), opt)
                    position_map[key] = position_map.get(key, 0) + orig_lots
                
                # Adjustment fills
                for fill in side.get('adjustment_fills', []):
                    fill_strike = float(fill.get('strike', active_strike) or active_strike)
                    fill_lots = fill.get('lots', 0)
                    if fill_strike and fill_lots > 0:
                        key = (fill_strike, opt)
                        position_map[key] = position_map.get(key, 0) + fill_lots
                
                # Frozen positions
                for frozen in side.get('frozen_positions', []):
                    f_strike = float(frozen.get('strike', 0))
                    f_lots = frozen.get('lots', 0)
                    if f_strike and f_lots > 0:
                        key = (f_strike, opt)
                        position_map[key] = position_map.get(key, 0) + f_lots
            
            if not position_map:
                self._last_gamma_data = {
                    'portfolio_gamma': 0.0,
                    'positions': [],
                }
                return 0.0

            # Fetch Greeks for all positions from exchange tickers
            # NOTE: Position lots come from session data only (this algo's
            # positions).  Session properly tracks buybacks via LIFO removals
            # in wind-down and close-at-5.  No exchange correction needed.
            creds = get_api_credentials()
            client = AsyncDeltaClient(
                api_key=creds.get('api_key', ''),
                api_secret=creds.get('api_secret', ''),
                testnet=creds.get('testnet', False) or False,
            )

            async def fetch_all():
                tasks = []
                keys = []
                for (strike, opt) in position_map:
                    symbol = initializer.build_symbol(opt, 'BTC', strike, expiry)
                    keys.append((strike, opt))
                    tasks.append(
                        client._request_with_retry(
                            method="GET", path=f"/v2/tickers/{symbol}",
                        )
                    )
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return list(zip(keys, results))
            
            ticker_results = await fetch_all()
            
            # Calculate portfolio delta AND extract gamma for regime controls
            portfolio_delta = 0.0
            portfolio_gamma = 0.0
            gamma_positions = []

            def _safe_greek(val):
                """Safely convert a greek value to float (exchange may return str/None/list)."""
                if val is None:
                    return 0.0
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, str):
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return 0.0
                return 0.0

            for (strike, opt), resp in ticker_results:
                if isinstance(resp, Exception):
                    continue

                result = resp.get('result', resp) if isinstance(resp, dict) else {}
                if isinstance(result, list):
                    result = result[0] if result else {}
                greeks = result.get('greeks', {}) or {}
                greek_delta = _safe_greek(greeks.get('delta', 0))
                greek_gamma = _safe_greek(greeks.get('gamma', 0))

                lots = int(position_map.get((strike, opt), 0))
                # multiplier: ALWAYS -1 for short positions (we are the seller)
                # Fix #26.1: short CE delta = -(+call_delta), short PE delta = -(-put_delta) = +
                # Old bug: put multiplier was +1, which preserved the negative put delta
                # instead of flipping it. This made portfolio_delta too negative,
                # causing the perp to BUY (go long) when it should have SOLD (gone short).
                multiplier = -1  # short position always negates the exchange delta
                position_delta = greek_delta * lots * LOT_SIZE_BTC * multiplier
                portfolio_delta += position_delta

                # Gamma: accumulate absolute gamma exposure (short options = negative gamma)
                position_gamma = greek_gamma * lots * LOT_SIZE_BTC
                portfolio_gamma += position_gamma
                if greek_gamma:
                    gamma_positions.append((greek_gamma, lots, opt))

            # Store gamma data for regime engine (zero extra API calls)
            self._last_gamma_data = {
                'portfolio_gamma': portfolio_gamma,
                'positions': gamma_positions,
            }

            return portfolio_delta
            
        except Exception as e:
            log.warning(f"[{self.session_id}] Failed to calculate portfolio delta: {e}")
            return 0.0

    def _emit_heartbeat_data(self, ce_now: float, pe_now: float):
        """Emit heartbeat WebSocket event with premium_map for live prices."""
        session = self.session
        ce_trigger = session.get('ce', {}).get('trigger_snapshot', {}).get(
            _strike_key(session.get('ce', {}).get('active_strike', 0)), 0
        )
        pe_trigger = session.get('pe', {}).get('trigger_snapshot', {}).get(
            _strike_key(session.get('pe', {}).get('active_strike', 0)), 0
        )

        realized = session.get('realized_pnl', 0)
        unrealized = session.get('unrealized_pnl', 0)

        # Build premium_map from _premium_cache for frontend position pricing
        # Format: {"70600:call": 95.5, "66400:put": 107.5, ...}
        premium_map = {}
        cache = getattr(self, '_premium_cache', {})
        for (strike, opt_type), price in cache.items():
            key = f"{int(strike)}:{opt_type}"
            premium_map[key] = price

        # Also ensure active strikes are in the map from this heartbeat's fetch
        ce_active = session.get('ce', {}).get('active_strike')
        pe_active = session.get('pe', {}).get('active_strike')
        if ce_active and ce_now:
            premium_map[f"{int(ce_active)}:call"] = ce_now
        if pe_active and pe_now:
            premium_map[f"{int(pe_active)}:put"] = pe_now

        # Persist premium_map in session for page-reload resilience
        session['_premium_map'] = premium_map

        # Get portfolio delta from session (calculated in heartbeat)
        portfolio_delta = session.get('portfolio_delta', 0)

        # Build regime summary for heartbeat payload
        regime_data = {
            'regime_action': session.get('_regime_action', 'NORMAL'),
            'vol_regime': session.get('_vol_regime', 'NORMAL'),
            'gamma_regime': session.get('_gamma_regime', 'NORMAL'),
            'trend_regime': session.get('_trend_regime', 'NORMAL'),
            'dollar_gamma': session.get('_portfolio_dollar_gamma', 0),
            'trend_move_pct': session.get('_trend_move_pct', 0),
            'vol_regime_score': session.get('_vol_regime_score', 0),
        }

        emit_heartbeat(
            self.session_id, ce_now, pe_now,
            ce_trigger, pe_trigger,
            session.get('strategy_status', 'UNKNOWN'),
            realized + unrealized, realized,
            premium_map=premium_map,
            adaptive_tier=session.get('_adaptive_tier', ''),
            wind_down_active=is_wind_down_active(session),
            portfolio_delta=portfolio_delta,
            margin_data=getattr(self, '_last_margin_snapshot', None),
            regime_data=regime_data,
            perp_hedge_data=get_perp_summary(session),
        )


# =============================================================================
# Monitor Registry — track all active monitors
# =============================================================================

_monitors: Dict[str, MMMMonitor] = {}

# C-1 fix: module-level lock protecting all _monitors dict access.
# The per-instance self._session_lock was previously unused; this module-level
# lock guards the registry itself across Flask threads, watchdog thread, and
# monitor stop threads.
_monitors_lock = threading.Lock()


def start_session_monitor(session_id: str, session: Dict) -> MMMMonitor:
    """Start a monitor for a session. Thread-safe (C-1 fix)."""
    # Check-then-stop under lock to prevent TOCTOU race
    with _monitors_lock:
        existing = _monitors.pop(session_id, None)

    if existing:
        log.warning(f"Monitor already exists for {session_id}, stopping old one")
        existing.stop('Replaced by new monitor')  # Outside lock — can take time

    monitor = MMMMonitor(session_id, session)

    with _monitors_lock:
        _monitors[session_id] = monitor

    monitor.start()
    return monitor


def stop_session_monitor(session_id: str, reason: str = 'Stopped'):
    """Stop a session's monitor. Thread-safe (C-1 fix)."""
    # Pop atomically under lock so no concurrent thread can also pop it
    with _monitors_lock:
        monitor = _monitors.pop(session_id, None)

    if monitor:
        monitor.stop(reason)  # Outside lock — stop() can take time


def pause_session_monitor(session_id: str, reason: str = 'Paused'):
    """Pause a session's monitor. Thread-safe (C-1 fix)."""
    with _monitors_lock:
        monitor = _monitors.get(session_id)
    if monitor:
        monitor.pause(reason)


def resume_session_monitor(session_id: str, reason: str = 'Resumed'):
    """Resume a session's monitor. Thread-safe (C-1 fix)."""
    with _monitors_lock:
        monitor = _monitors.get(session_id)
    if monitor:
        monitor.resume(reason)


def get_monitor(session_id: str) -> Optional[MMMMonitor]:
    """Get an existing monitor. Thread-safe (C-1 fix)."""
    with _monitors_lock:
        return _monitors.get(session_id)


def get_all_monitors() -> Dict[str, MMMMonitor]:
    """Get a snapshot of all active monitors. Thread-safe (C-1 fix)."""
    with _monitors_lock:
        return dict(_monitors)


def _save_session(session: Dict, my_generation: int = 0):
    """Persist session to storage, preserving hot-reload param updates.

    The heartbeat never modifies session['params'].  However, the user may
    update params via the Settings API (PATCH /params) while a heartbeat is
    in-flight.  If we blindly save the monitor's in-memory copy, those
    API-driven param changes get overwritten.  To prevent this, we re-read
    the latest params from storage right before saving so hot-reload
    updates are never lost.

    H-4 fix: my_generation guards against stale saves from old monitor threads
    that didn't exit cleanly after a watchdog restart. If the stored generation
    is higher than this monitor's generation, the save is rejected.
    """
    # Guard: if the monitor has been stopped (e.g. by watchdog restart),
    # do NOT save — an in-flight heartbeat completing after stop() could
    # overwrite the watchdog's freshly-saved RUNNING status with STOPPED.
    if session.get('_save_disabled'):
        log.warning(
            f"[{session.get('session_id')}] _save_session blocked: "
            f"monitor was stopped (save_disabled flag set)"
        )
        return
    try:
        storage = get_storage()
        sid = session.get('session_id')
        if sid:
            stored = storage.get_session(sid)
            if stored:
                # H-4 fix: generation check — reject save from stale monitor thread
                if my_generation > 0:
                    stored_gen = stored.get('_monitor_generation', 0)
                    if stored_gen > my_generation:
                        log.warning(
                            f"[{sid}] _save_session blocked: stale monitor "
                            f"gen={my_generation} < stored_gen={stored_gen}"
                        )
                        return
                if 'params' in stored:
                    session['params'] = stored['params']
                    # BUG FIX (mmm01mar26-1): Re-apply session-level auto-trigger overrides
                    # that were set in-memory but not yet persisted to params_json.
                    # Specifically: ATM wind-down trigger sets wind_down_enabled=True in-memory,
                    # but the line above just replaced session['params'] with the STORED copy
                    # (which still has wind_down_enabled=False). Re-apply the override so it
                    # gets written to DB in this very save call.
                    if session.get('_atm_wind_down_triggered'):
                        session['params']['wind_down_enabled'] = True
                    elif '_atm_prev_wind_down_enabled' in session:
                        # P1-C fix: ATM flag was just cleared (both-sides-closed).
                        # The stored params still have wind_down_enabled=True from when the
                        # trigger originally persisted it.  Restore the original value so the
                        # DB is left clean for the next session round.
                        session['params']['wind_down_enabled'] = session.pop('_atm_prev_wind_down_enabled')
        storage.save_session(session)
    except Exception as e:
        log.error(f"Failed to save session: {e}")
