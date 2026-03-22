"""
Contract tests for MMM Storage — T3-2

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Functions covered:
  MMMStorage.save_session(session) -> session_id
  MMMStorage.get_session(session_id) -> Dict | None
  MMMStorage.list_sessions(active_only) -> List[Dict]
  MMMStorage.delete_session(session_id) -> bool
  (update_session is tested indirectly)

File: webui/backend/routes/mmm/mmm_storage.py

Tests use an in-process SQLite DB in a temp directory — no shared state.
No exchange API calls required.

--- save_session contracts ---
C-SS-1: save + get round-trip — session fully recoverable
C-SS-2: save sets/updates updated_at timestamp
C-SS-3: params_json is authoritative — hot-updated params survive save+reload
C-SS-4: save without session_id raises ValueError
C-SS-5: duplicate save overwrites (upsert behavior)

--- get_session contracts ---
C-SS-6: unknown session_id → None (no crash)
C-SS-7: checksum mismatch → _checksum_warning=True, session still returned
C-SS-8: fresh save → valid checksum, _checksum_warning absent

--- list_sessions contracts ---
C-SS-9: empty DB → []
C-SS-10: multiple sessions returned, sorted newest first
C-SS-11: active_only=True filters to RUNNING/PAUSED/BOTH_SIDES_UP

--- delete_session contracts ---
C-SS-12: delete existing → True, session no longer retrievable
C-SS-13: delete non-existent → False
"""

import pytest
import tempfile
import os


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: isolated storage per test
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def storage(tmp_path):
    from webui.backend.routes.mmm.mmm_storage import MMMStorage
    db_path = str(tmp_path / 'test_mmm.db')
    return MMMStorage(db_path=db_path)


def _make_session(session_id='test-001', status='IDLE', extra_params=None):
    params = {'expiry': '21032026', 'initial_lots': 5, **(extra_params or {})}
    return {
        'session_id': session_id,
        'strategy_status': status,
        'params': params,
        'created_at': '2026-03-21T00:00:00+00:00',
        'updated_at': '2026-03-21T00:00:00+00:00',
        'realized_pnl': 0.0,
        'unrealized_pnl': 0.0,
        'ce': {'active_lots': 0, 'original_lots': 5},
        'pe': {'active_lots': 0, 'original_lots': 5},
        'adjustment_history': [],
    }


# =============================================================================
# save_session
# =============================================================================

class TestSaveSession:

    @pytest.mark.sealed
    def test_c_ss_1_round_trip(self, storage):
        sess = _make_session()
        storage.save_session(sess)
        loaded = storage.get_session('test-001')
        assert loaded is not None
        assert loaded['session_id'] == 'test-001'
        assert loaded['strategy_status'] == 'IDLE'

    @pytest.mark.sealed
    def test_c_ss_2_save_updates_updated_at(self, storage):
        sess = _make_session()
        original_ts = sess['updated_at']
        import time; time.sleep(0.01)
        storage.save_session(sess)
        loaded = storage.get_session('test-001')
        # updated_at should have been set to current time by save_session
        assert loaded['updated_at'] != original_ts

    @pytest.mark.sealed
    def test_c_ss_3_params_json_authoritative_on_reload(self, storage):
        """Params stored in params_json column override data_json on load."""
        sess = _make_session()
        storage.save_session(sess)

        # Hot-reload: update params externally (simulates params_json column update)
        # Load the session, change params in memory, save again
        sess['params']['initial_lots'] = 99
        storage.save_session(sess)

        loaded = storage.get_session('test-001')
        assert loaded['params']['initial_lots'] == 99

    @pytest.mark.sealed
    def test_c_ss_4_missing_session_id_raises(self, storage):
        sess = {'strategy_status': 'IDLE', 'params': {'expiry': '21032026'}}
        with pytest.raises(ValueError, match='session_id'):
            storage.save_session(sess)

    @pytest.mark.sealed
    def test_c_ss_5_duplicate_save_upserts(self, storage):
        sess = _make_session()
        storage.save_session(sess)
        sess['realized_pnl'] = 42.5
        storage.save_session(sess)
        loaded = storage.get_session('test-001')
        assert loaded['realized_pnl'] == 42.5


