"""
test_kill_switch_endpoint.py — Backend tests for the per-session kill switch

Tests:
  T1  Kill switch on RUNNING session → 202, EXITING status, _kill_switch_triggered=True
  T2  Kill switch idempotent on EXITING → 200 (already in progress)
  T3  Kill switch on STOPPED session → 200 graceful success (nothing to close)
  T4  Kill switch on IDLE session → 200 graceful success
  T5  Kill switch on unknown session → 404
  T6  _kill_switch_triggered marker is written to DB
  T7  Kill switch on PAUSED session → 202, EXITING
  T8  Kill switch on BOTH_SIDES_UP session → 202, EXITING
  T9  No other session is touched (session isolation)
  T10 Multiple rapid calls are idempotent (no duplicate exits)
"""

import pytest
from unittest.mock import MagicMock, patch, call
from flask import Flask


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    from webui.backend.routes.mmm.mmm_api import mmm_bp
    app.register_blueprint(mmm_bp)
    return app


def _mock_session(session_id='mmm-test-1', status='RUNNING'):
    return {
        'session_id': session_id,
        'strategy_status': status,
        'ce': {'active_lots': 5, 'frozen_total_lots': 0, 'total_lots': 5},
        'pe': {'active_lots': 5, 'frozen_total_lots': 0, 'total_lots': 5},
        '_kill_switch_triggered': False,
        '_exit_all_requested': False,
        'params': {'max_loss_amount': 100.0},
    }


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    app = _make_app()
    with app.test_client() as c:
        yield c


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    return storage


# ── T1: RUNNING → 202, EXITING, kill_switch_triggered ───────────────────────

def test_T1_running_session_returns_202_and_sets_exiting(client, mock_storage):
    session = _mock_session(status='RUNNING')
    mock_storage.get_session.return_value = session
    mock_storage.update_session.return_value = None

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=mock_storage), \
         patch('webui.backend.routes.mmm.mmm_api.get_monitor', return_value=None), \
         patch('webui.backend.routes.mmm.mmm_api.emit_status_change'):

        resp = client.post('/api/mmm/session/mmm-test-1/kill_switch',
                           json={'reason': 'test'})

    assert resp.status_code == 202
    data = resp.get_json()
    assert data['success'] is True
    assert 'kill switch' in data['message'].lower()

    # Verify update_session called with kill switch fields
    update_call = mock_storage.update_session.call_args
    fields = update_call[0][1]
    assert fields['strategy_status'] == 'EXITING'
    assert fields['_kill_switch_triggered'] is True
    assert fields['_exit_all_requested'] is True
    assert '_kill_switch_at' in fields


# ── T2: EXITING → 200 idempotent ────────────────────────────────────────────

def test_T2_exiting_session_returns_200_idempotent(client, mock_storage):
    session = _mock_session(status='EXITING')
    session['_kill_switch_triggered'] = True
    mock_storage.get_session.return_value = session

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=mock_storage):
        resp = client.post('/api/mmm/session/mmm-test-1/kill_switch', json={})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert 'already in progress' in data['message'].lower()
    mock_storage.update_session.assert_not_called()


# ── T3: STOPPED → 200 graceful ──────────────────────────────────────────────

def test_T3_stopped_session_returns_200_graceful(client, mock_storage):
    session = _mock_session(status='STOPPED')
    mock_storage.get_session.return_value = session

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=mock_storage):
        resp = client.post('/api/mmm/session/mmm-test-1/kill_switch', json={})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    mock_storage.update_session.assert_not_called()


# ── T4: IDLE → 200 graceful ─────────────────────────────────────────────────

def test_T4_idle_session_returns_200_graceful(client, mock_storage):
    session = _mock_session(status='IDLE')
    mock_storage.get_session.return_value = session

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=mock_storage):
        resp = client.post('/api/mmm/session/mmm-test-1/kill_switch', json={})

    assert resp.status_code == 200
    assert resp.get_json()['success'] is True
    mock_storage.update_session.assert_not_called()


# ── T5: Unknown session → 404 ───────────────────────────────────────────────

def test_T5_unknown_session_returns_404(client, mock_storage):
    mock_storage.get_session.return_value = None

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=mock_storage):
        resp = client.post('/api/mmm/session/nonexistent/kill_switch', json={})

    assert resp.status_code == 404
    assert resp.get_json()['success'] is False


# ── T6: _kill_switch_triggered written to DB ─────────────────────────────────

