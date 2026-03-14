"""
Contract tests for execute_single_order

SEALED — v1.0.0 — March 4, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Function: execute_single_order(client, order_data, order_preference, index)
File: webui/backend/routes/options/batch_add_endpoint.py

Contracts:
  - Returns dict with 'success' key always
  - On error: returns success=False with symbol, size, side, index, error preserved
  - On success: returns success=True with symbol, execution_type, fill_price, order_id, index
  - size is cast to float from order_data
  - index is always propagated to the result
"""
import asyncio
import selectors
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.sealed

BASE_PATH = "webui.backend.routes.options.options_control"


def _run(coro):
    """Run async coroutine using SelectSelector to avoid eventlet kqueue conflict on macOS."""
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


from webui.backend.routes.options.batch_add_endpoint import execute_single_order


class TestExecuteSingleOrderErrorPath:

    def test_returns_success_false_on_validate_failure(self):
        order_data = {"symbol": "C-BTC-100000-300126", "size": 1, "side": "buy"}
        with patch(f"{BASE_PATH}.validate_order_size", new=AsyncMock(side_effect=Exception("Invalid size"))):
            result = _run(execute_single_order(MagicMock(), order_data, "market_only", 0))
        assert result["success"] is False

    def test_error_symbol_propagated(self):
        order_data = {"symbol": "C-ETH-2000-300126", "size": 2, "side": "sell"}
        with patch(f"{BASE_PATH}.validate_order_size", new=AsyncMock(side_effect=Exception("test"))):
            result = _run(execute_single_order(None, order_data, "market_only", 3))
        assert result["symbol"] == "C-ETH-2000-300126"
        assert result["side"] == "sell"
        assert result["index"] == 3

    def test_error_message_captured_in_result(self):
        order_data = {"symbol": "X", "size": 1, "side": "buy"}
        with patch(f"{BASE_PATH}.validate_order_size", new=AsyncMock(side_effect=Exception("margin too low"))):
            result = _run(execute_single_order(None, order_data, "market_only", 0))
        assert "margin too low" in result["error"]

    def test_size_float_cast(self):
        order_data = {"symbol": "S", "size": "3.5", "side": "buy"}
        with patch(f"{BASE_PATH}.validate_order_size", new=AsyncMock(side_effect=Exception("test"))):
            result = _run(execute_single_order(None, order_data, "market_only", 0))
        assert result["size"] == 3.5

    def test_index_zero_propagated(self):
        order_data = {"symbol": "S", "size": 1, "side": "buy"}
        with patch(f"{BASE_PATH}.validate_order_size", new=AsyncMock(side_effect=Exception("err"))):
            result = _run(execute_single_order(None, order_data, "maker_first", 0))
        assert result["index"] == 0


class TestExecuteSingleOrderSuccessPath:

    def _mock_success(self, exec_type="market", fill_price=100.0, order_id="ord-1"):
        return {
            "execution_type": exec_type,
            "fill_price": fill_price,
            "id": order_id,
        }

    def test_returns_success_true_when_order_fills(self):
        order_data = {"symbol": "C-BTC-120000-300126", "size": 1, "side": "buy"}
        mock_result = self._mock_success()
        with patch(f"{BASE_PATH}.validate_order_size", new=AsyncMock(return_value=None)), \
             patch(f"{BASE_PATH}.place_smart_order", new=AsyncMock(return_value=mock_result)), \
             patch(f"{BASE_PATH}.with_timeout", new=AsyncMock(return_value=mock_result)):
            result = _run(execute_single_order(MagicMock(), order_data, "market_only", 0))
        assert result["success"] is True

    def test_success_has_all_required_keys(self):
        order_data = {"symbol": "C-BTC-120000-300126", "size": 1, "side": "buy"}
        mock_result = self._mock_success()
        with patch(f"{BASE_PATH}.validate_order_size", new=AsyncMock(return_value=None)), \
             patch(f"{BASE_PATH}.place_smart_order", new=AsyncMock(return_value=mock_result)), \
             patch(f"{BASE_PATH}.with_timeout", new=AsyncMock(return_value=mock_result)):
            result = _run(execute_single_order(MagicMock(), order_data, "market_only", 2))
        for key in ("success", "symbol", "size", "side", "execution_type", "fill_price", "order_id", "index"):
            assert key in result, f"Missing key: {key}"

    def test_order_id_mapped_from_id(self):
        order_data = {"symbol": "C-BTC-120000-300126", "size": 1, "side": "buy"}
        mock_result = self._mock_success(order_id="abc-xyz")
        with patch(f"{BASE_PATH}.validate_order_size", new=AsyncMock(return_value=None)), \
             patch(f"{BASE_PATH}.place_smart_order", new=AsyncMock(return_value=mock_result)), \
             patch(f"{BASE_PATH}.with_timeout", new=AsyncMock(return_value=mock_result)):
            result = _run(execute_single_order(MagicMock(), order_data, "market_only", 0))
        assert result["order_id"] == "abc-xyz"

    def test_correct_index_in_success(self):
        order_data = {"symbol": "S", "size": 1, "side": "sell"}
        mock_result = self._mock_success()
        with patch(f"{BASE_PATH}.validate_order_size", new=AsyncMock(return_value=None)), \
             patch(f"{BASE_PATH}.place_smart_order", new=AsyncMock(return_value=mock_result)), \
             patch(f"{BASE_PATH}.with_timeout", new=AsyncMock(return_value=mock_result)):
            result = _run(execute_single_order(MagicMock(), order_data, "market_only", 7))
        assert result["index"] == 7
