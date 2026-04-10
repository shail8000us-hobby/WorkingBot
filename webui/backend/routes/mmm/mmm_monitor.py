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
import functools
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta, timezone

import random

from .mmm_state import recompute_side_lots, get_session_summary
from .mmm_trigger import (
    evaluate_triggers, update_trigger_snapshots, check_frozen_pnl_trigger,
    apply_theta_acceleration, compute_adaptive_interval,
    apply_theta_acceleration_v2, compute_adaptive_interval_v2,
    OUTCOME_NONE, OUTCOME_CE,
    OUTCOME_PE, OUTCOME_BOTH,
)
from .mmm_heartbeat_health import HeartbeatHealth, MAX_STALE_CONSECUTIVE
from .mmm_pnl_core import compute_current_total_pnl as _pnl_total
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
    emit_harvest, emit_recycle, emit_scale_up, emit_breakeven, emit_gamma,
    emit_price_tick, get_ws_health,
)
from .mmm_atm_shield import execute_atm_shield, _check_shield_gates
from .mmm_adaptive import get_adaptive_engine
from .mmm_breakeven_engine import get_breakeven_engine
from .mmm_gamma_detector import get_gamma_detector
from .mmm_harvester import scan_harvestable_positions
from .mmm_recycler import execute_lot_recycling
from .mmm_perp_hedge import (
    run_perp_hedge, close_all_perp, get_perp_summary,
    is_perp_hedge_enabled,
)
from .mmm_storage import get_storage
from .mmm_constants import LOT_SIZE_BTC, strike_key as _strike_key, _D, _LOT
from .mmm_margin_guardian import MarginGuardian, TIER_GREEN, TIER_YELLOW, TIER_ORANGE, TIER_RED, TIER_CRITICAL
from .mmm_dte_presets import STRADDLE_WITH_ADJUSTMENT_CATEGORY, SHORT_STRADDLE_CATEGORY, STRADDLE_ROLL_CATEGORY
from .mmm_regime import MMMRegimeEngine, ACTION_NORMAL, ACTION_WARN, ACTION_BLOCK_CE_SELLS, ACTION_BLOCK_PE_SELLS, ACTION_BLOCK_ALL_SELLS, ACTION_FORCE_REDUCE, ACTION_PAUSE
from .mmm_telegram import (
    alert_margin_tier_change, alert_emergency_close,
    alert_session_stopped, alert_rapid_check_activated,
    alert_max_loss_breach, alert_both_sides_up,
)
from .mmm_reverse import (
    process_reverse_entry, update_reverse_mtm,
    check_reverse_close_at_threshold, close_all_reverse_positions,
    check_reverse_emergency, disable_reverse_mode,
    is_reverse_mode_on, initialize_reverse_state,
)

# L-2 fix: module-level import removes per-call import-lock overhead on every heartbeat.
# Wrapped in try/except to avoid blocking startup if the activity module fails.
try:
    from .mmm_activity import log_activity
except ImportError:
    def log_activity(*args, **kwargs):  # noqa: E306 — fallback no-op
        pass

log = logging.getLogger('mmm_monitor')


