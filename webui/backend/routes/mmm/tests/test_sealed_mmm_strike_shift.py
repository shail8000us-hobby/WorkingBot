"""
Sealed contract tests for mmm_strike_shift (#86)

Functions sealed:
  - check_shift_needed(session, side, current_premium) → bool
  - freeze_current_positions(session, side) → dict
  - find_new_strike(initializer, session, side, spot_price, min_otm_distance) → dict|None
  - activate_new_strike(session, side, new_strike, fill_premium, lots) → dict

File: webui/backend/routes/mmm/mmm_strike_shift.py

Bug found and fixed (2026-03-20):
  _initial_hedge_premium ordering bug: recompute_side_lots() in freeze_current_positions()
  zeroes original_premium BEFORE activate_new_strike() reads it to seed
  _initial_hedge_premium. Result: dynamic shift threshold used first-shift fill premium
  instead of original entry premium for all subsequent shift checks.
  Fix: save _initial_hedge_premium in freeze_current_positions() BEFORE recompute runs.

Contracts:

  [check_shift_needed — 7 contracts]
  C1.  premium < shift_threshold (floor only) → True
  C2.  premium >= shift_threshold (floor only) → False
  C3.  premium == shift_threshold → False (strictly <, not <=)
  C4.  threshold_pct > 0, dynamic > floor → uses dynamic (max wins)
  C5.  threshold_pct > 0, floor > dynamic → uses floor (max wins)
  C6.  threshold_pct = 0 → uses floor regardless of hedge_entry_premium
  C7.  threshold_pct > 0, all premium sources = 0 → falls back to floor

  [freeze_current_positions — 6 contracts]
  F1.  All active positions get status='shifted'
  F2.  Non-active positions (closed, shifted) are not re-shifted
  F3.  Returns frozen_lots = sum of active position lots before freeze
  F4.  trigger_snapshot for old_strike is cleared
  F5.  Returns {frozen_lots, old_strike, frozen_entry}
  F6.  _initial_hedge_premium preserved from original_premium BEFORE recompute zeroes it

  [find_new_strike — 9 contracts]
  N1.  No expiry set → None
  N2.  Chain fetch fails (success=False) → None
  N3.  Empty chain list → None
  N4.  OTM call with premium >= threshold → returned, sorted by target_premium proximity
  N5.  ITM call (strike <= spot for CE) skipped
  N6.  OTM put with premium >= threshold → returned
  N7.  Candidate at active old_strike excluded
  N8.  Frozen strike skipped when non-frozen candidate also exists (pass 1 preferred)
  N9.  Frozen strike used as last resort when it is the ONLY viable candidate (pass 2)

  [activate_new_strike — 7 contracts]
  A1.  active_strike updated to new_strike
  A2.  active_strike_pinned removed
  A3.  _initial_hedge_premium not overwritten when already set
  A4.  New position appended: type='strike_shift', status='active', correct premium/lots
  A5.  trigger_snapshot set for new_strike
  A6.  recompute_side_lots called (total_lots reflects new position)
  A7.  session updated_at set
"""

import pytest
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.sealed

