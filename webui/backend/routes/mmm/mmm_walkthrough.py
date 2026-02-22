"""
MMM Walkthrough Generator — Money Mind & Method

Generates a live algorithm walkthrough from session state,
mirroring the format of MONEY_POWER_CALCULATION_LOGIC.md Section 16.

Each heartbeat appends a new entry showing the exact calculation steps
the algorithm performed. This keeps users aware of every decision.

All timestamps are in IST (UTC+5:30).

Created: February 16, 2026
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

from .mmm_constants import LOT_SIZE_BTC, strike_key

log = logging.getLogger('mmm_walkthrough')

# IST timezone offset: UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))


def _to_ist(iso_str: str) -> str:
    """Convert an ISO timestamp string to IST formatted string."""
    if not iso_str:
        return '--'
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ist_dt = dt.astimezone(IST)
        return ist_dt.strftime('%d-%b-%Y %I:%M:%S %p IST')
    except Exception:
        return iso_str


def _to_ist_short(iso_str: str) -> str:
    """Convert to short IST time (HH:MM:SS AM/PM IST)."""
    if not iso_str:
        return '--'
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ist_dt = dt.astimezone(IST)
        return ist_dt.strftime('%I:%M:%S %p IST')
    except Exception:
        return iso_str


def generate_entry_walkthrough(session: Dict) -> Dict[str, Any]:
    """
    Generate the T=0 ENTRY block from session state.

    Reads:
      - session.ce.original_strike, original_premium, original_lots
      - session.pe.original_strike, original_premium, original_lots
      - session.entry_time, session.created_at
      - session.initial_total_premium, session.actual_total_premium
    """
    ce = session.get('ce', {})
    pe = session.get('pe', {})
    params = session.get('params', {})

    ce_strike = ce.get('original_strike', 0)
    pe_strike = pe.get('original_strike', 0)
    ce_prem = ce.get('entry_fill_price', ce.get('original_premium', 0))
    pe_prem = pe.get('entry_fill_price', pe.get('original_premium', 0))
    lots = ce.get('original_lots', 0)

    entry_time = session.get('entry_time') or session.get('execution_timestamp') or session.get('created_at', '')
    total_prem_btc = session.get('actual_total_premium') or session.get('initial_total_premium', 0)

    # BTC value: premium × lots × LOT_SIZE_BTC per side
    ce_btc = ce_prem * lots * LOT_SIZE_BTC
    pe_btc = pe_prem * lots * LOT_SIZE_BTC

    entry = {
        'heartbeat': 0,
        'timestamp': entry_time,
        'timestamp_ist': _to_ist(entry_time),
        'label': 'ENTRY',
        'type': 'entry',
        'summary': f'Sell {lots} CE @ {ce_strike:,.0f} (${ce_prem:.2f}) + '
                   f'Sell {lots} PE @ {pe_strike:,.0f} (${pe_prem:.2f})',
        'calculation': '',
        'details': [
            f'Sell {lots} CE @ strike {ce_strike:,.0f}, premium ${ce_prem:.2f}',
            f'Sell {lots} PE @ strike {pe_strike:,.0f}, premium ${pe_prem:.2f}',
            '',
            f'CE: active_strike={ce_strike:,.0f}, active_lots={lots}, '
            f'trigger_snapshot={{{ce_strike:,.0f}: {ce_prem:.2f}}}',
            f'PE: active_strike={pe_strike:,.0f}, active_lots={lots}, '
            f'trigger_snapshot={{{pe_strike:,.0f}: {pe_prem:.2f}}}',
            f'last_aggressor = "NONE"',
            f'Total premium = {total_prem_btc:.4f} BTC '
            f'(${ce_prem:.2f}×{lots}×{LOT_SIZE_BTC} + ${pe_prem:.2f}×{lots}×{LOT_SIZE_BTC})',
        ],
        'state': {
            'ce_active_strike': ce_strike,
            'ce_active_lots': lots,
            'ce_trigger': {strike_key(ce_strike): ce_prem},
            'pe_active_strike': pe_strike,
            'pe_active_lots': lots,
            'pe_trigger': {strike_key(pe_strike): pe_prem},
            'last_aggressor': 'NONE',
            'adjustment_count': 0,
            'total_premium_btc': round(total_prem_btc, 6),
        },
    }

    return entry


def generate_heartbeat_walkthrough(
    session: Dict,
    heartbeat_num: int,
    ce_now: float,
    pe_now: float,
    outcome: str,
    adjustment_info: Optional[Dict] = None,
    reversal_info: Optional[Dict] = None,
    shift_info: Optional[Dict] = None,
    close_at_5_info: Optional[List] = None,
    safety_events: Optional[List] = None,
    pnl_info: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Generate a heartbeat walkthrough entry showing the exact calculations.

    This function reads the CURRENT session state and the outcome to
    reconstruct what the algorithm computed. Future changes to the
    engine formulas will be reflected automatically because we
    use the same source data.

    Args:
        session: Full session dict (AFTER the heartbeat has been processed)
        heartbeat_num: The heartbeat counter
        ce_now: Current CE premium fetched this beat
        pe_now: Current PE premium fetched this beat
        outcome: 'none', 'ce_triggered', 'pe_triggered', 'both'
        adjustment_info: If adjustment was made, dict with details
        reversal_info: If reversal was detected, dict with details
        shift_info: If strike shift occurred, dict with details
        close_at_5_info: List of close-at-5 events this beat
        safety_events: List of safety events this beat
        pnl_info: Current PnL snapshot
    """
    ce = session.get('ce', {})
    pe = session.get('pe', {})
    params = session.get('params', {})
    now_iso = datetime.now(timezone.utc).isoformat()

    ce_strike = ce.get('active_strike', 0)
    pe_strike = pe.get('active_strike', 0)
    ce_trigger_val = ce.get('trigger_snapshot', {}).get(strike_key(ce_strike), 0)
    pe_trigger_val = pe.get('trigger_snapshot', {}).get(strike_key(pe_strike), 0)
    min_trigger = params.get('min_trigger_move', 3.0)
    shift_threshold = params.get('shift_threshold', 50.0)
    interval = params.get('adjustment_interval', 300)
    last_agg = session.get('last_aggressor', 'NONE')

    details = []
    calc_lines = []

    # --- Trigger check lines ---
    ce_excess = ce_now - ce_trigger_val
    pe_excess = pe_now - pe_trigger_val
    ce_base = max(ce_trigger_val, 1.0)
    pe_base = max(pe_trigger_val, 1.0)
    ce_excess_pct = (ce_excess / ce_base) * 100
    pe_excess_pct = (pe_excess / pe_base) * 100
    ce_triggered = ce_excess_pct > min_trigger
    pe_triggered = pe_excess_pct > min_trigger

    calc_lines.append(
        f'CE(${ce_now:.2f}) vs trigger(${ce_trigger_val:.2f}): '
        f'excess={ce_excess:+.2f} ({ce_excess_pct:+.1f}%) vs {min_trigger}% → {"YES ✓" if ce_triggered else "NO"}'
    )
    calc_lines.append(
        f'PE(${pe_now:.2f}) vs trigger(${pe_trigger_val:.2f}): '
        f'excess={pe_excess:+.2f} ({pe_excess_pct:+.1f}%) vs {min_trigger}% → {"YES ✓" if pe_triggered else "NO"}'
    )

    # --- Outcome determination ---
    hb_type = 'none'
    summary_parts = [f'CE=${ce_now:.2f}, PE=${pe_now:.2f}']

    if outcome == 'none':
        details.append('Result: NONE — both sides within safe zone ✓')
        summary_parts.append('No triggers fired')

    elif outcome == 'both':
        hb_type = 'both_sides_up'
        details.append('Result: BOTH SIDES UP ⚠️ — CE and PE both exceeded triggers')
        details.append('Action: PAUSED — Waiting for user decision (§8)')
        summary_parts.append('BOTH SIDES UP — Paused')

    elif outcome in ('ce_triggered', 'pe_triggered'):
        aggressor = 'CE' if outcome == 'ce_triggered' else 'PE'
        hedge = 'PE' if aggressor == 'CE' else 'CE'
        agg_key = aggressor.lower()
        hedge_key = hedge.lower()

        details.append(f'Result: {aggressor}_TRIGGERED — {aggressor} is aggressor')

        # Reversal check
        if reversal_info:
            is_reversal = reversal_info.get('detected', reversal_info.get('is_reversal', False))
            adj_pnl = reversal_info.get('adj_pnl', 0)
            skipped = reversal_info.get('skipped', False)

            if is_reversal:
                from_side = reversal_info.get('prev_aggressor', reversal_info.get('from_side', last_agg))
                details.append(f'')
                details.append(f'Reversal? last_aggressor="{from_side}", now "{aggressor}" → YES, reversal!')
                details.append(f'')

                # Show the per-fill P&L computation
                agg_state = session.get(agg_key, {})
                fills = agg_state.get('adjustment_fills', [])
                frozen = agg_state.get('frozen_positions', [])

                if fills or frozen:
                    details.append(f'Compute {aggressor} adjustment P&L (all fills):')
                    for f in fills:
                        f_strike = f.get('strike', 0)
                        f_prem = f.get('premium', 0)
                        f_lots = f.get('lots', 0)
                        # We can't get the exact current premium at computation time
                        # from here, but we store the outcome
                        details.append(
                            f'  {aggressor} {f_lots}@${f_prem:.2f} at strike {f_strike:,.0f}'
                        )
                    for fr in frozen:
                        fr_strike = fr.get('strike', 0)
                        fr_prem = fr.get('entry_premium', 0)
                        fr_lots = fr.get('lots', 0)
                        details.append(
                            f'  {aggressor} {fr_lots}@${fr_prem:.2f} at strike {fr_strike:,.0f} (frozen)'
                        )

                    details.append(f'Total adjustment P&L = ${adj_pnl:.4f} BTC')

                if skipped:
                    hb_type = 'reversal_skip'
                    details.append(f'')
                    details.append(
                        f'adjustment_pnl ≥ 0 → adjustments still profitable → DO NOTHING ✓'
                    )
                    summary_parts.append(
                        f'Reversal {from_side}→{aggressor}: adj P&L ${adj_pnl:.4f} (profitable) — Skipped'
                    )
                else:
                    hb_type = 'first_reversal'
                    details.append(f'')
                    details.append(
                        f'adjustment_pnl < 0 → TRIGGERED. loss_to_cover = ${abs(adj_pnl):.4f} BTC'
                    )
            else:
                details.append(f'')
                details.append(f'Reversal? last_aggressor="{last_agg}" → NO (continuation or first-ever)')

        # Adjustment info
        if adjustment_info and not (reversal_info and reversal_info.get('skipped', False)):
            hb_type = adjustment_info.get('adj_type', adjustment_info.get('type', 'standard'))
            loss = adjustment_info.get('loss', 0)
            lots_sold = adjustment_info.get('lots', 0)
            fill_price = adjustment_info.get('fill_price', 0)
            adj_strike = adjustment_info.get('strike', 0)
            adj_premium_collected = adjustment_info.get(
                'premium_collected',
                fill_price * lots_sold * LOT_SIZE_BTC if fill_price and lots_sold else 0
            )

            details.append(f'')

            if not reversal_info or not reversal_info.get('is_reversal', False):
                # Standard loss formula
                agg_state = session.get(agg_key, {})
                # Note: trigger_val is the PRE-update value; after adjustment it changes
                details.append(
                    f'Standard Loss = (${ce_now:.2f} - trigger) × active_lots × {LOT_SIZE_BTC}'
                    if aggressor == 'CE' else
                    f'Standard Loss = (${pe_now:.2f} - trigger) × active_lots × {LOT_SIZE_BTC}'
                )
                details.append(f'Loss to cover = ${loss:.4f} BTC')

            # Shift check
            if shift_info:
                old_s = shift_info.get('old_strike', 0)
                new_s = shift_info.get('new_strike', 0)
                frozen_lots = shift_info.get('frozen_lots', 0)
                details.append(f'')
                details.append(
                    f'{hedge} at {old_s:,.0f} = ${pe_now:.2f} < shift_threshold(${shift_threshold:.0f}) → STRIKE SHIFT!'
                    if hedge == 'PE' else
                    f'{hedge} at {old_s:,.0f} = ${ce_now:.2f} < shift_threshold(${shift_threshold:.0f}) → STRIKE SHIFT!'
                )
                details.append(f'Shift: freeze {hedge} at {old_s:,.0f} ({frozen_lots} lots)')
                details.append(f'New active {hedge} strike = {new_s:,.0f}')
                hb_type = 'shift'
            else:
                hedge_prem = pe_now if hedge == 'PE' else ce_now
                hedge_strike_val = pe_strike if hedge == 'PE' else ce_strike
                details.append(
                    f'{hedge} at {hedge_strike_val:,.0f} = ${hedge_prem:.2f} ≥ '
                    f'shift_threshold(${shift_threshold:.0f}) → sell at active strike ✓'
                )

            # Lots calculation
            hedge_prem_used = fill_price or (pe_now if hedge == 'PE' else ce_now)
            if hedge_prem_used > 0 and loss > 0:
                buffer_pct = params.get('premium_buffer_pct', 0.05)
                raw = loss / (hedge_prem_used * LOT_SIZE_BTC) * (1 + buffer_pct)
                details.append(f'')
                details.append(
                    f'Lots = ⌈ ${loss:.4f} / (${hedge_prem_used:.2f} × {LOT_SIZE_BTC}) '
                    f'× (1 + {buffer_pct:.0%}) ⌉ = ⌈{raw:.2f}⌉ = {lots_sold}'
                )

            details.append(
                f'Execute: SELL {lots_sold} {hedge} @ {adj_strike:,.0f} at ${fill_price:.2f}'
            )
            details.append(
                f'Premium collected = {lots_sold} × ${fill_price:.2f} × {LOT_SIZE_BTC} '
                f'= {adj_premium_collected:.4f} BTC'
            )
            summary_parts.append(
                f'{aggressor} triggered → SELL {lots_sold} {hedge} @ {adj_strike:,.0f} (${fill_price:.2f})'
            )

    # --- Close-at-5 ---
    if close_at_5_info:
        details.append(f'')
        details.append(f'--- Close-at-5 (§11) ---')
        for c5 in close_at_5_info:
            c5_side = c5.get('side', '?')
            c5_strike = c5.get('strike', 0)
            c5_lots = c5.get('lots_closed', c5.get('lots', 0))
            c5_pnl = c5.get('realized_pnl', 0)
            c5_prem = c5.get('close_premium', 0)
            details.append(
                f'{c5_side} @ {c5_strike:,.0f} premium=${c5_prem:.2f} ≤ 5 → CLOSE'
            )
            details.append(
                f'Bought back {c5_lots} lots. Realized P&L = ${c5_pnl:.4f} BTC'
            )

    # --- Safety events ---
    if safety_events:
        details.append(f'')
        details.append(f'--- Safety Checks (§13-14) ---')
        for se in safety_events:
            details.append(f'{se.get("type", "?")}: {se.get("message", "")}')
    else:
        details.append(f'')
        details.append('Safety Checks: All clear ✓')

    # --- State after this heartbeat ---
    ce_active_lots = ce.get('active_lots', 0)
    pe_active_lots = pe.get('active_lots', 0)
    ce_total_lots = ce.get('total_lots', 0)
    pe_total_lots = pe.get('total_lots', 0)
    ce_adj_lots = ce.get('adjustment_total_lots', 0)
    pe_adj_lots = pe.get('adjustment_total_lots', 0)
    ce_frozen = ce.get('frozen_total_lots', 0)
    pe_frozen = pe.get('frozen_total_lots', 0)

    net_pnl = 0
    realized = 0
    unrealized = 0
    if pnl_info:
        net_pnl = pnl_info.get('net_pnl', 0)
        realized = pnl_info.get('realized', 0)
        unrealized = pnl_info.get('unrealized', 0)

    state_lines = [
        f'CE: active_strike={ce_strike:,.0f}, active_lots={ce_active_lots} '
        f'({ce.get("original_lots", 0)} orig + {ce_adj_lots} adj'
        f'{f" + {ce_frozen} frozen" if ce_frozen else ""})',
        f'    trigger_snapshot={{{ce_strike:,.0f}: {ce_trigger_val:.2f}}}',
        f'PE: active_strike={pe_strike:,.0f}, active_lots={pe_active_lots} '
        f'({pe.get("original_lots", 0)} orig + {pe_adj_lots} adj'
        f'{f" + {pe_frozen} frozen" if pe_frozen else ""})',
        f'    trigger_snapshot={{{pe_strike:,.0f}: {pe_trigger_val:.2f}}}',
        f'last_aggressor = "{session.get("last_aggressor", "NONE")}"',
        f'adjustment_count = {session.get("adjustment_count", 0)}',
        f'total_premium = {session.get("total_premium_collected", 0):.4f} BTC',
        f'P&L: Net=${net_pnl:.2f}, Realized=${realized:.2f}, Unrealized=${unrealized:.2f}',
    ]

    details.append(f'')
    details.append('--- State After This Heartbeat ---')
    details.extend(state_lines)

    return {
        'heartbeat': heartbeat_num,
        'timestamp': now_iso,
        'timestamp_ist': _to_ist(now_iso),
        'label': f'Heartbeat #{heartbeat_num}',
        'type': hb_type,
        'interval': interval,
        'summary': ' | '.join(summary_parts),
        'calculation': '\n'.join(calc_lines),
        'details': details,
        'premiums': {
            'ce': round(ce_now, 2),
            'pe': round(pe_now, 2),
            'ce_strike': ce_strike,
            'pe_strike': pe_strike,
        },
        'triggers': {
            'ce_trigger': round(ce_trigger_val, 2),
            'pe_trigger': round(pe_trigger_val, 2),
            'ce_excess': round(ce_excess, 2),
            'pe_excess': round(pe_excess, 2),
            'min_trigger_move': min_trigger,
        },
        'outcome': outcome,
        'state': {
            'ce_active_strike': ce_strike,
            'ce_active_lots': ce_active_lots,
            'ce_total_lots': ce_total_lots,
            'pe_active_strike': pe_strike,
            'pe_active_lots': pe_active_lots,
            'pe_total_lots': pe_total_lots,
            'last_aggressor': session.get('last_aggressor', 'NONE'),
            'adjustment_count': session.get('adjustment_count', 0),
            'total_premium_btc': round(session.get('total_premium_collected', 0), 6),
            'net_pnl': round(net_pnl, 2),
            'realized': round(realized, 2),
            'unrealized': round(unrealized, 2),
        },
    }


