"""
Contract tests for recompute_side_lots

SEALED — v1.0.0 — March 14, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Function: recompute_side_lots(side_state: Dict) → Dict
File: webui/backend/routes/mmm/mmm_state.py

Contracts:
  C1.  active_lots = original_lots + adjustment_total_lots (active positions only)
  C2.  total_lots = active_lots + frozen_total_lots
  C3.  original_lots = sum of 'original' type active positions
  C4.  adjustment_total_lots = sum of non-original active position lots
  C5.  adjustment_avg = lot-weighted average premium of adjustments
  C6.  frozen_total_lots = sum of 'shifted' position lots
  C7.  adjustment_fills rebuilt from active non-original positions (includes _pos_id)
  C8.  frozen_positions rebuilt from shifted positions (includes _pos_id, frozen_at)
  C9.  empty positions[] → all scalars zero, all lists empty
  C10. auto-migrates old 3-array format (no positions key) to new format
  C11. positions[] of invalid type (not list) → resets to empty, all scalars zero
  C12. returns the same side_state dict (mutates and returns)
"""

import pytest
from copy import deepcopy

pytestmark = pytest.mark.sealed

from webui.backend.routes.mmm.mmm_state import recompute_side_lots


def _make_position(pos_id, pos_type, lots, premium, status='active', strike=90000):
    return {
        'id': pos_id,
        'type': pos_type,
        'lots': lots,
        'entry_premium': premium,
        'premium': premium,
        'status': status,
        'strike': strike,
        'created_at': '2026-03-14T10:00:00+00:00',
        'shifted_at': '2026-03-14T11:00:00+00:00' if status == 'shifted' else None,
        'timestamp': '2026-03-14T10:00:00+00:00',
    }


# ─── C1: active_lots = original + adjustments ──────────────────────────────

def test_c1_active_lots_is_original_plus_adjustment():
    side = {
        'positions': [
            _make_position('ce_orig', 'original', 10, 100.0),
            _make_position('ce_adj_001', 'adjustment', 5, 80.0),
        ]
    }
    result = recompute_side_lots(side)
    assert result['active_lots'] == 15


# ─── C2: total_lots = active_lots + frozen ─────────────────────────────────

def test_c2_total_lots_includes_frozen():
    side = {
        'positions': [
            _make_position('ce_orig', 'original', 10, 100.0),
            _make_position('ce_frozen_001', 'adjustment', 3, 60.0, status='shifted'),
        ]
    }
    result = recompute_side_lots(side)
    assert result['active_lots'] == 10
    assert result['frozen_total_lots'] == 3
    assert result['total_lots'] == 13


# ─── C3: original_lots = sum of active original positions ──────────────────

def test_c3_original_lots_from_active_originals():
    side = {
        'positions': [
            _make_position('ce_orig', 'original', 8, 100.0),
        ]
    }
    result = recompute_side_lots(side)
    assert result['original_lots'] == 8


def test_c3b_closed_original_not_counted():
    side = {
        'positions': [
            _make_position('ce_orig', 'original', 8, 100.0, status='closed'),
        ]
    }
    result = recompute_side_lots(side)
    assert result['original_lots'] == 0


# ─── C4: adjustment_total_lots = non-original active positions ─────────────

def test_c4_adjustment_total_lots():
    side = {
        'positions': [
            _make_position('ce_orig', 'original', 10, 100.0),
            _make_position('ce_adj_001', 'adjustment', 4, 80.0),
            _make_position('ce_adj_002', 'adjustment', 3, 70.0),
        ]
    }
    result = recompute_side_lots(side)
    assert result['adjustment_total_lots'] == 7


# ─── C5: adjustment_avg is lot-weighted premium average ────────────────────

def test_c5_adjustment_avg_weighted():
    side = {
        'positions': [
            _make_position('ce_adj_001', 'adjustment', 4, 80.0),
            _make_position('ce_adj_002', 'adjustment', 2, 50.0),
        ]
    }
    result = recompute_side_lots(side)
    # weighted avg = (4*80 + 2*50) / 6 = 420 / 6 = 70
    assert abs(result['adjustment_avg'] - 70.0) < 0.001


