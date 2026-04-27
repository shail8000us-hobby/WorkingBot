"""
MMM Exit All — Global Graceful Exit Handler

Invoked from _heartbeat_inner() when strategy_status == 'EXITING'.
Closes all open positions across both sides using existing close_position(),
then calls monitor.stop() to terminate cleanly.

Design principles:
  - Core engine is untouched (close_position is called as-is)
  - This module has zero knowledge of trading logic
  - All closes use mechanism='exit_all' which bypasses G1/G2 guardian guards
  - hedge_guard=False so observer/guardian do not block coordinated exit
  - Interleaved CE/PE ordering prevents single-side wipeout detection
  - Always terminates via monitor.stop() — never raises to caller

Created: March 2026
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List

from .mmm_state import recompute_side_lots
from .mmm_close_at_5 import close_position, check_both_sides_closed


def _enqueue_exit_event(sid, event_type, details):
    """Feature 10: Fire-and-forget exit round event. Never raises."""
    try:
        from .mmm_audit_log import get_event_log
        get_event_log().enqueue_event(
            session_id=sid,
            event_category='EXECUTION_INTENT',
            event_type=event_type,
            remark=f'Exit round: {event_type}',
            severity='INFO',
            details=details,
        )
    except Exception:
        pass

log = logging.getLogger('mmm_exit_all')

# Max closing rounds before giving up and stopping as partial
MAX_EXIT_ROUNDS = 3

# Seconds to wait between rounds (lets exchange settle)
INTER_ROUND_DELAY_SEC = 1

# Max concurrent close orders per side (limits Delta Exchange API pressure)
MAX_CONCURRENT_CLOSES_PER_SIDE = 3


# =============================================================================
# Public entry point
# =============================================================================

async def run_exit_all(monitor) -> None:
    """
    Global graceful exit handler. Called from _heartbeat_inner() when
    strategy_status == 'EXITING'. Runs round-based position closing, then
    always calls monitor.stop() regardless of outcome.

    Args:
        monitor: MMMMonitor instance (provides executor, initializer, session)
    """
    session = monitor.session
    sid = monitor.session_id
    initiated_at = session.get('_exit_all_initiated_at') or datetime.now(timezone.utc).isoformat()

    log.warning(f"[{sid}] EXIT ALL: Global graceful exit started (initiated_at={initiated_at})")

    # Feature 10: Orphan check — find ORDER_INTENT events with no ORDER_CONFIRMED.
    # Runs on both first-time exit and restart-of-EXITING sessions.
    # Fire-and-forget: result is logged only, never blocks exit flow.
    try:
        from .mmm_audit_log import get_event_log
        orphans = get_event_log().query_execution_orphans(sid)
        if orphans:
            log.warning(
                f"[{sid}] EXIT ALL: {len(orphans)} orphaned ORDER_INTENT(s) detected "
                f"(no matching ORDER_CONFIRMED within 90s). "
                f"order_ids={[o.get('_parsed_details', {}).get('order_id') for o in orphans]}"
            )
            get_event_log().enqueue_event(
                session_id=sid,
                event_category='RECONCILIATION',
                event_type='ORPHAN_INTENTS_DETECTED',
                remark=f'{len(orphans)} unconfirmed order intent(s) at exit start',
                severity='WARNING',
                details={'orphan_count': len(orphans),
                         'order_ids': [o.get('_parsed_details', {}).get('order_id') for o in orphans]},
            )
    except Exception:
        pass

    # Force-clear ALL _being_closed flags before any round begins.
    # During EXITING, the heartbeat gate blocks all normal logic so no concurrent
    # order placements are in-flight. Stale flags from a prior close_at_5 scan
    # would block every round otherwise (3 rounds × 2s = 6s << 180s TTL).
    _force_clear_being_closed(session, sid)

    # ── Pre-flight Layer 1: Order-ID verification ────────────────────────
    # Query each 'closed' position's close_order_id directly on Delta Exchange.
    # GET /v2/orders/{id} gives deterministic filled_size for that specific order.
    # Positions not fully confirmed are reopened for exit rounds to re-close.
    # 100% session-internal — only queries THIS session's own order IDs.
    await _reopen_unverified_closed_positions(monitor, session, sid)

    # ── Pre-flight Layer 2: Sub-ledger net-lots verification ─────────────
    # The position sub-ledger (mmm_ledger.py) tracks every fill persisted via
    # fill_sync. Query: net_lots = sell_fills - buy_fills per symbol.
    # If ledger shows open lots at a symbol but positions[] says closed, reopen.
    # This catches cases where fill_sync confirmed a close fill that was wrong
    # (the authoritative ledger will show more sell than buy fills).
    _reopen_from_ledger(session, sid)

    # ── Kill Switch mode: cancel pending adjustment orders + use market orders ──
    kill_switch_mode = bool(session.get('_kill_switch_triggered'))
    if kill_switch_mode:
        log.warning(f"[{sid}] KILL SWITCH: Cancelling pending adjustment orders before close")
        await _cancel_pending_for_kill_switch(monitor, sid)

    try:
        # ── Close reverse positions FIRST (unhedged, highest risk) ──
        if session.get('_reverse', {}).get('positions'):
            try:
                from .mmm_reverse import close_all_reverse_positions, disable_reverse_mode
                await close_all_reverse_positions(session, monitor._engine, 'exit_all')
                disable_reverse_mode(session, 'exit_all')
                log.info(f"[{sid}] EXIT ALL: Reverse positions closed")
            except Exception as _rev_err:
                log.error(f"[{sid}] EXIT ALL: Failed to close reverse positions: {_rev_err}")

        # ── Close perp hedge SECOND (reduces delta risk while options close) ──
        try:
            from .mmm_perp_hedge import is_perp_hedge_enabled, close_all_perp
            if is_perp_hedge_enabled(session):
                perp_result = await close_all_perp(session, monitor.executor, 'exit_all')
                if perp_result.get('success'):
                    log.info(f"[{sid}] EXIT ALL: Perp hedge closed")
                else:
                    perp_lots = session.get('perp_hedge', {}).get('lots', 0)
                    if perp_lots != 0:
                        log.error(f"[{sid}] EXIT ALL: Perp close failed ({perp_lots} lots remain)")
        except Exception as _perp_err:
            log.error(f"[{sid}] EXIT ALL: Failed to close perp hedge: {_perp_err}")

        # ── Close options positions (CE/PE) via round-based logic ──
        # Kill switch → market orders (immediate fill, no price-improvement wait).
        # Normal exit  → limit orders (smart_execute with repricing).
        await _run_exit_rounds(monitor, use_market_orders=kill_switch_mode)
    except Exception as e:
        log.error(f"[{sid}] EXIT ALL: Unexpected exception during exit rounds: {e}", exc_info=True)
        session['_exit_all_partial'] = True

    # Record completion timestamp
    completed_at = datetime.now(timezone.utc).isoformat()
    session['_exit_all_completed_at'] = completed_at

    # Determine stop reason and emit result event
    if session.get('_exit_all_partial'):
        failed = session.get('_exit_all_failed_positions', [])
        reason = f'Exit All partial — {len(failed)} position(s) may still be open on exchange'
        log.warning(f"[{sid}] EXIT ALL PARTIAL: {len(failed)} position(s) not closed: {failed}")
        _emit_exit_partial(sid, failed)
    else:
        reason = 'Exit All — all positions closed'
        log.warning(f"[{sid}] EXIT ALL COMPLETE: all positions closed")
        _emit_exit_completed(sid, completed_at, initiated_at)

    # --- Exchange-side alert-only verification ---
    # Query the exchange to detect any remaining positions at managed strikes.
    # This is ALERT-ONLY — no orders are placed here. Multiple algos can share
    # the same strike, so we cannot safely close exchange positions without
    # knowing which session owns them. Session-internal safety re-close (for
    # unconfirmed-closed positions) is handled earlier via _collect_side_positions.
    await _verify_and_alert_remaining(monitor, session, sid)

    # Zero unrealized_pnl in-memory so stop()'s full save writes 0.0.
    # Without this the last heartbeat's mark-to-market stays in DB and the
    # frontend shows a stale U (unrealized) on a stopped session.
    session['unrealized_pnl'] = 0.0

    # Audit activity log (before stop so it's visible immediately)
    try:
        from .mmm_activity import log_activity
        log_activity(
            'session_exit_all_completed',
            f'\U0001f6aa Exit All {"partial" if session.get("_exit_all_partial") else "complete"}: {reason}',
            sid,
            'warning' if session.get('_exit_all_partial') else 'success',
            {'initiated_at': initiated_at, 'completed_at': completed_at,
             'rounds': session.get('_exit_all_rounds_attempted', 0),
             'realized_pnl': round(session.get('realized_pnl', 0), 4)},
        )
    except Exception:
        pass

    # Clean up straddle roll lock before stopping (same pattern as M-03 handle_stale_monitor)
    try:
        from .mmm_straddle_adjustment import _cleanup_roll_lock
        _cleanup_roll_lock(sid)
    except Exception:
        pass

    # Clean up pure straddle roll lock (STRADDLE_ROLL preset)
    try:
        from .mmm_straddle_roll_pure import cleanup_pure_roll_lock
        cleanup_pure_roll_lock(sid)
    except Exception:
        pass

    # Stop the monitor — this does the primary full session save (includes
    # updated realized_pnl from close_position() calls + unrealized=0.0 above).
    monitor.stop(reason)

    # Safety-net write AFTER stop() — prevents a race where a concurrent
    # heartbeat from an earlier monitor instance (higher _monitor_generation
    # in DB) caused stop()'s generation-check to reject the save.
    # update_session() is atomic (read-merge-write) and has no generation check.
    # It runs after stop() so _save_disabled is already set — no concurrent
    # heartbeat can overwrite these values after this point.
    try:
        from .mmm_storage import get_storage
        get_storage().update_session(sid, {
            'realized_pnl': session.get('realized_pnl', 0),
            'unrealized_pnl': 0.0,
            'strategy_status': 'STOPPED',
        })
        log.info(f"[{sid}] EXIT ALL: Final P&L persisted — "
                 f"realized={session.get('realized_pnl', 0):.4f}, unrealized=0.0")
    except Exception as _persist_e:
        log.error(f"[{sid}] EXIT ALL: Could not persist final P&L to storage: {_persist_e}")


# =============================================================================
# Round-based closing logic
# =============================================================================

async def _run_exit_rounds(monitor, use_market_orders: bool = False) -> None:
    """Execute up to MAX_EXIT_ROUNDS of position closing.

    Args:
        use_market_orders: When True (kill switch mode), each close_position call
                           uses order_type='market' for immediate fills at any price.
                           When False (normal exit), uses limit orders with repricing.
    """
    session = monitor.session
    sid = monitor.session_id

    if use_market_orders:
        log.warning(f"[{sid}] EXIT ALL: KILL SWITCH MODE — using market orders for all closes")

    # Spot price for ATM-proximity risk sorting
    spot_price = float(session.get('_regime_spot_price') or 0)

    for round_num in range(1, MAX_EXIT_ROUNDS + 1):

        # Always record that this round was attempted BEFORE any early-return check.
        # Keeping this at 0 would falsely imply "nothing was tried" if we bail early.
        session['_exit_all_rounds_attempted'] = round_num

        # Short-circuit only AFTER round 1 has actually run.
        # The pre-round-1 check was the source of a critical bug: check_both_sides_closed()
        # reads total_lots (a derived scalar) which can be stale if recompute_side_lots()
        # hasn't run. A false True meant zero close orders were ever fired while positions
        # remained open on the exchange. We now only trust this check after real work is done.
        if round_num > 1 and check_both_sides_closed(session):
            log.info(f"[{sid}] EXIT ALL: All positions closed after round {round_num - 1}")
            return

        # Build sorted position lists for this round
        ce_positions = _collect_side_positions(session, 'ce', spot_price)
        pe_positions = _collect_side_positions(session, 'pe', spot_price)
        total_open = len(ce_positions) + len(pe_positions)

        if total_open == 0:
            log.info(f"[{sid}] EXIT ALL: No closeable positions found in round {round_num}")
            return

        log.warning(
            f"[{sid}] EXIT ALL Round {round_num}/{MAX_EXIT_ROUNDS}: "
            f"CE={len(ce_positions)} pos, PE={len(pe_positions)} pos to close"
        )
        _enqueue_exit_event(sid, 'EXIT_ROUND_START', {
            'round_num': round_num, 'positions_to_close': total_open,
            'ce_count': len(ce_positions), 'pe_count': len(pe_positions),
        })

        _emit_exit_progress(sid, round_num, 0, total_open,
                            len(session.get('_exit_all_failed_positions', [])))

        closed_count = 0

        # Close CE and PE concurrently, with up to MAX_CONCURRENT_CLOSES_PER_SIDE
        # parallel close orders within each side. This is safe because:
        #   - asyncio is single-threaded: session mutations happen between awaits
        #   - Each close_position gets its own position dict from the pre-collected list
        #   - recompute_side_lots() is idempotent
        #   - Semaphore limits API pressure on Delta Exchange
        _sem = asyncio.Semaphore(MAX_CONCURRENT_CLOSES_PER_SIDE)

        _order_type = 'market' if use_market_orders else 'limit'

        async def _close_one(side_key: str, pos: dict) -> bool:
            pos_id = pos.get('_pos_id') or f"{side_key}@{pos.get('strike')}"
            async with _sem:
                try:
                    result = await close_position(
                        executor=monitor.executor,
                        initializer=monitor.initializer,
                        session=session,
                        position=pos,
                        mechanism='exit_all',
                        hedge_guard=False,
                        side=side_key,
                        order_type=_order_type,
                    )
                    if result.get('success'):
                        log.info(
                            f"[{sid}] EXIT ALL: Closed {side_key.upper()} @ {pos['strike']} "
                            f"({result.get('lots_closed', pos['lots'])} lots, "
                            f"pnl={result.get('realized_pnl', 0):.4f}, "
                            f"order_type={_order_type})"
                        )
                        return True
                    else:
                        err = result.get('error', 'unknown')
                        log.warning(f"[{sid}] EXIT ALL: Failed to close {pos_id} ({_order_type}): {err}")
                except Exception as e:
                    log.error(f"[{sid}] EXIT ALL: Exception closing {pos_id}: {e}")
            return False

        # Launch all close tasks across both sides — semaphore limits concurrency
        all_tasks = (
            [_close_one('ce', p) for p in ce_positions] +
            [_close_one('pe', p) for p in pe_positions]
        )
        results = await asyncio.gather(*all_tasks, return_exceptions=True)
        closed_count = sum(1 for r in results if r is True)

        # Recompute both sides after each round
        for sk in ('ce', 'pe'):
            side_state = session.get(sk)
            if isinstance(side_state, dict):
                recompute_side_lots(side_state)
                session[sk] = side_state

        remaining_open = _count_open_positions(session)

        _emit_exit_progress(sid, round_num, closed_count, remaining_open,
                            len(session.get('_exit_all_failed_positions', [])))

        log.info(
            f"[{sid}] EXIT ALL Round {round_num} complete: "
            f"closed={closed_count}, remaining={remaining_open}"
        )
        _enqueue_exit_event(sid, 'EXIT_ROUND_END', {
            'round_num': round_num, 'closed_count': closed_count,
            'remaining_open': remaining_open, 'partial': remaining_open > 0,
        })

        if remaining_open == 0:
            return

        # Wait before next round (unless this is the last round)
        if round_num < MAX_EXIT_ROUNDS:
            await asyncio.sleep(INTER_ROUND_DELAY_SEC)

    # All rounds exhausted — check for residual positions
    remaining_open = _count_open_positions(session)
    if remaining_open > 0:
        log.warning(
            f"[{sid}] EXIT ALL: {remaining_open} position(s) remain after "
            f"{MAX_EXIT_ROUNDS} rounds — marking as partial exit"
        )
        session['_exit_all_partial'] = True
        session['_exit_all_failed_positions'] = _build_failed_list(session)


# =============================================================================
# Helpers
# =============================================================================

async def _verify_and_alert_remaining(monitor, session: Dict, sid: str) -> None:
    """
    Alert-only verification: query the exchange for open options positions at
    ALL strikes this session ever managed.

    IMPORTANT: This function NEVER places orders. Multiple algos may share the
    same strike; we cannot safely close exchange positions without knowing which
    session owns them. Session-internal safety re-close for unconfirmed-closed
    positions is done earlier via _collect_side_positions including those entries.

    On exchange API failure: always mark _exit_all_unverified + Telegram alert.
    Old behaviour (silent pass when rounds > 0) is the bug that caused mmm25apr26-1.
    """
    try:
        # Use _create_rest_client() → AsyncDeltaClient which has get_positions_margined.
        # Do NOT use monitor.executor.client (UnifiedAPIClient) — it lacks this method.
        rest = monitor.executor._create_rest_client()
        resp = await rest._request_with_retry(method="GET", path="/v2/positions/margined")
        all_positions = resp.get('result', []) if isinstance(resp, dict) else []
    except Exception as e:
        log.error(
            f"[{sid}] EXIT ALL verify: exchange query failed: {e} — "
            f"CANNOT confirm positions cleared"
        )
        # Always flag unverified regardless of rounds_attempted.
        # Previously only marked partial when rounds==0; that silent pass caused
        # the mmm25apr26-1 incident where 72 lots remained open undetected.
        session['_exit_all_unverified'] = True
        session['_exit_all_partial'] = True
        session['_exit_all_failed_positions'] = _build_failed_list(session)
        try:
            from .mmm_telegram import send_telegram_message
            send_telegram_message(
                f"⚠️ [{sid}] EXIT ALL: exchange verification FAILED ({e}). "
                f"Positions may still be open — check exchange manually."
            )
        except Exception:
            pass
        return

    # Build managed_strikes from EVERY strike this session ever touched.
    # Intentionally includes positions with status='closed' — if the exchange
    # still has a position at a closed strike, the operator must know about it.
    managed_strikes: set = set()
    for sk in ('ce', 'pe'):
        side_state = session.get(sk, {})
        if not isinstance(side_state, dict):
            continue
        active_strike = side_state.get('active_strike', 0)
        if active_strike:
            managed_strikes.add(int(active_strike))
        for pos in side_state.get('positions', []):
            strike = pos.get('strike', 0)
            if strike:
                managed_strikes.add(int(strike))
        for fp in side_state.get('frozen_positions', []):
            strike = fp.get('strike', 0)
            if strike:
                managed_strikes.add(int(strike))

    # Collect any option positions on the exchange at managed strikes.
    # /v2/positions/margined returns items with symbol in product.symbol or product_symbol.
    live_on_exchange = []
    for ep in all_positions:
        sym = (ep.get('product', {}) or {}).get('symbol', '') or ep.get('product_symbol', '') or ep.get('symbol', '')
        size = ep.get('size', 0)
        if not size or size == 0:
            continue
        if '-BTC-' not in sym:
            continue
        parts = sym.split('-')
        if len(parts) >= 3:
            try:
                strike = int(parts[2])
                if strike in managed_strikes:
                    live_on_exchange.append({
                        'symbol': sym,
                        'size': size,
                        'strike': strike,
                    })
            except (ValueError, IndexError):
                pass

    if not live_on_exchange:
        log.info(f"[{sid}] EXIT ALL verify: exchange confirmed — no positions at managed strikes")
        return

    # Positions found — mark unverified and alert. Do NOT place any orders here.
    # The operator must manually determine whether these belong to this session
    # or to another concurrently-running algo at the same strike.
    session['_exit_all_unverified'] = True
    session['_exit_all_partial'] = True
    session['_exit_all_failed_positions'] = live_on_exchange
    log.error(
        f"[{sid}] EXIT ALL verify: {len(live_on_exchange)} position(s) still on exchange "
        f"at managed strikes: {live_on_exchange}. "
        f"Could belong to another session — manual verification required."
    )
    try:
        from .mmm_telegram import send_telegram_message
        send_telegram_message(
            f"⚠️ [{sid}] EXIT ALL: {len(live_on_exchange)} position(s) still open at managed "
            f"strike(s): {[p['symbol'] for p in live_on_exchange]}. "
            f"May belong to another algo — check exchange manually."
        )
    except Exception:
        pass


def _collect_side_positions(session: Dict, side_key: str, spot_price: float) -> List[Dict]:
    """
    Collect all open positions for one side from positions[], sorted by risk priority.

    Priority order:
      1. ATM proximity ascending (closest to ATM = highest gamma/delta risk = close first)
      2. Lots descending (larger exposure first within same strike band)
      3. Type: original > adjustment > shifted (frozen are lowest risk, close last)

    Note: _force_clear_being_closed() is called once before the first round, so
    any stale flags from prior heartbeat scans are already gone by the time this
    function runs. The guard here only skips positions genuinely in-flight within
    this exit session (set by an earlier round's close attempt that is still pending).
    """
    side_state = session.get(side_key, {})
    if not isinstance(side_state, dict):
        return []

    # Map type string from positions[] to risk tier
    _type_order = {'original': 0, 'adjustment': 1, 'shifted': 2}

    results = []
    for pos in side_state.get('positions', []):
        if pos.get('status') == 'closed':
            # Only skip a 'closed' position if the fill was explicitly confirmed by
            # fill_sync (_fill_confirmed=True).  Positions marked 'closed' WITHOUT
            # fill confirmation were written prematurely (e.g. close_at_5 marks status
            # before the fill arrives).  Include them so exit_all re-attempts the close
            # using reduce_only=True — if the position is truly gone on exchange the
            # order fails gracefully with no_position_for_reduce_only (treated as success).
            # This is the fix for the mmm25apr26-1 incident (79000 lots missed).
            if pos.get('_fill_confirmed'):
                continue
            # Unconfirmed-closed: fall through and include below
        if pos.get('lots', 0) <= 0:
            continue
        # Skip genuinely in-flight positions (fresh _being_closed flags).
        # Stale flags (>180s) are auto-cleared by close_position() on the next
        # close attempt so we include them here and let close_position handle it.
        if pos.get('_being_closed'):
            import time as _time
            set_at = pos.get('_being_closed_at', 0)
            if set_at and _time.monotonic() - set_at <= 180:
                log.debug(
                    f"[{session.get('session_id', '?')}] EXIT ALL: skipping "
                    f"{side_key.upper()} pos {pos.get('id')} — _being_closed (in-flight)"
                )
                continue

        pos_type_raw = pos.get('type', 'original')
        # positions[] uses 'status'='shifted' for frozen; map type for sort
        pos_type = pos.get('type', 'original')
        if pos.get('status') == 'shifted':
            pos_type = 'shifted'

        strike = float(pos.get('strike', 0))
        lots = int(pos.get('lots', 0))
        entry_premium = float(pos.get('entry_premium', 0))

        results.append({
            'side': side_key,
            'strike': strike,
            'lots': lots,
            'entry_premium': entry_premium,
            'current_premium': 0,   # placeholder — close_position fetches actual price
            'type': pos_type_raw,   # 'original' | 'adjustment' | 'frozen' (for close_position)
            'profit': 0,
            '_pos_id': pos.get('id'),
            '_sort_type': pos_type,
        })

    if not results:
        return []

    _type_order_sort = {'original': 0, 'adjustment': 1, 'shifted': 2}

    def sort_key(p):
        atm_dist = abs(spot_price - p['strike']) if spot_price > 0 else 0
        return (atm_dist, -p['lots'], _type_order_sort.get(p.get('_sort_type', 'original'), 1))

    results.sort(key=sort_key)

    # Remove internal sort key before passing to close_position
    for p in results:
        p.pop('_sort_type', None)

    return results


def _count_open_positions(session: Dict) -> int:
    """Count positions with > 0 lots and status != 'closed' across both sides."""
    count = 0
    for sk in ('ce', 'pe'):
        side_state = session.get(sk, {})
        if not isinstance(side_state, dict):
            continue
        for pos in side_state.get('positions', []):
            if pos.get('status') != 'closed' and pos.get('lots', 0) > 0:
                count += 1
    return count


def _build_failed_list(session: Dict) -> List[Dict]:
    """Build a list of still-open positions for the partial-exit alert."""
    failed = []
    for sk in ('ce', 'pe'):
        side_state = session.get(sk, {})
        if not isinstance(side_state, dict):
            continue
        for pos in side_state.get('positions', []):
            if pos.get('status') != 'closed' and pos.get('lots', 0) > 0:
                failed.append({
                    'side': sk,
                    'strike': pos.get('strike'),
                    'lots': pos.get('lots'),
                    'id': pos.get('id'),
                    'type': pos.get('type', 'unknown'),
                })
    return failed


async def _reopen_unverified_closed_positions(monitor, session: Dict, sid: str) -> None:
    """
    Order-ID-based pre-flight before exit rounds.

    For every position marked status='closed', query its close_order_id directly
    via GET /v2/orders/{id} and check that filled_size covers all lots.  Positions
    that are NOT fully confirmed are reset to status='active' so the normal exit
    rounds re-close them.

    Why this is the right fix (not fill_sync or position sweeps):
      - close_order_id is THIS session's own order — no ambiguity with other algos
      - GET /v2/orders/{id} is deterministic — no time-cursor, no fill matching
      - reduce_only on re-close is safe: if truly closed, exchange rejects gracefully
      - Does not query or touch any position not owned by this session

    Sets _fill_confirmed=True on verified-closed positions so _collect_side_positions
    does not redundantly re-include them.
    """
    executor = monitor.executor
    reopened = 0

    for sk in ('ce', 'pe'):
        side_state = session.get(sk, {})
        if not isinstance(side_state, dict):
            continue
        for pos in side_state.get('positions', []):
            if pos.get('status') != 'closed':
                continue
            lots = int(pos.get('lots', 0) or 0)
            if lots <= 0:
                continue

            close_oid = str(pos.get('close_order_id', '') or '').strip()

            # Case 1: marked 'closed' but no close_order_id recorded.
            # close_at_5 / wind_down always sets close_order_id before marking
            # closed.  If it is missing, the status was written prematurely.
            if not close_oid:
                pos['status'] = 'active'
                pos['_fill_confirmed'] = False
                reopened += 1
                log.warning(
                    f"[{sid}] EXIT pre-flight: reopening {sk.upper()} "
                    f"pos {pos.get('id')} @ {pos.get('strike')} — "
                    f"status='closed' but no close_order_id recorded"
                )
                continue

            # Case 2: has close_order_id — query exchange directly
            try:
                order_data = await executor._get_order_status(close_oid)
            except Exception as qe:
                order_data = None
                log.warning(
                    f"[{sid}] EXIT pre-flight: order query failed for "
                    f"{close_oid} ({qe}) — reopening conservatively"
                )

            if order_data is None:
                # Could not reach exchange or order expired from API.
                # Conservatively reopen so exit rounds retry.
                pos['status'] = 'active'
                pos['_fill_confirmed'] = False
                reopened += 1
                log.warning(
                    f"[{sid}] EXIT pre-flight: reopening {sk.upper()} "
                    f"pos {pos.get('id')} @ {pos.get('strike')} — "
                    f"close_order {close_oid} not found on exchange"
                )
                continue

            # Compute filled lots from exchange order data.
            # Delta returns: size (original), unfilled_size (remaining).
            order_size = int(order_data.get('size', 0) or 0)
            unfilled = int(order_data.get('unfilled_size', 0) or 0)
            filled_size = order_size - unfilled if order_size > 0 else 0
            # Fallback: some responses carry filled_size directly
            if filled_size <= 0:
                filled_size = int(order_data.get('filled_size', 0) or 0)

            state = (
                order_data.get('state', '') or order_data.get('status', '')
            ).lower()

            fully_confirmed = (filled_size >= lots) or (state in {'filled', 'closed', 'completed'} and filled_size > 0)

            if fully_confirmed:
                # Genuine close confirmed by exchange order record.
                # Stamp _fill_confirmed so _collect_side_positions skips it.
                pos['_fill_confirmed'] = True
                log.debug(
                    f"[{sid}] EXIT pre-flight: {sk.upper()} pos {pos.get('id')} "
                    f"@ {pos.get('strike')} confirmed closed "
                    f"(order {close_oid} state={state}, filled={filled_size}/{lots})"
                )
            else:
                # Close not fully confirmed — reopen for re-close attempt
                pos['status'] = 'active'
                pos['_fill_confirmed'] = False
                reopened += 1
                log.warning(
                    f"[{sid}] EXIT pre-flight: reopening {sk.upper()} "
                    f"pos {pos.get('id')} @ {pos.get('strike')} — "
                    f"close_order {close_oid} state={state}, "
                    f"filled={filled_size}/{lots} lots (not fully confirmed)"
                )

    if reopened:
        log.warning(
            f"[{sid}] EXIT pre-flight: {reopened} position(s) reopened "
            f"after order-ID verification — exit rounds will re-close them"
        )
        _enqueue_exit_event(sid, 'PREFLIGHT_REOPEN', {
            'reopened_count': reopened,
            'reason': 'close_order not fully confirmed on exchange',
        })
        try:
            from .mmm_telegram import send_telegram_message
            send_telegram_message(
                f"⚠️ [{sid}] EXIT ALL pre-flight: {reopened} position(s) were marked "
                f"'closed' in session but close order not confirmed on exchange — "
                f"re-closing now."
            )
        except Exception:
            pass


def _reopen_from_ledger(session: Dict, sid: str) -> None:
    """
    Sub-ledger net-lots check: reopen any position that the ledger shows
    as still having open short lots, even if positions[] says closed.

    The ledger (mmm_ledger.py) records every fill (sell + buy) tagged by
    session_id. If sell_fills > buy_fills for a symbol, the session still
    has open short exposure — regardless of what _fill_confirmed says.

    Positions are matched to ledger by building the same symbol the position
    would have (option_type + underlying + strike + expiry). If the ledger
    shows net_lots > 0 for a symbol that positions[] marks closed, the
    position is reopened for exit rounds to re-close (reduce_only=True).

    Fail-safe: all ledger errors are caught; session close proceeds even
    if ledger is unavailable (belt-and-suspenders, not a hard dependency).
    """
    try:
        from .mmm_ledger import get_session_open_symbols
    except Exception as _le:
        log.warning(f"[{sid}] EXIT pre-flight ledger: import failed ({_le}) — skipping")
        return

    try:
        open_symbols = get_session_open_symbols(sid)
    except Exception as _qe:
        log.warning(f"[{sid}] EXIT pre-flight ledger: query failed ({_qe}) — skipping")
        return

    if not open_symbols:
        log.debug(f"[{sid}] EXIT pre-flight ledger: no open symbols found")
        return

    # Build a map of symbol → net_lots from ledger
    ledger_open = {entry['symbol']: entry['net_lots'] for entry in open_symbols}

    reopened = 0
    for sk in ('ce', 'pe'):
        side_state = session.get(sk, {})
        if not isinstance(side_state, dict):
            continue
        for pos in side_state.get('positions', []):
            if pos.get('status') != 'closed':
                continue
            pos_symbol = pos.get('symbol', '')
            if not pos_symbol:
                continue
            ledger_lots = ledger_open.get(pos_symbol, 0)
            if ledger_lots <= 0:
                continue
            # Ledger shows open lots; positions[] says closed — discrepancy
            pos['status'] = 'active'
            pos['_fill_confirmed'] = False
            # Adjust lots to match what ledger says is still open (may differ
            # from original lots if partially closed)
            if ledger_lots < pos.get('lots', 0):
                pos['lots'] = ledger_lots
            reopened += 1
            log.warning(
                f"[{sid}] EXIT pre-flight ledger: reopening {sk.upper()} "
                f"pos {pos.get('id')} @ {pos.get('strike')} — "
                f"ledger shows {ledger_lots} lots still open at {pos_symbol}"
            )

    if reopened:
        log.warning(
            f"[{sid}] EXIT pre-flight ledger: {reopened} position(s) reopened "
            f"from sub-ledger mismatch — exit rounds will re-close them"
        )
        _enqueue_exit_event(sid, 'LEDGER_PREFLIGHT_REOPEN', {
            'reopened_count': reopened,
            'open_symbols': [s['symbol'] for s in open_symbols],
        })
        try:
            from .mmm_telegram import send_telegram_message
            send_telegram_message(
                f"⚠️ [{sid}] EXIT ALL ledger pre-flight: {reopened} position(s) marked "
                f"'closed' in session but sub-ledger shows open lots — re-closing."
            )
        except Exception:
            pass


async def _cancel_pending_for_kill_switch(monitor, sid: str) -> None:
    """
    Cancel any in-flight adjustment orders before kill switch closes.

    The pending_orders registry tracks SELL orders placed during the last heartbeat.
    If kill switch fires mid-heartbeat those orders are still open on the exchange and
    must be cancelled before market buy orders go out — otherwise we'd end up with
    extra short legs while simultaneously closing.

    Best-effort: failure to cancel a single order is logged but never blocks the close.
    """
    try:
        from .mmm_pending_orders import get_pending, clear_all as clear_all_pending
        executor = monitor.executor
        for side in ('ce', 'pe'):
            pending = get_pending(sid, side)
            if not pending:
                continue
            order_id = pending.get('order_id', '')
            if not order_id or order_id == 'pending':
                continue
            # Look up the exchange order to get its product_id (needed by cancel_order)
            try:
                order_data = await executor._get_order_status(order_id)
                if order_data:
                    product_id = order_data.get('product_id')
                    if product_id:
                        cancelled = await executor._cancel_order(order_id, int(product_id))
                        log.warning(
                            f"[{sid}] KILL SWITCH: Cancel pending {side.upper()} "
                            f"order {order_id}: {'ok' if cancelled else 'failed/already gone'}"
                        )
                    else:
                        log.warning(
                            f"[{sid}] KILL SWITCH: No product_id for pending {side.upper()} "
                            f"order {order_id} — skipping cancel"
                        )
            except Exception as _ce:
                log.warning(
                    f"[{sid}] KILL SWITCH: Could not cancel pending {side.upper()} "
                    f"order {order_id}: {_ce}"
                )
        # Clear in-memory registry regardless — no new adjustment should retry
        clear_all_pending(sid)
    except Exception as e:
        log.warning(f"[{sid}] KILL SWITCH: _cancel_pending_for_kill_switch failed: {e} — continuing")


def _force_clear_being_closed(session: Dict, sid: str) -> None:
    """
    Force-clear _being_closed on every position in both sides.

    Safe to call at exit_all entry because the EXITING gate in _heartbeat_inner()
    prevents any concurrent close_at_5 / normal heartbeat logic from running.
    Without this, stale in-flight flags from a prior heartbeat scan block all
    exit rounds (3 rounds × 2s delay = 6s, never reaches 180s TTL auto-clear).
    """
    cleared = 0
    for sk in ('ce', 'pe'):
        side_state = session.get(sk, {})
        if not isinstance(side_state, dict):
            continue
        for pos in side_state.get('positions', []):
            if pos.get('_being_closed'):
                pos['_being_closed'] = False
                pos.pop('_being_closed_at', None)
                cleared += 1
    if cleared:
        log.warning(f"[{sid}] EXIT ALL: Cleared {cleared} stale _being_closed flag(s) before exit rounds")


# =============================================================================
# WebSocket emitters (fire-and-forget, never raise)
# =============================================================================

def _emit_exit_progress(sid: str, round_num: int, closed_count: int,
                         remaining_count: int, failed_count: int) -> None:
    try:
        from .mmm_websocket import emit_to_session
        emit_to_session(sid, 'mmm_exit_progress', {
            'round': round_num,
            'max_rounds': MAX_EXIT_ROUNDS,
            'closed_count': closed_count,
            'remaining_count': remaining_count,
            'failed_count': failed_count,
        })
    except Exception:
        pass


def _emit_exit_completed(sid: str, completed_at: str, initiated_at: str) -> None:
    try:
        from .mmm_websocket import emit_to_session
        duration_ms = 0
        try:
            start = datetime.fromisoformat(initiated_at.replace('Z', '+00:00'))
            end = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
            duration_ms = int((end - start).total_seconds() * 1000)
        except Exception:
            pass
        emit_to_session(sid, 'mmm_exit_completed', {
            'completed_at': completed_at,
            'duration_ms': duration_ms,
        })
    except Exception:
        pass


def _emit_exit_partial(sid: str, failed_positions: List[Dict]) -> None:
    try:
        from .mmm_websocket import emit_to_session
        emit_to_session(sid, 'mmm_exit_partial', {
            'failed_positions': failed_positions,
            'message': (
                f'{len(failed_positions)} position(s) could not be closed automatically. '
                'Please close them manually on the exchange.'
            ),
        })
    except Exception:
        pass
