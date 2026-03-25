"""
SSDH Kill Switch — Emergency Flatten-All

No conditions, no waiting. Closes all active positions at market immediately.

Rule: Kill switch does NOT check _being_closed flags — overrides them all.
Exchange deduplication handles any duplicate orders.

Created: March 21, 2026
"""

import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger('ssdh_kill')


async def run_kill_switch(session: dict, executor) -> dict:
    """
    1. Set session status = STATUS_EMERGENCY (overrides any current status)
    2. Emit emit_kill_switch()
    3. Log activity 'kill_switch'
    4. Close ALL active positions at market in parallel (asyncio.gather)
    5. Exchange verification
    6. Set status = STATUS_CLOSED, close_reason = CLOSE_KILL
    7. Persist session
    8. Return {'success': bool, 'positions_closed': int, 'errors': []}

    Note: This bypasses _being_closed. If a close is already in-flight, the
    market order races it. The exchange handles the duplicate (only one fill
    per position).
    """
    from .ssdh_state import (
        get_active_positions, mark_position_closed, recompute_net_pnl,
        persist_session, STATUS_EMERGENCY, STATUS_CLOSED, CLOSE_KILL, POS_ACTIVE,
    )
    from .ssdh_activity import log_activity
    from .ssdh_websocket import emit_kill_switch, emit_session_closed

    sid = session['session_id']

    # Step 1: Set EMERGENCY
    session['status']       = STATUS_EMERGENCY
    session['close_reason'] = CLOSE_KILL
    persist_session(session)

    # Step 2+3
    try:
        emit_kill_switch(sid)
    except Exception:
        pass
    log_activity('kill_switch', 'Kill switch activated — closing all positions at market',
        sid, 'error')

    # Step 4: Close all active positions at market in parallel
    active = get_active_positions(session)

    errors = []
    closed = 0

    async def _kill_one(pos: dict) -> None:
        nonlocal closed
        symbol = pos.get('symbol', '')
        # Override _being_closed — kill switch takes priority
        pos['_being_closed']    = True
        pos['_being_closed_at'] = None

        result = await executor.emergency_execute(pos, sid, symbol)
        if result.get('success'):
            mark_position_closed(
                position               = pos,
                close_premium          = result.get('fill_price', 0.0),
                close_order_id         = result.get('order_id', ''),
                close_client_order_id  = result.get('client_order_id', ''),
                close_reason           = CLOSE_KILL,
                session                = session,
                fees                   = result.get('fees', 0.0),
            )
            closed += 1
        else:
            err = f"{pos['pos_id']}: {result.get('error', 'unknown error')}"
            errors.append(err)
            log.error("[%s] kill_switch: failed to close %s: %s", sid, pos['pos_id'], err)
            # Clear flag so monitor/operator can retry
            pos['_being_closed'] = False

    if active:
        await asyncio.gather(*[_kill_one(p) for p in active], return_exceptions=True)

    # Step 5: Refresh P&L after all closes
    recompute_net_pnl(session)

    # Step 6: Mark closed
    now = datetime.now(timezone.utc).isoformat()
    session['status']    = STATUS_CLOSED
    session['closed_at'] = now
    persist_session(session)

    # Step 7: Emit
    try:
        emit_session_closed(sid, session)
    except Exception:
        pass

    log_activity('exit_complete',
        f"Kill switch complete: {closed}/{len(active)} closed, {len(errors)} error(s)",
        sid, 'success' if not errors else 'error')

    return {
        'success':          len(errors) == 0,
        'positions_closed': closed,
        'errors':           errors,
    }
