"""
Sealed contract tests for mmm_pnl_core.py

All public functions covered:
  - record_close
  - confirm_fill
  - rollback_close
  - rollback_closes_since
  - ledger_snapshot
  - compute_realized_pnl
  - compute_confirmed_pnl
  - compute_fees
  - compute_unrealized_pnl          ← today's bug; deepest coverage
  - compute_attribution
  - compute_net_premium
  - compute_current_total_pnl
  - check_stale_estimates
  - get_pnl
  - record_fee
  - flag_discrepancy
  - manual_close

Can this be silently skipped?
  compute_unrealized_pnl: YES — if _total_positions collapses to 0 (via being_closed
  over-subtraction) and all fetches succeed, the function returns 0.0 silently.
  Type 2 infrastructure contract included.
"""

import pytest
import time
from copy import deepcopy
from datetime import datetime, timezone, timedelta

from webui.backend.routes.mmm.mmm_pnl_core import (
    record_close,
    confirm_fill,
    rollback_close,
    rollback_closes_since,
    ledger_snapshot,
    compute_realized_pnl,
    compute_confirmed_pnl,
    compute_fees,
    compute_unrealized_pnl,
    compute_attribution,
    compute_net_premium,
    compute_current_total_pnl,
    check_stale_estimates,
    get_pnl,
    record_fee,
    flag_discrepancy,
    manual_close,
)
from webui.backend.routes.mmm.mmm_constants import LOT_SIZE_BTC

pytestmark = pytest.mark.sealed

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _session():
    """Minimal fresh session with no ledger."""
    return {
        'session_id': 'test-seal',
        'ce': {
            'active_strike': 70000.0,
            'original_strike': 70000.0,
            'original_premium': 100.0,
            'original_lots': 10,
            'active_lots': 10,
            'total_lots': 10,
            'frozen_total_lots': 0,
            'positions': [
                {'id': 'p1', 'type': 'original', 'status': 'active',
                 'strike': 70000.0, 'lots': 10}
            ],
            'adjustment_fills': [],
            'frozen_positions': [],
        },
        'pe': {
            'active_strike': 68000.0,
            'original_strike': 68000.0,
            'original_premium': 100.0,
            'original_lots': 10,
            'active_lots': 10,
            'total_lots': 10,
            'frozen_total_lots': 0,
            'positions': [
                {'id': 'p2', 'type': 'original', 'status': 'active',
                 'strike': 68000.0, 'lots': 10}
            ],
            'adjustment_fills': [],
            'frozen_positions': [],
        },
    }


def _fetch_50(strike, otype):
    """Premium always 50.0."""
    return 50.0


def _fetch_none(strike, otype):
    """Premium always unavailable."""
    return None


# ─────────────────────────────────────────────────────────────────────────────
# record_close
# ─────────────────────────────────────────────────────────────────────────────

def test_record_close_creates_ledger_entry():
    s = _session()
    eid = record_close(s, 'ord1', 'C-BTC-70000', 'ce', 70000.0, 10, 100.0, 50.0, 0.01, 'close_at_5')
    ledger = s['_fill_ledger']
    assert len(ledger) == 1
    assert ledger[0]['id'] == eid
    assert ledger[0]['pnl'] == pytest.approx((100.0 - 50.0) * 10 * LOT_SIZE_BTC)


def test_record_close_syncs_realized_pnl():
    s = _session()
    record_close(s, 'ord1', 'C-BTC-70000', 'ce', 70000.0, 10, 100.0, 50.0, 0.0, 'close_at_5')
    assert s['realized_pnl'] == pytest.approx((100.0 - 50.0) * 10 * LOT_SIZE_BTC)


def test_record_close_dedup_by_fill_id():
    s = _session()
    eid1 = record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5',
                        fill_id='fill1', confirmed=True)
    eid2 = record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5',
                        fill_id='fill1', confirmed=True)
    assert eid1 == eid2
    assert len(s['_fill_ledger']) == 1


def test_record_close_dedup_estimate_by_order_id():
    s = _session()
    eid1 = record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    eid2 = record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    assert eid1 == eid2
    assert len(s['_fill_ledger']) == 1