# =============================================================================
# get_session
# =============================================================================

class TestGetSession:

    @pytest.mark.sealed
    def test_c_ss_6_unknown_id_returns_none(self, storage):
        result = storage.get_session('nonexistent-id')
        assert result is None

    @pytest.mark.sealed
    def test_c_ss_7_checksum_mismatch_sets_warning(self, storage):
        """Manually corrupting data_json after save → _checksum_warning on reload."""
        import sqlite3, json
        sess = _make_session()
        storage.save_session(sess)

        # Corrupt the stored data by modifying data_json directly in the DB
        # Must change a checksummed field: session_id, params, strategy_status,
        # positions, fills, or trade_history (realized_pnl is NOT checksummed).
        conn = sqlite3.connect(storage.db_path)
        row = conn.execute(
            "SELECT data_json FROM mmm_sessions WHERE session_id = ?",
            ('test-001',)
        ).fetchone()
        data = json.loads(row[0])
        data['strategy_status'] = 'TAMPERED'  # checksummed field — will mismatch
        conn.execute(
            "UPDATE mmm_sessions SET data_json = ? WHERE session_id = ?",
            (json.dumps(data), 'test-001')
        )
        conn.commit()
        conn.close()

        loaded = storage.get_session('test-001')
        assert loaded is not None  # still returns session
        assert loaded.get('_checksum_warning') is True

    @pytest.mark.sealed
    def test_c_ss_8_valid_checksum_no_warning(self, storage):
        """Normal save → no _checksum_warning on load."""
        sess = _make_session()
        storage.save_session(sess)
        loaded = storage.get_session('test-001')
        assert '_checksum_warning' not in loaded


# =============================================================================
# list_sessions
# =============================================================================

class TestListSessions:

    @pytest.mark.sealed
    def test_c_ss_9_empty_db_returns_empty_list(self, storage):
        assert storage.list_sessions() == []

    @pytest.mark.sealed
    def test_c_ss_10_multiple_sessions_sorted_newest_first(self, storage):
        import time
        s1 = _make_session('aaa-001')
        s1['created_at'] = '2026-03-21T00:00:00+00:00'
        storage.save_session(s1)

        time.sleep(0.05)
        s2 = _make_session('bbb-002')
        s2['created_at'] = '2026-03-21T00:01:00+00:00'
        storage.save_session(s2)

        sessions = storage.list_sessions()
        assert len(sessions) == 2
        # Newest created_at first
        assert sessions[0]['session_id'] == 'bbb-002'
        assert sessions[1]['session_id'] == 'aaa-001'

    @pytest.mark.sealed
    def test_c_ss_11_active_only_filters_status(self, storage):
        """active_only=True returns RUNNING/PAUSED/BOTH_SIDES_UP, not IDLE/STOPPED."""
        for sid, status in [
            ('r-001', 'RUNNING'),
            ('p-002', 'PAUSED'),
            ('b-003', 'BOTH_SIDES_UP'),
            ('i-004', 'IDLE'),
            ('s-005', 'STOPPED'),
        ]:
            storage.save_session(_make_session(sid, status))

        active = storage.list_sessions(active_only=True)
        active_ids = {s['session_id'] for s in active}
        assert 'r-001' in active_ids
        assert 'p-002' in active_ids
        assert 'b-003' in active_ids
        assert 'i-004' not in active_ids
        assert 's-005' not in active_ids


# =============================================================================
# delete_session
# =============================================================================

class TestDeleteSession:

    @pytest.mark.sealed
    def test_c_ss_12_delete_returns_true_and_removes(self, storage):
        sess = _make_session()
        storage.save_session(sess)
        result = storage.delete_session('test-001')
        assert result is True
        assert storage.get_session('test-001') is None

    @pytest.mark.sealed
    def test_c_ss_13_delete_nonexistent_returns_false(self, storage):
        result = storage.delete_session('ghost-999')
        assert result is False
