"""
MMMX Phase 8 Unit Tests — UI + Hot Reload (WebUI Integration)

Covers:
  - hedge_distance_pct min bug fix (1.0 → 10.0)
  - split_hot_reload_patch: partial success (applied/rejected split)
  - PATCH /params: hard_stop recalc, audit, close_at_dte=6/7, mixed patch, 404, 422
  - POST /pause: RUNNING→PAUSED; monitor stopped only; PAUSED→409
  - POST /resume: PAUSED→RUNNING; monitor starts; COMPLETE→409
  - GET /scan_strikes: GATES_PASSED→no_live_chain; DRAFT→200 (no_live_chain)
  - POST /deploy_tranche1: valid body; missing fields→422; non-RUNNING→409
  - POST /profit_book: valid→queue; invalid tranche→422; non-RUNNING→409

All 385 prior tests must still pass.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..')
)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── Helpers ───────────────────────────────────────────────────────────────────

_PKG = 'webui.backend.routes.mmmx'


def _make_session(status='RUNNING', session_id='test-session-001'):
    return {
        'session_id': session_id,
        'status': status,
        'params': {
            'hard_stop_multiplier': 2.0,
            'close_at_dte': 7,
            'hedge_distance_pct': 20.0,
            'entry_dte_min': 20,
            'adjustment_interval_hours': 1,
        },
        'total_premium_collected': 500.0,
        'hard_stop_usd': 1000.0,
        'tranches': [],
        '_profit_booking_queue': [],
        'expiry_ddmmyy': '280326',
    }


def _mock_storage(session=None):
    s = MagicMock()
    s.load_session.return_value = session
    s.get_generation.return_value = 1
    s.save_session.return_value = True
    return s


def _make_app():
    from flask import Flask
    from webui.backend.routes.mmmx.mmmx_api import mmmx_bp
    app = Flask(__name__)
    app.register_blueprint(mmmx_bp)
    app.config['TESTING'] = True
    return app


# ══════════════════════════════════════════════════════════════════════════════
# hedge_distance_pct min bug fix
# ══════════════════════════════════════════════════════════════════════════════

class TestHedgeDistancePctBugFix:

    def test_hedge_distance_pct_5_rejected(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params, ConfigError
        with pytest.raises(ConfigError):
            validate_params({'hedge_distance_pct': 5.0})

    def test_hedge_distance_pct_9_rejected(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params, ConfigError
        with pytest.raises(ConfigError):
            validate_params({'hedge_distance_pct': 9.0})

    def test_hedge_distance_pct_10_accepted(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params
        validate_params({'hedge_distance_pct': 10.0})  # must not raise

    def test_hedge_distance_pct_50_accepted(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_params
        validate_params({'hedge_distance_pct': 50.0})


# ══════════════════════════════════════════════════════════════════════════════
# split_hot_reload_patch
# ══════════════════════════════════════════════════════════════════════════════

class TestSplitHotReloadPatch:

    def test_disallowed_key_rejected(self):
        from webui.backend.routes.mmmx.mmmx_config import split_hot_reload_patch
        applied, rejected = split_hot_reload_patch({'entry_dte_min': 15})
        assert 'entry_dte_min' in rejected
        assert 'entry_dte_min' not in applied
        assert 'hot-reloadable' in rejected['entry_dte_min'].lower() or 'not hot' in rejected['entry_dte_min'].lower()

    def test_allowed_key_applied(self):
        from webui.backend.routes.mmmx.mmmx_config import split_hot_reload_patch
        applied, rejected = split_hot_reload_patch({'close_at_dte': 7})
        assert applied == {'close_at_dte': 7}
        assert not rejected

    def test_close_at_dte_6_rejected(self):
        from webui.backend.routes.mmmx.mmmx_config import split_hot_reload_patch
        applied, rejected = split_hot_reload_patch({'close_at_dte': 6})
        assert 'close_at_dte' in rejected
        assert 'close_at_dte' not in applied
        reason = rejected['close_at_dte']
        assert ('gamma' in reason.lower() or 'hard' in reason.lower() or '7' in reason)

    def test_close_at_dte_7_accepted(self):
        from webui.backend.routes.mmmx.mmmx_config import split_hot_reload_patch
        applied, rejected = split_hot_reload_patch({'close_at_dte': 7})
        assert applied['close_at_dte'] == 7

    def test_hedge_distance_pct_5_rejected_in_split(self):
        from webui.backend.routes.mmmx.mmmx_config import split_hot_reload_patch
        applied, rejected = split_hot_reload_patch({'hedge_distance_pct': 5.0})
        assert 'hedge_distance_pct' in rejected
        assert 'hedge_distance_pct' not in applied

    def test_hedge_distance_pct_10_applied(self):
        from webui.backend.routes.mmmx.mmmx_config import split_hot_reload_patch
        applied, rejected = split_hot_reload_patch({'hedge_distance_pct': 10.0})
        assert applied.get('hedge_distance_pct') == 10.0
        assert not rejected

    def test_mixed_patch_partial_success(self):
        from webui.backend.routes.mmmx.mmmx_config import split_hot_reload_patch
        applied, rejected = split_hot_reload_patch({
            'hard_stop_multiplier': 3.0,
            'entry_dte_min': 15,
        })
        assert 'hard_stop_multiplier' in applied
        assert applied['hard_stop_multiplier'] == 3.0
        assert 'entry_dte_min' in rejected

    def test_all_disallowed_returns_empty_applied(self):
        from webui.backend.routes.mmmx.mmmx_config import split_hot_reload_patch
        applied, rejected = split_hot_reload_patch({
            'entry_dte_min': 15,
            'entry_dte_max': 45,
        })
        assert not applied
        assert len(rejected) == 2

    def test_entry_dte_min_reason_mentions_not_hot_reloadable(self):
        from webui.backend.routes.mmmx.mmmx_config import split_hot_reload_patch
        _, rejected = split_hot_reload_patch({'entry_dte_min': 20})
        assert 'entry_dte_min' in rejected
        assert 'not hot-reloadable' in rejected['entry_dte_min'] or 'hot-reloadable' in rejected['entry_dte_min']


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /params endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestHotReloadEndpoint:

    def test_unknown_session_returns_404(self):
        app = _make_app()
        storage = _mock_storage(session=None)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_config.split_hot_reload_patch',
                       return_value=({'close_at_dte': 7}, {})):
                with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                    resp = c.patch(
                        '/api/mmmx/session/nonexistent/params',
                        json={'params': {'close_at_dte': 7}},
                    )
        assert resp.status_code == 404

    def test_all_rejected_returns_422(self):
        app = _make_app()
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_config.split_hot_reload_patch',
                       return_value=({}, {'entry_dte_min': 'not hot-reloadable'})):
                resp = c.patch(
                    '/api/mmmx/session/s1/params',
                    json={'params': {'entry_dte_min': 15}},
                )
        assert resp.status_code == 422
        data = resp.get_json()
        assert data['ok'] is False
        assert 'entry_dte_min' in data['rejected']

    def test_mixed_patch_returns_200(self):
        app = _make_app()
        session = _make_session()
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_config.split_hot_reload_patch',
                       return_value=({'hard_stop_multiplier': 3.0}, {'entry_dte_min': 'not hot-reloadable'})):
                with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                    with patch(f'{_PKG}.mmmx_engine.recalc_hard_stop', return_value=1500.0):
                        with patch(f'{_PKG}.mmmx_param_audit.record_param_change', return_value={}):
                            with patch(f'{_PKG}.mmmx_websocket.emit_params_changed'):
                                with patch(f'{_PKG}.mmmx_activity.log_activity'):
                                    resp = c.patch(
                                        f'/api/mmmx/session/{session["session_id"]}/params',
                                        json={'params': {'hard_stop_multiplier': 3.0, 'entry_dte_min': 15}},
                                    )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert 'hard_stop_multiplier' in data['applied']
        assert 'entry_dte_min' in data['rejected']
        assert 'audit_id' in data

    def test_hard_stop_multiplier_recalculates_usd(self):
        app = _make_app()
        session = _make_session()
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_config.split_hot_reload_patch',
                       return_value=({'hard_stop_multiplier': 3.0}, {})):
                with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                    with patch(f'{_PKG}.mmmx_engine.recalc_hard_stop', return_value=1500.0) as mock_recalc:
                        with patch(f'{_PKG}.mmmx_param_audit.record_param_change', return_value={}):
                            with patch(f'{_PKG}.mmmx_websocket.emit_params_changed'):
                                with patch(f'{_PKG}.mmmx_activity.log_activity'):
                                    resp = c.patch(
                                        f'/api/mmmx/session/{session["session_id"]}/params',
                                        json={'params': {'hard_stop_multiplier': 3.0}},
                                    )
        assert resp.status_code == 200
        mock_recalc.assert_called_once()
        assert session['hard_stop_usd'] == 1500.0

    def test_no_params_body_returns_400(self):
        app = _make_app()
        with app.test_client() as c:
            resp = c.patch('/api/mmmx/session/s1/params', json={})
        assert resp.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# Pause / Resume
# ══════════════════════════════════════════════════════════════════════════════

class TestPauseResume:

    def test_pause_running_stops_monitor_sets_paused(self):
        app = _make_app()
        session = _make_session(status='RUNNING')
        storage = _mock_storage(session=session)
        mock_monitor = MagicMock()
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_monitor.get_monitor', return_value=mock_monitor):
                    with patch(f'{_PKG}.mmmx_websocket.emit_status_change'):
                        with patch(f'{_PKG}.mmmx_activity.log_activity'):
                            with patch(f'{_PKG}.mmmx_telegram.send_alert'):
                                resp = c.post(f'/api/mmmx/session/{session["session_id"]}/pause')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['data']['status'] == 'PAUSED'
        mock_monitor.stop.assert_called_once_with(reason='operator_pause')
        assert session['status'] == 'PAUSED'

    def test_pause_already_paused_returns_409(self):
        app = _make_app()
        session = _make_session(status='PAUSED')
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_monitor.get_monitor', return_value=None):
                    resp = c.post(f'/api/mmmx/session/{session["session_id"]}/pause')
        assert resp.status_code == 409

    def test_pause_does_not_call_stop_session_monitor(self):
        """PAUSE must only call monitor.stop(), NOT stop_session_monitor() which kills listener."""
        app = _make_app()
        session = _make_session(status='RUNNING')
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_monitor.get_monitor', return_value=MagicMock()):
                    with patch(f'{_PKG}.mmmx_websocket.emit_status_change'):
                        with patch(f'{_PKG}.mmmx_activity.log_activity'):
                            with patch(f'{_PKG}.mmmx_telegram.send_alert'):
                                with patch(f'{_PKG}.mmmx_monitor.stop_session_monitor') as mock_ssm:
                                    resp = c.post(f'/api/mmmx/session/{session["session_id"]}/pause')
        # stop_session_monitor must NOT be called (it kills the listener)
        mock_ssm.assert_not_called()
        assert resp.status_code == 200

    def test_resume_paused_starts_monitor(self):
        app = _make_app()
        session = _make_session(status='PAUSED')
        storage = _mock_storage(session=session)
        mock_monitor = MagicMock()
        mock_monitor._my_generation = 5
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_monitor.start_session_monitor', return_value=mock_monitor) as mock_start:
                    with patch(f'{_PKG}.mmmx_websocket.emit_status_change'):
                        with patch(f'{_PKG}.mmmx_activity.log_activity'):
                            resp = c.post(f'/api/mmmx/session/{session["session_id"]}/resume')
        assert resp.status_code == 200
        assert resp.get_json()['data']['status'] == 'RUNNING'
        mock_start.assert_called_once_with(session['session_id'])
        assert session['status'] == 'RUNNING'

    def test_resume_complete_returns_409(self):
        app = _make_app()
        session = _make_session(status='COMPLETE')
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                resp = c.post(f'/api/mmmx/session/{session["session_id"]}/resume')
        assert resp.status_code == 409

    def test_pause_unknown_session_returns_404(self):
        app = _make_app()
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=_mock_storage(session=None)):
                resp = c.post('/api/mmmx/session/nonexistent/pause')
        assert resp.status_code == 404

    def test_resume_unknown_session_returns_404(self):
        app = _make_app()
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=_mock_storage(session=None)):
                resp = c.post('/api/mmmx/session/nonexistent/resume')
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# POST /force-heartbeat
# ══════════════════════════════════════════════════════════════════════════════

class TestForceHeartbeat:

    def test_running_session_monitor_alive_returns_200(self):
        app = _make_app()
        session = _make_session(status='RUNNING')
        storage = _mock_storage(session=session)
        mock_monitor = MagicMock()
        mock_monitor.is_alive.return_value = True

        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_monitor.get_monitor', return_value=mock_monitor):
                    with patch(f'{_PKG}.mmmx_premium_listener.get_listener', return_value=None):
                        with patch(f'{_PKG}.mmmx_activity.log_activity'):
                            resp = c.post(
                                f'/api/mmmx/session/{session["session_id"]}/force-heartbeat',
                                json={'reason': 'operator_manual'},
                            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['data']['queued'] is True
        assert data['data']['monitor_alive'] is True
        mock_monitor.signal_force_check.assert_called_once()

    def test_listener_attached_uses_listener_path(self):
        app = _make_app()
        session = _make_session(status='PAUSED')
        storage = _mock_storage(session=session)
        mock_monitor = MagicMock()
        mock_monitor.is_alive.return_value = True
        mock_listener = MagicMock()

        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_monitor.get_monitor', return_value=mock_monitor):
                    with patch(f'{_PKG}.mmmx_premium_listener.get_listener', return_value=mock_listener):
                        with patch(f'{_PKG}.mmmx_activity.log_activity'):
                            resp = c.post(
                                f'/api/mmmx/session/{session["session_id"]}/force-heartbeat',
                                json={'reason': 'cb_manual_review'},
                            )

        assert resp.status_code == 200
        mock_listener.force_heartbeat.assert_called_once()

    def test_non_running_paused_status_returns_409(self):
        app = _make_app()
        session = _make_session(status='DRAFT')
        storage = _mock_storage(session=session)

        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                resp = c.post(f'/api/mmmx/session/{session["session_id"]}/force-heartbeat')

        assert resp.status_code == 409

    def test_monitor_not_alive_returns_409(self):
        app = _make_app()
        session = _make_session(status='RUNNING')
        storage = _mock_storage(session=session)
        dead_monitor = MagicMock()
        dead_monitor.is_alive.return_value = False

        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_monitor.get_monitor', return_value=dead_monitor):
                    resp = c.post(f'/api/mmmx/session/{session["session_id"]}/force-heartbeat')

        assert resp.status_code == 409

    def test_unknown_session_returns_404(self):
        app = _make_app()
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=_mock_storage(session=None)):
                resp = c.post('/api/mmmx/session/nonexistent/force-heartbeat')
        assert resp.status_code == 404

    def test_generation_conflict_returns_ok_with_save_flag_false(self):
        app = _make_app()
        session = _make_session(status='RUNNING')
        storage = _mock_storage(session=session)
        mock_monitor = MagicMock()
        mock_monitor.is_alive.return_value = True
        from webui.backend.routes.mmmx.mmmx_storage import GenerationConflict
        storage.save_session.side_effect = GenerationConflict('stale save')

        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_monitor.get_monitor', return_value=mock_monitor):
                    with patch(f'{_PKG}.mmmx_premium_listener.get_listener', return_value=None):
                        with patch(f'{_PKG}.mmmx_activity.log_activity'):
                            resp = c.post(
                                f'/api/mmmx/session/{session["session_id"]}/force-heartbeat',
                                json={'reason': 'operator_manual'},
                            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['data']['save_ok'] is False


# ══════════════════════════════════════════════════════════════════════════════
# GET /scan_strikes
# ══════════════════════════════════════════════════════════════════════════════

def _mock_chain_svc_no_spot():
    """Mock OptionsChainService where spot returns 0 → no_live_chain path."""
    svc = MagicMock()
    svc.return_value._get_spot_price.return_value = 0.0
    return svc


class TestScanStrikes:

    def _patch_chain_svc(self, app, session, storage):
        """Context manager that patches OptionsChainService to return no spot."""
        return patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage)

    def test_gates_passed_returns_no_live_chain(self):
        app = _make_app()
        session = _make_session(status='GATES_PASSED')
        storage = _mock_storage(session=session)
        mock_svc_cls = MagicMock()
        mock_svc_cls.return_value._get_spot_price.return_value = 0.0
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch('webui.backend.options_chain.chain_service.OptionsChainService', mock_svc_cls):
                    resp = c.get(f'/api/mmmx/session/{session["session_id"]}/scan_strikes?otm_pct=15')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['data']['reason'] == 'no_live_chain'
        assert data['data']['ce'] is None

    def test_running_session_allowed(self):
        app = _make_app()
        session = _make_session(status='RUNNING')
        storage = _mock_storage(session=session)
        mock_svc_cls = MagicMock()
        mock_svc_cls.return_value._get_spot_price.return_value = 0.0
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch('webui.backend.options_chain.chain_service.OptionsChainService', mock_svc_cls):
                    resp = c.get(f'/api/mmmx/session/{session["session_id"]}/scan_strikes')
        assert resp.status_code == 200

    def test_draft_session_now_allowed(self):
        """DRAFT sessions are now allowed; returns no_live_chain when chain unavailable."""
        app = _make_app()
        session = _make_session(status='DRAFT')
        storage = _mock_storage(session=session)
        mock_svc_cls = MagicMock()
        mock_svc_cls.return_value._get_spot_price.return_value = 0.0
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch('webui.backend.options_chain.chain_service.OptionsChainService', mock_svc_cls):
                    resp = c.get(f'/api/mmmx/session/{session["session_id"]}/scan_strikes')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['data']['reason'] == 'no_live_chain'

    def test_draft_no_expiry_returns_no_expiry_set(self):
        """DRAFT session with no expiry returns no_expiry_set reason."""
        app = _make_app()
        session = _make_session(status='DRAFT')
        session['expiry_ddmmyy'] = ''
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                resp = c.get(f'/api/mmmx/session/{session["session_id"]}/scan_strikes')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['data']['reason'] == 'no_expiry_set'

    def test_unknown_session_returns_404(self):
        app = _make_app()
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=_mock_storage(session=None)):
                resp = c.get('/api/mmmx/session/nonexistent/scan_strikes')
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# POST /deploy_tranche1
# ══════════════════════════════════════════════════════════════════════════════

class TestDeployTranche1:

    _VALID = {
        'ce_symbol': 'C-BTC-80000-280326',
        'ce_strike': 80000.0,
        'pe_symbol': 'P-BTC-70000-280326',
        'pe_strike': 70000.0,
        'lots': 10,
    }

    def test_valid_body_returns_tranche(self):
        app = _make_app()
        session = _make_session(status='RUNNING')
        storage = _mock_storage(session=session)
        mock_tranche = {'tranche_id': 1, 'status': 'ACTIVE', 'success': True}
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_executor.get_executor', return_value=MagicMock()):
                    with patch(f'{_PKG}.mmmx_audit_log.get_audit_log', return_value=MagicMock()):
                        with patch(f'{_PKG}.mmmx_initializer.deploy_manual_tranche1',
                                   return_value=mock_tranche):
                            # Patch asyncio.run so it doesn't start an event loop in tests;
                            # just return the value the mock function returned.
                            with patch('asyncio.run', side_effect=lambda coro: mock_tranche):
                                resp = c.post(
                                    f'/api/mmmx/session/{session["session_id"]}/deploy_tranche1',
                                    json=self._VALID,
                                )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert 'tranche' in data['data']

    def test_missing_ce_strike_returns_422(self):
        app = _make_app()
        with app.test_client() as c:
            body = dict(self._VALID)
            del body['ce_strike']
            resp = c.post('/api/mmmx/session/s1/deploy_tranche1', json=body)
        assert resp.status_code == 422

    def test_missing_pe_symbol_returns_422(self):
        app = _make_app()
        with app.test_client() as c:
            body = dict(self._VALID)
            del body['pe_symbol']
            resp = c.post('/api/mmmx/session/s1/deploy_tranche1', json=body)
        assert resp.status_code == 422

    def test_draft_session_auto_transitions_and_deploys(self):
        # DRAFT sessions now auto-parse expiry from CE symbol, transition to
        # GATES_PASSED, and proceed to deploy (no longer return 409).
        app = _make_app()
        session = _make_session(status='DRAFT')
        storage = _mock_storage(session=session)
        mock_tranche = {'tranche_id': 1, 'status': 'ACTIVE', 'success': True}
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_executor.get_executor', return_value=MagicMock()):
                    with patch(f'{_PKG}.mmmx_audit_log.get_audit_log', return_value=MagicMock()):
                        with patch(f'{_PKG}.mmmx_initializer.deploy_manual_tranche1',
                                   return_value=mock_tranche):
                            with patch('asyncio.run', side_effect=lambda coro: mock_tranche):
                                resp = c.post(
                                    f'/api/mmmx/session/{session["session_id"]}/deploy_tranche1',
                                    json=self._VALID,
                                )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True

    def test_complete_session_returns_409(self):
        # COMPLETE sessions are still rejected — only DRAFT/GATES_PASSED/RUNNING allowed.
        app = _make_app()
        session = _make_session(status='COMPLETE')
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                resp = c.post(
                    f'/api/mmmx/session/{session["session_id"]}/deploy_tranche1',
                    json=self._VALID,
                )
        assert resp.status_code == 409

    def test_unknown_session_returns_404(self):
        app = _make_app()
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=_mock_storage(session=None)):
                resp = c.post('/api/mmmx/session/nonexistent/deploy_tranche1', json=self._VALID)
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# POST /profit_book
# ══════════════════════════════════════════════════════════════════════════════

class TestProfitBook:

    def test_valid_queues_and_returns_queue(self):
        app = _make_app()
        session = _make_session(status='RUNNING')
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_profit_booking.queue_close') as mock_qc:
                    with patch(f'{_PKG}.mmmx_activity.log_activity'):
                        resp = c.post(
                            f'/api/mmmx/session/{session["session_id"]}/profit_book',
                            json={'tranche_id': 1, 'target_pct': 20.0},
                        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert 'queue' in data['data']
        mock_qc.assert_called_once_with(session, 1, 20.0)

    def test_invalid_tranche_id_returns_422(self):
        app = _make_app()
        session = _make_session(status='RUNNING')
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_profit_booking.queue_close',
                           side_effect=ValueError("Tranche 999 not found")):
                    resp = c.post(
                        f'/api/mmmx/session/{session["session_id"]}/profit_book',
                        json={'tranche_id': 999, 'target_pct': 20.0},
                    )
        assert resp.status_code == 422

    def test_paused_session_returns_409(self):
        app = _make_app()
        session = _make_session(status='PAUSED')
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                resp = c.post(
                    f'/api/mmmx/session/{session["session_id"]}/profit_book',
                    json={'tranche_id': 1, 'target_pct': 20.0},
                )
        assert resp.status_code == 409

    def test_missing_tranche_id_returns_422(self):
        app = _make_app()
        session = _make_session(status='RUNNING')
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                resp = c.post(
                    f'/api/mmmx/session/{session["session_id"]}/profit_book',
                    json={'target_pct': 20.0},
                )
        assert resp.status_code == 422

    def test_missing_target_pct_returns_422(self):
        app = _make_app()
        session = _make_session(status='RUNNING')
        storage = _mock_storage(session=session)
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                resp = c.post(
                    f'/api/mmmx/session/{session["session_id"]}/profit_book',
                    json={'tranche_id': 1},
                )
        assert resp.status_code == 422

    def test_unknown_session_returns_404(self):
        app = _make_app()
        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=_mock_storage(session=None)):
                resp = c.post(
                    '/api/mmmx/session/nonexistent/profit_book',
                    json={'tranche_id': 1, 'target_pct': 20.0},
                )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# GET /session/<id> integrity payload
# ══════════════════════════════════════════════════════════════════════════════

class TestGetSessionIntegrity:

    def test_get_session_includes_integrity_signature(self):
        app = _make_app()
        session = _make_session(status='RUNNING', session_id='session-int-001')
        session['beat_number'] = 11
        storage = _mock_storage(session=session)

        with app.test_client() as c:
            with patch(f'{_PKG}.mmmx_storage.get_storage', return_value=storage):
                with patch(f'{_PKG}.mmmx_monitor.get_monitor', return_value=None):
                    resp = c.get('/api/mmmx/session/session-int-001')

        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert '_integrity' in data
        assert data['_integrity']['source'] == 'snapshot'
        assert data['_integrity']['schema'] == 'v1'
        assert data['_integrity']['state_version'] == 11
        assert isinstance(data['_integrity']['state_checksum'], str)
        assert len(data['_integrity']['state_checksum']) == 64


# ══════════════════════════════════════════════════════════════════════════════
# Backward-compat: validate_hot_reload_patch still raises
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateHotReloadPatchBackwardCompat:

    def test_still_raises_for_disallowed(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_hot_reload_patch, ConfigError
        with pytest.raises(ConfigError):
            validate_hot_reload_patch({'entry_dte_min': 15})

    def test_still_accepts_allowed(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_hot_reload_patch
        validate_hot_reload_patch({'close_at_dte': 7})

    def test_still_rejects_close_at_dte_6(self):
        from webui.backend.routes.mmmx.mmmx_config import validate_hot_reload_patch, ConfigError
        with pytest.raises(ConfigError):
            validate_hot_reload_patch({'close_at_dte': 6})
