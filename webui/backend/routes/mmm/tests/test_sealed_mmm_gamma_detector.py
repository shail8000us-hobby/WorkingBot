"""
Contract tests for MMM Gamma Detector — T3-7

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

No bugs found during audit.

Functions covered:
  GammaDetector.compute_gamma(session, spot_price, be_engine) -> Dict
  GammaDetector.invalidate_cache(session_id) -> None
  GammaDetector._run_boundary_scan(...) -> Tuple
  GammaDetector._classify_zone(nearest_distance_pct, params) -> str

File: webui/backend/routes/mmm/mmm_gamma_detector.py

--- compute_gamma contracts ---
C-CG-1: spot_price <= 0 → empty safe result
C-CG-2: gamma_detector_enabled=False → enabled=False
C-CG-3: no positions → safe default
C-CG-4: straddle with kinks at strikes → lower/upper boundaries detected
C-CG-5: same positions second call → from_cache=True
C-CG-6: invalidate_cache → next call recomputes (from_cache=False)

--- invalidate_cache contracts ---
C-IC-1: invalidate non-existent session_id → no crash

--- _run_boundary_scan contracts ---
C-RBS-1: no positions → no boundaries found (None, None)
C-RBS-2: short call above spot → upper boundary detected at call strike
C-RBS-3: short put below spot → lower boundary detected at put strike

--- _classify_zone contracts ---
C-CZ-1: nearest_distance_pct=None → SAFE
C-CZ-2: above warning → SAFE
C-CZ-3: between warning and danger → WARNING
C-CZ-4: at or below danger → DANGER
"""

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_session(ce_strike=90000, pe_strike=88000, ce_prem=200.0, pe_prem=200.0, lots=1):
    return {
        'session_id': 'gamma-test-001',
        'params': {
            'gamma_detector_enabled': True,
            'gamma_step_pct': 0.55,       # ~500 at spot=90000
            'gamma_scan_steps': 40,
            'gamma_detect_epsilon': 0.3,
            'gamma_warning_distance_pct': 3.0,
            'gamma_danger_distance_pct': 1.5,
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


def _make_detector():
    from webui.backend.routes.mmm.mmm_gamma_detector import GammaDetector
    return GammaDetector()


def _make_be_engine():
    from webui.backend.routes.mmm.mmm_breakeven_engine import BreakevenEngine
    return BreakevenEngine()


# =============================================================================
# compute_gamma
# =============================================================================

class TestComputeGamma:

    @pytest.mark.sealed
    def test_c_cg_1_nonpositive_spot_returns_safe_default(self):
        detector = _make_detector()
        sess = _make_session()
        result = detector.compute_gamma(sess, 0.0, _make_be_engine())
        assert result['gamma_zone'] == 'SAFE'
        assert result['lower_gamma_boundary'] is None
        assert result['upper_gamma_boundary'] is None

    @pytest.mark.sealed
    def test_c_cg_2_disabled_returns_enabled_false(self):
        detector = _make_detector()
        sess = _make_session()
        sess['params']['gamma_detector_enabled'] = False
        result = detector.compute_gamma(sess, 89000.0, _make_be_engine())
        assert result['enabled'] is False
        assert result['gamma_zone'] == 'SAFE'

    @pytest.mark.sealed
    def test_c_cg_3_no_positions_returns_safe_default(self):
        detector = _make_detector()
        sess = _make_session()
        sess['ce']['original_lots'] = 0
        sess['pe']['original_lots'] = 0
        result = detector.compute_gamma(sess, 89000.0, _make_be_engine())
        assert result['gamma_zone'] == 'SAFE'
        assert result['positions_included'] == 0

    @pytest.mark.sealed
    def test_c_cg_4_straddle_detects_kinks_at_strikes(self):
        """Short straddle: CE@90000, PE@88000, spot=89000.
        Upper kink ≈ 90000 (CE strike), lower kink ≈ 88000 (PE strike).
        """
        detector = _make_detector()
        sess = _make_session(ce_strike=90000, pe_strike=88000, ce_prem=200.0, pe_prem=200.0)
        be = _make_be_engine()
        result = detector.compute_gamma(sess, 89000.0, be)
        assert result['enabled'] is True
        # Both boundaries should be detected
        assert result['lower_gamma_boundary'] is not None
        assert result['upper_gamma_boundary'] is not None
        # Upper kink near CE strike (90000)
        assert 89000 < result['upper_gamma_boundary'] <= 90500
        # Lower kink near PE strike (88000)
        assert 87000 <= result['lower_gamma_boundary'] < 89000

    @pytest.mark.sealed
    def test_c_cg_5_same_positions_second_call_uses_cache(self):
        detector = _make_detector()
        sess = _make_session()
        be = _make_be_engine()
        result1 = detector.compute_gamma(sess, 89000.0, be)
        result2 = detector.compute_gamma(sess, 89000.0, be)
        assert result1['from_cache'] is False
        assert result2['from_cache'] is True

    @pytest.mark.sealed
    def test_c_cg_6_invalidate_forces_recompute(self):
        detector = _make_detector()
        sess = _make_session()
        sess['session_id'] = 'gamma-cache-test'
        be = _make_be_engine()
        detector.compute_gamma(sess, 89000.0, be)  # prime cache
        detector.invalidate_cache('gamma-cache-test')
        result = detector.compute_gamma(sess, 89000.0, be)
        assert result['from_cache'] is False


# =============================================================================
# invalidate_cache
# =============================================================================

class TestInvalidateCache:

    @pytest.mark.sealed
    def test_c_ic_1_nonexistent_session_no_crash(self):
        detector = _make_detector()
        detector.invalidate_cache('session-not-in-cache-gamma')


# =============================================================================
# _run_boundary_scan (direct)
# =============================================================================

class TestRunBoundaryScan:

    @pytest.mark.sealed
    def test_c_rbs_1_no_positions_returns_none_boundaries(self):
        detector = _make_detector()
        be = _make_be_engine()
        sess = {'realized_pnl': 0.0}
        result = detector._run_boundary_scan(
            positions=[], session=sess, spot=89000.0,
            step=500.0, scan_steps=20, epsilon=0.3, be_engine=be
        )
        lower, upper, sev_lower, sev_upper = result
        assert lower is None
        assert upper is None
        assert sev_lower is None
        assert sev_upper is None

    @pytest.mark.sealed
    def test_c_rbs_2_short_call_above_spot_detects_upper_boundary(self):
        """Short call at 90000, spot=89000 → upper kink near 90000."""
        detector = _make_detector()
        be = _make_be_engine()
        # Single CE position
        positions = [{
            'strike': 90000.0,
            'lots': 1,
            'entry_premium': 200.0,
            'option_type': 'call',
            'pos_type': 'original',
        }]
        sess = {'realized_pnl': 0.0}
        lower, upper, sev_lower, sev_upper = detector._run_boundary_scan(
            positions, sess, 89000.0, step=500.0, scan_steps=20, epsilon=0.1, be_engine=be
        )
        assert upper is not None
        # Upper boundary should be near the call strike
        assert 89000 < upper <= 91000

    @pytest.mark.sealed
    def test_c_rbs_3_short_put_below_spot_detects_lower_boundary(self):
        """Short put at 88000, spot=89000 → lower kink near 88000."""
        detector = _make_detector()
        be = _make_be_engine()
        positions = [{
            'strike': 88000.0,
            'lots': 1,
            'entry_premium': 200.0,
            'option_type': 'put',
            'pos_type': 'original',
        }]
        sess = {'realized_pnl': 0.0}
        lower, upper, sev_lower, sev_upper = detector._run_boundary_scan(
            positions, sess, 89000.0, step=500.0, scan_steps=20, epsilon=0.1, be_engine=be
        )
        assert lower is not None
        assert 87000 <= lower < 89000


# =============================================================================
# _classify_zone (direct)
# =============================================================================

class TestClassifyZoneGamma:

    def _params(self):
        return {
            'gamma_warning_distance_pct': 3.0,
            'gamma_danger_distance_pct': 1.5,
        }

    @pytest.mark.sealed
    def test_c_cz_1_none_is_safe(self):
        detector = _make_detector()
        assert detector._classify_zone(None, self._params()) == 'SAFE'

    @pytest.mark.sealed
    def test_c_cz_2_above_warning_is_safe(self):
        detector = _make_detector()
        assert detector._classify_zone(4.0, self._params()) == 'SAFE'

    @pytest.mark.sealed
    def test_c_cz_3_between_warning_danger_is_warning(self):
        detector = _make_detector()
        assert detector._classify_zone(2.0, self._params()) == 'WARNING'  # 3.0 > 2.0 > 1.5

    @pytest.mark.sealed
    def test_c_cz_4_at_or_below_danger_is_danger(self):
        detector = _make_detector()
        assert detector._classify_zone(1.5, self._params()) == 'DANGER'  # not > 1.5
        assert detector._classify_zone(0.5, self._params()) == 'DANGER'
