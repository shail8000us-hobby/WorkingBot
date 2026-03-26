"""
MMM Safety — Money Mind & Method

All 7 safety mechanisms (§13) and 7 strength improvements (§14).

Safety mechanisms protect against:
  1. Position cap per side
  2. Maximum adjustments
  3. Maximum loss hard stop
  4. Whipsaw detection (rapid alternating adjustments)
  5. Position asymmetry warning
  6. Near-expiry behavior (stop adjustments / auto-close)
  7. Margin check before selling

Strength improvements enhance the algorithm:
  1. Premium buffer (extra lots for slippage) — §14.1
  2. Minimum trigger move — §14.2
  3. Cooldown on reversal — §14.3
  4. Net P&L guardrail (warning/pause/hard-stop tiers) — §14.4
  5. Periodic P&L reconciliation — §14.5
  6. Trailing profit protection — §14.6
  7. Theta acceleration — §14.7

Maps to MONEY_POWER_CALCULATION_LOGIC.md §13-§14

Created: February 15, 2026
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta, timezone

from webui.backend.sealed import sealed

log = logging.getLogger('mmm_safety')


class MMMSafety:
    """
    Safety checks run every heartbeat BEFORE any adjustment.
    Returns a list of safety events (warnings, alerts, hard stops).
    """

    def run_all_checks(
        self,
        session: Dict,
        minutes_to_expiry: float = None,
    ) -> List[Dict[str, Any]]:
        """
        Run all safety checks in order.

        Returns:
            List of safety events, each:
            {type, level, message, action, details}

            level: 'info', 'warning', 'alert', 'critical'
            action: 'continue', 'warn', 'pause', 'stop'
        """
        events = []

        events.extend(self.check_position_cap(session))
        events.extend(self.check_total_exposure(session))   # Split Ledger
        events.extend(self.check_max_adjustments(session))
        events.extend(self.check_max_loss(session))
        events.extend(self.check_whipsaw(session))
        events.extend(self.check_asymmetry(session))

        if minutes_to_expiry is not None:
            # Use v2 for multi-DTE sessions
            params = session.get('params', {})
            total_dte_hours = params.get('total_dte_hours', 0)
            dte_cat = params.get('dte_category', '')
            if total_dte_hours > 36 and dte_cat != '0DTE':
                events.extend(
                    self.check_near_expiry_v2(session, minutes_to_expiry)
                )
            else:
                events.extend(
                    self.check_near_expiry(session, minutes_to_expiry)
                )

        events.extend(self.check_pnl_guardrail(session))
        events.extend(self.check_trailing_stop(session))
        events.extend(self.check_margin(session))
        events.extend(self.check_lot_velocity(session))
        events.extend(self.check_max_loss_sizing(session))

        return events

    # =========================================================================
    # §13.1: Position Cap
    # =========================================================================

    def check_position_cap(self, session: Dict) -> List[Dict]:
        """Check if any side is near or at position cap."""
        events = []
        params = session.get('params', {})
        max_lots = params.get('max_lots_per_side', 100)

        for side_key in ['ce', 'pe']:
            side_state = session.get(side_key, {})
            total = side_state.get('active_lots', 0)  # Split Ledger: cap on active lots only
            ratio = total / max_lots if max_lots > 0 else 0

            if total >= max_lots:
                events.append({
                    'type': 'position_cap',
                    'level': 'alert',
                    'message': (
                        f"{side_key.upper()} POSITION CAP REACHED: "
                        f"{total}/{max_lots} lots — ADJUSTMENTS BLOCKED"
                    ),
                    'action': 'stop_adjustments',
                    'details': {
                        'side': side_key,
                        'lots': total,
                        'max': max_lots,
                    },
                })
            elif ratio >= 0.8:
                events.append({
                    'type': 'position_cap',
                    'level': 'warning',
                    'message': (
                        f"{side_key.upper()} approaching cap: "
                        f"{total}/{max_lots} lots ({ratio:.0%})"
                    ),
                    'action': 'continue',
                    'details': {
                        'side': side_key,
                        'lots': total,
                        'max': max_lots,
                    },
                })

        return events

    # =========================================================================
    # §13.2: Max Adjustments
    # =========================================================================

    def check_max_adjustments(self, session: Dict) -> List[Dict]:
        """Check if max adjustment count reached.

        When the limit is hit: pause the session (visible PAUSED state) so
        the user can decide whether to raise max_adjustments via Settings.
        Close-at-5 continues every heartbeat while paused.

        Auto-resume: if the user increases max_adjustments via hot-reload and
        adjustment_count is now below the new limit, emits a 'resume' event so
        the session picks up adjustments again without manual intervention.
        """
        events = []
        params = session.get('params', {})
        max_adj = params.get('max_adjustments', 100)
        current = session.get('adjustment_count', 0)

        # Auto-resume: user increased max_adjustments via hot-reload.
        if session.get('_max_adj_paused') and current < max_adj:
            session.pop('_max_adj_paused', None)
            events.append({
                'type': 'max_adjustments_resume',
                'level': 'info',
                'message': (
                    f"Adjustments resumed: limit raised to {max_adj} "
                    f"(used {current}/{max_adj})"
                ),
                'action': 'resume',
                'details': {'count': current, 'max': max_adj},
            })
            return events  # Don't re-evaluate this heartbeat

        if current >= max_adj:
            session['_max_adj_paused'] = True
            events.append({
                'type': 'max_adjustments',
                'level': 'critical',
                'message': (
                    f"Max adjustments reached: {current}/{max_adj}. "
                    f"Pausing — increase limit in Settings to resume, "
                    f"or leave paused and positions will close at ≤5."
                ),
                'action': 'pause',
                'details': {'count': current, 'max': max_adj},
            })
        elif current >= max_adj * 0.9:
            events.append({
                'type': 'max_adjustments',
                'level': 'warning',
                'message': (
                    f"Approaching max adjustments: {current}/{max_adj}"
                ),
                'action': 'continue',
                'details': {'count': current, 'max': max_adj},
            })

        return events

    # =========================================================================
    # §13.3: Max Loss Hard Stop
    # =========================================================================

    @sealed
    def check_max_loss(self, session: Dict) -> List[Dict]:
        """Check if total P&L has exceeded max loss threshold."""
        events = []
        params = session.get('params', {})
        max_loss = params.get('max_loss_amount', 5000.0)

        # AUDIT FIX: Guard against max_loss ≤ 0 which would trigger instant auto-close
        if max_loss <= 0:
            return events

        # H-1: use single canonical formula (includes fees + perp)
        from .mmm_pnl_core import compute_current_total_pnl as _pnl_total
        total_pnl = _pnl_total(session)

        if total_pnl <= -max_loss:
            events.append({
                'type': 'max_loss',
                'level': 'critical',
                'message': (
                    f"MAX LOSS BREACHED: P&L ${total_pnl:.2f} exceeds "
                    f"-${max_loss:.2f} limit. CLOSING ALL POSITIONS."
                ),
                'action': 'auto_close',
                'details': {
                    'total_pnl': total_pnl,
                    'max_loss': max_loss,
                    'realized': session.get('realized_pnl', 0),
                    'unrealized': session.get('unrealized_pnl', 0),
                    'fees': session.get('total_fees', 0),
                    'perp_pnl': round(
                        float(session.get('perp_hedge', {}).get('realized_pnl', 0) or 0)
                        + float(session.get('perp_hedge', {}).get('unrealized_pnl', 0) or 0),
                        4,
                    ),
                },
            })
        elif total_pnl <= -max_loss * 0.8:
            events.append({
                'type': 'max_loss',
                'level': 'alert',
                'message': (
                    f"Approaching max loss: P&L ${total_pnl:.2f} "
                    f"(limit: -${max_loss:.2f})"
                ),
                'action': 'warn',
                'details': {
                    'total_pnl': total_pnl,
                    'max_loss': max_loss,
                },
            })

        return events

    @sealed
    def check_max_loss_sizing(self, session: Dict) -> List[Dict]:
        """
        IMP-6: Warn once per session if max_loss_amount is below the suggested
        minimum for the current position size.

        suggested_min = initial_lots × total_net_premium_per_lot × 0.50

        This fires at most once per session (flag _max_loss_sizing_warned).
        Action is 'warn' — never blocks trading.
        """
        events = []
        if session.get('_max_loss_sizing_warned'):
            return events

        params = session.get('params', {})
        max_loss = params.get('max_loss_amount', 5000.0)
        initial_lots = params.get('initial_lots', 0)
        if initial_lots <= 0:
            return events

        # Compute average premium per lot across both sides at entry
        ce_entry = session.get('ce', {}).get('original_premium', 0.0) or 0.0
        pe_entry = session.get('pe', {}).get('original_premium', 0.0) or 0.0
        if ce_entry <= 0 or pe_entry <= 0:
            return events

        from .mmm_constants import LOT_SIZE_BTC
        total_net_premium_per_lot = (ce_entry + pe_entry) * LOT_SIZE_BTC
        suggested_min = initial_lots * total_net_premium_per_lot * 0.50

        if suggested_min > 0 and max_loss < suggested_min:
            session['_max_loss_sizing_warned'] = True
            events.append({
                'type': 'max_loss_sizing',
                'level': 'warning',
                'message': (
                    f"max_loss_amount (${max_loss:,.0f}) is below suggested minimum "
                    f"(${suggested_min:,.0f}) for {initial_lots} lots × "
                    f"${total_net_premium_per_lot:.2f}/lot premium. "
                    f"Consider raising max_loss_amount."
                ),
                'action': 'warn',
                'details': {
                    'max_loss': max_loss,
                    'suggested_min': round(suggested_min, 2),
                    'initial_lots': initial_lots,
                    'premium_per_lot': round(total_net_premium_per_lot, 4),
                },
            })

        return events

    # =========================================================================
    # §13.4: Adaptive Whipsaw Guard
    # =========================================================================

    def check_whipsaw(self, session: Dict) -> List[Dict]:
        """
        Adaptive Whipsaw Guard — graduated response to alternating adjustments.

        Three rules:
        1. Time-windowed counting: only count alternations within rolling window
        2. Spot-move validation: skip alternations where BTC spot moved enough
        3. Graduated response: score → NORMAL / CAUTION / RESTRICT / COOLDOWN

        Session state keys:
          _whipsaw_score           int   — current noise score
          _whipsaw_last_noise_at   str   — ISO timestamp of last noise increment
          _whipsaw_skip_until      str   — ISO timestamp, skip adjustments until
          _whipsaw_last_checked_idx int  — last algo_history index evaluated
        """
        events = []
        params = session.get('params', {})
        now = datetime.now(timezone.utc)

        # ── Migration: clear old binary-pause whipsaw state ───────────────
        # Sessions created before the Adaptive Guard upgrade may have
        # _whipsaw_paused_at set (old system). Clear it and auto-resume so
        # the session is not stuck PAUSED forever.
        old_paused_at = session.pop('_whipsaw_paused_at', None)
        session.pop('_whipsaw_checked_up_to', None)
        session.pop('_whipsaw_consecutive_alternating', None)
        if old_paused_at:
            log.info(
                f"Whipsaw migration: cleared old _whipsaw_paused_at, "
                f"resuming under Adaptive Guard"
            )
            events.append({
                'type': 'whipsaw_guard',
                'level': 'info',
                'message': (
                    'Whipsaw system upgraded to Adaptive Guard. '
                    'Previous pause cleared — resuming adjustments.'
                ),
                'action': 'resume',
                'details': {'migration': True},
            })
            return events
        window_mins = params.get('whipsaw_window_mins', 30)
        spot_move_pct = params.get('whipsaw_spot_move_pct', 0.3)
        caution_threshold = params.get('whipsaw_caution_score', 2)
        restrict_threshold = params.get('whipsaw_restrict_score', 3)
        cooldown_threshold = params.get('whipsaw_cooldown_score', 4)
        interval = params.get('adjustment_interval', 300)

        score = session.get('_whipsaw_score', 0)

        # ── Rule 0: Skip-interval check ──────────────────────────────────
        skip_until = session.get('_whipsaw_skip_until')
        if skip_until:
            try:
                skip_time = datetime.fromisoformat(skip_until)
                if skip_time.tzinfo is None:
                    skip_time = skip_time.replace(tzinfo=timezone.utc)
                if now < skip_time:
                    remaining = (skip_time - now).total_seconds()
                    log.debug(
                        f"Whipsaw COOLDOWN skip active: {remaining:.0f}s remaining"
                    )
                    events.append({
                        'type': 'whipsaw_guard',
                        'level': 'alert',
                        'message': (
                            f"Whipsaw COOLDOWN active (score {score}): "
                            f"skipping adjustments, {remaining:.0f}s remaining"
                        ),
                        'action': 'stop_adjustments',
                        'details': {
                            'score': score,
                            'level': 'COOLDOWN',
                            'remaining': round(remaining),
                        },
                    })
                    return events
                else:
                    # Skip expired — reduce score by 2
                    score = max(0, score - 2)
                    session.pop('_whipsaw_skip_until', None)
                    session['_whipsaw_score'] = score
                    log.info(
                        f"Whipsaw COOLDOWN expired, score reduced to {score}"
                    )
            except (ValueError, TypeError):
                session.pop('_whipsaw_skip_until', None)

        # ── Rule 1: Score decay ───────────────────────────────────────────
        # Decay -1 for each full adjustment_interval elapsed since last noise
        last_noise = session.get('_whipsaw_last_noise_at')
        if last_noise and score > 0:
            try:
                noise_time = datetime.fromisoformat(last_noise)
                if noise_time.tzinfo is None:
                    noise_time = noise_time.replace(tzinfo=timezone.utc)
                elapsed = (now - noise_time).total_seconds()
                decay_intervals = int(elapsed / interval)
                if decay_intervals > 0:
                    old_score = score
                    score = max(0, score - decay_intervals)
                    session['_whipsaw_score'] = score
                    # Advance the noise timestamp so we don't double-decay
                    session['_whipsaw_last_noise_at'] = (
                        noise_time + timedelta(seconds=decay_intervals * interval)
                    ).isoformat()
                    if score < old_score:
                        log.info(
                            f"Whipsaw score decayed {old_score} → {score} "
                            f"({decay_intervals} interval(s) without noise)"
                        )
            except (ValueError, TypeError):
                session.pop('_whipsaw_last_noise_at', None)

        # ── Rule 2: Evaluate new adjustment history ───────────────────────
        history = session.get('adjustment_history', [])
        algo_history = [h for h in history
                        if h.get('aggressor', '') not in ('OPERATOR', 'STRADDLE_ROLL')]

        last_checked_idx = session.get('_whipsaw_last_checked_idx', None)
        if last_checked_idx is None:
            # BUG-C3 fix: first-ever run (including post-migration heartbeat where old
            # _whipsaw_paused_at was cleared but _whipsaw_last_checked_idx was never set).
            # Skip all past history to avoid false COOLDOWN on session restore/upgrade.
            last_checked_idx = len(algo_history)
            session['_whipsaw_last_checked_idx'] = last_checked_idx
        if len(algo_history) > last_checked_idx and len(algo_history) >= 2:
            window_cutoff = now - timedelta(minutes=window_mins)

            start_idx = max(1, last_checked_idx)
            for i in range(start_idx, len(algo_history)):
                curr = algo_history[i]
                prev = algo_history[i - 1]

                # Not an alternation — same direction
                if curr.get('aggressor', '') == prev.get('aggressor', ''):
                    continue

                # Outside rolling window — skip
                try:
                    curr_ts = datetime.fromisoformat(curr.get('timestamp', ''))
                    if curr_ts.tzinfo is None:
                        curr_ts = curr_ts.replace(tzinfo=timezone.utc)
                    if curr_ts < window_cutoff:
                        continue
                except (ValueError, TypeError):
                    continue

                # Spot-move validation: if BTC moved enough, this is justified
                curr_spot = curr.get('spot', 0)
                prev_spot = prev.get('spot', 0)
                if curr_spot > 0 and prev_spot > 0:
                    spot_delta_pct = abs(curr_spot - prev_spot) / prev_spot * 100
                    if spot_delta_pct >= spot_move_pct:
                        continue  # Justified — real market movement

                # This is a noise alternation — increment score
                score += 1
                session['_whipsaw_last_noise_at'] = now.isoformat()

            session['_whipsaw_last_checked_idx'] = len(algo_history)
            session['_whipsaw_score'] = score

        # ── Rule 3: Graduated response ────────────────────────────────────
        if score >= cooldown_threshold:
            skip_secs = interval
            session['_whipsaw_skip_until'] = (
                now + timedelta(seconds=skip_secs)
            ).isoformat()
            events.append({
                'type': 'whipsaw_guard',
                'level': 'alert',
                'message': (
                    f"Whipsaw COOLDOWN (score {score}): "
                    f"skipping adjustments for {skip_secs}s, "
                    f"then score drops by 2"
                ),
                'action': 'stop_adjustments',
                'details': {
                    'score': score,
                    'level': 'COOLDOWN',
                    'skip_seconds': skip_secs,
                    'thresholds': {
                        'caution': caution_threshold,
                        'restrict': restrict_threshold,
                        'cooldown': cooldown_threshold,
                    },
                },
            })
        elif score >= restrict_threshold:
            events.append({
                'type': 'whipsaw_guard',
                'level': 'warning',
                'message': (
                    f"Whipsaw RESTRICT (score {score}): "
                    f"triggers widened +100%, lots halved"
                ),
                'action': 'continue',
                'details': {
                    'score': score,
                    'level': 'RESTRICT',
                    'trigger_factor': 2.0,
                    'lot_factor': 0.5,
                },
            })
        elif score >= caution_threshold:
            events.append({
                'type': 'whipsaw_guard',
                'level': 'info',
                'message': (
                    f"Whipsaw CAUTION (score {score}): "
                    f"triggers widened +50%"
                ),
                'action': 'continue',
                'details': {
                    'score': score,
                    'level': 'CAUTION',
                    'trigger_factor': 1.5,
                    'lot_factor': 1.0,
                },
            })

        return events

    def check_total_exposure(self, session: Dict) -> List[Dict]:
        """
        Split Ledger: Warn when active + frozen lots approach max_total_exposure
        ceiling. action='warn' only — the engine handles the hard block.
        Does NOT fire 'stop_adjustments' to avoid bypassing the engine path.
        """
        events = []
        params = session.get('params', {})
        max_lots = params.get('max_lots_per_side', 100)
        max_total = params.get('max_total_exposure', 0)
        if max_total <= 0:
            max_total = max_lots * 2

        # Per-side reverse lots from positions (not combined total_lots).
        # CE reverse positions are CE exchange exposure; PE reverse are PE exposure.
        # Using total_lots (combined CE+PE) on both sides would double-count.
        _rev_positions = session.get('_reverse', {}).get('positions', [])
        _reverse_lots_by_side = {
            'ce': sum(p.get('lots', 0) for p in _rev_positions
                      if p.get('status') == 'open' and p.get('option_type') == 'ce'),
            'pe': sum(p.get('lots', 0) for p in _rev_positions
                      if p.get('status') == 'open' and p.get('option_type') == 'pe'),
        }

        for side_key in ['ce', 'pe']:
            side_state = session.get(side_key, {})
            total = side_state.get('total_lots', 0)
            frozen = side_state.get('frozen_total_lots', 0)
            active = side_state.get('active_lots', 0)
            # Add per-side reverse lots (CE reverse to CE, PE reverse to PE)
            total = total + _reverse_lots_by_side.get(side_key, 0)
            ratio = total / max_total if max_total > 0 else 0

            if total >= max_total:
                events.append({
                    'type': 'total_exposure',
                    'level': 'alert',
                    'message': (
                        f"{side_key.upper()} TOTAL EXPOSURE CEILING: "
                        f"{total}/{max_total} lots "
                        f"(active: {active}, frozen: {frozen})"
                    ),
                    'action': 'warn',
                    'details': {
                        'side': side_key, 'total': total,
                        'active': active, 'frozen': frozen, 'max': max_total,
                    },
                })
            elif ratio >= 0.8:
                events.append({
                    'type': 'total_exposure',
                    'level': 'info',
                    'message': (
                        f"{side_key.upper()} approaching total exposure ceiling: "
                        f"{total}/{max_total} lots ({ratio:.0%})"
                    ),
                    'action': 'continue',
                    'details': {
                        'side': side_key, 'total': total,
                        'active': active, 'frozen': frozen, 'max': max_total,
                    },
                })

        return events

    # =========================================================================
    # §13.5: Position Asymmetry
    # =========================================================================

    def check_asymmetry(self, session: Dict) -> List[Dict]:
        """
        IMP-3: Three-tier asymmetry protection.
          3:1 warning  — log and continue
          5:1 alert    — reduce next lot size by 50% (sets session flag)
          7:1 critical — hard-block ALL new sells (stop_adjustments)
        """
        events = []
        params = session.get('params', {})
        ce_lots = session.get('ce', {}).get('total_lots', 0)
        pe_lots = session.get('pe', {}).get('total_lots', 0)

        if ce_lots == 0 and pe_lots == 0:
            session.pop('_asymmetry_lot_reduction_pct', None)
            session.pop('_asymmetry_heavy_side', None)
            return events

        max_lots = max(ce_lots, pe_lots)
        min_lots = max(min(ce_lots, pe_lots), 1)  # avoid /0
        ratio = max_lots / min_lots
        heavy_side = 'ce' if ce_lots >= pe_lots else 'pe'

        hard_block_enabled = params.get('asymmetry_7to1_hard_block', True)
        lot_reduction = params.get('asymmetry_5to1_lot_reduction', 0.5)

        if ratio >= 7 and hard_block_enabled:
            # Tier 3: block ONLY the heavy-side sells — allow the light side to
            # rebalance.  Previously used 'stop_adjustments' which blocked ALL
            # trigger evaluation via _skip_to_pnl, preventing PE sells when CE
            # was the heavy side (e.g. CE=126, PE=2 → PE sells were forbidden
            # even though they would reduce asymmetry).  Fix: use targeted block.
            session.pop('_asymmetry_lot_reduction_pct', None)
            session.pop('_asymmetry_heavy_side', None)
            light_side = 'pe' if heavy_side == 'ce' else 'ce'
            events.append({
                'type': 'asymmetry',
                'level': 'critical',
                'message': (
                    f"ASYMMETRY HARD BLOCK: CE={ce_lots}, PE={pe_lots} "
                    f"(ratio: {ratio:.1f}:1 ≥ 7:1) — "
                    f"{heavy_side.upper()} sells blocked, {light_side.upper()} sells allowed to rebalance"
                ),
                'action': 'block_heavy_side_sells',
                'details': {
                    'ce_lots': ce_lots,
                    'pe_lots': pe_lots,
                    'ratio': round(ratio, 1),
                    'heavy_side': heavy_side,
                    'light_side': light_side,
                },
            })
        elif ratio >= 5:
            # Tier 2: reduce heavy-side lot size by 50%
            session['_asymmetry_lot_reduction_pct'] = lot_reduction
            session['_asymmetry_heavy_side'] = heavy_side
            events.append({
                'type': 'asymmetry',
                'level': 'alert',
                'message': (
                    f"HIGH asymmetry: CE={ce_lots}, PE={pe_lots} "
                    f"(ratio: {ratio:.1f}:1) — {heavy_side.upper()} lots reduced "
                    f"by {int((1 - lot_reduction) * 100)}%"
                ),
                'action': 'warn',
                'details': {
                    'ce_lots': ce_lots,
                    'pe_lots': pe_lots,
                    'ratio': round(ratio, 1),
                    'heavy_side': heavy_side,
                    'lot_reduction_pct': lot_reduction,
                },
            })
        elif ratio >= 3:
            # Tier 1: warning only
            session.pop('_asymmetry_lot_reduction_pct', None)
            session.pop('_asymmetry_heavy_side', None)
            events.append({
                'type': 'asymmetry',
                'level': 'warning',
                'message': (
                    f"Position asymmetry: CE={ce_lots}, PE={pe_lots} "
                    f"(ratio: {ratio:.1f}:1)"
                ),
                'action': 'continue',
                'details': {
                    'ce_lots': ce_lots,
                    'pe_lots': pe_lots,
                    'ratio': round(ratio, 1),
                },
            })
        else:
            # Below 3:1 — clear any prior flags
            session.pop('_asymmetry_lot_reduction_pct', None)
            session.pop('_asymmetry_heavy_side', None)

        return events

    # =========================================================================
    # §13.6: Near-Expiry Behavior
    # =========================================================================

    def check_near_expiry(
        self,
        session: Dict,
        minutes_to_expiry: float,
    ) -> List[Dict]:
        """
        Stop adjustments at N minutes, auto-close at M minutes before expiry.
        """
        events = []
        params = session.get('params', {})
        stop_mins = params.get('stop_adjustment_mins', 15)
        close_mins = params.get('auto_close_mins', 5)

        if minutes_to_expiry <= close_mins:
            events.append({
                'type': 'near_expiry',
                'level': 'critical',
                'message': (
                    f"AUTO-CLOSE: {minutes_to_expiry:.1f} min to expiry "
                    f"(threshold: {close_mins} min). Closing all positions."
                ),
                'action': 'auto_close',
                'details': {
                    'minutes_to_expiry': minutes_to_expiry,
                    'threshold': close_mins,
                },
            })
        elif minutes_to_expiry <= stop_mins:
            events.append({
                'type': 'near_expiry',
                'level': 'alert',
                'message': (
                    f"STOP ADJUSTMENTS: {minutes_to_expiry:.1f} min to expiry "
                    f"(threshold: {stop_mins} min). No more adjustments."
                ),
                'action': 'stop_adjustments',
                'details': {
                    'minutes_to_expiry': minutes_to_expiry,
                    'threshold': stop_mins,
                },
            })
        elif minutes_to_expiry <= 60:
            events.append({
                'type': 'near_expiry',
                'level': 'info',
                'message': (
                    f"Expiry approaching: {minutes_to_expiry:.0f} min"
                ),
                'action': 'continue',
                'details': {
                    'minutes_to_expiry': minutes_to_expiry,
                },
            })

        return events

    def check_near_expiry_v2(
        self,
        session: Dict,
        minutes_to_expiry: float,
    ) -> List[Dict]:
        """
        DTE-aware near-expiry check for multi-expiry sessions.

        Combines:
        1. Absolute-minute thresholds (auto_close_mins, stop_adjustment_mins)
           — always enforced, same as v1
        2. Percentage-based soft wind-down warning based on total DTE

        For 0DTE sessions, behaves identically to v1.
        For 5DTE+ sessions, adds early warnings when entering the last X% of DTE.
        """
        events = []
        params = session.get('params', {})
        stop_mins = params.get('stop_adjustment_mins', 15)
        close_mins = params.get('auto_close_mins', 5)
        total_dte_hours = params.get('total_dte_hours', 0)
        wind_down_hours = params.get('wind_down_hours_before_expiry', 2.0)

        # 1. Absolute thresholds — always enforced (same as v1)
        if minutes_to_expiry <= close_mins:
            events.append({
                'type': 'near_expiry',
                'level': 'critical',
                'message': (
                    f"AUTO-CLOSE: {minutes_to_expiry:.1f} min to expiry "
                    f"(threshold: {close_mins} min). Closing all positions."
                ),
                'action': 'auto_close',
                'details': {
                    'minutes_to_expiry': minutes_to_expiry,
                    'threshold': close_mins,
                },
            })
            return events  # Most critical — skip other checks

        if minutes_to_expiry <= stop_mins:
            events.append({
                'type': 'near_expiry',
                'level': 'alert',
                'message': (
                    f"STOP ADJUSTMENTS: {minutes_to_expiry:.1f} min to expiry "
                    f"(threshold: {stop_mins} min). No more adjustments."
                ),
                'action': 'stop_adjustments',
                'details': {
                    'minutes_to_expiry': minutes_to_expiry,
                    'threshold': stop_mins,
                },
            })
            return events

        # 2. Wind-down zone — from preset's wind_down_hours_before_expiry
        wind_down_mins = wind_down_hours * 60
        if minutes_to_expiry <= wind_down_mins:
            events.append({
                'type': 'near_expiry',
                'level': 'warning',
                'message': (
                    f"WIND-DOWN ZONE: {minutes_to_expiry:.0f} min to expiry "
                    f"(wind-down starts at {wind_down_mins:.0f} min). "
                    f"Reducing activity."
                ),
                'action': 'wind_down',
                'details': {
                    'minutes_to_expiry': minutes_to_expiry,
                    'wind_down_threshold_mins': wind_down_mins,
                },
            })
            return events

        # 3. Percentage-based early warning (last 5% of total DTE)
        if total_dte_hours > 36:  # Only for multi-DTE sessions
            total_dte_mins = total_dte_hours * 60
            warning_pct = 0.05  # Last 5% of DTE
            warning_mins = total_dte_mins * warning_pct
            if minutes_to_expiry <= warning_mins:
                events.append({
                    'type': 'near_expiry',
                    'level': 'info',
                    'message': (
                        f"Expiry approaching: {minutes_to_expiry:.0f} min "
                        f"(last 5% of {total_dte_hours:.0f}h DTE)"
                    ),
                    'action': 'continue',
                    'details': {
                        'minutes_to_expiry': minutes_to_expiry,
                        'warning_pct': warning_pct,
                        'total_dte_hours': total_dte_hours,
                    },
                })

        return events

    # =========================================================================
    # §14.4: Net P&L Guardrail
    # =========================================================================

    def check_pnl_guardrail(self, session: Dict) -> List[Dict]:
        """
        Multi-tier P&L guardrail:
          - 50% of max_loss → warning
          - 80% of max_loss → alert (consider pausing)
          - 100% → hard stop (handled by check_max_loss)
        """
        events = []
        params = session.get('params', {})
        max_loss = params.get('max_loss_amount', 5000.0)

        realized = session.get('realized_pnl', 0)
        unrealized = session.get('unrealized_pnl', 0)
        # Fix #26: Include perp hedge P&L for accurate guardrail tracking
        perp = session.get('perp_hedge', {})
        perp_pnl = perp.get('realized_pnl', 0.0) + perp.get('unrealized_pnl', 0.0)
        total_pnl = realized + unrealized + perp_pnl

        ratio = abs(total_pnl) / max_loss if max_loss > 0 and total_pnl < 0 else 0

        if 0.5 <= ratio < 0.8:
            events.append({
                'type': 'pnl_guardrail',
                'level': 'warning',
                'message': (
                    f"P&L guardrail: at {ratio:.0%} of max loss "
                    f"(${total_pnl:.2f} / -${max_loss:.2f})"
                ),
                'action': 'continue',
                'details': {
                    'total_pnl': total_pnl,
                    'max_loss': max_loss,
                    'ratio': round(ratio, 2),
                },
            })
        elif 0.8 <= ratio < 1.0:
            events.append({
                'type': 'pnl_guardrail',
                'level': 'alert',
                'message': (
                    f"P&L guardrail ALERT: at {ratio:.0%} of max loss "
                    f"(${total_pnl:.2f} / -${max_loss:.2f}). "
                    f"Consider pausing."
                ),
                'action': 'warn',
                'details': {
                    'total_pnl': total_pnl,
                    'max_loss': max_loss,
                    'ratio': round(ratio, 2),
                },
            })

        return events

    # =========================================================================
    # §13.7: Margin Check
    # =========================================================================

    def check_margin(self, session: Dict) -> List[Dict]:
        """
        §13.7: Check if there's sufficient margin before selling.

        Uses total_lots and premium as a proxy for margin utilization.
        A full margin API check would require exchange integration,
        but this provides a safety net based on position size.
        """
        events = []
        params = session.get('params', {})
        max_lots = params.get('max_lots_per_side', 100)

        total_ce = session.get('ce', {}).get('total_lots', 0)
        total_pe = session.get('pe', {}).get('total_lots', 0)
        # Include reverse lots in margin check (audit fix)
        reverse_lots = session.get('_reverse', {}).get('total_lots', 0)
        total_lots = total_ce + total_pe + reverse_lots

        # Warn if combined lots exceed 150% of single-side cap
        combined_cap = max_lots * 1.5
        if total_lots > combined_cap:
            events.append({
                'type': 'margin_warning',
                'level': 'alert',
                'message': (
                    f"High margin utilization: {total_lots} total lots "
                    f"(CE: {total_ce}, PE: {total_pe}). "
                    f"Combined cap: {combined_cap:.0f}"
                ),
                'action': 'warn',
                'details': {
                    'total_lots': total_lots,
                    'ce_lots': total_ce,
                    'pe_lots': total_pe,
                    'combined_cap': combined_cap,
                },
            })

        return events

    # =========================================================================
    # T2-4: Lot Velocity Limiter
    # =========================================================================

    def check_lot_velocity(self, session: Dict) -> List[Dict]:
        """T2-4: Cap lot growth rate to prevent exponential accumulation.

        Counts lots sold across both sides in a rolling window.
        If velocity exceeds `lot_velocity_limit` in `lot_velocity_window_mins`,
        blocks further adjustments until the window rolls forward.
        """
        events = []
        params = session.get('params', {})
        if not params.get('lot_velocity_enabled', True):
            return events

        limit = params.get('lot_velocity_limit', 10)
        window_mins = params.get('lot_velocity_window_mins', 30)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_mins)

        history = session.get('adjustment_history', [])
        lots_in_window = 0
        for adj in history:
            # AUDIT FIX: Skip OPERATOR/STRADDLE_ROLL injections — same as whipsaw filter
            if adj.get('aggressor', '') in ('OPERATOR', 'STRADDLE_ROLL'):
                continue
            try:
                ts = datetime.fromisoformat(adj.get('timestamp', ''))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    lots_in_window += adj.get('lots_sold', 0)
            except (ValueError, TypeError):
                continue

        if lots_in_window >= limit:
            events.append({
                'type': 'lot_velocity',
                'level': 'alert',
                'message': (
                    f'LOT VELOCITY LIMIT: {lots_in_window} lots sold in last '
                    f'{window_mins}min (limit: {limit}) — adjustments blocked'
                ),
                'action': 'stop_adjustments',
                'details': {
                    'lots_in_window': lots_in_window,
                    'limit': limit,
                    'window_mins': window_mins,
                },
            })
        elif lots_in_window >= limit * 0.8:
            events.append({
                'type': 'lot_velocity',
                'level': 'warning',
                'message': (
                    f'Lot velocity warning: {lots_in_window}/{limit} lots '
                    f'in last {window_mins}min'
                ),
                'action': 'continue',
                'details': {
                    'lots_in_window': lots_in_window,
                    'limit': limit,
                    'window_mins': window_mins,
                },
            })

        return events

    # =========================================================================
    # §14.6: Trailing Profit Protection
    # =========================================================================

    def check_trailing_stop(self, session: Dict) -> List[Dict]:
        """
        Protect profits: if P&L drops below trailing_stop_pct of peak, alert.
        """
        events = []
        params = session.get('params', {})
        trailing_pct = params.get('trailing_stop_pct', 0.50)

        # trailing_stop_pct=0 means disabled — threshold would be $0 which
        # fires on any dip below zero after profit, not the intended behavior.
        # The API/UI already treats 0 as "disabled" for display purposes;
        # this guard makes the safety check consistent with that intent.
        if trailing_pct <= 0:
            return events

        peak = session.get('peak_pnl', 0)
        if peak <= 0:
            return events  # No profit to protect

        # H-1: use single canonical formula (includes fees + perp)
        from .mmm_pnl_core import compute_current_total_pnl as _pnl_total
        current = _pnl_total(session)

        threshold = peak * trailing_pct
        if current < threshold:
            # H-3 fix: changed from 'warn' to 'stop_adjustments' so that
            # should_block_adjustment() actually blocks new adjustments when
            # the trailing floor is breached. Previously 'warn' was not in
            # the blocking set so adjustments continued while profits evaporated.
            events.append({
                'type': 'trailing_stop',
                'level': 'alert',
                'message': (
                    f'TRAILING STOP BREACHED — ADJUSTMENTS BLOCKED. '
                    f'P&L ${current:.2f} below floor ${threshold:.2f} '
                    f'(peak ${peak:.2f})'
                ),
                'action': 'stop_adjustments',
                'details': {
                    'current_pnl': current,
                    'peak_pnl': peak,
                    'trailing_pct': trailing_pct,
                    'floor': threshold,
                },
            })

        return events


def update_peak_pnl(session: Dict, total_pnl: float):
    """Track high-water mark for trailing stop.

    AUDIT FIX: Changed from 10%/heartbeat decay (which nullified trailing stop
    in ~2 minutes) to time-based decay with 15-minute half-life.
    This preserves the peak long enough for trailing stop to be meaningful
    while still preventing stale peaks after close-at-5 reduces positions.
    """
    current_peak = session.get('peak_pnl', 0)
    if total_pnl > current_peak:
        session['peak_pnl'] = total_pnl
        session['_peak_pnl_set_at'] = datetime.now(timezone.utc).isoformat()
    elif current_peak > 0 and total_pnl < current_peak:
        # Time-based decay: half-life of 15 minutes
        decay_factor = 0.95  # fallback per-beat decay (much gentler than 0.9)
        peak_set_at = session.get('_peak_pnl_set_at')
        if peak_set_at:
            try:
                t = datetime.fromisoformat(peak_set_at)
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                age_mins = (datetime.now(timezone.utc) - t).total_seconds() / 60
                half_life = 15.0  # minutes
                decay_factor = 0.5 ** (age_mins / half_life)
            except (ValueError, TypeError):
                pass
        decayed = current_peak * decay_factor + total_pnl * (1 - decay_factor)
        session['peak_pnl'] = max(decayed, 0)
        # BUG-C1 fix: update timestamp after each decay so age_mins resets to
        # ~1 interval on the next heartbeat. Without this, age_mins grows unboundedly
        # and decay_factor collapses to ~0 after 60 min, nullifying the trailing stop.
        session['_peak_pnl_set_at'] = datetime.now(timezone.utc).isoformat()


def reset_peak_pnl_on_reversal(session: Dict, total_pnl: float):
    """
    Robust v2 Fix #7: Reset peak P&L when a reversal is detected.
    A reversal starts a new profit phase — the old peak is irrelevant.
    """
    log.info(
        f"Resetting peak_pnl on reversal: "
        f"old={session.get('peak_pnl', 0):.2f}, new baseline={total_pnl:.2f}"
    )
    session['peak_pnl'] = max(total_pnl, 0)


def should_block_adjustment(safety_events: List[Dict]) -> bool:
    """
    Determine if safety events should block the next adjustment.

    Returns:
        True if any event requires blocking adjustments, False otherwise.
        Use get_block_action() to get the reason and action type.
    """
    for event in safety_events:
        if event.get('action') in ('stop', 'auto_close', 'stop_adjustments'):
            return True
    return False


def get_block_action(safety_events: List[Dict]) -> Tuple[str, str]:
    """
    Return (reason, action_type) for the most severe blocking safety event.

    Priority (highest → lowest): auto_close > stop > stop_adjustments.
    action_type is one of: 'stop', 'auto_close', 'stop_adjustments'.
    Call only after should_block_adjustment() returns True.
    """
    priority = {'auto_close': 3, 'stop': 2, 'stop_adjustments': 1}
    best = None
    best_priority = 0
    for event in safety_events:
        action = event.get('action', '')
        if action in priority and priority[action] > best_priority:
            best = event
            best_priority = priority[action]
    if best:
        return best.get('message', 'Safety block'), best['action']
    return 'Safety block', 'stop'


def should_pause(safety_events: List[Dict]) -> Tuple[bool, str]:
    """
    Determine if safety events should pause the algorithm.

    Returns:
        (should_pause, reason)
    """
    for event in safety_events:
        if event.get('action') == 'pause':
            return True, event.get('message', 'Safety pause')

    return False, ''


# Singleton (M-4 fix: double-checked locking prevents TOCTOU race)
import threading as _threading_safety
_safety_instance = None
_safety_lock = _threading_safety.Lock()


def get_safety() -> MMMSafety:
    global _safety_instance
    if _safety_instance is None:
        with _safety_lock:
            if _safety_instance is None:
                _safety_instance = MMMSafety()
    return _safety_instance
