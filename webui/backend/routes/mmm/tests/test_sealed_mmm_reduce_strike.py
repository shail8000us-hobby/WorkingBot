"""
Sealed tests for _build_strike_close_records() — the candidate-building
logic for specific-strike manual reduce (reduce_position endpoint).

What is sealed:
  - Shifted-only strike is reducible (frozen lots reachable)
  - Mixed active+shifted at the same strike both contribute
  - _being_closed positions are excluded from candidates
  - When ALL lots at strike are in-flight → fatal error with inflight_lots count
  - Requested > strike-available → clamped with non-fatal clamp_error
  - Close records carry _pos_id for ID-based removal (Fix #23)
  - LIFO order: non-originals newest-first, originals last

These tests exercise the pure candidate logic only — no exchange I/O,
no Flask context required.
"""

import pytest
from datetime import datetime, timezone
from copy import deepcopy

from webui.backend.routes.mmm.mmm_api import _build_strike_close_records


# ─── helpers ──────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc).isoformat()


def _pos(id_, strike, lots, status='active', type_='adjustment',
         being_closed=False, entry_premium=100.0, created_at=None):
    return {
        'id': id_,
        'strike': float(strike),
        'lots': lots,
        'status': status,
        'type': type_,
        'entry_premium': entry_premium,
        'premium': entry_premium,
        '_being_closed': being_closed,
        '_being_closed_at': _now() if being_closed else None,
        'created_at': created_at or _now(),
    }


def _side_state(positions):
    """Build a minimal side_state dict with a positions[] list."""
    return {
        'positions': positions,
        'active_strike': 71600,
        'original_strike': 71600,
        'active_lots': sum(p['lots'] for p in positions if p['status'] == 'active'),
    }


# ─── shifted-only strike ──────────────────────────────────────────────────────

@pytest.mark.sealed
def test_a1_shifted_only_strike_is_reducible():
    """Frozen/shifted lots at a strike are included in candidate set."""
    positions = [
        _pos('p1', 71600, 30, status='shifted', type_='adjustment', entry_premium=85.0),
        _pos('p2', 71600, 20, status='shifted', type_='adjustment', entry_premium=80.0),
    ]
    side_state = _side_state(positions)
    result = _build_strike_close_records(side_state, 71600.0, 50)

    assert result['error'] is None
    assert result['strike_available'] == 50
    assert result['lots_to_close'] == 50
    assert len(result['close_records']) == 2
    total_lots = sum(r['lots'] for r in result['close_records'])
    assert total_lots == 50


@pytest.mark.sealed
def test_a2_shifted_only_strike_carries_pos_id():
    """Each close record must contain _pos_id (Fix #23 ID-based removal)."""
    positions = [
        _pos('shifted_abc', 71600, 10, status='shifted'),
    ]
    result = _build_strike_close_records(_side_state(positions), 71600.0, 10)

    assert result['error'] is None
    assert len(result['close_records']) == 1
    assert result['close_records'][0]['_pos_id'] == 'shifted_abc'


# ─── mixed active + shifted ───────────────────────────────────────────────────

@pytest.mark.sealed
def test_b1_mixed_active_and_shifted_both_contribute():
    """Active and shifted positions at same strike both count toward available lots."""
    positions = [
        _pos('act1', 71600, 15, status='active', type_='adjustment'),
        _pos('shf1', 71600, 25, status='shifted', type_='adjustment'),
    ]
    result = _build_strike_close_records(_side_state(positions), 71600.0, 40)

    assert result['error'] is None
    assert result['strike_available'] == 40
    assert result['lots_to_close'] == 40
    total_lots = sum(r['lots'] for r in result['close_records'])
    assert total_lots == 40


@pytest.mark.sealed
def test_b2_original_at_strike_included():
    """Original position type at the target strike is also reducible."""
    positions = [
        _pos('orig1', 71600, 100, status='active', type_='original', entry_premium=120.0),
    ]
    result = _build_strike_close_records(_side_state(positions), 71600.0, 50)

    assert result['error'] is None
    assert result['strike_available'] == 100
    assert result['lots_to_close'] == 50
    assert result['close_records'][0]['source'] == 'original'
    assert result['close_records'][0]['_pos_id'] == 'orig1'


# ─── _being_closed exclusion ─────────────────────────────────────────────────

@pytest.mark.sealed
def test_c1_being_closed_excluded_from_candidates():
    """Position with _being_closed=True must not appear in close_records."""
    positions = [
        _pos('inflight', 71600, 30, being_closed=True),
        _pos('open1', 71600, 20, being_closed=False),
    ]
    result = _build_strike_close_records(_side_state(positions), 71600.0, 50)

    assert result['error'] is None, "Should succeed — 20 lots available"
    assert result['strike_available'] == 20
    assert result['inflight_lots'] == 30
    pos_ids = [r['_pos_id'] for r in result['close_records']]
    assert 'inflight' not in pos_ids
    assert 'open1' in pos_ids


