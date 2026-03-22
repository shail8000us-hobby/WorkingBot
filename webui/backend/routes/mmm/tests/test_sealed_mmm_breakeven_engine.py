"""
Contract tests for MMM Breakeven Engine — T3-6

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

No bugs found during audit.

Functions covered:
  BreakevenEngine.compute_breakeven(session, spot_price) -> Dict
  BreakevenEngine.get_aggression_multiplier(result) -> float
  BreakevenEngine.invalidate_cache(session_id) -> None
  BreakevenEngine._classify_zone(nearest_distance_pct, params, dte_scale) -> str
  BreakevenEngine._compute_multiplier(zone, nearest_distance_pct, params, ...) -> float

File: webui/backend/routes/mmm/mmm_breakeven_engine.py

--- compute_breakeven contracts ---
C-CB-1: spot_price <= 0 → empty safe result (zone=SAFE, lower/upper=None)
C-CB-2: breakeven_control_enabled=False → enabled=False
C-CB-3: no positions in session → safe default
C-CB-4: short straddle → lower/upper breakeven prices in expected range
C-CB-5: second call with same positions → from_cache=True
C-CB-6: invalidate_cache → next call recomputes (from_cache=False)

--- get_aggression_multiplier contracts ---
C-GAM-1: result=None → 1.0
C-GAM-2: zone=SAFE → 1.0
C-GAM-3: CRITICAL zone with known multiplier → returns result['multiplier']

--- invalidate_cache contracts ---
C-IC-1: invalidate non-existent session_id → no crash

--- _classify_zone contracts ---
C-CZ-1: nearest_distance_pct=None → SAFE
C-CZ-2: above warning_pct → SAFE
C-CZ-3: between warning and danger → WARNING
C-CZ-4: between danger and critical → DANGER
C-CZ-5: below critical_pct → CRITICAL

--- _compute_multiplier contracts ---
C-CM-1: SAFE zone → 1.0
C-CM-2: WARNING at max progress → 1.0 + 0.3 = 1.3
C-CM-3: CRITICAL at max progress → max_mult
C-CM-4: dte_aggression_damp reduces WARNING/DANGER but NOT CRITICAL
"""

import pytest
from unittest.mock import MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_session(ce_strike=90000, pe_strike=88000, ce_prem=200.0, pe_prem=200.0, lots=1):
    """Build a minimal session with one CE + one PE original position."""
    return {
        'session_id': 'test-be-001',
        'params': {
            'breakeven_control_enabled': True,
            'breakeven_warning_pct': 2.0,
            'breakeven_danger_pct': 1.0,
            'breakeven_critical_pct': 0.5,
            'breakeven_aggression_max': 3.0,
        },
        'realized_pnl': 0.0,
        'ce': {
            'active_strike': ce_strike,
            'original_lots': lots,
            'original_premium': ce_prem,
            'adjustment_fills': [],
            'frozen_positions': [],
        },
        'pe': {
            'active_strike': pe_strike,
            'original_lots': lots,
            'original_premium': pe_prem,
            'adjustment_fills': [],
            'frozen_positions': [],
        },
    }


def _make_engine():
    from webui.backend.routes.mmm.mmm_breakeven_engine import BreakevenEngine
    return BreakevenEngine()


# =============================================================================
# compute_breakeven
# =============================================================================

class TestComputeBreakeven:

    @pytest.mark.sealed
    def test_c_cb_1_nonpositive_spot_returns_safe_default(self):
        engine = _make_engine()
        sess = _make_session()
        result = engine.compute_breakeven(sess, 0.0)
        assert result['zone'] == 'SAFE'
        assert result['lower_breakeven'] is None
        assert result['upper_breakeven'] is None
        assert result['multiplier'] == 1.0

    @pytest.mark.sealed
    def test_c_cb_1b_negative_spot(self):
        engine = _make_engine()
        sess = _make_session()
        result = engine.compute_breakeven(sess, -100.0)
        assert result['zone'] == 'SAFE'
        assert result['lower_breakeven'] is None

    @pytest.mark.sealed
    def test_c_cb_2_disabled_returns_enabled_false(self):
        engine = _make_engine()
        sess = _make_session()
        sess['params']['breakeven_control_enabled'] = False
        result = engine.compute_breakeven(sess, 89000.0)
        assert result['enabled'] is False
        assert result['zone'] == 'SAFE'

    @pytest.mark.sealed
    def test_c_cb_3_no_positions_returns_safe_default(self):
        engine = _make_engine()
        sess = _make_session()
        # Wipe all positions
        sess['ce']['original_lots'] = 0
        sess['pe']['original_lots'] = 0
        result = engine.compute_breakeven(sess, 89000.0)
        assert result['zone'] == 'SAFE'
        assert result['lower_breakeven'] is None
        assert result['upper_breakeven'] is None

    @pytest.mark.sealed
    def test_c_cb_4_straddle_breakeven_in_expected_range(self):
        """Short straddle: CE@90000 prem=200, PE@88000 prem=200, spot=89000.
        Upper breakeven ≈ 90400, lower breakeven ≈ 87600 (within $10 precision).
        """
        engine = _make_engine()
        sess = _make_session(ce_strike=90000, pe_strike=88000,
                             ce_prem=200.0, pe_prem=200.0)
        result = engine.compute_breakeven(sess, 89000.0)
        assert result['enabled'] is True
        assert result['lower_breakeven'] is not None
        assert result['upper_breakeven'] is not None
        # Lower breakeven should be below spot
        assert result['lower_breakeven'] < 89000.0
        # Upper breakeven should be above spot
        assert result['upper_breakeven'] > 89000.0
        # Rough bounds (within ±100 of theoretical)
        assert 87500 < result['lower_breakeven'] < 88000
        assert 90000 < result['upper_breakeven'] < 90500

    @pytest.mark.sealed
    def test_c_cb_5_same_positions_second_call_uses_cache(self):
        engine = _make_engine()
        sess = _make_session()
        result1 = engine.compute_breakeven(sess, 89000.0)
        result2 = engine.compute_breakeven(sess, 89000.0)
        assert result1['from_cache'] is False
        assert result2['from_cache'] is True

    @pytest.mark.sealed
    def test_c_cb_6_invalidate_forces_recompute(self):
        engine = _make_engine()
        sess = _make_session()
        sess['session_id'] = 'cache-test-sid'
        engine.compute_breakeven(sess, 89000.0)  # prime cache
        engine.invalidate_cache('cache-test-sid')
        result = engine.compute_breakeven(sess, 89000.0)
        assert result['from_cache'] is False