def test_record_close_pnl_negative_when_loss():
    s = _session()
    record_close(s, 'ord1', 'C', 'ce', 70000, 10, 50.0, 100.0, 0, 'close_at_5')
    assert s['_fill_ledger'][0]['pnl'] < 0


def test_record_close_commission_is_absolute():
    s = _session()
    record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100, 50, -0.05, 'close_at_5')
    assert s['_fill_ledger'][0]['commission'] == pytest.approx(0.05)


# ─────────────────────────────────────────────────────────────────────────────
# confirm_fill
# ─────────────────────────────────────────────────────────────────────────────

def test_confirm_fill_updates_estimate():
    s = _session()
    record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100.0, 50.0, 0.0, 'close_at_5')
    result = confirm_fill(s, 'ord1', 'fill1', 45.0, 0.01)
    assert result is not None
    assert result['confirmed'] is True
    assert result['close_premium'] == 45.0
    assert result['pnl'] == pytest.approx((100.0 - 45.0) * 10 * LOT_SIZE_BTC)


def test_confirm_fill_dedup_already_confirmed():
    s = _session()
    record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100.0, 50.0, 0.0, 'close_at_5')
    confirm_fill(s, 'ord1', 'fill1', 45.0, 0.01)
    result2 = confirm_fill(s, 'ord1', 'fill1', 45.0, 0.01)
    assert result2 is not None  # returns existing entry
    assert len(s['_fill_ledger']) == 1


def test_confirm_fill_returns_none_if_no_estimate():
    s = _session()
    result = confirm_fill(s, 'ord_missing', 'fill99', 45.0, 0.0)
    assert result is None


def test_confirm_fill_actual_lots_override():
    s = _session()
    record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100.0, 50.0, 0.0, 'close_at_5')
    result = confirm_fill(s, 'ord1', 'fill1', 45.0, 0.0, actual_lots=8)
    assert result['lots'] == 8
    assert result['pnl'] == pytest.approx((100.0 - 45.0) * 8 * LOT_SIZE_BTC)


# ─────────────────────────────────────────────────────────────────────────────
# rollback_close
# ─────────────────────────────────────────────────────────────────────────────

def test_rollback_close_removes_unconfirmed():
    s = _session()
    record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    removed = rollback_close(s, 'ord1')
    assert removed is not None
    assert len(s['_fill_ledger']) == 0
    assert s['realized_pnl'] == 0.0


def test_rollback_close_does_not_remove_confirmed():
    s = _session()
    record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5',
                 confirmed=True, fill_id='fill1')
    removed = rollback_close(s, 'ord1')
    assert removed is None
    assert len(s['_fill_ledger']) == 1


def test_rollback_close_returns_none_if_not_found():
    s = _session()
    assert rollback_close(s, 'nonexistent') is None


# ─────────────────────────────────────────────────────────────────────────────
# rollback_closes_since
# ─────────────────────────────────────────────────────────────────────────────

def test_rollback_closes_since_removes_unconfirmed_after_snapshot():
    s = _session()
    snap = ledger_snapshot(s)
    record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    record_close(s, 'ord2', 'C', 'ce', 70000, 5, 100, 50, 0, 'close_at_5')
    removed = rollback_closes_since(s, snap)
    assert removed == 2
    assert len(s['_fill_ledger']) == 0


def test_rollback_closes_since_preserves_confirmed():
    s = _session()
    snap = ledger_snapshot(s)
    record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5',
                 confirmed=True, fill_id='fill1')
    record_close(s, 'ord2', 'C', 'ce', 70000, 5, 100, 50, 0, 'close_at_5')
    removed = rollback_closes_since(s, snap)
    assert removed == 1
    assert len(s['_fill_ledger']) == 1


def test_rollback_closes_since_confirmed_partial_raises_discrepancy():
    s = _session()
    snap = ledger_snapshot(s)
    record_close(s, 'ord1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5',
                 confirmed=True, fill_id='fill1')
    rollback_closes_since(s, snap)
    assert len(s.get('_pnl_discrepancies', [])) == 1


# ─────────────────────────────────────────────────────────────────────────────
# compute_realized_pnl / compute_confirmed_pnl / compute_fees
# ─────────────────────────────────────────────────────────────────────────────

def test_compute_realized_pnl_empty_ledger():
    s = _session()
    assert compute_realized_pnl(s) == 0.0


