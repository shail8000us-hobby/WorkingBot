"""
SSDH Reconciler — Exchange State Verification

Periodic check that local session state matches Delta Exchange.
Run on monitor startup and every 10 heartbeats.

Key rules:
- NEVER auto-correct positions with fill_confirmed_at within 120s
  (exchange REST API settlement lag up to 60s)
- SIZE_MISMATCH: log warning only — may be manual trade at same strike
- MISSING_ON_EXCHANGE: verify via get_order(order_id) first
- Uses client_order_id prefix 'ssdh_' to distinguish from MMM/manual orders
- Session expiry in ddmmyyyy format; Delta symbols use ddmmyy suffix

Created: March 21, 2026
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

log = logging.getLogger('ssdh_reconciler')

RECENT_FILL_WINDOW = 120   # seconds — don't touch positions filled within this window


def expiry_to_symbol_suffix(expiry_ddmmyyyy: str) -> str:
    """
    '11032026' → '110326' (ddmm + yy, skip century digits 4-5)

    Session stores expiry as ddmmyyyy (8 digits).
    Delta Exchange symbols use ddmmyy suffix (6 digits).
    Use this everywhere a Delta Exchange symbol string is built.
    NEVER use the raw expiry parameter directly in symbol string comparisons.
    """
    if len(expiry_ddmmyyyy) != 8 or not expiry_ddmmyyyy.isdigit():
        raise ValueError(f"expiry_to_symbol_suffix: expected 8-digit ddmmyyyy, got {expiry_ddmmyyyy!r}")
    dd   = expiry_ddmmyyyy[0:2]
    mm   = expiry_ddmmyyyy[2:4]
    yy   = expiry_ddmmyyyy[6:8]
    return f"{dd}{mm}{yy}"


def _has_recent_fill(position: dict, window_seconds: int = RECENT_FILL_WINDOW) -> bool:
    """
    Returns True if fill_confirmed_at is within window_seconds of now.
    Guards against exchange REST API settlement lag.
    """
    fill_ts = position.get('fill_confirmed_at')
    if not fill_ts:
        return False
    try:
        fill_dt = datetime.fromisoformat(fill_ts.replace('Z', '+00:00'))
        age     = (datetime.now(timezone.utc) - fill_dt).total_seconds()
        return age < window_seconds
    except Exception:
        return False


def _build_symbol(side: str, expiry: str, strike: float) -> str:
    """
    Builds Delta Exchange option symbol.
    e.g. 'C-BTC-100000-210326' for a CE with strike 100000, expiry 21032026
    side: 'CE' → 'C', 'PE' → 'P'
    """
    suffix = expiry_to_symbol_suffix(expiry)
    option_type = 'C' if side == 'CE' else 'P'
    strike_int  = int(strike)
    return f"{option_type}-BTC-{strike_int}-{suffix}"


async def reconcile_session(session: dict, rest_client) -> dict:
    """
    Queries exchange positions for all active SSDH positions.
    Compares with session['positions'].

    Returns:
    {
        'ok':         bool,
        'mismatches': [{'pos_id': str, 'issue': str, 'action': str}]
    }

    Rules:
    - NEVER auto-correct a position with _has_recent_fill=True
    - SIZE_MISMATCH: log warning, do not auto-correct (may be manual trade)
    - MISSING_ON_EXCHANGE: verify via get_order(order_id) first
      - If order filled → trust local state (REST lag)
      - If order unknown → log critical, flag for operator
    - Only considers positions with client_order_id starting with 'ssdh_'
    """
    from .ssdh_state import get_active_positions, POS_ACTIVE
    from .ssdh_activity import log_activity

    sid        = session['session_id']
    expiry     = session['params'].get('expiry', '')
    mismatches = []

    active = get_active_positions(session)
    if not active:
        log_activity('reconciliation_run', 'No active positions to reconcile', sid, 'info')
        return {'ok': True, 'mismatches': []}

    # Fetch exchange positions
    try:
        exchange_positions = await rest_client.get_positions()
        if exchange_positions is None:
            exchange_positions = []
    except Exception as e:
        log.warning("[%s] reconcile_session: get_positions failed: %s", sid, e)
        return {'ok': True, 'mismatches': [], 'note': 'exchange fetch failed — skipping'}

    # Build lookup: {symbol: {size: int, side: str}}
    ex_lookup: Dict[str, dict] = {}
    for ex_pos in (exchange_positions or []):
        sym  = ex_pos.get('product_symbol', '') or ex_pos.get('symbol', '')
        size = abs(int(ex_pos.get('size', 0) or 0))
        if sym:
            ex_lookup[sym] = {'size': size, 'raw': ex_pos}

    for pos in active:
        pos_id = pos['pos_id']
        coid   = pos.get('client_order_id', '')

        # Only reconcile positions placed by SSDH (filter by client_order_id prefix)
        if not coid.startswith('ssdh_'):
            continue

        # Skip positions within recent-fill window
        if _has_recent_fill(pos):
            log.debug("[%s] reconcile: skip %s — recent fill (%ds guard)",
                      sid, pos_id, RECENT_FILL_WINDOW)
            continue

        symbol = pos.get('symbol') or _build_symbol(pos['side'], expiry, pos['strike'])
        ex     = ex_lookup.get(symbol)

        if ex is None:
            # Position not found on exchange — verify via order_id before flagging
            order_id = pos.get('order_id')
            confirmed = False
            if order_id:
                try:
                    order = await rest_client.get_order(order_id)
                    state = str((order or {}).get('state', '') or (order or {}).get('status', '')).lower()
                    if state in {'filled', 'closed', 'completed'}:
                        confirmed = True
                        log.info("[%s] reconcile: %s confirmed filled via order_id (REST lag)",
                                 sid, pos_id)
                except Exception as e:
                    log.warning("[%s] reconcile: get_order(%s) failed: %s", sid, order_id, e)

            if not confirmed:
                issue = f"MISSING_ON_EXCHANGE: {pos['direction']} {pos['side']} @ {pos['strike']}"
                log.critical("[%s] reconcile: %s — %s", sid, pos_id, issue)
                log_activity('reconciliation_mismatch', issue, sid, 'error')
                mismatches.append({'pos_id': pos_id, 'issue': 'MISSING_ON_EXCHANGE',
                                   'action': 'operator_review_required'})
        else:
            # Position found — check size
            ex_size  = ex['size']
            our_size = pos['lots']
            if ex_size != our_size:
                issue = f"SIZE_MISMATCH: local={our_size} exchange={ex_size}"
                log.warning("[%s] reconcile: %s — %s (may be manual trade at same strike)",
                            sid, pos_id, issue)
                log_activity('reconciliation_mismatch', issue, sid, 'warning')
                mismatches.append({'pos_id': pos_id, 'issue': 'SIZE_MISMATCH',
                                   'action': 'logged_no_autocorrect'})

    ok = len([m for m in mismatches if m.get('issue') == 'MISSING_ON_EXCHANGE']) == 0
    log_activity('reconciliation_run',
        f"Reconciliation complete: {len(mismatches)} mismatch(es)", sid, 'info')

    return {'ok': ok, 'mismatches': mismatches}