def build_full_walkthrough(session: Dict) -> List[Dict[str, Any]]:
    """
    Build the complete walkthrough from session state.

    Reconstructs the walkthrough from:
      - Entry data (session.ce/pe original fields)
      - adjustment_history (ordered list of all adjustments)
      - pnl_history (ordered list of P&L points)
      - reversal_history (reversal events)
      - The session's walkthrough_log if available

    If session has a stored walkthrough_log, returns that directly.
    Otherwise, reconstructs from adjustment_history for existing sessions.
    """
    entries = []

    # The live walkthrough_log is maintained by the monitor
    stored_log = session.get('_walkthrough_log', [])
    if stored_log:
        return stored_log

    # Fallback: reconstruct from session data for existing sessions
    # Entry
    entry = generate_entry_walkthrough(session)
    entries.append(entry)

    # Reconstruction from adjustment_history and pnl_history
    adj_history = session.get('adjustment_history', [])
    pnl_history = session.get('pnl_history', [])
    reversal_history = session.get('reversal_history', [])

    ce = session.get('ce', {})
    pe = session.get('pe', {})
    params = session.get('params', {})

    # Build a map of reversal timestamps for annotation
    reversal_map = {}
    for rev in reversal_history:
        ts = rev.get('timestamp', '')
        reversal_map[ts[:16]] = rev  # key by minute precision

    hb_counter = 0
    adj_idx = 0

    for pnl_point in pnl_history:
        hb_counter += 1
        ts = pnl_point.get('timestamp', '')
        ce_prem = pnl_point.get('ce_premium', 0)
        pe_prem = pnl_point.get('pe_premium', 0)
        net_pnl = pnl_point.get('total_pnl', 0)
        realized = pnl_point.get('realized', 0)
        unrealized = pnl_point.get('unrealized', net_pnl)

        # Check if an adjustment happened at approx this timestamp
        adj_info = None
        rev_info = None
        if adj_idx < len(adj_history):
            adj = adj_history[adj_idx]
            adj_ts = adj.get('timestamp', '')
            # Match within ~60 seconds
            if abs(_ts_diff(ts, adj_ts)) < 60:
                adj_info = {
                    'type': adj.get('type', 'standard'),
                    'lots': adj.get('lots_sold', 0),
                    'fill_price': adj.get('premium', 0),
                    'strike': adj.get('strike', 0),
                    'side': adj.get('side', ''),
                    'premium_collected': adj.get('premium_collected', 0),
                    'loss': 0,  # Not stored in history, computed at the time
                }

                # Check if this was during a reversal
                for rev in reversal_history:
                    rev_ts = rev.get('timestamp', '')
                    if abs(_ts_diff(ts, rev_ts)) < 60:
                        rev_info = {
                            'is_reversal': True,
                            'from_side': rev.get('from', ''),
                            'adj_pnl': 0,
                            'skipped': False,
                        }
                        break

                adj_idx += 1

        # Check for reversal skips (reversals without corresponding adjustments)
        if not adj_info:
            for rev in reversal_history:
                rev_ts = rev.get('timestamp', '')
                rev_adj_count = rev.get('adjustment_count_at', -1)
                if abs(_ts_diff(ts, rev_ts)) < 60:
                    # Check if this reversal has a matching adjustment
                    matched = False
                    for a in adj_history:
                        if abs(_ts_diff(a.get('timestamp', ''), rev_ts)) < 60:
                            matched = True
                            break
                    if not matched:
                        rev_info = {
                            'is_reversal': True,
                            'from_side': rev.get('from', ''),
                            'adj_pnl': 0,
                            'skipped': True,
                        }
                    break

        # Determine outcome
        outcome = 'none'
        if adj_info:
            aggressor = adj_info.get('side', '')  # This is the HEDGE side
            # The aggressor is the OTHER side
            if aggressor == 'PE':
                outcome = 'ce_triggered'
            elif aggressor == 'CE':
                outcome = 'pe_triggered'

        if rev_info and rev_info.get('skipped') and not adj_info:
            # Reversal skip with no adjustment
            from_side = rev_info.get('from_side', '')
            if from_side == 'PE':
                outcome = 'ce_triggered'
            elif from_side == 'CE':
                outcome = 'pe_triggered'

        hb_entry = {
            'heartbeat': hb_counter,
            'timestamp': ts,
            'timestamp_ist': _to_ist(ts),
            'label': f'Heartbeat #{hb_counter}',
            'type': adj_info.get('type', 'no_action') if adj_info else (
                'reversal_skip' if (rev_info and rev_info.get('skipped')) else 'no_action'
            ),
            'interval': params.get('adjustment_interval', 300),
            'summary': _build_reconstructed_summary(
                ce_prem, pe_prem, adj_info, rev_info, outcome
            ),
            'premiums': {
                'ce': round(ce_prem, 2),
                'pe': round(pe_prem, 2),
                'ce_strike': ce.get('active_strike', 0),
                'pe_strike': pe.get('active_strike', 0),
            },
            'outcome': outcome,
            'state': {
                'net_pnl': round(net_pnl, 2),
                'realized': round(realized, 2),
                'unrealized': round(unrealized, 2),
                'adjustment_count': session.get('adjustment_count', 0),
                'total_premium_btc': round(session.get('total_premium_collected', 0), 6),
            },
            'adjustment': adj_info,
            'reversal': rev_info,
        }

        entries.append(hb_entry)

    return entries


