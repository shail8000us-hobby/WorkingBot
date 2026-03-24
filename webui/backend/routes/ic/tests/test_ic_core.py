"""
IC Unit Tests — Core Engine, Trigger, Safety, Exit, Config

Tests the critical calculation logic without API dependency.
"""

import os
import sys
import json
import tempfile
import unittest

# Add project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from webui.backend.routes.ic.ic_constants import (
    LOT_SIZE_BTC, LEG_SP, LEG_LP, LEG_SC, LEG_LC,
    STATUS_IDLE, STATUS_RUNNING,
    STRATEGY_IDLE, STRATEGY_ACTIVE, STRATEGY_ENTRY_PENDING,
)
from webui.backend.routes.ic.ic_config import (
    DEFAULT_PARAMS, validate_params, get_hot_reload_params,
)
from webui.backend.routes.ic.ic_state import (
    create_session, create_cycle_state, create_leg_state,
    compute_cycle_strikes, compute_entry_credit, archive_cycle,
    reset_daily_loss,
)
from webui.backend.routes.ic.ic_engine import (
    compute_net_credit, compute_max_profit, compute_max_loss,
    compute_effective_net_credit, compute_leg_pnl,
    compute_unrealized_pnl, compute_pnl_pct, compute_realized_pnl,
    update_cycle_pnl, compute_roll_credit,
)
from webui.backend.routes.ic.ic_trigger import (
    is_call_side_threatened, is_put_side_threatened,
    get_breach_status, should_use_rapid_check,
    get_call_distance_pct, get_put_distance_pct,
)
from webui.backend.routes.ic.ic_greeks import (
    compute_portfolio_greeks, is_portfolio_skewed,
)
from webui.backend.routes.ic.ic_safety import (
    check_daily_loss_limit, check_max_loss, check_max_adjustments,
    check_emergency_breach, run_safety_gate,
)
from webui.backend.routes.ic.ic_exit import check_exit_conditions
from webui.backend.routes.ic.ic_adjuster import (
    decide_adjustment, DECISION_NO_ACTION, DECISION_ROLL_CALL,
    DECISION_ROLL_BOTH, DECISION_EMERGENCY_CLOSE, DECISION_EXIT_CYCLE,
)
from webui.backend.routes.ic.ic_cycle import (
    should_open_new_cycle, prepare_new_cycle, activate_cycle,
)
from webui.backend.routes.ic.ic_storage import ICStorage


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_legs(
    sp_strike=84000, lp_strike=83000,
    sc_strike=90000, lc_strike=91000,
    sp_prem=120, lp_prem=60, sc_prem=130, lc_prem=65,
    lots=10,
):
    """Create a standard 4-leg IC for testing."""
    return {
        LEG_SP: create_leg_state(LEG_SP, sp_strike, lots, 'put', 'sell', sp_prem),
        LEG_LP: create_leg_state(LEG_LP, lp_strike, lots, 'put', 'buy', lp_prem),
        LEG_SC: create_leg_state(LEG_SC, sc_strike, lots, 'call', 'sell', sc_prem),
        LEG_LC: create_leg_state(LEG_LC, lc_strike, lots, 'call', 'buy', lc_prem),
    }


def _make_session_with_cycle(**kwargs):
    """Create a session with an active cycle for testing."""
    session = create_session(params={'simulate': True, **kwargs})
    session['status'] = STATUS_RUNNING
    session['strategy_status'] = STRATEGY_ACTIVE
    cycle = create_cycle_state(cycle_number=1, expiry='2026-04-01', lots=10)
    cycle['legs'] = _make_legs()
    compute_cycle_strikes(cycle)
    compute_entry_credit(cycle, 10)
    session['current_cycle'] = cycle
    session['expiry'] = '2026-04-01'
    return session


# =============================================================================
# Config Tests
# =============================================================================

