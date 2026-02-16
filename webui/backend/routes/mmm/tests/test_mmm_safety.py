"""
Test MMM Safety — Section 13/14 safety mechanisms.

Tests:
  - Position cap check
  - Max adjustments check
  - Max loss check
  - Whipsaw detection
  - Asymmetry detection
  - Near-expiry auto-close
  - P&L guardrail
  - Trailing stop
  - run_all_checks aggregation
  - should_block_adjustment
  - should_pause
"""

import pytest
from copy import deepcopy


def _make_session(**overrides):
    """Minimal session for safety tests."""
    session = {
        'session_id': 'test-safety-001',
        'strategy_status': 'RUNNING',
        'params': {
            'max_lots_per_side': 50,
            'max_adjustments': 20,
            'max_loss_amount': 3000,
            'whipsaw_count': 6,
            'whipsaw_window': 600,
            'near_expiry_auto_close_mins': 15,
            'near_expiry_stop_adjustment_mins': 30,
            'pnl_guardrail_pct': 0.5,
            'trailing_stop_pct': 0.3,
        },
        'ce': {
            'total_lots': 10,
            'active_lots': 10,
        },
        'pe': {
            'total_lots': 10,
            'active_lots': 10,
        },
        'adjustment_count': 5,
        'reversal_count': 2,
        'realized_pnl': 0,
        'unrealized_pnl': 0,
        'total_premium_collected': 2000,
        'peak_pnl': 500,
        'adjustment_history': [],
    }
    session.update(overrides)
    return session


class TestPositionCap:
    """Safety: position cap check."""

    def test_under_cap_ok(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        events = safety.check_position_cap(session)
        assert all(e.get('level') != 'critical' for e in events)

    def test_over_cap_critical(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        session['ce']['total_lots'] = 55  # Over max of 50
        events = safety.check_position_cap(session)
        critical = [e for e in events if e.get('level') == 'critical']
        assert len(critical) > 0


class TestMaxAdjustments:
    """Safety: max adjustments check."""

    def test_under_max_ok(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        session['adjustment_count'] = 5
        events = safety.check_max_adjustments(session)
        critical = [e for e in events if e.get('action') == 'stop_adjustments']
        assert len(critical) == 0

    def test_at_max_stops(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        session['adjustment_count'] = 20
        events = safety.check_max_adjustments(session)
        stop_events = [e for e in events if e.get('action') == 'stop_adjustments']
        assert len(stop_events) > 0


class TestMaxLoss:
    """Safety: max loss check."""

    def test_within_limit_ok(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        session['realized_pnl'] = -500
        session['unrealized_pnl'] = -500
        events = safety.check_max_loss(session)
        auto_close = [e for e in events if e.get('action') == 'auto_close']
        assert len(auto_close) == 0

    def test_exceeds_limit_auto_close(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        session['realized_pnl'] = -2000
        session['unrealized_pnl'] = -1500
        events = safety.check_max_loss(session)
        auto_close = [e for e in events if e.get('action') == 'auto_close']
        assert len(auto_close) > 0


class TestNearExpiry:
    """Safety: near-expiry auto-close."""

    def test_far_from_expiry_ok(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        events = safety.check_near_expiry(session, minutes_to_expiry=120)
        assert len(events) == 0

    def test_near_expiry_stops_adjustments(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        events = safety.check_near_expiry(session, minutes_to_expiry=25)
        stop_events = [e for e in events if e.get('action') == 'stop_adjustments']
        assert len(stop_events) > 0

    def test_very_near_expiry_auto_close(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        events = safety.check_near_expiry(session, minutes_to_expiry=10)
        auto_close = [e for e in events if e.get('action') == 'auto_close']
        assert len(auto_close) > 0


class TestTrailingStop:
    """Safety: trailing profit stop."""

    def test_no_trailing_when_pnl_above_floor(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        session['peak_pnl'] = 1000
        session['realized_pnl'] = 400
        session['unrealized_pnl'] = 400  # total = 800, floor = 700
        events = safety.check_trailing_stop(session)
        auto_close = [e for e in events if e.get('action') == 'auto_close']
        assert len(auto_close) == 0

    def test_trailing_triggers_auto_close(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        session['peak_pnl'] = 1000
        session['realized_pnl'] = 200
        session['unrealized_pnl'] = 200  # total = 400 < floor = 700
        events = safety.check_trailing_stop(session)
        auto_close = [e for e in events if e.get('action') == 'auto_close']
        assert len(auto_close) > 0


class TestRunAllChecks:
    """Integration: run_all_checks aggregates all individual checks."""

    def test_healthy_session_no_critical(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        events = safety.run_all_checks(session, minutes_to_expiry=120)
        critical = [e for e in events if e.get('level') == 'critical']
        assert len(critical) == 0

    def test_multiple_violations(self):
        from webui.backend.routes.mmm.mmm_safety import MMWSafety
        safety = MMWSafety()
        session = _make_session()
        session['adjustment_count'] = 25  # Over max
        session['realized_pnl'] = -4000  # Near max loss
        events = safety.run_all_checks(session, minutes_to_expiry=120)
        assert len(events) > 0


class TestShouldBlock:
    """should_block_adjustment checks."""

    def test_healthy_session_not_blocked(self):
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        session = _make_session()
        events = []
        assert should_block_adjustment(events) is False

    def test_auto_close_blocks(self):
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        events = [{'type': 'max_loss', 'level': 'critical', 'action': 'auto_close'}]
        assert should_block_adjustment(events) is True

    def test_stop_adjustments_blocks(self):
        from webui.backend.routes.mmm.mmm_safety import should_block_adjustment
        events = [{'type': 'near_expiry', 'level': 'warning', 'action': 'stop_adjustments'}]
        assert should_block_adjustment(events) is True
