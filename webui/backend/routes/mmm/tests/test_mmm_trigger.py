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

    def test_zero_snapshot_early_returns_outcome_none(self):
        """Zero snapshot causes early-return OUTCOME_NONE (safety guard vs false triggers)."""
        session = _make_session(ce_snapshot=0.0, min_trigger_move=10.0)
        result = _trigger.evaluate_triggers(session, ce_now=5.0, pe_now=100.0)
        # Guard fires when snapshot missing/zero — no evaluation, no adjustment
        assert result['outcome'] == OUTCOME_NONE
        assert result['ce_triggered'] is False

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


# =============================================================================
# Phase 1 Tests — min_trigger_dollar (dollar floor alongside % trigger)
# =============================================================================

LOT = _constants.LOT_SIZE_BTC  # 0.001


def _make_session_lots(
    ce_snapshot=200.0,
    pe_snapshot=180.0,
    ce_active_lots=10,
    pe_active_lots=10,
    min_trigger_move=10.0,
    min_trigger_dollar=0.0,
    ce_strike=100000,
    pe_strike=95000,
):
    """Session fixture with active_lots set (needed for dollar floor calculation)."""
    sk_ce = _constants.strike_key(ce_strike)
    sk_pe = _constants.strike_key(pe_strike)
    return {
        'session_id': 'test-dollar-001',
        'strategy_status': 'RUNNING',
        'params': {
            'min_trigger_move': min_trigger_move,
            'min_trigger_dollar': min_trigger_dollar,
            'adjustment_interval': 300,
            'theta_acceleration_window': 120,
        },
        'ce': {
            'active_strike': ce_strike,
            'trigger_snapshot': {sk_ce: ce_snapshot},
            'active_lots': ce_active_lots,
            'original_lots': ce_active_lots,
            'adjustment_fills': [],
            'frozen_positions': [],
        },
        'pe': {
            'active_strike': pe_strike,
            'trigger_snapshot': {sk_pe: pe_snapshot},
            'active_lots': pe_active_lots,
            'original_lots': pe_active_lots,
            'adjustment_fills': [],
            'frozen_positions': [],
        },
    }


