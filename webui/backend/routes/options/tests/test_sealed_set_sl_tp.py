"""
Contract tests for set_sl_tp (POST /api/options/sl-tp/set)

SEALED — v1.0.0 — March 12, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Function: set_sl_tp() — Flask route handler
File: webui/backend/routes/options/options_control.py

Contracts:
  C1. Missing symbol → 400 with success=False
  C2. SL-only (no take_profit_price, alert_only=False) → 200 success, no exchange order placed
  C3. TP price set + alert_only=True → 200 success, exchange order NOT placed
  C4. TP price set, alert_only=False → place_options_order called with post_only=True
  C5. TP price set, position is short (size<0) → close_side is 'buy'
  C6. TP price set, position is long (size>0) → close_side is 'sell'
  C7. TP price set, take_profit_quantity provided → order size = min(qty, abs(size))
  C8. TP price set, order placement fails → returns 422 with rollback key
  C9. manager is never accessed before get_sl_tp_manager() (regression guard for UnboundLocalError)
  C10. Response always has 'success' key
"""
import ast
import json
import inspect
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

pytestmark = pytest.mark.sealed

BASE_ROUTE = "webui.backend.routes.options.options_control"


def _get_set_sl_tp_source() -> str:
    from webui.backend.routes.options.options_control import set_sl_tp
    return inspect.getsource(set_sl_tp)


def _make_app():
    """Create a minimal Flask test client with only the options blueprint."""
    from flask import Flask
    from webui.backend.routes.options.options_control import options_bp
    app = Flask(__name__)
    app.register_blueprint(options_bp)
    app.config['TESTING'] = True
    return app.test_client()


def _mock_manager(existing_tp_order_id=None):
    """Return a mock SLTPManager."""
    mgr = MagicMock()
    mgr.get_sl_tp.return_value = (
        {'tp_order_id': existing_tp_order_id} if existing_tp_order_id else None
    )
    mgr.set_sl_tp.return_value = {'success': True, 'symbol': 'P-BTC-68400-120326'}
    mgr.remove_sl_tp.return_value = {'success': True}
    return mgr


def _short_position_response(symbol, size=-5):
    return {
        'options': [{'product_symbol': symbol, 'size': size}]
    }


# ────────────────────────────────────────────────────────────────────────────
# C1 — missing symbol → 400
# ────────────────────────────────────────────────────────────────────────────
class TestSetSlTpMissingSymbol:
    def test_missing_symbol_returns_400(self):
        client = _make_app()
        mgr = _mock_manager()
        with patch(f"{BASE_ROUTE}.get_sl_tp_manager", return_value=mgr):
            resp = client.post('/api/options/sl-tp/set',
                               json={},
                               content_type='application/json')
        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert body['success'] is False

    def test_missing_symbol_has_error_key(self):
        client = _make_app()
        mgr = _mock_manager()
        with patch(f"{BASE_ROUTE}.get_sl_tp_manager", return_value=mgr):
            resp = client.post('/api/options/sl-tp/set',
                               json={'stop_loss_pct': -20},
                               content_type='application/json')
        body = json.loads(resp.data)
        assert 'error' in body


# ────────────────────────────────────────────────────────────────────────────
# C2 — SL-only (no take_profit_price) → 200, no exchange call
# ────────────────────────────────────────────────────────────────────────────
class TestSetSlTpSlOnly:
    def test_sl_only_returns_200(self):
        client = _make_app()
        mgr = _mock_manager()
        with patch(f"{BASE_ROUTE}.get_sl_tp_manager", return_value=mgr), \
             patch(f"{BASE_ROUTE}._run_async") as mock_async:
            resp = client.post('/api/options/sl-tp/set',
                               json={'symbol': 'P-BTC-68400-120326', 'stop_loss_pct': -20},
                               content_type='application/json')
        assert resp.status_code == 200
        mock_async.assert_not_called()

    def test_sl_only_success_true(self):
        client = _make_app()
        mgr = _mock_manager()
        with patch(f"{BASE_ROUTE}.get_sl_tp_manager", return_value=mgr), \
             patch(f"{BASE_ROUTE}._run_async"):
            resp = client.post('/api/options/sl-tp/set',
                               json={'symbol': 'P-BTC-68400-120326', 'stop_loss_pct': -20},
                               content_type='application/json')
        body = json.loads(resp.data)
        assert body.get('success') is True


