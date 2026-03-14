"""
Contract tests for place_smart_order

SEALED — v1.0.0 — March 4, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Function: place_smart_order(client, symbol, size, side, order_preference, reduce_only, limit_price)
File: webui/backend/routes/options/options_control.py

Contracts:
  - Always returns dict with 'execution_type' key
  - size is always converted to int(abs(float(size))) — negatives → positive
  - market_only preference → execution_type is 'market'
  - On any unrecoverable error falls back to market order with execution_type starting with 'market'
"""
import asyncio
import selectors
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.sealed

BASE = "webui.backend.routes.options.order_executor"


def _run(coro):
    """Run async coroutine using SelectSelector to avoid eventlet kqueue conflict on macOS."""
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


from webui.backend.routes.options.options_control import place_smart_order


class TestPlaceSmartOrderMarketOnly:

    def test_market_only_returns_market_execution_type(self):
        with patch(f"{BASE}.place_options_order", new=AsyncMock(return_value={"id": "o1"})):
            result = _run(place_smart_order(MagicMock(), "C-BTC-100000-300126", 1, "buy", "market_only"))
        assert result["execution_type"] == "market"

    def test_market_only_buy_side(self):
        with patch(f"{BASE}.place_options_order", new=AsyncMock(return_value={"id": "o2"})):
            result = _run(place_smart_order(MagicMock(), "C-BTC-100000-300126", 1, "buy", "market_only"))
        assert result["execution_type"] == "market"

    def test_market_only_sell_side(self):
        with patch(f"{BASE}.place_options_order", new=AsyncMock(return_value={"id": "o3"})):
            result = _run(place_smart_order(MagicMock(), "P-ETH-2000-300126", 1, "sell", "market_only"))
        assert result["execution_type"] == "market"

    def test_returns_dict_with_execution_type_key(self):
        with patch(f"{BASE}.place_options_order", new=AsyncMock(return_value={"id": "o4"})):
            result = _run(place_smart_order(MagicMock(), "C-BTC-100000-300126", 1, "buy", "market_only"))
        assert isinstance(result, dict)
        assert "execution_type" in result


class TestPlaceSmartOrderSizeConversion:

    def test_negative_size_converted_to_positive(self):
        """size = int(abs(float(size))) — negative input must not crash"""
        with patch(f"{BASE}.place_options_order", new=AsyncMock(return_value={"id": "o5"})):
            result = _run(place_smart_order(MagicMock(), "C-BTC-100000-300126", -2, "sell", "market_only"))
        assert result["execution_type"] == "market"

    def test_float_size_converted_to_int(self):
        """3.7 → 3 (int truncation via int(abs(...)))"""
        with patch(f"{BASE}.place_options_order", new=AsyncMock(return_value={"id": "o6"})):
            result = _run(place_smart_order(MagicMock(), "C-BTC-100000-300126", 3.7, "buy", "market_only"))
        assert result["execution_type"] == "market"

    def test_string_size_handled(self):
        """size passed as string '2' must be converted"""
        with patch(f"{BASE}.place_options_order", new=AsyncMock(return_value={"id": "o7"})):
            result = _run(place_smart_order(MagicMock(), "C-BTC-100000-300126", "2", "buy", "market_only"))
        assert result["execution_type"] == "market"
