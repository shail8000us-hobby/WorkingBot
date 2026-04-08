"""
MMMX Profit Booking — Per-Tranche Selective Close

Allows operator-requested or rule-based partial close of individual tranches
once their unrealized P&L reaches a target percentage of premium collected.

Spec: MMMX_COMPLETE.md — Profit Booking section.

Key design rules:
  - queue_close() adds a booking request to session['_profit_booking_queue'].
  - process_pending() checks each queued tranche each beat; closes if target met.
  - close_tranche() uses smart_execute (not emergency) — operator-triggered close.
  - Both deployment and recovery tranches can be profit-booked identically.
  - Closing a deployment tranche frees the deployment slot:
      tranches_deployed -= 1, tranches_remaining += 1.
  - Recovery tranches do NOT change tranches_deployed/remaining counters.
  - hard_stop_usd is recalculated after every close (premium changes).
  - Isolation: ZERO imports from routes.mmm.* in this file.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .mmmx_constants import (
    TrncStatus,
    TrncType,
    LOT_SIZE_BTC,
    SMART_EXECUTE_REPRICE_ATTEMPTS,
)
from .mmmx_engine import recalc_hard_stop
from .mmmx_websocket import emit_tranche_closed
from .mmmx_activity import log_activity
from .mmmx_telegram import alert_profit_booking

log = logging.getLogger('mmmx_profit_booking')


# ── queue_close ────────────────────────────────────────────────────────────────

def queue_close(
    session: Dict[str, Any],
    tranche_id: Any,
    target_pct: float,
) -> None:
    """
    Add a profit-booking request for tranche_id.

    The request is fulfilled by process_pending() each beat once the tranche's
    unrealized P&L reaches premium_collected × target_pct / 100.

    Validates that the tranche exists and is ACTIVE before queuing.
    Raises ValueError on invalid tranche_id or status.

    Spec: MMMX_COMPLETE.md — profit_booking.queue_close.
    """
    tranche = _find_tranche(session, tranche_id)
    if tranche is None:
        raise ValueError(f"Tranche {tranche_id} not found in session")

    if tranche.get('status') != TrncStatus.ACTIVE:
        raise ValueError(
            f"Tranche {tranche_id} is not ACTIVE (status={tranche.get('status')})"
        )

    if not (0 < target_pct <= 100):
        raise ValueError(f"target_pct must be in (0, 100], got {target_pct}")

    queue = session.setdefault('_profit_booking_queue', [])

    # Avoid duplicate entries for same tranche
    for entry in queue:
        if entry.get('tranche_id') == tranche_id:
            log.info(
                f"[ProfitBooking] Tr{tranche_id} already queued at "
                f"{entry.get('target_pct')}% — updating to {target_pct}%"
            )
            entry['target_pct'] = target_pct
            entry['queued_at'] = datetime.now(timezone.utc).isoformat()
            return

    queue.append({
        'tranche_id': tranche_id,
        'target_pct': target_pct,
        'queued_at':  datetime.now(timezone.utc).isoformat(),
    })
    log.info(
        f"[ProfitBooking] Tr{tranche_id} queued for close at {target_pct}% of premium."
    )


# ── process_pending ────────────────────────────────────────────────────────────

async def process_pending(
    session: Dict[str, Any],
    executor: Any,
    audit: Any,
    save_fn: Optional[Callable] = None,
) -> List[Dict]:
    """
    Check each queued profit-booking request and close tranches whose target is met.

    P&L condition: tranche unrealized_pnl >= premium_collected × target_pct / 100

    Returns a list of result dicts from close_tranche() for each closed tranche.

    Spec: MMMX_COMPLETE.md — profit_booking.process_pending.
    """
    queue = session.get('_profit_booking_queue', [])
    if not queue:
        return []

    results = []
    still_pending = []

    for entry in list(queue):
        tranche_id = entry['tranche_id']
        target_pct = float(entry['target_pct'])

        tranche = _find_tranche(session, tranche_id)
        if tranche is None:
            log.warning(
                f"[ProfitBooking] Tr{tranche_id} no longer in session — removing from queue."
            )
            continue   # drop from queue

        if tranche.get('status') != TrncStatus.ACTIVE:
            log.info(
                f"[ProfitBooking] Tr{tranche_id} is {tranche.get('status')} — removing from queue."
            )
            continue   # tranche already closed; drop

        # Compute current P&L for this tranche
        ce_pnl = float(tranche.get('ce', {}).get('unrealized_pnl', 0.0))
        pe_pnl = float(tranche.get('pe', {}).get('unrealized_pnl', 0.0))
        current_pnl = ce_pnl + pe_pnl
        premium = float(tranche.get('premium_collected', 0.0))
        target_usd = premium * target_pct / 100.0

        if current_pnl >= target_usd:
            log.info(
                f"[ProfitBooking] Tr{tranche_id}: P&L ${current_pnl:.2f} >= "
                f"target ${target_usd:.2f} ({target_pct}% of ${premium:.2f}). Closing."
            )
            result = await close_tranche(session, tranche_id, executor, audit)
            results.append(result)
            if result.get('success') and save_fn:
                try:
                    ok = save_fn(session)
                    if not ok:
                        log.error(
                            f"[ProfitBooking] Mid-beat persist failed after closing Tr{tranche_id}."
                        )
                except Exception as exc:
                    log.error(f"[ProfitBooking] save_fn raised: {exc}")
            # Whether close succeeded or failed, remove from queue to avoid retry loops
            # (if failed, operator must re-queue manually)
        else:
            still_pending.append(entry)

    session['_profit_booking_queue'] = still_pending
    return results


# ── close_tranche ──────────────────────────────────────────────────────────────

async def close_tranche(
    session: Dict[str, Any],
    tranche_id: Any,
    executor: Any,
    audit: Any,
) -> Dict[str, Any]:
    """
    Close both legs of a tranche via smart_execute (buy-to-close).

    Execution strategy:
      - CE leg: smart_execute(side='buy', reduce_only=True) — up to 4 reprice attempts
      - PE leg: smart_execute(side='buy', reduce_only=True) — up to 4 reprice attempts
      - Both legs attempted independently; partial close logged but not rolled back.
      - On both legs closed: tranche marked CLOSED; capacity freed (deployment tranches only);
        hard_stop_usd recalculated; profit booked to session['profit_booked_total'].

    Returns:
        {'success': bool, 'pnl_usd': float, 'tranche_id': any, 'ce_closed': bool, 'pe_closed': bool,
         'reason': str}

    Spec: MMMX_COMPLETE.md — profit_booking.close_tranche.
    """
    session_id = session.get('session_id', '')
    tranche = _find_tranche(session, tranche_id)

    if tranche is None:
        return {
            'success': False,
            'tranche_id': tranche_id,
            'pnl_usd': 0.0,
            'ce_closed': False,
            'pe_closed': False,
            'reason': f"Tranche {tranche_id} not found",
        }

    ce_leg = tranche.get('ce', {})
    pe_leg = tranche.get('pe', {})

    ce_symbol = ce_leg.get('symbol', '')
    pe_symbol = pe_leg.get('symbol', '')
    ce_lots   = int(ce_leg.get('lots', 0))
    pe_lots   = int(pe_leg.get('lots', 0))

    ce_closed = False
    pe_closed = False
    ce_fees   = 0.0
    pe_fees   = 0.0
    close_reason_text = ''

    # -- Close CE leg ────────────────────────────────────────────────────────────
    if ce_lots > 0 and ce_leg.get('status') == TrncStatus.ACTIVE:
        ce_result = await executor.smart_execute(
            symbol=ce_symbol,
            side='buy',
            size=ce_lots,
            reduce_only=True,
            max_reprice_attempts=SMART_EXECUTE_REPRICE_ATTEMPTS,
            use_bid_entry=True,
            session_id=session_id,
            tranche_id=tranche_id,
            action=f'PROFIT_BOOK_CE_{tranche_id}',
            position=ce_leg,
        )
        if ce_result.success:
            ce_closed = True
            ce_fees = float(ce_result.fees_paid or 0.0)
            # Update realized P&L for the leg
            exit_price = float(ce_result.avg_price or ce_leg.get('entry_premium', 0.0))
            entry_price = float(ce_leg.get('entry_premium', 0.0))
            lots = ce_lots
            # SHORT: realized = (entry - exit) × lots × LOT_SIZE_BTC
            realized = (entry_price - exit_price) * lots * LOT_SIZE_BTC
            ce_leg['realized_pnl'] = float(ce_leg.get('realized_pnl', 0.0)) + realized
            ce_leg['fees_paid']    = float(ce_leg.get('fees_paid', 0.0)) + ce_fees
            ce_leg['status']       = TrncStatus.CLOSED
            ce_leg['_being_closed'] = False
        else:
            close_reason_text += f"CE close failed: {ce_result.reason}. "
            log.error(
                f"[ProfitBooking] Tr{tranche_id} CE close failed: {ce_result.reason}"
            )
    elif ce_leg.get('status') != TrncStatus.ACTIVE:
        ce_closed = True   # already closed

    # -- Close PE leg ────────────────────────────────────────────────────────────
    if pe_lots > 0 and pe_leg.get('status') == TrncStatus.ACTIVE:
        pe_result = await executor.smart_execute(
            symbol=pe_symbol,
            side='buy',
            size=pe_lots,
            reduce_only=True,
            max_reprice_attempts=SMART_EXECUTE_REPRICE_ATTEMPTS,
            use_bid_entry=True,
            session_id=session_id,
            tranche_id=tranche_id,
            action=f'PROFIT_BOOK_PE_{tranche_id}',
            position=pe_leg,
        )
        if pe_result.success:
            pe_closed = True
            pe_fees = float(pe_result.fees_paid or 0.0)
            exit_price  = float(pe_result.avg_price or pe_leg.get('entry_premium', 0.0))
            entry_price = float(pe_leg.get('entry_premium', 0.0))
            lots = pe_lots
            realized = (entry_price - exit_price) * lots * LOT_SIZE_BTC
            pe_leg['realized_pnl'] = float(pe_leg.get('realized_pnl', 0.0)) + realized
            pe_leg['fees_paid']    = float(pe_leg.get('fees_paid', 0.0)) + pe_fees
            pe_leg['status']       = TrncStatus.CLOSED
            pe_leg['_being_closed'] = False
        else:
            close_reason_text += f"PE close failed: {pe_result.reason}."
            log.error(
                f"[ProfitBooking] Tr{tranche_id} PE close failed: {pe_result.reason}"
            )
    elif pe_leg.get('status') != TrncStatus.ACTIVE:
        pe_closed = True   # already closed

    both_closed = ce_closed and pe_closed
    total_realized = (
        float(ce_leg.get('realized_pnl', 0.0)) +
        float(pe_leg.get('realized_pnl', 0.0))
    )
    total_fees = ce_fees + pe_fees

    if both_closed:
        # Mark tranche CLOSED
        tranche['status']        = TrncStatus.CLOSED
        tranche['close_reason']  = 'profit_booking'
        tranche['closed_at']     = datetime.now(timezone.utc).isoformat()

        # Free deployment slot (deployment tranches only)
        if tranche.get('type') == TrncType.DEPLOYMENT:
            session['tranches_deployed']  = max(0, int(session.get('tranches_deployed', 0)) - 1)
            session['tranches_remaining'] = int(session.get('tranches_remaining', 0)) + 1

        # Book profit
        session['profit_booked_total'] = (
            float(session.get('profit_booked_total', 0.0)) + total_realized
        )

        # Recalculate hard stop (total_premium_collected unchanged — we don't subtract)
        session['hard_stop_usd'] = recalc_hard_stop(session)

        # Update session fee tracking
        ft = session.setdefault('fees_tracking', {})
        ft['total_fees_paid'] = float(ft.get('total_fees_paid', 0.0)) + total_fees
        ft['last_fee_charge'] = datetime.now(timezone.utc).isoformat()

        log.info(
            f"[ProfitBooking] Tr{tranche_id} fully closed. "
            f"realized_pnl=${total_realized:.2f}, fees=${total_fees:.4f}"
        )

        # Telegram
        try:
            alert_profit_booking(session_id, tranche_id, total_realized)
        except Exception:
            pass

        # WebSocket
        try:
            emit_tranche_closed(
                session_id=session_id,
                tranche_id=tranche_id,
                reason='profit_booking',
                pnl_usd=total_realized,
            )
        except Exception:
            pass

        # Audit log
        try:
            audit.enqueue_event(
                session_id=session_id,
                category='PROFIT_BOOKING',
                message=f"Tr{tranche_id} profit-booked: ${total_realized:.2f}",
                data={
                    'tranche_id': tranche_id,
                    'realized_pnl': total_realized,
                    'fees': total_fees,
                },
            )
        except Exception:
            pass

        # Activity log
        try:
            log_activity(
                event_type='profit_booking',
                message=f"Tr{tranche_id} closed via profit booking: ${total_realized:.2f}",
                session_id=session_id,
                level='info',
                data={'tranche_id': tranche_id, 'pnl': total_realized},
            )
        except Exception:
            pass

    return {
        'success':    both_closed,
        'tranche_id': tranche_id,
        'pnl_usd':    total_realized,
        'ce_closed':  ce_closed,
        'pe_closed':  pe_closed,
        'reason':     close_reason_text if not both_closed else 'ok',
    }


# ── Private helpers ────────────────────────────────────────────────────────────

def _find_tranche(session: Dict[str, Any], tranche_id: Any) -> Optional[Dict]:
    """Find tranche by ID in session['tranches']. Returns None if not found."""
    for t in session.get('tranches', []):
        if t.get('tranche_id') == tranche_id:
            return t
    return None
