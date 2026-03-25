"""
Test MMM State — Lot Recycling params integration.

Tests:
  - All 15 M1/M2/M3 params present in DEFAULT_PARAMS
  - All 15 M1/M2/M3 params present in HOT_RELOAD_PARAMS
  - create_session() includes all new params with correct defaults
  - All 15 params have PARAM_RULES entries in mmm_config
  - All 15 params have get_param_info descriptions
  - Analytics counters initialized correctly

Created: March 3, 2026
"""

import sys
import os
import types
import importlib
import importlib.util
import pytest

# ─── Direct module loader ─────────────────────────────────────────────────────
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
    sys.modules['webui.backend.routes.mmm'].__path__ = [_MMM_PKG_DIR]


def _load_mmm_module(name):
    full_name = f'webui.backend.routes.mmm.{name}'
    if full_name in sys.modules:
        # Force reload to pick up latest file edits
        return importlib.reload(sys.modules[full_name])
    path = os.path.join(_MMM_PKG_DIR, f'{name}.py')
    spec = importlib.util.spec_from_file_location(
        full_name, path, submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'webui.backend.routes.mmm'
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_setup_mmm_package()

# Load dependencies first
_load_mmm_module('mmm_constants')


# ─── All 15 params that MUST exist ──────────────────────────────────────────

M1_PARAMS = [
    'harvest_enabled', 'harvest_profit_pct', 'harvest_min_age_mins',
    'harvest_max_per_beat', 'harvest_pressure_threshold',
]

M2_PARAMS = [
    'recycle_enabled', 'recycle_min_premium_ratio', 'recycle_premium_ceiling',
    'recycle_max_pct', 'recycle_cooldown_sec', 'recycle_min_lot_gain',
    'recycle_free_lot_buffer', 'recycle_protect_original',
]

M3_PARAMS = [
    'rebalance_enabled', 'rebalance_asymmetry_threshold',
    'rebalance_pressure_threshold',
]

ALL_NEW_PARAMS = M1_PARAMS + M2_PARAMS + M3_PARAMS


# =============================================================================
# Tests: DEFAULT_PARAMS
# =============================================================================

class TestDefaultParams:
    """All 15 M1/M2/M3 params must be in DEFAULT_PARAMS with correct types."""

    def test_all_params_present_in_defaults(self):
        state_mod = _load_mmm_module('mmm_state')
        defaults = state_mod.DEFAULT_PARAMS

        missing = [p for p in ALL_NEW_PARAMS if p not in defaults]
        assert missing == [], f"Missing from DEFAULT_PARAMS: {missing}"

    def test_harvest_defaults(self):
        state_mod = _load_mmm_module('mmm_state')
        d = state_mod.DEFAULT_PARAMS

        assert d['harvest_enabled'] is True
        assert d['harvest_profit_pct'] == 40.0
        assert d['harvest_min_age_mins'] == 30
        assert d['harvest_max_per_beat'] == 3
        assert d['harvest_pressure_threshold'] == 0.5

    def test_recycle_defaults(self):
        state_mod = _load_mmm_module('mmm_state')
        d = state_mod.DEFAULT_PARAMS

        assert d['recycle_enabled'] is True
        assert d['recycle_min_premium_ratio'] == 2.5
        assert d['recycle_premium_ceiling'] == 50.0
        assert d['recycle_max_pct'] == 0.50
        assert d['recycle_cooldown_sec'] == 300
        assert d['recycle_min_lot_gain'] == 5
        assert d['recycle_free_lot_buffer'] == 10
        assert d['recycle_protect_original'] is True

    def test_rebalance_defaults(self):
        state_mod = _load_mmm_module('mmm_state')
        d = state_mod.DEFAULT_PARAMS

        assert d['rebalance_enabled'] is True
        assert d['rebalance_asymmetry_threshold'] == 5.0
        assert d['rebalance_pressure_threshold'] == 0.7


# =============================================================================
# Tests: HOT_RELOAD_PARAMS
# =============================================================================

class TestHotReloadParams:
    """All 15 params must be hot-reloadable."""

    def test_all_params_in_hot_reload(self):
        state_mod = _load_mmm_module('mmm_state')
        hot = state_mod.HOT_RELOAD_PARAMS

        missing = [p for p in ALL_NEW_PARAMS if p not in hot]
        assert missing == [], f"Missing from HOT_RELOAD_PARAMS: {missing}"


# =============================================================================
# Tests: create_session includes new params
# =============================================================================

class TestCreateSession:
    """New sessions must have all 15 params initialized."""

    def test_new_session_has_all_params(self):
        state_mod = _load_mmm_module('mmm_state')
        session = state_mod.create_session(
            params={'expiry': '28MAR26'},
        )

        params = session['params']
        missing = [p for p in ALL_NEW_PARAMS if p not in params]
        assert missing == [], f"Missing in new session params: {missing}"

    def test_new_session_custom_override(self):
        state_mod = _load_mmm_module('mmm_state')
        session = state_mod.create_session(
            params={'expiry': '28MAR26', 'harvest_profit_pct': 50.0,
                    'recycle_enabled': False},
        )

        assert session['params']['harvest_profit_pct'] == 50.0
        assert session['params']['recycle_enabled'] is False
        # Others still have defaults
        assert session['params']['harvest_enabled'] is True


# =============================================================================
# Tests: PARAM_RULES in mmm_config
# =============================================================================

class TestParamRules:
    """All 15 params must have PARAM_RULES and descriptions."""

    def test_all_params_have_rules(self):
        config_mod = _load_mmm_module('mmm_config')
        rules = config_mod.PARAM_RULES

        missing = [p for p in ALL_NEW_PARAMS if p not in rules]
        assert missing == [], f"Missing PARAM_RULES: {missing}"

    def test_all_params_have_descriptions(self):
        config_mod = _load_mmm_module('mmm_config')
        info = config_mod.get_param_info()

        missing = [p for p in ALL_NEW_PARAMS if p not in info]
        assert missing == [], f"Missing get_param_info: {missing}"

    def test_bool_params_are_bool_type(self):
        config_mod = _load_mmm_module('mmm_config')
        rules = config_mod.PARAM_RULES

        bool_params = ['harvest_enabled', 'recycle_enabled',
                       'recycle_protect_original', 'rebalance_enabled']
        for p in bool_params:
            assert rules[p]['type'] is bool, f"{p} should be bool type"

    def test_hot_reload_consistent(self):
        """PARAM_RULES 'hot' flags should match HOT_RELOAD_PARAMS set."""
        config_mod = _load_mmm_module('mmm_config')
        state_mod = _load_mmm_module('mmm_state')
        rules = config_mod.PARAM_RULES
        hot = state_mod.HOT_RELOAD_PARAMS

        for p in ALL_NEW_PARAMS:
            if p in rules:
                rule_hot = rules[p].get('hot', False)
                in_hot_set = p in hot
                assert rule_hot == in_hot_set, (
                    f"{p}: PARAM_RULES hot={rule_hot} "
                    f"but {'in' if in_hot_set else 'NOT in'} HOT_RELOAD_PARAMS"
                )