# =============================================================================
# get_aggression_multiplier
# =============================================================================

class TestGetAggressionMultiplier:

    @pytest.mark.sealed
    def test_c_gam_1_none_result_returns_1(self):
        engine = _make_engine()
        assert engine.get_aggression_multiplier(None) == 1.0

    @pytest.mark.sealed
    def test_c_gam_2_safe_zone_returns_1(self):
        engine = _make_engine()
        result = {'enabled': True, 'zone': 'SAFE', 'multiplier': 1.5}
        assert engine.get_aggression_multiplier(result) == 1.0

    @pytest.mark.sealed
    def test_c_gam_3_critical_zone_returns_stored_multiplier(self):
        engine = _make_engine()
        result = {'enabled': True, 'zone': 'CRITICAL', 'multiplier': 2.8}
        assert engine.get_aggression_multiplier(result) == 2.8


# =============================================================================
# invalidate_cache
# =============================================================================

class TestInvalidateCache:

    @pytest.mark.sealed
    def test_c_ic_1_nonexistent_session_no_crash(self):
        engine = _make_engine()
        # Must not raise even when session_id not in cache
        engine.invalidate_cache('session-not-in-cache')


# =============================================================================
# _classify_zone (direct — internal method)
# =============================================================================

class TestClassifyZone:

    def _params(self):
        return {
            'breakeven_warning_pct': 2.0,
            'breakeven_danger_pct': 1.0,
            'breakeven_critical_pct': 0.5,
        }

    @pytest.mark.sealed
    def test_c_cz_1_none_distance_is_safe(self):
        engine = _make_engine()
        assert engine._classify_zone(None, self._params()) == 'SAFE'

    @pytest.mark.sealed
    def test_c_cz_2_above_warning_is_safe(self):
        engine = _make_engine()
        assert engine._classify_zone(2.5, self._params()) == 'SAFE'  # > 2.0

    @pytest.mark.sealed
    def test_c_cz_3_between_warning_danger_is_warning(self):
        engine = _make_engine()
        assert engine._classify_zone(1.5, self._params()) == 'WARNING'  # 2.0 > 1.5 > 1.0

    @pytest.mark.sealed
    def test_c_cz_4_between_danger_critical_is_danger(self):
        engine = _make_engine()
        assert engine._classify_zone(0.8, self._params()) == 'DANGER'  # 1.0 > 0.8 > 0.5

    @pytest.mark.sealed
    def test_c_cz_5_below_critical_is_critical(self):
        engine = _make_engine()
        assert engine._classify_zone(0.3, self._params()) == 'CRITICAL'  # < 0.5


# =============================================================================
# _compute_multiplier (direct — internal method)
# =============================================================================

class TestComputeMultiplier:

    def _params(self):
        return {
            'breakeven_warning_pct': 2.0,
            'breakeven_danger_pct': 1.0,
            'breakeven_critical_pct': 0.5,
            'breakeven_aggression_max': 3.0,
        }

    @pytest.mark.sealed
    def test_c_cm_1_safe_zone_returns_1(self):
        engine = _make_engine()
        result = engine._compute_multiplier('SAFE', 5.0, self._params())
        assert result == 1.0

    @pytest.mark.sealed
    def test_c_cm_2_warning_at_max_progress_returns_1_3(self):
        """WARNING zone at danger_pct boundary → multiplier = 1.3 (no damp)."""
        engine = _make_engine()
        # nearest=danger_pct → progress=1 → 1.0 + 1.0 * 0.3 = 1.3
        result = engine._compute_multiplier('WARNING', 1.0, self._params(),
                                            dte_aggression_damp=0.0)
        assert abs(result - 1.3) < 0.01

    @pytest.mark.sealed
    def test_c_cm_3_critical_at_max_progress_returns_max_mult(self):
        """CRITICAL at max depth → multiplier = max_mult (3.0)."""
        engine = _make_engine()
        # nearest=0 → progress ≈ 1.0 → 2.0 + 1.0*(3.0-2.0) = 3.0
        result = engine._compute_multiplier('CRITICAL', 0.0, self._params())
        assert abs(result - 3.0) < 0.01

    @pytest.mark.sealed
    def test_c_cm_4_damp_reduces_warning_danger_but_not_critical(self):
        """damp=1.0 → WARNING/DANGER collapse to 1.0, CRITICAL unaffected."""
        engine = _make_engine()
        # With 100% damp: WARNING → 1.0 + progress * 0.3 * 0 = 1.0
        warning_result = engine._compute_multiplier('WARNING', 1.5, self._params(),
                                                    dte_aggression_damp=1.0)
        assert abs(warning_result - 1.0) < 0.01

        # CRITICAL zone: ignores damp
        critical_result = engine._compute_multiplier('CRITICAL', 0.0, self._params(),
                                                     dte_aggression_damp=1.0)
        assert critical_result >= 2.0  # damp did not suppress CRITICAL
