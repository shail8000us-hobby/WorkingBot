"""
SSDH Monitor — Heartbeat Orchestrator

Central controller for a running SSDH session.
Runs a heartbeat loop in a real OS thread (eventlet-safe).

CRITICAL: gunicorn uses worker_class=eventlet. threading.Thread is
monkey-patched into greenlets. asyncio event loops cannot run inside
greenlets. Use eventlet.patcher.original('threading').Thread to get
a genuine OS thread where asyncio.run() works cleanly.

Heartbeat steps (every adaptive interval, default 30s):
  1. Fetch premiums (4-layer fallback)
  2. Update premiums on positions
  3. Recompute P&L (atomic pair)
  4. Structure integrity check
  5. TTL-clear stale _being_closed flags (180s TTL)
  6. Safety checks (max_loss, margin, circuit breaker)
  7. Exit condition checks (time window, trailing stop, vega)
  8. Adaptive interval update
  9. Emit WebSocket state
  10. Persist session

Created: March 21, 2026
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from time import monotonic
from typing import Dict, Optional

log = logging.getLogger('ssdh_monitor')

_BEING_CLOSED_TTL = 180   # seconds — clear stale _being_closed flag after 3 min


class OPTMonitor:

    def __init__(self):
        self._session        = None
        self._session_id     = None
        self._running        = False
        self._session_lock   = threading.Lock()
        self._stop_event     = threading.Event()

        from .ssdh_engine     import OPTEngine
        from .ssdh_executor   import SSDHExecutor
        from .ssdh_entry      import AtomicEntryOrchestrator
        from .ssdh_safety     import SSDHSafety

        self._engine              = OPTEngine()
        self._executor            = SSDHExecutor()
        self._entry_orchestrator  = AtomicEntryOrchestrator()
        self._safety              = SSDHSafety()
        self._heartbeat_thread    = None
        self._current_interval    = 30
        self._last_good_premiums: Dict[str, float] = {}
        self._premium_cache:      Dict[str, float] = {}
        self._heartbeat_count     = 0

    # =========================================================================
    # Start / Stop
    # =========================================================================

    def start(self, session: dict) -> None:
        """
        Starts heartbeat in a real OS thread.
        MANDATORY: eventlet.patcher.original('threading').Thread
        """
        try:
            from eventlet.patcher import original as _ep_original
            RealThread = _ep_original('threading').Thread
        except (ImportError, AttributeError):
            RealThread = threading.Thread

        self._session    = session
        self._session_id = session['session_id']
        self._running    = True
        self._stop_event.clear()

        self._heartbeat_thread = RealThread(
            target    = self._run_heartbeat_loop,
            daemon    = True,
            name      = f'ssdh_heartbeat_{self._session_id}',
        )
        self._heartbeat_thread.start()
        log.warning("[%s] SSDH Monitor started (thread: %s)",
                    self._session_id, self._heartbeat_thread.name)

    def stop(self) -> None:
        """Signals heartbeat to stop. Non-blocking."""
        self._running = False
        self._stop_event.set()
        log.info("[%s] SSDH Monitor stop signalled", self._session_id)

    def get_session(self) -> Optional[dict]:
        """Thread-safe read of current session state (shallow copy)."""
        with self._session_lock:
            return dict(self._session) if self._session else None

    def is_running(self) -> bool:
        return self._running

    # =========================================================================
    # Heartbeat loop
    # =========================================================================

    def _run_heartbeat_loop(self) -> None:
        """Runs in real OS thread. Uses DefaultEventLoopPolicy to bypass eventlet."""
        try:
            loop = asyncio.DefaultEventLoopPolicy().new_event_loop()
            asyncio.set_event_loop(loop)
        except Exception as e:
            log.critical("[%s] Failed to create event loop: %s", self._session_id, e)
            return

        while self._running and not self._stop_event.is_set():
            beat_start = monotonic()
            try:
                loop.run_until_complete(self._single_heartbeat())
            except Exception as e:
                log.error("[%s] Heartbeat error: %s", self._session_id, e, exc_info=True)
                try:
                    from .ssdh_activity import log_activity
                    log_activity('heartbeat_error', str(e), self._session_id, 'error')
                except Exception:
                    pass

            elapsed = monotonic() - beat_start

            # Guardian: warn if heartbeat takes too long
            max_beat = int(
                (self._session or {}).get('params', {}).get('guardian_max_beat_sec', 90)
            )
            if elapsed > max_beat:
                log.warning("[%s] Heartbeat took %.1fs > max %ds",
                            self._session_id, elapsed, max_beat)

            sleep_for = max(0, self._current_interval - elapsed)
            self._stop_event.wait(timeout=sleep_for)

        try:
            loop.close()
        except Exception:
            pass
        log.info("[%s] Heartbeat loop exited", self._session_id)

    # =========================================================================
    # Single heartbeat
    # =========================================================================

    async def _single_heartbeat(self) -> None:
        from .ssdh_state import (
            persist_session, STATUS_WIND_DOWN, STATUS_CLOSED, STATUS_EMERGENCY,
            CLOSE_STRUCTURE, CLOSE_MAX_LOSS, CLOSE_TRAILING,
        )
        from .ssdh_activity import log_activity
        from .ssdh_integrity import check_structure_integrity
        from .ssdh_websocket import emit_state_update, emit_vega_spike

        with self._session_lock:
            session = self._session

        if not session:
            return

        sid = session['session_id']

        # Step 1: Fetch premiums (4-layer fallback)
        premium_map = await self._fetch_all_premiums(session)

        # Step 2: Update premiums on positions
        with self._session_lock:
            self._engine.update_premiums(session, premium_map)

        # Step 3: Recompute P&L (atomic pair)
        with self._session_lock:
            self._engine.compute_and_store_pnl(session)

        # Step 4: Structure integrity check
        ok, reason = check_structure_integrity(session)
        if not ok:
            session['_structure_ok'] = False
            try:
                from .ssdh_websocket import emit_structure_break
                emit_structure_break(sid, reason)
            except Exception:
                pass
            await self._trigger_exit(session, CLOSE_STRUCTURE, reason)
            return
        session['_structure_ok'] = True

        # Step 5: Clear stale _being_closed flags (180s TTL)
        self._clear_stale_being_closed(session)

        # Step 6: Safety checks
        max_loss_triggered, ml_reason = self._safety.check_max_loss(session)
        if max_loss_triggered:
            log_activity('max_loss_breach', ml_reason, sid, 'error')
            await self._trigger_exit(session, CLOSE_MAX_LOSS, ml_reason)
            return

        cb_ok, cb_reason = self._safety.check_circuit_breaker(session)
        if not cb_ok:
            log_activity('circuit_open', cb_reason, sid, 'warning')

        # Step 7: Exit condition checks (only when not already winding down)
        # NOTE: No time-based auto-exit — SSDH is a 2× hedged strategy with minimal theta
        # risk. Session runs to expiry or until the operator manually exits.
        if session.get('status') not in (STATUS_WIND_DOWN, STATUS_CLOSED, STATUS_EMERGENCY):
            trailing, tr_reason = self._safety.check_trailing_stop(session)
            if trailing:
                log_activity('trailing_stop', tr_reason, sid, 'warning')
                await self._trigger_exit(session, CLOSE_TRAILING, tr_reason)
                return

            vega_info = self._engine.compute_vega_indicator(session)
            if vega_info.get('spike_detected'):
                emit_vega_spike(sid, vega_info.get('ce_ratio', 0), vega_info.get('pe_ratio', 0))
                log_activity('vega_spike',
                    f"avg_ratio={vega_info['avg_ratio']:.2f}", sid, 'warning')
                if session['params'].get('vega_exit_auto'):
                    await self._trigger_exit(session, CLOSE_TRAILING, 'vega_spike')
                    return

        # Step 8: Adaptive interval
        self._current_interval = self._engine.compute_adaptive_interval(session)

        # Step 9: Emit WebSocket state
        try:
            emit_state_update(sid, session)
        except Exception as e:
            log.warning("[%s] emit_state_update failed: %s", sid, e)

        # Step 10: Persist session
        with self._session_lock:
            persist_session(session)

        # Step 11: Log heartbeat
        self._heartbeat_count += 1
        log_activity('heartbeat_pnl',
            f"net_pnl={session.get('net_pnl', 0):.4f} interval={self._current_interval}s",
            sid, 'info')

        # Periodic reconciliation (every 10 heartbeats)
        if self._heartbeat_count % 10 == 0:
            try:
                await self._run_reconciliation(session)
            except Exception as e:
                log.warning("[%s] Reconciliation error: %s", sid, e)

    # =========================================================================
    # Premium fetching — 4-layer fallback
    # =========================================================================

    async def _fetch_all_premiums(self, session: dict) -> Dict[str, Optional[float]]:
        """
        Returns {symbol: float | None} for every active leg.

        Layer 1: REST mark_price (primary — no WS in Phase 1)
        Layer 2: Per-symbol _premium_cache
        Layer 3: self._last_good_premiums[symbol]
        On ALL failing: return None (NEVER 0 — 0 is valid price for nearly worthless options)

        Write _last_good_premiums on every valid price.
        """
        from .ssdh_state import get_active_positions

        active  = get_active_positions(session)
        symbols = list({p.get('symbol') for p in active if p.get('symbol')})
        result  = {}

        if not symbols:
            return result

        # Try REST mark prices in parallel
        try:
            from .ssdh_executor import _create_rest_client
            client = _create_rest_client()
            try:
                tasks = {sym: self._fetch_mark_price(sym, client) for sym in symbols}
                fetched = await asyncio.gather(*[tasks[s] for s in symbols], return_exceptions=True)
                for sym, price in zip(symbols, fetched):
                    if isinstance(price, Exception) or price is None:
                        result[sym] = None
                    else:
                        result[sym] = float(price)
                        self._last_good_premiums[sym] = float(price)
                        self._premium_cache[sym] = float(price)
            finally:
                try:
                    await client.close()
                except Exception:
                    pass
        except Exception as e:
            log.warning("[%s] _fetch_all_premiums REST error: %s", session['session_id'], e)

        # Layer 2+3 fallback for any Nones
        for sym in symbols:
            if result.get(sym) is None:
                cached = self._premium_cache.get(sym)
                if cached is not None:
                    result[sym] = cached
                    log.debug("[%s] Using cache for %s", session['session_id'], sym)
                    continue
                last_good = self._last_good_premiums.get(sym)
                if last_good is not None:
                    result[sym] = last_good
                    try:
                        from .ssdh_activity import log_activity
                        log_activity('premium_stale', f"Using last_good for {sym}",
                            session['session_id'], 'warning')
                    except Exception:
                        pass
                    continue
                # All layers failed — return None (never 0)
                result[sym] = None
                try:
                    from .ssdh_activity import log_activity
                    log_activity('premium_fetch_failed', f"All fetch layers failed for {sym}",
                        session['session_id'], 'error')
                except Exception:
                    pass

        return result

    async def _fetch_mark_price(self, symbol: str, client) -> Optional[float]:
        """Fetch mark_price for one symbol. Returns None on error."""
        try:
            ticker = await client.get_ticker(symbol)
            if not ticker:
                return None
            price = float(ticker.get('mark_price', 0) or 0)
            if price <= 0:
                # Try mid from bid/ask
                bid = float(ticker.get('best_bid', 0) or 0)
                ask = float(ticker.get('best_ask', 0) or 0)
                if bid > 0 and ask > 0:
                    price = (bid + ask) / 2
            return price if price > 0 else None
        except Exception as e:
            log.debug("_fetch_mark_price %s: %s", symbol, e)
            return None

    # =========================================================================
    # Exit logic
    # =========================================================================

    async def _trigger_exit(self, session: dict, reason: str, detail: str) -> None:
        """
        Sets session status = WIND_DOWN, then calls exit sequence.
        Idempotent — if already winding down/closed/emergency, returns immediately.
        """
        from .ssdh_state import STATUS_WIND_DOWN, STATUS_CLOSED, STATUS_EMERGENCY, persist_session
        from .ssdh_activity import log_activity
        from .ssdh_websocket import emit_wind_down

        with self._session_lock:
            if session.get('status') in (STATUS_WIND_DOWN, STATUS_CLOSED, STATUS_EMERGENCY):
                return
            session['status']       = STATUS_WIND_DOWN
            session['close_reason'] = reason

        log_activity('wind_down_started', f'{reason}: {detail}', session['session_id'], 'warning')
        try:
            emit_wind_down(session['session_id'], reason)
        except Exception:
            pass

        await self._run_exit_sequence(session, reason)

    async def _run_exit_sequence(self, session: dict, reason: str) -> None:
        """
        Close all 4 legs in correct order:
        1. Close both SHORT legs in parallel (highest urgency — naked risk)
           - Aggressive limit (ask × 1.05)
           - Fallback to market if not filled
           - NEVER proceed until both shorts confirmed closed
        2. Close both LONG legs in parallel
           - Limit at bid × 0.97
           - Fallback to market
        3. Refresh P&L (atomic pair)
        4. Exchange verification
        5. Set CLOSED, emit session_closed, persist
        """
        from .ssdh_state import (
            get_positions_by_type, mark_position_closed,
            persist_session, recompute_net_pnl,
            DIR_SHORT, DIR_LONG, STATUS_CLOSED,
            POS_ACTIVE,
        )
        from .ssdh_activity import log_activity
        from .ssdh_websocket import emit_leg_close, emit_session_closed

        sid = session['session_id']

        def _get_symbol(pos: dict) -> str:
            return pos.get('symbol', '')

        async def _close_leg(pos: dict, aggressive: bool = True) -> Optional[dict]:
            """Mark being_closed, place close order, call mark_position_closed."""
            with self._session_lock:
                if pos.get('status') != POS_ACTIVE:
                    return None
                if pos.get('_being_closed'):
                    return None
                pos['_being_closed']    = True
                pos['_being_closed_at'] = str(monotonic())

            log_activity('leg_closing',
                f"{pos['direction'].upper()} {pos['side']} @ strike {pos['strike']:.0f}",
                sid, 'progress')

            symbol = _get_symbol(pos)
            result = await self._executor.close_position(
                position     = pos,
                session_id   = sid,
                reason       = reason,
                symbol       = symbol,
                aggressive   = aggressive,
                session_params = session['params'],
            )

            if result.get('success'):
                fees      = result.get('fees', 0.0)
                fill_prc  = result.get('fill_price', 0.0)
                with self._session_lock:
                    realized = mark_position_closed(
                        position               = pos,
                        close_premium          = fill_prc,
                        close_order_id         = result.get('order_id', ''),
                        close_client_order_id  = result.get('client_order_id', ''),
                        close_reason           = reason,
                        session                = session,
                        fees                   = fees,
                    )
                try:
                    emit_leg_close(sid, pos, realized)
                except Exception:
                    pass
                log_activity('leg_closed',
                    f"{pos['direction'].upper()} {pos['side']} closed @ {fill_prc:.2f}, realized={realized:.4f}",
                    sid, 'success')
                return result
            else:
                log_activity('leg_close_failed',
                    f"{pos['direction'].upper()} {pos['side']}: {result.get('error')}",
                    sid, 'error')
                with self._session_lock:
                    pos['_being_closed']    = False
                    pos['_being_closed_at'] = None
                return None

        # Phase 1: Close SHORT legs first (remove naked risk)
        short_ce = get_positions_by_type(session, DIR_SHORT, 'CE')
        short_pe = get_positions_by_type(session, DIR_SHORT, 'PE')
        all_shorts = [p for p in short_ce + short_pe if p.get('status') == POS_ACTIVE]

        if all_shorts:
            close_results = await asyncio.gather(
                *[_close_leg(p, aggressive=True) for p in all_shorts],
                return_exceptions=True,
            )
            # Verify all shorts closed before proceeding
            remaining_shorts = [p for p in all_shorts if p.get('status') == POS_ACTIVE]
            if remaining_shorts:
                log.error("[%s] Short leg(s) still open after close attempt — escalating to market", sid)
                await asyncio.gather(
                    *[self._executor.emergency_execute(p, sid, _get_symbol(p)) for p in remaining_shorts],
                    return_exceptions=True,
                )

        # Phase 2: Close LONG legs
        long_ce  = get_positions_by_type(session, DIR_LONG, 'CE')
        long_pe  = get_positions_by_type(session, DIR_LONG, 'PE')
        all_longs = [p for p in long_ce + long_pe if p.get('status') == POS_ACTIVE]

        if all_longs:
            await asyncio.gather(
                *[_close_leg(p, aggressive=False) for p in all_longs],
                return_exceptions=True,
            )

        # Phase 3: Refresh P&L atomic pair
        with self._session_lock:
            recompute_net_pnl(session)

        # Phase 4: Mark session closed
        now = datetime.now(timezone.utc).isoformat()
        with self._session_lock:
            session['status']     = STATUS_CLOSED
            session['closed_at']  = now
        persist_session(session)

        # Phase 5: Emit closed event
        try:
            emit_session_closed(sid, session)
        except Exception:
            pass

        log_activity('exit_complete',
            f"Session closed: reason={reason}, net_pnl={session.get('net_pnl', 0):.4f}",
            sid, 'success')

        self.stop()

    # =========================================================================
    # Utilities
    # =========================================================================

    def _clear_stale_being_closed(self, session: dict) -> None:
        """
        Auto-clears _being_closed flags older than _BEING_CLOSED_TTL seconds.
        Prevents permanent lock after crash.
        """
        now = monotonic()
        for pos in session.get('positions', []):
            if pos.get('_being_closed') and pos.get('_being_closed_at'):
                try:
                    age = now - float(pos['_being_closed_at'])
                    if age > _BEING_CLOSED_TTL:
                        pos['_being_closed']    = False
                        pos['_being_closed_at'] = None
                        log.warning("[%s] Cleared stale _being_closed on %s (age=%.0fs)",
                                    self._session_id, pos['pos_id'], age)
                except Exception:
                    pass

    async def _run_reconciliation(self, session: dict) -> None:
        """Periodic reconciliation — runs every 10 heartbeats."""
        try:
            from .ssdh_reconciler import reconcile_session
            from .ssdh_executor   import _create_rest_client

            client = _create_rest_client()
            try:
                result = await reconcile_session(session, client)
                if not result.get('ok'):
                    from .ssdh_activity import log_activity
                    log_activity('reconciliation_mismatch',
                        f"Mismatches: {result.get('mismatches', [])}",
                        session['session_id'], 'warning')
            finally:
                try:
                    await client.close()
                except Exception:
                    pass
        except Exception as e:
            log.warning("[%s] _run_reconciliation: %s", self._session_id, e)


# =============================================================================
# Global monitor registry
# =============================================================================

_monitors: Dict[str, OPTMonitor] = {}
_monitors_lock = threading.Lock()


def get_monitor(session_id: str) -> Optional[OPTMonitor]:
    with _monitors_lock:
        return _monitors.get(session_id)


def register_monitor(session_id: str, monitor: OPTMonitor) -> None:
    with _monitors_lock:
        _monitors[session_id] = monitor


def unregister_monitor(session_id: str) -> None:
    with _monitors_lock:
        _monitors.pop(session_id, None)
