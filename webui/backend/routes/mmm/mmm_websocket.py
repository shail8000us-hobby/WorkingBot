"""
MMM WebSocket — Money Mind & Method

WebSocket event emission for real-time UI updates.
Maps to MONEY_POWER_CALCULATION_LOGIC.md Section 6.4: Push to WebUI.

Created: February 15, 2026
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

log = logging.getLogger('mmm_websocket')

# SocketIO instance — set during init
_socketio = None

# Fix #17: Track emission failures for staleness detection
_consecutive_failures = 0
_last_successful_emit = None
_FAILURE_THRESHOLD = 10  # After N consecutive failures, flag as stale


def init_websocket(socketio):
    """Initialize WebSocket with the Flask-SocketIO instance."""
    global _socketio
    _socketio = socketio
    log.info("MMM WebSocket initialized")


def get_ws_health() -> Dict:
    """
    Return WebSocket health metrics. Fix #17.
    Called by safety checks or API to detect UI staleness.
    """
    return {
        'consecutive_failures': _consecutive_failures,
        'last_successful_emit': _last_successful_emit.isoformat() if _last_successful_emit else None,
        'is_stale': _consecutive_failures >= _FAILURE_THRESHOLD,
        'socketio_initialized': _socketio is not None,
    }


def _emit(event: str, data: Dict[str, Any]):
    """
    Emit a WebSocket event.

    Args:
        event: Event name (prefixed with 'mmm_')
        data: Event payload

    Fix #17: Tracks consecutive failures. After _FAILURE_THRESHOLD consecutive
    failures, get_ws_health() reports is_stale=True so callers can warn user.
    """
    global _consecutive_failures, _last_successful_emit

    if _socketio is None:
        _consecutive_failures += 1
        log.debug(f"WebSocket not initialized, skipping emit: {event}")
        if 'price_tick' in event:
            import sys
            print(f"[MMM WS] _socketio is None! Cannot emit {event}", flush=True, file=sys.stderr)
        return

    try:
        data['timestamp'] = datetime.utcnow().isoformat()
        _socketio.emit(event, data, namespace='/')
        _consecutive_failures = 0
        _last_successful_emit = datetime.utcnow()
    except Exception as e:
        _consecutive_failures += 1
        log.error(f"Failed to emit {event}: {e} (consecutive_failures={_consecutive_failures})")
        if _consecutive_failures == _FAILURE_THRESHOLD:
            log.critical(
                f"WebSocket stale! {_FAILURE_THRESHOLD} consecutive emission failures. "
                "UI may be out of sync with algo state."
            )
        if 'price_tick' in event:
            import sys
            print(f"[MMM WS] Failed to emit {event}: {e}", flush=True, file=sys.stderr)


def emit_heartbeat(session_id: str, ce_premium: float, pe_premium: float,
                   ce_trigger: float, pe_trigger: float, status: str,
                   total_pnl: float, realized_pnl: float,
                   premium_map: Dict = None,
                   adaptive_tier: str = None,
                   wind_down_active: bool = False,
                   portfolio_delta: float = 0,
                   margin_data: Dict = None,
                   regime_data: Dict = None):
    """Emit heartbeat data every interval. Section 4.

    Args:
        premium_map: Dict mapping "strike:option_type" to current mark price.
                     Includes ALL strikes with open positions (active + frozen).
                     e.g. {"69600:call": 72.85, "68400:call": 303.5, "68000:put": 96.5}
        adaptive_tier: Label of the current adaptive interval tier (e.g. "10-20h (0.50x)")
        wind_down_active: Whether wind-down mode is currently active
        portfolio_delta: Portfolio delta (monitoring only, no trading impact)
        margin_data: Optional margin guardian snapshot (tier, utilization_pct, etc.)
        regime_data: Optional regime controls snapshot (vol/gamma/trend regimes + action)
    """
    payload = {
        'session_id': session_id,
        'ce_premium': ce_premium,
        'pe_premium': pe_premium,
        'ce_trigger': ce_trigger,
        'pe_trigger': pe_trigger,
        'status': status,
        'total_pnl': total_pnl,
        'realized_pnl': realized_pnl,
        'premium_map': premium_map or {},
        'adaptive_tier': adaptive_tier,
        'wind_down_active': wind_down_active,
        'portfolio_delta': portfolio_delta,
    }
    if margin_data:
        payload['margin'] = margin_data
    if regime_data:
        payload['regime'] = regime_data
    _emit('mmm_heartbeat', payload)


def emit_price_tick(session_id: str, premium_map: Dict):
    """Emit lightweight price-only tick every 5 seconds for real-time UI updates.

    This runs independently of the 5-minute heartbeat/adjustment loop.
    Contains only session_id and the premium_map, no trigger or PnL data.
    """
    _emit('mmm_price_tick', {
        'session_id': session_id,
        'premium_map': premium_map,
    })


def emit_adjustment(session_id: str, side: str, lots: int, premium: float,
                    strike: float, loss_covered: float, adj_type: str,
                    adjustment_count: int):
    """Emit adjustment event. Section 5-6."""
    _emit('mmm_adjustment', {
        'session_id': session_id,
        'side': side,
        'lots': lots,
        'premium': premium,
        'strike': strike,
        'loss_covered': loss_covered,
        'type': adj_type,  # 'standard', 'reversal', 'first_reversal'
        'adjustment_count': adjustment_count,
    })


def emit_reversal(session_id: str, from_side: str, to_side: str,
                  adjustment_pnl: float, action: str):
    """Emit reversal detection event. Section 9."""
    _emit('mmm_reversal', {
        'session_id': session_id,
        'from_side': from_side,
        'to_side': to_side,
        'adjustment_pnl': adjustment_pnl,
        'action': action,  # 'hedge', 'skip_profitable', 'cooldown'
    })


def emit_strike_shift(session_id: str, side: str, old_strike: float,
                      new_strike: float, frozen_lots: int, new_premium: float):
    """Emit strike shift event. Section 10."""
    _emit('mmm_shift', {
        'session_id': session_id,
        'side': side,
        'old_strike': old_strike,
        'new_strike': new_strike,
        'frozen_lots': frozen_lots,
        'new_premium': new_premium,
    })


def emit_close_at_5(session_id: str, side: str, strike: float,
                    lots: int, realized_pnl: float, close_premium: float):
    """Emit close-at-5 event. Section 11."""
    _emit('mmm_close_at_5', {
        'session_id': session_id,
        'side': side,
        'strike': strike,
        'lots': lots,
        'realized_pnl': realized_pnl,
        'close_premium': close_premium,
    })


def emit_both_sides_alert(session_id: str, ce_premium: float, pe_premium: float,
                          ce_trigger: float, pe_trigger: float,
                          ce_excess: float, pe_excess: float):
    """Emit both-sides-up alert. Section 8."""
    _emit('mmm_both_sides', {
        'session_id': session_id,
        'ce_premium': ce_premium,
        'pe_premium': pe_premium,
        'ce_trigger': ce_trigger,
        'pe_trigger': pe_trigger,
        'ce_excess': ce_excess,
        'pe_excess': pe_excess,
    })


def emit_safety(session_id: str, safety_type: str, level: str, message: str,
                details: Dict = None):
    """
    Emit safety mechanism event. Section 13-14.

    Args:
        safety_type: 'position_cap', 'max_adjustments', 'max_loss', 'whipsaw',
                     'asymmetry', 'near_expiry', 'margin', 'pnl_guardrail',
                     'trailing_stop'
        level: 'warning', 'alert', 'critical'
        message: Human-readable message
        details: Optional extra data
    """
    _emit('mmm_safety', {
        'session_id': session_id,
        'type': safety_type,
        'level': level,
        'message': message,
        'details': details or {},
    })


def emit_pnl_update(session_id: str, total_pnl: float, realized: float,
                    unrealized: float, fees: float, premium_collected: float):
    """Emit P&L update. Every interval."""
    _emit('mmm_pnl_update', {
        'session_id': session_id,
        'total_pnl': total_pnl,
        'realized': realized,
        'unrealized': unrealized,
        'fees': fees,
        'premium_collected': premium_collected,
    })


def emit_params_changed(session_id: str, changed_params: Dict):
    """Emit parameter hot-reload event. Section 19."""
    _emit('mmm_params_changed', {
        'session_id': session_id,
        'changed_params': changed_params,
    })


def emit_status_change(session_id: str, old_status: str, new_status: str,
                       reason: str = ''):
    """Emit strategy status change."""
    _emit('mmm_status_change', {
        'session_id': session_id,
        'old_status': old_status,
        'new_status': new_status,
        'reason': reason,
    })


def emit_session_created(session_id: str, session_summary: Dict):
    """Emit new session created event."""
    _emit('mmm_session_created', {
        'session_id': session_id,
        'summary': session_summary,
    })


def emit_session_deleted(session_id: str):
    """Emit session deleted event."""
    _emit('mmm_session_deleted', {
        'session_id': session_id,
    })


def emit_activity(activity: Dict):
    """Emit a background activity event for real-time UI updates."""
    _emit('mmm_activity', activity)


def emit_regime(session_id: str, regime_status: Dict):
    """
    Emit regime controls status update every heartbeat.

    Args:
        session_id: Session identifier
        regime_status: Full regime status from MMMRegimeEngine.get_regime_status()
            Contains: vol_regime, gamma_regime, trend_regime, regime_action, details
    """
    _emit('mmm_regime', {
        'session_id': session_id,
        **regime_status,
    })


def emit_activities_updated():
    """Emit signal to refresh activities (e.g., after clearing stale progress)."""
    _emit('mmm_activities_updated', {'refresh': True})
