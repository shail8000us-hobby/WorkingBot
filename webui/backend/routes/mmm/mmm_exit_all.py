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

log = logging.getLogger('mmm_exit_all')

# Max closing rounds before giving up and stopping as partial
MAX_EXIT_ROUNDS = 3

# Seconds to wait between rounds (lets exchange settle)
INTER_ROUND_DELAY_SEC = 1


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

    # Force-clear ALL _being_closed flags before any round begins.
    # During EXITING, the heartbeat gate blocks all normal logic so no concurrent
    # order placements are in-flight. Stale flags from a prior close_at_5 scan
    # would block every round otherwise (3 rounds × 2s = 6s << 180s TTL).
    _force_clear_being_closed(session, sid)

    try:
        await _run_exit_rounds(monitor)
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

async def _run_exit_rounds(monitor) -> None:
    """Execute up to MAX_EXIT_ROUNDS of position closing."""
    session = monitor.session
    sid = monitor.session_id

    # Spot price for ATM-proximity risk sorting
    spot_price = float(session.get('_regime_spot_price') or 0)

    for round_num in range(1, MAX_EXIT_ROUNDS + 1):

        # Check if already done
        if check_both_sides_closed(session):
            log.info(f"[{sid}] EXIT ALL: All positions closed (round {round_num - 1} finished cleanly)")
            return

        session['_exit_all_rounds_attempted'] = round_num

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

        _emit_exit_progress(sid, round_num, 0, total_open,
                            len(session.get('_exit_all_failed_positions', [])))

        closed_count = 0

        # Close CE and PE concurrently within each round.
        # asyncio.gather runs both side coroutines in parallel — each side
        # closes its positions sequentially by ATM proximity (riskiest first).
        # This halves wall-clock time vs the old CE[0]→PE[0]→CE[1]... loop
        # and reduces price slippage on ITM positions.
        async def _close_side(side_key: str, positions_list: list) -> int:
            count = 0
            for pos in positions_list:
                pos_id = pos.get('_pos_id') or f"{side_key}@{pos.get('strike')}"
                try:
                    result = await close_position(
                        executor=monitor.executor,
                        initializer=monitor.initializer,
                        session=session,
                        position=pos,
                        mechanism='exit_all',
                        hedge_guard=False,
                        side=side_key,
                    )
                    if result.get('success'):
                        count += 1
                        log.info(
                            f"[{sid}] EXIT ALL: Closed {side_key.upper()} @ {pos['strike']} "
                            f"({result.get('lots_closed', pos['lots'])} lots, "
                            f"pnl={result.get('realized_pnl', 0):.4f})"
                        )
                    else:
                        err = result.get('error', 'unknown')
                        log.warning(f"[{sid}] EXIT ALL: Failed to close {pos_id}: {err}")
                except Exception as e:
                    log.error(f"[{sid}] EXIT ALL: Exception closing {pos_id}: {e}")
            return count

        ce_count, pe_count = await asyncio.gather(
            _close_side('ce', ce_positions),
            _close_side('pe', pe_positions),
        )
        closed_count = ce_count + pe_count

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
            continue
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