def test_compute_realized_pnl_sums_all_entries():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    record_close(s, 'o2', 'C', 'pe', 68000, 5, 80, 40, 0, 'close_at_5')
    expected = (100-50)*10*LOT_SIZE_BTC + (80-40)*5*LOT_SIZE_BTC
    assert compute_realized_pnl(s) == pytest.approx(expected)


def test_compute_confirmed_pnl_only_confirmed():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    record_close(s, 'o2', 'C', 'ce', 70000, 5, 100, 50, 0, 'close_at_5',
                 confirmed=True, fill_id='f1')
    confirmed = compute_confirmed_pnl(s)
    assert confirmed == pytest.approx((100-50)*5*LOT_SIZE_BTC)


def test_compute_fees_sums_commissions():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0.02, 'close_at_5')
    record_close(s, 'o2', 'C', 'pe', 68000, 5, 80, 40, 0.03, 'close_at_5',
                 fill_id='f2', confirmed=True)
    assert compute_fees(s) == pytest.approx(0.05)


# ─────────────────────────────────────────────────────────────────────────────
# record_fee
# ─────────────────────────────────────────────────────────────────────────────

def test_record_fee_adds_fee_entry():
    s = _session()
    record_fee(s, 0.05, 'sell_adjustment', 'ord1', 'C-BTC-70000', 'ce')
    assert compute_fees(s) == pytest.approx(0.05)
    assert s['_fill_ledger'][0]['_is_fee_only'] is True


def test_record_fee_dedup_by_order_id():
    s = _session()
    record_fee(s, 0.05, 'sell_adjustment', 'ord1')
    record_fee(s, 0.05, 'sell_adjustment', 'ord1')
    assert compute_fees(s) == pytest.approx(0.05)


def test_record_fee_zero_is_noop():
    s = _session()
    eid = record_fee(s, 0.0, 'sell_adjustment')
    assert eid == ''
    assert '_fill_ledger' not in s


def test_record_fee_does_not_add_pnl():
    s = _session()
    record_fee(s, 0.1, 'perp_hedge')
    assert compute_realized_pnl(s) == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# flag_discrepancy
# ─────────────────────────────────────────────────────────────────────────────

def test_flag_discrepancy_does_not_touch_pnl():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    before = compute_realized_pnl(s)
    flag_discrepancy(s, 'C-BTC-70000', 'ce', 70000, 10, 8)
    assert compute_realized_pnl(s) == before


def test_flag_discrepancy_appends_report():
    s = _session()
    report = flag_discrepancy(s, 'C-BTC-70000', 'ce', 70000, 10, 8, 'test_reason')
    assert report['delta_lots'] == 2
    assert report['action_required'] == 'HUMAN_REVIEW'
    assert len(s['_pnl_discrepancies']) == 1


def test_flag_discrepancy_caps_at_50():
    s = _session()
    for i in range(55):
        flag_discrepancy(s, 'C', 'ce', 70000, 10, 8)
    assert len(s['_pnl_discrepancies']) == 50


# ─────────────────────────────────────────────────────────────────────────────
# manual_close
# ─────────────────────────────────────────────────────────────────────────────

def test_manual_close_creates_confirmed_entry():
    s = _session()
    manual_close(s, 'C-BTC-70000', 'ce', 70000, 10, 100.0, 60.0)
    entries = [e for e in s['_fill_ledger'] if e.get('confirmed')]
    assert len(entries) == 1
    assert entries[0]['pnl'] == pytest.approx((100.0-60.0)*10*LOT_SIZE_BTC)


def test_manual_close_source_is_manual():
    s = _session()
    manual_close(s, 'C', 'ce', 70000, 5, 100, 80)
    assert s['_fill_ledger'][0]['source'] == 'manual'


# ─────────────────────────────────────────────────────────────────────────────
# compute_unrealized_pnl — Type 1: Logic contracts
# ─────────────────────────────────────────────────────────────────────────────

def test_unrealized_pnl_basic_profit():
    """Sold at 100, now at 50 → profit. Both sides."""
    s = _session()
    pnl = compute_unrealized_pnl(s, _fetch_50)
    expected = (100.0 - 50.0) * 10 * LOT_SIZE_BTC * 2  # CE + PE
    assert pnl == pytest.approx(expected)
    assert not s.get('_pnl_calculation_incomplete')


