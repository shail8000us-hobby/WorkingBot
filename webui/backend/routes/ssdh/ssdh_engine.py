"""
SSDH Engine — P&L Computation, Adaptive Interval, Vega Detection

Stateless — all inputs come from the session dict.
Never touches the exchange or modifies session state except via explicit calls.

Created: March 21, 2026
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional

log = logging.getLogger('ssdh_engine')


class OPTEngine:
    """P&L engine, adaptive heartbeat interval, vega indicator."""

    # =========================================================================
    # Decimal helper
    # =========================================================================

    def _D(self, x) -> Decimal:
        try:
            return Decimal(str(x))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal('0')

    # =========================================================================
    # Premium update
    # =========================================================================

    def update_premiums(self, session: dict, premium_map: Dict[str, Optional[float]]) -> dict:
        """
        Updates current_premium on each active position.
        premium_map: {symbol: float | None}

        If premium is None for a position → mark stale, keep previous value.
        Returns: {'stale_legs': [pos_ids], 'updated_legs': [pos_ids]}
        """
        from .ssdh_state import get_active_positions

        stale   = []
        updated = []

        for pos in get_active_positions(session):
            symbol = pos.get('symbol')
            if not symbol:
                continue

            price = premium_map.get(symbol)
            if price is None:
                stale.append(pos['pos_id'])
                # Do NOT overwrite existing current_premium with None
                # (keeps last known good value for P&L estimate)
            else:
                pos['current_premium'] = float(price)
                updated.append(pos['pos_id'])

        return {'stale_legs': stale, 'updated_legs': updated}

    # =========================================================================
    # P&L store
    # =========================================================================

    def compute_and_store_pnl(self, session: dict) -> None:
        """
        Calls recompute_net_pnl(session) from ssdh_state.
        Updates session net_pnl, unrealized_pnl, peak_net_pnl.
        """
        from .ssdh_state import recompute_net_pnl
        recompute_net_pnl(session)
        # peak_net_pnl is updated inside recompute_net_pnl

    # =========================================================================
    # Adaptive interval
    # =========================================================================

    def compute_adaptive_interval(self, session: dict) -> int:
        """
        Returns heartbeat interval in seconds based on P&L proximity to max_loss.

        pnl_ratio = abs(net_pnl) / max_loss_amount
        < 0.25  → adjustment_interval (default 30s, slow)
        < 0.50  → max(adaptive_min_interval, adjustment_interval // 2)  (medium)
        >= 0.50 → adaptive_min_interval (default 10s, fast)
        """
        params = session.get('params', {})

        if not params.get('adaptive_interval_enabled', True):
            return int(params.get('adjustment_interval', 30))

        net_pnl   = float(session.get('net_pnl', 0.0))
        max_loss  = float(params.get('max_loss_amount', 9999))
        base      = int(params.get('adjustment_interval', 30))
        fast      = int(params.get('adaptive_min_interval', 10))
        slow      = int(params.get('adaptive_max_interval', 60))

        if max_loss <= 0:
            return base

        ratio = abs(net_pnl) / max_loss

        if ratio < 0.25:
            return min(base, slow)
        elif ratio < 0.50:
            return max(fast, base // 2)
        else:
            return fast

    # =========================================================================
    # Vega indicator
    # =========================================================================

    def compute_vega_indicator(self, session: dict) -> dict:
        """
        For SHORT legs only, compute premium inflation ratio:
          ce_ratio = current_ce_premium / entry_ce_premium
          pe_ratio = current_pe_premium / entry_pe_premium
          avg_ratio = (ce_ratio + pe_ratio) / 2

        Returns:
          {
            'avg_ratio':       float,
            'ce_ratio':        float,
            'pe_ratio':        float,
            'spike_detected':  bool,
          }
        """
        from .ssdh_state import get_positions_by_type, DIR_SHORT

        params     = session.get('params', {})
        multiplier = float(params.get('vega_exit_multiplier', 1.5))

        ce_shorts = get_positions_by_type(session, DIR_SHORT, 'CE')
        pe_shorts = get_positions_by_type(session, DIR_SHORT, 'PE')

        def _ratio(positions):
            ratios = []
            for p in positions:
                if p.get('current_premium') is None:
                    continue
                entry = float(p['entry_premium'])
                if entry > 0:
                    ratios.append(float(p['current_premium']) / entry)
            return sum(ratios) / len(ratios) if ratios else 0.0

        ce_ratio = _ratio(ce_shorts)
        pe_ratio = _ratio(pe_shorts)
        avg      = (ce_ratio + pe_ratio) / 2 if (ce_ratio or pe_ratio) else 0.0

        spike = avg > multiplier if avg > 0 else False

        return {
            'avg_ratio':      avg,
            'ce_ratio':       ce_ratio,
            'pe_ratio':       pe_ratio,
            'spike_detected': spike,
        }

    # =========================================================================
    # Time remaining
    # =========================================================================

    def compute_time_remaining(self, session: dict) -> float:
        """Returns seconds remaining in session window. 0 if expired or not started."""
        started = session.get('started_at')
        if not started:
            return 0.0
        try:
            started_dt     = datetime.fromisoformat(started.replace('Z', '+00:00'))
            window_hours   = float(session.get('params', {}).get('session_window_hours', 4.0))
            elapsed        = (datetime.now(timezone.utc) - started_dt).total_seconds()
            remaining      = window_hours * 3600 - elapsed
            return max(0.0, remaining)
        except Exception as e:
            log.warning("compute_time_remaining: %s", e)
            return 0.0
