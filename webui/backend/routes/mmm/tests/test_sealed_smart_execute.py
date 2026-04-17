"""
Sealed contract tests for MMMExecutor.smart_execute (#79)

smart_execute is async — @sealed decorator not applicable (see mmm_atm_shield pattern).
Contract tests cover the FIX-1.2 and FIX-2.1 guarantees introduced 2026-04-16.

Functions covered:
  MMMExecutor.smart_execute(symbol, side, size, ..., fill_timeout=None) -> Dict

File: webui/backend/routes/mmm/mmm_executor.py

--- FIX-1.2: Terminal audit event contracts ---
C-SE-1: All INITIAL_PLACEMENT_RETRIES exhausted → ORDER_FAILED event written to session_event_log
C-SE-2: Order goes dead (exchange cancels) with no partial fill → ORDER_CANCELLED event written
C-SE-3: ORDER_INTENT event written on successful placement

--- FIX-2.1: DTE/gamma-aware fill timeout contracts ---
C-SE-4: fill_timeout=20 supplied → _wait_for_fill called with timeout=20 (caller override respected)
C-SE-5: fill_timeout=None → _wait_for_fill called with FILL_TIMEOUT=60 (default preserved)

--- Core success / failure path contracts ---
C-SE-6: Successful fill → returns {success: True, fill_price, filled_size, order_id}
C-SE-7: max_buy_price exceeded at initial placement → returns failure, no order placed (premium bounce guard)
C-SE-8: Quotes unavailable at start → returns failure immediately

--- Bug note documented during seal (2026-04-17) ---
  - get_session / list_sessions / delete_session in mmm_storage.py swallow DB exceptions (return None/[]/False)
    without distinguishing "not found" from "DB error". This is an established resilience pattern but
    callers cannot detect DB-down scenarios. Not blocking for seal.
  - save_session hot-reload: after hot-reload param preservation, session['params'] in-memory is
    not updated to final_params. Self-corrects on next get_session call (one heartbeat cycle).
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from webui.backend.routes.mmm.mmm_executor import MMMExecutor, FILL_TIMEOUT


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def executor():
    """MMMExecutor with _create_rest_client mocked out — no real exchange connection."""
    ex = MMMExecutor()
    ex._create_rest_client = MagicMock(return_value=MagicMock())
    return ex


def _good_quotes():
    return {'best_bid': 50.0, 'best_ask': 52.0, 'tick_size': 0.5}


def _order_result(order_id='ORD-001', product_id=99):
    return {'id': order_id, 'product_id': product_id}


def _filled_order(order_id='ORD-001', fill_price=51.0, unfilled_size=0, size=5):
    return {
        'id': order_id,
        'state': 'filled',
        'average_fill_price': fill_price,
        'unfilled_size': unfilled_size,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# =============================================================================
# C-SE-1: All placement retries exhausted → ORDER_FAILED event written
# =============================================================================

class TestTerminalEventOnPlacementFailure:

    @pytest.mark.sealed
    def test_c_se_1_placement_failure_writes_order_failed_event(self, executor):
        """When all INITIAL_PLACEMENT_RETRIES placement attempts fail, ORDER_FAILED
        must be written to session_event_log so the intent row is never left dangling."""
        mock_event_log = MagicMock()
        mock_event_log.enqueue_event = MagicMock()

        executor._fetch_quotes = AsyncMock(return_value=_good_quotes())
        # All placements return no id → simulates exchange rejecting every attempt
        executor._place_limit_order = AsyncMock(return_value={'error': 'exchange_down'})

        with patch(
            'webui.backend.routes.mmm.mmm_audit_log.get_event_log',
            return_value=mock_event_log,
        ):
            result = _run(executor.smart_execute(
                symbol='C-BTC-90000-170426',
                side='sell',
                size=5,
                session_id='test-001',
            ))

        assert result['success'] is False
        assert result.get('error')

        # ORDER_FAILED must have been written
        enqueue_calls = mock_event_log.enqueue_event.call_args_list
        event_types = [c.kwargs.get('event_type') or c.args[2] if c.args else '' for c in enqueue_calls]
        # Also handle keyword-only calls
        event_types_kw = [c.kwargs.get('event_type', '') for c in enqueue_calls]
        assert 'ORDER_FAILED' in event_types or 'ORDER_FAILED' in event_types_kw, (
            f"ORDER_FAILED not written. Events: {event_types_kw}"
        )

    @pytest.mark.sealed
    def test_c_se_1b_placement_failure_no_session_id_still_writes_event(self, executor):
        """ORDER_FAILED event must still be written even when session_id is None."""
        mock_event_log = MagicMock()
        executor._fetch_quotes = AsyncMock(return_value=_good_quotes())
        executor._place_limit_order = AsyncMock(return_value={'error': 'network_timeout'})

        with patch(
            'webui.backend.routes.mmm.mmm_audit_log.get_event_log',
            return_value=mock_event_log,
        ):
            result = _run(executor.smart_execute(
                symbol='C-BTC-90000-170426',
                side='sell',
                size=3,
                session_id=None,
            ))

        assert result['success'] is False
        event_types = [c.kwargs.get('event_type', '') for c in mock_event_log.enqueue_event.call_args_list]
        assert 'ORDER_FAILED' in event_types


# =============================================================================
# C-SE-2: Dead order (cancelled by exchange) → ORDER_CANCELLED event written
# =============================================================================

class TestTerminalEventOnDeadOrder:

    @pytest.mark.sealed
    def test_c_se_2_dead_order_writes_order_cancelled_event(self, executor):
        """When the exchange cancels an open order (_dead=True), ORDER_CANCELLED
        must be written so the ORDER_INTENT is never permanently dangling."""
        mock_event_log = MagicMock()

        executor._fetch_quotes = AsyncMock(return_value=_good_quotes())
        executor._place_limit_order = AsyncMock(return_value=_order_result())
        executor._get_order_status = AsyncMock(return_value=_filled_order())

        # _wait_for_fill returns _dead=True — exchange cancelled the order
        dead_order = {'id': 'ORD-001', 'state': 'cancelled', '_dead': True, 'unfilled_size': 5}
        executor._wait_for_fill = AsyncMock(return_value=(False, dead_order))

        with patch(
            'webui.backend.routes.mmm.mmm_audit_log.get_event_log',
            return_value=mock_event_log,
        ):
            result = _run(executor.smart_execute(
                symbol='C-BTC-90000-170426',
                side='sell',
                size=5,
                session_id='test-001',
                max_reprice_attempts=1,  # fail fast
            ))

        assert result['success'] is False
        event_types = [c.kwargs.get('event_type', '') for c in mock_event_log.enqueue_event.call_args_list]
        assert 'ORDER_CANCELLED' in event_types, (
            f"ORDER_CANCELLED not written. Events: {event_types}"
        )

    @pytest.mark.sealed
    def test_c_se_3_successful_placement_writes_order_intent(self, executor):
        """On successful initial placement, ORDER_INTENT must be written (pre-fill durable record)."""
        mock_event_log = MagicMock()

        executor._fetch_quotes = AsyncMock(return_value=_good_quotes())
        executor._place_limit_order = AsyncMock(return_value=_order_result())
        filled = _filled_order(unfilled_size=0, size=5)
        executor._wait_for_fill = AsyncMock(return_value=(True, filled))
        executor._get_order_status = AsyncMock(return_value=filled)

        with patch(
            'webui.backend.routes.mmm.mmm_audit_log.get_event_log',
            return_value=mock_event_log,
        ):
            result = _run(executor.smart_execute(
                symbol='C-BTC-90000-170426',
                side='sell',
                size=5,
                session_id='test-001',
            ))

        assert result['success'] is True
        event_types = [c.kwargs.get('event_type', '') for c in mock_event_log.enqueue_event.call_args_list]
        assert 'ORDER_INTENT' in event_types, (
            f"ORDER_INTENT not written. Events: {event_types}"
        )


# =============================================================================
# C-SE-4 / C-SE-5: FIX-2.1 — fill_timeout override respected
# =============================================================================

class TestFillTimeoutOverride:

    @pytest.mark.sealed
    def test_c_se_4_custom_fill_timeout_passed_to_wait_for_fill(self, executor):
        """fill_timeout=20 must be passed to _wait_for_fill (DTE/gamma-aware timeout)."""
        executor._fetch_quotes = AsyncMock(return_value=_good_quotes())
        executor._place_limit_order = AsyncMock(return_value=_order_result())
        filled = _filled_order(unfilled_size=0, size=5)
        executor._wait_for_fill = AsyncMock(return_value=(True, filled))
        executor._get_order_status = AsyncMock(return_value=filled)

        with patch('webui.backend.routes.mmm.mmm_audit_log.get_event_log', return_value=MagicMock()):
            _run(executor.smart_execute(
                symbol='C-BTC-90000-170426',
                side='sell',
                size=5,
                fill_timeout=20,
            ))

        # _wait_for_fill must have been called with timeout=20
        assert executor._wait_for_fill.called
        call_kwargs = executor._wait_for_fill.call_args
        timeout_used = call_kwargs.kwargs.get('timeout') or call_kwargs.args[2]
        assert timeout_used == 20, f"Expected timeout=20, got {timeout_used}"

    @pytest.mark.sealed
    def test_c_se_5_default_fill_timeout_is_60(self, executor):
        """fill_timeout=None → _wait_for_fill must use FILL_TIMEOUT=60 (constant preserved)."""
        executor._fetch_quotes = AsyncMock(return_value=_good_quotes())
        executor._place_limit_order = AsyncMock(return_value=_order_result())
        filled = _filled_order(unfilled_size=0, size=5)
        executor._wait_for_fill = AsyncMock(return_value=(True, filled))
        executor._get_order_status = AsyncMock(return_value=filled)

        with patch('webui.backend.routes.mmm.mmm_audit_log.get_event_log', return_value=MagicMock()):
            _run(executor.smart_execute(
                symbol='C-BTC-90000-170426',
                side='sell',
                size=5,
                fill_timeout=None,
            ))

        call_kwargs = executor._wait_for_fill.call_args
        timeout_used = call_kwargs.kwargs.get('timeout') or call_kwargs.args[2]
        assert timeout_used == FILL_TIMEOUT == 60, (
            f"Expected default FILL_TIMEOUT={FILL_TIMEOUT}, got {timeout_used}"
        )


# =============================================================================
# C-SE-6: Successful fill returns correct dict
# =============================================================================

class TestSuccessfulFill:

    @pytest.mark.sealed
    def test_c_se_6_successful_fill_returns_correct_fields(self, executor):
        """Filled order must return success=True with fill_price, filled_size, order_id."""
        executor._fetch_quotes = AsyncMock(return_value=_good_quotes())
        executor._place_limit_order = AsyncMock(return_value=_order_result('ORD-XYZ'))
        filled = {
            'id': 'ORD-XYZ',
            'state': 'filled',
            'average_fill_price': '51.50',  # string — exchange returns strings
            'unfilled_size': 0,
        }
        executor._wait_for_fill = AsyncMock(return_value=(True, filled))
        executor._get_order_status = AsyncMock(return_value=filled)

        with patch('webui.backend.routes.mmm.mmm_audit_log.get_event_log', return_value=MagicMock()):
            result = _run(executor.smart_execute(
                symbol='C-BTC-90000-170426',
                side='sell',
                size=5,
            ))

        assert result['success'] is True
        assert result['order_id'] == 'ORD-XYZ'
        assert result['fill_price'] == 51.5
        assert result['filled_size'] == 5
        assert 'total_time' in result
        assert 'attempts' in result


# =============================================================================
# C-SE-7: max_buy_price cap at initial placement
# =============================================================================

class TestMaxBuyPriceCap:

    @pytest.mark.sealed
    def test_c_se_7_max_buy_price_exceeded_returns_failure_without_placing(self, executor):
        """When mid_price > max_buy_price at initial placement, must return failure
        WITHOUT placing any order (premium bounce guard)."""
        # mid_price = (50 + 52) / 2 = 51.0; cap = 45.0 → should abort
        executor._fetch_quotes = AsyncMock(return_value=_good_quotes())  # bid=50, ask=52
        executor._place_limit_order = AsyncMock(return_value=_order_result())

        with patch('webui.backend.routes.mmm.mmm_audit_log.get_event_log', return_value=MagicMock()):
            result = _run(executor.smart_execute(
                symbol='C-BTC-90000-170426',
                side='buy',
                size=5,
                max_buy_price=45.0,
            ))

        assert result['success'] is False
        assert 'cap' in result.get('error', '').lower() or 'above' in result.get('error', '').lower()
        # No order should have been placed
        executor._place_limit_order.assert_not_called()


# =============================================================================
# C-SE-8: No quotes available → immediate failure
# =============================================================================

class TestNoQuotes:

    @pytest.mark.sealed
    def test_c_se_8_no_quotes_returns_failure_immediately(self, executor):
        """When _fetch_quotes returns None/empty, smart_execute must return failure
        immediately without placing any order."""
        executor._fetch_quotes = AsyncMock(return_value=None)
        executor._place_limit_order = AsyncMock(return_value=_order_result())

        with patch('webui.backend.routes.mmm.mmm_audit_log.get_event_log', return_value=MagicMock()):
            result = _run(executor.smart_execute(
                symbol='C-BTC-90000-170426',
                side='sell',
                size=5,
            ))

        assert result['success'] is False
        executor._place_limit_order.assert_not_called()
