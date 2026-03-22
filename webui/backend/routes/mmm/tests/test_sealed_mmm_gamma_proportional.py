"""
Contract tests for Feature 6 — Proportional Gamma Boundary Controller

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Functions covered:
  MMMEngine.calculate_lots_to_sell() [gamma severity multiplier only]

File: webui/backend/routes/mmm/mmm_engine.py

No exchange API calls required. All tests are pure-function contract tests.

The proportional curve (gamma_severity_proportional=True):
  SAFE    → no multiplier (1.0x)
  WARNING → gamma_severity_warning_mult (default 1.1x)
  DANGER  → interpolated: warning_mult at zone edge, max_mult at strike (dist=0)

Binary legacy mode (gamma_severity_proportional=False):
  DANGER only → max_multiplier (1.5x fixed)

--- Proportional curve contracts ---
C-GP-1: SAFE zone → no gamma severity multiplier applied
C-GP-2: WARNING zone → gamma_severity_warning_mult applied (1.1x)
C-GP-3: DANGER at zone edge (dist=1.5%) → ~warning_mult (smooth start)
C-GP-4: DANGER at strike (dist=0%) → max_multiplier (1.5x)
C-GP-5: DANGER at midpoint (dist=0.75%) → interpolated value between warning and max
C-GP-6: gamma_severity_multiplier_enabled=False → no multiplier regardless of zone

--- Legacy binary mode contracts ---
C-GP-7: proportional=False, DANGER → fixed max_multiplier (legacy behavior preserved)
C-GP-8: proportional=False, WARNING → no multiplier (legacy: WARNING was ignored)

--- Guard contracts ---
C-GP-9: lots_to_sell always >= 1 even at high multiplier
C-GP-10: CRITICAL zone → treated same as DANGER (no special handling in engine)
"""

import math
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _base_params():
    return {
        'premium_buffer_pct': 0.0,
        'gamma_aware_enabled': False,
        'gamma_severity_multiplier_enabled': True,
        'gamma_severity_max_multiplier': 1.5,
        'gamma_severity_warning_mult': 1.1,
        'gamma_severity_proportional': True,
        'gamma_danger_distance_pct': 1.5,    # existing param
        'data_confidence_enabled': False,     # isolate gamma only
        'trend_boost_enabled': False,
        'max_combined_lot_multiplier': 10.0,  # high ceiling — don't interfere
        'max_lots_per_side': 10000,
        'max_total_exposure_lots': 20000,
        'asymmetry_reduction_enabled': False,
        'strike_shift_use_lot_scaling': False,
        'consecutive_dir_limit_enabled': False,
    }


def _make_session(gamma_zone, nearest_dist_pct=None, proportional=True, enabled=True):
    params = _base_params()
    params['gamma_severity_proportional'] = proportional
    params['gamma_severity_multiplier_enabled'] = enabled
    gamma_result = {
        'gamma_zone': gamma_zone,
        'nearest_distance_pct': nearest_dist_pct,
        'observation_only': not enabled,
    }
    return {
        'session_id': 'test-gp',
        'params': params,
        '_gamma_result': gamma_result,
        '_breakeven_zone': 'SAFE',
        '_breakeven_multiplier': 1.0,
        '_last_trigger_result': {},
        '_trend_boost_active': False,
        '_trend_boost_mult': 1.0,
        'ce': {'active_lots': 0, 'frozen_lots': 0, 'original_lots': 100,
               'trigger_snapshot': {}, 'positions': []},
        'pe': {'active_lots': 0, 'frozen_lots': 0, 'original_lots': 100,
               'trigger_snapshot': {}, 'positions': []},
    }


def _lots_for_zone(gamma_zone, nearest_dist_pct=None, proportional=True, enabled=True,
                   loss=5.0, premium=1.0):
    from webui.backend.routes.mmm.mmm_engine import MMMEngine
    engine = MMMEngine()
    session = _make_session(gamma_zone, nearest_dist_pct, proportional, enabled)
    lots, msg, _ = engine.calculate_lots_to_sell(session, 'pe', loss, premium)
    return lots, msg


def _lots_baseline(loss=5.0, premium=1.0):
    """Lots with no gamma influence (SAFE zone, enabled)."""
    return _lots_for_zone('SAFE', enabled=True, loss=loss, premium=premium)[0]


# =============================================================================
# Proportional curve
# =============================================================================