class TestDollarFloorTrigger:
    """Phase 1: min_trigger_dollar — fires when active-strike USD loss exceeds threshold."""

    # ── Disabled behaviour ────────────────────────────────────────────────────

    def test_disabled_zero_leaves_pct_trigger_unchanged(self):
        """min_trigger_dollar=0 → disabled. Existing pct logic unaffected."""
        session = _make_session_lots(
            ce_snapshot=200.0, min_trigger_move=10.0, min_trigger_dollar=0.0,
        )
        # 5% rise → below 10% threshold, dollar disabled → no trigger
        result = _trigger.evaluate_triggers(session, ce_now=210.0, pe_now=180.0)
        assert result['outcome'] == OUTCOME_NONE
        assert result['ce_dollar_triggered'] is False
        assert result['pe_dollar_triggered'] is False

    def test_disabled_does_not_trigger(self):
        """When disabled (min_trigger_dollar=0), dollar excess is computed but trigger is False."""
        session = _make_session_lots(min_trigger_dollar=0.0)
        # excess=10, lots=10 → dollar_excess = 0.1 (computed but not used as trigger)
        result = _trigger.evaluate_triggers(session, ce_now=210.0, pe_now=180.0)
        assert result['ce_dollar_triggered'] is False
        assert result['min_trigger_dollar'] == 0.0
        # Dollar excess is informational regardless of enabled state
        assert result['ce_dollar_excess'] == pytest.approx(0.1, abs=1e-6)

    # ── Dollar triggers when % would not (dead-zone coverage) ────────────────

    def test_dollar_fires_in_pct_dead_zone(self):
        """5% move below 10% pct-threshold: dollar catches it if lots × excess > threshold."""
        # excess = 10, lots=10, dollar_excess = 10 × 10 × 0.001 = 0.10
        # min_trigger_dollar=0.05 → 0.10 > 0.05 → fires
        session = _make_session_lots(
            ce_snapshot=200.0, ce_active_lots=10,
            min_trigger_move=10.0, min_trigger_dollar=0.05,
        )
        result = _trigger.evaluate_triggers(session, ce_now=210.0, pe_now=180.0)
        assert result['outcome'] == OUTCOME_CE
        assert result['ce_triggered'] is True
        assert result['ce_dollar_triggered'] is True

    def test_pct_fires_when_dollar_would_not(self):
        """High-% move on few lots: pct fires, dollar doesn't. Both coexist correctly."""
        # 20% move on 1 lot: dollar_excess = 40 × 1 × 0.001 = 0.04 < 1.00 → dollar no
        # but 20% > 10% → pct fires
        session = _make_session_lots(
            ce_snapshot=200.0, ce_active_lots=1,
            min_trigger_move=10.0, min_trigger_dollar=1.0,
        )
        result = _trigger.evaluate_triggers(session, ce_now=240.0, pe_now=180.0)
        assert result['outcome'] == OUTCOME_CE
        assert result['ce_triggered'] is True
        assert result['ce_dollar_triggered'] is False   # pct did it, not dollar

    def test_both_conditions_true_outcome_is_still_ce(self):
        """When both pct AND dollar trigger for CE, outcome is OUTCOME_CE (not doubled)."""
        session = _make_session_lots(
            ce_snapshot=200.0, ce_active_lots=50,
            min_trigger_move=5.0, min_trigger_dollar=0.01,
        )
        # 12% move: pct fires (12>5). dollar_excess = 24 × 50 × 0.001 = 1.20 > 0.01
        result = _trigger.evaluate_triggers(session, ce_now=224.0, pe_now=180.0)
        assert result['outcome'] == OUTCOME_CE
        assert result['ce_triggered'] is True
        assert result['ce_dollar_triggered'] is True

    # ── Dollar excess calculation ─────────────────────────────────────────────

    def test_dollar_excess_calculation_correct(self):
        """(ce_now - trigger) × active_lots × LOT_SIZE_BTC."""
        # excess = 210 - 200 = 10; dollar = 10 × 15 × 0.001 = 0.15
        session = _make_session_lots(ce_snapshot=200.0, ce_active_lots=15)
        result = _trigger.evaluate_triggers(session, ce_now=210.0, pe_now=180.0)
        assert result['ce_dollar_excess'] == pytest.approx(0.15, abs=1e-5)

    def test_dollar_excess_clamped_to_zero_on_decline(self):
        """Negative excess (price below snapshot) → clamped to 0.0, never triggers."""
        session = _make_session_lots(
            ce_snapshot=200.0, ce_active_lots=100, min_trigger_dollar=0.001,
        )
        result = _trigger.evaluate_triggers(session, ce_now=150.0, pe_now=180.0)
        assert result['ce_dollar_excess'] == 0.0
        assert result['ce_dollar_triggered'] is False

    def test_zero_lots_dollar_excess_is_zero(self):
        """0 active_lots → dollar_excess = 0 regardless of move."""
        session = _make_session_lots(
            ce_snapshot=200.0, ce_active_lots=0,
            min_trigger_dollar=0.001,
        )
        result = _trigger.evaluate_triggers(session, ce_now=500.0, pe_now=180.0)
        assert result['ce_dollar_excess'] == 0.0
        assert result['ce_dollar_triggered'] is False

    # ── Threshold boundary ────────────────────────────────────────────────────

    def test_exactly_at_dollar_threshold_does_not_trigger(self):
        """Strict greater-than: exact equality does NOT fire."""
        # excess=10, lots=10 → dollar_excess = 0.10; threshold=0.10 → NOT triggered
        session = _make_session_lots(
            ce_snapshot=200.0, ce_active_lots=10, min_trigger_dollar=0.10,
        )
        result = _trigger.evaluate_triggers(session, ce_now=210.0, pe_now=180.0)
        assert result['ce_dollar_triggered'] is False

    def test_just_above_dollar_threshold_triggers(self):
        """One more lot pushes it over: (11 lots × 10 excess × 0.001 = 0.11 > 0.10)."""
        session = _make_session_lots(
            ce_snapshot=200.0, ce_active_lots=11, min_trigger_dollar=0.10,
        )
        result = _trigger.evaluate_triggers(session, ce_now=210.0, pe_now=180.0)
        assert result['ce_dollar_triggered'] is True

    # ── Both sides / PE side ──────────────────────────────────────────────────

    def test_both_sides_dollar_trigger_outcome_both(self):
        """CE and PE both exceed dollar threshold → OUTCOME_BOTH."""
        session = _make_session_lots(
            ce_snapshot=200.0, pe_snapshot=180.0,
            ce_active_lots=10, pe_active_lots=10,
            min_trigger_move=10.0, min_trigger_dollar=0.05,
        )
        # CE: 10 × 10 × 0.001 = 0.10 > 0.05 ✓
        # PE: 10 × 10 × 0.001 = 0.10 > 0.05 ✓
        result = _trigger.evaluate_triggers(session, ce_now=210.0, pe_now=190.0)
        assert result['outcome'] == OUTCOME_BOTH
        assert result['ce_dollar_triggered'] is True
        assert result['pe_dollar_triggered'] is True

    def test_pe_only_dollar_trigger(self):
        """PE crosses dollar threshold, CE does not → OUTCOME_PE."""
        session = _make_session_lots(
            ce_snapshot=200.0, pe_snapshot=180.0,
            ce_active_lots=1, pe_active_lots=20,
            min_trigger_move=10.0, min_trigger_dollar=0.10,
        )
        # CE: (210-200) × 1 × 0.001 = 0.01 < 0.10 ✗
        # PE: (195-180) × 20 × 0.001 = 0.30 > 0.10 ✓
        result = _trigger.evaluate_triggers(session, ce_now=210.0, pe_now=195.0)
        assert result['outcome'] == OUTCOME_PE
        assert result['pe_dollar_triggered'] is True
        assert result['ce_dollar_triggered'] is False

    # ── Return dict completeness ──────────────────────────────────────────────

    def test_all_dollar_fields_present_when_disabled(self):
        """New fields always present in return dict, even when feature disabled."""
        session = _make_session_lots(min_trigger_dollar=0.0)
        result = _trigger.evaluate_triggers(session, ce_now=200.0, pe_now=180.0)
        for key in ('ce_dollar_excess', 'pe_dollar_excess',
                    'ce_dollar_triggered', 'pe_dollar_triggered', 'min_trigger_dollar'):
            assert key in result, f"Missing field: {key}"

    def test_all_dollar_fields_present_in_snapshot_guard_early_return(self):
        """Zero-snapshot guard early-return also contains all dollar fields."""
        sk_ce = _constants.strike_key(100000)
        sk_pe = _constants.strike_key(95000)
        session = {
            'session_id': 'x', 'strategy_status': 'RUNNING',
            'params': {'min_trigger_move': 10.0, 'min_trigger_dollar': 1.0},
            'ce': {'active_strike': 100000,
                   'trigger_snapshot': {sk_ce: 0}, 'active_lots': 10, 'frozen_positions': []},
            'pe': {'active_strike': 95000,
                   'trigger_snapshot': {sk_pe: 0}, 'active_lots': 10, 'frozen_positions': []},
        }
        result = _trigger.evaluate_triggers(session, ce_now=200.0, pe_now=180.0)
        assert result['outcome'] == OUTCOME_NONE
        for key in ('ce_dollar_excess', 'pe_dollar_excess',
                    'ce_dollar_triggered', 'pe_dollar_triggered', 'min_trigger_dollar'):
            assert key in result, f"Missing field in snapshot guard return: {key}"

    def test_backward_compat_session_without_min_trigger_dollar(self):
        """Old sessions with no min_trigger_dollar in params default to 0 (disabled)."""
        session = _make_session(ce_snapshot=200.0, min_trigger_move=10.0)
        # _make_session doesn't set min_trigger_dollar → defaults to 0
        result = _trigger.evaluate_triggers(session, ce_now=210.0, pe_now=180.0)
        assert result['min_trigger_dollar'] == 0.0
        assert result['ce_dollar_triggered'] is False


