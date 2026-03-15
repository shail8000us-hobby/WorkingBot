"""
MMM Close-at-5 — Money Mind & Method

Scans ALL open positions (original + adjustment + frozen) every heartbeat.
If any position's premium drops to <= close_at_threshold (default 5),
buy it back to lock in realized profit.

Maps to MONEY_POWER_CALCULATION_LOGIC.md:
  §11: Close-at-5 Rule

Created: February 15, 2026
"""

import logging
import time
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from .mmm_state import recompute_side_lots
from .mmm_constants import LOT_SIZE_BTC
from webui.backend.sealed import sealed

# Fix #19: Decimal precision helper — mirrors mmm_engine._D
def _D(x) -> Decimal:
    return Decimal(str(x))

_LOT = _D(LOT_SIZE_BTC)

# Auto-clear _being_closed flag if stuck longer than this — prevents permanent lock-out (March 11 incident)
_BEING_CLOSED_TTL = 180  # seconds

log = logging.getLogger('mmm_close_at_5')


def _check_stale_being_closed(pos: dict, label: str) -> bool:
    """Return True if position is legitimately in-flight (caller should skip).
    Auto-clears the flag if it has been set for longer than _BEING_CLOSED_TTL seconds.
    """
    if not pos.get('_being_closed'):
        return False
    set_at = pos.get('_being_closed_at', 0)
    if set_at and time.monotonic() - set_at > _BEING_CLOSED_TTL:
        log.warning(
            f"Auto-cleared stale _being_closed on {label} "
            f"(stuck >{_BEING_CLOSED_TTL}s — previous close attempt likely crashed)"
        )
        pos.pop('_being_closed', None)
        pos.pop('_being_closed_at', None)
        return False
    return True


