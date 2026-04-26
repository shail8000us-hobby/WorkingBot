"""
MMM P&L Core — Single Source of Truth for MMM Session P&L

All realized P&L mutations go through this module. No other file should write
directly to session['realized_pnl'], session['total_fees'], or attribution
buckets (pnl_initial, pnl_adjustment, pnl_harvest, pnl_recycle,
manual_reduction_pnl). Instead, callers use:

    record_close()   — when a BUY-back order fills (estimated or confirmed)
    confirm_fill()   — when fill_sync gets actual exchange fill data
    rollback_close() — when recycler Phase B fails
    manual_close()   — when human confirms a reconciliation discrepancy
    record_fee()     — when a SELL order or perp hedge incurs exchange fees

After every ledger mutation, _sync_session_fields() recomputes the session
fields from the ledger so all existing readers still work.

Architecture:
  close_at_5 ─────┐
  harvester  ─────┤  record_close()  ──►  session['_fill_ledger']
  recycler   ─────┤                              │
  manual_reduce ──┤                              │  _sync_session_fields()
  wind_down  ─────┤                              ▼
  auto_close ─────┘                     session['realized_pnl']   (cache)
                                        session['total_fees']     (cache)
  fill_sync  ────►  confirm_fill()      session['pnl_initial']   (cache)
                                        session['pnl_adjustment'] (cache)
  sell fees  ─────►  record_fee()       session['pnl_harvest']    (cache)
  perp fees  ─────┘                     session['pnl_recycle']    (cache)

  reconcile  ────►  flag_discrepancy()  ──►  alert only, NO ledger write

  recycler   ────►  rollback_closes_since()  ──►  undo Phase A entries

  get_pnl()  ────►  derive from ledger  ──►  {realized, unrealized, fees, net_pnl}

Created: 2026-03-25
Audit:  2026-03-25 — CRIT-1 (fee wipe), CRIT-2 (storage overwrite),
        ARCH-1 (recycler encap), DV-1 (MMMEngine.__new__ hack) fixed
"""

import logging
import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Callable
from datetime import datetime, timezone

from .mmm_constants import LOT_SIZE_BTC
from webui.backend.sealed import sealed

_D = Decimal
_LOT = _D(str(LOT_SIZE_BTC))

log = logging.getLogger('mmm_pnl_core')

# ─────────────────────────────────────────────────────────────────────────────
# Source → attribution bucket mapping
# ─────────────────────────────────────────────────────────────────────────────

_SOURCE_TO_ATTR = {
    'initial':           'pnl_initial',
    'close_at_5':        'pnl_initial',
    'adjustment':        'pnl_adjustment',
    'harvest':           'pnl_harvest',
    'recycle':           'pnl_recycle',
    'manual':            'manual_reduction_pnl',
    'manual_reduce':     'manual_reduction_pnl',
    'close_by_strike':   'manual_reduction_pnl',
    'wind_down':         'pnl_adjustment',
    'auto_close_active': 'pnl_adjustment',
    'auto_close_frozen': 'pnl_adjustment',
    'reverse_close':     'pnl_reverse',
}


# ─────────────────────────────────────────────────────────────────────────────
# Ledger access + migration
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_ledger(session: Dict) -> List[Dict]:
    """Ensure the fill ledger exists. Migrate existing P&L on first access."""
    if '_fill_ledger' not in session:
        session['_fill_ledger'] = []
        # If session already has P&L from before migration, seed the ledger.
        # Check attribution buckets too: zero-net sessions (realized_pnl==0) can
        # still have non-zero per-bucket values whose history must be preserved.
        _LEGACY_ATTR_KEYS = (
            'pnl_initial', 'pnl_adjustment', 'pnl_harvest',
            'pnl_recycle', 'manual_reduction_pnl', 'pnl_reverse',
        )
        if (session.get('realized_pnl', 0) != 0
                or session.get('total_fees', 0) != 0
                or any(session.get(k, 0) != 0 for k in _LEGACY_ATTR_KEYS)):
            _migrate_existing_pnl(session)
    return session['_fill_ledger']


