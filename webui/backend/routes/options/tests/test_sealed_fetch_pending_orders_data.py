"""
Contract tests for fetch_pending_orders_data

SEALED — v1.0.0 — March 4, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Function: fetch_pending_orders_data() -> dict
File: webui/backend/routes/options/dashboard_service.py

Contracts:
  - Always returns a dict (never raises)
  - On success: returns dict with success=True and 'orders' key
  - On exception: returns {'success': False, 'orders': [], 'error': <str>}
  - Invalid response type is handled gracefully (returns error dict)
"""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.sealed

from webui.backend.routes.options.dashboard_service import fetch_pending_orders_data


def _make_flask_response(data: dict):
    """Build a minimal mock of a Flask JSON response."""
    m = MagicMock()
    m.get_json.return_value = data
    return m


class TestFetchPendingOrdersDataSuccess:

    def test_returns_dict_always(self):
        mock_resp = _make_flask_response({'success': True, 'orders': [], 'count': 0})
        with patch('webui.backend.routes.positions.get_pending_orders',
                   return_value=(mock_resp, 200)):
            result = fetch_pending_orders_data()
        assert isinstance(result, dict)

    def test_returns_success_true(self):
        mock_resp = _make_flask_response({'success': True, 'orders': [{'id': 1}], 'count': 1})
        with patch('webui.backend.routes.positions.get_pending_orders',
                   return_value=(mock_resp, 200)):
            result = fetch_pending_orders_data()
        assert result['success'] is True

    def test_orders_list_passed_through(self):
        orders = [{'id': 1, 'symbol': 'C-BTC-100000-300126'}]
        mock_resp = _make_flask_response({'success': True, 'orders': orders, 'count': 1})
        with patch('webui.backend.routes.positions.get_pending_orders',
                   return_value=(mock_resp, 200)):
            result = fetch_pending_orders_data()
        assert result['orders'] == orders

    def test_handles_tuple_response(self):
        """get_pending_orders returns (jsonify_resp, status_code) tuple"""
        mock_resp = _make_flask_response({'success': True, 'orders': [], 'count': 0})
        with patch('webui.backend.routes.positions.get_pending_orders',
                   return_value=(mock_resp, 200)):
            result = fetch_pending_orders_data()
        assert 'orders' in result


class TestFetchPendingOrdersDataFailure:

    def test_exception_returns_error_dict(self):
        with patch('webui.backend.routes.positions.get_pending_orders',
                   side_effect=Exception('API down')):
            result = fetch_pending_orders_data()
        assert result['success'] is False
        assert 'API down' in result['error']

    def test_exception_includes_empty_orders(self):
        with patch('webui.backend.routes.positions.get_pending_orders',
                   side_effect=Exception('timeout')):
            result = fetch_pending_orders_data()
        assert result['orders'] == []

    def test_never_raises(self):
        with patch('webui.backend.routes.positions.get_pending_orders',
                   side_effect=RuntimeError('fatal')):
            try:
                result = fetch_pending_orders_data()
                assert result['success'] is False
            except Exception:
                pytest.fail("fetch_pending_orders_data should never raise")
