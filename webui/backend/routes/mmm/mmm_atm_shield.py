"""
MMM ATM Shield — Close & Retreat

Pre-emptively closes positions approaching ATM and repositions at a safer
OTM strike.  Fires BEFORE close_at_ATM to preserve premium-collection capacity.

Key behavior:
  - Full position shift: original lots are re-established at the new strike
  - Loss recovery: additional lots are sold to cover 30%/70% of buyback loss
  - Sympathetic rebalance: safe side shifted closer if premium decayed

Created: March 12, 2026
"""

import logging
import math
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from webui.backend.sealed import sealed
from .mmm_constants import LOT_SIZE_BTC, strike_key
from .mmm_close_at_5 import close_position
from .mmm_engine import get_engine
from .mmm_strike_shift import find_new_strike
from .mmm_wind_down import is_wind_down_active

log = logging.getLogger('mmm_atm_shield')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@sealed
def _compute_time_mult(minutes_to_expiry: float) -> float:
    """Time-to-expiry multiplier: fires wider as expiry approaches."""
    hours = max(minutes_to_expiry / 60.0, 0.5)
    return min(3.0, max(1.0, 3.0 / hours))


@sealed
def _compute_effective_proximity(params: Dict, time_mult: float) -> float:
    """Effective proximity % scaled by time multiplier."""
    base = params.get('atm_shield_proximity_pct', 0.5)
    return base * time_mult


@sealed
def _compute_effective_target_otm(params: Dict, time_mult: float,
                                  shield_count: int) -> float:
    """Effective target OTM % scaled by time and progressive widening."""
    base = params.get('atm_shield_target_otm_pct', 1.0)
    progressive_mult = 1.0 + (shield_count * 0.5)
    return base * time_mult * progressive_mult


@sealed
def check_atm_proximity(
    session: Dict,
    spot: float,
    params: Dict,
    time_mult: float,
) -> Tuple[Optional[str], float]:
    """Return (endangered_side, distance_pct) or (None, 0)."""
    eff_proximity = _compute_effective_proximity(params, time_mult)

    for side in ('ce', 'pe'):
        side_state = session.get(side, {})
        active_lots = side_state.get('active_lots', 0)
        active_strike = side_state.get('active_strike', 0)
        if active_lots <= 0 or active_strike <= 0:
            continue

        if side == 'ce':
            distance_pct = (active_strike - spot) / spot * 100
        else:
            distance_pct = (spot - active_strike) / spot * 100

        if distance_pct <= eff_proximity:
            return side, distance_pct

    return None, 0.0


@sealed
def _check_shield_gates(
    session: Dict,
    side: str,
    params: Dict,
    margin_tier: str,
    minutes_to_expiry: float,
) -> Tuple[bool, str]:
    """Return (can_fire, reason).  can_fire=True means gate checks pass."""
    sid = session.get('session_id', '?')
    from .mmm_margin_guardian import TIER_RED, TIER_CRITICAL

    if not params.get('atm_shield_enabled', False):
        return False, 'disabled'

    status = session.get('strategy_status', 'RUNNING')
    if status != 'RUNNING':
        return False, f'status={status}'

    if margin_tier in (TIER_RED, TIER_CRITICAL):
        return False, f'margin={margin_tier}'

    auto_close_mins = params.get('auto_close_mins', 5)
    if minutes_to_expiry is not None and minutes_to_expiry <= auto_close_mins:
        return False, 'within auto_close window'

    # Cooldown
    cooldown_mins = params.get('atm_shield_cooldown_mins', 10)
    last_fire_key = f'_atm_shield_last_fire_{side}'
    last_fire = session.get(last_fire_key)
    if last_fire:
        try:
            last_dt = datetime.fromisoformat(last_fire)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60.0
            if elapsed < cooldown_mins:
                return False, f'cooldown ({elapsed:.1f}/{cooldown_mins}min)'
        except (ValueError, TypeError):
            pass

    # Capacity
    max_fires = params.get('atm_shield_max_per_session', 3)
    count = session.get(f'_atm_shield_count_{side}', 0)
    if count >= max_fires:
        return False, f'exhausted ({count}/{max_fires})'

    # Already proactively shifted this beat
    if session.get(f'_proactive_shifted_{side}'):
        return False, 'proactive shift already ran'

    # Replenish grace hold — when replenish was forced to use a within-buffer
    # strike (no safe OTM alternative found), it sets this flag to prevent an
    # immediate ATM-shield-close → replenish → close cycle.  The hold is per-side
    # so each leg can be independently protected.
    _hold_key = f'_replenish_shield_hold_until_{side}'
    _hold_until = session.get(_hold_key, 0)
    if _hold_until and time.time() < _hold_until:
        _hold_remaining = int(_hold_until - time.time())
        return False, f'replenish_grace_hold ({_hold_remaining}s remaining)'

    return True, 'ok'