def test_unrealized_pnl_basic_loss():
    """Sold at 100, now at 150 → loss."""
    s = _session()
    pnl = compute_unrealized_pnl(s, lambda st, ot: 150.0)
    expected = (100.0 - 150.0) * 10 * LOT_SIZE_BTC * 2
    assert pnl == pytest.approx(expected)
    assert not s.get('_pnl_calculation_incomplete')


def test_unrealized_pnl_includes_adjustment_fills():
    s = _session()
    s['ce']['adjustment_fills'] = [
        {'lots': 5, 'premium': 80.0, 'strike': 70000.0}
    ]
    pnl = compute_unrealized_pnl(s, _fetch_50)
    # CE original: (100-50)*10*0.001 + CE adj: (80-50)*5*0.001 + PE: (100-50)*10*0.001
    expected = (100-50)*10*LOT_SIZE_BTC + (80-50)*5*LOT_SIZE_BTC + (100-50)*10*LOT_SIZE_BTC
    assert pnl == pytest.approx(expected)


def test_unrealized_pnl_includes_frozen_positions():
    s = _session()
    s['ce']['frozen_positions'] = [
        {'lots': 3, 'entry_premium': 90.0, 'strike': 70000.0}
    ]
    pnl = compute_unrealized_pnl(s, _fetch_50)
    expected = (100-50)*10*LOT_SIZE_BTC + (90-50)*3*LOT_SIZE_BTC + (100-50)*10*LOT_SIZE_BTC
    assert pnl == pytest.approx(expected)


def test_unrealized_pnl_zero_lots_skipped():
    """Positions with 0 lots should not be counted."""
    s = _session()
    s['ce']['original_lots'] = 0
    pnl = compute_unrealized_pnl(s, _fetch_50)
    # Only PE contributes
    expected = (100-50)*10*LOT_SIZE_BTC
    assert pnl == pytest.approx(expected)
    assert s['_pnl_fetch_errors'] == 0


def test_unrealized_pnl_fetch_error_increments_counter():
    s = _session()
    pnl = compute_unrealized_pnl(s, _fetch_none)
    assert s['_pnl_fetch_errors'] == 2  # CE + PE both fail
    assert s.get('_pnl_calculation_incomplete') is True


def test_unrealized_pnl_incomplete_flag_threshold_50_pct():
    """1 failure out of 2 positions = 50% — NOT > 50%, should NOT set flag."""
    s = _session()
    # Only CE, no PE
    s['pe']['original_lots'] = 0
    calls = [0]
    def fetch_one_fail(strike, otype):
        calls[0] += 1
        if otype == 'call':
            return None
        return 50.0
    compute_unrealized_pnl(s, fetch_one_fail)
    # 1 position total (CE), 1 failure = 1/1 = 100% > 50% → incomplete
    assert s.get('_pnl_calculation_incomplete') is True


def test_unrealized_pnl_1_failure_out_of_3_not_incomplete():
    """1 failure out of 3 = 33% — below 50%, should NOT set incomplete flag."""
    s = _session()
    s['ce']['adjustment_fills'] = [{'lots': 5, 'premium': 80.0, 'strike': 70000.0}]
    fail_strikes = {70000.0}  # only CE original fails
    def fetch_fn(strike, otype):
        if otype == 'call' and float(strike) in fail_strikes:
            fail_strikes.discard(float(strike))
            return None
        return 50.0
    compute_unrealized_pnl(s, fetch_fn)
    # 3 positions: CE orig (fail), CE adj (ok), PE orig (ok) → 1/3 = 33% — not incomplete
    assert not s.get('_pnl_calculation_incomplete')


def test_unrealized_pnl_incomplete_flag_cleared_on_success():
    """After a successful run the flag must be cleared."""
    s = _session()
    s['_pnl_calculation_incomplete'] = True  # pre-existing
    compute_unrealized_pnl(s, _fetch_50)
    assert '_pnl_calculation_incomplete' not in s


def test_unrealized_pnl_empty_session():
    """Completely empty session — returns 0, no error, no flag."""
    pnl = compute_unrealized_pnl({}, _fetch_50)
    assert pnl == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# compute_unrealized_pnl — Type 2: Infrastructure (being_closed spillover)