def scan_closeable_positions(
    session: Dict,
    fetch_premium_fn,
    threshold_override: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    §11: Scan ALL positions across both sides for premiums <= threshold.

    Args:
        session: Full session dict
        fetch_premium_fn: callable(strike, option_type) → current_premium
        threshold_override: If provided, use this instead of params threshold.
                           Used by wind-down mode to elevate the close threshold.

    Returns:
        List of positions that should be closed, each:
        {side, strike, lots, entry_premium, current_premium, type, profit}
    """
    params = session.get('params', {})
    threshold = threshold_override if threshold_override is not None else params.get('close_at_threshold', 5.0)
    closeable = []

    for side_key in ['ce', 'pe']:
        side_state = session.get(side_key, {})
        option_type = 'call' if side_key == 'ce' else 'put'
        active_strike = side_state.get('active_strike', 0)

        # Fix #23: Look up original position ID from positions[] for ID-based removal
        # Audit fix: skip positions marked _being_closed (in-flight guard)
        orig_pos_id = None
        orig_being_closed = False
        for _p in side_state.get('positions', []):
            if _p.get('type') == 'original' and _p.get('status') == 'active':
                orig_pos_id = _p.get('id')
                orig_being_closed = _check_stale_being_closed(
                    _p, f"{side_key} original id={_p.get('id')}"
                )
                break

        # Check original lots at original strike (Fix #9: use original_strike, not
        # active_strike. In current flow they're the same until a shift occurs, at
        # which point original_lots becomes 0 anyway. Using original_strike here is
        # the correct defensive approach — avoids premium mismatch if the two ever
        # diverge in future code paths).
        orig_lots = side_state.get('original_lots', 0)
        orig_prem = side_state.get('original_premium', 0)
        orig_strike = side_state.get('original_strike', active_strike)
        if orig_lots > 0 and orig_strike > 0 and not orig_being_closed:
            try:
                current = fetch_premium_fn(orig_strike, option_type)
                # AUDIT FIX: Guard against None premium return
                if current is None:
                    log.debug(f"No premium data for {side_key} original @ {orig_strike}")
                elif current <= threshold:
                    profit = (orig_prem - current) * orig_lots * LOT_SIZE_BTC
                    closeable.append({
                        'side': side_key,
                        'strike': orig_strike,
                        'lots': orig_lots,
                        'entry_premium': orig_prem,
                        'current_premium': current,
                        'type': 'original',
                        'profit': profit,
                        '_pos_id': orig_pos_id,  # Fix #23: ID-based removal
                    })
            except Exception as e:
                log.warning(f"Error fetching {side_key} original premium: {e}")


        # Check adjustment fills at active strike
        # Fix #8: removal is content-match based (with Fix #23 ID fallback)
        for fill in side_state.get('adjustment_fills', []):
            if _check_stale_being_closed(fill, f"{side_key} adjustment @ {fill.get('strike')}"):
                continue
            lots = fill.get('lots', 0)
            prem = fill.get('premium', 0)
            strike = fill.get('strike', active_strike)
            if lots > 0:
                try:
                    current = fetch_premium_fn(strike, option_type)
                    if current is None:
                        continue
                    if current <= threshold:
                        profit = (prem - current) * lots * LOT_SIZE_BTC
                        closeable.append({
                            'side': side_key,
                            'strike': strike,
                            'lots': lots,
                            'entry_premium': prem,
                            'current_premium': current,
                            'type': 'adjustment',
                            'profit': profit,
                            '_pos_id': fill.get('_pos_id'),  # Fix #23: ID-based removal
                        })
                except Exception as e:
                    log.warning(f"Error fetching adj fill premium: {e}")

        # Check frozen positions
        # Fix #8: removal is content-match based (with Fix #23 ID fallback)
        for frozen in side_state.get('frozen_positions', []):
            if _check_stale_being_closed(frozen, f"{side_key} frozen @ {frozen.get('strike')}"):
                continue
            lots = frozen.get('lots', 0)
            prem = frozen.get('entry_premium', 0)
            strike = frozen.get('strike', 0)
            if lots > 0 and strike > 0:
                try:
                    current = fetch_premium_fn(strike, option_type)
                    if current is None:
                        continue
                    if current <= threshold:
                        profit = (prem - current) * lots * LOT_SIZE_BTC
                        closeable.append({
                            'side': side_key,
                            'strike': strike,
                            'lots': lots,
                            'entry_premium': prem,
                            'current_premium': current,
                            'type': 'frozen',
                            'profit': profit,
                            '_pos_id': frozen.get('_pos_id'),  # Fix #23: ID-based removal
                        })
                except Exception as e:
                    log.warning(f"Error fetching frozen premium: {e}")

    # Log scan summary for debugging (even when nothing is closeable)
    session_id = session.get('session_id', '?')
    total_checked = 0
    for side_key in ['ce', 'pe']:
        ss = session.get(side_key, {})
        total_checked += (1 if ss.get('original_lots', 0) > 0 else 0)
        total_checked += len([f for f in ss.get('adjustment_fills', []) if f.get('lots', 0) > 0])
        total_checked += len([f for f in ss.get('frozen_positions', []) if f.get('lots', 0) > 0])

    if not closeable and total_checked > 0:
        log.debug(
            f"[{session_id}] Close-at-5 scan: checked {total_checked} positions, "
            f"none below threshold {threshold:.1f}"
        )

    # Stamp every result item with the threshold that triggered it, so callers
    # (walkthrough, monitor) can display it accurately (wind-down uses $20, normal $5).
    for item in closeable:
        item['threshold_used'] = threshold

    if closeable:
        log.info(
            f"[{session_id}] Found {len(closeable)} position(s) eligible for close-at-5 "
            f"(threshold={threshold:.1f})"
        )
        # Fix #8: content-match-first removal makes index-based sorting unnecessary.
        # Sort by profit descending — close the most profitable positions first.
        # (Frozen > adjustment > original ordering is preserved as a secondary key
        # so higher-premium frozen positions don't accidentally beat active strikes.)
        _type_order = {'frozen': 2, 'adjustment': 1, 'original': 0}
        closeable.sort(
            key=lambda p: (
                p.get('side', ''),
                _type_order.get(p.get('type', ''), -1),
                p.get('profit', 0),
            ),
            reverse=True,
        )

    return closeable


async def close_position(
    executor,
    initializer,
    session: Dict,
    position: Dict,
    pnl_attribution_key: str = None,
    hedge_guard: bool = True,
    mechanism: str = 'close_at_5',
    side: str = None,
) -> Dict[str, Any]:
    """
    §11: Buy back a single position at market/ask price.

    Args:
        executor: MMMExecutor instance
        initializer: MMMInitializer instance for symbol building
        session: Full session dict (mutated in place)
        position: Position dict from scan_closeable_positions or raw ledger
        hedge_guard: Kept for backward compatibility. When True, the Strategy
                 Observer's continuity check (CHECK 1) is enforced.
                 Pass False only when both sides are closing together.
        mechanism: Why this close is being requested. Passed to the Strategy
               Observer for price-consistency and velocity checks.
               Values: 'close_at_5' | 'harvest' | 'recycler' | 'atm_shield'
                   | 'wind_down' | 'both_sides_close' | 'emergency'
        side: Explicit side ('ce'/'pe'). Falls back to position['side'].

    Returns:
        {success, realized_pnl, close_premium, lots_closed}

    Audit fix (double-close guard): Sets _being_closed=True on the position in
    positions[] BEFORE placing the exchange order. If the order fills but
    _remove_closed_position() crashes, the position stays in-state but is marked
    as in-flight. scan_closeable_positions() skips '_being_closed' positions, so
    the next heartbeat will NOT place a duplicate buy order on the exchange.
    On failure, the flag is cleared to allow retry on the next scan cycle.
    """
    side = side or position.get('side')
    if not side:
        log.error("close_position called without side — position dict has no 'side' key and no explicit side param")
        return {'success': False, 'error': 'missing side'}
    strike = position['strike']
    lots = position['lots']
    entry_prem = position['entry_premium']
    pos_type = position['type']
    pos_id = position.get('_pos_id') or position.get('id')

    # ── GUARDIAN G1+G2: HEDGE INTEGRITY + BEAT VELOCITY ────────────────
    # Look up the real guardian instance for this session (registered by
    # the monitor). Falls back to a temporary instance for G1-only check
    # if the registry lookup fails (e.g. standalone test).
    _guardian = None
    if hedge_guard:
        try:
            from .mmm_guardian import get_guardian, MMMGuardian
            sid_for_lookup = session.get('session_id', '')
            _guardian = get_guardian(sid_for_lookup)
            if _guardian is None:
                # Standalone call (no monitor) — temporary for G1 only
                _guardian = MMMGuardian(sid_for_lookup)
            _allowed, _g_reason = _guardian.check_close_allowed(
                session, side, lots, mechanism,
                both_sides_closing=False,
            )
            if not _allowed:
                return {
                    'success': False,
                    'error': _g_reason,
                    'hedge_guard_blocked': True,
                }
        except ImportError:
            pass
    # ── END GUARDIAN G1+G2 ──────────────────────────────────────────────

    # ── STRATEGY OBSERVER ─────────────────────────────────────────────────
    # Validate this BUY order against strategy logic BEFORE touching the
    # exchange.  Runs 4 checks: strategy continuity, price consistency,
    # close velocity, and ledger integrity.  hedge_guard=False means both
    # sides are closing together (clean exit) — pass to observer via
    # both_sides_closing flag so continuity check is exempt.
    if hedge_guard:
        try:
            from .mmm_observer import get_observer
            _obs_result = get_observer().validate_close(
                session=session,
                side=side,
                lots=lots,
                current_premium=position.get('current_premium', 0),
                mechanism=mechanism,
                entry_premium=entry_prem,
                both_sides_closing=False,
            )
            if not _obs_result['allowed']:
                _sid = session.get('session_id', '?')
                return {
                    'success': False,
                    'error': _obs_result['reason'],
                    'observer_blocked': True,
                    'block_type': _obs_result.get('block_type'),
                }
        except ImportError:
            pass  # Observer not available — fall through
        # ── END STRATEGY OBSERVER ─────────────────────────────────────────────
    # Audit fix: Mark position as in-flight in the ledger BEFORE placing order.
    # This prevents a duplicate buy order if the state-removal crashes post-fill.
    side_state = session.get(side, {})
    _content_match_view = None  # Track content-match entry for flag cleanup
    if pos_id:
        for pos in side_state.get('positions', []):
            if pos.get('id') == pos_id:
                if pos.get('_being_closed'):
                    log.warning(
                        f"Close-at-5: Skipping {side.upper()} pos_id={pos_id} — "
                        f"already marked _being_closed (in-flight guard). "
                        f"Previous close may have partially succeeded."
                    )
                    return {
                        'success': False,
                        'error': 'Position already being closed (in-flight guard)',
                    }
                pos['_being_closed'] = True
                pos['_being_closed_at'] = time.monotonic()
                break
    else:
        # AUDIT FIX BUG4: Content-match guard for pre-migration (no pos_id) positions
        view_key = 'adjustment_fills' if pos_type == 'adjustment' else (
            'frozen_positions' if pos_type == 'frozen' else None
        )
        if view_key:
            for entry in side_state.get(view_key, []):
                prem_key = 'premium' if pos_type == 'adjustment' else 'entry_premium'
                if (entry.get('lots') == lots
                        and abs(entry.get(prem_key, 0) - entry_prem) < 0.01
                        and abs(entry.get('strike', 0) - strike) < 1):
                    if entry.get('_being_closed'):
                        log.warning(
                            f"Close-at-5: Skipping {side.upper()} {pos_type} @ {strike} — "
                            f"already marked _being_closed (content-match guard)."
                        )
                        return {
                            'success': False,
                            'error': 'Position already being closed (content-match guard)',
                        }
                    entry['_being_closed'] = True
                    entry['_being_closed_at'] = time.monotonic()
                    _content_match_view = entry
                    break

    # Build symbol
    expiry = session.get('params', {}).get('expiry', '')
    option_type = 'call' if side == 'ce' else 'put'
    symbol = initializer.build_symbol(option_type, 'BTC', strike, expiry)

    log.info(
        f"Close-at-5: Buying back {lots} {side.upper()} @ {strike} "
        f"({symbol}), current ~{position.get('current_premium', 0):.2f}"
    )

    try:
        result = await executor.smart_execute(
            symbol=symbol,
            side='buy',
            size=lots,
            reduce_only=True,
            use_bid_entry=(mechanism == 'close_at_5'),  # Bid-entry for close_at_5: cheaper maker fill
        )

        if not result.get('success'):
            # Clear in-flight flag so position can be retried next heartbeat
            if pos_id:
                for pos in side_state.get('positions', []):
                    if pos.get('id') == pos_id:
                        pos.pop('_being_closed', None)
                        break
            elif _content_match_view:
                _content_match_view.pop('_being_closed', None)
            # On order failure, check if position was already closed externally
            try:
                rest = executor._create_rest_client()
                pos_resp = await rest._request_with_retry(
                    method="GET", path="/v2/positions/margined"
                )
                open_positions = pos_resp.get('result', [])
                position_still_open = any(
                    (p.get('product', {}).get('symbol', '') or p.get('symbol', '')) == symbol
                    and abs(float(p.get('size', 0))) > 0
                    for p in open_positions
                )
                if not position_still_open:
                    log.warning(
                        "Position %s already closed externally, marking as closed in session",
                        symbol,
                    )
                    _remove_closed_position(session, side, position, pos_type)
                    # AUDIT FIX BUG5: Estimate realized PnL from last known premium
                    est_close = position.get('current_premium', 0)
                    est_pnl = float((_D(entry_prem) - _D(est_close)) * _D(lots) * _LOT) if est_close else 0.0
                    
                    # Record successful close for velocity tracking (externally closed)
                    try:
                        from .mmm_observer import get_observer
                        session_id = session.get('session_id', '')
                        if session_id:
                            get_observer().record_close(session_id, side, lots)
                    except Exception:
                        pass
                    if _guardian is not None:
                        try:
                            _guardian.record_close(side, lots)
                        except Exception:
                            pass
                    
                    return {
                        'success': True,
                        'realized_pnl': est_pnl,
                        'close_premium': est_close,
                        'lots_closed': lots,
                        'side': side,
                        'strike': strike,
                        'externally_closed': True,
                    }
            except Exception as check_err:
                log.warning("Could not verify position existence: %s", check_err)
            return {
                'success': False,
                'error': result.get('error', 'Buy-back not filled'),
            }

        close_price = result.get('fill_price', 0)
        # AUDIT BUG-2 FIX: Use actual filled size, not requested lots.
        actual_lots = result.get('filled_size', lots)
        if actual_lots <= 0:
            actual_lots = lots
        if actual_lots < lots:
            log.warning(
                f"Close-at-5 PARTIAL FILL: requested {lots} {side.upper()} "
                f"@ {strike}, only {actual_lots} filled."
            )
        # Fix #19: Decimal arithmetic to prevent float rounding accumulation
        realized_pnl = float((_D(entry_prem) - _D(close_price)) * _D(actual_lots) * _LOT)

        # Update state: remove or reduce the closed position.
        # Partial fill: reduce remaining lots in-state instead of removing entirely.
        # Full fill:    mark position closed (original behaviour).
        # Note: _being_closed flag is cleared by _remove_closed_position / _partial_close_position.
        if actual_lots < lots:
            _partial_close_position(session, side, position, pos_type, actual_lots)
        else:
            _remove_closed_position(session, side, position, pos_type)

        # Register this close for post-close verification.
        # The exchange positions API takes 1-5 s to reflect a fill; without this
        # registry the very-next-heartbeat reconciliation sees the position still
        # on the exchange but no longer in session state and raises a spurious
        # UNTRACKED_EXCHANGE_POSITION warning.
        _pcv = session.setdefault('_pending_close_verification', {})
        _pcv[symbol] = {
            'side': side,
            'strike': strike,
            'lots_closed': actual_lots,
            'grace_beats': 3,          # skip mismatch for up to 3 reconciliation cycles
        }

        # Record realized P&L
        session['realized_pnl'] = session.get('realized_pnl', 0) + realized_pnl
        # T2-5: P&L attribution by source
        _attr_key = pnl_attribution_key
        if _attr_key is None:
            _attr_key = 'pnl_initial' if pos_type == 'original' else 'pnl_adjustment'
        session[_attr_key] = session.get(_attr_key, 0.0) + realized_pnl
        session['close_at_5_count'] = session.get('close_at_5_count', 0) + 1
        session['updated_at'] = datetime.now(timezone.utc).isoformat()

        # Analytics: Track auto-close event (no trading logic impact)
        analytics = session.setdefault('analytics', {})
        analytics.setdefault('auto_close_events', []).append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'side': side,
            'strike': strike,
            'lots': actual_lots,
            'reason': 'close_at_threshold',
            'realized_pnl': realized_pnl,
        })
        if len(analytics['auto_close_events']) > 200:
            analytics['auto_close_events'] = analytics['auto_close_events'][-200:]
        analytics['auto_close_total_lots'] = analytics.get('auto_close_total_lots', 0) + actual_lots

        log.info(
            f"Close-at-5 success: {actual_lots} {side.upper()} @ {strike}, "
            f"realized P&L: {realized_pnl:.2f}"
        )

        # Persistent audit trail (activity log)
        try:
            from .mmm_activity import log_activity as _log_activity
            _log_activity(
                'close_at_5',
                f'{actual_lots} {side.upper()} @ {strike} | entry={entry_prem:.2f} close={close_price:.2f} pnl={realized_pnl:.4f}',
                session.get('session_id', ''),
                'info',
                {
                    'side': side, 'strike': strike, 'lots': actual_lots,
                    'entry_premium': entry_prem, 'close_premium': close_price,
                    'realized_pnl': realized_pnl, 'mechanism': mechanism,
                },
            )
        except Exception:
            pass

        # Record successful close for velocity tracking (observer + guardian)
        try:
            from .mmm_observer import get_observer
            session_id = session.get('session_id', '')
            if session_id:
                get_observer().record_close(session_id, side, actual_lots)
        except Exception:
            pass
        if _guardian is not None:
            try:
                _guardian.record_close(side, actual_lots)
            except Exception:
                pass

        return {
            'success': True,
            'realized_pnl': realized_pnl,
            'close_premium': close_price,
            'lots_closed': actual_lots,
            'side': side,
            'strike': strike,
        }

    except Exception as e:
        # Clear in-flight flag on unexpected exception so position can be retried
        if pos_id:
            for pos in side_state.get('positions', []):
                if pos.get('id') == pos_id:
                    pos.pop('_being_closed', None)
                    break
        elif _content_match_view:
            _content_match_view.pop('_being_closed', None)
        # Fix F2.4: Force recompute after exception to ensure derived values are consistent
        recompute_side_lots(side_state)
        session[side] = side_state
        
        log.exception(f"Close-at-5 execution failed: {e}")
        return {
            'success': False,
            'error': str(e),
        }




def _partial_close_position(
    session: Dict,
    side: str,
    position: Dict,
    pos_type: str,
    closed_lots: int,
):
    """
    Reduce a position's lot count after a partial fill.

    Called instead of _remove_closed_position when smart_execute returns
    filled_size < requested lots.  The unfilled remainder stays in session
    state so that:
      (a) reconciliation can track the remaining exchange position, and
      (b) the next close-at-5 scan can attempt to buy back the remainder.

    Does NOT mark the position as closed — only mutates the 'lots' field
    on the position record in positions[] and calls recompute_side_lots.
    """
    side_state = session.get(side, {})
    pos_id = position.get('_pos_id') or position.get('id')
    remaining = max(0, position.get('lots', 0) - closed_lots)

    if pos_id:
        for pos in side_state.get('positions', []):
            if pos.get('id') == pos_id:
                pos['lots'] = remaining
                pos.pop('_being_closed', None)
                if remaining <= 0:
                    # Edge-case: became 0 through rounding — treat as fully closed
                    pos['status'] = 'closed'
                    pos['closed_at'] = datetime.now(timezone.utc).isoformat()
                break
    else:
        # Content-match fallback (pre-migration sessions)
        if pos_type == 'original':
            side_state['original_lots'] = remaining
            if remaining <= 0:
                for pos in side_state.get('positions', []):
                    if pos.get('type') == 'original' and pos.get('status') == 'active':
                        pos['status'] = 'closed'
                        pos['closed_at'] = datetime.now(timezone.utc).isoformat()
                        break
        elif pos_type in ('adjustment', 'frozen'):
            view_key = 'adjustment_fills' if pos_type == 'adjustment' else 'frozen_positions'
            prem_key = 'premium' if pos_type == 'adjustment' else 'entry_premium'
            target_lots = position.get('lots', 0)
            target_prem = position.get('entry_premium', 0)
            target_strike = position.get('strike', 0)
            for entry in side_state.get(view_key, []):
                if (entry.get('lots') == target_lots
                        and abs(entry.get(prem_key, 0) - target_prem) < 0.01
                        and abs(entry.get('strike', 0) - target_strike) < 1):
                    entry['lots'] = remaining
                    entry.pop('_being_closed', None)
                    break

    recompute_side_lots(side_state)
    session[side] = side_state
    log.info(
        f"Partial close: {side.upper()} @ {position.get('strike')} "
        f"closed={closed_lots}, remaining={remaining} lots in state"
    )


def _remove_closed_position(
    session: Dict,
    side: str,
    position: Dict,
    pos_type: str,
):
    """
    Mark a position as closed in state.

    Fix #23: Uses ID-based O(1) lookup in positions[] when _pos_id is available.
    Falls back to content-match for pre-migration sessions or missing IDs.
    """
    side_state = session.get(side, {})
    now = datetime.now(timezone.utc).isoformat()

    pos_id = position.get('_pos_id') or position.get('id')

    # Fix #23: Primary path — ID-based lookup in positions[] (O(1), always correct)
    if pos_id:
        found = False
        for pos in side_state.get('positions', []):
            if pos.get('id') == pos_id:
                pos['status'] = 'closed'
                pos['closed_at'] = now
                found = True
                break
        if not found:
            log.warning(
                f"Close-at-5 ID-based removal: pos_id={pos_id} not found in "
                f"positions[]. Position may already be closed."
            )
        recompute_side_lots(side_state)
        session[side] = side_state
        return

    # Fallback: content-match (Fix #8 logic for pre-migration sessions).
    # After first heartbeat recompute, _pos_id is always present.
    if pos_type == 'original':
        side_state['original_lots'] = 0
        side_state['original_premium'] = 0.0
        # AUDIT FIX: Also mark in positions[] so recompute doesn't revert
        for pos in side_state.get('positions', []):
            if pos.get('type') == 'original' and pos.get('status') == 'active':
                pos['status'] = 'closed'
                pos['closed_at'] = now
                break

    elif pos_type == 'adjustment':
        fills = side_state.get('adjustment_fills', [])
        target_lots = position.get('lots')
        target_prem = position.get('entry_premium', 0)
        target_strike = position.get('strike', 0)
        found = False
        for i in range(len(fills) - 1, -1, -1):
            f = fills[i]
            if (f.get('lots') == target_lots
                    and abs(f.get('premium', 0) - target_prem) < 0.01
                    and (target_strike == 0 or abs(f.get('strike', 0) - target_strike) < 1)):
                fills.pop(i)
                found = True
                break
        if not found:
            log.warning(
                f"Close-at-5 adjustment content-match failed: "
                f"lots={target_lots}, prem≈{target_prem:.2f}, strike={target_strike}. "
                f"Position may already have been removed."
            )

    elif pos_type == 'frozen':
        frozen = side_state.get('frozen_positions', [])
        target_lots = position.get('lots')
        target_prem = position.get('entry_premium', 0)
        target_strike = position.get('strike', 0)
        found = False
        for i in range(len(frozen) - 1, -1, -1):
            f = frozen[i]
            if (f.get('lots') == target_lots
                    and abs(f.get('entry_premium', 0) - target_prem) < 0.01
                    and (target_strike == 0 or abs(f.get('strike', 0) - target_strike) < 1)):
                frozen.pop(i)
                found = True
                break
        if not found:
            log.warning(
                f"Close-at-5 frozen content-match failed: "
                f"lots={target_lots}, prem≈{target_prem:.2f}, strike={target_strike}. "
                f"Position may already have been removed."
            )

    recompute_side_lots(side_state)
    session[side] = side_state


@sealed
def check_side_fully_closed(session: Dict, side: str) -> bool:
    """
    §11: Check if all positions on a side have been closed.

    Returns:
        True if the side has zero total lots
    """
    side_state = session.get(side, {})
    return side_state.get('total_lots', 0) == 0


@sealed
def check_both_sides_closed(session: Dict) -> bool:
    """
    §11: Check if both sides are fully closed.
    This is the BEST outcome — all sold options expired/closed worthless.

    Returns:
        True if both CE and PE have zero total lots
    """
    return (
        check_side_fully_closed(session, 'ce') and
        check_side_fully_closed(session, 'pe')
    )
