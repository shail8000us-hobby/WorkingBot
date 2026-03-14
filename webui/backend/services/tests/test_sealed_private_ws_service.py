"""
Contract Test: start_private_ws_service
========================================
SEALED — v1.0.0 — March 14, 2026
Protocol: AI_SEAL.md

Locks the known-good event-routing behaviour of start_private_ws_service
in delta_private_websocket.py.

Contracts locked:
  1. Missing credentials → returns None (never starts subprocess)
  2. Valid credentials → creates DeltaPrivateWebSocket and calls start()
  3. order_filled SocketIO event emitted when order state=closed/reason=fill
  4. pending_orders_updated emitted for ANY order state change
  5. order_filled NOT emitted for non-fill order events
  6. positions_updated SocketIO event emitted when position changes

Run with:
    python3 -m pytest webui/backend/services/tests/test_sealed_private_ws_service.py -v
Or all sealed:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.sealed


def _capture_callbacks(api_key='key', api_secret='secret'):
    """
    Helper: calls start_private_ws_service with mocked subprocess start.
    Returns (result, on_order_update_fn, on_position_update_fn, socketio_mock).
    """
    from webui.backend.services.delta_private_websocket import (
        start_private_ws_service, DeltaPrivateWebSocket
    )
    socketio = MagicMock()
    captured = {}

    original_init = DeltaPrivateWebSocket.__init__

    def fake_init(self, on_order_update=None, on_position_update=None):
        original_init(self, on_order_update=on_order_update,
                      on_position_update=on_position_update)
        captured['on_order_update'] = on_order_update
        captured['on_position_update'] = on_position_update

    with patch.object(DeltaPrivateWebSocket, '__init__', fake_init), \
         patch.object(DeltaPrivateWebSocket, 'start'):
        result = start_private_ws_service(socketio, api_key, api_secret)

    return result, captured.get('on_order_update'), captured.get('on_position_update'), socketio


# ---------------------------------------------------------------------------
# CONTRACT 1 — No credentials → returns None, never starts subprocess
# ---------------------------------------------------------------------------

def test_returns_none_when_api_key_missing():
    from webui.backend.services.delta_private_websocket import start_private_ws_service
    assert start_private_ws_service(MagicMock(), '', 'secret') is None


def test_returns_none_when_api_secret_missing():
    from webui.backend.services.delta_private_websocket import start_private_ws_service
    assert start_private_ws_service(MagicMock(), 'key', '') is None


def test_returns_none_when_both_missing():
    from webui.backend.services.delta_private_websocket import start_private_ws_service
    assert start_private_ws_service(MagicMock(), '', '') is None


# ---------------------------------------------------------------------------
# CONTRACT 2 — Valid credentials → service starts with correct key/secret
# ---------------------------------------------------------------------------

def test_starts_service_with_valid_credentials():
    from webui.backend.services.delta_private_websocket import (
        start_private_ws_service, DeltaPrivateWebSocket
    )
    socketio = MagicMock()
    with patch.object(DeltaPrivateWebSocket, 'start') as mock_start:
        result = start_private_ws_service(socketio, 'MY_KEY', 'MY_SECRET')
        assert result is not None
        mock_start.assert_called_once_with('MY_KEY', 'MY_SECRET')


# ---------------------------------------------------------------------------
# CONTRACT 3 — Fill event (state=closed, reason=fill) → order_filled emitted
# ---------------------------------------------------------------------------

def test_order_filled_emitted_on_fill_state_closed():
    """state=closed + reason=fill must emit order_filled SocketIO event."""
    _, on_order_update, _, socketio = _capture_callbacks()
    on_order_update({
        'state': 'closed', 'reason': 'fill',
        'symbol': 'C-BTC-72400-140326', 'order_id': 999, 'timestamp': 1.0
    })
    emitted = [c[0][0] for c in socketio.emit.call_args_list]
    assert 'order_filled' in emitted


def test_order_filled_emitted_on_reason_filled():
    """reason=filled (alternate form) must also emit order_filled."""
    _, on_order_update, _, socketio = _capture_callbacks()
    on_order_update({
        'state': 'filled', 'reason': 'filled',
        'symbol': 'P-BTC-71600-140326', 'order_id': 123, 'timestamp': 1.0
    })
    emitted = [c[0][0] for c in socketio.emit.call_args_list]
    assert 'order_filled' in emitted


# ---------------------------------------------------------------------------
# CONTRACT 4 — Any order change → pending_orders_updated always emitted
# ---------------------------------------------------------------------------

def test_pending_orders_updated_on_fill():
    """Fill events must emit pending_orders_updated in addition to order_filled."""
    _, on_order_update, _, socketio = _capture_callbacks()
    on_order_update({
        'state': 'closed', 'reason': 'fill',
        'symbol': 'C-BTC-72400-140326', 'order_id': 1, 'timestamp': 1.0
    })
    emitted = [c[0][0] for c in socketio.emit.call_args_list]
    assert 'pending_orders_updated' in emitted


def test_pending_orders_updated_on_new_open_order():
    """New limit order (state=open) must emit pending_orders_updated."""
    _, on_order_update, _, socketio = _capture_callbacks()
    on_order_update({
        'state': 'open', 'reason': '',
        'symbol': 'C-BTC-73000-140326', 'order_id': 42, 'timestamp': 1.0
    })
    emitted = [c[0][0] for c in socketio.emit.call_args_list]
    assert 'pending_orders_updated' in emitted


def test_pending_orders_updated_on_cancelled():
    """Cancelled order must emit pending_orders_updated."""
    _, on_order_update, _, socketio = _capture_callbacks()
    on_order_update({
        'state': 'cancelled', 'reason': 'user',
        'symbol': 'C-BTC-73000-140326', 'order_id': 42, 'timestamp': 1.0
    })
    emitted = [c[0][0] for c in socketio.emit.call_args_list]
    assert 'pending_orders_updated' in emitted


# ---------------------------------------------------------------------------
# CONTRACT 5 — Non-fill order events must NOT emit order_filled
# ---------------------------------------------------------------------------

def test_order_filled_not_emitted_for_open_order():
    """state=open (limit placed, not filled) must NOT emit order_filled."""
    _, on_order_update, _, socketio = _capture_callbacks()
    on_order_update({
        'state': 'open', 'reason': '',
        'symbol': 'C-BTC-73000-140326', 'order_id': 77, 'timestamp': 1.0
    })
    emitted = [c[0][0] for c in socketio.emit.call_args_list]
    assert 'order_filled' not in emitted


def test_order_filled_not_emitted_for_cancelled():
    """Cancelled orders must NOT emit order_filled."""
    _, on_order_update, _, socketio = _capture_callbacks()
    on_order_update({
        'state': 'cancelled', 'reason': 'user',
        'symbol': 'C-BTC-73000-140326', 'order_id': 77, 'timestamp': 1.0
    })
    emitted = [c[0][0] for c in socketio.emit.call_args_list]
    assert 'order_filled' not in emitted


# ---------------------------------------------------------------------------
# CONTRACT 6 — Position change → positions_updated emitted
# ---------------------------------------------------------------------------

def test_positions_updated_emitted_on_position_change():
    """Position update from exchange must emit positions_updated SocketIO event."""
    _, _, on_position_update, socketio = _capture_callbacks()
    on_position_update({
        'symbol': 'C-BTC-72400-140326', 'size': 651, 'timestamp': 1.0
    })
    emitted = [c[0][0] for c in socketio.emit.call_args_list]
    assert 'positions_updated' in emitted
