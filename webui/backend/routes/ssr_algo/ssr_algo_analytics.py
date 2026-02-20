"""
SSR ALGO Analytics & Reporting

Per-session and cross-session analytics:
- Total P&L (realized + unrealized)
- Max drawdown tracking
- Win rate across sessions
- Average theta collected per day
- Execution quality metrics (slippage)
- Delta hedge efficiency

Created: February 20, 2026
Phase 10 of SSR Algo Development Plan
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

log = logging.getLogger('ssr_algo_analytics')


class SSRAnalytics:
    """
    Computes analytics for SSR Algo sessions.

    Calculates per-session metrics and aggregated cross-session statistics.
    """

    def get_session_analytics(self, session: Dict) -> Dict:
        """
        Calculate analytics for a single session.

        Args:
            session: Full session data from storage

        Returns:
            {
                'total_pnl': float,
                'unrealized_pnl': float,
                'realized_pnl': float,
                'net_premium': float,
                'return_on_premium': float,
                'max_drawdown': float,
                'holding_period_hours': float,
                'theta_per_day': float,
                'hedge_count': int,
                'adjustment_count': int,
                'execution_quality': dict,
                'position_count': int,
                'status': str,
                'dte_at_entry': float,
                'current_dte': float,
            }
        """
        live_pnl = session.get('live_pnl', {})
        live_greeks = session.get('live_greeks', {})
        exec_stats = session.get('execution_stats', {})

        unrealized = live_pnl.get('unrealized_pnl', 0)
        realized = live_pnl.get('realized_pnl', 0)
        total_pnl = live_pnl.get('total_pnl', unrealized + realized)
        net_premium = session.get('net_premium', 0)

        # Return on premium
        rop = (total_pnl / net_premium * 100) if net_premium else 0

        # Holding period
        started_at = session.get('started_at')
        stopped_at = session.get('stopped_at')
        holding_hours = 0
        if started_at:
            start = datetime.fromisoformat(started_at) if isinstance(started_at, str) else started_at
            end = datetime.fromisoformat(stopped_at) if stopped_at and isinstance(stopped_at, str) else datetime.utcnow()
            holding_hours = max(0, (end - start).total_seconds() / 3600)

        # Theta per day
        net_theta = live_greeks.get('net_theta', 0)
        theta_per_day = net_theta if net_theta else 0

        # Position count
        positions = session.get('positions', [])
        total_legs = sum(
            len([k for k in pg.keys() if k in ('atm_ce', 'atm_pe', 'otm_ce_buy', 'otm_pe_buy', 'far_otm_ce', 'far_otm_pe')
                 and isinstance(pg.get(k), dict) and not pg.get(k, {}).get('closed', False)])
            for pg in positions
        )

        # DTE
        current_dte = 0
        expiry = session.get('expiry', '')
        if expiry:
            try:
                from .ssr_algo_exit_manager import get_exit_manager
                current_dte = get_exit_manager().calculate_dte(expiry)
            except Exception:
                pass

        # Max drawdown from P&L history (if tracked)
        pnl_history = session.get('pnl_history', [])
        max_drawdown = self._calculate_max_drawdown(pnl_history) if pnl_history else 0

        return {
            'session_id': session.get('session_id', ''),
            'underlying': session.get('underlying', ''),
            'expiry': expiry,
            'status': session.get('status', 'UNKNOWN'),
            'total_pnl': round(total_pnl, 4),
            'unrealized_pnl': round(unrealized, 4),
            'realized_pnl': round(realized, 4),
            'net_premium': round(net_premium, 4),
            'return_on_premium_pct': round(rop, 2),
            'max_drawdown': round(max_drawdown, 4),
            'holding_period_hours': round(holding_hours, 1),
            'theta_per_day': round(theta_per_day, 4),
            'hedge_count': session.get('daily_hedge_count', 0),
            'adjustment_count': session.get('trigger_count', 0),
            'rounds_completed': session.get('rounds_completed', 0),
            'auto_loop_rounds': session.get('auto_loop_rounds', 2),
            'position_count': total_legs,
            'current_dte': round(current_dte, 1),
            'execution_quality': {
                'total_orders': exec_stats.get('total_orders', 0),
                'avg_slippage_pct': exec_stats.get('avg_slippage_pct', 0),
                'maker_fills': exec_stats.get('maker_fills', 0),
                'taker_fills': exec_stats.get('taker_fills', 0),
            },
            'exit_details': session.get('exit_details'),
            'rolled_to': session.get('rolled_to'),
            'rolled_from': session.get('rolled_from'),
        }

    def get_aggregate_analytics(self, sessions: List[Dict]) -> Dict:
        """
        Calculate aggregate analytics across multiple sessions.

        Args:
            sessions: List of session data dicts

        Returns:
            Aggregated metrics across all sessions
        """
        if not sessions:
            return {
                'total_sessions': 0,
                'active_sessions': 0,
                'total_pnl': 0,
                'win_rate': 0,
                'avg_return_on_premium': 0,
                'total_adjustments': 0,
                'total_hedges': 0,
                'avg_holding_hours': 0,
            }

        analytics = [self.get_session_analytics(s) for s in sessions]

        completed = [a for a in analytics if a['status'] in ('STOPPED', 'COMPLETED')]
        active = [a for a in analytics if a['status'] in ('MONITORING', 'EXECUTING_AUTO_LOOP', 'PAUSED')]
        winners = [a for a in completed if a['total_pnl'] > 0]

        total_pnl = sum(a['total_pnl'] for a in analytics)
        total_adjustments = sum(a['adjustment_count'] for a in analytics)
        total_hedges = sum(a['hedge_count'] for a in analytics)
        holding_hours = [a['holding_period_hours'] for a in analytics if a['holding_period_hours'] > 0]
        rops = [a['return_on_premium_pct'] for a in analytics if a['net_premium'] != 0]

        return {
            'total_sessions': len(sessions),
            'active_sessions': len(active),
            'completed_sessions': len(completed),
            'total_pnl': round(total_pnl, 4),
            'win_rate': round(len(winners) / len(completed) * 100, 1) if completed else 0,
            'avg_return_on_premium': round(sum(rops) / len(rops), 2) if rops else 0,
            'best_session_pnl': round(max((a['total_pnl'] for a in analytics), default=0), 4),
            'worst_session_pnl': round(min((a['total_pnl'] for a in analytics), default=0), 4),
            'total_adjustments': total_adjustments,
            'total_hedges': total_hedges,
            'avg_holding_hours': round(sum(holding_hours) / len(holding_hours), 1) if holding_hours else 0,
            'sessions': analytics,
        }

    def _calculate_max_drawdown(self, pnl_history: List) -> float:
        """
        Calculate maximum drawdown from P&L history.

        Args:
            pnl_history: List of P&L values over time

        Returns:
            Maximum drawdown as absolute value
        """
        if not pnl_history or len(pnl_history) < 2:
            return 0

        values = [p.get('total_pnl', 0) if isinstance(p, dict) else p for p in pnl_history]

        peak = values[0]
        max_dd = 0

        for val in values:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd

        return max_dd


# Singleton
_analytics = None

def get_analytics() -> SSRAnalytics:
    """Get singleton SSRAnalytics instance."""
    global _analytics
    if _analytics is None:
        _analytics = SSRAnalytics()
    return _analytics
