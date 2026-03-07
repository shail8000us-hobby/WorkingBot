"""
Contract Test: enrich_position_data
========================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of enrich_position_data.
Uses in-memory dict structures only — no API calls, no mocking needed.

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest bot/options/utils/tests/test_sealed_enrich_position_data.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
from bot.options.utils.options_helper import enrich_position_data

pytestmark = pytest.mark.sealed


def _make_position(size=-10, entry=100.0, symbol='C-BTC-66000-300126'):
    return {'size': size, 'entry_price': entry, 'product_symbol': symbol}


def _make_ticker(bid=90.0, ask=110.0, mark=100.0, greeks=None):
    return {
        'mark_price': mark,
        'spread_pct': 20.0,
        'quotes': {'best_bid': bid, 'best_ask': ask},
        'greeks': greeks or {'delta': -0.5, 'gamma': 0.001, 'theta': -0.8, 'vega': 0.3},
    }


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Returns a dict (not None, not list)
# ---------------------------------------------------------------------------

def test_returns_dict():
    """enrich_position_data must return a dict."""
    result = enrich_position_data(_make_position(), _make_ticker())
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Contains required keys
# ---------------------------------------------------------------------------

def test_contains_required_keys():
    """Result must contain mark_price, mid_price, best_bid, best_ask, unrealized_pnl, pnl_percentage, cashflow."""
    result = enrich_position_data(_make_position(), _make_ticker())
    for key in ('mark_price', 'mid_price', 'best_bid', 'best_ask',
                'unrealized_pnl', 'pnl_percentage', 'cashflow', 'greeks'):
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — mid_price is (bid + ask) / 2
# ---------------------------------------------------------------------------

def test_mid_price_is_average_of_bid_ask():
    """mid_price must be (best_bid + best_ask) / 2."""
    result = enrich_position_data(_make_position(), _make_ticker(bid=90, ask=110))
    assert abs(result['mid_price'] - 100.0) < 0.001


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — cashflow uses BTC multiplier 0.001
# ---------------------------------------------------------------------------

def test_cashflow_uses_contract_multiplier():
    """cashflow = abs(size) * entry_price * 0.001 for BTC."""
    pos = _make_position(size=-10, entry=500.0)
    result = enrich_position_data(pos, _make_ticker())
    # abs(-10) * 500 * 0.001 = 5.0 USD
    assert abs(result['cashflow'] - 5.0) < 0.001


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Short position profit when price drops
# ---------------------------------------------------------------------------

def test_short_position_unrealized_pnl_is_positive_when_price_drops():
    """Short (size < 0): mid < entry must give positive unrealized_pnl."""
    pos = _make_position(size=-10, entry=200.0)
    ticker = _make_ticker(bid=80.0, ask=100.0)  # mid = 90, entry = 200 → profit
    result = enrich_position_data(pos, ticker)
    assert result['unrealized_pnl'] > 0


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Original position fields are preserved
# ---------------------------------------------------------------------------

def test_original_position_fields_are_preserved():
    """enrich_position_data must not lose the original position's fields."""
    pos = _make_position()
    pos['some_custom_field'] = 'special_value'
    result = enrich_position_data(pos, _make_ticker())
    assert result.get('some_custom_field') == 'special_value'


# ---------------------------------------------------------------------------
# CONTRACT TEST 7 — return_on_cashflow is present and is a number
# ---------------------------------------------------------------------------

def test_return_on_cashflow_is_present():
    """return_on_cashflow must be present and a float."""
    result = enrich_position_data(_make_position(), _make_ticker())
    assert 'return_on_cashflow' in result
    assert isinstance(result['return_on_cashflow'], float)


# ---------------------------------------------------------------------------
# CONTRACT TEST 8 — greeks are passed through from ticker
# ---------------------------------------------------------------------------

def test_greeks_passed_through():
    """greeks from the ticker must appear in the enriched result."""
    greeks = {'delta': -0.45, 'gamma': 0.002, 'theta': -1.2, 'vega': 0.5}
    result = enrich_position_data(_make_position(), _make_ticker(greeks=greeks))
    assert result['greeks'] == greeks
