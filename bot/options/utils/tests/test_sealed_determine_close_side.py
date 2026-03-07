"""
Contract Test: determine_close_side
========================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of determine_close_side.
Pure logic — no external calls, no mocking needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest bot/options/utils/tests/test_sealed_determine_close_side.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
from bot.options.utils.options_helper import determine_close_side

pytestmark = pytest.mark.sealed


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Long position (positive size) returns 'sell'
# ---------------------------------------------------------------------------

def test_long_position_returns_sell():
    """Positive size (long) must return 'sell' to close."""
    assert determine_close_side(10) == 'sell'


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Short position (negative size) returns 'buy'
# ---------------------------------------------------------------------------

def test_short_position_returns_buy():
    """Negative size (short) must return 'buy' to close."""
    assert determine_close_side(-10) == 'buy'


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Fractional positive size returns 'sell'
# ---------------------------------------------------------------------------

def test_fractional_positive_returns_sell():
    """Fractional positive size must also return 'sell'."""
    assert determine_close_side(0.5) == 'sell'


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Fractional negative size returns 'buy'
# ---------------------------------------------------------------------------

def test_fractional_negative_returns_buy():
    """Fractional negative size must also return 'buy'."""
    assert determine_close_side(-0.5) == 'buy'


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Return type is always str
# ---------------------------------------------------------------------------

def test_return_type_is_str():
    """Return value must always be a str, never None."""
    result = determine_close_side(5)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Zero size returns 'buy' (size <= 0 path)
# ---------------------------------------------------------------------------

def test_zero_size_returns_buy():
    """Zero size is not long — must return 'buy' (same as short path)."""
    assert determine_close_side(0) == 'buy'
