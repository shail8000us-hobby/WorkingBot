"""
MMMX Premium Listener — Real-Time WebSocket Subscriber + Tier-0 Circuit Breakers

Spec: MMMX_COMPLETE.md Section 5 (Listener), MMMX_IMPLEMENTATION_PLAN.md Phase 7.

Runs in its own daemon thread. Receives live bid/ask ticks for CE/PE strikes.
Evaluates 4 Tier-0 circuit breakers on every tick (~1–2 seconds).

Tier-0 CBs:
  CB_PREMIUM_JUMP    — leg premium jumps >50% vs entry_premium → force heartbeat
  CB_DELTA_BLOWOUT   — abs(portfolio_delta) > emergency_delta (0.70) → force heartbeat
  CB_IV_FLASH_SPIKE  — IV > iv_catastrophe_pct (80%) → force heartbeat
  CB_NEAR_ITM        — any position delta >= 0.72 → emergency 50% reduce + force heartbeat

Isolation rules:
  - Listener thread MUST NOT mutate session state except:
      session['live_quotes'], session['_force_check'], session['_listener_force_count']
  - CB_NEAR_ITM is the only exception (also modifies position state via executor)
  - ZERO imports from routes.mmm.* in this file

Generation guard:
  - Watchdog loop checks stored_gen vs _my_generation each cycle.
  - If stale: self-stop.

All timestamps: datetime.now(timezone.utc).isoformat() — never naive utcnow().
"""

import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

log = logging.getLogger('mmmx_premium_listener')

# ── Registry ───────────────────────────────────────────────────────────────────
# session_id -> PremiumListener. Written only by start_session_listener().
_mmmx_listeners: Dict[str, 'PremiumListener'] = {}
_listeners_lock = threading.RLock()   # RLock: allows re-entry from stop() inside start()

# Stale-WS watchdog threshold
_STALE_WS_SECS = 300  # 5 minutes

# CB_NEAR_ITM threshold (per spec)
_NEAR_ITM_DELTA_THRESHOLD = 0.72


