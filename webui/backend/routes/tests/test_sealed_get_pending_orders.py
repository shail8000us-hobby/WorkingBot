"""
Contract tests for get_pending_orders

SEALED — v1.0.0 — March 4, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Function: get_pending_orders()
File: webui/backend/routes/positions.py

Contracts:
  - On success: returns JSON with success=True, orders list, count matching len(orders)
  - On circuit breaker open (None): returns 503 with success=False, empty orders
  - On exception: returns 500 with success=False, orders=[], count=0
  - Price for None limit_price is always 0.0 (never crashes on null price)
  - Each formatted order has: id, symbol, product_id, side, size, unfilled_size,
    price, order_type, state, created_at, client_order_id
"""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

pytestmark = pytest.mark.sealed

from webui.backend.routes.positions import positions_bp, get_pending_orders


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(positions_bp)
    app.config['TESTING'] = True
    return app


def _raw_order(symbol='C-BTC-100000-300126', side='buy', limit_price='2500.0',
               order_id=1234, state='open'):
    return {
        'id': order_id,
        'product': {'symbol': symbol},
        'product_id': 99,
        'side': side,
        'size': 1,
        'unfilled_size': 1,
        'limit_price': limit_price,
        'order_type': 'limit_order',
        'state': state,
        'created_at': '2026-03-04T11:14:22Z',
        'client_order_id': None,
    }


class TestGetPendingOrdersSuccess:

    def test_returns_success_true_with_orders(self):
        with _make_app().test_client() as client:
            with patch('webui.backend.utils.circuit_breaker.delta_api_breaker.call',
                       return_value={'success': True, 'result': [_raw_order()]}):
                resp = client.get('/api/positions/pending-orders')
        data = resp.get_json()
        assert data['success'] is True
        assert isinstance(data['orders'], list)
        assert len(data['orders']) == 1

    def test_count_matches_orders_length(self):
        orders = [_raw_order(order_id=i) for i in range(3)]
        with _make_app().test_client() as client:
            with patch('webui.backend.utils.circuit_breaker.delta_api_breaker.call',
                       return_value={'success': True, 'result': orders}):
                resp = client.get('/api/positions/pending-orders')
        data = resp.get_json()
        assert data['count'] == len(data['orders'])

    def test_formatted_order_has_required_keys(self):
        with _make_app().test_client() as client:
            with patch('webui.backend.utils.circuit_breaker.delta_api_breaker.call',
                       return_value={'success': True, 'result': [_raw_order()]}):
                resp = client.get('/api/positions/pending-orders')
        order = resp.get_json()['orders'][0]
        for key in ('id', 'symbol', 'product_id', 'side', 'size', 'price',
                    'order_type', 'state', 'created_at'):
            assert key in order, f"Missing key: {key}"

    def test_null_limit_price_becomes_zero_float(self):
        raw = _raw_order(limit_price=None)
        with _make_app().test_client() as client:
            with patch('webui.backend.utils.circuit_breaker.delta_api_breaker.call',
                       return_value={'success': True, 'result': [raw]}):
                resp = client.get('/api/positions/pending-orders')
        order = resp.get_json()['orders'][0]
        assert order['price'] == 0.0

    def test_price_parsed_as_float(self):
        raw = _raw_order(limit_price='2024.90')
        with _make_app().test_client() as client:
            with patch('webui.backend.utils.circuit_breaker.delta_api_breaker.call',
                       return_value={'success': True, 'result': [raw]}):
                resp = client.get('/api/positions/pending-orders')
        order = resp.get_json()['orders'][0]
        assert order['price'] == 2024.90


class TestGetPendingOrdersFailure:

    def test_circuit_breaker_none_returns_503(self):
        with _make_app().test_client() as client:
            with patch('webui.backend.utils.circuit_breaker.delta_api_breaker.call',
                       return_value=None):
                resp = client.get('/api/positions/pending-orders')
        assert resp.status_code == 503
        data = resp.get_json()
        assert data['success'] is False
        assert data['orders'] == []
        assert data['count'] == 0

    def test_exception_returns_500(self):
        with _make_app().test_client() as client:
            with patch('webui.backend.utils.circuit_breaker.delta_api_breaker.call',
                       side_effect=Exception('network error')):
                resp = client.get('/api/positions/pending-orders')
        assert resp.status_code == 500
        data = resp.get_json()
        assert data['success'] is False
        assert data['orders'] == []
