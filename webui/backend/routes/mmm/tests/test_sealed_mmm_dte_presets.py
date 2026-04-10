"""
Contract tests for MMM DTE Presets — T3-5

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

BUG FIXED at seal time:
  build_straddle_adjustment_preset: max_loss_amount was 3.0 (USD) — clearly wrong
  given 0DTE max_loss_amount=5000 and 5DTE=15000. Fixed to 3000.0.
  list_presets() already showed 3000 (with comment "Updated to reflect actual max
  loss amount"), confirming 3.0 was a typo.

Functions covered:
  compute_total_dte_hours(expiry_str, expiry_hour_utc, expiry_minute_utc) -> float
  infer_dte_category(total_dte_hours) -> str
  check_aggregate_pnl(active_sessions, global_max_loss) -> Dict
  check_chain_liquidity(chain, min_liquidity_lots, min_strikes_per_side) -> Dict
  apply_preset(params, dte_category) -> Dict
  build_straddle_adjustment_preset(hours_to_expiry) -> Dict

File: webui/backend/routes/mmm/mmm_dte_presets.py

--- compute_total_dte_hours contracts ---
C-CTDH-1: future expiry → positive hours
C-CTDH-2: past expiry → negative hours
C-CTDH-3: bad format → 0.0
C-CTDH-4: expiry_hour_utc offset produces exact hour difference

--- infer_dte_category contracts ---
C-IDC-1: 24h → '0DTE'
C-IDC-2: exactly 36h (1.5-day boundary) → '0DTE' (inclusive)
C-IDC-3: 36.1h → '5DTE'

--- check_aggregate_pnl contracts ---
C-CAP-1: empty sessions → ok, combined_pnl=0, safe=True
C-CAP-2: combined_pnl = -global_max_loss → breach, safe=False
C-CAP-3: combined_pnl at 80% of limit → critical, safe=True
C-CAP-4: combined_pnl at 50% of limit → warning, safe=True
C-CAP-5: positive combined_pnl → ok, safe=True
C-CAP-6: manual_reduction_pnl included in combined total
C-CAP-7: result dict has all required keys

--- check_chain_liquidity contracts ---
C-CCL-1: empty chain → not liquid
C-CCL-2: both sides meet min_strikes → liquid=True
C-CCL-3: only CE side meets minimum → not liquid
C-CCL-4: bid=0 → doesn't count toward liquid_strikes
C-CCL-5: bid_size below minimum → doesn't count

--- apply_preset contracts ---
C-AP-1: known static preset merges, dte_category stored
C-AP-2: user params override preset values
C-AP-3: unknown preset → returns params unchanged
C-AP-4: STRADDLE_WITH_ADJUSTMENT without expiry → returns params unchanged
C-AP-5: STRADDLE_WITH_ADJUSTMENT valid → dte_category='0DTE', _preset_source='STRADDLE_WITH_ADJUSTMENT'
C-AP-6: STRADDLE_WITH_ADJUSTMENT hours<1 → ValueError caught, returns params unchanged

--- build_straddle_adjustment_preset contracts ---
C-BSS-1: H < 1 → raises ValueError
C-BSS-2: H > 24 → does not raise (warning only)
C-BSS-3: H = 5.0 → returns complete dict
C-BSS-4: max_loss_amount = 3000.0 (not 3.0 — BUG FIXED)
C-BSS-5: dte_category = '0DTE'
C-BSS-6: scaled params within expected clamp bounds for H=5.0
"""

import pytest
from unittest.mock import patch


# =============================================================================
# compute_total_dte_hours
# =============================================================================

class TestComputeTotalDteHours:

    @pytest.mark.sealed
    def test_c_ctdh_1_future_expiry_positive(self):
        from webui.backend.routes.mmm.mmm_dte_presets import compute_total_dte_hours
        # Year 2050 is safely in the future — hours must be positive
        result = compute_total_dte_hours('21032050')
        assert result > 1000  # Many years away

    @pytest.mark.sealed
    def test_c_ctdh_2_past_expiry_negative(self):
        from webui.backend.routes.mmm.mmm_dte_presets import compute_total_dte_hours
        # Year 2000 is safely in the past — hours must be negative
        result = compute_total_dte_hours('21032000')
        assert result < -1000

    @pytest.mark.sealed
    def test_c_ctdh_3_bad_format_returns_zero(self):
        from webui.backend.routes.mmm.mmm_dte_presets import compute_total_dte_hours
        assert compute_total_dte_hours('') == 0.0
        assert compute_total_dte_hours('not-a-date') == 0.0
        assert compute_total_dte_hours('99999999') == 0.0  # invalid month/day

    @pytest.mark.sealed
    def test_c_ctdh_4_hour_offset_produces_exact_difference(self):
        from webui.backend.routes.mmm.mmm_dte_presets import compute_total_dte_hours
        # Same far-future expiry, 3-hour difference in UTC → exactly 3h difference
        r12 = compute_total_dte_hours('21032050', expiry_hour_utc=12)
        r15 = compute_total_dte_hours('21032050', expiry_hour_utc=15)
        assert abs(r15 - r12 - 3.0) < 0.01