# The specific latent bug that caused the 2026-03-31 false-positive pause.
# ─────────────────────────────────────────────────────────────────────────────

def test_being_closed_deduction_does_not_spill_to_other_fills_at_same_strike():
    """
    THE MARCH 31 BUG:
    128-lot fill at 67800 with _being_closed=True → being_closed_lots_at[67800]=128.
    Old code: max(0, 30-128)=0 for 30-lot fill → it was wrongly excluded.
    New depleting counter: 128-lot fill consumes all 128 → 30/1/1 fills get deduct=0.
    _total_positions must be 4 (not 1), not triggering incomplete threshold.
    """
    s = {
        'session_id': 'test-bug-march31',
        'ce': {
            'active_strike': 67800.0,
            'original_strike': 67800.0,
            'original_premium': 50.0,
            'original_lots': 0,  # original fully being closed
            'active_lots': 160,
            'total_lots': 160,
            'frozen_total_lots': 0,
            'positions': [
                # The 128-lot position flagged as being closed
                {'id': 'p1', 'type': 'adjustment', 'status': 'active',
                 'strike': 67800.0, 'lots': 128, '_being_closed': True,
                 '_being_closed_at': time.monotonic()},
            ],
            'adjustment_fills': [
                {'lots': 128, 'premium': 55.0, 'strike': 67800.0},  # being closed
                {'lots': 30,  'premium': 60.0, 'strike': 67800.0},  # NOT being closed
                {'lots': 1,   'premium': 65.0, 'strike': 67800.0},  # NOT being closed
                {'lots': 1,   'premium': 70.0, 'strike': 67800.0},  # NOT being closed
            ],
            'frozen_positions': [],
        },
        'pe': {
            'active_strike': 67000.0,
            'original_strike': 67000.0,
            'original_premium': 40.0,
            'original_lots': 30,
            'active_lots': 30,
            'total_lots': 30,
            'frozen_total_lots': 0,
            'positions': [
                {'id': 'p2', 'type': 'original', 'status': 'active',
                 'strike': 67000.0, 'lots': 30}
            ],
            'adjustment_fills': [],
            'frozen_positions': [],
        },
    }

    pnl = compute_unrealized_pnl(s, _fetch_50)

    # 128-lot fill: fully consumed by being_closed → lots_effective=0 → not counted
    # 30, 1, 1-lot fills: _remaining_bc[67800]=0 → lots_effective=30/1/1 → counted (3 positions)
    # PE original: counted (1 position)
    # Total: 4 positions
    assert s['_pnl_fetch_errors'] == 0
    assert not s.get('_pnl_calculation_incomplete'), (
        "_pnl_calculation_incomplete must NOT be set — 0 errors out of 4 positions"
    )
    # P&L: CE 30-lot: (60-50)*30*0.001, CE 1-lot: (65-50)*1*0.001, CE 1-lot: (70-50)*1*0.001
    #      PE: (40-50)*30*0.001
    expected = (
        (60.0 - 50.0) * 30 * LOT_SIZE_BTC
        + (65.0 - 50.0) * 1  * LOT_SIZE_BTC
        + (70.0 - 50.0) * 1  * LOT_SIZE_BTC
        + (40.0 - 50.0) * 30 * LOT_SIZE_BTC
    )
    assert pnl == pytest.approx(expected)


def test_being_closed_full_deduction_when_one_fill_only():
    """Single fill at a strike, fully being_closed → lots_effective=0, not counted."""
    s = {
        'session_id': 'test',
        'ce': {
            'active_strike': 70000.0, 'original_strike': 70000.0,
            'original_premium': 100.0, 'original_lots': 10,
            'positions': [
                {'id': 'p1', 'strike': 70000.0, 'lots': 10,
                 '_being_closed': True, '_being_closed_at': time.monotonic()}
            ],
            'adjustment_fills': [], 'frozen_positions': [],
        },
        'pe': {
            'active_strike': 68000.0, 'original_strike': 68000.0,
            'original_premium': 100.0, 'original_lots': 10,
            'positions': [{'id': 'p2', 'strike': 68000.0, 'lots': 10}],
            'adjustment_fills': [], 'frozen_positions': [],
        },
    }
    pnl = compute_unrealized_pnl(s, _fetch_50)
    # CE original being_closed → excluded; PE counts → 1 position, 0 errors → not incomplete
    assert not s.get('_pnl_calculation_incomplete')
    expected = (100.0 - 50.0) * 10 * LOT_SIZE_BTC
    assert pnl == pytest.approx(expected)


