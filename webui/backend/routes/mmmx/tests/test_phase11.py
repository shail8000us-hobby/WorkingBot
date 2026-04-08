"""
MMMX Phase 11 Unit Tests — Granular Order Lifecycle Stream

Covers:
  - mmmx_websocket emits:
      mmmx_order_intent / mmmx_order_ack / mmmx_order_partial /
      mmmx_order_retry / mmmx_order_filled / mmmx_order_failed
  - MMMXExecutor smart_execute wiring:
      intent → ack → filled, preflight failure → failed,
      partial fill emits partial before filled
  - MMMXExecutor emergency_execute wiring:
      intent → ack/retry loops → failed terminal state
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..')
)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _quotes(bid=95.0, ask=105.0, tick=0.5):
    return {
        'best_bid': bid,
        'best_ask': ask,
        'tick_size': tick,
        'fresh': True,
    }


class TestOrderLifecycleEmitters:

    def test_emit_all_lifecycle_events(self):
        from webui.backend.routes.mmmx import mmmx_websocket as ws

        fake_socketio = MagicMock()
        ws.init_websocket(fake_socketio)

        ws.emit_order_intent(
            session_id='sid-11',
            symbol='C-BTC-100000-280326',
            side='sell',
            requested_size=10,
            mode='limit',
            attempt=1,
            client_order_id='coid-11',
            tranche_id=1,
            action='DEPLOY',
        )
        ws.emit_order_ack(
            session_id='sid-11',
            symbol='C-BTC-100000-280326',
            side='sell',
            requested_size=10,
            mode='limit',
            attempt=1,
            client_order_id='coid-11',
            order_id='ord-11',
            tranche_id=1,
            action='DEPLOY',
            price=100.0,
        )
        ws.emit_order_partial(
            session_id='sid-11',
            symbol='C-BTC-100000-280326',
            side='sell',
            requested_size=10,
            mode='limit',
            attempt=1,
            client_order_id='coid-11',
            order_id='ord-11',
            filled_size=6,
            residual_size=4,
            tranche_id=1,
            action='DEPLOY',
            avg_price=101.0,
        )
        ws.emit_order_retry(
            session_id='sid-11',
            symbol='C-BTC-100000-280326',
            side='sell',
            requested_size=10,
            mode='limit',
            attempt=1,
            client_order_id='coid-11',
            reason_code='TIMEOUT_REPRICE',
            reason='No fill, repricing',
            tranche_id=1,
            action='DEPLOY',
            order_id='ord-11',
        )
        ws.emit_order_filled(
            session_id='sid-11',
            symbol='C-BTC-100000-280326',
            side='sell',
            requested_size=10,
            mode='limit',
            attempt=2,
            client_order_id='coid-11',
            order_id='ord-12',
            filled_size=10,
            residual_size=0,
            avg_price=100.5,
            tranche_id=1,
            action='DEPLOY',
            fees_paid=0.01,
        )
        ws.emit_order_failed(
            session_id='sid-11',
            symbol='C-BTC-100000-280326',
            side='sell',
            requested_size=10,
            mode='limit',
            attempt=2,
            client_order_id='coid-11',
            reason_code='ORDER_DEAD',
            reason='Order cancelled',
            tranche_id=1,
            action='DEPLOY',
            order_id='ord-12',
            filled_size=6,
            residual_size=4,
        )

        calls = fake_socketio.emit.call_args_list
        event_names = [c.args[0] for c in calls]

        assert event_names == [
            'mmmx_order_intent',
            'mmmx_order_ack',
            'mmmx_order_partial',
            'mmmx_order_retry',
            'mmmx_order_filled',
            'mmmx_order_failed',
        ]

        for c in calls:
            payload = c.args[1]
            kwargs = c.kwargs
            assert payload['session_id'] == 'sid-11'
            assert 'timestamp' in payload
            assert kwargs.get('namespace') == '/'


class TestExecutorLifecycleWiring:

    def _make_executor(self):
        from webui.backend.routes.mmmx.mmmx_executor import MMMXExecutor
        return MMMXExecutor()

    def test_smart_execute_emits_intent_ack_filled(self):
        from webui.backend.routes.mmmx.mmmx_executor import MarginVerdict

        executor = self._make_executor()

        with patch.object(executor, '_create_rest_client', return_value=AsyncMock()), \
             patch.object(executor, '_fetch_open_orders_by_client_id', new=AsyncMock(return_value=None)), \
             patch.object(executor, 'preflight_margin_check', new=AsyncMock(return_value=MarginVerdict.OK)), \
             patch.object(executor, '_fetch_quotes', new=AsyncMock(return_value=_quotes())), \
             patch.object(executor, '_place_limit_order', new=AsyncMock(return_value={'id': 'ord-11', 'product_id': 42})), \
             patch.object(executor, '_wait_for_fill', new=AsyncMock(return_value=(True, {'state': 'filled', 'average_fill_price': '101.5', 'unfilled_size': 0}))), \
             patch.object(executor, '_get_order_status', new=AsyncMock(return_value={'state': 'filled', 'average_fill_price': '101.5', 'unfilled_size': 0})), \
             patch.object(executor, '_audit_trade'), \
             patch('webui.backend.routes.mmmx.mmmx_executor.asyncio.sleep', new=AsyncMock()), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_intent') as mock_intent, \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_ack') as mock_ack, \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_filled') as mock_filled, \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_partial') as mock_partial, \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_retry') as mock_retry, \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_failed') as mock_failed:

            result = _run(executor.smart_execute(
                symbol='C-BTC-100000-280326',
                side='sell',
                size=10,
                session_id='sid-11',
                tranche_id=1,
                action='DEPLOY',
            ))

        assert result.success is True
        assert result.filled_size == 10
        mock_intent.assert_called_once()
        mock_ack.assert_called_once()
        mock_filled.assert_called_once()
        mock_partial.assert_not_called()
        mock_retry.assert_not_called()
        mock_failed.assert_not_called()

    def test_smart_execute_preflight_block_emits_failed(self):
        from webui.backend.routes.mmmx.mmmx_executor import MarginVerdict

        executor = self._make_executor()

        with patch.object(executor, '_create_rest_client', return_value=AsyncMock()), \
             patch.object(executor, '_fetch_open_orders_by_client_id', new=AsyncMock(return_value=None)), \
             patch.object(executor, 'preflight_margin_check', new=AsyncMock(return_value=MarginVerdict.MARGIN_BLOCKED)), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_intent') as mock_intent, \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_failed') as mock_failed:

            result = _run(executor.smart_execute(
                symbol='C-BTC-100000-280326',
                side='sell',
                size=10,
                session_id='sid-11',
                tranche_id=1,
                action='DEPLOY',
            ))

        assert result.success is False
        assert result.reason == 'MARGIN_BLOCKED'
        mock_intent.assert_called_once()
        mock_failed.assert_called_once()
        assert mock_failed.call_args.kwargs['reason_code'] == 'MARGIN_BLOCKED'

    def test_smart_execute_partial_fill_emits_partial_then_filled(self):
        from webui.backend.routes.mmmx.mmmx_executor import MarginVerdict

        executor = self._make_executor()

        with patch.object(executor, '_create_rest_client', return_value=AsyncMock()), \
             patch.object(executor, '_fetch_open_orders_by_client_id', new=AsyncMock(return_value=None)), \
             patch.object(executor, 'preflight_margin_check', new=AsyncMock(return_value=MarginVerdict.OK)), \
             patch.object(executor, '_fetch_quotes', new=AsyncMock(return_value=_quotes())), \
             patch.object(executor, '_place_limit_order', new=AsyncMock(return_value={'id': 'ord-11', 'product_id': 42})), \
             patch.object(executor, '_wait_for_fill', new=AsyncMock(return_value=(True, {'state': 'filled', 'average_fill_price': '100.0', 'unfilled_size': 4}))), \
             patch.object(executor, '_get_order_status', new=AsyncMock(return_value={'state': 'filled', 'average_fill_price': '100.0', 'unfilled_size': 4})), \
             patch.object(executor, '_audit_trade'), \
             patch('webui.backend.routes.mmmx.mmmx_executor.asyncio.sleep', new=AsyncMock()), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_partial') as mock_partial, \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_filled') as mock_filled:

            result = _run(executor.smart_execute(
                symbol='C-BTC-100000-280326',
                side='sell',
                size=10,
                session_id='sid-11',
                tranche_id=1,
                action='DEPLOY',
            ))

        assert result.success is True
        assert result.filled_size == 6
        mock_partial.assert_called_once()
        assert mock_partial.call_args.kwargs['filled_size'] == 6
        assert mock_partial.call_args.kwargs['residual_size'] == 4
        mock_filled.assert_called_once()

    def test_emergency_execute_emits_retry_and_failed(self):
        executor = self._make_executor()

        mock_rest = AsyncMock()
        mock_rest.place_order_by_symbol = AsyncMock(return_value={'result': {'id': 'emrg-11', 'product_id': 42}})

        with patch.object(executor, '_create_rest_client', return_value=mock_rest), \
             patch.object(executor, '_fetch_quotes', new=AsyncMock(return_value=_quotes())), \
             patch.object(executor, '_get_order_status', new=AsyncMock(return_value={'state': 'cancelled'})), \
             patch('webui.backend.routes.mmmx.mmmx_executor.asyncio.sleep', new=AsyncMock()), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_intent') as mock_intent, \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_ack') as mock_ack, \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_retry') as mock_retry, \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_order_failed') as mock_failed:

            result = _run(executor.emergency_execute(
                symbol='C-BTC-100000-280326',
                side='buy',
                size=5,
                session_id='sid-emrg',
                tranche_id=3,
                action='EMERGENCY_CLOSE',
            ))

        assert result.success is False
        assert result.reason == 'EMERGENCY_NOT_FILLED'
        mock_intent.assert_called_once()
        assert mock_ack.call_count >= 1
        assert mock_retry.call_count >= 1
        mock_failed.assert_called()
