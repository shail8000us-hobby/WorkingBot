"""
MMM Lot Recycling (M2) — Money Mind & Method

Emergency capacity relief when max lots blocks an adjustment.

When an adjustment trigger fires but the position cap is hit, this module:
  Phase A — Buyback: close cheap frozen positions on the capped side
  Phase B — New Sell: sell fewer lots at a better (ATM-closer) strike that
            covers the buyback cost + the original loss to hedge

Net result: fewer lots, better premium, freed capacity.

See MMM_LOT_RECYCLING_IMPLEMENTATION_PLAN.md §4.

Created: March 3, 2026
"""

import logging
import math
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from .mmm_constants import LOT_SIZE_BTC, _D, _LOT
from .mmm_state import recompute_side_lots

log = logging.getLogger('mmm_recycler')


# =============================================================================
# §4.3: Recyclable Position Selection
# =============================================================================

def select_recyclable_positions(
    session: Dict,
    side: str,
) -> List[Dict[str, Any]]:
    """
    §4.3: Select frozen positions on `side` eligible for recycling.

    Eligibility:
      - Position is on the capped side
      - Position is NOT the original entry if recycle_protect_original=True
      - Not marked _being_closed (in-flight guard)

    Returns positions sorted ascending by entry_premium (cheapest first heuristic
    before live premium fetch). Caller must populate current_premium before use.
    Each entry is compatible with close_position() from mmm_close_at_5.
    """
    params = session.get('params', {})
    protect_original = params.get('recycle_protect_original', True)

    side_state = session.get(side, {})
    frozen_positions = side_state.get('frozen_positions', [])

    # Pre-build set of in-flight position IDs (O(1) lookup instead of O(N) scan)
    being_closed_ids = {
        p.get('id') for p in side_state.get('positions', [])
        if p.get('_being_closed')
    }

    recyclable = []
    for frozen in frozen_positions:
        lots = frozen.get('lots', 0)
        entry_prem = frozen.get('entry_premium', 0)
        strike = frozen.get('strike', 0)
        pos_id = frozen.get('_pos_id', '')
        pos_type = frozen.get('type', 'adjustment')

        if lots <= 0 or strike <= 0:
            continue

        # Never recycle the original entry position if protection is on
        if protect_original and pos_type == 'original':
            continue

        # Skip positions marked _being_closed (in-flight guard)
        if pos_id and pos_id in being_closed_ids:
            continue

        recyclable.append({
            'side': side,
            'strike': strike,
            'lots': lots,
            'entry_premium': entry_prem,
            'current_premium': None,  # Populated by caller after live fetch
            'type': 'frozen',
            'profit': 0.0,            # Populated by caller
            '_pos_id': pos_id,
        })

    # Sort by entry_premium ascending (cheapest-first heuristic before live fetch)
    recyclable.sort(key=lambda p: p.get('entry_premium', 0))
    return recyclable


# =============================================================================
# §4.4: Viability Check
# =============================================================================

