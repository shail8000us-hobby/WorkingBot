#!/usr/bin/env python3
"""Test tiered trend guard implementation."""
import sys
sys.path.insert(0, '.')

# ── 1. Import checks ──
from webui.backend.routes.mmm.mmm_regime import (
    MMMRegimeEngine, TREND_TIER_NONE, TREND_TIER_ALERT, TREND_TIER_GUARD,
    TREND_TIER_BLOCK, TREND_TIER_WIND_DOWN,
    ACTION_NORMAL, ACTION_WARN, ACTION_BLOCK_CE_SELLS, ACTION_BLOCK_PE_SELLS,
    ACTION_BLOCK_ALL_SELLS, ACTION_FORCE_REDUCE,
    _check_acceleration, _compute_trend_tier,
)
print('OK mmm_regime.py — all tier imports successful')
print(f'   Tiers: NONE={TREND_TIER_NONE} ALERT={TREND_TIER_ALERT} GUARD={TREND_TIER_GUARD} BLOCK={TREND_TIER_BLOCK} WIND_DOWN={TREND_TIER_WIND_DOWN}')

from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS, HOT_RELOAD_PARAMS
defaults = dict(DEFAULT_PARAMS)
tier_keys = [k for k in defaults if 'tier' in k or 'acceleration' in k]
print(f'OK mmm_state.py — tier params: {tier_keys}')
hot_tier = [p for p in HOT_RELOAD_PARAMS if 'tier' in p or 'acceleration' in p]
print(f'   Hot-reload: {hot_tier}')

from webui.backend.routes.mmm.mmm_config import validate_params
print('OK mmm_config.py — imports successful')

# ── 2. Tier ordering validation (valid) ──
test = dict(defaults)
test['trend_tier1_pct'] = 0.5
test['trend_tier2_pct'] = 1.0
test['trend_tier3_pct'] = 1.5
test['trend_tier4_pct'] = 2.0
clean, warns = validate_params(test)
tier_warns = [w for w in warns if 'tier' in w.lower()]
assert len(tier_warns) == 0, f'Expected no warnings, got: {tier_warns}'
print('OK Tier ordering validation — valid ordering passes')

# ── 3. Tier ordering validation (invalid) ──
test2 = dict(defaults)
test2['trend_tier1_pct'] = 1.5
test2['trend_tier2_pct'] = 1.0
clean2, warns2 = validate_params(test2)
tier_warns2 = [w for w in warns2 if 'tier' in w.lower()]
assert len(tier_warns2) > 0, f'Expected tier ordering warning, got none'
print(f'OK Tier ordering validation — invalid ordering caught: {tier_warns2[0]}')

# ── 4. _compute_trend_tier tests ──
params = dict(defaults)
params['trend_tier1_pct'] = 0.5
params['trend_tier2_pct'] = 1.0
params['trend_tier3_pct'] = 1.5
params['trend_tier4_pct'] = 2.0

# With EMA confirming (ema_slope_confirms=True)
assert _compute_trend_tier(0.3, True, False, params) == TREND_TIER_NONE
assert _compute_trend_tier(0.5, True, False, params) == TREND_TIER_ALERT
assert _compute_trend_tier(0.7, True, False, params) == TREND_TIER_ALERT
assert _compute_trend_tier(1.0, True, False, params) == TREND_TIER_GUARD
assert _compute_trend_tier(1.3, True, False, params) == TREND_TIER_GUARD
assert _compute_trend_tier(1.5, True, False, params) == TREND_TIER_BLOCK
assert _compute_trend_tier(1.8, True, False, params) == TREND_TIER_BLOCK
assert _compute_trend_tier(2.0, True, False, params) == TREND_TIER_WIND_DOWN
assert _compute_trend_tier(3.0, True, False, params) == TREND_TIER_WIND_DOWN
print('OK _compute_trend_tier — all threshold tests pass (EMA confirming)')

# Tier 1 requires EMA or acceleration — without both, stays NONE
assert _compute_trend_tier(0.6, False, False, params) == TREND_TIER_NONE
print('OK _compute_trend_tier — Tier 1 blocked without EMA or acceleration')

# Tier 1 with acceleration bypass (fast move)
assert _compute_trend_tier(0.6, False, True, params) == TREND_TIER_ALERT
print('OK _compute_trend_tier — Tier 1 fires with acceleration bypass')

# Tiers 2+ fire without EMA
assert _compute_trend_tier(1.0, False, False, params) == TREND_TIER_GUARD
assert _compute_trend_tier(1.5, False, False, params) == TREND_TIER_BLOCK
assert _compute_trend_tier(2.0, False, False, params) == TREND_TIER_WIND_DOWN
print('OK _compute_trend_tier — Tiers 2-4 fire without EMA')

# ── 5. RegimeEngine instantiation ──
engine = MMMRegimeEngine()
print('OK RegimeEngine instantiation')

# ── 6. Session state init check ──
from webui.backend.routes.mmm.mmm_state import create_session
# Just check the function exists and has our fields in its source
import inspect
src = inspect.getsource(create_session)
assert '_trend_tier' in src, '_trend_tier not in create_session'
assert '_trend_direction' in src, '_trend_direction not in create_session'
assert '_trend_acceleration_move_pct' in src, '_trend_acceleration_move_pct not in create_session'
print('OK Session state init — _trend_tier, _trend_direction, _trend_acceleration_move_pct present')

# ── 7. Engine lot reduction check ──
from webui.backend.routes.mmm.mmm_engine import MMMEngine
src_engine = inspect.getsource(MMMEngine.calculate_lots_to_sell)
assert '_trend_tier' in src_engine, '_trend_tier not referenced in calculate_lots_to_sell'
assert 'trend_tier1_lot_reduction' in src_engine, 'lot reduction param not in calculate_lots_to_sell'
print('OK calculate_lots_to_sell — trend tier lot reduction integrated')

print()
print('=' * 60)
print('ALL TESTS PASSED — Tiered Trend Guard implementation verified')
print('=' * 60)
