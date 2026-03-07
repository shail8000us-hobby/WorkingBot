"""
Contract Test: get_all
================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of GroupsStorage.get_all.
Uses an in-memory SQLite database — no real file touched, no cleanup needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/routes/options/tests/test_sealed_get_all.py -v
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
# CONTRACT TEST 1 — Returns empty dict when DB is empty
# ---------------------------------------------------------------------------

def test_get_all_empty_db_returns_empty_dict(storage):
    """Empty DB must return empty dict, not None, not a list."""
    svc, _ = storage
    result = svc.get_all()
    assert isinstance(result, dict)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Returns all expiry keys
# ---------------------------------------------------------------------------

def test_get_all_returns_all_keys(storage):
    """Must return one entry per distinct expiry key present in the DB."""
    svc, conn = storage
    conn.execute("INSERT INTO expiry_groups (expiry_key, group_id, name, color) VALUES (?, ?, ?, ?)",
                 ('BTC-20032026', 'g1', 'Alpha', '#ff0000'))
    conn.execute("INSERT INTO expiry_groups (expiry_key, group_id, name, color) VALUES (?, ?, ?, ?)",
                 ('BTC-27032026', 'g2', 'Beta', '#00ff00'))
    conn.commit()

    result = svc.get_all()
    assert 'BTC-20032026' in result
    assert 'BTC-27032026' in result
    assert len(result) == 2


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Each key has correct structure
# ---------------------------------------------------------------------------

def test_get_all_structure_per_key(storage):
    """Each key in the result must have groups, collapsed, order, groupOrder."""
    svc, conn = storage
    conn.execute("INSERT INTO expiry_groups (expiry_key, group_id, name, color) VALUES (?, ?, ?, ?)",
                 ('BTC-20032026', 'g1', 'Test', '#7c3aed'))
    conn.commit()

    result = svc.get_all()
    entry = result['BTC-20032026']
    assert 'groups'     in entry
    assert 'collapsed'  in entry
    assert 'order'      in entry
    assert 'groupOrder' in entry


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Group data correct (name, color, note, symbols)
# ---------------------------------------------------------------------------

def test_get_all_group_data_correct(storage):
    """Group fields must match what was stored."""
    svc, conn = storage
    conn.execute(
        "INSERT INTO expiry_groups (expiry_key, group_id, name, color, note, symbols) VALUES (?, ?, ?, ?, ?, ?)",
        ('BTC-20032026', 'g1', 'Iron Condor', '#e44', 'my note', '["BTC-66000-call"]')
    )
    conn.commit()

    result = svc.get_all()
    grp = result['BTC-20032026']['groups']['g1']
    assert grp['name']    == 'Iron Condor'
    assert grp['color']   == '#e44'
    assert grp['note']    == 'my note'
    assert grp['symbols'] == ['BTC-66000-call']


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Meta data (collapsed, order, groupOrder) populated
# ---------------------------------------------------------------------------

def test_get_all_meta_populated(storage):
    """collapsed/order/groupOrder must come from expiry_meta table."""
    svc, conn = storage
    conn.execute(
        "INSERT INTO expiry_meta (expiry_key, collapsed, position_order, group_order) VALUES (?, ?, ?, ?)",
        ('BTC-20032026', '{"g1": true}', '["BTC-66000"]', '["g1", "g2"]')
    )
    conn.commit()

    result = svc.get_all()
    entry = result['BTC-20032026']
    assert entry['collapsed']  == {'g1': True}
    assert entry['order']      == ['BTC-66000']
    assert entry['groupOrder'] == ['g1', 'g2']


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Groups from multiple keys don't bleed into each other
# ---------------------------------------------------------------------------

def test_get_all_keys_are_isolated(storage):
    """Groups for different expiry keys must not appear under each other."""
    svc, conn = storage
    conn.execute("INSERT INTO expiry_groups (expiry_key, group_id, name, color) VALUES (?, ?, ?, ?)",
                 ('BTC-20032026', 'g1', 'Mine', '#aaa'))
    conn.execute("INSERT INTO expiry_groups (expiry_key, group_id, name, color) VALUES (?, ?, ?, ?)",
                 ('BTC-27032026', 'g2', 'Other', '#bbb'))
    conn.commit()

    result = svc.get_all()
    assert 'g1' in result['BTC-20032026']['groups']
    assert 'g2' not in result['BTC-20032026']['groups']
    assert 'g2' in result['BTC-27032026']['groups']
    assert 'g1' not in result['BTC-27032026']['groups']