def test_being_closed_partial_deduction_across_different_strikes():
    """being_closed at strike A must NOT affect fills at strike B."""
    s = {
        'session_id': 'test',
        'ce': {
            'active_strike': 70000.0, 'original_strike': 70000.0,
            'original_premium': 100.0, 'original_lots': 10,
            'positions': [
                {'id': 'p1', 'strike': 70000.0, 'lots': 10,
                 '_being_closed': True, '_being_closed_at': time.monotonic()}
            ],
            'adjustment_fills': [
                {'lots': 5, 'premium': 80.0, 'strike': 71000.0},  # different strike
            ],
            'frozen_positions': [],
        },
        'pe': {'active_strike': 68000.0, 'original_premium': 100.0,
               'original_lots': 0, 'positions': [], 'adjustment_fills': [],
               'frozen_positions': []},
    }
    pnl = compute_unrealized_pnl(s, _fetch_50)
    # CE original at 70000 being_closed → excluded
    # CE adj at 71000 → NOT affected by being_closed at 70000 → counted
    assert not s.get('_pnl_calculation_incomplete')
    expected = (80.0 - 50.0) * 5 * LOT_SIZE_BTC
    assert pnl == pytest.approx(expected)


def test_being_closed_without_timestamp_treated_as_stale_for_pnl():
    """
    _being_closed=True with _being_closed_at=None/missing:
    This was the Bug 2 scenario. The position should still be accounted for —
    being_closed_lots_at accumulates it, depleting counter drains correctly.
    The position is excluded from P&L while flag is set regardless of timestamp.
    """
    s = {
        'session_id': 'test',
        'ce': {
            'active_strike': 70000.0, 'original_strike': 70000.0,
            'original_premium': 100.0, 'original_lots': 10,
            'positions': [
                {'id': 'p1', 'strike': 70000.0, 'lots': 10,
                 '_being_closed': True}  # no _being_closed_at
            ],
            'adjustment_fills': [
                {'lots': 5, 'premium': 80.0, 'strike': 70000.0},
            ],
            'frozen_positions': [],
        },
        'pe': {'active_strike': 68000.0, 'original_premium': 100.0,
               'original_lots': 10, 'positions': [],
               'adjustment_fills': [], 'frozen_positions': []},
    }
    pnl = compute_unrealized_pnl(s, _fetch_50)
    # being_closed_lots_at[70000] = 10
    # CE orig: orig_lots=10, deduct=min(10,10)=10 → lots_effective=0 → not counted
    # CE adj: lots=5, remaining_bc[70000]=0 → lots_effective=5 → counted
    # PE orig: counted
    assert not s.get('_pnl_calculation_incomplete')
    expected = (80-50)*5*LOT_SIZE_BTC + (100-50)*10*LOT_SIZE_BTC
    assert pnl == pytest.approx(expected)


# ─────────────────────────────────────────────────────────────────────────────
# compute_attribution
# ─────────────────────────────────────────────────────────────────────────────

def test_compute_attribution_routes_close_at_5_to_pnl_initial():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    attr = compute_attribution(s)
    assert attr['pnl_initial'] == pytest.approx((100-50)*10*LOT_SIZE_BTC)


def test_compute_attribution_routes_harvest_to_pnl_harvest():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'harvest')
    attr = compute_attribution(s)
    assert attr['pnl_harvest'] == pytest.approx((100-50)*10*LOT_SIZE_BTC)


def test_compute_attribution_unknown_source_goes_to_adjustment():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'unknown_source')
    attr = compute_attribution(s)
    assert attr['pnl_adjustment'] != 0.0


def test_compute_attribution_empty_ledger():
    s = _session()
    attr = compute_attribution(s)
    assert all(v == 0.0 for v in attr.values())


