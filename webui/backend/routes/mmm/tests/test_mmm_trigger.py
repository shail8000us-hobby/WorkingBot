"""
Test MMM Trigger System — §7 Percentage-based trigger evaluation.

Tests:
  - evaluate_triggers: none / CE / PE / BOTH outcomes
  - Percentage vs absolute threshold behaviour
  - min_trigger_move floor (TRIGGER_PCT_FLOOR prevents div-by-zero)
  - update_trigger_snapshots: CE + PE, and frozen position snapshots
  - apply_theta_acceleration: interval tiers, trigger widening
  - compute_adaptive_interval: tier multipliers, floor enforcement
  - _effective_min_trigger_move ephemeral override

P2 Audit: Previously zero test coverage on the most critical decision module.
"""

import sys
import os
import types
import importlib
import importlib.util
import pytest
from copy import deepcopy

# ─── Direct module loader (bypasses routes/__init__.py) ───────────────────────
_MMM_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _setup_mmm_package():
    if 'webui.backend.routes.mmm' in sys.modules:
        return
    for name in ['webui', 'webui.backend', 'webui.backend.routes',
                 'webui.backend.routes.mmm']:
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = []
            pkg.__package__ = name
            sys.modules[name] = pkg
    mmm_pkg = sys.modules['webui.backend.routes.mmm']
    mmm_pkg.__path__ = [_MMM_PKG_DIR]