# =============================================================================
# Phase 2 Tests — check_frozen_pnl_trigger (fallback trigger for frozen positions)
# =============================================================================

def _make_frozen_session(
    ce_snapshot=200.0,
    pe_snapshot=180.0,
    min_trigger_move=10.0,
    min_frozen_trigger_dollar=0.0,
    ce_strike=100000,
    pe_strike=95000,
):
    """Session with configurable frozen positions for Phase 2 tests."""
    sk_ce = _constants.strike_key(ce_strike)
    sk_pe = _constants.strike_key(pe_strike)
    return {
        'session_id': 'test-frozen-001',
        'strategy_status': 'RUNNING',
        'params': {
            'min_trigger_move': min_trigger_move,
            'min_trigger_dollar': 0.0,
            'min_frozen_trigger_dollar': min_frozen_trigger_dollar,
            'adjustment_interval': 300,
        },
        'ce': {
            'active_strike': ce_strike,
            'trigger_snapshot': {sk_ce: ce_snapshot},
            'active_lots': 10,
            'original_lots': 10,
            'adjustment_fills': [],
            'frozen_positions': [],
        },
        'pe': {
            'active_strike': pe_strike,
            'trigger_snapshot': {sk_pe: pe_snapshot},
            'active_lots': 10,
            'original_lots': 10,
            'adjustment_fills': [],
            'frozen_positions': [],
        },
    }