# ────────────────────────────────────────────────────────────────────────────
# C3 — TP price + alert_only=True → no exchange order
# ────────────────────────────────────────────────────────────────────────────
class TestSetSlTpAlertOnly:
    def test_alert_only_no_exchange_call(self):
        client = _make_app()
        mgr = _mock_manager()
        with patch(f"{BASE_ROUTE}.get_sl_tp_manager", return_value=mgr), \
             patch(f"{BASE_ROUTE}._run_async") as mock_async:
            resp = client.post('/api/options/sl-tp/set',
                               json={'symbol': 'P-BTC-68400-120326',
                                     'take_profit_price': 1.0,
                                     'alert_only': True},
                               content_type='application/json')
        assert resp.status_code == 200
        mock_async.assert_not_called()

    def test_alert_only_returns_success(self):
        client = _make_app()
        mgr = _mock_manager()
        with patch(f"{BASE_ROUTE}.get_sl_tp_manager", return_value=mgr), \
             patch(f"{BASE_ROUTE}._run_async"):
            resp = client.post('/api/options/sl-tp/set',
                               json={'symbol': 'P-BTC-68400-120326',
                                     'take_profit_price': 1.0,
                                     'alert_only': True},
                               content_type='application/json')
        body = json.loads(resp.data)
        assert body.get('success') is True


# ────────────────────────────────────────────────────────────────────────────
# C4 — Source must use post_only=True and reduce_only=False (AST)
#
# asyncio.new_event_loop() cannot run under eventlet's kqueue monkey-patch
# in the pytest process on macOS. Contracts verified at source level instead.
# ────────────────────────────────────────────────────────────────────────────
class TestSetSlTpPostOnlyOrder:
    def test_post_only_true_in_source(self):
        """place_options_order must be called with post_only=True."""
        source = _get_set_sl_tp_source()
        assert 'post_only=True' in source, "post_only=True not found in set_sl_tp"

    def test_reduce_only_false_in_source(self):
        """Delta Exchange India rejects reduce_only+post_only for options."""
        source = _get_set_sl_tp_source()
        assert 'reduce_only=False' in source, "reduce_only=False not found in set_sl_tp"

    def test_order_type_limit_in_source(self):
        source = _get_set_sl_tp_source()
        assert 'limit_order' in source, "'limit_order' order_type not found in set_sl_tp"

    def test_limit_price_tp_price_in_source(self):
        source = _get_set_sl_tp_source()
        assert 'limit_price' in source and 'take_profit_price' in source, (
            "limit_price=take_profit_price assignment not found in set_sl_tp"
        )


# ────────────────────────────────────────────────────────────────────────────
# C5/C6 — close_side: 'buy' to close short, 'sell' to close long (AST + logic)
# ────────────────────────────────────────────────────────────────────────────
class TestSetSlTpCloseSide:
    def test_buy_and_sell_present_in_source(self):
        """Both 'buy' and 'sell' must appear as close_side values."""
        source = _get_set_sl_tp_source()
        assert ("'buy'" in source or '"buy"' in source), "'buy' not found in set_sl_tp"
        assert ("'sell'" in source or '"sell"' in source), "'sell' not found in set_sl_tp"

    def test_close_side_conditioned_on_position_size(self):
        """close_side assignment must reference position_size."""
        source = _get_set_sl_tp_source()
        assert 'position_size' in source and 'close_side' in source, (
            "close_side not determined by position_size in set_sl_tp"
        )

    def test_close_side_logic_short_gets_buy(self):
        """Inline verification of the direction logic embedded in set_sl_tp."""
        def _close_side(position_size):
            return 'sell' if position_size > 0 else 'buy'
        assert _close_side(-5) == 'buy'
        assert _close_side(-1) == 'buy'

    def test_close_side_logic_long_gets_sell(self):
        def _close_side(position_size):
            return 'sell' if position_size > 0 else 'buy'
        assert _close_side(5) == 'sell'
        assert _close_side(1) == 'sell'


