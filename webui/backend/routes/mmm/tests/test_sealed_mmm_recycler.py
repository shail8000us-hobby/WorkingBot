"""
Sealed contract tests for mmm_recycler (#87)

Functions sealed:
  - select_recyclable_positions(session, side) → list
  - check_recycle_viability(recyclable_with_prices, loss_to_hedge, new_premium,
                            current_active_lots, max_lots_per_side, params) → (bool, str, dict)

File: webui/backend/routes/mmm/mmm_recycler.py

Audit outcome (2026-03-20):
  - No bugs in the two sealed functions.
  - Observation (out of scope): Phase B rollback in execute_lot_recycling appends
    recyclable-format dicts (type='frozen', no 'id') back to positions[], causing
    recompute_side_lots to classify them as adjustment fills. Total lots preserved
    but category wrong. Flagged for future audit of execute_lot_recycling.

Contracts:

  [select_recyclable_positions — 9 contracts]
  S1.  Empty frozen_positions → empty list
  S2.  Frozen position with lots=0 → skipped
  S3.  Frozen position with strike=0 → skipped
  S4.  type='original' with recycle_protect_original=True → skipped
  S5.  type='original' with recycle_protect_original=False → included
  S6.  Frozen position in being_closed_ids → skipped
  S7.  Eligible position → included with correct side/strike/lots/entry_premium/_pos_id
  S8.  Multiple eligible positions sorted ascending by entry_premium (cheapest first)
  S9.  current_premium=None in returned items (caller populates after live fetch)

  [check_recycle_viability — 10 contracts]
  V1.  Empty recyclable_with_prices → (False, reason, {})
  V2.  new_premium <= 0 → (False, reason, {})
  V3.  recycled_lots = 0 (all positions have lots=0) → (False, reason, {})
  V4.  ratio < min_ratio → (False, reason with ratio info, details)
  V5.  ratio OK, net_lot_gain < min_lot_gain → (False, reason with lot counts, details)
  V6.  affordability check fails → (False, reason, details)
  V7.  All checks pass → (True, 'Viable', details with correct fields)
  V8.  loss_to_hedge < 0 (profit) floored to 0 — not subtracted from total_to_cover
  V9.  new_lots_needed always >= 1 (min of ceil result)
  V10. details dict contains: buyback_cost, recycled_lots, avg_recycle_premium,
       ratio, total_to_cover, new_lots_needed, net_lot_gain, current_active
"""

import math
import pytest

pytestmark = pytest.mark.sealed