class PremiumListener:
    """
    Real-time WebSocket listener for one MMMX session.

    Subscribes to live CE/PE bid/ask ticks, evaluates Tier-0 circuit breakers,
    and wakes the heartbeat monitor when danger is detected.

    Only mutates session keys: live_quotes, _force_check, _listener_force_count.
    CB_NEAR_ITM also mutates position state (via emergency_execute).
    """

    def __init__(self, session_id: str, my_generation: int, executor=None):
        self.session_id = session_id
        self._my_generation = my_generation
        self._executor = executor          # set via constructor or set_executor()
        self._running = False
        self._last_tick_at: Optional[datetime] = None
        self._subscribed_symbols: List[str] = []
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def set_executor(self, executor) -> None:
        """Attach an executor (needed for CB_NEAR_ITM emergency reduce)."""
        self._executor = executor

    # ── Subscription ──────────────────────────────────────────────────────────

    def subscribe(self, session: Dict[str, Any]) -> None:
        """
        Register symbols for active CE/PE legs. Initialise session fields.

        Does NOT connect to any WebSocket here — that is the responsibility
        of the WS-routing layer. This call just records which symbols this
        listener cares about and ensures session defaults exist.
        """
        symbols = []
        for tranche in session.get('tranches', []):
            if tranche.get('status') == 'ACTIVE':
                symbols.append(tranche['ce']['symbol'])
                symbols.append(tranche['pe']['symbol'])
        self._subscribed_symbols = list(set(symbols))

        session.setdefault('live_quotes', {})
        session.setdefault('_listener_force_count', 0)

        log.info(
            f"[MMMX][{self.session_id[:8]}] Listener subscribed to "
            f"{len(self._subscribed_symbols)} symbols"
        )

    # ── Tick handler ──────────────────────────────────────────────────────────

    async def on_tick(self, tick: Dict[str, Any], session: Dict[str, Any]) -> List[str]:
        """
        Called by the WS routing layer whenever a fresh tick arrives.

        Updates session['live_quotes'][symbol] and runs evaluate_cbs().
        Returns the list of CB names that fired.
        """
        symbol = tick.get('symbol')
        if symbol:
            session.setdefault('live_quotes', {})[symbol] = tick

        self._last_tick_at = datetime.now(timezone.utc)
        return await self.evaluate_cbs(tick, session)

    # ── Circuit breakers ──────────────────────────────────────────────────────

    async def evaluate_cbs(
        self, tick: Dict[str, Any], session: Dict[str, Any]
    ) -> List[str]:
        """
        Evaluate all 4 Tier-0 circuit breakers against the incoming tick.

        Returns a list of CB names that fired (may be empty).

        Permitted session mutations: _force_check, _listener_force_count.
        CB_NEAR_ITM additionally calls emergency_execute (executor must be set).
        """
        fired: List[str] = []
        params = session.get('params', {})

        symbol = tick.get('symbol', '')
        # Accept mark_price, mid, or bid as current premium
        current_premium = (
            tick.get('mark_price')
            or tick.get('mid')
            or tick.get('bid')
            or 0.0
        )
        tick_iv = tick.get('iv') or tick.get('iv_rank')

        # ── CB_PREMIUM_JUMP ────────────────────────────────────────────────
        # Leg premium jumps >50% vs its entry_premium → force heartbeat
        for tranche in session.get('tranches', []):
            if tranche.get('status') != 'ACTIVE':
                continue
            for side in ('ce', 'pe'):
                leg = tranche[side]
                if leg.get('symbol') != symbol:
                    continue
                entry_premium = leg.get('entry_premium', 0.0)
                if entry_premium > 0 and current_premium > 0:
                    jump_pct = (current_premium - entry_premium) / entry_premium * 100.0
                    if jump_pct > 50.0:
                        if 'CB_PREMIUM_JUMP' not in fired:
                            fired.append('CB_PREMIUM_JUMP')
                        self.force_heartbeat(session, 'CB_PREMIUM_JUMP')
                        log.warning(
                            f"[MMMX][{self.session_id[:8]}] CB_PREMIUM_JUMP: "
                            f"{symbol} premium {entry_premium:.1f}→{current_premium:.1f} "
                            f"({jump_pct:.1f}%)"
                        )

        # ── CB_DELTA_BLOWOUT ───────────────────────────────────────────────
        # abs(portfolio_delta) > emergency_delta (0.70)
        emergency_delta = float(params.get('emergency_delta', 0.70))
        portfolio_delta = session.get('portfolio_delta', 0.0)
        if abs(portfolio_delta) > emergency_delta:
            if 'CB_DELTA_BLOWOUT' not in fired:
                fired.append('CB_DELTA_BLOWOUT')
            self.force_heartbeat(session, 'CB_DELTA_BLOWOUT')
            log.warning(
                f"[MMMX][{self.session_id[:8]}] CB_DELTA_BLOWOUT: "
                f"portfolio_delta={portfolio_delta:.3f}, limit={emergency_delta}"
            )

        # ── CB_IV_FLASH_SPIKE ──────────────────────────────────────────────
        # IV > iv_catastrophe_pct (80%)
        iv_catastrophe = float(params.get('iv_catastrophe_pct', 80.0))
        if tick_iv is not None and float(tick_iv) > iv_catastrophe:
            if 'CB_IV_FLASH_SPIKE' not in fired:
                fired.append('CB_IV_FLASH_SPIKE')
            self.force_heartbeat(session, 'CB_IV_FLASH_SPIKE')
            log.warning(
                f"[MMMX][{self.session_id[:8]}] CB_IV_FLASH_SPIKE: "
                f"IV={tick_iv:.1f}%, limit={iv_catastrophe}"
            )

        # ── CB_NEAR_ITM ────────────────────────────────────────────────────
        # Any position delta >= 0.72 → emergency 50% reduce THEN force heartbeat
        # CB_NEAR_ITM is the ONLY CB that executes orders directly.
        near_itm_leg = None
        near_itm_tranche_id = None
        near_itm_side = None

        for tranche in session.get('tranches', []):
            if tranche.get('status') != 'ACTIVE':
                continue
            for side in ('ce', 'pe'):
                leg = tranche[side]
                current_delta = leg.get('current_delta')
                if current_delta is not None and abs(float(current_delta)) >= _NEAR_ITM_DELTA_THRESHOLD:
                    near_itm_leg = leg
                    near_itm_tranche_id = tranche.get('tranche_id')
                    near_itm_side = side
                    break
            if near_itm_leg:
                break

        if near_itm_leg is not None:
            if 'CB_NEAR_ITM' not in fired:
                fired.append('CB_NEAR_ITM')
            log.critical(
                f"[MMMX][{self.session_id[:8]}] CB_NEAR_ITM: "
                f"Tr{near_itm_tranche_id}/{near_itm_side} delta="
                f"{near_itm_leg.get('current_delta')}"
            )
            # Execute 50% emergency reduce BEFORE force-heartbeat
            if self._executor is not None:
                lots_to_reduce = max(1, near_itm_leg.get('lots', 2) // 2)
                try:
                    await self._executor.emergency_execute(
                        symbol=near_itm_leg['symbol'],
                        side='buy',
                        size=lots_to_reduce,
                        session_id=self.session_id,
                        tranche_id=near_itm_tranche_id,
                        action=f'CB_NEAR_ITM_REDUCE_Tr{near_itm_tranche_id}_{near_itm_side.upper()}',
                    )
                    log.info(
                        f"[MMMX][{self.session_id[:8]}] CB_NEAR_ITM: "
                        f"emergency reduce executed ({lots_to_reduce} lots)"
                    )
                except Exception as exc:
                    log.error(
                        f"[MMMX][{self.session_id[:8]}] CB_NEAR_ITM emergency_execute failed: {exc}"
                    )
            else:
                log.error(
                    f"[MMMX][{self.session_id[:8]}] CB_NEAR_ITM: no executor — cannot reduce!"
                )
            # Always force heartbeat after CB_NEAR_ITM, even if reduce failed
            self.force_heartbeat(session, 'CB_NEAR_ITM')

        return fired

    # ── Force heartbeat ────────────────────────────────────────────────────────

    def force_heartbeat(self, session: Dict[str, Any], reason: str) -> None:
        """
        Set session['_force_check'] = True and increment _listener_force_count.
        Also signals the monitor's in-memory wake event so it wakes from sleep.

        Permitted session mutations: _force_check, _listener_force_count.
        """
        session['_force_check'] = True
        session['_listener_force_count'] = session.get('_listener_force_count', 0) + 1
        log.info(
            f"[MMMX][{self.session_id[:8]}] force_heartbeat: {reason} "
            f"(count={session['_listener_force_count']})"
        )
        # Signal the in-memory wake event on the monitor (lazy import to avoid circular)
        try:
            from .mmmx_monitor import get_monitor
            monitor = get_monitor(self.session_id)
            if monitor is not None:
                monitor.signal_force_check()
        except Exception as exc:
            log.debug(f"[MMMX] Could not signal monitor wake: {exc}")

    # ── Stale WS watchdog ──────────────────────────────────────────────────────

    def check_stale_ws(self, session: Dict[str, Any]) -> None:
        """
        5-minute watchdog. If no ticks received:
          - Force heartbeat + Telegram WARNING.
          - If monitor is ALSO stale (no beat for 5 min): Telegram CRITICAL.

        Called from the watchdog thread. Receives a freshly loaded session dict.
        """
        if self._last_tick_at is None:
            return

        now = datetime.now(timezone.utc)
        age_secs = (now - self._last_tick_at).total_seconds()

        if age_secs < _STALE_WS_SECS:
            return

        self.force_heartbeat(session, 'stale_ws')

        # Check if monitor is also stale
        monitor_stale = False
        last_beat_raw = session.get('_last_beat_at')
        if last_beat_raw:
            try:
                last_beat_dt = datetime.fromisoformat(last_beat_raw)
                if last_beat_dt.tzinfo is None:
                    last_beat_dt = last_beat_dt.replace(tzinfo=timezone.utc)
                if (now - last_beat_dt).total_seconds() >= _STALE_WS_SECS:
                    monitor_stale = True
            except Exception:
                pass

        try:
            from .mmmx_telegram import send_alert
            if monitor_stale:
                send_alert(
                    f"🚨 CRITICAL: WS stale ({age_secs / 60:.1f}m) AND monitor stale. "
                    "No ticks AND no heartbeat. Positions are EXPOSED.",
                    alert_type='ws_and_monitor_stale',
                    session_id=self.session_id,
                    dedup_ttl=300,
                )
                log.critical(
                    f"[MMMX][{self.session_id[:8]}] WS AND monitor both stale ({age_secs/60:.1f}m)"
                )
            else:
                send_alert(
                    f"⚠️ WARNING: Premium listener — no ticks for {age_secs / 60:.1f} min.",
                    alert_type='ws_stale',
                    session_id=self.session_id,
                    dedup_ttl=300,
                )
                log.warning(
                    f"[MMMX][{self.session_id[:8]}] WS stale ({age_secs/60:.1f}m)"
                )
        except Exception as exc:
            log.error(f"[MMMX] Stale-WS telegram failed: {exc}")

    # ── Thread lifecycle ───────────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            log.warning(
                f"[MMMX][{self.session_id[:8]}] Listener start() called while thread alive — ignoring"
            )
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watchdog_loop,
            name=f"mmmx_listener_{self.session_id[:8]}_gen{self._my_generation}",
            daemon=True,
        )
        self._thread.start()
        log.info(
            f"[MMMX][{self.session_id[:8]}] Listener gen={self._my_generation} started."
        )

    def stop(self) -> None:
        """Signal the watchdog thread to stop and remove from registry."""
        self._running = False
        self._stop_event.set()
        log.info(
            f"[MMMX][{self.session_id[:8]}] Listener gen={self._my_generation} stop requested."
        )
        # Remove from registry
        with _listeners_lock:
            _mmmx_listeners.pop(self.session_id, None)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── Watchdog loop ──────────────────────────────────────────────────────────

    def _watchdog_loop(self) -> None:
        """Background thread: runs stale-WS check every 60 seconds."""
        WATCHDOG_INTERVAL = 60.0

        log.info(
            f"[MMMX][{self.session_id[:8]}] Listener watchdog started gen={self._my_generation}"
        )

        while self._running and not self._stop_event.is_set():
            self._stop_event.wait(timeout=WATCHDOG_INTERVAL)
            if not self._running:
                break

            try:
                self._run_watchdog_tick()
            except Exception as exc:
                log.error(
                    f"[MMMX][{self.session_id[:8]}] Listener watchdog error: {exc}"
                )

        log.info(
            f"[MMMX][{self.session_id[:8]}] Listener watchdog exited gen={self._my_generation}"
        )

    def _run_watchdog_tick(self) -> None:
        """Single watchdog iteration: generation check + stale-WS check."""
        from .mmmx_storage import get_storage

        storage = get_storage()

        # Generation check — same pattern as monitor layer 2
        stored_gen = storage.get_generation(self.session_id)
        if stored_gen > self._my_generation:
            log.info(
                f"[MMMX][{self.session_id[:8]}] Listener gen stale "
                f"(my={self._my_generation}, stored={stored_gen}) — stopping."
            )
            self._running = False
            return

        session = storage.load_session(self.session_id)
        if session is None:
            return

        self.check_stale_ws(session)


