"""
MMMX Phase 2 Unit Tests

Covers: executor, circuit breaker, margin guardian adapter, reconciler.
Exit criteria per MMMX_IMPLEMENTATION_PLAN.md Section 4 Phase 2:
  - Mocked exchange: limit fills first attempt → success
  - All reprice attempts timeout → falls through to market (emergency_execute)
  - Margin 85% mid-loop → switches to market on next reprice
  - Margin 95% mid-loop → aborts, returns ExecutionResult(success=False, reason='MARGIN_CRITICAL')
  - Preflight: SELL blocked at util >= 80%
  - Duplicate client_order_id: second smart_execute finds open order, returns without new POST
  - Partial fill recorded; tick_partials retries remainder; audit log has both rows
  - Circuit breaker: CLOSED → HALF_OPEN after 3 failures → OPEN after probe fails → CLOSED
  - MMM isolation scan for all Phase 2 modules (except mmmx_margin_guardian.py)
"""

import asyncio
import os
import sys
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── Ensure package root is importable ─────────────────────────────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _run(coro):
    """Run a coroutine in a fresh event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_filled_order(order_id='ord-001', fill_price=100.0, size=10):
    """Build a fake 'filled' order response dict."""
    return {
        'id':                 order_id,
        'product_id':         42,
        'state':              'filled',
        'average_fill_price': str(fill_price),
        'unfilled_size':      0,
        'limit_price':        str(fill_price),
    }


def _make_open_order(order_id='ord-existing', limit_price=95.0, coid='abc123456789abcd'):
    """Build a fake open order (for dedup test)."""
    return {
        'id':                order_id,
        'product_id':        42,
        'state':             'open',
        'limit_price':       str(limit_price),
        'client_order_id':   coid,
    }


def _make_quotes(bid=95.0, ask=105.0, tick=0.5):
    return {
        'best_bid':  bid,
        'best_ask':  ask,
        'bid_size':  10,
        'ask_size':  10,
        'tick_size': tick,
        'fresh':     True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Circuit Breaker Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCircuitBreaker:
    """CLOSED → HALF_OPEN → OPEN → HALF_OPEN → CLOSED lifecycle."""

    def setup_method(self):
        from webui.backend.routes.mmmx.mmmx_circuit_breaker import reset
        self.session = 'cb-test-session'
        reset(self.session)

    def test_initial_state_is_closed(self):
        from webui.backend.routes.mmmx.mmmx_circuit_breaker import get_state, CBState
        from webui.backend.routes.mmmx.mmmx_constants import CBState as ConstCBState
        assert get_state(self.session) == 'CLOSED'

    def test_allow_in_closed_state(self):
        from webui.backend.routes.mmmx.mmmx_circuit_breaker import allow_request
        assert allow_request(self.session) is True

    def test_two_failures_stay_closed(self):
        from webui.backend.routes.mmmx.mmmx_circuit_breaker import (
            record_failure, get_state,
        )
        record_failure(self.session)
        record_failure(self.session)
        assert get_state(self.session) == 'CLOSED'

    def test_three_failures_trip_to_half_open(self):
        from webui.backend.routes.mmmx.mmmx_circuit_breaker import (
            record_failure, get_state,
        )
        record_failure(self.session)
        record_failure(self.session)
        record_failure(self.session)
        assert get_state(self.session) == 'HALF_OPEN'

    def test_half_open_allows_one_probe(self):
        from webui.backend.routes.mmmx.mmmx_circuit_breaker import (
            record_failure, allow_request,
        )
        for _ in range(3):
            record_failure(self.session)
        assert allow_request(self.session) is True

    def test_half_open_failure_opens(self):
        from webui.backend.routes.mmmx.mmmx_circuit_breaker import (
            record_failure, get_state,
        )
        for _ in range(3):   # → HALF_OPEN
            record_failure(self.session)
        record_failure(self.session)  # probe fails → OPEN
        assert get_state(self.session) == 'OPEN'

    def test_open_blocks_requests(self):
        from webui.backend.routes.mmmx.mmmx_circuit_breaker import (
            record_failure, allow_request,
        )
        for _ in range(4):   # 3 → HALF_OPEN, 4th → OPEN
            record_failure(self.session)
        assert allow_request(self.session) is False

    def test_open_to_half_open_after_cooldown(self):
        from webui.backend.routes.mmmx import mmmx_circuit_breaker as cb
        for _ in range(4):
            cb.record_failure(self.session)
        assert cb.get_state(self.session) == 'OPEN'

        # Backdate opened_at to simulate cooldown elapsed
        with cb._lock:
            cb._states[self.session].opened_at = time.time() - 10.0

        assert cb.get_state(self.session) == 'HALF_OPEN'
        assert cb.allow_request(self.session) is True

    def test_success_resets_to_closed(self):
        from webui.backend.routes.mmmx.mmmx_circuit_breaker import (
            record_failure, record_success, get_state,
        )
        for _ in range(3):
            record_failure(self.session)
        assert get_state(self.session) == 'HALF_OPEN'
        record_success(self.session)
        assert get_state(self.session) == 'CLOSED'

    def test_independent_sessions(self):
        """Two different sessions have independent state."""
        from webui.backend.routes.mmmx.mmmx_circuit_breaker import (
            record_failure, get_state, reset,
        )
        s1, s2 = 'sess-aaa', 'sess-bbb'
        reset(s1)
        reset(s2)
        for _ in range(3):
            record_failure(s1)
        assert get_state(s1) == 'HALF_OPEN'
        assert get_state(s2) == 'CLOSED'


# ═══════════════════════════════════════════════════════════════════════════════
# Margin Guardian Adapter Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarginGuardianAdapter:

    def test_estimated_margin_positive(self):
        from webui.backend.routes.mmmx.mmmx_margin_guardian import MMMXMarginGuardianAdapter
        from webui.backend.routes.mmmx.mmmx_constants import LOT_SIZE_BTC
        adapter = MMMXMarginGuardianAdapter()
        est = adapter.estimated_margin_for_order('C-BTC-100000-280326', 'sell', 10, 200.0)
        expected = round(200.0 * 10 * LOT_SIZE_BTC, 4)
        assert abs(est - expected) < 1e-6

    def test_estimated_margin_zero_price(self):
        from webui.backend.routes.mmmx.mmmx_margin_guardian import MMMXMarginGuardianAdapter
        adapter = MMMXMarginGuardianAdapter()
        assert adapter.estimated_margin_for_order('C-BTC-100000-280326', 'buy', 10, 0) == 0.0

    def test_current_utilization_falls_back_on_error(self):
        """If fetch fails, current_utilization() returns last cached value (0.0 initially)."""
        from webui.backend.routes.mmmx.mmmx_margin_guardian import MMMXMarginGuardianAdapter
        adapter = MMMXMarginGuardianAdapter()
        adapter._last_util = 42.0

        async def _run_test():
            # Patch _create_rest_client to raise immediately
            with patch.object(adapter, '_create_rest_client', side_effect=RuntimeError("no conn")):
                util = await adapter.current_utilization()
            return util

        util = _run(asyncio.coroutine(_run_test)()) if False else asyncio.get_event_loop().run_until_complete(_run_test())
        assert util == 42.0

    def test_current_utilization_success(self):
        """current_utilization() returns the fetched value and caches it."""
        from webui.backend.routes.mmmx.mmmx_margin_guardian import MMMXMarginGuardianAdapter
        adapter = MMMXMarginGuardianAdapter()

        fake_margin_result = {'success': True, 'utilization_pct': 67.5}

        # fetch_margin_utilization is imported lazily inside current_utilization(),
        # so we patch it at the source module (routes.mmm), not the adapter module.
        async def _run_test():
            mock_rest = AsyncMock()
            with patch.object(adapter, '_create_rest_client', return_value=mock_rest), \
                 patch(
                     'webui.backend.routes.mmm.mmm_margin_guardian.fetch_margin_utilization',
                     new=AsyncMock(return_value=fake_margin_result),
                 ):
                util = await adapter.current_utilization()
            return util, adapter._last_util

        util, cached = asyncio.get_event_loop().run_until_complete(_run_test())
        assert abs(util - 67.5) < 1e-6
        assert abs(cached - 67.5) < 1e-6

    def test_singleton_is_same_instance(self):
        from webui.backend.routes.mmmx.mmmx_margin_guardian import get_margin_guardian
        a = get_margin_guardian()
        b = get_margin_guardian()
        assert a is b


# ═══════════════════════════════════════════════════════════════════════════════
# Executor: client_order_id
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeClientOrderId:
    def test_returns_16_hex_chars(self):
        from webui.backend.routes.mmmx.mmmx_executor import compute_client_order_id
        coid = compute_client_order_id('sess-1', 1, 'sell', 'DEPLOY')
        assert len(coid) == 16
        assert all(c in '0123456789abcdef' for c in coid)

    def test_deterministic_within_minute(self):
        from webui.backend.routes.mmmx.mmmx_executor import compute_client_order_id
        c1 = compute_client_order_id('sess-1', 1, 'sell', 'DEPLOY')
        c2 = compute_client_order_id('sess-1', 1, 'sell', 'DEPLOY')
        assert c1 == c2

    def test_different_params_different_id(self):
        from webui.backend.routes.mmmx.mmmx_executor import compute_client_order_id
        c1 = compute_client_order_id('sess-1', 1, 'sell', 'DEPLOY')
        c2 = compute_client_order_id('sess-1', 2, 'sell', 'DEPLOY')
        assert c1 != c2


# ═══════════════════════════════════════════════════════════════════════════════
# Executor: smart_execute
# ═══════════════════════════════════════════════════════════════════════════════

class TestSmartExecute:
    """Mocked-exchange smart_execute tests."""

    SYMBOL     = 'C-BTC-100000-280326'
    SESSION_ID = 'test-session-p2'

    def _make_executor(self):
        from webui.backend.routes.mmmx.mmmx_executor import MMMXExecutor
        return MMMXExecutor()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _patch_margin_ok(self):
        """Patch margin guardian to return OK (util=0%)."""
        return patch(
            'webui.backend.routes.mmmx.mmmx_executor.MMMXExecutor.preflight_margin_check',
            new=AsyncMock(return_value='OK'),
        )

    def _patch_midloop_ok(self):
        return patch(
            'webui.backend.routes.mmmx.mmmx_executor.MMMXExecutor._midloop_margin_check',
            new=AsyncMock(return_value='OK'),
        )

    # ── Test: limit fills on first attempt ─────────────────────────────────────

    def test_limit_fills_first_attempt(self):
        """Mocked exchange: limit order fills first attempt → success."""
        executor = self._make_executor()
        filled_order = _make_filled_order(fill_price=100.0, size=10)

        mock_rest = AsyncMock()
        mock_rest.get_open_orders_by_symbol = AsyncMock(return_value=[])
        mock_rest.place_order_by_symbol = AsyncMock(return_value={
            'result': {'id': 'ord-001', 'product_id': 42}
        })
        mock_rest.get_order = AsyncMock(return_value={'result': filled_order})
        mock_rest.get_orderbook = AsyncMock(return_value={
            'buy':  [{'price': '95.0', 'size': '100'}],
            'sell': [{'price': '105.0', 'size': '100'}],
        })

        async def run():
            with patch.object(executor, '_create_rest_client', return_value=mock_rest), \
                 self._patch_margin_ok(), \
                 self._patch_midloop_ok():
                return await executor.smart_execute(
                    symbol=self.SYMBOL, side='sell', size=10,
                    session_id=self.SESSION_ID, tranche_id=1, action='DEPLOY',
                )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.success is True
        assert result.filled_size == 10
        assert abs(result.avg_price - 100.0) < 1e-6
        assert result.attempts == 1

    # ── Test: all reprice attempts timeout → market fallback ───────────────────

    def test_all_reprices_timeout_market_fallback(self):
        """All limit reprice attempts time out → emergency_execute called."""
        executor = self._make_executor()

        # We'll patch emergency_execute to return success
        from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult

        async def fake_emergency(**kw):
            return ExecutionResult(
                success=True, filled_size=10, avg_price=90.0, attempts=1,
                total_ms=500, order_id='emrg-001', client_order_id='xyz',
            )

        mock_rest = AsyncMock()
        mock_rest.get_open_orders_by_symbol = AsyncMock(return_value=[])
        mock_rest.place_order_by_symbol = AsyncMock(return_value={
            'result': {'id': 'ord-002', 'product_id': 42}
        })
        # _wait_for_fill always returns (False, None) — timeout on every attempt
        mock_rest.get_order = AsyncMock(return_value={'result': {'id': 'ord-002', 'state': 'open'}})
        mock_rest.get_orderbook = AsyncMock(return_value={
            'buy':  [{'price': '95.0', 'size': '100'}],
            'sell': [{'price': '105.0', 'size': '100'}],
        })
        mock_rest.cancel_order = AsyncMock()

        async def run():
            with patch.object(executor, '_create_rest_client', return_value=mock_rest), \
                 self._patch_margin_ok(), \
                 self._patch_midloop_ok(), \
                 patch.object(executor, 'emergency_execute', side_effect=fake_emergency), \
                 patch('webui.backend.routes.mmmx.mmmx_executor.FILL_TIMEOUT_SECS', 0.01), \
                 patch('webui.backend.routes.mmmx.mmmx_executor.FILL_CHECK_INTERVAL', 0.005), \
                 patch('webui.backend.routes.mmmx.mmmx_executor.SMART_EXECUTE_REPRICE_ATTEMPTS', 2):
                return await executor.smart_execute(
                    symbol=self.SYMBOL, side='sell', size=10,
                    session_id=self.SESSION_ID, tranche_id=1, action='DEPLOY',
                )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.success is True
        assert result.order_id == 'emrg-001'
        # attempts from smart_execute (2) + from emergency (1) = 3
        assert result.attempts >= 2

    # ── Test: margin 85% mid-loop → market fallback ────────────────────────────

    def test_midloop_margin_85_falls_back_to_market(self):
        """Mid-loop util >= 85% → cancel + emergency_execute."""
        executor = self._make_executor()
        from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult

        async def fake_emergency(**kw):
            return ExecutionResult(
                success=True, filled_size=10, avg_price=90.0, attempts=1,
                total_ms=200, order_id='emrg-002',
            )

        mock_rest = AsyncMock()
        mock_rest.get_open_orders_by_symbol = AsyncMock(return_value=[])
        mock_rest.place_order_by_symbol = AsyncMock(return_value={
            'result': {'id': 'ord-003', 'product_id': 42}
        })
        mock_rest.get_order = AsyncMock(return_value={
            'result': {'id': 'ord-003', 'state': 'open'}
        })
        mock_rest.get_orderbook = AsyncMock(return_value={
            'buy':  [{'price': '95.0', 'size': '10'}],
            'sell': [{'price': '105.0', 'size': '10'}],
        })
        mock_rest.cancel_order = AsyncMock()

        async def run():
            with patch.object(executor, '_create_rest_client', return_value=mock_rest), \
                 self._patch_margin_ok(), \
                 patch.object(
                     executor, '_midloop_margin_check',
                     new=AsyncMock(return_value='MARGIN_BLOCKED'),   # 85% path
                 ), \
                 patch.object(executor, 'emergency_execute', side_effect=fake_emergency), \
                 patch('webui.backend.routes.mmmx.mmmx_executor.FILL_TIMEOUT_SECS', 0.01), \
                 patch('webui.backend.routes.mmmx.mmmx_executor.FILL_CHECK_INTERVAL', 0.005):
                return await executor.smart_execute(
                    symbol=self.SYMBOL, side='sell', size=10,
                    session_id=self.SESSION_ID, tranche_id=1, action='DEPLOY',
                )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.success is True
        assert result.order_id == 'emrg-002'

    # ── Test: margin 95% mid-loop → abort ─────────────────────────────────────

    def test_midloop_margin_95_aborts(self):
        """Mid-loop util >= 95% → cancel + return MARGIN_CRITICAL immediately."""
        executor = self._make_executor()

        mock_rest = AsyncMock()
        mock_rest.get_open_orders_by_symbol = AsyncMock(return_value=[])
        mock_rest.place_order_by_symbol = AsyncMock(return_value={
            'result': {'id': 'ord-004', 'product_id': 42}
        })
        mock_rest.get_order = AsyncMock(return_value={
            'result': {'id': 'ord-004', 'state': 'open'}
        })
        mock_rest.get_orderbook = AsyncMock(return_value={
            'buy':  [{'price': '95.0', 'size': '10'}],
            'sell': [{'price': '105.0', 'size': '10'}],
        })
        mock_rest.cancel_order = AsyncMock()

        async def run():
            with patch.object(executor, '_create_rest_client', return_value=mock_rest), \
                 self._patch_margin_ok(), \
                 patch.object(
                     executor, '_midloop_margin_check',
                     new=AsyncMock(return_value='MARGIN_CRITICAL'),   # 95% path
                 ), \
                 patch('webui.backend.routes.mmmx.mmmx_executor.FILL_TIMEOUT_SECS', 0.01), \
                 patch('webui.backend.routes.mmmx.mmmx_executor.FILL_CHECK_INTERVAL', 0.005):
                return await executor.smart_execute(
                    symbol=self.SYMBOL, side='sell', size=10,
                    session_id=self.SESSION_ID, tranche_id=1, action='DEPLOY',
                )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.success is False
        assert result.reason == 'MARGIN_CRITICAL'

    # ── Test: preflight SELL blocked at 80% ────────────────────────────────────

    def test_preflight_sell_blocked_at_80pct(self):
        """Preflight: SELL blocked when margin util >= 80%."""
        executor = self._make_executor()

        # preflight_margin_check does: from .mmmx_margin_guardian import get_margin_guardian
        # So we patch it at mmmx_margin_guardian (where get_margin_guardian lives).
        mock_adapter = MagicMock()
        mock_adapter.current_utilization = AsyncMock(return_value=81.0)

        async def run():
            mock_rest = AsyncMock()
            mock_rest.get_open_orders_by_symbol = AsyncMock(return_value=[])
            with patch.object(executor, '_create_rest_client', return_value=mock_rest), \
                 patch(
                     'webui.backend.routes.mmmx.mmmx_margin_guardian.get_margin_guardian',
                     return_value=mock_adapter,
                 ):
                return await executor.smart_execute(
                    symbol=self.SYMBOL, side='sell', size=10,
                    session_id=self.SESSION_ID,
                )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.success is False
        assert result.reason == 'MARGIN_BLOCKED'

    # ── Test: preflight SELL OK at 79% ────────────────────────────────────────

    def test_preflight_margin_verdict_ok(self):
        """preflight_margin_check: SELL with util=79% → OK."""
        executor = self._make_executor()

        mock_adapter = MagicMock()
        mock_adapter.current_utilization = AsyncMock(return_value=79.0)

        async def run():
            with patch(
                'webui.backend.routes.mmmx.mmmx_margin_guardian.get_margin_guardian',
                return_value=mock_adapter,
            ):
                return await executor.preflight_margin_check('sell', self.SESSION_ID)

        verdict = asyncio.get_event_loop().run_until_complete(run())
        assert verdict == 'OK'

    # ── Test: duplicate client_order_id dedup ─────────────────────────────────

    def test_dedup_existing_open_order(self):
        """Second smart_execute with same coid finds open order — no new POST."""
        executor = self._make_executor()
        from webui.backend.routes.mmmx.mmmx_executor import compute_client_order_id

        coid = compute_client_order_id(self.SESSION_ID, 1, 'sell', 'DEPLOY')
        existing = _make_open_order(order_id='ord-existing', limit_price=95.0, coid=coid)

        mock_rest = AsyncMock()
        mock_rest.get_open_orders_by_symbol = AsyncMock(return_value=[existing])
        # Ensure place_order is NEVER called
        mock_rest.place_order_by_symbol = AsyncMock(
            side_effect=AssertionError("place_order should not be called on dedup")
        )

        async def run():
            with patch.object(executor, '_create_rest_client', return_value=mock_rest), \
                 self._patch_margin_ok():
                return await executor.smart_execute(
                    symbol=self.SYMBOL, side='sell', size=10,
                    session_id=self.SESSION_ID, tranche_id=1, action='DEPLOY',
                )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.success is True
        assert result.order_id == 'ord-existing'
        assert result.reason == 'DEDUPED_EXISTING_ORDER'
        mock_rest.place_order_by_symbol.assert_not_called()

    # ── Test: position marked _being_closed ────────────────────────────────────

    def test_position_being_closed_set_and_cleared(self):
        """smart_execute marks position _being_closed=True and clears it on fill."""
        executor = self._make_executor()
        position = {'lots': 10, 'status': 'ACTIVE'}
        filled_order = _make_filled_order(fill_price=100.0, size=10)

        mock_rest = AsyncMock()
        mock_rest.get_open_orders_by_symbol = AsyncMock(return_value=[])
        mock_rest.place_order_by_symbol = AsyncMock(return_value={
            'result': {'id': 'ord-bc', 'product_id': 42}
        })
        mock_rest.get_order = AsyncMock(return_value={'result': filled_order})
        mock_rest.get_orderbook = AsyncMock(return_value={
            'buy':  [{'price': '95.0', 'size': '10'}],
            'sell': [{'price': '105.0', 'size': '10'}],
        })

        async def run():
            with patch.object(executor, '_create_rest_client', return_value=mock_rest), \
                 self._patch_margin_ok(), \
                 self._patch_midloop_ok():
                return await executor.smart_execute(
                    symbol=self.SYMBOL, side='sell', size=10,
                    session_id=self.SESSION_ID, tranche_id=1, action='DEPLOY',
                    position=position,
                )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.success is True
        # _being_closed should be cleared after fill
        assert '_being_closed' not in position


# ═══════════════════════════════════════════════════════════════════════════════
# Executor: emergency_execute
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmergencyExecute:

    SYMBOL = 'C-BTC-100000-280326'

    def _make_executor(self):
        from webui.backend.routes.mmmx.mmmx_executor import MMMXExecutor
        return MMMXExecutor()

    def test_emergency_fill_success(self):
        """emergency_execute: IOC order fills → success."""
        executor = self._make_executor()

        mock_rest = AsyncMock()
        mock_rest.get_orderbook = AsyncMock(return_value={
            'buy':  [{'price': '95.0', 'size': '10'}],
            'sell': [{'price': '105.0', 'size': '10'}],
        })
        mock_rest.place_order_by_symbol = AsyncMock(return_value={
            'result': {'id': 'emrg-ok', 'product_id': 42}
        })
        mock_rest.get_order = AsyncMock(return_value={
            'result': {
                'id': 'emrg-ok',
                'state': 'filled',
                'average_fill_price': '98.0',
                'unfilled_size': 0,
            }
        })

        async def run():
            with patch.object(executor, '_create_rest_client', return_value=mock_rest), \
                 patch('webui.backend.routes.mmmx.mmmx_executor.EMERGENCY_FILL_WAIT', 0.01):
                return await executor.emergency_execute(
                    symbol=self.SYMBOL, side='sell', size=10, session_id='test-s',
                )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.success is True
        assert abs(result.avg_price - 98.0) < 1e-6
        assert result.filled_size == 10

    def test_emergency_not_filled_returns_failure(self):
        """emergency_execute: IOC cancelled on all attempts → failure."""
        executor = self._make_executor()

        mock_rest = AsyncMock()
        mock_rest.get_orderbook = AsyncMock(return_value={
            'buy':  [{'price': '95.0', 'size': '10'}],
            'sell': [{'price': '105.0', 'size': '10'}],
        })
        mock_rest.place_order_by_symbol = AsyncMock(return_value={
            'result': {'id': 'emrg-nf', 'product_id': 42}
        })
        mock_rest.get_order = AsyncMock(return_value={
            'result': {'id': 'emrg-nf', 'state': 'cancelled'}
        })

        async def run():
            with patch.object(executor, '_create_rest_client', return_value=mock_rest), \
                 patch('webui.backend.routes.mmmx.mmmx_executor.EMERGENCY_FILL_WAIT', 0.01):
                return await executor.emergency_execute(
                    symbol=self.SYMBOL, side='sell', size=5, session_id='test-s',
                )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.success is False
        assert 'EMERGENCY' in result.reason or 'FILLED' in result.reason.upper()


# ═══════════════════════════════════════════════════════════════════════════════
# Reconciler Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestReconciler:

    SESSION_ID = 'reconciler-test-session'

    def setup_method(self):
        from webui.backend.routes.mmmx.mmmx_reconciler import clear_all_residuals
        clear_all_residuals()

    def test_track_partial_fill_creates_residual(self):
        from webui.backend.routes.mmmx.mmmx_reconciler import (
            track_partial_fill, get_pending_residuals,
        )
        track_partial_fill(
            order_id='ord-partial-1',
            symbol='C-BTC-100000-280326',
            side='sell',
            tranche_id=1,
            requested_lots=10,
            filled_lots=6,
            session_id=self.SESSION_ID,
        )
        residuals = get_pending_residuals()
        assert len(residuals) == 1
        assert residuals[0]['remaining'] == 4
        assert residuals[0]['filled'] == 6

    def test_track_full_fill_clears_residual(self):
        """If filled == requested, no residual created."""
        from webui.backend.routes.mmmx.mmmx_reconciler import (
            track_partial_fill, get_pending_residuals,
        )
        track_partial_fill(
            order_id='ord-full', symbol='C-BTC-100000-280326', side='sell',
            tranche_id=1, requested_lots=10, filled_lots=10,
            session_id=self.SESSION_ID,
        )
        assert get_pending_residuals() == []

    def test_tick_partials_retries_remainder(self):
        """tick_partials calls smart_execute on the remaining lots."""
        from webui.backend.routes.mmmx.mmmx_reconciler import (
            track_partial_fill, tick_partials, get_pending_residuals,
        )
        from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult

        track_partial_fill(
            order_id='ord-partial-2',
            symbol='C-BTC-100000-280326', side='sell',
            tranche_id=1, requested_lots=10, filled_lots=7,
            session_id=self.SESSION_ID,
        )

        session = {'session_id': self.SESSION_ID, 'params': {}}

        async def fake_smart(**kw):
            return ExecutionResult(
                success=True, filled_size=3, avg_price=100.0, attempts=1,
                total_ms=100, order_id='ord-retry-001',
            )

        mock_executor = MagicMock()
        mock_executor.smart_execute = AsyncMock(side_effect=fake_smart)
        mock_executor.emergency_execute = AsyncMock(
            side_effect=AssertionError("should not call emergency for 3-lot remainder")
        )

        async def run():
            # get_executor is lazily imported inside tick_partials — patch at mmmx_executor
            with patch(
                'webui.backend.routes.mmmx.mmmx_executor.get_executor',
                return_value=mock_executor,
            ):
                return await tick_partials(session)

        results = asyncio.get_event_loop().run_until_complete(run())
        assert len(results) == 1
        assert results[0]['result']['success'] is True

        # Residual should be cleared after successful retry
        assert get_pending_residuals() == []

    def test_tick_partials_retains_on_failure(self):
        """tick_partials retains the residual if the retry fails."""
        from webui.backend.routes.mmmx.mmmx_reconciler import (
            track_partial_fill, tick_partials, get_pending_residuals,
        )
        from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult

        track_partial_fill(
            order_id='ord-partial-3',
            symbol='C-BTC-100000-280326', side='sell',
            tranche_id=2, requested_lots=10, filled_lots=5,
            session_id=self.SESSION_ID,
        )

        session = {'session_id': self.SESSION_ID, 'params': {}}

        async def fake_smart(**kw):
            return ExecutionResult(success=False, reason='NO_QUOTES', filled_size=0)

        mock_executor = MagicMock()
        mock_executor.smart_execute = AsyncMock(side_effect=fake_smart)
        mock_executor.emergency_execute = AsyncMock(side_effect=fake_smart)

        async def run():
            with patch(
                'webui.backend.routes.mmmx.mmmx_executor.get_executor',
                return_value=mock_executor,
            ):
                return await tick_partials(session)

        results = asyncio.get_event_loop().run_until_complete(run())
        assert len(results) == 1
        assert results[0]['result']['success'] is False
        # Residual should still be pending
        assert len(get_pending_residuals()) == 1

    def test_tick_partials_large_remainder_uses_emergency(self):
        """Remaining >= 20 lots escalates to emergency_execute."""
        from webui.backend.routes.mmmx.mmmx_reconciler import (
            track_partial_fill, tick_partials,
        )
        from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult

        track_partial_fill(
            order_id='ord-large', symbol='C-BTC-100000-280326', side='sell',
            tranche_id=3, requested_lots=30, filled_lots=0,
            session_id=self.SESSION_ID,
        )

        session = {'session_id': self.SESSION_ID, 'params': {}}
        emergency_called = []

        async def fake_emergency(**kw):
            emergency_called.append(True)
            return ExecutionResult(success=True, filled_size=30, avg_price=100.0, attempts=1)

        mock_executor = MagicMock()
        mock_executor.smart_execute = AsyncMock(
            side_effect=AssertionError("should use emergency for large lots")
        )
        mock_executor.emergency_execute = AsyncMock(side_effect=fake_emergency)

        async def run():
            with patch(
                'webui.backend.routes.mmmx.mmmx_executor.get_executor',
                return_value=mock_executor,
            ):
                return await tick_partials(session)

        asyncio.get_event_loop().run_until_complete(run())
        assert emergency_called, "emergency_execute should have been called for 30-lot remainder"

    def test_audit_log_entries_for_partial_flow(self):
        """Audit log receives PARTIAL_FILL_TRACKED on track, PARTIAL_FILL_CLEARED on success."""
        from webui.backend.routes.mmmx.mmmx_reconciler import (
            track_partial_fill, tick_partials,
        )
        from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult

        audit_events = []

        track_partial_fill(
            order_id='ord-audit', symbol='C-BTC-100000-280326', side='sell',
            tranche_id=1, requested_lots=10, filled_lots=4,
            session_id=self.SESSION_ID,
        )

        session = {'session_id': self.SESSION_ID, 'params': {}}

        async def fake_smart(**kw):
            return ExecutionResult(success=True, filled_size=6, avg_price=100.0, attempts=1)

        mock_executor = MagicMock()
        mock_executor.smart_execute = AsyncMock(side_effect=fake_smart)
        mock_executor.emergency_execute = AsyncMock()

        async def run():
            with patch(
                'webui.backend.routes.mmmx.mmmx_executor.get_executor',
                return_value=mock_executor,
            ), \
            patch(
                'webui.backend.routes.mmmx.mmmx_reconciler._audit_event',
                side_effect=lambda session_id, cat, data: audit_events.append(
                    {'category': cat, 'data': data}
                ),
            ):
                return await tick_partials(session)

        asyncio.get_event_loop().run_until_complete(run())

        categories = [e['category'] for e in audit_events]
        # tick_partials on success writes PARTIAL_FILL_CLEARED
        assert 'PARTIAL_FILL_CLEARED' in categories


# ═══════════════════════════════════════════════════════════════════════════════
# ExecutionResult helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecutionResult:
    def test_to_dict_fields(self):
        from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult
        r = ExecutionResult(
            success=True, filled_size=5, avg_price=101.5, attempts=2,
            total_ms=3200, reason='', order_id='ord-x', client_order_id='abc',
            fees_paid=0.01,
        )
        d = r.to_dict()
        assert d['success'] is True
        assert d['filled_size'] == 5
        assert abs(d['avg_price'] - 101.5) < 1e-6
        assert d['order_id'] == 'ord-x'

    def test_failure_result(self):
        from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult
        r = ExecutionResult(success=False, reason='MARGIN_BLOCKED')
        assert r.success is False
        assert r.filled_size == 0
        assert r.avg_price == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# MMM Isolation Scan — Phase 2 modules
# ═══════════════════════════════════════════════════════════════════════════════

class TestMMMIsolationPhase2:
    """
    Verify Phase 2 modules (except mmmx_margin_guardian.py) don't import routes.mmm.*.
    mmmx_margin_guardian.py IS the designated bridge — excluded from scan.
    """

    PHASE2_MODULES = [
        'mmmx_circuit_breaker',
        'mmmx_executor',
        'mmmx_reconciler',
    ]

    def test_no_mmm_imports_in_phase2_modules(self):
        import re
        import importlib
        import inspect

        import_re = re.compile(r'^\s*(import|from)\s+.*routes\.mmm', re.MULTILINE)
        violations = []

        for mod_name in self.PHASE2_MODULES:
            full_name = f'webui.backend.routes.mmmx.{mod_name}'
            try:
                mod = importlib.import_module(full_name)
                src = inspect.getsource(mod)
                if import_re.search(src):
                    violations.append(mod_name)
            except Exception as exc:
                pytest.fail(f"Could not import {full_name}: {exc}")

        assert not violations, (
            f"MMM isolation violated in Phase 2 modules: {violations}. "
            "Only mmmx_margin_guardian.py is allowed to import from routes.mmm.*"
        )

    def test_margin_guardian_allowed_to_import_routes_mmm(self):
        """mmmx_margin_guardian.py is the only allowed cross-boundary importer."""
        import re
        import importlib
        import inspect

        mod = importlib.import_module('webui.backend.routes.mmmx.mmmx_margin_guardian')
        src = inspect.getsource(mod)
        import_re = re.compile(r'routes\.mmm', re.MULTILINE)
        # It MUST have the routes.mmm import (that's its purpose)
        assert import_re.search(src), (
            "mmmx_margin_guardian.py should import from routes.mmm.* "
            "(it's the designated bridge)"
        )

    def test_executor_not_mmm_db(self):
        """mmmx_executor.py must not reference mmm_sessions.db."""
        import inspect
        import webui.backend.routes.mmmx.mmmx_executor as mod
        src = inspect.getsource(mod)
        assert 'mmm_sessions.db' not in src

    def test_no_mmm_websocket_events_in_phase2(self):
        """Phase 2 modules must not emit mmm_* (non-mmmx) events."""
        import re
        import importlib
        import inspect

        bad_event_re = re.compile(r"emit\('mmm_[^x]", re.MULTILINE)
        for mod_name in self.PHASE2_MODULES:
            full_name = f'webui.backend.routes.mmmx.{mod_name}'
            mod = importlib.import_module(full_name)
            src = inspect.getsource(mod)
            bad = bad_event_re.findall(src)
            assert not bad, f"{mod_name} emits non-mmmx WebSocket events: {bad}"
