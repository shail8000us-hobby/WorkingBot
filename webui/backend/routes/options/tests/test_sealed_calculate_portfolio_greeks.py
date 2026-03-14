"""
Contract Test: calculate_portfolio_greeks
========================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of calculate_portfolio_greeks.
Pure calculation — no external calls, no mocking needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/routes/options/tests/test_sealed_calculate_portfolio_greeks.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
from webui.backend.routes.options.dashboard import calculate_portfolio_greeks

pytestmark = pytest.mark.sealed


def _pos(symbol, size, delta=0.0, gamma=0.0, theta=0.0, vega=0.0):
    return {
        'product_symbol': symbol,
        'size': size,
        'greeks': {'delta': delta, 'gamma': gamma, 'theta': theta, 'vega': vega}
    }


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Returns correct dict shape
# ---------------------------------------------------------------------------

def test_returns_correct_shape():
    """Must return dict with delta, gamma, theta, vega, btcDelta, ethDelta, count."""
    result = calculate_portfolio_greeks([])
    for key in ('delta', 'gamma', 'theta', 'vega', 'btcDelta', 'ethDelta', 'count'):
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Empty list returns all zeros
# ---------------------------------------------------------------------------

def test_empty_positions_all_zeros():
    """Empty positions list must return all zero Greeks."""
    result = calculate_portfolio_greeks([])
    assert result['delta']    == 0.0
    assert result['gamma']    == 0.0
    assert result['theta']    == 0.0
    assert result['vega']     == 0.0
    assert result['btcDelta'] == 0.0
    assert result['ethDelta'] == 0.0
    assert result['count']    == 0


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Delta is scaled by signed size
# ---------------------------------------------------------------------------

def test_delta_scaled_by_signed_size():
    """Portfolio delta = per_contract_delta * size * 0.001 (1 lot = 0.001 BTC)."""
    positions = [_pos('C-BTC-66000-300126', size=-10, delta=0.5)]
    result = calculate_portfolio_greeks(positions)
    # 0.5 * -10 * 0.001 = -0.005
    assert abs(result['delta'] - (-0.005)) < 1e-9


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Gamma uses abs(size) * 0.001
# ---------------------------------------------------------------------------

def test_gamma_uses_abs_size():
    """Portfolio gamma = per_contract_gamma * abs(size) * 0.001 (1 lot = 0.001 BTC)."""
    positions = [_pos('C-BTC-66000-300126', size=-10, gamma=0.002)]
    result = calculate_portfolio_greeks(positions)
    # 0.002 * abs(-10) * 0.001 = 0.00002
    assert abs(result['gamma'] - 0.00002) < 1e-10


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Theta divided by 1000 for USD conversion
# ---------------------------------------------------------------------------

def test_theta_divided_by_1000():
    """Theta must be divided by 1000 for USD units."""
    positions = [_pos('C-BTC-66000-300126', size=-10, theta=-1000.0)]
    result = calculate_portfolio_greeks(positions)
    # (-1000 / 1000) * -10 = +10.0
    assert abs(result['theta'] - 10.0) < 0.001


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — BTC and ETH delta are separated correctly
# ---------------------------------------------------------------------------

def test_btc_eth_delta_separation():
    """btcDelta and ethDelta must only sum contributions from their respective underlying."""
    positions = [
        _pos('C-BTC-66000-300126', size=2, delta=0.5),   # btcDelta += 0.5 * 2 * 0.001 = +0.001
        _pos('C-ETH-3000-300126',  size=-5, delta=0.4),  # ethDelta += 0.4 * -5 * 0.001 = -0.002
    ]
    result = calculate_portfolio_greeks(positions)
    assert abs(result['btcDelta'] - 0.001)  < 1e-9
    assert abs(result['ethDelta'] - (-0.002)) < 1e-9


# ---------------------------------------------------------------------------
# CONTRACT TEST 7 — count equals number of positions with non-zero size
# ---------------------------------------------------------------------------

def test_count_equals_positions_with_size():
    """count must reflect number of positions that contributed (size != 0)."""
    positions = [
        _pos('C-BTC-66000-300126', size=-5, delta=0.5),
        _pos('C-BTC-68000-300126', size=-3, delta=0.4),
        _pos('C-BTC-70000-300126', size=0, delta=0.3),   # size=0, skipped
    ]
    result = calculate_portfolio_greeks(positions)
    assert result['count'] == 2


# ---------------------------------------------------------------------------
# CONTRACT TEST 8 — None positions list handled safely
# ---------------------------------------------------------------------------

def test_none_positions_returns_zeros():
    """None input must return zero Greeks without raising."""
    result = calculate_portfolio_greeks(None)
    assert result['delta'] == 0.0
    assert result['count'] == 0