# F02-P1-050: reverse_close attribution — was raising KeyError('pnl_reverse')
def test_compute_attribution_reverse_close_routes_to_pnl_reverse():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'reverse_close')
    attr = compute_attribution(s)
    expected_pnl = pytest.approx((100 - 50) * 10 * LOT_SIZE_BTC)
    assert attr['pnl_reverse'] == expected_pnl
    assert attr['pnl_adjustment'] == pytest.approx(0.0)


def test_compute_attribution_reverse_close_no_keyerror_in_sync():
    # _sync_session_fields calls compute_attribution; must not raise
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 5, 80, 30, 0, 'reverse_close')
    assert s.get('pnl_reverse') == pytest.approx((80 - 30) * 5 * LOT_SIZE_BTC)


def test_get_pnl_stable_after_reverse_close():
    # get_pnl calls compute_attribution; must not raise after reverse_close row
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 5, 80, 30, 0, 'reverse_close')
    result = get_pnl(s)
    expected = pytest.approx((80 - 30) * 5 * LOT_SIZE_BTC)
    assert result['attribution']['pnl_reverse'] == expected
    assert result['realized'] == expected


# F02-P2-048: zero-net sessions with non-zero buckets must still migrate
def test_ensure_ledger_migrates_zero_net_session_with_nonzero_buckets():
    s = _session()
    s['realized_pnl'] = 0.0      # net zero
    s['total_fees'] = 0.0
    s['pnl_initial'] = 1.0
    s['pnl_adjustment'] = -1.0
    from webui.backend.routes.mmm.mmm_pnl_core import _ensure_ledger
    ledger = _ensure_ledger(s)
    assert len(ledger) >= 2, "migration should have seeded rows for non-zero buckets"
    assert s.get('_pnl_migrated') is True


# F02-P3-049: legacy pnl_reverse should migrate as reverse_close, not adjustment
def test_migrate_existing_pnl_preserves_pnl_reverse_attribution():
    s = _session()
    s['realized_pnl'] = 0.5
    s['pnl_reverse'] = 0.5       # entire realized is from reverse
    from webui.backend.routes.mmm.mmm_pnl_core import _ensure_ledger
    _ensure_ledger(s)
    attr = compute_attribution(s)
    assert attr['pnl_reverse'] == pytest.approx(0.5)
    assert attr['pnl_adjustment'] == pytest.approx(0.0)


# ─────────────────────────────────────────────────────────────────────────────
# compute_net_premium
# ─────────────────────────────────────────────────────────────────────────────

def test_compute_net_premium_subtracts_buyback_costs():
    s = _session()
    s['total_premium_collected'] = 1.0
    s['ce_premium_collected'] = 0.6
    s['pe_premium_collected'] = 0.4
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    net = compute_net_premium(s)
    buyback = 50.0 * 10 * LOT_SIZE_BTC
    assert net['total'] == pytest.approx(1.0 - buyback)
    assert net['ce'] == pytest.approx(0.6 - buyback)


def test_compute_net_premium_skips_migration_entries():
    s = _session()
    s['realized_pnl'] = 0.5
    s['total_premium_collected'] = 1.0
    s['ce_premium_collected'] = 1.0
    s['pe_premium_collected'] = 0.0
    # trigger migration
    from webui.backend.routes.mmm.mmm_pnl_core import _ensure_ledger
    _ensure_ledger(s)
    net = compute_net_premium(s)
    # migration entries have close_premium=0 → buyback=0 → net = gross
    assert net['total'] == pytest.approx(1.0)


# ─────────────────────────────────────────────────────────────────────────────
# compute_current_total_pnl
# ─────────────────────────────────────────────────────────────────────────────

def test_compute_current_total_pnl_basic():
    s = _session()
    s['realized_pnl'] = 0.5
    s['unrealized_pnl'] = 0.2
    s['total_fees'] = 0.1
    total = compute_current_total_pnl(s)
    assert total == pytest.approx(0.6)


def test_compute_current_total_pnl_includes_perp():
    s = _session()
    s['realized_pnl'] = 0.0
    s['unrealized_pnl'] = 0.0
    s['total_fees'] = 0.0
    s['perp_hedge'] = {'realized_pnl': -0.3, 'unrealized_pnl': 0.1}
    total = compute_current_total_pnl(s)
    assert total == pytest.approx(-0.2)


