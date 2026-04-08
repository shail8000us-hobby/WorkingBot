"""
MMMX WebSocket — Event Emission

All events are prefixed mmmx_* (never mmm_*).
Spec: MMMX_IMPLEMENTATION_PLAN.md Section 1 (mmmx_websocket.py).

Usage:
    from .mmmx_websocket import init_websocket, emit_heartbeat, emit_safety
    init_websocket(socketio)
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .mmmx_constants import WS_EVENT_PREFIX

log = logging.getLogger('mmmx_websocket')

_socketio = None
_consecutive_failures = 0
_last_successful_emit: Optional[datetime] = None
_FAILURE_THRESHOLD = 10
_ws_lock = threading.Lock()


def init_websocket(socketio) -> None:
    """Call once on backend startup with the Flask-SocketIO instance."""
    global _socketio
    _socketio = socketio
    log.info("MMMX WebSocket initialized")


def get_ws_health() -> Dict[str, Any]:
    """Return WebSocket health snapshot (thread-safe)."""
    with _ws_lock:
        return {
            'consecutive_failures':  _consecutive_failures,
            'last_successful_emit':  _last_successful_emit.isoformat() if _last_successful_emit else None,
            'is_stale':              _consecutive_failures >= _FAILURE_THRESHOLD,
            'socketio_initialized':  _socketio is not None,
        }


def _emit(event: str, data: Dict[str, Any]) -> None:
    """
    Emit a WebSocket event. Tracks consecutive failures for stale detection.
    All events automatically get a UTC timestamp injected.
    """
    global _consecutive_failures, _last_successful_emit

    if _socketio is None:
        with _ws_lock:
            _consecutive_failures += 1
        log.error(f"_socketio is None — cannot emit {event}")
        return

    try:
        data['timestamp'] = datetime.now(timezone.utc).isoformat()
        _socketio.emit(event, data, namespace='/')
        with _ws_lock:
            _consecutive_failures = 0
            _last_successful_emit = datetime.now(timezone.utc)
    except Exception as exc:
        with _ws_lock:
            _consecutive_failures += 1
            current = _consecutive_failures
        log.error(f"Failed to emit {event}: {exc} (failures={current})")
        if current == _FAILURE_THRESHOLD:
            log.critical(
                f"MMMX WebSocket stale — {_FAILURE_THRESHOLD} consecutive failures. "
                "UI may be out of sync."
            )


# ── Typed emitters ─────────────────────────────────────────────────────────────

def emit_heartbeat(
    session_id: str,
    beat_number: int,
    status: str,
    portfolio_pnl: float,
    portfolio_delta: float,
    hard_stop_usd: float,
    tranches_deployed: int,
    tranches_remaining: int,
    total_premium_collected: float,
    active_hedges: int,
    whipsaw_score: int,
    next_heartbeat: Optional[str] = None,
    extra: Optional[Dict] = None,
) -> None:
    """Emit per-beat heartbeat summary to the frontend."""
    payload: Dict[str, Any] = {
        'session_id':              session_id,
        'beat_number':             beat_number,
        'status':                  status,
        'portfolio_pnl':           portfolio_pnl,
        'portfolio_delta':         portfolio_delta,
        'hard_stop_usd':           hard_stop_usd,
        'tranches_deployed':       tranches_deployed,
        'tranches_remaining':      tranches_remaining,
        'total_premium_collected': total_premium_collected,
        'active_hedges':           active_hedges,
        'whipsaw_score':           whipsaw_score,
        'next_heartbeat':          next_heartbeat,
    }
    if extra:
        payload.update(extra)
    _emit('mmmx_heartbeat', payload)


def emit_safety(
    session_id: str,
    safety_type: str,
    level: str,
    message: str,
    details: Optional[Dict] = None,
) -> None:
    """
    Emit a safety event (hard stop, shield, naked position, stale monitor, etc.).

    safety_type: 'hard_stop'|'dte_close'|'atm_shield'|'naked_position'|
                 'stale_monitor'|'generation_guard'|'circuit_breaker'|...
    level: 'info'|'warning'|'error'|'critical'
    """
    _emit('mmmx_safety', {
        'session_id': session_id,
        'type':       safety_type,
        'level':      level,
        'message':    message,
        'details':    details or {},
    })


def emit_status_change(
    session_id: str,
    old_status: str,
    new_status: str,
    reason: str = '',
) -> None:
    _emit('mmmx_status_change', {
        'session_id': session_id,
        'old_status': old_status,
        'new_status': new_status,
        'reason':     reason,
    })


def emit_session_created(session_id: str, summary: Dict) -> None:
    _emit('mmmx_session_created', {'session_id': session_id, 'summary': summary})


def emit_session_stopped(session_id: str, reason: str = '') -> None:
    _emit('mmmx_session_stopped', {'session_id': session_id, 'reason': reason})


def emit_kill_switch_progress(
    correlation_id: str,
    scope: str,
    stage: str,
    status: str,
    session_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Emit kill-switch lifecycle progress for deterministic operator feedback.

    Stages:
      - accepted      (request accepted)
      - session_result (per-session stop result)
      - completed     (aggregate summary)
    """
    payload: Dict[str, Any] = {
        'correlation_id': correlation_id,
        'scope': scope,
        'stage': stage,
        'status': status,
    }
    if session_id:
        payload['session_id'] = session_id
    if details:
        payload['details'] = details
    _emit('mmmx_kill_switch_progress', payload)


