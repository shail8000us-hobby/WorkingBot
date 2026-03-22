"""
Contract tests for MMM Config — T3-3

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Functions covered:
  validate_params(params, hot_only) -> (validated_dict, errors_list)
  _interdependency_checks(validated, errors)    (via validate_params)
  get_hot_reload_params() -> Set[str]
  get_param_info() -> Dict[str, Dict]

File: webui/backend/routes/mmm/mmm_config.py

--- validate_params contracts ---
C-VP-1: valid int param → coerced to int, empty errors
C-VP-2: valid float param → coerced to float, empty errors
C-VP-3: bool string 'true'/'1'/'yes'/'on' → True; other strings → False
C-VP-4: unknown param key → silently skipped (not in returned validated dict)
C-VP-5: hot_only=True + non-hot param → error, key absent from validated
C-VP-6: value below minimum → error appended
C-VP-7: value above maximum → error appended
C-VP-8: invalid type string for int → error appended
C-VP-9: empty params dict → returns ({},[]) with no crash

--- _interdependency_checks (via validate_params) contracts ---
C-IC-1: wind_down_close_threshold < close_at_threshold → error
C-IC-2: wind_down_close_threshold >= close_at_threshold → no error
C-IC-3: margin tiers out of order → error (e.g. yellow >= orange)
C-IC-4: perp_hedge_delta_threshold <= rebalance_band → error
C-IC-5: perp_hedge_delta_threshold > rebalance_band → no error
C-IC-6: gamma_soft_limit >= gamma_hard_limit → error

--- get_hot_reload_params contracts ---
C-HR-1: returns a set (not list/dict)
C-HR-2: adjustment_interval is hot-reloadable
C-HR-3: initial_lots is NOT hot-reloadable

--- get_param_info contracts ---
C-PI-1: returns a non-empty dict
C-PI-2: each entry has 'type', 'min', 'max', 'hot' keys
"""

import pytest


# =============================================================================
# validate_params
# =============================================================================

