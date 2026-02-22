"""
MMM Pending Order Guard

Prevents duplicate adjustment orders by tracking in-flight orders per session
per side.  Before each adjustment execution the monitor checks this registry:

  - If there is a pending order for that side, the exchange is queried for its
    current state:
      • Filled  → record the fill in session state, skip new order.
      • Open    → order still working, skip new order (avoid accumulation).
      • Dead    → cancelled/rejected, clear registry, allow new order.
  - If no pending order, allow execution and register after placement.

This is the institutional-grade guard that prevents the "double position"
scenario where smart_execute times out or cancel+replace leaves a dangling
open order and the next heartbeat re-triggers the same sign.

Created: February 18, 2026
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Any

log = logging.getLogger('mmm_pending_orders')

# ─────────────────────────────────────────────────────────────────────────────
# In-memory registry — survives intra-session restarts but clears on backend
# restart (intentional: stale orders from previous run should be verified fresh)
# ─────────────────────────────────────────────────────────────────────────────

_lock = threading.Lock()

# Structure:
# {
#   session_id: {
#     'ce': { order_id, symbol, lots, strike, placed_at, adj_type },
#     'pe': { order_id, symbol, lots, strike, placed_at, adj_type },
#   }
# }
_registry: Dict[str, Dict[str, Optional[Dict]]] = {}

# Order states that mean "it got filled"
_STATES_FILLED = {'filled', 'closed', 'completed'}
# Order states that mean "it's dead / gone"
_STATES_DEAD   = {'cancelled', 'canceled', 'rejected', 'expired'}
# Time after which we consider an unverifiable order stale and allow a new one
_STALE_SECONDS = 900  # 15 minutes


def register_pending(
    session_id: str,
    side: str,
    order_id: str,
    symbol: str,
    lots: int,
    strike: float,
    adj_type: str = 'standard',
) -> None:
    """Register an in-flight adjustment order before it is confirmed filled."""
    with _lock:
        session_entry = _registry.setdefault(session_id, {'ce': None, 'pe': None})
        session_entry[side] = {
            'order_id': str(order_id),
            'symbol': symbol,
            'lots': lots,
            'strike': strike,
            'adj_type': adj_type,
            'placed_at': datetime.now(timezone.utc).isoformat(),
        }
        log.info(
            f"[{session_id}] Pending order registered: "
            f"{side.upper()} order {order_id} ({lots} lots @ {strike})"
        )


def clear_pending(session_id: str, side: str) -> None:
    """Clear the pending order for a side (after confirmed fill or confirmed dead)."""
    with _lock:
        entry = _registry.get(session_id, {})
        if entry.get(side):
            order_id = entry[side].get('order_id', '?')
            entry[side] = None
            log.info(f"[{session_id}] Pending order cleared: {side.upper()} order {order_id}")


def get_pending(session_id: str, side: str) -> Optional[Dict]:
    """Return the pending order dict for a side, or None."""
    with _lock:
        return (_registry.get(session_id) or {}).get(side)


def clear_all(session_id: str) -> None:
    """Clear ALL pending orders for a session (on stop/reset)."""
    with _lock:
        _registry.pop(session_id, None)
        log.info(f"[{session_id}] All pending orders cleared")


# ─────────────────────────────────────────────────────────────────────────────
# Exchange verification helper
# ─────────────────────────────────────────────────────────────────────────────

async def check_and_resolve_pending(
    session_id: str,
    side: str,
    session: Dict,
    rest_client: Any,
    record_fill_fn,
) -> str:
    """
    Check if there's a pending order for this side and resolve its state.

    Args:
        session_id:     MMM session ID
        side:           'ce' or 'pe'
        session:        Full session dict (mutated if fill is recorded)
        rest_client:    AsyncDeltaClient instance (already created for this beat)
        record_fill_fn: Callable(session, side, strike, lots, fill_price, adj_type)
                        to record a confirmed fill into session state.

    Returns one of:
        'none'         — no pending order, proceed with new order
        'filled'       — pending order was filled; state recorded; skip new order
        'open'         — pending order still open; skip new order
        'dead'         — pending order is dead/cancelled; proceed with new order
        'stale'        — pending order is too old to verify; proceed with new order
        'error'        — could not verify; treat conservatively as 'open'
    """
    pending = get_pending(session_id, side)
    if not pending:
        return 'none'

    order_id = pending['order_id']
    symbol   = pending['symbol']
    strike   = pending['strike']
    lots     = pending['lots']
    adj_type = pending.get('adj_type', 'standard')
    placed_at_str = pending.get('placed_at', '')

    # Stale check: if placed > 15 min ago and we still can't verify, let through
    if placed_at_str:
        try:
            placed_dt = datetime.fromisoformat(placed_at_str)
            if placed_dt.tzinfo is None:
                placed_dt = placed_dt.replace(tzinfo=timezone.utc)
            age_seconds = (datetime.now(timezone.utc) - placed_dt).total_seconds()
            if age_seconds > _STALE_SECONDS:
                log.warning(
                    f"[{session_id}] Pending order {order_id} is stale "
                    f"({age_seconds:.0f}s old) — clearing and allowing new order"
                )
                clear_pending(session_id, side)
                return 'stale'
        except (ValueError, TypeError):
            pass

    log.info(
        f"[{session_id}] Checking pending {side.upper()} order {order_id} "
        f"({lots} lots @ {strike}) placed at {placed_at_str}"
    )

    try:
        order_data = await rest_client.get_order(str(order_id))
        if not order_data:
            log.warning(
                f"[{session_id}] Cannot fetch order {order_id} — "
                f"treating as open (conservative)"
            )
            return 'error'

        state = (
            order_data.get('state', '')
            or order_data.get('status', '')
        ).lower()

        if state in _STATES_FILLED:
            # Confirmed fill — extract fill price and record in session state
            raw_fill = order_data.get('average_fill_price')
            if raw_fill and str(raw_fill).strip() not in ('', '0'):
                fill_price = float(raw_fill)
                log.info(
                    f"[{session_id}] Pending order {order_id} CONFIRMED FILLED "
                    f"@ ${fill_price:.2f} — recording fill"
                )
                record_fill_fn(
                    session=session,
                    side=side,
                    strike=strike,
                    lots=lots,
                    fill_price=fill_price,
                    adj_type=adj_type,
                )
                clear_pending(session_id, side)
                return 'filled'
            else:
                # Filled but no average_fill_price yet (exchange lag) — treat as open
                log.warning(
                    f"[{session_id}] Order {order_id} state=filled but no fill price yet — "
                    f"treating as open, will re-check next beat"
                )
                return 'error'

        elif state in _STATES_DEAD:
            log.info(
                f"[{session_id}] Pending order {order_id} is dead ({state}) — "
                f"clearing, allowing new order"
            )
            clear_pending(session_id, side)
            return 'dead'

        else:
            # Still open / partially filled / pending
            unfilled = order_data.get('unfilled_size', '?')
            log.info(
                f"[{session_id}] Pending order {order_id} still {state} "
                f"(unfilled={unfilled}) — skipping new order this beat"
            )
            return 'open'

    except Exception as e:
        log.warning(
            f"[{session_id}] Failed to verify pending order {order_id}: {e} — "
            f"treating as open (conservative)"
        )
        return 'error'
