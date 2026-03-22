"""
Contract tests for Feature 10 — Pre-Fill Execution Event Log

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Functions covered:
  MMMSessionEventLog.enqueue_event(category='EXECUTION_INTENT', ...)
  MMMSessionEventLog.query_execution_orphans(session_id, ...) -> List[Dict]

File: webui/backend/routes/mmm/mmm_audit_log.py

Tests use an isolated in-process SQLite DB — no shared state.
No exchange API calls required.

--- EXECUTION_INTENT enqueue contracts ---
C-EE-1: ORDER_INTENT event saved with correct fields
C-EE-2: ORDER_CONFIRMED event saved with correct fields
C-EE-3: EXIT_ROUND_START event saved with correct fields
C-EE-4: EXIT_ROUND_END event saved with correct fields

--- query_execution_orphans contracts ---
C-EE-5: No intents → empty orphan list
C-EE-6: Intent + matching confirm → not an orphan
C-EE-7: Intent with no confirm → orphan detected
C-EE-8: Two intents, one confirmed, one not → only unconfirmed is orphan
C-EE-9: Orphan outside lookback window → not returned
C-EE-10: query error (bad db path) → returns [] without raising
"""

import json
import time
import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: isolated event log per test
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def event_log(tmp_path):
    from webui.backend.routes.mmm.mmm_audit_log import MMMSessionEventLog
    db_path = str(tmp_path / 'test_events.db')
    el = MMMSessionEventLog(db_path=db_path)
    # Give the writer thread a moment to init the schema
    time.sleep(0.05)
    return el


def _flush(el):
    """Force-flush event log queue. Writer batches on 2s interval; sleep 2.5s to be safe."""
    time.sleep(2.5)


def _write_direct(db_path, session_id, event_category, event_type, details_dict):
    """Write an event directly to SQLite — bypasses the queue for fast test setup."""
    import sqlite3
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO session_event_log "
        "(session_id, timestamp_ist, created_at, event_category, event_type, severity, details, remark) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, now, now, event_category, event_type, 'INFO',
         json.dumps(details_dict), f'{event_type} direct'),
    )
    conn.commit()
    conn.close()


def _query_all(el, session_id):
    return el.query_session(session_id)


# =============================================================================
# EXECUTION_INTENT enqueue
# =============================================================================

class TestExecutionIntentEnqueue:

    @pytest.mark.sealed
    def test_c_ee_1_order_intent_saved(self, event_log):
        event_log.enqueue_event(
            session_id='sess-001',
            event_category='EXECUTION_INTENT',
            event_type='ORDER_INTENT',
            remark='SELL 10 lots BTC-CE @ $200.00',
            severity='INFO',
            details={'order_id': 'ORD-001', 'symbol': 'C-BTC-100000-150226',
                     'side': 'sell', 'size': 10, 'mid_price': 200.0},
        )
        _flush(event_log)
        rows = _query_all(event_log, 'sess-001')
        intents = [r for r in rows if r['event_type'] == 'ORDER_INTENT']
        assert len(intents) == 1
        assert intents[0]['event_category'] == 'EXECUTION_INTENT'
        d = json.loads(intents[0]['details'])
        assert d['order_id'] == 'ORD-001'
        assert d['size'] == 10

    @pytest.mark.sealed
    def test_c_ee_2_order_confirmed_saved(self, event_log):
        event_log.enqueue_event(
            session_id='sess-002',
            event_category='EXECUTION_INTENT',
            event_type='ORDER_CONFIRMED',
            remark='SELL 10 lots @ $198.50',
            severity='INFO',
            details={'order_id': 'ORD-002', 'fill_price': 198.5, 'filled_size': 10},
        )
        _flush(event_log)
        rows = _query_all(event_log, 'sess-002')
        confirms = [r for r in rows if r['event_type'] == 'ORDER_CONFIRMED']
        assert len(confirms) == 1
        d = json.loads(confirms[0]['details'])
        assert d['order_id'] == 'ORD-002'
        assert d['fill_price'] == 198.5

    @pytest.mark.sealed
    def test_c_ee_3_exit_round_start_saved(self, event_log):
        event_log.enqueue_event(
            session_id='sess-003',
            event_category='EXECUTION_INTENT',
            event_type='EXIT_ROUND_START',
            remark='Exit round: EXIT_ROUND_START',
            severity='INFO',
            details={'round_num': 1, 'positions_to_close': 5,
                     'ce_count': 3, 'pe_count': 2},
        )
        _flush(event_log)
        rows = _query_all(event_log, 'sess-003')
        starts = [r for r in rows if r['event_type'] == 'EXIT_ROUND_START']
        assert len(starts) == 1
        d = json.loads(starts[0]['details'])
        assert d['round_num'] == 1
        assert d['positions_to_close'] == 5

    @pytest.mark.sealed
    def test_c_ee_4_exit_round_end_saved(self, event_log):
        event_log.enqueue_event(
            session_id='sess-004',
            event_category='EXECUTION_INTENT',
            event_type='EXIT_ROUND_END',
            remark='Exit round: EXIT_ROUND_END',
            severity='INFO',
            details={'round_num': 1, 'closed_count': 4,
                     'remaining_open': 1, 'partial': True},
        )
        _flush(event_log)
        rows = _query_all(event_log, 'sess-004')
        ends = [r for r in rows if r['event_type'] == 'EXIT_ROUND_END']
        assert len(ends) == 1
        d = json.loads(ends[0]['details'])
        assert d['closed_count'] == 4
        assert d['partial'] is True


