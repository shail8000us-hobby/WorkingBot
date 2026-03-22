"""
Sealed contract tests for scan_closeable_positions + close_position (#84)

Functions sealed:
  - scan_closeable_positions(session, fetch_premium_fn, threshold_override) → list
  - close_position(executor, initializer, session, position, ...) → dict

File: webui/backend/routes/mmm/mmm_close_at_5.py

Audit outcome (2026-03-20):
  - No critical money bugs found.
  - Sort key puts side before profit (low impact — all items processed per heartbeat).
  - _being_closed_at not cleared on failure paths — harmless orphan field.

Contracts:

  [scan_closeable_positions — 18 contracts]
  C1.  Empty session → empty list
  C2.  Original position below threshold → returned
  C3.  Original position above threshold → skipped
  C4.  Original with lots=0 → skipped
  C5.  Original with strike=0 → skipped
  C6.  Original with active _being_closed (fresh) → skipped, flag preserved
  C7.  Stale _being_closed (>TTL) → flag auto-cleared, position returned
  C8.  Adjustment fill below threshold → returned
  C9.  Adjustment fill with _being_closed → skipped
  C10. Frozen position below threshold → returned
  C11. Frozen position with _being_closed → skipped
  C12. fetch_premium_fn returns None → position skipped, no crash
  C13. fetch_premium_fn raises → position skipped, no uncaught exception
  C14. threshold_override used when provided (overrides params default)
  C15. All returned items carry 'threshold_used' key equal to threshold applied
  C16. Both CE and PE sides scanned simultaneously
  C17. premium == threshold exactly → included (<=, not <)
  C18. Sort: frozen > adjustment > original within same side

  [close_position — 12 contracts]
  CA1.  Missing side → {success: False, error: 'missing side'}
  CA2.  _being_closed guard (pos_id path) blocks duplicate close
  CA3.  _being_closed guard (content-match path) blocks duplicate close
  CA4.  Order failure → clears _being_closed flag so retry is possible
  CA5.  Order success → session realized_pnl updated correctly
  CA6.  Order success → close_at_5_count incremented
  CA7.  Partial fill → position lots reduced, not removed
  CA8.  Partial fill → realized_pnl uses actual_lots not requested lots
  CA9.  Commission added to session total_fees
  CA10. P&L attribution: original → pnl_initial
  CA11. P&L attribution: adjustment → pnl_adjustment
  CA12. Exception → _being_closed cleared, recompute_side_lots called
"""

import asyncio
import selectors
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

pytestmark = pytest.mark.sealed


def _run(coro):
    """Run an async coroutine using select()-based event loop.

    Avoids macOS kqueue fd-reuse bug: after a prior loop closes its kqueue,
    the kernel may still hold stale fd registrations. A new kqueue() call can
    reuse the same fd number, causing KqueueSelector.register() to fail with
    a duplicate-fd error when _make_self_pipe() runs.

    Using SelectSelector (POSIX select() syscall) bypasses kqueue entirely
    and is safe to call repeatedly within a single pytest session.
    """
    loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)

