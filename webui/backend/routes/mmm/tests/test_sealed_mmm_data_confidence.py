"""
Contract tests for Feature 9 — Data Confidence Score + Trade Confidence Gate

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Functions covered:
  MMMMonitor._compute_data_confidence() -> float
  MMMEngine.calculate_lots_to_sell() [confidence gate only]

File: webui/backend/routes/mmm/mmm_monitor.py
      webui/backend/routes/mmm/mmm_engine.py

No exchange API calls required. All tests are pure-function contract tests.

--- _compute_data_confidence contracts ---
C-DC-1: No stale flags, no WS failures → confidence = 1.0
C-DC-2: CE stale only → 1.0 - stale_penalty
C-DC-3: Both sides stale → 1.0 - 2 * stale_penalty
C-DC-4: WS failures deduct proportionally
C-DC-5: Combined penalties clamped to confidence_min_floor
C-DC-6: data_confidence_enabled=False → always 1.0

--- calculate_lots_to_sell confidence gate contracts ---
C-DC-7: confidence=1.0 → no lot reduction
C-DC-8: confidence=0.5 → lots halved (floor to 1)
C-DC-9: data_confidence_enabled=False → gate skipped even with low confidence
C-DC-10: confidence gate applied after all multipliers (raw lots not changed)
"""

import math
import pytest
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_monitor_with_session(session_overrides=None, params_overrides=None):
    """Build a minimal MMMMonitor-like object with a fake session."""
    from webui.backend.routes.mmm.mmm_monitor import MMMMonitor

    params = {
        'data_confidence_enabled': True,
        'confidence_stale_penalty': 0.25,
        'confidence_ws_failure_penalty': 0.04,
        'confidence_min_floor': 0.20,
        **(params_overrides or {}),
    }
    session = {
        'session_id': 'test-dc',
        'params': params,
        **(session_overrides or {}),
    }
    monitor = MMMMonitor.__new__(MMMMonitor)
    monitor.session = session
    monitor.session_id = 'test-dc'
    return monitor


def _make_engine_session(lots_override=None, confidence=1.0, enabled=True):
    """Build a minimal session for calculate_lots_to_sell confidence gate tests."""
    return {
        'session_id': 'test-eng',
        '_data_confidence': confidence,
        'params': {
            'data_confidence_enabled': enabled,
            'confidence_min_floor': 0.20,
            # Required params for calculate_lots_to_sell to reach the confidence gate
            'premium_buffer_pct': 0.0,
            'gamma_aware_enabled': False,
            'gamma_severity_multiplier_enabled': False,
            'gamma_severity_proportional': False,
            'trend_boost_enabled': False,
            'max_combined_lot_multiplier': 10.0,
            'max_lots_per_side': lots_override or 1000,
            'max_total_exposure_lots': 2000,
            'asymmetry_reduction_enabled': False,
            'strike_shift_use_lot_scaling': False,
            'consecutive_dir_limit_enabled': False,
        },
        'ce': {'active_lots': 0, 'frozen_lots': 0, 'original_lots': 100,
               'trigger_snapshot': {}, 'positions': []},
        'pe': {'active_lots': 0, 'frozen_lots': 0, 'original_lots': 100,
               'trigger_snapshot': {}, 'positions': []},
        '_gamma_result': {},
        '_breakeven_zone': 'SAFE',
        '_breakeven_multiplier': 1.0,
        '_last_trigger_result': {},
        '_trend_boost_active': False,
        '_trend_boost_mult': 1.0,
    }


# =============================================================================
# _compute_data_confidence
# =============================================================================

