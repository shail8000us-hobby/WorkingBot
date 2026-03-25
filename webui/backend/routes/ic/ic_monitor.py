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
Updated: 2026-03-24 — AUDIT: C2/C4/C6/L6 fixes
"""

import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

from .ic_constants import (
    STATUS_RUNNING, STATUS_PAUSED, STATUS_STOPPED,
    STRATEGY_IDLE, STRATEGY_ACTIVE, STRATEGY_CYCLING, STRATEGY_EXIT_PENDING,
    EXIT_MAX_ADJUSTMENTS, EXIT_EMERGENCY,
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
from .ic_websocket import (
    emit_heartbeat, emit_pnl_update, emit_breach_alert,
    emit_cycle_opened, emit_cycle_closed, emit_safety,
    emit_status_change,
)

log = logging.getLogger('ic_monitor')


class ICMonitor:
    """
    Background heartbeat monitor for a single IC session.

    Mirrors the MMMMonitor architecture:
    - Runs in a daemon thread
    - Respects PAUSED status
    - Persists state after every heartbeat
    - Handles all 7 phases per beat
    - AUDIT L6: Thread lock protects session state access
    """

    def __init__(self, session_id: str, session: Dict):
        self.session_id = session_id
        self.session = session
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        # AUDIT L6: Lock to protect session state between monitor and API threads
        self._session_lock = threading.Lock()
        # Exchange integration — lazy-loaded
        self._initializer = None
        self._chain_service = None

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

    # ─── Exchange Integration (AUDIT C2) ──────────────────────────────────────

    def _get_initializer(self):
        """Lazy-load the MMMInitializer for spot prices and chain data."""
        if self._initializer is None:
            try:
                from webui.backend.routes.mmm.mmm_initializer import MMMInitializer
                self._initializer = MMMInitializer()
            except ImportError:
                try:
                    import sys
                    import os
                    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                    if backend_root not in sys.path:
                        sys.path.insert(0, backend_root)
                    from webui.backend.routes.mmm.mmm_initializer import MMMInitializer
                    self._initializer = MMMInitializer()
                except Exception as e:
                    log.error(f"[{self.session_id}] Failed to load MMMInitializer: {e}")
        return self._initializer

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
                with self._session_lock:
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
                # AUDIT C4: Emit safety event to UI
                emit_safety(self.session_id, safety_event)
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
            if session['consecutive_fetch_failures'] <= 3:
                log.debug(f"[{self.session_id}] Spot price fetch failed ({session['consecutive_fetch_failures']})")
            else:
                log.warning(
                    f"[{self.session_id}] Spot price fetch failed "
                    f"{session['consecutive_fetch_failures']} consecutive times"
                )
            return  # Can't proceed without data

        # ─── Phase 2: Compute P&L + Greeks ─────────────────────────────
        if cycle and cycle.get('legs'):
            lots = params.get('lots', 10)
            update_cycle_pnl(cycle, lots)

            # Portfolio Greeks
            greeks = compute_portfolio_greeks(cycle['legs'], lots)
            cycle['portfolio_greeks'] = greeks

            # AUDIT C4: Emit P&L update to UI
            emit_pnl_update(
                session_id=self.session_id,
                unrealized_pnl=cycle.get('unrealized_pnl', 0),
                max_profit=cycle.get('max_profit_usd', 0),
                max_loss=cycle.get('max_loss_usd', 0),
                pnl_pct=cycle.get('pnl_as_pct_of_max_profit', 0),
                total_realized=session.get('total_realized_pnl', 0),
            )

        # ─── Phase 2.5: Expiry check ──────────────────────────────────
        # Handled via minutes_to_expiry in exit checks below

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

            # AUDIT C4: Emit breach alert to UI when a side is threatened
            if breach_type != 'none':
                short_strike = (
                    cycle.get('short_call_strike', 0) if call_threatened
                    else cycle.get('short_put_strike', 0)
                )
                from .ic_trigger import get_call_distance_pct, get_put_distance_pct
                dist_pct = (
                    get_call_distance_pct(spot_price, cycle.get('short_call_strike', 0))
                    if call_threatened
                    else get_put_distance_pct(spot_price, cycle.get('short_put_strike', 0))
                )
                emit_breach_alert(
                    session_id=self.session_id,
                    breach_type=breach_type,
                    spot=spot_price,
                    short_strike=short_strike,
                    distance_pct=dist_pct,
                )

            # ─── Phase 6: Adjustment decision ────────────────────────
            if breach_type != 'none':
                minutes_to_expiry = self._get_minutes_to_expiry()
                decision = decide_adjustment(
                    cycle, session,
                    call_threatened, put_threatened,
                    minutes_to_expiry,
                )

                # AUDIT C6: Use proper EXIT_* constants
                if decision == DECISION_EXIT_CYCLE:
                    self._execute_exit(EXIT_MAX_ADJUSTMENTS)
                elif decision == DECISION_EMERGENCY_CLOSE:
                    self._execute_exit(EXIT_EMERGENCY)
                elif decision != DECISION_NO_ACTION:
                    self._execute_roll(decision, spot_price)

        # ─── Phase 7: Emit heartbeat ──────────────────────────────────
        # AUDIT C4: Emit full heartbeat to UI
        if cycle:
            greeks_data = cycle.get('portfolio_greeks', {})
            emit_heartbeat(
                session_id=self.session_id,
                spot_price=spot_price or 0,
                unrealized_pnl=cycle.get('unrealized_pnl', 0),
                pnl_pct=cycle.get('pnl_as_pct_of_max_profit', 0),
                portfolio_greeks=greeks_data,
                cycle_data={
                    'cycle_id': cycle.get('cycle_id'),
                    'cycle_number': cycle.get('cycle_number'),
                    'short_put_strike': cycle.get('short_put_strike'),
                    'short_call_strike': cycle.get('short_call_strike'),
                    'entry_net_credit': cycle.get('entry_net_credit'),
                    'adjustment_count': cycle.get('adjustment_count', 0),
                    'spot_price': spot_price,
                },
                status=session.get('status', ''),
                strategy_status=session.get('strategy_status', ''),
            )

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

    # ─── Exchange Data Methods (AUDIT C2: Implemented) ────────────────────────

    def _fetch_spot_price(self) -> Optional[float]:
        """
        Fetch current BTC spot price from the exchange.

        AUDIT C2: Integrated with MMMInitializer.get_spot_price()
        which uses OptionsChainService → Delta Exchange API.
        """
        try:
            init = self._get_initializer()
            if init:
                price = init.get_spot_price('BTC')
                if price and price > 0:
                    return float(price)
            return None
        except Exception as e:
            log.debug(f"[{self.session_id}] Spot price fetch error: {e}")
            return None

    def _update_leg_mark_prices(self, cycle: Dict):
        """
        Update mark prices for all legs from exchange ticker data.

        AUDIT C2: Uses MMMInitializer.build_symbol() + chain_service
        to fetch individual option tickers.
        """
        init = self._get_initializer()
        if not init:
            return

        session = self.session
        params = session.get('params', {})
        expiry = session.get('expiry', '')
        if not expiry:
            return

        legs = cycle.get('legs', {})
        for leg_key, leg in legs.items():
            if leg.get('status') != 'open':
                continue

            try:
                symbol = leg.get('product_symbol', '')
                if not symbol:
                    # Build symbol from leg data
                    opt_type = 'call' if leg.get('side') == 'call' else 'put'
                    symbol = init.build_symbol(opt_type, 'BTC', leg['strike'], expiry)
                    leg['product_symbol'] = symbol

                # Fetch ticker via chain service
                ticker = init.chain_service.get_option_ticker(symbol)
                if ticker:
                    mark = float(ticker.get('mark_price', 0) or 0)
                    if mark > 0:
                        leg['mark_premium'] = mark

                    # Also store delta for Greeks
                    greeks = ticker.get('greeks', {}) or {}
                    if greeks.get('delta') is not None:
                        try:
                            leg['mark_delta'] = float(greeks['delta'])
                        except (ValueError, TypeError):
                            pass

            except Exception as e:
                log.debug(f"[{self.session_id}] Mark price fetch error for {leg_key}: {e}")

    def _get_minutes_to_expiry(self) -> float:
        """
        Calculate minutes remaining until expiry.

        AUDIT C2: Computes from the session's expiry date string.
        BTC options on Delta Exchange expire at 12:00 UTC (5:30 PM IST).
        """
        session = self.session
        expiry = session.get('expiry', '')
        if not expiry:
            return 99999.0

        try:
            # Try ISO format first (e.g., '2026-04-01')
            if 'T' in expiry:
                exp_dt = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
            elif '-' in expiry:
                exp_dt = datetime.strptime(expiry, '%Y-%m-%d')
                # BTC options expire at 12:00 UTC
                exp_dt = exp_dt.replace(hour=12, minute=0, second=0, tzinfo=timezone.utc)
            elif len(expiry) == 8 and expiry.isdigit():
                # DDMMYYYY format
                exp_dt = datetime.strptime(expiry, '%d%m%Y')
                exp_dt = exp_dt.replace(hour=12, minute=0, second=0, tzinfo=timezone.utc)
            else:
                log.warning(f"[{self.session_id}] Unrecognized expiry format: {expiry}")
                return 99999.0

            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            minutes = max((exp_dt - now).total_seconds() / 60, 0)
            return minutes

        except (ValueError, TypeError) as e:
            log.warning(f"[{self.session_id}] Expiry parse error: {e}")
            return 99999.0

    def _execute_entry(self):
        """
        Execute cycle entry (strike selection + order placement).

        AUDIT C2: Connects to strike selector and executor.
        """
        session = self.session
        params = session.get('params', {})
        simulate = params.get('simulate', False)

        cycle = prepare_new_cycle(session)
        if not cycle:
            log.error(f"[{self.session_id}] Failed to prepare new cycle")
            return

        try:
            from .ic_strike_selector import select_ic_strikes
            from .ic_executor import get_executor
            from .ic_cycle import activate_cycle

            init = self._get_initializer()
            if not init:
                log.error(f"[{self.session_id}] No initializer — cannot select strikes")
                return

            # Get expiry from session
            expiry = session.get('expiry', '')
            if not expiry:
                log.error(f"[{self.session_id}] No expiry set — cannot select strikes")
                return

            # Select strikes
            spot = self._fetch_spot_price()
            if not spot:
                log.error(f"[{self.session_id}] No spot price — cannot select strikes")
                return

            selection = select_ic_strikes(
                spot_price=spot,
                params=params,
                chain_fetcher=init,
                expiry=expiry,
            )

            if not selection or not selection.get('success'):
                log.error(
                    f"[{self.session_id}] Strike selection failed: "
                    f"{selection.get('error', 'unknown') if selection else 'no result'}"
                )
                return

            legs = selection['legs']

            # Place entry orders
            executor = get_executor(api_client=None)  # Real API client TBD
            success, updated_legs = executor.place_entry_orders(legs, session)

            if success:
                activate_cycle(session, updated_legs)
                # AUDIT C4: Emit cycle opened to UI
                emit_cycle_opened(self.session_id, {
                    'cycle_id': session['current_cycle'].get('cycle_id'),
                    'cycle_number': session.get('cycle_number'),
                    'short_put_strike': session['current_cycle'].get('short_put_strike'),
                    'short_call_strike': session['current_cycle'].get('short_call_strike'),
                    'entry_net_credit': session['current_cycle'].get('entry_net_credit'),
                    'expiry': expiry,
                })
                log.info(f"[{self.session_id}] Cycle {session.get('cycle_number')} opened")

                # Telegram alert
                try:
                    from .ic_telegram import alert_cycle_opened
                    c = session['current_cycle']
                    alert_cycle_opened(
                        self.session_id, session.get('cycle_number', 1),
                        c.get('short_put_strike', 0), c.get('short_call_strike', 0),
                        c.get('entry_net_credit', 0), c.get('max_loss_usd', 0),
                        expiry,
                    )
                except Exception:
                    pass
            else:
                log.error(f"[{self.session_id}] Entry order placement failed")

        except Exception as e:
            log.error(f"[{self.session_id}] Entry execution error: {e}", exc_info=True)

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

        # Store cycle info for event emission before finalize clears it
        cycle_summary = {
            'cycle_id': cycle.get('cycle_id'),
            'cycle_number': cycle.get('cycle_number'),
            'exit_reason': exit_reason,
            'unrealized_pnl': cycle.get('unrealized_pnl', 0),
        }

        finalize_cycle_close(self.session, cycle, exit_reason, close_premiums)

        # AUDIT C4: Emit cycle closed to UI
        cycle_summary['realized_pnl'] = cycle.get('realized_pnl', 0)
        emit_cycle_closed(self.session_id, cycle_summary)

        # Telegram alert
        try:
            from .ic_telegram import alert_cycle_closed
            alert_cycle_closed(
                self.session_id,
                cycle_summary.get('cycle_number', 0),
                exit_reason,
                cycle.get('realized_pnl', 0),
                self.session.get('total_realized_pnl', 0),
            )
        except Exception:
            pass

        # Transition to cycling or idle
        if self.session.get('params', {}).get('auto_cycle', True):
            transition_to_cycling(self.session)
        else:
            from .ic_cycle import transition_to_idle
            transition_to_idle(self.session)

    def _execute_roll(self, decision: str, spot: float):
        """Execute a roll adjustment."""
        cycle = self.session.get('current_cycle')
        if not cycle:
            return

        try:
            from .ic_roller import execute_roll_call_up, execute_roll_put_down
            from .ic_strike_selector import select_roll_strikes
            from .ic_adjuster import DECISION_ROLL_CALL, DECISION_ROLL_PUT, DECISION_ROLL_BOTH
            from .ic_executor import get_executor

            init = self._get_initializer()
            if not init:
                log.error(f"[{self.session_id}] No initializer for roll")
                return

            params = self.session.get('params', {})
            expiry = self.session.get('expiry', '')
            executor = get_executor()

            # Select new strikes for the roll
            roll_data = select_roll_strikes(
                decision=decision,
                cycle=cycle,
                spot_price=spot,
                params=params,
                chain_fetcher=init,
                expiry=expiry,
            )

            if not roll_data or not roll_data.get('success'):
                log.error(f"[{self.session_id}] Roll strike selection failed")
                return

            # Execute the roll
            if decision in (DECISION_ROLL_CALL, DECISION_ROLL_BOTH):
                if 'new_sc' in roll_data and 'new_lc' in roll_data:
                    execute_roll_call_up(
                        cycle, self.session, executor,
                        roll_data['new_sc'], roll_data['new_lc'], spot,
                    )

            if decision in (DECISION_ROLL_PUT, DECISION_ROLL_BOTH):
                if 'new_sp' in roll_data and 'new_lp' in roll_data:
                    execute_roll_put_down(
                        cycle, self.session, executor,
                        roll_data['new_sp'], roll_data['new_lp'], spot,
                    )

            log.info(f"[{self.session_id}] Roll {decision} complete at spot={spot}")

            # Telegram alert
            try:
                from .ic_telegram import alert_adjustment
                alert_adjustment(
                    self.session_id, decision,
                    {}, {},  # old/new strikes from roll events
                    cycle.get('cumulative_roll_credit', 0),
                    cycle.get('adjustment_count', 0),
                    params.get('max_adjustments_per_cycle', 3),
                )
            except Exception:
                pass

        except Exception as e:
            log.error(f"[{self.session_id}] Roll execution error: {e}", exc_info=True)

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
            with self._session_lock:
                storage.save_session(self.session)
        except Exception as e:
            log.error(f"[{self.session_id}] Failed to persist: {e}")