from webui.backend.routes.mmm.mmm_close_at_5 import (
    scan_closeable_positions,
    close_position,
    _BEING_CLOSED_TTL,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

def _pos_entry(pos_id, pos_type='original', status='active', **kwargs):
    entry = {'id': pos_id, 'type': pos_type, 'status': status}
    entry.update(kwargs)
    return entry


def _side(
    original_lots=0,
    original_premium=0.0,
    original_strike=0,
    adjustment_fills=None,
    frozen_positions=None,
    positions=None,
    total_lots=None,
):
    fills = adjustment_fills or []
    frozen = frozen_positions or []
    pos = positions or []
    tl = total_lots if total_lots is not None else (
        original_lots
        + sum(f.get('lots', 0) for f in fills)
        + sum(f.get('lots', 0) for f in frozen)
    )
    return {
        'original_lots': original_lots,
        'original_premium': original_premium,
        'original_strike': original_strike,
        'active_strike': original_strike,
        'adjustment_fills': fills,
        'frozen_positions': frozen,
        'positions': pos,
        'total_lots': tl,
        'trigger_snapshot': {},
    }


def _session(ce=None, pe=None, params=None, session_id='test-001'):
    return {
        'session_id': session_id,
        'params': params or {'close_at_threshold': 5.0, 'expiry': '2026-03-28'},
        'ce': ce or _side(),
        'pe': pe or _side(),
        'realized_pnl': 0.0,
        'close_at_5_count': 0,
        'total_fees': 0.0,
        'strategy_status': 'RUNNING',
    }


def _fixed_premium(value):
    """fetch_premium_fn that always returns `value`."""
    return lambda strike, opt_type: value


def _make_executor(fill_price=3.0, filled_size=5, success=True):
    executor = MagicMock()
    executor.smart_execute = AsyncMock(return_value={
        'success': success,
        'fill_price': fill_price if success else None,
        'filled_size': filled_size,
        'order_id': 'ord-001',
        'order_details': {},
        'error': None if success else 'simulated failure',
    })
    # Prevent external-close REST check from hanging in tests
    executor._create_rest_client.side_effect = AttributeError("no REST in test")
    return executor


def _make_init(symbol='BTC-28MAR26-80000-C'):
    init = MagicMock()
    init.build_symbol.return_value = symbol
    return init


# ─── C1–C18: scan_closeable_positions ─────────────────────────────────────────

def test_c1_empty_session_returns_empty():
    assert scan_closeable_positions(_session(), _fixed_premium(1.0)) == []


def test_c2_original_below_threshold_returned():
    ce = _side(
        original_lots=5, original_premium=50.0, original_strike=80000,
        positions=[_pos_entry('p1', 'original')],
    )
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(4.0))
    assert len(result) == 1
    r = result[0]
    assert r['side'] == 'ce'
    assert r['type'] == 'original'
    assert r['strike'] == 80000
    assert r['lots'] == 5
    assert r['current_premium'] == 4.0


def test_c3_original_above_threshold_skipped():
    ce = _side(
        original_lots=5, original_premium=50.0, original_strike=80000,
        positions=[_pos_entry('p1')],
    )
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(10.0))
    assert result == []


def test_c4_original_lots_zero_skipped():
    ce = _side(original_lots=0, original_premium=50.0, original_strike=80000)
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(1.0))
    assert result == []


def test_c5_original_strike_zero_skipped():
    ce = _side(original_lots=5, original_premium=50.0, original_strike=0)
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(1.0))
    assert result == []


def test_c6_original_being_closed_fresh_skipped():
    pos = _pos_entry('p1', 'original',
                     _being_closed=True, _being_closed_at=time.monotonic())
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[pos])
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(1.0))
    assert result == []
    assert pos.get('_being_closed') is True  # flag untouched


def test_c7_stale_being_closed_cleared_position_returned():
    stale_time = time.monotonic() - (_BEING_CLOSED_TTL + 10)
    pos = _pos_entry('p1', 'original',
                     _being_closed=True, _being_closed_at=stale_time)
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[pos])
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(2.0))
    # Flag auto-cleared
    assert not pos.get('_being_closed')
    # Position returned since premium 2.0 <= threshold 5.0
    assert len(result) == 1
    assert result[0]['type'] == 'original'


def test_c8_adjustment_fill_below_threshold_returned():
    fill = {'lots': 3, 'premium': 40.0, 'strike': 79000}
    pe = _side(adjustment_fills=[fill])
    result = scan_closeable_positions(_session(pe=pe), _fixed_premium(3.0))
    assert len(result) == 1
    r = result[0]
    assert r['type'] == 'adjustment'
    assert r['side'] == 'pe'
    assert r['strike'] == 79000
    assert r['lots'] == 3


def test_c9_adjustment_fill_being_closed_skipped():
    fill = {
        'lots': 3, 'premium': 40.0, 'strike': 79000,
        '_being_closed': True, '_being_closed_at': time.monotonic(),
    }
    pe = _side(adjustment_fills=[fill])
    result = scan_closeable_positions(_session(pe=pe), _fixed_premium(1.0))
    assert result == []


def test_c10_frozen_position_below_threshold_returned():
    frozen = {'lots': 4, 'entry_premium': 30.0, 'strike': 78000}
    ce = _side(frozen_positions=[frozen])
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(2.0))
    assert len(result) == 1
    r = result[0]
    assert r['type'] == 'frozen'
    assert r['side'] == 'ce'
    assert r['lots'] == 4