# =============================================================================
# infer_dte_category
# =============================================================================

class TestInferDteCategory:

    @pytest.mark.sealed
    def test_c_idc_1_24h_is_0dte(self):
        from webui.backend.routes.mmm.mmm_dte_presets import infer_dte_category
        assert infer_dte_category(24.0) == '0DTE'

    @pytest.mark.sealed
    def test_c_idc_2_exactly_36h_is_0dte_boundary_inclusive(self):
        from webui.backend.routes.mmm.mmm_dte_presets import infer_dte_category
        # 36h = 1.5 days — boundary is ≤1.5 so 36.0h is still 0DTE
        assert infer_dte_category(36.0) == '0DTE'

    @pytest.mark.sealed
    def test_c_idc_3_above_36h_is_5dte(self):
        from webui.backend.routes.mmm.mmm_dte_presets import infer_dte_category
        assert infer_dte_category(36.1) == '5DTE'
        assert infer_dte_category(120.0) == '5DTE'


# =============================================================================
# check_aggregate_pnl
# =============================================================================

class TestCheckAggregatePnl:

    @pytest.mark.sealed
    def test_c_cap_1_empty_sessions_ok(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        result = check_aggregate_pnl([])
        assert result['level'] == 'ok'
        assert result['safe'] is True
        assert result['combined_pnl'] == 0.0

    @pytest.mark.sealed
    def test_c_cap_2_breach_at_max_loss(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        sessions = [{'realized_pnl': -1000.0, 'unrealized_pnl': 0.0}]
        result = check_aggregate_pnl(sessions, global_max_loss=1000.0)
        assert result['level'] == 'breach'
        assert result['safe'] is False

    @pytest.mark.sealed
    def test_c_cap_3_critical_at_80_pct(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        # combined_pnl = -800, global_max_loss = 1000 → pnl_pct = 80 → critical
        sessions = [{'realized_pnl': -800.0, 'unrealized_pnl': 0.0}]
        result = check_aggregate_pnl(sessions, global_max_loss=1000.0)
        assert result['level'] == 'critical'
        assert result['safe'] is True

    @pytest.mark.sealed
    def test_c_cap_4_warning_at_50_pct(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        # combined_pnl = -500, global_max_loss = 1000 → pnl_pct = 50 → warning
        sessions = [{'realized_pnl': -500.0, 'unrealized_pnl': 0.0}]
        result = check_aggregate_pnl(sessions, global_max_loss=1000.0)
        assert result['level'] == 'warning'
        assert result['safe'] is True

    @pytest.mark.sealed
    def test_c_cap_5_positive_pnl_is_ok(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        sessions = [{'realized_pnl': 200.0, 'unrealized_pnl': 50.0}]
        result = check_aggregate_pnl(sessions, global_max_loss=1000.0)
        assert result['level'] == 'ok'
        assert result['safe'] is True
        assert result['combined_pnl'] == 250.0

    @pytest.mark.sealed
    def test_c_cap_6_manual_reduction_pnl_included(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        # manual_reduction_pnl is added to combined_realized
        sessions = [{
            'realized_pnl': -400.0,
            'unrealized_pnl': 0.0,
            'manual_reduction_pnl': -200.0,  # extra loss
        }]
        result = check_aggregate_pnl(sessions, global_max_loss=1000.0)
        # combined = -400 + -200 = -600 → pnl_pct=60 → warning
        assert result['combined_pnl'] == -600.0
        assert result['level'] == 'warning'

    @pytest.mark.sealed
    def test_c_cap_7_result_has_required_keys(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_aggregate_pnl
        result = check_aggregate_pnl([])
        for key in ('safe', 'combined_pnl', 'combined_realized', 'combined_unrealized',
                    'session_count', 'pnl_pct_of_limit', 'level', 'message'):
            assert key in result, f"Missing key: {key}"


# =============================================================================
# check_chain_liquidity
# =============================================================================

def _make_chain_entry(call_bid=0, call_bid_size=0, put_bid=0, put_bid_size=0):
    return {
        'strike': 90000,
        'call': {'bid': call_bid, 'bid_size': call_bid_size},
        'put': {'bid': put_bid, 'bid_size': put_bid_size},
    }


class TestCheckChainLiquidity:

    @pytest.mark.sealed
    def test_c_ccl_1_empty_chain_not_liquid(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_chain_liquidity
        result = check_chain_liquidity([])
        assert result['liquid'] is False
        assert result['ce_liquid_strikes'] == 0
        assert result['pe_liquid_strikes'] == 0

    @pytest.mark.sealed
    def test_c_ccl_2_both_sides_meet_min_liquid(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_chain_liquidity
        chain = [
            _make_chain_entry(100, 5, 100, 5),
            _make_chain_entry(90, 5, 90, 5),
        ]
        result = check_chain_liquidity(chain, min_liquidity_lots=5, min_strikes_per_side=2)
        assert result['liquid'] is True
        assert result['ce_liquid_strikes'] == 2
        assert result['pe_liquid_strikes'] == 2

    @pytest.mark.sealed
    def test_c_ccl_3_only_ce_meets_min_not_liquid(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_chain_liquidity
        chain = [
            _make_chain_entry(100, 5, 0, 0),   # CE ok, PE zero
            _make_chain_entry(90, 5, 0, 0),
        ]
        result = check_chain_liquidity(chain, min_liquidity_lots=5, min_strikes_per_side=2)
        assert result['liquid'] is False
        assert result['ce_liquid_strikes'] == 2
        assert result['pe_liquid_strikes'] == 0

    @pytest.mark.sealed
    def test_c_ccl_4_zero_bid_not_counted(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_chain_liquidity
        # bid=0 even with large bid_size → not liquid
        chain = [
            _make_chain_entry(call_bid=0, call_bid_size=100, put_bid=0, put_bid_size=100),
            _make_chain_entry(call_bid=0, call_bid_size=100, put_bid=0, put_bid_size=100),
        ]
        result = check_chain_liquidity(chain, min_liquidity_lots=5, min_strikes_per_side=2)
        assert result['liquid'] is False
        assert result['ce_liquid_strikes'] == 0

    @pytest.mark.sealed
    def test_c_ccl_5_bid_size_below_min_not_counted(self):
        from webui.backend.routes.mmm.mmm_dte_presets import check_chain_liquidity
        # bid > 0 but bid_size < min → not liquid
        chain = [
            _make_chain_entry(100, 4, 100, 4),  # size=4 < min_liquidity_lots=5
            _make_chain_entry(90, 4, 90, 4),
        ]
        result = check_chain_liquidity(chain, min_liquidity_lots=5, min_strikes_per_side=2)
        assert result['liquid'] is False
        assert result['ce_liquid_strikes'] == 0
        assert result['pe_liquid_strikes'] == 0


# =============================================================================
# apply_preset
# =============================================================================

class TestApplyPreset:

    @pytest.mark.sealed
    def test_c_ap_1_static_preset_merges_dte_category_stored(self):
        from webui.backend.routes.mmm.mmm_dte_presets import apply_preset
        params = {'expiry': '21032026', 'initial_lots': 5}
        result = apply_preset(params, '0DTE')
        # dte_category always stored
        assert result['dte_category'] == '0DTE'
        # Preset values present (e.g., adjustment_interval from PRESET_0DTE)
        assert 'adjustment_interval' in result
        # User params preserved
        assert result['initial_lots'] == 5

    @pytest.mark.sealed
    def test_c_ap_2_user_params_override_preset(self):
        from webui.backend.routes.mmm.mmm_dte_presets import apply_preset, PRESET_0DTE
        # Preset 0DTE has adjustment_interval=300; user overrides to 60
        params = {'expiry': '21032026', 'adjustment_interval': 60}
        result = apply_preset(params, '0DTE')
        assert result['adjustment_interval'] == 60  # user wins

    @pytest.mark.sealed
    def test_c_ap_3_unknown_preset_returns_params_unchanged(self):
        from webui.backend.routes.mmm.mmm_dte_presets import apply_preset
        params = {'expiry': '21032026', 'initial_lots': 3}
        result = apply_preset(params, 'UNKNOWN_PRESET')
        assert result == params  # unchanged

    @pytest.mark.sealed
    def test_c_ap_4_short_straddle_no_expiry_returns_unchanged(self):
        from webui.backend.routes.mmm.mmm_dte_presets import apply_preset
        params = {'initial_lots': 1}  # no expiry
        result = apply_preset(params, 'STRADDLE_WITH_ADJUSTMENT')
        assert result == params  # returned unchanged

    @pytest.mark.sealed
    def test_c_ap_5_short_straddle_valid_hours(self):
        from webui.backend.routes.mmm.mmm_dte_presets import apply_preset
        params = {'expiry': '21032050', 'initial_lots': 1}  # dummy expiry
        # Mock compute_total_dte_hours to return controlled 5.0
        with patch('webui.backend.routes.mmm.mmm_dte_presets.compute_total_dte_hours',
                   return_value=5.0):
            result = apply_preset(params, 'STRADDLE_WITH_ADJUSTMENT')
        # dte_category comes from preset (not 'STRADDLE_WITH_ADJUSTMENT')
        assert result['dte_category'] == '0DTE'
        # Source tracked for UI
        assert result['_preset_source'] == 'STRADDLE_WITH_ADJUSTMENT'
        # User params preserved
        assert result['initial_lots'] == 1

    @pytest.mark.sealed
    def test_c_ap_6_short_straddle_hours_below_2_returns_unchanged(self):
        from webui.backend.routes.mmm.mmm_dte_presets import apply_preset
        params = {'expiry': '21032026', 'initial_lots': 1}
        # Hours < 1 → build_straddle_adjustment_preset raises ValueError → caught, params returned
        with patch('webui.backend.routes.mmm.mmm_dte_presets.compute_total_dte_hours',
                   return_value=0.5):
            result = apply_preset(params, 'STRADDLE_WITH_ADJUSTMENT')
        assert '_preset_source' not in result
        assert result.get('initial_lots') == 1


# =============================================================================
# build_straddle_adjustment_preset
# =============================================================================

class TestBuildShortStraddlePreset:

    @pytest.mark.sealed
    def test_c_bss_1_below_1h_raises(self):
        from webui.backend.routes.mmm.mmm_dte_presets import build_straddle_adjustment_preset
        with pytest.raises(ValueError, match='1h'):
            build_straddle_adjustment_preset(0.9)

    @pytest.mark.sealed
    def test_c_bss_2_above_24h_does_not_raise(self):
        from webui.backend.routes.mmm.mmm_dte_presets import build_straddle_adjustment_preset
        # H > 24 now produces a warning, not an error
        result = build_straddle_adjustment_preset(25.0)
        assert isinstance(result, dict)
        assert 'dte_category' in result

    @pytest.mark.sealed
    def test_c_bss_3_valid_h5_returns_complete_dict(self):
        from webui.backend.routes.mmm.mmm_dte_presets import build_straddle_adjustment_preset
        result = build_straddle_adjustment_preset(5.0)
        assert isinstance(result, dict)
        # Key sections present
        for key in ('dte_category', 'max_loss_amount', 'adjustment_interval',
                    'wind_down_enabled', 'straddle_roll_enabled',
                    'atm_shield_enabled', 'perp_hedge_enabled'):
            assert key in result, f"Missing key: {key}"

    @pytest.mark.sealed
    def test_c_bss_4_max_loss_amount_3000(self):
        """BUG FIX: was 3.0 (USD), should be 3000.0."""
        from webui.backend.routes.mmm.mmm_dte_presets import build_straddle_adjustment_preset
        result = build_straddle_adjustment_preset(5.0)
        assert result['max_loss_amount'] == 3000.0, (
            f"max_loss_amount={result['max_loss_amount']!r} — should be 3000.0 (bug fix: was 3.0)"
        )

    @pytest.mark.sealed
    def test_c_bss_5_dte_category_is_0dte(self):
        from webui.backend.routes.mmm.mmm_dte_presets import build_straddle_adjustment_preset
        result = build_straddle_adjustment_preset(5.0)
        assert result['dte_category'] == '0DTE'

    @pytest.mark.sealed
    def test_c_bss_6_scaled_params_within_clamp_bounds_for_h5(self):
        """H=5.0 → check that clamped/scaled params are within expected ranges."""
        from webui.backend.routes.mmm.mmm_dte_presets import build_straddle_adjustment_preset
        result = build_straddle_adjustment_preset(5.0)
        # max_adjustments: clamp(round(5*4)=20, 10, 50) = 20
        assert result['max_adjustments'] == 20
        # wind_down_enabled is False (disabled — fights roll mechanism)
        assert result['wind_down_enabled'] is False
        # straddle_roll_trigger_pct: round(clamp(0.4+5*0.05=0.65, 0.5, 1.5), 2) = 0.65
        assert abs(result['straddle_roll_trigger_pct'] - 0.65) < 0.01
        # ATM shield disabled for straddle (both legs start at spot)
        assert result['atm_shield_enabled'] is False
        # Perp hedge disabled
        assert result['perp_hedge_enabled'] is False
        # straddle_roll_max_per_session NOT in preset (operator must set explicitly)
        assert 'straddle_roll_max_per_session' not in result
        # harvest_enabled is False (disabled — fights roll)
        assert result['harvest_enabled'] is False