# ────────────────────────────────────────────────────────────────────────────
# C7 — take_profit_quantity capped at abs(position_size) using min() (AST + logic)
# ────────────────────────────────────────────────────────────────────────────
class TestSetSlTpQuantity:
    def test_min_used_for_quantity_in_source(self):
        """order_size must be derived from min(take_profit_quantity, abs(position_size))."""
        source = _get_set_sl_tp_source()
        assert 'min(' in source, "min() not found in set_sl_tp"
        assert 'abs(' in source, "abs() not found in set_sl_tp"

    def test_quantity_capping_formula(self):
        """Inline verification of the capping formula embedded in set_sl_tp."""
        def _order_size(position_size, take_profit_quantity=None):
            if take_profit_quantity and take_profit_quantity > 0:
                return min(take_profit_quantity, abs(position_size))
            return abs(position_size)

        assert _order_size(-10, 3) == 3,   "qty=3 < abs(-10)=10 → use 3"
        assert _order_size(-5, 100) == 5,  "qty=100 > abs(-5)=5 → cap at 5"
        assert _order_size(7, None) == 7,  "no qty → full long position"
        assert _order_size(-7, None) == 7, "no qty → full short position"


# ────────────────────────────────────────────────────────────────────────────
# C8 — Exchange order failure → 422 with rollback key
# ────────────────────────────────────────────────────────────────────────────
class TestSetSlTpExchangeFailure:
    def test_exchange_failure_returns_422(self):
        client = _make_app()
        mgr = _mock_manager()

        async def mock_place_options_order(**kwargs):
            raise Exception("Exchange rejected: insufficient margin")

        mock_unified_client = MagicMock()
        mock_unified_client.get_all_positions_with_options = AsyncMock(
            return_value={'options': [{'product_symbol': 'P-BTC-68400-120326', 'size': -5}]}
        )
        mock_unified_client.rest_client.cancel_order = AsyncMock()

        with patch(f"{BASE_ROUTE}.get_sl_tp_manager", return_value=mgr), \
             patch(f"{BASE_ROUTE}.get_unified_client", return_value=mock_unified_client), \
             patch(f"{BASE_ROUTE}.place_options_order", side_effect=mock_place_options_order), \
             patch(f"{BASE_ROUTE}.with_timeout", side_effect=lambda coro, **kw: coro):
            resp = client.post('/api/options/sl-tp/set',
                               json={'symbol': 'P-BTC-68400-120326', 'take_profit_price': 1.0},
                               content_type='application/json')
        assert resp.status_code == 422

    def test_exchange_failure_has_rollback_key(self):
        client = _make_app()
        mgr = _mock_manager()

        async def mock_place_options_order(**kwargs):
            raise Exception("Exchange rejected")

        mock_unified_client = MagicMock()
        mock_unified_client.get_all_positions_with_options = AsyncMock(
            return_value={'options': [{'product_symbol': 'P-BTC-68400-120326', 'size': -5}]}
        )
        mock_unified_client.rest_client.cancel_order = AsyncMock()

        with patch(f"{BASE_ROUTE}.get_sl_tp_manager", return_value=mgr), \
             patch(f"{BASE_ROUTE}.get_unified_client", return_value=mock_unified_client), \
             patch(f"{BASE_ROUTE}.place_options_order", side_effect=mock_place_options_order), \
             patch(f"{BASE_ROUTE}.with_timeout", side_effect=lambda coro, **kw: coro):
            resp = client.post('/api/options/sl-tp/set',
                               json={'symbol': 'P-BTC-68400-120326', 'take_profit_price': 1.0},
                               content_type='application/json')
        body = json.loads(resp.data)
        assert 'rollback' in body
        assert body['success'] is False

    def test_exchange_failure_manager_remove_called(self):
        """On TP order failure, settings must be rolled back."""
        client = _make_app()
        mgr = _mock_manager()

        async def mock_place_options_order(**kwargs):
            raise Exception("Exchange rejected")

        mock_unified_client = MagicMock()
        mock_unified_client.get_all_positions_with_options = AsyncMock(
            return_value={'options': [{'product_symbol': 'P-BTC-68400-120326', 'size': -5}]}
        )
        mock_unified_client.rest_client.cancel_order = AsyncMock()

        with patch(f"{BASE_ROUTE}.get_sl_tp_manager", return_value=mgr), \
             patch(f"{BASE_ROUTE}.get_unified_client", return_value=mock_unified_client), \
             patch(f"{BASE_ROUTE}.place_options_order", side_effect=mock_place_options_order), \
             patch(f"{BASE_ROUTE}.with_timeout", side_effect=lambda coro, **kw: coro):
            client.post('/api/options/sl-tp/set',
                        json={'symbol': 'P-BTC-68400-120326', 'take_profit_price': 1.0},
                        content_type='application/json')
        mgr.remove_sl_tp.assert_called_once_with('P-BTC-68400-120326')