def _load_mmm_module(name):
    full_name = f'webui.backend.routes.mmm.{name}'
    if full_name in sys.modules:
        return sys.modules[full_name]
    path = os.path.join(_MMM_PKG_DIR, f'{name}.py')
    spec = importlib.util.spec_from_file_location(
        full_name, path,
        submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'webui.backend.routes.mmm'
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_setup_mmm_package()
_constants = _load_mmm_module('mmm_constants')
_trigger = _load_mmm_module('mmm_trigger')

OUTCOME_NONE = _trigger.OUTCOME_NONE
OUTCOME_CE = _trigger.OUTCOME_CE
OUTCOME_PE = _trigger.OUTCOME_PE
OUTCOME_BOTH = _trigger.OUTCOME_BOTH


# ─── Fixture helpers ──────────────────────────────────────────────────────────

def _make_session(
    ce_strike=100000,
    ce_snapshot=200.0,
    pe_strike=95000,
    pe_snapshot=180.0,
    min_trigger_move=10.0,   # 10% threshold
):
    """Minimal session with two active strikes and snapshots."""
    sk_ce = _constants.strike_key(ce_strike)
    sk_pe = _constants.strike_key(pe_strike)
    return {
        'session_id': 'test-trig-001',
        'strategy_status': 'RUNNING',
        'params': {
            'min_trigger_move': min_trigger_move,
            'adjustment_interval': 300,
            'theta_acceleration_window': 120,
        },
        'ce': {
            'active_strike': ce_strike,
            'trigger_snapshot': {sk_ce: ce_snapshot},
            'original_lots': 5,
            'original_premium': ce_snapshot,
            'adjustment_fills': [],
            'frozen_positions': [],
        },
        'pe': {
            'active_strike': pe_strike,
            'trigger_snapshot': {sk_pe: pe_snapshot},
            'original_lots': 5,
            'original_premium': pe_snapshot,
            'adjustment_fills': [],
            'frozen_positions': [],
        },
    }


# ─── evaluate_triggers tests ──────────────────────────────────────────────────

class TestEvaluateTriggers:
    """§7 — evaluate_triggers: outcome is NONE/CE/PE/BOTH."""

    def test_no_trigger_when_premiums_unchanged(self):
        session = _make_session(ce_snapshot=200.0, pe_snapshot=180.0)
        result = _trigger.evaluate_triggers(session, ce_now=200.0, pe_now=180.0)
        assert result['outcome'] == OUTCOME_NONE
        assert result['ce_triggered'] is False
        assert result['pe_triggered'] is False

    def test_ce_triggers_when_premium_rises_above_threshold(self):
        """CE snapshot=200, 10% threshold → 200 * 1.10 = 220 → needs > 220."""
        session = _make_session(ce_snapshot=200.0, min_trigger_move=10.0)
        # 230 > 200 * 1.10 = 220 → triggered
        result = _trigger.evaluate_triggers(session, ce_now=230.0, pe_now=180.0)
        assert result['outcome'] == OUTCOME_CE
        assert result['ce_triggered'] is True
        assert result['pe_triggered'] is False

    def test_pe_triggers_when_premium_rises_above_threshold(self):
        """PE snapshot=180, 10% threshold → needs > 198."""
        session = _make_session(pe_snapshot=180.0, min_trigger_move=10.0)
        result = _trigger.evaluate_triggers(session, ce_now=200.0, pe_now=210.0)
        assert result['outcome'] == OUTCOME_PE
        assert result['pe_triggered'] is True
        assert result['ce_triggered'] is False

    def test_both_trigger_simultaneously(self):
        """Both sides rise above threshold → OUTCOME_BOTH."""
        session = _make_session(
            ce_snapshot=200.0, pe_snapshot=180.0, min_trigger_move=10.0
        )
        result = _trigger.evaluate_triggers(session, ce_now=230.0, pe_now=210.0)
        assert result['outcome'] == OUTCOME_BOTH
        assert result['ce_triggered'] is True
        assert result['pe_triggered'] is True

    def test_just_at_threshold_does_not_trigger(self):
        """Exactly at threshold (not strictly above) should NOT trigger."""
        session = _make_session(ce_snapshot=200.0, min_trigger_move=10.0)
        # 10% of 200 = 20. At exactly 220 → 10% excess, not > 10% → no trigger
        result = _trigger.evaluate_triggers(session, ce_now=220.0, pe_now=180.0)
        assert result['ce_triggered'] is False

    def test_below_threshold_does_not_trigger(self):
        session = _make_session(ce_snapshot=200.0, min_trigger_move=10.0)
        # 5% rise → below 10% threshold
        result = _trigger.evaluate_triggers(session, ce_now=210.0, pe_now=180.0)
        assert result['ce_triggered'] is False

    def test_price_drop_never_triggers(self):
        """Premium falling below snapshot → negative excess → never triggers."""
        session = _make_session(ce_snapshot=200.0)
        result = _trigger.evaluate_triggers(session, ce_now=150.0, pe_now=100.0)
        assert result['outcome'] == OUTCOME_NONE

    def test_zero_snapshot_uses_floor(self):
        """Zero snapshot uses TRIGGER_PCT_FLOOR (1.0) to avoid div-by-zero."""
        session = _make_session(ce_snapshot=0.0, min_trigger_move=10.0)
        result = _trigger.evaluate_triggers(session, ce_now=5.0, pe_now=100.0)
        # 5 / 1.0 * 100 = 500% excess → way above 10% → triggered
        assert result['ce_triggered'] is True

    def test_ephemeral_effective_min_trigger_move_overrides_params(self):
        """_effective_min_trigger_move ephemeral key overrides params.min_trigger_move."""
        session = _make_session(ce_snapshot=200.0, min_trigger_move=10.0)
        # With 10% threshold, 230 (15% rise) triggers CE
        session['_effective_min_trigger_move'] = 20.0  # requires 20% now
        # 230 = only 15% above 200 → should NOT trigger with 20% threshold
        result = _trigger.evaluate_triggers(session, ce_now=230.0, pe_now=180.0)
        assert result['ce_triggered'] is False

    def test_outcome_excess_values_calculated_correctly(self):
        """Check ce_excess and ce_excess_pct values are accurate."""
        session = _make_session(ce_snapshot=200.0, min_trigger_move=5.0)
        result = _trigger.evaluate_triggers(session, ce_now=230.0, pe_now=180.0)
        assert result['ce_excess'] == pytest.approx(30.0, abs=0.01)
        assert result['ce_excess_pct'] == pytest.approx(15.0, abs=0.01)


# ─── update_trigger_snapshots tests ───────────────────────────────────────────

class TestUpdateTriggerSnapshots:
    """§6.2 — Both sides update after every adjustment."""

    def test_updates_both_active_strikes(self):
        session = _make_session(
            ce_strike=100000, ce_snapshot=200.0,
            pe_strike=95000, pe_snapshot=180.0,
        )
        _trigger.update_trigger_snapshots(session, ce_now=230.0, pe_now=210.0)

        sk_ce = _constants.strike_key(100000)
        sk_pe = _constants.strike_key(95000)
        assert session['ce']['trigger_snapshot'][sk_ce] == 230.0
        assert session['pe']['trigger_snapshot'][sk_pe] == 210.0


    def test_returns_session(self):
        session = _make_session()
        result = _trigger.update_trigger_snapshots(session, 220.0, 200.0)
        assert result is session  # Returns the same dict

    def test_frozen_positions_snapshot_updated_when_fetch_fn_provided(self):
        """Frozen position at old strike should get its snapshot updated."""
        session = _make_session()
        old_frozen_strike = 98000
        session['pe']['frozen_positions'] = [{
            'strike': old_frozen_strike,
            'lots': 3,
            'entry_premium': 120.0,
        }]

        def fetch_fn(strike, option_type):
            if strike == old_frozen_strike:
                return 95.0
            return 100.0

        _trigger.update_trigger_snapshots(session, 220.0, 190.0, fetch_premium_fn=fetch_fn)
        sk_frozen = _constants.strike_key(old_frozen_strike)
        assert session['pe']['trigger_snapshot'].get(sk_frozen) == 95.0

    def test_creates_trigger_snapshot_if_missing(self):
        """If trigger_snapshot dict is missing, it's created."""
        session = _make_session()
        del session['ce']['trigger_snapshot']
        _trigger.update_trigger_snapshots(session, 220.0, 190.0)
        assert 'trigger_snapshot' in session['ce']


# ─── apply_theta_acceleration tests ───────────────────────────────────────────

class TestApplyThetaAcceleration:
    """§14.7 — Near-expiry interval and trigger widening."""

    def test_no_acceleration_when_far_from_expiry(self):
        session = _make_session()
        session['params']['theta_acceleration_window'] = 120  # 2 hours
        result = _trigger.apply_theta_acceleration(session, minutes_to_expiry=200)
        assert result['accelerated'] is False

    def test_no_acceleration_at_zero_minutes(self):
        session = _make_session()
        result = _trigger.apply_theta_acceleration(session, minutes_to_expiry=0)
        assert result['accelerated'] is False

    def test_acceleration_within_window(self):
        session = _make_session()
        session['params']['theta_acceleration_window'] = 120
        result = _trigger.apply_theta_acceleration(session, minutes_to_expiry=60)
        assert result['accelerated'] is True

    def test_interval_tiers_5min(self):
        session = _make_session()
        result = _trigger.apply_theta_acceleration(session, minutes_to_expiry=3)
        assert result['effective_interval'] == 5

    def test_interval_tiers_15min(self):
        session = _make_session()
        result = _trigger.apply_theta_acceleration(session, minutes_to_expiry=10)
        assert result['effective_interval'] == 10

    def test_interval_tiers_30min(self):
        session = _make_session()
        result = _trigger.apply_theta_acceleration(session, minutes_to_expiry=20)
        assert result['effective_interval'] == 20

    def test_trigger_move_doubled_within_window(self):
        """Trigger widening: base 10% → 20% within theta window."""
        session = _make_session(min_trigger_move=10.0)
        session['params']['theta_acceleration_window'] = 120
        result = _trigger.apply_theta_acceleration(session, minutes_to_expiry=60)
        assert result['effective_min_trigger_move'] == pytest.approx(20.0, abs=0.1)

    def test_trigger_move_capped_at_80_pct(self):
        """Robust v2 Fix #21: cap prevents unfireable triggers."""
        session = _make_session(min_trigger_move=50.0)  # 50 * 2 = 100 → capped at 80
        session['params']['theta_acceleration_window'] = 120
        result = _trigger.apply_theta_acceleration(session, minutes_to_expiry=10)
        assert result['effective_min_trigger_move'] == 80.0


# ─── compute_adaptive_interval tests ──────────────────────────────────────────

class TestComputeAdaptiveInterval:
    """Adaptive interval tiers compress heartbeat as expiry nears."""

    def test_disabled_returns_base(self):
        result = _trigger.compute_adaptive_interval(300, hours_to_expiry=10, enabled=False)
        assert result['effective_interval'] == 300
        assert result['adaptive'] is False

    def test_far_expiry_full_interval(self):
        """More than 30h away → full base interval."""
        result = _trigger.compute_adaptive_interval(300, hours_to_expiry=48)
        assert result['effective_interval'] == 300
        assert result['multiplier'] == 1.0

    def test_mid_range_halved(self):
        """10-20h → 0.5 multiplier → 150s for 300s base (but floor at 30s if base is small)."""
        result = _trigger.compute_adaptive_interval(300, hours_to_expiry=15)
        assert result['effective_interval'] == int(300 * 0.5)
        assert result['adaptive'] is True

    def test_interval_floor_enforced(self):
        """Even with small base, interval never drops below ADAPTIVE_INTERVAL_FLOOR (30s)."""
        result = _trigger.compute_adaptive_interval(60, hours_to_expiry=15)
        # 60 * 0.5 = 30 → exactly the floor
        assert result['effective_interval'] >= _trigger.ADAPTIVE_INTERVAL_FLOOR

    def test_fixed_floor_zone(self):
        """30m-1h → fixed floor (30s), regardless of base_interval."""
        result = _trigger.compute_adaptive_interval(600, hours_to_expiry=0.75)
        assert result['effective_interval'] == _trigger.ADAPTIVE_INTERVAL_FLOOR

    def test_zero_hours_not_adaptive(self):
        """0 hours → handed to theta_acceleration, not adaptive."""
        result = _trigger.compute_adaptive_interval(300, hours_to_expiry=0)
        assert result['adaptive'] is False
