import ast
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from webui.backend.routes.mmm import mmm_activity as activity_mod
from webui.backend.routes.mmm.mmm_activity import (
    ACTIVITY_CATEGORIES,
    ACTIVITY_TYPE_ALIASES,
    ACTIVITY_TYPES,
    MMMActivityLog,
)
from webui.backend.routes.mmm.mmm_api import mmm_bp


def _make_isolated_activity_log(monkeypatch, tmp_path):
    activity_file = tmp_path / 'mmm_activity_log.json'
    monkeypatch.setattr(activity_mod, 'ACTIVITY_FILE', str(activity_file), raising=False)
    monkeypatch.setattr(activity_mod, 'ACTIVITY_BACKUP_FILE', f'{activity_file}.bak', raising=False)
    log = MMMActivityLog()
    with log._lock:
        log._activities.clear()
        log._dedup_cache.clear()
        log._suppressed_dedup_count = 0
    return log


def test_activity_registry_covers_literal_log_types():
    """Every literal log_activity/_log_activity type in MMM backend must be registered + categorized."""
    mmm_root = Path(activity_mod.__file__).resolve().parent
    used_types = set()

    for py_file in mmm_root.rglob('*.py'):
        if '/tests/' in str(py_file):
            continue
        source = py_file.read_text(encoding='utf-8')
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in {'log_activity', '_log_activity'} and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    used_types.add(first.value)

            for kw in node.keywords or []:
                if kw.arg == 'activity_type' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    used_types.add(kw.value.value)

    category_types = set().union(*ACTIVITY_CATEGORIES.values())

    missing = []
    uncategorized = []
    for raw_type in sorted(used_types):
        normalized = ACTIVITY_TYPE_ALIASES.get(raw_type, raw_type)
        if normalized not in ACTIVITY_TYPES:
            missing.append(raw_type)
        if normalized not in category_types:
            uncategorized.append(raw_type)

    assert not missing, f'Missing activity type registrations: {missing}'
    assert not uncategorized, f'Used activity types not categorized: {uncategorized}'


def test_activity_query_cursor_filters_and_search(monkeypatch, tmp_path):
    log = _make_isolated_activity_log(monkeypatch, tmp_path)

    a1 = log.add('manual_reduce', 'alpha reduce', session_id='s1', severity='warning')
    a2 = log.add('watchdog', 'watchdog alert', session_id='s1', severity='critical')
    a3 = log.add('manual_inject', 'beta inject', session_id='s2', severity='info')

    # Page 1 (newest first)
    page1 = log.query(limit=1, session_id='s1', order='desc')
    assert page1['count'] == 1
    assert page1['items'][0]['id'] == a2['id']
    assert page1['has_more'] is True
    assert page1['next_cursor'] == a2['id']

    # Page 2 via cursor
    page2 = log.query(limit=2, session_id='s1', cursor=page1['next_cursor'], order='desc')
    assert page2['count'] == 1
    assert page2['items'][0]['id'] == a1['id']

    # Filter by type + severity + search
    filtered = log.query(
        limit=10,
        types=['manual_reduce'],
        severities=['warning'],
        search='alpha',
    )
    assert filtered['count'] == 1
    assert filtered['items'][0]['id'] == a1['id']

    # Category inference should classify manual actions as adjustments
    assert a1['category'] == 'adjustments'
    assert a3['category'] == 'adjustments'


def test_activity_stats_and_api_routes(monkeypatch, tmp_path):
    log = _make_isolated_activity_log(monkeypatch, tmp_path)

    log.add('warning', 'dup-msg', session_id='s1', severity='warning')
    assert log.add('warning', 'dup-msg', session_id='s1', severity='warning') is None  # dedup suppressed
    log.add('watchdog', 'watchdog critical', session_id='s1', severity='critical')

    stats = log.get_stats(session_id='s1')
    assert stats['total'] == 2
    assert stats['critical_count'] == 1
    assert stats['warning_count'] == 1
    assert stats['suppressed_dedup_count'] == 1

    class _StubActivityLog:
        def __init__(self):
            self.last_query = None

        def query(self, **kwargs):
            self.last_query = kwargs
            return {
                'items': [{'id': 'act_1', 'type': 'watchdog', 'message': 'x'}],
                'count': 1,
                'total': 1,
                'has_more': False,
                'next_cursor': None,
            }

        def get_stats(self, **kwargs):
            return {'total': 3, 'critical_count': 1, 'warning_count': 2}

        def get_critical_feed(self, **kwargs):
            return {
                'items': [{'id': 'act_crit', 'type': 'watchdog'}],
                'count': 1,
                'total': 1,
                'has_more': False,
                'next_cursor': None,
            }

    stub = _StubActivityLog()

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(mmm_bp)
    client = app.test_client()

    with patch('webui.backend.routes.mmm.mmm_activity.get_activity_log', return_value=stub):
        resp = client.get(
            '/api/mmm/activities?limit=25&session_id=s1&severity=warning,error&'
            'category=safety&type=watchdog&search=abc&cursor=cur1&min_severity=warning&order=asc'
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['count'] == 1
        assert stub.last_query['limit'] == 25
        assert stub.last_query['session_id'] == 's1'
        assert stub.last_query['severities'] == ['warning', 'error']
        assert stub.last_query['categories'] == ['safety']
        assert stub.last_query['types'] == ['watchdog']
        assert stub.last_query['search'] == 'abc'
        assert stub.last_query['cursor'] == 'cur1'
        assert stub.last_query['min_severity'] == 'warning'
        assert stub.last_query['order'] == 'asc'

        stats_resp = client.get('/api/mmm/activities/stats?session_id=s1')
        assert stats_resp.status_code == 200
        assert stats_resp.get_json()['stats']['critical_count'] == 1

        crit_resp = client.get('/api/mmm/activities/critical?session_id=s1&limit=5')
        assert crit_resp.status_code == 200
        crit_body = crit_resp.get_json()
        assert crit_body['success'] is True
        assert crit_body['count'] == 1
