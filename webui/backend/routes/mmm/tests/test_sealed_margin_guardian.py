"""
Contract tests for Margin Guardian pure logic functions

SEALED — v1.0.0 — March 14, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Functions:
  tier_severity(tier) -> int
  evaluate_margin_tier(utilization_pct, params) -> Dict
  estimate_lots_to_close(session, current_util, target_util) -> Dict

File: webui/backend/routes/mmm/mmm_margin_guardian.py

Verified working: session mmm15mar26-1 — algo closed due to margin trigger.

--- tier_severity contracts ---
  C1.  GREEN=0, YELLOW=1, ORANGE=2, RED=3, CRITICAL=4 (exact order)
  C2.  Unknown tier → -1 (never raises)

--- evaluate_margin_tier contracts ---
  C3.  util < green_pct → GREEN, actions=['normal']
  C4.  util >= yellow_pct (but < orange) → YELLOW, actions=['block_sells']
  C5.  util >= orange_pct (but < red) → ORANGE, actions=['block_sells', 'auto_wind_down']
  C6.  util >= red_pct (but < critical) → RED, actions=['emergency_reduce']
  C7.  util >= critical_pct → CRITICAL, actions=['survival_close_all']
  C8.  headroom_pct = next_threshold - util (clamped to 0)
  C9.  CRITICAL tier → next_threshold=None, headroom=0.0
  C10. threshold boundaries are INCLUSIVE (>= crosses the tier, not >)
  C11. falls back to MARGIN_PARAM_DEFAULTS when params keys absent
  C12. utilization_pct in result is rounded to 2 decimal places
  C13. result always has all required keys: tier, utilization_pct, actions,
       threshold_crossed, next_threshold, headroom_pct

--- estimate_lots_to_close contracts ---
  C14. current <= target → {'ce': 0, 'pe': 0} (no action needed)
  C15. proportional: reduction_ratio = (current - target) / current, ceil applied
  C16. minimum reduction_ratio is 0.1 (floor) to ensure progress
  C17. result never exceeds total lots available per side
  C18. empty session (no ce/pe keys) → {'ce': 0, 'pe': 0}
  C19. frozen_positions lots are included in total (frozen can also be closed)
"""

import math
import pytest

pytestmark = pytest.mark.sealed

from webui.backend.routes.mmm.mmm_margin_guardian import (
    tier_severity,
    evaluate_margin_tier,
    estimate_lots_to_close,
    TIER_GREEN, TIER_YELLOW, TIER_ORANGE, TIER_RED, TIER_CRITICAL,
    MARGIN_PARAM_DEFAULTS,
)

# ─── Default params (matches the UI screenshot: 50/60/75/85/90) ────────────

DEFAULT_PARAMS = {
    'margin_green_pct':    50.0,
    'margin_yellow_pct':   60.0,
    'margin_orange_pct':   75.0,
    'margin_red_pct':      85.0,
    'margin_critical_pct': 90.0,
    'margin_target_pct':   50.0,
}


# ═══════════════════════════════════════════════════════════════
# tier_severity contracts
# ═══════════════════════════════════════════════════════════════

def test_c1_tier_severity_order():
    assert tier_severity(TIER_GREEN)    == 0
    assert tier_severity(TIER_YELLOW)   == 1
    assert tier_severity(TIER_ORANGE)   == 2
    assert tier_severity(TIER_RED)      == 3
    assert tier_severity(TIER_CRITICAL) == 4


def test_c2_unknown_tier_returns_minus_one():
    assert tier_severity('UNKNOWN') == -1
    assert tier_severity('')        == -1
    assert tier_severity('green')   == -1   # case-sensitive


# ═══════════════════════════════════════════════════════════════
# evaluate_margin_tier contracts
# ═══════════════════════════════════════════════════════════════

def test_c3_below_green_returns_green():
    result = evaluate_margin_tier(30.0, DEFAULT_PARAMS)
    assert result['tier'] == TIER_GREEN
    assert result['actions'] == ['normal']


