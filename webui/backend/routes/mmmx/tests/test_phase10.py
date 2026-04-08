"""
MMMX Phase 10 Unit Tests — Trigger Evaluation Contract (winner + ladder)

Covers:
  - mmmx_trigger.evaluate_with_ladder():
      * RUNNING session returns ordered ladder rows
      * Winner is priority-deterministic (DTE_CLOSE beats HARD_STOP)
      * Non-RUNNING session returns BLOCKED rows
      * evaluate() remains backward-compatible
  - mmmx_websocket.emit_trigger_evaluation():
      * Emits mmmx_trigger_evaluation with required payload fields
  - MMMXMonitor._heartbeat():
      * Emits trigger evaluation payload once per beat

This phase adds explainability contract plumbing without changing trigger
priority semantics from Phase 3.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..')
)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _future_expiry(days: float = 30.0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _make_session(status='RUNNING'):
    return {
        '_schema_version': 1,
        'session_id': 'test-p10-session-0001',
        'status': status,
        'expiry_datetime': _future_expiry(30),
        '_pnl_calculation_incomplete': False,
        'hard_stop_usd': 500.0,
        'portfolio_pnl': 0.0,
        'portfolio_delta': 0.0,
        '_naked_positions': [],
        '_whipsaw_score': 0,
        'beat_number': 3,
        '_last_beat_at': None,
        'tranches': [],
        'hedges': [],
        'total_premium_collected': 250.0,
        'tranches_deployed': 0,
        'tranches_remaining': 10,
        'total_hedge_cost_paid': 0.0,
        'active_hedges': 0,
        'ce_lot_balance': {},
        '_profit_booking_queue': [],
        'deployment_eligible_tranches': [],
        'params': {
            'close_at_dte': 7,
            'near_itm_delta': 0.55,
            'portfolio_delta_threshold': 0.15,
            'delta_drift_threshold': 0.35,
            'iv_spike_threshold_pct': 50,
            'iv_catastrophe_pct': 80,
            'hard_stop_multiplier': 2.0,
            'adjustment_interval_hours': 0.001,
        },
    }


class TestTriggerLadder:

    def _metrics(self, pnl=0.0, delta=0.0, dte=30.0, iv=None):
        return {
            'portfolio_pnl': pnl,
            'portfolio_delta': delta,
            'dte_days': dte,
            'iv_rank': iv,
            'lot_imbalance': {},
            'spot_price': None,
        }

    def test_priority_winner_and_skipped_rows(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate_with_ladder
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName

        session = _make_session(status='RUNNING')
        # Both DTE and hard stop are true; priority winner must be DTE_CLOSE.
        winner, rows = evaluate_with_ladder(
            session,
            self._metrics(pnl=-600.0, dte=5.0, iv=90.0),
        )

        assert winner is not None
        assert winner.trigger_name == TriggerName.DTE_CLOSE
        assert len(rows) == 7
        assert rows[0]['trigger_name'] == TriggerName.DTE_CLOSE
        assert rows[0]['status'] == 'FIRED'
        assert rows[0]['threshold'] == 7
        assert rows[0]['value'] == 5.0
        assert rows[1]['trigger_name'] == TriggerName.HARD_STOP
        assert rows[1]['status'] == 'SKIPPED_AFTER_WINNER'
        assert rows[1]['excluded_by'] == TriggerName.DTE_CLOSE
        assert rows[1]['data']['would_status'] == 'FIRED'

    def test_non_running_session_returns_blocked_rows(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate_with_ladder

        session = _make_session(status='PAUSED')
        winner, rows = evaluate_with_ladder(session, self._metrics())

        assert winner is None
        assert len(rows) == 7
        assert all(r['status'] == 'BLOCKED' for r in rows)

    def test_evaluate_backwards_compatible(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName

        session = _make_session(status='RUNNING')
        hit = evaluate(session, self._metrics(dte=6.0))

        assert hit is not None
        assert hit.trigger_name == TriggerName.DTE_CLOSE


class TestTriggerEvaluationEmitter:

    def test_emit_trigger_evaluation_payload(self):
        from webui.backend.routes.mmmx import mmmx_websocket as ws

        fake_socketio = MagicMock()
        ws.init_websocket(fake_socketio)

        ws.emit_trigger_evaluation(
            session_id='sid-001',
            beat_number=11,
            status='RUNNING',
            winner={
                'trigger_name': 'IV_SPIKE',
                'reason': 'IV rank 60.0% >= spike threshold 50%',
                'severity': 'warning',
                'data': {'iv_rank': 60.0, 'iv_spike_threshold_pct': 50},
            },
            ladder=[
                {
                    'priority': 1,
                    'trigger_name': 'DTE_CLOSE',
                    'severity': 'critical',
                    'status': 'NOT_MET',
                    'reason': 'DTE 20.00 days > close_at_dte 7',
                    'data': {'dte_days': 20.0, 'close_at_dte': 7},
                },
            ],
            metrics={'portfolio_pnl': 42.0, 'dte_days': 20.0},
        )

        fake_socketio.emit.assert_called_once()
        event_name, payload = fake_socketio.emit.call_args[0][:2]
        kwargs = fake_socketio.emit.call_args.kwargs

        assert event_name == 'mmmx_trigger_evaluation'
        assert kwargs.get('namespace') == '/'
        assert payload['session_id'] == 'sid-001'
        assert payload['beat_number'] == 11
        assert payload['status'] == 'RUNNING'
        assert payload['winner']['trigger_name'] == 'IV_SPIKE'
        assert isinstance(payload.get('ladder'), list)
        assert 'timestamp' in payload  # injected by _emit


class TestMonitorTriggerEvaluationWiring:

    def test_heartbeat_emits_trigger_evaluation_once(self):
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor

        session = _make_session(status='RUNNING')

        storage = MagicMock()
        storage.load_session.return_value = session
        storage.get_generation.return_value = 1
        storage.save_session.return_value = None

        decision = SimpleNamespace(should_deploy=False, spot_move_pct=0.0)

        with patch('webui.backend.routes.mmmx.mmmx_storage.get_storage', return_value=storage), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_portfolio_pnl', return_value=15.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_portfolio_delta', return_value=0.02), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_lot_imbalance', return_value={'imbalance_pct': 0.0}), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_dte_days', return_value=20.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.recalc_hard_stop', return_value=500.0), \
             patch('webui.backend.routes.mmmx.mmmx_trigger.evaluate_with_ladder', return_value=(None, [
                 {
                     'priority': 1,
                     'trigger_name': 'DTE_CLOSE',
                     'severity': 'critical',
                     'status': 'NOT_MET',
                     'reason': 'DTE 20.00 days > close_at_dte 7',
                     'data': {'dte_days': 20.0, 'close_at_dte': 7},
                 }
             ])), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_trigger_evaluation') as mock_emit_eval, \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_heartbeat'), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_activity.log_activity'), \
             patch('webui.backend.routes.mmmx.mmmx_reconciler.check_naked_watchdog', new=AsyncMock(return_value=[])), \
             patch('webui.backend.routes.mmmx.mmmx_atm_shield.evaluate_and_fire', new=AsyncMock(return_value=[])), \
             patch('webui.backend.routes.mmmx.mmmx_whipsaw.decay_score'), \
             patch('webui.backend.routes.mmmx.mmmx_whipsaw.score_tick'), \
             patch('webui.backend.routes.mmmx.mmmx_initializer.clear_queue_on_retrace'), \
             patch('webui.backend.routes.mmmx.mmmx_initializer.check_deploy_conditions', return_value=decision), \
             patch('webui.backend.routes.mmmx.mmmx_hedger.tick', new=AsyncMock(return_value=[])):

            monitor = MMMXMonitor('test-p10-session-0001', my_generation=1)
            monitor._running = True
            _run(monitor._heartbeat())

        mock_emit_eval.assert_called_once()
        kwargs = mock_emit_eval.call_args.kwargs
        assert kwargs['session_id'] == 'test-p10-session-0001'
        assert kwargs['status'] == 'RUNNING'
        assert isinstance(kwargs['ladder'], list)
