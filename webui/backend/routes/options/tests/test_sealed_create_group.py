"""
Contract Test: create_group
================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of GroupsStorage.create_group.
Uses an in-memory SQLite database — no real file touched, no cleanup needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/routes/options/tests/test_sealed_create_group.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
import sqlite3
import json
from unittest.mock import patch

pytestmark = pytest.mark.sealed


# ---------------------------------------------------------------------------
# Fixture — fresh in-memory SQLite per test, patches _get_conn to use it
# ---------------------------------------------------------------------------

@pytest.fixture
def storage():
    """GroupsStorage backed by a fresh in-memory SQLite — no real file touched."""
    conn = sqlite3.connect(':memory:')
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row

    # Initialize the real schema on the in-memory DB
    conn.executescript("""
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
    """)
    conn.commit()

    with patch('webui.backend.routes.options.groups_storage._get_conn', return_value=conn):
        from webui.backend.routes.options.groups_storage import GroupsStorage
        yield GroupsStorage(), conn


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Returns correct dict shape
# ---------------------------------------------------------------------------

def test_create_group_returns_correct_shape(storage):
    """create_group must return a dict with name, color, note, symbols."""
    svc, _ = storage
    result = svc.create_group('BTC-06032026', 'grp_001', 'Hedge Leg', '#7c3aed')

    assert isinstance(result, dict), "Must return a dict"
    assert 'name'    in result, "Result must contain 'name'"
    assert 'color'   in result, "Result must contain 'color'"
    assert 'note'    in result, "Result must contain 'note'"
    assert 'symbols' in result, "Result must contain 'symbols'"


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Returned values match what was passed in
# ---------------------------------------------------------------------------

def test_create_group_returns_correct_values(storage):
    """Returned dict must reflect the exact inputs passed."""
    svc, _ = storage
    result = svc.create_group('BTC-06032026', 'grp_001', 'Iron Condor', '#10b981')

    assert result['name']    == 'Iron Condor'
    assert result['color']   == '#10b981'
    assert result['note']    == ''       # always empty on creation
    assert result['symbols'] == []       # always empty on creation


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Group is persisted to the database
# ---------------------------------------------------------------------------

def test_create_group_persists_to_db(storage):
    """Group must actually be saved in the DB after create_group is called."""
    svc, conn = storage
    svc.create_group('BTC-06032026', 'grp_001', 'Hedge Leg', '#7c3aed')

    row = conn.execute(
        "SELECT * FROM expiry_groups WHERE expiry_key = 'BTC-06032026' AND group_id = 'grp_001'"
    ).fetchone()
    assert row is not None, "Group must exist in DB after create_group"
    assert row['name']  == 'Hedge Leg'
    assert row['color'] == '#7c3aed'
    assert row['note']  == ''
    assert json.loads(row['symbols']) == []


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — group_id is added to group_order in metadata
# ---------------------------------------------------------------------------

def test_create_group_adds_to_group_order(storage):
    """After creating a group, its ID must appear in expiry_meta.group_order."""
    svc, conn = storage
    svc.create_group('BTC-06032026', 'grp_001', 'Hedge Leg', '#7c3aed')

    meta = conn.execute(
        "SELECT group_order FROM expiry_meta WHERE expiry_key = 'BTC-06032026'"
    ).fetchone()
    assert meta is not None, "expiry_meta must be created when group is created"
    order = json.loads(meta['group_order'])
    assert 'grp_001' in order, "group_id must appear in group_order"


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Two groups maintain correct order in metadata
# ---------------------------------------------------------------------------

def test_create_group_preserves_order_of_multiple_groups(storage):
    """Creating two groups must result in both appearing in group_order in creation order."""
    svc, conn = storage
    svc.create_group('BTC-06032026', 'grp_001', 'First Group',  '#7c3aed')
    svc.create_group('BTC-06032026', 'grp_002', 'Second Group', '#10b981')

    meta = conn.execute(
        "SELECT group_order FROM expiry_meta WHERE expiry_key = 'BTC-06032026'"
    ).fetchone()
    order = json.loads(meta['group_order'])
    assert order == ['grp_001', 'grp_002'], f"Expected ordered list, got {order}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Different expiry keys are stored independently
# ---------------------------------------------------------------------------

def test_create_group_isolated_across_expiries(storage):
    """Groups for different expiry keys must not interfere with each other."""
    svc, conn = storage
    svc.create_group('BTC-06032026', 'grp_001', 'BTC Group', '#7c3aed')
    svc.create_group('ETH-06032026', 'grp_001', 'ETH Group', '#f59e0b')

    btc_row = conn.execute(
        "SELECT name FROM expiry_groups WHERE expiry_key = 'BTC-06032026' AND group_id = 'grp_001'"
    ).fetchone()
    eth_row = conn.execute(
        "SELECT name FROM expiry_groups WHERE expiry_key = 'ETH-06032026' AND group_id = 'grp_001'"
    ).fetchone()

    assert btc_row['name'] == 'BTC Group'
    assert eth_row['name'] == 'ETH Group'