def test_c5b_no_adjustments_avg_is_zero():
    side = {
        'positions': [
            _make_position('ce_orig', 'original', 5, 100.0),
        ]
    }
    result = recompute_side_lots(side)
    assert result['adjustment_avg'] == 0.0


# ─── C6: frozen_total_lots = sum of shifted positions ──────────────────────

def test_c6_frozen_total_lots():
    side = {
        'positions': [
            _make_position('ce_frozen_001', 'adjustment', 5, 60.0, status='shifted'),
            _make_position('ce_frozen_002', 'adjustment', 3, 50.0, status='shifted'),
        ]
    }
    result = recompute_side_lots(side)
    assert result['frozen_total_lots'] == 8


# ─── C7: adjustment_fills contains _pos_id from position id ────────────────

def test_c7_adjustment_fills_has_pos_id():
    side = {
        'positions': [
            _make_position('ce_adj_001', 'adjustment', 4, 80.0),
        ]
    }
    result = recompute_side_lots(side)
    assert len(result['adjustment_fills']) == 1
    assert result['adjustment_fills'][0]['_pos_id'] == 'ce_adj_001'
    assert result['adjustment_fills'][0]['lots'] == 4
    assert result['adjustment_fills'][0]['premium'] == 80.0


# ─── C8: frozen_positions contains _pos_id and frozen_at ──────────────────

def test_c8_frozen_positions_structure():
    side = {
        'positions': [
            _make_position('ce_frozen_001', 'adjustment', 3, 60.0, status='shifted'),
        ]
    }
    result = recompute_side_lots(side)
    assert len(result['frozen_positions']) == 1
    fp = result['frozen_positions'][0]
    assert fp['_pos_id'] == 'ce_frozen_001'
    assert fp['lots'] == 3
    assert fp['frozen_at'] == '2026-03-14T11:00:00+00:00'


# ─── C9: empty positions list → all scalars zero ───────────────────────────

def test_c9_empty_positions_all_zero():
    side = {'positions': []}
    result = recompute_side_lots(side)
    assert result['original_lots'] == 0
    assert result['adjustment_total_lots'] == 0
    assert result['frozen_total_lots'] == 0
    assert result['active_lots'] == 0
    assert result['total_lots'] == 0
    assert result['adjustment_fills'] == []
    assert result['frozen_positions'] == []


# ─── C10: auto-migrates old 3-array format ─────────────────────────────────

def test_c10_auto_migrates_old_format():
    """Old sessions had original_lots scalar + adjustment_fills[] + frozen_positions[]
    but no positions[] key. recompute_side_lots must migrate and produce correct scalars."""
    side = {
        'side': 'ce',
        'original_lots': 10,
        'original_premium': 100.0,
        'original_strike': 90000,
        'active_strike': 90000,
        'adjustment_fills': [
            {'lots': 3, 'premium': 80.0, 'strike': 90000, 'timestamp': '2026-03-14T10:00:00+00:00'}
        ],
        'frozen_positions': [],
        # NOTE: no 'positions' key → triggers migration
    }
    result = recompute_side_lots(side)
    assert result['original_lots'] == 10
    assert result['adjustment_total_lots'] == 3
    assert result['active_lots'] == 13
    assert result['total_lots'] == 13
    assert 'positions' in result  # migration created it


# ─── C11: invalid positions type → reset to empty ──────────────────────────

def test_c11_invalid_positions_type_reset():
    side = {'positions': 'not_a_list'}
    result = recompute_side_lots(side)
    assert result['original_lots'] == 0
    assert result['total_lots'] == 0
    assert result['positions'] == []


# ─── C12: returns same dict object (mutates in place) ──────────────────────

def test_c12_returns_same_dict():
    side = {'positions': []}
    result = recompute_side_lots(side)
    assert result is side