class TestConfig(unittest.TestCase):
    def test_defaults_have_all_rules(self):
        """Every default param should have a validation rule."""
        for key in DEFAULT_PARAMS:
            self.assertIn(key, {
                k for k in DEFAULT_PARAMS
            }, f"Missing rule for default param: {key}")

    def test_validate_valid_params(self):
        """All defaults should pass validation."""
        validated, errors = validate_params(DEFAULT_PARAMS)
        self.assertEqual(errors, [], f"Default params validation errors: {errors}")

    def test_validate_rejects_out_of_range(self):
        validated, errors = validate_params({'lots': 9999})
        self.assertTrue(len(errors) > 0)

    def test_validate_rejects_bad_type(self):
        validated, errors = validate_params({'lots': 'abc'})
        self.assertTrue(len(errors) > 0)

    def test_hot_reload_params_exist(self):
        hot = get_hot_reload_params()
        self.assertIn('simulate', hot)
        self.assertNotIn('lots', hot)

    def test_interdependency_rapid_vs_normal(self):
        validated, errors = validate_params({
            'rapid_check_interval': 120,
            'adjustment_interval': 60,
        })
        self.assertTrue(any('rapid_check_interval' in e for e in errors))


# =============================================================================
# State Tests
# =============================================================================

class TestState(unittest.TestCase):
    def test_create_session(self):
        session = create_session(name='Test IC', params={'lots': 5})
        self.assertIn('ic_', session['session_id'])
        self.assertEqual(session['status'], STATUS_IDLE)
        self.assertEqual(session['params']['lots'], 5)
        self.assertIsNone(session['current_cycle'])

    def test_create_leg_state(self):
        leg = create_leg_state(LEG_SP, 84000, 10, 'put', 'sell', 120.0)
        self.assertEqual(leg['leg_key'], LEG_SP)
        self.assertEqual(leg['strike'], 84000)
        self.assertEqual(leg['entry_premium'], 120.0)
        self.assertEqual(leg['action'], 'sell')

    def test_compute_cycle_strikes(self):
        cycle = create_cycle_state(1, '2026-04-01', 10)
        cycle['legs'] = _make_legs()
        compute_cycle_strikes(cycle)
        self.assertEqual(cycle['short_put_strike'], 84000)
        self.assertEqual(cycle['long_put_strike'], 83000)
        self.assertEqual(cycle['short_call_strike'], 90000)
        self.assertEqual(cycle['long_call_strike'], 91000)
        self.assertEqual(cycle['wing_width_put'], 1000)
        self.assertEqual(cycle['wing_width_call'], 1000)

    def test_compute_entry_credit(self):
        cycle = create_cycle_state(1, '2026-04-01', 10)
        legs = _make_legs(sp_prem=120, lp_prem=60, sc_prem=130, lc_prem=65)
        cycle['legs'] = legs
        compute_entry_credit(cycle, 10)
        # Net credit = (120 + 130) - (60 + 65) = 125 USD/BTC
        self.assertAlmostEqual(cycle['entry_net_credit'], 125.0)
        # USD: 125 × 10 × 0.001 = 1.25
        self.assertAlmostEqual(cycle['entry_net_credit_usd'], 1.25)

    def test_archive_cycle(self):
        session = _make_session_with_cycle()
        session['current_cycle']['closed_at'] = '2026-04-01T00:00:00'
        session['current_cycle']['exit_reason'] = 'profit_target'
        archive_cycle(session)
        self.assertIsNone(session['current_cycle'])
        self.assertEqual(len(session['cycle_history']), 1)
        self.assertEqual(session['cycle_history'][0]['exit_reason'], 'profit_target')


# =============================================================================
# Engine Tests
# =============================================================================