def _migrate_existing_pnl(session: Dict) -> None:
    """One-time: create ledger entries from existing session P&L fields."""
    ledger = session['_fill_ledger']
    now = session.get('updated_at', datetime.now(timezone.utc).isoformat())

    attributed_total = 0.0
    for source, attr_key in [
        ('initial',       'pnl_initial'),
        ('adjustment',    'pnl_adjustment'),
        ('harvest',       'pnl_harvest'),
        ('recycle',       'pnl_recycle'),
        ('manual',        'manual_reduction_pnl'),
        ('reverse_close', 'pnl_reverse'),
    ]:
        val = session.get(attr_key, 0)
        if val != 0:
            attributed_total += val
            ledger.append({
                'id': f'mig_{source}',
                'fill_id': f'mig_{source}',
                'order_id': f'mig_{source}',
                'symbol': 'MIGRATION',
                'option_side': '',
                'strike': 0,
                'lots': 0,
                'entry_premium': 0,
                'close_premium': 0,
                'commission': 0,
                'pnl': round(val, 8),
                'source': source,
                'confirmed': True,
                'timestamp': now,
                'position_id': '',
                '_is_migration': True,
            })

    # Capture any gap between realized_pnl and attributed total
    # (e.g. from reconciliation auto-correct or other unattributed writes)
    realized = session.get('realized_pnl', 0)
    gap = realized - attributed_total
    if abs(gap) > 1e-8:
        ledger.append({
            'id': 'mig_unattributed',
            'fill_id': 'mig_unattributed',
            'order_id': 'mig_unattributed',
            'symbol': 'MIGRATION',
            'option_side': '',
            'strike': 0,
            'lots': 0,
            'entry_premium': 0,
            'close_premium': 0,
            'commission': 0,
            'pnl': round(gap, 8),
            'source': 'adjustment',
            'confirmed': True,
            'timestamp': now,
            'position_id': '',
            '_is_migration': True,
        })

    fees = session.get('total_fees', 0)
    if fees != 0:
        ledger.append({
            'id': 'mig_fees',
            'fill_id': 'mig_fees',
            'order_id': 'mig_fees',
            'symbol': 'MIGRATION',
            'option_side': '',
            'strike': 0,
            'lots': 0,
            'entry_premium': 0,
            'close_premium': 0,
            'commission': round(fees, 8),
            'pnl': 0,
            'source': 'migration',
            'confirmed': True,
            'timestamp': now,
            'position_id': '',
            '_is_migration': True,
        })

    session['_pnl_migrated'] = True
    log.info(
        f"[{session.get('session_id', '?')}] PnlCore: migrated existing P&L "
        f"(realized={realized:.6f}, "
        f"fees={fees:.6f}, entries={len(ledger)})"
    )


# ─────────────────────────────────────────────────────────────────────────────
# WRITE PATHS
# ─────────────────────────────────────────────────────────────────────────────

