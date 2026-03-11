"""
MMM Favorable Scale-Up (FSU)

When both CE and PE premiums are decaying significantly (OUTCOME_NONE),
opens new positions at fresh OTM strikes to capture additional theta.

Once created, positions become standard MMM positions — fully tracked
by the unified ledger, included in all loss calculations, adjustments,
close-at-5, harvesting, and recycling.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

log = logging.getLogger(__name__)


def check_scale_eligibility(
    session: Dict,
    ce_now: float,
    pe_now: float,
) -> Tuple[bool, str]:
    """
    Check whether the session is eligible for a scale-up event.

    Returns:
        (eligible, reason) — reason explains why eligible or why not.
    """
    params = session.get('params', {})

    # 1. Master switch
    if not params.get('scale_enabled', False):
        return False, 'scale_enabled=False'

    # 2. Session must be RUNNING
    if session.get('strategy_status') != 'RUNNING':
        return False, f"status={session.get('strategy_status')}"

    # 3. Max events cap
    scale_count = session.get('scale_count', 0)
    max_events = params.get('scale_max_events', 3)
    if scale_count >= max_events:
        return False, f'max_events reached ({scale_count}/{max_events})'

    # 4. Cooldown check
    last_scale_at = session.get('_last_scale_at')
    if last_scale_at:
        try:
            last_dt = datetime.fromisoformat(last_scale_at)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            cooldown = params.get('scale_cooldown_mins', 30) * 60
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                return False, f'cooldown ({remaining}s remaining)'
        except (ValueError, TypeError):
            pass

    # 5. Session P&L must be positive
    realized = session.get('realized_pnl', 0)
    unrealized = session.get('unrealized_pnl', 0)
    total_pnl = realized + unrealized
    if total_pnl <= 0:
        return False, f'session P&L negative (${total_pnl:.2f})'

    # 6. Margin tier must be GREEN
    margin_block = session.get('_margin_block_sells', False)
    margin_wind_down = session.get('_margin_wind_down', False)
    if margin_block or margin_wind_down:
        return False, 'margin tier not GREEN'

    # 7. Regime must not block sells
    from .mmm_regime import ACTION_BLOCK_ALL_SELLS, ACTION_FORCE_REDUCE
    regime_action = session.get('_regime_action', 'normal')
    if regime_action in (ACTION_BLOCK_ALL_SELLS, ACTION_FORCE_REDUCE):
        return False, f'regime blocks sells ({regime_action})'

    # 8. P&L must not be incomplete (stale data guard)
    if session.get('_pnl_calculation_incomplete', False):
        return False, 'P&L calculation incomplete'

    # 9. Near-expiry guard — don't scale into positions that will immediately
    #    enter wind-down. Block if minutes_to_expiry < scale_cooldown_mins * 1.5
    #    or less than 60 minutes (hard floor).
    expiry_str = params.get('expiry', '')
    if expiry_str:
        try:
            from .mmm_initializer import expiry_to_utc_datetime
            expiry_iso = expiry_to_utc_datetime(expiry_str, params)
            expiry_dt = datetime.fromisoformat(expiry_iso)
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            minutes_remaining = (expiry_dt - datetime.now(timezone.utc)).total_seconds() / 60.0
            cooldown_mins = params.get('scale_cooldown_mins', 30)
            min_minutes = max(cooldown_mins * 1.5, 60)
            if minutes_remaining < min_minutes:
                return False, f'too close to expiry ({minutes_remaining:.0f}m < {min_minutes:.0f}m floor)'
        except Exception:
            pass  # If parsing fails, let other guards handle it

    # 10. Both premiums must have decayed by scale_min_decay_pct from snapshot
    min_decay = params.get('scale_min_decay_pct', 35.0)

    ce_state = session.get('ce', {})
    pe_state = session.get('pe', {})
    ce_active_strike = ce_state.get('active_strike', 0)
    pe_active_strike = pe_state.get('active_strike', 0)

    from .mmm_constants import strike_key
    ce_snap = ce_state.get('trigger_snapshot', {}).get(strike_key(ce_active_strike), 0)
    pe_snap = pe_state.get('trigger_snapshot', {}).get(strike_key(pe_active_strike), 0)

    if ce_snap <= 0 or pe_snap <= 0:
        return False, 'trigger snapshot zero/missing'

    ce_decay_pct = ((ce_snap - ce_now) / ce_snap) * 100.0
    pe_decay_pct = ((pe_snap - pe_now) / pe_snap) * 100.0

    if ce_decay_pct < min_decay:
        return False, f'CE decay {ce_decay_pct:.1f}% < {min_decay}%'
    if pe_decay_pct < min_decay:
        return False, f'PE decay {pe_decay_pct:.1f}% < {min_decay}%'

    # 11. Total exposure ceiling check (Split Ledger)
    initial_lots = params.get('initial_lots', 5)
    scale_lots = max(1, int(initial_lots * params.get('scale_lots_pct', 50.0) / 100.0))
    max_lots = params.get('max_lots_per_side', 100)
    max_total = params.get('max_total_exposure', 0) or (max_lots * 2)
    ce_total = ce_state.get('total_lots', 0)
    pe_total = pe_state.get('total_lots', 0)
    if ce_total + scale_lots > max_total:
        return False, f'CE total exposure ceiling ({ce_total}+{scale_lots} > {max_total})'
    if pe_total + scale_lots > max_total:
        return False, f'PE total exposure ceiling ({pe_total}+{scale_lots} > {max_total})'

    return True, (
        f'eligible: CE decay {ce_decay_pct:.1f}%, '
        f'PE decay {pe_decay_pct:.1f}%, '
        f'lots={scale_lots}, P&L=${total_pnl:.2f}'
    )


def find_scale_strikes(
    initializer,
    session: Dict,
    spot_price: float,
) -> Optional[Dict]:
    """
    Find fresh OTM strikes for scale-up on both CE and PE sides.

    Returns:
        {
            'ce': {'strike': float, 'premium': float, 'symbol': str},
            'pe': {'strike': float, 'premium': float, 'symbol': str},
            'lots': int,
        }
        or None if no suitable strikes found.
    """
    params = session.get('params', {})
    expiry = params.get('expiry', '')
    target_premium = params.get('scale_target_premium', 100.0)
    min_premium = params.get('scale_min_premium', 30.0)
    initial_lots = params.get('initial_lots', 5)
    scale_lots = max(1, int(initial_lots * params.get('scale_lots_pct', 50.0) / 100.0))

    try:
        chain_data = initializer.get_full_chain(expiry)
        if not chain_data or not chain_data.get('chain'):
            log.warning("Scale-up: No chain data available")
            return None

        chain = chain_data['chain']

        # Collect existing strikes to avoid duplicates
        ce_existing = set()
        pe_existing = set()
        for pos in session.get('ce', {}).get('positions', []):
            if pos.get('lots', 0) > 0:
                ce_existing.add(int(round(pos.get('strike', 0))))
        for pos in session.get('pe', {}).get('positions', []):
            if pos.get('lots', 0) > 0:
                pe_existing.add(int(round(pos.get('strike', 0))))

        # Also exclude the current active strikes
        ce_active = int(round(session.get('ce', {}).get('active_strike', 0)))
        pe_active = int(round(session.get('pe', {}).get('active_strike', 0)))
        ce_existing.add(ce_active)
        pe_existing.add(pe_active)

        ce_candidates = []
        pe_candidates = []

        for entry in chain:
            strike = entry.get('strike', 0)
            if strike <= 0:
                continue

            # CE candidates: CALL, OTM (strike > spot)
            call_data = entry.get('call', {})
            if call_data and strike > spot_price:
                bid = call_data.get('best_bid', 0) or 0
                mark = call_data.get('mark_price', 0) or 0
                premium = bid if bid > 0 else mark
                symbol = call_data.get('symbol', '')
                strike_int = int(round(strike))

                if premium > 0 and strike_int not in ce_existing:
                    if premium < min_premium:
                        continue
                    ce_candidates.append({
                        'strike': strike,
                        'premium': premium,
                        'symbol': symbol,
                        'distance': abs(premium - target_premium),
                    })

            # PE candidates: PUT, OTM (strike < spot)
            put_data = entry.get('put', {})
            if put_data and strike < spot_price:
                bid = put_data.get('best_bid', 0) or 0
                mark = put_data.get('mark_price', 0) or 0
                premium = bid if bid > 0 else mark
                symbol = put_data.get('symbol', '')
                strike_int = int(round(strike))

                if premium > 0 and strike_int not in pe_existing:
                    if premium < min_premium:
                        continue
                    pe_candidates.append({
                        'strike': strike,
                        'premium': premium,
                        'symbol': symbol,
                        'distance': abs(premium - target_premium),
                    })

        # Sort by proximity to target premium (closest first)
        ce_candidates.sort(key=lambda c: c['distance'])
        pe_candidates.sort(key=lambda c: c['distance'])

        if not ce_candidates or not pe_candidates:
            log.info(
                f"Scale-up: No strikes found "
                f"(CE candidates={len(ce_candidates)}, PE candidates={len(pe_candidates)})"
            )
            return None

        best_ce = ce_candidates[0]
        best_pe = pe_candidates[0]

        # Reject if best premium is too far from target (> 3x or < 0.2x)
        for label, best in [('CE', best_ce), ('PE', best_pe)]:
            ratio = best['premium'] / target_premium if target_premium > 0 else 0
            if ratio > 3.0 or ratio < 0.2:
                log.info(
                    f"Scale-up: {label} best premium ${best['premium']:.2f} "
                    f"too far from target ${target_premium:.2f} (ratio={ratio:.2f})"
                )
                return None

        return {
            'ce': {'strike': best_ce['strike'], 'premium': best_ce['premium'], 'symbol': best_ce['symbol']},
            'pe': {'strike': best_pe['strike'], 'premium': best_pe['premium'], 'symbol': best_pe['symbol']},
            'lots': scale_lots,
        }

    except Exception as e:
        log.exception(f"Scale-up strike scan failed: {e}")
        return None


def record_scale_event(session: Dict, ce_info: Dict, pe_info: Dict, lots: int):
    """Record a scale-up event in session state."""
    session['scale_count'] = session.get('scale_count', 0) + 1
    session['_last_scale_at'] = datetime.now(timezone.utc).isoformat()
    session.setdefault('scale_history', []).append({
        'event_number': session['scale_count'],
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'ce_strike': ce_info['strike'],
        'ce_premium': ce_info['premium'],
        'pe_strike': pe_info['strike'],
        'pe_premium': pe_info['premium'],
        'lots_per_side': lots,
    })
    # Cap history size
    if len(session['scale_history']) > 50:
        session['scale_history'] = session['scale_history'][-50:]