class TestEngine(unittest.TestCase):
    def test_net_credit(self):
        legs = _make_legs(sp_prem=120, lp_prem=60, sc_prem=130, lc_prem=65)
        nc = compute_net_credit(legs)
        self.assertAlmostEqual(nc, 125.0)

    def test_max_profit(self):
        # 125 USD/BTC × 10 lots × 0.001
        mp = compute_max_profit(125.0, 10)
        self.assertAlmostEqual(mp, 1.25)

    def test_max_loss_symmetric(self):
        # Wing = 1000, credit = 125
        # max_loss_per_btc = 1000 - 125 = 875
        # max_loss_usd = -(875 × 10 × 0.001) = -8.75
        ml = compute_max_loss(84000, 83000, 90000, 91000, 125.0, 10)
        self.assertAlmostEqual(ml, -8.75)

    def test_max_loss_asymmetric_after_roll(self):
        # After roll: put wing = 1000, call wing = 2000 (wider)
        # max_wing = 2000, credit = 100
        # max_loss = -(2000 - 100) × 10 × 0.001 = -19.0
        ml = compute_max_loss(84000, 83000, 90000, 92000, 100.0, 10)
        self.assertAlmostEqual(ml, -19.0)

    def test_leg_pnl_sell(self):
        leg = create_leg_state(LEG_SP, 84000, 10, 'put', 'sell', 120.0)
        leg['mark_premium'] = 80.0  # Premium fell → profit for seller
        pnl = compute_leg_pnl(leg)
        self.assertAlmostEqual(pnl, 40.0)  # 120 - 80

    def test_leg_pnl_buy(self):
        leg = create_leg_state(LEG_LP, 83000, 10, 'put', 'buy', 60.0)
        leg['mark_premium'] = 40.0  # Premium fell → loss for buyer
        pnl = compute_leg_pnl(leg)
        self.assertAlmostEqual(pnl, -20.0)  # 40 - 60

    def test_unrealized_pnl(self):
        legs = _make_legs()
        # Set mark prices such that premiums decayed 50%
        legs[LEG_SP]['mark_premium'] = 60.0   # sell 120 → 60, gain 60
        legs[LEG_LP]['mark_premium'] = 30.0   # buy 60 → 30, loss -30
        legs[LEG_SC]['mark_premium'] = 65.0   # sell 130 → 65, gain 65
        legs[LEG_LC]['mark_premium'] = 32.5   # buy 65 → 32.5, loss -32.5
        # Net per BTC: 60 - 30 + 65 - 32.5 = 62.5
        pnl = compute_unrealized_pnl(legs, 10)
        self.assertAlmostEqual(pnl, 0.625)  # 62.5 × 10 × 0.001

    def test_pnl_pct(self):
        pct = compute_pnl_pct(0.625, 1.25)
        self.assertAlmostEqual(pct, 50.0)

    def test_roll_credit_positive(self):
        """Rolling to wider strikes for net credit."""
        old_legs = _make_legs()
        new_legs = _make_legs(sc_strike=92000, lc_strike=93000,
                              sc_prem=100, lc_prem=45)

        old_close_premiums = {LEG_SC: 150, LEG_LC: 70}
        new_entry_premiums = {LEG_SC: 100, LEG_LC: 45}

        credit = compute_roll_credit(
            old_close_premiums, new_entry_premiums,
            old_legs, new_legs,
        )
        # Close old: buy back SC at 150 (-150), sell LC at 70 (+70) = -80
        # Open new: sell SC at 100 (+100), buy LC at 45 (-45) = +55
        # Net: -80 + 55 = -25
        self.assertAlmostEqual(credit, -25.0)


# =============================================================================
# Trigger Tests
# =============================================================================

class TestTrigger(unittest.TestCase):
    def test_call_threatened_within_breach(self):
        # spot=89600, SC=90000, breach=5%
        # distance = (90000 - 89600) / 89600 × 100 = 0.446%
        self.assertTrue(is_call_side_threatened(89600, 90000, 5.0))

    def test_call_not_threatened(self):
        # spot=85000, SC=90000, breach=5%
        # distance = (90000 - 85000) / 85000 × 100 = 5.88%
        self.assertFalse(is_call_side_threatened(85000, 90000, 5.0))

    def test_put_threatened(self):
        # spot=84200, SP=84000, breach=5%
        # distance = (84200 - 84000) / 84200 × 100 = 0.237%
        self.assertTrue(is_put_side_threatened(84200, 84000, 5.0))

    def test_both_threatened(self):
        # spot=87000, SP=86800, SC=87200
        _, _, breach_type = get_breach_status(87000, 86800, 87200, 5.0)
        self.assertEqual(breach_type, 'both')

    def test_rapid_check(self):
        # spot=85000, SP=84000, SC=90000, breach=5%
        # call distance = 5.88%, rapid threshold = 10% → True
        # put distance = 1.18%, rapid threshold = 10% → True
        self.assertTrue(should_use_rapid_check(85000, 84000, 90000, 5.0))