@sealed
def record_close(
    session: Dict,
    order_id: str,
    symbol: str,
    option_side: str,
    strike: float,
    lots: int,
    entry_premium: float,
    close_premium: float,
    commission: float,
    source: str,
    position_id: str = '',
    confirmed: bool = False,
    fill_id: str = None,
) -> str:
    """
    Record a close event in the fill ledger.

    Called by close_at_5, harvester, recycler, manual_reduce, wind_down,
    auto_close paths when a BUY-back order is placed or fills immediately.

    Args:
        session:       MMM session dict
        order_id:      Exchange order ID
        symbol:        e.g. 'C-BTC-71000-250326'
        option_side:   'ce' or 'pe'
        strike:        Strike price
        lots:          Number of lots closed
        entry_premium: What we sold at (from position)
        close_premium: What we bought back at (fill price or estimate)
        commission:    Exchange fee (absolute value)
        source:        'initial' | 'adjustment' | 'harvest' | 'recycle' |
                       'manual_reduce' | 'close_by_strike' | 'wind_down' |
                       'auto_close_active' | 'auto_close_frozen'
        position_id:   Reference to position (optional)
        confirmed:     True if from actual exchange fill
        fill_id:       Exchange fill ID (required if confirmed)

    Returns:
        Ledger entry ID
    """
    ledger = _ensure_ledger(session)

    # Dedup: confirmed fill already recorded
    if fill_id:
        for e in ledger:
            if e.get('fill_id') == fill_id:
                return e['id']

    # Dedup: estimate for this order already exists
    if not confirmed:
        for e in ledger:
            if e.get('order_id') == str(order_id) and not e.get('confirmed'):
                return e['id']

    entry_id = str(uuid.uuid4())[:12]
    pnl = (float(entry_premium) - float(close_premium)) * int(lots) * LOT_SIZE_BTC

    entry = {
        'id': entry_id,
        'fill_id': fill_id,
        'order_id': str(order_id),
        'symbol': symbol,
        'option_side': option_side,
        'strike': float(strike),
        'lots': int(lots),
        'entry_premium': float(entry_premium),
        'close_premium': float(close_premium),
        'commission': abs(float(commission)),
        'pnl': round(pnl, 8),
        'source': source,
        'confirmed': confirmed,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'position_id': position_id,
    }
    if confirmed:
        entry['confirmed_at'] = entry['timestamp']
    else:
        # H-4: track when estimate was created for stale-estimate detection
        entry['estimated_at'] = entry['timestamp']

    ledger.append(entry)
    _sync_session_fields(session)
    return entry_id


@sealed
def confirm_fill(
    session: Dict,
    order_id: str,
    fill_id: str,
    actual_fill_price: float,
    actual_commission: float,
    actual_lots: int = None,
) -> Optional[Dict]:
    """
    Confirm an estimated ledger entry with actual exchange fill data.

    Called by fill_sync when the real fill arrives from the exchange.
    Finds the estimate by order_id, updates with actual values, and
    recomputes P&L from the ledger.

    Returns:
        Updated entry dict, or None if no matching estimate found
        (caller should use record_close with confirmed=True instead).
    """
    ledger = _ensure_ledger(session)

    # Already recorded?
    for e in ledger:
        if e.get('fill_id') == fill_id:
            return e

    # Find estimate by order_id
    for e in ledger:
        if e.get('order_id') == str(order_id) and not e.get('confirmed'):
            old_pnl = e['pnl']
            old_comm = e.get('commission', 0)

            e['fill_id'] = fill_id
            e['close_premium'] = float(actual_fill_price)
            e['commission'] = abs(float(actual_commission))
            if actual_lots is not None:
                e['lots'] = int(actual_lots)
            e['pnl'] = round(
                (e['entry_premium'] - float(actual_fill_price))
                * e['lots'] * LOT_SIZE_BTC, 8
            )
            e['confirmed'] = True
            e['confirmed_at'] = datetime.now(timezone.utc).isoformat()

            _sync_session_fields(session)

            pnl_diff = e['pnl'] - old_pnl
            comm_diff = e['commission'] - old_comm
            if abs(pnl_diff) > 1e-9 or abs(comm_diff) > 1e-9:
                log.info(
                    f"[{session.get('session_id', '?')}] PnlCore: confirmed "
                    f"order={order_id} fill={fill_id}, "
                    f"pnl_corr={pnl_diff:+.8f} comm_corr={comm_diff:+.8f}"
                )
            return e

    return None


@sealed
def rollback_close(session: Dict, order_id: str) -> Optional[Dict]:
    """
    Remove an UNCONFIRMED ledger entry by order_id.

    Used by recycler when Phase B fails and Phase A must be undone.
    Only removes unconfirmed entries — confirmed fills are permanent.

    Returns:
        Removed entry, or None if not found.
    """
    ledger = _ensure_ledger(session)

    for i, e in enumerate(ledger):
        if e.get('order_id') == str(order_id) and not e.get('confirmed'):
            removed = ledger.pop(i)
            _sync_session_fields(session)
            log.info(
                f"[{session.get('session_id', '?')}] PnlCore: rolled back "
                f"order={order_id}, pnl={removed['pnl']:+.8f}"
            )
            return removed
    return None


