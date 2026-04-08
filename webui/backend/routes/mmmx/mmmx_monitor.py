"""
MMMX Monitor — Heartbeat Thread with 3-Layer Generation Guard

Spec: MMMX_IMPLEMENTATION_PLAN.md Section 1 + CLAUDE.md §4 (Stale Monitor Invariants).

Phase 1 scope:
  - Thread skeleton: _run_loop loads/saves session, emits mmmx_heartbeat, increments beat.
  - All three generation guard layers ARE implemented here (they must be present from day 1).

Phase 3 scope:
  - _heartbeat() replaces _heartbeat_stub — full hot-path with safety check + trigger evaluation.
  - _dispatch_close_all() — emergency close for HARD_STOP and DTE_CLOSE triggers.

Three guard layers (MUST NOT be removed or weakened):
  1. start_session_monitor() — thread.join(15s): waits for old thread to exit before new spawns.
  2. _run_loop primary guard: at top of every cycle, checks stored_gen > _my_generation → self-stop.
  3. _heartbeat G5 hook: inside heartbeat, re-checks generation before any state mutation.

_save_session() returns True on success, False if blocked by generation conflict.
Callers MUST check the return value and set _stale_abort_gen if False.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional

log = logging.getLogger('mmmx_monitor')

# -- Registry ------------------------------------------------------------------
# session_id -> MMMXMonitor. Written only by start_session_monitor().
_mmmx_monitors: Dict[str, 'MMMXMonitor'] = {}
_monitors_lock = threading.Lock()

# -- Generation counter --------------------------------------------------------
# Monotonic, DB-persisted. Incremented BEFORE new thread spawns.
# Written only via mmmx_storage.bump_generation().


class MMMXMonitor:
    """
    Heartbeat monitor for one MMMX session.

    Phase 1: Bare skeleton — loads session, emits heartbeat, saves session.
    Phase 3: Full trigger logic, safety pre-check, dispatch close-all.
    Phase 5+: Deployment, profit booking, hedger.
    """

    def __init__(self, session_id: str, my_generation: int):
        self.session_id = session_id
        self._my_generation = my_generation
        self._running = False
        self._stale_abort_gen = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # Phase 7: in-memory wake event; set by signal_force_check() or stop()
        self._force_wake_event = threading.Event()

    def start(self) -> None:
        """Spawn the heartbeat thread."""
        if self._thread is not None and self._thread.is_alive():
            log.warning(
                f"[MMMX][{self.session_id[:8]}] start() called while thread is still alive — "
                "ignoring (caller should have called stop() first)"
            )
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"mmmx_monitor_{self.session_id[:8]}_gen{self._my_generation}",
            daemon=True,
        )
        self._thread.start()
        log.info(
            f"[MMMX][{self.session_id[:8]}] Monitor gen={self._my_generation} started."
        )

    def stop(self, reason: str = 'requested') -> None:
        """Signal the thread to stop cleanly."""
        self._running = False
        self._stop_event.set()
        self._force_wake_event.set()   # also wake from sleep immediately
        log.info(
            f"[MMMX][{self.session_id[:8]}] Monitor gen={self._my_generation} "
            f"stop requested: {reason}"
        )

    def signal_force_check(self) -> None:
        """
        Wake the monitor from its inter-beat sleep so it runs a heartbeat immediately.
        Called by PremiumListener.force_heartbeat() when a Tier-0 CB fires.
        """
        self._force_wake_event.set()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # -- Layer 2: _run_loop primary generation guard ---------------------------

    def _run_loop(self) -> None:
        """
        Main heartbeat loop.

        Guard Layer 2: At the top of each cycle, loads fresh stored_gen from DB.
        If stored_gen > _my_generation -> this monitor is stale -> self-stop immediately.
        """
        from .mmmx_storage import get_storage
        from .mmmx_telegram import alert_stale_monitor
        from .mmmx_websocket import emit_safety

        log.info(
            f"[MMMX][{self.session_id[:8]}] _run_loop started gen={self._my_generation}"
        )

        storage = get_storage()

        while self._running and not self._stop_event.is_set():
            # -- Guard Layer 2: stale check ------------------------------------
            stored_gen = storage.get_generation(self.session_id)
            if stored_gen > self._my_generation:
                log.error(
                    f"[MMMX][{self.session_id[:8]}] STALE MONITOR: "
                    f"my_gen={self._my_generation}, stored_gen={stored_gen}. Self-stopping."
                )
                self._running = False

                # Fire Telegram (sync, not run_until_complete per CLAUDE.md §4)
                try:
                    alert_stale_monitor(self.session_id, self._my_generation, stored_gen)
                except Exception as exc:
                    log.error(f"Stale monitor telegram failed: {exc}")

                # Fire safety WebSocket (regular def — call directly)
                try:
                    emit_safety(
                        session_id=self.session_id,
                        safety_type='stale_monitor',
                        level='critical',
                        message=(
                            f"Stale monitor self-stopped: "
                            f"my_gen={self._my_generation}, stored_gen={stored_gen}"
                        ),
                    )
                except Exception as exc:
                    log.error(f"Stale monitor emit_safety failed: {exc}")

                break

            # -- Heartbeat (async, run in this thread's event loop) ------------
            try:
                asyncio.run(self._heartbeat())
            except Exception as exc:
                log.exception(
                    f"[MMMX][{self.session_id[:8]}] Heartbeat error (gen={self._my_generation}): {exc}"
                )

            # -- Sleep until next beat (or force-wake from listener) -----------
            beat_secs = self._get_beat_interval_secs()
            self._force_wake_event.clear()
            woken_early = self._force_wake_event.wait(timeout=beat_secs)
            if woken_early and self._running:
                log.info(
                    f"[MMMX][{self.session_id[:8]}] "
                    "Force-wake received — running heartbeat immediately (skipping sleep)"
                )

        log.info(
            f"[MMMX][{self.session_id[:8]}] _run_loop exited gen={self._my_generation}"
        )

    def _get_beat_interval_secs(self) -> float:
        """Return heartbeat interval in seconds. Reads from params, default 1h."""
        try:
            from .mmmx_storage import get_storage
            storage = get_storage()
            session = storage.load_session(self.session_id)
            if session:
                hours = session.get('params', {}).get('adjustment_interval_hours', 1.0)
                return float(hours) * 3600.0
        except Exception:
            pass
        return 3600.0

    # -- Layer 3: _heartbeat G5 hook -------------------------------------------

    async def _heartbeat(self) -> None:
        """
        Phase 3 full heartbeat hot-path.

        Guard Layer 3 (G5): After loading fresh session, re-checks generation
        before any state mutation. If stale -> stop and return.

        Steps:
          1. Safety pre-check (mmmx_safety.pre_beat_check)
          2. Recompute engine metrics
          3. Trigger evaluation (winner + full ladder)
          4. Dispatch (HARD_STOP / DTE_CLOSE only in Phase 3)
          5. Emit heartbeat + save
        """
        from .mmmx_storage import get_storage, GenerationConflict
        from .mmmx_websocket import emit_heartbeat, emit_safety, emit_trigger_evaluation
        from .mmmx_activity import log_activity
        from .mmmx_integrity import build_integrity_signature
        from .mmmx_engine import (
            compute_portfolio_pnl,
            compute_portfolio_delta,
            compute_lot_imbalance,
            compute_dte_days,
            recalc_hard_stop,
            PnLIncompleteError,
        )
        from .mmmx_constants import TriggerName
        from . import mmmx_safety as safety
        from . import mmmx_trigger as trigger

        storage = get_storage()

        # Load fresh session
        session = storage.load_session(self.session_id)
        if session is None:
            log.error(
                f"[MMMX][{self.session_id[:8]}] Session not found in DB — stopping monitor."
            )
            self._running = False
            return

        # -- Guard Layer 3 (G5): generation check inside heartbeat -------------
        stored_gen = storage.get_generation(self.session_id)
        if stored_gen > self._my_generation:
            log.error(
                f"[MMMX][{self.session_id[:8]}] G5 guard: stale gen inside heartbeat. "
                f"my={self._my_generation}, stored={stored_gen}. Stopping."
            )
            self._running = False
            try:
                emit_safety(
                    session_id=self.session_id,
                    safety_type='generation_guard',
                    level='critical',
                    message=f"G5 guard fired inside heartbeat: my_gen={self._my_generation}",
                )
            except Exception:
                pass
            return

        # -- 1. Safety pre-check -----------------------------------------------
        verdict = safety.pre_beat_check(session, stored_gen, self._my_generation)

        if verdict.abort:
            log.error(
                f"[MMMX][{self.session_id[:8]}] Safety abort: {verdict.reason}"
            )
            self._running = False
            try:
                emit_safety(
                    session_id=self.session_id,
                    safety_type='safety_abort',
                    level='critical',
                    message=f"Monitor aborted by safety check: {verdict.reason}",
                )
            except Exception:
                pass
            return

        if verdict.skip_beat:
            log.info(
                f"[MMMX][{self.session_id[:8]}] Safety skip_beat: {verdict.reason}"
            )
            now = datetime.now(timezone.utc).isoformat()
            session['beat_number'] = session.get('beat_number', 0) + 1
            session['_last_beat_at'] = now
            saved = self._save_session(session, storage)
            if not saved:
                self._stale_abort_gen = self._my_generation
                self._running = False
            return

        # -- 2. Recompute engine metrics ----------------------------------------
        try:
            pnl = compute_portfolio_pnl(session)
            delta = compute_portfolio_delta(session)
            imbal = compute_lot_imbalance(session)
            dte = compute_dte_days(session['expiry_datetime'])
            session['_pnl_calculation_incomplete'] = False
        except PnLIncompleteError as exc:
            log.warning(
                f"[MMMX][{self.session_id[:8]}] PnLIncompleteError: {exc}"
            )
            session['_pnl_calculation_incomplete'] = True
            now = datetime.now(timezone.utc).isoformat()
            session['beat_number'] = session.get('beat_number', 0) + 1
            session['_last_beat_at'] = now
            try:
                log_activity(
                    event_type='heartbeat_skipped',
                    message=f"Beat skipped — PnL incomplete: {exc}",
                    session_id=self.session_id,
                    level='warning',
                )
            except Exception:
                pass
            saved = self._save_session(session, storage)
            if not saved:
                self._stale_abort_gen = self._my_generation
                self._running = False
            return

        # Update session snapshot fields
        session['portfolio_pnl'] = pnl
        session['portfolio_delta'] = delta
        session['ce_lot_balance'] = imbal

        # recalc_hard_stop returns the value but does NOT mutate session — we update it
        new_hard_stop = recalc_hard_stop(session)
        session['hard_stop_usd'] = new_hard_stop

        # -- 2.5. Fetch live market data (non-blocking; None on failure) ----------
        _live_spot: float | None = None
        _live_iv_rank: float | None = None
        try:
            from webui.backend.options_chain.chain_service import get_chain_service
            _live_spot = get_chain_service()._get_spot_price('BTC') or None
        except Exception:
            try:
                from options_chain.chain_service import get_chain_service
                _live_spot = get_chain_service()._get_spot_price('BTC') or None
            except Exception:
                pass

        try:
            from .mmmx_iv_adapter import get_iv_rank as _get_iv_rank
            _live_iv_rank = _get_iv_rank()
        except Exception:
            pass

        # -- 3. Trigger evaluation ---------------------------------------------
        metrics = {
            'portfolio_pnl':   pnl,
            'portfolio_delta': delta,
            'dte_days':        dte,
            'iv_rank':         _live_iv_rank,
            'lot_imbalance':   imbal,
            'spot_price':      _live_spot,
        }
        hit, trigger_ladder = trigger.evaluate_with_ladder(session, metrics)

        try:
            emit_trigger_evaluation(
                session_id=self.session_id,
                beat_number=session.get('beat_number', 0) + 1,
                status=session.get('status', 'PAUSED'),
                winner={
                    'trigger_name': hit.trigger_name,
                    'reason': hit.reason,
                    'severity': hit.severity,
                    'data': hit.data,
                } if hit else None,
                ladder=trigger_ladder,
                metrics={
                    'portfolio_pnl': pnl,
                    'portfolio_delta': delta,
                    'dte_days': dte,
                    'iv_rank': _live_iv_rank,
                    'spot_price': _live_spot,
                },
            )
        except Exception as exc:
            log.error(
                f"[MMMX][{self.session_id[:8]}] emit_trigger_evaluation failed: {exc}"
            )

        # -- 4. Dispatch -------------------------------------------------------
        if hit:
            log.warning(
                f"[MMMX][{self.session_id[:8]}] Trigger fired: "
                f"{hit.trigger_name} — {hit.reason}"
            )

            # Activity log
            try:
                event_map = {
                    TriggerName.HARD_STOP: 'hard_stop_fired',
                    TriggerName.DTE_CLOSE: 'dte_close_fired',
                    TriggerName.IV_CATASTROPHE: 'iv_catastrophe_fired',
                    TriggerName.NEAR_ITM: 'near_itm_fired',
                    TriggerName.PORTFOLIO_DELTA: 'delta_gate_fired',
                    TriggerName.DELTA_DRIFT: 'delta_gate_fired',
                    TriggerName.IV_SPIKE: 'delta_gate_fired',
                }
                log_activity(
                    event_type=event_map.get(hit.trigger_name, 'hard_stop_fired'),
                    message=hit.reason,
                    session_id=self.session_id,
                    level=hit.severity,
                    data=hit.data,
                )
            except Exception:
                pass

            # Audit log
            try:
                from .mmmx_audit_log import get_audit_log
                get_audit_log().enqueue_event(
                    session_id=self.session_id,
                    category='TRIGGER',
                    message=f"{hit.trigger_name}: {hit.reason}",
                    data=hit.data,
                )
            except Exception:
                pass

            # Phase 3: only HARD_STOP and DTE_CLOSE actually execute
            if hit.trigger_name in (TriggerName.HARD_STOP, TriggerName.DTE_CLOSE):
                await self._dispatch_close_all(session, hit.trigger_name)
                return  # session is now COMPLETE — do not save RUNNING state

            # All other triggers: log only, no action yet (Phase 5+)

        # -- 4b. Naked watchdog (G37) ------------------------------------------
        try:
            from . import mmmx_reconciler as reconciler
            from .mmmx_executor import get_executor as _get_executor
            await reconciler.check_naked_watchdog(session, _get_executor())
        except Exception as exc:
            log.error(
                f"[MMMX][{self.session_id[:8]}] Naked watchdog error: {exc}"
            )

        # -- 4c. ATM Shield (Phase 5) — fires before deployment (Phase 6+) ----
        try:
            from . import mmmx_atm_shield as atm_shield
            from .mmmx_executor import get_executor as _get_executor
            from .mmmx_audit_log import get_audit_log as _get_audit
            _spot = metrics.get('spot_price')   # None in Phase 5 (no live feed yet)
            if _spot:
                shield_results = await atm_shield.evaluate_and_fire(
                    session=session,
                    spot=_spot,
                    executor=_get_executor(),
                    audit=_get_audit(),
                    save_fn=lambda s: self._save_session(s, storage),
                )
                if shield_results:
                    log.info(
                        f"[MMMX][{self.session_id[:8]}] "
                        f"ATM Shield: {len(shield_results)} shield(s) fired."
                    )
        except Exception as exc:
            log.error(
                f"[MMMX][{self.session_id[:8]}] ATM Shield error: {exc}"
            )

        # -- 5. Whipsaw decay + deployment (Phase 6) ---------------------------
        # 5a. Decay whipsaw score (run every beat regardless of deploy)
        try:
            from . import mmmx_whipsaw as _whipsaw
            _whipsaw.decay_score(session)
        except Exception as exc:
            log.error(f"[MMMX][{self.session_id[:8]}] Whipsaw decay error: {exc}")

        # 5b. Deployment: check conditions → manage queue → deploy one tranche
        _spot = metrics.get('spot_price')
        _iv_rank = metrics.get('iv_rank')
        if (
            session.get('status') == 'RUNNING'
            and _spot is not None
        ):
            try:
                from . import mmmx_initializer as _init

                # Score new shield events from this beat (after ATM shield phase)
                try:
                    _whipsaw.score_tick(session)
                except Exception as exc:
                    log.debug(
                        f"[MMMX][{self.session_id[:8]}] Whipsaw score_tick error: {exc}"
                    )

                # Check retrace — may clear queue
                _init.clear_queue_on_retrace(session, _spot)

                # Evaluate deployment trigger
                _deploy_decision = _init.check_deploy_conditions(session, metrics)

                if _deploy_decision.should_deploy:
                    # Populate eligibility queue if empty
                    if not session.get('deployment_eligible_tranches'):
                        _init.populate_eligibility_queue(
                            session,
                            spot_move_pct=_deploy_decision.spot_move_pct,
                            current_spot=_spot,
                            last_deployment_spot=session.get('last_deployment_spot'),
                        )

                    # Deploy one tranche per beat (queue pop happens inside execute_tranche_deploy)
                    if session.get('deployment_eligible_tranches'):
                        _chain = metrics.get('chain', [])
                        from .mmmx_executor import get_executor as _get_executor_deploy
                        from .mmmx_audit_log import get_audit_log as _get_audit_deploy
                        _deployed_tranche = await _init.execute_tranche_deploy(
                            session=session,
                            executor=_get_executor_deploy(),
                            audit=_get_audit_deploy(),
                            spot=_spot,
                            iv_rank=float(_iv_rank or 0.0),
                            chain=_chain,
                            save_fn=lambda s: self._save_session(s, storage),
                        )
                        # Phase 7: schedule hedge for Tr5+ deployments
                        if _deployed_tranche is not None:
                            try:
                                from . import mmmx_hedger as _hedger_sched
                                _hedger_sched.schedule_post_deploy(
                                    session=session,
                                    tranche_id=_deployed_tranche.get('tranche_id'),
                                    deployed_at=_deployed_tranche.get(
                                        'deployed_at',
                                        datetime.now(timezone.utc).isoformat(),
                                    ),
                                )
                            except Exception as _hedge_exc:
                                log.error(
                                    f"[MMMX][{self.session_id[:8]}] "
                                    f"schedule_post_deploy error: {_hedge_exc}"
                                )

            except Exception as exc:
                log.error(
                    f"[MMMX][{self.session_id[:8]}] Deployment step error: {exc}"
                )

        # 5c. Process pending profit booking
        try:
            from . import mmmx_profit_booking as _pb
            from .mmmx_executor import get_executor as _get_executor_pb
            from .mmmx_audit_log import get_audit_log as _get_audit_pb
            if session.get('_profit_booking_queue'):
                await _pb.process_pending(
                    session=session,
                    executor=_get_executor_pb(),
                    audit=_get_audit_pb(),
                    save_fn=lambda s: self._save_session(s, storage),
                )
        except Exception as exc:
            log.error(
                f"[MMMX][{self.session_id[:8]}] Profit booking step error: {exc}"
            )

        # -- 5d. Hedger tick (Phase 7) -----------------------------------------
        # Execute scheduled hedges; update hedge P&L
        try:
            from . import mmmx_hedger as _hedger
            from .mmmx_executor import get_executor as _get_executor_hedge
            from .mmmx_audit_log import get_audit_log as _get_audit_hedge
            _executed_hedges = await _hedger.tick(
                session=session,
                executor=_get_executor_hedge(),
                audit=_get_audit_hedge(),
            )
            if _executed_hedges:
                log.info(
                    f"[MMMX][{self.session_id[:8]}] "
                    f"Hedger: {len(_executed_hedges)} hedge(s) executed this beat."
                )
            # Update unrealised P&L on all active hedges using live quotes
            _live_quotes = session.get('live_quotes', {})
            if _live_quotes:
                _hedger.update_hedge_pnl(session, _live_quotes)
        except Exception as exc:
            log.error(
                f"[MMMX][{self.session_id[:8]}] Hedger tick error: {exc}"
            )

        # -- 6. Emit heartbeat + save ------------------------------------------
        now = datetime.now(timezone.utc).isoformat()
        session['beat_number'] = session.get('beat_number', 0) + 1
        session['_last_beat_at'] = now
        session['_integrity'] = build_integrity_signature(session, source='heartbeat')

        try:
            emit_heartbeat(
                session_id=self.session_id,
                beat_number=session['beat_number'],
                status=session.get('status', 'PAUSED'),
                portfolio_pnl=session.get('portfolio_pnl', 0.0),
                portfolio_delta=session.get('portfolio_delta', 0.0),
                hard_stop_usd=session.get('hard_stop_usd', 0.0),
                tranches_deployed=session.get('tranches_deployed', 0),
                tranches_remaining=session.get('tranches_remaining', 10),
                total_premium_collected=session.get('total_premium_collected', 0.0),
                active_hedges=session.get('active_hedges', 0),
                whipsaw_score=session.get('_whipsaw_score', 0),
                extra={'integrity': session.get('_integrity')},
            )
        except Exception as exc:
            log.error(f"[MMMX][{self.session_id[:8]}] emit_heartbeat failed: {exc}")

        saved = self._save_session(session, storage)
        if not saved:
            self._stale_abort_gen = self._my_generation
            self._running = False
            return

        try:
            log_activity(
                event_type='heartbeat_complete',
                message=f"Beat #{session['beat_number']} complete (gen={self._my_generation})",
                session_id=self.session_id,
            )
        except Exception:
            pass

    async def _dispatch_close_all(self, session: dict, reason: str) -> None:
        """
        Phase 4: Delegates to mmmx_close_all.close_all() for production-grade close.

        After close_all completes:
          - Logs G36 slippage (HARD_STOP only): actual P&L vs trigger threshold.
          - Saves session (generation-checked); sets _stale_abort_gen if save rejected.
          - Sets _running = False unconditionally.
        """
        from .mmmx_close_all import close_all
        from .mmmx_executor import get_executor
        from .mmmx_audit_log import get_audit_log
        from .mmmx_storage import get_storage

        log.critical(
            f"[MMMX][{self.session_id[:8]}] _dispatch_close_all: trigger={reason}"
        )

        executor = get_executor()
        audit = get_audit_log()
        storage = get_storage()

        report = await close_all(session, reason, executor, audit)

        # G36: Log slippage reality after hard stop so operator can see the gap risk
        if reason == 'HARD_STOP':
            actual_pnl = session.get('portfolio_pnl', 0.0)
            trigger_usd = session.get('hard_stop_usd', 0.0)
            # overshoot: negative means we lost more than the trigger threshold
            overshoot = actual_pnl + trigger_usd
            log.warning(
                f"[G36] Hard stop slippage: "
                f"trigger=-{trigger_usd:.2f}, "
                f"actual={actual_pnl:.2f}, "
                f"overshoot={overshoot:.2f} "
                f"({'worse than trigger' if overshoot < 0 else 'within trigger'})"
            )

        saved = self._save_session(session, storage)
        if not saved:
            log.error(
                f"[MMMX][{self.session_id[:8]}] "
                "Failed to save COMPLETE state after _dispatch_close_all"
            )
            self._stale_abort_gen = self._my_generation

        self._running = False

    def _save_session(self, session: dict, storage=None) -> bool:
        """
        Generation-checked session save.

        Returns True on success, False if GenerationConflict (stale monitor detected).
        Callers MUST check the return value per CLAUDE.md §4.
        """
        from .mmmx_storage import get_storage as _get_storage, GenerationConflict

        if storage is None:
            storage = _get_storage()

        try:
            storage.save_session(session, expected_gen=self._my_generation)
            return True
        except GenerationConflict as exc:
            log.error(
                f"[MMMX][{self.session_id[:8]}] _save_session blocked (generation conflict): {exc}"
            )
            return False
        except Exception as exc:
            log.error(
                f"[MMMX][{self.session_id[:8]}] _save_session failed: {exc}"
            )
            return False


# -- Public API ----------------------------------------------------------------

def start_session_monitor(session_id: str) -> MMMXMonitor:
    """
    Start a new monitor for session_id.

    Guard Layer 1: If an existing monitor is running, calls stop() and joins
    for up to 15 seconds before spawning the new one. This prevents two monitors
    from running concurrently for the same session.

    Always bumps the generation counter before spawning.

    Returns the new MMMXMonitor instance.
    """
    from .mmmx_storage import get_storage

    storage = get_storage()

    with _monitors_lock:
        existing = _mmmx_monitors.get(session_id)
        if existing is not None and existing.is_alive():
            log.info(
                f"[MMMX][{session_id[:8]}] Stopping existing monitor "
                f"(gen={existing._my_generation}) before spawning new one."
            )
            existing.stop(reason='replaced by new monitor')
            # Layer 1: Wait up to 15s for old thread to exit
            existing._thread.join(timeout=15.0)
            if existing.is_alive():
                log.error(
                    f"[MMMX][{session_id[:8]}] Old monitor did not exit within 15s! "
                    "Proceeding anyway — stale monitor self-stop will fire on its next beat."
                )

        # Bump generation BEFORE spawning (atomic DB write)
        new_gen = storage.bump_generation(session_id)
        log.info(
            f"[MMMX][{session_id[:8]}] Generation bumped to {new_gen}."
        )

        monitor = MMMXMonitor(session_id=session_id, my_generation=new_gen)
        _mmmx_monitors[session_id] = monitor

    monitor.start()

    # Phase 7: also start the Premium Listener (same generation)
    try:
        from .mmmx_premium_listener import start_session_listener
        from .mmmx_executor import get_executor as _get_exec_for_listener
        start_session_listener(
            session_id=session_id,
            my_generation=new_gen,
            executor=_get_exec_for_listener(),
        )
    except Exception as _listener_exc:
        log.warning(
            f"[MMMX][{session_id[:8]}] Could not start Premium Listener: {_listener_exc}"
        )

    return monitor


def stop_session_monitor(session_id: str, reason: str = 'requested') -> None:
    """Stop the monitor for session_id (if running). Also stops the listener."""
    with _monitors_lock:
        monitor = _mmmx_monitors.get(session_id)

    if monitor is None:
        log.debug(f"[MMMX][{session_id[:8]}] stop_session_monitor: no monitor found.")
        return

    monitor.stop(reason=reason)

    # Also stop the listener
    try:
        from .mmmx_premium_listener import stop_session_listener
        stop_session_listener(session_id)
    except Exception:
        pass


def get_monitor(session_id: str) -> Optional[MMMXMonitor]:
    """Return the current monitor for session_id, or None."""
    with _monitors_lock:
        return _mmmx_monitors.get(session_id)


def get_all_monitors() -> Dict[str, MMMXMonitor]:
    """Return a snapshot of all registered monitors."""
    with _monitors_lock:
        return dict(_mmmx_monitors)


def get_storage():
    """Local helper to avoid circular imports in nested calls."""
    from .mmmx_storage import get_storage as _gs
    return _gs()
