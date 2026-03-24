"""
IC Monitor — Iron Condor Background Heartbeat Loop

Runs the continuous monitoring loop for an IC session:
  Phase 0: Safety gate
  Phase 1: Fetch market data
  Phase 2: Compute P&L + Greeks
  Phase 2.5: Expiry check
  Phase 3: Exit checks
  Phase 4: Entry check (if no active cycle)
  Phase 5: Breach detection
  Phase 6: Adjustment decision
  Phase 7: Emit & persist

From IC_ALGO_PLAN.md §6.

Created: 2026-03-24
"""

import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

from .ic_constants import (
    STATUS_RUNNING, STATUS_PAUSED, STATUS_STOPPED,
    STRATEGY_IDLE, STRATEGY_ACTIVE, STRATEGY_CYCLING, STRATEGY_EXIT_PENDING,
)
from .ic_engine import update_cycle_pnl
from .ic_greeks import compute_portfolio_greeks
from .ic_trigger import get_breach_status, should_use_rapid_check
from .ic_safety import run_safety_gate
from .ic_exit import check_exit_conditions, finalize_cycle_close
from .ic_adjuster import decide_adjustment, DECISION_NO_ACTION, DECISION_EXIT_CYCLE, DECISION_EMERGENCY_CLOSE
from .ic_cycle import should_open_new_cycle, should_wait_cycle_delay, prepare_new_cycle, transition_to_cycling
from .ic_state import reset_daily_loss
from .ic_storage import get_storage

log = logging.getLogger('ic_monitor')


