"""
MMMX Phase 3 Unit Tests

Covers: mmmx_safety, mmmx_trigger, mmmx_monitor heartbeat (Phase 3 hot-path).

Exit criteria per MMMX_IMPLEMENTATION_PLAN.md Section 4 Phase 3:
  - SafetyVerdict: stale generation -> abort; PNL incomplete -> skip_beat;
    expired DTE -> abort; RUNNING status passes
  - Trigger priority: HARD_STOP fires over DEPLOY_TRANCHE when both conditions met
  - Trigger: DTE_CLOSE fires at dte_days <= close_at_dte (e.g. 6.9 <= 7)
  - Trigger: HARD_STOP fires when portfolio_pnl <= -hard_stop_usd
  - Trigger: returns None if session status is PAUSED
  - Trigger: NEAR_ITM scan — finds position with delta >= near_itm_delta threshold
  - Monitor heartbeat (mocked executor + storage): PnLIncompleteError -> beat skipped
  - Monitor heartbeat: HARD_STOP trigger fires -> _dispatch_close_all -> COMPLETE
  - Monitor heartbeat: DTE_CLOSE trigger fires -> _dispatch_close_all -> COMPLETE
  - Monitor heartbeat: no trigger -> beat_number incremented, session saved
  - Monitor heartbeat: _save_session returns False -> _stale_abort_gen set, _running=False
  - MMM isolation scan: mmmx_safety and mmmx_trigger have no routes.mmm.* imports
"""

import asyncio
import inspect
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone, timedelta

# -- Ensure package root is importable ----------------------------------------
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# =============================================================================
# Helpers
# =============================================================================

