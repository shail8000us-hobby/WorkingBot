import json
from unittest.mock import patch

from flask import Flask

from webui.backend.routes.mmm.mmm_api import mmm_bp


class _StubStorage:
    def __init__(self, session):
        self._session = session
        self.update_calls = []

    def get_session(self, session_id):
        if self._session.get('session_id') == session_id:
            return self._session
        return None

    def update_session(self, session_id, updates):
        self.update_calls.append((session_id, updates))
        for k, v in updates.items():
            if k == 'params' and isinstance(v, dict):
                self._session.setdefault('params', {}).update(v)
            else:
                self._session[k] = v
        return self._session


def _make_client():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(mmm_bp)
    return app.test_client()


def test_create_session_rejects_client_strategy_type_injection():
    client = _make_client()

    response = client.post(
        '/api/mmm/session/create',
        data=json.dumps({
            'mode': 'fresh',
            'params': {
                'strategy_type': '5DTE',
                'expiry': '21032026',
            },
        }),
        content_type='application/json',
    )

    body = response.get_json()
    assert response.status_code == 400
    assert body['success'] is False
    assert 'Do not set strategy_type directly' in body['error']


def test_patch_params_rejects_strategy_identity_drift_attempt():
    client = _make_client()
    session = {
        'session_id': 'mmm-strategy-test-1',
        'strategy_status': 'RUNNING',
        'strategy_type': '5DTE',
        'params': {
            'dte_category': '5DTE',
            'adjustment_interval': 300,
            'expiry': '21032026',
        },
    }
    storage = _StubStorage(session)

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=storage):
        response = client.patch(
            '/api/mmm/session/mmm-strategy-test-1/params',
            data=json.dumps({'dte_category': '0DTE'}),
            content_type='application/json',
        )

    body = response.get_json()
    assert response.status_code == 400
    assert body['success'] is False
    assert 'Strategy identity is immutable' in body['error']
    assert storage.update_calls == []


def test_patch_params_ignores_same_strategy_type_when_other_mutable_param_changes():
    client = _make_client()
    session = {
        'session_id': 'mmm-strategy-test-2',
        'strategy_status': 'IDLE',
        'strategy_type': '5DTE',
        'params': {
            'dte_category': '5DTE',
            'adjustment_interval': 300,
            'expiry': '21032026',
        },
    }
    storage = _StubStorage(session)

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=storage), \
         patch('webui.backend.routes.mmm.mmm_api.emit_params_changed', return_value=None):
        response = client.patch(
            '/api/mmm/session/mmm-strategy-test-2/params',
            data=json.dumps({
                'strategy_type': '5DTE',
                'adjustment_interval': 305,
            }),
            content_type='application/json',
        )

    body = response.get_json()
    assert response.status_code == 200
    assert body['success'] is True
    assert 'adjustment_interval' in body['changed']
    assert storage.update_calls, 'Expected storage.update_session to be called'


def test_patch_params_rejects_adjustment_only_param_for_straddle_roll():
    client = _make_client()
    session = {
        'session_id': 'mmm-strategy-test-3',
        'strategy_status': 'RUNNING',
        'strategy_type': 'STRADDLE_ROLL',
        'params': {
            'dte_category': 'STRADDLE_ROLL',
            'adjustment_interval': 300,
            'expiry': '21032026',
        },
    }
    storage = _StubStorage(session)

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=storage):
        response = client.patch(
            '/api/mmm/session/mmm-strategy-test-3/params',
            data=json.dumps({'min_trigger_move': 12.0}),
            content_type='application/json',
        )

    body = response.get_json()
    assert response.status_code == 400
    assert body['success'] is False
    assert body['strategy_type'] == 'STRADDLE_ROLL'
    assert 'min_trigger_move' in body['forbidden_params']
    assert storage.update_calls == []


def test_patch_params_rejects_pure_roll_only_param_for_0dte():
    client = _make_client()
    session = {
        'session_id': 'mmm-strategy-test-4',
        'strategy_status': 'IDLE',
        'strategy_type': '0DTE',
        'params': {
            'dte_category': '0DTE',
            'adjustment_interval': 300,
            'expiry': '21032026',
        },
    }
    storage = _StubStorage(session)

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=storage):
        response = client.patch(
            '/api/mmm/session/mmm-strategy-test-4/params',
            data=json.dumps({'straddle_roll_hard_stop_market_order': True}),
            content_type='application/json',
        )

    body = response.get_json()
    assert response.status_code == 400
    assert body['success'] is False
    assert body['strategy_type'] == '0DTE'
    assert 'straddle_roll_hard_stop_market_order' in body['forbidden_params']
    assert storage.update_calls == []


def test_patch_params_returns_suggested_max_total_exposure_hint():
    client = _make_client()
    session = {
        'session_id': 'mmm-strategy-test-5',
        'strategy_status': 'RUNNING',
        'strategy_type': '5DTE',
        'params': {
            'dte_category': '5DTE',
            'adjustment_interval': 300,
            'max_lots_per_side': 100,
            'max_total_exposure': 100,
            'expiry': '21032026',
        },
    }
    storage = _StubStorage(session)

    with patch('webui.backend.routes.mmm.mmm_api.get_storage', return_value=storage), \
         patch('webui.backend.routes.mmm.mmm_api.emit_params_changed', return_value=None):
        response = client.patch(
            '/api/mmm/session/mmm-strategy-test-5/params',
            data=json.dumps({'max_lots_per_side': 120}),
            content_type='application/json',
        )

    body = response.get_json()
    assert response.status_code == 200
    assert body['success'] is True
    assert body['suggest_max_total_exposure'] == 240
    assert 'total_exposure_warning' in body


def test_create_session_rejects_strategy_validator_violations():
    client = _make_client()

    with patch(
        'webui.backend.routes.mmm.mmm_api.validate_session_for_strategy',
        return_value=['test invariant failed'],
    ):
        response = client.post(
            '/api/mmm/session/create',
            data=json.dumps({
                'mode': 'fresh',
                'params': {
                    'expiry': '21032026',
                },
            }),
            content_type='application/json',
        )

    body = response.get_json()
    assert response.status_code == 400
    assert body['success'] is False
    assert body['error'] == 'Strategy validation failed'
    assert body['violations'] == ['test invariant failed']