@sealed
def flag_discrepancy(
    session: Dict,
    symbol: str,
    option_side: str,
    strike: float,
    session_lots: int,
    exchange_lots: int,
    reason: str = 'exchange_mismatch',
) -> Dict:
    """
    Called by reconciliation when exchange vs session don't match.
    Does NOT modify P&L or the ledger. Returns a discrepancy report.
    Emits safety alert for human review.
    """
    report = {
        'symbol': symbol,
        'option_side': option_side,
        'strike': float(strike),
        'session_lots': session_lots,
        'exchange_lots': exchange_lots,
        'delta_lots': session_lots - exchange_lots,
        'reason': reason,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'action_required': 'HUMAN_REVIEW',
    }
    discrepancies = session.setdefault('_pnl_discrepancies', [])
    discrepancies.append(report)
    if len(discrepancies) > 50:
        session['_pnl_discrepancies'] = discrepancies[-50:]
    return report


@sealed
def manual_close(
    session: Dict,
    symbol: str,
    option_side: str,
    strike: float,
    lots: int,
    entry_premium: float,
    close_price: float,
    commission: float = 0.0,
) -> str:
    """
    Human-confirmed close at a specific price.
    Used when reconciliation flags a discrepancy and operator decides the price.
    """
    return record_close(
        session=session,
        order_id=f'manual_{uuid.uuid4().hex[:8]}',
        symbol=symbol,
        option_side=option_side,
        strike=strike,
        lots=lots,
        entry_premium=entry_premium,
        close_premium=close_price,
        commission=commission,
        source='manual',
        confirmed=True,
        fill_id=f'manual_{uuid.uuid4().hex[:8]}',
    )


@sealed
def record_fee(
    session: Dict,
    commission: float,
    source: str,
    order_id: str = '',
    symbol: str = '',
    side: str = '',
) -> str:
    """
    Record a fee/commission event that is NOT a close (e.g. sell-side fees,
    perp hedge fees).

    CRIT-1 fix: Without this, sell-side fees written directly to
    session['total_fees'] get wiped by _sync_session_fields() on the next
    close event because compute_fees() only sees ledger commissions.

    Args:
        session:    MMM session dict
        commission: Exchange fee (absolute value)
        source:     'sell_initial' | 'sell_adjustment' | 'sell_scale_up' |
                    'sell_replenish' | 'sell_inject' | 'sell_retry' |
                    'perp_hedge' | 'perp_close' | etc.
        order_id:   Exchange order ID (for audit trail)
        symbol:     Instrument symbol
        side:       'ce' | 'pe' | 'perp' | ''
    """
    if not commission or abs(float(commission)) < 1e-12:
        return ''

    ledger = _ensure_ledger(session)

    # H-2: Dedup by order_id — prevents double-booking fees on retry/crash
    if order_id:
        for e in ledger:
            if e.get('_is_fee_only') and e.get('order_id') == str(order_id):
                return e['id']

    entry_id = str(uuid.uuid4())[:12]
    ledger.append({
        'id': entry_id,
        'fill_id': None,
        'order_id': str(order_id) if order_id else '',
        'symbol': symbol,
        'option_side': side,
        'strike': 0,
        'lots': 0,
        'entry_premium': 0,
        'close_premium': 0,
        'commission': abs(float(commission)),
        'pnl': 0,
        'source': source,
        'confirmed': True,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'position_id': '',
        '_is_fee_only': True,
    })
    _sync_session_fields(session)
    return entry_id


