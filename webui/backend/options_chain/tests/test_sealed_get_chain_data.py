"""
Contract Test: get_chain_data
================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

This test locks the known-good behavior of get_chain_data.
If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/options_chain/tests/test_sealed_get_chain_data.py -v
"""

import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.sealed


# ---------------------------------------------------------------------------
# Fake ticker data helpers — simulates what Delta Exchange returns
# ---------------------------------------------------------------------------

def _make_ticker(symbol: str, strike: float, bid: float, ask: float,
                 delta: float = 0.5, iv: float = 0.8, oi: int = 100) -> dict:
    return {
        'symbol': symbol,
        'mark_price': str((bid + ask) / 2),
        'volume': '10.0',
        'oi_contracts': str(oi),
        'turnover_usd': '50000',
        'strike_price': str(strike),
        'spot_price': '90000',
        'quotes': {
            'best_bid': str(bid),
            'best_ask': str(ask),
            'bid_size': '5',
            'ask_size': '5',
            'mark_iv': str(iv),
            'bid_iv': str(iv - 0.05),
            'ask_iv': str(iv + 0.05),
        },
        'greeks': {
            'delta': str(delta),
            'gamma': '0.00001',
            'theta': '-50.0',
            'vega': '100.0',
        }
    }


# Expiry: March 6, 2026 = 06032026
# Symbol format: C-BTC-90000-060326  (DDMMYY)
FAKE_TICKERS = [
    _make_ticker('C-BTC-88000-060326', 88000.0, bid=500,  ask=520,  delta=0.3,  oi=200),
    _make_ticker('P-BTC-88000-060326', 88000.0, bid=1800, ask=1820, delta=-0.7, oi=180),
    _make_ticker('C-BTC-90000-060326', 90000.0, bid=300,  ask=320,  delta=0.5,  oi=350),
    _make_ticker('P-BTC-90000-060326', 90000.0, bid=300,  ask=320,  delta=-0.5, oi=340),
    _make_ticker('C-BTC-92000-060326', 92000.0, bid=150,  ask=170,  delta=0.25, oi=120),
    _make_ticker('P-BTC-92000-060326', 92000.0, bid=2500, ask=2520, delta=-0.75, oi=110),
]

FAKE_SPOT = 90000.0
TEST_EXPIRY = '06032026'


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def service():
    """OptionsChainService with external calls mocked."""
    with patch('webui.backend.options_chain.chain_service.get_config') as mock_cfg, \
         patch('webui.backend.options_chain.chain_service.get_api_credentials'):

        mock_cfg.return_value = MagicMock(trading_mode='live')

        from webui.backend.options_chain.chain_service import OptionsChainService, _cache
        _cache.invalidate()

        svc = OptionsChainService()
        yield svc


@pytest.fixture
def chain_result(service):
    """Pre-built result using fake data — reused across tests."""
    with patch.object(service, '_get_spot_price', return_value=FAKE_SPOT), \
         patch.object(service, '_get_option_tickers', return_value=FAKE_TICKERS):
        return service.get_chain_data('BTC', TEST_EXPIRY)


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Return must be a dict, never None
# ---------------------------------------------------------------------------

def test_get_chain_data_returns_dict(chain_result):
    """get_chain_data must always return a dict, never None."""
    assert chain_result is not None, "Must never return None"
    assert isinstance(chain_result, dict), "Must return a dict"


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Required top-level keys must always be present
# ---------------------------------------------------------------------------

def test_get_chain_data_required_keys_present(chain_result):
    """Result dict must always contain these exact top-level keys."""
    required_keys = ['underlying', 'expiry', 'spot_price', 'atm_strike', 'chain', 'summary', 'cached_at']
    for key in required_keys:
        assert key in chain_result, f"Missing required key: '{key}'"


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — summary sub-dict must have all 4 counters
# ---------------------------------------------------------------------------

def test_get_chain_data_summary_keys_present(chain_result):
    """summary dict must always contain: total_calls, total_puts, call_oi, put_oi."""
    summary = chain_result['summary']
    assert isinstance(summary, dict), "summary must be a dict"
    for key in ['total_calls', 'total_puts', 'call_oi', 'put_oi']:
        assert key in summary, f"Missing summary key: '{key}'"
        assert isinstance(summary[key], (int, float)), f"summary['{key}'] must be numeric"


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — chain must be a list and each strike must have call/put keys
# ---------------------------------------------------------------------------

def test_get_chain_data_chain_structure(chain_result):
    """chain must be a list; each entry must have 'strike', 'call', 'put' keys."""
    chain = chain_result['chain']
    assert isinstance(chain, list), "chain must be a list"
    assert len(chain) > 0, "chain must not be empty when valid tickers exist"

    for row in chain:
        assert 'strike' in row, f"Strike row missing 'strike': {row}"
        assert 'call' in row, f"Strike row missing 'call': {row}"
        assert 'put' in row, f"Strike row missing 'put': {row}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — ATM strike must be closest to spot price
# ---------------------------------------------------------------------------

def test_get_chain_data_atm_strike_is_closest_to_spot(chain_result):
    """atm_strike must be the strike price closest to spot_price."""
    spot = chain_result['spot_price']
    atm = chain_result['atm_strike']
    chain = chain_result['chain']

    assert atm is not None, "atm_strike must not be None when chain has data"

    # Verify no other strike is closer
    for row in chain:
        strike = row['strike']
        assert abs(strike - spot) >= abs(atm - spot), (
            f"Strike {strike} is closer to spot {spot} than atm_strike {atm}"
        )


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — underlying and expiry must be echoed back correctly
# ---------------------------------------------------------------------------

def test_get_chain_data_echoes_inputs(chain_result):
    """underlying and expiry in result must match what was passed in."""
    assert chain_result['underlying'] == 'BTC'
    assert chain_result['expiry'] == TEST_EXPIRY


# ---------------------------------------------------------------------------
# CONTRACT TEST 7 — Empty tickers must return valid empty structure, not crash
# ---------------------------------------------------------------------------

def test_get_chain_data_handles_empty_tickers_gracefully(service):
    """If exchange returns no tickers, function must return valid structure, not raise."""
    with patch.object(service, '_get_spot_price', return_value=90000.0), \
         patch.object(service, '_get_option_tickers', return_value=[]):
        result = service.get_chain_data('BTC', TEST_EXPIRY)

    assert result is not None
    assert isinstance(result['chain'], list)
    assert result['chain'] == []
    assert result['summary']['total_calls'] == 0
    assert result['summary']['total_puts'] == 0