def check_recycle_viability(
    recyclable_with_prices: List[Dict],
    loss_to_hedge: float,
    new_premium: float,
    current_active_lots: int,   # Split Ledger: was current_total_lots, now active only
    max_lots_per_side: int,
    params: Dict,
) -> Tuple[bool, str, Dict]:
    """
    §4.4: Verify the math works before committing to a recycle.

    Three checks must ALL pass:
      1. Premium ratio: new_premium / avg_recycle_premium >= min_ratio
      2. Net lot gain: recycled_lots - new_lots_needed >= min_lot_gain
      3. Affordability: current_active_lots + new_lots_needed <= max_lots_per_side

    Args:
        recyclable_with_prices: Selected positions with current_premium populated
        loss_to_hedge: Original loss that triggered the adjustment (USD)
        new_premium: Premium at the proposed new strike
        current_active_lots: Current ACTIVE lots on the capped side (excludes frozen)
        max_lots_per_side: Max allowed lots per side
        params: Session params dict

    Returns:
        (viable, reason, details_dict)
    """
    min_ratio = params.get('recycle_min_premium_ratio', 2.5)
    buffer_pct = params.get('premium_buffer_pct', 0.05)
    min_lot_gain = params.get('recycle_min_lot_gain', 5)

    if not recyclable_with_prices:
        return False, 'No recyclable positions selected', {}

    if new_premium <= 0:
        return False, 'New strike has zero premium', {}

    # Compute buyback cost (USD) — Decimal arithmetic for precision
    buyback_cost = float(sum(
        _D(p['current_premium']) * _D(p['lots']) * _LOT
        for p in recyclable_with_prices
    ))
    recycled_lots = sum(p['lots'] for p in recyclable_with_prices)

    if recycled_lots == 0:
        return False, 'Zero recyclable lots', {}

    # Compute avg recycle premium — consistent Decimal arithmetic
    avg_recycle_premium = float(sum(
        _D(p['current_premium']) * _D(p['lots'])
        for p in recyclable_with_prices
    )) / recycled_lots

    # Check 1: Premium ratio
    ratio = new_premium / max(avg_recycle_premium, 0.01)
    if ratio < min_ratio:
        return (
            False,
            f'Premium ratio {ratio:.2f} < {min_ratio:.2f} '
            f'(new={new_premium:.2f}, avg_recycle={avg_recycle_premium:.2f})',
            {'ratio': ratio, 'min_ratio': min_ratio},
        )

    # Check 2: Net lot gain
    total_to_cover = buyback_cost + max(loss_to_hedge, 0)
    raw_new_lots = total_to_cover / (new_premium * LOT_SIZE_BTC) * (1 + buffer_pct)
    new_lots_needed = max(math.ceil(raw_new_lots), 1)
    net_lot_gain = recycled_lots - new_lots_needed

    if net_lot_gain < min_lot_gain:
        return (
            False,
            f'Net lot gain {net_lot_gain} < {min_lot_gain} '
            f'(recycled={recycled_lots}, new_needed={new_lots_needed})',
            {'net_lot_gain': net_lot_gain, 'recycled_lots': recycled_lots,
             'new_lots_needed': new_lots_needed},
        )

    # Check 3: Affordability — Split Ledger
    # Phase A closes frozen positions → active_lots is UNCHANGED after Phase A.
    # Phase B adds new_lots_needed to active_lots. Verify it fits within cap.
    if current_active_lots + new_lots_needed > max_lots_per_side:
        return (
            False,
            f'Affordability: {new_lots_needed} new + {current_active_lots} active '
            f'= {new_lots_needed + current_active_lots} > cap {max_lots_per_side}',
            {'new_lots_needed': new_lots_needed, 'current_active': current_active_lots,
             'cap': max_lots_per_side},
        )

    details = {
        'buyback_cost': round(buyback_cost, 4),
        'recycled_lots': recycled_lots,
        'avg_recycle_premium': round(avg_recycle_premium, 2),
        'ratio': round(ratio, 2),
        'total_to_cover': round(total_to_cover, 4),
        'new_lots_needed': new_lots_needed,
        'net_lot_gain': net_lot_gain,
        'current_active': current_active_lots,
    }
    return True, 'Viable', details


# =============================================================================
# §4.5: Two-Phase Execution
# =============================================================================