@sealed
def rollback_closes_since(session: Dict, snapshot_len: int) -> int:
    """
    Remove all UNCONFIRMED ledger entries added after snapshot_len.

    Used by recycler when Phase B fails — removes all Phase A entries
    that were appended after the snapshot was taken.

    Args:
        session:      MMM session dict
        snapshot_len: len(ledger) at the time of the snapshot

    Returns:
        Number of entries removed
    """
    ledger = _ensure_ledger(session)
    removed = 0
    # H-8: count confirmed entries above snapshot_len — rollback can't undo these
    skipped_confirmed = 0
    # Walk backward from end to snapshot_len, removing unconfirmed entries
    i = len(ledger) - 1
    while i >= snapshot_len:
        if not ledger[i].get('confirmed'):
            ledger.pop(i)
            removed += 1
        else:
            skipped_confirmed += 1
        i -= 1

    if removed > 0:
        _sync_session_fields(session)
        log.info(
            f"[{session.get('session_id', '?')}] PnlCore: rolled back "
            f"{removed} entries since snapshot={snapshot_len}"
        )

    # H-8: Phase A fills confirmed during Phase B failure — flag for human review
    if skipped_confirmed > 0:
        flag_discrepancy(
            session=session,
            symbol='RECYCLE_ROLLBACK',
            option_side='',
            strike=0,
            session_lots=skipped_confirmed,
            exchange_lots=0,
            reason='phase_b_failure_confirmed_pnl',
        )
        log.error(
            f"[{session.get('session_id', '?')}] PnlCore: ROLLBACK INCOMPLETE — "
            f"{skipped_confirmed} confirmed Phase A entries cannot be rolled back. "
            f"P&L may be overstated. Human review required."
        )

    return removed


@sealed
def ledger_snapshot(session: Dict) -> int:
    """Return current ledger length as a snapshot point for rollback."""
    return len(_ensure_ledger(session))


# ─────────────────────────────────────────────────────────────────────────────
# READ PATHS — pure, always derived from ledger
# ─────────────────────────────────────────────────────────────────────────────

@sealed
def compute_realized_pnl(session: Dict) -> float:
    """Sum of all ledger entries' P&L (both estimated and confirmed)."""
    ledger = _ensure_ledger(session)
    return sum(e['pnl'] for e in ledger)


@sealed
def compute_confirmed_pnl(session: Dict) -> float:
    """Sum of only exchange-confirmed entries."""
    ledger = _ensure_ledger(session)
    return sum(e['pnl'] for e in ledger if e.get('confirmed'))


@sealed
def compute_fees(session: Dict) -> float:
    """Sum of all commissions from the ledger."""
    ledger = _ensure_ledger(session)
    return sum(abs(e.get('commission', 0)) for e in ledger)