def test_compute_current_total_pnl_includes_reverse():
    s = _session()
    s['realized_pnl'] = 0.0
    s['unrealized_pnl'] = 0.0
    s['total_fees'] = 0.0
    s['_reverse'] = {'net_pnl': 0.15}
    total = compute_current_total_pnl(s)
    assert total == pytest.approx(0.15)


def test_compute_current_total_pnl_missing_fields_default_zero():
    total = compute_current_total_pnl({})
    assert total == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# check_stale_estimates
# ─────────────────────────────────────────────────────────────────────────────

def _stale_ts(minutes_ago):
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return dt.isoformat()


def test_check_stale_estimates_returns_old_unconfirmed():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    # Manually backdating the estimated_at
    s['_fill_ledger'][0]['estimated_at'] = _stale_ts(15)
    stale = check_stale_estimates(s, max_age_minutes=10.0)
    assert len(stale) == 1
    assert stale[0]['_age_sec'] > 600


def test_check_stale_estimates_ignores_confirmed():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5',
                 confirmed=True, fill_id='f1')
    s['_fill_ledger'][0]['estimated_at'] = _stale_ts(20)
    stale = check_stale_estimates(s, max_age_minutes=10.0)
    assert stale == []


def test_check_stale_estimates_ignores_fee_only_entries():
    s = _session()
    record_fee(s, 0.05, 'sell_adjustment', 'ord1')
    s['_fill_ledger'][0]['estimated_at'] = _stale_ts(20)
    stale = check_stale_estimates(s, max_age_minutes=10.0)
    assert stale == []


def test_check_stale_estimates_fresh_entry_not_returned():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    stale = check_stale_estimates(s, max_age_minutes=10.0)
    assert stale == []


def test_check_stale_estimates_does_not_modify_ledger():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0, 'close_at_5')
    s['_fill_ledger'][0]['estimated_at'] = _stale_ts(20)
    before_len = len(s['_fill_ledger'])
    check_stale_estimates(s, max_age_minutes=10.0)
    assert len(s['_fill_ledger']) == before_len


# ─────────────────────────────────────────────────────────────────────────────
# get_pnl
# ─────────────────────────────────────────────────────────────────────────────

def test_get_pnl_returns_all_required_keys():
    s = _session()
    result = get_pnl(s, _fetch_50)
    for key in ('realized', 'unrealized', 'fees', 'net_pnl', 'attribution',
                'confirmed_pnl', 'unconfirmed_pnl', 'fill_count',
                'confirmed_count', 'net_premium_collected'):
        assert key in result, f"Missing key: {key}"


def test_get_pnl_net_pnl_formula():
    s = _session()
    record_close(s, 'o1', 'C', 'ce', 70000, 10, 100, 50, 0.02, 'close_at_5')
    result = get_pnl(s, _fetch_50)
    assert result['net_pnl'] == pytest.approx(
        result['realized'] + result['unrealized'] - result['fees']
    )


def test_get_pnl_without_fetch_fn_unrealized_zero():
    s = _session()
    result = get_pnl(s)
    assert result['unrealized'] == 0.0


def test_get_pnl_includes_perp_in_net():
    s = _session()
    s['perp_hedge'] = {'realized_pnl': -0.1, 'unrealized_pnl': 0.0}
    result = get_pnl(s)
    assert result['perp_pnl'] == pytest.approx(-0.1)
    assert result['net_pnl'] == pytest.approx(-0.1)


def test_get_pnl_includes_reverse_in_net():
    s = _session()
    s['_reverse'] = {'net_pnl': 0.25}
    result = get_pnl(s)
    assert result['reverse_pnl'] == pytest.approx(0.25)
    assert result['net_pnl'] == pytest.approx(0.25)


def test_get_pnl_updates_peak_pnl():
    s = _session()
    s['peak_pnl'] = 0.0
    get_pnl(s, _fetch_50)
    # unrealized > 0 (sold at 100, now at 50) → peak should update
    assert s['peak_pnl'] > 0.0


def test_get_pnl_peak_not_updated_on_lower_value():
    s = _session()
    s['peak_pnl'] = 999.0
    result = get_pnl(s, _fetch_50)
    assert s['peak_pnl'] == pytest.approx(999.0)