async def execute_lot_recycling(
    session: Dict,
    aggressor: str,
    hedge_side: str,
    loss_to_hedge: float,
    fetch_premium_fn,
    initializer,
    executor,
    spot_price: float,
    engine,
    ce_now: float = 0.0,
    pe_now: float = 0.0,
) -> Dict[str, Any]:
    """
    §4.5: Execute lot recycling — two-phase atomic operation.

    Phase A — Buyback recyclable frozen positions on the capped side.
    Phase B — Sell fewer lots at a better (closer-to-ATM) strike.

    Args:
        session: Full session dict (mutated in place)
        aggressor: 'ce' or 'pe' — the triggering side
        hedge_side: 'ce' or 'pe' — the capped side to recycle
        loss_to_hedge: Loss amount that triggered the adjustment (USD)
        fetch_premium_fn: callable(strike, option_type) → premium
        initializer: MMMInitializer instance
        executor: MMMExecutor instance
        spot_price: Current BTC spot price
        engine: MMMEngine instance (for execute_adjustment in Phase B)
        ce_now: Current CE premium (passed to execute_adjustment for trigger update)
        pe_now: Current PE premium (passed to execute_adjustment for trigger update)

    Returns:
        {
            'success': bool,
            'recycled_lots': int,
            'new_lots_sold': int,
            'buyback_cost': float,
            'new_strike': float,
            'new_premium': float,
            'net_lot_gain': int,
            'error': str (on failure),
        }
    """
    from .mmm_close_at_5 import close_position
    from .mmm_strike_shift import find_new_strike

    params = session.get('params', {})
    session_id = session.get('session_id', '?')

    if not params.get('recycle_enabled', True):
        return {'success': False, 'error': 'recycle_enabled=False'}

    # §4.2: Cooldown check
    last_recycle = session.get('_last_recycle_at')
    cooldown_sec = params.get('recycle_cooldown_sec', 300)
    if last_recycle:
        try:
            last_dt = datetime.fromisoformat(last_recycle)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if elapsed < cooldown_sec:
                return {
                    'success': False,
                    'error': f'Recycle cooldown active ({elapsed:.0f}s < {cooldown_sec}s)',
                }
        except (ValueError, TypeError):
            pass

    # ── Step 1: Find new strike for Phase B ────────────────────────────────
    new_strike_info = find_new_strike(initializer, session, hedge_side, spot_price)
    if not new_strike_info:
        return {
            'success': False,
            'error': f'No suitable new {hedge_side.upper()} strike found for Phase B',
        }
    new_strike = new_strike_info['strike']
    new_premium = new_strike_info['premium']

    # ── Step 2: Select recyclable positions ────────────────────────────────
    candidates = select_recyclable_positions(session, hedge_side)
    if not candidates:
        return {
            'success': False,
            'error': f'No recyclable positions on {hedge_side.upper()}',
        }

    # Fetch live premiums for candidates and filter by ceiling
    option_type = 'call' if hedge_side == 'ce' else 'put'
    ceiling = params.get('recycle_premium_ceiling', 50.0)
    priced_candidates = []
    for cand in candidates:
        try:
            current = fetch_premium_fn(cand['strike'], option_type)
        except Exception as e:
            log.warning(
                f"[{session_id}] Recycle: error fetching premium for "
                f"{hedge_side.upper()} @ {cand['strike']}: {e}"
            )
            continue
        if current is None or current <= 0 or current > ceiling:
            continue
        cand['current_premium'] = current
        cand['profit'] = float(
            (_D(cand['entry_premium']) - _D(current)) * _D(cand['lots']) * _LOT
        )
        priced_candidates.append(cand)

    if not priced_candidates:
        return {
            'success': False,
            'error': (
                f'No {hedge_side.upper()} frozen positions with premium '
                f'<= {ceiling} found'
            ),
        }

    # Sort cheapest-first (least buyback cost per freed lot)
    priced_candidates.sort(key=lambda p: p['current_premium'])

    # Greedy selection: add positions until we have enough freed lots
    max_lots = params.get('max_lots_per_side', 100)
    hedge_state = session.get(hedge_side, {})
    current_total = hedge_state.get('total_lots', 0)
    max_recycle_pct = params.get('recycle_max_pct', 0.50)
    max_recyclable_lots = math.floor(current_total * max_recycle_pct)
    free_lot_buffer = params.get('recycle_free_lot_buffer', 10)

    # Compute estimated lots needed to determine target freed lots.
    # BUG FIX: Cannot use engine.calculate_lots_to_sell() here because it
    # applies the position cap — which returns 0 since we're at cap (that's
    # why recycling was triggered). Compute raw uncapped lots directly.
    buffer_pct = params.get('premium_buffer_pct', 0.05)
    raw_new_lots = max(
        math.ceil(loss_to_hedge / (new_premium * LOT_SIZE_BTC) * (1 + buffer_pct)),
        1,
    )
    target_freed = max(raw_new_lots + free_lot_buffer, 1)

    selected = []
    selected_lots = 0
    for cand in priced_candidates:
        if selected_lots >= max_recyclable_lots:
            break
        selected.append(cand)
        selected_lots += cand['lots']
        if selected_lots >= target_freed:
            break

    if not selected:
        return {
            'success': False,
            'error': 'No recyclable positions selected after greedy pass',
        }

    # ── Step 3: Viability check ────────────────────────────────────────────
    current_active = hedge_state.get('active_lots', 0)   # Split Ledger
    viable, reason, viability_details = check_recycle_viability(
        recyclable_with_prices=selected,
        loss_to_hedge=loss_to_hedge,
        new_premium=new_premium,
        current_active_lots=current_active,
        max_lots_per_side=max_lots,
        params=params,
    )

    if not viable:
        log.info(f"[{session_id}] Recycle viability check FAILED: {reason}")
        return {
            'success': False,
            'error': f'Viability check failed: {reason}',
            'viability_details': viability_details,
        }

    new_lots_needed = viability_details['new_lots_needed']
    buyback_cost = viability_details['buyback_cost']

    log.info(
        f"[{session_id}] Recycle viable: recycling {selected_lots} lots "
        f"from {len(selected)} {hedge_side.upper()} frozen positions, "
        f"selling {new_lots_needed} @ new strike {new_strike} "
        f"(ratio={viability_details['ratio']:.2f}x, "
        f"net_gain={viability_details['net_lot_gain']} lots)"
    )

    # ── Phase A: Buyback recyclable positions ──────────────────────────────
    phase_a_pnl = 0.0
    phase_a_lots = 0
    phase_a_fails = 0
    bought_back_positions = []  # Track successfully closed positions for rollback

    for pos in selected:
        try:
            result = await close_position(
                executor, initializer, session, pos,
                pnl_attribution_key='pnl_recycle',
            )
            if result.get('success'):
                phase_a_pnl += result.get('realized_pnl', 0)
                phase_a_lots += result.get('lots_closed', 0)
                bought_back_positions.append(pos)
            else:
                phase_a_fails += 1
                log.warning(
                    f"[{session_id}] Recycle Phase A: buyback failed for "
                    f"{hedge_side.upper()} @ {pos['strike']}: "
                    f"{result.get('error', 'unknown')}"
                )
        except Exception as e:
            phase_a_fails += 1
            log.exception(
                f"[{session_id}] Recycle Phase A: exception buying back "
                f"{hedge_side.upper()} @ {pos['strike']}: {e}"
            )

    if phase_a_lots == 0:
        return {
            'success': False,
            'error': f'Phase A: all {len(selected)} buybacks failed',
        }

    log.info(
        f"[{session_id}] Recycle Phase A complete: bought back {phase_a_lots} lots, "
        f"realized P&L: {phase_a_pnl:.4f}, fails: {phase_a_fails}"
    )

    # ── Phase B: Sell at new strike ────────────────────────────────────────
    # Recompute final Phase B lots using the viability details
    total_to_cover = buyback_cost + max(loss_to_hedge, 0)
    buffer_pct = params.get('premium_buffer_pct', 0.05)
    raw_phase_b_lots = total_to_cover / (new_premium * LOT_SIZE_BTC) * (1 + buffer_pct)
    phase_b_lots = max(math.ceil(raw_phase_b_lots), 1)

    # Final cap check after Phase A — Split Ledger: Phase A only closes frozen,
    # so active_lots is unchanged. Phase B adds to active_lots.
    hedge_state_refreshed = session.get(hedge_side, {})
    remaining_after_a = hedge_state_refreshed.get('active_lots', 0)
    if remaining_after_a + phase_b_lots > max_lots:
        phase_b_lots = max_lots - remaining_after_a
        if phase_b_lots <= 0:
            log.warning(
                f"[{session_id}] Recycle Phase B: still at cap after Phase A. "
                f"Phase A freed capacity but not enough for new sell."
            )
            session['recycle_attempt_count'] = session.get('recycle_attempt_count', 0) + 1
            session['_last_recycle_at'] = datetime.now(timezone.utc).isoformat()
            return {
                'success': False,
                'error': 'Phase B: still at cap after Phase A (partial — lots freed)',
                'phase_a_lots': phase_a_lots,
                'phase_a_pnl': phase_a_pnl,
                'new_lots_sold': 0,
            }

    try:
        phase_b_result = await engine.execute_adjustment(
            session, hedge_side, new_strike, phase_b_lots,
            ce_now, pe_now,
            adj_type='recycle',
        )
    except Exception as e:
        log.exception(f"[{session_id}] Recycle Phase B execution exception: {e}")
        # Compensating transaction: restore bought-back positions to active state
        side_state = session.get(hedge_side, {})
        for pos in bought_back_positions:
            pos['status'] = 'active'
            pos.pop('_being_closed', None)
            side_state.setdefault('positions', []).append(pos)
        recompute_side_lots(side_state)
        session[hedge_side] = side_state
        # Rollback realized P&L added by close_position() during Phase A
        session['realized_pnl'] = session.get('realized_pnl', 0) - phase_a_pnl
        # T2-5: Roll back pnl_recycle attribution (mirrors realized_pnl rollback)
        session['pnl_recycle'] = session.get('pnl_recycle', 0.0) - phase_a_pnl
        log.error(
            "Phase B exception — restored %d positions to active state, "
            "rolled back Phase A P&L: %.4f",
            len(bought_back_positions), phase_a_pnl,
        )
        session['recycle_attempt_count'] = session.get('recycle_attempt_count', 0) + 1
        session['_last_recycle_at'] = datetime.now(timezone.utc).isoformat()
        return {
            'success': False,
            'error': f'Phase B exception: {e} (Phase A lots freed)',
            'phase_a_lots': phase_a_lots,
            'phase_a_pnl': phase_a_pnl,
            'new_lots_sold': 0,
        }

    if not phase_b_result.get('success'):
        error_msg = phase_b_result.get('error', 'unknown')
        log.warning(
            f"[{session_id}] Recycle Phase B FAILED: {error_msg}. "
            f"Phase A lots were freed."
        )
        # Compensating transaction: restore bought-back positions to active state
        side_state = session.get(hedge_side, {})
        for pos in bought_back_positions:
            pos['status'] = 'active'
            pos.pop('_being_closed', None)
            side_state.setdefault('positions', []).append(pos)
        recompute_side_lots(side_state)
        session[hedge_side] = side_state
        # Rollback realized P&L added by close_position() during Phase A
        session['realized_pnl'] = session.get('realized_pnl', 0) - phase_a_pnl
        # T2-5: Roll back pnl_recycle attribution (mirrors realized_pnl rollback)
        session['pnl_recycle'] = session.get('pnl_recycle', 0.0) - phase_a_pnl
        log.error(
            "Phase B failed — restored %d positions to active state, "
            "rolled back Phase A P&L: %.4f",
            len(bought_back_positions), phase_a_pnl,
        )
        session['recycle_attempt_count'] = session.get('recycle_attempt_count', 0) + 1
        session['_last_recycle_at'] = datetime.now(timezone.utc).isoformat()
        return {
            'success': False,
            'error': f'Phase B failed: {error_msg} (Phase A lots freed)',
            'phase_a_lots': phase_a_lots,
            'phase_a_pnl': phase_a_pnl,
            'new_lots_sold': 0,
        }

    # ── Success ────────────────────────────────────────────────────────────
    session['recycle_count'] = session.get('recycle_count', 0) + 1
    session['_last_recycle_at'] = datetime.now(timezone.utc).isoformat()
    session['updated_at'] = datetime.now(timezone.utc).isoformat()

    net_lot_gain = viability_details['net_lot_gain']
    log.info(
        f"[{session_id}] Recycle COMPLETE: "
        f"freed {phase_a_lots} lots, sold {phase_b_lots} @ {new_strike} "
        f"(net gain: {net_lot_gain} lots, Phase A P&L: {phase_a_pnl:.4f})"
    )

    return {
        'success': True,
        'recycled_lots': phase_a_lots,
        'new_lots_sold': phase_b_lots,
        'buyback_cost': buyback_cost,
        'new_strike': new_strike,
        'new_premium': new_premium,
        'net_lot_gain': net_lot_gain,
        'phase_a_pnl': phase_a_pnl,
        'fill_price': phase_b_result.get('fill_price', 0),
        'viability_details': viability_details,
    }