@sealed
def compute_unrealized_pnl(session: Dict, fetch_premium_fn: Callable) -> float:
    """
    Compute unrealized P&L across all open positions.

    For sold options: P&L = (entry_premium - current_premium) x lots x LOT_SIZE
    (Positive = option decayed = profit for seller)

    Extracted from MMMEngine to avoid MMMEngine.__new__() instantiation hack.
    Uses Decimal internally to prevent float rounding accumulation.
    """
    total_unrealized = _D(0)
    _fetch_errors = 0
    _total_positions = 0

    for side_key in ['ce', 'pe']:
        side_state = session.get(side_key, {})
        option_type = 'call' if side_key == 'ce' else 'put'

        # Track lots being closed to prevent transient double-count.
        # Sum being_closed lots per strike across all position records.
        being_closed_lots_at = {}
        for pos in side_state.get('positions', []):
            if pos.get('_being_closed') and pos.get('lots', 0) > 0:
                s = float(pos.get('strike', 0))
                being_closed_lots_at[s] = (
                    being_closed_lots_at.get(s, 0) + int(pos.get('lots', 0))
                )

        # Depleting counter: each fill consumes only as many being_closed lots
        # as it actually holds, so the deduction never spills over to other fills
        # at the same strike (fix: was subtracting full total from every fill).
        _remaining_bc = dict(being_closed_lots_at)

        # Original lots
        orig_lots = side_state.get('original_lots', 0)
        orig_prem = side_state.get('original_premium', 0)
        active_strike = side_state.get('active_strike', 0)

        _orig_key = float(active_strike)
        _orig_deduct = min(orig_lots, _remaining_bc.get(_orig_key, 0))
        _remaining_bc[_orig_key] = _remaining_bc.get(_orig_key, 0) - _orig_deduct
        orig_lots_effective = orig_lots - _orig_deduct

        if orig_lots_effective > 0 and active_strike > 0:
            _total_positions += 1
            try:
                current = fetch_premium_fn(active_strike, option_type)
                if current is None:
                    raise ValueError(
                        f"Premium is None for {side_key}@{active_strike}"
                    )
                total_unrealized += (
                    (_D(str(orig_prem)) - _D(str(current)))
                    * _D(orig_lots_effective) * _LOT
                )
            except Exception as e:
                _fetch_errors += 1
                log.warning(
                    f"Failed to fetch {side_key} premium at {active_strike}: {e}"
                )

        # Adjustment fills
        for fill in side_state.get('adjustment_fills', []):
            lots = fill.get('lots', 0)
            prem = fill.get('premium', 0)
            strike = fill.get('strike', active_strike)
            _strike_f = float(strike)
            _deduct = min(lots, _remaining_bc.get(_strike_f, 0))
            _remaining_bc[_strike_f] = _remaining_bc.get(_strike_f, 0) - _deduct
            lots_effective = lots - _deduct
            if lots_effective > 0:
                _total_positions += 1
                try:
                    current = fetch_premium_fn(strike, option_type)
                    if current is None:
                        raise ValueError(
                            f"Premium is None for {side_key}@{strike}"
                        )
                    total_unrealized += (
                        (_D(str(prem)) - _D(str(current)))
                        * _D(lots_effective) * _LOT
                    )
                except Exception as e:
                    _fetch_errors += 1
                    log.warning(
                        f"Failed to fetch {side_key} adj premium at {strike}: {e}"
                    )

        # Frozen positions
        for frozen in side_state.get('frozen_positions', []):
            lots = frozen.get('lots', 0)
            prem = frozen.get('entry_premium', 0)
            strike = frozen.get('strike', 0)
            if lots > 0 and strike > 0:
                _total_positions += 1
                try:
                    current = fetch_premium_fn(strike, option_type)
                    if current is None:
                        raise ValueError(
                            f"Premium is None for {side_key}@{strike}"
                        )
                    total_unrealized += (
                        (_D(str(prem)) - _D(str(current)))
                        * _D(lots) * _LOT
                    )
                except Exception as e:
                    _fetch_errors += 1
                    log.warning(
                        f"Failed to fetch {side_key} frozen premium "
                        f"at {strike}: {e}"
                    )

    # Track incomplete calculations in session state
    session['_pnl_fetch_errors'] = _fetch_errors
    if _total_positions > 0 and _fetch_errors > (_total_positions * 0.5):
        session['_pnl_calculation_incomplete'] = True
        log.error(
            f"P&L CALCULATION INCOMPLETE: {_fetch_errors}/{_total_positions} "
            f"position premium fetches failed (>50%). P&L is unreliable."
        )
    else:
        session.pop('_pnl_calculation_incomplete', None)

    return float(total_unrealized)


@sealed
def compute_attribution(session: Dict) -> Dict[str, float]:
    """Derive P&L attribution from the ledger source field."""
    ledger = _ensure_ledger(session)
    attr = {
        'pnl_initial': 0.0,
        'pnl_adjustment': 0.0,
        'pnl_harvest': 0.0,
        'pnl_recycle': 0.0,
        'manual_reduction_pnl': 0.0,
        'pnl_reverse': 0.0,
    }
    for e in ledger:
        key = _SOURCE_TO_ATTR.get(e.get('source', ''), 'pnl_adjustment')
        # Guard: unknown mapped keys (future sources) must not KeyError
        if key not in attr:
            attr[key] = 0.0
        attr[key] += e['pnl']
    return {k: round(v, 8) for k, v in attr.items()}