# ── Public API ─────────────────────────────────────────────────────────────────

def start_session_listener(
    session_id: str,
    my_generation: int,
    executor=None,
) -> 'PremiumListener':
    """
    Start a new PremiumListener for session_id.

    Stops any existing listener for the same session first.
    Returns the new PremiumListener instance.
    """
    with _listeners_lock:
        existing = _mmmx_listeners.get(session_id)
        if existing is not None and existing.is_alive():
            log.info(
                f"[MMMX][{session_id[:8]}] Stopping existing listener "
                f"(gen={existing._my_generation}) before spawning new one."
            )
            existing.stop()

        listener = PremiumListener(
            session_id=session_id,
            my_generation=my_generation,
            executor=executor,
        )
        _mmmx_listeners[session_id] = listener

    listener.start()
    return listener


def stop_session_listener(session_id: str) -> None:
    """Stop the listener for session_id (if running)."""
    with _listeners_lock:
        listener = _mmmx_listeners.get(session_id)

    if listener is None:
        log.debug(f"[MMMX][{session_id[:8]}] stop_session_listener: no listener found.")
        return

    listener.stop()


def get_listener(session_id: str) -> Optional['PremiumListener']:
    """Return the current listener for session_id, or None."""
    with _listeners_lock:
        return _mmmx_listeners.get(session_id)