def _is_user_awake_hours() -> bool:
    """Return True if current IST time is between 8:00 AM and 11:00 PM.

    IST = UTC+5:30. Awake window: [08:00, 23:00) IST.
    Outside this window (11PM–8AM IST) the user is assumed to be asleep,
    and the auto-stop behavior applies for unhedged/both-sides-closed conditions.
    """
    IST = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(IST)
    return 8 <= now_ist.hour < 23


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
        self._heartbeat_in_progress = False  # AUDIT FIX BUG5: re-entrancy guard
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

        # Strategy Guardian (heartbeat-level integrity checks)
        try:
            from .mmm_guardian import MMMGuardian, register_guardian
            self._guardian = MMMGuardian(session_id)
            register_guardian(session_id, self._guardian)
        except Exception as e:
            log.warning(f"[{session_id}] Guardian init failed (non-fatal): {e}")
            self._guardian = None

        # Regime Engine (pre-adjustment risk controls)
        self._regime_engine = MMMRegimeEngine()
        self._last_iv_data = {}   # Populated by _fetch_premiums
        self._last_gamma_data = {}  # Populated by _calculate_portfolio_delta

        # Last-known-good premiums — NEVER None once set.
        # Updated on every successful price fetch from any source.
        # Used as ultimate fallback so ce_now/pe_now are never None after first beat.
        # TTL: stale prices older than _LAST_GOOD_TTL seconds are discarded.
        self._last_good_ce = None  # float
        self._last_good_pe = None  # float
        self._last_good_ce_at = 0.0  # time.time() when last set
        self._last_good_pe_at = 0.0
        self._LAST_GOOD_TTL = 300  # 5 minutes max staleness

        # Performance Intelligence collector (zero I/O during heartbeat)
        self._perf_collector = None  # Initialized in start() when timing is known

        # Fill sync — ground-truth P&L reconciliation via exchange fills
        from .mmm_fill_sync import FillSyncer
        self._fill_syncer = FillSyncer(self)

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
        elif stored_status == 'EXITING':
            # Backend restarted mid-exit — keep EXITING so the heartbeat gate
            # resumes the exit sequence on the next beat.
            self._paused = False
            log.warning(f"[{self.session_id}] Restoring in EXITING state — exit_all will resume on next heartbeat")
        else:
            self._paused = False
            self.session['strategy_status'] = 'RUNNING'

        # CRITICAL FIX C-3: Detect half-rolled sessions on startup
        half_roll_state = self.session.get('_straddle_half_roll_state')
        from .mmm_straddle_adjustment import HALF_ROLL_NONE
        if half_roll_state and half_roll_state != HALF_ROLL_NONE:
            log.critical(
                f"[{self.session_id}] HALF-ROLL DETECTED on startup: {half_roll_state} — "
                f"session will NOT auto-start. Manual recovery required."
            )
            self.session['strategy_status'] = 'STOPPED'
            self._paused = True  # Prevent any trading

            # Fire recovery alert
            try:
                from .mmm_telegram import alert_half_roll_recovery_needed
                alert_half_roll_recovery_needed(self.session_id, half_roll_state)
            except Exception:
                pass

            # Add to activity log for dashboard visibility
            try:
                from .mmm_activity import log_activity
                log_activity(
                    'straddle_roll_blocked',
                    f"🔴 STARTUP: Half-roll detected ({half_roll_state}). "
                    f"Review positions and close/reset manually.",
                    self.session_id,
                    'error',
                )
            except Exception:
                pass

            # C-3 FIX: Abort startup — do NOT launch thread, close watcher,
            # price ticker, or register with watchdog. Monitor must stay dormant
            # until the half-roll is resolved and the session is manually reset.
            self._running = False
            try:
                _save_session(self.session, my_generation=0)
            except Exception as _hr_save_e:
                log.error(f"[{self.session_id}] Failed to save STOPPED state after half-roll: {_hr_save_e}")
            try:
                emit_status_change(
                    self.session_id, 'IDLE', 'STOPPED',
                    f'Monitor aborted: half-roll state requires manual recovery',
                )
            except Exception:
                pass
            return

        # Backfill any new params that did not exist when this session was created.
        # Uses setdefault so existing user-configured values are never overwritten.
        try:
            from .mmm_state import DEFAULT_PARAMS as _DP
            session_params = self.session.setdefault('params', {})
            for _k, _v in _DP.items():
                session_params.setdefault(_k, _v)
        except Exception as _e:
            log.warning(f"[{self.session_id}] Could not backfill DEFAULT_PARAMS: {_e}")

        # Reverse Mode: ensure _reverse state key exists for session restore compatibility.
        # Uses initialize_reverse_state only when key is absent (never overwrites live state).
        if '_reverse' not in self.session:
            initialize_reverse_state(self.session)

        # NOTE: _being_closed flags are cleared in the AUDIT DEAD-6 block below
        # (after generation is set), then immediately saved to SQLite.

        # Adaptive Tuning: load preset when mode is 'preset' or 'adaptive'.
        # Uses _adaptive_preset_loaded flag so this only fires once per session lifetime,
        # not on every backend restart — operator changes are never overwritten.
        try:
            _adaptive_mode = self.session.get('params', {}).get('adaptive_mode', 'manual')
            if _adaptive_mode in ('preset', 'adaptive') and not self.session.get('_adaptive_preset_loaded'):
                from .mmm_adaptive import AdaptiveEngine
                AdaptiveEngine.load_preset(self.session)
                self.session['_adaptive_preset_loaded'] = True
                log.info(
                    f"[{self.session_id}] Adaptive: preset "
                    f"'{self.session.get('params', {}).get('adaptive_preset', 'strangle')}' "
                    f"loaded at session start"
                )
        except Exception as _adapt_e:
            log.warning(f"[{self.session_id}] Could not load adaptive preset: {_adapt_e}")

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

        # ── Straddle Roll: session-level state ──────────────────────────────
        # Initialised once per session start for STRADDLE_WITH_ADJUSTMENT presets.
        # These keys are consumed by mmm_straddle_adjustment.execute_straddle_roll().
        if self.session.get('params', {}).get('_preset_source') in (
            STRADDLE_WITH_ADJUSTMENT_CATEGORY, SHORT_STRADDLE_CATEGORY
        ):
            # Re-run if key missing OR if it was computed with the old buggy logic
            # (original_lots key doesn't exist on position dicts → was always 0).
            # _straddle_credit_v2 flag marks sessions already fixed.
            _needs_credit_init = (
                '_straddle_initial_credit' not in self.session
                or (
                    self.session.get('_straddle_initial_credit', 0) == 0
                    and not self.session.get('_straddle_credit_v2')
                )
            )
            if _needs_credit_init:
                # Capture the combined credit received at entry.
                # Use 'lots' (per-position field) not 'original_lots' (side-state aggregate).
                # Multiply by LOT_SIZE_BTC to match BTC-adjusted units used in Gate 9/10.
                ce_state = self.session.get('ce') or {}
                pe_state = self.session.get('pe') or {}
                ce_prem = 0.0
                pe_prem = 0.0
                if isinstance(ce_state, dict):
                    for pos in ce_state.get('positions', []):
                        ce_prem += float(pos.get('entry_premium', 0)) * int(pos.get('lots', 0))
                if isinstance(pe_state, dict):
                    for pos in pe_state.get('positions', []):
                        pe_prem += float(pos.get('entry_premium', 0)) * int(pos.get('lots', 0))
                self.session['_straddle_initial_credit'] = round(
                    (ce_prem + pe_prem) * LOT_SIZE_BTC, 4
                )
                self.session['_straddle_credit_v2'] = True  # marks correct computation
                self.session.setdefault('_straddle_roll_count', 0)
                self.session.setdefault('_straddle_last_roll_at', None)
                self.session.setdefault('_straddle_entry_iv', None)  # lazy-captured on first heartbeat
                log.info(
                    f"[{self.session_id}] Straddle Roll state initialised — "
                    f"initial_credit={self.session['_straddle_initial_credit']}"
                )
            # ── Compute premium-based roll trigger (CHANGE 1-A) ────────────────
            # Roll fires when spot has moved ≥ (CE_entry_premium + PE_entry_premium) points.
            # This is the financial breakeven of a short straddle seller.
            # Stored per-roll: updated in mmm_straddle_adjustment.py after each successful roll.
            if '_straddle_roll_trigger_pts' not in self.session or self.session.get('_straddle_roll_trigger_pts', 0) <= 0:
                _ce_active = [p for p in (self.session.get('ce') or {}).get('positions', [])
                              if p.get('status') == 'active' and p.get('lots', 0) > 0]
                _pe_active = [p for p in (self.session.get('pe') or {}).get('positions', [])
                              if p.get('status') == 'active' and p.get('lots', 0) > 0]
                _ce_lots = sum(p.get('lots', 0) for p in _ce_active)
                _pe_lots = sum(p.get('lots', 0) for p in _pe_active)
                _ce_avg = (sum(float(p.get('entry_premium', 0)) * p.get('lots', 0)
                               for p in _ce_active) / _ce_lots) if _ce_lots > 0 else 0
                _pe_avg = (sum(float(p.get('entry_premium', 0)) * p.get('lots', 0)
                               for p in _pe_active) / _pe_lots) if _pe_lots > 0 else 0
                _trigger_pts = _ce_avg + _pe_avg
                if _trigger_pts > 0:
                    self.session['_straddle_roll_trigger_pts'] = round(_trigger_pts, 2)
                    log.info(
                        f"[{self.session_id}] Straddle trigger initialised: "
                        f"{_trigger_pts:.2f}pts (CE_avg={_ce_avg:.2f}, PE_avg={_pe_avg:.2f})"
                    )
                else:
                    log.warning(
                        f"[{self.session_id}] Could not compute trigger_pts — "
                        f"positions may lack entry_premium. Fallback will apply at Gate 8."
                    )

            # AUDIT FIX M-2: Always seed these keys via setdefault for restart safety.
            # Gate 6 reads _straddle_roll_blocked/.._block_logged with .get() fallback,
            # but Step 6 += on _straddle_cumulative_credit needs a numeric seed.
            self.session.setdefault('_straddle_roll_blocked', False)
            self.session.setdefault('_straddle_roll_block_logged', False)
            self.session.setdefault('_straddle_roll_trigger_pts', 0)
            self.session.setdefault(
                '_straddle_cumulative_credit',
                self.session.get('_straddle_initial_credit', 0),
            )

        # Short Window: compute session deadline from start time + window hours
        _window_hours = self.session.get('params', {}).get('session_window_hours', 0)
        if _window_hours and float(_window_hours) > 0 and not self.session.get('session_deadline_utc'):
            from datetime import timedelta
            _deadline = datetime.now(timezone.utc) + timedelta(hours=float(_window_hours))
            self.session['session_deadline_utc'] = _deadline.isoformat()
            log.info(f"[{self.session_id}] Short Window: deadline set to "
                     f"{_deadline.isoformat()} ({_window_hours}h from now)")

        # Performance Intelligence: initialize collector with session time bounds
        try:
            from .mmm_performance import PerformanceCollector
            _start = datetime.fromisoformat(
                analytics.get('session_start_time') or datetime.now(timezone.utc).isoformat()
            )
            if _start.tzinfo is None:
                _start = _start.replace(tzinfo=timezone.utc)
            # End time: session_deadline_utc or expiry_time
            _end_str = self.session.get('session_deadline_utc') or self.session.get('expiry_time')
            if _end_str:
                _end = datetime.fromisoformat(_end_str)
                if _end.tzinfo is None:
                    _end = _end.replace(tzinfo=timezone.utc)
            else:
                _end = _start + timedelta(hours=24)  # fallback
            self._perf_collector = PerformanceCollector(self.session_id, _start, _end)
        except Exception as _perf_e:
            log.warning(f"[{self.session_id}] Performance collector init failed (non-fatal): {_perf_e}")

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

        # AUDIT DEAD-6 FIX: Clear stale _being_closed flags from all positions.
        # If the process crashed mid-order, these flags persist in storage and
        # permanently block close-at-5 from retrying the position.
        try:
            _cleared_count = 0
            for _side_key in ('ce', 'pe'):
                _side_data = self.session.get(_side_key, {})
                if not isinstance(_side_data, dict):
                    continue
                for _pos in _side_data.get('positions', []):
                    if _pos.pop('_being_closed', None):
                        _pos.pop('_being_closed_at', None)
                        _cleared_count += 1
                for _frz in _side_data.get('frozen_positions', []):
                    if _frz.pop('_being_closed', None):
                        _frz.pop('_being_closed_at', None)
                        _cleared_count += 1
            if _cleared_count:
                log.info(f"[{self.session_id}] Cleared {_cleared_count} stale _being_closed flags at start")
        except Exception as _bc_e:
            log.warning(f"[{self.session_id}] Failed to clear _being_closed flags: {_bc_e}")

        # Persist startup cleanup (flag clears, backfills, status) to SQLite immediately.
        # Without this, the API reads stale data from storage until the first heartbeat save.
        self._save_my_session()

        # Use a REAL OS thread (not an eventlet greenlet) so that asyncio's
        # run_until_complete() works inside _run_loop().  When gunicorn uses
        # worker_class=eventlet, threading.Thread is monkey-patched to a
        # greenlet; calling run_until_complete() from a greenlet raises
        # "Cannot run the event loop while another loop is running" because
        # eventlet's hub is already running in that greenlet context.
        # eventlet.patcher.original('threading').Thread gives us the genuine
        # OS thread class, giving asyncio a clean, isolated execution context.
        try:
            from eventlet.patcher import original as _ep_original
            _RealThread = _ep_original('threading').Thread
        except (ImportError, AttributeError):
            _RealThread = threading.Thread

        self._thread = _RealThread(
            target=self._run_loop,
            name=f"mmm-monitor-{self.session_id}",
            daemon=True,
        )
        self._thread.start()
        self._start_close_watcher()
        self._start_price_ticker()

        # Price Guard: start real-time spot monitor for straddle sessions.
        # STRADDLE_ROLL reuses the same price guard coroutine — it reads
        # _straddle_roll_trigger_pts which both presets populate identically.
        if self.session.get('params', {}).get('_preset_source') in (
            STRADDLE_WITH_ADJUSTMENT_CATEGORY, SHORT_STRADDLE_CATEGORY, STRADDLE_ROLL_CATEGORY
        ):
            self._start_price_guard()

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

        # CRITICAL FIX C-1: Cleanup roll lock when session stops
        try:
            from .mmm_straddle_adjustment import _cleanup_roll_lock
            _cleanup_roll_lock(self.session_id)
        except Exception:
            pass

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

        # Performance Intelligence: analyze and persist (ONE final write)
        try:
            from .mmm_performance import analyze_session, get_performance_storage
            perf_record = analyze_session(self.session, self._perf_collector)
            get_performance_storage().save(perf_record)
        except Exception as e:
            log.error(f"Failed to save performance record for {self.session_id}: {e}")

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

        # Deregister guardian from registry
        try:
            from .mmm_guardian import deregister_guardian
            deregister_guardian(self.session_id)
        except Exception:
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
            # AUDIT FIX: Clear stale margin flags that persist across pause/resume
            self.session.pop('_margin_block_sells', None)
            self.session.pop('_margin_wind_down', None)
            self.session.pop('_margin_rapid_check', None)
            # AUDIT BUG-3 FIX: Clear ATM wind-down flag so it can re-arm after resume.
            # Without this, if ATM wind-down fired once and session was paused
            # (e.g. one-side-close guard), the flag sticks forever on resume.
            self.session.pop('_atm_wind_down_triggered', None)
            # Force immediate reconciliation on next heartbeat
            self.session['_recon_counter'] = 0
            self.session['_force_recon'] = True

        self._save_my_session()

        emit_status_change(
            self.session_id, old_status, 'RUNNING', reason
        )
        log.info(f"Monitor resumed for {self.session_id}: {reason}")

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
        
        saved = _save_session(target, self._my_generation)
        # H-4 SECONDARY GUARD: If _save_session returned False (stale generation
        # rejected the save), this monitor must stop immediately. It has already
        # placed an order it cannot persist — continuing would create more phantom
        # positions. The _run_loop's primary guard should have caught this before
        # any order was placed, but this acts as a failsafe for in-flight saves.
        if saved is False and self._running:
            log.error(
                f"[{self.session_id}] STALE MONITOR (post-trade): save rejected "
                f"(gen={self._my_generation}). Stopping to prevent further phantom orders."
            )
            self._running = False
            self._stop_event.set()
            # Flag for _run_loop to send Telegram after run_until_complete returns.
            # Cannot call run_until_complete here (we're already inside it).
            self._stale_abort_gen = self._my_generation

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
        _cleared_consecutive = False
        _cleared_cooldown = False
        # IMP-5: A force-heartbeat from the operator confirms they want to
        # continue despite the consecutive same-direction block — clear it
        # and reset the counter so it doesn't immediately re-block.
        # Also clear active cooldown: cooldown is designed to prevent rapid
        # automatic re-triggering; an explicit operator force-heartbeat should
        # not be silently blocked by it (operators use force to urgently hedge).
        with self._session_lock:
            if self.session:
                if self.session.get('_consecutive_dir_blocked'):
                    self.session.pop('_consecutive_dir_blocked', None)
                    self.session['_consecutive_same_dir_count'] = 0
                    self.session['_consecutive_same_dir_side'] = ''
                    _cleared_consecutive = True
                if self.session.get('cooldown_active'):
                    self.session['cooldown_active'] = False
                    self.session['cooldown_until'] = None
                    self.session.pop('_cooldown_block_logged', None)
                    _cleared_cooldown = True
        if _cleared_consecutive:
            log.info(
                f"[{self.session_id}] IMP-5: consecutive direction block and counter "
                f"cleared by force-heartbeat"
            )
        if _cleared_cooldown:
            log.info(f"[{self.session_id}] Force heartbeat cleared active cooldown")
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
    # Price Guard — Real-time spot monitoring for STRADDLE_WITH_ADJUSTMENT sessions
    # =========================================================================

    def _start_price_guard(self):
        """Start a background thread that polls spot price and forces heartbeat
        when price approaches the roll trigger distance.

        Only started for STRADDLE_WITH_ADJUSTMENT sessions (called from start()).
        Uses the same threading pattern as _start_price_ticker / _start_close_watcher.
        """
        try:
            from eventlet.patcher import original as _ep_original
            _RealThread = _ep_original('threading').Thread
        except (ImportError, AttributeError):
            _RealThread = threading.Thread
        t = _RealThread(
            target=self._run_price_guard_loop,
            name=f"mmm-price-guard-{self.session_id}",
            daemon=True,
        )
        t.start()
        log.info(f"[{self.session_id}] Price Guard: started")

    def _run_price_guard_loop(self):
        """Poll spot price and fire force_heartbeat when trigger proximity detected.

        Fires at most once per cooldown period to avoid heartbeat flooding.
        Reads spot from session['analytics']['last_spot_price'] (set by price ticker).
        """
        sid = self.session_id
        _last_fire = 0.0

        while self._running and not self._stop_event.is_set():
            params = self.session.get('params', {})
            if not params.get('price_guard_enabled', True):
                self._stop_event.wait(timeout=5)
                continue

            interval = max(1, params.get('price_guard_interval_secs', 5))
            buffer_pts = params.get('price_guard_buffer_pts', 50)
            cooldown = params.get('price_guard_cooldown_secs', 30)

            self._stop_event.wait(timeout=interval)
            if self._stop_event.is_set() or not self._running:
                break

            try:
                spot = self.session.get('analytics', {}).get('last_spot_price', 0)
                if not spot or spot <= 0:
                    continue

                atm_strike = self.session.get('ce', {}).get('active_strike', 0)
                trigger_pts = self.session.get('_straddle_roll_trigger_pts', 0)
                if atm_strike <= 0 or trigger_pts <= 0:
                    continue

                spot_move = abs(spot - atm_strike)
                fire_threshold = max(0, trigger_pts - buffer_pts)

                if spot_move >= fire_threshold:
                    now = time.monotonic()
                    if now - _last_fire >= cooldown:
                        _last_fire = now
                        log.warning(
                            f"[{sid}] Price Guard: spot={spot:.0f} moved "
                            f"{spot_move:.0f}pts from ATM={atm_strike:.0f} "
                            f"(threshold={fire_threshold:.0f}pts) — forcing heartbeat"
                        )
                        self.force_heartbeat()
                        try:
                            emit_price_tick(sid, {
                                'event': 'price_guard_fire',
                                'spot': spot,
                                'atm_strike': atm_strike,
                                'spot_move': round(spot_move, 1),
                                'trigger_pts': trigger_pts,
                            })
                        except Exception:
                            pass
            except Exception as _e:
                log.debug(f"[{sid}] Price Guard: error (non-fatal): {_e}")

        log.info(f"[{sid}] Price Guard: stopped")

    # =========================================================================
    # Main Loop
    # =========================================================================

    def _run_loop(self):
        """Main heartbeat loop (runs in background thread)."""
        # Use DefaultEventLoopPolicy to bypass eventlet's monkey-patched asyncio.
        # Without this, run_until_complete() fails with "Cannot run the event
        # loop while another loop is running" because eventlet's custom policy
        # returns a loop wrapper that detects the eventlet hub as a running loop.
        try:
            self._loop = asyncio.DefaultEventLoopPolicy().new_event_loop()
            asyncio.set_event_loop(self._loop)
        except Exception as loop_err:
            log.critical(f"[{self.session_id}] _run_loop FAILED to create event loop: {loop_err}")
            return

        try:
            while self._running and not self._stop_event.is_set():
                # RELOAD session from storage to pick up hot-reload params
                storage = get_storage()
                try:
                    fresh_session = storage.get_session(self.session_id)
                except Exception as e:
                    log.critical("Storage read failed — aborting heartbeat: %s", e)
                    self._wait_for_next_cycle(
                        self.session.get('params', {}).get('adjustment_interval', 300)
                    )
                    continue
                if fresh_session:
                    # H-4 STALE-MONITOR GUARD: If the stored generation exceeds
                    # this monitor's generation, a newer monitor instance has taken
                    # over. This thread is stale — its saves are already blocked by
                    # _save_session(). Without this guard, it would continue placing
                    # orders on the exchange that it can NEVER persist, creating
                    # phantom positions (untracked lots) on every heartbeat.
                    # Fix: detect the staleness here and stop before doing anything.
                    _stored_gen = fresh_session.get('_monitor_generation', 0)
                    if _stored_gen > self._my_generation and self._my_generation > 0:
                        log.error(
                            f"[{self.session_id}] STALE MONITOR: my_gen={self._my_generation} "
                            f"< stored_gen={_stored_gen}. Stopping to prevent phantom orders."
                        )
                        self._running = False
                        # Send Telegram + WebSocket safety alert so user is notified
                        # even if sleeping. This fires BEFORE any order is placed.
                        try:
                            from .mmm_telegram import alert_stale_monitor as _tg_stale
                            self._loop.run_until_complete(_tg_stale(
                                self.session_id,
                                self._my_generation,
                                _stored_gen,
                                context='pre-heartbeat (no orders placed this cycle)',
                            ))
                        except Exception as _tg_err:
                            log.warning(f"[{self.session_id}] Stale monitor Telegram failed: {_tg_err}")
                        try:
                            emit_safety(
                                self.session_id, 'stale_monitor', 'critical',
                                f'STALE MONITOR stopped: gen={self._my_generation} < stored={_stored_gen}. '
                                f'No orders were placed this cycle.',
                                {'my_gen': self._my_generation, 'stored_gen': _stored_gen},
                            )
                        except Exception:
                            pass
                        break

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
                total_dte_hours = params.get('total_dte_hours', 0)
                dte_category = params.get('dte_category', '')

                # Use v2 percentage-based scaling for multi-DTE sessions
                if total_dte_hours > 36 and dte_category and dte_category != '0DTE':
                    adaptive_result = compute_adaptive_interval_v2(
                        interval, hours_to_expiry, total_dte_hours,
                        enabled=adaptive_enabled,
                    )
                else:
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
                    # Use v2 for multi-DTE sessions
                    if total_dte_hours > 36 and dte_category and dte_category != '0DTE':
                        total_dte_mins = total_dte_hours * 60.0
                        accel = apply_theta_acceleration_v2(
                            self.session, minutes_to_expiry, total_dte_mins
                        )
                    else:
                        accel = apply_theta_acceleration(
                            self.session, minutes_to_expiry
                        )
                    if accel.get('accelerated'):
                        interval = min(interval, accel['effective_interval'])
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
                _hb_exc = None
                try:
                    self._loop.run_until_complete(self._heartbeat())
                except Exception as e:
                    _hb_exc = e

                # H-4 SECONDARY GUARD follow-up: if _save_my_session flagged a stale
                # abort during the heartbeat, send Telegram now that run_until_complete
                # has returned (we cannot call run_until_complete from within itself).
                if hasattr(self, '_stale_abort_gen'):
                    _abort_gen = self._stale_abort_gen
                    del self._stale_abort_gen
                    try:
                        from .mmm_telegram import alert_stale_monitor as _tg_stale2
                        self._loop.run_until_complete(_tg_stale2(
                            self.session_id,
                            _abort_gen,
                            0,
                            context='post-trade (order placed — ghost positions may exist on exchange)',
                        ))
                    except Exception as _tg_err2:
                        log.warning(f"[{self.session_id}] Post-trade stale Telegram failed: {_tg_err2}")
                    try:
                        emit_safety(
                            self.session_id, 'stale_monitor_post_trade', 'critical',
                            f'STALE MONITOR stopped AFTER trade: gen={_abort_gen}. '
                            f'Ghost positions may exist — check exchange immediately.',
                            {'my_gen': _abort_gen},
                        )
                    except Exception:
                        pass

                if _hb_exc is not None:
                    e = _hb_exc
                    log.exception(f"Heartbeat error for {self.session_id}: {e}")
                    self.session['last_error'] = str(e)

                    # Circuit breaker: record failure (not a blunt stop)
                    self._circuit.record_failure(str(e))

                    # H-16 fix: best-effort state preservation after heartbeat crash
                    try:
                        current_pnl = _pnl_total(self.session)
                        update_peak_pnl(self.session, current_pnl)
                        self._save_my_session(self.session)
                    except Exception as save_err:
                        log.error(f"Failed to save state after heartbeat crash: {save_err}")

                    # Graduated response: only hard-stop on truly unrecoverable errors
                    # (e.g. programming bugs), not exchange connectivity issues.
                    # Use isinstance so subclasses are caught (e.g. UnboundLocalError
                    # is a NameError subclass — the old str(e) check missed it).
                    unrecoverable = isinstance(e, (TypeError, AttributeError, NameError, AssertionError))
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
        """Execute one heartbeat cycle."""
        # AUDIT FIX BUG5: Re-entrancy guard — prevent overlapping heartbeats
        if self._heartbeat_in_progress:
            log.warning(f"[{self.session_id}] Heartbeat already in progress — skipping")
            return
        self._heartbeat_in_progress = True
        try:
            await self._heartbeat_inner()
        finally:
            self._heartbeat_in_progress = False

    async def _heartbeat_inner(self):
        """Execute one heartbeat cycle (inner implementation).

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

        # H-10 fix (redundant read removed): _run_loop already loads the full fresh
        # session from storage and sets self.session = fresh_session before calling
        # _heartbeat(). By the time we reach here, session['params'] is already the
        # latest from storage. The extra get_session() call here added 1 SQLite read
        # per beat with no benefit — any API param change that arrived after _run_loop's
        # read will be picked up on the next cycle anyway.

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

        # ── GLOBAL GRACEFUL EXIT GATE ─────────────────────────────────────────
        # When strategy_status == 'EXITING' (set by POST /exit_all endpoint),
        # skip ALL normal trading logic and hand off to the exit handler.
        # The recompute above already ran so lot counts are authoritative.
        if session.get('strategy_status') == 'EXITING':
            try:
                from .mmm_exit_all import run_exit_all
                await run_exit_all(self)
            except Exception as _exit_e:
                log.error(f"[{sid}] EXIT ALL handler raised unexpectedly: {_exit_e}", exc_info=True)
                self.stop(f'Exit All failed: {_exit_e}')
            return
        # ── END GLOBAL GRACEFUL EXIT GATE ────────────────────────────────────

        # Heartbeat counter (no activity log — summary emitted at end)
        session['_heartbeat_counter'] = session.get('_heartbeat_counter', 0) + 1

        beat_start_mono = time.monotonic()

        # Fix A3 + Guardian: Set beat deadline and pre-beat snapshot
        _guardian_snapshot = None
        if hasattr(self, '_guardian') and self._guardian:
            _guardian_snapshot = self._guardian.pre_beat_snapshot(session)
            # G5: stale monitor detection — check before any trading logic
            _g5_violation = self._guardian.check_generation_integrity(
                session, self._my_generation
            )
            if _g5_violation:
                self._guardian.handle_stale_monitor(
                    self, self._my_generation,
                    session.get('_monitor_generation', 0),
                )
                return  # handle_stale_monitor sets _running=False and _stale_abort_gen
            _beat_deadline = self._guardian.get_beat_deadline(
                session, beat_start_mono,
            )
        else:
            _beat_deadline = beat_start_mono + session.get('params', {}).get(
                'guardian_max_beat_sec', 120,
            )
        session['_beat_deadline'] = _beat_deadline

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

        # Step 0.1: Fill sync — ground-truth P&L reconciliation via exchange fills.
        # Runs every heartbeat. Catches any position closed outside the algo's view
        # (expiry, manual buyback, reconciliation, crash-recovery) and books realized
        # P&L at the ACTUAL exchange fill price. Non-blocking — errors are swallowed.
        try:
            _fs_rest = self._create_heartbeat_rest_client()
            _fs_expiry = session.get('params', {}).get('expiry', '')
            await self._fill_syncer.sync(_fs_rest, session, _fs_expiry)
        except Exception as _fs_err:
            log.debug(f"[{sid}] FillSync step skipped: {_fs_err}")

        # H-4: Stale estimate check — alert if any close estimate is unconfirmed
        # for >10 min. Means fill_sync hasn't seen the fill (order may not have
        # executed or exchange API is failing). Read-only: does not modify P&L.
        try:
            from .mmm_pnl_core import check_stale_estimates as _pnl_stale
            _stale = _pnl_stale(session, max_age_minutes=10.0)
            if _stale:
                emit_safety(
                    sid, 'stale_estimate', 'warning',
                    f"{len(_stale)} unconfirmed P&L estimate(s) >10min old — "
                    f"fill_sync may be failing or order(s) did not execute.",
                    {'stale_orders': [e.get('order_id') for e in _stale[:5]],
                     'oldest_age_sec': max(e.get('_age_sec', 0) for e in _stale)},
                )
        except Exception as _stale_err:
            log.debug(f"[{sid}] Stale estimate check skipped: {_stale_err}")

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
            # T1-3: consecutive CRITICAL escalation — stop session before any action
            if 'force_stop_session' in margin_result.get('actions', []):
                log.error(
                    f"[{sid}] MARGIN FORCE STOP: {margin_result.get('consecutive_critical', 0)} "
                    f"consecutive CRITICAL beats — stopping session now"
                )
                session['stop_reason'] = (
                    f"Margin consecutive CRITICAL x{margin_result.get('consecutive_critical', 0)}"
                )
                self.stop()
                return
            if margin_result['tier'] in (TIER_RED, TIER_CRITICAL):
                # RED/CRITICAL: emergency close already handled inside _check_margin_guardian
                # C-1 fix: run cleanup before returning so peak P&L, session save,
                # heartbeat emit, and health telemetry are not skipped.
                try:
                    current_pnl = _pnl_total(session)
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

        # Step 0.75: Auto-promote the open strike closest to ATM as the active strike.
        # Runs before premium fetch so _fetch_premiums uses the correct new active strike.
        # Skipped when the user has manually pinned a strike (active_strike_pinned=True).
        try:
            await self._auto_promote_atm_strike()
        except Exception as _atm_promo_err:
            log.warning(f"[{sid}] Auto-ATM promotion error: {_atm_promo_err}")

        # Step 1: Fetch current premiums — with circuit breaker + fallback
        ce_now, pe_now, fetch_ok = await self._fetch_premiums_with_fallback()

        # Feature 9: Compute data confidence after fetch (stale flags are now set on session)
        self._compute_data_confidence()

        _partial_safety_checked = False  # P1-A: dedup flag — prevents double safety run

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
                _partial_safety_checked = True  # P1-A: safety already ran above
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
                # P1-A: Skip if already ran during partial beat to avoid double-fire.
                if _partial_safety_checked:
                    _miss_safety_events: list = []
                else:
                    minutes_to_expiry = self._get_minutes_to_expiry()
                    _miss_safety_events = self._safety.run_all_checks(session, minutes_to_expiry)
                safety_events = _miss_safety_events
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

        # ── Trigger snapshot heal (runs even when PAUSED) ──
        # Moved from Step 6 so it fires regardless of _skip_to_pnl.
        # If active_strike has no trigger_snapshot entry (e.g. set-active-strike
        # API failed to fetch prices, or session was paused before heal ran),
        # initialize it with the current premium to prevent 0.0 baseline.
        for _heal_side in ('ce', 'pe'):
            _heal = session.get(_heal_side, {})
            _heal_strike = _heal.get('active_strike', 0)
            if _heal_strike > 0:
                from .mmm_constants import strike_key as _sk
                _heal_key = _sk(_heal_strike)
                _heal_snap = _heal.get('trigger_snapshot', {})
                if _heal_key not in _heal_snap or _heal_snap.get(_heal_key, 0) == 0:
                    _heal_prem = ce_now if _heal_side == 'ce' else pe_now
                    if _heal_prem > 0:
                        if 'trigger_snapshot' not in _heal:
                            _heal['trigger_snapshot'] = {}
                        _heal['trigger_snapshot'][_heal_key] = _heal_prem
                        session[_heal_side] = _heal
                        log.warning(
                            f"[{sid}] Trigger snapshot healed: "
                            f"{_heal_side.upper()}[{_heal_key}] = {_heal_prem:.2f} (was missing/zero)"
                        )
                        log_activity('trigger_stale',
                                    f'⚠️ Trigger snapshot healed for {_heal_side.upper()} '
                                    f'@ {_heal_key} = ${_heal_prem:.2f} (was missing/zero)',
                                    sid, 'warning',
                                    {'side': _heal_side, 'strike': _heal_key, 'premium': _heal_prem})

        # Stale-price guard: warn if HeartbeatHealth detects frozen exchange data
        if self._health.stale_ce_detected or self._health.stale_pe_detected:
            stale_sides = []
            if self._health.stale_ce_detected:
                stale_sides.append('CE')
            if self._health.stale_pe_detected:
                stale_sides.append('PE')
            stale_msg = (
                f"Stale price detected for {'/'.join(stale_sides)}: "
                f"mark_price unchanged for {MAX_STALE_CONSECUTIVE}+ consecutive beats. "
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

        # Pre-scan shift candidates when either side is approaching shift territory.
        # pre_scan_shift_candidates has a proximity guard — if both sides are far above
        # shift_threshold it returns immediately without any REST call (microseconds).
        # When a shift fires later this heartbeat, _process_strike_shift uses the cached
        # result directly — no extra chain API call at order time.
        # The spot is stored in session['_last_prescan_spot'] so _process_strike_shift
        # can reuse it without a redundant _fetch_spot_price() call.
        try:
            from .mmm_strike_shift import pre_scan_shift_candidates
            _prescan_spot = await self._fetch_spot_price()
            if _prescan_spot > 0:
                # Store spot before running executor — used by _process_strike_shift
                # to skip a redundant _fetch_spot_price() call in the same heartbeat.
                # Timestamp is set AFTER executor completes so that _prescan_age
                # in _process_strike_shift correctly reflects actual scan completion,
                # not initiation. If proximity guard skips the actual chain fetch,
                # _last_prescan_ts is still set — _should_flush relies on both
                # _prescan_age AND _beat_age (candidate's own scanned_at) so stale
                # chain data is correctly identified even when ts is fresh.
                session['_last_prescan_spot'] = _prescan_spot
                _scan_fn = functools.partial(
                    pre_scan_shift_candidates,
                    self.initializer, session, _prescan_spot,
                    ce_premium=ce_now, pe_premium=pe_now,
                )
                await asyncio.get_running_loop().run_in_executor(None, _scan_fn)
                session['_last_prescan_ts'] = time.time()  # set AFTER executor finishes
        except Exception as _prescan_err:
            log.warning(f"[{sid}] Shift pre-scan failed (non-fatal): {_prescan_err}")

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
                    # BUG FIX (Mar 12 2026): use active_strike, NOT original_strike.
                    # After multiple shifts the original entry strike can be 3-4% away
                    # from current spot while the active strike is already ATM/ITM.
                    # Guard: active_lots > 0 (prevents stale zero-lot sides from firing).
                    _ce_orig = session.get('ce', {}).get('active_strike', 0)
                    _pe_orig = session.get('pe', {}).get('active_strike', 0)
                    _ce_lots = session.get('ce', {}).get('active_lots', 0)
                    _pe_lots = session.get('pe', {}).get('active_lots', 0)
                    _atm_wd_side = None

                    if _ce_orig and _ce_lots > 0 and abs(_wd_spot - _ce_orig) <= _wd_atm_threshold:
                        _atm_wd_side = 'CE'
                    elif _pe_orig and _pe_lots > 0 and abs(_wd_spot - _pe_orig) <= _wd_atm_threshold:
                        _atm_wd_side = 'PE'

                    if _atm_wd_side:
                        # ATM Shield takes priority: if enabled and has capacity
                        # AND can actually fire (gates pass), suppress wind-down
                        # — shield will reposition at Step 5.5.
                        # Wind-down only fires if shield has no viable OTM strike
                        # (the shield itself sets _atm_wind_down_triggered in that case).
                        if params.get('atm_shield_enabled', False):
                            _ws = _atm_wd_side.lower()
                            _shield_margin_tier = getattr(self._margin_guardian, 'last_tier', 'GREEN')
                            _shield_mte = self._get_minutes_to_expiry()
                            _can_fire, _gate_reason = _check_shield_gates(
                                session, _ws, params, _shield_margin_tier,
                                _shield_mte if _shield_mte is not None else 999,
                            )
                            if _can_fire:
                                log.info(f"[{sid}] ATM wind-down suppressed — ATM Shield active "
                                         f"(gates pass). "
                                         f"Wind-down will auto-activate only if no viable OTM strike.")
                                _atm_wd_side = None   # shield handles it at Step 5.5
                            else:
                                log.info(f"[{sid}] ATM Shield cannot fire ({_gate_reason}) "
                                         f"— letting wind-down proceed")

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
                            f"0.5% of {_atm_wd_side} ACTIVE strike ${_triggered_strike:.0f}. "
                            f"Switching to wind-down mode (gradual LIFO buyback)."
                        )
                        log_activity('atm_wind_down',
                                     f'🌙 ATM WIND-DOWN: Spot ${_wd_spot:.0f} reached '
                                     f'{_atm_wd_side} ACTIVE strike ${_triggered_strike:.0f} '
                                     f'— activating wind-down mode (gradual buyback)',
                                     sid, 'warning',
                                     {'spot': _wd_spot,
                                      'ce_active_strike': _ce_orig,
                                      'pe_active_strike': _pe_orig,
                                      'triggered_side': _atm_wd_side,
                                      'triggered_strike': _triggered_strike})
                        emit_safety(
                            sid, 'atm_wind_down', 'warning',
                            f'ATM WIND-DOWN: Spot ${_wd_spot:.0f} reached {_atm_wd_side} '
                            f'ACTIVE strike ${_triggered_strike:.0f}. Wind-down mode activated.',
                            {'spot': _wd_spot, 'triggered_side': _atm_wd_side,
                             'triggered_strike': _triggered_strike}
                        )

        if params.get('close_at_atm', False):
            # Guard: skip if already triggered this session (prevent repeat fires)
            if session.get('_atm_close_triggered'):
                log.debug(f"[{sid}] ATM auto-close already triggered, skipping")
            # AUDIT CONFLICT-6 FIX: If wind_down_on_atm already triggered,
            # skip close_at_atm — wind-down takes priority for gradual exit.
            # Both use 0.5% threshold; without this guard, wind-down activates
            # then close_at_atm immediately overrides and closes everything.
            elif session.get('_atm_wind_down_triggered'):
                log.debug(f"[{sid}] ATM wind-down active, skipping close_at_atm")
            else:
                spot_price = await self._fetch_spot_price()
                if spot_price > 0:
                    atm_threshold_pct = 0.005  # 0.5% of spot
                    atm_threshold = spot_price * atm_threshold_pct
                    # BUG FIX (Mar 12 2026): use active_strike, NOT original_strike.
                    # After multiple shifts the original entry strike can be 3-4% away
                    # from current spot while the active strike is already ATM/ITM.
                    # Guard: active_lots > 0 (prevents stale zero-lot sides from firing).
                    ce_original_strike = session.get('ce', {}).get('active_strike', 0)
                    pe_original_strike = session.get('pe', {}).get('active_strike', 0)
                    ce_total_lots = session.get('ce', {}).get('active_lots', 0)
                    pe_total_lots = session.get('pe', {}).get('active_lots', 0)
                    atm_triggered_side = None

                    if ce_original_strike and ce_total_lots > 0 and abs(spot_price - ce_original_strike) <= atm_threshold:
                        atm_triggered_side = 'CE'
                    elif pe_original_strike and pe_total_lots > 0 and abs(spot_price - pe_original_strike) <= atm_threshold:
                        atm_triggered_side = 'PE'

                    if atm_triggered_side:
                        # ATM Shield deferral: let shield handle if gates pass
                        if params.get('atm_shield_enabled', False):
                            _es = atm_triggered_side.lower()
                            _shield_margin_tier = getattr(self._margin_guardian, 'last_tier', 'GREEN')
                            _shield_mte = self._get_minutes_to_expiry()
                            _can_fire, _gate_reason = _check_shield_gates(
                                session, _es, params, _shield_margin_tier,
                                _shield_mte if _shield_mte is not None else 999,
                            )
                            if _can_fire:
                                log.info(f"[{sid}] close_at_ATM deferred to ATM Shield "
                                         f"(gates pass)")
                                atm_triggered_side = None  # skip — shield at Step 5.5
                            else:
                                log.info(f"[{sid}] ATM Shield cannot fire ({_gate_reason}) "
                                         f"— letting close_at_ATM proceed")

                    if atm_triggered_side:
                        triggered_strike = ce_original_strike if atm_triggered_side == 'CE' else pe_original_strike
                        # Set guard flag BEFORE close to prevent re-entry
                        session['_atm_close_triggered'] = True
                        log.critical(
                            f"[{sid}] ATM AUTO-CLOSE: Spot ${spot_price:.0f} within "
                            f"0.5% of {atm_triggered_side} ACTIVE strike "
                            f"${triggered_strike:.0f}. CLOSING ALL."
                        )
                        log_activity('atm_auto_close',
                                    f'🛑 ATM AUTO-CLOSE: Spot ${spot_price:.0f} is at '
                                    f'{atm_triggered_side} ACTIVE strike ${triggered_strike:.0f} '
                                    f'— closing all positions',
                                    sid, 'error',
                                    {'spot': spot_price,
                                     'ce_active_strike': ce_original_strike,
                                     'pe_active_strike': pe_original_strike,
                                     'triggered_side': atm_triggered_side,
                                     'triggered_strike': triggered_strike})
                        emit_safety(
                            sid, 'atm_auto_close', 'critical',
                            f'ATM AUTO-CLOSE: Spot ${spot_price:.0f} reached {atm_triggered_side} '
                            f'ACTIVE strike ${triggered_strike:.0f}. Closing all positions.',
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
                            current_pnl = _pnl_total(session)
                            update_peak_pnl(session, current_pnl)
                            self._emit_heartbeat_data(ce_now, pe_now)
                            self._save_my_session(session)
                            latency_ms = (time.monotonic() - beat_start_mono) * 1000
                            self._health.record_beat('ok', latency_ms=latency_ms)
                        except Exception as _cleanup_err:
                            log.error(f"[{sid}] Cleanup after ATM auto-close failed: {_cleanup_err}")
                        return

        # Step 1.5: Proactive Shift Scanner — MOVED to Step 5.6 (after safety checks)
        # Fix A1 (March 12 incident): proactive shift was running BEFORE safety
        # checks, bypassing lot_velocity, asymmetry, margin tier, and regime blocks.
        # Now gated behind _skip_to_pnl so all safety mechanisms are respected.

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
        _both_closed = check_both_sides_closed(session)
        if not _both_closed:
            # Clear alert flag when new positions have been entered so the
            # next close cycle sends a fresh Telegram notification.
            session.pop('_both_sides_closed_alerted', None)
        if _both_closed:
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
            # ── USER AWAKE HOURS GUARD ───────────────────────────────────────
            # 8AM–11PM IST: do NOT auto-stop. The user is awake and near the
            # computer. Send a Telegram alert once and keep the session alive
            # so the user can manually decide (re-enter positions or stop).
            # Outside these hours (11PM–8AM IST): stop as before.
            if _is_user_awake_hours():
                if not session.get('_both_sides_closed_alerted'):
                    session['_both_sides_closed_alerted'] = True
                    _bsc_pnl = (session.get('unrealized_pnl', 0)
                                + session.get('realized_pnl', 0)
                                - session.get('total_fees', 0))
                    log.warning(
                        f"[{sid}] Both sides fully closed during awake hours "
                        f"(8AM-11PM IST) — Telegram alert sent, session kept alive."
                    )
                    log_activity(
                        'both_sides_closed_awake',
                        '🔔 Both sides at 0 lots (awake hours) — session kept running. '
                        'Manual action required.',
                        sid, 'warning',
                        {'pnl': round(_bsc_pnl, 4)},
                    )
                    try:
                        from .mmm_telegram import alert_both_sides_closed_awake as _tg_bsc
                        asyncio.ensure_future(_tg_bsc(sid, _bsc_pnl))
                    except Exception:
                        pass
                # Emit heartbeat so dashboard stays live; save state; continue.
                try:
                    current_pnl = (session.get('unrealized_pnl', 0)
                                   + session.get('realized_pnl', 0)
                                   - session.get('total_fees', 0))
                    update_peak_pnl(session, current_pnl)
                    self._emit_heartbeat_data(ce_now, pe_now)
                    self._save_my_session(session)
                    latency_ms = (time.monotonic() - beat_start_mono) * 1000
                    self._health.record_beat('ok', latency_ms=latency_ms)
                except Exception as _cleanup_err:
                    log.error(f"[{sid}] Heartbeat after both-sides-closed (awake) failed: {_cleanup_err}")
                return
            # Off-hours: stop as before
            self.stop('Both sides fully closed — strategy complete!')
            # ── SESSION EVENT: lifecycle completed ────────────────────────
            try:
                from .mmm_audit_log import get_event_log as _get_evl
                from .mmm_audit_remark import build_event_remark as _ber
                _get_evl().enqueue_event(
                    session_id=sid,
                    event_category='SESSION_LIFECYCLE',
                    event_type='completed',
                    severity='INFO',
                    remark=_ber('SESSION_LIFECYCLE', 'completed'),
                    details={
                        'realized_pnl': session.get('realized_pnl', 0),
                        'adjustment_count': session.get('adjustment_count', 0),
                    },
                )
            except Exception:
                pass
            # ── END SESSION EVENT ─────────────────────────────────────────
            # H-2 fix: emit final heartbeat data and save before returning
            try:
                current_pnl = _pnl_total(session)
                update_peak_pnl(session, current_pnl)
                self._emit_heartbeat_data(ce_now, pe_now)
                self._save_my_session(session)
                latency_ms = (time.monotonic() - beat_start_mono) * 1000
                self._health.record_beat('ok', latency_ms=latency_ms)
            except Exception as _cleanup_err:
                log.error(f"[{sid}] Cleanup after both-sides-closed failed: {_cleanup_err}")
            return

        # ── ONE-SIDE CLOSE GUARD + AUTO-REPLENISH ────────────────────────────
        # If one side is fully closed while the other still has open positions,
        # try auto-replenish first. If replenish fails or is ineligible, fall
        # back to the original PAUSE behavior.
        for _cs in ['ce', 'pe']:
            _os = 'pe' if _cs == 'ce' else 'ce'
            _ocs_flag = f'_one_side_closed_{_cs}'
            _orig_closed_flag = f'_orig_pos_closed_{_cs}'
            _lots_remaining_key = f'_replenish_lots_remaining_{_cs}'

            # Trigger condition:
            #   (a) side fully closed (total_lots=0) AND open side still has lots — primary trigger
            #   (b) partial fill pending (_replenish_ocs_active + lots_remaining > 0) — top-up trigger
            _os_lots = session.get(_os, {}).get('total_lots', 0)
            _fully_closed = check_side_fully_closed(session, _cs) and _os_lots > 0
            _partial_pending = (
                session.get('_replenish_ocs_active', False)
                and session.get(_lots_remaining_key, 0) > 0
                and _os_lots > 0
            )

            if _fully_closed or _partial_pending:

                # Bug 4 fix: if the monitor is already stopping (watchdog killed it
                # mid-heartbeat), _save_disabled=True and status=STOPPED — replenish
                # Gate 2 would block, any pause/save would silently fail, and the
                # unhedged state would not be persisted to DB. Skip entirely and let
                # the new monitor handle it cleanly on its first healthy heartbeat.
                if self._should_stop() or session.get('_save_disabled'):
                    log.warning(f"[{sid}] ONE-SIDE CLOSE: skipping replenish/pause — "
                                f"monitor is stopping (will retry on next start)")
                    break

                # Mark OCS recovery active — Gate 2 in check_replenish_eligibility
                # allows PAUSED sessions when this flag is True, so the watchdog can
                # still fire replenish even after an off-hours PAUSE.
                session['_replenish_ocs_active'] = True

                # ── TRY AUTO-REPLENISH (every heartbeat while side is empty/partial) ──
                _replenished = False
                try:
                    _replenished = await self._process_replenish(
                        _cs, _os, ce_now, pe_now)
                except Exception as _repl_err:
                    log.error(f"[{sid}] Replenish exception: {_repl_err}")

                if _replenished:
                    # Full fill: clear all OCS/partial flags and continue heartbeat
                    _partial_still = session.get(_lots_remaining_key, 0) > 0
                    if not _partial_still:
                        session.pop(_ocs_flag, None)
                        session.pop(_orig_closed_flag, None)
                        session.pop('_replenish_ocs_active', None)
                        session.pop(_lots_remaining_key, None)
                        log.info(f"[{sid}] Auto-replenished {_cs.upper()} — hedge fully restored")
                        # Auto-resume if paused by this OCS event
                        _pr = session.get('_paused_reason', '')
                        if self._paused and f'{_cs.upper()} fully closed' in _pr:
                            log_activity(
                                'ocs_auto_resume',
                                f'✅ OCS hedge restored — auto-resuming (was: {_pr})',
                                sid, 'success',
                                {'replenished_side': _cs},
                            )
                            self.resume(f'OCS hedge restored — {_cs.upper()} replenished')
                    else:
                        # Partial fill — registered, top-up will fire next heartbeat
                        log.info(f"[{sid}] Auto-replenished {_cs.upper()} partial "
                                f"({session[_lots_remaining_key]} lots remaining for top-up)")
                    try:
                        self._emit_heartbeat_data(ce_now, pe_now)
                        self._save_my_session(session)
                    except Exception:
                        pass
                    break

                # ── FALLBACK: PAUSE (awake hours) or STOP (off-hours) — only on first detection ──
                if not session.get(_ocs_flag):
                    session[_ocs_flag] = True
                    _ocs_awake = _is_user_awake_hours()
                    # Stop lock: off-hours with open lots → PAUSE not STOP
                    _ocs_will_stop = not _ocs_awake and _os_lots == 0
                    _ocs_action = ('PAUSED' if _ocs_awake
                                   else ('STOPPED (off-hours, no open lots)'
                                         if _ocs_will_stop
                                         else 'PAUSED (stop lock: open lots protected)'))
                    _ocs_msg = (
                        f'{_cs.upper()} fully closed (all positions at or below threshold) '
                        f'but {_os.upper()} has {_os_lots} lot(s) still open — '
                        f'one-sided exposure detected. Session {_ocs_action}. '
                        f'Action required: close {_os.upper()} positions or '
                        f're-enter {_cs.upper()} at a new strike.'
                    )
                    log.error(f"[{sid}] ONE-SIDE CLOSE: {_ocs_msg}")
                    log_activity(
                        'safety_block',
                        f'⛔ ONE-SIDE CLOSE: {_cs.upper()}=0 lots, '
                        f'{_os.upper()}={_os_lots} lots open — unhedged. {_ocs_action}.',
                        sid, 'error',
                        {'closed_side': _cs, 'open_side': _os, 'open_lots': _os_lots},
                    )
                    emit_safety(
                        sid, 'one_side_closed', 'critical', _ocs_msg,
                        {'closed_side': _cs, 'open_side': _os, 'open_lots': _os_lots},
                    )
                    if _ocs_awake:
                        # Awake hours: pause, set AWAITING_USER_ACTION flag, fire Telegram.
                        _ocs_pnl = (session.get('unrealized_pnl', 0)
                                    + session.get('realized_pnl', 0)
                                    - session.get('total_fees', 0))
                        _os_strike = session.get(_os, {}).get('active_strike', 0)
                        _IST = timezone(timedelta(hours=5, minutes=30))
                        _detected_ist = datetime.now(_IST).strftime('%d %b %Y, %H:%M IST')

                        # Persist AWAITING_USER_ACTION flags so WebUI can show banner
                        session['_awaiting_user_action'] = True
                        session['_awaiting_user_action_reason'] = (
                            f'{_cs.upper()} fully closed — '
                            f'{_os.upper()} unhedged ({_os_lots} lots @ {_os_strike})'
                        )
                        session['_awaiting_user_action_details'] = {
                            'closed_side': _cs,
                            'open_side': _os,
                            'open_lots': _os_lots,
                            'open_strike': _os_strike,
                            'current_pnl': round(_ocs_pnl, 2),
                            'detected_at_ist': _detected_ist,
                            'session_id': sid,
                        }

                        # Telegram alert — 30-minute wall-clock cooldown
                        _tg_last = session.get('_ocs_telegram_sent_at', 0)
                        if time.time() - _tg_last > 1800:
                            session['_ocs_telegram_sent_at'] = time.time()
                            try:
                                from .mmm_telegram import alert_active_hours_unhedged_pause as _tg_ahup
                                asyncio.ensure_future(
                                    _tg_ahup(sid, _cs, _os, _os_lots, _ocs_pnl,
                                              session['_awaiting_user_action_details'])
                                )
                            except Exception:
                                pass

                        self.pause(f'{_cs.upper()} fully closed — {_os.upper()} unhedged')
                    else:
                        # Off-hours (11PM–8AM IST): STOP LOCK — never stop with open lots.
                        # If the open side has any lots, convert STOP → PAUSE so the OCS
                        # watchdog can keep retrying replenish on subsequent heartbeats.
                        # Only stop when there are truly no open lots (nothing left to protect).
                        _ocs_pnl_v = (session.get('unrealized_pnl', 0)
                                      + session.get('realized_pnl', 0)
                                      - session.get('total_fees', 0))
                        try:
                            from .mmm_telegram import alert_offhours_unhedged_stop as _tg_ohs
                            asyncio.ensure_future(
                                _tg_ohs(sid, _cs, _os, _os_lots, _ocs_pnl_v)
                            )
                        except Exception:
                            pass
                        if _os_lots > 0:
                            # Stop lock: open exposure detected — PAUSE so watchdog can
                            # continue replenishing.  Stopping would kill the monitor and
                            # leave the open side completely unmonitored.
                            log.warning(
                                f"[{sid}] STOP LOCK: {_os.upper()} has {_os_lots} open lots — "
                                f"converting off-hours STOP to PAUSE so OCS watchdog can recover"
                            )
                            self.pause(
                                f'{_cs.upper()} fully closed — {_os.upper()} unhedged '
                                f'(stop lock: {_os_lots} lots protected, off-hours → PAUSE)'
                            )
                        else:
                            self.stop(
                                f'{_cs.upper()} fully closed — {_os.upper()} unhedged '
                                f'(off-hours auto-stop)'
                            )
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
                        log.error(f"[{sid}] Cleanup after one-side-close action failed: {_ocs_err}")
                    return
                # Flag already set (user resumed or subsequent heartbeat) — let run continue
                break
            else:
                # Clear flags when the closed side has regained lots (manually or via replenish).
                # Only clear AWAITING_USER_ACTION and OCS-recovery flags if THIS side was the one
                # flagged — prevents the healthy side's else-branch from wiping flags that belong
                # to the still-closed OTHER side.
                _was_flagged = session.get(_ocs_flag)
                session.pop(_ocs_flag, None)
                session.pop(_orig_closed_flag, None)
                session.pop(_lots_remaining_key, None)
                if _was_flagged:
                    session.pop('_replenish_ocs_active', None)
                    session.pop('_awaiting_user_action', None)
                    session.pop('_awaiting_user_action_reason', None)
                    session.pop('_awaiting_user_action_details', None)
                    session.pop('_ocs_telegram_sent_at', None)
                    # Auto-resume if paused by this OCS event (side regained lots externally)
                    _pr = session.get('_paused_reason', '')
                    if self._paused and f'{_cs.upper()} fully closed' in _pr:
                        log_activity(
                            'ocs_auto_resume',
                            f'✅ OCS hedge restored — auto-resuming (was: {_pr})',
                            sid, 'success',
                            {'restored_side': _cs},
                        )
                        self.resume(f'OCS hedge restored — {_cs.upper()} lots regained')
        # ── END ONE-SIDE CLOSE GUARD + AUTO-REPLENISH ────────────────────────

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
            # H-1: use single canonical formula for peak tracking
            current_pnl = _pnl_total(session)
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

        # ── SESSION EVENT: critical safety events ─────────────────────────
        try:
            from .mmm_audit_log import get_event_log as _get_evl
            from .mmm_audit_remark import build_event_remark as _ber
            _SAFETY_SEV = {'critical': 'CRITICAL', 'alert': 'WARN', 'warning': 'WARN', 'info': 'INFO'}
            _CRITICAL_ACTIONS = {'auto_close', 'stop', 'pause'}
            for _se in safety_events:
                if _se.get('action') in _CRITICAL_ACTIONS:
                    _ev_type = _se.get('type', 'unknown')
                    _sev = _SAFETY_SEV.get(_se.get('level', 'warning'), 'WARN')
                    _get_evl().enqueue_event(
                        session_id=sid,
                        event_category='SAFETY',
                        event_type=_ev_type,
                        severity=_sev,
                        remark=_se.get('message', _ber('SAFETY', _ev_type,
                                                       **(_se.get('details') or {}))),
                        details=_se.get('details'),
                    )
        except Exception:
            pass

        # Track safety events for walkthrough
        self._hb_wt['safety_events'] = safety_events

        # ── Dangerous Mode flag — resolved once, used across all gates ──────
        # When ON: bypasses all cooldowns, regime blocks, whipsaw, asymmetry,
        # and margin-YELLOW blocks. max_loss hard stop, ITM guard, and
        # auto-close near expiry remain fully active regardless.
        _dangerous_mode = params.get('dangerous_mode', False)
        if _dangerous_mode:
            log.warning(
                f"[{sid}] ⚠️ DANGEROUS MODE ACTIVE — all safety gates bypassed. "
                f"Only max_loss, ITM guard, and auto-close near expiry are enforced."
            )

        # Handle safety actions
        _skip_to_pnl = False  # Flag: skip triggers/adjustments but finish heartbeat
        if should_block_adjustment(safety_events):
            reason, action_type = get_block_action(safety_events)
            if action_type == 'auto_close':
                # auto_close = max_loss breach or near-expiry close — NEVER bypassed
                await self._auto_close_all(reason, emergency=True)
                # H-5 fix: run cleanup before returning
                try:
                    current_pnl = _pnl_total(session)
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
                    current_pnl = _pnl_total(session)
                    update_peak_pnl(session, current_pnl)
                    self._emit_heartbeat_data(ce_now, pe_now)
                    self._save_my_session(session)
                    latency_ms = (time.monotonic() - beat_start_mono) * 1000
                    self._health.record_beat('ok', latency_ms=latency_ms)
                except Exception as _cleanup_err:
                    log.error(f"[{sid}] Cleanup after safety stop failed: {_cleanup_err}")
                return
            elif _dangerous_mode:
                # Dangerous mode: bypass stop_adjustments (whipsaw, velocity, asymmetry, guardrails)
                log_activity('dangerous_mode_bypass',
                             f'⚠️ DANGEROUS MODE: safety gate bypassed — {reason}',
                             sid, 'warning',
                             {'reason': reason, 'action_type': action_type,
                              'dangerous_mode': True})
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

        # Handle asymmetry side-specific block: store which side is blocked so
        # _process_adjustment() can reject only heavy-side sells while still
        # allowing light-side sells to rebalance the position.
        _asym_block_event = next(
            (e for e in safety_events if e.get('action') == 'block_heavy_side_sells'), None
        )
        if _asym_block_event:
            _asym_heavy = _asym_block_event.get('details', {}).get('heavy_side', '')
            session['_asymmetry_blocked_side'] = _asym_heavy
            log_activity('asymmetry_side_block',
                        f'⚖️ Asymmetry 7:1 — blocking {_asym_heavy.upper()} sells only '
                        f'(light side may still sell to rebalance)',
                        sid, 'warning',
                        {'heavy_side': _asym_heavy,
                         'ratio': _asym_block_event.get('details', {}).get('ratio', 0)})
        else:
            session.pop('_asymmetry_blocked_side', None)

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
                log.error("Regime engine error (observation mode): %s", e, exc_info=True)
                # AUDIT CONFLICT-1 FIX: When regime is DISABLED, error should NOT
                # silently block all sells. The user explicitly disabled regime.
                session['_regime_action'] = ACTION_NORMAL
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
                session['_regime_action'] = regime_action

                # ── SESSION EVENT: regime state transition (log once per change) ──
                try:
                    _prev_regime = getattr(self, '_last_logged_regime_action', ACTION_NORMAL)
                    if regime_action != _prev_regime:
                        from .mmm_audit_log import get_event_log as _get_evl
                        from .mmm_audit_remark import build_event_remark as _ber
                        _sev = 'CRITICAL' if 'BLOCK' in str(regime_action) or regime_action == ACTION_FORCE_REDUCE else 'WARN'
                        _get_evl().enqueue_event(
                            session_id=sid,
                            event_category='REGIME',
                            event_type='transition',
                            severity=_sev,
                            remark=_ber('REGIME', 'transition',
                                        old_state=str(_prev_regime),
                                        new_state=str(regime_action)),
                            details={
                                'old_action': str(_prev_regime),
                                'new_action': str(regime_action),
                                'vol_regime': session.get('_vol_regime'),
                                'gamma_regime': session.get('_gamma_regime'),
                                'trend_regime': session.get('_trend_regime'),
                                'trend_tier': session.get('_trend_tier'),
                            },
                        )
                        self._last_logged_regime_action = regime_action
                except Exception:
                    pass
                # ── END SESSION EVENT ─────────────────────────────────────

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
                    if _dangerous_mode:
                        log_activity('dangerous_mode_bypass',
                                    f'⚠️ DANGEROUS MODE: gamma emergency FORCE_REDUCE bypassed '
                                    f'($Γ={session.get("_portfolio_dollar_gamma", 0):.2f})',
                                    sid, 'warning',
                                    {'dollar_gamma': session.get('_portfolio_dollar_gamma', 0),
                                     'dangerous_mode': True})
                    else:
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
                    if _dangerous_mode:
                        log_activity('dangerous_mode_bypass',
                                    f'⚠️ DANGEROUS MODE: regime PAUSE bypassed '
                                    f'(vol={vol_r}, trend={trend_r})',
                                    sid, 'warning',
                                    {'vol_regime': vol_r, 'trend_regime': trend_r,
                                     'dangerous_mode': True})
                    else:
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

                # Handle BLOCK_ALL_SELLS — skip trigger evaluation entirely,
                # UNLESS wind-down is also active.
                # When wind-down is active, we MUST let trigger evaluation run so the
                # OUTCOME_CE/PE path can execute buybacks instead of sells (line ~1786:
                # 'if blocked and regime_action != FORCE_REDUCE: wind-down buyback').
                # Proactive wind-down (every heartbeat regardless of trigger) was
                # intentionally removed — it caused unintended position erosion.
                if not _skip_to_pnl and regime_action == ACTION_BLOCK_ALL_SELLS:
                    if _dangerous_mode:
                        log_activity('dangerous_mode_bypass',
                                    f'⚠️ DANGEROUS MODE: BLOCK_ALL_SELLS regime bypassed — '
                                    f'trigger evaluation continuing',
                                    sid, 'warning',
                                    {'regime_action': str(regime_action), 'dangerous_mode': True})
                    elif is_wind_down_active(session):
                        # Wind-down is active — don't skip trigger evaluation.
                        # The OUTCOME_CE/PE path will call _process_wind_down_buyback()
                        # when a trigger fires, even though sells are blocked.
                        log_activity('regime_block',
                                    f'All sells blocked by regime — but wind-down is active: '
                                    f'trigger evaluation continues so buybacks can fire',
                                    sid, 'warning')
                    else:
                        log_activity('regime_block',
                                    f'All sells blocked by regime controls — skipping trigger evaluation',
                                    sid, 'warning')
                        _skip_to_pnl = True

            except Exception as e:
                log.warning(f"[{sid}] Regime check failed (non-fatal): {e}")
                # Regime failure is non-fatal — continue with normal heartbeat
                session['_regime_action'] = ACTION_NORMAL
        # ────────────────── END Regime Controls ──────────────────

        # Auto-resume if session was paused by regime/gamma and regime has now normalized
        if self._paused and not _skip_to_pnl:
            _pause_reason = session.get('_paused_reason', '')
            _was_regime_pause = (
                _pause_reason.startswith('Regime pause') or
                'Gamma emergency' in _pause_reason
            )
            if _was_regime_pause:
                _current_regime_action = session.get('_regime_action', ACTION_NORMAL)
                if _current_regime_action not in (ACTION_PAUSE, ACTION_FORCE_REDUCE):
                    log_activity(
                        'regime_auto_resume',
                        f'✅ Regime normalized — auto-resuming session (was paused: {_pause_reason})',
                        sid, 'success',
                        {
                            'new_regime_action': str(_current_regime_action),
                            'vol_regime': session.get('_vol_regime', 'NORMAL'),
                            'trend_regime': session.get('_trend_regime', 'NORMAL'),
                            'gamma_regime': session.get('_gamma_regime', 'NORMAL'),
                        },
                    )
                    self.resume('Regime normalized')

        # Auto-heal if paused by a guardian G3 violation and condition is resolved.
        # G3 fires when one side goes to 0 lots in a single beat (side wipeout).
        # This can happen during fill processing where state momentarily shows 0
        # before fills are applied. If both sides have lots on the next heartbeat,
        # the hedge is intact — auto-resume and alert via Telegram.
        if self._paused and not _skip_to_pnl:
            _pause_reason = session.get('_paused_reason', '')
            if (
                _pause_reason.startswith('Guardian violations:')
                and hasattr(self, '_guardian') and self._guardian
                and self._guardian.check_g3_healed(session)
            ):
                _ce_lots = session.get('ce', {}).get('active_lots', 0)
                _pe_lots = session.get('pe', {}).get('active_lots', 0)
                log_activity(
                    'guardian_auto_heal',
                    f'✅ Guardian G3 violation healed — CE={_ce_lots} active lots, '
                    f'PE={_pe_lots} active lots — auto-resuming session',
                    sid, 'success',
                    {'ce_active_lots': _ce_lots, 'pe_active_lots': _pe_lots,
                     'was_paused': _pause_reason},
                )
                try:
                    import asyncio as _asyncio
                    from .mmm_telegram import alert_guardian_healed as _tg_gh
                    _asyncio.ensure_future(_tg_gh(sid, _pause_reason))
                except Exception as _e:
                    log.warning(f"[{sid}] Guardian heal Telegram failed: {_e}")
                self.resume('Guardian healed — both sides have positions')
                # Skip trading this heartbeat — let the operator see the Telegram
                # alert before the algo fires any new orders. The resume takes
                # effect next heartbeat under normal flow.
                _skip_to_pnl = True

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

        # Step 5: Cooldown check (§14.3)
        if not _skip_to_pnl and is_cooldown_active(session):
            if _dangerous_mode:
                # Dangerous mode: bypass reversal cooldown — log once then continue
                if not session.get('_cooldown_block_logged'):
                    log_activity('dangerous_mode_bypass',
                                 f'⚠️ DANGEROUS MODE: reversal cooldown bypassed '
                                 f'(until {str(session.get("cooldown_until", "?"))[:19]})',
                                 sid, 'warning',
                                 {'cooldown_until': session.get('cooldown_until'),
                                  'dangerous_mode': True})
                    session['_cooldown_block_logged'] = True
                # Clear cooldown so it doesn't block _process_adjustment either
                session['cooldown_active'] = False
                session['cooldown_until'] = None
                session.pop('_cooldown_block_logged', None)
            else:
                # Log once per cooldown activation so the activity log shows WHY
                # force-heartbeat or a normal beat produced no hedge.
                if not session.get('_cooldown_block_logged'):
                    log_activity('cooldown_blocking',
                                 f'⏰ Cooldown active — trigger evaluation skipped '
                                 f'(until {str(session.get("cooldown_until", "?"))[:19]})',
                                 sid, 'info',
                                 {'cooldown_until': session.get('cooldown_until')})
                    session['_cooldown_block_logged'] = True
                _skip_to_pnl = True

        # Step 5.3: Adaptive Tuning Engine — parameter optimization per market regime
        # Runs only when adaptive_mode='adaptive'. No-op for 'manual' and 'preset'.
        # Never raises — wrapped so any bug here cannot kill the heartbeat.
        try:
            get_adaptive_engine().evaluate(session, minutes_to_expiry)
        except Exception as _adapt_err:
            log.error(f"[{sid}] Adaptive engine error: {_adapt_err}", exc_info=True)

        # ── Step 5.4: Straddle Roll ─────────────────────────────────────────
        # Full ATM reset for STRADDLE_WITH_ADJUSTMENT sessions. Only fires when
        # _preset_source is STRADDLE_WITH_ADJUSTMENT and straddle_roll_enabled is True.
        # NOTE: _skip_to_pnl is intentionally NOT checked here (same pattern as
        # ATM Shield). The roll is the primary risk-management action — a trailing
        # stop or guardrail block (stop_adjustments) must NOT prevent the roll.
        # Only a paused/stopped session suppresses the roll.
        if (params.get('straddle_roll_enabled', False)
                and params.get('_preset_source') in (
                    STRADDLE_WITH_ADJUSTMENT_CATEGORY, SHORT_STRADDLE_CATEGORY
                )
                and not self._paused):
            try:
                from .mmm_straddle_adjustment import execute_straddle_roll
                _straddle_roll_fired = await execute_straddle_roll(
                    self, session, sid, minutes_to_expiry
                )
                if _straddle_roll_fired:
                    _skip_to_pnl = True
            except Exception as _roll_err:
                log.error(f"[{sid}] Straddle Roll error: {_roll_err}", exc_info=True)
        elif (params.get('_preset_source') == STRADDLE_ROLL_CATEGORY
                and not self._paused):
            # Pure straddle roll — no adjustment engine between rolls.
            # This branch is mutually exclusive with the STRADDLE_WITH_ADJUSTMENT block above:
            # a session has exactly one _preset_source value.
            try:
                from .mmm_straddle_roll_pure import execute_pure_straddle_roll
                _pure_roll_fired = await execute_pure_straddle_roll(
                    self, session, sid, minutes_to_expiry
                )
                if _pure_roll_fired:
                    _skip_to_pnl = True
            except Exception as _pure_roll_err:
                log.error(f"[{sid}] Pure Straddle Roll error: {_pure_roll_err}", exc_info=True)
        # ────────────────────────────────────────────────────────────────────

        # Step 5.5: ATM Shield — proactive close & retreat
        # Runs regardless of _skip_to_pnl: the shield does buybacks (closes), not new sells.
        # Position cap and BLOCK_ALL_SELLS must not suppress it — that is what caused the
        # Mar 21 incident (CE near-ATM for 4.5h with no shield response).
        # The shield's own internal vol_gamma_blocked guard prevents the re-sell step when
        # gamma=HARD or vol=ELEVATED, so regime blocking is already handled internally.
        # Only exception: paused session — nothing should trade while paused.
        if params.get('atm_shield_enabled', False) and not self._paused:
            try:
                _shield_fired = await execute_atm_shield(self, ce_now, pe_now)
                if _shield_fired:
                    session['_atm_shield_fired'] = True
            except Exception as _shield_err:
                log.error(f"[{sid}] ATM Shield error: {_shield_err}", exc_info=True)

        # Step 5.6: Proactive Shift Scanner (T3-1) — MOVED HERE from Step 1.5
        # Fix A1 (March 12 incident): proactive shift previously ran BEFORE safety
        # checks, bypassing lot_velocity, asymmetry, margin tier, and regime blocks.
        # Now gated behind _skip_to_pnl so all safety mechanisms are respected.
        if not _skip_to_pnl and session.get('params', {}).get('proactive_shift_enabled', True):
            session.pop('_proactive_shifted_ce', None)
            session.pop('_proactive_shifted_pe', None)
            await self._proactive_shift_scan(ce_now, pe_now)

        # Step 5.7: Breakeven Engine — compute portfolio breakeven awareness
        # Runs regardless of _skip_to_pnl so UI data stays fresh.
        # No API calls — intrinsic-only model uses in-memory data only.
        if params.get('breakeven_control_enabled', False):
            # H1 FIX: Reset multiplier to safe default every beat before attempting compute.
            # If be_spot==0 or engine throws, the stale value from the previous
            # beat must not persist — a stale CRITICAL multiplier (2.5x) would
            # silently apply until the engine recovers.
            session['_breakeven_multiplier'] = 1.0
            try:
                be_engine = get_breakeven_engine()
                be_spot = session.get('_regime_spot_price', 0) or 0
                if be_spot > 0:
                    be_result = be_engine.compute_breakeven(session, be_spot)
                    session['_breakeven_result'] = be_result
                    session['_breakeven_multiplier'] = be_engine.get_aggression_multiplier(be_result)
                    session['_breakeven_zone'] = be_result.get('zone', 'SAFE')

                    # Log zone transitions
                    prev_zone = session.get('_breakeven_zone_prev', 'SAFE')
                    new_zone = be_result.get('zone', 'SAFE')
                    if new_zone != prev_zone:
                        log_activity(
                            'breakeven_zone_change',
                            f'Breakeven zone: {prev_zone} → {new_zone} | '
                            f'nearest={be_result.get("nearest_distance_pct") or "N/A"}% | '
                            f'multiplier={be_result.get("multiplier", 1.0):.2f}x',
                            sid, 'warning' if new_zone in ('DANGER', 'CRITICAL') else 'info',
                            {'prev_zone': prev_zone, 'new_zone': new_zone,
                             'nearest_pct': be_result.get('nearest_distance_pct'),
                             'multiplier': be_result.get('multiplier', 1.0)},
                        )
                    session['_breakeven_zone_prev'] = new_zone

                    # Log band contraction
                    if be_result.get('band_contracting'):
                        log_activity(
                            'breakeven_band_contracting',
                            f'Breakeven band contracting: '
                            f'{be_result.get("band_width_prev_pct", 0):.1f}% → '
                            f'{be_result.get("band_width_pct", 0):.1f}%',
                            sid, 'warning',
                            {'band_width_pct': be_result.get('band_width_pct'),
                             'band_width_prev_pct': be_result.get('band_width_prev_pct')},
                        )

                    # Log narrow band
                    if be_result.get('is_narrow_band'):
                        log_activity(
                            'breakeven_narrow_band',
                            f'Narrow Breakeven Band: {be_result.get("band_width_pct", 0):.1f}% — '
                            f'Consider reducing exposure',
                            sid, 'warning',
                            {'band_width_pct': be_result.get('band_width_pct'),
                             'threshold': params.get('breakeven_narrow_band_threshold', 5.0)},
                        )
            except Exception as _be_err:
                log.error(f"[{sid}] Breakeven engine error: {_be_err}", exc_info=True)

        # Step 5.8: Gamma Detector — portfolio curvature scanning
        # Runs regardless of _skip_to_pnl so UI data stays fresh.
        # Observation-only: stored in session, does NOT influence lot sizing (Phases 1-8).
        if params.get('gamma_detector_enabled', False):
            try:
                gd = get_gamma_detector()
                gd_spot = session.get('_regime_spot_price', 0) or 0
                if gd_spot > 0:
                    gd_result = gd.compute_gamma(
                        session, gd_spot,
                        be_engine=get_breakeven_engine()
                    )
                    session['_gamma_result'] = gd_result

                    # Log zone transitions
                    prev_gamma_zone = session.get('_gamma_zone_prev', 'SAFE')
                    new_gamma_zone = gd_result.get('gamma_zone', 'SAFE')
                    if new_gamma_zone != prev_gamma_zone:
                        log_activity(
                            'gamma_zone_change',
                            f'Gamma zone: {prev_gamma_zone} → {new_gamma_zone} | '
                            f'nearest={gd_result.get("nearest_distance_pct") or "N/A"}% | '
                            f'lower_boundary={gd_result.get("lower_gamma_boundary")} | '
                            f'upper_boundary={gd_result.get("upper_gamma_boundary")}',
                            sid,
                            'warning' if new_gamma_zone == 'DANGER' else 'info',
                            {'prev_zone': prev_gamma_zone, 'new_zone': new_gamma_zone,
                             'nearest_pct': gd_result.get('nearest_distance_pct'),
                             'lower_boundary': gd_result.get('lower_gamma_boundary'),
                             'upper_boundary': gd_result.get('upper_gamma_boundary')},
                        )
                        if new_gamma_zone == 'DANGER':
                            log_activity(
                                'gamma_danger_detected',
                                f'Gamma DANGER — losses will accelerate rapidly near '
                                f'lower={gd_result.get("lower_gamma_boundary")} / '
                                f'upper={gd_result.get("upper_gamma_boundary")}',
                                sid, 'warning', gd_result,
                            )
                    session['_gamma_zone_prev'] = new_gamma_zone
            except Exception as _gd_err:
                log.warning(f'[{sid}] Gamma detector error (non-fatal): {_gd_err}')

        # ── Skip trigger evaluation + adjustments when safety blocks ──
        # When trailing stop (or other stop_adjustments safety) fires,
        # skip directly to P&L update so peak_pnl decays and session saves.
        if _skip_to_pnl:
            self._emit_heartbeat_data(ce_now, pe_now)
            # Fall through to Step 7.5 (perp hedge) + Step 8 (P&L) + save + record_beat

        if not _skip_to_pnl:
            # Shield fired this beat → skip trigger evaluation (snapshots are stale)
            if session.pop('_atm_shield_fired', False):
                log.info(f"[{sid}] ATM Shield fired this beat — skipping trigger evaluation")
                _skip_to_pnl = True
                self._emit_heartbeat_data(ce_now, pe_now)

        if not _skip_to_pnl:
            # Step 6: Evaluate triggers (§7)
            # NOTE: Trigger snapshot healing moved earlier (runs even when paused).

            # Adaptive Whipsaw Guard: widen triggers based on score
            _ws_score = session.get('_whipsaw_score', 0)
            _ws_params = session.get('params', {})
            _ws_caution = _ws_params.get('whipsaw_caution_score', 2)
            _ws_restrict = _ws_params.get('whipsaw_restrict_score', 3)
            if _ws_score >= _ws_restrict:
                _ws_factor = 2.0
            elif _ws_score >= _ws_caution:
                _ws_factor = 1.5
            else:
                _ws_factor = 1.0
            if _ws_factor > 1.0:
                # Always use the raw config param as base for whipsaw widening.
                # _effective_min_trigger_move may already carry theta-acceleration
                # (applied earlier in the heartbeat near expiry).  Multiplying that
                # value again compounds the two factors multiplicatively (4× intended
                # in the worst case).  Instead: compute each widening independently
                # and take the max so whichever adjustment is larger prevails.
                _raw_trigger = _ws_params.get('min_trigger_move', 10.0)
                _ws_widened = _raw_trigger * _ws_factor
                _theta_widened = session.get('_effective_min_trigger_move', _raw_trigger)
                session['_effective_min_trigger_move'] = max(_ws_widened, _theta_widened)
                session['_whipsaw_trigger_widened'] = True

            trigger_result = evaluate_triggers(session, ce_now, pe_now)
            outcome = trigger_result['outcome']

            # Phase 2: Frozen PnL fallback trigger.
            # Only runs when the active-strike trigger did NOT fire (OUTCOME_NONE).
            # This is the double-hedging prevention gate: active and frozen triggers
            # are mutually exclusive within a single heartbeat. If active fired, frozen
            # positions will be covered by calculate_standard_loss in _process_adjustment
            # (it already includes frozen losses) and snapshots will be ratcheted after.
            # Also skipped during wind-down — wind-down has its own buyback path.
            if outcome == OUTCOME_NONE and not is_wind_down_active(session):
                _frozen_result = check_frozen_pnl_trigger(
                    session, self._make_fetch_fn(), ce_now, pe_now,
                )
                if _frozen_result['outcome'] != OUTCOME_NONE:
                    outcome = _frozen_result['outcome']
                    trigger_result = _frozen_result
                    log_activity('info',
                                 f'📍 Frozen PnL trigger: '
                                 f'CE=${_frozen_result["ce_frozen_loss"]:.2f} '
                                 f'PE=${_frozen_result["pe_frozen_loss"]:.2f} '
                                 f'(threshold=${_frozen_result["min_frozen_trigger_dollar"]:.2f}) '
                                 f'→ {outcome}',
                                 sid, 'info',
                                 {'ce_frozen_loss': _frozen_result['ce_frozen_loss'],
                                  'pe_frozen_loss': _frozen_result['pe_frozen_loss'],
                                  'trigger_type': 'frozen_pnl'})

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
                'frozen_triggered': trigger_result.get('frozen_triggered', False),
            }

            # Step 7: Process outcome (§4.7)
            if outcome == OUTCOME_NONE:
                # FSU: Favorable Scale-Up — add positions when both sides are decaying
                if not is_wind_down_active(session):
                    await self._process_scale_up(ce_now, pe_now)
                # Wind-down + no trigger: just wait. Close-at-5 handles cheap positions.
                # Proactive wind-down every heartbeat was intentionally removed (position erosion).

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

                # IMP-12: Telegram push notification — only fires on first entry to BOTH_SIDES_UP
                # (subsequent beats with status already BOTH_SIDES_UP skip this block via
                # the OUTCOME_BOTH / _BOTH_SIDES_UP state logic, so re-fire guard not needed)
                try:
                    await alert_both_sides_up(
                        sid, ce_now, pe_now,
                        trigger_result['ce_trigger'],
                        trigger_result['pe_trigger'],
                    )
                except Exception as _tg_err:
                    log.warning(f"[{sid}] Both-sides-up Telegram alert failed: {_tg_err}")

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

                # ── Tier D: Delta Rescue ──────────────────────────────────────
                # Near expiry, the algo MUST hedge when a trigger fires.  A
                # forced hedge sell cannot be blocked by gamma regime — the
                # unhedged directional exposure is more dangerous than the
                # gamma risk of adding one more hedge lot.
                # Only hard overrides survive: FORCE_REDUCE (gamma emergency)
                # and PAUSE (session-level halt).  Wind-down and margin blocks
                # are checked below in the elif chain and still apply.
                if blocked and regime_action not in (ACTION_FORCE_REDUCE, ACTION_PAUSE):
                    _rescue_window = params.get('gamma_rescue_window_minutes', 120)
                    if minutes_to_expiry is not None and minutes_to_expiry <= _rescue_window:
                        log_activity(
                            'delta_rescue',
                            f'Delta Rescue: regime block overridden for {hedge.upper()} '
                            f'hedge sell — {minutes_to_expiry:.0f}m to expiry '
                            f'(window: {_rescue_window}m) | was blocked by: {block_reason}',
                            sid, 'warning',
                            {'hedge': hedge, 'aggressor': aggressor,
                             'original_block': block_reason,
                             'minutes_to_expiry': minutes_to_expiry},
                        )
                        emit_safety(
                            sid, 'delta_rescue', 'warning',
                            f'Delta Rescue: {hedge.upper()} hedge allowed '
                            f'({block_reason} overridden, {minutes_to_expiry:.0f}m to expiry)',
                            {'minutes_to_expiry': minutes_to_expiry,
                             'block_reason': block_reason},
                        )
                        blocked = False
                        session['_delta_rescue_count'] = (
                            session.get('_delta_rescue_count', 0) + 1
                        )
                        session['_delta_rescue_last_at'] = (
                            datetime.now(timezone.utc).isoformat()
                        )
                # ── End Tier D ────────────────────────────────────────────────

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
                    if is_wind_down_active(session):
                        await self._process_wind_down_buyback(aggressor, ce_now, pe_now)
                # Wind-down mode: reduce instead of adding positions
                elif is_wind_down_active(session):
                    session['_wind_down_mode'] = True
                    # Reverse Mode: disable immediately when wind-down activates.
                    # Reverse positions are unhedged — wind-down and reverse are incompatible.
                    # Sync context only: set flags, do not await.
                    if session.get('_reverse', {}).get('active', False):
                        disable_reverse_mode(session, 'wind_down_activated')
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
                        # ORANGE tier: force aggressive buyback — NOT bypassed even in dangerous mode
                        # (ORANGE margin means selling more would push toward liquidation)
                        log_activity('margin_wind_down',
                                    f'🟠 MARGIN WIND-DOWN ({margin_util:.1f}%): '
                                    f'{aggressor.upper()} triggered — reducing positions '
                                    f'instead of adding (tier: {margin_tier})',
                                    sid, 'warning',
                                    {'margin_tier': margin_tier, 'utilization': margin_util})
                        await self._process_wind_down_buyback(
                            aggressor, ce_now, pe_now,
                        )
                    elif _dangerous_mode:
                        # YELLOW tier + dangerous mode: bypass the sell block, proceed to adjustment
                        log_activity('dangerous_mode_bypass',
                                    f'⚠️ DANGEROUS MODE: margin YELLOW sell-block bypassed '
                                    f'({margin_util:.1f}%, tier: {margin_tier})',
                                    sid, 'warning',
                                    {'margin_tier': margin_tier, 'utilization': margin_util,
                                     'dangerous_mode': True})
                        # Fall through to adjustment (no `else` branch taken)
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

                    # ── Reverse Mode intercept (hard mutual exclusion) ──────────
                    # When reverse mode is active, ONLY reverse entry runs.
                    # _process_adjustment() is completely bypassed.
                    # When reverse is OFF, this block has zero effect.
                    if session.get('params', {}).get('reverse_enabled', False) and \
                            session.get('_reverse', {}).get('active', False):
                        await process_reverse_entry(
                            session, aggressor, hedge, ce_now, pe_now, self._engine
                        )
                    else:
                        # Normal MMM adjustment path (unmodified)

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
                    # BUG FIX (Mar 12 2026): use active_strike not original_strike.
                    # After shifts the active strike is the current risk exposure.
                    ce_orig_strike = float(session.get('ce', {}).get('active_strike', 0) or 0)
                    pe_orig_strike = float(session.get('pe', {}).get('active_strike', 0) or 0)
                    ce_total_lots = session.get('ce', {}).get('active_lots', 0)
                    pe_total_lots = session.get('pe', {}).get('active_lots', 0)
                    atm_triggered_side = None

                    if ce_orig_strike > 0 and ce_total_lots > 0 and perp_btc_mark > 0:
                        dist_pct = abs(ce_orig_strike - perp_btc_mark) / perp_btc_mark * 100
                        if dist_pct <= atm_threshold_pct:
                            atm_gate_passed = True
                            atm_triggered_side = 'CE'
                            log.info(
                                f"[{sid}] Perp ATM gate: CE ACTIVE strike "
                                f"{ce_orig_strike:.0f} is {dist_pct:.1f}% "
                                f"from spot {perp_btc_mark:.0f} (threshold {atm_threshold_pct}%)"
                            )

                    if not atm_gate_passed and pe_orig_strike > 0 and pe_total_lots > 0 and perp_btc_mark > 0:
                        dist_pct = abs(pe_orig_strike - perp_btc_mark) / perp_btc_mark * 100
                        if dist_pct <= atm_threshold_pct:
                            atm_gate_passed = True
                            atm_triggered_side = 'PE'
                            log.info(
                                f"[{sid}] Perp ATM gate: PE ACTIVE strike "
                                f"{pe_orig_strike:.0f} is {dist_pct:.1f}% "
                                f"from spot {perp_btc_mark:.0f} (threshold {atm_threshold_pct}%)"
                            )

                    if not atm_gate_passed:
                        log.debug(
                            f"[{sid}] Perp ATM-only mode: active strikes "
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

        # Reverse emergency baseline: snapshot core-only P&L BEFORE the update
        # so check_reverse_emergency() has a valid prev baseline to compare against.
        # Core-only = realized + unrealized - fees + perp (excludes reverse P&L).
        if session.get('_reverse', {}).get('active', False):
            session['_prev_core_net_pnl'] = (
                float(session.get('realized_pnl', 0.0))
                + float(session.get('unrealized_pnl', 0.0))
                - float(session.get('total_fees', 0.0))
                + float(session.get('perp_hedge', {}).get('realized_pnl', 0.0) or 0.0)
                + float(session.get('perp_hedge', {}).get('unrealized_pnl', 0.0) or 0.0)
            )

        pnl = self._engine.compute_total_pnl(
            session, self._make_fetch_fn()
        )
        session['unrealized_pnl'] = pnl['unrealized']

        # T2-5: Mirror perp hedge realized P&L to attribution field (sync, not incremental)
        session['pnl_perp'] = session.get('perp_hedge', {}).get('realized_pnl', 0.0)

        # Reverse Mode M2M hook: MUST run BEFORE update_peak_pnl so peak sees
        # fresh reverse P&L (not stale values from the previous heartbeat).
        # M2M and close-at-threshold run whenever there are open reverse positions
        # (mode may be OFF already — positions close in normal operation).
        # Emergency check only runs while mode is actively ON.
        _rev_has_open = any(
            p.get('status') == 'open'
            for p in session.get('_reverse', {}).get('positions', [])
        )
        if _rev_has_open:
            try:
                update_reverse_mtm(session, ce_now, pe_now)
            except Exception as _rev_mtm_err:
                log.warning(f"[{sid}] reverse MTM update failed (non-fatal): {_rev_mtm_err}")
            try:
                await check_reverse_close_at_threshold(session, ce_now, pe_now, self._engine)
            except Exception as _rev_close_err:
                log.warning(f"[{sid}] reverse close-at-threshold check failed (non-fatal): {_rev_close_err}")
        if session.get('_reverse', {}).get('active', False):
            try:
                rev_emergency = check_reverse_emergency(session)
                if rev_emergency:
                    log.warning(f"[{sid}] Reverse emergency detected: {rev_emergency} — disabling reverse mode")
                    disable_reverse_mode(session, rev_emergency)
            except Exception as _rev_emerg_err:
                log.warning(f"[{sid}] reverse emergency check failed (non-fatal): {_rev_emerg_err}")

        # Include reverse P&L in peak tracking so trailing stop accounts for it.
        # Now uses FRESH reverse P&L updated by the M2M hook above.
        _reverse_net_pnl = float(session.get('_reverse', {}).get('net_pnl', 0.0) or 0.0)
        total_for_peak = pnl['net_pnl'] + _reverse_net_pnl
        update_peak_pnl(session, total_for_peak)

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

        # Performance Intelligence: track phase transitions (zero I/O)
        if self._perf_collector:
            try:
                self._perf_collector.on_heartbeat(
                    datetime.now(timezone.utc),
                    pnl['net_pnl'], pnl['realized'], pnl['unrealized'],
                )
            except Exception:
                pass  # Never block heartbeat for performance tracking

        # §13.3 POST-UPDATE MAX LOSS CHECK: Immediate enforcement
        # Safety checks in Step 3 use previous heartbeat's P&L.
        # This check catches max_loss breach on the SAME heartbeat.
        max_loss_amount = session.get('params', {}).get('max_loss_amount', 5000.0)
        # Include reverse P&L so max_loss check sees the complete picture.
        current_total_pnl = pnl['net_pnl'] + float(session.get('_reverse', {}).get('net_pnl', 0.0) or 0.0)
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

        # Guardian post-beat check — detect invariant violations
        if hasattr(self, '_guardian') and self._guardian and _guardian_snapshot:
            _violations = self._guardian.post_beat_check(session, _guardian_snapshot)
            if _violations:
                self._guardian.handle_violations(self, _violations)

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

        # ── Auto-Reconcile: periodic drift check (ARCH-1 fix) ────────────────
        # Compares audit log totals vs live session state every N beats.
        # Detects silent drift without self-healing — emits alert for human review.
        _recon_interval = session.get('params', {}).get('auto_recon_interval_beats', 50)
        if _recon_interval and heartbeat_counter > 0 and heartbeat_counter % _recon_interval == 0:
            try:
                from .mmm_audit_reconciler import reconcile_session as _do_reconcile
                _recon = _do_reconcile(sid, session)
                if not _recon.get('is_clean'):
                    _disc = _recon.get('position_discrepancies', [])
                    _pnl_delta = _recon.get('pnl_delta', 0)
                    _alert_msg = (
                        f"⚠️ AUTO-RECON MISMATCH @ beat {heartbeat_counter}: "
                        f"P&L delta=${_pnl_delta:.4f} | "
                        f"position discrepancies={len(_disc)}"
                    )
                    log.warning(f"[{sid}] {_alert_msg} — {_disc}")
                    log_activity('safety', _alert_msg, sid, 'warning', {
                        'pnl_delta': _pnl_delta,
                        'position_discrepancies': _disc,
                        'auto_recon_beat': heartbeat_counter,
                    })
                    session['_last_auto_recon_clean'] = False
                    session['_last_auto_recon_beat'] = heartbeat_counter
                    session['_last_auto_recon_discrepancies'] = _disc
                else:
                    log.debug(f"[{sid}] Auto-recon OK @ beat {heartbeat_counter}")
                    session['_last_auto_recon_clean'] = True
                    session['_last_auto_recon_beat'] = heartbeat_counter
            except Exception as _recon_err:
                log.warning(f"[{sid}] Auto-recon failed (non-fatal): {_recon_err}")

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

            # ── GUARDIAN G1: HEDGE INTEGRITY GATE ─────────────────────────
            # Centralized check via MMMGuardian (replaces inline hedge guard).
            if hasattr(self, '_guardian') and self._guardian:
                _allowed, _g_reason = self._guardian.check_close_allowed(
                    session, aggressor, group_lots, 'wind_down',
                    both_sides_closing=False,
                )
                if not _allowed:
                    log.warning(
                        f"[{sid}] GUARDIAN BLOCK (wind-down): {group_lots} "
                        f"{aggressor.upper()} @ {strike_val} — {_g_reason}"
                    )
                    any_failed = True
                    continue
            # ── END GUARDIAN G1 ──────────────────────────────────────────────

            # ── STRATEGY OBSERVER VALIDATION ─────────────────────────────────
            # Validate wind-down buyback against strategy logic before smart_execute.
            # Uses group's weighted average entry premium for price consistency check.
            try:
                from .mmm_observer import get_observer
                current_premium = self._make_fetch_fn()(strike_val, option_type)
                if current_premium is None:
                    current_premium = 0  # Fallback if premium fetch fails
                _obs_result = get_observer().validate_close(
                    session=session,
                    side=aggressor,
                    lots=group_lots,
                    current_premium=current_premium,
                    mechanism='wind_down',
                    entry_premium=group_avg_entry,
                    both_sides_closing=False,
                )
                if not _obs_result['allowed']:
                    log.warning(
                        f"[{sid}] OBSERVER BLOCK (wind-down): {group_lots} "
                        f"{aggressor.upper()} @ {strike_val} — {_obs_result['reason']}"
                    )
                    log_activity('wind_down',
                                f'🌙 Wind-Down BLOCKED: {_obs_result["reason"]}',
                                sid, 'warning',
                                {'error': _obs_result['reason'], 'lots': group_lots, 
                                 'strike': strike_val, 'block_type': _obs_result.get('block_type')})
                    any_failed = True
                    continue
            except Exception as _obs_e:
                log.warning(f"[{sid}] Observer validation failed (wind-down): {_obs_e}")
                # Continue with buyback if observer fails (graceful degradation)
            # ── END STRATEGY OBSERVER VALIDATION ─────────────────────────────

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

            # Fix F1.2 (wind-down): Pre-mark _being_closed on positions to prevent
            # concurrent close by close-at-5 or recycler during async smart_execute.
            _wd_marked_ids = []
            _wd_mark_ts = time.monotonic()
            for rec in group_records:
                _pid = rec.get('_pos_id')
                if _pid:
                    for p in side_state.get('positions', []):
                        if p.get('id') == _pid:
                            p['_being_closed'] = True
                            p['_being_closed_at'] = _wd_mark_ts
                            _wd_marked_ids.append(_pid)
                            break

            try:
                _reprice_max = self.session.get('params', {}).get('max_reprice_attempts', None)
                result = await self.executor.smart_execute(
                    symbol=symbol,
                    side='buy',
                    size=group_lots,
                    reduce_only=True,
                    max_reprice_attempts=_reprice_max,
                    session_id=sid,
                )

                if not result.get('success'):
                    # Clear _being_closed flags on failure so positions can be retried
                    for _pid in _wd_marked_ids:
                        for p in side_state.get('positions', []):
                            if p.get('id') == _pid:
                                p.pop('_being_closed', None)
                                break
                    log_activity('wind_down',
                                f'🌙 Wind-Down FAILED: Could not buy back {group_lots} '
                                f'{aggressor.upper()} @ {strike_val} — {result.get("error", "unknown")}',
                                sid, 'error',
                                {'error': result.get('error'), 'lots': group_lots, 'strike': strike_val})
                    any_failed = True
                    continue

                close_price = result.get('fill_price', 0)
                # AUDIT BUG-2 FIX: Use actual filled size for P&L calculation.
                actual_filled = result.get('filled_size', group_lots)
                if actual_filled <= 0:
                    actual_filled = group_lots
                if actual_filled < group_lots:
                    log.warning(
                        f"[{sid}] Wind-down PARTIAL FILL: requested {group_lots} "
                        f"{aggressor.upper()} @ {strike_val}, only {actual_filled} filled."
                    )

                # Apply LIFO removals for this strike's records only
                avg_entry = apply_lifo_removals(side_state, group_records)
                session[aggressor] = side_state

                # Realized P&L for this strike group
                group_realized = (avg_entry - close_price) * actual_filled * LOT_SIZE_BTC
                total_realized += group_realized
                # Record exchange commission (fee) — Delta uses 'paid_commission' for actual fees
                _od = result.get('order_details') or {}
                _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)

                # ── P&L via ledger (single source of truth) ──────────
                _wd_close_oid = str(result.get('order_id', '') or '')
                from .mmm_pnl_core import record_close as _pnl_record
                _pnl_record(
                    session=session,
                    order_id=_wd_close_oid,
                    symbol=result.get('symbol', ''),
                    option_side=aggressor,
                    strike=strike_val,
                    lots=int(actual_filled),
                    entry_premium=float(avg_entry),
                    close_premium=float(close_price),
                    commission=abs(float(_commission)) if _commission else 0.0,
                    source='wind_down',
                )
                # ── END P&L via ledger ───────────────────────────────

                # Stamp close_order_id on positions for FillSyncer matching
                _wd_close_coid = str(result.get('client_order_id', '') or '')
                for _wp in side_state.get('positions', []):
                    if (_wp.get('status') == 'closed'
                            and _wp.get('_estimated_pnl_booked') is None):
                        if _wd_close_oid:
                            _wp['close_order_id'] = _wd_close_oid
                        if _wd_close_coid:
                            _wp['close_client_order_id'] = _wd_close_coid
                        _wp_entry = float(_wp.get('entry_premium', 0) or 0)
                        _wp_lots = float(_wp.get('_closed_lots', _wp.get('lots', 0)) or 0)
                        if _wp_lots > 0 and _wp_entry > 0:
                            _wp['_estimated_pnl_booked'] = round(
                                (_wp_entry - close_price) * _wp_lots * LOT_SIZE_BTC, 8)
                            _wp['_estimated_commission_booked'] = round(
                                abs(_commission) * _wp_lots / actual_filled, 8) if _commission and actual_filled else 0.0

                # Record successful close for velocity tracking (observer + guardian)
                try:
                    from .mmm_observer import get_observer
                    get_observer().record_close(sid, aggressor, actual_filled)
                except Exception:
                    pass
                if hasattr(self, '_guardian') and self._guardian:
                    try:
                        self._guardian.record_close(aggressor, actual_filled)
                    except Exception:
                        pass

                log_activity('wind_down',
                            f'🌙 Wind-Down leg: Bought back {actual_filled} {aggressor.upper()} '
                            f'@ {strike_val} fill ${close_price:.2f} '
                            f'(avg entry ${avg_entry:.2f}, P&L ${group_realized:.2f})',
                            sid, 'success',
                            {'side': aggressor.upper(), 'strike': strike_val,
                             'lots': actual_filled, 'close_price': close_price,
                             'avg_entry': round(avg_entry, 2),
                             'realized_pnl': round(group_realized, 2)})

                # ── TRADE AUDIT: wind-down LIFO buyback ───────────────────
                try:
                    from .mmm_audit_log import get_audit_log as _get_aud
                    from .mmm_audit_remark import build_trade_remark as _btr
                    _get_aud().enqueue_trade(
                        session_id=sid,
                        action='BUY',
                        option_type=aggressor.upper(),
                        strike=int(strike_val),
                        quantity_requested=group_lots,
                        quantity_filled=actual_filled,
                        premium=close_price,
                        event_type='WIND_DOWN',
                        mechanism='wind_down',
                        order_id=str(result.get('order_id', '')),
                        expiry=session.get('params', {}).get('expiry', ''),
                        closing_entry_premium=float(avg_entry),
                        closing_entry_lots=actual_filled,
                        realized_pnl_usd=float(group_realized),
                        spot_price_usd=float(session.get('_regime_spot_price', 0) or 0),
                        remark=_btr(
                            'BUY', 'WIND_DOWN',
                            side=aggressor, strike=int(strike_val),
                            lots=actual_filled, premium=close_price,
                            mechanism='wind_down',
                            entry_premium=float(avg_entry),
                            realized_pnl=float(group_realized),
                            is_partial=(actual_filled < group_lots),
                        ),
                    )
                except Exception:
                    pass
                # ── END TRADE AUDIT ───────────────────────────────────────

            except Exception as e:
                # Clear _being_closed flags on exception so positions can be retried
                for _pid in _wd_marked_ids:
                    for p in side_state.get('positions', []):
                        if p.get('id') == _pid:
                            p.pop('_being_closed', None)
                            break
                log.exception(f"[{sid}] Wind-down buyback @ {strike_val} failed: {e}")
                log_activity('wind_down',
                            f'🌙 Wind-Down ERROR @ {strike_val}: {str(e)}',
                            sid, 'error', {'error': str(e), 'strike': strike_val})
                any_failed = True

        # Always update trigger snapshots — even on partial failure.
        # Successful buybacks already mutated session state (lots removed,
        # P&L booked).  Skipping snapshot updates leaves stale trigger
        # baselines that cause spurious re-triggers on the next heartbeat
        # for positions that were already closed.
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
        order_id: str = '',
        client_order_id: str = '',
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
            'fill_confirmed_at': now,
            'order_id': order_id,
            'client_order_id': client_order_id,
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
        _side_prem_key = 'ce_premium_collected' if side.lower() == 'ce' else 'pe_premium_collected'
        session[_side_prem_key] = session.get(_side_prem_key, 0) + premium_collected

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
            'spot': session.get('_regime_spot_price', 0),
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
        params = session.get('params', {})

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

        # Asymmetry side-block: only block the heavy side — the light side is
        # allowed to sell so it can rebalance the position toward symmetry.
        _asym_blocked_side = session.get('_asymmetry_blocked_side', '')
        _dangerous_mode_adj = params.get('dangerous_mode', False)
        if _asym_blocked_side and hedge == _asym_blocked_side:
            if _dangerous_mode_adj:
                log_activity('dangerous_mode_bypass',
                            f'⚠️ DANGEROUS MODE: asymmetry 7:1 block bypassed — '
                            f'{hedge.upper()} sell proceeding',
                            sid, 'warning',
                            {'blocked_side': hedge, 'dangerous_mode': True})
            else:
                log_activity('asymmetry_side_blocked',
                            f'⚖️ {hedge.upper()} sell blocked: asymmetry 7:1 — '
                            f'{hedge.upper()} is the heavy side',
                            sid, 'warning',
                            {'blocked_side': hedge})
                return

        # §9: Check for reversal
        # FM1 fix: Consecutive reversal-skip circuit breaker.
        # If N skips have fired in a row without any real hedge executing,
        # the market is whipsawing and both sides keep skipping.  Force
        # standard formula so the accumulated loss gets hedged.
        # Dangerous mode: bypass circuit breaker — always use real reversal detection.
        _rev_skip_count = session.get('_consecutive_reversal_skip_count', 0)
        _rev_skip_threshold = params.get('reversal_skip_force_through', 3)
        if not _dangerous_mode_adj and _rev_skip_count >= _rev_skip_threshold:
            is_reversal = False
            log_activity('reversal_skip_force_through',
                        f'⚡ FORCE-THROUGH: {_rev_skip_count} consecutive reversal skips — '
                        f'bypassing reversal detection, using standard loss formula',
                        sid, 'warning',
                        {'count': _rev_skip_count,
                         'threshold': _rev_skip_threshold,
                         'aggressor': aggressor.upper()})
            emit_safety(
                sid, 'reversal_force_through', 'warning',
                f'Reversal force-through: {_rev_skip_count} skips without hedge — '
                f'standard formula applied',
                {'aggressor': aggressor.upper(), 'skip_count': _rev_skip_count},
            )
        else:
            is_reversal = detect_reversal(session, aggressor)

        if is_reversal:
            record_reversal(session, session.get('last_aggressor', 'NONE'), aggressor)

            # Robust v2 Fix #7: Reset peak P&L on reversal — new profit phase begins
            current_total = _pnl_total(session)
            reset_peak_pnl_on_reversal(session, current_total)

            # Analytics: Track reversal event (no trading logic impact)
            analytics = session.setdefault('analytics', {})
            analytics.setdefault('reversal_timestamps', []).append(datetime.now(timezone.utc).isoformat())
            if len(analytics['reversal_timestamps']) > 200:
                analytics['reversal_timestamps'] = analytics['reversal_timestamps'][-200:]

            # First reversal: use adjustment P&L formula
            # FM2 fix: calculate_reversal_loss now returns 4 values.
            # active_strike_pnl is the P&L of fills at the CURRENT active strike only.
            # adj_pnl is the full P&L including frozen positions at old strikes.
            loss, active_strike_pnl, adj_pnl, _rev_incomplete = self._engine.calculate_reversal_loss(
                session, aggressor, self._make_fetch_fn()
            )
            session['_last_adjustment_loss'] = float(loss)   # audit context only

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

            # §9: If ACTIVE-STRIKE adjustments still profitable, skip.
            # FM2 fix: pass active_strike_pnl as the gate — frozen profits
            # at old strikes must not block hedging of the active position.
            skip, skip_reason = should_skip_reversal_adjustment(
                session, active_strike_pnl, adj_pnl
            )
            if skip:
                log.info(f"[{sid}] {skip_reason}")
                log_activity('reversal_skip',
                             f'↩️ Reversal skip: {aggressor.upper()} triggered but '
                             f'active-strike adjustments still profitable '
                             f'(active=${active_strike_pnl:.2f}, total=${adj_pnl:.2f}) '
                             f'— no CE/PE hedge placed',
                             sid, 'info',
                             {
                                 'aggressor': aggressor.upper(),
                                 'prev_aggressor': session.get('last_aggressor', ''),
                                 'active_strike_pnl': active_strike_pnl,
                                 'adj_pnl': adj_pnl,
                             })
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
            if params.get('cooldown_on_reversal', True):
                activate_cooldown(session)
        else:
            # Standard or continuation — include frozen position losses
            loss, _std_incomplete = self._engine.calculate_standard_loss(
                session, aggressor, premium_now,
                fetch_premium_fn=self._make_fetch_fn(),
            )
            adj_type = 'standard'
            session['_last_adjustment_loss'] = float(loss)   # audit context only

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
                # FETCH-FALLBACK FIX: When calculation is incomplete, use the last
                # complete loss as a floor to prevent systematic under-hedging during
                # API degradation. Frozen position premiums couldn't be fetched, so
                # the computed loss is understated — don't go below what we last knew.
                _last_complete = session.get('_last_complete_std_loss', {}).get(aggressor, 0)
                if _last_complete > loss:
                    log.warning(
                        f"[{sid}] Applying last-complete std loss floor: "
                        f"${loss:.4f} → ${_last_complete:.4f} ({aggressor.upper()})"
                    )
                    loss = _last_complete
            else:
                # Cache the complete loss for use as a fallback on future incomplete beats
                session.setdefault('_last_complete_std_loss', {})[aggressor] = loss

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

        # §10b: Pre-sell shift — when enabled, shift to target premium BEFORE selling
        # cheap lots. Prevents lot accumulation in the grey zone (shift_threshold → shift_target_premium).
        # Default OFF — enable via WebUI toggle 'pre_sell_shift_enabled'.
        if params.get('pre_sell_shift_enabled', False):
            target_premium = params.get('shift_target_premium', 100.0)
            if hedge_premium < target_premium:
                spot_price = await self._fetch_spot_price()
                better = await asyncio.get_running_loop().run_in_executor(
                    None, find_new_strike, self.initializer, session, hedge, spot_price
                )
                if better:
                    log.info(
                        f"[{sid}] PROACTIVE SHIFT: {hedge.upper()} premium "
                        f"${hedge_premium:.2f} < target ${target_premium:.2f} — "
                        f"shifting to {better['strike']} @ {better['premium']:.2f} "
                        f"before selling"
                    )
                    self._hb_wt['shift'] = {
                        'side': hedge,
                        'reason': 'proactive_below_target',
                        'hedge_premium': hedge_premium,
                        'target_premium': target_premium,
                        'loss': loss,
                    }
                    await self._process_strike_shift(
                        hedge, loss, ce_now, pe_now,
                    )
                    return
                # No better strike found — fall through and sell at current premium

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

        # ── Adaptive Whipsaw Guard: lot reduction at RESTRICT+ ────────────
        _ws_score = session.get('_whipsaw_score', 0)
        _ws_restrict = session.get('params', {}).get('whipsaw_restrict_score', 3)
        if _ws_score >= _ws_restrict and lots > 1:
            _ws_orig_lots = lots
            lots = max(1, int(lots * 0.5))
            constraint_msg = (constraint_msg or '') + f' [whipsaw lot reduction {_ws_orig_lots}→{lots}]'
            log.info(
                f"[{sid}] Whipsaw RESTRICT lot reduction: "
                f"{_ws_orig_lots} → {lots} lots (score={_ws_score})"
            )

        # ── IMP-5: Consecutive same-direction adjustment limiter ──────────
        # Dangerous mode: skip the limiter entirely — operator accepts the risk.
        if not _dangerous_mode_adj:
            lots, constraint_msg = self._apply_consecutive_dir_limit(
                session, aggressor, lots, constraint_msg
            )
            # After applying the limit, check if we should block entirely
            if lots <= 0 and session.get('_consecutive_dir_blocked'):
                log_activity('consecutive_dir_blocked',
                            f'🚫 CONSECUTIVE {aggressor.upper()} BLOCKED: '
                            f'{session.get("_consecutive_same_dir_count", 0)} consecutive adjustments '
                            f'in same direction — force-heartbeat required to continue',
                            sid, 'warning',
                            {'side': aggressor, 'count': session.get('_consecutive_same_dir_count', 0)})
                emit_safety(sid, 'consecutive_dir_block', 'alert',
                           f'Consecutive {aggressor.upper()} direction limit reached')
                return
        # ── END IMP-5 ─────────────────────────────────────────────────────

        # ── Velocity headroom cap ──────────────────────────────────────────
        # Safety stage only BLOCKS when lots_in_window >= limit. If the window
        # is not yet full but this single sell would exceed it (e.g. window=0,
        # limit=30, lots=40), cap to remaining headroom.
        # Pre-flight mirror of MMMSafety.check_lot_velocity — keep params/logic in sync.
        if lots > 0 and params.get('lot_velocity_enabled', True):
            from datetime import timedelta as _td
            _vel_limit = params.get('lot_velocity_limit', 10)
            _vel_window = params.get('lot_velocity_window_mins', 30)
            _cutoff = datetime.now(timezone.utc) - _td(minutes=_vel_window)
            _lots_in_window = 0
            for _adj in session.get('adjustment_history', []):
                if _adj.get('aggressor', '') in ('OPERATOR', 'STRADDLE_ROLL'):
                    continue
                try:
                    _ts = datetime.fromisoformat(_adj.get('timestamp', ''))
                    if _ts.tzinfo is None:
                        _ts = _ts.replace(tzinfo=timezone.utc)
                    if _ts >= _cutoff:
                        _lots_in_window += _adj.get('lots_sold', 0)
                except (ValueError, TypeError):
                    continue
            _headroom = _vel_limit - _lots_in_window
            if lots > _headroom:
                log.info(
                    f"[{sid}] Adjustment: capping lots {lots} → {_headroom} "
                    f"(velocity headroom: {_lots_in_window}/{_vel_limit} in window)"
                )
                constraint_msg = (constraint_msg or '') + f' [velocity cap {lots}→{_headroom}]'
                lots = max(1, _headroom)
        # ── END velocity headroom cap ──────────────────────────────────────

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

                # §4.6 CAP-DRIVEN AUTO-SHIFT: M2 recycling failed (likely no
                # frozen positions to recycle).  Freeze current active positions
                # and shift to a new strike — this resets active_lots to 0 so
                # the algo can continue selling.
                log.info(
                    f"[{sid}] CAP AUTO-SHIFT: {hedge.upper()} capped at "
                    f"{session.get(hedge, {}).get('active_lots', 0)} lots, "
                    f"M2 recycling failed — triggering strike shift"
                )
                log_activity('cap_auto_shift',
                    f'🔄 CAP AUTO-SHIFT: {hedge.upper()} hit position cap, '
                    f'M2 recycling unavailable — freezing {session.get(hedge, {}).get("active_lots", 0)} '
                    f'lots and shifting to new strike',
                    sid, 'warning',
                    {'side': hedge.upper(), 'active_lots': session.get(hedge, {}).get('active_lots', 0)})
                self._hb_wt['shift'] = {
                    'side': hedge,
                    'reason': 'cap_auto_shift',
                    'hedge_premium': hedge_premium,
                    'loss': loss,
                }
                await self._process_strike_shift(
                    hedge, loss, ce_now, pe_now,
                )
                return

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

        # §5.5.1: Projected Gamma Check (Section B.4.1)
        try:
            from bot.api.async_delta_client import AsyncDeltaClient
            from config.loader import get_api_credentials
            from .mmm_gamma import _safe_greek
            creds = get_api_credentials()
            client = AsyncDeltaClient(
                api_key=creds.get('api_key', ''),
                api_secret=creds.get('api_secret', ''),
                testnet=creds.get('testnet', False) or False,
            )
            opt_char = 'call' if hedge == 'ce' else 'put'
            expiry = session.get('params', {}).get('expiry', '')
            symbol = self.initializer.build_symbol(opt_char, 'BTC', hedge_strike, expiry)
            ticker = await client._request_with_retry("GET", f"/v2/tickers/{symbol}")
            greeks = ticker.get('result', {}).get('greeks', {})
            new_strike_gamma = _safe_greek(greeks.get('gamma'))

            spot_price = await self._fetch_spot_price()
            blocked, projected_dollar_gamma = self._regime_engine.check_projected_gamma(
                session, new_strike_gamma, lots, spot_price
            )
            if blocked:
                log_activity('gamma_projection_blocked',
                            f'🚫 Gamma Cap Blocked: {hedge.upper()} adjustment would push projected '
                            f'portfolio gamma (${projected_dollar_gamma:.0f}) past hard limit',
                            sid, 'warning',
                            {'hedge': hedge.upper(), 'projected_gamma': projected_dollar_gamma})
                emit_safety(sid, 'gamma_cap_block', 'alert',
                           f'Gamma Cap Limit Reached (Projected ${projected_dollar_gamma:.0f})')
                return
        except Exception as e:
            log.warning(f"[{sid}] Failed to fetch greek gamma for projection check: {e}")

        result = await self._engine.execute_adjustment(
            session, hedge, hedge_strike, lots,
            ce_now, pe_now, adj_type,
            fetch_premium_fn=self._make_fetch_fn(),
        )

        if result.get('success'):
            fill_price = result['fill_price']

            # FM1/FM3 fix: A real hedge executed — reset the consecutive reversal-skip
            # counter.  The circuit breaker and trigger-preserve logic only activate
            # when skips accumulate without any hedge in between.
            session['_consecutive_reversal_skip_count'] = 0

            # STALE-TRIGGER FIX: execution takes 30-60s; ce_now/pe_now captured at
            # heartbeat start are stale by the time the fill completes.  Re-fetch live
            # premiums and update trigger snapshots so the next heartbeat doesn't
            # immediately re-trigger because the aggressor's snapshot is too low.
            # Same technique as the strike-shift BUG-1 FIX in _process_strike_shift.
            try:
                _fresh_ce, _fresh_pe = await self._fetch_premiums()
                if _fresh_ce and _fresh_pe:
                    update_trigger_snapshots(
                        session, _fresh_ce, _fresh_pe,
                        fetch_premium_fn=self._make_fetch_fn(),
                    )
                    log.info(
                        f"[{sid}] Post-adj trigger refresh: "
                        f"CE {ce_now:.2f}→{_fresh_ce:.2f}, "
                        f"PE {pe_now:.2f}→{_fresh_pe:.2f}"
                    )
            except Exception as _trf_e:
                log.warning(
                    f"[{sid}] Post-adj trigger refresh failed "
                    f"(stale snapshot retained): {_trf_e}"
                )

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
            # Breakeven + gamma cache invalidation — positions changed after fill
            try:
                get_breakeven_engine().invalidate_cache(sid)
                get_gamma_detector().invalidate_cache(sid)
            except Exception:
                pass

            # Trend Boost: log when boost multiplier was applied
            if session.get('_trend_boost_active'):
                boost_mult = session.get('_trend_boost_mult', 1.0)
                trend_dir = session.get('_trend_direction', '?')
                trend_tier = session.get('_trend_tier', 0)
                log_activity('trend_boost',
                            f'⚡ Trend Boost T{trend_tier} ({trend_dir.upper()}): '
                            f'{hedge.upper()} {lots} lots @ {boost_mult:.1f}x multiplier',
                            sid, 'info',
                            {
                                'side': hedge.upper(),
                                'lots': lots,
                                'boost_mult': boost_mult,
                                'trend_tier': trend_tier,
                                'trend_direction': trend_dir,
                            })
            # IMP-5: Update consecutive same-direction counter after successful sell
            self._update_consecutive_dir_counter(session, aggressor)
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
    # IMP-5: Consecutive Same-Direction Adjustment Limiter
    # =========================================================================

    def _apply_consecutive_dir_limit(
        self,
        session: Dict,
        aggressor: str,
        lots: int,
        constraint_msg: str,
    ):
        """
        IMP-5: After N consecutive same-direction adjustments, cap lot size.
        After M consecutive, block entirely until force-heartbeat resets the counter.
        If consecutive_dir_auto_resume_mins > 0, the block auto-clears after that timeout.

        Returns (adjusted_lots, updated_constraint_msg).
        """
        params = session.get('params', {})
        limit = params.get('consecutive_dir_limit', 3)
        block_after = params.get('consecutive_dir_block_after', 5)
        lot_cap_pct = params.get('consecutive_dir_lot_cap_pct', 0.25)

        count = session.get('_consecutive_same_dir_count', 0)
        last_dir = session.get('_consecutive_same_dir_side', '')

        # IMP-5 auto-resume: if blocked and timeout has elapsed, clear the block
        if session.get('_consecutive_dir_blocked'):
            auto_mins = params.get('consecutive_dir_auto_resume_mins', 10)
            if auto_mins > 0:
                blocked_at = session.get('_consecutive_dir_blocked_at')
                if blocked_at is None:
                    # Migration: timestamp not recorded (blocked before this feature).
                    # Start the countdown from now rather than auto-clearing immediately.
                    session['_consecutive_dir_blocked_at'] = time.time()
                elif time.time() - blocked_at >= auto_mins * 60:
                    session.pop('_consecutive_dir_blocked', None)
                    session.pop('_consecutive_dir_blocked_at', None)
                    session['_consecutive_same_dir_count'] = 0
                    session['_consecutive_same_dir_side'] = ''
                    count = 0
                    last_dir = ''
                    log_activity(
                        'consecutive_dir_auto_resume',
                        f'✅ CONSECUTIVE DIR BLOCK AUTO-CLEARED: {auto_mins}min timeout elapsed — resuming normally',
                        self.session_id, 'info',
                        {'side': aggressor, 'auto_resume_mins': auto_mins},
                    )

        # If direction changed, reset counter (counter updated on success in _update_)
        if last_dir and last_dir.lower() != aggressor.lower():
            return lots, constraint_msg

        # Block entirely after block_after consecutive adjustments
        if count >= block_after:
            session['_consecutive_dir_blocked'] = True
            session.setdefault('_consecutive_dir_blocked_at', time.time())
            return 0, f'Consecutive {aggressor.upper()} block: {count} adjustments'

        # Cap lot size after limit consecutive adjustments
        if count >= limit:
            initial_lots = session.get('params', {}).get('initial_lots', 10) or 1
            max_allowed = max(1, int(initial_lots * lot_cap_pct))
            if lots > max_allowed:
                msg = (
                    f'Consecutive {aggressor.upper()} cap (#{count}): '
                    f'{lots} → {max_allowed} lots '
                    f'({int(lot_cap_pct * 100)}% of {initial_lots} initial)'
                )
                constraint_msg = f"{constraint_msg}; {msg}" if constraint_msg else msg
                lots = max_allowed

        return lots, constraint_msg

    def _update_consecutive_dir_counter(self, session: Dict, aggressor: str):
        """IMP-5: Update consecutive same-direction counter after successful adjustment."""
        last_dir = session.get('_consecutive_same_dir_side', '')
        if last_dir and last_dir.lower() == aggressor.lower():
            session['_consecutive_same_dir_count'] = session.get('_consecutive_same_dir_count', 0) + 1
        else:
            # Direction changed — reset
            session['_consecutive_same_dir_count'] = 1
            session['_consecutive_same_dir_side'] = aggressor.lower()
            session.pop('_consecutive_dir_blocked', None)

        log.debug(
            f"[{self.session_id}] Consecutive {aggressor.upper()} count: "
            f"{session['_consecutive_same_dir_count']}"
        )

    # =========================================================================
    # T3-1: Proactive Shift Scanner
    # =========================================================================

    async def _proactive_shift_scan(self, ce_now: float, pe_now: float):
        """T3-1: Proactively shift a side when its premium decays below shift_threshold.

        Checks each side: if premium < shift_threshold AND the side has active lots,
        trigger a shift NOW rather than waiting for the opposite side trigger to fire.
        This prevents the scenario where one side decays to close-at-5 territory
        before a shift occurs, wasting premium.
        """
        session = self.session
        sid = self.session_id
        params = session.get('params', {})
        shift_threshold = params.get('shift_threshold', 50.0)

        for side, premium in [('ce', ce_now), ('pe', pe_now)]:
            side_state = session.get(side, {})
            active_lots = side_state.get('active_lots', 0)
            if active_lots <= 0:
                continue
            # Only shift if premium is below threshold but above close-at-5
            close_threshold = params.get('close_at_threshold', 5.0)
            if premium >= shift_threshold or premium <= close_threshold:
                continue
            # Check the side hasn't already been shifted this beat
            if session.get(f'_proactive_shifted_{side}'):
                continue

            log.info(
                f"[{sid}] T3-1 PROACTIVE SHIFT: {side.upper()} premium "
                f"${premium:.2f} < shift_threshold ${shift_threshold:.0f} "
                f"with {active_lots} active lots — triggering shift"
            )
            log_activity(
                'proactive_shift',
                f'🔄 Proactive Shift: {side.upper()} premium ${premium:.2f} '
                f'< ${shift_threshold:.0f} — shifting to better strike',
                sid, 'info',
                {'side': side, 'premium': premium, 'shift_threshold': shift_threshold,
                 'active_lots': active_lots},
            )
            # Use 0 for loss since we're not reacting to a trigger
            await self._process_strike_shift(
                side, 0.0, ce_now, pe_now,
            )
            session[f'_proactive_shifted_{side}'] = True
            # Only shift one side per beat to avoid race conditions
            break

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

        # AUDIT CONFLICT-7 FIX: Shift cooldown — prevent rapid oscillation
        # when premium bounces around shift_threshold. Default 120s cooldown.
        # Dangerous mode: bypass shift cooldown — near expiry, premium collapses
        # faster than 120s allows; operator needs immediate shift capability.
        _dm_shift = session.get('params', {}).get('dangerous_mode', False)
        shift_cooldown = session.get('params', {}).get('shift_cooldown_sec', 120)
        last_shift_time = session.get('_last_shift_time', 0)
        if not _dm_shift and shift_cooldown > 0 and last_shift_time:
            elapsed = time.time() - last_shift_time
            if elapsed < shift_cooldown:
                log.debug(
                    f"[{sid}] Strike shift {side.upper()} skipped: cooldown "
                    f"{elapsed:.0f}s / {shift_cooldown}s"
                )
                return

        params = session.get('params', {})   # defined early — used by validation, lot-scaling, and cooldown
        old_strike = session.get(side, {}).get('active_strike', 0)
        hedge_premium = ce_now if side == 'ce' else pe_now
        # Preserve old-strike premium for the remark — hedge_premium is
        # overwritten with new_strike_info['premium'] later in this method.
        _old_strike_premium = hedge_premium

        # Find new strike FIRST — do NOT freeze positions until we confirm
        # a viable new strike exists. If we freeze first and find_new_strike
        # fails, positions get stuck at active_lots=0 with no active strike.
        # Reuse spot from the pre-scan that ran earlier this heartbeat (if < 10s old)
        # to avoid a redundant _fetch_spot_price() REST call.
        _cached_spot = session.get('_last_prescan_spot', 0)
        _cached_spot_age = time.time() - session.get('_last_prescan_ts', 0)
        if _cached_spot > 0 and _cached_spot_age < 10:
            spot_price = _cached_spot
        else:
            spot_price = await self._fetch_spot_price()

        # Feature 6: Shift distance widening — when gamma is in DANGER zone,
        # enforce a minimum OTM distance so the new strike is further from spot.
        _gamma_shift_min_otm = 0.0
        _g6_params = session.get('params', {})
        if (_g6_params.get('gamma_severity_multiplier_enabled', False) and
                session.get('_gamma_result', {}).get('gamma_zone') == 'DANGER' and
                spot_price > 0):
            _shift_mult = _g6_params.get('gamma_severity_shift_distance_mult', 1.2)
            _base_pct   = _g6_params.get('gamma_danger_distance_pct', 1.5) / 100.0
            _gamma_shift_min_otm = spot_price * _base_pct * _shift_mult
            log.debug(
                f"[{sid}] F6 shift widening: min_otm={_gamma_shift_min_otm:.0f} "
                f"(spot={spot_price:.0f} × {_base_pct:.3f} × {_shift_mult:.2f})"
            )

        # Step 1: Use the pre-scanned candidate from this heartbeat's pre-scan.
        # pre_scan_shift_candidates() ran unconditionally earlier this beat
        # with a fresh chain fetch — the result is always warm and never stale.
        new_strike_info = None
        _expiry_param = session.get('params', {}).get('expiry', '')
        _candidate = session.get('_shift_candidates', {}).get(side, {})
        _scanned_at = _candidate.get('scanned_at', 0)
        _beat_age = time.time() - _scanned_at  # seconds since this heartbeat's pre-scan
        _params_match = (
            _candidate.get('shift_threshold') == session.get('params', {}).get('shift_threshold')
            and _candidate.get('shift_target_premium') == session.get('params', {}).get('shift_target_premium')
        )

        if _candidate.get('strike') and _beat_age < 60 and _params_match:
            # Verify candidate respects the current gamma OTM distance constraint.
            # Pre-scan runs with min_otm_distance=0 (gamma zone unknown at scan time),
            # so a candidate found during normal conditions could violate the OTM
            # floor that applies when gamma is in DANGER zone at shift time.
            _cstrike = _candidate['strike']
            _otm_ok = True
            if _gamma_shift_min_otm > 0 and spot_price > 0:
                if side == 'ce' and _cstrike < spot_price + _gamma_shift_min_otm:
                    _otm_ok = False
                    log.info(
                        f"[{sid}] Pre-scan CE candidate {_cstrike} too close to spot "
                        f"({_cstrike - spot_price:.0f} < gamma min_otm {_gamma_shift_min_otm:.0f}) "
                        f"— falling back to fresh scan with gamma constraint"
                    )
                elif side == 'pe' and _cstrike > spot_price - _gamma_shift_min_otm:
                    _otm_ok = False
                    log.info(
                        f"[{sid}] Pre-scan PE candidate {_cstrike} too close to spot "
                        f"({spot_price - _cstrike:.0f} < gamma min_otm {_gamma_shift_min_otm:.0f}) "
                        f"— falling back to fresh scan with gamma constraint"
                    )

            if _otm_ok:
                # Use the pre-warmed candidate — no extra chain call needed
                new_strike_info = {
                    'strike': _candidate['strike'],
                    'premium': _candidate['premium'],
                    'symbol': _candidate.get('symbol', ''),
                    'distance_from_spot': abs(_candidate['strike'] - spot_price),
                }
                log.info(
                    f"[{sid}] Using pre-scanned {side.upper()} candidate: "
                    f"strike={_candidate['strike']} @ ${_candidate['premium']:.2f} "
                    f"(scanned {_beat_age:.1f}s ago)"
                )
        if not new_strike_info:
            # Covers: no candidate, stale, config changed, or gamma OTM violation.
            # Only flush the chain cache if the pre-scan ran in a PREVIOUS heartbeat
            # (age >= 30s). If pre-scan ran this heartbeat (<30s ago), the chain data
            # is already fresh — flushing and re-fetching wastes one blocking REST call
            # for identical data. The gamma OTM path especially hits this: pre-scan
            # fetches chain, candidate rejected by OTM check, then falls here — the
            # chain data is seconds old and correct.
            _prescan_age = time.time() - session.get('_last_prescan_ts', 0)
            _should_flush = _prescan_age >= 30 or _beat_age >= 30
            _age_str = 'never scanned' if _scanned_at == 0 else f'{_beat_age:.0f}s ago'
            log.info(
                f"[{sid}] No accepted pre-scan for {side.upper()} "
                f"(candidate age={_age_str}, strike={_candidate.get('strike')}) — "
                f"fresh scan {'with cache flush' if _should_flush else '(cache still fresh from this beat)'}"
            )
            try:
                if _should_flush and _expiry_param and hasattr(self.initializer, 'chain_service'):
                    from .mmm_initializer import normalize_expiry as _ne
                    self.initializer.chain_service.invalidate_cache('BTC', _ne(_expiry_param))
            except Exception as _cache_err:
                log.debug(f"[{sid}] Chain cache clear failed (non-fatal): {_cache_err}")

            new_strike_info = await asyncio.get_running_loop().run_in_executor(
                None, find_new_strike,
                self.initializer, session, side, spot_price, _gamma_shift_min_otm,
            )

            # If still nothing, retry once with a fresh spot price.
            # Always flush cache here — data could have changed since first attempt.
            if not new_strike_info:
                log.info(f"[{sid}] Shift scan returned no candidates — retrying with fresh spot + cache flush")
                spot_price = await self._fetch_spot_price()
                try:
                    if _expiry_param and hasattr(self.initializer, 'chain_service'):
                        from .mmm_initializer import normalize_expiry as _ne
                        self.initializer.chain_service.invalidate_cache('BTC', _ne(_expiry_param))
                except Exception:
                    pass
                new_strike_info = await asyncio.get_running_loop().run_in_executor(
                    None, find_new_strike,
                    self.initializer, session, side, spot_price, _gamma_shift_min_otm,
                )

        if not new_strike_info:
            shift_threshold = session.get('params', {}).get('shift_threshold', 50.0)
            log.warning(
                f"[{sid}] SHIFT FAILED: No OTM {side.upper()} strike with "
                f"premium >= ${shift_threshold:.0f} found. "
                f"Skipping adjustment — will retry next heartbeat."
            )
            log_activity('shift_no_strike',
                        f'⚠️ Strike Shift Failed: No {side.upper()} strike with premium '
                        f'>= ${shift_threshold:.0f} found. Adjustment skipped — '
                        f'will not sell at decayed strike {old_strike} (${hedge_premium:.2f}). '
                        f'Retrying next heartbeat.',
                        sid, 'warning',
                        {
                            'side': side.upper(),
                            'current_strike': old_strike,
                            'current_premium': hedge_premium,
                            'shift_threshold': shift_threshold,
                            'reason': 'no_suitable_strike_skip',
                        })
            emit_safety(
                sid, 'no_strike', 'alert',
                f"No suitable strike found for {side.upper()} shift "
                f"(need premium >= ${shift_threshold:.0f}). "
                f"Activating fallback — selling at decayed strike {old_strike} "
                f"(${hedge_premium:.2f}).",
            )
            # Fallback: sell at the current (decayed) active strike so hedging is not
            # skipped indefinitely. Two gates:
            #   1. shift_fallback_enabled (default True) — master switch
            #   2. shift_fallback_min_premium (default $25) — premium floor.
            #      If decayed premium < floor: skip entirely. Selling near-worthless
            #      options generates negligible credit while adding full delta risk —
            #      worse than not hedging (e.g. PE @ $7.50 on 70 lots = $525 credit
            #      but 70 lots of near-zero-premium PE delta is a liability, not a hedge).
            _fallback_min = params.get('shift_fallback_min_premium', 25.0)
            if params.get('shift_fallback_enabled', True):
                if hedge_premium >= _fallback_min:
                    log.warning(
                        f"[{sid}] Shift fallback ACTIVE — selling {side.upper()} at "
                        f"decayed strike {old_strike} (${hedge_premium:.2f} >= "
                        f"floor ${_fallback_min:.0f})."
                    )
                    await self._process_shift_fallback(side, loss, hedge_premium, ce_now, pe_now)
                else:
                    log.warning(
                        f"[{sid}] Shift fallback SKIPPED — {side.upper()} premium "
                        f"${hedge_premium:.2f} is below fallback floor ${_fallback_min:.0f}. "
                        f"Selling near-worthless options adds delta risk without meaningful credit."
                    )
                    log_activity('shift_fallback_below_floor',
                                f'⛔ Shift Fallback Skipped: {side.upper()} premium '
                                f'${hedge_premium:.2f} < fallback floor ${_fallback_min:.0f}. '
                                f'Near-worthless premium — skipping to avoid delta risk.',
                                sid, 'warning',
                                {'side': side.upper(), 'premium': hedge_premium,
                                 'fallback_min': _fallback_min, 'strike': old_strike})
            return

        # Validate: fetch the candidate's current live premium before committing.
        # 0DTE premiums move fast — the pre-scanned value can be stale by seconds.
        # If the current premium has drifted outside shift_target_premium ± tolerance,
        # rescan the chain for a better strike before placing any order.
        _target_prem = params.get('shift_target_premium', 100.0)
        _tolerance = params.get('shift_premium_tolerance', 10.0)
        if _tolerance > 0 and new_strike_info.get('symbol'):
            try:
                _tkr = await asyncio.get_running_loop().run_in_executor(
                    None, self.initializer.chain_service.get_option_ticker,
                    new_strike_info['symbol'],
                )
                if _tkr:
                    _mark = float(_tkr.get('mark_price', 0) or 0)
                    _bid = float(_tkr.get('bid', 0) or 0)
                    _ask = float(_tkr.get('ask', 0) or 0)
                    _live = (
                        _mark if _mark > 0
                        else (_bid + _ask) / 2 if _bid > 0 and _ask > 0
                        else _bid
                    )
                    if _live > 0 and abs(_live - _target_prem) > _tolerance:
                        log.info(
                            f"[{sid}] Candidate {new_strike_info['strike']} live premium "
                            f"${_live:.2f} is outside target ${_target_prem:.0f}±${_tolerance:.0f} "
                            f"— rescanning chain for better strike"
                        )
                        log_activity(
                            'shift_candidate_stale',
                            f'🔄 Shift candidate {side.upper()} {new_strike_info["strike"]} '
                            f'live premium ${_live:.2f} outside target '
                            f'${_target_prem:.0f}±${_tolerance:.0f} — rescanning',
                            sid, 'info',
                            {'strike': new_strike_info['strike'], 'live_premium': _live,
                             'target': _target_prem, 'tolerance': _tolerance},
                        )
                        # Rescan with fresh spot + cache flush (spot_price from method
                        # entry may be stale by now; refresh before OTM filter).
                        _rescan_spot = await self._fetch_spot_price()
                        if _rescan_spot <= 0:
                            _rescan_spot = spot_price  # fallback to original if fetch fails
                        try:
                            if _expiry_param and hasattr(self.initializer, 'chain_service'):
                                from .mmm_initializer import normalize_expiry as _ne
                                self.initializer.chain_service.invalidate_cache(
                                    'BTC', _ne(_expiry_param)
                                )
                        except Exception:
                            pass
                        _rescanned = await asyncio.get_running_loop().run_in_executor(
                            None, find_new_strike,
                            self.initializer, session, side, _rescan_spot, _gamma_shift_min_otm,
                        )
                        if _rescanned:
                            log.info(
                                f"[{sid}] Rescan found better {side.upper()} candidate: "
                                f"{_rescanned['strike']} @ ${_rescanned['premium']:.2f}"
                            )
                            new_strike_info = _rescanned
                        else:
                            log.info(
                                f"[{sid}] Rescan found nothing better — "
                                f"proceeding with original candidate {new_strike_info['strike']}"
                            )
            except Exception as _val_err:
                log.debug(f"[{sid}] Candidate validation failed (non-fatal): {_val_err}")

        # New strike found — NOW freeze current positions
        freeze_result = freeze_current_positions(session, side)

        # ── Split Ledger Phase 2: Shift-Time Recycle ─────────────────────────
        shift_recycle_buyback = 0.0
        if params.get('shift_recycle_enabled', False):
            shift_recycle_buyback = await self._shift_time_recycle(
                side, new_strike_info,
            )
        # ─────────────────────────────────────────────────────────────────────

        # Sell at new strike
        new_strike = new_strike_info['strike']
        hedge_premium = new_strike_info['premium']

        # Fold buyback cost so extra lots at new strike recover it
        total_loss_to_cover = loss + shift_recycle_buyback

        # IMP-4: Set OTM multiplier on session before calling calculate_lots_to_sell.
        # The engine reads session['_strike_shift_otm_multiplier'] to scale lots.
        # params already defined at method top.
        if params.get('strike_shift_use_lot_scaling', False) and spot_price > 0:
            otm_pct = abs(new_strike - spot_price) / spot_price * 100.0
            tier1 = params.get('strike_shift_otm_tier1', 1.0)
            tier2 = params.get('strike_shift_otm_tier2', 2.0)
            tier3 = params.get('strike_shift_otm_tier3', 3.0)
            if otm_pct < tier1:
                session['_strike_shift_otm_multiplier'] = 0.25
            elif otm_pct < tier2:
                session['_strike_shift_otm_multiplier'] = 0.50
            elif otm_pct < tier3:
                session['_strike_shift_otm_multiplier'] = 0.75
            else:
                session['_strike_shift_otm_multiplier'] = 1.0
        else:
            session.pop('_strike_shift_otm_multiplier', None)

        lots, _, _ = self._engine.calculate_lots_to_sell(
            session, side, total_loss_to_cover, hedge_premium,
        )
        # Clear after use — don't affect non-shift lot calculations
        session.pop('_strike_shift_otm_multiplier', None)

        # ── PROACTIVE SHIFT LOT FALLBACK ──────────────────────────────────
        # When this shift was triggered by premium decay (total_loss_to_cover=0),
        # calculate_lots_to_sell returns 0 ("No loss to cover").
        # Without this fallback: positions freeze, nothing is sold, CE/PE ends up
        # with 0 active lots and cannot hedge when the opposite side triggers.
        # Fix: seed lots from frozen_lots so the delta-neutral matching below
        # can correctly inflate to match the opposite side's active count.
        # inflate_cap = int(pre_match_lots * 1.5) = 0 when pre_match_lots=0,
        # so the seed must be > 0 for the cap math to work.
        if lots <= 0 and total_loss_to_cover <= 0:
            fallback = max(freeze_result.get('frozen_lots', 0), 1)
            log.info(
                f"[{sid}] PROACTIVE SHIFT LOT FALLBACK: {side.upper()} "
                f"lots=0 (no loss) → {fallback} "
                f"(frozen={freeze_result.get('frozen_lots', 0)})"
            )
            log_activity(
                'proactive_shift_lot_fallback',
                f'📌 Proactive Shift: {side.upper()} seeding {fallback} lots '
                f'at new strike (premium decay — no aggressor loss to cover)',
                sid, 'info',
                {'side': side, 'lots': fallback,
                 'frozen_lots': freeze_result.get('frozen_lots', 0)},
            )
            lots = fallback
        # ── END PROACTIVE SHIFT LOT FALLBACK ──────────────────────────────

        # ── DELTA-NEUTRAL LOT MATCHING ────────────────────────────────────
        # During a strike shift, the old positions are frozen and the new
        # position gets only as many lots as the loss formula demands.
        # This creates immediate asymmetry (e.g. 4 CE vs 11 PE) because
        # the loss-driven count doesn't consider opposing side lot count.
        # Fix: match the opposite side's active lots so delta stays neutral.
        # Risk controls respected: trend tier lot reduction is applied to the
        # matching target so regime constraints are never bypassed.
        if params.get('shift_match_opposite_lots', True):
            opposite_side = 'pe' if side == 'ce' else 'ce'
            opposite_active = session.get(opposite_side, {}).get('active_lots', 0)
            if opposite_active > lots:
                pre_match_lots = lots
                target = opposite_active
                # Apply trend-tier adjustment to the balance target
                # (the formula lots already went through calculate_lots_to_sell
                # which applied this adjustment, so repeat it here too)
                trend_tier = session.get('_trend_tier', 0)
                trend_direction = session.get('_trend_direction', 'none')
                is_safe_side = (
                    (trend_direction == 'up' and side == 'pe') or
                    (trend_direction == 'down' and side == 'ce')
                )
                if trend_tier >= 1 and params.get('trend_boost_enabled', False) and is_safe_side:
                    # Trend Boost: boost lots on safe side during shifts too
                    if trend_tier >= 3:
                        boost_mult = params.get('trend_boost_tier3_mult', 2.0)
                    elif trend_tier >= 2:
                        boost_mult = params.get('trend_boost_tier2_mult', 1.5)
                    else:
                        boost_mult = params.get('trend_boost_tier1_mult', 1.3)
                    target = max(int(opposite_active * boost_mult + 0.999), lots)
                elif trend_tier >= 1:
                    lot_reduction = params.get('trend_tier1_lot_reduction', 0.30)
                    mult = max(1.0 - lot_reduction, 0.1)
                    # Floor at formula lots — never go below what hedging demands
                    target = max(int(opposite_active * mult + 0.999), lots)
                # Respect position cap (after freeze, active_lots for this side is 0)
                max_per_side = params.get('max_lots_per_side', 100)
                # Fix A5: Cap inflation — don't jump from formula lots to opposite lots
                # uncapped. March 12 incident inflated 81→126 creating destructive cascade.
                max_inflate = params.get('shift_match_max_inflate_mult', 1.5)
                inflate_cap = int(pre_match_lots * max_inflate + 0.999)
                lots = min(target, max_per_side, inflate_cap)
                if lots > pre_match_lots:
                    if trend_tier >= 1 and params.get('trend_boost_enabled', False) and is_safe_side:
                        trend_note = f' (trend T{trend_tier} boost {boost_mult:.1f}x)'
                    elif trend_tier >= 1:
                        trend_note = f' (trend T{trend_tier} reduction applied)'
                    else:
                        trend_note = ''
                    log.info(
                        f"[{sid}] DELTA-NEUTRAL MATCH: {side.upper()} lots "
                        f"{pre_match_lots} → {lots} (matching "
                        f"{opposite_side.upper()} active_lots={opposite_active}){trend_note}"
                    )
                    log_activity('delta_neutral_match',
                        f'⚖️ Delta-Neutral Match: {side.upper()} shift lots '
                        f'{pre_match_lots} → {lots} '
                        f'(matching {opposite_side.upper()}={opposite_active}{trend_note})',
                        sid, 'info',
                        {'side': side, 'pre_match': pre_match_lots,
                         'matched_to': lots, 'opposite_side': opposite_side,
                         'opposite_lots': opposite_active, 'trend_tier': trend_tier})
        # ── END DELTA-NEUTRAL LOT MATCHING ────────────────────────────────

        if lots <= 0:
            return

        # GUARD: Abort if monitor was stopped (e.g. by watchdog restart).
        # An in-flight strike shift that completes AFTER stop() places orders
        # on exchange but _save_disabled prevents persisting the state update.
        # This creates orphaned positions invisible to the new monitor.
        if not self._running or session.get('_save_disabled'):
            log.warning(
                f"[{sid}] SHIFT ABORTED: monitor stopped during "
                f"{side.upper()} shift {old_strike}→{new_strike} "
                f"(would create orphan). Unfreezing positions."
            )
            # Unfreeze positions so the new monitor sees them correctly
            from .mmm_state import recompute_side_lots
            for pos in session.get(side, {}).get('positions', []):
                if pos.get('status') == 'shifted':
                    pos['status'] = 'active'
            recompute_side_lots(session.get(side, {}))
            log_activity('shift_aborted',
                f'⚠️ Strike shift {side.upper()} {old_strike}→{new_strike} '
                f'aborted: monitor stopped (preventing orphan position)',
                sid, 'warning',
                {'side': side, 'old_strike': old_strike,
                 'new_strike': new_strike, 'lots': lots})
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
            session_id=sid,
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

            # Record exchange commission via ledger (CRIT-1 fix)
            _od = result.get('order_details') or {}
            _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)
            if _commission:
                from .mmm_pnl_core import record_fee as _pnl_fee
                _pnl_fee(session, _commission, 'sell_adjustment',
                         order_id=str(result.get('order_id', '')), side=side)

            # AUDIT BUG-2 FIX: Use actual filled size, not requested lots.
            # smart_execute() can return partial fills; recording requested
            # lots would make the ledger diverge from exchange state.
            filled_lots = result.get('filled_size', lots)
            if filled_lots <= 0:
                filled_lots = lots
            if filled_lots < lots:
                log.warning(
                    f"[{sid}] STRIKE SHIFT PARTIAL FILL: requested {lots} "
                    f"{side.upper()} lots, only {filled_lots} filled."
                )
            lots = filled_lots  # Override for all downstream state updates

            # BUG-1 FIX: Wrap entire post-fill sequence in try/except.
            # Each step is individually exception-safe so a failure in one
            # (e.g. frozen position snapshot) cannot abort the critical
            # trigger snapshot update or adjustment_complete event.
            _shift_errors = []

            # Step 1: Activate new strike (sets trigger_snapshot to fill_price)
            try:
                activate_new_strike(
                    session, side, new_strike, fill_price, lots,
                    order_id=str(result.get('order_id', '')),
                    client_order_id=str(result.get('client_order_id', '')),
                    old_premium=_old_strike_premium,
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
                session['_last_shift_time'] = time.time()  # AUDIT CONFLICT-7: cooldown tracking
                session['total_premium_collected'] = (
                    session.get('total_premium_collected', 0) + premium_collected
                )
                _spk = 'ce_premium_collected' if side.lower() == 'ce' else 'pe_premium_collected'
                session[_spk] = session.get(_spk, 0) + premium_collected
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
                    'spot': session.get('_regime_spot_price', 0),
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
            _shift_threshold = params.get('shift_threshold', 50.0)
            log_activity('strike_shift',
                        f'🔀 Strike Shift: {side.upper()} {old_strike} → {new_strike} '
                        f'(old premium ${_old_strike_premium:.2f} < threshold ${_shift_threshold:.0f}; '
                        f'frozen {freeze_result["frozen_lots"]} lots at old strike)',
                        sid, 'info',
                        {
                            'side': side.upper(),
                            'old_strike': old_strike,
                            'new_strike': new_strike,
                            'old_premium': _old_strike_premium,
                            'shift_threshold': _shift_threshold,
                            'frozen_lots': freeze_result['frozen_lots'],
                            'fill_price': fill_price,
                        })

            # BUG-1 FIX: Log adjustment_complete — this was MISSING for strike
            # shifts, causing the trigger snapshot update + history record to
            # appear incomplete in the activity log.
            log_activity('adjustment_complete',
                        f'✓ Strike Shift Complete: SELL {lots} lots {side.upper()} @ {new_strike} '
                        f'for ${fill_price:.2f} (shifted from {old_strike} — old premium '
                        f'${_old_strike_premium:.2f} below ${_shift_threshold:.0f} threshold)',
                        sid, 'success',
                        {
                            'side': side.upper(),
                            'strike': new_strike,
                            'old_strike': old_strike,
                            'lots': lots,
                            'fill_price': fill_price,
                            'old_premium': _old_strike_premium,
                            'shift_threshold': _shift_threshold,
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

            # ── TRADE AUDIT: strike shift SELL at new strike ──────────────
            try:
                from .mmm_audit_log import get_audit_log as _get_aud
                from .mmm_audit_remark import build_trade_remark as _btr
                _aggressor = 'pe' if side == 'ce' else 'ce'
                _get_aud().enqueue_trade(
                    session_id=sid,
                    action='SELL',
                    option_type=side.upper(),
                    strike=int(new_strike),
                    quantity_requested=lots,
                    quantity_filled=lots,
                    premium=fill_price,
                    event_type='ADJUSTMENT',
                    adj_type='strike_shift',
                    mechanism='strike_shift',
                    aggressor_side=_aggressor,
                    order_id=str(result.get('order_id', '')),
                    expiry=session.get('params', {}).get('expiry', ''),
                    spot_price_usd=float(session.get('_regime_spot_price', 0) or 0),
                    whipsaw_state=str(session.get('_whipsaw_state', '') or ''),
                    margin_tier=str(session.get('_margin_tier', '') or ''),
                    remark=_btr(
                        'SELL', 'ADJUSTMENT',
                        side=side, strike=int(new_strike),
                        lots=lots, premium=fill_price,
                        adj_type='strike_shift', aggressor=_aggressor,
                    ),
                )
            except Exception:
                pass
            # ── END TRADE AUDIT ───────────────────────────────────────────

            # Breakeven + gamma cache invalidation — positions changed after strike shift
            try:
                get_breakeven_engine().invalidate_cache(sid)
                get_gamma_detector().invalidate_cache(sid)
            except Exception:
                pass

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

            # Sell failed — restore positions frozen at old_strike so side is not stranded.
            # freeze_current_positions() marked active positions as 'shifted'; without this
            # rollback the side stays frozen with 0 active lots and cannot hedge next trigger.
            _fail_side_state = session.get(side, {})
            for _pos in _fail_side_state.get('positions', []):
                if _pos.get('status') == 'shifted' and _pos.get('strike') == old_strike:
                    _pos['status'] = 'active'
                    _pos.pop('shifted_at', None)
            from .mmm_state import recompute_side_lots as _rsl_shift_fail
            _rsl_shift_fail(_fail_side_state)
            session[side] = _fail_side_state
            log.warning(
                f"[{sid}] Strike shift sell failed — restored "
                f"{freeze_result.get('frozen_lots', 0)} frozen lots at {old_strike} "
                f"(side not stranded)"
            )
            log_activity('shift_sell_failed_unfreeze',
                        f'♻️ Strike Shift Sell Failed: {side.upper()} restored '
                        f'{freeze_result.get("frozen_lots", 0)} lots at {old_strike} '
                        f'(preventing stranded side)',
                        sid, 'warning',
                        {'side': side.upper(), 'old_strike': old_strike,
                         'frozen_lots': freeze_result.get('frozen_lots', 0)})

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

        # Delta-neutral lot matching (same logic as _process_strike_shift)
        params = session.get('params', {})
        if lots > 0 and params.get('shift_match_opposite_lots', True):
            opposite_side = 'pe' if side == 'ce' else 'ce'
            opposite_active = session.get(opposite_side, {}).get('active_lots', 0)
            if opposite_active > lots:
                pre_match_lots = lots
                target = opposite_active
                trend_tier = session.get('_trend_tier', 0)
                trend_direction = session.get('_trend_direction', 'none')
                is_safe_side = (
                    (trend_direction == 'up' and side == 'pe') or
                    (trend_direction == 'down' and side == 'ce')
                )
                if trend_tier >= 1 and params.get('trend_boost_enabled', False) and is_safe_side:
                    if trend_tier >= 3:
                        boost_mult = params.get('trend_boost_tier3_mult', 2.0)
                    elif trend_tier >= 2:
                        boost_mult = params.get('trend_boost_tier2_mult', 1.5)
                    else:
                        boost_mult = params.get('trend_boost_tier1_mult', 1.3)
                    target = max(int(opposite_active * boost_mult + 0.999), lots)
                elif trend_tier >= 1:
                    lot_reduction = params.get('trend_tier1_lot_reduction', 0.30)
                    mult = max(1.0 - lot_reduction, 0.1)
                    target = max(int(opposite_active * mult + 0.999), lots)
                max_per_side = params.get('max_lots_per_side', 100)
                current_active = session.get(side, {}).get('active_lots', 0)
                lots = min(target, max_per_side - current_active)
                lots = max(lots, pre_match_lots)  # never go below formula result
                if lots > pre_match_lots:
                    log.info(
                        f"[{sid}] DELTA-NEUTRAL MATCH (fallback): {side.upper()} lots "
                        f"{pre_match_lots} → {lots} (matching "
                        f"{opposite_side.upper()} active_lots={opposite_active})"
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
            # Breakeven + gamma cache invalidation — positions changed after shift fallback fill
            try:
                get_breakeven_engine().invalidate_cache(sid)
                get_gamma_detector().invalidate_cache(sid)
            except Exception:
                pass

    # =========================================================================
    # §11: Close-at-5 Processing
    # =========================================================================

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
                        p['_being_closed_at'] = time.monotonic()
                        break

            result = await close_position(
                self.executor, self.initializer, session, pos,
                pnl_attribution_key='pnl_harvest',
                mechanism='harvest',
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

                # Breakeven + gamma cache invalidation — positions changed after harvest fill
                try:
                    get_breakeven_engine().invalidate_cache(sid)
                    get_gamma_detector().invalidate_cache(sid)
                except Exception:
                    pass

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
    # §3b: FSU — Favorable Scale-Up
    # =========================================================================

    async def _process_scale_up(self, ce_now: float, pe_now: float):
        """
        Favorable Scale-Up: When both premiums are decaying, open new
        positions at fresh OTM strikes to capture additional theta.

        Positions are registered in the unified ledger with status='shifted'
        and become standard MMM frozen positions — subject to all loss
        calculations, adjustments, close-at-5, harvesting, and recycling.
        """
        session = self.session
        sid = self.session_id

        from .mmm_scaler import check_scale_eligibility, find_scale_strikes, record_scale_event

        # Step 1: Check eligibility
        eligible, reason = check_scale_eligibility(session, ce_now, pe_now)
        if not eligible:
            return

        log.info(f"[{sid}] Scale-up eligible: {reason}")

        # Step 2: Find strikes
        spot_price = await self._fetch_spot_price()
        if spot_price <= 0:
            log.warning(f"[{sid}] Scale-up: Could not fetch spot price")
            return

        scale_info = find_scale_strikes(self.initializer, session, spot_price)
        if not scale_info:
            log_activity('scale_up_no_strikes',
                        f'\U0001F4C8 Scale-up eligible but no suitable strikes found',
                        sid, 'info', {'reason': reason})
            return

        lots = scale_info['lots']
        ce_target = scale_info['ce']
        pe_target = scale_info['pe']

        log_activity('scale_up_triggered',
                    f'\U0001F4C8 Scale-Up Triggered: Selling {lots} lots each \u2014 '
                    f'CE @ {ce_target["strike"]} (${ce_target["premium"]:.2f}), '
                    f'PE @ {pe_target["strike"]} (${pe_target["premium"]:.2f})',
                    sid, 'info',
                    {
                        'lots': lots,
                        'ce_strike': ce_target['strike'],
                        'ce_premium': ce_target['premium'],
                        'pe_strike': pe_target['strike'],
                        'pe_premium': pe_target['premium'],
                        'reason': reason,
                        'scale_event': session.get('scale_count', 0) + 1,
                    })

        # Step 3: Execute CE sell
        params = session.get('params', {})
        expiry = params.get('expiry', '')
        _reprice_max = params.get('max_reprice_attempts', None)

        ce_symbol = ce_target.get('symbol') or self.initializer.build_symbol(
            'call', 'BTC', ce_target['strike'], expiry
        )
        pe_symbol = pe_target.get('symbol') or self.initializer.build_symbol(
            'put', 'BTC', pe_target['strike'], expiry
        )

        # Register pending orders
        try:
            register_pending(sid, 'ce', 'pending', ce_symbol, lots,
                           ce_target['strike'], 'scale_up')
        except Exception:
            pass

        ce_result = await self.executor.smart_execute(
            symbol=ce_symbol, side='sell', size=lots,
            max_reprice_attempts=_reprice_max,
            session_id=sid,
        )

        try:
            if ce_result.get('success'):
                register_pending(sid, 'ce', str(ce_result.get('order_id', '')),
                               ce_symbol, lots, ce_target['strike'], 'scale_up')
            else:
                clear_pending(sid, 'ce')
        except Exception:
            pass

        if not ce_result.get('success'):
            log_activity('scale_up_failed',
                        f'\u274C Scale-up CE sell FAILED @ {ce_target["strike"]}: '
                        f'{ce_result.get("error", "unknown")}',
                        sid, 'error',
                        {'side': 'CE', 'strike': ce_target['strike'],
                         'error': ce_result.get('error')})
            try:
                clear_pending(sid, 'ce')
            except Exception:
                pass
            return  # Abort — don't sell PE without CE (keeps balance)

        ce_fill = ce_result.get('fill_price', 0)

        # Record exchange commission via ledger (CRIT-1 fix)
        _od = ce_result.get('order_details') or {}
        _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)
        if _commission:
            from .mmm_pnl_core import record_fee as _pnl_fee
            _pnl_fee(session, _commission, 'sell_scale_up',
                     order_id=str(ce_result.get('order_id', '')), side='ce')

        # Step 4: Execute PE sell
        try:
            register_pending(sid, 'pe', 'pending', pe_symbol, lots,
                           pe_target['strike'], 'scale_up')
        except Exception:
            pass

        pe_result = await self.executor.smart_execute(
            symbol=pe_symbol, side='sell', size=lots,
            max_reprice_attempts=_reprice_max,
            session_id=sid,
        )

        try:
            if pe_result.get('success'):
                register_pending(sid, 'pe', str(pe_result.get('order_id', '')),
                               pe_symbol, lots, pe_target['strike'], 'scale_up')
            else:
                clear_pending(sid, 'pe')
        except Exception:
            pass

        if not pe_result.get('success'):
            log_activity('scale_up_failed',
                        f'\u274C Scale-up PE sell FAILED @ {pe_target["strike"]}: '
                        f'{pe_result.get("error", "unknown")} '
                        f'(CE was filled @ {ce_fill:.2f} \u2014 positions will be asymmetric)',
                        sid, 'error',
                        {'side': 'PE', 'strike': pe_target['strike'],
                         'error': pe_result.get('error')})
            # CE already filled — must still register it. Continue below.

        pe_fill = pe_result.get('fill_price', 0) if pe_result.get('success') else 0

        # Record exchange commission via ledger (CRIT-1 fix)
        if pe_result.get('success'):
            _od = pe_result.get('order_details') or {}
            _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)
            if _commission:
                from .mmm_pnl_core import record_fee as _pnl_fee
                _pnl_fee(session, _commission, 'sell_scale_up',
                         order_id=str(pe_result.get('order_id', '')), side='pe')

        # Step 5: Register positions in the unified ledger
        from .mmm_constants import LOT_SIZE_BTC, strike_key as _sk
        from .mmm_state import recompute_side_lots
        from .mmm_trigger import update_trigger_snapshots

        now = datetime.now(timezone.utc).isoformat()

        # Register CE position
        ce_state = session.get('ce', {})
        counter = ce_state.get('_pos_counter', 0) + 1
        ce_state['_pos_counter'] = counter
        ce_state.setdefault('positions', []).append({
            'id': f"ce_scale_{counter:03d}",
            'strike': ce_target['strike'],
            'lots': lots,
            'entry_premium': ce_fill,
            'premium': ce_fill,
            'type': 'scale_up',
            'status': 'shifted',          # NOT 'active' — frozen from birth (§1.4)
            'created_at': now,
            'fill_confirmed_at': now,
            'order_id': str(ce_result.get('order_id', '')),
            'client_order_id': str(ce_result.get('client_order_id', '')),
            'shifted_at': now,
            'closed_at': None,
            'realized_pnl': None,
            'timestamp': now,
        })
        recompute_side_lots(ce_state)
        session['ce'] = ce_state

        # Register PE position (only if filled)
        if pe_result.get('success'):
            pe_state = session.get('pe', {})
            counter = pe_state.get('_pos_counter', 0) + 1
            pe_state['_pos_counter'] = counter
            pe_state.setdefault('positions', []).append({
                'id': f"pe_scale_{counter:03d}",
                'strike': pe_target['strike'],
                'lots': lots,
                'entry_premium': pe_fill,
                'premium': pe_fill,
                'type': 'scale_up',
                'status': 'shifted',          # NOT 'active' — frozen from birth (§1.4)
                'created_at': now,
                'fill_confirmed_at': now,
                'order_id': str(pe_result.get('order_id', '')),
                'client_order_id': str(pe_result.get('client_order_id', '')),
                'shifted_at': now,
                'closed_at': None,
                'realized_pnl': None,
                'timestamp': now,
            })
            recompute_side_lots(pe_state)
            session['pe'] = pe_state

        # Step 6: Set trigger snapshots for the new scale-up strikes.
        # CRITICAL: update_trigger_snapshots() only writes snapshots for
        # active_strike and existing frozen_positions. Scale-up positions
        # were JUST created and their strikes may not be in the premium cache.
        # We must EXPLICITLY set trigger_snapshot to the fill price.
        ce_state = session.get('ce', {})
        ce_state.setdefault('trigger_snapshot', {})[_sk(ce_target['strike'])] = ce_fill
        session['ce'] = ce_state

        if pe_result.get('success'):
            pe_state = session.get('pe', {})
            pe_state.setdefault('trigger_snapshot', {})[_sk(pe_target['strike'])] = pe_fill
            session['pe'] = pe_state

        # Update trigger snapshots for active strikes + other frozen positions
        update_trigger_snapshots(session, ce_now, pe_now,
                                fetch_premium_fn=self._make_fetch_fn())

        # Force-set AGAIN after update_trigger_snapshots to prevent overwrite
        ce_state = session.get('ce', {})
        ce_state.setdefault('trigger_snapshot', {})[_sk(ce_target['strike'])] = ce_fill
        session['ce'] = ce_state
        if pe_result.get('success'):
            pe_state = session.get('pe', {})
            pe_state.setdefault('trigger_snapshot', {})[_sk(pe_target['strike'])] = pe_fill
            session['pe'] = pe_state

        # Step 7: Update session tracking
        premium_collected_ce = ce_fill * lots * LOT_SIZE_BTC
        premium_collected_pe = pe_fill * lots * LOT_SIZE_BTC if pe_result.get('success') else 0
        total_premium = premium_collected_ce + premium_collected_pe
        session['total_premium_collected'] = session.get('total_premium_collected', 0) + total_premium
        session['ce_premium_collected'] = session.get('ce_premium_collected', 0) + premium_collected_ce
        session['pe_premium_collected'] = session.get('pe_premium_collected', 0) + premium_collected_pe

        record_scale_event(session, ce_target, pe_target, lots)

        # Clear pending orders
        try:
            clear_pending(sid, 'ce')
            clear_pending(sid, 'pe')
        except Exception:
            pass

        # Step 8: Emit events
        emit_scale_up(
            sid, lots,
            ce_target['strike'], ce_fill,
            pe_target['strike'], pe_fill if pe_result.get('success') else 0,
            session.get('scale_count', 0),
        )

        sessions_filled = 2 if pe_result.get('success') else 1
        pe_status_str = f'${pe_fill:.2f}' if pe_result.get('success') else 'FAILED'
        log_activity('scale_up_complete',
                    f'\u2705 Scale-Up #{session.get("scale_count", 0)}: '
                    f'{sessions_filled}/2 sides filled \u2014 '
                    f'CE {lots}L @ {ce_target["strike"]} (${ce_fill:.2f}), '
                    f'PE {lots}L @ {pe_target["strike"]} ({pe_status_str})',
                    sid, 'success',
                    {
                        'scale_event': session.get('scale_count', 0),
                        'ce_strike': ce_target['strike'],
                        'ce_premium': ce_fill,
                        'pe_strike': pe_target['strike'],
                        'pe_premium': pe_fill if pe_result.get('success') else 0,
                        'lots': lots,
                        'sides_filled': sessions_filled,
                        'premium_collected': total_premium,
                    })

        session['updated_at'] = datetime.now(timezone.utc).isoformat()

    # =========================================================================
    # §3c: Auto-Replenish Leg
    # =========================================================================

    async def _process_replenish(
        self,
        closed_side: str,
        open_side: str,
        ce_now: float,
        pe_now: float,
    ) -> bool:
        """
        Auto-replenish: when one side reaches 0 positions, sell a new leg
        on the empty side to maintain hedged exposure.

        Returns True if replenishment succeeded, False otherwise.
        On False the caller falls back to the existing PAUSE behavior.
        """
        session = self.session
        sid = self.session_id
        params = session.get('params', {})

        from .mmm_replenish import check_replenish_eligibility, determine_replenish_lots

        # Step 1: Eligibility
        eligible, reason = check_replenish_eligibility(session, closed_side, open_side)
        if not eligible:
            log.info(f"[{sid}] Replenish blocked: {reason}")
            log_activity('replenish_blocked',
                        f'\u26D4 Replenish {closed_side.upper()} blocked: {reason}',
                        sid, 'info',
                        {'closed_side': closed_side, 'open_side': open_side,
                         'reason': reason})
            return False

        log_activity('replenish_triggered',
                    f'\U0001F504 Replenish {closed_side.upper()} triggered — '
                    f'{open_side.upper()} has {session.get(open_side, {}).get("total_lots", 0)} lots',
                    sid, 'info',
                    {'closed_side': closed_side, 'open_side': open_side})

        # Step 2: Determine lots
        lots = determine_replenish_lots(session, closed_side, open_side)

        # Cap lots to velocity headroom — Gate 11 confirmed window < limit,
        # but the single sell may still exceed the remaining capacity.
        # Only count same-side lots — cross-side velocity is irrelevant for replenish.
        if params.get('lot_velocity_enabled', True):
            from datetime import timedelta
            _vel_limit = params.get('lot_velocity_limit', 10)
            _vel_window = params.get('lot_velocity_window_mins', 30)
            _cutoff = datetime.now(timezone.utc) - timedelta(minutes=_vel_window)
            _lots_in_window = 0
            for _adj in session.get('adjustment_history', []):
                if _adj.get('aggressor', '') in ('OPERATOR', 'STRADDLE_ROLL'):
                    continue
                if _adj.get('side', '') != closed_side:
                    continue
                try:
                    _ts = datetime.fromisoformat(_adj.get('timestamp', ''))
                    if _ts.tzinfo is None:
                        _ts = _ts.replace(tzinfo=timezone.utc)
                    if _ts >= _cutoff:
                        _lots_in_window += _adj.get('lots_sold', 0)
                except (ValueError, TypeError):
                    continue
            _headroom = _vel_limit - _lots_in_window
            if lots > _headroom:
                log.info(f"[{sid}] Replenish: capping lots {lots} → {_headroom} "
                         f"(velocity headroom: {_lots_in_window}/{_vel_limit} in window)")
                lots = max(1, _headroom)

        # Step 3–5: Find strike + execute — with retry on transient failures.
        #
        # Retry policy:
        #   • no_spot_price / no_strike_found / fast execution failure (attempts=0):
        #     retry up to replenish_retry_max times with replenish_retry_delay_sec delay.
        #     Fresh spot + chain data are fetched on each attempt so the strike stays current.
        #   • premium < min_premium: hard stop — market condition, not a transient error.
        #     Next heartbeat (OCS watchdog) retries when market moves.
        #   • smart_execute failed with attempts>0: an order was live on exchange. Do NOT
        #     retry within this heartbeat — risk of placing a second order on the same side.
        #     OCS watchdog retries on the next heartbeat automatically.
        _retry_max = params.get('replenish_retry_max', 3)
        _retry_delay = params.get('replenish_retry_delay_sec', 2)
        _reprice_max = params.get('replenish_max_reprice_attempts', 2)

        # Determine lots to sell: resume a partial fill top-up if one is pending.
        _lots_remaining = session.get(f'_replenish_lots_remaining_{closed_side}', 0)
        lots_to_sell = _lots_remaining if _lots_remaining > 0 else lots

        expiry = params.get('expiry', '')
        dte_cat = params.get('dte_category', '')
        preset = params.get('adaptive_preset', 'strangle')
        # Straddle mode: use ATM strike (computed once — doesn't change between retries)
        is_straddle = (
            dte_cat in ('STRADDLE_WITH_ADJUSTMENT', 'SHORT_STRADDLE', 'STRADDLE_ROLL')
            or preset == 'straddle'
            or (session.get('ce', {}).get('original_strike', 0) > 0
                and session.get('ce', {}).get('original_strike', 0)
                == session.get('pe', {}).get('original_strike', 0))
        )
        min_premium = params.get('replenish_min_premium', 30.0)

        _exec_result = None
        _last_fail_reason = 'unknown'
        spot_price = 0  # declared here so regime-reset block can reference it

        for _attempt in range(1, _retry_max + 1):
            _is_last = (_attempt == _retry_max)

            # Step 3: Fetch spot price (fresh on every attempt)
            spot_price = await self._fetch_spot_price()
            if spot_price <= 0:
                _last_fail_reason = 'no_spot_price'
                log.warning(f"[{sid}] Replenish attempt {_attempt}/{_retry_max}: "
                            f"could not fetch spot price")
                if not _is_last:
                    await asyncio.sleep(_retry_delay)
                    continue
                log_activity('replenish_failed',
                            f'\u274C Replenish {closed_side.upper()} failed: no spot price',
                            sid, 'error',
                            {'closed_side': closed_side, 'error': 'no_spot_price',
                             'attempts': _attempt})
                return False

            # Step 3b: Find strike (fresh chain data on every attempt)
            strike_info = None
            if is_straddle:
                try:
                    atm = self.initializer.preview_atm_straddle(expiry)
                    if atm and atm.get('success'):
                        side_key = 'ce' if closed_side == 'ce' else 'pe'
                        _atm_premium = atm.get(f'{side_key}_premium', 0)
                        _atm_strike = atm.get('strike', 0)
                        _atm_symbol = atm.get(f'{side_key}_symbol', '')
                        if _atm_premium > 0 and _atm_strike > 0:
                            strike_info = {
                                'strike': _atm_strike,
                                'premium': _atm_premium,
                                'symbol': _atm_symbol,
                            }
                except Exception as _atm_err:
                    log.warning(f"[{sid}] Replenish straddle ATM lookup failed: {_atm_err}")

            # Strangle-mode params — hoisted here so the ATM-guard fallback (below)
            # can reuse the same chain data and premium threshold without re-fetching.
            _desired = params.get(
                f'desired_{closed_side}_premium',
                params.get('replenish_min_premium', 30.0),
            )
            _opt_type = 'call' if closed_side == 'ce' else 'put'
            _above_spot = (closed_side == 'ce')
            _chain_result = None   # populated below if strangle path runs
            _chain_spot = spot_price

            if not strike_info:
                # Strangle mode or straddle fallback: scan only the closed side's chain
                # using _rank_strikes — the same scoring used at session start.
                # Scores by |premium - desired| + liquidity penalty. No active_strike
                # or frozen_strike exclusions (fixes bugs 1, 2, 3).
                #
                # NOT using preview_strikes() here: that function requires BOTH CE and
                # PE to produce a result and returns success=False if either side has no
                # candidate — which would block PE replenish whenever CE happens to have
                # no suitable strike, and vice versa. We only need the closed side.
                try:
                    _chain_result = await asyncio.get_running_loop().run_in_executor(
                        None, self.initializer.get_full_chain, expiry
                    )
                    if _chain_result and _chain_result.get('success'):
                        _chain_spot = _chain_result.get('spot_price', spot_price) or spot_price
                        _best, _ = self.initializer._rank_strikes(
                            chain=_chain_result.get('chain', []),
                            option_type=_opt_type,
                            desired_premium=_desired,
                            spot_price=_chain_spot,
                            above_spot=_above_spot,
                            expiry=_chain_result.get('expiry', expiry),
                            underlying='BTC',
                        )
                        if _best:
                            strike_info = {
                                'strike': _best['strike'],
                                'premium': _best.get('premium', 0),
                                'symbol': _best.get('symbol', ''),
                            }
                    else:
                        log.warning(f"[{sid}] Replenish: chain fetch failed for "
                                    f"{closed_side.upper()} — "
                                    f"{_chain_result.get('error', 'no data') if _chain_result else 'no data'}")
                except Exception as _rs_err:
                    log.error(f"[{sid}] Replenish _rank_strikes exception: {_rs_err}")

            if not strike_info:
                _last_fail_reason = 'no_strikes'
                log.warning(f"[{sid}] Replenish attempt {_attempt}/{_retry_max}: "
                            f"no suitable strike for {closed_side.upper()}")
                if not _is_last:
                    await asyncio.sleep(_retry_delay)
                    continue
                log_activity('replenish_failed',
                            f'\u274C Replenish {closed_side.upper()} failed: no suitable strikes',
                            sid, 'error',
                            {'closed_side': closed_side, 'error': 'no_strikes',
                             'attempts': _attempt})
                return False

            # Step 3b-ATM: Proximity guard — prevent replenish → immediate shield cycle
            # _rank_strikes selects by |premium - desired| and may pick a strike that is
            # already within (or dangerously close to) the ATM shield's effective proximity
            # threshold.  If so, the very next heartbeat fires the ATM shield, closes the
            # freshly replenished position, and leaves PE=0 again — burning two rounds of
            # broker fees to end up where we started.
            #
            # Fix: check the candidate against a 2× safety buffer of the effective
            # proximity threshold.  If too close:
            #   (a) Re-scan the already-fetched chain for strikes outside the buffer
            #       using replenish_min_premium (NOT shift_threshold — find_new_strike
            #       uses shift_threshold which is too strict for replenish).
            #   (b) If no safe strike exists → return False so PAUSE takes over.
            if strike_info and params.get('atm_shield_enabled', False):
                _mins_rem = self._get_minutes_to_expiry() or 360
                _hours_rem = max(_mins_rem / 60.0, 0.5)
                _t_mult = min(3.0, max(1.0, 3.0 / _hours_rem))
                _base_prox = params.get('atm_shield_proximity_pct', 0.5)
                _eff_prox_pct = _base_prox * _t_mult
                # 2× buffer gives the replenished position room to survive at
                # least one heartbeat interval without triggering the shield.
                _safe_pct = _eff_prox_pct * 2.0
                _cand_strike = strike_info['strike']
                if closed_side == 'pe':
                    _cand_dist_pct = (spot_price - _cand_strike) / spot_price * 100
                else:
                    _cand_dist_pct = (_cand_strike - spot_price) / spot_price * 100
                if _cand_dist_pct <= _safe_pct:
                    log.warning(
                        f"[{sid}] Replenish attempt {_attempt}/{_retry_max}: "
                        f"{closed_side.upper()} candidate {_cand_strike} is within ATM "
                        f"safety buffer ({_cand_dist_pct:.2f}% <= {_safe_pct:.2f}% = "
                        f"2× shield threshold {_eff_prox_pct:.2f}%). "
                        f"Scanning for a safer OTM position outside the buffer."
                    )
                    _min_abs_dist = spot_price * _safe_pct / 100.0
                    # Use the already-fetched chain with replenish_min_premium threshold
                    # (not shift_threshold). find_new_strike uses shift_threshold which
                    # can block viable strikes like 71600 at $35 when shift_threshold=$50.
                    _safe_strike_info = None
                    if _chain_result and _chain_result.get('success'):
                        # Filter chain to only strikes safely outside the ATM buffer
                        _safe_chain = [
                            row for row in _chain_result.get('chain', [])
                            if (closed_side == 'ce'
                                and row.get('strike', 0) >= spot_price + _min_abs_dist)
                            or (closed_side == 'pe'
                                and row.get('strike', 0) <= spot_price - _min_abs_dist)
                        ]
                        try:
                            _safe_best, _ = self.initializer._rank_strikes(
                                chain=_safe_chain,
                                option_type=_opt_type,
                                desired_premium=_desired,
                                spot_price=_chain_spot,
                                above_spot=_above_spot,
                                expiry=_chain_result.get('expiry', expiry),
                                underlying='BTC',
                            )
                            if _safe_best:
                                _safe_strike_info = {
                                    'strike': _safe_best['strike'],
                                    'premium': _safe_best.get('premium', 0),
                                    'symbol': _safe_best.get('symbol', ''),
                                }
                        except Exception as _safe_err:
                            log.warning(f"[{sid}] Replenish ATM guard safe scan failed: "
                                        f"{_safe_err}")
                    else:
                        # Chain not available (straddle path or fetch failed): fall back
                        _safe_strike_info = find_new_strike(
                            self.initializer, session, closed_side, spot_price,
                            min_otm_distance=_min_abs_dist,
                        )
                    if _safe_strike_info:
                        log.info(
                            f"[{sid}] Replenish: safer {closed_side.upper()} strike "
                            f"{_safe_strike_info['strike']} found "
                            f"(premium ${_safe_strike_info.get('premium', 0):.2f}, "
                            f"replacing unsafe candidate {_cand_strike})."
                        )
                        strike_info = _safe_strike_info
                    else:
                        log.warning(
                            f"[{sid}] Replenish: no safe {closed_side.upper()} strike "
                            f"at >= {_safe_pct:.2f}% OTM (spot ${spot_price:.0f}). "
                            f"Blocking replenish — PAUSE to prevent replenish→shield cycle."
                        )
                        log_activity(
                            'replenish_blocked',
                            f'\u26D4 Replenish {closed_side.upper()} blocked: '
                            f'no safe strike at \u2265{_safe_pct:.2f}% OTM '
                            f'(shield buffer, spot ${spot_price:.0f}). '
                            f'Closest candidate {_cand_strike} is only {_cand_dist_pct:.2f}% '
                            f'OTM — too close to ATM shield threshold {_eff_prox_pct:.2f}%.',
                            sid, 'warning',
                            {'closed_side': closed_side,
                             'rejected_strike': _cand_strike,
                             'dist_pct': round(_cand_dist_pct, 3),
                             'safe_pct': round(_safe_pct, 3),
                             'shield_pct': round(_eff_prox_pct, 3),
                             'spot': spot_price},
                        )
                        return False  # PAUSE takes over; retries when spot moves away

            # Step 3c: Premium check — hard stop, NOT retriable (market condition)
            strike = strike_info['strike']
            premium = strike_info.get('premium', 0)
            if premium < min_premium:
                log.info(f"[{sid}] Replenish: premium ${premium:.2f} < min ${min_premium:.2f}")
                log_activity('replenish_blocked',
                            f'\u26D4 Replenish {closed_side.upper()} blocked: '
                            f'premium ${premium:.2f} < min ${min_premium:.2f}',
                            sid, 'info',
                            {'closed_side': closed_side, 'premium': premium,
                             'min_premium': min_premium, 'strike': strike})
                return False  # Market condition — do not retry

            # Step 4: Build symbol
            option_type = 'call' if closed_side == 'ce' else 'put'
            symbol = strike_info.get('symbol') or self.initializer.build_symbol(
                option_type, 'BTC', strike, expiry
            )

            # Step 5: Register pending + execute sell
            try:
                register_pending(sid, closed_side, 'pending', symbol, lots_to_sell,
                               strike, 'replenish')
            except Exception:
                pass

            _result = await self.executor.smart_execute(
                symbol=symbol, side='sell', size=lots_to_sell,
                max_reprice_attempts=_reprice_max,
                session_id=sid,
            )

            if _result.get('success'):
                _exec_result = _result
                break

            # ── Execution failed — decide whether to retry ──
            _exec_attempts = _result.get('attempts', 0)
            _exec_error = _result.get('error', 'unknown')
            try:
                clear_pending(sid, closed_side)
            except Exception:
                pass

            if _exec_attempts > 0:
                # An order was live on the exchange during the failure.
                # Do NOT retry here — risk of placing a duplicate order.
                # The OCS watchdog will retry on the next heartbeat.
                log.error(f"[{sid}] Replenish sell FAILED — order was live "
                         f"({_exec_attempts} reprice attempt(s)): {_exec_error}")
                log_activity('replenish_failed',
                            f'\u274C Replenish {closed_side.upper()} sell FAILED @ {strike}: '
                            f'{_exec_error}',
                            sid, 'error',
                            {'closed_side': closed_side, 'strike': strike,
                             'error': _exec_error, 'exec_attempts': _exec_attempts})
                return False

            # Fast failure (no order placed) — safe to retry
            _last_fail_reason = f'exec_fast_fail:{_exec_error}'
            log.warning(f"[{sid}] Replenish attempt {_attempt}/{_retry_max} fast-failed "
                       f"(no order placed): {_exec_error}")
            if not _is_last:
                await asyncio.sleep(_retry_delay)
                continue

            # Exhausted all retries
            log.error(f"[{sid}] Replenish FAILED after {_retry_max} attempt(s): {_last_fail_reason}")
            log_activity('replenish_failed',
                        f'\u274C Replenish {closed_side.upper()} failed after {_retry_max} '
                        f'attempt(s): {_last_fail_reason}',
                        sid, 'error',
                        {'closed_side': closed_side, 'error': _last_fail_reason,
                         'attempts': _retry_max})
            return False

        if not _exec_result:
            return False

        # Step 6: Success — register position in unified ledger
        fill_price = _exec_result.get('fill_price', 0)
        filled_lots = _exec_result.get('filled_size', lots_to_sell)  # use actual fill, not requested

        from .mmm_state import recompute_side_lots
        from .mmm_trigger import update_trigger_snapshots

        now = datetime.now(timezone.utc).isoformat()
        side_state = session.get(closed_side, {})

        # Reset active strike to the new replenish strike
        side_state['active_strike'] = strike
        side_state['symbol'] = symbol
        # Clear operator trigger pin — new strike has different premium dynamics
        side_state.pop('_trigger_pinned', None)
        side_state.pop('_pinned_trigger_value', None)
        side_state.pop('_pin_adj_count', None)

        # Append position to unified ledger
        counter = side_state.get('_pos_counter', 0) + 1
        side_state['_pos_counter'] = counter
        side_state.setdefault('positions', []).append({
            'id': f"{closed_side}_replenish_{counter:03d}",
            'strike': strike,
            'lots': filled_lots,
            'entry_premium': fill_price,
            'premium': fill_price,
            'type': 'replenish',
            'status': 'active',
            'created_at': now,
            'fill_confirmed_at': now,
            'order_id': str(_exec_result.get('order_id', '')),
            'client_order_id': str(_exec_result.get('client_order_id', '')),
            'shifted_at': None,
            'closed_at': None,
            'realized_pnl': None,
            'timestamp': now,
        })
        recompute_side_lots(side_state)
        session[closed_side] = side_state

        # Set trigger snapshot for the new strike
        side_state.setdefault('trigger_snapshot', {})[_strike_key(strike)] = fill_price

        # Update trigger snapshots for other strikes
        update_trigger_snapshots(session, ce_now, pe_now,
                                fetch_premium_fn=self._make_fetch_fn())
        # Force-set again to prevent overwrite
        side_state = session.get(closed_side, {})
        side_state.setdefault('trigger_snapshot', {})[_strike_key(strike)] = fill_price
        session[closed_side] = side_state

        # Partial fill tracking — if fewer lots filled than requested, mark the
        # remainder so the OCS watchdog tops up on the next heartbeat.
        _partial_fill = filled_lots < lots_to_sell
        if _partial_fill:
            _remaining = lots_to_sell - filled_lots
            session[f'_replenish_lots_remaining_{closed_side}'] = _remaining
            session['_replenish_ocs_active'] = True
            log.warning(f"[{sid}] Replenish partial fill: {filled_lots}/{lots_to_sell} lots — "
                       f"{_remaining} remaining, OCS watchdog will top up next heartbeat")
        else:
            session.pop(f'_replenish_lots_remaining_{closed_side}', None)
            # _replenish_ocs_active is cleared by the OCS guard caller on full success

        # Record commission via ledger (CRIT-1 fix)
        _od = _exec_result.get('order_details') or {}
        _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)
        if _commission:
            from .mmm_pnl_core import record_fee as _pnl_fee
            _pnl_fee(session, _commission, 'sell_replenish',
                     order_id=str(_exec_result.get('order_id', '')), side=closed_side)

        # Update premium collected
        premium_collected = fill_price * filled_lots * LOT_SIZE_BTC
        session['total_premium_collected'] = session.get('total_premium_collected', 0) + premium_collected
        prem_key = f'{closed_side}_premium_collected'
        session[prem_key] = session.get(prem_key, 0) + premium_collected

        # Record replenish in adjustment_history so lot_velocity checks count it
        session.setdefault('adjustment_history', []).append({
            'side': closed_side.upper(),
            'aggressor': 'REPLENISH',
            'lots_sold': filled_lots,
            'premium': fill_price,
            'strike': strike,
            'timestamp': now,
        })
        if len(session['adjustment_history']) > 200:
            session['adjustment_history'] = session['adjustment_history'][-200:]

        # Update replenish tracking
        session['_replenish_count'] = session.get('_replenish_count', 0) + 1
        session['_last_replenish_at'] = time.time()
        session.setdefault('_replenish_history', []).append({
            'side': closed_side,
            'strike': strike,
            'lots': filled_lots,
            'premium': fill_price,
            'timestamp': now,
        })

        # Clear pending
        try:
            clear_pending(sid, closed_side)
        except Exception:
            pass

        # Activity log
        log_activity('replenish_complete',
                    f'\u2705 Replenish #{session["_replenish_count"]}: '
                    f'{closed_side.upper()} {filled_lots}L @ {strike} '
                    f'(${fill_price:.2f}) — hedge restored',
                    sid, 'success',
                    {
                        'closed_side': closed_side,
                        'strike': strike,
                        'lots': filled_lots,
                        'premium': fill_price,
                        'premium_collected': premium_collected,
                        'replenish_count': session['_replenish_count'],
                    })

        # Trade audit (fire-and-forget)
        try:
            from .mmm_audit_log import get_audit_log
            get_audit_log().enqueue_trade(
                session_id=sid,
                action='SELL',
                option_type=closed_side.upper(),
                strike=int(strike),
                quantity_requested=lots_to_sell,
                quantity_filled=filled_lots,
                premium=fill_price,
                event_type='REPLENISH',
                adj_type='replenish',
                mechanism='replenish',
            )
        except Exception:
            pass

        session['updated_at'] = now

        # ── REGIME + TREND RESET (hedge-restoration fresh start) ─────────────
        # After successfully re-entering the empty side, reset all regime and
        # trend state so the new leg starts with a clean slate — exactly as if
        # the session had just started.  Rationale:
        #   • The old trend anchor was relative to the previous entry price.
        #     The replenish enters at a new strike/premium; the anchor must
        #     move to current spot so T1/T2/T3/T4 tiers compute correctly.
        #   • Vol/trend regime flags that blocked the replenish were computed
        #     relative to the old entry context.  The new leg is a fresh trade.
        #   • Wind-down trigger flags would block future adjustments on the
        #     replenished side; they must be cleared now.
        #   • Consecutive-direction block must be reset — the new leg has no
        #     direction history yet.
        # The regime module will recompute _vol_regime / _trend_regime / action
        # from scratch on the very next heartbeat using live market data.
        try:
            _rst_spot = spot_price if spot_price > 0 else session.get('_regime_spot_price', 0)
            # Trend state — reset anchor to current spot, tier to NONE
            session['_trend_anchor_spot'] = _rst_spot
            session['_trend_regime'] = 'NORMAL'
            session['_trend_tier'] = 0
            session['_trend_direction'] = 'none'
            session.pop('_trend_since', None)
            session.pop('_trend_high', None)
            session.pop('_trend_low', None)
            session.pop('_trend_ema', None)
            session.pop('_trend_ema_prev', None)
            session['_trend_calm_beats'] = 0
            session['_trend_plateau_beats'] = 0
            session['_trend_t4_beats'] = 0
            session['_trend_wind_down_triggered'] = False
            # Vol regime — reset to NORMAL; cooldown counter reset
            session['_vol_regime'] = 'NORMAL'
            session['_vol_regime_beats_below'] = 0
            session['_vol_wind_down_triggered'] = False
            # ATM wind-down
            session['_atm_wind_down_triggered'] = False
            # Regime action — cleared so next heartbeat recomputes from fresh state
            session.pop('_regime_action', None)
            # Consecutive-direction block — new leg has no direction history
            session['_consecutive_dir_blocked'] = False
            session['_consecutive_same_dir_count'] = 0
            session['_consecutive_same_dir_side'] = ''
            session.pop('_consecutive_dir_blocked_at', None)
            # One-side-close guard flags — hedge is restored, clear both sides
            session.pop('_one_side_closed_ce', None)
            session.pop('_one_side_closed_pe', None)
            session.pop('_replenish_ocs_active', None)
            session.pop(f'_replenish_lots_remaining_{closed_side}', None)
            session.pop('_awaiting_user_action', None)
            session.pop('_awaiting_user_action_reason', None)
            session.pop('_awaiting_user_action_details', None)
            session.pop('_ocs_telegram_sent_at', None)
            log.info(f"[{sid}] Replenish: regime/trend state reset to clean slate "
                     f"(anchor={_rst_spot:.0f}, new leg starts fresh)")
        except Exception as _rst_err:
            log.warning(f"[{sid}] Replenish: regime reset failed (non-critical): {_rst_err}")
        # ── END REGIME RESET ─────────────────────────────────────────────────

        log.info(f"[{sid}] Replenish complete: {closed_side.upper()} "
                f"{filled_lots}L @ {strike} (${fill_price:.2f})")

        return True

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
            # Breakeven + gamma cache invalidation — positions changed after lot recycling
            try:
                get_breakeven_engine().invalidate_cache(sid)
                get_gamma_detector().invalidate_cache(sid)
            except Exception:
                pass
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
        premium_floor = params.get('shift_recycle_premium_floor', 20.0)
        if premium_floor <= 0:
            # Dynamic mode: close frozen if cheaper than N% of new strike premium
            dynamic_ratio = params.get('shift_recycle_floor_ratio', 0.40)
            premium_floor = new_strike_info.get('premium', 100.0) * dynamic_ratio
        max_pct = params.get('shift_recycle_max_pct', 1.0)

        side_state = session.get(side, {})
        frozen_positions = side_state.get('frozen_positions', [])

        if not frozen_positions:
            return 0.0

        # Capacity pressure gate: only recycle when lot book is under pressure.
        # Without this gate the recycle fires at every shift — closing winning,
        # naturally-decaying positions that would reach close_at_threshold on their
        # own, wasting fees and leaving premium on the table.
        # Same pattern as M1 Harvest (harvest_pressure_threshold).
        max_lots = max(params.get('max_lots_per_side', 100), 1)
        total_side_lots = side_state.get('total_lots', 0)
        capacity_pressure = total_side_lots / max_lots
        min_pressure = params.get('shift_recycle_pressure_threshold', 0.7)
        if capacity_pressure < min_pressure:
            log.debug(
                f"[{sid}] Shift recycle skipped: {side.upper()} pressure "
                f"{capacity_pressure:.2f} < {min_pressure:.2f} — no capacity relief needed"
            )
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
            # Stop check: abort if monitor was stopped mid-loop (March 12 fix —
            # old monitor kept placing orders after watchdog killed the session)
            if self._should_stop():
                log.info(f"[{sid}] Shift recycle: stop requested, aborting remaining closes")
                break
            # Fix A2: Per-beat cap on shift-time recycle (March 12 incident fix)
            max_per_beat = params.get('shift_recycle_max_per_beat', 10)
            if closed_lots >= max_per_beat:
                log.info(
                    f"[{sid}] Shift recycle: per-beat cap reached "
                    f"({max_per_beat} lots) — deferring remaining to next beat"
                )
                break
            # Fix A3: Heartbeat wall-clock deadline (March 12 incident fix)
            beat_deadline = session.get('_beat_deadline', 0)
            if beat_deadline and time.monotonic() > beat_deadline:
                log.warning(
                    f"[{sid}] Shift recycle: heartbeat deadline exceeded "
                    f"— deferring remaining closes to next beat"
                )
                break
            lots = close_payload['lots']
            live_premium = close_payload['current_premium']
            try:
                result = await close_position(
                    self.executor, self.initializer, session, close_payload,
                    mechanism='shift_recycle',
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
                _reject_reason = result.get('error', 'unknown')
                log.warning(
                    f"[{sid}] Shift recycle: close rejected for "
                    f"{side.upper()} @ {close_payload['strike']}: "
                    f"{_reject_reason}"
                )
                # Guardian velocity/hedge block → stop trying (cap applies to all)
                if result.get('hedge_guard_blocked'):
                    log.info(f"[{sid}] Shift recycle: guardian blocked — stopping loop")
                    break

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

            # Breakeven + gamma cache invalidation — positions changed after shift-time recycle
            try:
                get_breakeven_engine().invalidate_cache(sid)
                get_gamma_detector().invalidate_cache(sid)
            except Exception:
                pass

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
        params = session.get('params', {})
        max_closes = params.get('close_at_max_per_beat', 3)

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

        # Wide-spread guard removed: if bid is ≤ threshold we close unconditionally.
        # Execution uses bid-entry (maker limit at bid), so the fill price ≤ threshold
        # regardless of mark price. Carrying the position is unnecessary risk.

        if closeable:
            threshold_note = f' (wind-down elevated threshold: {wd_threshold})' if using_elevated else ''
            bid_note = ' [using bid price]' if use_bid else ''
            closeable_summary = ', '.join([f"{p['side'].upper()} @ {p['strike']}" for p in closeable])
            log_activity('info',
                        f'Close-at-5 Scan: {len(closeable)} position(s) ready to close'
                        f'{threshold_note}{bid_note} - {closeable_summary}',
                        sid, 'info',
                        {'closeable_count': len(closeable), 'positions': closeable_summary,
                         'wind_down_elevated': using_elevated,
                         'using_bid_price': use_bid,
                         'threshold_used': wd_threshold if using_elevated else normal_threshold})

        closed_count = 0
        sides_closed: set = set()  # Fix #11: track which sides had successful closes

        # ── HEDGE INTEGRITY: both-sides-closing detection ─────────────────
        # If the closeable list covers ALL lots on BOTH sides, both sides are
        # being wound down simultaneously → no one-sided exposure risk.
        # In that case, bypass the hedge guard so the strategy can complete.
        _ce_closeable_lots = sum(p['lots'] for p in closeable if p['side'] == 'ce')
        _pe_closeable_lots = sum(p['lots'] for p in closeable if p['side'] == 'pe')
        _ce_total = session.get('ce', {}).get('total_lots', 0)
        _pe_total = session.get('pe', {}).get('total_lots', 0)
        _both_sides_closing = (
            _ce_closeable_lots >= _ce_total and _pe_closeable_lots >= _pe_total
            and _ce_total > 0 and _pe_total > 0
        )
        if _both_sides_closing:
            log.info(
                f"[{sid}] Close-at-5: both sides fully closeable "
                f"(CE={_ce_closeable_lots}/{_ce_total}, PE={_pe_closeable_lots}/{_pe_total}) "
                f"— hedge guard bypassed for clean exit"
            )
        # ──────────────────────────────────────────────────────────────────

        for pos in closeable:
            # Check if monitor was stopped while we were executing closes
            if self._should_stop():
                log.info(f"[{sid}] Close-at-5: stop requested, aborting remaining closes")
                break

            # close_at_max_per_beat cap — defer remainder to next heartbeat
            if closed_count >= max_closes:
                log.info(
                    f"[{sid}] Close-at-5: reached close_at_max_per_beat={max_closes}, "
                    f"deferring {len(closeable) - closed_count} position(s) to next heartbeat"
                )
                break

            # G4: Beat deadline — defer remaining closes to next heartbeat
            beat_deadline = session.get('_beat_deadline', 0)
            if beat_deadline and time.monotonic() > beat_deadline:
                log.warning(
                    f"[{sid}] Close-at-5: heartbeat deadline exceeded "
                    f"— deferring {len(closeable) - closed_count} remaining closes"
                )
                break


            result = await close_position(
                self.executor, self.initializer, session, pos,
                hedge_guard=not _both_sides_closing,
                mechanism='wind_down' if using_elevated else 'close_at_5',
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

                # Breakeven + gamma cache invalidation — positions changed after close-at-5 fill
                try:
                    get_breakeven_engine().invalidate_cache(sid)
                    get_gamma_detector().invalidate_cache(sid)
                except Exception:
                    pass

                # Check if side fully closed — heartbeat will detect and PAUSE
                # (one-side close guard runs after _process_close_at_5 returns)
                if check_side_fully_closed(session, pos['side']):
                    log.info(
                        f"[{sid}] {pos['side'].upper()} fully closed — "
                        f"one-side guard in heartbeat will evaluate."
                    )

            elif result.get('hedge_guard_blocked'):
                # Hedge integrity guard blocked this close — stop trying
                # more positions on this side (they'll all be blocked too)
                log.info(
                    f"[{sid}] Close-at-5: hedge guard stopped further "
                    f"{pos['side'].upper()} closes (preserving hedge)"
                )
                break

        # AUDIT FIX (stale-unrealized bug): After closes, realized_pnl increased but
        # unrealized_pnl still reflects pre-close state (next heartbeat step 8 would
        # fix it, but the mmm_close_at_5 WS event already triggered fetchSessions() in
        # the frontend, which reads SQLite — which has the PREVIOUS heartbeat's data).
        # Refreshing unrealized + saving here ensures REST returns accurate net_pnl
        # even in the race window between close emission and heartbeat step 8.
        if closed_count > 0:
            try:
                fresh = self._engine.compute_unrealized_pnl(session, self._make_fetch_fn())
                session['unrealized_pnl'] = fresh
                self._save_my_session(session)
                log.debug(f"[{sid}] P&L refresh after close-at-5: unrealized={fresh:.4f}")
            except Exception as e:
                log.warning(f"[{sid}] P&L refresh after close-at-5 failed (non-critical): {e}")

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

        # BUG-9 FIX: Update _last_trigger_result so gamma-aware multiplier in
        # calculate_lots_to_sell uses current excess data, not stale values from
        # the previous heartbeat's evaluate_triggers call.
        ce_base = max(ce_trigger, 1.0)  # matches TRIGGER_PCT_FLOOR in mmm_trigger
        pe_base = max(pe_trigger, 1.0)
        ce_excess_pct = ((ce_now - ce_trigger) / ce_base) * 100 if ce_active_lots > 0 else 0
        pe_excess_pct = ((pe_now - pe_trigger) / pe_base) * 100 if pe_active_lots > 0 else 0
        params = session.get('params', {})
        session['_last_trigger_result'] = {
            'ce_excess_pct': round(ce_excess_pct, 2),
            'pe_excess_pct': round(pe_excess_pct, 2),
            'min_trigger_move': params.get('min_trigger_move', 10.0),
            'outcome': 'both_triggered',
        }

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
            # Reverse Mode: close all reverse positions FIRST.
            # They are unhedged and must be covered before normal positions.
            if session.get('_reverse', {}).get('positions'):
                try:
                    await close_all_reverse_positions(session, self._engine, reason)
                    disable_reverse_mode(session, f'auto_close_all: {reason}')
                except Exception as _rev_close_all_err:
                    log.error(f"[{sid}] Failed to close reverse positions in auto_close_all: {_rev_close_all_err}")

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
                _ce_result, _pe_result = await asyncio.gather(
                    ce_task, pe_task, return_exceptions=True)
                ce_fails = (
                    [f"CE close raised: {_ce_result}"]
                    if isinstance(_ce_result, Exception) else _ce_result
                )
                pe_fails = (
                    [f"PE close raised: {_pe_result}"]
                    if isinstance(_pe_result, Exception) else _pe_result
                )
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
            # ── Shutdown fill sync flush ──────────────────────────────────────
            # After placing all close orders, give exchange up to 15 s to return
            # fills, then run one fill sync pass.  This catches the race where
            # orders are filled milliseconds after _close_one_side returns
            # (executor already confirmed fills, but the sync confirms the
            # close_fill_price and locks in the final P&L).
            # Also catches any externally-closed positions we missed.
            try:
                await asyncio.sleep(3)   # brief wait for fills to land
                _shutdown_rest = self._create_heartbeat_rest_client()
                _shutdown_expiry = session.get('params', {}).get('expiry', '')
                _n_synced = await self._fill_syncer.sync(
                    _shutdown_rest, session, _shutdown_expiry)
                if _n_synced:
                    log.info(
                        f"[{sid}] Shutdown fill sync: confirmed {_n_synced} "
                        f"position(s) — final P&L locked in."
                    )
            except Exception as _fs_e:
                log.warning(
                    f"[{sid}] Shutdown fill sync failed (non-critical): {_fs_e}")

            # AUDIT FIX: refresh unrealized before stop() so the saved session has
            # accurate net_pnl (realized was updated by closes but unrealized is stale).
            # Uses cached prices — best-effort, never blocks the stop path.
            try:
                fresh = self._engine.compute_unrealized_pnl(session, self._make_fetch_fn())
                session['unrealized_pnl'] = fresh
                log.debug(f"[{sid}] P&L refresh before auto-close stop: unrealized={fresh:.4f}")
            except Exception as _e:
                log.warning(f"[{sid}] P&L refresh before stop failed (non-critical): {_e}")
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
                    session_id=sid,
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
                        # Record exchange commission from auto-close active
                        _od = result.get('order_details') or {}
                        _comm = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)
                        # ── P&L via ledger ────────────────────────────
                        _ac_oid = str(result.get('order_id', '') or '')
                        from .mmm_pnl_core import record_close as _pnl_ac_rec
                        _pnl_ac_rec(
                            session=session,
                            order_id=_ac_oid,
                            symbol=symbol,
                            option_side=side_key,
                            strike=active_strike,
                            lots=int(active_lots),
                            entry_premium=float(avg_entry),
                            close_premium=float(close_price),
                            commission=abs(float(_comm)) if _comm else 0.0,
                            source='auto_close_active',
                        )
                        # ── END P&L via ledger ────────────────────────
                        log.info(
                            f"[{sid}] Closed {active_lots} active "
                            f"{side_key.upper()} @ {active_strike}, "
                            f"avg_entry: {avg_entry:.2f}, P&L: {pnl:.2f}"
                        )
                        # Fix #23: Mark all active positions as closed in positions[]
                        _now = datetime.now(timezone.utc).isoformat()
                        _close_oid = str(result.get('order_id', '') or '')
                        _close_comm = abs(_comm)
                        for _pos in side_state.get('positions', []):
                            if _pos.get('status') == 'active':
                                _pos['status'] = 'closed'
                                _pos['closed_at'] = _now
                                # Fill sync tracking: record close order so
                                # FillSyncer can match fills precisely.
                                if _close_oid:
                                    _pos['close_order_id'] = _close_oid
                                _pos['close_fill_price'] = round(close_price, 6)
                                _pos['_fill_confirmed'] = True
                                # Record what was booked so FillSyncer can
                                # compute the correction (actual − estimated).
                                _pos_lots = _pos.get('lots', 0)
                                _pos_entry = float(_pos.get('entry_premium', 0) or 0)
                                _pos['_estimated_pnl_booked'] = round(
                                    (_pos_entry - close_price) * _pos_lots * LOT_SIZE_BTC, 8)
                                _pos['_estimated_commission_booked'] = round(
                                    _close_comm * (_pos_lots / max(active_lots, 1)), 8)
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
                            # Record exchange commission from auto-close frozen
                            _od = result.get('order_details') or {}
                            _comm = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)
                            # ── P&L via ledger ────────────────────────
                            _fz_oid = str(result.get('order_id', '') or '')
                            from .mmm_pnl_core import record_close as _pnl_fz_rec
                            _pnl_fz_rec(
                                session=session,
                                order_id=_fz_oid,
                                symbol=symbol,
                                option_side=side_key,
                                strike=frozen_strike,
                                lots=int(frozen_lots),
                                entry_premium=float(frozen_entry),
                                close_premium=float(close_price),
                                commission=abs(float(_comm)) if _comm else 0.0,
                                source='auto_close_frozen',
                            )
                            # ── END P&L via ledger ────────────────────
                            log.info(
                                f"[{sid}] Closed {frozen_lots} frozen "
                                f"{side_key.upper()} @ {frozen_strike}, P&L: {pnl:.2f}"
                            )
                            closed_frozen_indices.append(fi)
                            # Fill sync tracking for frozen closes
                            frozen['close_order_id'] = str(result.get('order_id', '') or '')
                            frozen['close_fill_price'] = round(close_price, 6)
                            frozen['_fill_confirmed'] = True
                            frozen['_estimated_pnl_booked'] = round(pnl, 8)
                            _fcomm = abs(float(
                                (result.get('order_details') or {}).get(
                                    'paid_commission',
                                    (result.get('order_details') or {}).get('commission', 0)
                                ) or 0))
                            frozen['_estimated_commission_booked'] = round(_fcomm, 8)
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
            # Build map: _pos_id → frozen view entry (carries fill tracking fields)
            closed_frozen_map = {
                frozen_view[fi].get('_pos_id'): frozen_view[fi]
                for fi in closed_frozen_indices
                if fi < len(frozen_view)
            }
            for _pos in side_state.get('positions', []):
                if _pos.get('id') in closed_frozen_map:
                    _fv = closed_frozen_map[_pos['id']]
                    _pos['status'] = 'closed'
                    _pos['closed_at'] = _now
                    # Propagate fill sync tracking fields from frozen view
                    for _field in ('close_order_id', 'close_fill_price',
                                   '_fill_confirmed', '_estimated_pnl_booked',
                                   '_estimated_commission_booked'):
                        if _field in _fv:
                            _pos[_field] = _fv[_field]

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
        Return the total lots that OTHER MMM sessions (running OR stopped)
        claim at a given exchange symbol.  Used during reconciliation to
        avoid auto-syncing positions that belong to a different session.

        BUG FIX: Previously only checked running monitors. Stopped/idle
        sessions from storage were invisible, causing orphan adoption of
        positions that belonged to stopped sessions.
        """
        total = 0

        # 1) Check running monitors (in-memory, most up-to-date)
        checked_sids = {self.session_id}  # skip self
        for other_sid, other_mon in get_all_monitors().items():
            if other_sid == self.session_id:
                continue
            checked_sids.add(other_sid)
            total += self._count_session_lots_at_symbol(other_mon.session, symbol)

        # 2) Check ALL sessions from storage (catches stopped/idle/historical)
        try:
            from .mmm_storage import get_storage
            storage = get_storage()
            for stored in storage.list_sessions():
                stored_sid = stored.get('session_id', '')
                if stored_sid in checked_sids:
                    continue  # already counted from monitor
                checked_sids.add(stored_sid)
                total += self._count_session_lots_at_symbol(stored, symbol)
        except Exception as e:
            log.warning(f"[{self.session_id}] Failed to check stored sessions: {e}")

        return total

    def _count_session_lots_at_symbol(self, session_data: Dict, symbol: str) -> int:
        """Count lots a session claims at a specific exchange symbol."""
        total = 0
        other_expiry = session_data.get('params', {}).get('expiry', '')
        for side_key in ['ce', 'pe']:
            side = session_data.get(side_key, {})
            opt = 'call' if side_key == 'ce' else 'put'

            # Active strike lots (from positions ledger — most accurate)
            for pos in side.get('positions', []):
                if pos.get('status') not in ('active', 'shifted'):
                    continue
                p_strike = pos.get('strike', 0)
                if p_strike > 0:
                    psym = self.initializer.build_symbol(opt, 'BTC', p_strike, other_expiry)
                    if psym == symbol:
                        total += pos.get('lots', 0)

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

    def _has_recent_fill_at_strike(
        self, side_state: Dict, strike: float, grace_seconds: int = 120
    ) -> bool:
        """
        Return True if any position at *strike* was fill-confirmed within
        grace_seconds ago.

        The exchange REST positions API has a settlement lag of ~5-60s after
        a fresh fill. Running reconciliation during this window can wrongly
        zero a just-confirmed position. This guard prevents that by checking
        fill_confirmed_at on every position at the target strike.

        Root cause: mmm21mar26-3 — PE zeroed 5s after fill (2026-03-21).
        """
        now_ts = datetime.now(timezone.utc)
        for pos in side_state.get('positions', []):
            if abs(pos.get('strike', -1) - strike) > 0.1:
                continue
            fca = pos.get('fill_confirmed_at') or pos.get('created_at')
            if not fca:
                continue
            try:
                pos_dt = datetime.fromisoformat(fca)
                if pos_dt.tzinfo is None:
                    pos_dt = pos_dt.replace(tzinfo=timezone.utc)
                if (now_ts - pos_dt).total_seconds() < grace_seconds:
                    return True
            except Exception:
                pass
        return False

    async def _verify_order_filled(self, rest, order_id: str) -> str:
        """
        Query the exchange to verify if a specific order was filled.

        Returns:
            'filled'  — order exists and was filled (position is/was real)
            'dead'    — order was cancelled/rejected (position is phantom)
            'open'    — order is still working (unexpected after 120s)
            'unknown' — could not verify (network error, order not found)

        Used by reconciliation to verify positions by order_id instead of
        relying on exchange position count (which includes manual/other-algo positions).
        """
        try:
            order_data = await rest.get_order(str(order_id))
            if not order_data:
                return 'unknown'
            state = (order_data.get('state', '') or order_data.get('status', '')).lower()
            if state in ('filled', 'closed', 'completed'):
                return 'filled'
            elif state in ('cancelled', 'canceled', 'rejected', 'expired'):
                return 'dead'
            elif state:
                return 'open'
            return 'unknown'
        except Exception as e:
            log.debug(f"Order verify failed for {order_id}: {e}")
            return 'unknown'

    def _auto_correct_missing_positions(
        self, side_state: Dict, strike: float, reason: str, close_price: float = 0.0
    ):
        """
        Mark ALL positions at a given strike as closed/expired in the
        Unified Position Ledger. Called when exchange shows 0 lots at a
        strike the session thinks it owns.

        close_price: current market premium used to book realized P&L.
          Defaults to 0.0 (option expired worthless).
          Pass the live mark price when available.
        """
        from .mmm_state import recompute_side_lots
        now = datetime.now(timezone.utc).isoformat()
        removed_lots = 0
        strike_tol = 1.0  # float tolerance for strike comparison
        _LOT_SIZE_BTC = 0.001
        realized_gain = 0.0

        for pos in side_state.get('positions', []):
            if pos.get('status') in ('active', 'shifted'):
                pos_strike = pos.get('strike', 0)
                if abs(pos_strike - strike) < strike_tol:
                    pos_lots = pos.get('lots', 0)
                    removed_lots += pos_lots
                    pos['status'] = 'closed'
                    pos['closed_at'] = now
                    pos['close_reason'] = f'exchange_reconciliation:{reason}'
                    pos['close_price'] = round(close_price, 6)
                    # DO NOT set _fill_confirmed — let FillSyncer process any
                    # actual fill that arrives later and book correct P&L.
                    # DO NOT book estimated P&L — reconciliation is READ-ONLY.

        if removed_lots > 0:
            recompute_side_lots(side_state)
            # ── PnlCore: flag discrepancy, do NOT book P&L ──────────
            # Reconciliation is read-only. Human reviews and uses
            # manual_close endpoint to record actual close price + P&L.
            from .mmm_pnl_core import flag_discrepancy as _pnl_flag
            _side_label = side_state.get('side', '?').upper()
            _pnl_flag(
                session=self.session,
                symbol=f'{_side_label}-BTC-{int(strike)}',
                option_side=side_state.get('side', ''),
                strike=strike,
                session_lots=removed_lots,
                exchange_lots=0,
                reason=reason,
            )
            log.warning(
                f"[{self.session_id}] RECON-FLAG: {removed_lots} phantom "
                f"{_side_label} lots @ {strike} removed from session "
                f"(reason: {reason}, exchange=0). P&L NOT booked — "
                f"awaiting fill_sync or manual close."
            )
            # Emit safety alert for human review
            try:
                from .mmm_websocket import emit_safety
                emit_safety(self.session_id, 'POSITION_MISSING_FROM_EXCHANGE', {
                    'side': _side_label,
                    'strike': strike,
                    'lots': removed_lots,
                    'reason': reason,
                    'action': 'HUMAN_REVIEW — use manual close to book P&L',
                })
            except Exception:
                pass
            log_activity('reconciliation_autocorrect',
                f'RECON-FLAG: removed {removed_lots} phantom '
                f'{_side_label} lots @ {strike} '
                f'(exchange shows 0, P&L NOT booked — needs manual close)',
                self.session_id, 'warning',
                {'strike': strike, 'removed_lots': removed_lots, 'reason': reason,
                 'close_price': round(close_price, 6),
                 'pnl_action': 'PENDING_MANUAL_CLOSE'})

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

        # ── Tick down grace-period counters for pending close-at-5 verifications.
        # Entries with grace_beats <= 0 are purged so that genuinely stale
        # positions (never confirmed closed by the exchange) eventually surface.
        _pcv = session.get('_pending_close_verification', {})
        if _pcv:
            expired_keys = [k for k, v in _pcv.items() if v.get('grace_beats', 0) <= 0]
            for k in expired_keys:
                log.warning(
                    f"[{sid}] close_at_5 verification: grace expired for {k} "
                    f"— any remaining exchange position will now surface as a mismatch"
                )
                del _pcv[k]

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

        # ── One-time cleanup: remove ALL orphan_adopted positions.
        #    Auto-adopt is now disabled — these are artifacts from the old
        #    code that adopted other sessions'/algos'/manual positions. ──
        if not session.get('_orphan_adopted_cleaned'):
            session['_orphan_adopted_cleaned'] = True
            from .mmm_state import recompute_side_lots as _recompute
            for side_key in ['ce', 'pe']:
                side = session.get(side_key, {})
                _now = datetime.now(timezone.utc).isoformat()
                removed_lots = 0
                for _pos in side.get('positions', []):
                    if _pos.get('type') == 'orphan_adopted' and _pos.get('status') in ('active', 'shifted'):
                        removed_lots += _pos.get('lots', 0)
                        _pos['status'] = 'closed'
                        _pos['closed_at'] = _now
                        _pos['close_reason'] = 'orphan_adopt_disabled_cleanup'
                if removed_lots > 0:
                    _recompute(side)
                    log.warning(
                        f"[{sid}] Cleanup: removed {removed_lots} orphan_adopted "
                        f"{side_key.upper()} lots (auto-adopt disabled)"
                    )
                    log_activity('reconciliation_autocorrect',
                        f'🧹 Cleanup: removed {removed_lots} orphan_adopted '
                        f'{side_key.upper()} lots — auto-adopt is now disabled',
                        sid, 'warning',
                        {'side': side_key, 'removed_lots': removed_lots})

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

                    # Exchange shows 0 — verify via order_id before auto-correcting.
                    # Exchange count is NOT reliable when manual trades or other algos
                    # trade the same strike on the same account (they affect net position).
                    # We verify OUR fills via client_order_id/order_id instead.
                    if self._has_recent_fill_at_strike(side, active_strike, grace_seconds=120):
                        # Settlement lag — our fill hasn't shown up on exchange yet.
                        discrepancies[-1]['auto_corrected'] = False
                        log.info(
                            f"[{sid}] Recon: skipping MISSING_ON_EXCHANGE auto-correct for "
                            f"{side_key.upper()} @ {active_strike} — fill confirmed within 120s "
                            f"(exchange settlement lag)"
                        )
                    else:
                        # Check order_ids: if ALL active positions at this strike have
                        # confirmed fills, exchange showing 0 means external force-close
                        # (option expired / manual buyback). Safe to auto-correct.
                        # If any order is "dead" (never filled), it's a phantom — remove.
                        active_pos_at_strike = [
                            p for p in side.get('positions', [])
                            if abs(p.get('strike', 0) - active_strike) < 0.1
                            and p.get('status') in ('active',)
                            and p.get('order_id')
                        ]
                        _should_correct = True
                        for _ap in active_pos_at_strike:
                            _oid_status = await self._verify_order_filled(rest, _ap['order_id'])
                            if _oid_status == 'unknown':
                                # Can't verify — be conservative, skip
                                _should_correct = False
                                log.warning(
                                    f"[{sid}] Recon: MISSING_ON_EXCHANGE {side_key.upper()} "
                                    f"@ {active_strike} — cannot verify order "
                                    f"{_ap['order_id']} (skipping auto-correct)"
                                )
                                break
                        if _should_correct:
                            # Pass current mark price so P&L is booked at close.
                            # 0.0 = expired worthless (correct if option lapsed).
                            _recon_close_price = float(
                                (self._last_good_ce if side_key == 'ce' else self._last_good_pe)
                                or 0.0
                            )
                            self._auto_correct_missing_positions(
                                side_state=side,
                                strike=active_strike,
                                reason='exchange_shows_zero',
                                close_price=_recon_close_price,
                            )
                        else:
                            discrepancies[-1]['auto_corrected'] = False

                elif abs(active_lots - effective_exchange_size) > 0.1 and active_lots > 0:
                    # Count mismatch — exchange shows a different number than session.
                    # NEVER auto-correct by count comparison: the exchange figure includes
                    # manual trades and other algos at the same strike on the same account.
                    # Only log the discrepancy; human or order_id verification decides.
                    discrepancies.append({
                        'side': side_key.upper(),
                        'type': 'SIZE_MISMATCH',
                        'detail': (
                            f"{side_key.upper()} active @ {active_strike}: session={active_lots} "
                            f"vs exchange={exchange_size} (other_mmm={other_lots_at_active}) "
                            f"— NOT auto-corrected (count comparison unreliable with "
                            f"manual/other-algo positions at same strike)"
                        ),
                        'symbol': active_symbol,
                        'session_lots': active_lots,
                        'exchange_size': exchange_size,
                        'auto_corrected': False,
                    })
                    log.warning(
                        f"[{sid}] Recon SIZE_MISMATCH {side_key.upper()} @ {active_strike}: "
                        f"session={active_lots} exchange={exchange_size} "
                        f"(other_mmm={other_lots_at_active}) — logged only, no auto-correct. "
                        f"Verify via client_order_id if count diverges further."
                    )

                    # Bug B fix: First-time alert when exchange has MORE lots than session.
                    # Pre-existing / external positions can contaminate readings — alert operator.
                    if exchange_size > active_lots:
                        _warn_key = f'{side_key}_{int(active_strike)}'
                        _warned_list = session.setdefault('_warned_size_excess_strikes', [])
                        if _warn_key not in _warned_list:
                            _warned_list.append(_warn_key)
                            excess = int(round(exchange_size - active_lots))
                            log_activity('exchange_position_warning',
                                f'⚠️ Exchange has {excess} MORE {side_key.upper()} lots @ {active_strike} '
                                f'than session tracks (exchange={int(exchange_size)}, '
                                f'session={active_lots}). May be pre-existing or external positions '
                                f'— NOT adopted. Investigate manually.',
                                sid, 'warning',
                                {'side': side_key, 'strike': active_strike,
                                 'exchange_lots': int(exchange_size),
                                 'session_lots': active_lots,
                                 'excess': excess,
                                 'other_mmm_lots': other_lots_at_active})

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

                        # Same two-layer guard as active MISSING_ON_EXCHANGE:
                        # 1. Fill-age guard (120s settlement lag protection)
                        # 2. Order_id verification before auto-correcting
                        if self._has_recent_fill_at_strike(side, f_strike, grace_seconds=120):
                            discrepancies[-1]['auto_corrected'] = False
                            log.info(
                                f"[{sid}] Recon: skipping FROZEN_MISSING auto-correct for "
                                f"{side_key.upper()} @ {f_strike} — fill confirmed within 120s"
                            )
                        else:
                            frozen_pos_with_oid = [
                                p for p in side.get('positions', [])
                                if abs(p.get('strike', 0) - f_strike) < 0.1
                                and p.get('status') == 'shifted'
                                and p.get('order_id')
                            ]
                            _should_correct = True
                            for _fp in frozen_pos_with_oid:
                                _fstatus = await self._verify_order_filled(rest, _fp['order_id'])
                                if _fstatus == 'unknown':
                                    _should_correct = False
                                    log.warning(
                                        f"[{sid}] Recon: FROZEN_MISSING {side_key.upper()} "
                                        f"@ {f_strike} — cannot verify order "
                                        f"{_fp['order_id']} (skipping auto-correct)"
                                    )
                                    break
                            if _should_correct:
                                _recon_close_price_f = float(
                                    (self._last_good_ce if side_key == 'ce' else self._last_good_pe)
                                    or 0.0
                                )
                                self._auto_correct_missing_positions(
                                    side_state=side,
                                    strike=f_strike,
                                    reason='frozen_exchange_shows_zero',
                                    close_price=_recon_close_price_f,
                                )
                            else:
                                discrepancies[-1]['auto_corrected'] = False

                    elif abs(total_frozen_lots - effective_frozen_ex) > 0.1:
                        if total_frozen_lots > effective_frozen_ex:
                            # Never auto-correct count mismatch for frozen positions either —
                            # same reason as active SIZE_MISMATCH: exchange count includes
                            # manual/other-algo positions at the same strike.
                            discrepancies.append({
                                'side': side_key.upper(),
                                'type': 'FROZEN_MISMATCH',
                                'detail': (
                                    f"{side_key.upper()} frozen @ {f_strike}: "
                                    f"session={total_frozen_lots} vs exchange={f_ex_size} "
                                    f"— NOT auto-corrected (count comparison unreliable)"
                                ),
                                'symbol': fsym,
                                'session_lots': total_frozen_lots,
                                'exchange_size': f_ex_size,
                                'auto_corrected': False,
                            })
                            log.warning(
                                f"[{sid}] Recon FROZEN_MISMATCH {side_key.upper()} @ {f_strike}: "
                                f"session={total_frozen_lots} exchange={f_ex_size} — logged only."
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
                # doesn't know about at all (completely untracked).
                # BUG FIX: Scan ALL exchange positions matching this session's
                # expiry + option type, not just those in session_symbols.
                # Without this, orphaned positions created by a dead monitor
                # instance during an in-flight strike shift are invisible
                # (session_symbols only contains known strikes, so orphans
                # at unknown strikes are filtered out by the earlier guard).
                known_strikes = set()
                if active_strike > 0:
                    known_strikes.add(active_strike)
                known_strikes.update(frozen_by_strike.keys())
                for fill in side.get('adjustment_fills', []):
                    fs = fill.get('strike', 0)
                    if fs > 0:
                        known_strikes.add(fs)

                prefix = 'C-BTC-' if option_type == 'call' else 'P-BTC-'
                # expiry is ddmmyyyy but symbol suffix is ddmmyy
                from .mmm_initializer import expiry_to_symbol_suffix
                sym_expiry = expiry_to_symbol_suffix(expiry) if expiry else ''
                expiry_suffix = f'-{sym_expiry}' if sym_expiry else ''

                for pos in positions:
                    sym = pos.get('product', {}).get('symbol', '') or pos.get('symbol', '')
                    if not sym.startswith(prefix):
                        continue
                    if expiry_suffix and not sym.endswith(expiry_suffix):
                        continue
                    # Extract strike from symbol (e.g., C-BTC-68000-210226 → 68000)
                    try:
                        parts = sym.split('-')
                        ex_strike = float(parts[2])
                    except (IndexError, ValueError):
                        continue

                    ex_size = abs(float(pos.get('size', 0)))
                    if ex_size <= 0:
                        continue

                    if ex_strike not in known_strikes:
                        # Before flagging, check if other sessions own
                        # these lots — avoid cross-session position adoption.
                        other_lots = self._get_other_sessions_lots_at_symbol(sym)
                        unowned = ex_size - other_lots

                        if unowned <= 0:
                            continue  # fully owned by other sessions

                        # ── close_at_5 grace period ──────────────────────────────────────
                        # If this session just closed this position via close_at_5, the
                        # exchange positions API may still reflect the old lot count for
                        # 1-5 s after the fill is confirmed.  Skip the mismatch report
                        # for up to 3 reconciliation cycles (grace_beats) so we don't
                        # raise a spurious UNTRACKED_EXCHANGE_POSITION warning.
                        _pcv = session.get('_pending_close_verification', {})
                        if sym in _pcv:
                            _pcv[sym]['grace_beats'] = _pcv[sym].get('grace_beats', 1) - 1
                            log.debug(
                                f"[{sid}] Reconciliation grace: {sym} recently closed by "
                                f"close_at_5 — suppressing UNTRACKED mismatch "
                                f"({_pcv[sym]['grace_beats']} beats remaining)"
                            )
                            continue  # Do NOT add to discrepancies this beat
                        # ── end grace period ─────────────────────────────────────────────

                        # ── Known external position suppression ───────────────────────
                        # If this untracked position was already classified as external
                        # (manual trade / other algo) in a prior reconciliation cycle,
                        # suppress repeat warnings.  Re-alert only if the lot count
                        # changes (e.g., external trade partially closed or added to).
                        _ext_key = f"{side_key.upper()}@{int(ex_strike)}"
                        _known_ext = session.setdefault('_known_external_positions', {})
                        _last_size = _known_ext.get(_ext_key)
                        if _last_size is not None and _last_size == ex_size:
                            continue  # already known, size unchanged — suppress noise
                        # First detection or size changed — record and warn once.
                        # If size INCREASED (growing ghost positions), send Telegram so
                        # user is alerted even if sleeping. Stale monitors produce this
                        # pattern: untracked lot count grows every ~5min heartbeat.
                        _size_grew = (_last_size is not None and ex_size > _last_size)
                        _known_ext[_ext_key] = ex_size
                        if _size_grew or _last_size is None:
                            try:
                                from .mmm_telegram import alert_ghost_positions_growing as _tg_ghost
                                asyncio.ensure_future(_tg_ghost(
                                    sid, side_key.upper(), ex_strike, ex_size,
                                ))
                            except Exception as _ge:
                                log.warning(f"[{sid}] Ghost position Telegram failed: {_ge}")
                        # ── end known external suppression ────────────────────────────

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
                            'auto_corrected': False,
                        })

                        # WARNING ONLY: Log untracked positions but do NOT
                        # auto-adopt. Previous auto-adopt caused catastrophic
                        # bugs — adopting positions from other stopped sessions,
                        # manual trades, or other algos. A session must NEVER
                        # claim positions it didn't create.
                        log.warning(
                            f"[{sid}] UNTRACKED POSITION: {side_key.upper()} @ {ex_strike} "
                            f"({int(unowned)} lots on exchange, not in this session). "
                            f"NOT auto-adopting — may belong to another algo/session/manual trade."
                        )

            # §26.9b: Self-heal existing positions with entry_premium=0.
            # Orphan positions adopted before this fix may have entry_premium=0.
            # Look up the exchange entry_price and patch them.
            for side_key in ['ce', 'pe']:
                side = session.get(side_key, {})
                option_type = 'call' if side_key == 'ce' else 'put'
                for p in side.get('positions', []):
                    if p.get('status') != 'active':
                        continue
                    if (p.get('entry_premium') or 0) > 0:
                        continue
                    # Position has entry_premium=0 — try to fix from exchange
                    p_strike = p.get('strike', 0)
                    if p_strike <= 0:
                        continue
                    p_sym = self.initializer.build_symbol(
                        option_type, 'BTC', p_strike, expiry)
                    for epos in positions:
                        esym = epos.get('product', {}).get('symbol', '') or epos.get('symbol', '')
                        if esym == p_sym:
                            ex_ep = float(epos.get('entry_price', 0))
                            if ex_ep > 0:
                                p['entry_premium'] = ex_ep
                                p['premium'] = ex_ep
                                log.info(
                                    f"[{sid}] HEALED entry_premium: "
                                    f"{side_key.upper()} {p['id']} @ {p_strike} "
                                    f"→ {ex_ep}")
                            break

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

        Price source priority:
        1. WebSocket l1_orderbook mid = (best_bid + best_ask) / 2  — real-time ~500ms
        2. REST /v2/tickers mark_price — fallback when WS is cold/stale/disconnected

        REST is always fetched (for IV data used by the regime engine). The price
        from REST is only used when WS has no fresh quote for that side.

        IV note: l1_orderbook does not carry mark_vol/IV — REST remains the IV source.
        """
        try:
            ce_state = self.session.get('ce', {})
            pe_state = self.session.get('pe', {})
            ce_strike = ce_state.get('active_strike', 0)
            pe_strike = pe_state.get('active_strike', 0)

            if ce_strike == 0 or pe_strike == 0:
                return None, None

            expiry = self.session.get('params', {}).get('expiry', '')

            ce_symbol = self.initializer.build_symbol('call', 'BTC', ce_strike, expiry)
            pe_symbol = self.initializer.build_symbol('put', 'BTC', pe_strike, expiry)

            # --- 1. WebSocket mid prices (real-time, ~500ms, no network call) ---
            from webui.backend.services.delta_price_websocket import get_price_websocket
            ws = get_price_websocket()

            def _ws_mid(entry):
                if not entry:
                    return None
                bid = entry.get('best_bid', 0) or 0
                ask = entry.get('best_ask', 0) or 0
                # Require both sides — one-sided quotes are unreliable for trigger decisions
                if not (bid > 0 and ask > 0):
                    return None
                mid = (bid + ask) / 2.0
                if mid <= 0:
                    return None
                spread_pct = (ask - bid) / mid
                # Reject if spread > 50% of mid — indicates market maker gaming or
                # pulled liquidity (e.g. bid=$5, ask=$256 → mid=$130.5 is garbage).
                # Fall back to REST mark_price which is model-based and more stable.
                if spread_pct > 0.50:
                    log.debug(
                        f"[{self.session_id}] WS mid rejected: bid={bid} ask={ask} "
                        f"spread={spread_pct:.0%} > 50% — using REST mark"
                    )
                    return None
                return mid

            ce_ws_mid = _ws_mid(ws.get_option_price(ce_symbol, max_age_sec=3.0))
            pe_ws_mid = _ws_mid(ws.get_option_price(pe_symbol, max_age_sec=3.0))

            # --- 2. REST fetch — always runs for IV; price used only as fallback ---
            ce_rest = 0.0
            pe_rest = 0.0
            try:
                rest = self._create_heartbeat_rest_client()
                ce_resp, pe_resp = await asyncio.gather(
                    rest._request_with_retry(method="GET", path=f"/v2/tickers/{ce_symbol}"),
                    rest._request_with_retry(method="GET", path=f"/v2/tickers/{pe_symbol}"),
                )
                ce_data = ce_resp.get('result', ce_resp)
                pe_data = pe_resp.get('result', pe_resp)

                ce_rest = float(ce_data.get('mark_price', 0) or 0)
                pe_rest = float(pe_data.get('mark_price', 0) or 0)

                # IV for regime engine (REST-only — l1_orderbook doesn't carry mark_vol)
                try:
                    ce_iv_raw = ce_data.get('mark_vol') or ce_data.get('quotes', {}).get('mark_iv') or 0
                    ce_iv = float(ce_iv_raw) * 100
                except (ValueError, TypeError):
                    ce_iv = 0.0
                try:
                    pe_iv_raw = pe_data.get('mark_vol') or pe_data.get('quotes', {}).get('mark_iv') or 0
                    pe_iv = float(pe_iv_raw) * 100
                except (ValueError, TypeError):
                    pe_iv = 0.0
                self._last_iv_data = {'ce_iv': ce_iv, 'pe_iv': pe_iv}
                self._heartbeat_rest = rest

            except Exception as rest_err:
                log.warning(f"[{self.session_id}] REST ticker fetch failed: {rest_err} — WS prices only this beat")

            # --- 3. Merge: WS mid → REST mark → last-known-good ---
            # Waterfall ensures we NEVER return None once a valid price has been seen.
            ce_final = ce_ws_mid or ce_rest or 0.0
            pe_final = pe_ws_mid or pe_rest or 0.0

            ce_src = 'WS' if ce_ws_mid else ('REST' if ce_rest else None)
            pe_src = 'WS' if pe_ws_mid else ('REST' if pe_rest else None)

            # Update last-known-good when we have a live price
            _now = time.time()
            if ce_final > 0:
                self._last_good_ce = ce_final
                self._last_good_ce_at = _now
            if pe_final > 0:
                self._last_good_pe = pe_final
                self._last_good_pe_at = _now

            # Fall back to last-known-good if both live sources failed (with TTL)
            if ce_final <= 0 and self._last_good_ce is not None:
                if (_now - self._last_good_ce_at) < self._LAST_GOOD_TTL:
                    ce_final = self._last_good_ce
                    ce_src = 'CACHED'
                else:
                    log.warning(f"[{self.session_id}] CE last-known-good expired ({_now - self._last_good_ce_at:.0f}s old)")
                    ce_src = 'STALE'
            if pe_final <= 0 and self._last_good_pe is not None:
                if (_now - self._last_good_pe_at) < self._LAST_GOOD_TTL:
                    pe_final = self._last_good_pe
                    pe_src = 'CACHED'
                else:
                    log.warning(f"[{self.session_id}] PE last-known-good expired ({_now - self._last_good_pe_at:.0f}s old)")
                    pe_src = 'STALE'

            log.debug(
                f"[{self.session_id}] Price source — CE={ce_final:.2f}({ce_src}) "
                f"PE={pe_final:.2f}({pe_src})"
            )

            return ce_final if ce_final > 0 else None, pe_final if pe_final > 0 else None

        except Exception as e:
            log.error(f"[{self.session_id}] Error fetching premiums: {e}")
            # Last-known-good fallback even on exception — with TTL
            _now = time.time()
            ce_fallback = None
            pe_fallback = None
            if self._last_good_ce is not None and (_now - self._last_good_ce_at) < self._LAST_GOOD_TTL:
                ce_fallback = self._last_good_ce
            if self._last_good_pe is not None and (_now - self._last_good_pe_at) < self._LAST_GOOD_TTL:
                pe_fallback = self._last_good_pe
            if ce_fallback and pe_fallback:
                log.warning(f"[{self.session_id}] Exception fallback — last-known-good CE={ce_fallback:.2f} PE={pe_fallback:.2f}")
            else:
                log.error(f"[{self.session_id}] Exception fallback — no valid cached prices (expired or never set)")
            return ce_fallback, pe_fallback

    def _compute_data_confidence(self) -> float:
        """
        Feature 9: Compute a unified data confidence score (0.0–1.0) each heartbeat.

        Signals:
          - CE premium stale flag (-confidence_stale_penalty per side)
          - PE premium stale flag (-confidence_stale_penalty per side)
          - WS consecutive failure count (-confidence_ws_failure_penalty per failure)

        Result is clamped to [confidence_min_floor, 1.0] and stored on session
        as '_data_confidence'. Returns 1.0 if disabled or params unavailable.
        """
        try:
            session = self.session
            params = session.get('params', {})
            if not params.get('data_confidence_enabled', True):
                session['_data_confidence'] = 1.0
                return 1.0

            score = 1.0
            stale_penalty = params.get('confidence_stale_penalty', 0.25)
            ws_penalty    = params.get('confidence_ws_failure_penalty', 0.04)
            min_floor     = params.get('confidence_min_floor', 0.20)

            if session.get('_ce_premium_stale'):
                score -= stale_penalty
            if session.get('_pe_premium_stale'):
                score -= stale_penalty

            try:
                failures = get_ws_health().get('consecutive_failures', 0)
                score -= int(failures) * ws_penalty
            except Exception:
                pass

            confidence = max(min_floor, min(1.0, score))
            session['_data_confidence'] = confidence
            return confidence
        except Exception:
            return 1.0

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
                        f"{'N/A' if pe_final is None else f'{pe_final:.2f}'}"
                    )
                    session['_ce_premium_stale'] = True
                    ce_final = cached_ce

            if pe_final is None:
                cached_pe = cache.get((pe_strike, 'put'))
                if cached_pe:
                    log.warning(
                        f"[{sid}] Fix #12: PE premium fetch failed — using cached "
                        f"price {cached_pe:.2f} (stale). CE fresh: "
                        f"{'N/A' if ce_final is None else f'{ce_final:.2f}'}"
                    )
                    session['_pe_premium_stale'] = True
                    pe_final = cached_pe

            if ce_final is not None and pe_final is not None:
                # At least partial fresh data — record circuit as success for
                # the side that worked, but don't reset failure count fully.
                self._circuit.record_success()
                return ce_final, pe_final, True

            # Both live sources failed — use last-known-good as ultimate fallback (with TTL)
            _now = time.time()
            if ce_final is None and self._last_good_ce is not None:
                if (_now - self._last_good_ce_at) < self._LAST_GOOD_TTL:
                    ce_final = self._last_good_ce
                    session['_ce_premium_stale'] = True
                else:
                    log.warning(f"[{sid}] CE last-known-good expired ({_now - self._last_good_ce_at:.0f}s old)")
            if pe_final is None and self._last_good_pe is not None:
                if (_now - self._last_good_pe_at) < self._LAST_GOOD_TTL:
                    pe_final = self._last_good_pe
                    session['_pe_premium_stale'] = True
                else:
                    log.warning(f"[{sid}] PE last-known-good expired ({_now - self._last_good_pe_at:.0f}s old)")

            if ce_final is not None and pe_final is not None:
                log.warning(f"[{sid}] All live sources failed — using last-known-good CE={ce_final:.2f} PE={pe_final:.2f}")
                # ok=False: data is stale, heartbeat should skip trading decisions
                return ce_final, pe_final, False

            self._circuit.record_failure('all premium sources returned invalid data')
            return None, None, False

        except Exception as e:
            self._circuit.record_failure(str(e))
            log.error(f"[{sid}] Premium fetch exception: {e}")
            # Even on exception, try last-known-good
            if self._last_good_ce is not None and self._last_good_pe is not None:
                log.warning(f"[{sid}] Exception fallback — using last-known-good CE={self._last_good_ce:.2f} PE={self._last_good_pe:.2f}")
                return self._last_good_ce, self._last_good_pe, True
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
                        mid = (best_bid + best_ask) / 2.0
                        spread_pct = (best_ask - best_bid) / mid if mid > 0 else 1.0
                        if spread_pct > 0.50:
                            return None  # Wide spread — don't use this as fallback
                        return mid
                    # One-sided quotes are unreliable for trigger decisions
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

    # ── Proactive Close-at-5 Watcher ──────────────────────────────────────────
    # Runs independently of the main heartbeat on a shorter interval.
    # Detects when any position's bid drops to close_at_threshold and immediately
    # forces a heartbeat, making close-at-5 near-real-time instead of waiting
    # up to adjustment_interval seconds.

    def _start_close_watcher(self):
        """Start a background thread that proactively polls for close-at-5 conditions."""
        try:
            from eventlet.patcher import original as _ep_original
            _RealThread = _ep_original('threading').Thread
        except (ImportError, AttributeError):
            _RealThread = threading.Thread
        t = _RealThread(
            target=self._run_close_watcher,
            name=f"mmm-close-watcher-{self.session_id}",
            daemon=True,
        )
        t.start()
        log.warning(f"[{self.session_id}] Close-watcher started (interval={self.session.get('params', {}).get('close_at_watch_interval', 30)}s)")

    def _run_close_watcher(self):
        """
        Background close-at-5 watcher loop.

        Default: activates only within close_at_watch_hours_before_expiry hours of expiry (default 3h).
        Override: set close_at_watcher_force_enabled=True to run at any time.
        Near-expiry: uses close_at_watch_near_expiry_interval (default 10s) for faster response.
        Force-enabled: uses close_at_watch_interval (default 30s).
        Setting close_at_watch_interval=0 and close_at_watch_near_expiry_interval=0 disables watcher entirely.
        """
        while self._running and not self._stop_event.is_set():
            params = self.session.get('params', {})
            try:
                normal_interval = int(params.get('close_at_watch_interval', 30) or 30)
            except (TypeError, ValueError):
                normal_interval = 30
            try:
                near_expiry_interval = int(params.get('close_at_watch_near_expiry_interval', 10) or 10)
            except (TypeError, ValueError):
                near_expiry_interval = 10

            force_enabled = bool(params.get('close_at_watcher_force_enabled', False))
            try:
                hours_before = float(params.get('close_at_watch_hours_before_expiry', 3.0) or 3.0)
            except (TypeError, ValueError):
                hours_before = 3.0

            # Check if we're within the auto-activate window
            mins_to_exp = self._get_minutes_to_expiry()
            in_window = (
                hours_before > 0
                and mins_to_exp is not None
                and mins_to_exp <= hours_before * 60
            )

            if not force_enabled and not in_window:
                # Neither force-enabled nor in expiry window — sleep and recheck in 60s
                self._stop_event.wait(timeout=60)
                continue

            # Use faster interval when in expiry window
            interval = near_expiry_interval if in_window else normal_interval
            if interval <= 0:
                self._stop_event.wait(timeout=60)
                continue

            self._stop_event.wait(timeout=interval)
            if self._stop_event.is_set() or not self._running:
                break
            if self._heartbeat_in_progress:
                # Heartbeat is running now — it will call _process_close_at_5 anyway
                continue
            try:
                breached = asyncio.run(self._watcher_check_close_threshold())
                if breached:
                    mode = f"near-expiry {mins_to_exp:.0f}min left" if in_window else "force-enabled"
                    log.warning(
                        f"[{self.session_id}] Close-watcher [{mode}]: premium at/below threshold "
                        f"— forcing heartbeat"
                    )
                    self.force_heartbeat()
            except Exception as _we:
                log.warning(f"[{self.session_id}] Close-watcher check error (non-fatal): {_we}")
        log.warning(f"[{self.session_id}] Close-watcher stopped")

    # ── Real-time Price Ticker ─────────────────────────────────────────────────
    # Emits mmm_price_tick every PRICE_TICK_INTERVAL seconds using the cached
    # premiums — no extra exchange API calls.

    PRICE_TICK_INTERVAL = 5  # seconds

    def _start_price_ticker(self):
        """Start a background thread that emits price ticks every 5 seconds."""
        try:
            from eventlet.patcher import original as _ep_original
            _RealThread = _ep_original('threading').Thread
        except (ImportError, AttributeError):
            _RealThread = threading.Thread
        t = _RealThread(
            target=self._run_price_ticker,
            name=f"mmm-price-ticker-{self.session_id}",
            daemon=True,
        )
        t.start()
        log.info(f"[{self.session_id}] Price ticker started (interval={self.PRICE_TICK_INTERVAL}s)")

    def _run_price_ticker(self):
        """Emit mmm_price_tick every PRICE_TICK_INTERVAL seconds from cached prices."""
        while self._running and not self._stop_event.is_set():
            self._stop_event.wait(timeout=self.PRICE_TICK_INTERVAL)
            if self._stop_event.is_set() or not self._running:
                break
            try:
                cache = getattr(self, '_premium_cache', {}) or {}
                if not cache:
                    continue
                session = self.session
                premium_map = {}
                for (strike, opt_type), price in cache.items():
                    # Mirror the _emit_heartbeat_data None-check: don't emit
                    # failed-fetch sentinels (None) — they clobber valid prices
                    # already in the frontend's premium_map from the last full
                    # heartbeat, causing frozen position P&L to swing wildly.
                    if price is not None:
                        premium_map[f"{int(strike)}:{opt_type}"] = price
                # Ensure active strikes are always present
                ce_active = session.get('ce', {}).get('active_strike')
                pe_active = session.get('pe', {}).get('active_strike')
                ce_key = f"{int(ce_active)}:call" if ce_active else None
                pe_key = f"{int(pe_active)}:put" if pe_active else None
                if ce_key and ce_key not in premium_map:
                    stored = (session.get('_premium_map') or {}).get(ce_key)
                    if stored:
                        premium_map[ce_key] = stored
                if pe_key and pe_key not in premium_map:
                    stored = (session.get('_premium_map') or {}).get(pe_key)
                    if stored:
                        premium_map[pe_key] = stored
                if premium_map:
                    emit_price_tick(self.session_id, premium_map)
            except Exception as _e:
                log.debug(f"[{self.session_id}] Price ticker error (non-fatal): {_e}")
        log.info(f"[{self.session_id}] Price ticker stopped")

    async def _watcher_check_close_threshold(self) -> bool:
        """
        Fetch bid prices for all open positions.
        Returns True if ANY position is at or below close_at_threshold.
        """
        session = self.session
        params = session.get('params', {})
        threshold = params.get('close_at_threshold', 5.0)
        use_bid = params.get('close_at_use_bid', True)
        expiry = params.get('expiry', '')

        # Collect all open (strike, option_type) pairs — skip _being_closed
        strike_pairs: set = set()
        for side_key in ['ce', 'pe']:
            side = session.get(side_key, {})
            opt = 'call' if side_key == 'ce' else 'put'
            orig_lots = side.get('original_lots', 0)
            orig_strike = side.get('original_strike', side.get('active_strike', 0))
            if orig_lots > 0 and orig_strike:
                strike_pairs.add((float(orig_strike), opt))
            for fill in side.get('adjustment_fills', []):
                if fill.get('lots', 0) > 0 and fill.get('strike') and not fill.get('_being_closed'):
                    strike_pairs.add((float(fill['strike']), opt))
            for frozen in side.get('frozen_positions', []):
                if frozen.get('lots', 0) > 0 and frozen.get('strike') and not frozen.get('_being_closed'):
                    strike_pairs.add((float(frozen['strike']), opt))

        if not strike_pairs:
            return False

        rest = self._create_heartbeat_rest_client()

        async def _check_one(strike, opt):
            try:
                symbol = self.initializer.build_symbol(opt, 'BTC', strike, expiry)
                if use_bid:
                    ob_resp = await rest._request_with_retry(
                        method="GET", path=f"/v2/orderbook/{symbol}",
                        params={"depth": 1},
                    )
                    bids = ob_resp.get('result', ob_resp).get('buy', [])
                    if bids:
                        return float(bids[0][0]) <= threshold
                # Fallback: mark price from ticker
                tick = await rest._request_with_retry(
                    method="GET", path=f"/v2/tickers/{symbol}",
                )
                mark = float(tick.get('result', tick).get('mark_price', 0) or 0)
                return 0 < mark <= threshold
            except Exception:
                return False

        results = await asyncio.gather(*[_check_one(s, o) for s, o in strike_pairs])
        return any(results)

    # ── End Proactive Close-at-5 Watcher ──────────────────────────────────────

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

        # Keep ce_now/pe_now as fallbacks for active strikes (used below if fresh fetch fails).
        # Do NOT seed active strikes into cache before computing to_fetch — doing so would
        # exclude them from the fetch loop, which is the only place bid_cache is populated.
        # Bug: active strikes seeded into mark_cache but never into bid_cache → _make_bid_fetch_fn
        # fell back to mark price for active strikes even when close_at_use_bid=True.
        # When mark > threshold but bid < threshold, close_at_5 never fired.
        ce_state = session.get('ce', {})
        pe_state = session.get('pe', {})
        _active_fallbacks: Dict[tuple, float] = {}
        if ce_state.get('active_strike'):
            _active_fallbacks[(float(ce_state['active_strike']), 'call')] = ce_now
        if pe_state.get('active_strike'):
            _active_fallbacks[(float(pe_state['active_strike']), 'put')] = pe_now

        # Fetch ALL strikes — including active strikes — so bid prices are populated for them.
        # Active strikes were previously excluded (pre-seeded into cache), leaving bid_cache
        # empty for them. Now they go through _fetch_one like any other strike.
        rest = getattr(self, '_heartbeat_rest', None) or self._create_heartbeat_rest_client()
        to_fetch = list(strike_pairs)

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
                    # AUDIT FIX: return None (not 0) so failed fetches are NOT stored in
                    # cache. Storing 0 bypasses the None-check in compute_unrealized_pnl,
                    # making every failed-fetch position look fully decayed (max profit),
                    # which inflates unrealized P&L. None → cache miss → fetch error →
                    # position excluded from P&L (conservative, correct behaviour).
                    return (strike, opt), None, None

            results = await asyncio.gather(
                *[_fetch_one(s, o) for s, o in to_fetch],
                return_exceptions=True,
            )

            for r in results:
                if isinstance(r, Exception):
                    continue
                key, mark_price, bid_price = r
                # AUDIT FIX: only cache when prefetch succeeded (mark_price is not None).
                # Failed prefetches return None; storing them as 0 would make those
                # positions appear worthless and inflate unrealized P&L.
                if mark_price is not None and mark_price > 0:
                    cache[key] = mark_price
                    # Store bid price: use bid if available, else fall back to mark
                    bid_cache[key] = bid_price if bid_price and bid_price > 0 else mark_price

        # Fallback: if fetch failed for an active strike, seed mark price from ce_now/pe_now
        # so _make_fetch_fn still has a value for trigger / engine calculations.
        # bid_cache is intentionally NOT seeded with mark price — a missing bid entry
        # causes _make_bid_fetch_fn to fall back to mark_cache, which is correct behaviour
        # (mark > threshold → don't close, even if bid fetch failed).
        for key, fallback_mark in _active_fallbacks.items():
            if key not in cache:
                cache[key] = fallback_mark

        self._premium_cache = cache
        # AUDIT FIX: Replace bid_cache fresh each beat to prevent stale entries
        self._bid_cache = bid_cache

    async def _auto_promote_atm_strike(self) -> None:
        """
        Step 0.75: Auto-promote the open strike closest to ATM as the active strike.

        For PE (puts): the highest OTM strike (closest to spot from below) carries the
        most gamma risk and should be actively monitored.
        For CE (calls): the lowest OTM strike (closest to spot from above) carries the
        most gamma risk and should be actively monitored.

        Skipped when:
        - Session is not RUNNING or PAUSED
        - Wind-down is active
        - User has explicitly pinned the active strike (active_strike_pinned=True)
        - Only one open strike exists for that side
        """
        session = self.session
        sid = self.session_id

        status = session.get('strategy_status', 'IDLE').upper()
        if status not in ('RUNNING', 'PAUSED'):
            return

        if session.get('_wind_down_active') or session.get('_atm_wind_down_triggered'):
            return

        spot_price = await self._fetch_spot_price()
        if spot_price <= 0:
            return

        from .mmm_constants import strike_key as _sk
        from .mmm_state import recompute_side_lots
        from .mmm_activity import log_activity

        changed = False
        for side in ('ce', 'pe'):
            side_state = session.get(side, {})
            if not side_state:
                continue

            current_active = side_state.get('active_strike', 0)
            positions = side_state.get('positions', [])

            # Collect all open strikes (active + shifted) with lots > 0
            open_strikes = {}  # strike → lots
            for pos in positions:
                if pos.get('status') in ('active', 'shifted') and pos.get('lots', 0) > 0:
                    s = float(pos.get('strike', 0))
                    if s > 0:
                        open_strikes[s] = open_strikes.get(s, 0) + pos.get('lots', 0)

            # Recovery path: if active_lots=0 but frozen positions exist, promote the
            # highest-lots strike as the new active — regardless of open-strike count
            # AND regardless of whether the user has pinned the strike (active_strike_pinned).
            # The pin is respected only while there are live lots at the pinned strike.
            # When close-at-5 drains the last active lot, the pin is stale and must be
            # cleared so the trigger system regains a valid baseline. Without this, the
            # pinned-but-empty strike keeps the auto-promote skipped every beat, and the
            # trigger heal sets the baseline to current price → algo goes blind.
            if side_state.get('active_lots', 0) == 0 and open_strikes:
                best_strike = max(open_strikes, key=open_strikes.get)
                for pos in positions:
                    pos_strike = float(pos.get('strike', 0))
                    if pos.get('status') == 'shifted' and abs(pos_strike - best_strike) < 1:
                        pos['status'] = 'active'
                        pos['shifted_at'] = None
                side_state['active_strike'] = best_strike
                side_state['active_strike_pinned'] = False  # stale pin cleared
                recompute_side_lots(side_state)
                session[side] = side_state
                changed = True
                log.info(
                    f"[{sid}] ZERO-LOTS RECOVERY: {side.upper()} active strike "
                    f"{int(current_active)} → {int(best_strike)} "
                    f"(active_lots was 0, {open_strikes[best_strike]} frozen lots promoted)"
                )
                log_activity(
                    'auto_atm_promote',
                    f'📌 Zero-lots recovery: {side.upper()} active strike '
                    f'{int(current_active)} → {int(best_strike)} '
                    f'({open_strikes[best_strike]} frozen lots restored as active)',
                    sid, 'info',
                    {'side': side.upper(), 'old_strike': current_active,
                     'new_strike': best_strike, 'reason': 'active_lots_zero'},
                )
                try:
                    from .mmm_websocket import emit_to_session
                    emit_to_session(sid, 'mmm_active_strike_changed', {
                        'session_id': sid,
                        'side': side.upper(),
                        'old_strike': current_active,
                        'new_strike': best_strike,
                        'reason': 'active_lots_zero',
                    })
                except Exception:
                    pass
                continue  # Don't fall through to normal ATM-proximity logic

            # Skip normal ATM-proximity promotion if user pinned the strike.
            # (Zero-lots recovery above already ran and cleared the pin when needed.)
            if side_state.get('active_strike_pinned'):
                continue

            if len(open_strikes) <= 1:
                continue  # Only one open strike, nothing to promote

            # Find the OTM strike closest to ATM
            best_strike = None
            best_dist = float('inf')
            for s in open_strikes:
                if side == 'pe' and s >= spot_price:
                    continue  # Must be below spot for OTM put
                if side == 'ce' and s <= spot_price:
                    continue  # Must be above spot for OTM call
                dist = abs(spot_price - s)
                if dist < best_dist:
                    best_dist = dist
                    best_strike = s

            if best_strike is None or abs(best_strike - current_active) < 1:
                continue  # Already monitoring the closest-to-ATM strike

            # Promote best_strike: un-shift its positions, set as active, recompute
            for pos in positions:
                pos_strike = float(pos.get('strike', 0))
                if pos.get('status') == 'shifted' and abs(pos_strike - best_strike) < 1:
                    pos['status'] = 'active'
                    pos['shifted_at'] = None
            side_state['active_strike'] = best_strike
            recompute_side_lots(side_state)
            session[side] = side_state
            changed = True

            log.info(
                f"[{sid}] AUTO-ATM: {side.upper()} active strike "
                f"{int(current_active)} → {int(best_strike)} "
                f"(spot=${spot_price:.0f}, dist=${best_dist:.0f})"
            )
            log_activity(
                'auto_atm_promote',
                f'📌 Auto-ATM: {side.upper()} active strike '
                f'{int(current_active)} → {int(best_strike)} '
                f'(spot ${spot_price:.0f}, OTM dist ${best_dist:.0f})',
                sid, 'info',
                {'side': side.upper(), 'old_strike': current_active,
                 'new_strike': best_strike, 'spot': spot_price},
            )
            try:
                from .mmm_websocket import emit_to_session
                emit_to_session(sid, 'mmm_active_strike_changed', {
                    'session_id': sid,
                    'side': side.upper(),
                    'old_strike': current_active,
                    'new_strike': best_strike,
                    'reason': 'auto_atm',
                })
            except Exception:
                pass

        if changed:
            self._save_my_session(session)

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
            # Cannot create a new event loop here — we're already inside
            # self._loop.run_until_complete(_heartbeat()), so any
            # loop.run_until_complete() call will fail with "Cannot run the
            # event loop while another loop is running". The next heartbeat's
            # prefetch will populate this key.
            log.warning(
                f"Premium cache miss for {option_type}@{strike}. "
                f"This should not happen — check _prefetch_all_premiums coverage."
            )
            # AUDIT FIX: Return None instead of 0. Returning 0 makes every
            # position look maximally profitable and hides losses. Callers
            # must handle None (engine treats it as fetch failure).
            cache[key] = None
            return None
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
            # If neither cache has it, return None so scan_closeable_positions skips it.
            # (Matches _make_fetch_fn audit fix — returning 0 would make 0 <= threshold
            #  appear eligible and trigger a spurious market buyback at wrong price.)
            log.warning(f"Bid cache miss for {option_type}@{strike}, skipping close check")
            return None
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
            minutes_to_expiry = max((exp - now).total_seconds() / 60, 0)

            # Short Window: if session_deadline_utc is set, use the earlier deadline
            deadline_str = self.session.get('session_deadline_utc')
            if deadline_str:
                try:
                    deadline_dt = datetime.fromisoformat(deadline_str)
                    if deadline_dt.tzinfo is None:
                        deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
                    minutes_to_deadline = max((deadline_dt - now).total_seconds() / 60, 0)
                    return min(minutes_to_expiry, minutes_to_deadline)
                except (ValueError, TypeError):
                    pass

            return minutes_to_expiry
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

        Also populates self._last_gamma_data via compute_gamma_data() from mmm_gamma.

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
            from .mmm_gamma import build_position_map, compute_gamma_data, GammaData, _safe_greek
            import asyncio

            initializer = get_initializer()

            # Build position map from session state (extracted to mmm_gamma)
            position_map = build_position_map(session)

            if not position_map:
                self._last_gamma_data = GammaData(portfolio_gamma=0.0, positions=[])
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

            # Compute raw gamma data via mmm_gamma (single canonical location for opt_char mapping).
            # Dollar gamma values are computed later by _update_gamma_cap which has spot_price.
            gamma_data = compute_gamma_data(ticker_results, position_map)
            self._last_gamma_data = gamma_data

            # Calculate portfolio delta from ticker results
            portfolio_delta = 0.0

            _greek_zero_positions = 0
            for (strike, opt), resp in ticker_results:
                if isinstance(resp, Exception):
                    log.warning(
                        f"[{self.session_id}] Greeks fetch FAILED for "
                        f"{opt} @ {strike}: {resp}"
                    )
                    continue

                result = resp.get('result', resp) if isinstance(resp, dict) else {}
                if isinstance(result, list):
                    result = result[0] if result else {}
                greeks = result.get('greeks', {}) or {}
                greek_delta = _safe_greek(greeks.get('delta', 0))

                lots = int(position_map.get((strike, opt), 0))

                # Diagnostic: warn when exchange returns no greeks for a live position
                if lots > 0 and greek_delta == 0.0:
                    _greek_zero_positions += 1
                    log.warning(
                        f"[{self.session_id}] GREEKS MISSING: {opt} @ {strike} "
                        f"({lots} lots) — exchange returned delta=0. "
                        f"Portfolio delta will be understated. "
                        f"greeks={greeks!r}"
                    )

                # multiplier: ALWAYS -1 for short positions (we are the seller)
                # Fix #26.1: short CE delta = -(+call_delta), short PE delta = -(-put_delta) = +
                # Old bug: put multiplier was +1, which preserved the negative put delta
                # instead of flipping it. This made portfolio_delta too negative,
                # causing the perp to BUY (go long) when it should have SOLD (gone short).
                multiplier = -1  # short position always negates the exchange delta
                position_delta = greek_delta * lots * LOT_SIZE_BTC * multiplier
                portfolio_delta += position_delta
                log.debug(
                    f"[{self.session_id}] Greek: {opt} @ {int(strike)} | "
                    f"lots={lots} δ={greek_delta:+.4f} → pos_δ={position_delta:+.6f} BTC"
                )

            total_pos = len(position_map)
            if _greek_zero_positions > 0:
                log.warning(
                    f"[{self.session_id}] GREEKS SUMMARY: {_greek_zero_positions}/{total_pos} "
                    f"positions returned delta=0 — portfolio_delta={portfolio_delta:+.6f} BTC "
                    f"may be understated. Check exchange ticker availability."
                )
            else:
                log.info(
                    f"[{self.session_id}] GREEKS OK: {total_pos} positions, "
                    f"portfolio_delta={portfolio_delta:+.6f} BTC, "
                    f"portfolio_gamma={gamma_data['portfolio_gamma']:+.6f}"
                )

            return portfolio_delta

        except Exception as e:
            log.exception(f"Unexpected error in _calculate_portfolio_delta: {e}")
            self.session['_gamma_data_incomplete'] = True
            return 0.0

    def _emit_heartbeat_data(self, ce_now: float, pe_now: float):
        """Emit heartbeat WebSocket event with premium_map for live prices."""
        # Guarantee non-None, non-zero prices using last-known-good fallback (with TTL).
        # Without this, the trigger gauge shows 0.0/0.0 when a side has no
        # fresh price (e.g. CE with 0 active lots but 66 frozen).
        _now = time.time()
        if not ce_now and self._last_good_ce is not None and (_now - self._last_good_ce_at) < self._LAST_GOOD_TTL:
            ce_now = self._last_good_ce
        if not pe_now and self._last_good_pe is not None and (_now - self._last_good_pe_at) < self._LAST_GOOD_TTL:
            pe_now = self._last_good_pe

        session = self.session
        ce_trigger = session.get('ce', {}).get('trigger_snapshot', {}).get(
            _strike_key(session.get('ce', {}).get('active_strike', 0)), 0
        )
        pe_trigger = session.get('pe', {}).get('trigger_snapshot', {}).get(
            _strike_key(session.get('pe', {}).get('active_strike', 0)), 0
        )

        realized = session.get('realized_pnl', 0)
        unrealized = session.get('unrealized_pnl', 0)
        fees = session.get('total_fees', 0)

        # Build premium_map from _premium_cache for frontend position pricing
        # Format: {"70600:call": 95.5, "66400:put": 107.5, ...}
        # AUDIT FIX: skip None entries (cache miss sentinels from _make_fetch_fn) so
        # the frontend never receives null/0 as a "known" price for a position.
        premium_map = {}
        cache = getattr(self, '_premium_cache', {})
        for (strike, opt_type), price in cache.items():
            if price is not None:
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
            realized + unrealized - fees, realized,
            premium_map=premium_map,
            adaptive_tier=session.get('_adaptive_tier', ''),
            wind_down_active=is_wind_down_active(session),
            portfolio_delta=portfolio_delta,
            margin_data=getattr(self, '_last_margin_snapshot', None),
            regime_data=regime_data,
            perp_hedge_data=get_perp_summary(session),
            effective_interval=getattr(self, '_effective_interval', session.get('params', {}).get('adjustment_interval', 300)),
            next_heartbeat=session.get('next_heartbeat', ''),
            breakeven_data=session.get('_breakeven_result'),
            gamma_data=session.get('_gamma_result'),
            data_confidence=session.get('_data_confidence'),
            awaiting_user_action=session.get('_awaiting_user_action', False),
            awaiting_user_action_details=session.get('_awaiting_user_action_details'),
            reverse_data=session.get('_reverse') if session.get('_reverse', {}).get('active') else None,
        )

        # Also emit as standalone breakeven event for subscribers
        be_result = session.get('_breakeven_result')
        if be_result:
            try:
                emit_breakeven(self.session_id, be_result)
            except Exception:
                pass

        # Also emit as standalone gamma event for subscribers
        gd_result = session.get('_gamma_result')
        if gd_result:
            try:
                emit_gamma(self.session_id, gd_result)
            except Exception:
                pass


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
        # ROOT-CAUSE FIX: Wait for the old thread to actually finish before
        # starting the new one. Without this, the old thread can still be
        # mid-heartbeat when the new monitor starts. The new monitor increments
        # _monitor_generation, but the old thread reloads the session each cycle
        # (clearing _save_disabled) — so it keeps trading and placing phantom
        # orders whose saves are blocked. Joining here guarantees the old thread
        # is dead before the new monitor's first heartbeat.
        # Timeout=15s: a heartbeat in-flight takes at most ~60-120s for order fill,
        # but stop() sets _stop_event which interrupts the wait loop within 1 cycle.
        # If the thread is stuck beyond 15s, proceed anyway — the generation guard
        # (primary + secondary) is the final backstop.
        thread = existing._thread
        if thread is not None and thread.is_alive():
            log.warning(
                f"[{session_id}] Waiting for old monitor thread to exit "
                f"(gen={existing._my_generation})..."
            )
            thread.join(timeout=15)
            if thread.is_alive():
                log.error(
                    f"[{session_id}] Old monitor thread did NOT exit within 15s "
                    f"(gen={existing._my_generation}). Generation guard is the backstop."
                )
            else:
                log.info(f"[{session_id}] Old monitor thread exited cleanly.")

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


def compute_live_pnl(session_id: str) -> Optional[Dict[str, float]]:
    """Compute authoritative P&L for a running session from cached prices.

    This is the SINGLE SOURCE OF TRUTH for unrealized P&L on running sessions.
    The stored session['unrealized_pnl'] is a cache that can be stale between
    heartbeats; this function always computes fresh from positions + the
    monitor's latest cached prices.

    Staleness fix: for active-strike positions, queries the WS price service
    directly (max_age_sec=10s) to get fresher quotes than the heartbeat cache.
    Falls back to heartbeat cache for non-WS-covered strikes.

    Returns:
        {realized, unrealized, fees, net_pnl} or None if monitor not running
        or prices unavailable.
    """
    with _monitors_lock:
        monitor = _monitors.get(session_id)
    if not monitor or not monitor._running:
        return None
    try:
        # Thread safety: take a snapshot under the session lock to avoid
        # torn reads from concurrent heartbeat mutations.
        import copy
        with monitor._session_lock:
            session_snap = copy.deepcopy(monitor.session)

        # Build a fresh-first fetch function: try WS for a live quote,
        # fall back to heartbeat cache. This prevents stale P&L between heartbeats.
        cache = dict(getattr(monitor, '_premium_cache', {}))
        try:
            from webui.backend.services.delta_price_websocket import get_price_websocket
            ws = get_price_websocket()
            expiry = session_snap.get('params', {}).get('expiry', '')
            initializer = monitor.initializer

            def _ws_mid(entry):
                if not entry:
                    return None
                bid = entry.get('best_bid', 0) or 0
                ask = entry.get('best_ask', 0) or 0
                if not (bid > 0 and ask > 0):
                    return None
                mid = (bid + ask) / 2.0
                if mid <= 0 or (ask - bid) / mid > 0.50:
                    return None
                return mid

            def fetch_live(strike, option_type):
                key = (float(strike), option_type)
                otype = 'call' if option_type == 'call' else 'put'
                try:
                    symbol = initializer.build_symbol(otype, 'BTC', float(strike), expiry)
                    live = _ws_mid(ws.get_option_price(symbol, max_age_sec=10.0))
                    if live is not None:
                        return live
                except Exception:
                    pass
                return cache.get(key)

        except Exception:
            # WS not available — fall back to heartbeat cache only
            def fetch_live(strike, option_type):
                return cache.get((float(strike), option_type))

        from .mmm_pnl_core import get_pnl as _pnl_get
        return _pnl_get(session_snap, fetch_live)
    except Exception:
        return None


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
        return False
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
                        return False  # Signal to caller that save was rejected
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

                # API-inject race fix: re-apply positions written by inject-position or
                # set-active-strike APIs that arrived while this heartbeat was in-flight.
                # The monitor only tracks positions it knows about (loaded at heartbeat start);
                # any position added via API after that reload is invisible to this save and
                # would be silently overwritten. Fix: find positions in storage (by ID) that
                # are not in the monitor's in-memory copy and merge them back in.
                for _side in ('ce', 'pe'):
                    _stored_side = stored.get(_side, {})
                    _mem_side = session.get(_side)
                    if not _mem_side or not isinstance(_stored_side.get('positions'), list):
                        continue
                    _mem_ids = {p['id'] for p in _mem_side.get('positions', []) if 'id' in p}
                    _new_pos = [
                        p for p in _stored_side['positions']
                        if 'id' in p and p['id'] not in _mem_ids
                    ]
                    if _new_pos:
                        log.info(
                            f"[{sid}] _save_session: merging {len(_new_pos)} API-injected "
                            f"{_side.upper()} position(s) from storage: "
                            f"{[p['id'] for p in _new_pos]}"
                        )
                        _mem_side.setdefault('positions', []).extend(_new_pos)
                        # Also preserve the higher _pos_counter from storage so future
                        # IDs don't collide with the injected positions.
                        _stored_counter = _stored_side.get('_pos_counter', 0)
                        if _stored_counter > _mem_side.get('_pos_counter', 0):
                            _mem_side['_pos_counter'] = _stored_counter
                        recompute_side_lots(_mem_side)
                        session[_side] = _mem_side
                    # Preserve active_strike + position status changes from
                    # set-active-strike API that arrived while this heartbeat was
                    # in-flight. The new-positions merge above handles injected
                    # positions (by ID); this handles active_strike field and
                    # position status (shifted→active) changes from set_active_strike.
                    # Guard: only fires when stored has active_strike_pinned=True
                    # (explicit API call) but the heartbeat's in-memory copy doesn't.
                    if (_stored_side.get('active_strike_pinned')
                            and not _mem_side.get('active_strike_pinned', False)):
                        _api_active = float(_stored_side.get('active_strike') or 0)
                        _mem_active = float(_mem_side.get('active_strike') or 0)
                        if _api_active > 0 and abs(_api_active - _mem_active) >= 1:
                            _sp_map = {
                                p['id']: p
                                for p in _stored_side.get('positions', [])
                                if 'id' in p
                            }
                            for _pos in _mem_side.get('positions', []):
                                _pid = _pos.get('id')
                                if _pid in _sp_map:
                                    _pos['status'] = _sp_map[_pid].get(
                                        'status', _pos['status'])
                                    _pos['shifted_at'] = _sp_map[_pid].get('shifted_at')
                            _mem_side['active_strike'] = _api_active
                            _mem_side['active_strike_pinned'] = True
                            recompute_side_lots(_mem_side)
                            session[_side] = _mem_side
                            log.info(
                                f"[{sid}] _save_session: preserved API active_strike "
                                f"{_side.upper()} {int(_mem_active)} → {int(_api_active)} "
                                f"(set-active-strike during in-flight heartbeat)"
                            )
        storage.save_session(session)
        return True
    except Exception as e:
        log.error(f"Failed to save session: {e}")
        return False
