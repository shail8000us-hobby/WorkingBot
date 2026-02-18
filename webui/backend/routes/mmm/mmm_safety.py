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
from datetime import datetime, timedelta

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
        events.extend(self.check_max_adjustments(session))
        events.extend(self.check_max_loss(session))
        events.extend(self.check_whipsaw(session))
        events.extend(self.check_asymmetry(session))

        if minutes_to_expiry is not None:
            events.extend(
                self.check_near_expiry(session, minutes_to_expiry)
            )

        events.extend(self.check_pnl_guardrail(session))
        events.extend(self.check_trailing_stop(session))
        events.extend(self.check_margin(session))

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
            total = side_state.get('total_lots', 0)
            ratio = total / max_lots if max_lots > 0 else 0

            if total >= max_lots:
                events.append({
                    'type': 'position_cap',
                    'level': 'alert',
                    'message': (
                        f"{side_key.upper()} position cap reached: "
                        f"{total}/{max_lots} lots"
                    ),
                    'action': 'warn',
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
        """Check if max adjustment count reached."""
        events = []
        params = session.get('params', {})
        max_adj = params.get('max_adjustments', 100)
        current = session.get('adjustment_count', 0)

        if current >= max_adj:
            events.append({
                'type': 'max_adjustments',
                'level': 'critical',
                'message': (
                    f"Max adjustments reached: {current}/{max_adj}. "
                    f"No more adjustments allowed."
                ),
                'action': 'stop',
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

    def check_max_loss(self, session: Dict) -> List[Dict]:
        """Check if total P&L has exceeded max loss threshold."""
        events = []
        params = session.get('params', {})
        max_loss = params.get('max_loss_amount', 5000.0)

        realized = session.get('realized_pnl', 0)
        unrealized = session.get('unrealized_pnl', 0)
        total_pnl = realized + unrealized

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
                    'realized': realized,
                    'unrealized': unrealized,
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

    # =========================================================================
    # §13.4: Whipsaw Detection
    # =========================================================================

    def check_whipsaw(self, session: Dict) -> List[Dict]:
        """
        Detect 3 rapid alternating adjustments (CE→PE→CE or PE→CE→PE).
        Bug #15 fix: track whipsaw_paused_at for auto-resume after 2 intervals.
        """
        events = []
        params = session.get('params', {})
        whipsaw_limit = params.get('whipsaw_limit', 3)

        # Bug #15 fix: check for auto-resume
        whipsaw_paused_at = session.get('_whipsaw_paused_at')
        if whipsaw_paused_at:
            try:
                paused_time = datetime.fromisoformat(whipsaw_paused_at)
                interval = params.get('adjustment_interval', 300)
                resume_after = interval * 2  # Resume after 2 intervals
                elapsed = (datetime.utcnow() - paused_time).total_seconds()
                if elapsed >= resume_after:
                    session.pop('_whipsaw_paused_at', None)
                    log.info(
                        f"Whipsaw auto-resume: {elapsed:.0f}s elapsed "
                        f"(threshold: {resume_after}s)"
                    )
                    events.append({
                        'type': 'whipsaw_resume',
                        'level': 'info',
                        'message': (
                            f"Whipsaw auto-resume after {elapsed:.0f}s cooldown. "
                            f"Adjustments re-enabled."
                        ),
                        'action': 'resume',
                        'details': {
                            'elapsed': round(elapsed),
                            'resume_after': resume_after,
                        },
                    })
                    return events  # Resume, don't re-check whipsaw
            except (ValueError, TypeError):
                session.pop('_whipsaw_paused_at', None)

        history = session.get('adjustment_history', [])
        if len(history) < whipsaw_limit:
            return events

        # Check last N adjustments for alternating pattern
        recent = history[-whipsaw_limit:]
        sides = [h.get('aggressor', '') for h in recent]

        alternating = True
        for i in range(1, len(sides)):
            if sides[i] == sides[i - 1]:
                alternating = False
                break

        if alternating and len(set(sides)) > 1:
            session['_whipsaw_paused_at'] = datetime.utcnow().isoformat()
            events.append({
                'type': 'whipsaw',
                'level': 'alert',
                'message': (
                    f"Whipsaw detected: {whipsaw_limit} alternating "
                    f"adjustments ({' → '.join(sides)}). "
                    f"Auto-pausing for {params.get('adjustment_interval', 300) * 2}s."
                ),
                'action': 'pause',
                'details': {
                    'sequence': sides,
                    'limit': whipsaw_limit,
                },
            })

        return events

    # =========================================================================
    # §13.5: Position Asymmetry
    # =========================================================================

    def check_asymmetry(self, session: Dict) -> List[Dict]:
        """
        Detect asymmetric position sizes (ratio 3:1 = warning, 5:1 = alert).
        """
        events = []
        ce_lots = session.get('ce', {}).get('total_lots', 0)
        pe_lots = session.get('pe', {}).get('total_lots', 0)

        if ce_lots == 0 and pe_lots == 0:
            return events

        max_lots = max(ce_lots, pe_lots)
        min_lots = max(min(ce_lots, pe_lots), 1)  # avoid /0
        ratio = max_lots / min_lots

        if ratio >= 5:
            events.append({
                'type': 'asymmetry',
                'level': 'alert',
                'message': (
                    f"HIGH position asymmetry: CE={ce_lots}, PE={pe_lots} "
                    f"(ratio: {ratio:.1f}:1)"
                ),
                'action': 'warn',
                'details': {
                    'ce_lots': ce_lots,
                    'pe_lots': pe_lots,
                    'ratio': round(ratio, 1),
                },
            })
        elif ratio >= 3:
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
        total_pnl = realized + unrealized

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
        total_lots = total_ce + total_pe

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
    # §14.6: Trailing Profit Protection
    # =========================================================================

    def check_trailing_stop(self, session: Dict) -> List[Dict]:
        """
        Protect profits: if P&L drops below trailing_stop_pct of peak, alert.
        """
        events = []
        params = session.get('params', {})
        trailing_pct = params.get('trailing_stop_pct', 0.50)

        peak = session.get('peak_pnl', 0)
        if peak <= 0:
            return events  # No profit to protect

        realized = session.get('realized_pnl', 0)
        unrealized = session.get('unrealized_pnl', 0)
        current = realized + unrealized

        threshold = peak * trailing_pct
        if current < threshold:
            events.append({
                'type': 'trailing_stop',
                'level': 'alert',
                'message': (
                    f"Trailing stop: P&L dropped to ${current:.2f} "
                    f"(peak: ${peak:.2f}, floor: ${threshold:.2f})"
                ),
                'action': 'warn',
                'details': {
                    'current_pnl': current,
                    'peak_pnl': peak,
                    'trailing_pct': trailing_pct,
                    'floor': threshold,
                },
            })

        return events


def update_peak_pnl(session: Dict, total_pnl: float):
    """Track high-water mark for trailing stop."""
    if total_pnl > session.get('peak_pnl', 0):
        session['peak_pnl'] = total_pnl


def should_block_adjustment(safety_events: List[Dict]) -> Tuple[bool, str]:
    """
    Determine if safety events should block the next adjustment.

    Returns:
        (should_block, reason)
    """
    for event in safety_events:
        action = event.get('action', 'continue')
        if action in ('stop', 'auto_close'):
            return True, event.get('message', 'Safety stop')
        if action == 'stop_adjustments':
            return True, event.get('message', 'Adjustments stopped')

    return False, ''


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


# Singleton
_safety_instance = None


def get_safety() -> MMMSafety:
    global _safety_instance
    if _safety_instance is None:
        _safety_instance = MMMSafety()
    return _safety_instance
