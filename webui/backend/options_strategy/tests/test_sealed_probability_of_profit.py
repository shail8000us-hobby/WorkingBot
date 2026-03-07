"""
Contract Test: probability_of_profit
========================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of ProbabilityAnalyzer.probability_of_profit.
Uses deterministic math — lognormal distribution with fixed inputs.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/options_strategy/tests/test_sealed_probability_of_profit.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
from webui.backend.options_strategy.probability_analyzer import ProbabilityAnalyzer

pytestmark = pytest.mark.sealed

# A short OTM call: profit if price < strike at expiry
#   site=82000, strike=100000 → deeply OTM → value=0 at expiry → receive premium
_SHORT_OTM_CALL = [{'strike': 100_000, 'option_type': 'call', 'side': 'sell', 'quantity': 1, 'entry_price': 100.0}]

# A long OTM call: loss if price < strike at expiry
_LONG_OTM_CALL  = [{'strike': 100_000, 'option_type': 'call', 'side': 'buy',  'quantity': 1, 'entry_price': 100.0}]

_SPOT       = 82_000.0
_VOL        = 0.80   # 80% IV for BTC
_T_1_MONTH  = 30 / 365  # ~1 month to expiry


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Returns correct dict shape
# ---------------------------------------------------------------------------

def test_returns_correct_shape():
    """Must return dict with pop, expected_value, value_at_risk_95, conditional_var_95."""
    result = ProbabilityAnalyzer.probability_of_profit(
        _SHORT_OTM_CALL, _SPOT, _VOL, _T_1_MONTH
    )
    assert 'pop'               in result
    assert 'expected_value'    in result
    assert 'value_at_risk_95'  in result
    assert 'conditional_var_95' in result


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — PoP is always in [0, 1]
# ---------------------------------------------------------------------------

def test_pop_is_between_0_and_1():
    """pop must never be outside the [0, 1] range."""
    result = ProbabilityAnalyzer.probability_of_profit(
        _SHORT_OTM_CALL, _SPOT, _VOL, _T_1_MONTH
    )
    assert 0.0 <= result['pop'] <= 1.0


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — At expiry (time=0): profitable short → pop = 1.0
# ---------------------------------------------------------------------------

def test_at_expiry_profitable_position_gives_pop_1():
    """When time_to_expiry=0 and position is profitable, pop must be 1.0."""
    # Short OTM call at spot below strike: at expiry, call is worthless → seller profits
    result = ProbabilityAnalyzer.probability_of_profit(
        _SHORT_OTM_CALL, _SPOT, _VOL, time_to_expiry=0
    )
    assert result['pop'] == 1.0


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — At expiry (time=0): losing long OTM call → pop = 0.0
# ---------------------------------------------------------------------------

def test_at_expiry_losing_position_gives_pop_0():
    """When time_to_expiry=0 and position is at a loss, pop must be 0.0."""
    # Long OTM call at spot below strike: at expiry, call worthless → buyer loses premium
    result = ProbabilityAnalyzer.probability_of_profit(
        _LONG_OTM_CALL, _SPOT, _VOL, time_to_expiry=0
    )
    assert result['pop'] == 0.0


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — expected_value is a float (not None)
# ---------------------------------------------------------------------------

def test_expected_value_is_float():
    """expected_value must be a float."""
    result = ProbabilityAnalyzer.probability_of_profit(
        _SHORT_OTM_CALL, _SPOT, _VOL, _T_1_MONTH
    )
    assert isinstance(result['expected_value'], float)


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Deterministic: same inputs give same result
# ---------------------------------------------------------------------------

def test_is_deterministic():
    """Same inputs must produce identical results on repeated calls."""
    r1 = ProbabilityAnalyzer.probability_of_profit(_SHORT_OTM_CALL, _SPOT, _VOL, _T_1_MONTH)
    r2 = ProbabilityAnalyzer.probability_of_profit(_SHORT_OTM_CALL, _SPOT, _VOL, _T_1_MONTH)
    assert r1['pop'] == r2['pop']
    assert r1['expected_value'] == r2['expected_value']


# ---------------------------------------------------------------------------
# CONTRACT TEST 7 — Works for put options too (no crash)
# ---------------------------------------------------------------------------

def test_works_for_put_options():
    """Must work correctly for put option positions without raising."""
    short_otm_put = [{'strike': 50_000, 'option_type': 'put', 'side': 'sell', 'quantity': 1, 'entry_price': 50.0}]
    result = ProbabilityAnalyzer.probability_of_profit(
        short_otm_put, _SPOT, _VOL, _T_1_MONTH
    )
    assert 0.0 <= result['pop'] <= 1.0