def test_c3b_exactly_at_green_still_green():
    """50.0 < yellow(60) → GREEN"""
    result = evaluate_margin_tier(50.0, DEFAULT_PARAMS)
    assert result['tier'] == TIER_GREEN


def test_c4_at_yellow_threshold_returns_yellow():
    result = evaluate_margin_tier(60.0, DEFAULT_PARAMS)
    assert result['tier'] == TIER_YELLOW
    assert result['actions'] == ['block_sells']


def test_c4b_just_above_yellow_returns_yellow():
    result = evaluate_margin_tier(60.1, DEFAULT_PARAMS)
    assert result['tier'] == TIER_YELLOW
    assert result['actions'] == ['block_sells']


def test_c5_at_orange_threshold_returns_orange():
    result = evaluate_margin_tier(75.0, DEFAULT_PARAMS)
    assert result['tier'] == TIER_ORANGE
    assert 'block_sells' in result['actions']
    assert 'auto_wind_down' in result['actions']


def test_c5b_orange_has_both_actions():
    result = evaluate_margin_tier(80.0, DEFAULT_PARAMS)
    assert result['tier'] == TIER_ORANGE
    assert set(result['actions']) == {'block_sells', 'auto_wind_down'}


def test_c6_at_red_threshold_returns_red():
    result = evaluate_margin_tier(85.0, DEFAULT_PARAMS)
    assert result['tier'] == TIER_RED
    assert result['actions'] == ['emergency_reduce']


def test_c6b_just_below_critical_still_red():
    result = evaluate_margin_tier(89.9, DEFAULT_PARAMS)
    assert result['tier'] == TIER_RED


def test_c7_at_critical_threshold_returns_critical():
    result = evaluate_margin_tier(90.0, DEFAULT_PARAMS)
    assert result['tier'] == TIER_CRITICAL
    assert result['actions'] == ['survival_close_all']


def test_c7b_above_100_still_critical():
    """Can exceed 100 in liquidation territory — should still be CRITICAL."""
    result = evaluate_margin_tier(110.0, DEFAULT_PARAMS)
    assert result['tier'] == TIER_CRITICAL


def test_c8_headroom_is_next_minus_util():
    """At 65% util, orange threshold=75 → headroom = 75 - 65 = 10."""
    result = evaluate_margin_tier(65.0, DEFAULT_PARAMS)
    assert result['tier'] == TIER_YELLOW
    assert abs(result['headroom_pct'] - 10.0) < 0.01


def test_c8b_headroom_never_negative():
    """util=89.99, red=85, critical=90 → headroom = 90 - 89.99 = 0.01 (not negative)."""
    result = evaluate_margin_tier(89.99, DEFAULT_PARAMS)
    assert result['headroom_pct'] >= 0.0


def test_c9_critical_next_threshold_is_none():
    result = evaluate_margin_tier(95.0, DEFAULT_PARAMS)
    assert result['tier'] == TIER_CRITICAL
    assert result['next_threshold'] is None
    assert result['headroom_pct'] == 0.0


def test_c10_boundary_inclusive():
    """Exactly at each threshold crosses into that tier (>=)."""
    assert evaluate_margin_tier(60.0, DEFAULT_PARAMS)['tier'] == TIER_YELLOW
    assert evaluate_margin_tier(75.0, DEFAULT_PARAMS)['tier'] == TIER_ORANGE
    assert evaluate_margin_tier(85.0, DEFAULT_PARAMS)['tier'] == TIER_RED
    assert evaluate_margin_tier(90.0, DEFAULT_PARAMS)['tier'] == TIER_CRITICAL


