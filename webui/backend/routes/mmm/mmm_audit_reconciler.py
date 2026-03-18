"""
MMM Audit Reconciler

Compares position_audit_log totals against live session state to detect
any discrepancy between what the bot recorded and what the DB says happened.

Called on-demand via REST API. Never runs in the heartbeat loop.

Created: 2026-03-18
"""

import logging
from typing import Dict, List

log = logging.getLogger('mmm_audit_reconciler')

LOT_SIZE_BTC = 0.001
_PNL_TOLERANCE = 0.005   # $0.005 tolerance — rounding only


def reconcile_session(session_id: str, session: Dict) -> Dict:
    """
    Compare audit log totals against live session state.

    Checks:
      1. Realized P&L: audit SUM(realized_pnl_usd) vs session['realized_pnl']
      2. Open qty: per-strike audit open_qty vs positions[] lots in session state

    Args:
        session_id: session ID string
        session:    live session dict from mmm_storage

    Returns:
        {
            session_id       : str,
            is_clean         : bool,  — True if both checks pass
            pnl_ok           : bool,
            pnl_audit        : float, — USD
            pnl_session      : float, — USD
            pnl_delta        : float,
            position_discrepancies: list of {side, strike, audit_open_qty, session_lots, delta},
            trade_count      : int,   — total audit rows for session
            summary          : list,  — get_strike_summary() rows
            error            : str,   — only present if query failed
        }
    """
    try:
        from .mmm_audit_log import get_audit_log
    except Exception as e:
        return {'session_id': session_id, 'is_clean': False, 'error': str(e)}

    try:
        aud = get_audit_log()
        summary = aud.get_strike_summary(session_id)
        attribution = aud.get_pnl_attribution(session_id)
        trade_count = aud.get_trade_count(session_id)

        # ── Check 1: Realized P&L ─────────────────────────────────────────
        audit_pnl = attribution.get('total_realized_pnl_usd', 0.0) or 0.0
        session_pnl = float(session.get('realized_pnl', 0.0) or 0.0)
        pnl_delta = abs(audit_pnl - session_pnl)
        pnl_ok = pnl_delta <= _PNL_TOLERANCE

        # ── Check 2: Open qty per strike ──────────────────────────────────
        discrepancies: List[Dict] = []

        for row in summary:
            if row.get('option_type') not in ('CE', 'PE'):
                continue
            side = 'ce' if row['option_type'] == 'CE' else 'pe'
            strike_val = float(row.get('strike', 0) or 0)
            audit_open = int(row.get('open_qty', 0) or 0)

            # Count lots in session positions[] at this strike
            side_state = session.get(side, {})
            session_lots = 0
            for pos in side_state.get('positions', []):
                if (
                    pos.get('status') in ('active', 'shifted')
                    and abs(float(pos.get('strike', 0) or 0) - strike_val) < 1.0
                ):
                    session_lots += int(pos.get('lots', 0) or 0)

            if audit_open != session_lots:
                discrepancies.append({
                    'side':           side.upper(),
                    'strike':         int(strike_val),
                    'audit_open_qty': audit_open,
                    'session_lots':   session_lots,
                    'delta':          audit_open - session_lots,
                })

        is_clean = pnl_ok and len(discrepancies) == 0

        return {
            'session_id':              session_id,
            'is_clean':                is_clean,
            'pnl_ok':                  pnl_ok,
            'pnl_audit':               round(audit_pnl, 6),
            'pnl_session':             round(session_pnl, 6),
            'pnl_delta':               round(pnl_delta, 6),
            'pnl_tolerance':           _PNL_TOLERANCE,
            'position_discrepancies':  discrepancies,
            'trade_count':             trade_count,
            'summary':                 summary,
            'attribution':             attribution,
        }

    except Exception as e:
        log.exception('reconcile_session failed for %s', session_id)
        return {
            'session_id': session_id,
            'is_clean':   False,
            'error':      str(e),
        }