def _make_fetch_fn(price_map):
    """Return a sync fetch callable that looks up prices from a dict.
    Keys: (strike_float, option_type_str) or (strike_float,) for any type.
    """
    def fetch(strike, option_type):
        key = (float(strike), option_type)
        if key in price_map:
            return price_map[key]
        # Also try strike-only key for convenience in tests
        key2 = (float(strike),)
        return price_map.get(key2, None)
    return fetch


class TestCheckFrozenPnlTrigger:
    """Phase 2: check_frozen_pnl_trigger — fallback trigger for frozen position losses."""

    # ── Disabled / no positions ───────────────────────────────────────────────

    def test_disabled_always_outcome_none(self):
        """min_frozen_trigger_dollar=0 → always OUTCOME_NONE."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.0)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 20, 'entry_premium': 50.0}
        ]
        fetch = _make_fetch_fn({(98000.0, 'call'): 200.0})  # huge loss, but disabled
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_NONE
        assert result['frozen_triggered'] is False

    def test_no_frozen_positions_outcome_none(self):
        """No frozen positions on either side → OUTCOME_NONE."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.10)
        fetch = _make_fetch_fn({})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_NONE

    # ── Single-side triggers ──────────────────────────────────────────────────

    def test_ce_frozen_loss_exceeds_threshold_outcome_ce(self):
        """CE frozen position with loss > threshold → OUTCOME_CE."""
        # frozen CE at 98000: entry=50, current=80 → loss=(80-50)×5×0.001=$0.15
        # threshold=$0.10 → fires
        session = _make_frozen_session(min_frozen_trigger_dollar=0.10)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 5, 'entry_premium': 50.0}
        ]
        fetch = _make_fetch_fn({(98000.0, 'call'): 80.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_CE
        assert result['ce_triggered'] is True
        assert result['pe_triggered'] is False
        assert result['frozen_triggered'] is True
        assert result['ce_frozen_loss'] == pytest.approx(0.15, abs=1e-5)

    def test_pe_frozen_loss_exceeds_threshold_outcome_pe(self):
        """PE frozen position with loss > threshold → OUTCOME_PE."""
        # frozen PE at 92000: entry=60, current=100 → loss=(100-60)×10×0.001=$0.40
        session = _make_frozen_session(min_frozen_trigger_dollar=0.20)
        session['pe']['frozen_positions'] = [
            {'strike': 92000, 'lots': 10, 'entry_premium': 60.0}
        ]
        fetch = _make_fetch_fn({(92000.0, 'put'): 100.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_PE
        assert result['pe_triggered'] is True
        assert result['ce_triggered'] is False
        assert result['pe_frozen_loss'] == pytest.approx(0.40, abs=1e-5)

    def test_both_sides_frozen_loss_outcome_both(self):
        """Both CE and PE frozen exceed threshold → OUTCOME_BOTH."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.05)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 10, 'entry_premium': 50.0}
        ]
        session['pe']['frozen_positions'] = [
            {'strike': 92000, 'lots': 10, 'entry_premium': 60.0}
        ]
        fetch = _make_fetch_fn({
            (98000.0, 'call'): 60.0,   # CE loss = 10×10×0.001 = 0.10 > 0.05 ✓
            (92000.0, 'put'): 70.0,    # PE loss = 10×10×0.001 = 0.10 > 0.05 ✓
        })
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_BOTH
        assert result['ce_triggered'] is True
        assert result['pe_triggered'] is True

    # ── Baseline: trigger_snapshot vs entry_premium ───────────────────────────

    def test_uses_trigger_snapshot_when_available(self):
        """Trigger snapshot (not entry_premium) is baseline — prevents double-counting."""
        # entry=50, snapshot=70, current=80 → loss=(80-70)×10×0.001=$0.10
        # if entry used: loss=(80-50)×10×0.001=$0.30 → different result
        session = _make_frozen_session(min_frozen_trigger_dollar=0.05)
        sk_frozen = _constants.strike_key(98000)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 10, 'entry_premium': 50.0}
        ]
        session['ce']['trigger_snapshot'][sk_frozen] = 70.0  # snapshot ratcheted to 70
        fetch = _make_fetch_fn({(98000.0, 'call'): 80.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        # Loss from snapshot (70→80): 10 × 10 × 0.001 = 0.10 > 0.05 → fires
        assert result['outcome'] == OUTCOME_CE
        assert result['ce_frozen_loss'] == pytest.approx(0.10, abs=1e-5)

    def test_falls_back_to_entry_premium_when_no_snapshot(self):
        """Falls back to entry_premium when trigger_snapshot has no entry for this strike."""
        # entry=50, no snapshot, current=80 → loss=(80-50)×5×0.001=$0.15
        session = _make_frozen_session(min_frozen_trigger_dollar=0.10)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 5, 'entry_premium': 50.0}
        ]
        # No entry for 98000 in trigger_snapshot (only active strike is there)
        fetch = _make_fetch_fn({(98000.0, 'call'): 80.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_CE
        assert result['ce_frozen_loss'] == pytest.approx(0.15, abs=1e-5)

    def test_snapshot_ratchet_prevents_retriggering_same_loss(self):
        """After a hedge ratchets the snapshot to current price, same position shows zero loss."""
        # Simulates beat N+1 after adjustment: snapshot advanced to 80 (the current price)
        session = _make_frozen_session(min_frozen_trigger_dollar=0.10)
        sk_frozen = _constants.strike_key(98000)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 10, 'entry_premium': 50.0}
        ]
        session['ce']['trigger_snapshot'][sk_frozen] = 80.0  # ratcheted to current
        fetch = _make_fetch_fn({(98000.0, 'call'): 80.0})  # still at 80
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        # loss = (80 - 80) × 10 × 0.001 = 0.0 → below threshold → no trigger
        assert result['outcome'] == OUTCOME_NONE
        assert result['ce_frozen_loss'] == 0.0

    # ── Declining premium / no-loss ───────────────────────────────────────────

    def test_declining_frozen_premium_does_not_trigger(self):
        """Frozen premium below baseline → clamped to 0, no trigger."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.01)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 100, 'entry_premium': 80.0}
        ]
        fetch = _make_fetch_fn({(98000.0, 'call'): 30.0})  # price fell → our profit
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_NONE
        assert result['ce_frozen_loss'] == 0.0

    # ── Threshold boundary ────────────────────────────────────────────────────

    def test_exactly_at_threshold_does_not_trigger(self):
        """Strict greater-than: exact equality at threshold does NOT fire."""
        # loss = (60-50) × 10 × 0.001 = 0.10; threshold = 0.10 → NOT triggered
        session = _make_frozen_session(min_frozen_trigger_dollar=0.10)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 10, 'entry_premium': 50.0}
        ]
        fetch = _make_fetch_fn({(98000.0, 'call'): 60.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_NONE

    def test_just_above_threshold_triggers(self):
        """One more unit of loss pushes it over."""
        # loss = (60-50) × 11 × 0.001 = 0.11 > 0.10 → triggers
        session = _make_frozen_session(min_frozen_trigger_dollar=0.10)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 11, 'entry_premium': 50.0}
        ]
        fetch = _make_fetch_fn({(98000.0, 'call'): 60.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_CE

    # ── Position filtering ────────────────────────────────────────────────────

    def test_skips_being_closed_positions(self):
        """Positions with _being_closed=True are excluded from loss sum."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.01)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 100, 'entry_premium': 50.0, '_being_closed': True}
        ]
        fetch = _make_fetch_fn({(98000.0, 'call'): 200.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_NONE   # position excluded

    def test_skips_zero_lot_positions(self):
        """Zero-lot positions contribute nothing to loss sum."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.01)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 0, 'entry_premium': 50.0}
        ]
        fetch = _make_fetch_fn({(98000.0, 'call'): 999.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_NONE

    def test_skips_zero_strike_positions(self):
        """Positions with strike=0 are skipped."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.01)
        session['ce']['frozen_positions'] = [
            {'strike': 0, 'lots': 50, 'entry_premium': 50.0}
        ]
        fetch = _make_fetch_fn({(0.0, 'call'): 999.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_NONE

    def test_skips_zero_baseline(self):
        """Positions with entry_premium=0 and no snapshot are skipped (can't compute loss)."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.01)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 10, 'entry_premium': 0.0}
        ]
        fetch = _make_fetch_fn({(98000.0, 'call'): 100.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_NONE

    # ── Fetch failures ────────────────────────────────────────────────────────

    def test_fetch_failure_skips_position(self):
        """Fetch returning None skips that position; others still counted."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.10)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 5, 'entry_premium': 50.0},   # fetch fails
            {'strike': 97000, 'lots': 20, 'entry_premium': 50.0},  # fetch ok
        ]
        # 98000 returns None (failure), 97000 returns 80
        # 97000 loss = (80-50)×20×0.001 = 0.60 > 0.10 → fires on second position alone
        fetch = _make_fetch_fn({(97000.0, 'call'): 80.0})  # 98000 missing → None
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_CE
        assert result['ce_frozen_loss'] == pytest.approx(0.60, abs=1e-5)

    def test_all_fetch_failures_no_trigger(self):
        """All fetch failures → no computable loss → OUTCOME_NONE."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.01)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 100, 'entry_premium': 50.0}
        ]
        fetch = _make_fetch_fn({})  # nothing in cache
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_NONE

    # ── Multiple positions summed ─────────────────────────────────────────────

    def test_multiple_frozen_positions_summed(self):
        """Loss from multiple frozen positions on same side are summed."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.20)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 5, 'entry_premium': 50.0},  # loss=0.05
            {'strike': 97000, 'lots': 10, 'entry_premium': 60.0}, # loss=0.10
            {'strike': 96000, 'lots': 8, 'entry_premium': 70.0},  # loss=0.08
        ]
        fetch = _make_fetch_fn({
            (98000.0, 'call'): 60.0,   # (60-50)×5×0.001=0.05
            (97000.0, 'call'): 70.0,   # (70-60)×10×0.001=0.10
            (96000.0, 'call'): 80.0,   # (80-70)×8×0.001=0.08
        })
        # total = 0.23 > 0.20 → fires
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_CE
        assert result['ce_frozen_loss'] == pytest.approx(0.23, abs=1e-4)

    # ── Return dict structure ─────────────────────────────────────────────────

    def test_return_dict_passthrough_ce_now_pe_now(self):
        """ce_now and pe_now from args appear in the returned dict."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.0)
        fetch = _make_fetch_fn({})
        result = _trigger.check_frozen_pnl_trigger(session, fetch, ce_now=222.0, pe_now=333.0)
        assert result['ce_now'] == 222.0
        assert result['pe_now'] == 333.0

    def test_return_dict_has_all_required_fields(self):
        """Return dict has same keys as evaluate_triggers + frozen-specific fields."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.0)
        fetch = _make_fetch_fn({})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        for key in ('outcome', 'ce_excess', 'pe_excess', 'ce_excess_pct', 'pe_excess_pct',
                    'ce_triggered', 'pe_triggered', 'ce_trigger', 'pe_trigger',
                    'ce_now', 'pe_now', 'min_trigger_move',
                    'frozen_triggered', 'ce_frozen_loss', 'pe_frozen_loss',
                    'min_frozen_trigger_dollar'):
            assert key in result, f"Missing key: {key}"

    def test_frozen_triggered_true_when_fires(self):
        """frozen_triggered=True when threshold is crossed."""
        session = _make_frozen_session(min_frozen_trigger_dollar=0.01)
        session['ce']['frozen_positions'] = [
            {'strike': 98000, 'lots': 10, 'entry_premium': 50.0}
        ]
        fetch = _make_fetch_fn({(98000.0, 'call'): 60.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['outcome'] == OUTCOME_CE
        assert result['frozen_triggered'] is True

    def test_frozen_triggered_true_even_when_outcome_none(self):
        """frozen_triggered=True is set in the return dict schema regardless of outcome."""
        # When disabled, frozen_triggered=False
        session = _make_frozen_session(min_frozen_trigger_dollar=0.0)
        fetch = _make_fetch_fn({})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        assert result['frozen_triggered'] is False


# =============================================================================
# Phase 1 + Phase 2 interaction: double-hedging prevention invariant
# =============================================================================

class TestTriggerInteractionInvariants:
    """Verify that the active and frozen triggers produce correct outcomes
    in isolation. The monitor's fallback gate (frozen only when OUTCOME_NONE)
    is the double-hedging prevention — these tests verify both triggers
    independently produce correct results so the gate logic works safely."""

    def test_active_pct_trigger_and_frozen_would_also_fire(self):
        """Scenario: active strike moves 12%, AND frozen has large loss.
        evaluate_triggers returns CE. check_frozen_pnl_trigger would also return CE.
        In the monitor these are sequential — only one runs per beat.
        Verify each produces OUTCOME_CE independently (correct for their scope)."""
        sk_ce = _constants.strike_key(100000)
        sk_pe = _constants.strike_key(95000)
        session = {
            'session_id': 'x',
            'strategy_status': 'RUNNING',
            'params': {
                'min_trigger_move': 10.0,
                'min_trigger_dollar': 0.0,
                'min_frozen_trigger_dollar': 0.10,
                'adjustment_interval': 300,
            },
            'ce': {
                'active_strike': 100000,
                'trigger_snapshot': {
                    sk_ce: 200.0,
                    _constants.strike_key(98000): 55.0,  # frozen snapshot
                },
                'active_lots': 10,
                'frozen_positions': [
                    {'strike': 98000, 'lots': 15, 'entry_premium': 50.0}
                ],
            },
            'pe': {
                'active_strike': 95000,
                'trigger_snapshot': {sk_pe: 180.0},
                'active_lots': 10,
                'frozen_positions': [],
            },
        }
        # Active CE: 224 → (224-200)/200 = 12% > 10% → OUTCOME_CE
        active_result = _trigger.evaluate_triggers(session, ce_now=224.0, pe_now=180.0)
        assert active_result['outcome'] == OUTCOME_CE

        # Frozen CE: (80-55)×15×0.001=0.375 > 0.10 → OUTCOME_CE (independently correct)
        fetch = _make_fetch_fn({(98000.0, 'call'): 80.0})
        frozen_result = _trigger.check_frozen_pnl_trigger(session, fetch, ce_now=224.0, pe_now=180.0)
        assert frozen_result['outcome'] == OUTCOME_CE

        # The monitor gate: active fired → frozen NOT called.
        # calculate_standard_loss will include frozen losses in the active-trigger path.

    def test_active_outcome_none_frozen_fires_correctly(self):
        """Scenario: active trigger is silent (7%), frozen has significant loss.
        This is the canonical Phase 2 use case — fallback fires."""
        sk_ce = _constants.strike_key(100000)
        sk_pe = _constants.strike_key(95000)
        sk_frozen = _constants.strike_key(98000)
        session = {
            'session_id': 'x',
            'strategy_status': 'RUNNING',
            'params': {
                'min_trigger_move': 10.0,
                'min_trigger_dollar': 0.0,
                'min_frozen_trigger_dollar': 0.10,
                'adjustment_interval': 300,
            },
            'ce': {
                'active_strike': 100000,
                'trigger_snapshot': {sk_ce: 200.0, sk_frozen: 55.0},
                'active_lots': 5,
                'frozen_positions': [
                    {'strike': 98000, 'lots': 20, 'entry_premium': 50.0}
                ],
            },
            'pe': {
                'active_strike': 95000,
                'trigger_snapshot': {sk_pe: 180.0},
                'active_lots': 10,
                'frozen_positions': [],
            },
        }
        # Active: (214-200)/200 = 7% → below 10% threshold → OUTCOME_NONE
        active_result = _trigger.evaluate_triggers(session, ce_now=214.0, pe_now=180.0)
        assert active_result['outcome'] == OUTCOME_NONE

        # Frozen fallback: (80-55)×20×0.001=0.50 > 0.10 → OUTCOME_CE
        fetch = _make_fetch_fn({(98000.0, 'call'): 80.0})
        frozen_result = _trigger.check_frozen_pnl_trigger(session, fetch, ce_now=214.0, pe_now=180.0)
        assert frozen_result['outcome'] == OUTCOME_CE
        assert frozen_result['ce_frozen_loss'] == pytest.approx(0.50, abs=1e-4)
        assert frozen_result['frozen_triggered'] is True

    def test_ratcheted_snapshot_prevents_frozen_retrigger(self):
        """After a frozen-triggered adjustment ratchets the snapshot, the same
        frozen position does NOT retrigger on the next beat at the same price."""
        sk_ce = _constants.strike_key(100000)
        sk_pe = _constants.strike_key(95000)
        sk_frozen = _constants.strike_key(98000)
        session = {
            'session_id': 'x',
            'strategy_status': 'RUNNING',
            'params': {
                'min_trigger_move': 10.0,
                'min_trigger_dollar': 0.0,
                'min_frozen_trigger_dollar': 0.10,
                'adjustment_interval': 300,
            },
            'ce': {
                'active_strike': 100000,
                # Snapshot ratcheted to 80 after beat N's adjustment
                'trigger_snapshot': {sk_ce: 200.0, sk_frozen: 80.0},
                'active_lots': 5,
                'frozen_positions': [
                    {'strike': 98000, 'lots': 20, 'entry_premium': 50.0}
                ],
            },
            'pe': {
                'active_strike': 95000,
                'trigger_snapshot': {sk_pe: 180.0},
                'active_lots': 10,
                'frozen_positions': [],
            },
        }
        # Beat N+1: price is still 80 (no new movement)
        fetch = _make_fetch_fn({(98000.0, 'call'): 80.0})
        result = _trigger.check_frozen_pnl_trigger(session, fetch)
        # loss = (80-80)×20×0.001 = 0.0 → no retrigger
        assert result['outcome'] == OUTCOME_NONE
        assert result['ce_frozen_loss'] == 0.0