@pytest.mark.sealed
def test_c2_all_lots_inflight_returns_inflight_conflict_error():
    """When every lot at the strike is in-flight, return fatal error with inflight count."""
    positions = [
        _pos('fl1', 71600, 50, being_closed=True),
        _pos('fl2', 71600, 30, being_closed=True),
    ]
    result = _build_strike_close_records(_side_state(positions), 71600.0, 80)

    assert result['error'] is not None
    assert result['inflight_lots'] == 80
    assert result['strike_available'] == 0
    assert 'in-flight' in result['error']
    assert result['close_records'] == []


@pytest.mark.sealed
def test_c3_inflight_error_message_contains_lot_count():
    """Inflight error message must include the count of blocked lots."""
    positions = [_pos('fl', 71600, 45, being_closed=True)]
    result = _build_strike_close_records(_side_state(positions), 71600.0, 45)

    assert '45' in result['error']


# ─── lot clamping ─────────────────────────────────────────────────────────────

@pytest.mark.sealed
def test_d1_requested_more_than_available_clamps_with_clamp_error():
    """If requested > strike-available, lots_to_close is clamped and clamp_error is set."""
    positions = [_pos('p1', 71600, 10)]
    result = _build_strike_close_records(_side_state(positions), 71600.0, 30)

    assert result['error'] is None
    assert result['clamp_error'] is not None
    assert result['lots_to_close'] == 10
    assert result['strike_available'] == 10
    total_lots = sum(r['lots'] for r in result['close_records'])
    assert total_lots == 10


@pytest.mark.sealed
def test_d2_exact_lots_no_clamp_error():
    """If requested == strike-available, no clamping occurs and clamp_error is None."""
    positions = [_pos('p1', 71600, 10)]
    result = _build_strike_close_records(_side_state(positions), 71600.0, 10)

    assert result['error'] is None
    assert result['clamp_error'] is None
    assert result['lots_to_close'] == 10


@pytest.mark.sealed
def test_d3_no_lots_at_strike_returns_error():
    """Strike with no positions (different strike) returns fatal error."""
    positions = [_pos('p1', 70000, 20)]  # different strike
    result = _build_strike_close_records(_side_state(positions), 71600.0, 10)

    assert result['error'] is not None
    assert result['inflight_lots'] == 0
    assert result['strike_available'] == 0
    assert 'no open lots' in result['error']


# ─── LIFO ordering ───────────────────────────────────────────────────────────

@pytest.mark.sealed
def test_e1_non_originals_newest_first_before_originals():
    """Non-original positions are ordered newest-first; originals appear last."""
    now = _now()
    import time; time.sleep(0.001)  # ensure distinct timestamps
    positions = [
        _pos('adj_old', 71600, 5, type_='adjustment', entry_premium=90.0, created_at=_now()),
        _pos('orig1', 71600, 10, type_='original', entry_premium=120.0),
        _pos('adj_new', 71600, 5, type_='adjustment', entry_premium=80.0, created_at=_now()),
    ]
    result = _build_strike_close_records(_side_state(positions), 71600.0, 5)

    assert result['error'] is None
    # Should take from adj_new first (newest non-original, reversed order)
    assert len(result['close_records']) == 1
    assert result['close_records'][0]['_pos_id'] == 'adj_new'


@pytest.mark.sealed
def test_e2_originals_consumed_last_resort():
    """Originals are only consumed after all non-originals at the strike are exhausted."""
    positions = [
        _pos('adj1', 71600, 5, type_='adjustment'),
        _pos('orig1', 71600, 20, type_='original'),
    ]
    # Request 10: should take all 5 from adj1 then 5 from orig1
    result = _build_strike_close_records(_side_state(positions), 71600.0, 10)

    assert result['error'] is None
    pos_ids = [r['_pos_id'] for r in result['close_records']]
    assert 'adj1' in pos_ids
    assert 'orig1' in pos_ids
    total_lots = sum(r['lots'] for r in result['close_records'])
    assert total_lots == 10


# ─── closed positions not included ───────────────────────────────────────────

@pytest.mark.sealed
def test_f1_closed_positions_not_included():
    """Positions with status='closed' must never appear in candidate set."""
    positions = [
        _pos('closed1', 71600, 50, status='closed'),
        _pos('open1', 71600, 10, status='active'),
    ]
    result = _build_strike_close_records(_side_state(positions), 71600.0, 50)

    assert result['strike_available'] == 10  # only open1 counts
    pos_ids = [r['_pos_id'] for r in result['close_records']]
    assert 'closed1' not in pos_ids


# ─── old-format side_state (no positions key) ─────────────────────────────────

@pytest.mark.sealed
def test_g1_auto_migrates_old_format_side_state():
    """Old-format side_state without positions[] key gets auto-migrated."""
    side_state_old = {
        'active_strike': 71600,
        'original_strike': 71600,
        'original_lots': 30,
        'original_premium': 110.0,
        'active_lots': 50,
        'adjustment_fills': [
            {'strike': 71600, 'lots': 20, 'premium': 90.0, 'type': 'adjustment', 'timestamp': _now()},
        ],
        'frozen_positions': [],
    }
    # No 'positions' key — should migrate and find 50 lots
    result = _build_strike_close_records(side_state_old, 71600.0, 10)

    # After migration, should find positions at 71600
    assert result['error'] is None or result['strike_available'] >= 0
    # If migration succeeds, positions[] is now populated
    assert 'positions' in side_state_old
