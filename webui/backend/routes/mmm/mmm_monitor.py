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
    get_safety, should_block_adjustment, should_pause,
    update_peak_pnl,
)
from .mmm_pending_orders import (
    register_pending, clear_pending, get_pending,
    check_and_resolve_pending, clear_all as clear_all_pending,
)
from .mmm_websocket import (
    emit_heartbeat, emit_adjustment, emit_reversal,
    emit_strike_shift, emit_close_at_5, emit_both_sides_alert,
    emit_safety, emit_pnl_update, emit_status_change,
)
from .mmm_storage import get_storage
from .mmm_constants import LOT_SIZE_BTC

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
        self._session_lock = threading.Lock()

        self._engine = get_engine()
        self._safety = get_safety()

        # Institutional heartbeat infrastructure
        base_interval = session.get('params', {}).get('adjustment_interval', 300)
        self._health = HeartbeatHealth(session_id, base_interval)
        self._circuit = CircuitBreaker(session_id)

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
        self._paused = False
        self._stop_event.clear()

        self.session['strategy_status'] = 'RUNNING'
        self.session['entry_time'] = (
            self.session.get('entry_time') or datetime.utcnow().isoformat()
        )
        self.session['updated_at'] = datetime.utcnow().isoformat()

        # Analytics: Track session start time
        analytics = self.session.setdefault('analytics', {})
        if not analytics.get('session_start_time'):
            analytics['session_start_time'] = datetime.utcnow().isoformat()
            # Capture initial lots from session
            analytics['initial_ce_lots'] = self.session.get('ce', {}).get('original_lots', 0)
            analytics['initial_pe_lots'] = self.session.get('pe', {}).get('original_lots', 0)
            # Initialize cumulative traded volume with initial position
            analytics['total_ce_lots_traded'] = analytics['initial_ce_lots']
            analytics['total_pe_lots_traded'] = analytics['initial_pe_lots']
            analytics['total_combined_lots_traded'] = analytics['initial_ce_lots'] + analytics['initial_pe_lots']

        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"mmm-monitor-{self.session_id}",
            daemon=True,
        )
        self._thread.start()

        emit_status_change(
            self.session_id, 'IDLE', 'RUNNING', 'Monitor started'
        )
        log.info(f"Monitor started for {self.session_id}")

        # Register with watchdog supervisor
        try:
            from .mmm_watchdog import MMMWatchdog
            MMMWatchdog.get_instance().register(self)
        except Exception as _we:
            log.warning(f"Watchdog registration failed: {_we}")

    def stop(self, reason: str = 'User requested'):
        """Stop the heartbeat monitor."""
        if not self._running:
            return

        old_status = self.session.get('strategy_status', 'RUNNING')
        self._running = False
        self._stop_event.set()
        self.session['strategy_status'] = 'STOPPED'
        self.session['updated_at'] = datetime.utcnow().isoformat()

        # Analytics: Track session end time and duration
        analytics = self.session.setdefault('analytics', {})
        analytics['session_end_time'] = datetime.utcnow().isoformat()
        start_time = analytics.get('session_start_time')
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.utcnow()
                analytics['session_duration_seconds'] = (end_dt - start_dt).total_seconds()
            except (ValueError, TypeError):
                pass

        _save_session(self.session)
        
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
        log.info(f"Monitor stopped for {self.session_id}: {reason}")

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

    def pause(self, reason: str = 'User requested'):
        """Pause the heartbeat (monitoring continues but no adjustments)."""
        old_status = self.session.get('strategy_status', 'RUNNING')
        self._paused = True
        self.session['strategy_status'] = 'PAUSED'
        self.session['updated_at'] = datetime.utcnow().isoformat()

        _save_session(self.session)

        emit_status_change(
            self.session_id, old_status, 'PAUSED', reason
        )
        log.info(f"Monitor paused for {self.session_id}: {reason}")

    def resume(self, reason: str = 'User requested'):
        """Resume from paused state."""
        old_status = self.session.get('strategy_status', 'PAUSED')
        self._paused = False
        self.session['strategy_status'] = 'RUNNING'
        self.session['updated_at'] = datetime.utcnow().isoformat()

        _save_session(self.session)

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
                from .mmm_activity import log_activity
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
                fresh_session = storage.get_session(self.session_id)
                if fresh_session:
                    old_params = self.session.get('params', {})
                    new_params = fresh_session.get('params', {})
                    
                    self.session = fresh_session
                    
                    # Log ALL hot-reloaded parameter changes
                    for pkey in new_params:
                        old_val = old_params.get(pkey)
                        new_val = new_params.get(pkey)
                        if old_val is not None and old_val != new_val:
                            from .mmm_activity import log_activity
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

                # Store effective interval so _heartbeat() can log it
                self._effective_interval = interval

                # Record next heartbeat time
                self.session['next_heartbeat'] = (
                    datetime.utcnow() + timedelta(seconds=interval)
                ).isoformat()

                hb_start = time.monotonic()
                try:
                    self._loop.run_until_complete(self._heartbeat())
                except Exception as e:
                    log.exception(f"Heartbeat error for {self.session_id}: {e}")
                    self.session['last_error'] = str(e)

                    # Circuit breaker: record failure (not a blunt stop)
                    self._circuit.record_failure(str(e))

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
            _save_session(self.session)
        finally:
            self._loop.close()
            self._loop = None

    # =========================================================================
    # §4: Single Heartbeat
    # =========================================================================

    async def _heartbeat(self):
        """Execute one heartbeat cycle."""
        session = self.session
        sid = self.session_id

        session['last_heartbeat'] = datetime.utcnow().isoformat()
        # NOTE: error_count is reset at the END of a successful heartbeat,
        # not here at the start. This ensures consecutive errors accumulate.

        # Log heartbeat start
        from .mmm_activity import log_activity
        log_activity('heartbeat_start',
                    f'Heartbeat #{session.get("_heartbeat_counter", 0) + 1}: Checking market conditions',
                    sid, 'info')
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
        await self._reconcile_exchange_positions()

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
                self._safety.run_all_checks(session, minutes_to_expiry)
                _save_session(session)
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
            return

        # Log premium values
        ce_strike = session.get('ce', {}).get('active_strike', 'N/A')
        pe_strike = session.get('pe', {}).get('active_strike', 'N/A')
        log_activity('info',
                    f'Current Premiums: CE {ce_strike} = ${ce_now:.2f}, PE {pe_strike} = ${pe_now:.2f}',
                    sid, 'info',
                    {'ce_premium': ce_now, 'pe_premium': pe_now, 'ce_strike': ce_strike, 'pe_strike': pe_strike})

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

        # Log wind-down status every heartbeat so user can see if it's active or pending
        wd_status = get_wind_down_status(session)
        if wd_status['enabled']:
            if wd_status['active']:
                log_activity('wind_down',
                             f'🌙 Wind-Down MODE ACTIVE — reducing positions '
                             f'({wd_status.get("hours_remaining", "?"):.1f}h to expiry)',
                             sid, 'info', wd_status)
            else:
                activates_in = wd_status.get('activates_in_hours')
                if activates_in is not None:
                    log_activity('wind_down',
                                 f'🌙 Wind-Down PENDING — activates in {activates_in:.1f}h '
                                 f'({wd_status.get("hours_before_expiry")}h before expiry threshold)',
                                 sid, 'info', wd_status)

        # Populate premium cache for sync engine calls (_make_fetch_fn)
        await self._prefetch_all_premiums(ce_now, pe_now)

        # ATM Auto-Close Check: if enabled, close all when spot ≈ ORIGINAL strike
        # CRITICAL: Must use original_strike (entry strike), NOT active_strike.
        # active_strike changes on shifts/reversals — using it would falsely
        # trigger when the algo has shifted closer to spot (normal operation).
        # The purpose of close_at_atm is to protect when spot reaches the
        # ORIGINAL entry strike — real danger territory.
        params = session.get('params', {})
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
                            f'original strike ${triggered_strike:.0f}'
                        )
                        return

        # Step 2: Close-at-5 scan (§11)
        await self._process_close_at_5(ce_now, pe_now)

        # Check if both sides fully closed
        if check_both_sides_closed(session):
            self.stop('Both sides fully closed — strategy complete!')
            return

        # Step 2b: Proactive wind-down buyback — every heartbeat while wind-down is active
        # (independent of trigger evaluation — reduces positions even when no trigger fires)
        if is_wind_down_active(session):
            await self._process_proactive_wind_down(ce_now, pe_now)
            # Re-check if both sides fully closed after proactive reduction
            if check_both_sides_closed(session):
                self.stop('Both sides fully closed via wind-down — strategy complete!')
                return

        # Bug #7 fix: compute FRESH unrealized P&L before safety checks
        # so that check_max_loss uses current prices, not stale values.
        fresh_unrealized = self._engine.compute_unrealized_pnl(
            session, self._make_fetch_fn()
        )
        session['unrealized_pnl'] = fresh_unrealized

        # Step 3: Safety checks (§13-14)
        minutes_to_expiry = self._get_minutes_to_expiry()
        safety_events = self._safety.run_all_checks(
            session, minutes_to_expiry
        )

        # Log safety check summary
        if safety_events:
            safety_summary = ', '.join([f"{e['type']} ({e['level']})" for e in safety_events])
            log_activity('safety_warning',
                        f'Safety Checks: {len(safety_events)} event(s) - {safety_summary}',
                        sid, 'warning',
                        {'event_count': len(safety_events), 'events': [e['type'] for e in safety_events]})
        else:
            log_activity('info',
                        'Safety Checks: All clear ✓',
                        sid, 'success')

        for event in safety_events:
            emit_safety(
                sid, event['type'], event['level'], event['message'],
                event.get('details')
            )

        # Track safety events for walkthrough
        self._hb_wt['safety_events'] = safety_events

        # Handle safety actions
        block, reason = should_block_adjustment(safety_events)
        if block:
            if 'auto_close' in reason.lower():
                await self._auto_close_all(reason)
            else:
                self.stop(reason)
            return

        pause_needed, pause_reason = should_pause(safety_events)
        if pause_needed:
            log_activity('session_paused',
                        f'Auto-paused by safety: {pause_reason}',
                        sid, 'warning',
                        {'reason': pause_reason, 'whipsaw_limit': session.get('params', {}).get('whipsaw_limit', 3)})
            self.pause(pause_reason)

        # Bug #15 fix: handle whipsaw auto-resume events
        for event in safety_events:
            if event.get('action') == 'resume' and self._paused:
                log_activity('session_resumed',
                            f'Auto-resumed: {event.get("message", "")}',
                            sid, 'success')
                self.resume(event.get('message', 'Whipsaw auto-resume'))

        # Step 4: If paused, check for both-sides-up auto-decision (30s timeout)
        if self._paused:
            status = session.get('strategy_status', '')
            if status == 'BOTH_SIDES_UP':
                both_up_at = session.get('both_sides_up_at', '')
                if both_up_at:
                    try:
                        up_time = datetime.fromisoformat(both_up_at)
                        elapsed = (datetime.utcnow() - up_time).total_seconds()
                        if elapsed >= 30:
                            # Auto-decide: hedge whichever side has loss
                            decision = self._auto_decide_both_sides(
                                session, ce_now, pe_now
                            )
                            log_activity('both_sides_auto_decision',
                                        f'⏱️ Auto-decision after {elapsed:.0f}s: {decision} '
                                        f'(no user response within 30s)',
                                        sid, 'warning',
                                        {'decision': decision, 'elapsed_seconds': elapsed})
                            # Apply decision
                            session['both_sides_decision'] = decision
                            session['both_sides_decided_at'] = datetime.utcnow().isoformat()
                            session['both_sides_auto'] = True
                            adj_history = session.get('adjustment_history', [])
                            adj_history.append({
                                'type': 'both_sides_decision',
                                'decision': decision,
                                'auto': True,
                                'timestamp': datetime.utcnow().isoformat(),
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
                            if decision == 'adjust_pe':
                                await self._process_adjustment(
                                    'ce', 'pe', ce_now, pe_now, ce_now, pe_now
                                )
                            elif decision == 'adjust_ce':
                                await self._process_adjustment(
                                    'pe', 'ce', pe_now, ce_now, ce_now, pe_now
                                )
                            # else 'skip' — just resume, no adjustment needed
                        else:
                            log_activity('info',
                                        f'BOTH SIDES UP - Waiting for user decision '
                                        f'({30 - elapsed:.0f}s remaining)',
                                        sid, 'warning')
                            self._emit_heartbeat_data(ce_now, pe_now)
                            _save_session(session)
                            return
                    except (ValueError, TypeError):
                        pass

            if self._paused:
                log_activity('info',
                            'Session PAUSED - Monitoring only, no adjustments',
                            sid, 'warning')
                self._emit_heartbeat_data(ce_now, pe_now)
                _save_session(session)
                return

        # Step 5: Cooldown check (§14.3)
        if is_cooldown_active(session):
            cooldown_until = session.get('cooldown_until', '')
            log_activity('info',
                        f'Cooldown Active - Skip adjustment until {cooldown_until[:19] if cooldown_until else "unknown"}',
                        sid, 'info',
                        {'cooldown_until': cooldown_until})
            self._emit_heartbeat_data(ce_now, pe_now)
            _save_session(session)
            return

        # Step 6: Evaluate triggers (§7)
        trigger_result = evaluate_triggers(session, ce_now, pe_now)
        outcome = trigger_result['outcome']

        # Log trigger evaluation
        params = session.get('params', {})
        min_trigger = trigger_result.get('min_trigger_move', params.get('min_trigger_move', 10.0))
        ce_excess_pct = trigger_result.get('ce_excess_pct', 0)
        pe_excess_pct = trigger_result.get('pe_excess_pct', 0)
        
        log_activity('info',
                    f'Trigger Check: CE {ce_excess_pct:+.1f}% (need >{min_trigger:.1f}%), '
                    f'PE {pe_excess_pct:+.1f}% (need >{min_trigger:.1f}%) - '
                    f'Result: {outcome.upper()}',
                    sid, 'info',
                    {
                        'ce_excess_pct': round(ce_excess_pct, 2),
                        'pe_excess_pct': round(pe_excess_pct, 2),
                        'min_trigger_move': min_trigger,
                        'outcome': outcome
                    })

        # Step 7: Process outcome (§4.7)
        if outcome == OUTCOME_NONE:
            log_activity('info',
                        'No triggers fired - Positions stable',
                        sid, 'success')

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
            session['both_sides_up_at'] = datetime.utcnow().isoformat()
            
            # Analytics: Track both_sides_up event (no trading logic impact)
            analytics = session.setdefault('analytics', {})
            analytics.setdefault('both_sides_up_timestamps', []).append(datetime.utcnow().isoformat())
            
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

            # Wind-down mode: reduce instead of adding positions
            if is_wind_down_active(session):
                session['_wind_down_mode'] = True
                log_activity('wind_down',
                            f'🌙 Wind-Down Active: {aggressor.upper()} triggered — '
                            f'reducing positions instead of hedging',
                            sid, 'info',
                            {'aggressor': aggressor.upper(), 'premium': premium_now})

                await self._process_wind_down_buyback(
                    aggressor, ce_now, pe_now,
                )
            else:
                session.pop('_wind_down_mode', None)
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

        # Step 8: Update P&L
        pnl = self._engine.compute_total_pnl(
            session, self._make_fetch_fn()
        )
        session['unrealized_pnl'] = pnl['unrealized']
        update_peak_pnl(session, pnl['net_pnl'])

        # Track P&L for walkthrough
        self._hb_wt['pnl'] = pnl

        # Log P&L summary
        log_activity('info',
                    f'P&L Update: Net ${pnl["net_pnl"]:.2f} '
                    f'(Realized: ${pnl["realized"]:.2f}, Unrealized: ${pnl["unrealized"]:.2f}, '
                    f'Fees: ${pnl["fees"]:.2f})',
                    sid, 'info' if pnl['net_pnl'] >= 0 else 'warning',
                    {
                        'net_pnl': round(pnl['net_pnl'], 2),
                        'realized': round(pnl['realized'], 2),
                        'unrealized': round(pnl['unrealized'], 2),
                        'fees': round(pnl['fees'], 2)
                    })

        # Step 9: Calculate Portfolio Delta (monitoring only, no trading logic)
        portfolio_delta = await self._calculate_portfolio_delta()
        session['portfolio_delta'] = portfolio_delta
        log_activity('info',
                    f'Portfolio Delta: {portfolio_delta:+.3f}',
                    sid, 'info',
                    {'portfolio_delta': round(portfolio_delta, 3)})

        # Update analytics tracking (zero impact on trading logic)
        self._update_analytics_exposure()
        self._update_analytics_pnl_milestones(pnl)
        self._update_analytics_delta(portfolio_delta)

        # P&L history for chart
        session.setdefault('pnl_history', []).append({
            'timestamp': datetime.utcnow().isoformat(),
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
            await self._auto_close_all(
                f'Max loss breached: P&L ${current_total_pnl:.2f} <= -${max_loss_amount:.2f}'
            )
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
        _save_session(session)
        
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

        # Log heartbeat completion with ACTUAL effective interval
        effective_iv = getattr(self, '_effective_interval', session.get('params', {}).get('adjustment_interval', 300))
        from .mmm_activity import log_activity
        log_activity('heartbeat_complete',
                    f'✓ Heartbeat #{session.get("_heartbeat_counter", 0)} complete '
                    f'[{beat_latency_ms:.0f}ms, grade={self._health.grade()}] — '
                    f'Next check in {effective_iv}s',
                    sid, 'success',
                    {'next_interval': effective_iv,
                     'latency_ms': round(beat_latency_ms, 1),
                     'health_grade': self._health.grade()})

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
        from .mmm_activity import log_activity

        reduced_any = False
        for side in ['ce', 'pe']:
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

        from .mmm_activity import log_activity

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
                result = await self.executor.smart_execute(
                    symbol=symbol,
                    side='buy',
                    size=group_lots,
                    reduce_only=True,
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
            'timestamp': datetime.utcnow().isoformat(),
            'side': aggressor.upper(),
            'lots_closed': actual_lots,
            'total_realized_pnl': round(total_realized, 2),
            'remaining_active_lots': remaining,
            'remaining_total_lots': session.get(aggressor, {}).get('total_lots', 0),
            'strikes_closed': list(by_strike.keys()),
            'any_failed': any_failed,
        })

        remaining = session.get(aggressor, {}).get('active_lots', 0)
        session['updated_at'] = datetime.utcnow().isoformat()
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
        from .mmm_activity import log_activity

        side_state = session.setdefault(side, {})
        aggressor_side = 'pe' if side == 'ce' else 'ce'

        # Record the fill
        side_state.setdefault('adjustment_fills', []).append({
            'lots': lots,
            'premium': fill_price,
            'strike': strike,
            'timestamp': datetime.utcnow().isoformat(),
            'type': adj_type,
            'source': 'pending_order_recovery',  # Distinguishes from normal fills
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
            'timestamp': datetime.utcnow().isoformat(),
            'type': adj_type,
            'premium_collected': premium_collected,
            'adjustment_number': session['adjustment_count'],
            'source': 'pending_order_recovery',
        })

        session['updated_at'] = datetime.utcnow().isoformat()

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
        _save_session(session)

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
        from .mmm_activity import log_activity as _log_act
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
                _log_act('pending_order_resolved',
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
                _log_act('pending_order_active',
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
            
            # Analytics: Track reversal event (no trading logic impact)
            analytics = session.setdefault('analytics', {})
            analytics.setdefault('reversal_timestamps', []).append(datetime.utcnow().isoformat())

            # First reversal: use adjustment P&L formula
            loss, adj_pnl = self._engine.calculate_reversal_loss(
                session, aggressor, self._make_fetch_fn()
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
            loss = self._engine.calculate_standard_loss(
                session, aggressor, premium_now,
                fetch_premium_fn=self._make_fetch_fn(),
            )
            adj_type = 'standard'

        if loss <= 0:
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
                        from .mmm_activity import log_activity
                        log_activity('itm_guard_blocked',
                                    f'🚫 ITM GUARD: {hedge.upper()} @ {hedge_strike} is ITM '
                                    f'(spot ${spot_price:.0f}). Adjustment blocked — will not sell ITM.',
                                    sid, 'error',
                                    {'hedge': hedge.upper(), 'strike': hedge_strike, 'spot': spot_price})
                        emit_safety(
                            sid, 'itm_guard', 'critical',
                            f'ITM GUARD: Cannot sell {hedge.upper()} @ {hedge_strike} — '
                            f'strike is ITM (spot ${spot_price:.0f}). Adjustment blocked.',
                            {'hedge': hedge.upper(), 'strike': hedge_strike, 'spot': spot_price}
                        )
                        return
                    else:
                        # ITM guard disabled — user explicitly allows ITM selling
                        log.warning(
                            f"[{sid}] ITM GUARD OFF: {hedge.upper()} strike {hedge_strike} is ITM "
                            f"(spot=${spot_price:.0f}). Proceeding with adjustment (user disabled guard)."
                        )
                        from .mmm_activity import log_activity
                        log_activity('itm_guard_bypassed',
                                    f'⚠️ ITM GUARD OFF: {hedge.upper()} @ {hedge_strike} is ITM '
                                    f'(spot ${spot_price:.0f}). Proceeding — guard disabled by user.',
                                    sid, 'warning',
                                    {'hedge': hedge.upper(), 'strike': hedge_strike, 'spot': spot_price})

        lots, constraint_msg = self._engine.calculate_lots_to_sell(
            session, hedge, loss, hedge_premium,
        )

        if lots <= 0:
            if constraint_msg:
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
            from .mmm_activity import log_activity
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

        # Freeze current positions
        freeze_result = freeze_current_positions(session, side)

        # Find new strike
        spot_price = await self._fetch_spot_price()
        new_strike_info = find_new_strike(
            self.initializer, session, side, spot_price,
        )

        if not new_strike_info:
            emit_safety(
                sid, 'no_strike', 'alert',
                f"No suitable strike found for {side.upper()} shift. "
                f"Cannot shift.",
            )
            return

        # Sell at new strike
        new_strike = new_strike_info['strike']
        hedge_premium = new_strike_info['premium']

        lots, _ = self._engine.calculate_lots_to_sell(
            session, side, loss, hedge_premium,
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

        result = await self.executor.smart_execute(
            symbol=symbol,
            side='sell',
            size=lots,
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
            activate_new_strike(
                session, side, new_strike, fill_price, lots,
            )

            # Clear pending after state is updated
            try:
                clear_pending(sid, side)
            except Exception:
                pass

            # Update triggers at new strike
            update_trigger_snapshots(session, ce_now, pe_now,
                                     fetch_premium_fn=self._make_fetch_fn())

            # Bug #8 fix: update tracking fields that _process_adjustment
            # normally handles via engine._update_state_after_adjustment
            premium_collected = fill_price * lots * LOT_SIZE_BTC
            aggressor_side = 'pe' if side == 'ce' else 'ce'
            session['last_aggressor'] = aggressor_side.upper()
            session['adjustment_count'] = session.get('adjustment_count', 0) + 1
            session['shift_count'] = session.get('shift_count', 0) + 1
            session['total_premium_collected'] = (
                session.get('total_premium_collected', 0) + premium_collected
            )
            
            # Analytics: Track shift event (no trading logic impact)
            analytics = session.setdefault('analytics', {})
            analytics.setdefault('shift_timestamps', []).append({
                'timestamp': datetime.utcnow().isoformat(),
                'side': side.upper(),
                'old_strike': old_strike,
                'new_strike': new_strike,
                'frozen_lots': freeze_result['frozen_lots'],
            })
            
            session.setdefault('adjustment_history', []).append({
                'side': side.upper(),
                'aggressor': aggressor_side.upper(),
                'lots_sold': lots,
                'premium': fill_price,
                'strike': new_strike,
                'old_strike': old_strike,
                'timestamp': datetime.utcnow().isoformat(),
                'type': 'strike_shift',
                'premium_collected': premium_collected,
                'adjustment_number': session['adjustment_count'],
            })
            session['updated_at'] = datetime.utcnow().isoformat()

            emit_strike_shift(
                sid, side.upper(), old_strike, new_strike,
                freeze_result['frozen_lots'], fill_price,
            )

            log.info(
                f"Strike shift complete: {side.upper()} "
                f"{old_strike} → {new_strike}"
            )

    # =========================================================================
    # §11: Close-at-5 Processing
    # =========================================================================

    async def _process_close_at_5(
        self,
        ce_now: float,
        pe_now: float,
    ):
        """Scan and close positions at or below threshold.
        During wind-down, uses elevated threshold from wind_down_close_threshold
        to harvest opportunity (close positions that have decayed significantly).
        """
        session = self.session
        sid = self.session_id

        # During wind-down, elevate the close threshold for opportunity harvest
        wd_threshold = get_wind_down_close_threshold(session)
        normal_threshold = session.get('params', {}).get('close_at_threshold', 5.0)
        using_elevated = wd_threshold > normal_threshold

        closeable = scan_closeable_positions(
            session, self._make_fetch_fn(),
            threshold_override=wd_threshold if using_elevated else None,
        )

        if closeable:
            from .mmm_activity import log_activity
            threshold_note = f' (wind-down elevated threshold: {wd_threshold})' if using_elevated else ''
            closeable_summary = ', '.join([f"{p['side'].upper()} @ {p['strike']}" for p in closeable])
            log_activity('info',
                        f'Close-at-5 Scan: {len(closeable)} position(s) ready to close{threshold_note} - {closeable_summary}',
                        sid, 'info',
                        {'closeable_count': len(closeable), 'positions': closeable_summary,
                         'wind_down_elevated': using_elevated, 'threshold_used': wd_threshold if using_elevated else normal_threshold})

        for pos in closeable:
            result = await close_position(
                self.executor, self.initializer, session, pos,
            )

            if result.get('success'):
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
                })

                # Check if side fully closed → auto-find new strike
                if check_side_fully_closed(session, pos['side']):
                    log.info(
                        f"[{sid}] {pos['side'].upper()} fully closed, "
                        f"seeking new strike..."
                    )
                    # This is a special case — we don't shift, we re-enter
                    # For now, just log. Full auto-re-entry needs user config.

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
        ce_trigger_strike = str(int(ce_state.get('active_strike', 0)))
        pe_trigger_strike = str(int(pe_state.get('active_strike', 0)))
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

    async def _auto_close_all(self, reason: str):
        """Close all open positions (near-expiry safety).
        
        Closes each position at its own strike:
        - Active positions (original + adjustment) at active_strike
        - Each frozen position at its own frozen strike

        Bug #9 fix: retry failed closes up to MAX_CLOSE_RETRIES times.
        Bug #13 fix: clear lot counts and position arrays after closes.
        Bug #16 fix: always call self.stop() even if exceptions occur.
        """
        session = self.session
        sid = self.session_id
        MAX_CLOSE_RETRIES = 3

        log.info(f"[{sid}] Auto-closing all positions: {reason}")

        failed_closes = []

        try:

            for side_key in ['ce', 'pe']:
                # Bug #11 fix: check stop event between sides
                if self._should_stop():
                    log.warning(f"[{sid}] Stop requested during auto-close, aborting remaining closes")
                    break

                side_state = session.get(side_key, {})
                option_type = 'call' if side_key == 'ce' else 'put'
                active_strike = side_state.get('active_strike', 0)
                expiry = session.get('params', {}).get('expiry', '')

                # Close active lots (original + adjustment) at active strike
                active_lots = side_state.get('active_lots', 0)
                if active_lots > 0 and active_strike > 0:
                    closed = False
                    for attempt in range(1, MAX_CLOSE_RETRIES + 1):
                        try:
                            symbol = self.initializer.build_symbol(
                                option_type, 'BTC', active_strike, expiry,
                            )
                            result = await self.executor.smart_execute(
                                symbol=symbol,
                                side='buy',
                                size=active_lots,
                                reduce_only=True,
                            )
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
                                # Bug #13 fix: clear state
                                side_state['original_lots'] = 0
                                side_state['adjustment_fills'] = []
                                side_state['active_lots'] = 0
                                closed = True
                                break
                            else:
                                log.warning(
                                    f"[{sid}] Auto-close active {side_key.upper()} "
                                    f"attempt {attempt}/{MAX_CLOSE_RETRIES} failed: "
                                    f"{result.get('error', 'unknown')}"
                                )
                        except Exception as e:
                            log.error(
                                f"[{sid}] Auto-close active {side_key.upper()} "
                                f"attempt {attempt}/{MAX_CLOSE_RETRIES} error: {e}"
                            )
                        if attempt < MAX_CLOSE_RETRIES:
                            await asyncio.sleep(2)  # Brief pause before retry
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
                        for attempt in range(1, MAX_CLOSE_RETRIES + 1):
                            try:
                                symbol = self.initializer.build_symbol(
                                    option_type, 'BTC', frozen_strike, expiry,
                                )
                                result = await self.executor.smart_execute(
                                    symbol=symbol,
                                    side='buy',
                                    size=frozen_lots,
                                    reduce_only=True,
                                )
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
                                        f"attempt {attempt}/{MAX_CLOSE_RETRIES} failed"
                                    )
                            except Exception as e:
                                log.error(
                                    f"Failed to auto-close frozen {side_key.upper()} "
                                    f"@ {frozen_strike}, attempt {attempt}: {e}"
                                )
                            if attempt < MAX_CLOSE_RETRIES:
                                await asyncio.sleep(2)
                        if not closed:
                            failed_closes.append(f"{side_key.upper()} frozen @ {frozen_strike}")

                # Bug #13 fix: remove successfully closed frozen positions (descending)
                for fi in sorted(closed_frozen_indices, reverse=True):
                    side_state.get('frozen_positions', []).pop(fi)

                # Recompute lots after clearing
                recompute_side_lots(side_state)
                session[side_key] = side_state

            if failed_closes:
                log.error(
                    f"[{sid}] Auto-close completed with FAILURES: {failed_closes}. "
                    f"Manual intervention may be needed."
                )

        except Exception as e:
            log.exception(f"[{sid}] CRITICAL: _auto_close_all crashed: {e}")
        finally:
            # Bug #16 fix: ALWAYS stop the session, even if close orders failed
            self.stop(reason)

    # =========================================================================
    # Helpers
    # =========================================================================

    # =========================================================================
    # §14.5: Exchange Position Reconciliation
    # =========================================================================

    async def _reconcile_exchange_positions(self):
        """
        Query actual exchange positions and compare with session state.

        ISOLATION: Only checks symbols that THIS session manages.
        Does NOT look at or interfere with positions from other algos,
        manual trades, or other MMM sessions.

        Detects discrepancies like:
        - Session thinks position is open but exchange shows 0
        - Lot count mismatch between session state and exchange

        Logs discrepancies as activities but does NOT auto-correct.
        """
        session = self.session
        sid = self.session_id

        # Only reconcile every Nth heartbeat to avoid API spam
        recon_counter = session.get('_recon_counter', 0) + 1
        session['_recon_counter'] = recon_counter
        if recon_counter % 5 != 1:  # Every 5th heartbeat (first, 6th, 11th, ...)
            return

        # ── Build the set of symbols THIS session owns ──
        session_symbols = set()
        expiry = session.get('params', {}).get('expiry', '')

        for side_key in ['ce', 'pe']:
            side = session.get(side_key, {})
            # Active symbol
            sym = side.get('symbol', '')
            if sym:
                session_symbols.add(sym)
            # Frozen positions may be at different strikes
            for frozen in side.get('frozen_positions', []):
                frozen_strike = frozen.get('strike', 0)
                if frozen_strike > 0:
                    opt = 'call' if side_key == 'ce' else 'put'
                    fsym = self.initializer.build_symbol(opt, 'BTC', frozen_strike, expiry)
                    session_symbols.add(fsym)

        if not session_symbols:
            return

        try:
            rest = self._create_heartbeat_rest_client()

            # Fetch all open positions from the exchange
            resp = await rest._request_with_retry(
                method="GET",
                path="/v2/positions",
                params={"product_types": "options"},
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
                symbol = side.get('symbol', '')

                if not symbol:
                    continue

                # Bug #6 fix: Compare active symbol lots (original + adj at active strike)
                # separately from frozen position lots at their own strikes.
                active_lots = side.get('original_lots', 0)
                for fill in side.get('adjustment_fills', []):
                    f_strike = fill.get('strike', active_strike)
                    if f_strike == active_strike:
                        active_lots += fill.get('lots', 0)

                exchange_pos = exchange_positions.get(symbol, {})
                exchange_size = exchange_pos.get('size', 0)

                if active_lots > 0 and exchange_size == 0:
                    discrepancies.append({
                        'side': side_key.upper(),
                        'type': 'MISSING_ON_EXCHANGE',
                        'detail': f"{side_key.upper()} active: session has {active_lots} lots but exchange shows 0",
                        'symbol': symbol,
                        'session_lots': active_lots,
                        'exchange_size': 0,
                    })
                elif abs(active_lots - exchange_size) > 0.1 and active_lots > 0:
                    discrepancies.append({
                        'side': side_key.upper(),
                        'type': 'SIZE_MISMATCH',
                        'detail': f"{side_key.upper()} active: session={active_lots} vs exchange={exchange_size}",
                        'symbol': symbol,
                        'session_lots': active_lots,
                        'exchange_size': exchange_size,
                    })

                # Check frozen positions at their own strikes
                for frozen in side.get('frozen_positions', []):
                    f_strike = frozen.get('strike', 0)
                    f_lots = frozen.get('lots', 0)
                    if f_lots <= 0 or f_strike <= 0:
                        continue
                    fsym = self.initializer.build_symbol(option_type, 'BTC', f_strike, expiry)
                    f_exchange = exchange_positions.get(fsym, {})
                    f_ex_size = f_exchange.get('size', 0)

                    if f_lots > 0 and f_ex_size == 0:
                        discrepancies.append({
                            'side': side_key.upper(),
                            'type': 'FROZEN_MISSING',
                            'detail': f"{side_key.upper()} frozen @ {f_strike}: session={f_lots} but exchange=0",
                            'symbol': fsym,
                            'session_lots': f_lots,
                            'exchange_size': 0,
                        })
                    elif abs(f_lots - f_ex_size) > 0.1:
                        discrepancies.append({
                            'side': side_key.upper(),
                            'type': 'FROZEN_MISMATCH',
                            'detail': f"{side_key.upper()} frozen @ {f_strike}: session={f_lots} vs exchange={f_ex_size}",
                            'symbol': fsym,
                            'session_lots': f_lots,
                            'exchange_size': f_ex_size,
                        })

            # Store last reconciliation result (only our symbols)
            session['last_reconciliation'] = {
                'timestamp': datetime.utcnow().isoformat(),
                'session_symbols': list(session_symbols),
                'exchange_positions': {k: v for k, v in exchange_positions.items()},
                'discrepancies': discrepancies,
                'matched_count': len(exchange_positions),
            }

            if discrepancies:
                from .mmm_activity import log_activity
                for d in discrepancies:
                    log.warning(f"[{sid}] RECONCILIATION: {d['detail']}")
                    log_activity('reconciliation_warning',
                        f"Position mismatch: {d['detail']}",
                        session_id=sid, severity='warning',
                        details=d)
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

            ce_mark = float(ce_data.get('mark_price', 0))
            pe_mark = float(pe_data.get('mark_price', 0))

            # Store the rest client for prefetch to reuse in this heartbeat
            self._heartbeat_rest = rest

            return ce_mark, pe_mark

        except Exception as e:
            log.error(f"Error fetching premiums: {e}")
            return None, None

    async def _fetch_premiums_with_fallback(self):
        """
        Circuit-breaker-aware premium fetch with order-book mid fallback.

        Returns:
            (ce_premium, pe_premium, ok: bool)
            ok=False means partial/miss beat should run, not full beat.
        """
        sid = self.session_id

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

            # Primary ticker API returned zeros — try order-book mid as fallback
            ce_fb, pe_fb = await self._fetch_premiums_orderbook_fallback()
            if ce_fb is not None and pe_fb is not None and ce_fb > 0 and pe_fb > 0:
                log.info(
                    f"[{sid}] Ticker API returned zero — using order-book mid: "
                    f"CE={ce_fb:.2f} PE={pe_fb:.2f}"
                )
                self._circuit.record_success()
                return ce_fb, pe_fb, True

            # Both sources failed
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

        if to_fetch:
            async def _fetch_one(strike, opt):
                try:
                    symbol = self.initializer.build_symbol(
                        opt, 'BTC', strike, expiry,
                    )
                    resp = await rest._request_with_retry(
                        method="GET", path=f"/v2/tickers/{symbol}",
                    )
                    data = resp.get('result', resp)
                    return (strike, opt), float(data.get('mark_price', 0))
                except Exception as e:
                    log.warning(f"Prefetch failed for {opt}@{strike}: {e}")
                    return (strike, opt), 0

            results = await asyncio.gather(
                *[_fetch_one(s, o) for s, o in to_fetch],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    continue
                key, value = r
                cache[key] = value

        self._premium_cache = cache

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
            now = datetime.utcnow()
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
            analytics['peak_risk_timestamp'] = datetime.utcnow().isoformat()
        
        if pe_lots > analytics.get('max_pe_lots', 0):
            analytics['max_pe_lots'] = pe_lots
            if not analytics.get('peak_risk_timestamp'):
                analytics['peak_risk_timestamp'] = datetime.utcnow().isoformat()
        
        if combined_lots > analytics.get('max_combined_lots', 0):
            analytics['max_combined_lots'] = combined_lots
            analytics['peak_risk_timestamp'] = datetime.utcnow().isoformat()

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
                    elapsed = (datetime.utcnow() - start_dt).total_seconds()
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
                    elapsed = (datetime.utcnow() - start_dt).total_seconds()
                    analytics['time_to_peak_pnl'] = elapsed
                except (ValueError, TypeError):
                    pass
        
        # Track max drawdown from peak
        if peak > 0:
            drawdown = peak - net_pnl
            if drawdown > analytics.get('max_drawdown_from_peak', 0):
                analytics['max_drawdown_from_peak'] = drawdown
                analytics['max_drawdown_timestamp'] = datetime.utcnow().isoformat()

    def _update_analytics_delta(self, portfolio_delta: float):
        """Update delta tracking (no trading logic impact)."""
        session = self.session
        analytics = session.setdefault('analytics', {})
        
        abs_delta = abs(portfolio_delta)
        if abs_delta > analytics.get('max_abs_delta', 0):
            analytics['max_abs_delta'] = abs_delta
            analytics['max_abs_delta_timestamp'] = datetime.utcnow().isoformat()

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
                return 0.0
            
            # Fetch Greeks for all positions
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
            
            # Calculate portfolio delta
            portfolio_delta = 0.0
            for (strike, opt), resp in ticker_results:
                if isinstance(resp, Exception):
                    continue
                
                result = resp.get('result', {})
                greek_delta = result.get('greeks', {}).get('delta', 0)
                
                lots = position_map[(strike, opt)]
                # multiplier: short CE = -1, short PE = +1
                multiplier = 1 if opt == 'put' else -1
                position_delta = greek_delta * lots * LOT_SIZE_BTC * multiplier
                portfolio_delta += position_delta
            
            return portfolio_delta
            
        except Exception as e:
            log.warning(f"[{self.session_id}] Failed to calculate portfolio delta: {e}")
            return 0.0

    def _emit_heartbeat_data(self, ce_now: float, pe_now: float):
        """Emit heartbeat WebSocket event with premium_map for live prices."""
        session = self.session
        ce_trigger = session.get('ce', {}).get('trigger_snapshot', {}).get(
            str(int(session.get('ce', {}).get('active_strike', 0))), 0
        )
        pe_trigger = session.get('pe', {}).get('trigger_snapshot', {}).get(
            str(int(session.get('pe', {}).get('active_strike', 0))), 0
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

        emit_heartbeat(
            self.session_id, ce_now, pe_now,
            ce_trigger, pe_trigger,
            session.get('strategy_status', 'UNKNOWN'),
            realized + unrealized, realized,
            premium_map=premium_map,
            adaptive_tier=session.get('_adaptive_tier', ''),
            wind_down_active=is_wind_down_active(session),
            portfolio_delta=portfolio_delta,
        )


# =============================================================================
# Monitor Registry — track all active monitors
# =============================================================================

_monitors: Dict[str, MMMMonitor] = {}


def start_session_monitor(session_id: str, session: Dict) -> MMMMonitor:
    """Start a monitor for a session."""
    if session_id in _monitors:
        log.warning(f"Monitor already exists for {session_id}")
        _monitors[session_id].stop('Replaced by new monitor')

    monitor = MMMMonitor(session_id, session)
    _monitors[session_id] = monitor
    monitor.start()
    return monitor


def stop_session_monitor(session_id: str, reason: str = 'Stopped'):
    """Stop a session's monitor."""
    monitor = _monitors.get(session_id)
    if monitor:
        monitor.stop(reason)
        del _monitors[session_id]


def pause_session_monitor(session_id: str, reason: str = 'Paused'):
    """Pause a session's monitor."""
    monitor = _monitors.get(session_id)
    if monitor:
        monitor.pause(reason)


def resume_session_monitor(session_id: str, reason: str = 'Resumed'):
    """Resume a session's monitor."""
    monitor = _monitors.get(session_id)
    if monitor:
        monitor.resume(reason)


def get_monitor(session_id: str) -> Optional[MMMMonitor]:
    """Get an existing monitor."""
    return _monitors.get(session_id)


def get_all_monitors() -> Dict[str, MMMMonitor]:
    """Get all active monitors."""
    return dict(_monitors)


def _save_session(session: Dict):
    """Persist session to storage, preserving hot-reload param updates.

    The heartbeat never modifies session['params'].  However, the user may
    update params via the Settings API (PATCH /params) while a heartbeat is
    in-flight.  If we blindly save the monitor's in-memory copy, those
    API-driven param changes get overwritten.  To prevent this, we re-read
    the latest params from storage right before saving so hot-reload
    updates are never lost.
    """
    try:
        storage = get_storage()
        sid = session.get('session_id')
        if sid:
            stored = storage.get_session(sid)
            if stored and 'params' in stored:
                session['params'] = stored['params']
        storage.save_session(session)
    except Exception as e:
        log.error(f"Failed to save session: {e}")
