"""
MMM WebSocket — Money Mind & Method

WebSocket event emission for real-time UI updates.
Maps to MONEY_POWER_CALCULATION_LOGIC.md Section 6.4: Push to WebUI.

Created: February 15, 2026
"""

import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone

log = logging.getLogger('mmm_websocket')

# SocketIO instance — set during init
_socketio = None

# Fix #17: Track emission failures for staleness detection
_consecutive_failures = 0
_last_successful_emit = None
_FAILURE_THRESHOLD = 10  # After N consecutive failures, flag as stale

# M-2 fix: lock protecting _consecutive_failures and _last_successful_emit
# which are read/written from multiple monitor threads concurrently.
_ws_lock = threading.Lock()


def init_websocket(socketio):
    """Initialize WebSocket with the Flask-SocketIO instance."""
    global _socketio
    _socketio = socketio
    log.info("MMM WebSocket initialized")


def get_ws_health() -> Dict:
    """
    Return WebSocket health metrics. Fix #17.
    Called by safety checks or API to detect UI staleness.
    M-2 fix: reads counters under lock for thread-safe snapshot.
    """
    with _ws_lock:
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
        # H-2 fix: replaced print() with log.error() (no sys.stderr, no flush= I/O block)
        # M-2 fix: counter update under lock
        with _ws_lock:
            _consecutive_failures += 1
        log.error(f"_socketio is None! Cannot emit {event}")
        return

    try:
        payload = dict(data)
        payload.setdefault('timestamp', datetime.now(timezone.utc).isoformat())
        _socketio.emit(event, payload, namespace='/')
        # M-2 fix: success resets under lock
        with _ws_lock:
            _consecutive_failures = 0
            _last_successful_emit = datetime.now(timezone.utc)
    except Exception as e:
        # M-2 fix: failure increment under lock; read count for logging outside lock
        with _ws_lock:
            _consecutive_failures += 1
            current_failures = _consecutive_failures
        # H-2 fix: replaced print() with log.error()
        log.error(f"Failed to emit {event}: {e} (consecutive_failures={current_failures})")
        if current_failures == _FAILURE_THRESHOLD:
            log.critical(
                f"WebSocket stale! {_FAILURE_THRESHOLD} consecutive emission failures. "
                "UI may be out of sync with algo state."
            )


def emit_heartbeat(session_id: str, ce_premium: float, pe_premium: float,
                   ce_trigger: float, pe_trigger: float, status: str,
                   total_pnl: float, realized_pnl: float,
                   premium_map: Dict = None,
                   adaptive_tier: str = None,
                   wind_down_active: bool = False,
                   portfolio_delta: float = 0,
                   margin_data: Dict = None,
                   regime_data: Dict = None,
                   perp_hedge_data: Dict = None,
                   effective_interval: int = None,
                   next_heartbeat: str = None,
                   breakeven_data: Dict = None,
                   gamma_data: Dict = None,
                   data_confidence: float = None,
                   awaiting_user_action: bool = False,
                   awaiting_user_action_details: Dict = None,
                   reverse_data: Dict = None):
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
        perp_hedge_data: Optional perp delta hedge snapshot (lots, pnl, last_delta, etc.)
        effective_interval: Actual heartbeat interval in seconds (after adaptive/theta scaling)
        next_heartbeat: ISO timestamp of next scheduled heartbeat
        breakeven_data: Optional breakeven band snapshot (zone, distances, multiplier, etc.)
        gamma_data: Optional gamma detector snapshot (zone, boundaries, severity, etc.)
        reverse_data: Optional session['_reverse'] snapshot for live panel updates.
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
        'effective_interval': effective_interval,
        'next_heartbeat': next_heartbeat,
    }
    if margin_data:
        payload['margin'] = margin_data
    if regime_data:
        payload['regime'] = regime_data
    if perp_hedge_data:
        payload['perp_hedge'] = perp_hedge_data
    if breakeven_data:
        payload['breakeven'] = breakeven_data
    if gamma_data:
        payload['gamma'] = gamma_data
    if data_confidence is not None:
        payload['data_confidence'] = round(data_confidence, 3)
    if awaiting_user_action:
        payload['awaiting_user_action'] = True
        payload['awaiting_user_action_details'] = awaiting_user_action_details or {}
    if reverse_data:
        payload['_reverse'] = reverse_data
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
                    unrealized: float, fees: float, premium_collected: float,
                    net_premium_collected: float = None,
                    ce_net_premium: float = None,
                    pe_net_premium: float = None):
    """Emit P&L update. Every interval."""
    payload = {
        'session_id': session_id,
        'total_pnl': total_pnl,
        'realized': realized,
        'unrealized': unrealized,
        'fees': fees,
        'premium_collected': premium_collected,
    }
    if net_premium_collected is not None:
        payload['net_premium_collected'] = round(net_premium_collected, 6)
    if ce_net_premium is not None:
        payload['ce_net_premium'] = round(ce_net_premium, 6)
    if pe_net_premium is not None:
        payload['pe_net_premium'] = round(pe_net_premium, 6)
    _emit('mmm_pnl_update', payload)


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