def test_T6_kill_switch_triggered_marker_written(client, mock_storage):
    session = _mock_session(status='RUNNING')
    mock_storage.get_session.return_value = session

    written_fields = {}

    def capture_update(sid, fields):
        written_fields.update(fields)

    mock_storage.update_session.side_effect = capture_update

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=mock_storage), \
         patch('webui.backend.routes.mmm.mmm_api.get_monitor', return_value=None), \
         patch('webui.backend.routes.mmm.mmm_api.emit_status_change'):
        client.post('/api/mmm/session/mmm-test-1/kill_switch', json={'reason': 'manual test'})

    assert written_fields.get('_kill_switch_triggered') is True
    assert written_fields.get('_kill_switch_reason') == 'manual test'
    assert written_fields.get('strategy_status') == 'EXITING'
    assert '_kill_switch_at' in written_fields


# ── T7: PAUSED session → 202 ─────────────────────────────────────────────────

def test_T7_paused_session_returns_202(client, mock_storage):
    session = _mock_session(status='PAUSED')
    mock_storage.get_session.return_value = session

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=mock_storage), \
         patch('webui.backend.routes.mmm.mmm_api.get_monitor', return_value=None), \
         patch('webui.backend.routes.mmm.mmm_api.emit_status_change'):
        resp = client.post('/api/mmm/session/mmm-test-1/kill_switch', json={})

    assert resp.status_code == 202
    assert resp.get_json()['success'] is True


# ── T8: BOTH_SIDES_UP → 202 ──────────────────────────────────────────────────

def test_T8_both_sides_up_returns_202(client, mock_storage):
    session = _mock_session(status='BOTH_SIDES_UP')
    mock_storage.get_session.return_value = session

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=mock_storage), \
         patch('webui.backend.routes.mmm.mmm_api.get_monitor', return_value=None), \
         patch('webui.backend.routes.mmm.mmm_api.emit_status_change'):
        resp = client.post('/api/mmm/session/mmm-test-1/kill_switch', json={})

    assert resp.status_code == 202
    assert resp.get_json()['success'] is True


# ── T9: Session isolation — other sessions not touched ───────────────────────

def test_T9_other_sessions_not_touched(client, mock_storage):
    """kill_switch on session A must not update session B."""
    session_a = _mock_session(session_id='mmm-a', status='RUNNING')
    session_b = _mock_session(session_id='mmm-b', status='RUNNING')

    mock_storage.get_session.side_effect = lambda sid: session_a if sid == 'mmm-a' else session_b

    updated_sessions = []

    def track_update(sid, fields):
        updated_sessions.append(sid)

    mock_storage.update_session.side_effect = track_update

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=mock_storage), \
         patch('webui.backend.routes.mmm.mmm_api.get_monitor', return_value=None), \
         patch('webui.backend.routes.mmm.mmm_api.emit_status_change'):
        resp = client.post('/api/mmm/session/mmm-a/kill_switch', json={})

    assert resp.status_code == 202
    assert all(sid == 'mmm-a' for sid in updated_sessions), \
        f"Expected only mmm-a to be updated, got: {updated_sessions}"
    assert 'mmm-b' not in updated_sessions


# ── T10: Rapid duplicate calls are idempotent ─────────────────────────────────

def test_T10_rapid_duplicate_calls_idempotent(client, mock_storage):
    """Second call while EXITING returns 200 and does not call update_session again."""
    session = _mock_session(status='RUNNING')
    call_count = [0]

    def get_session_side_effect(sid):
        call_count[0] += 1
        if call_count[0] == 1:
            return session
        # Second call: session is now EXITING (simulating first call's effect)
        return {**session, 'strategy_status': 'EXITING', '_kill_switch_triggered': True}

    mock_storage.get_session.side_effect = get_session_side_effect
    update_count = [0]

    def track_update(sid, fields):
        update_count[0] += 1

    mock_storage.update_session.side_effect = track_update

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=mock_storage), \
         patch('webui.backend.routes.mmm.mmm_api.get_monitor', return_value=None), \
         patch('webui.backend.routes.mmm.mmm_api.emit_status_change'):
        r1 = client.post('/api/mmm/session/mmm-test-1/kill_switch', json={})
        r2 = client.post('/api/mmm/session/mmm-test-1/kill_switch', json={})

    assert r1.status_code == 202
    assert r2.status_code == 200   # idempotent
    assert update_count[0] == 1    # update_session called only once