def test_c11_frozen_being_closed_skipped():
    frozen = {
        'lots': 4, 'entry_premium': 30.0, 'strike': 78000,
        '_being_closed': True, '_being_closed_at': time.monotonic(),
    }
    ce = _side(frozen_positions=[frozen])
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(1.0))
    assert result == []


def test_c12_fetch_premium_none_skips_no_crash():
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[_pos_entry('p1')])
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(None))
    assert result == []


def test_c13_fetch_premium_raises_no_uncaught_exception():
    def bad_fetch(strike, opt_type):
        raise ValueError("network timeout")

    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[_pos_entry('p1')])
    result = scan_closeable_positions(_session(ce=ce), bad_fetch)
    assert result == []


def test_c14_threshold_override_used_over_params():
    # params default = 5.0, current premium = 8.0 → skipped normally
    # override = 10.0 → returned
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[_pos_entry('p1')])
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(8.0),
                                      threshold_override=10.0)
    assert len(result) == 1
    assert result[0]['threshold_used'] == 10.0


def test_c15_threshold_used_stamped_on_all_returned_items():
    ce = _side(
        original_lots=5, original_premium=50.0, original_strike=80000,
        positions=[_pos_entry('p1')],
        adjustment_fills=[{'lots': 2, 'premium': 30.0, 'strike': 79000}],
    )
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(2.0))
    assert len(result) == 2
    for item in result:
        assert 'threshold_used' in item
        assert item['threshold_used'] == 5.0


def test_c16_both_sides_scanned():
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[_pos_entry('p1')])
    pe = _side(original_lots=3, original_premium=40.0, original_strike=79000,
               positions=[_pos_entry('p2')])
    result = scan_closeable_positions(_session(ce=ce, pe=pe), _fixed_premium(2.0))
    sides = {r['side'] for r in result}
    assert 'ce' in sides
    assert 'pe' in sides


def test_c17_premium_equal_to_threshold_included():
    # Exactly at threshold — condition is <=, not <
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[_pos_entry('p1')])
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(5.0))
    assert len(result) == 1


def test_c18_sort_order_frozen_before_adj_before_original_same_side():
    ce = _side(
        original_lots=5, original_premium=50.0, original_strike=80000,
        positions=[_pos_entry('p1', 'original')],
        adjustment_fills=[{'lots': 2, 'premium': 30.0, 'strike': 80000}],
        frozen_positions=[{'lots': 3, 'entry_premium': 20.0, 'strike': 80000}],
    )
    result = scan_closeable_positions(_session(ce=ce), _fixed_premium(2.0))
    assert len(result) == 3
    ce_items = [r for r in result if r['side'] == 'ce']
    assert ce_items[0]['type'] == 'frozen'
    assert ce_items[1]['type'] == 'adjustment'
    assert ce_items[2]['type'] == 'original'


# ─── CA1–CA12: close_position ─────────────────────────────────────────────────

def test_ca1_missing_side_returns_error():
    pos = {'type': 'original', 'strike': 80000, 'lots': 5, 'entry_premium': 50.0}
    result = _run(
        close_position(None, None, _session(), pos, hedge_guard=False)
    )
    assert result['success'] is False
    assert result['error'] == 'missing side'


def test_ca2_being_closed_guard_pos_id_blocks_duplicate():
    pos_id = 'p-001'
    pos_entry = _pos_entry(pos_id, 'original',
                           _being_closed=True, _being_closed_at=time.monotonic())
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[pos_entry])
    session = _session(ce=ce)
    position = {
        'side': 'ce', 'strike': 80000, 'lots': 5,
        'entry_premium': 50.0, 'type': 'original', '_pos_id': pos_id,
    }
    result = _run(
        close_position(None, None, session, position, hedge_guard=False)
    )
    assert result['success'] is False
    assert 'in-flight guard' in result['error']


def test_ca3_being_closed_guard_content_match_blocks_duplicate():
    fill = {
        'lots': 3, 'premium': 40.0, 'strike': 79000,
        '_being_closed': True, '_being_closed_at': time.monotonic(),
    }
    pe = _side(adjustment_fills=[fill])
    session = _session(pe=pe)
    # No _pos_id → triggers content-match path
    position = {
        'side': 'pe', 'strike': 79000, 'lots': 3,
        'entry_premium': 40.0, 'type': 'adjustment',
    }
    result = _run(
        close_position(None, None, session, position, hedge_guard=False)
    )
    assert result['success'] is False
    assert 'content-match guard' in result['error']