def emit_heartbeat_summary(session_id: str, summary: Dict):
    """Emit a compact heartbeat summary for the live monitor panel.

    This replaces the flood of per-heartbeat log_activity calls with a single
    structured event the frontend can render as a live status dashboard.

    Args:
        session_id: Session identifier
        summary: Dict with keys:
            heartbeat_num, latency_ms, health_grade, status,
            ce_strike, ce_premium, ce_trigger_pct, pe_strike, pe_premium,
            pe_trigger_pct, net_pnl, realized_pnl, unrealized_pnl,
            portfolio_delta, next_interval, next_heartbeat,
            wind_down_active, regime_action, margin_tier,
            adaptive_tier, outcome, circuit_state
    """
    _emit('mmm_heartbeat_summary', {
        'session_id': session_id,
        **summary,
    })


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


def emit_perp_hedge_execution(session_id: str, action: str, lots: int,
                               fill_price: float, effective_delta: float,
                               target_lots: int, current_lots: int,
                               realized_pnl: float, unrealized_pnl: float):
    """Emit perp hedge execution event. Fix #26."""
    _emit('mmm_perp_hedge_execution', {
        'session_id': session_id,
        'action': action,         # 'buy' or 'sell'
        'lots': lots,
        'fill_price': fill_price,
        'effective_delta': effective_delta,
        'target_lots': target_lots,
        'current_lots': current_lots,
        'realized_pnl': realized_pnl,
        'unrealized_pnl': unrealized_pnl,
    })


def emit_perp_hedge_update(session_id: str, perp_summary: Dict):
    """Emit perp hedge state update (e.g., after mark P&L refresh). Fix #26."""
    _emit('mmm_perp_hedge_update', {
        'session_id': session_id,
        **perp_summary,
    })


def emit_harvest(session_id: str, side: str, strike: float,
                 lots: int, realized_pnl: float, close_premium: float,
                 profit_pct: float, harvest_score: float,
                 asymmetry_boosted: bool = False):
    """Emit M1 profit harvest event."""
    _emit('mmm_harvest', {
        'session_id': session_id,
        'side': side,
        'strike': strike,
        'lots': lots,
        'realized_pnl': realized_pnl,
        'close_premium': close_premium,
        'profit_pct': profit_pct,
        'harvest_score': harvest_score,
        'asymmetry_boosted': asymmetry_boosted,
    })


def emit_recycle(session_id: str, hedge_side: str,
                 recycled_lots: int, new_lots_sold: int,
                 old_strike: float, new_strike: float,
                 new_premium: float, net_lot_gain: int,
                 buyback_cost: float, phase_a_pnl: float):
    """Emit M2 lot recycling event."""
    _emit('mmm_recycle', {
        'session_id': session_id,
        'hedge_side': hedge_side,
        'recycled_lots': recycled_lots,
        'new_lots_sold': new_lots_sold,
        'old_strike': old_strike,
        'new_strike': new_strike,
        'new_premium': new_premium,
        'net_lot_gain': net_lot_gain,
        'buyback_cost': buyback_cost,
        'phase_a_pnl': phase_a_pnl,
    })