# ---------------------------------------------------------------------------
# Main entry point — called from mmm_monitor heartbeat at Step 5.5
# ---------------------------------------------------------------------------

async def execute_atm_shield(monitor, ce_now: float, pe_now: float) -> bool:
    """
    ATM Shield core logic.  Returns True if the shield fired this beat.

    Called from MMMMonitor._run_heartbeat() between Step 5 (cooldown) and
    Step 6 (evaluate triggers).
    """
    session = monitor.session
    sid = session.get('session_id', '?')
    params = session.get('params', {})

    if not params.get('atm_shield_enabled', False):
        return False

    # Fetch spot + time context
    spot = await monitor._fetch_spot_price()
    if spot <= 0:
        return False

    minutes_to_expiry = monitor._get_minutes_to_expiry() or 360
    time_mult = _compute_time_mult(minutes_to_expiry)

    # Proximity check
    endangered_side, distance_pct = check_atm_proximity(
        session, spot, params, time_mult,
    )
    if endangered_side is None:
        return False

    # Both sides endangered simultaneously → defer to close_at_ATM
    safe_side = 'pe' if endangered_side == 'ce' else 'ce'
    _, safe_distance = check_atm_proximity(
        session, spot, params, time_mult,
    )
    # Check safe side explicitly
    safe_state = session.get(safe_side, {})
    safe_active_strike = safe_state.get('active_strike', 0)
    safe_active_lots = safe_state.get('active_lots', 0)
    if safe_active_lots > 0 and safe_active_strike > 0:
        eff_prox = _compute_effective_proximity(params, time_mult)
        if safe_side == 'ce':
            safe_dist = (safe_active_strike - spot) / spot * 100
        else:
            safe_dist = (spot - safe_active_strike) / spot * 100
        if safe_dist <= eff_prox:
            log.warning(
                f"[{sid}] ATM Shield: both sides endangered — "
                f"deferring to close_at_ATM"
            )
            return False

    # Gate checks
    margin_tier = getattr(monitor, '_margin_guardian', None)
    margin_tier_val = margin_tier.last_tier if margin_tier else 'GREEN'
    can_fire, gate_reason = _check_shield_gates(
        session, endangered_side, params, margin_tier_val, minutes_to_expiry,
    )
    if not can_fire:
        log.debug(f"[{sid}] ATM Shield skipped: {gate_reason}")
        return False

    # ── Check for deferred re-sell from previous fire ─────────────────────
    # If a prior fire stored a pending re-sell, execute it now before
    # checking for new proximity.
    pending_key = f'_atm_shield_pending_resell_{endangered_side}'
    pending = session.get(pending_key)
    if pending and time.time() >= pending.get('execute_after', 0):
        session.pop(pending_key, None)
        # Validate strike is still correct.  A strike shift can occur between
        # the beat that stored the deferred re-sell and the beat that executes it.
        # Executing at a stale strike places a sell at a non-active strike that
        # is never recorded in the session ledger → orphaned exchange position.
        _pending_strike = pending.get('strike', 0)
        _current_active = session.get(endangered_side, {}).get('active_strike', 0)
        if _pending_strike != _current_active:
            log.warning(
                f"[{sid}] ATM Shield deferred re-sell ABORTED: "
                f"stored strike {_pending_strike} != current active_strike "
                f"{_current_active} ({endangered_side.upper()} shifted between "
                f"fire and execution) — discarding stale re-sell"
            )
            return False
        log.info(
            f"[{sid}] ATM Shield: executing deferred re-sell for "
            f"{endangered_side.upper()} — "
            f"{pending.get('lots')} lots @ {_pending_strike}"
        )
        try:
            engine = get_engine()
            _dr = await engine.execute_adjustment(
                session, endangered_side, pending['strike'], pending['lots'],
                ce_now, pe_now, adj_type='atm_shield',
            )
            if _dr.get('success'):
                side_state = session.get(endangered_side)
                if isinstance(side_state, dict) and 'active_strike' in side_state:
                    side_state['active_strike'] = pending['strike']
                else:
                    log.warning(
                        f"[{sid}] ATM Shield deferred re-sell: "
                        f"cannot update active_strike — {endangered_side} state missing"
                    )
                log.info(
                    f"[{sid}] ATM Shield: deferred re-sell complete — "
                    f"{pending.get('lots')} lots @ {pending.get('strike')}"
                )
                monitor._save_my_session()
        except Exception as _dr_e:
            log.error(f"[{sid}] ATM Shield deferred re-sell error: {_dr_e}", exc_info=True)
        # Return False — this beat is consumed by the deferred re-sell, not a new fire
        return False

    # ── FIRE ──────────────────────────────────────────────────────────────

    shield_count = session.get(f'_atm_shield_count_{endangered_side}', 0)
    endangered_strike = session.get(endangered_side, {}).get('active_strike', 0)

    log.warning(
        f"[{sid}] 🛡️ ATM SHIELD FIRE #{shield_count + 1}: "
        f"{endangered_side.upper()} @ {endangered_strike:.0f} "
        f"(spot ${spot:.0f}, dist {distance_pct:.2f}%, "
        f"time_mult {time_mult:.1f}x)"
    )

    # ── Step 1: CLOSE all active positions on endangered side ─────────
    side_state = session.get(endangered_side, {})

    # Recovery: clear _being_closed on active positions that are stuck.
    # A close order sets _being_closed=True before sending to exchange.
    # If the state update then fails (bug), the flag is never cleared.
    # Any _being_closed still set at a new heartbeat is definitively stuck
    # (exchange orders resolve in < 1s, heartbeat interval is ≥ 15s).
    for _p in side_state.get('positions', []):
        if _p.get('status') == 'active' and _p.get('_being_closed'):
            log.warning(
                f"[{sid}] ATM Shield: clearing stuck _being_closed on "
                f"{endangered_side.upper()} pos {_p.get('id')} "
                f"@ {_p.get('strike')} ({_p.get('lots')} lots)"
            )
            _p.pop('_being_closed', None)

    positions_to_close = [
        p for p in side_state.get('positions', [])
        if p.get('status') == 'active' and not p.get('_being_closed')
    ]

    # Partial close: atm_shield_partial_pct < 1.0 closes only the closest positions.
    # Positions are already ordered ATM-first (active strike is always at the front
    # of the positions list). Take ceil(N * partial_pct) positions.
    partial_pct = max(0.1, min(1.0, params.get('atm_shield_partial_pct', 1.0)))
    if partial_pct < 1.0 and len(positions_to_close) > 1:
        n_close = math.ceil(len(positions_to_close) * partial_pct)
        positions_to_close = positions_to_close[:n_close]
        log.info(
            f"[{sid}] ATM Shield: partial close {n_close}/{len(side_state.get('positions', []))} "
            f"positions (partial_pct={partial_pct:.2f})"
        )

    total_realized_loss = 0.0
    total_closed_lots = 0

    for pos in positions_to_close:
        try:
            result = await close_position(
                monitor.executor, monitor.initializer, session, pos,
                pnl_attribution_key='atm_shield',
                hedge_guard=False,
                mechanism='atm_shield',
                side=endangered_side,
            )
            if result.get('success'):
                close_prem = result.get('close_premium', 0)
                entry_prem = pos.get('entry_premium', 0)
                lots = pos.get('lots', 0)
                total_closed_lots += lots
                total_realized_loss += (close_prem - entry_prem) * lots * LOT_SIZE_BTC
        except Exception as e:
            log.error(
                f"[{sid}] ATM Shield close error on {endangered_side.upper()}: {e}",
                exc_info=True,
            )

    if total_closed_lots == 0:
        log.warning(f"[{sid}] ATM Shield: no positions closed, aborting")
        return False

    log.info(
        f"[{sid}] ATM Shield closed {total_closed_lots} lots on "
        f"{endangered_side.upper()}, realized loss: ${total_realized_loss:.4f}"
    )

    # ── Step 2: FIND new OTM strike ──────────────────────────────────
    eff_target_otm = _compute_effective_target_otm(params, time_mult, shield_count)
    min_distance = spot * eff_target_otm / 100.0

    new_strike_info = find_new_strike(
        monitor.initializer, session, endangered_side, spot,
        min_otm_distance=min_distance,
    )

    new_strike = new_strike_info['strike'] if new_strike_info else None
    new_premium = new_strike_info['premium'] if new_strike_info else 0

    if new_strike is None:
        log.warning(
            f"[{sid}] ATM Shield: no viable strike at {eff_target_otm:.1f}% OTM "
            f"for {endangered_side.upper()} — close only (loss absorbed). "
            f"Activating wind-down as fallback."
        )
        # No viable OTM strike exists → activate wind-down as the only safe response.
        # This is the ONE case where wind-down is allowed when ATM Shield is active.
        params['wind_down_enabled'] = True
        session['_atm_wind_down_triggered'] = True
        session['_atm_prev_wind_down_enabled'] = False

    # ── Step 3: RE-SELL — full position shift + loss recovery ────────
    engine = get_engine()

    # Deferred re-sell: when atm_shield_defer_resell_beats > 0, store the
    # re-sell for execution on the next heartbeat. Close is always immediate.
    defer_beats = int(params.get('atm_shield_defer_resell_beats', 0))
    defer_resell = defer_beats > 0 and new_strike is not None

    # Check sell-blocking conditions (vol/gamma only — trend exempt for shield)
    from .mmm_margin_guardian import TIER_YELLOW, TIER_ORANGE
    margin_blocks_sells = margin_tier_val in (TIER_YELLOW, TIER_ORANGE)
    wind_down_active = is_wind_down_active(session)
    stop_adj_mins = params.get('stop_adjustment_mins', 15)
    near_stop = (minutes_to_expiry is not None and minutes_to_expiry <= stop_adj_mins)

    vol_regime = session.get('_vol_regime', 'NORMAL')
    gamma_regime = session.get('_gamma_regime', 'NORMAL')
    vol_gamma_blocked = (
        vol_regime in ('HIGH', 'ELEVATED')
        or gamma_regime in ('HARD', 'EMERGENCY')
    )

    # ATM Shield is exempt from wind-down blocking on the endangered side re-sell.
    # Wind-down may fire in the SAME beat (step 4) before the shield runs (step 5.5).
    # The shield IS the answer to ATM proximity — it must be able to re-establish.
    sells_possible = not (
        margin_blocks_sells or near_stop or vol_gamma_blocked
    )

    lots_sold_endangered = 0
    lots_sold_safe = 0
    loss_split_agr = params.get('atm_shield_loss_split_aggressor', 0.3)

    # Endangered side re-sell (exempt from BLOCK_CE/PE_SELLS trend regime)
    if new_strike is not None and sells_possible:
        # Base lots: re-establish original position at new strike
        base_lots = total_closed_lots

        # Recovery lots: cover 30% of loss (capped to closed lots to avoid
        # disproportionate risk — selling 33 lots to recover $1.85 is insane)
        loss_share_agr = max(total_realized_loss, 0) * loss_split_agr
        recovery_lots = 0
        if loss_share_agr > 0 and new_premium > 0:
            recovery_lots = min(
                max(math.ceil(loss_share_agr / (new_premium * LOT_SIZE_BTC)), 0),
                total_closed_lots,
            )

        total_lots_agr = base_lots + recovery_lots

        # Apply position cap
        max_lots = params.get('max_lots_per_side', 100)
        current_lots = session.get(endangered_side, {}).get('active_lots', 0)
        cap_remaining = max(max_lots - current_lots, 0)
        total_lots_agr = min(total_lots_agr, cap_remaining)

        if total_lots_agr > 0:
            if defer_resell:
                # Store for execution on the next heartbeat
                adj_interval = params.get('adjustment_interval', 300)
                execute_after = time.time() + adj_interval * defer_beats
                session[f'_atm_shield_pending_resell_{endangered_side}'] = {
                    'strike': new_strike,
                    'lots': total_lots_agr,
                    'execute_after': execute_after,
                }
                log.info(
                    f"[{sid}] ATM Shield: deferring re-sell {total_lots_agr} lots "
                    f"@ {new_strike:.0f} for {defer_beats} beat(s)"
                )
            else:
                try:
                    result = await engine.execute_adjustment(
                        session, endangered_side, new_strike, total_lots_agr,
                        ce_now, pe_now, adj_type='atm_shield',
                    )
                    if result.get('success'):
                        lots_sold_endangered = total_lots_agr
                        # Update active_strike to reflect new position location
                        session[endangered_side]['active_strike'] = new_strike
                        # Force-set trigger snapshot at new_strike to fill_price.
                        # execute_adjustment → update_trigger_snapshots used the OLD
                        # active_strike key (active_strike is updated above, AFTER the
                        # call returns). Without this, trigger_snapshot[new_strike] is
                        # missing → evaluate_triggers sees trigger=0 → safety guard skips
                        # BOTH sides for the entire next heartbeat.
                        # Mirrors the identical fix in _process_strike_shift (BUG-1 FIX).
                        try:
                            _atm_fill_px = result.get('fill_price', 0)
                            if _atm_fill_px > 0:
                                session[endangered_side].setdefault(
                                    'trigger_snapshot', {}
                                )[strike_key(new_strike)] = _atm_fill_px
                                log.info(
                                    f"[{sid}] ATM Shield trigger snapshot force-set: "
                                    f"{endangered_side.upper()}[{strike_key(new_strike)}] = "
                                    f"${_atm_fill_px:.2f} (fill price, prevents next-beat blindness)"
                                )
                        except Exception as _snap_e:
                            log.error(
                                f"[{sid}] ATM Shield: failed to force trigger snapshot: {_snap_e}"
                            )
                        # Shield successfully repositioned — clear any pending wind-down
                        # that may have fired in the same beat (step 4 runs before step 5.5)
                        if session.get('_atm_wind_down_triggered'):
                            session.pop('_atm_wind_down_triggered', None)
                            params['wind_down_enabled'] = session.pop('_atm_prev_wind_down_enabled', False)
                            log.info(f"[{sid}] ATM Shield repositioned — wind-down deactivated")
                        log.info(
                            f"[{sid}] ATM Shield re-sold {total_lots_agr} lots "
                            f"({base_lots} shifted + {recovery_lots} recovery) "
                            f"on {endangered_side.upper()} @ {new_strike:.0f} "
                            f"(active_strike updated {endangered_strike:.0f} → {new_strike:.0f})"
                        )
                        # Save immediately so a watchdog restart cannot orphan this
                        # position.  ATM Shield places multiple orders; each fill must
                        # be persisted before the next order so that if the session is
                        # killed mid-execution the new position is not lost.
                        monitor._save_my_session()
                except Exception as e:
                    log.error(
                        f"[{sid}] ATM Shield re-sell error: {e}", exc_info=True,
                    )

    # Safe side re-sell — loss recovery only, normal regime rules apply
    safe_premium = pe_now if safe_side == 'pe' else ce_now
    safe_active_strike = session.get(safe_side, {}).get('active_strike', 0)

    if (safe_active_strike > 0 and safe_premium > 0
            and sells_possible and not margin_blocks_sells):
        # Check normal regime blocks (NOT exempt for safe side)
        from .mmm_regime import MMMRegimeEngine
        regime_engine = MMMRegimeEngine()
        blocked, _ = regime_engine.should_block_sell(session, safe_side)

        if not blocked:
            loss_share_safe = max(total_realized_loss, 0) * (1.0 - loss_split_agr)
            if loss_share_safe > 0 and safe_premium > 0:
                lots_safe, _, _ = engine.calculate_lots_to_sell(
                    session, safe_side, loss_share_safe, safe_premium,
                )
                # Cap at remaining position capacity on the safe side.
                # The old cap (min(lots_safe, total_closed_lots)) was wrong: when the
                # safe-side premium is much lower than the close premium, recovering 70%
                # of the loss requires far more lots than were closed.  The hard cap
                # made the 70% recovery target impossible to achieve.
                # Use the same position-cap pattern as the endangered-side re-sell.
                _max_lots_safe = params.get('max_lots_per_side', 100)
                _current_safe = session.get(safe_side, {}).get('active_lots', 0)
                _cap_safe = max(_max_lots_safe - _current_safe, 0)
                lots_safe = min(lots_safe, _cap_safe)
                if lots_safe > 0:
                    try:
                        result = await engine.execute_adjustment(
                            session, safe_side, safe_active_strike, lots_safe,
                            ce_now, pe_now, adj_type='atm_shield',
                        )
                        if result.get('success'):
                            lots_sold_safe = lots_safe
                            log.info(
                                f"[{sid}] ATM Shield safe-side re-sold "
                                f"{lots_safe} lots on {safe_side.upper()} "
                                f"@ {safe_active_strike:.0f}"
                            )
                            # Save immediately — same watchdog-race guard as endangered side
                            monitor._save_my_session()
                    except Exception as e:
                        log.error(
                            f"[{sid}] ATM Shield safe-side error: {e}",
                            exc_info=True,
                        )

    # ── Step 4: SYMPATHETIC REBALANCE — shift safe side if premium decayed
    shift_threshold = params.get('shift_threshold', 50.0)
    safe_current_lots = session.get(safe_side, {}).get('active_lots', 0)
    if (safe_current_lots > 0
            and safe_premium < shift_threshold
            and not session.get(f'_proactive_shifted_{safe_side}')):
        log.info(
            f"[{sid}] ATM Shield: sympathetic rebalance {safe_side.upper()} "
            f"(premium ${safe_premium:.2f} < threshold ${shift_threshold:.0f})"
        )
        try:
            await monitor._process_strike_shift(safe_side, 0.0, ce_now, pe_now)
            session[f'_proactive_shifted_{safe_side}'] = True
            sympathetic_shifted = True
        except Exception as e:
            log.error(
                f"[{sid}] ATM Shield sympathetic shift error: {e}",
                exc_info=True,
            )
            sympathetic_shifted = False
    else:
        sympathetic_shifted = False

    # ── Step 5: UPDATE STATE ─────────────────────────────────────────
    max_fires = params.get('atm_shield_max_per_session', 3)
    new_count = shield_count + 1
    session[f'_atm_shield_count_{endangered_side}'] = new_count
    session[f'_atm_shield_last_fire_{endangered_side}'] = (
        datetime.now(timezone.utc).isoformat()
    )
    session['_atm_shield_fired'] = True

    if new_count >= max_fires:
        session[f'_atm_shield_exhausted_{endangered_side}'] = True
        log.warning(
            f"[{sid}] ATM Shield EXHAUSTED for {endangered_side.upper()} "
            f"({new_count}/{max_fires})"
        )

    # ── Step 6: ACTIVITY LOG + WEBSOCKET ─────────────────────────────
    try:
        from .mmm_activity import log_activity
        log_activity(
            'atm_shield',
            f'🛡️ ATM Shield #{new_count}: {endangered_side.upper()} '
            f'@ {endangered_strike:.0f} → {new_strike or "close-only"} '
            f'(closed {total_closed_lots}L, re-sold {lots_sold_endangered}L '
            f'+ {lots_sold_safe}L safe, loss ${total_realized_loss:.4f})',
            sid, 'warning',
            {
                'side': endangered_side,
                'endangered_strike': endangered_strike,
                'new_strike': new_strike,
                'spot': spot,
                'distance_pct': round(distance_pct, 3),
                'fire_number': new_count,
                'fires_remaining': max_fires - new_count,
                'total_closed_lots': total_closed_lots,
                'lots_sold_endangered': lots_sold_endangered,
                'lots_sold_safe': lots_sold_safe,
                'realized_loss': round(total_realized_loss, 6),
                'effective_target_otm_pct': round(eff_target_otm, 2),
                'time_mult': round(time_mult, 2),
                'sympathetic_shifted': sympathetic_shifted,
            },
        )
    except Exception as e:
        log.error(f"[{sid}] ATM Shield activity log error: {e}")

    try:
        from .mmm_websocket import emit_atm_shield
        emit_atm_shield(sid, {
            'side': endangered_side,
            'endangered_strike': endangered_strike,
            'spot_price': spot,
            'distance_pct': round(distance_pct, 3),
            'fire_number': new_count,
            'fires_remaining': max_fires - new_count,
            'new_strike': new_strike,
            'effective_target_otm_pct': round(eff_target_otm, 2),
            'realized_loss': round(total_realized_loss, 6),
            'lots_closed': total_closed_lots,
            'lots_sold_endangered': lots_sold_endangered,
            'lots_sold_safe': lots_sold_safe,
            'sympathetic_shifted': sympathetic_shifted,
        })
    except Exception as e:
        log.error(f"[{sid}] ATM Shield websocket emit error: {e}")

    return True