def emit_tranche_deployed(
    session_id: str,
    tranche_id,
    ce_strike: float,
    pe_strike: float,
    ce_premium: float,
    pe_premium: float,
    lots: int,
    total_deployed_lots: int,
) -> None:
    _emit('mmmx_tranche_deployed', {
        'session_id':          session_id,
        'tranche_id':          str(tranche_id),
        'ce_strike':           ce_strike,
        'pe_strike':           pe_strike,
        'ce_premium':          ce_premium,
        'pe_premium':          pe_premium,
        'lots':                lots,
        'total_deployed_lots': total_deployed_lots,
    })


def emit_tranche_closed(
    session_id: str,
    tranche_id,
    reason: str,
    realized_pnl: float,
) -> None:
    _emit('mmmx_tranche_closed', {
        'session_id':  session_id,
        'tranche_id':  str(tranche_id),
        'reason':      reason,
        'realized_pnl': realized_pnl,
    })


def emit_atm_shield(session_id: str, data: Dict) -> None:
    _emit('mmmx_atm_shield', {'session_id': session_id, **data})


def emit_hedge_executed(session_id: str, hedge_id: str, data: Dict) -> None:
    _emit('mmmx_hedge_executed', {'session_id': session_id, 'hedge_id': hedge_id, **data})


def emit_pnl_update(
    session_id: str,
    portfolio_pnl: float,
    hard_stop_usd: float,
    total_premium_collected: float,
    profit_booked_total: float,
    total_hedge_cost_paid: float,
) -> None:
    _emit('mmmx_pnl_update', {
        'session_id':              session_id,
        'portfolio_pnl':           portfolio_pnl,
        'hard_stop_usd':           hard_stop_usd,
        'total_premium_collected': total_premium_collected,
        'profit_booked_total':     profit_booked_total,
        'total_hedge_cost_paid':   total_hedge_cost_paid,
    })


def emit_params_changed(session_id: str, diff: Dict) -> None:
    _emit('mmmx_params_changed', {'session_id': session_id, 'diff': diff})


def emit_deployment_queue(session_id: str, queue_data: Dict) -> None:
    """Emit deployment queue status (populated/cleared/deployed)."""
    _emit('mmmx_deployment_queue', {'session_id': session_id, **queue_data})


def emit_whipsaw_update(session_id: str, score: int, level: str) -> None:
    _emit('mmmx_whipsaw', {
        'session_id': session_id,
        'score':      score,
        'level':      level,
    })


def emit_circuit_breaker(session_id: str, old_state: str, new_state: str) -> None:
    _emit('mmmx_circuit_breaker', {
        'session_id': session_id,
        'old_state':  old_state,
        'new_state':  new_state,
    })


def emit_naked_position(session_id: str, tranche_id, side: str, since: str) -> None:
    _emit('mmmx_naked_position', {
        'session_id': session_id,
        'tranche_id': str(tranche_id),
        'side':       side,
        'since':      since,
    })


