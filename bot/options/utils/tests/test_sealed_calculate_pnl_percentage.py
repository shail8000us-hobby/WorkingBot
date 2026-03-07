"""
Contract Test: calculate_pnl_percentage
========================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of calculate_pnl_percentage.
Pure math — no external calls, no mocking needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest bot/options/utils/tests/test_sealed_calculate_pnl_percentage.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
from bot.options.utils.options_helper import calculate_pnl_percentage

pytestmark = pytest.mark.sealed

_POS = lambda size, entry: {'size': size, 'entry_price': entry}


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Short position: price drops 50% → positive percentage
# ---------------------------------------------------------------------------

def test_short_profit_shows_positive_percentage():
    """Short (size < 0): price drop means profit — must return positive %."""
    pos = _POS(-10, 100.0)
    pct = calculate_pnl_percentage(pos, 50.0)  # 50% drop
    assert pct > 0, f"Expected positive % for short profit, got {pct}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Short position: price rises 50% → negative percentage
# ---------------------------------------------------------------------------

def test_short_loss_shows_negative_percentage():
    """Short (size < 0): price rise means loss — must return negative %."""
    pos = _POS(-10, 100.0)
    pct = calculate_pnl_percentage(pos, 150.0)
    assert pct < 0


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Long position: price rises 50% → positive percentage
# ---------------------------------------------------------------------------

def test_long_profit_shows_positive_percentage():
    """Long (size > 0): price rise means profit — must return positive %."""
    pos = _POS(10, 100.0)
    pct = calculate_pnl_percentage(pos, 150.0)
    assert pct > 0


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Long position: price drops 50% → negative percentage
# ---------------------------------------------------------------------------

def test_long_loss_shows_negative_percentage():
    """Long (size > 0): price drop means loss — must return negative %."""
    pos = _POS(10, 100.0)
    pct = calculate_pnl_percentage(pos, 50.0)
    assert pct < 0


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Zero entry price returns 0.0 (no division error)
# ---------------------------------------------------------------------------

def test_zero_entry_price_returns_zero():
    """Entry price of 0 must return 0.0 — no ZeroDivisionError."""
    pos = _POS(-10, 0.0)
    result = calculate_pnl_percentage(pos, 50.0)
    assert result == 0.0


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Short: 50% price drop → exactly +50%
# ---------------------------------------------------------------------------

def test_short_50pct_drop_gives_plus_50():
    """Short position: 50% price drop must return exactly +50.0%."""
    pos = _POS(-10, 200.0)
    pct = calculate_pnl_percentage(pos, 100.0)
    # price change = (100-200)/200 * 100 = -50%, inverted for short = +50%
    assert abs(pct - 50.0) < 0.001


# ---------------------------------------------------------------------------
# CONTRACT TEST 7 — Return type is always float
# ---------------------------------------------------------------------------

def test_return_type_is_float():
    """Return value must always be a float."""
    result = calculate_pnl_percentage(_POS(-5, 100.0), 90.0)
    assert isinstance(result, float)
