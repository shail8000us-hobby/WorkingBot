"""
SSDH Safety Checks — All exit triggers in one place

Called by the heartbeat before any exit logic.
All methods return (bool, str) — never raise.

Critical rules:
- check_margin() uses blocked_margin (NOT portfolio_margin — see lessons.md)
- check_trailing_stop() never fires when peak_net_pnl <= 0
- check_max_loss() uses Decimal comparison

Created: March 21, 2026
"""

import logging
from decimal import Decimal
from typing import Tuple

log = logging.getLogger('ssdh_safety')


class SSDHSafety:

    def __init__(self):
        self._circuit_failures = 0

    # =========================================================================
    # Max loss check
    # =========================================================================

    def check_max_loss(self, session: dict) -> Tuple[bool, str]:
        """
        Returns (triggered, reason).
        triggered=True if net_pnl < -max_loss_amount.
        Uses Decimal comparison to avoid float edge cases.
        """
        try:
            net_pnl      = Decimal(str(session.get('net_pnl', 0.0)))
            max_loss     = Decimal(str(session['params'].get('max_loss_amount', 9999999)))
            threshold    = -max_loss

            if net_pnl <= threshold:
                return True, f"net_pnl {float(net_pnl):.4f} ≤ -{float(max_loss):.4f} max_loss"
            return False, ''
        except Exception as e:
            log.error("check_max_loss error: %s", e)
            return False, ''

    # =========================================================================
    # Margin check
    # =========================================================================

    def check_margin(self, rest_client=None) -> Tuple[bool, str]:
        """
        Queries Delta Exchange wallet for actual margin utilisation.

        Uses blocked_margin (actual locked collateral), NOT portfolio_margin
        (theoretical risk model — can be higher than actual, causes false positives).

        Priority: blocked_margin > portfolio_margin > (position_margin + order_margin)

        Returns (ok, reason) — ok=False means margin is dangerously high.
        rest_client: async Delta client (unused in sync call — use in async context).
        """
        try:
            if rest_client is None:
                # Defer to caller to pass wallet data when calling from async context
                return True, 'no_client'

            wallet = rest_client.get_wallet() if hasattr(rest_client, 'get_wallet') else {}
            balance = float(wallet.get('available_balance', 0) or 0)
            if balance <= 0:
                return True, 'balance_unavailable'

            # Delta Exchange API quirk: use blocked_margin, not portfolio_margin
            margin_used = (
                float(wallet.get('blocked_margin', 0) or 0) or
                float(wallet.get('portfolio_margin', 0) or 0) or
                (float(wallet.get('position_margin', 0) or 0) +
                 float(wallet.get('order_margin', 0) or 0))
            )
            total = balance + margin_used
            if total <= 0:
                return True, 'cannot_compute_margin_ratio'

            ratio = margin_used / total

            # Use session params if available from caller context
            limit = 0.70  # default combined_margin_limit
            if ratio > limit:
                return False, f"margin utilisation {ratio:.1%} > limit {limit:.1%}"
            return True, ''
        except Exception as e:
            log.error("check_margin error: %s", e)
            return True, ''   # don't block trading on margin check error

    def check_margin_from_wallet(self, wallet: dict, params: dict) -> Tuple[bool, str]:
        """
        Synchronous margin check from pre-fetched wallet dict.
        Called from heartbeat with already-fetched wallet data.
        """
        try:
            balance = float(wallet.get('available_balance', 0) or 0)
            margin_used = (
                float(wallet.get('blocked_margin', 0) or 0) or
                float(wallet.get('portfolio_margin', 0) or 0) or
                (float(wallet.get('position_margin', 0) or 0) +
                 float(wallet.get('order_margin', 0) or 0))
            )
            if balance + margin_used <= 0:
                return True, ''

            ratio = margin_used / (balance + margin_used)
            limit = float(params.get('combined_margin_limit', 0.70))
            yellow = float(params.get('margin_yellow_pct', 0.65))

            if ratio > limit:
                return False, f"margin {ratio:.1%} > combined limit {limit:.1%}"
            if ratio > yellow:
                log.warning("SSDH margin warning: %s%%", f'{ratio:.1%}')
            return True, ''
        except Exception as e:
            log.error("check_margin_from_wallet error: %s", e)
            return True, ''

    # =========================================================================
    # Circuit breaker
    # =========================================================================

    def check_circuit_breaker(self, session: dict) -> Tuple[bool, str]:
        """
        Returns (ok, reason). ok=False if circuit is OPEN.
        Circuit opens after N consecutive API errors (circuit_breaker_threshold).
        """
        threshold = int(session['params'].get('circuit_breaker_threshold', 5))
        if self._circuit_failures >= threshold:
            return False, f"circuit OPEN: {self._circuit_failures} consecutive API errors"
        return True, ''

    def record_api_success(self) -> None:
        """Call on every successful API call. Resets failure counter."""
        self._circuit_failures = 0

    def record_api_failure(self) -> None:
        """Call on every API error. Increments failure counter."""
        self._circuit_failures += 1
        log.warning("SSDH circuit breaker: %d consecutive failures", self._circuit_failures)

    # =========================================================================
    # Trailing stop
    # =========================================================================

    def check_trailing_stop(self, session: dict) -> Tuple[bool, str]:
        """
        Returns (triggered, reason).
        Only fires when peak_net_pnl > 0 (never fire if never profitable).
        Triggers if: (net_pnl / peak_net_pnl) < (1 - trailing_stop_pct)
        """
        try:
            peak    = float(session.get('peak_net_pnl', 0.0))
            if peak <= 0:
                return False, ''

            net     = float(session.get('net_pnl', 0.0))
            pct     = float(session['params'].get('trailing_stop_pct', 0.50))
            floor   = peak * (1 - pct)

            if net < floor:
                return True, f"trailing stop: net_pnl {net:.4f} < floor {floor:.4f} (peak {peak:.4f} × {1-pct:.0%})"
            return False, ''
        except Exception as e:
            log.error("check_trailing_stop error: %s", e)
            return False, ''

    # =========================================================================
    # Vega spike detector
    # =========================================================================

    def check_vega_spike(self, session: dict, current_spot: float = None) -> Tuple[bool, str]:
        """
        Returns (spiking, reason).
        Computes avg(ce_ratio, pe_ratio) for SHORT legs only.
        Returns spiking=True if ratio > vega_exit_multiplier AND
        abs(spot_now - spot_at_entry) / spot_at_entry < 1%
        (Pure vega expansion — not directional move.)
        """
        try:
            from .ssdh_state import get_positions_by_type, DIR_SHORT

            multiplier = float(session['params'].get('vega_exit_multiplier', 1.5))
            ce_shorts  = get_positions_by_type(session, DIR_SHORT, 'CE')
            pe_shorts  = get_positions_by_type(session, DIR_SHORT, 'PE')

            ratios = []
            for pos in ce_shorts + pe_shorts:
                if pos.get('current_premium') is None:
                    continue
                entry = float(pos['entry_premium'])
                cur   = float(pos['current_premium'])
                if entry > 0:
                    ratios.append(cur / entry)

            if not ratios:
                return False, ''

            avg_ratio = sum(ratios) / len(ratios)
            if avg_ratio <= multiplier:
                return False, ''

            # Check if move is directional (> 1% spot move)
            spot_entry = session.get('spot_at_entry')
            if spot_entry and current_spot:
                spot_move = abs(current_spot - float(spot_entry)) / float(spot_entry)
                if spot_move >= 0.01:
                    return False, f'directional move {spot_move:.1%} — not pure vega'

            return True, f"vega spike: avg_ratio {avg_ratio:.2f} > multiplier {multiplier:.2f}"
        except Exception as e:
            log.error("check_vega_spike error: %s", e)
            return False, ''
