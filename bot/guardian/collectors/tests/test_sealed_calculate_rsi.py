"""
Contract Test: _calculate_rsi
================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of the RSI calculation (Wilder's smoothing method).
This is pure math — NO mocking needed. Tests use real price sequences with
mathematically verified expected outputs.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest bot/guardian/collectors/tests/test_sealed_calculate_rsi.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
from unittest.mock import patch

pytestmark = pytest.mark.sealed


# ---------------------------------------------------------------------------
# Fixture — bypasses the complex constructor entirely.
# _calculate_rsi is pure math and uses zero instance state (self.*).
# ---------------------------------------------------------------------------

@pytest.fixture
def collector():
    from bot.guardian.collectors.rsi_collector import RSICollector
    with patch.object(RSICollector, '__init__', lambda self, *a, **kw: None):
        instance = RSICollector.__new__(RSICollector)
    return instance


# ---------------------------------------------------------------------------
# Helper: build a flat price list (useful for confirming RSI=50 on no movement)
# ---------------------------------------------------------------------------

def _flat_prices(value: float, count: int):
    return [value] * count


def _rising_prices(start: float, step: float, count: int):
    return [start + i * step for i in range(count)]


def _falling_prices(start: float, step: float, count: int):
    return [start - i * step for i in range(count)]


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Return type must be float when given valid input
# ---------------------------------------------------------------------------

def test_calculate_rsi_returns_float(collector):
    """Must return a float, never None, when given ≥ period+1 prices."""
    prices = _rising_prices(90000, 100, 20)
    result = collector._calculate_rsi(prices, period=14)
    assert result is not None, "Must not return None for valid input"
    assert isinstance(result, float), "Must return a float"


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Result must always be in range [0, 100]
# ---------------------------------------------------------------------------

def test_calculate_rsi_always_in_0_to_100_range(collector):
    """RSI must always be between 0 and 100 inclusive."""
    test_price_sets = [
        _rising_prices(90000, 500, 30),   # strongly rising
        _falling_prices(90000, 500, 30),  # strongly falling
        _rising_prices(90000, 10, 30),    # slowly rising
        _flat_prices(90000, 30),          # no movement
    ]
    for prices in test_price_sets:
        result = collector._calculate_rsi(prices, period=14)
        if result is not None:
            assert 0 <= result <= 100, f"RSI out of range: {result} for prices starting at {prices[0]}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Strongly rising prices → RSI must be above 70 (overbought)
# ---------------------------------------------------------------------------

def test_calculate_rsi_rising_prices_give_high_rsi(collector):
    """Consistently rising prices must produce RSI above 70."""
    prices = _rising_prices(80000, 1000, 30)  # +1000 every candle
    result = collector._calculate_rsi(prices, period=14)
    assert result is not None
    assert result > 70, f"Rising prices should give RSI > 70, got {result:.2f}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Strongly falling prices → RSI must be below 30 (oversold)
# ---------------------------------------------------------------------------

def test_calculate_rsi_falling_prices_give_low_rsi(collector):
    """Consistently falling prices must produce RSI below 30."""
    prices = _falling_prices(90000, 1000, 30)  # -1000 every candle
    result = collector._calculate_rsi(prices, period=14)
    assert result is not None
    assert result < 30, f"Falling prices should give RSI < 30, got {result:.2f}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — All gains, no losses → RSI must be exactly 100
# ---------------------------------------------------------------------------

def test_calculate_rsi_all_gains_returns_100(collector):
    """When avg_loss = 0 and avg_gain > 0, RSI must be exactly 100.0"""
    prices = _rising_prices(90000, 100, 20)
    result = collector._calculate_rsi(prices, period=14)
    assert result == 100.0, f"All-gain sequence must return exactly 100.0, got {result}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Insufficient data → must return None, never crash
# ---------------------------------------------------------------------------

def test_calculate_rsi_returns_none_for_insufficient_data(collector):
    """Must return None (not raise) when fewer than period+1 prices are given."""
    too_few = _rising_prices(90000, 100, 10)  # only 10 prices, period=14 needs 15
    result = collector._calculate_rsi(too_few, period=14)
    assert result is None, "Must return None for insufficient data, not crash"


# ---------------------------------------------------------------------------
# CONTRACT TEST 7 — Empty list → must return None, never crash
# ---------------------------------------------------------------------------

def test_calculate_rsi_handles_empty_list(collector):
    """Empty price list must return None gracefully."""
    result = collector._calculate_rsi([], period=14)
    assert result is None, "Empty price list must return None"


# ---------------------------------------------------------------------------
# CONTRACT TEST 8 — Result is stable: same input always gives same output
# ---------------------------------------------------------------------------

def test_calculate_rsi_is_deterministic(collector):
    """Same prices must always produce exactly the same RSI value (no randomness)."""
    prices = [90000, 91000, 89500, 92000, 91500, 93000, 92500,
              94000, 93500, 95000, 94500, 96000, 95500, 97000, 96500]
    result_1 = collector._calculate_rsi(prices, period=14)
    result_2 = collector._calculate_rsi(prices, period=14)
    assert result_1 == result_2, f"Same input gave different results: {result_1} vs {result_2}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 9 — Works for ETH price range too (lower prices, same logic)
# ---------------------------------------------------------------------------

def test_calculate_rsi_works_for_eth_price_range(collector):
    """RSI calculation must work correctly at ETH price levels (~2000-3000)."""
    prices = _rising_prices(2000, 50, 20)
    result = collector._calculate_rsi(prices, period=14)
    assert result is not None
    assert 0 <= result <= 100