def _build_reconstructed_summary(ce_prem, pe_prem, adj_info, rev_info, outcome):
    """Build summary line for reconstructed heartbeat."""
    parts = [f'CE=${ce_prem:.2f}, PE=${pe_prem:.2f}']

    if outcome == 'none':
        parts.append('No triggers fired')
    elif adj_info:
        side = adj_info.get('side', '?')
        lots = adj_info.get('lots', 0)
        strike = adj_info.get('strike', 0)
        price = adj_info.get('fill_price', 0)
        agg = 'CE' if side == 'PE' else 'PE'
        type_label = adj_info.get('type', 'standard')
        parts.append(f'{agg} triggered → SELL {lots} {side} @ {strike:,.0f} (${price:.2f}) [{type_label}]')
    elif rev_info and rev_info.get('skipped'):
        parts.append(f'Reversal skipped (adj profitable)')

    return ' | '.join(parts)


def _ts_diff(ts1: str, ts2: str) -> float:
    """Get absolute difference in seconds between two ISO timestamps."""
    try:
        d1 = datetime.fromisoformat(ts1.replace('Z', '+00:00'))
        d2 = datetime.fromisoformat(ts2.replace('Z', '+00:00'))
        return abs((d1 - d2).total_seconds())
    except Exception:
        return 9999
