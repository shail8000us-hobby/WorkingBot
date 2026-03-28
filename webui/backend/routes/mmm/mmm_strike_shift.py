"""
MMM Strike Shift — Money Mind & Method

Handles strike shifting when hedge premium drops below shift_threshold.
Freezes current positions at the old strike and finds a new, closer strike
with sufficient premium.

Maps to MONEY_POWER_CALCULATION_LOGIC.md:
  §10: Strike Shifting

Created: February 15, 2026
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone

from .mmm_state import recompute_side_lots, _migrate_side_to_positions
from .mmm_constants import strike_key as _strike_key

log = logging.getLogger('mmm_strike_shift')


def check_shift_needed(
    session: Dict,
    side: str,
    current_premium: float,
) -> bool:
    """
    §10: Check if the hedge side's premium has dropped below shift_threshold.

    Uses dynamic threshold: max(shift_threshold, hedge_entry_premium * shift_threshold_pct)
    when shift_threshold_pct > 0. This prefers fewer lots at higher premium over
    many lots at dying premium.

    Args:
        session: Full session dict
        side: 'ce' or 'pe' — the hedge side
        current_premium: Current premium at the active strike

    Returns:
        True if strike shift is needed
    """
    params = session.get('params', {})
    threshold_floor = params.get('shift_threshold', 50.0)
    threshold_pct = params.get('shift_threshold_pct', 0.0)
    
    sid = session.get('session_id', 'unknown')

    # Dynamic threshold: use hedge entry premium * pct if configured
    effective_threshold = threshold_floor
    hedge_entry_premium = 0
    
    if threshold_pct > 0:
        side_state = session.get(side, {})
        # AUDIT FIX: Use persistent _initial_hedge_premium to prevent threshold
        # collapse after shifts (original_premium goes to 0 after first shift)
        hedge_entry_premium = side_state.get('_initial_hedge_premium', 0)
        if hedge_entry_premium == 0:
            hedge_entry_premium = side_state.get('original_premium', 0)
        # If original was shifted, use latest adjustment fill premium
        if hedge_entry_premium == 0:
            fills = side_state.get('adjustment_fills', [])
            if fills:
                hedge_entry_premium = fills[-1].get('premium', 0)
        dynamic = hedge_entry_premium * threshold_pct
        effective_threshold = max(threshold_floor, dynamic)
        
        # DETAILED LOGGING for debugging
        log.info(
            f"[{sid}] 🔍 SHIFT CHECK: {side.upper()} | "
            f"Current: ${current_premium:.2f}, "
            f"Entry: ${hedge_entry_premium:.2f}, "
            f"Floor: ${threshold_floor:.2f}, "
            f"Pct: {threshold_pct:.0%}, "
            f"Dynamic: ${dynamic:.2f}, "
            f"Effective: ${effective_threshold:.2f}"
        )

    if current_premium < effective_threshold:
        log.info(
            f"[{sid}] ✅ SHIFT NEEDED: {side.upper()} premium "
            f"${current_premium:.2f} < ${effective_threshold:.2f} "
            f"(floor=${threshold_floor:.2f}, pct={threshold_pct:.0%}, entry=${hedge_entry_premium:.2f})"
        )
        return True
    else:
        log.info(
            f"[{sid}] ❌ NO SHIFT: {side.upper()} premium "
            f"${current_premium:.2f} >= ${effective_threshold:.2f} "
            f"(still above threshold)"
        )

    return False


def freeze_current_positions(
    session: Dict,
    side: str,
) -> Dict[str, Any]:
    """
    §10: Freeze all active positions at the current strike.

    Move original lots + adjustment fills → frozen_positions.
    Clear adjustment_fills at the old strike.

    Args:
        session: Full session dict (mutated in place)
        side: 'ce' or 'pe'

    Returns:
        {frozen_lots, old_strike, frozen_entry}
    """
    side_state = session.get(side, {})
    old_strike = side_state.get('active_strike', 0)

    # Fix #23: Ensure positions[] exists (migrate if this is a legacy session)
    if 'positions' not in side_state:
        _migrate_side_to_positions(side_state)

    # Fix #23: Set all active positions to 'shifted' status (O(n) over positions[])
    now = datetime.now(timezone.utc).isoformat()
    frozen_lots = 0
    for pos in side_state.get('positions', []):
        if pos.get('status') == 'active':
            pos['status'] = 'shifted'
            pos['shifted_at'] = now
            frozen_lots += pos.get('lots', 0)

    # BUG FIX: Preserve _initial_hedge_premium BEFORE recompute zeroes original_premium.
    # recompute_side_lots() sets original_premium=0.0 when no active 'original' positions
    # remain. activate_new_strike() reads original_premium to seed _initial_hedge_premium,
    # but by that point it is already 0 → _initial_hedge_premium gets set to the new
    # strike's fill premium instead of the true original entry premium.
    # Preserving here ensures the dynamic shift threshold always references the first
    # ever entry premium, not the shifted one.
    if not side_state.get('_initial_hedge_premium'):
        orig_prem = side_state.get('original_premium', 0)
        if orig_prem > 0:
            side_state['_initial_hedge_premium'] = orig_prem

    # recompute_side_lots() rebuilds frozen_positions view + resets
    # original_lots/adjustment_fills to empty (no active positions remain)
    recompute_side_lots(side_state)

    # AUDIT FIX BUG2: Clear stale trigger_snapshot for old strike.
    # The frozen positions won't trigger adjustments; leaving the old key
    # confuses evaluate_trigger() if the bot ever shifts back to this strike.
    old_key = _strike_key(old_strike)
    side_state.get('trigger_snapshot', {}).pop(old_key, None)

    session[side] = side_state

    # AUDIT FIX BUG6: Compute frozen_entry (lot-weighted avg premium)
    frozen_entry = 0.0
    if frozen_lots > 0:
        total_prem = 0.0
        for pos in side_state.get('frozen_positions', []):
            if pos.get('strike') == old_strike:
                total_prem += pos.get('entry_premium', 0) * pos.get('lots', 0)
        frozen_entry = total_prem / frozen_lots

    log.info(
        f"Frozen {frozen_lots} lots at strike {old_strike} "
        f"for {side.upper()}"
    )

    return {
        'frozen_lots': frozen_lots,
        'old_strike': old_strike,
        'frozen_entry': frozen_entry,
    }


def find_new_strike(
    initializer,
    session: Dict,
    side: str,
    spot_price: float,
    min_otm_distance: float = 0.0,
) -> Optional[Dict[str, Any]]:
    """
    §10: Scan the chain for a new strike closer to spot with premium >= threshold.

    For CE (calls): Find OTM call with strike > spot, premium >= threshold
    For PE (puts): Find OTM put with strike < spot, premium >= threshold

    Args:
        initializer: MMMInitializer instance for chain access
        session: Full session dict
        side: 'ce' or 'pe'
        spot_price: Current BTC spot price
        min_otm_distance: Minimum absolute distance from spot (used by ATM Shield)

    Returns:
        {strike, premium, symbol} or None if no suitable strike found
    """
    params = session.get('params', {})
    threshold_floor = params.get('shift_threshold', 50.0)
    threshold_pct = params.get('shift_threshold_pct', 0.0)
    expiry = params.get('expiry', '')

    # Dynamic threshold for candidate filtering
    effective_threshold = threshold_floor
    if threshold_pct > 0:
        side_state = session.get(side, {})
        # AUDIT FIX: Use persistent _initial_hedge_premium (same as check_shift_needed)
        hedge_entry_premium = side_state.get('_initial_hedge_premium', 0)
        if hedge_entry_premium == 0:
            hedge_entry_premium = side_state.get('original_premium', 0)
        if hedge_entry_premium == 0:
            fills = side_state.get('adjustment_fills', [])
            if fills:
                hedge_entry_premium = fills[-1].get('premium', 0)
        effective_threshold = max(threshold_floor, hedge_entry_premium * threshold_pct)

    if not expiry:
        log.error("No expiry set in session params")
        return None

    try:
        chain_result = initializer.get_full_chain(expiry)
        if not chain_result or not chain_result.get('success'):
            log.error("Failed to fetch chain data for strike shift")
            return None

        chain_list = chain_result.get('chain', [])
        if not chain_list:
            log.error("Empty chain data for strike shift")
            return None

        option_type = 'call' if side == 'ce' else 'put'
        candidates = []
        old_strike = session.get(side, {}).get('active_strike', 0)

        for row in chain_list:
            strike = row.get('strike', 0)
            option_data = row.get(option_type, {})
            if not option_data:
                continue

            bid = float(option_data.get('bid', 0) or 0)
            ask = float(option_data.get('ask', 0) or 0)
            mark = float(option_data.get('mark_price', 0) or 0)
            symbol = option_data.get('symbol', '')

            # Use mark_price for candidate filtering (consistent with _rank_strikes).
            # mark_price is the exchange's theoretical fair value — more stable than
            # bid on 0DTE/illiquid options where bids can be stale or pulled.
            # Actual execution will still use bid-based pricing via smart_execute.
            if mark > 0:
                premium = mark
            elif bid > 0 and ask > 0:
                premium = (bid + ask) / 2
            elif bid > 0:
                premium = bid
            else:
                continue  # No usable price data

            if premium < effective_threshold:
                continue

            # Must be OTM
            if option_type == 'call' and strike <= spot_price:
                continue
            if option_type == 'put' and strike >= spot_price:
                continue

            # ATM Shield: enforce minimum OTM distance
            if min_otm_distance > 0:
                if option_type == 'call' and strike < spot_price + min_otm_distance:
                    continue
                if option_type == 'put' and strike > spot_price - min_otm_distance:
                    continue

            # Don't re-select the current active strike
            if abs(strike - old_strike) < 1:
                continue

            # AUDIT FIX BUG5: Don't shift back to a strike with frozen positions
            frozen = session.get(side, {}).get('frozen_positions', [])
            frozen_strikes = {f.get('strike', 0) for f in frozen if f.get('lots', 0) > 0}
            if any(abs(strike - fs) < 1 for fs in frozen_strikes):
                continue

            candidates.append({
                'strike': strike,
                'premium': premium,
                'symbol': symbol,
                'distance_from_spot': abs(strike - spot_price),
            })

        if not candidates:
            # Diagnostic: log first 5 OTM strikes to show why each was rejected.
            # If this recurs, the log will immediately show bid vs mark values.
            diag = []
            for row in chain_list[:20]:
                s = row.get('strike', 0)
                od = row.get(option_type, {})
                if not od:
                    continue
                b = float(od.get('bid', 0) or 0)
                m = float(od.get('mark_price', 0) or 0)
                is_otm = (option_type == 'call' and s > spot_price) or \
                         (option_type == 'put' and s < spot_price)
                if is_otm:
                    diag.append(f"{s}(bid={b:.1f},mark={m:.1f})")
                if len(diag) >= 5:
                    break
            log.warning(
                f"No suitable strike for {side.upper()} shift "
                f"(threshold=${effective_threshold:.0f}, spot={spot_price:.0f}, "
                f"old_strike={old_strike}). "
                f"Nearest OTM strikes: {', '.join(diag) if diag else 'NONE'}"
            )
            return None

        # §10 FIX: Sort by proximity to shift_target_premium (default 100)
        # This ensures we pick an OTM strike with manageable premium,
        # NOT the closest-to-spot (which can be near-ATM with 500+ premium)
        target_premium = params.get('shift_target_premium', 100.0)

        candidates.sort(key=lambda c: abs(c['premium'] - target_premium))

        best = candidates[0]
        log.info(
            f"Found new strike for {side.upper()}: "
            f"{best['strike']} @ {best['premium']:.2f} "
            f"(target premium: {target_premium:.2f})"
        )
        return best

    except Exception as e:
        log.exception(f"Error finding new strike: {e}")
        return None


def activate_new_strike(
    session: Dict,
    side: str,
    new_strike: float,
    fill_premium: float,
    lots: int,
    order_id: str = '',
    client_order_id: str = '',
) -> Dict:
    """
    Set the new active strike after a shift.

    Args:
        session: Full session dict (mutated in place)
        side: 'ce' or 'pe'
        new_strike: The new strike price
        fill_premium: Premium obtained from selling at new strike
        lots: Number of lots sold at new strike
        order_id: Exchange order ID from the shift sell (for reconciliation)
        client_order_id: Session-tagged client order ID (for per-session fill tracking)

    Returns:
        Updated session
    """
    side_state = session.get(side, {})

    side_state['active_strike'] = new_strike
    # Clear user pin — algo auto-shifted, re-enable auto-ATM selection
    side_state.pop('active_strike_pinned', None)

    # AUDIT FIX: Preserve initial hedge premium for dynamic threshold across shifts
    if '_initial_hedge_premium' not in side_state or side_state.get('_initial_hedge_premium', 0) == 0:
        # First shift — preserve the original premium before it's zeroed by recompute
        orig_prem = side_state.get('original_premium', 0)
        side_state['_initial_hedge_premium'] = orig_prem if orig_prem > 0 else fill_premium

    # FIX: Update symbol to match the new active strike.
    expiry = session.get('params', {}).get('expiry', '')
    option_type = 'call' if side == 'ce' else 'put'
    # H3 FIX: Use get_initializer() singleton instead of MMMInitializer() inline.
    # Inline construction can silently fail (API timeout, missing creds) and leave
    # side_state['symbol'] pointing at the old strike — next order then uses a wrong
    # symbol and burns through the full reprice loop (4 × 60s) before surfacing.
    # Failure is promoted to log.error so it is visible in alerting/monitoring.
    from .mmm_initializer import get_initializer
    try:
        _init = get_initializer()
        side_state['symbol'] = _init.build_symbol(option_type, 'BTC', new_strike, expiry)
        log.info(f"Symbol updated for {side.upper()}: {side_state['symbol']}")
    except Exception as e:
        log.error(
            f"Failed to update symbol for {side.upper()} shift to {new_strike}: {e}. "
            f"Existing symbol retained — next order will likely be rejected; "
            f"reconciliation required."
        )

    # Fix #23: Append new position to Unified Position Ledger
    # Shifted positions use type='strike_shift' so calculate_reversal_loss()
    # includes them in risk assessment (non-'original' type).
    now = datetime.now(timezone.utc).isoformat()
    counter = side_state.get('_pos_counter', 0) + 1
    side_state['_pos_counter'] = counter
    side_state.setdefault('positions', []).append({
        'id': f"{side}_shift_{counter:03d}",
        'strike': new_strike,
        'lots': lots,
        'entry_premium': fill_premium,
        'premium': fill_premium,        # backward-compat alias
        'type': 'strike_shift',
        'status': 'active',
        'created_at': now,
        'fill_confirmed_at': now,       # reconciliation: settlement-lag guard
        'order_id': order_id,           # reconciliation: verify fill via exchange
        'client_order_id': client_order_id,  # reconciliation: per-session fill attribution
        'shifted_at': None,
        'closed_at': None,
        'realized_pnl': None,
        'timestamp': now,               # backward-compat alias
    })

    # Set trigger snapshot at the new strike
    side_state.setdefault('trigger_snapshot', {})[_strike_key(new_strike)] = fill_premium

    # recompute_side_lots() rebuilds: original_lots=0 (no 'original' type active),
    # adjustment_fills=[new strike_shift entry], active_lots=lots
    recompute_side_lots(side_state)
    session[side] = side_state

    # NOTE: shift_count is incremented by _process_strike_shift() in mmm_monitor.py
    session['updated_at'] = datetime.now(timezone.utc).isoformat()

    log.info(
        f"Strike shift complete: {side.upper()} now active at "
        f"{new_strike} with {lots} lots @ {fill_premium:.2f}"
    )

    # ── SESSION EVENT: strike shift ────────────────────────────────────────
    try:
        from .mmm_audit_log import get_event_log as _get_evl
        from .mmm_audit_remark import build_event_remark as _ber
        # Old strike is in frozen_positions (set to 'shifted' by freeze_current_positions)
        _old_strike = 0
        for _fp in side_state.get('frozen_positions', []):
            if _fp.get('lots', 0) > 0:
                _old_strike = int(_fp.get('strike', 0))
                break
        _get_evl().enqueue_event(
            session_id=session.get('session_id', ''),
            event_category='STRIKE_SHIFT',
            event_type='shifted',
            severity='INFO',
            remark=_ber('STRIKE_SHIFT', 'shifted',
                        side=side, old_strike=_old_strike,
                        new_strike=int(new_strike), old_premium=fill_premium),
            details={
                'side': side,
                'old_strike': _old_strike,
                'new_strike': new_strike,
                'lots': lots,
                'fill_premium': fill_premium,
            },
        )
    except Exception:
        pass

    return session
