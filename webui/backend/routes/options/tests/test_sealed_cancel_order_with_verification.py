"""
Contract tests for cancel_order_with_verification

SEALED — v1.0.0 — March 4, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Function: cancel_order_with_verification(client, order_id, max_retries=3)
File: webui/backend/routes/options/options_control.py

Contracts:
  - Always returns dict with 'state' and 'safe_to_place_market' keys
  - Already filled → state='filled', safe_to_place_market=False
  - Already cancelled → state='cancelled', safe_to_place_market=True
  - Successful cancel verified → state='cancelled', safe_to_place_market=True
  - Order fills mid-cancellation → state='filled', safe_to_place_market=False
  - All retries fail → state='unknown', safe_to_place_market=False (safe=False!)
"""
import asyncio
import selectors
import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.sealed

from webui.backend.routes.options.options_control import cancel_order_with_verification


def _run(coro):
    """Run async coroutine using SelectSelector to avoid eventlet kqueue conflict on macOS."""
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_client(states: list):
    """Create a mock client that returns successive order states."""
    client = MagicMock()
    call_count = [0]

    async def _get_order(_oid):
        idx = min(call_count[0], len(states) - 1)
        call_count[0] += 1
        return {'state': states[idx]}

    async def _cancel_order(_oid):
        return {'success': True}

    client.rest_client = MagicMock()
    client.rest_client.get_order = _get_order
    client.rest_client.cancel_order = _cancel_order
    return client


class TestCancelAlreadySettled:

    def test_already_filled_returns_filled(self):
        client = _make_client(['filled'])
        result = _run(cancel_order_with_verification(client, 'ord-1', max_retries=3))
        assert result['state'] == 'filled'

    def test_already_filled_safe_to_place_market_is_false(self):
        client = _make_client(['filled'])
        result = _run(cancel_order_with_verification(client, 'ord-1', max_retries=3))
        assert result['safe_to_place_market'] is False

    def test_already_cancelled_returns_cancelled(self):
        client = _make_client(['cancelled'])
        result = _run(cancel_order_with_verification(client, 'ord-2', max_retries=3))
        assert result['state'] == 'cancelled'

    def test_already_cancelled_safe_to_place_market_is_true(self):
        client = _make_client(['cancelled'])
        result = _run(cancel_order_with_verification(client, 'ord-2', max_retries=3))
        assert result['safe_to_place_market'] is True


class TestCancelVerified:

    def test_successful_cancel_returns_cancelled(self):
        # First call: open, second call (verification): cancelled
        client = _make_client(['open', 'cancelled'])
        result = _run(cancel_order_with_verification(client, 'ord-3', max_retries=3))
        assert result['state'] == 'cancelled'
        assert result['safe_to_place_market'] is True

    def test_fills_during_cancel_returns_filled(self):
        # First call: open, second call (verification): filled
        client = _make_client(['open', 'filled'])
        result = _run(cancel_order_with_verification(client, 'ord-4', max_retries=3))
        assert result['state'] == 'filled'
        assert result['safe_to_place_market'] is False


class TestCancelAllRetriesFail:

    def test_all_retries_exception_returns_unknown(self):
        client = MagicMock()

        async def _failing_get(_oid):
            raise Exception("network error")

        client.rest_client = MagicMock()
        client.rest_client.get_order = _failing_get
        result = _run(cancel_order_with_verification(client, 'ord-5', max_retries=3))
        assert result['state'] == 'unknown'

    def test_all_retries_fail_safe_to_place_market_is_false(self):
        client = MagicMock()

        async def _failing_get(_oid):
            raise Exception("timeout")

        client.rest_client = MagicMock()
        client.rest_client.get_order = _failing_get
        result = _run(cancel_order_with_verification(client, 'ord-6', max_retries=2))
        assert result['safe_to_place_market'] is False

    def test_result_always_has_both_keys(self):
        client = _make_client(['open', 'cancelled'])
        result = _run(cancel_order_with_verification(client, 'ord-7', max_retries=1))
        assert 'state' in result
        assert 'safe_to_place_market' in result