def _oldest_estimate_age_sec(ledger: list) -> Optional[float]:
    """Return age in seconds of oldest unconfirmed (non-fee) estimate, or None."""
    now = datetime.now(timezone.utc)
    oldest: Optional[float] = None
    for e in ledger:
        if e.get('confirmed') or e.get('_is_fee_only'):
            continue
        ts = e.get('estimated_at') or e.get('timestamp', '')
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            age = (now - dt).total_seconds()
            if oldest is None or age > oldest:
                oldest = age
        except Exception:
            pass
    return oldest


@sealed
def compute_net_premium(session: Dict) -> Dict:
    """Compute net premium (gross sells minus buyback costs from fill ledger).

    total_premium_collected only accumulates on sells and is never decremented.
    This function subtracts what was paid in buybacks so the displayed value
    decreases when positions are closed (close_at_5, ATM shield, wind-down, etc.).

    Skips migration entries (which have close_premium=0 and carry no buyback data).

    Returns:
        {'total': net_total, 'ce': net_ce, 'pe': net_pe}
    """
    ledger = session.get('_fill_ledger', [])
    buyback_total = buyback_ce = buyback_pe = 0.0
    for entry in ledger:
        if entry.get('_is_migration'):
            continue
        close_prem = float(entry.get('close_premium', 0) or 0)
        lots = int(entry.get('lots', 0) or 0)
        cost = close_prem * lots * float(_LOT)
        buyback_total += cost
        side = str(entry.get('option_side', '') or '').lower()
        if side == 'ce':
            buyback_ce += cost
        elif side == 'pe':
            buyback_pe += cost

    gross_total = float(session.get('total_premium_collected', 0) or 0)
    gross_ce = float(session.get('ce_premium_collected', 0) or 0)
    gross_pe = float(session.get('pe_premium_collected', 0) or 0)

    return {
        'total': round(gross_total - buyback_total, 6),
        'ce': round(gross_ce - buyback_ce, 6),
        'pe': round(gross_pe - buyback_pe, 6),
    }


@sealed
def get_pnl(session: Dict, fetch_premium_fn: Callable = None) -> Dict:
    """
    The single P&L endpoint. Everything derived from the ledger.

    Args:
        session:          MMM session dict
        fetch_premium_fn: function(strike, option_type) -> float
                          for computing unrealized P&L on open positions.

    Returns:
        {realized, unrealized, fees, net_pnl, attribution, ...}
        H-6 additions: unconfirmed_pnl, oldest_estimate_age_sec
    """
    realized = compute_realized_pnl(session)
    confirmed = compute_confirmed_pnl(session)
    fees = compute_fees(session)

    unrealized = 0.0
    if fetch_premium_fn:
        unrealized = compute_unrealized_pnl(session, fetch_premium_fn)

    # Include perp hedge and reverse P&L so net_pnl matches compute_current_total_pnl.
    # Previously get_pnl() omitted these, causing the API/dashboard to show a different
    # number than safety checks — perp losses were invisible to the operator.
    perp = session.get('perp_hedge', {})
    perp_pnl = (
        float(perp.get('realized_pnl', 0.0) or 0.0)
        + float(perp.get('unrealized_pnl', 0.0) or 0.0)
    )
    reverse_pnl = float(session.get('_reverse', {}).get('net_pnl', 0.0) or 0.0)

    net = realized + unrealized - fees + perp_pnl + reverse_pnl

    # Track peak P&L
    peak = session.get('peak_pnl', 0.0)
    if net > peak:
        session['peak_pnl'] = round(net, 6)

    ledger = _ensure_ledger(session)
    net_prem = compute_net_premium(session)
    return {
        'realized': round(realized, 6),
        'unrealized': round(unrealized, 6),
        'fees': round(fees, 6),
        'net_pnl': round(net, 6),
        'perp_pnl': round(perp_pnl, 6),
        'reverse_pnl': round(reverse_pnl, 6),
        'attribution': compute_attribution(session),
        'confirmed_pnl': round(confirmed, 6),
        # H-6: expose unconfirmed estimate exposure and staleness
        'unconfirmed_pnl': round(realized - confirmed, 6),
        'oldest_estimate_age_sec': _oldest_estimate_age_sec(ledger),
        'fill_count': len(ledger),
        'confirmed_count': sum(1 for e in ledger if e.get('confirmed')),
        # Net premium: gross sells minus buyback costs (decreases when positions closed)
        'net_premium_collected': net_prem['total'],
        'ce_net_premium': net_prem['ce'],
        'pe_net_premium': net_prem['pe'],
    }


