"""
MMM Audit Remark Engine

Converts system events into clean, trader-readable strings for the
position_audit_log and session_event_log tables.

Rules:
- Every function must return a non-empty string. Never raises.
- Language is trader-facing, not developer-facing.
- No external imports, no DB, no I/O.

Created: 2026-03-18
"""

LOT_SIZE_BTC = 0.001


def build_trade_remark(
    action: str,
    event_type: str,
    side: str = '',
    strike: int = 0,
    lots: int = 0,
    premium: float = 0.0,
    mechanism: str = '',
    adj_type: str = '',
    aggressor: str = '',
    loss_covered: float = 0.0,
    threshold: float = 0.0,
    entry_premium: float = 0.0,
    realized_pnl: float = 0.0,
    new_strike: int = 0,
    profit_pct: float = 0.0,
    age_mins: int = 0,
    wind_down_pct: float = 0.0,
    proximity_pct: float = 0.0,
    is_partial: bool = False,
    **_extra,
) -> str:
    """
    Build a human-readable remark for a position_audit_log row.

    Args:
        action      : 'BUY' or 'SELL'
        event_type  : ENTRY | ADJUSTMENT | REVERSAL | CLOSE | WIND_DOWN |
                      EXIT | RECYCLE_BUY | RECYCLE_SELL | PERP_HEDGE
        side        : 'ce' | 'pe' | 'perp'
        strike      : strike price (int)
        lots        : filled lots
        premium     : fill price (USD)
        mechanism   : close_at_5 | harvest | wind_down | recycler |
                      atm_shield | emergency | operator | import | adopt |
                      fresh_entry
        adj_type    : standard | reversal | first_reversal | recycle_phase_b
        aggressor   : 'ce' or 'pe' — side that triggered this adjustment
        loss_covered: loss this adjustment was sized to cover (USD)
        threshold   : close-at-5 threshold used
        entry_premium: original SELL premium of position being closed
        realized_pnl: realized P&L of this close (USD)
        new_strike  : for recycle Phase B — the new strike sold at
        profit_pct  : for harvest — profit % at close
        age_mins    : for harvest — age of position in minutes
        wind_down_pct: for wind-down — close threshold as % of entry
        proximity_pct: for ATM shield — how close spot was to strike
        is_partial  : True if fill was partial

    Returns:
        Non-empty trader-readable string. Never raises.
    """
    try:
        side_up = side.upper() if side else ''
        partial_tag = ' [PARTIAL FILL]' if is_partial else ''
        gross = lots * premium * LOT_SIZE_BTC

        # ── SELL ──────────────────────────────────────────────────────────
        if action == 'SELL':

            if event_type == 'ENTRY':
                if mechanism == 'import':
                    return f'Mode B import — user-supplied fill price, no order placed'
                if mechanism == 'adopt':
                    return f'Mode C adopt — mapped from live exchange position'
                if mechanism in ('operator', 'adopt_inject'):
                    return f'Operator inject — manual lot placement @ strike {strike}'
                # fresh_entry (Mode A)
                return (
                    f'Initial entry — Short Strangle {side_up} leg | '
                    f'{lots} lots @ ${premium:.2f} | gross ${gross:.4f}{partial_tag}'
                )

            if event_type in ('ADJUSTMENT', 'REVERSAL'):
                agg_up = aggressor.upper() if aggressor else '?'
                other = 'PE' if side_up == 'CE' else 'CE'
                loss_str = f' | loss covered ${loss_covered:.4f}' if loss_covered > 0 else ''
                if event_type == 'REVERSAL':
                    detail = (
                        'adj P&L was negative'
                        if adj_type in ('reversal', 'first_reversal')
                        else 'direction flip'
                    )
                    return (
                        f'Reversal: {agg_up} aggressor → {side_up} hedge | '
                        f'{detail} | {lots} lots @ ${premium:.2f}{loss_str}{partial_tag}'
                    )
                return (
                    f'{agg_up} aggressor → {side_up} hedge | '
                    f'{lots} lots @ ${premium:.2f}{loss_str} | '
                    f'gross ${gross:.4f}{partial_tag}'
                )

            if event_type == 'RECYCLE_SELL':
                ns = f' @ new strike {new_strike}' if new_strike else ''
                return (
                    f'M2 Recycle Phase B — sell {lots} {side_up}{ns} '
                    f'@ ${premium:.2f} | gross ${gross:.4f}{partial_tag}'
                )

            if event_type == 'PERP_HEDGE':
                return (
                    f'Perp delta hedge SELL {lots} BTCUSD @ ${premium:.2f} | '
                    f'delta rebalance'
                )

        # ── BUY ───────────────────────────────────────────────────────────
        if action == 'BUY':
            pnl_str = f' | P&L ${realized_pnl:+.4f}' if realized_pnl != 0 else ''
            entry_str = f' (entry ${entry_premium:.2f})' if entry_premium > 0 else ''

            if event_type == 'CLOSE':
                if mechanism == 'harvest':
                    age_str = f' age {age_mins}min' if age_mins > 0 else ''
                    pct_str = f'{profit_pct:.0f}% profit' if profit_pct > 0 else 'profit threshold'
                    return (
                        f'M1 Harvest — {pct_str} locked{age_str}'
                        f'{entry_str} | close ${premium:.2f}{pnl_str}{partial_tag}'
                    )
                thresh_str = f' ≤ ${threshold:.0f}' if threshold > 0 else ''
                return (
                    f'Close-at-5 threshold hit — premium ${premium:.2f}{thresh_str}'
                    f'{entry_str}{pnl_str}{partial_tag}'
                )

            if event_type == 'WIND_DOWN':
                pct_str = f' ({wind_down_pct:.0f}% of entry)' if wind_down_pct > 0 else ''
                return (
                    f'Wind-down LIFO buyback{pct_str}'
                    f'{entry_str} | close ${premium:.2f}{pnl_str}{partial_tag}'
                )

            if event_type == 'RECYCLE_BUY':
                return (
                    f'M2 Recycle Phase A — buy back cheap frozen lot'
                    f'{entry_str} | close ${premium:.2f}{pnl_str}{partial_tag}'
                )

            if event_type == 'EXIT':
                if mechanism == 'atm_shield':
                    prox = f'{proximity_pct:.1f}%' if proximity_pct > 0 else 'ATM proximity'
                    return (
                        f'ATM Shield close — spot within {prox} of strike {strike}'
                        f'{pnl_str}{partial_tag}'
                    )
                if mechanism == 'operator':
                    return (
                        f'Operator close-strike — manual buyback @ ${premium:.2f}'
                        f'{pnl_str}{partial_tag}'
                    )
                if mechanism == 'emergency':
                    return f'Forced close — max-loss / emergency trigger{pnl_str}{partial_tag}'
                return f'Forced exit — {mechanism or "auto_close"}{pnl_str}{partial_tag}'

            if event_type == 'PERP_HEDGE':
                return (
                    f'Perp delta hedge BUY {lots} BTCUSD @ ${premium:.2f}'
                    f'{pnl_str}'
                )

        # Fallback
        return f'{action} {side_up} @ {strike} | {event_type} | {mechanism}'

    except Exception:
        return f'{action} {side} | {event_type}'


