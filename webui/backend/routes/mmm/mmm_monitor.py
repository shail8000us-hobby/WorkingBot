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

from .mmm_state import recompute_side_lots, get_session_summary
from .mmm_trigger import (
    evaluate_triggers, update_trigger_snapshots,
    apply_theta_acceleration, OUTCOME_NONE, OUTCOME_CE,
    OUTCOME_PE, OUTCOME_BOTH,
)
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
from .mmm_close_at_5 import (
    scan_closeable_positions, close_position,
    check_side_fully_closed, check_both_sides_closed,
)
from .mmm_safety import (
    get_safety, should_block_adjustment, should_pause,
    update_peak_pnl,
)
from .mmm_websocket import (
    emit_heartbeat, emit_adjustment, emit_reversal,
    emit_strike_shift, emit_close_at_5, emit_both_sides_alert,
    emit_safety, emit_pnl_update, emit_status_change,
    emit_price_tick,
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
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._session_lock = threading.Lock()

        self._engine = get_engine()
        self._safety = get_safety()

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

    def stop(self, reason: str = 'User requested'):
        """Stop the heartbeat monitor."""
        if not self._running:
            return

        old_status = self.session.get('strategy_status', 'RUNNING')
        self._running = False
        self._stop_event.set()
        self.session['strategy_status'] = 'STOPPED'
        self.session['updated_at'] = datetime.utcnow().isoformat()

        _save_session(self.session)

        emit_status_change(
            self.session_id, old_status, 'STOPPED', reason
        )
        log.info(f"Monitor stopped for {self.session_id}: {reason}")

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
                    old_whipsaw = self.session.get('params', {}).get('whipsaw_limit', 3)
                    new_whipsaw = fresh_session.get('params', {}).get('whipsaw_limit', 3)
                    
                    self.session = fresh_session
                    
                    # Log parameter reload if whipsaw changed
                    if old_whipsaw != new_whipsaw:
                        from .mmm_activity import log_activity
                        log_activity('info',
                                    f'🔄 Hot Reload: whipsaw_limit updated {old_whipsaw} → {new_whipsaw}',
                                    self.session_id, 'success',
                                    {'old_value': old_whipsaw, 'new_value': new_whipsaw})
                else:
                    log.error(f"Session {self.session_id} not found in storage, stopping monitor")
                    self.stop('Session not found')
                    break

                params = self.session.get('params', {})
                interval = params.get('adjustment_interval', 300)

                # Apply theta acceleration if near expiry
                minutes_to_expiry = self._get_minutes_to_expiry()
                if minutes_to_expiry is not None:
                    accel = apply_theta_acceleration(
                        self.session, minutes_to_expiry
                    )
                    if accel.get('accelerated'):
                        interval = accel['effective_interval']
                        # Also widen the trigger move so evaluate_triggers
                        # uses the accelerated value (§14.7)
                        params['min_trigger_move'] = accel['effective_min_trigger_move']
                        self.session['_theta_accelerated'] = True
                    elif self.session.pop('_theta_accelerated', False):
                        # Restore original trigger move when leaving theta window
                        # (shouldn't normally happen since theta window is at end)
                        pass

                # Record next heartbeat time
                self.session['next_heartbeat'] = (
                    datetime.utcnow() + timedelta(seconds=interval)
                ).isoformat()

                try:
                    self._loop.run_until_complete(self._heartbeat())
                except Exception as e:
                    log.exception(f"Heartbeat error for {self.session_id}: {e}")
                    self.session['last_error'] = str(e)
                    self.session['error_count'] = (
                        self.session.get('error_count', 0) + 1
                    )
                    # Persist error state so reload doesn't wipe error_count
                    _save_session(self.session)

                    # If too many consecutive errors, stop
                    if self.session.get('error_count', 0) >= 5:
                        self.stop('Too many consecutive errors')
                        break

                # Wait for next interval, BUT tick prices every 5s in between
                PRICE_TICK_INTERVAL = 5  # seconds
                elapsed = 0
                while elapsed < interval and not self._stop_event.is_set():
                    wait_time = min(PRICE_TICK_INTERVAL, interval - elapsed)
                    self._stop_event.wait(timeout=wait_time)
                    elapsed += wait_time

                    if self._stop_event.is_set():
                        break

                    # Fetch and emit live prices between heartbeats
                    try:
                        import sys
                        print(f"[MMM PRICE TICK] elapsed={elapsed:.0f}s — fetching now", flush=True, file=sys.stderr)
                        log.info(f"[{self.session_id}] Price tick: fetching live prices (elapsed={elapsed:.0f}s)")
                        self._emit_price_tick()
                    except Exception as e:
                        import traceback
                        print(f"[MMM PRICE TICK ERROR] {e}", flush=True, file=sys.stderr)
                        traceback.print_exc(file=sys.stderr)
                        log.warning(f"[{self.session_id}] Price tick error: {e}", exc_info=True)

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
        
        # Step 0: Sanitize state (Fix for stuck reversal sessions)
        sanitize_session_state(session)

        # NOTE: error_count is reset at the END of a successful heartbeat,
        # not here at the start. This ensures consecutive errors accumulate.

        # Log heartbeat start
        from .mmm_activity import log_activity
        log_activity('heartbeat_start',
                    f'Heartbeat #{session.get("_heartbeat_counter", 0) + 1}: Checking market conditions',
                    sid, 'info')
        session['_heartbeat_counter'] = session.get('_heartbeat_counter', 0) + 1

        # Recommendation #2: Cap reversal_count growth.
        # If reversal_count >> adjustment_count, something is looping.
        # Force-transition to standard mode to break the cycle.
        _check_reversal_count_health(session, sid)

        # Step 0: Reconcile with exchange positions (§14.5 — exchange reality check)
        await self._reconcile_exchange_positions()

        # Step 1: Fetch current premiums
        ce_now, pe_now = await self._fetch_premiums()
        if ce_now is None or pe_now is None:
            log.warning(f"[{sid}] Failed to fetch premiums, skipping beat")
            log_activity('heartbeat_error',
                        'Failed to fetch premium data from exchange',
                        sid, 'error')
            return

        # Log premium values
        ce_strike = session.get('ce', {}).get('active_strike', 'N/A')
        pe_strike = session.get('pe', {}).get('active_strike', 'N/A')
        log_activity('info',
                    f'Current Premiums: CE {ce_strike} = ${ce_now:.2f}, PE {pe_strike} = ${pe_now:.2f}',
                    sid, 'info',
                    {'ce_premium': ce_now, 'pe_premium': pe_now, 'ce_strike': ce_strike, 'pe_strike': pe_strike})

        # Populate premium cache for sync engine calls (_make_fetch_fn)
        await self._prefetch_all_premiums(ce_now, pe_now)

        # §CRITICAL: Persist premium_map into session so the REST API can serve
        # current prices on page load (before WebSocket heartbeat reaches frontend).
        # Without this, the frontend falls back to trigger_snapshot which is the
        # trigger reference level, NOT the current market price.
        cache = getattr(self, '_premium_cache', {})
        session['_premium_map'] = {
            f"{int(strike)}:{opt_type}": round(price, 2)
            for (strike, opt_type), price in cache.items()
        }
        session['_premium_map_ts'] = datetime.utcnow().isoformat()

        # Step 2: Close-at-5 scan (§11)
        await self._process_close_at_5(ce_now, pe_now)

        # Check if both sides fully closed
        if check_both_sides_closed(session):
            self.stop('Both sides fully closed — strategy complete!')
            return

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

        # Step 4: If paused, emit heartbeat but skip adjustment
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
        min_trigger = params.get('min_trigger_move', 3.0)
        ce_entry = session.get('ce', {}).get('entry_fill_price', 0)
        pe_entry = session.get('pe', {}).get('entry_fill_price', 0)
        ce_move_pct = ((ce_now - ce_entry) / ce_entry * 100) if ce_entry else 0
        pe_move_pct = ((pe_now - pe_entry) / pe_entry * 100) if pe_entry else 0
        
        log_activity('info',
                    f'Trigger Check: CE {ce_move_pct:+.1f}% (need {min_trigger:+.1f}%), '
                    f'PE {pe_move_pct:+.1f}% (need {min_trigger:+.1f}%) - '
                    f'Result: {outcome.upper()}',
                    sid, 'info',
                    {
                        'ce_move_pct': round(ce_move_pct, 2),
                        'pe_move_pct': round(pe_move_pct, 2),
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
                        sid, 'warning',
                        {
                            'ce_premium': ce_now,
                            'pe_premium': pe_now,
                            'ce_excess': trigger_result.get('ce_excess', 0),
                            'pe_excess': trigger_result.get('pe_excess', 0)
                        })
            self.pause('Both sides triggered')
            session['strategy_status'] = 'BOTH_SIDES_UP'
            emit_both_sides_alert(
                sid, ce_now, pe_now,
                trigger_result['ce_trigger'],
                trigger_result['pe_trigger'],
                trigger_result['ce_excess'],
                trigger_result['pe_excess'],
            )

        elif outcome in (OUTCOME_CE, OUTCOME_PE):
            aggressor = 'ce' if outcome == OUTCOME_CE else 'pe'
            hedge = 'pe' if aggressor == 'ce' else 'ce'
            premium_now = ce_now if aggressor == 'ce' else pe_now
            hedge_premium = pe_now if aggressor == 'ce' else ce_now

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

        # Periodic reconciliation (§14.5)
        adj_count = session.get('adjustment_count', 0)
        if adj_count > 0 and adj_count % 5 == 0:
            self._engine.reconcile_pnl(
                session, self._make_fetch_fn()
            )

        # Recommendation #3: Trigger staleness detection
        _check_trigger_staleness(session, ce_now, pe_now, sid)

        # Save state
        _save_session(session)

        # Reset error count AFTER successful heartbeat completion
        session['error_count'] = 0

        # Log heartbeat completion
        from .mmm_activity import log_activity
        log_activity('heartbeat_complete',
                    f'✓ Heartbeat #{session.get("_heartbeat_counter", 0)} complete - '
                    f'Next check in {session.get("params", {}).get("adjustment_interval", 300)}s',
                    sid, 'success',
                    {'next_interval': session.get('params', {}).get('adjustment_interval', 300)})

    # =========================================================================
    # §5: Process Adjustment
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

        # §9: Check for reversal
        is_reversal = detect_reversal(session, aggressor)

        if is_reversal:
            record_reversal(session, session.get('last_aggressor', 'NONE'), aggressor)

            # First reversal: use adjustment P&L formula
            loss, adj_pnl = self._engine.calculate_reversal_loss(
                session, aggressor, self._make_fetch_fn()
            )

            # §9: If adjustments still profitable, skip
            skip, skip_reason = should_skip_reversal_adjustment(session, adj_pnl)
            if skip:
                log.info(f"[{sid}] {skip_reason}")

                from .mmm_activity import log_activity
                log_activity('reversal_skip',
                    f'Reversal {session.get("last_aggressor", "NONE")}→{aggressor.upper()} '
                    f'skipped: adj P&L ${adj_pnl:.2f} (profitable). '
                    f'Transitioning to standard mode.',
                    sid, 'info',
                    {'adj_pnl': round(adj_pnl, 2), 'aggressor': aggressor.upper()})

                emit_reversal(
                    sid, session.get('last_aggressor', ''),
                    aggressor.upper(), adj_pnl, 'skip_profitable',
                )

                # §9: "After first reversal → standard mode."
                # When the reversal is SKIPPED (profitable), the same transition
                # applies. The market HAS reversed. Update last_aggressor and
                # triggers so subsequent intervals use standard formula (Case A)
                # instead of re-detecting the same reversal forever.
                handle_reversal_skip_transition(
                    session, aggressor, ce_now, pe_now,
                )

                # §14.3: Activate cooldown ONCE for the reversal direction
                # change. activate_cooldown() is idempotent — it won't
                # re-activate if already in cooldown.
                params = session.get('params', {})
                if params.get('cooldown_on_reversal', True):
                    activate_cooldown(session)

                return

            adj_type = 'first_reversal'
            emit_reversal(
                sid, session.get('last_aggressor', ''),
                aggressor.upper(), adj_pnl, 'hedge',
            )

            # Cooldown after reversal
            params = session.get('params', {})
            if params.get('cooldown_on_reversal', True):
                activate_cooldown(session)
        else:
            # Standard or continuation
            loss = self._engine.calculate_standard_loss(
                session, aggressor, premium_now,
            )
            adj_type = 'standard'

        if loss <= 0:
            return

        # §10: Check if strike shift needed on hedge side
        if check_shift_needed(session, hedge, hedge_premium):
            await self._process_strike_shift(
                hedge, loss, ce_now, pe_now,
            )
            return

        # §5.4: Calculate lots to sell
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
        )

        if result.get('success'):
            from .mmm_activity import log_activity
            fill_price = result['fill_price']
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

        result = await self.executor.smart_execute(
            symbol=symbol,
            side='sell',
            size=lots,
        )

        if result.get('success'):
            fill_price = result.get('fill_price', 0)
            activate_new_strike(
                session, side, new_strike, fill_price, lots,
            )

            # Update triggers at new strike
            update_trigger_snapshots(session, ce_now, pe_now)

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
        """Scan and close positions at or below threshold."""
        session = self.session
        sid = self.session_id

        closeable = scan_closeable_positions(
            session, self._make_fetch_fn(),
        )

        if closeable:
            from .mmm_activity import log_activity
            closeable_summary = ', '.join([f"{p['side'].upper()} @ {p['strike']}" for p in closeable])
            log_activity('info',
                        f'Close-at-5 Scan: {len(closeable)} position(s) ready to close - {closeable_summary}',
                        sid, 'info',
                        {'closeable_count': len(closeable), 'positions': closeable_summary})

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

                # Check if side fully closed → auto-find new strike
                if check_side_fully_closed(session, pos['side']):
                    log.info(
                        f"[{sid}] {pos['side'].upper()} fully closed, "
                        f"seeking new strike..."
                    )
                    # This is a special case — we don't shift, we re-enter
                    # For now, just log. Full auto-re-entry needs user config.

    # =========================================================================
    # Auto-Close All (Near Expiry)
    # =========================================================================

    async def _auto_close_all(self, reason: str):
        """Close all open positions (near-expiry safety).
        
        Closes each position at its own strike:
        - Active positions (original + adjustment) at active_strike
        - Each frozen position at its own frozen strike
        """
        session = self.session
        sid = self.session_id

        log.info(f"[{sid}] Auto-closing all positions: {reason}")

        for side_key in ['ce', 'pe']:
            side_state = session.get(side_key, {})
            option_type = 'call' if side_key == 'ce' else 'put'
            active_strike = side_state.get('active_strike', 0)
            expiry = session.get('params', {}).get('expiry', '')

            # Close active lots (original + adjustment) at active strike
            active_lots = side_state.get('active_lots', 0)
            if active_lots > 0 and active_strike > 0:
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
                        # Compute P&L per-fill (not just original_premium)
                        pnl = 0.0
                        # Original lots
                        orig_lots = side_state.get('original_lots', 0)
                        orig_prem = side_state.get('original_premium', 0)
                        if orig_lots > 0:
                            pnl += (orig_prem - close_price) * orig_lots * LOT_SIZE_BTC
                        # Adjustment fills at active strike
                        for fill in side_state.get('adjustment_fills', []):
                            f_lots = fill.get('lots', 0)
                            f_prem = fill.get('premium', 0)
                            if f_lots > 0:
                                pnl += (f_prem - close_price) * f_lots * LOT_SIZE_BTC
                        session['realized_pnl'] = (
                            session.get('realized_pnl', 0) + pnl
                        )
                        log.info(
                            f"[{sid}] Closed {active_lots} active "
                            f"{side_key.upper()} @ {active_strike}, P&L: {pnl:.2f}"
                        )
                except Exception as e:
                    log.error(
                        f"Failed to auto-close active {side_key.upper()}: {e}"
                    )

            # Close each frozen position at its OWN strike
            for frozen in side_state.get('frozen_positions', []):
                frozen_strike = frozen.get('strike', 0)
                frozen_lots = frozen.get('lots', 0)
                frozen_entry = frozen.get('entry_premium', 0)

                if frozen_lots > 0 and frozen_strike > 0:
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
                    except Exception as e:
                        log.error(
                            f"Failed to auto-close frozen {side_key.upper()} "
                            f"@ {frozen_strike}: {e}"
                        )

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

            # Compare with session state
            discrepancies = []

            for side_key in ['ce', 'pe']:
                side = session.get(side_key, {})
                symbol = side.get('symbol', '')
                session_lots = side.get('total_lots', side.get('original_lots', 0))

                if not symbol:
                    continue

                exchange_pos = exchange_positions.get(symbol, {})
                exchange_size = exchange_pos.get('size', 0)

                if session_lots > 0 and exchange_size == 0:
                    discrepancies.append({
                        'side': side_key.upper(),
                        'type': 'MISSING_ON_EXCHANGE',
                        'detail': f"{side_key.upper()} session has {session_lots} lots but exchange shows 0",
                        'symbol': symbol,
                        'session_lots': session_lots,
                        'exchange_size': 0,
                    })
                elif abs(session_lots - exchange_size) > 0.1 and session_lots > 0:
                    discrepancies.append({
                        'side': side_key.upper(),
                        'type': 'SIZE_MISMATCH',
                        'detail': f"{side_key.upper()} session={session_lots} vs exchange={exchange_size}",
                        'symbol': symbol,
                        'session_lots': session_lots,
                        'exchange_size': exchange_size,
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

        # Fetch any remaining strikes not yet in cache
        # Use a fresh client context to avoid 'Event loop is closed' issues
        from bot.api.async_delta_client import AsyncDeltaClient
        from config.loader import get_api_credentials
        creds = get_api_credentials()
        
        rest = AsyncDeltaClient(
            api_key=creds.get('api_key', ''),
            api_secret=creds.get('api_secret', ''),
            testnet=creds.get('testnet', False) or False,
        )
        try:
            for strike, opt in strike_pairs:
                if (strike, opt) in cache:
                    continue
                try:
                    symbol = self.initializer.build_symbol(
                        opt, 'BTC', strike, expiry,
                    )
                    # Use direct request to avoid any session state issues
                    resp = await rest._request_with_retry(
                        method="GET", path=f"/v2/tickers/{symbol}",
                    )
                    data = resp.get('result', resp) if hasattr(resp, 'get') else resp
                    cache[(strike, opt)] = float(data.get('mark_price', 0))
                except Exception as e:
                    log.warning(f"Prefetch failed for {opt}@{strike}: {e}")
                    # Do NOT default to 0. Leave it out of cache so fetch_fn raises error.
        except Exception as e:
            log.error(f"Global prefetch loop error: {e}")
        finally:
            # Ensure we close the temporary session
            await rest.close()

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
            
            # Cache miss - likely failed to fetch. Raise error rather than returning 0.
            # Returning 0 for a short position signals infinite profit, which is dangerous.
            raise ValueError(f"Premium data unavailable for {option_type}@{strike}")
            
        return fetch

    def _get_minutes_to_expiry(self) -> Optional[float]:
        """Calculate minutes remaining until expiry."""
        expiry_time = self.session.get('expiry_time')
        if not expiry_time:
            return None
        try:
            exp = datetime.fromisoformat(expiry_time)
            now = datetime.utcnow()
            delta = (exp - now).total_seconds() / 60
            return max(delta, 0)
        except (ValueError, TypeError):
            return None

    def _emit_heartbeat_data(self, ce_now: float, pe_now: float):
        """Emit heartbeat WebSocket event."""
        session = self.session
        ce_trigger = session.get('ce', {}).get('trigger_snapshot', {}).get(
            str(int(session.get('ce', {}).get('active_strike', 0))), 0
        )
        pe_trigger = session.get('pe', {}).get('trigger_snapshot', {}).get(
            str(int(session.get('pe', {}).get('active_strike', 0))), 0
        )

        realized = session.get('realized_pnl', 0)
        unrealized = session.get('unrealized_pnl', 0)

        # Build premium_map from the pre-fetched cache for ALL strikes
        # Format: {"strike:option_type": mark_price}
        premium_map = {}
        cache = getattr(self, '_premium_cache', {})
        for (strike, opt_type), mark_price in cache.items():
            key = f"{int(strike)}:{opt_type}"
            premium_map[key] = mark_price

        emit_heartbeat(
            self.session_id, ce_now, pe_now,
            ce_trigger, pe_trigger,
            session.get('strategy_status', 'UNKNOWN'),
            realized + unrealized, realized,
            premium_map=premium_map,
        )

    def _emit_price_tick(self):
        """Fetch live mark prices for ALL strikes and emit a price-only tick.

        Runs every 5 seconds between heartbeats for real-time UI price updates.
        Does NOT run any adjustment logic — just price fetch + emit.
        
        Uses synchronous httpx.get() instead of the AsyncDeltaClient to avoid
        event loop lifecycle issues between heartbeats.
        """
        import httpx
        import sys

        session = self.session
        expiry = session.get('params', {}).get('expiry', '')
        underlying = session.get('underlying', 'BTC')

        # Collect all (strike, option_type) pairs from session
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

        if not strike_pairs:
            print(f"[MMM PRICE TICK] No strike pairs found!", flush=True, file=sys.stderr)
            return

        print(f"[MMM PRICE TICK] {len(strike_pairs)} strikes to fetch", flush=True, file=sys.stderr)

        # Determine API base URL
        from config.loader import get_api_credentials
        creds = get_api_credentials()
        testnet = creds.get('testnet', False) or False
        base_url = (
            'https://cdn-testnet.delta.exchange'
            if testnet
            else 'https://api.india.delta.exchange'
        )

        premium_map = {}
        for strike, opt_type in strike_pairs:
            try:
                symbol = self.initializer.build_symbol(
                    opt_type, underlying, strike, expiry,
                )
                resp = httpx.get(
                    f"{base_url}/v2/tickers/{symbol}",
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    data = resp.json().get('result', {})
                    mark = float(data.get('mark_price', 0))
                    key = f"{int(strike)}:{opt_type}"
                    premium_map[key] = mark
                else:
                    print(f"[MMM PRICE TICK] HTTP {resp.status_code} for {symbol}", flush=True, file=sys.stderr)
            except Exception as e:
                print(f"[MMM PRICE TICK] Fetch error {opt_type}@{strike}: {e}", flush=True, file=sys.stderr)

        print(f"[MMM PRICE TICK] Fetched {len(premium_map)} prices: {premium_map}", flush=True, file=sys.stderr)

        if premium_map:
            # Update session premium_map so REST API also serves fresh prices
            session['_premium_map'] = {
                k: round(v, 2) for k, v in premium_map.items()
            }
            session['_premium_map_ts'] = datetime.utcnow().isoformat()

            # Emit to frontend via WebSocket
            emit_price_tick(self.session_id, premium_map)
            print(f"[MMM PRICE TICK] Emitted to WebSocket", flush=True, file=sys.stderr)

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
    """Persist session to storage."""
    try:
        storage = get_storage()
        storage.save_session(session)
    except Exception as e:
        log.error(f"Failed to save session: {e}")


def sanitize_session_state(session: Dict):
    """Fix known state inconsistencies.
    
    Runs once per session (sets _sanitized flag to avoid duplicate runs).
    Fixes:
    1. Shifted positions misclassified as original_lots
    2. original_premium not matching entry_fill_price
    """
    # Only run once per session lifetime
    if session.get('_sanitized', False):
        return

    sanitized_anything = False

    # Fix 1: Shifted positions misclassified as original_lots
    if session.get('shift_count', 0) > 0:
        for side_key in ['ce', 'pe']:
            side = session.get(side_key, {})
            # If we have original lots at a shifted strike (different from original),
            # move to adjustment
            if (side.get('original_lots', 0) > 0
                    and side.get('active_strike', 0) != side.get('original_strike', 0)):
                log.warning(
                    f"Sanitizing {side_key}: Moving {side['original_lots']} "
                    f"original_lots to adjustments (active strike shifted)"
                )
                
                # Use entry_fill_price if available, fall back to original_premium
                prem = side.get('entry_fill_price', 0) or side.get('original_premium', 0)
                strike = side.get('active_strike', 0)
                lots = side.get('original_lots')
                
                side.setdefault('adjustment_fills', []).append({
                    'lots': lots,
                    'premium': prem,
                    'strike': strike,
                    'timestamp': datetime.utcnow().isoformat(),
                    'type': 'strike_shift_sanitized'
                })
                
                side['original_lots'] = 0
                side['original_premium'] = 0.0
                
                from .mmm_state import recompute_side_lots
                recompute_side_lots(side)
                session[side_key] = side
                sanitized_anything = True

    # Fix 2: original_premium should match entry_fill_price
    for side_key in ['ce', 'pe']:
        side = session.get(side_key, {})
        fill_price = side.get('entry_fill_price')
        orig_prem = side.get('original_premium', 0)
        if fill_price and orig_prem > 0 and abs(fill_price - orig_prem) > 0.01:
            log.warning(
                f"Sanitizing {side_key}: original_premium {orig_prem} != "
                f"entry_fill_price {fill_price}, correcting"
            )
            side['original_premium'] = fill_price
            # Also update trigger_snapshot at original strike if it used the wrong premium
            orig_strike_key = str(int(side.get('original_strike', 0)))
            if orig_strike_key in side.get('trigger_snapshot', {}):
                old_trigger = side['trigger_snapshot'][orig_strike_key]
                if abs(old_trigger - orig_prem) < 0.01:
                    side['trigger_snapshot'][orig_strike_key] = fill_price
            session[side_key] = side
            sanitized_anything = True

    if sanitized_anything:
        log.info("Session sanitization complete, setting _sanitized flag")

    session['_sanitized'] = True


def _check_reversal_count_health(session: Dict, sid: str):
    """
    Recommendation #2: Detect runaway reversal detection loops.

    If reversal_count > adjustment_count × 3 (and > 5 absolute),
    something is wrong — force-transition to standard mode.

    This catches infinite reversal loops that the explicit skip-transition
    fix should prevent, as a defense-in-depth measure.
    """
    rev_count = session.get('reversal_count', 0)
    adj_count = session.get('adjustment_count', 0)

    # Only flag if there are enough reversals to matter
    if rev_count <= 5:
        return

    max_expected = max(adj_count * 3, 6)
    if rev_count > max_expected:
        from .mmm_activity import log_activity
        log.error(
            f"[{sid}] REVERSAL LOOP DETECTED: reversal_count={rev_count} >> "
            f"adjustment_count={adj_count}. Force-resetting reversal state."
        )
        log_activity('safety_warning',
            f'⚠️ Reversal loop detected: {rev_count} reversals vs {adj_count} adjustments. '
            f'Force-resetting to prevent infinite loop.',
            sid, 'error',
            {'reversal_count': rev_count, 'adjustment_count': adj_count})

        # Force-reset: update last_aggressor to break the loop
        # The current trigger evaluation will determine the next aggressor
        # and standard formula will be used.
        session['_reversal_loop_detected'] = True
        session['_reversal_loop_reset_at'] = datetime.utcnow().isoformat()
        # Don't change last_aggressor here — let the next trigger+adjustment
        # cycle set it naturally. Instead, cap the count and log.
        session['reversal_count'] = adj_count + 1  # Reset to sane value


def _check_trigger_staleness(
    session: Dict,
    ce_now: float,
    pe_now: float,
    sid: str,
):
    """
    Recommendation #3: Detect stale triggers.

    If a trigger snapshot at the active strike hasn't been updated for N
    heartbeats AND the current premium has moved significantly from the
    trigger level, something may be wrong (e.g. skipped adjustments
    without trigger updates).

    Tracks the last trigger update heartbeat counter and flags staleness.
    """
    hb_counter = session.get('_heartbeat_counter', 0)

    for side_key, premium_now in [('ce', ce_now), ('pe', pe_now)]:
        side_state = session.get(side_key, {})
        active_strike = str(int(side_state.get('active_strike', 0)))
        trigger_val = side_state.get('trigger_snapshot', {}).get(active_strike, 0)

        if trigger_val <= 0 or premium_now <= 0:
            continue

        # Track when trigger was last changed
        last_key = f'_trigger_last_updated_hb_{side_key}'
        stored_trigger_key = f'_trigger_last_value_{side_key}'

        stored_val = session.get(stored_trigger_key, 0)
        if abs(stored_val - trigger_val) > 0.01:
            # Trigger WAS updated — record the heartbeat when it changed
            session[last_key] = hb_counter
            session[stored_trigger_key] = trigger_val
        else:
            # Trigger hasn't changed — check staleness
            last_updated_hb = session.get(last_key, hb_counter)
            hb_since_update = hb_counter - last_updated_hb

            # If trigger hasn't changed in 10+ heartbeats and premium has moved
            # more than 50% from trigger, flag staleness
            if hb_since_update >= 10:
                move_pct = abs(premium_now - trigger_val) / trigger_val * 100
                if move_pct > 50:
                    from .mmm_activity import log_activity
                    log.warning(
                        f"[{sid}] STALE TRIGGER: {side_key.upper()} trigger at "
                        f"{active_strike}={trigger_val:.2f} hasn't changed in "
                        f"{hb_since_update} heartbeats, but premium is now "
                        f"{premium_now:.2f} ({move_pct:.0f}% away)"
                    )
                    log_activity('trigger_stale',
                        f'⚠️ Stale {side_key.upper()} trigger: unchanged for '
                        f'{hb_since_update} heartbeats. Trigger={trigger_val:.2f}, '
                        f'Premium={premium_now:.2f} ({move_pct:.0f}% drift)',
                        sid, 'warning',
                        {
                            'side': side_key.upper(),
                            'trigger': trigger_val,
                            'premium': premium_now,
                            'drift_pct': round(move_pct, 1),
                            'stale_heartbeats': hb_since_update,
                        })