def emit_scale_up(session_id: str, lots: int,
                  ce_strike: float, ce_premium: float,
                  pe_strike: float, pe_premium: float,
                  scale_count: int):
    """Emit FSU scale-up event."""
    _emit('mmm_scale_up', {
        'session_id': session_id,
        'lots': lots,
        'ce_strike': ce_strike,
        'ce_premium': ce_premium,
        'pe_strike': pe_strike,
        'pe_premium': pe_premium,
        'scale_count': scale_count,
    })


def emit_atm_shield(session_id: str, data: dict):
    """Emit ATM Shield fire event to connected clients."""
    _emit('mmm_atm_shield', {'session_id': session_id, **data})


def emit_perp_hedge_flip(session_id: str, old_direction: str,
                         new_direction: str, lots_closed: int,
                         new_lots: int, realized_pnl: float,
                         fill_price: float):
    """Emit perp position direction flip event. Fix #26."""
    _emit('mmm_perp_hedge_flip', {
        'session_id': session_id,
        'old_direction': old_direction,   # 'long' or 'short'
        'new_direction': new_direction,   # 'long' or 'short'
        'lots_closed': lots_closed,
        'new_lots': new_lots,             # signed new position
        'realized_pnl': realized_pnl,
        'fill_price': fill_price,
    })


def emit_to_session(session_id: str, event: str, data: Dict):
    """Generic per-session emit. Merges session_id into payload.

    Used by route handlers that need to emit a custom event without
    having a dedicated typed emit function.
    """
    _emit(event, {'session_id': session_id, **data})


def emit_manual_injection(session_id: str, side: str, lots: int,
                          strike: float, fill_price: float, order_id: str):
    """Emit operator position injection event."""
    _emit('mmm_manual_injection', {
        'session_id': session_id,
        'side': side,
        'lots': lots,
        'strike': strike,
        'fill_price': fill_price,
        'order_id': order_id,
    })


def emit_breakeven(session_id: str, breakeven_data: Dict):
    """Emit breakeven band status for real-time UI updates."""
    _emit('mmm_breakeven', {
        'session_id': session_id,
        **breakeven_data,
    })


def emit_gamma(session_id: str, gamma_data: Dict):
    """Emit gamma detector result as standalone event."""
    _emit('mmm_gamma', {
        'session_id': session_id,
        **gamma_data,
    })


# ── Reverse Mode Events ───────────────────────────────────────────────────────
# Note: these signatures match the call sites in mmm_reverse.py exactly.

def emit_reverse_entry(session_id: str, reverse_state: Dict, position: Dict):
    """Emit when a reverse mode position is opened.

    Args:
        session_id: session ID string
        reverse_state: session['_reverse'] dict (slots, counts, etc.)
        position: the new position dict (side, strike, lots, entry_premium, ...)
    """
    _emit('mmm_reverse_entry', {
        'session_id':    session_id,
        'reverse_state': reverse_state,
        'position':      position,
        'timestamp':     datetime.now(timezone.utc).isoformat(),
    })


def emit_reverse_closed(session_id: str, reverse_state: Dict, position: Dict, reason: str):
    """Emit when a reverse mode position is closed.

    Args:
        session_id: session ID string
        reverse_state: session['_reverse'] dict
        position: the closed position dict (includes realized_pnl)
        reason: close reason string
    """
    _emit('mmm_reverse_closed', {
        'session_id':    session_id,
        'reverse_state': reverse_state,
        'position':      position,
        'reason':        reason,
        'timestamp':     datetime.now(timezone.utc).isoformat(),
    })


def emit_reverse_status(session_id: str, reverse_state: Dict):
    """Emit current reverse mode state (on enable/disable or per heartbeat when active)."""
    _emit('mmm_reverse_status', {
        'session_id':    session_id,
        'reverse_state': reverse_state,
        'timestamp':     datetime.now(timezone.utc).isoformat(),
    })


def emit_reverse_disabled(session_id: str, reason: str):
    """Emit when reverse mode is auto-disabled by safety logic."""
    _emit('mmm_reverse_disabled', {
        'session_id': session_id,
        'reason':     reason,
        'timestamp':  datetime.now(timezone.utc).isoformat(),
    })