def _run(coro):
    """Run a coroutine in a fresh event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _future_expiry(days: float = 30.0) -> str:
    """Return an ISO UTC datetime string N days in the future."""
    dt = datetime.now(timezone.utc) + timedelta(days=days)
    return dt.isoformat()


def _past_expiry() -> str:
    """Return an ISO UTC datetime string 1 day in the past."""
    dt = datetime.now(timezone.utc) - timedelta(days=1)
    return dt.isoformat()


def _make_session(
    status='RUNNING',
    pnl_incomplete=False,
    expiry_days=30.0,
    hard_stop_usd=500.0,
    tranches=None,
    portfolio_pnl=0.0,
    portfolio_delta=0.0,
) -> dict:
    """Build a minimal session dict suitable for safety / trigger tests."""
    return {
        '_schema_version': 1,
        'session_id': 'test-session-id-1234',
        'status': status,
        'expiry_datetime': _future_expiry(expiry_days) if expiry_days >= 0 else _past_expiry(),
        '_pnl_calculation_incomplete': pnl_incomplete,
        'hard_stop_usd': hard_stop_usd,
        'portfolio_pnl': portfolio_pnl,
        'portfolio_delta': portfolio_delta,
        '_naked_positions': [],
        '_whipsaw_score': 0,
        'beat_number': 0,
        '_last_beat_at': None,
        'tranches': tranches or [],
        'hedges': [],
        'total_premium_collected': 250.0,
        'tranches_deployed': 0,
        'tranches_remaining': 10,
        'total_hedge_cost_paid': 0.0,
        'active_hedges': 0,
        'ce_lot_balance': {},
        'params': {
            'close_at_dte': 7,
            'near_itm_delta': 0.55,
            'portfolio_delta_threshold': 0.15,
            'delta_drift_threshold': 0.35,
            'iv_spike_threshold_pct': 50,
            'iv_catastrophe_pct': 80,
            'hard_stop_multiplier': 2.0,
            'adjustment_interval_hours': 0.001,  # tiny for fast tests
        },
    }


def _make_active_leg(
    lots=10,
    entry_premium=100.0,
    current_premium=90.0,
    entry_delta=0.30,
    current_delta=0.30,
    symbol='C-BTC-90000-280326',
    status='ACTIVE',
) -> dict:
    return {
        'lots': lots,
        'entry_premium': entry_premium,
        'current_premium': current_premium,
        'entry_delta': entry_delta,
        'current_delta': current_delta,
        'symbol': symbol,
        'status': status,
        'realized_pnl': 0.0,
        'fees_paid': 0.0,
        '_being_closed': False,
    }


def _make_tranche(tranche_id=1, ce_delta=0.30, pe_delta=0.30, status='ACTIVE') -> dict:
    return {
        'tranche_id': tranche_id,
        'type': 'deployment',
        'ce': _make_active_leg(
            entry_delta=ce_delta, current_delta=ce_delta,
            symbol=f'C-BTC-90000-280326', status=status,
        ),
        'pe': _make_active_leg(
            entry_delta=pe_delta, current_delta=pe_delta,
            symbol=f'P-BTC-70000-280326', status=status,
        ),
    }


# =============================================================================
# Safety Tests
# =============================================================================

class TestSafetyVerdict:
    """pre_beat_check() returns correct verdict for each check."""

    def test_stale_generation_aborts(self):
        from webui.backend.routes.mmmx.mmmx_safety import pre_beat_check
        session = _make_session()
        verdict = pre_beat_check(session, stored_gen=2, my_generation=1)
        assert verdict.abort is True
        assert verdict.ok is False
        assert verdict.reason == 'STALE_GENERATION'

    def test_matching_generation_does_not_abort(self):
        from webui.backend.routes.mmmx.mmmx_safety import pre_beat_check
        session = _make_session()
        # No abort from gen check — but DTE future so should be ok=True
        verdict = pre_beat_check(session, stored_gen=1, my_generation=1)
        assert verdict.abort is False

    def test_pnl_incomplete_causes_skip_beat(self):
        from webui.backend.routes.mmmx.mmmx_safety import pre_beat_check
        session = _make_session(pnl_incomplete=True)
        verdict = pre_beat_check(session, stored_gen=1, my_generation=1)
        assert verdict.skip_beat is True
        assert verdict.abort is False
        assert verdict.reason == 'PNL_INCOMPLETE'

    def test_expired_dte_aborts(self):
        """compute_dte_days returns -1.0 when expiry_datetime is None."""
        from webui.backend.routes.mmmx.mmmx_safety import pre_beat_check
        session = _make_session(expiry_days=30)
        session['expiry_datetime'] = None  # None -> compute_dte_days returns -1.0
        verdict = pre_beat_check(session, stored_gen=1, my_generation=1)
        assert verdict.abort is True
        assert verdict.reason == 'EXPIRY_PAST'

    def test_running_status_passes(self):
        from webui.backend.routes.mmmx.mmmx_safety import pre_beat_check
        session = _make_session(status='RUNNING')
        verdict = pre_beat_check(session, stored_gen=3, my_generation=3)
        assert verdict.ok is True
        assert verdict.abort is False
        assert verdict.skip_beat is False

    def test_paused_status_passes_safety(self):
        """PAUSED is in the allowed set ('RUNNING', 'PAUSED') — safety passes it through.
        Trigger evaluator (not safety) handles skipping evaluation for PAUSED."""
        from webui.backend.routes.mmmx.mmmx_safety import pre_beat_check
        session = _make_session(status='PAUSED')
        verdict = pre_beat_check(session, stored_gen=1, my_generation=1)
        # PAUSED passes status guard — ok=True (trigger eval skips it separately)
        assert verdict.abort is False
        assert verdict.skip_beat is False
        assert verdict.ok is True

    def test_draft_status_skips_beat(self):
        from webui.backend.routes.mmmx.mmmx_safety import pre_beat_check
        session = _make_session(status='DRAFT')
        verdict = pre_beat_check(session, stored_gen=1, my_generation=1)
        assert verdict.skip_beat is True

    def test_naked_positions_do_not_abort(self):
        """Naked positions trigger a warning log but do NOT abort the beat."""
        from webui.backend.routes.mmmx.mmmx_safety import pre_beat_check
        session = _make_session()
        session['_naked_positions'] = [{'tranche_id': 1, 'side': 'ce'}]
        verdict = pre_beat_check(session, stored_gen=1, my_generation=1)
        assert verdict.ok is True
        assert verdict.abort is False
        assert verdict.skip_beat is False

    def test_generation_check_beats_pnl_incomplete(self):
        """STALE_GENERATION aborts before PNL_INCOMPLETE can skip_beat."""
        from webui.backend.routes.mmmx.mmmx_safety import pre_beat_check
        session = _make_session(pnl_incomplete=True)
        verdict = pre_beat_check(session, stored_gen=5, my_generation=2)
        assert verdict.abort is True
        assert verdict.reason == 'STALE_GENERATION'


# =============================================================================
# Trigger Tests
# =============================================================================

class TestTriggerEvaluate:
    """evaluate() returns correct TriggerHit (or None) for each scenario."""

    def _metrics(self, pnl=0.0, delta=0.0, dte=30.0, iv=None) -> dict:
        return {
            'portfolio_pnl':   pnl,
            'portfolio_delta': delta,
            'dte_days':        dte,
            'iv_rank':         iv,
            'lot_imbalance':   {},
            'spot_price':      None,
        }

    def test_returns_none_when_paused(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        session = _make_session(status='PAUSED')
        result = evaluate(session, self._metrics())
        assert result is None

    def test_returns_none_when_no_trigger(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        result = evaluate(session, self._metrics(pnl=100.0, dte=20.0))
        assert result is None

    def test_dte_close_fires_at_threshold(self):
        """dte_days <= close_at_dte (6.9 <= 7) fires DTE_CLOSE."""
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName
        session = _make_session(status='RUNNING')
        result = evaluate(session, self._metrics(dte=6.9))
        assert result is not None
        assert result.trigger_name == TriggerName.DTE_CLOSE

    def test_dte_close_fires_at_exact_threshold(self):
        """dte_days == close_at_dte exactly also fires."""
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName
        session = _make_session(status='RUNNING')
        result = evaluate(session, self._metrics(dte=7.0))
        assert result is not None
        assert result.trigger_name == TriggerName.DTE_CLOSE

    def test_dte_does_not_fire_above_threshold(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        result = evaluate(session, self._metrics(dte=7.1, pnl=0.0))
        # Should not fire DTE_CLOSE; might fire nothing
        if result is not None:
            from webui.backend.routes.mmmx.mmmx_constants import TriggerName
            assert result.trigger_name != TriggerName.DTE_CLOSE

    def test_hard_stop_fires_when_pnl_below_threshold(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        # portfolio_pnl <= -500
        result = evaluate(session, self._metrics(pnl=-500.0, dte=30.0))
        assert result is not None
        assert result.trigger_name == TriggerName.HARD_STOP

    def test_hard_stop_fires_below_threshold(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        result = evaluate(session, self._metrics(pnl=-600.0, dte=30.0))
        assert result is not None
        assert result.trigger_name == TriggerName.HARD_STOP

    def test_hard_stop_does_not_fire_above_threshold(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        result = evaluate(session, self._metrics(pnl=-499.9, dte=30.0))
        if result is not None:
            from webui.backend.routes.mmmx.mmmx_constants import TriggerName
            assert result.trigger_name != TriggerName.HARD_STOP

    def test_dte_close_fires_before_hard_stop(self):
        """DTE_CLOSE (priority 1) beats HARD_STOP (priority 2) when both conditions met."""
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        # Both conditions: dte <= 7 AND pnl <= -500
        result = evaluate(session, self._metrics(pnl=-600.0, dte=5.0))
        assert result is not None
        assert result.trigger_name == TriggerName.DTE_CLOSE  # DTE wins (priority 1)

    def test_near_itm_fires_when_delta_high(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        # Tranche with high delta
        tranche = _make_tranche(tranche_id=1, ce_delta=0.60)  # >= 0.55 threshold
        session['tranches'] = [tranche]
        result = evaluate(session, self._metrics(pnl=-100.0, dte=20.0))
        assert result is not None
        assert result.trigger_name == TriggerName.NEAR_ITM
        assert result.data['side'] == 'ce'
        assert result.data['delta'] >= 0.55

    def test_near_itm_does_not_fire_when_delta_below_threshold(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        tranche = _make_tranche(tranche_id=1, ce_delta=0.40)  # below 0.55
        session['tranches'] = [tranche]
        result = evaluate(session, self._metrics(pnl=-100.0, dte=20.0))
        if result is not None:
            from webui.backend.routes.mmmx.mmmx_constants import TriggerName
            assert result.trigger_name != TriggerName.NEAR_ITM

    def test_near_itm_uses_abs_delta(self):
        """PE delta is stored as negative; abs() must be used."""
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        tranche = _make_tranche(tranche_id=1, ce_delta=0.30, pe_delta=-0.60)
        session['tranches'] = [tranche]
        result = evaluate(session, self._metrics(pnl=-100.0, dte=20.0))
        assert result is not None
        assert result.trigger_name == TriggerName.NEAR_ITM
        assert result.data['side'] == 'pe'

    def test_portfolio_delta_fires_when_exceeded(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        # abs(0.20) >= 0.15 threshold
        result = evaluate(session, self._metrics(delta=0.20, dte=30.0, pnl=-100.0))
        assert result is not None
        assert result.trigger_name == TriggerName.PORTFOLIO_DELTA

    def test_iv_catastrophe_fires_when_iv_high(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        result = evaluate(session, self._metrics(dte=20.0, pnl=-100.0, iv=85.0))
        assert result is not None
        assert result.trigger_name == TriggerName.IV_CATASTROPHE

    def test_iv_spike_fires_below_catastrophe(self):
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        # iv=55 >= iv_spike=50 but < iv_catastrophe=80
        result = evaluate(session, self._metrics(dte=20.0, pnl=-100.0, iv=55.0))
        assert result is not None
        assert result.trigger_name == TriggerName.IV_SPIKE

    def test_none_iv_skips_iv_checks(self):
        """iv_rank=None means IV checks are skipped entirely."""
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        result = evaluate(session, self._metrics(dte=20.0, pnl=-100.0, iv=None))
        if result is not None:
            from webui.backend.routes.mmmx.mmmx_constants import TriggerName
            assert result.trigger_name not in (
                TriggerName.IV_CATASTROPHE,
                TriggerName.IV_SPIKE,
            )

    def test_delta_drift_fires(self):
        """Delta drift fires when abs(current-entry) >= threshold but NEAR_ITM doesn't fire.
        Use current_delta below near_itm threshold (0.55) but with high drift."""
        from webui.backend.routes.mmmx.mmmx_trigger import evaluate
        from webui.backend.routes.mmmx.mmmx_constants import TriggerName
        session = _make_session(status='RUNNING')
        session['hard_stop_usd'] = 500.0
        # entry=0.10, current=0.50 -> drift=0.40 >= 0.35, but 0.50 < 0.55 (no NEAR_ITM)
        tranche = {
            'tranche_id': 1,
            'type': 'deployment',
            'ce': _make_active_leg(entry_delta=0.10, current_delta=0.50),
            'pe': _make_active_leg(entry_delta=0.20, current_delta=0.20),
        }
        session['tranches'] = [tranche]
        result = evaluate(session, self._metrics(dte=20.0, pnl=-100.0))
        assert result is not None
        assert result.trigger_name == TriggerName.DELTA_DRIFT


# =============================================================================
# Monitor Heartbeat Tests (mocked storage + executor)
# =============================================================================

class TestMonitorHeartbeat:
    """Tests for MMMXMonitor._heartbeat() using mocked dependencies."""

    def _make_monitor(self, session_id='sess-0001', my_gen=1) -> 'MMMXMonitor':
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor
        m = MMMXMonitor(session_id=session_id, my_generation=my_gen)
        m._running = True
        return m

    def _make_storage_mock(self, session: dict, stored_gen: int = 1):
        """Build a mock storage that returns the given session and generation."""
        storage = MagicMock()
        storage.load_session.return_value = session
        storage.get_generation.return_value = stored_gen
        storage.save_session.return_value = None  # no exception = success
        return storage

    def _patch_imports(self, storage_mock, executor_mock=None):
        """Return a dict of patch targets for heartbeat imports."""
        patches = {
            'webui.backend.routes.mmmx.mmmx_storage.get_storage': lambda: storage_mock,
            'webui.backend.routes.mmmx.mmmx_websocket.emit_heartbeat': MagicMock(),
            'webui.backend.routes.mmmx.mmmx_websocket.emit_safety': MagicMock(),
            'webui.backend.routes.mmmx.mmmx_activity.log_activity': MagicMock(),
            'webui.backend.routes.mmmx.mmmx_telegram.alert_hard_stop': MagicMock(),
            'webui.backend.routes.mmmx.mmmx_telegram.alert_dte_close': MagicMock(),
            'webui.backend.routes.mmmx.mmmx_telegram.alert_session_complete': MagicMock(),
        }
        return patches

    def test_pnl_incomplete_skips_beat_and_saves(self):
        """PnLIncompleteError -> beat skipped, session saved with _pnl_calculation_incomplete=True."""
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor
        from webui.backend.routes.mmmx.mmmx_engine import PnLIncompleteError

        session = _make_session(status='RUNNING', expiry_days=30)
        session['_pnl_calculation_incomplete'] = False
        storage = self._make_storage_mock(session, stored_gen=1)

        monitor = self._make_monitor(my_gen=1)

        saved_sessions = []

        def fake_save(s, expected_gen):
            saved_sessions.append(dict(s))

        storage.save_session.side_effect = fake_save

        with patch('webui.backend.routes.mmmx.mmmx_storage.get_storage', return_value=storage), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_portfolio_pnl',
                   side_effect=PnLIncompleteError("missing quote")), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_heartbeat'), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_activity.log_activity'):
            _run(monitor._heartbeat())

        assert len(saved_sessions) == 1
        assert saved_sessions[0]['_pnl_calculation_incomplete'] is True

    def test_no_trigger_increments_beat_and_saves(self):
        """No trigger -> beat_number incremented, session saved."""
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor

        session = _make_session(status='RUNNING', expiry_days=30)
        session['hard_stop_usd'] = 500.0
        session['beat_number'] = 5
        storage = self._make_storage_mock(session, stored_gen=1)

        saved_sessions = []

        def fake_save(s, expected_gen):
            saved_sessions.append(dict(s))

        storage.save_session.side_effect = fake_save

        monitor = self._make_monitor(my_gen=1)

        with patch('webui.backend.routes.mmmx.mmmx_storage.get_storage', return_value=storage), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_portfolio_pnl', return_value=50.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_portfolio_delta', return_value=0.01), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_lot_imbalance',
                   return_value={'total_ce_lots': 10, 'total_pe_lots': 10, 'imbalance_pct': 0.0}), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_dte_days', return_value=20.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.recalc_hard_stop', return_value=500.0), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_heartbeat'), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_activity.log_activity'), \
             patch('webui.backend.routes.mmmx.mmmx_audit_log.get_audit_log', return_value=MagicMock()):
            _run(monitor._heartbeat())

        assert len(saved_sessions) == 1
        assert saved_sessions[0]['beat_number'] == 6  # incremented from 5

    def test_save_session_false_sets_stale_abort(self):
        """_save_session returns False -> _stale_abort_gen set, _running=False."""
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor
        from webui.backend.routes.mmmx.mmmx_storage import GenerationConflict

        session = _make_session(status='RUNNING', expiry_days=30)
        session['hard_stop_usd'] = 500.0
        storage = self._make_storage_mock(session, stored_gen=1)

        # save_session raises GenerationConflict -> _save_session returns False
        storage.save_session.side_effect = GenerationConflict("conflict")

        monitor = self._make_monitor(my_gen=1)

        with patch('webui.backend.routes.mmmx.mmmx_storage.get_storage', return_value=storage), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_portfolio_pnl', return_value=50.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_portfolio_delta', return_value=0.01), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_lot_imbalance',
                   return_value={'total_ce_lots': 10, 'total_pe_lots': 10, 'imbalance_pct': 0.0}), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_dte_days', return_value=20.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.recalc_hard_stop', return_value=500.0), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_heartbeat'), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_activity.log_activity'), \
             patch('webui.backend.routes.mmmx.mmmx_audit_log.get_audit_log', return_value=MagicMock()):
            _run(monitor._heartbeat())

        assert monitor._stale_abort_gen == 1
        assert monitor._running is False

    def test_hard_stop_trigger_dispatches_close_all(self):
        """HARD_STOP trigger -> _dispatch_close_all called -> session status COMPLETE."""
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor
        from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult

        session = _make_session(status='RUNNING', expiry_days=30)
        session['hard_stop_usd'] = 500.0
        session['portfolio_pnl'] = -600.0

        # Add an active tranche so there's something to close
        tranche = _make_tranche(tranche_id=1)
        session['tranches'] = [tranche]

        storage = self._make_storage_mock(session, stored_gen=1)
        saved_sessions = []

        def fake_save(s, expected_gen):
            saved_sessions.append(dict(s))

        storage.save_session.side_effect = fake_save

        mock_executor = MagicMock()
        mock_executor.emergency_execute = AsyncMock(return_value=ExecutionResult(
            success=True,
            filled_size=10,
            avg_price=95.0,
            order_id='ord-123',
            client_order_id='coid-123',
            fees_paid=0.05,
        ))

        mock_audit = MagicMock()

        monitor = self._make_monitor(my_gen=1)

        with patch('webui.backend.routes.mmmx.mmmx_storage.get_storage', return_value=storage), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_portfolio_pnl', return_value=-600.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_portfolio_delta', return_value=0.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_lot_imbalance',
                   return_value={'total_ce_lots': 10, 'total_pe_lots': 10, 'imbalance_pct': 0.0}), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_dte_days', return_value=20.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.recalc_hard_stop', return_value=500.0), \
             patch('webui.backend.routes.mmmx.mmmx_executor.get_executor', return_value=mock_executor), \
             patch('webui.backend.routes.mmmx.mmmx_audit_log.get_audit_log', return_value=mock_audit), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_heartbeat'), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_activity.log_activity'), \
             patch('webui.backend.routes.mmmx.mmmx_telegram.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_telegram.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_telegram.alert_session_complete'):
            _run(monitor._heartbeat())

        # Session should be saved as COMPLETE
        assert len(saved_sessions) >= 1
        final_session = saved_sessions[-1]
        assert final_session['status'] == 'COMPLETE'
        # Monitor should stop
        assert monitor._running is False

    def test_dte_close_trigger_dispatches_close_all(self):
        """DTE_CLOSE trigger -> _dispatch_close_all called -> session status COMPLETE."""
        from webui.backend.routes.mmmx.mmmx_monitor import MMMXMonitor
        from webui.backend.routes.mmmx.mmmx_executor import ExecutionResult

        session = _make_session(status='RUNNING', expiry_days=30)
        session['hard_stop_usd'] = 500.0

        tranche = _make_tranche(tranche_id=1)
        session['tranches'] = [tranche]

        storage = self._make_storage_mock(session, stored_gen=1)
        saved_sessions = []

        def fake_save(s, expected_gen):
            saved_sessions.append(dict(s))

        storage.save_session.side_effect = fake_save

        mock_executor = MagicMock()
        mock_executor.emergency_execute = AsyncMock(return_value=ExecutionResult(
            success=True,
            filled_size=10,
            avg_price=95.0,
        ))
        mock_audit = MagicMock()

        monitor = self._make_monitor(my_gen=1)

        with patch('webui.backend.routes.mmmx.mmmx_storage.get_storage', return_value=storage), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_portfolio_pnl', return_value=50.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_portfolio_delta', return_value=0.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_lot_imbalance',
                   return_value={'total_ce_lots': 10, 'total_pe_lots': 10, 'imbalance_pct': 0.0}), \
             patch('webui.backend.routes.mmmx.mmmx_engine.compute_dte_days', return_value=6.0), \
             patch('webui.backend.routes.mmmx.mmmx_engine.recalc_hard_stop', return_value=500.0), \
             patch('webui.backend.routes.mmmx.mmmx_executor.get_executor', return_value=mock_executor), \
             patch('webui.backend.routes.mmmx.mmmx_audit_log.get_audit_log', return_value=mock_audit), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_heartbeat'), \
             patch('webui.backend.routes.mmmx.mmmx_websocket.emit_safety'), \
             patch('webui.backend.routes.mmmx.mmmx_activity.log_activity'), \
             patch('webui.backend.routes.mmmx.mmmx_telegram.alert_hard_stop'), \
             patch('webui.backend.routes.mmmx.mmmx_telegram.alert_dte_close'), \
             patch('webui.backend.routes.mmmx.mmmx_telegram.alert_session_complete'):
            _run(monitor._heartbeat())

        assert len(saved_sessions) >= 1
        final_session = saved_sessions[-1]
        assert final_session['status'] == 'COMPLETE'
        assert monitor._running is False


# =============================================================================
# MMM Isolation Scan
# =============================================================================

class TestMMMIsolation:
    """Phase 3 new modules must not import from routes.mmm.*"""

    def _check_module_isolation(self, module_name: str) -> None:
        import importlib
        import re
        mod = importlib.import_module(f'webui.backend.routes.mmmx.{module_name}')
        src = inspect.getsource(mod)
        # Check for actual import statements referencing routes.mmm (not just docs/comments)
        # Pattern: 'import' or 'from' followed by routes.mmm anywhere on the line
        lines = src.splitlines()
        violations = [
            line.strip() for line in lines
            if re.search(r'^\s*(import|from)\s+.*routes\.mmm', line)
        ]
        assert not violations, (
            f"{module_name} imports from routes.mmm — isolation violation: {violations}"
        )

    def test_mmmx_safety_isolation(self):
        self._check_module_isolation('mmmx_safety')

    def test_mmmx_trigger_isolation(self):
        self._check_module_isolation('mmmx_trigger')

    def test_mmmx_monitor_isolation(self):
        """mmmx_monitor must not import routes.mmm — only mmmx_margin_guardian may."""
        self._check_module_isolation('mmmx_monitor')

    def test_mmmx_constants_isolation(self):
        self._check_module_isolation('mmmx_constants')

    def test_mmmx_engine_isolation(self):
        self._check_module_isolation('mmmx_engine')