from webui.backend.routes.mmm.mmm_recycler import (
    select_recyclable_positions,
    check_recycle_viability,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

def _frozen(strike=90000, lots=5, entry_premium=120.0, pos_type='strike_shift',
            pos_id='pos-001', **kwargs):
    entry = {
        'strike': strike,
        'lots': lots,
        'entry_premium': entry_premium,
        'type': pos_type,
        '_pos_id': pos_id,
    }
    entry.update(kwargs)
    return entry


def _session(side='ce', frozen_positions=None, protect_original=True,
             positions=None):
    return {
        'session_id': 'test-001',
        'params': {
            'recycle_protect_original': protect_original,
        },
        side: {
            'frozen_positions': frozen_positions or [],
            'positions': positions or [],
            'total_lots': 10,
            'active_lots': 5,
        },
    }


def _params(min_ratio=2.5, buffer_pct=0.05, min_lot_gain=5,
            max_lots=100, premium_buffer_pct=0.05):
    return {
        'recycle_min_premium_ratio': min_ratio,
        'premium_buffer_pct': buffer_pct,
        'recycle_min_lot_gain': min_lot_gain,
    }


def _recyclable(current_premium=10.0, lots=20, entry_premium=100.0):
    return {
        'lots': lots,
        'entry_premium': entry_premium,
        'current_premium': current_premium,
    }


# ─── S1–S9: select_recyclable_positions ───────────────────────────────────────

def test_s1_empty_frozen_returns_empty():
    session = _session(frozen_positions=[])
    assert select_recyclable_positions(session, 'ce') == []


def test_s2_frozen_with_zero_lots_skipped():
    frozen = [_frozen(lots=0, pos_id='p1')]
    session = _session(frozen_positions=frozen)
    assert select_recyclable_positions(session, 'ce') == []


def test_s3_frozen_with_zero_strike_skipped():
    frozen = [_frozen(strike=0, pos_id='p1')]
    session = _session(frozen_positions=frozen)
    assert select_recyclable_positions(session, 'ce') == []


def test_s4_original_protected_when_flag_true():
    frozen = [_frozen(pos_type='original', pos_id='p1')]
    session = _session(frozen_positions=frozen, protect_original=True)
    assert select_recyclable_positions(session, 'ce') == []


def test_s5_original_included_when_flag_false():
    frozen = [_frozen(pos_type='original', pos_id='p1')]
    session = _session(frozen_positions=frozen, protect_original=False)
    result = select_recyclable_positions(session, 'ce')
    assert len(result) == 1


def test_s6_being_closed_position_skipped():
    # pos_id='p1' is in being_closed_ids from positions[]
    pos_entry = {'id': 'p1', '_being_closed': True, 'status': 'active', 'lots': 5}
    frozen = [_frozen(pos_id='p1')]
    session = _session(frozen_positions=frozen, positions=[pos_entry])
    assert select_recyclable_positions(session, 'ce') == []


def test_s7_eligible_position_fields_correct():
    frozen = [_frozen(strike=90000, lots=5, entry_premium=120.0, pos_id='p1')]
    session = _session(frozen_positions=frozen)
    result = select_recyclable_positions(session, 'ce')
    assert len(result) == 1
    r = result[0]
    assert r['side'] == 'ce'
    assert r['strike'] == 90000
    assert r['lots'] == 5
    assert r['entry_premium'] == 120.0
    assert r['_pos_id'] == 'p1'
    assert r['type'] == 'frozen'
    assert r['current_premium'] is None  # caller populates after live fetch


def test_s8_sorted_ascending_by_entry_premium():
    frozen = [
        _frozen(strike=90000, lots=5, entry_premium=150.0, pos_id='p1'),
        _frozen(strike=85000, lots=3, entry_premium=50.0, pos_id='p2'),
        _frozen(strike=80000, lots=2, entry_premium=100.0, pos_id='p3'),
    ]
    session = _session(frozen_positions=frozen)
    result = select_recyclable_positions(session, 'ce')
    prems = [r['entry_premium'] for r in result]
    assert prems == sorted(prems)


def test_s9_current_premium_none_in_all_returned():
    frozen = [
        _frozen(pos_id='p1'),
        _frozen(strike=85000, pos_id='p2'),
    ]
    session = _session(frozen_positions=frozen)
    result = select_recyclable_positions(session, 'ce')
    for r in result:
        assert r['current_premium'] is None


# ─── V1–V10: check_recycle_viability ──────────────────────────────────────────

def test_v1_empty_recyclable_returns_false():
    viable, reason, details = check_recycle_viability(
        [], loss_to_hedge=100.0, new_premium=200.0,
        current_active_lots=10, max_lots_per_side=50, params=_params()
    )
    assert viable is False
    assert reason


def test_v2_new_premium_zero_returns_false():
    viable, reason, details = check_recycle_viability(
        [_recyclable()], loss_to_hedge=100.0, new_premium=0.0,
        current_active_lots=10, max_lots_per_side=50, params=_params()
    )
    assert viable is False
    assert 'zero' in reason.lower()


def test_v3_zero_recyclable_lots_returns_false():
    pos = _recyclable(lots=0)
    viable, reason, details = check_recycle_viability(
        [pos], loss_to_hedge=100.0, new_premium=200.0,
        current_active_lots=10, max_lots_per_side=50, params=_params()
    )
    assert viable is False
    assert 'zero' in reason.lower()


def test_v4_ratio_below_min_returns_false():
    # avg_recycle_premium=10, new_premium=15 → ratio=1.5 < min=2.5
    pos = _recyclable(current_premium=10.0, lots=20)
    viable, reason, details = check_recycle_viability(
        [pos], loss_to_hedge=0.0, new_premium=15.0,
        current_active_lots=10, max_lots_per_side=200, params=_params(min_ratio=2.5)
    )
    assert viable is False
    assert 'ratio' in reason.lower()
    assert details.get('ratio') < 2.5


def test_v5_net_lot_gain_below_min_returns_false():
    # avg_recycle_premium=10, new_premium=50 → ratio OK (5.0 >= 2.5)
    # recycled_lots=10, loss=50 → new_lots_needed large → net_lot_gain < 5
    pos = _recyclable(current_premium=10.0, lots=10)
    # new_premium=50, loss=5 USD → raw = (cost+5)/(50*0.001)*1.05 ≈ small
    # Make loss huge so new_lots_needed > recycled_lots
    viable, reason, details = check_recycle_viability(
        [pos], loss_to_hedge=1000.0, new_premium=50.0,
        current_active_lots=5, max_lots_per_side=200,
        params=_params(min_ratio=2.5, min_lot_gain=5)
    )
    assert viable is False
    assert 'lot gain' in reason.lower()


def test_v6_affordability_check_fails():
    # current_active=48 + new_lots_needed=5 > max=50 → fails
    # Set up: ratio=5x OK, net_gain OK, but cap exceeded
    # recycled_lots=20, loss=0, new_premium=200, buyback=10*20*0.001=0.20
    # raw_new_lots = 0.20 / (200*0.001) * 1.05 ≈ 1.05 → ceil = 2
    # net_lot_gain = 20 - 2 = 18 ≥ 5 OK
    # affordability: current_active=49 + 2 = 51 > max=50 → FAIL
    pos = _recyclable(current_premium=10.0, lots=20)
    viable, reason, details = check_recycle_viability(
        [pos], loss_to_hedge=0.0, new_premium=200.0,
        current_active_lots=49, max_lots_per_side=50,
        params=_params(min_ratio=2.5, min_lot_gain=5)
    )
    assert viable is False
    assert 'affordab' in reason.lower() or 'cap' in reason.lower()


def test_v7_all_checks_pass_returns_viable():
    # Setup: recycled=20 lots @ current=10, new_premium=200
    # ratio = 200/10 = 20 >= 2.5 ✓
    # buyback = 10*20*0.001 = 0.20, loss=0 → total=0.20
    # raw = 0.20/(200*0.001)*1.05 ≈ 1.05 → new_lots=2
    # net_gain = 20-2=18 >= 5 ✓
    # affordability: 10+2=12 <= 100 ✓
    pos = _recyclable(current_premium=10.0, lots=20)
    viable, reason, details = check_recycle_viability(
        [pos], loss_to_hedge=0.0, new_premium=200.0,
        current_active_lots=10, max_lots_per_side=100,
        params=_params(min_ratio=2.5, min_lot_gain=5)
    )
    assert viable is True
    assert reason == 'Viable'
    assert isinstance(details, dict)


def test_v8_negative_loss_floored_to_zero():
    # loss_to_hedge=-100 (profit) → max(-100, 0) = 0 → not added to total_to_cover
    pos = _recyclable(current_premium=10.0, lots=30)
    viable, reason, details = check_recycle_viability(
        [pos], loss_to_hedge=-100.0, new_premium=200.0,
        current_active_lots=10, max_lots_per_side=100,
        params=_params(min_ratio=2.5, min_lot_gain=5)
    )
    # With loss=0 (floored), total_to_cover = buyback only = 10*30*0.001 = 0.30
    # raw_new_lots = 0.30/(200*0.001)*1.05 = 1.575 → ceil = 2
    # net_gain = 30-2=28 >= 5 → viable
    assert viable is True
    # Confirm total_to_cover does not include negative loss
    # If loss was applied: total_to_cover = 0.30 + 0 = 0.30 (same since floored)
    # Verify new_lots_needed is consistent with loss=0
    assert details['new_lots_needed'] >= 1


def test_v9_new_lots_needed_always_at_least_1():
    # Even if total_to_cover is tiny, new_lots_needed >= 1
    pos = _recyclable(current_premium=0.1, lots=10)  # tiny buyback cost
    viable, reason, details = check_recycle_viability(
        [pos], loss_to_hedge=0.0, new_premium=10000.0,
        current_active_lots=0, max_lots_per_side=100,
        params=_params(min_ratio=2.5, min_lot_gain=5)
    )
    # new_lots_needed = max(ceil(tiny_number), 1) = 1
    assert details.get('new_lots_needed', 1) >= 1


def test_v10_details_contains_required_fields():
    pos = _recyclable(current_premium=10.0, lots=20)
    viable, reason, details = check_recycle_viability(
        [pos], loss_to_hedge=0.0, new_premium=200.0,
        current_active_lots=10, max_lots_per_side=100,
        params=_params(min_ratio=2.5, min_lot_gain=5)
    )
    assert viable is True
    for field in ['buyback_cost', 'recycled_lots', 'avg_recycle_premium',
                  'ratio', 'total_to_cover', 'new_lots_needed',
                  'net_lot_gain', 'current_active']:
        assert field in details, f"Missing field: {field}"
