"""
Contract Test: update_group
================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of GroupsStorage.update_group.
Uses an in-memory SQLite database — no real file touched, no cleanup needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/routes/options/tests/test_sealed_update_group.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
import sqlite3
import json
from unittest.mock import patch

pytestmark = pytest.mark.sealed

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS expiry_groups (
        expiry_key TEXT NOT NULL,
        group_id TEXT NOT NULL,
        name TEXT NOT NULL,
        color TEXT NOT NULL DEFAULT '#7c3aed',
        note TEXT DEFAULT '',
        symbols TEXT DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (expiry_key, group_id)
    );
    CREATE TABLE IF NOT EXISTS expiry_meta (
        expiry_key TEXT PRIMARY KEY,
        collapsed TEXT DEFAULT '{}',
        position_order TEXT DEFAULT '[]',
        group_order TEXT DEFAULT '[]',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""


@pytest.fixture
def storage():
    """GroupsStorage backed by a fresh in-memory SQLite — no real file touched."""
    conn = sqlite3.connect(':memory:')
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()

    with patch('webui.backend.routes.options.groups_storage._get_conn', return_value=conn):
        from webui.backend.routes.options.groups_storage import GroupsStorage
        yield GroupsStorage(), conn


def _insert_group(conn, expiry_key, group_id, name='OldName', color='#111111', note='', symbols=None):
    conn.execute(
        "INSERT INTO expiry_groups (expiry_key, group_id, name, color, note, symbols) VALUES (?, ?, ?, ?, ?, ?)",
        (expiry_key, group_id, name, color, note, json.dumps(symbols or []))
    )
    conn.commit()


def _fetch_group(conn, expiry_key, group_id):
    return conn.execute(
        "SELECT * FROM expiry_groups WHERE expiry_key = ? AND group_id = ?",
        (expiry_key, group_id)
    ).fetchone()


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — name is updated
# ---------------------------------------------------------------------------

def test_update_group_name(storage):
    """Setting name in updates must persist to DB."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')
    svc.update_group('BTC-20032026', 'g1', {'name': 'New Hedge'})

    row = _fetch_group(conn, 'BTC-20032026', 'g1')
    assert row['name'] == 'New Hedge'


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — color is updated
# ---------------------------------------------------------------------------

def test_update_group_color(storage):
    """Setting color in updates must persist to DB."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')
    svc.update_group('BTC-20032026', 'g1', {'color': '#ff0000'})

    row = _fetch_group(conn, 'BTC-20032026', 'g1')
    assert row['color'] == '#ff0000'


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — note is updated
# ---------------------------------------------------------------------------

def test_update_group_note(storage):
    """Setting note in updates must persist to DB."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')
    svc.update_group('BTC-20032026', 'g1', {'note': 'Added after market crash'})

    row = _fetch_group(conn, 'BTC-20032026', 'g1')
    assert row['note'] == 'Added after market crash'


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — symbols list is updated (stored as JSON)
# ---------------------------------------------------------------------------

def test_update_group_symbols(storage):
    """Symbols list update must be persisted as JSON-encoded list."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')
    svc.update_group('BTC-20032026', 'g1', {'symbols': ['BTC-66000-call', 'BTC-68000-call']})

    row = _fetch_group(conn, 'BTC-20032026', 'g1')
    stored = json.loads(row['symbols'])
    assert stored == ['BTC-66000-call', 'BTC-68000-call']


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Unknown/disallowed fields are silently ignored
# ---------------------------------------------------------------------------

def test_update_group_ignores_unknown_fields(storage):
    """Fields not in {name, color, note, symbols} must be ignored without error."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1', name='Keep')
    # should not raise, and must not change anything
    svc.update_group('BTC-20032026', 'g1', {'hacker_field': 'DROP TABLE expiry_groups;'})

    row = _fetch_group(conn, 'BTC-20032026', 'g1')
    assert row['name'] == 'Keep'


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Empty updates dict is a no-op (no crash, no change)
# ---------------------------------------------------------------------------

def test_update_group_empty_updates_is_noop(storage):
    """Empty updates dict must not crash and must not modify the group."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1', name='Stable')
    svc.update_group('BTC-20032026', 'g1', {})

    row = _fetch_group(conn, 'BTC-20032026', 'g1')
    assert row['name'] == 'Stable'


# ---------------------------------------------------------------------------
# CONTRACT TEST 7 — Other groups in same expiry are unaffected
# ---------------------------------------------------------------------------

def test_update_group_does_not_affect_other_groups(storage):
    """Updating one group must not touch sibling groups."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1', name='First')
    _insert_group(conn, 'BTC-20032026', 'g2', name='Second')

    svc.update_group('BTC-20032026', 'g1', {'name': 'Updated First'})

    row = _fetch_group(conn, 'BTC-20032026', 'g2')
    assert row['name'] == 'Second'
