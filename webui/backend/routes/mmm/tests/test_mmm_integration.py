"""
Test MMM Integration — end-to-end flow tests.

Tests:
  - Trigger evaluation → adjustment flow
  - Session state consistency
  - API endpoint smoke tests
  - State model creation and initialization
  - Config validation
"""

import pytest
from copy import deepcopy


# ---------------------------------------------------------------------------
# State Model Tests
# ---------------------------------------------------------------------------

class TestStateModel:
    """Test mmm_state.py functions."""

    def test_create_session_has_required_fields(self):
        from webui.backend.routes.mmm.mmm_state import create_session
        session = create_session(params={'expiry': '28MAR26'})

        assert 'session_id' in session
        assert 'strategy_status' in session
        assert session['strategy_status'] == 'IDLE'
        assert 'params' in session
        assert 'ce' in session
        assert 'pe' in session
        assert 'adjustment_count' in session
        assert 'realized_pnl' in session

    def test_create_session_with_custom_params(self):
        from webui.backend.routes.mmm.mmm_state import create_session
        session = create_session(params={'expiry': '28MAR26', 'initial_lots': 20, 'max_loss_amount': 10000})

        assert session['params']['initial_lots'] == 20
        assert session['params']['max_loss_amount'] == 10000

    def test_create_side_state(self):
        from webui.backend.routes.mmm.mmm_state import create_side_state
        # Signature: create_side_state(side, ...) — side is required
        side = create_side_state('ce')

        assert side['original_lots'] == 0
        assert side['active_lots'] == 0
        assert side['total_lots'] == 0
        assert side['frozen_total_lots'] == 0
        assert side['adjustment_fills'] == []
        assert side['frozen_positions'] == []

    def test_initialize_side_from_entry(self):
        from webui.backend.routes.mmm.mmm_state import create_session, initialize_side_from_entry
        session = create_session(params={'expiry': '28MAR26'})

        # symbol= kwarg removed from current API
        initialize_side_from_entry(session, 'ce', strike=100000, premium=100.0, lots=10)

        ce = session['ce']
        assert ce['original_strike'] == 100000
        assert ce['active_strike'] == 100000
        assert ce['original_premium'] == 100.0
        assert ce['original_lots'] == 10
        assert ce['active_lots'] == 10
        assert ce['total_lots'] == 10

    def test_recompute_side_lots(self):
        from webui.backend.routes.mmm.mmm_state import create_session, initialize_side_from_entry, recompute_side_lots
        session = create_session(params={'expiry': '28MAR26'})
        initialize_side_from_entry(session, 'ce', strike=100000, premium=100.0, lots=10)

        # Add an adjustment position to positions[] (the single source of truth)
        session['ce'].setdefault('positions', []).append({
            'id': 'test-adj-1',
            'type': 'adjustment',
            'side': 'ce',
            'strike': 100000,
            'entry_premium': 120.0,
            'lots': 5,
            'status': 'active',
        })

        # recompute_side_lots takes side_state dict, not (session, 'ce')
        recompute_side_lots(session['ce'])
        ce = session['ce']
        assert ce['active_lots'] == 15
        assert ce['total_lots'] == 15

    def test_get_session_summary(self):
        from webui.backend.routes.mmm.mmm_state import create_session, get_session_summary
        session = create_session(params={'expiry': '28MAR26'})
        summary = get_session_summary(session)

        assert 'session_id' in summary
        assert 'status' in summary or 'strategy_status' in summary


# ---------------------------------------------------------------------------
# Config Validation Tests
# ---------------------------------------------------------------------------

class TestConfigValidation:
    """Test mmm_config.py validation."""

    def test_valid_params_pass(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        # validate_params returns (cleaned_params, errors_list)
        _, errors = validate_params({
            'initial_lots': 10,
            'max_loss_amount': 5000,
            'adjustment_interval': 300,
        })
        assert len(errors) == 0

    def test_negative_lots_rejected(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        _, errors = validate_params({'initial_lots': -5})
        assert len(errors) > 0

    def test_unknown_param_ignored_or_warned(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        # Unknown params should not cause crashes; returns (cleaned, errors)
        result = validate_params({'totally_fake_param': 42})
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_hot_reload_params(self):
        from webui.backend.routes.mmm.mmm_config import get_hot_reload_params
        hot = get_hot_reload_params()
        assert isinstance(hot, (list, set, tuple))
        assert len(hot) > 0


# ---------------------------------------------------------------------------
# Trigger Evaluation Tests
# ---------------------------------------------------------------------------

class TestTriggerEvaluation:
    """Test mmm_trigger.py evaluation."""

    def test_not_triggered_when_below(self):
        from webui.backend.routes.mmm.mmm_trigger import evaluate_triggers
        session = {
            'session_id': 'test-trig',
            'params': {'min_trigger_move': 3},
            'ce': {
                'active_strike': 100000,
                'active_lots': 10,
                'trigger_snapshot': {'100000': 100.0},
            },
            'pe': {
                'active_strike': 90000,
                'active_lots': 10,
                'trigger_snapshot': {'90000': 100.0},
            },
        }

        result = evaluate_triggers(session, ce_now=101.0, pe_now=101.0)
        assert result['ce_triggered'] is False
        assert result['pe_triggered'] is False

    def test_triggered_when_above(self):
        from webui.backend.routes.mmm.mmm_trigger import evaluate_triggers
        session = {
            'session_id': 'test-trig',
            'params': {'min_trigger_move': 3},
            'ce': {
                'active_strike': 100000,
                'active_lots': 10,
                'trigger_snapshot': {'100000': 100.0},
            },
            'pe': {
                'active_strike': 90000,
                'active_lots': 10,
                'trigger_snapshot': {'90000': 100.0},
            },
        }

        result = evaluate_triggers(session, ce_now=110.0, pe_now=101.0)
        assert result['ce_triggered'] is True
        assert result['pe_triggered'] is False


# ---------------------------------------------------------------------------
# Storage Tests
# ---------------------------------------------------------------------------

class TestStorage:
    """Test mmm_storage.py basic operations."""

    def test_save_and_load(self, tmp_path):
        import json
        import os

        # Patch storage directory
        from webui.backend.routes.mmm.mmm_storage import MMMStorage
        storage = MMMStorage(str(tmp_path / 'mmm_sessions.db'))

        from webui.backend.routes.mmm.mmm_state import create_session
        session = create_session(params={'expiry': '28MAR26'})
        sid = session['session_id']

        storage.save_session(session)
        loaded = storage.get_session(sid)

        assert loaded is not None
        assert loaded['session_id'] == sid

    def test_list_sessions(self, tmp_path):
        from webui.backend.routes.mmm.mmm_storage import MMMStorage
        storage = MMMStorage(str(tmp_path / 'mmm_sessions.db'))

        from webui.backend.routes.mmm.mmm_state import create_session
        s1 = create_session(params={'expiry': '28MAR26'})
        s2 = create_session(params={'expiry': '28MAR26'})

        storage.save_session(s1)
        storage.save_session(s2)

        sessions = storage.list_sessions()
        assert len(sessions) >= 2

    def test_delete_session(self, tmp_path):
        from webui.backend.routes.mmm.mmm_storage import MMMStorage
        storage = MMMStorage(str(tmp_path / 'mmm_sessions.db'))

        from webui.backend.routes.mmm.mmm_state import create_session
        session = create_session(params={'expiry': '28MAR26'})
        sid = session['session_id']

        storage.save_session(session)
        storage.delete_session(sid)

        assert storage.get_session(sid) is None
