"""
Contract tests for MMM Gamma — extracted gamma computation module

SEALED — v1.0.0 — April 3, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Covers:
  build_position_map     — session position extraction
  compute_gamma_data     — gamma metrics from ticker results
  _update_gamma_cap      — gamma cap regime (ported from mmm_regime tests)

File: webui/backend/routes/mmm/mmm_gamma.py

--- build_position_map contracts ---
C-BPM-1: Active strike + original_lots → included in map
C-BPM-2: Adjustment fills contribute to position map
C-BPM-3: Frozen positions contribute to position map
C-BPM-4: Empty session → empty map
C-BPM-5: Zero-lot positions filtered out

--- compute_gamma_data contracts ---
C-CGD-1: opt_char mapping: 'call'→'C', 'put'→'P'
C-CGD-2: CE gamma >> PE gamma reflected in positions list when CE lots*gamma dominant
C-CGD-3: Exception responses skipped gracefully

--- _update_gamma_cap contracts ---
C-UGC-1: 'C'/'P' strings produce per-side gamma (ported from regime tests)
"""

import pytest


# =============================================================================
# build_position_map
# =============================================================================

class TestBuildPositionMap:

    @pytest.mark.sealed
    def test_c_bpm_1_active_strike_original_lots(self):
        """Active strike + original_lots included in map."""
        from webui.backend.routes.mmm.mmm_gamma import build_position_map
        session = {
            'ce': {'active_strike': 70000, 'original_lots': 5, 'adjustment_fills': [], 'frozen_positions': []},
            'pe': {'active_strike': 65000, 'original_lots': 3, 'adjustment_fills': [], 'frozen_positions': []},
        }
        result = build_position_map(session)
        assert result == {(70000.0, 'call'): 5, (65000.0, 'put'): 3}

    @pytest.mark.sealed
    def test_c_bpm_2_adjustment_fills(self):
        """Adjustment fills contribute to the position map."""
        from webui.backend.routes.mmm.mmm_gamma import build_position_map
        session = {
            'ce': {
                'active_strike': 70000, 'original_lots': 5,
                'adjustment_fills': [
                    {'strike': 70000, 'lots': 3},
                    {'strike': 71000, 'lots': 2},
                ],
                'frozen_positions': [],
            },
            'pe': {},
        }
        result = build_position_map(session)
        assert result[(70000.0, 'call')] == 8  # 5 orig + 3 fill
        assert result[(71000.0, 'call')] == 2

    @pytest.mark.sealed
    def test_c_bpm_3_frozen_positions(self):
        """Frozen positions contribute to the position map."""
        from webui.backend.routes.mmm.mmm_gamma import build_position_map
        session = {
            'ce': {
                'active_strike': 70000, 'original_lots': 5,
                'adjustment_fills': [],
                'frozen_positions': [{'strike': 69000, 'lots': 4}],
            },
            'pe': {},
        }
        result = build_position_map(session)
        assert result[(70000.0, 'call')] == 5
        assert result[(69000.0, 'call')] == 4

    @pytest.mark.sealed
    def test_c_bpm_4_empty_session(self):
        """Empty session → empty position map."""
        from webui.backend.routes.mmm.mmm_gamma import build_position_map
        session = {}
        assert build_position_map(session) == {}

    @pytest.mark.sealed
    def test_c_bpm_5_zero_lots_filtered(self):
        """Zero-lot positions are excluded from map."""
        from webui.backend.routes.mmm.mmm_gamma import build_position_map
        session = {
            'ce': {
                'active_strike': 70000, 'original_lots': 0,
                'adjustment_fills': [{'strike': 70000, 'lots': 0}],
                'frozen_positions': [{'strike': 69000, 'lots': 0}],
            },
            'pe': {},
        }
        assert build_position_map(session) == {}


# =============================================================================
# compute_gamma_data
# =============================================================================