# ─────────────────────────────────────────────────────────────────────────────
# H-1: Single canonical total P&L formula — all safety checks must use this
# ─────────────────────────────────────────────────────────────────────────────

@sealed
def compute_current_total_pnl(session: Dict) -> float:
    """
    Single canonical formula for current total P&L across all components.

    Formula: realized_pnl + unrealized_pnl - total_fees + perp_pnl + reverse_pnl

    All inputs are session cache fields kept in sync by _sync_session_fields()
    and compute_unrealized_pnl(). Perp hedge P&L (realized + unrealized) is
    included so max_loss and trailing_stop see the full picture. Reverse P&L
    is included so all safety checks account for reverse position exposure.

    ALL safety checks (check_max_loss, check_trailing_stop, etc.) must call
    this instead of building their own formula.
    """
    realized = session.get('realized_pnl', 0.0)
    unrealized = session.get('unrealized_pnl', 0.0)
    fees = session.get('total_fees', 0.0)
    perp = session.get('perp_hedge', {})
    perp_pnl = (
        float(perp.get('realized_pnl', 0.0) or 0.0)
        + float(perp.get('unrealized_pnl', 0.0) or 0.0)
    )
    reverse_pnl = float(session.get('_reverse', {}).get('net_pnl', 0.0) or 0.0)
    return float(realized) + float(unrealized) - float(fees) + perp_pnl + reverse_pnl


# ─────────────────────────────────────────────────────────────────────────────
# H-4: Stale estimate detection
# ─────────────────────────────────────────────────────────────────────────────

@sealed
def check_stale_estimates(
    session: Dict,
    max_age_minutes: float = 10.0,
) -> list:
    """
    Return unconfirmed ledger entries older than max_age_minutes.

    Called by MMMMonitor after fill_sync (Step 0.1) each heartbeat.
    Does NOT modify the ledger — read-only scan.

    A stale estimate means fill_sync hasn't confirmed this close in
    max_age_minutes, suggesting the order may not have filled, the fill
    arrived under a different order_id, or the exchange fill API is failing.

    Returns:
        List of stale ledger entry dicts, each with an extra '_age_sec' key.
        Empty list if no stale estimates.
    """
    ledger = _ensure_ledger(session)
    now = datetime.now(timezone.utc)
    cutoff_sec = max_age_minutes * 60.0
    stale = []

    for e in ledger:
        if e.get('confirmed') or e.get('_is_fee_only'):
            continue
        ts = e.get('estimated_at') or e.get('timestamp', '')
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            age_sec = (now - dt).total_seconds()
            if age_sec > cutoff_sec:
                stale.append({**e, '_age_sec': round(age_sec, 1)})
        except Exception:
            pass

    if stale:
        log.warning(
            f"[{session.get('session_id', '?')}] PnlCore: {len(stale)} stale "
            f"estimate(s) >{max_age_minutes:.0f}min: "
            + ', '.join(
                f"order={e.get('order_id')} age={e.get('_age_sec')}s"
                for e in stale[:5]
            )
        )
    return stale


# ─────────────────────────────────────────────────────────────────────────────
# Internal: sync session fields from ledger (backward compatibility)
# ─────────────────────────────────────────────────────────────────────────────

def _sync_session_fields(session: Dict) -> None:
    """
    Recompute session P&L fields from the ledger.
    Called after every ledger mutation so all existing code that reads
    session['realized_pnl'] etc. still gets correct values.
    """
    session['realized_pnl'] = round(compute_realized_pnl(session), 8)
    session['total_fees'] = round(compute_fees(session), 8)

    attr = compute_attribution(session)
    for key, value in attr.items():
        # Only set non-zero values or update existing keys
        if value != 0 or key in session:
            session[key] = value