# =============================================================================
# query_execution_orphans
# =============================================================================

class TestQueryExecutionOrphans:

    @pytest.mark.sealed
    def test_c_ee_5_no_intents_returns_empty(self, event_log):
        orphans = event_log.query_execution_orphans('sess-empty')
        assert orphans == []

    @pytest.mark.sealed
    def test_c_ee_6_intent_with_matching_confirm_not_orphan(self, event_log):
        # Write directly to bypass queue delay
        db = event_log._db_path
        _write_direct(db, 'sess-010', 'EXECUTION_INTENT', 'ORDER_INTENT', {'order_id': 'ORD-A'})
        _write_direct(db, 'sess-010', 'EXECUTION_INTENT', 'ORDER_CONFIRMED',
                      {'order_id': 'ORD-A', 'fill_price': 200.0, 'filled_size': 5})
        orphans = event_log.query_execution_orphans('sess-010')
        assert orphans == []

    @pytest.mark.sealed
    def test_c_ee_7_intent_without_confirm_is_orphan(self, event_log):
        db = event_log._db_path
        _write_direct(db, 'sess-011', 'EXECUTION_INTENT', 'ORDER_INTENT',
                      {'order_id': 'ORD-B', 'symbol': 'C-BTC-100000', 'side': 'sell', 'size': 8})
        orphans = event_log.query_execution_orphans('sess-011')
        assert len(orphans) == 1
        assert orphans[0]['_parsed_details']['order_id'] == 'ORD-B'

    @pytest.mark.sealed
    def test_c_ee_8_two_intents_one_confirmed(self, event_log):
        db = event_log._db_path
        # ORD-C confirmed, ORD-D not
        _write_direct(db, 'sess-012', 'EXECUTION_INTENT', 'ORDER_INTENT', {'order_id': 'ORD-C'})
        _write_direct(db, 'sess-012', 'EXECUTION_INTENT', 'ORDER_INTENT', {'order_id': 'ORD-D'})
        _write_direct(db, 'sess-012', 'EXECUTION_INTENT', 'ORDER_CONFIRMED',
                      {'order_id': 'ORD-C', 'fill_price': 150.0, 'filled_size': 3})
        orphans = event_log.query_execution_orphans('sess-012')
        assert len(orphans) == 1
        assert orphans[0]['_parsed_details']['order_id'] == 'ORD-D'

    @pytest.mark.sealed
    def test_c_ee_9_orphan_outside_lookback_not_returned(self, event_log):
        # Write an old intent directly to DB (bypassing the queue) via raw SQL
        import sqlite3
        old_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        db_path = event_log._db_path
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO session_event_log "
            "(session_id, timestamp_ist, created_at, event_category, event_type, severity, details, remark) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ('sess-013', old_time, old_time, 'EXECUTION_INTENT', 'ORDER_INTENT',
             'INFO', json.dumps({'order_id': 'ORD-OLD'}), 'old intent'),
        )
        conn.commit()
        conn.close()
        # lookback_minutes=60 → 3-hour-old row is outside window
        orphans = event_log.query_execution_orphans('sess-013', lookback_minutes=60)
        assert orphans == []

    @pytest.mark.sealed
    def test_c_ee_10_bad_db_path_returns_empty_no_raise(self):
        from webui.backend.routes.mmm.mmm_audit_log import MMMSessionEventLog
        bad_el = MMMSessionEventLog.__new__(MMMSessionEventLog)
        bad_el._db_path = '/nonexistent/path/test.db'
        result = bad_el.query_execution_orphans('any-session')
        assert result == []