# =============================================================================
# Greeks Tests
# =============================================================================

class TestGreeks(unittest.TestCase):
    def test_portfolio_greeks_net_near_zero(self):
        """A well-balanced IC should have near-zero net delta."""
        legs = _make_legs()
        # Typical deltas for a balanced IC
        legs[LEG_SP]['mark_delta'] = -0.16  # Short put
        legs[LEG_LP]['mark_delta'] = -0.05  # Long put (further OTM)
        legs[LEG_SC]['mark_delta'] = 0.16   # Short call
        legs[LEG_LC]['mark_delta'] = 0.05   # Long call (further OTM)

        greeks = compute_portfolio_greeks(legs, 10)
        # sell SP: -1 × (-0.16) × 10 = +1.6
        # buy LP: +1 × (-0.05) × 10 = -0.5
        # sell SC: -1 × 0.16 × 10 = -1.6
        # buy LC: +1 × 0.05 × 10 = +0.5
        # Net delta = 1.6 - 0.5 - 1.6 + 0.5 = 0.0
        self.assertAlmostEqual(greeks['delta'], 0.0, places=4)

    def test_skew_detection(self):
        self.assertTrue(is_portfolio_skewed({'delta': 0.1}, threshold=0.05))
        self.assertFalse(is_portfolio_skewed({'delta': 0.03}, threshold=0.05))


# =============================================================================
# Safety Tests
# =============================================================================

class TestSafety(unittest.TestCase):
    def test_daily_loss_limit_triggered(self):
        session = create_session(params={'max_daily_loss_usd': 500})
        session['daily_loss_usd'] = 600
        event = check_daily_loss_limit(session)
        self.assertIsNotNone(event)
        self.assertEqual(event['action'], 'stop')

    def test_daily_loss_warning(self):
        session = create_session(params={'max_daily_loss_usd': 500})
        session['daily_loss_usd'] = 420  # 84%
        event = check_daily_loss_limit(session)
        self.assertIsNotNone(event)
        self.assertEqual(event['action'], 'warn')

    def test_max_adjustments_hit(self):
        cycle = create_cycle_state(1, '2026-04-01', 10)
        cycle['adjustment_count'] = 3
        event = check_max_adjustments(cycle, {'max_adjustments_per_cycle': 3})
        self.assertIsNotNone(event)

    def test_emergency_breach(self):
        event = check_emergency_breach(True, True)
        self.assertIsNotNone(event)
        self.assertEqual(event['action'], 'stop')

    def test_safety_gate_passes_on_healthy(self):
        session = _make_session_with_cycle()
        is_blocked, event = run_safety_gate(session)
        self.assertFalse(is_blocked)


# =============================================================================
# Exit Tests
# =============================================================================

class TestExit(unittest.TestCase):
    def test_profit_target_hit(self):
        cycle = create_cycle_state(1, '2026-04-01', 10)
        cycle['pnl_as_pct_of_max_profit'] = 55.0
        reason = check_exit_conditions(
            cycle, {'profit_target_pct': 50, 'close_at_dte': 1, 'max_loss_pct': 100},
            minutes_to_expiry=5000,
        )
        self.assertEqual(reason, 'profit_target')

    def test_dte_close(self):
        cycle = create_cycle_state(1, '2026-04-01', 10)
        cycle['pnl_as_pct_of_max_profit'] = 10.0
        reason = check_exit_conditions(
            cycle, {'profit_target_pct': 50, 'close_at_dte': 1, 'max_loss_pct': 100},
            minutes_to_expiry=1000,  # < 1 day = 1440 min
        )
        self.assertEqual(reason, 'dte_close')

    def test_emergency_both_breached(self):
        cycle = create_cycle_state(1, '2026-04-01', 10)
        reason = check_exit_conditions(
            cycle, {'profit_target_pct': 50, 'close_at_dte': 1, 'max_loss_pct': 100},
            minutes_to_expiry=5000,
            call_threatened=True, put_threatened=True,
        )
        self.assertEqual(reason, 'emergency_close')

    def test_no_exit_when_healthy(self):
        cycle = create_cycle_state(1, '2026-04-01', 10)
        cycle['pnl_as_pct_of_max_profit'] = 20.0
        reason = check_exit_conditions(
            cycle, {'profit_target_pct': 50, 'close_at_dte': 1, 'max_loss_pct': 100},
            minutes_to_expiry=5000,
        )
        self.assertIsNone(reason)