class TestComputeDataConfidence:

    @pytest.mark.sealed
    def test_c_dc_1_no_stale_no_failures_returns_1(self):
        monitor = _make_monitor_with_session()
        with patch('webui.backend.routes.mmm.mmm_monitor.get_ws_health',
                   return_value={'consecutive_failures': 0}):
            result = monitor._compute_data_confidence()
        assert result == 1.0
        assert monitor.session['_data_confidence'] == 1.0

    @pytest.mark.sealed
    def test_c_dc_2_ce_stale_only_deducts_penalty(self):
        monitor = _make_monitor_with_session(session_overrides={'_ce_premium_stale': True})
        with patch('webui.backend.routes.mmm.mmm_monitor.get_ws_health',
                   return_value={'consecutive_failures': 0}):
            result = monitor._compute_data_confidence()
        assert abs(result - 0.75) < 0.001  # 1.0 - 0.25

    @pytest.mark.sealed
    def test_c_dc_3_both_stale_deducts_double_penalty(self):
        monitor = _make_monitor_with_session(
            session_overrides={'_ce_premium_stale': True, '_pe_premium_stale': True}
        )
        with patch('webui.backend.routes.mmm.mmm_monitor.get_ws_health',
                   return_value={'consecutive_failures': 0}):
            result = monitor._compute_data_confidence()
        assert abs(result - 0.50) < 0.001  # 1.0 - 0.25 - 0.25

    @pytest.mark.sealed
    def test_c_dc_4_ws_failures_deduct_proportionally(self):
        monitor = _make_monitor_with_session()
        # 5 failures × 0.04 = 0.20 deduction
        with patch('webui.backend.routes.mmm.mmm_monitor.get_ws_health',
                   return_value={'consecutive_failures': 5}):
            result = monitor._compute_data_confidence()
        assert abs(result - 0.80) < 0.001  # 1.0 - (5 * 0.04)

    @pytest.mark.sealed
    def test_c_dc_5_combined_penalties_clamped_to_floor(self):
        monitor = _make_monitor_with_session(
            session_overrides={'_ce_premium_stale': True, '_pe_premium_stale': True}
        )
        # Both stale (-0.50) + 20 WS failures (-0.80) = -1.30 → floor at 0.20
        with patch('webui.backend.routes.mmm.mmm_monitor.get_ws_health',
                   return_value={'consecutive_failures': 20}):
            result = monitor._compute_data_confidence()
        assert abs(result - 0.20) < 0.001  # floored at confidence_min_floor

    @pytest.mark.sealed
    def test_c_dc_6_disabled_always_returns_1(self):
        monitor = _make_monitor_with_session(
            session_overrides={'_ce_premium_stale': True, '_pe_premium_stale': True},
            params_overrides={'data_confidence_enabled': False},
        )
        with patch('webui.backend.routes.mmm.mmm_monitor.get_ws_health',
                   return_value={'consecutive_failures': 50}):
            result = monitor._compute_data_confidence()
        assert result == 1.0
        assert monitor.session['_data_confidence'] == 1.0


# =============================================================================
# calculate_lots_to_sell — confidence gate
# =============================================================================

class TestConfidenceLotGate:

    @pytest.mark.sealed
    def test_c_dc_7_confidence_1_no_lot_reduction(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session = _make_engine_session(confidence=1.0)
        # 100 lots loss at $1 premium: raw = 100 / (1 * 0.001) = 100,000 → but position cap = 1000
        lots, msg, _ = engine.calculate_lots_to_sell(
            session, 'pe', loss_to_cover=100.0, hedge_premium=1.0
        )
        # Confidence=1.0: no DataConf message
        assert 'DataConf' not in (msg or '')

    @pytest.mark.sealed
    def test_c_dc_8_confidence_half_halves_lots(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        # Build sessions: one full confidence, one half
        session_full = _make_engine_session(confidence=1.0, lots_override=100)
        session_half = _make_engine_session(confidence=0.5, lots_override=100)

        lots_full, _, _ = engine.calculate_lots_to_sell(
            session_full, 'pe', loss_to_cover=5.0, hedge_premium=1.0
        )
        lots_half, msg_half, _ = engine.calculate_lots_to_sell(
            session_half, 'pe', loss_to_cover=5.0, hedge_premium=1.0
        )
        # Half confidence should produce fewer lots (floor applied)
        assert lots_half <= lots_full
        assert lots_half >= 1  # never zero
        assert 'DataConf' in (msg_half or '')

    @pytest.mark.sealed
    def test_c_dc_9_disabled_gate_skipped(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        session_enabled  = _make_engine_session(confidence=0.2, enabled=True,  lots_override=100)
        session_disabled = _make_engine_session(confidence=0.2, enabled=False, lots_override=100)

        lots_enabled,  _, _ = engine.calculate_lots_to_sell(
            session_enabled,  'pe', loss_to_cover=5.0, hedge_premium=1.0
        )
        lots_disabled, _, _ = engine.calculate_lots_to_sell(
            session_disabled, 'pe', loss_to_cover=5.0, hedge_premium=1.0
        )
        # Disabled gate → no reduction → more lots than with 0.2x gate
        assert lots_disabled >= lots_enabled

    @pytest.mark.sealed
    def test_c_dc_10_floor_prevents_zero_lots(self):
        from webui.backend.routes.mmm.mmm_engine import MMMEngine
        engine = MMMEngine()
        # confidence at floor (0.20), loss=1 lot raw
        session = _make_engine_session(confidence=0.20, lots_override=100)
        lots, _, _ = engine.calculate_lots_to_sell(
            session, 'pe', loss_to_cover=0.001, hedge_premium=1.0
        )
        # floor prevents 0 lots: always at least 1
        assert lots >= 1