class TestValidateParams:

    @pytest.mark.sealed
    def test_c_vp_1_valid_int_coerced(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        validated, errors = validate_params({'initial_lots': '10'})
        assert errors == []
        assert validated['initial_lots'] == 10
        assert isinstance(validated['initial_lots'], int)

    @pytest.mark.sealed
    def test_c_vp_2_valid_float_coerced(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        validated, errors = validate_params({'min_trigger_move': '15.5'})
        assert errors == []
        assert abs(validated['min_trigger_move'] - 15.5) < 0.001
        assert isinstance(validated['min_trigger_move'], float)

    @pytest.mark.sealed
    def test_c_vp_3_bool_string_coercion(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        for truthy in ('true', '1', 'yes', 'on', 'TRUE', 'True'):
            validated, _ = validate_params({'wind_down_enabled': truthy})
            assert validated['wind_down_enabled'] is True, f"Expected True for {truthy!r}"
        for falsy in ('false', '0', 'no', 'off', 'nope'):
            validated, _ = validate_params({'wind_down_enabled': falsy})
            assert validated['wind_down_enabled'] is False, f"Expected False for {falsy!r}"

    @pytest.mark.sealed
    def test_c_vp_4_unknown_key_silently_skipped(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        validated, errors = validate_params({'_internal_flag': True, 'adjustment_interval': 300})
        assert '_internal_flag' not in validated
        assert 'adjustment_interval' in validated
        assert errors == []

    @pytest.mark.sealed
    def test_c_vp_5_hot_only_rejects_non_hot_param(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        # initial_lots is hot=False — should be rejected when hot_only=True
        validated, errors = validate_params({'initial_lots': 5}, hot_only=True)
        assert len(errors) == 1
        assert 'initial_lots' in errors[0]
        assert 'initial_lots' not in validated

    @pytest.mark.sealed
    def test_c_vp_6_below_minimum_error(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        # adjustment_interval min=10 → 5 is below minimum
        _, errors = validate_params({'adjustment_interval': 5})
        assert any('adjustment_interval' in e and 'minimum' in e for e in errors)

    @pytest.mark.sealed
    def test_c_vp_7_above_maximum_error(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        # initial_lots max=1000 → 9999 is above maximum
        _, errors = validate_params({'initial_lots': 9999})
        assert any('initial_lots' in e and 'maximum' in e for e in errors)

    @pytest.mark.sealed
    def test_c_vp_8_invalid_type_error(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        # adjustment_interval is int — passing 'not-a-number' should error
        _, errors = validate_params({'adjustment_interval': 'not-a-number'})
        assert any('adjustment_interval' in e for e in errors)

    @pytest.mark.sealed
    def test_c_vp_9_empty_params_no_crash(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        validated, errors = validate_params({})
        assert validated == {}
        assert errors == []


# =============================================================================
# _interdependency_checks (via validate_params)
# =============================================================================

class TestInterdependencyChecks:

    @pytest.mark.sealed
    def test_c_ic_1_wind_down_below_close_at_error(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        # wind_down_close_threshold=3 < close_at_threshold=5 → error
        _, errors = validate_params({
            'wind_down_close_threshold': 3.0,
            'close_at_threshold': 5.0,
        })
        assert any('wind_down_close_threshold' in e for e in errors)

    @pytest.mark.sealed
    def test_c_ic_2_wind_down_above_close_at_ok(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        _, errors = validate_params({
            'wind_down_close_threshold': 20.0,
            'close_at_threshold': 5.0,
        })
        # No interdependency error about wind_down/close_at ordering
        assert not any('wind_down_close_threshold' in e for e in errors)

    @pytest.mark.sealed
    def test_c_ic_3_margin_tier_ordering_violated(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        # yellow=80 >= orange=70 → violated
        _, errors = validate_params({
            'margin_yellow_pct': 80.0,
            'margin_orange_pct': 70.0,
        })
        assert any('margin' in e.lower() and 'ordering' in e.lower() or
                   'margin_yellow' in e for e in errors)

    @pytest.mark.sealed
    def test_c_ic_4_perp_threshold_below_or_equal_band_error(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        # delta_threshold=0.005 <= rebalance_band=0.005 → error
        _, errors = validate_params({
            'perp_hedge_delta_threshold': 0.005,
            'perp_hedge_rebalance_band': 0.005,
        })
        assert any('perp_hedge_delta_threshold' in e for e in errors)

    @pytest.mark.sealed
    def test_c_ic_5_perp_threshold_above_band_ok(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        _, errors = validate_params({
            'perp_hedge_delta_threshold': 0.02,
            'perp_hedge_rebalance_band': 0.005,
        })
        assert not any('perp_hedge_delta_threshold' in e for e in errors)

    @pytest.mark.sealed
    def test_c_ic_6_gamma_soft_above_hard_error(self):
        from webui.backend.routes.mmm.mmm_config import validate_params
        # soft=100 >= hard=50 → error
        _, errors = validate_params({
            'gamma_soft_limit': 100.0,
            'gamma_hard_limit': 50.0,
        })
        assert any('gamma_soft_limit' in e for e in errors)


# =============================================================================
# get_hot_reload_params
# =============================================================================

class TestGetHotReloadParams:

    @pytest.mark.sealed
    def test_c_hr_1_returns_set(self):
        from webui.backend.routes.mmm.mmm_config import get_hot_reload_params
        result = get_hot_reload_params()
        assert isinstance(result, set)

    @pytest.mark.sealed
    def test_c_hr_2_adjustment_interval_is_hot(self):
        from webui.backend.routes.mmm.mmm_config import get_hot_reload_params
        assert 'adjustment_interval' in get_hot_reload_params()

    @pytest.mark.sealed
    def test_c_hr_3_initial_lots_not_hot(self):
        from webui.backend.routes.mmm.mmm_config import get_hot_reload_params
        assert 'initial_lots' not in get_hot_reload_params()


# =============================================================================
# get_param_info
# =============================================================================

class TestGetParamInfo:

    @pytest.mark.sealed
    def test_c_pi_1_returns_nonempty_dict(self):
        from webui.backend.routes.mmm.mmm_config import get_param_info
        result = get_param_info()
        assert isinstance(result, dict)
        assert len(result) > 0

    @pytest.mark.sealed
    def test_c_pi_2_each_entry_has_required_keys(self):
        from webui.backend.routes.mmm.mmm_config import get_param_info
        for key, info in get_param_info().items():
            for required in ('type', 'min', 'max', 'hot_reload'):
                assert required in info, f"Param '{key}' missing key '{required}'"