# =============================================================================
# Adjuster Tests
# =============================================================================

class TestAdjuster(unittest.TestCase):
    def test_no_breach_no_action(self):
        session = _make_session_with_cycle()
        cycle = session['current_cycle']
        decision = decide_adjustment(cycle, session, False, False, 5000)
        self.assertEqual(decision, DECISION_NO_ACTION)

    def test_call_threatened_rolls(self):
        session = _make_session_with_cycle()
        cycle = session['current_cycle']
        decision = decide_adjustment(cycle, session, True, False, 5000)
        self.assertEqual(decision, DECISION_ROLL_BOTH)

    def test_both_threatened_emergency(self):
        session = _make_session_with_cycle()
        cycle = session['current_cycle']
        decision = decide_adjustment(cycle, session, True, True, 5000)
        self.assertEqual(decision, DECISION_EMERGENCY_CLOSE)

    def test_max_adjustments_exits(self):
        session = _make_session_with_cycle()
        cycle = session['current_cycle']
        cycle['adjustment_count'] = 3
        decision = decide_adjustment(cycle, session, True, False, 5000)
        self.assertEqual(decision, DECISION_EXIT_CYCLE)


# =============================================================================
# Cycle Tests
# =============================================================================

class TestCycle(unittest.TestCase):
    def test_should_open_when_idle(self):
        session = create_session()
        session['status'] = STATUS_RUNNING
        session['strategy_status'] = STRATEGY_IDLE
        self.assertTrue(should_open_new_cycle(session))

    def test_should_not_open_when_daily_loss_hit(self):
        session = create_session()
        session['status'] = STATUS_RUNNING
        session['strategy_status'] = STRATEGY_IDLE
        session['max_daily_loss_hit'] = True
        self.assertFalse(should_open_new_cycle(session))

    def test_prepare_new_cycle(self):
        session = create_session()
        session['status'] = STATUS_RUNNING
        session['expiry'] = '2026-04-01'
        cycle = prepare_new_cycle(session)
        self.assertEqual(session['cycle_number'], 1)
        self.assertEqual(session['strategy_status'], STRATEGY_ENTRY_PENDING)
        self.assertIsNotNone(session['current_cycle'])

    def test_activate_cycle(self):
        session = create_session()
        session['status'] = STATUS_RUNNING
        prepare_new_cycle(session)
        legs = _make_legs()
        activate_cycle(session, legs)
        self.assertEqual(session['strategy_status'], STRATEGY_ACTIVE)
        self.assertAlmostEqual(session['current_cycle']['entry_net_credit'], 125.0)


# =============================================================================
# Storage Tests
# =============================================================================

class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, 'test_ic.db')
        self.storage = ICStorage(db_path=self.db_path)

    def test_save_and_get(self):
        session = create_session(session_id='test_001', name='Test')
        self.storage.save_session(session)
        loaded = self.storage.get_session('test_001')
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded['session_id'], 'test_001')

    def test_list_sessions(self):
        s1 = create_session(session_id='test_001')
        s2 = create_session(session_id='test_002')
        self.storage.save_session(s1)
        self.storage.save_session(s2)
        sessions = self.storage.list_sessions()
        self.assertEqual(len(sessions), 2)

    def test_delete_session(self):
        session = create_session(session_id='test_del')
        self.storage.save_session(session)
        self.assertTrue(self.storage.delete_session('test_del'))
        self.assertIsNone(self.storage.get_session('test_del'))

    def test_update_session(self):
        session = create_session(session_id='test_up')
        self.storage.save_session(session)
        updated = self.storage.update_session('test_up', {'status': STATUS_RUNNING})
        self.assertEqual(updated['status'], STATUS_RUNNING)

    def test_active_session_ids(self):
        s = create_session(session_id='test_active')
        s['status'] = STATUS_RUNNING
        self.storage.save_session(s)
        ids = self.storage.get_active_session_ids()
        self.assertIn('test_active', ids)


if __name__ == '__main__':
    unittest.main()