def test_ca4_order_failure_clears_being_closed():
    pos_id = 'p-001'
    pos_entry = _pos_entry(pos_id, 'original', lots=5)
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[pos_entry])
    session = _session(ce=ce)
    position = {
        'side': 'ce', 'strike': 80000, 'lots': 5,
        'entry_premium': 50.0, 'type': 'original', '_pos_id': pos_id,
        'current_premium': 3.0, 'threshold_used': 5.0,
    }
    executor = _make_executor(success=False)
    result = _run(
        close_position(executor, _make_init(), session, position, hedge_guard=False)
    )
    assert result['success'] is False
    # _being_closed must be cleared for retry
    assert not pos_entry.get('_being_closed')


def test_ca5_success_updates_realized_pnl():
    pos_id = 'p-001'
    pos_entry = _pos_entry(pos_id, 'original', lots=5)
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[pos_entry], total_lots=5)
    session = _session(ce=ce)
    position = {
        'side': 'ce', 'strike': 80000, 'lots': 5,
        'entry_premium': 50.0, 'current_premium': 3.0,
        'type': 'original', '_pos_id': pos_id, 'threshold_used': 5.0,
    }
    executor = _make_executor(fill_price=3.0, filled_size=5)

    with patch('webui.backend.routes.mmm.mmm_close_at_5.recompute_side_lots'):
        result = _run(
            close_position(executor, _make_init(), session, position, hedge_guard=False)
        )

    assert result['success'] is True
    # P&L = (50 - 3) * 5 * 0.001 = 0.235
    assert abs(result['realized_pnl'] - 0.235) < 1e-6
    assert abs(session['realized_pnl'] - 0.235) < 1e-6


def test_ca6_success_increments_close_at_5_count():
    pos_id = 'p-001'
    pos_entry = _pos_entry(pos_id, 'original', lots=5)
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[pos_entry], total_lots=5)
    session = _session(ce=ce)
    position = {
        'side': 'ce', 'strike': 80000, 'lots': 5,
        'entry_premium': 50.0, 'current_premium': 3.0,
        'type': 'original', '_pos_id': pos_id, 'threshold_used': 5.0,
    }
    executor = _make_executor(fill_price=3.0, filled_size=5)

    with patch('webui.backend.routes.mmm.mmm_close_at_5.recompute_side_lots'):
        _run(
            close_position(executor, _make_init(), session, position, hedge_guard=False)
        )

    assert session['close_at_5_count'] == 1


def test_ca7_partial_fill_reduces_lots_not_closed():
    pos_id = 'p-001'
    pos_entry = _pos_entry(pos_id, 'original', lots=5, status='active')
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[pos_entry], total_lots=5)
    session = _session(ce=ce)
    position = {
        'side': 'ce', 'strike': 80000, 'lots': 5,
        'entry_premium': 50.0, 'current_premium': 3.0,
        'type': 'original', '_pos_id': pos_id, 'threshold_used': 5.0,
    }
    # Only 3 of 5 lots filled
    executor = _make_executor(fill_price=3.0, filled_size=3)

    with patch('webui.backend.routes.mmm.mmm_close_at_5.recompute_side_lots'):
        result = _run(
            close_position(executor, _make_init(), session, position, hedge_guard=False)
        )

    assert result['success'] is True
    assert result['lots_closed'] == 3
    # Position NOT fully closed — remaining 2 lots still active
    assert pos_entry.get('status') != 'closed'
    assert pos_entry.get('lots') == 2


def test_ca8_partial_fill_pnl_uses_actual_lots_not_requested():
    pos_id = 'p-001'
    pos_entry = _pos_entry(pos_id, 'original', lots=10, status='active')
    ce = _side(original_lots=10, original_premium=50.0, original_strike=80000,
               positions=[pos_entry], total_lots=10)
    session = _session(ce=ce)
    position = {
        'side': 'ce', 'strike': 80000, 'lots': 10,
        'entry_premium': 50.0, 'current_premium': 3.0,
        'type': 'original', '_pos_id': pos_id, 'threshold_used': 5.0,
    }
    # 4 of 10 filled
    executor = _make_executor(fill_price=3.0, filled_size=4)

    with patch('webui.backend.routes.mmm.mmm_close_at_5.recompute_side_lots'):
        result = _run(
            close_position(executor, _make_init(), session, position, hedge_guard=False)
        )

    # P&L = (50 - 3) * 4 * 0.001 = 0.188  (not 10-lot: 0.47)
    assert abs(result['realized_pnl'] - 0.188) < 1e-6


