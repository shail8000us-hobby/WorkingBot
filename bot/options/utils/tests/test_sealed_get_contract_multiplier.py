"""
Contract Test: get_contract_multiplier
========================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of get_contract_multiplier.
Pure lookup function — no external calls, no mocking needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest bot/options/utils/tests/test_sealed_get_contract_multiplier.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
from bot.options.utils.options_helper import get_contract_multiplier

pytestmark = pytest.mark.sealed


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — BTC returns 0.001
# ---------------------------------------------------------------------------

def test_btc_symbol_returns_0001():
    """BTC options must return multiplier 0.001."""
    result = get_contract_multiplier('C-BTC-66000-300126')
    assert result == 0.001


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — ETH returns 0.001
# ---------------------------------------------------------------------------

def test_eth_symbol_returns_0001():
    """ETH options must return multiplier 0.001."""
    result = get_contract_multiplier('C-ETH-3000-300126')
    assert result == 0.001


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Unknown asset defaults to 0.001
# ---------------------------------------------------------------------------

def test_unknown_asset_defaults_to_0001():
    """Unknown underlying must default to 0.001, not crash."""
    result = get_contract_multiplier('C-XYZ-5000-300126')
    assert result == 0.001


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Empty string does not crash, returns 0.001
# ---------------------------------------------------------------------------

def test_empty_string_does_not_crash():
    """Empty string must not raise and must return 0.001."""
    result = get_contract_multiplier('')
    assert result == 0.001


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Put options also return correct multiplier
# ---------------------------------------------------------------------------

def test_put_btc_symbol_returns_0001():
    """Put BTC options must also return 0.001 — type prefix is irrelevant."""
    result = get_contract_multiplier('P-BTC-66000-300126')
    assert result == 0.001


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Return type is always float
# ---------------------------------------------------------------------------

def test_return_type_is_float():
    """Return value must always be a float, never int or None."""
    result = get_contract_multiplier('C-BTC-66000-300126')
    assert isinstance(result, float)
