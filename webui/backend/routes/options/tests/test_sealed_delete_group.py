"""
Contract Test: delete_group
================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of GroupsStorage.delete_group.
Uses an in-memory SQLite database — no real file touched, no cleanup needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/routes/options/tests/test_sealed_delete_group.py -v
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


def _insert_group(conn, expiry_key, group_id, name='Test', color='#aaa'):
    conn.execute(
        "INSERT INTO expiry_groups (expiry_key, group_id, name, color) VALUES (?, ?, ?, ?)",
        (expiry_key, group_id, name, color)
    )
    conn.commit()


def _insert_meta(conn, expiry_key, group_order):
    conn.execute(
        "INSERT INTO expiry_meta (expiry_key, group_order) VALUES (?, ?)",
        (expiry_key, json.dumps(group_order))
    )
    conn.commit()


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Group is removed from the DB
# ---------------------------------------------------------------------------

def test_delete_group_removes_from_db(storage):
    """After delete, the group must not exist in expiry_groups."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')
    svc.delete_group('BTC-20032026', 'g1')

    row = conn.execute(
        "SELECT * FROM expiry_groups WHERE expiry_key = ? AND group_id = ?",
        ('BTC-20032026', 'g1')
    ).fetchone()
    assert row is None


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Removes group_id from group_order in meta
# ---------------------------------------------------------------------------

def test_delete_group_removes_from_group_order(storage):
    """Deleted group_id must be removed from group_order in expiry_meta."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')
    _insert_meta(conn, 'BTC-20032026', ['g1', 'g2'])

    svc.delete_group('BTC-20032026', 'g1')

    meta = conn.execute("SELECT group_order FROM expiry_meta WHERE expiry_key = ?",
                        ('BTC-20032026',)).fetchone()
    order = json.loads(meta['group_order'])
    assert 'g1' not in order
    assert 'g2' in order


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Other groups in same expiry are unaffected
# ---------------------------------------------------------------------------

def test_delete_group_does_not_affect_other_groups(storage):
    """Deleting one group must not touch sibling groups."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')
    _insert_group(conn, 'BTC-20032026', 'g2')
    svc.delete_group('BTC-20032026', 'g1')

    row = conn.execute(
        "SELECT * FROM expiry_groups WHERE expiry_key = ? AND group_id = ?",
        ('BTC-20032026', 'g2')
    ).fetchone()
    assert row is not None


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Deleting non-existent group does not crash
# ---------------------------------------------------------------------------

def test_delete_group_nonexistent_does_not_raise(storage):
    """Deleting a group that doesn't exist must not raise an exception."""
    svc, _ = storage
    # Should not raise
    svc.delete_group('BTC-20032026', 'ghost_id')


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Groups from other expiry keys are unaffected
# ---------------------------------------------------------------------------

def test_delete_group_isolated_to_expiry_key(storage):
    """Deleting from one expiry key must not affect another expiry key."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')
    _insert_group(conn, 'BTC-27032026', 'g1')  # Same group_id, different expiry

    svc.delete_group('BTC-20032026', 'g1')

    row = conn.execute(
        "SELECT * FROM expiry_groups WHERE expiry_key = ? AND group_id = ?",
        ('BTC-27032026', 'g1')
    ).fetchone()
    assert row is not None, "Group in a different expiry key must be untouched"


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Returns None (no return value contract)
# ---------------------------------------------------------------------------

def test_delete_group_returns_none(storage):
    """delete_group must return None — no data should be returned."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')
    result = svc.delete_group('BTC-20032026', 'g1')
    assert result is None