def build_event_remark(event_category: str, event_type: str, **ctx) -> str:
    """
    Build a human-readable remark for a session_event_log row.

    Args:
        event_category: SESSION_LIFECYCLE | SAFETY | REGIME | MARGIN |
                        PARAM_CHANGE | STRIKE_SHIFT | CIRCUIT_BREAKER |
                        RECONCILIATION | BOTH_SIDES_UP | WHIPSAW |
                        ORDER_FAILURE | ATM_SHIELD
        event_type    : specific event name within the category
        **ctx         : context fields used to build the message

    Returns:
        Non-empty trader-readable string. Never raises.
    """
    try:
        if event_category == 'SESSION_LIFECYCLE':
            msgs = {
                'created':   'Session created',
                'started':   'Session RUNNING — heartbeat monitor active',
                'paused':    f"Session paused — {ctx.get('reason', '')}",
                'resumed':   'Session resumed',
                'stopped':   f"Session stopped — {ctx.get('reason', '')}",
                'completed': 'Session complete — all positions closed',
                'error':     f"Session error — {ctx.get('reason', '')}",
            }
            return msgs.get(event_type, f'Session {event_type}')

        if event_category == 'SAFETY':
            msgs = {
                'position_cap_hit': (
                    f"Position cap reached — {ctx.get('side','?').upper()}: "
                    f"{ctx.get('active_lots',0)} active lots"
                ),
                'max_loss_breach': (
                    f"Max-loss breached — P&L ${ctx.get('pnl',0):.2f} "
                    f"< limit ${ctx.get('limit',0):.2f}"
                ),
                'asymmetry_alert': (
                    f"Lot asymmetry {ctx.get('ratio',0):.1f}:1 "
                    f"({ctx.get('heavy_side','?').upper()} heavy)"
                ),
                'pnl_guardrail': (
                    f"P&L guardrail {ctx.get('level','?').upper()} — "
                    f"${ctx.get('pnl',0):.2f}"
                ),
            }
            return msgs.get(event_type, f'Safety: {event_type}')

        if event_category == 'REGIME':
            old = ctx.get('old_state', '?')
            new = ctx.get('new_state', '?')
            reason = ctx.get('reason', '')
            reason_str = f' ({reason})' if reason else ''
            return f'Regime: {old} → {new}{reason_str}'

        if event_category == 'MARGIN':
            old = ctx.get('old_tier', '?')
            new = ctx.get('new_tier', '?')
            util = ctx.get('utilization_pct', 0)
            return f'Margin tier: {old} → {new} (utilization {util:.1f}%)'

        if event_category == 'PARAM_CHANGE':
            param = ctx.get('param', '?')
            old = ctx.get('old_value', '?')
            new = ctx.get('new_value', '?')
            return f'Param change: {param} {old!r} → {new!r}'

        if event_category == 'STRIKE_SHIFT':
            side = ctx.get('side', '?').upper()
            old_s = ctx.get('old_strike', 0)
            new_s = ctx.get('new_strike', 0)
            old_p = ctx.get('old_premium', 0)
            return (
                f'Strike shift {side}: {old_s} → {new_s} '
                f'(old premium ${old_p:.2f} below threshold)'
            )

        if event_category == 'CIRCUIT_BREAKER':
            old = ctx.get('old_state', '?')
            new = ctx.get('new_state', '?')
            return f'Circuit breaker: {old} → {new}'

        if event_category == 'RECONCILIATION':
            if ctx.get('mismatch'):
                return f"Reconciliation MISMATCH: {ctx.get('detail', '')}"
            return 'Reconciliation OK — audit sum matches session state'

        if event_category == 'BOTH_SIDES_UP':
            if event_type == 'triggered':
                ce_ex = ctx.get('ce_excess', 0)
                pe_ex = ctx.get('pe_excess', 0)
                return (
                    f'Both-sides-up: CE +{ce_ex:.2f} / PE +{pe_ex:.2f} — '
                    f'session paused'
                )
            decision = ctx.get('decision', '?').upper()
            return f'Both-sides-up resolved: user chose {decision}'

        if event_category == 'WHIPSAW':
            old = ctx.get('old_level', '?')
            new = ctx.get('new_level', '?')
            score = ctx.get('score', 0)
            return f'Whipsaw guard: {old} → {new} (score {score})'

        if event_category == 'ORDER_FAILURE':
            side = ctx.get('side', '?').upper()
            action = ctx.get('action', '?')
            strike = ctx.get('strike', 0)
            err = ctx.get('error', 'unknown')
            return f'Order failed: {side} {action} @ {strike} — {err}'

        if event_category == 'ATM_SHIELD':
            if event_type == 'activated':
                prox = ctx.get('proximity_pct', 0)
                side = ctx.get('side', '?').upper()
                strike = ctx.get('strike', 0)
                return (
                    f'ATM Shield activated — spot {prox:.2f}% from '
                    f'{side} strike {strike}'
                )
            if event_type == 'reestablished':
                return f"ATM Shield re-established at safer strike {ctx.get('new_strike', 0)}"
            return f'ATM Shield: {event_type}'

        return f'{event_category}: {event_type}'

    except Exception:
        return f'{event_category}: {event_type}'
