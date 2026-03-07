"""
Contract Test: calculate_unrealized_pnl
========================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of calculate_unrealized_pnl.
Pure math — no external calls, no mocking needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest bot/options/utils/tests/test_sealed_calculate_unrealized_pnl.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
from bot.options.utils.options_helper import calculate_unrealized_pnl

pytestmark = pytest.mark.sealed

_BTC_POS = lambda size, entry: {'size': size, 'entry_price': entry, 'product_symbol': 'C-BTC-66000-300126'}


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Short position profits when price drops
# ---------------------------------------------------------------------------

def test_short_position_profits_when_price_drops():
    """Short position (size < 0): mid < entry must produce positive PnL."""
    pos = _BTC_POS(-10, 100.0)
    pnl = calculate_unrealized_pnl(pos, 60.0)  # price dropped from 100 to 60
    assert pnl > 0, f"Expected profit for short, got {pnl}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Short position loses when price rises
# ---------------------------------------------------------------------------

def test_short_position_loses_when_price_rises():
    """Short position (size < 0): mid > entry must produce negative PnL."""
    pos = _BTC_POS(-10, 100.0)
    pnl = calculate_unrealized_pnl(pos, 150.0)
    assert pnl < 0, f"Expected loss for short, got {pnl}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Long position profits when price rises
# ---------------------------------------------------------------------------

def test_long_position_profits_when_price_rises():
    """Long position (size > 0): mid > entry must produce positive PnL."""
    pos = _BTC_POS(10, 100.0)
    pnl = calculate_unrealized_pnl(pos, 150.0)
    assert pnl > 0, f"Expected profit for long, got {pnl}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Long position loses when price drops
# ---------------------------------------------------------------------------

def test_long_position_loses_when_price_drops():
    """Long position (size > 0): mid < entry must produce negative PnL."""
    pos = _BTC_POS(10, 100.0)
    pnl = calculate_unrealized_pnl(pos, 60.0)
    assert pnl < 0, f"Expected loss for long, got {pnl}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — PnL is zero when mid equals entry
# ---------------------------------------------------------------------------

def test_pnl_is_zero_at_entry_price():
    """When mid_price == entry_price, PnL must be exactly 0.0."""
    pos = _BTC_POS(-5, 200.0)
    pnl = calculate_unrealized_pnl(pos, 200.0)
    assert pnl == 0.0


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Correct USD value using 0.001 multiplier
# ---------------------------------------------------------------------------

def test_pnl_uses_contract_multiplier():
    """PnL must use 0.001 BTC multiplier: (mid-entry) * size * 0.001."""
    pos = _BTC_POS(-10, 1000.0)
    pnl = calculate_unrealized_pnl(pos, 500.0)
    # (500 - 1000) * -10 * 0.001 = (-500) * -10 * 0.001 = +5.0
    assert abs(pnl - 5.0) < 0.0001


# ---------------------------------------------------------------------------
# CONTRACT TEST 7 — String values in position dict are handled (API returns strings)
# ---------------------------------------------------------------------------

def test_handles_string_values_from_api():
    """API often returns size/entry_price as strings — must not crash."""
    pos = {'size': '-5', 'entry_price': '100.0', 'product_symbol': 'C-BTC-66000-300126'}
    pnl = calculate_unrealized_pnl(pos, 80.0)
    assert isinstance(pnl, float)
    assert pnl > 0  # short profited from price drop


# ---------------------------------------------------------------------------
# CONTRACT TEST 8 — Return type is always float
# ---------------------------------------------------------------------------

def test_return_type_is_float():
    """Return value must always be a float."""
    pos = _BTC_POS(-10, 100.0)
    result = calculate_unrealized_pnl(pos, 90.0)
    assert isinstance(result, float)