def emit_trigger_evaluation(
    session_id: str,
    beat_number: int,
    status: str,
    winner: Optional[Dict[str, Any]],
    ladder: list,
    metrics: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Emit full trigger evaluation ladder for operator explainability.

    winner: TriggerHit serialized dict or None.
    ladder: ordered rows with trigger_name/status/reason/priority.
    """
    payload: Dict[str, Any] = {
        'session_id': session_id,
        'beat_number': beat_number,
        'status': status,
        'winner': winner,
        'ladder': ladder or [],
    }
    if metrics is not None:
        payload['metrics'] = metrics
    _emit('mmmx_trigger_evaluation', payload)


def _order_payload_base(
    session_id: str,
    symbol: str,
    side: str,
    requested_size: int,
    mode: str,
    attempt: int,
    client_order_id: str,
    tranche_id: Any = None,
    action: str = 'TRADE',
) -> Dict[str, Any]:
    """Build common payload shape for granular order lifecycle events."""
    return {
        'session_id': session_id or '',
        'tranche_id': str(tranche_id) if tranche_id is not None else None,
        'action': action,
        'symbol': symbol,
        'side': side,
        'requested_size': int(requested_size or 0),
        'mode': mode,
        'attempt': int(attempt or 0),
        'client_order_id': client_order_id or '',
    }


def emit_order_intent(
    session_id: str,
    symbol: str,
    side: str,
    requested_size: int,
    mode: str,
    attempt: int,
    client_order_id: str,
    tranche_id: Any = None,
    action: str = 'TRADE',
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _order_payload_base(
        session_id=session_id,
        symbol=symbol,
        side=side,
        requested_size=requested_size,
        mode=mode,
        attempt=attempt,
        client_order_id=client_order_id,
        tranche_id=tranche_id,
        action=action,
    )
    if extra:
        payload.update(extra)
    _emit('mmmx_order_intent', payload)


def emit_order_ack(
    session_id: str,
    symbol: str,
    side: str,
    requested_size: int,
    mode: str,
    attempt: int,
    client_order_id: str,
    order_id: str,
    tranche_id: Any = None,
    action: str = 'TRADE',
    price: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _order_payload_base(
        session_id=session_id,
        symbol=symbol,
        side=side,
        requested_size=requested_size,
        mode=mode,
        attempt=attempt,
        client_order_id=client_order_id,
        tranche_id=tranche_id,
        action=action,
    )
    payload['order_id'] = order_id
    if price is not None:
        payload['price'] = float(price)
    if extra:
        payload.update(extra)
    _emit('mmmx_order_ack', payload)


def emit_order_partial(
    session_id: str,
    symbol: str,
    side: str,
    requested_size: int,
    mode: str,
    attempt: int,
    client_order_id: str,
    order_id: str,
    filled_size: int,
    residual_size: int,
    tranche_id: Any = None,
    action: str = 'TRADE',
    avg_price: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _order_payload_base(
        session_id=session_id,
        symbol=symbol,
        side=side,
        requested_size=requested_size,
        mode=mode,
        attempt=attempt,
        client_order_id=client_order_id,
        tranche_id=tranche_id,
        action=action,
    )
    payload.update({
        'order_id': order_id,
        'filled_size': int(filled_size or 0),
        'residual_size': int(residual_size or 0),
    })
    if avg_price is not None:
        payload['avg_price'] = float(avg_price)
    if extra:
        payload.update(extra)
    _emit('mmmx_order_partial', payload)


def emit_order_retry(
    session_id: str,
    symbol: str,
    side: str,
    requested_size: int,
    mode: str,
    attempt: int,
    client_order_id: str,
    reason_code: str,
    reason: str,
    tranche_id: Any = None,
    action: str = 'TRADE',
    order_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _order_payload_base(
        session_id=session_id,
        symbol=symbol,
        side=side,
        requested_size=requested_size,
        mode=mode,
        attempt=attempt,
        client_order_id=client_order_id,
        tranche_id=tranche_id,
        action=action,
    )
    payload.update({
        'reason_code': reason_code,
        'reason': reason,
    })
    if order_id:
        payload['order_id'] = order_id
    if extra:
        payload.update(extra)
    _emit('mmmx_order_retry', payload)


def emit_order_filled(
    session_id: str,
    symbol: str,
    side: str,
    requested_size: int,
    mode: str,
    attempt: int,
    client_order_id: str,
    order_id: str,
    filled_size: int,
    residual_size: int,
    avg_price: float,
    tranche_id: Any = None,
    action: str = 'TRADE',
    fees_paid: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _order_payload_base(
        session_id=session_id,
        symbol=symbol,
        side=side,
        requested_size=requested_size,
        mode=mode,
        attempt=attempt,
        client_order_id=client_order_id,
        tranche_id=tranche_id,
        action=action,
    )
    payload.update({
        'order_id': order_id,
        'filled_size': int(filled_size or 0),
        'residual_size': int(residual_size or 0),
        'avg_price': float(avg_price or 0.0),
    })
    if fees_paid is not None:
        payload['fees_paid'] = float(fees_paid)
    if extra:
        payload.update(extra)
    _emit('mmmx_order_filled', payload)


def emit_order_failed(
    session_id: str,
    symbol: str,
    side: str,
    requested_size: int,
    mode: str,
    attempt: int,
    client_order_id: str,
    reason_code: str,
    reason: str,
    tranche_id: Any = None,
    action: str = 'TRADE',
    order_id: Optional[str] = None,
    filled_size: Optional[int] = None,
    residual_size: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _order_payload_base(
        session_id=session_id,
        symbol=symbol,
        side=side,
        requested_size=requested_size,
        mode=mode,
        attempt=attempt,
        client_order_id=client_order_id,
        tranche_id=tranche_id,
        action=action,
    )
    payload.update({
        'reason_code': reason_code,
        'reason': reason,
    })
    if order_id:
        payload['order_id'] = order_id
    if filled_size is not None:
        payload['filled_size'] = int(filled_size)
    if residual_size is not None:
        payload['residual_size'] = int(residual_size)
    if extra:
        payload.update(extra)
    _emit('mmmx_order_failed', payload)