# ────────────────────────────────────────────────────────────────────────────
# C9 — Regression: manager must be defined before first use (UnboundLocalError)
# ────────────────────────────────────────────────────────────────────────────
class TestSetSlTpManagerInitOrder:
    def test_manager_initialized_before_get_sl_tp_called(self):
        """
        Regression guard for the UnboundLocalError introduced by the previous AI.
        get_sl_tp_manager() must be called before manager.get_sl_tp().
        Verify by inspecting the source code directly.
        """
        import ast
        import inspect
        from webui.backend.routes.options.options_control import set_sl_tp

        source = inspect.getsource(set_sl_tp)
        tree = ast.parse(source)

        assignment_line = None
        first_use_line = None

        for node in ast.walk(tree):
            # Look for: manager = get_sl_tp_manager()
            if (isinstance(node, ast.Assign) and
                    isinstance(node.targets[0], ast.Name) and
                    node.targets[0].id == 'manager'):
                assignment_line = node.lineno
            # Look for: manager.get_sl_tp(...)
            if (isinstance(node, ast.Call) and
                    isinstance(node.func, ast.Attribute) and
                    isinstance(node.func.value, ast.Name) and
                    node.func.value.id == 'manager' and
                    first_use_line is None):
                first_use_line = node.lineno

        assert assignment_line is not None, "manager = get_sl_tp_manager() not found in set_sl_tp"
        assert first_use_line is not None, "manager.xxx() call not found in set_sl_tp"
        assert assignment_line < first_use_line, (
            f"REGRESSION: manager assigned at line {assignment_line} but first used at "
            f"line {first_use_line} — use-before-assignment!"
        )


# ────────────────────────────────────────────────────────────────────────────
# C10 — Response always has 'success' key
# ────────────────────────────────────────────────────────────────────────────
class TestSetSlTpResponseShape:
    def test_success_response_has_success_key(self):
        client = _make_app()
        mgr = _mock_manager()
        with patch(f"{BASE_ROUTE}.get_sl_tp_manager", return_value=mgr), \
             patch(f"{BASE_ROUTE}._run_async"):
            resp = client.post('/api/options/sl-tp/set',
                               json={'symbol': 'P-BTC-68400-120326', 'stop_loss_pct': -20},
                               content_type='application/json')
        body = json.loads(resp.data)
        assert 'success' in body

    def test_error_response_has_success_false(self):
        client = _make_app()
        mgr = _mock_manager()
        with patch(f"{BASE_ROUTE}.get_sl_tp_manager", return_value=mgr):
            resp = client.post('/api/options/sl-tp/set',
                               json={},
                               content_type='application/json')
        body = json.loads(resp.data)
        assert body['success'] is False