from webui.backend.routes.mmm.mmm_strike_shift import (
    check_shift_needed,
    freeze_current_positions,
    find_new_strike,
    activate_new_strike,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

def _session(side='ce', original_lots=5, original_premium=150.0,
             original_strike=90000, shift_threshold=50.0, shift_threshold_pct=0.0,
             shift_target_premium=100.0, active_strike=None, **kwargs):
    as_ = active_strike if active_strike is not None else original_strike
    pos = {
        'id': f'{side}_orig_001', 'type': 'original', 'status': 'active',
        'lots': original_lots, 'entry_premium': original_premium,
        'premium': original_premium, 'strike': original_strike,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'shifted_at': None, 'closed_at': None, 'realized_pnl': None,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    side_state = {
        'original_lots': original_lots,
        'original_premium': original_premium,
        'original_strike': original_strike,
        'active_strike': as_,
        'adjustment_fills': [],
        'frozen_positions': [],
        'positions': [pos],
        'total_lots': original_lots,
        'trigger_snapshot': {str(original_strike): original_premium},
        '_pos_counter': 0,
    }
    side_state.update(kwargs)
    return {
        'session_id': 'test-001',
        'params': {
            'shift_threshold': shift_threshold,
            'shift_threshold_pct': shift_threshold_pct,
            'shift_target_premium': shift_target_premium,
            'expiry': '28MAR26',
            'adjustment_interval': 300,
        },
        side: side_state,
        ('pe' if side == 'ce' else 'ce'): {
            'original_lots': 0, 'total_lots': 0, 'positions': [],
            'adjustment_fills': [], 'frozen_positions': [], 'trigger_snapshot': {},
        },
        'updated_at': '',
    }


def _chain_row(strike, bid, mark, symbol, opt_type='call'):
    return {
        'strike': strike,
        opt_type: {'bid': bid, 'mark_price': mark, 'symbol': symbol},
    }


def _make_initializer(chain_rows=None, success=True):
    init = MagicMock()
    init.get_full_chain.return_value = {
        'success': success,
        'chain': chain_rows or [],
    }
    init.build_symbol.return_value = 'BTC-28MAR26-90000-C'
    return init


# ─── C1–C7: check_shift_needed ────────────────────────────────────────────────

def test_c1_premium_below_floor_returns_true():
    session = _session(shift_threshold=50.0)
    assert check_shift_needed(session, 'ce', 30.0) is True


def test_c2_premium_above_floor_returns_false():
    session = _session(shift_threshold=50.0)
    assert check_shift_needed(session, 'ce', 80.0) is False


def test_c3_premium_equal_to_floor_returns_false():
    # Condition is strictly <, not <=
    session = _session(shift_threshold=50.0)
    assert check_shift_needed(session, 'ce', 50.0) is False


def test_c4_dynamic_threshold_above_floor_used():
    # hedge_entry = 200, pct = 0.5 → dynamic = 100 > floor=50 → effective = 100
    # premium=80 < 100 → True
    session = _session(shift_threshold=50.0, shift_threshold_pct=0.5,
                       original_premium=200.0)
    session['ce']['_initial_hedge_premium'] = 200.0
    assert check_shift_needed(session, 'ce', 80.0) is True


def test_c5_floor_beats_dynamic_used():
    # hedge_entry = 20, pct = 0.5 → dynamic = 10 < floor=50 → effective = 50
    # premium=30 < 50 → True
    session = _session(shift_threshold=50.0, shift_threshold_pct=0.5,
                       original_premium=20.0)
    session['ce']['_initial_hedge_premium'] = 20.0
    assert check_shift_needed(session, 'ce', 30.0) is True


def test_c6_pct_zero_uses_floor_only():
    session = _session(shift_threshold=50.0, shift_threshold_pct=0.0,
                       original_premium=300.0)
    # Even though 300 * 0 = 0, pct=0 means skip dynamic entirely → just floor=50
    assert check_shift_needed(session, 'ce', 40.0) is True
    assert check_shift_needed(session, 'ce', 60.0) is False


def test_c7_no_hedge_premium_source_falls_back_to_floor():
    # All premium sources are 0 → dynamic = 0 → effective = floor = 50
    session = _session(shift_threshold=50.0, shift_threshold_pct=0.5,
                       original_premium=0.0)
    session['ce']['_initial_hedge_premium'] = 0
    assert check_shift_needed(session, 'ce', 30.0) is True   # 30 < 50 (floor)
    assert check_shift_needed(session, 'ce', 70.0) is False  # 70 >= 50 (floor)


# ─── F1–F6: freeze_current_positions ─────────────────────────────────────────

def test_f1_active_positions_get_shifted_status():
    session = _session()
    freeze_current_positions(session, 'ce')
    positions = session['ce']['positions']
    for pos in positions:
        if pos.get('type') == 'original':
            assert pos['status'] == 'shifted'


def test_f2_non_active_positions_unchanged():
    session = _session()
    # Add an already-closed position
    closed_pos = {
        'id': 'ce_orig_closed', 'type': 'original', 'status': 'closed',
        'lots': 2, 'entry_premium': 100.0, 'strike': 90000,
        'created_at': '', 'shifted_at': None, 'closed_at': '', 'realized_pnl': 0.0,
        'premium': 100.0, 'timestamp': '',
    }
    session['ce']['positions'].append(closed_pos)
    freeze_current_positions(session, 'ce')
    # Closed position status must still be 'closed', not 'shifted'
    for pos in session['ce']['positions']:
        if pos['id'] == 'ce_orig_closed':
            assert pos['status'] == 'closed'


def test_f3_returns_correct_frozen_lots():
    session = _session(original_lots=7)
    result = freeze_current_positions(session, 'ce')
    assert result['frozen_lots'] == 7


def test_f4_trigger_snapshot_cleared_for_old_strike():
    session = _session(original_strike=90000)
    assert str(90000) in session['ce']['trigger_snapshot']
    freeze_current_positions(session, 'ce')
    assert str(90000) not in session['ce'].get('trigger_snapshot', {})


def test_f5_returns_frozen_lots_old_strike_frozen_entry():
    session = _session(original_lots=5, original_strike=90000, original_premium=150.0)
    result = freeze_current_positions(session, 'ce')
    assert 'frozen_lots' in result
    assert 'old_strike' in result
    assert 'frozen_entry' in result
    assert result['old_strike'] == 90000
    assert result['frozen_lots'] == 5


def test_f6_initial_hedge_premium_preserved_before_recompute():
    # Bug fix: _initial_hedge_premium must be set from original_premium
    # BEFORE recompute_side_lots zeroes original_premium.
    session = _session(original_premium=150.0)
    assert '_initial_hedge_premium' not in session['ce']
    freeze_current_positions(session, 'ce')
    # After freeze, recompute zeroes original_premium.
    assert session['ce'].get('original_premium', 0) == 0.0
    # _initial_hedge_premium must be 150, NOT 0.
    assert session['ce'].get('_initial_hedge_premium') == 150.0


# ─── N1–N8: find_new_strike ───────────────────────────────────────────────────

def test_n1_no_expiry_returns_none():
    session = _session()
    session['params']['expiry'] = ''
    result = find_new_strike(_make_initializer(), session, 'ce', 88000.0)
    assert result is None


def test_n2_chain_fetch_fails_returns_none():
    init = _make_initializer(success=False)
    result = find_new_strike(init, _session(), 'ce', 88000.0)
    assert result is None


def test_n3_empty_chain_returns_none():
    init = _make_initializer(chain_rows=[])
    result = find_new_strike(init, _session(), 'ce', 88000.0)
    assert result is None


def test_n4_otm_call_above_threshold_returned():
    # spot=88000, CE strike=95000 (OTM), mark=125 >= floor=50
    # mark_price is now the primary metric (consistent with _rank_strikes)
    row = _chain_row(95000, bid=120.0, mark=125.0, symbol='BTC-CE-95000')
    init = _make_initializer(chain_rows=[row])
    session = _session(shift_threshold=50.0, original_strike=80000)
    session['ce']['active_strike'] = 80000
    result = find_new_strike(init, session, 'ce', 88000.0)
    assert result is not None
    assert result['strike'] == 95000
    assert result['premium'] == 125.0  # mark_price preferred (fix: was bid=120.0)


def test_n4b_bid_below_threshold_mark_above_finds_strike():
    # Bug scenario: bid=30 < threshold=50, but mark=80 >= 50.
    # Old code (bid-first) would skip this strike; new code (mark-first) finds it.
    row = _chain_row(95000, bid=30.0, mark=80.0, symbol='BTC-CE-95000')
    init = _make_initializer(chain_rows=[row])
    session = _session(shift_threshold=50.0, original_strike=80000)
    session['ce']['active_strike'] = 80000
    result = find_new_strike(init, session, 'ce', 88000.0)
    assert result is not None, "Strike with mark >= threshold must be found even when bid < threshold"
    assert result['strike'] == 95000
    assert result['premium'] == 80.0  # mark_price used


def test_n5_itm_call_strike_below_spot_skipped():
    # strike=85000 < spot=88000 → ITM for CE → skip
    row = _chain_row(85000, bid=300.0, mark=310.0, symbol='BTC-CE-85000')
    init = _make_initializer(chain_rows=[row])
    result = find_new_strike(init, _session(), 'ce', 88000.0)
    assert result is None


def test_n6_otm_put_returned():
    # spot=88000, PE strike=80000 (OTM for put), premium=100 >= floor=50
    row = _chain_row(80000, bid=100.0, mark=105.0, symbol='BTC-PE-80000', opt_type='put')
    init = _make_initializer(chain_rows=[row])
    session = _session(side='pe', shift_threshold=50.0, original_strike=75000)
    session['pe']['active_strike'] = 75000
    result = find_new_strike(init, session, 'pe', 88000.0)
    assert result is not None
    assert result['strike'] == 80000


def test_n7_active_old_strike_excluded():
    # active_strike=90000; candidate at 90000 must be skipped
    row = _chain_row(90000, bid=120.0, mark=125.0, symbol='BTC-CE-90000')
    init = _make_initializer(chain_rows=[row])
    session = _session(shift_threshold=50.0, original_strike=90000)
    session['ce']['active_strike'] = 90000
    result = find_new_strike(init, session, 'ce', 88000.0)
    assert result is None


def test_n8_frozen_strike_skipped_when_non_frozen_exists():
    # When a non-frozen candidate also exists, the frozen strike must NOT be
    # returned in pass 1 (non-frozen candidate preferred).
    row_frozen = _chain_row(92000, bid=120.0, mark=125.0, symbol='BTC-CE-92000')
    row_clean  = _chain_row(93000, bid=80.0,  mark=85.0,  symbol='BTC-CE-93000')
    init = _make_initializer(chain_rows=[row_frozen, row_clean])
    session = _session(shift_threshold=50.0, original_strike=90000)
    session['ce']['active_strike'] = 90000
    session['ce']['frozen_positions'] = [{'strike': 92000, 'lots': 3}]
    result = find_new_strike(init, session, 'ce', 88000.0)
    assert result is not None
    # Must return the non-frozen candidate
    assert result['strike'] == 93000


def test_n9_frozen_strike_used_as_last_resort():
    # When the ONLY viable OTM candidate is a frozen strike (all non-frozen
    # are below threshold or ITM), pass 2 must return it rather than None.
    # This is the 0DTE near-expiry scenario: market has moved so far that
    # frozen strikes are the only OTM options with real premium.
    row = _chain_row(92000, bid=120.0, mark=125.0, symbol='BTC-CE-92000')
    init = _make_initializer(chain_rows=[row])
    session = _session(shift_threshold=50.0, original_strike=90000)
    session['ce']['active_strike'] = 90000
    session['ce']['frozen_positions'] = [{'strike': 92000, 'lots': 3}]
    result = find_new_strike(init, session, 'ce', 88000.0)
    assert result is not None
    assert result['strike'] == 92000
    assert result['is_frozen_strike'] is True


# ─── A1–A7: activate_new_strike ───────────────────────────────────────────────

def _run_activate(session=None, side='ce', new_strike=95000,
                  fill_premium=120.0, lots=5):
    if session is None:
        session = _session()
    # get_initializer is imported inside activate_new_strike, so patch at source
    with patch('webui.backend.routes.mmm.mmm_initializer.get_initializer') as mock_init:
        mock_init.return_value.build_symbol.return_value = f'BTC-28MAR26-{new_strike}-C'
        activate_new_strike(session, side, new_strike, fill_premium, lots)
    return session


def test_a1_active_strike_updated():
    session = _run_activate(new_strike=95000)
    assert session['ce']['active_strike'] == 95000


def test_a2_active_strike_pinned_cleared():
    session = _session()
    session['ce']['active_strike_pinned'] = True
    _run_activate(session=session, new_strike=95000)
    assert 'active_strike_pinned' not in session['ce']


def test_a3_initial_hedge_premium_not_overwritten_when_set():
    session = _session()
    session['ce']['_initial_hedge_premium'] = 200.0
    _run_activate(session=session, new_strike=95000, fill_premium=120.0)
    # Must still be 200, not 120
    assert session['ce']['_initial_hedge_premium'] == 200.0


def test_a4_new_position_appended_correctly():
    session = _run_activate(new_strike=95000, fill_premium=120.0, lots=5)
    positions = session['ce']['positions']
    shift_pos = [p for p in positions if p.get('type') == 'strike_shift']
    assert len(shift_pos) == 1
    sp = shift_pos[0]
    assert sp['strike'] == 95000
    assert sp['lots'] == 5
    assert sp['entry_premium'] == 120.0
    assert sp['status'] == 'active'


def test_a5_trigger_snapshot_set_for_new_strike():
    from webui.backend.routes.mmm.mmm_constants import strike_key
    session = _run_activate(new_strike=95000, fill_premium=120.0)
    key = strike_key(95000)
    assert session['ce']['trigger_snapshot'].get(key) == 120.0


def test_a6_recompute_side_lots_reflects_new_position():
    # After activate, total_lots should include the new lots
    session = _session(original_lots=0)  # no active original lots
    session['ce']['positions'] = []  # empty before shift
    session['ce']['original_lots'] = 0
    session['ce']['total_lots'] = 0
    _run_activate(session=session, new_strike=95000, fill_premium=120.0, lots=5)
    # recompute_side_lots should set total_lots = 5 (new position)
    assert session['ce']['total_lots'] == 5


def test_a7_updated_at_set_on_session():
    session = _run_activate()
    assert session.get('updated_at', '') != ''
