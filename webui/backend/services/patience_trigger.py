"""
Patience Trigger Engine — daemon thread.

Monitors ARMED cards against live BTC price + IV conditions.
One card executes at a time (priority: earliest created_at).

Trigger types:
  TOUCH:       abs(current - trigger) <= tolerance
  CROSS_UP:    previous < trigger AND current >= trigger
  CROSS_DOWN:  previous > trigger AND current <= trigger
  SUSTAIN:     price beyond trigger for sustain_minutes (resets on revert)

Price feed:
  delta_price_websocket.get_price_websocket().get_price('BTC')
  Stale > 30s → pause all monitoring, Telegram alert

IV gate (Phase 2 — stubs return True in Phase 1):
  patience_iv.get_current_iv_percentile() → compared against card gate

Created: March 14, 2026
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)

# Eventlet-safe real OS thread (see lessons.md — eventlet asyncio conflict)
try:
    from eventlet.patcher import original as _ep_original
    _RealThread = _ep_original('threading').Thread
except (ImportError, AttributeError):
    _RealThread = threading.Thread

POLL_INTERVAL = 1.0       # seconds between trigger evaluations
STALE_THRESHOLD = 30      # seconds — if price older, pause monitoring


class PatienceTrigger:
    """
    Daemon trigger engine. Started once by init_patience() in app startup.
    Monitors ARMED cards, fires execution when conditions met.
    """

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # State
        self._prev_price: Optional[float] = None
        self._feed_paused = False
        self._last_price_time: Optional[float] = None

        # Sustain tracking: card_id → first_time_in_zone
        self._sustain_tracker: dict = {}

        # Cards already triggered this session (prevent duplicate TRIGGER_HIT logs for TOUCH)
        self._triggered_cards: set = set()

        # Execution queue (priority: created_at ASC)
        self._executing_card_id: Optional[str] = None
        self._execution_queue: list = []
        self._exec_lock = threading.Lock()

        log.info("PatienceTrigger: initialized")

    # ── Start / Stop ──────────────────────────────────────────────────

    def start(self):
        """Start the trigger daemon. Called once at app startup."""
        if self._running:
            return
        self._running = True
        self._recover_on_startup()

        self._thread = _RealThread(
            target=self._run,
            daemon=True,
            name="patience-trigger",
        )
        self._thread.start()
        log.info("PatienceTrigger: daemon started")

    def stop(self):
        self._running = False
        log.info("PatienceTrigger: stop requested")

    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    # ── Startup recovery ──────────────────────────────────────────────

    def _recover_on_startup(self):
        """Recover cards that were in-flight when server restarted."""
        try:
            from webui.backend.routes.patience.patience_models import get_db
            db = get_db()

            # Cards stuck EXECUTING → PAUSED (loop was lost in restart)
            executing = db.get_cards_by_status('EXECUTING')
            for card in executing:
                db.update_card(card['card_id'], status='PAUSED')
                db.log_event(
                    card['card_id'], None, 'PAUSE',
                    'Server restart: execution state lost — resume manually'
                )
                try:
                    from webui.backend.routes.options.options_notifier import get_options_notifier
                    get_options_notifier().send(
                        f"Patience: [{card.get('card_name', card['card_id'])}] "
                        f"was EXECUTING on restart — PAUSED. Resume in Web UI."
                    )
                except Exception:
                    pass
                log.warning(
                    f"PatienceTrigger: [{card.get('card_name')}] was EXECUTING on restart → PAUSED"
                )

            # Cards stuck TRIGGERED → back to ARMED (re-evaluate)
            triggered = db.get_cards_by_status('TRIGGERED')
            for card in triggered:
                db.update_card(card['card_id'], status='ARMED')
                log.info(
                    f"PatienceTrigger: [{card.get('card_name')}] was TRIGGERED on restart → ARMED"
                )

        except Exception as e:
            log.error(f"PatienceTrigger: startup recovery failed: {e}", exc_info=True)

    # ── Main loop ─────────────────────────────────────────────────────

    def _run(self):
        """Main trigger evaluation loop. Runs every POLL_INTERVAL seconds."""
        from webui.backend.routes.patience.patience_models import get_db
        from webui.backend.services.delta_price_websocket import get_price_websocket

        while self._running:
            try:
                # ── Get price ──
                ws = get_price_websocket()
                current_price = ws.get_price('BTC')
                now_ts = time.time()

                # ── Stale / feed disconnect check ──
                if current_price is None or not ws.is_connected():
                    if not self._feed_paused:
                        self._feed_paused = True
                        self._prev_price = None
                        log.warning("PatienceTrigger: price feed disconnected — pausing monitoring")
                        self._notify("Patience: Price feed disconnected. Monitoring paused.")
                    time.sleep(POLL_INTERVAL)
                    continue

                # Check if price is stale (connected socket but no updates)
                price_ts = getattr(ws, 'get_price_timestamp', lambda _: None)('BTC')
                if price_ts and (now_ts - price_ts) > STALE_THRESHOLD:
                    if not self._feed_paused:
                        self._feed_paused = True
                        self._prev_price = None
                        log.warning(
                            f"PatienceTrigger: price stale ({now_ts - price_ts:.0f}s old) "
                            f"— pausing monitoring"
                        )
                        self._notify("Patience: BTC price stale (>30s). Monitoring paused.")
                    time.sleep(POLL_INTERVAL)
                    continue

                if self._feed_paused:
                    self._feed_paused = False
                    log.info("PatienceTrigger: price feed recovered — resuming monitoring")
                    self._notify("Patience: Price feed recovered. Monitoring resumed.")

                self._last_price_time = now_ts
                db = get_db()

                # ── WAITING → ARMED (parent completed) ──
                waiting = db.get_cards_by_status('WAITING')
                for card in waiting:
                    parent_id = card.get('parent_card_id')
                    if parent_id:
                        parent = db.get_card(parent_id)
                        if parent and parent.get('status') == 'COMPLETED':
                            db.update_card(card['card_id'], status='ARMED')
                            log.info(
                                f"PatienceTrigger: [{card.get('card_name')}] "
                                f"WAITING → ARMED (parent completed)"
                            )

                # ── Evaluate ARMED cards ──
                armed = db.get_cards_by_status('ARMED')
                for card in armed:
                    card_id = card['card_id']
                    # Skip cards already triggered (prevents TOUCH duplicate logging)
                    if card_id in self._triggered_cards:
                        continue
                    if self._evaluate_trigger(card, current_price, self._prev_price):
                        # Price trigger met — check IV gate
                        if not self._check_iv_gate(card):
                            # IV gate blocked — already logged in _check_iv_gate
                            continue
                        # All conditions met — queue for execution
                        self._triggered_cards.add(card_id)
                        self._queue_for_execution(card)

                self._prev_price = current_price

            except Exception as e:
                log.error(f"PatienceTrigger: loop error: {e}", exc_info=True)

            time.sleep(POLL_INTERVAL)

    # ── Trigger evaluation ────────────────────────────────────────────

    def _evaluate_trigger(self, card: dict, current: float,
                          prev: Optional[float]) -> bool:
        """Returns True if this card's price trigger condition is met."""
        card_id = card['card_id']
        t = float(card.get('trigger_price', 0))
        tol = float(card.get('trigger_tolerance', 50))
        typ = card.get('trigger_type', 'CROSS_UP')

        if typ == 'TOUCH':
            hit = abs(current - t) <= tol
            return hit

        elif typ == 'CROSS_UP':
            if prev is None:
                return False
            return prev < t and current >= t

        elif typ == 'CROSS_DOWN':
            if prev is None:
                return False
            return prev > t and current <= t

        elif typ == 'SUSTAIN':
            sustain_mins = int(card.get('sustain_minutes') or 0)
            if sustain_mins <= 0:
                return False

            # Direction: UP (default) = price >= trigger, DOWN = price <= trigger
            sustain_dir = card.get('sustain_direction', 'UP').upper()
            in_zone = current <= t if sustain_dir == 'DOWN' else current >= t

            if in_zone:
                if card_id not in self._sustain_tracker:
                    self._sustain_tracker[card_id] = time.time()
                elapsed = time.time() - self._sustain_tracker[card_id]
                if elapsed >= sustain_mins * 60:
                    return True
            else:
                # Reverted — reset tracker
                self._sustain_tracker.pop(card_id, None)
            return False

        else:
            log.warning(f"PatienceTrigger: unknown trigger_type '{typ}' for card {card_id}")
            return False

    # ── IV gate ───────────────────────────────────────────────────────

    def _check_iv_gate(self, card: dict) -> bool:
        """
        Check card's IV percentile gate against current Deribit DVOL percentile.
        Returns True if IV conditions are met (or no gate is set).
        Fails open if IV data unavailable — never blocks on data absence.
        """
        iv_min = card.get('iv_percentile_min')
        iv_max = card.get('iv_percentile_max')

        if iv_min is None and iv_max is None:
            return True  # No IV gate set — pass through

        # Get current IV percentile
        try:
            from webui.backend.services.patience_iv import get_current_iv_percentile
            lookback = int(card.get('iv_lookback_days') or 30)
            current_pct = get_current_iv_percentile(lookback_days=lookback)
        except Exception as e:
            log.warning(f"PatienceTrigger: IV percentile fetch failed ({e}) — failing open")
            return True  # fail open

        if current_pct is None:
            log.info("PatienceTrigger: IV percentile unavailable — failing open")
            return True  # fail open — no data yet

        # Check gates
        if iv_min is not None and current_pct < float(iv_min):
            self._notify(
                f"Patience: [{card.get('card_name')}] price triggered but IV at "
                f"{current_pct}% — waiting for ≥ {iv_min}% (credit strategy gate)"
            )
            log.info(
                f"PatienceTrigger: [{card.get('card_name')}] IV_BLOCKED "
                f"— current={current_pct}% < min={iv_min}%"
            )
            # Log to DB
            try:
                from webui.backend.routes.patience.patience_models import get_db
                get_db().log_event(
                    card['card_id'], None, 'IV_BLOCKED',
                    f"IV at {current_pct}% below min {iv_min}%",
                    {'current_pct': current_pct, 'required_min': iv_min}
                )
            except Exception:
                pass
            return False

        if iv_max is not None and current_pct > float(iv_max):
            self._notify(
                f"Patience: [{card.get('card_name')}] price triggered but IV at "
                f"{current_pct}% — waiting for ≤ {iv_max}% (debit strategy gate)"
            )
            log.info(
                f"PatienceTrigger: [{card.get('card_name')}] IV_BLOCKED "
                f"— current={current_pct}% > max={iv_max}%"
            )
            try:
                from webui.backend.routes.patience.patience_models import get_db
                get_db().log_event(
                    card['card_id'], None, 'IV_BLOCKED',
                    f"IV at {current_pct}% above max {iv_max}%",
                    {'current_pct': current_pct, 'required_max': iv_max}
                )
            except Exception:
                pass
            return False

        log.info(
            f"PatienceTrigger: [{card.get('card_name')}] IV gate passed "
            f"— current={current_pct}% (min={iv_min}, max={iv_max})"
        )
        return True

    # ── Execution queue ───────────────────────────────────────────────

    def _queue_for_execution(self, card: dict):
        """Queue card for execution. One card at a time, priority by created_at."""
        from webui.backend.routes.patience.patience_models import get_db
        from webui.backend.services.patience_executor import execute_card

        db = get_db()
        card_id = card['card_id']
        card_name = card.get('card_name', card_id)

        with self._exec_lock:
            # Already in queue or executing?
            if card_id == self._executing_card_id:
                return
            if any(c['card_id'] == card_id for c in self._execution_queue):
                return

            # Mark TRIGGERED in DB
            db.update_card(card_id, status='TRIGGERED')
            db.log_event(card_id, None, 'TRIGGER_HIT',
                         f"Trigger condition met, queued for execution")

            if self._executing_card_id is None:
                # Nothing executing — start immediately
                self._executing_card_id = card_id
                log.info(f"PatienceTrigger: [{card_name}] executing immediately")
                self._start_execution_thread(card_id)
            else:
                # Queue it (sorted by created_at)
                self._execution_queue.append(card)
                self._execution_queue.sort(key=lambda c: c.get('created_at', ''))
                log.info(
                    f"PatienceTrigger: [{card_name}] queued "
                    f"(position {len(self._execution_queue)}, "
                    f"waiting for {self._executing_card_id})"
                )

    def _start_execution_thread(self, card_id: str):
        """Start execute_card in a real OS thread (it's synchronous but blocking)."""
        from webui.backend.services.patience_executor import execute_card

        t = _RealThread(
            target=execute_card,
            args=(card_id,),
            daemon=True,
            name=f"patience-exec-{card_id[:8]}",
        )
        t.start()

    def _on_execution_done(self, finished_card_id: str):
        """Called by executor when card completes or pauses. Advance the queue."""
        # Clean up tracking state for finished card
        self._sustain_tracker.pop(finished_card_id, None)
        self._triggered_cards.discard(finished_card_id)

        with self._exec_lock:
            if self._executing_card_id == finished_card_id:
                self._executing_card_id = None

            if self._execution_queue:
                next_card = self._execution_queue.pop(0)
                next_id = next_card['card_id']
                self._executing_card_id = next_id
                log.info(
                    f"PatienceTrigger: advancing queue → "
                    f"[{next_card.get('card_name', next_id)}]"
                )
                self._start_execution_thread(next_id)

    # ── Kill switch ───────────────────────────────────────────────────

    def kill_switch(self) -> int:
        """Cancel all ARMED + WAITING + TRIGGERED cards. Returns count cancelled."""
        from webui.backend.routes.patience.patience_models import get_db
        db = get_db()

        # Clear execution queue and tracking state
        with self._exec_lock:
            self._execution_queue.clear()
        self._sustain_tracker.clear()
        self._triggered_cards.clear()

        cancelled = 0
        for card in db.get_cards_by_status('ARMED', 'WAITING', 'TRIGGERED'):
            db.update_card(card['card_id'], status='CANCELLED')
            db.log_event(card['card_id'], None, 'PAUSE', 'Kill switch activated')
            cancelled += 1

        log.warning(f"PatienceTrigger: KILL SWITCH — {cancelled} cards cancelled")
        if cancelled > 0:
            self._notify(f"Patience KILL SWITCH activated. {cancelled} card(s) cancelled.")
        return cancelled

    # ── Status ────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        from webui.backend.routes.patience.patience_models import get_db
        from webui.backend.services.delta_price_websocket import get_price_websocket

        try:
            db = get_db()
            armed_count = len(db.get_cards_by_status('ARMED'))
            executing = len(db.get_cards_by_status('EXECUTING'))
            ws = get_price_websocket()
            btc_price = ws.get_price('BTC')
        except Exception:
            armed_count = executing = 0
            btc_price = None

        return {
            'running': self.is_running(),
            'feed_paused': self._feed_paused,
            'btc_price': btc_price,
            'prev_price': self._prev_price,
            'armed_count': armed_count,
            'executing_card_id': self._executing_card_id,
            'queue_length': len(self._execution_queue),
            'executing_count': executing,
        }

    # ── Helpers ───────────────────────────────────────────────────────

    def _notify(self, msg: str):
        try:
            from webui.backend.routes.options.options_notifier import get_options_notifier
            get_options_notifier().send(msg)
        except Exception as e:
            log.warning(f"PatienceTrigger: Telegram notify failed: {e}")


# ── Singleton ─────────────────────────────────────────────────────────

_trigger: Optional[PatienceTrigger] = None


def get_patience_trigger() -> PatienceTrigger:
    global _trigger
    if _trigger is None:
        _trigger = PatienceTrigger()
    return _trigger


def init_patience_trigger():
    """Called once at app startup to start the trigger daemon."""
    trigger = get_patience_trigger()
    if not trigger.is_running():
        trigger.start()
    return trigger
