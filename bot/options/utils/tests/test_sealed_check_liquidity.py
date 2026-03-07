"""
Contract Test: check_liquidity
========================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of check_liquidity.
Pure math — no external calls, no mocking needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest bot/options/utils/tests/test_sealed_check_liquidity.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
from bot.options.utils.options_helper import check_liquidity

pytestmark = pytest.mark.sealed


def _ticker(bid, ask, mark):
    return {'quotes': {'best_bid': bid, 'best_ask': ask}, 'mark_price': mark}


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Returns correct dict shape
# ---------------------------------------------------------------------------

def test_returns_correct_shape():
    """Must return dict with is_liquid, spread_pct, spread, reason."""
    result = check_liquidity(_ticker(95, 105, 100))
    assert 'is_liquid'   in result
    assert 'spread_pct'  in result
    assert 'spread'      in result
    assert 'reason'      in result


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Tight spread (< 10%) is liquid
# ---------------------------------------------------------------------------

def test_tight_spread_is_liquid():
    """Spread < 10% of mark price must return is_liquid = True."""
    # spread = 105 - 95 = 10, spread_pct = 10/100 = 10% — right on boundary, NOT liquid
    # Use tighter spread: bid=96, ask=103, mark=100 → spread=7, 7% < 10% → liquid
    result = check_liquidity(_ticker(96, 103, 100))
    assert result['is_liquid'] is True


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Wide spread (> 10%) is not liquid
# ---------------------------------------------------------------------------

def test_wide_spread_is_not_liquid():
    """Spread > 10% of mark price must return is_liquid = False."""
    # bid=80, ask=125, mark=100 → spread=45, 45% > 10% → illiquid
    result = check_liquidity(_ticker(80, 125, 100))
    assert result['is_liquid'] is False


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Zero mark price returns safe illiquid result (no ZeroDivision)
# ---------------------------------------------------------------------------

def test_zero_mark_price_returns_illiquid():
    """Mark price of 0 must not crash — must return is_liquid = False."""
    result = check_liquidity(_ticker(0, 0, 0))
    assert result['is_liquid'] is False
    assert result['spread_pct'] == 999


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — spread value is (ask - bid)
# ---------------------------------------------------------------------------

def test_spread_value_is_correct():
    """spread field must equal ask - bid."""
    result = check_liquidity(_ticker(90, 100, 95))
    assert abs(result['spread'] - 10.0) < 0.001


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Invalid/missing ticker does not crash
# ---------------------------------------------------------------------------

def test_missing_ticker_fields_returns_illiquid():
    """Missing/empty ticker must return fallback dict without raising."""
    result = check_liquidity({})
    assert isinstance(result, dict)
    assert result['is_liquid'] is False