def test_c11_uses_defaults_when_params_empty():
    """Empty params → falls back to MARGIN_PARAM_DEFAULTS values."""
    # MARGIN_PARAM_DEFAULTS: yellow=60, orange=75, red=85, critical=90
    result = evaluate_margin_tier(91.0, {})
    assert result['tier'] == TIER_CRITICAL

    result2 = evaluate_margin_tier(55.0, {})
    assert result2['tier'] == TIER_GREEN


def test_c12_utilization_rounded_to_2dp():
    result = evaluate_margin_tier(72.1234567, DEFAULT_PARAMS)
    assert result['utilization_pct'] == round(72.1234567, 2)


def test_c13_result_has_all_required_keys():
    result = evaluate_margin_tier(50.0, DEFAULT_PARAMS)
    for key in ('tier', 'utilization_pct', 'actions', 'threshold_crossed',
                'next_threshold', 'headroom_pct'):
        assert key in result, f"Missing key: {key}"


# ═══════════════════════════════════════════════════════════════
# estimate_lots_to_close contracts
# ═══════════════════════════════════════════════════════════════

def _session(ce_active=0, pe_active=0, ce_frozen=None, pe_frozen=None):
    """Build minimal session for estimate_lots_to_close."""
    return {
        'ce': {
            'active_lots': ce_active,
            'frozen_positions': ce_frozen or [],
        },
        'pe': {
            'active_lots': pe_active,
            'frozen_positions': pe_frozen or [],
        },
    }


def test_c14_no_action_when_current_at_or_below_target():
    session = _session(ce_active=50, pe_active=50)
    assert estimate_lots_to_close(session, 50.0, 50.0) == {'ce': 0, 'pe': 0}
    assert estimate_lots_to_close(session, 40.0, 50.0) == {'ce': 0, 'pe': 0}


def test_c15_proportional_calculation():
    """
    current=80, target=50, ratio=(80-50)/80 = 0.375
    CE=100 lots → ceil(100 * 0.375) = 38
    PE=80 lots  → ceil(80  * 0.375) = 30
    """
    session = _session(ce_active=100, pe_active=80)
    result = estimate_lots_to_close(session, 80.0, 50.0)
    ratio = (80.0 - 50.0) / 80.0
    assert result['ce'] == math.ceil(100 * ratio)
    assert result['pe'] == math.ceil(80 * ratio)


def test_c16_minimum_ratio_0_1():
    """
    current=55, target=54.5 → raw_ratio ≈ 0.009 < 0.1 → floor to 0.1
    CE=10 lots → ceil(10 * 0.1) = 1
    """
    session = _session(ce_active=10, pe_active=10)
    result = estimate_lots_to_close(session, 55.0, 54.5)
    # ratio would be 0.5/55 ≈ 0.009 → floored to 0.1 → ceil(10*0.1)=1
    assert result['ce'] == 1
    assert result['pe'] == 1


def test_c17_never_exceeds_total_lots():
    """If ratio would produce more lots than available, cap at available."""
    # current=100, target=0 → ratio=(100-0)/100=1.0 → 100% of lots
    # With 10 active, would want 10 → exactly at cap (ok)
    session = _session(ce_active=5, pe_active=3)
    result = estimate_lots_to_close(session, 100.0, 0.0)
    assert result['ce'] <= 5
    assert result['pe'] <= 3


def test_c18_empty_session_returns_zero():
    result = estimate_lots_to_close({}, 80.0, 50.0)
    assert result == {'ce': 0, 'pe': 0}


def test_c19_frozen_lots_included_in_total():
    """
    CE: active=10, frozen=5 → total=15
    current=80, target=50, ratio=0.375 → ceil(15 * 0.375) = ceil(5.625) = 6
    """
    session = _session(
        ce_active=10,
        ce_frozen=[{'lots': 5}],
        pe_active=0,
    )
    result = estimate_lots_to_close(session, 80.0, 50.0)
    ratio = max((80.0 - 50.0) / 80.0, 0.1)
    expected_ce = min(math.ceil(15 * ratio), 15)
    assert result['ce'] == expected_ce
