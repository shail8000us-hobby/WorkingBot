"""
Contract Test: assign_symbol
================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of GroupsStorage.assign_symbol.
Uses an in-memory SQLite database — no real file touched, no cleanup needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/routes/options/tests/test_sealed_assign_symbol.py -v
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


def _insert_group(conn, expiry_key, group_id, symbols=None):
    conn.execute(
        "INSERT INTO expiry_groups (expiry_key, group_id, name, color, symbols) VALUES (?, ?, ?, ?, ?)",
        (expiry_key, group_id, f'Group {group_id}', '#7c3aed', json.dumps(symbols or []))
    )
    conn.commit()


def _get_symbols(conn, expiry_key, group_id):
    row = conn.execute(
        "SELECT symbols FROM expiry_groups WHERE expiry_key = ? AND group_id = ?",
        (expiry_key, group_id)
    ).fetchone()
    return json.loads(row['symbols']) if row else None


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Symbol added to target group
# ---------------------------------------------------------------------------

def test_assign_symbol_adds_to_target(storage):
    """Symbol must appear in target group's symbols list after assign."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')
    svc.assign_symbol('BTC-20032026', 'BTC-66000-call', 'g1')

    symbols = _get_symbols(conn, 'BTC-20032026', 'g1')
    assert 'BTC-66000-call' in symbols


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Symbol removed from previous group before adding to new
# ---------------------------------------------------------------------------

def test_assign_symbol_removes_from_old_group(storage):
    """Symbol must be removed from its previous group when moved to another."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1', symbols=['BTC-66000-call'])
    _insert_group(conn, 'BTC-20032026', 'g2')

    svc.assign_symbol('BTC-20032026', 'BTC-66000-call', 'g2')

    assert 'BTC-66000-call' not in _get_symbols(conn, 'BTC-20032026', 'g1')
    assert 'BTC-66000-call' in     _get_symbols(conn, 'BTC-20032026', 'g2')


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — None target_group_id unassigns (removes from all groups)
# ---------------------------------------------------------------------------

def test_assign_symbol_none_target_unassigns(storage):
    """When target_group_id is None, symbol must be removed from all groups."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1', symbols=['BTC-66000-call'])
    _insert_group(conn, 'BTC-20032026', 'g2', symbols=['BTC-66000-call'])

    svc.assign_symbol('BTC-20032026', 'BTC-66000-call', None)

    assert 'BTC-66000-call' not in _get_symbols(conn, 'BTC-20032026', 'g1')
    assert 'BTC-66000-call' not in _get_symbols(conn, 'BTC-20032026', 'g2')


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Symbol not duplicated if already in target group
# ---------------------------------------------------------------------------

def test_assign_symbol_no_duplicate_in_target(storage):
    """Symbol must appear exactly once even if re-assigned to its current group."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1', symbols=['BTC-66000-call'])

    svc.assign_symbol('BTC-20032026', 'BTC-66000-call', 'g1')

    symbols = _get_symbols(conn, 'BTC-20032026', 'g1')
    assert symbols.count('BTC-66000-call') == 1


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Works when symbol was in no group (fresh assign)
# ---------------------------------------------------------------------------

def test_assign_symbol_from_ungrouped(storage):
    """Assigning a symbol that is not yet in any group must work without error."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')

    svc.assign_symbol('BTC-20032026', 'BTC-NEW-call', 'g1')

    symbols = _get_symbols(conn, 'BTC-20032026', 'g1')
    assert 'BTC-NEW-call' in symbols


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Other symbols in target group are preserved
# ---------------------------------------------------------------------------

def test_assign_symbol_preserves_existing_symbols_in_target(storage):
    """Existing symbols in the target group must not be removed during assign."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1', symbols=['BTC-68000-call'])
    _insert_group(conn, 'BTC-20032026', 'g2')

    svc.assign_symbol('BTC-20032026', 'BTC-66000-call', 'g1')

    symbols = _get_symbols(conn, 'BTC-20032026', 'g1')
    assert 'BTC-68000-call' in symbols
    assert 'BTC-66000-call' in symbols


# ---------------------------------------------------------------------------
# CONTRACT TEST 7 — Groups in other expiry keys are untouched
# ---------------------------------------------------------------------------

def test_assign_symbol_isolated_to_expiry_key(storage):
    """assign_symbol must not touch groups belonging to a different expiry key."""
    svc, conn = storage
    _insert_group(conn, 'BTC-20032026', 'g1')
    _insert_group(conn, 'BTC-27032026', 'g1', symbols=['BTC-66000-call'])  # same group_id, different expiry

    svc.assign_symbol('BTC-20032026', 'BTC-66000-call', 'g1')

    # Other expiry's group must be unchanged
    symbols_other = _get_symbols(conn, 'BTC-27032026', 'g1')
    assert 'BTC-66000-call' in symbols_other, "Other expiry's group must not be touched"
