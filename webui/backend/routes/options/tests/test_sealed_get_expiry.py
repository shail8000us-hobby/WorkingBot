"""
Contract Test: get_expiry
================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of GroupsStorage.get_expiry.
Uses an in-memory SQLite database — no real file touched, no cleanup needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/routes/options/tests/test_sealed_get_expiry.py -v
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


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Returns correct empty structure for unknown key
# ---------------------------------------------------------------------------

def test_get_expiry_unknown_key_returns_empty_structure(storage):
    """Unknown expiry key must return empty but correctly-shaped structure."""
    svc, _ = storage
    result = svc.get_expiry('BTC-UNKNOWN')

    assert isinstance(result, dict)
    assert result['groups']     == {}
    assert result['collapsed']  == {}
    assert result['order']      == []
    assert result['groupOrder'] == []


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Returns groups for known key
# ---------------------------------------------------------------------------

def test_get_expiry_returns_groups(storage):
    """Must return group data previously stored for that expiry key."""
    svc, conn = storage
    conn.execute(
        "INSERT INTO expiry_groups (expiry_key, group_id, name, color, symbols) VALUES (?, ?, ?, ?, ?)",
        ('BTC-20032026', 'g1', 'Hedge', '#ff0000', '["BTC-CALL-66000"]')
    )
    conn.commit()

    result = svc.get_expiry('BTC-20032026')

    assert 'g1' in result['groups']
    assert result['groups']['g1']['name']    == 'Hedge'
    assert result['groups']['g1']['color']   == '#ff0000'
    assert result['groups']['g1']['symbols'] == ['BTC-CALL-66000']


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Group note defaults to empty string (not None)
# ---------------------------------------------------------------------------

def test_get_expiry_note_never_none(storage):
    """note field must be a string, never None."""
    svc, conn = storage
    conn.execute(
        "INSERT INTO expiry_groups (expiry_key, group_id, name, color, note) VALUES (?, ?, ?, ?, NULL)",
        ('BTC-20032026', 'g1', 'Test', '#000000')
    )
    conn.commit()

    result = svc.get_expiry('BTC-20032026')
    assert result['groups']['g1']['note'] == ''


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Returns meta (collapsed, order, groupOrder)
# ---------------------------------------------------------------------------

def test_get_expiry_returns_meta(storage):
    """Must read collapsed/order/groupOrder from expiry_meta table."""
    svc, conn = storage
    conn.execute(
        "INSERT INTO expiry_meta (expiry_key, collapsed, position_order, group_order) VALUES (?, ?, ?, ?)",
        ('BTC-20032026', '{"g1": true}', '["BTC-66000"]', '["g1", "g2"]')
    )
    conn.commit()

    result = svc.get_expiry('BTC-20032026')
    assert result['collapsed']  == {'g1': True}
    assert result['order']      == ['BTC-66000']
    assert result['groupOrder'] == ['g1', 'g2']


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Returns only data for specified key, not other keys
# ---------------------------------------------------------------------------

def test_get_expiry_isolates_to_requested_key(storage):
    """Must not return groups from a different expiry key."""
    svc, conn = storage
    conn.execute(
        "INSERT INTO expiry_groups (expiry_key, group_id, name, color) VALUES (?, ?, ?, ?)",
        ('BTC-20032026', 'g1', 'Mine', '#aaaaaa')
    )
    conn.execute(
        "INSERT INTO expiry_groups (expiry_key, group_id, name, color) VALUES (?, ?, ?, ?)",
        ('BTC-13032026', 'g2', 'Other', '#bbbbbb')
    )
    conn.commit()

    result = svc.get_expiry('BTC-20032026')
    assert 'g1' in result['groups']
    assert 'g2' not in result['groups']


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Multiple groups for same key all returned
# ---------------------------------------------------------------------------

def test_get_expiry_returns_all_groups_for_key(storage):
    """Must return every group belonging to the requested expiry key."""
    svc, conn = storage
    for i in range(1, 5):
        conn.execute(
            "INSERT INTO expiry_groups (expiry_key, group_id, name, color) VALUES (?, ?, ?, ?)",
            ('BTC-20032026', f'g{i}', f'Group {i}', '#7c3aed')
        )
    conn.commit()

    result = svc.get_expiry('BTC-20032026')
    assert len(result['groups']) == 4