def test_ca9_commission_added_to_total_fees():
    pos_id = 'p-001'
    pos_entry = _pos_entry(pos_id, 'original', lots=5)
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[pos_entry], total_lots=5)
    session = _session(ce=ce)
    position = {
        'side': 'ce', 'strike': 80000, 'lots': 5,
        'entry_premium': 50.0, 'current_premium': 3.0,
        'type': 'original', '_pos_id': pos_id, 'threshold_used': 5.0,
    }
    executor = MagicMock()
    executor.smart_execute = AsyncMock(return_value={
        'success': True,
        'fill_price': 3.0,
        'filled_size': 5,
        'order_id': 'ord-001',
        'order_details': {'paid_commission': 0.05},
    })
    executor._create_rest_client.side_effect = AttributeError("no REST in test")

    with patch('webui.backend.routes.mmm.mmm_close_at_5.recompute_side_lots'):
        _run(
            close_position(executor, _make_init(), session, position, hedge_guard=False)
        )

    assert abs(session['total_fees'] - 0.05) < 1e-9


def test_ca10_pnl_attribution_original_to_pnl_initial():
    pos_id = 'p-001'
    pos_entry = _pos_entry(pos_id, 'original', lots=5)
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[pos_entry], total_lots=5)
    session = _session(ce=ce)
    position = {
        'side': 'ce', 'strike': 80000, 'lots': 5,
        'entry_premium': 50.0, 'current_premium': 3.0,
        'type': 'original', '_pos_id': pos_id, 'threshold_used': 5.0,
    }
    executor = _make_executor(fill_price=3.0, filled_size=5)

    with patch('webui.backend.routes.mmm.mmm_close_at_5.recompute_side_lots'):
        _run(
            close_position(executor, _make_init(), session, position, hedge_guard=False)
        )

    assert 'pnl_initial' in session
    assert session['pnl_initial'] > 0
    assert 'pnl_adjustment' not in session


def test_ca11_pnl_attribution_adjustment_to_pnl_adjustment():
    fill_entry = {'lots': 3, 'premium': 40.0, 'strike': 79000}
    pe = _side(adjustment_fills=[fill_entry])
    session = _session(pe=pe)
    # No _pos_id → content-match path
    position = {
        'side': 'pe', 'strike': 79000, 'lots': 3,
        'entry_premium': 40.0, 'current_premium': 2.0,
        'type': 'adjustment', 'threshold_used': 5.0,
    }
    executor = _make_executor(fill_price=2.0, filled_size=3)

    with patch('webui.backend.routes.mmm.mmm_close_at_5.recompute_side_lots'):
        _run(
            close_position(executor, _make_init(), session, position, hedge_guard=False)
        )

    assert 'pnl_adjustment' in session
    assert session['pnl_adjustment'] > 0
    assert 'pnl_initial' not in session


def test_ca12_exception_clears_being_closed_and_calls_recompute():
    pos_id = 'p-001'
    pos_entry = _pos_entry(pos_id, 'original', lots=5)
    ce = _side(original_lots=5, original_premium=50.0, original_strike=80000,
               positions=[pos_entry], total_lots=5)
    session = _session(ce=ce)
    position = {
        'side': 'ce', 'strike': 80000, 'lots': 5,
        'entry_premium': 50.0, 'current_premium': 3.0,
        'type': 'original', '_pos_id': pos_id, 'threshold_used': 5.0,
    }
    executor = MagicMock()
    executor.smart_execute = AsyncMock(side_effect=RuntimeError("exchange down"))
    executor._create_rest_client.side_effect = AttributeError("no REST in test")

    with patch('webui.backend.routes.mmm.mmm_close_at_5.recompute_side_lots') as mock_recompute:
        result = _run(
            close_position(executor, _make_init(), session, position, hedge_guard=False)
        )

    assert result['success'] is False
    assert 'exchange down' in result['error']
    assert not pos_entry.get('_being_closed')
    mock_recompute.assert_called_once()