class TestComputeGammaData:

    def _make_ticker_result(self, strike, opt, gamma=0.01, delta=0.5):
        """Helper: build a (key, response) tuple mimicking exchange API."""
        return (
            (strike, opt),
            {'result': {'greeks': {'gamma': gamma, 'delta': delta}}},
        )

    @pytest.mark.sealed
    def test_c_cgd_1_opt_char_mapping(self):
        """'call' maps to 'C' and 'put' maps to 'P' in positions list."""
        from webui.backend.routes.mmm.mmm_gamma import compute_gamma_data
        ticker_results = [
            self._make_ticker_result(70000, 'call', gamma=0.02),
            self._make_ticker_result(65000, 'put', gamma=0.03),
        ]
        position_map = {(70000.0, 'call'): 10, (65000.0, 'put'): 8}
        result = compute_gamma_data(ticker_results, position_map)

        opt_chars = [pos[2] for pos in result['positions']]
        assert 'C' in opt_chars, f"Expected 'C' in positions, got {opt_chars}"
        assert 'P' in opt_chars, f"Expected 'P' in positions, got {opt_chars}"
        # No raw 'call' or 'put' strings
        assert 'call' not in opt_chars
        assert 'put' not in opt_chars

    @pytest.mark.sealed
    def test_c_cgd_2_ce_pe_gamma_in_positions(self):
        """CE positions with higher gamma-per-lot dominate the positions list.
        Dollar gamma is NOT computed here (no spot_price) — _update_gamma_cap does that."""
        from webui.backend.routes.mmm.mmm_gamma import compute_gamma_data
        from webui.backend.routes.mmm.mmm_constants import LOT_SIZE_BTC
        ticker_results = [
            self._make_ticker_result(70000, 'call', gamma=0.04),
            self._make_ticker_result(65000, 'put', gamma=0.005),
        ]
        position_map = {(70000.0, 'call'): 10, (65000.0, 'put'): 8}
        result = compute_gamma_data(ticker_results, position_map)

        ce_positions = [p for p in result['positions'] if p[2] == 'C']
        pe_positions = [p for p in result['positions'] if p[2] == 'P']
        assert ce_positions, "CE positions must be in result"
        assert pe_positions, "PE positions must be in result"
        ce_raw = sum(g * lots * LOT_SIZE_BTC for g, lots, _ in ce_positions)
        pe_raw = sum(g * lots * LOT_SIZE_BTC for g, lots, _ in pe_positions)
        # CE gamma (0.04 × 10 lots) >> PE gamma (0.005 × 8 lots) — ratio ≈ 10×
        assert ce_raw > pe_raw * 5, f"CE raw gamma {ce_raw} should dominate PE {pe_raw}"

    @pytest.mark.sealed
    def test_c_cgd_3_exception_responses_skipped(self):
        """Exception responses in ticker_results are skipped gracefully."""
        from webui.backend.routes.mmm.mmm_gamma import compute_gamma_data
        ticker_results = [
            ((70000.0, 'call'), RuntimeError("API timeout")),
            self._make_ticker_result(65000, 'put', gamma=0.01),
        ]
        position_map = {(70000.0, 'call'): 10, (65000.0, 'put'): 8}
        result = compute_gamma_data(ticker_results, position_map)

        # Only PE position should be in results
        assert len(result['positions']) == 1
        assert result['positions'][0][2] == 'P'


# =============================================================================
# _update_gamma_cap (ported from test_sealed_mmm_regime.py)
# =============================================================================

class TestUpdateGammaCap:

    @pytest.mark.sealed
    def test_c_ugc_opt_string_produces_per_side_gamma(self):
        """Regression: 'C'/'P' strings produce per-side gamma values."""
        from webui.backend.routes.mmm.mmm_gamma import _update_gamma_cap
        sess = {'params': {}, '_gamma_history': []}
        spot = 66000.0
        gamma_data = {
            'portfolio_gamma': 0.05,
            'positions': [
                (0.04, 10, 'C'),   # CE: 10 lots, gamma=0.04 — high CE gamma
                (0.005, 8, 'P'),   # PE: 8 lots, gamma=0.005 — low PE gamma
            ],
        }
        _update_gamma_cap(sess, gamma_data, spot, minutes_to_expiry=300)
        ce_dg = sess['_ce_dollar_gamma']
        pe_dg = sess['_pe_dollar_gamma']
        assert ce_dg > 0, f"CE dollar gamma must be > 0, got {ce_dg}"
        assert pe_dg > 0, f"PE dollar gamma must be > 0, got {pe_dg}"
        assert ce_dg > pe_dg * 3, (
            f"CE ($Γ={ce_dg}) should far exceed PE ($Γ={pe_dg}) given dominant CE positions"
        )
