"""
Contract Tests: TakeProfitMonitor._close_position_with_retry / _close_position
================================================================================
SEALED — v1.0.0 — March 12, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of both order-placement functions inside
TakeProfitMonitor:

  • _close_position_with_retry  — retry wrapper (3 attempts, exponential backoff)
  • _close_position             — actual order placement (MAKER_ONLY, reduce_only,
                                   never market order)

Key contracts:
  1. On success: returns True, calls _close_position exactly once.
  2. On transient failure: retries up to max_retries times, returns False after exhaustion.
  3. On rate-limit: raises internally so retry wrapper can back off.
  4. Order placed is always MAKER_ONLY (never market).
  5. Order side is correct: long position → sell, short position → buy.
  6. Quantity is capped at actual position size (never over-closes).
  7. If position size is 0, _close_position returns early without placing an order.
  8. If position symbol is not found, raises an exception (propagated to retry wrapper).

All tests use MOCK — no live exchange calls.

If any test fails after a code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/options_strategy/tests/test_sealed_take_profit_close.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import asyncio
import selectors
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

pytestmark = pytest.mark.sealed


# ---------------------------------------------------------------------------
# Async helper — avoids kqueue selector bug in Python 3.9 on macOS
# ---------------------------------------------------------------------------

def _run_async_for_test(coro):
    """
    Run an async coroutine synchronously in tests.
    Forces SelectSelector (POSIX select()) instead of default KqueueSelector
    to avoid a Python 3.9 macOS bug where creating a new event loop after
    a previous one leaves kqueue in a broken state.
    """
    loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Helpers — build a minimal TakeProfitMonitor without real DB or API client
# ---------------------------------------------------------------------------

def _make_monitor():
    """Return a TakeProfitMonitor with mocked dependencies."""
    from webui.backend.options_strategy.take_profit_manager import TakeProfitMonitor, TakeProfitManager

    mock_api_client = MagicMock()
    mock_manager = MagicMock(spec=TakeProfitManager)

    monitor = TakeProfitMonitor.__new__(TakeProfitMonitor)
    monitor.api_client = mock_api_client
    monitor.manager = mock_manager
    monitor._lock = __import__('threading').Lock()
    monitor._recently_closed = {}
    monitor._close_cooldown = 60
    monitor._metrics = {"total_checks": 0, "total_triggers": 0, "last_check_at": None}
    monitor._rate_limit_window = 1.0
    monitor._rate_limit_max_calls = 8
    monitor._rate_limit_calls = []
    return monitor


def _long_position(symbol="C-BTC-100000-300126", size=10, pnl=25.0):
    return {"product_symbol": symbol, "size": size, "unrealized_pnl": pnl, "product_id": 42}


def _short_position(symbol="P-BTC-90000-300126", size=-5, pnl=-30.0):
    return {"product_symbol": symbol, "size": size, "unrealized_pnl": pnl, "product_id": 99}


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — _close_position_with_retry returns True on first success
# ---------------------------------------------------------------------------

def test_retry_returns_true_on_success():
    """Must return True when _close_position succeeds on the first attempt."""
    monitor = _make_monitor()
    monitor._close_position = MagicMock()  # succeeds (no exception)

    result = monitor._close_position_with_retry("C-BTC-100000-300126", 25.0, 5, 20.0)

    assert result is True
    monitor._close_position.assert_called_once()


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — _close_position_with_retry retries on transient failure
# ---------------------------------------------------------------------------

def test_retry_retries_on_failure(monkeypatch):
    """Must retry up to max_retries times and return False after exhaustion."""
    monitor = _make_monitor()
    monkeypatch.setattr("time.sleep", lambda _: None)  # speed up test
    monitor._close_position = MagicMock(side_effect=Exception("transient"))

    result = monitor._close_position_with_retry(
        "C-BTC-100000-300126", 25.0, 5, 20.0, max_retries=3
    )

    assert result is False
    assert monitor._close_position.call_count == 3


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — _close_position_with_retry succeeds on second attempt
# ---------------------------------------------------------------------------

def test_retry_succeeds_on_second_attempt(monkeypatch):
    """If first attempt fails but second succeeds, must return True."""
    monitor = _make_monitor()
    monkeypatch.setattr("time.sleep", lambda _: None)
    call_count = {"n": 0}

    def _flaky(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise Exception("temporary error")

    monitor._close_position = MagicMock(side_effect=_flaky)

    result = monitor._close_position_with_retry(
        "C-BTC-100000-300126", 25.0, 5, 20.0, max_retries=3
    )

    assert result is True
    assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — _close_position never places a market order
# ---------------------------------------------------------------------------

def test_close_position_uses_maker_only_never_market():
    """
    CRITICAL: _close_position must use ORDER_TYPE_MAKER_ONLY.
    It must NEVER call place_smart_order with ORDER_TYPE_MARKET_ONLY or
    ORDER_TYPE_MAKER_FIRST.
    """
    monitor = _make_monitor()

    fake_order = {"id": "ord_123", "state": "open"}

    captured_kwargs = {}

    async def fake_place_smart_order(client, symbol, size, side,
                                     order_preference=None, reduce_only=False):
        captured_kwargs['order_preference'] = order_preference
        captured_kwargs['reduce_only'] = reduce_only
        return fake_order

    monitor.api_client.get_all_positions_with_options = AsyncMock(return_value={"options": [_long_position()], "futures": []})

    from webui.backend.routes.options import order_executor
    ORDER_TYPE_MAKER_ONLY = order_executor.ORDER_TYPE_MAKER_ONLY
    ORDER_TYPE_MARKET_ONLY = order_executor.ORDER_TYPE_MARKET_ONLY
    ORDER_TYPE_MAKER_FIRST = order_executor.ORDER_TYPE_MAKER_FIRST

    with patch("routes.options.options_client._run_async", side_effect=_run_async_for_test), \
         patch("webui.backend.options_strategy.take_profit_manager.place_smart_order", fake_place_smart_order), \
         patch("webui.backend.options_strategy.take_profit_manager.ORDER_EXECUTION_AVAILABLE", True):

        monitor._close_position("C-BTC-100000-300126", 25.0, 5, 20.0)

    assert captured_kwargs.get('order_preference') == ORDER_TYPE_MAKER_ONLY, \
        f"Expected MAKER_ONLY but got: {captured_kwargs.get('order_preference')}"
    assert captured_kwargs.get('order_preference') != ORDER_TYPE_MARKET_ONLY, \
        "CRITICAL: market order was placed — this violates the maker-only rule!"
    assert captured_kwargs.get('order_preference') != ORDER_TYPE_MAKER_FIRST, \
        "MAKER_FIRST has a market fallback — must use MAKER_ONLY for TP"


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Long position triggers sell side
# ---------------------------------------------------------------------------

def test_close_position_long_triggers_sell():
    """Long position (size > 0) must place a sell order."""
    monitor = _make_monitor()

    fake_order = {"id": "ord_456", "state": "open"}
    captured = {}

    async def fake_place_smart_order(client, symbol, size, side,
                                     order_preference=None, reduce_only=False):
        captured['side'] = side
        return fake_order

    monitor.api_client.get_all_positions_with_options = AsyncMock(
        return_value={"options": [_long_position(size=10)], "futures": []}
    )

    with patch("routes.options.options_client._run_async", side_effect=_run_async_for_test), \
         patch("webui.backend.options_strategy.take_profit_manager.place_smart_order", fake_place_smart_order), \
         patch("webui.backend.options_strategy.take_profit_manager.ORDER_EXECUTION_AVAILABLE", True):

        monitor._close_position("C-BTC-100000-300126", 25.0, 5, 20.0)

    assert captured['side'] == 'sell', f"Expected sell for long position, got: {captured['side']}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Short position triggers buy side
# ---------------------------------------------------------------------------

def test_close_position_short_triggers_buy():
    """Short position (size < 0) must place a buy order."""
    monitor = _make_monitor()

    fake_order = {"id": "ord_789", "state": "open"}
    captured = {}

    async def fake_place_smart_order(client, symbol, size, side,
                                     order_preference=None, reduce_only=False):
        captured['side'] = side
        return fake_order

    monitor.api_client.get_all_positions_with_options = AsyncMock(
        return_value={"options": [_short_position(symbol="C-BTC-100000-300126", size=-8)], "futures": []}
    )

    with patch("routes.options.options_client._run_async", side_effect=_run_async_for_test), \
         patch("webui.backend.options_strategy.take_profit_manager.place_smart_order", fake_place_smart_order), \
         patch("webui.backend.options_strategy.take_profit_manager.ORDER_EXECUTION_AVAILABLE", True):

        monitor._close_position("C-BTC-100000-300126", -30.0, 5, -20.0)

    assert captured['side'] == 'buy', f"Expected buy for short position, got: {captured['side']}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 7 — Quantity is capped at actual position size
# ---------------------------------------------------------------------------

def test_close_position_caps_quantity_at_actual_size():
    """Exit quantity must never exceed actual position size."""
    monitor = _make_monitor()

    captured = {}
    fake_order = {"id": "ord_cap", "state": "open"}

    async def fake_place_smart_order(client, symbol, size, side,
                                     order_preference=None, reduce_only=False):
        captured['size'] = size
        return fake_order

    # Position has only 3 lots, but TP requests 10
    monitor.api_client.get_all_positions_with_options = AsyncMock(
        return_value={"options": [_long_position(size=3)], "futures": []}
    )

    with patch("routes.options.options_client._run_async", side_effect=_run_async_for_test), \
         patch("webui.backend.options_strategy.take_profit_manager.place_smart_order", fake_place_smart_order), \
         patch("webui.backend.options_strategy.take_profit_manager.ORDER_EXECUTION_AVAILABLE", True):

        monitor._close_position("C-BTC-100000-300126", 25.0, 10, 20.0)

    assert captured['size'] == 3, \
        f"Should cap at 3 (actual size), but tried to close {captured['size']}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 8 — Returns early (no order) when position size is 0
# ---------------------------------------------------------------------------

def test_close_position_returns_early_for_zero_size():
    """If position size is already 0 (closed), must not place any order."""
    monitor = _make_monitor()

    order_placed = {"called": False}

    async def fake_place_smart_order(*args, **kwargs):
        order_placed["called"] = True
        return {"id": "should_not_reach", "state": "open"}

    monitor.api_client.get_all_positions_with_options = AsyncMock(
        return_value={"options": [_long_position(size=0)], "futures": []}
    )

    with patch("routes.options.options_client._run_async", side_effect=_run_async_for_test), \
         patch("webui.backend.options_strategy.take_profit_manager.place_smart_order", fake_place_smart_order), \
         patch("webui.backend.options_strategy.take_profit_manager.ORDER_EXECUTION_AVAILABLE", True):

        monitor._close_position("C-BTC-100000-300126", 0.0, 5, 20.0)

    assert not order_placed["called"], "No order should be placed when position size is 0"


# ---------------------------------------------------------------------------
# CONTRACT TEST 9 — Raises when position symbol not found
# ---------------------------------------------------------------------------

def test_close_position_raises_when_symbol_not_found():
    """If the target symbol is not in the positions list, must raise an exception."""
    monitor = _make_monitor()

    # Different symbol in positions
    monitor.api_client.get_all_positions_with_options = AsyncMock(
        return_value={"options": [_long_position(symbol="P-BTC-80000-300126")], "futures": []}
    )

    with patch("routes.options.options_client._run_async", side_effect=_run_async_for_test), \
         patch("webui.backend.options_strategy.take_profit_manager.ORDER_EXECUTION_AVAILABLE", True):

        with pytest.raises(Exception, match="not found"):
            monitor._close_position("C-BTC-100000-300126", 25.0, 5, 20.0)


# ---------------------------------------------------------------------------
# CONTRACT TEST 10 — reduce_only is always True
# ---------------------------------------------------------------------------

def test_close_position_always_passes_reduce_only_true():
    """reduce_only must always be True — TP must only reduce, never add to position."""
    monitor = _make_monitor()

    captured = {}
    fake_order = {"id": "ord_reduce", "state": "open"}

    async def fake_place_smart_order(client, symbol, size, side,
                                     order_preference=None, reduce_only=False):
        captured['reduce_only'] = reduce_only
        return fake_order

    monitor.api_client.get_all_positions_with_options = AsyncMock(
        return_value={"options": [_long_position()], "futures": []}
    )

    with patch("routes.options.options_client._run_async", side_effect=_run_async_for_test), \
         patch("webui.backend.options_strategy.take_profit_manager.place_smart_order", fake_place_smart_order), \
         patch("webui.backend.options_strategy.take_profit_manager.ORDER_EXECUTION_AVAILABLE", True):

        monitor._close_position("C-BTC-100000-300126", 25.0, 5, 20.0)

    assert captured.get('reduce_only') is True, \
        "reduce_only must always be True — TP must never add to a position"