class ICMonitor:
    """
    Background heartbeat monitor for a single IC session.

    Mirrors the MMMMonitor architecture:
    - Runs in a daemon thread
    - Respects PAUSED status
    - Persists state after every heartbeat
    - Handles all 7 phases per beat
    """

    def __init__(self, session_id: str, session: Dict):
        self.session_id = session_id
        self.session = session
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

    def start(self):
        """Start the heartbeat loop in a background thread."""
        if self._running:
            log.warning(f"[{self.session_id}] Monitor already running")
            return

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"ic_monitor_{self.session_id}",
            daemon=True,
        )
        self._thread.start()
        log.info(f"[{self.session_id}] IC Monitor started")

    def stop(self):
        """Stop the heartbeat loop."""
        self._stop_event.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        log.info(f"[{self.session_id}] IC Monitor stopped")

    def is_running(self) -> bool:
        return self._running and not self._stop_event.is_set()

    def _heartbeat_loop(self):
        """Main heartbeat loop — runs until stopped."""
        while not self._stop_event.is_set():
            try:
                # Skip if paused
                if self.session.get('status') == STATUS_PAUSED:
                    self._stop_event.wait(5)
                    continue

                # Skip if stopped
                if self.session.get('status') == STATUS_STOPPED:
                    break

                # Run one heartbeat
                start_time = time.time()
                self._run_heartbeat()
                elapsed = time.time() - start_time

                # Update heartbeat metadata
                self.session['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
                self.session['heartbeat_count'] = self.session.get('heartbeat_count', 0) + 1

                # Persist after every heartbeat
                self._persist()

                # Determine sleep interval
                interval = self._get_interval()
                remaining = max(0, interval - elapsed)

                self._stop_event.wait(remaining)

            except Exception as e:
                log.error(f"[{self.session_id}] Heartbeat error: {e}", exc_info=True)
                self._stop_event.wait(10)  # Back off on error

        self._running = False
        log.info(f"[{self.session_id}] Heartbeat loop exited")

    def _run_heartbeat(self):
        """Execute one complete heartbeat cycle (all 7 phases)."""
        session = self.session
        params = session.get('params', {})
        cycle = session.get('current_cycle')

        # Daily loss reset
        reset_daily_loss(session)

        # ─── Phase 0: Safety gate ─────────────────────────────────────
        is_blocked, safety_event = run_safety_gate(session, cycle)
        if is_blocked:
            if safety_event:
                self._record_safety_event(safety_event)
                log.warning(
                    f"[{self.session_id}] Safety gate blocked: "
                    f"{safety_event.get('message')}"
                )
            return

        # ─── Phase 1: Fetch market data ───────────────────────────────
        spot_price = self._fetch_spot_price()
        if spot_price and cycle:
            cycle['spot_price'] = spot_price
            self._update_leg_mark_prices(cycle)
            session['consecutive_fetch_failures'] = 0
        elif not spot_price:
            session['consecutive_fetch_failures'] = session.get('consecutive_fetch_failures', 0) + 1
            return  # Can't proceed without data

        # ─── Phase 2: Compute P&L + Greeks ─────────────────────────────
        if cycle and cycle.get('legs'):
            lots = params.get('lots', 10)
            update_cycle_pnl(cycle, lots)

            # Portfolio Greeks
            greeks = compute_portfolio_greeks(cycle['legs'], lots)
            cycle['portfolio_greeks'] = greeks

        # ─── Phase 2.5: Expiry check ──────────────────────────────────
        # TODO: Implement expiry detection from exchange data

        # ─── Phase 3: Exit checks ─────────────────────────────────────
        if cycle and session.get('strategy_status') == STRATEGY_ACTIVE:
            minutes_to_expiry = self._get_minutes_to_expiry()

            call_threatened, put_threatened, _ = get_breach_status(
                spot_price or 0,
                cycle.get('short_put_strike', 0),
                cycle.get('short_call_strike', 0),
                params.get('breach_pct', 5.0),
            ) if spot_price else (False, False, 'none')

            exit_reason = check_exit_conditions(
                cycle, params, minutes_to_expiry,
                call_threatened, put_threatened,
            )

            if exit_reason:
                self._execute_exit(exit_reason)
                return  # Exit was triggered — skip remaining phases

        # ─── Phase 4: Entry check ─────────────────────────────────────
        if should_open_new_cycle(session):
            if not should_wait_cycle_delay(session):
                self._execute_entry()
                return

        # ─── Phase 5: Breach detection ────────────────────────────────
        if cycle and session.get('strategy_status') == STRATEGY_ACTIVE and spot_price:
            call_threatened, put_threatened, breach_type = get_breach_status(
                spot_price,
                cycle.get('short_put_strike', 0),
                cycle.get('short_call_strike', 0),
                params.get('breach_pct', 5.0),
            )

            # ─── Phase 6: Adjustment decision ────────────────────────
            if breach_type != 'none':
                minutes_to_expiry = self._get_minutes_to_expiry()
                decision = decide_adjustment(
                    cycle, session,
                    call_threatened, put_threatened,
                    minutes_to_expiry,
                )

                if decision == DECISION_EXIT_CYCLE:
                    self._execute_exit('max_adjustments')
                elif decision == DECISION_EMERGENCY_CLOSE:
                    self._execute_exit('emergency_close')
                elif decision != DECISION_NO_ACTION:
                    self._execute_roll(decision, spot_price)

        # ─── Phase 7: Emit & persist (done after return) ──────────────

    def _get_interval(self) -> float:
        """Get the heartbeat interval (normal or rapid)."""
        params = self.session.get('params', {})
        cycle = self.session.get('current_cycle')

        if cycle and cycle.get('spot_price'):
            if should_use_rapid_check(
                cycle['spot_price'],
                cycle.get('short_put_strike', 0),
                cycle.get('short_call_strike', 0),
                params.get('breach_pct', 5.0),
            ):
                return params.get('rapid_check_interval', 15)

        return params.get('adjustment_interval', 60)

    def _fetch_spot_price(self) -> Optional[float]:
        """Fetch current BTC spot price. Override for real API integration."""
        # TODO: Integrate with existing Delta Exchange data feed
        return None

    def _update_leg_mark_prices(self, cycle: Dict):
        """Update mark prices for all legs from exchange data."""
        # TODO: Fetch live mark prices from exchange
        pass

    def _get_minutes_to_expiry(self) -> float:
        """Calculate minutes remaining until expiry."""
        # TODO: Compute from expiry date
        return 99999.0

    def _execute_entry(self):
        """Execute cycle entry (strike selection + order placement)."""
        prepare_new_cycle(self.session)
        # TODO: Call strike selector, then executor
        log.info(f"[{self.session_id}] Entry triggered (stub — needs implementation)")

    def _execute_exit(self, exit_reason: str):
        """Execute cycle exit (close all legs)."""
        cycle = self.session.get('current_cycle')
        if not cycle:
            return

        log.info(f"[{self.session_id}] Exiting cycle: reason={exit_reason}")

        # In simulate mode, use mark prices as close prices
        close_premiums = {}
        for leg_key, leg in cycle.get('legs', {}).items():
            if leg.get('status') == 'open':
                close_premiums[leg_key] = leg.get('mark_premium', 0)

        finalize_cycle_close(self.session, cycle, exit_reason, close_premiums)

        # Transition to cycling or idle
        if self.session.get('params', {}).get('auto_cycle', True):
            transition_to_cycling(self.session)
        else:
            from .ic_cycle import transition_to_idle
            transition_to_idle(self.session)

    def _execute_roll(self, decision: str, spot: float):
        """Execute a roll adjustment."""
        # TODO: Call ic_roller with appropriate parameters
        log.info(f"[{self.session_id}] Roll triggered: {decision} at spot={spot} (stub)")

    def _record_safety_event(self, event: Dict):
        """Record a safety event on the session."""
        if 'safety_events' not in self.session:
            self.session['safety_events'] = []
        self.session['safety_events'].append(event)
        # Keep last 50 events
        self.session['safety_events'] = self.session['safety_events'][-50:]

    def _persist(self):
        """Save session state to storage."""
        try:
            storage = get_storage()
            storage.save_session(self.session)
        except Exception as e:
            log.error(f"[{self.session_id}] Failed to persist: {e}")
