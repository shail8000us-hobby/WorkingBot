"""
Test MMM Strike Shift — Section 10 freeze/find/activate.

Tests:
  - Shift needed detection
  - Freeze current positions
  - Activate new strike
"""

import pytest
from copy import deepcopy


def _make_session():
    """Minimal session for strike shift tests."""
    return {
        'session_id': 'test-shift-001',
        'strategy_status': 'RUNNING',
        'params': {
            'shift_threshold': 10,
        },
        'ce': {
            'original_strike': 100000,
            'active_strike': 100000,
            'original_premium': 100.0,
            'original_lots': 10,
            'active_lots': 10,
            'total_lots': 10,
            'frozen_total_lots': 0,
            'adjustment_fills': [
                {'strike': 100000, 'premium': 120.0, 'lots': 5, 'timestamp': '2026-02-15T10:00:00'},
            ],
            'frozen_positions': [],
            'symbol': 'C-BTC-100000-260215',
        },
        'pe': {
            'original_strike': 90000,
            'active_strike': 90000,
            'original_premium': 100.0,
            'original_lots': 10,
            'active_lots': 10,
            'total_lots': 10,
            'frozen_total_lots': 0,
            'adjustment_fills': [],
            'frozen_positions': [],
            'symbol': 'P-BTC-90000-260215',
        },
        'trigger_snapshots': {
            'ce': {'100000': 100.0},
            'pe': {'90000': 100.0},
        },
        'shift_count': 0,
    }


class TestCheckShiftNeeded:
    """Section 10: Shift when hedge premium drops below threshold."""

    def test_above_threshold_no_shift(self):
        from webui.backend.routes.mmm.mmm_strike_shift import check_shift_needed
        session = _make_session()
        assert check_shift_needed(session, 'pe', 50.0) is False

    def test_below_threshold_shift_needed(self):
        from webui.backend.routes.mmm.mmm_strike_shift import check_shift_needed
        session = _make_session()
        assert check_shift_needed(session, 'pe', 5.0) is True

    def test_at_threshold_no_shift(self):
        from webui.backend.routes.mmm.mmm_strike_shift import check_shift_needed
        session = _make_session()
        assert check_shift_needed(session, 'pe', 10.0) is False


class TestFreezePositions:
    """Section 10: Freeze current positions before shifting."""

    def test_freeze_moves_to_frozen(self):
        from webui.backend.routes.mmm.mmm_strike_shift import freeze_current_positions
        session = _make_session()

        freeze_current_positions(session, 'ce')
        ce = session['ce']

        # Original and adjustment fills should be moved to frozen
        assert len(ce['frozen_positions']) > 0
        assert ce['original_lots'] == 0
        assert len(ce['adjustment_fills']) == 0

    def test_freeze_preserves_frozen_lots_count(self):
        from webui.backend.routes.mmm.mmm_strike_shift import freeze_current_positions
        session = _make_session()

        freeze_current_positions(session, 'ce')
        ce = session['ce']

        # Total frozen lots should equal what was original + adjustment
        total_frozen = sum(p.get('lots', 0) for p in ce['frozen_positions'])
        assert total_frozen == 15  # 10 original + 5 adjustment


class TestActivateNewStrike:
    """Section 10: Activate a new strike after shifting."""

    def test_activate_updates_state(self):
        from webui.backend.routes.mmm.mmm_strike_shift import activate_new_strike
        session = _make_session()

        activate_new_strike(session, 'ce', 105000, 80.0, 10)

        ce = session['ce']
        assert ce['active_strike'] == 105000
        assert ce['original_premium'] == 80.0
        assert ce['original_lots'] == 10
        assert session['shift_count'] == 1

    def test_activate_updates_trigger_snapshot(self):
        from webui.backend.routes.mmm.mmm_strike_shift import activate_new_strike
        session = _make_session()

        activate_new_strike(session, 'pe', 85000, 90.0, 10)

        # Trigger snapshot should have new strike
        pe_snap = session['trigger_snapshots'].get('pe', {})
        assert '85000' in pe_snap or 85000 in pe_snap