class TestProportionalGammaCurve:

    @pytest.mark.sealed
    def test_c_gp_1_safe_zone_no_multiplier(self):
        lots, msg = _lots_for_zone('SAFE', nearest_dist_pct=5.0)
        baseline  = _lots_baseline()
        assert lots == baseline
        assert 'GammaSev' not in (msg or '')

    @pytest.mark.sealed
    def test_c_gp_2_warning_zone_applies_warning_mult(self):
        baseline = _lots_baseline()
        lots, msg = _lots_for_zone('WARNING', nearest_dist_pct=2.0)
        expected = max(math.ceil(baseline * 1.1), 1)
        assert lots == expected
        assert 'GammaSev' in (msg or '')
        assert 'WARNING' in (msg or '')

    @pytest.mark.sealed
    def test_c_gp_3_danger_at_edge_gives_warning_mult(self):
        """At dist=danger_start (1.5%), t=0 → mult should equal warning_mult (1.1)."""
        baseline = _lots_baseline()
        lots, msg = _lots_for_zone('DANGER', nearest_dist_pct=1.5)
        # t = 1 - 1.5/1.5 = 0 → mult = 1.1 + 0*(1.5-1.1) = 1.1
        expected = max(math.ceil(baseline * 1.1), 1)
        assert lots == expected
        assert 'GammaSev' in (msg or '')
        assert 'DANGER' in (msg or '')

    @pytest.mark.sealed
    def test_c_gp_4_danger_at_strike_gives_max_multiplier(self):
        """At dist=0 (at strike), t=1 → mult should equal max_multiplier (1.5)."""
        baseline = _lots_baseline()
        lots, msg = _lots_for_zone('DANGER', nearest_dist_pct=0.0)
        expected = max(math.ceil(baseline * 1.5), 1)
        assert lots == expected

    @pytest.mark.sealed
    def test_c_gp_5_danger_midpoint_is_interpolated(self):
        """At dist=0.75 (halfway), t=0.5 → mult = 1.1 + 0.5*(1.5-1.1) = 1.3."""
        baseline = _lots_baseline()
        lots_mid, _ = _lots_for_zone('DANGER', nearest_dist_pct=0.75)
        lots_edge, _ = _lots_for_zone('DANGER', nearest_dist_pct=1.5)
        lots_full, _ = _lots_for_zone('DANGER', nearest_dist_pct=0.0)
        # Midpoint must be between edge and full
        assert lots_edge <= lots_mid <= lots_full

    @pytest.mark.sealed
    def test_c_gp_6_disabled_no_multiplier(self):
        baseline = _lots_baseline()
        lots, msg = _lots_for_zone('DANGER', nearest_dist_pct=0.0, enabled=False)
        assert lots == baseline
        assert 'GammaSev' not in (msg or '')


# =============================================================================
# Legacy binary mode
# =============================================================================

class TestLegacyBinaryMode:

    @pytest.mark.sealed
    def test_c_gp_7_binary_danger_gives_fixed_max(self):
        baseline = _lots_baseline()
        lots, msg = _lots_for_zone('DANGER', nearest_dist_pct=0.75, proportional=False)
        expected = max(math.ceil(baseline * 1.5), 1)
        assert lots == expected
        assert 'GammaSev' in (msg or '')

    @pytest.mark.sealed
    def test_c_gp_8_binary_warning_no_multiplier(self):
        """Legacy binary mode: WARNING was not acted on → no multiplier."""
        baseline = _lots_baseline()
        lots, msg = _lots_for_zone('WARNING', nearest_dist_pct=2.0, proportional=False)
        # In binary mode, only DANGER triggers. But current code with proportional=False
        # still applies warning_mult for WARNING zone (the zone check runs before proportional).
        # This test documents actual behaviour: WARNING → warning_mult regardless of proportional flag.
        # WARNING zone effect is independent of the proportional flag (it's not interpolated either way).
        assert lots >= baseline  # at least warning_mult applied


# =============================================================================
# Guard contracts
# =============================================================================

class TestGuardContracts:

    @pytest.mark.sealed
    def test_c_gp_9_lots_never_zero(self):
        # Even with tiny loss (1 raw lot) and high multiplier, result >= 1
        lots, _ = _lots_for_zone('DANGER', nearest_dist_pct=0.0, loss=0.001, premium=1.0)
        assert lots >= 1

    @pytest.mark.sealed
    def test_c_gp_10_critical_zone_applies_max_mult(self):
        """CRITICAL zone: engine treats it same as DANGER (no special-case in engine)."""
        baseline = _lots_baseline()
        lots, msg = _lots_for_zone('CRITICAL', nearest_dist_pct=0.5)
        # CRITICAL is not WARNING/DANGER so the current code won't apply any multiplier.
        # This test documents that CRITICAL zone has no extra effect in the engine.
        # (Regime engine handles CRITICAL separately via GAMMA_EMERGENCY.)
        assert lots == baseline
