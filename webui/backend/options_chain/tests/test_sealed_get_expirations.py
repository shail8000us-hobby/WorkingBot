"""
Contract Test: get_expirations
================================
SEALED — v1.0.0 — March 4, 2026
Protocol: AI_SEAL.md

This test locks the known-good behavior of get_expirations.
If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/options_chain/tests/test_sealed_get_expirations.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

pytestmark = pytest.mark.sealed


# ---------------------------------------------------------------------------
# Helpers — build fake Delta Exchange API product data
# ---------------------------------------------------------------------------

def _make_product(settlement_time_iso: str, contract_type: str = 'call_options', underlying: str = 'BTC') -> dict:
    """Build a minimal fake Delta Exchange product dict."""
    return {
        'contract_type': contract_type,
        'underlying_asset': {'symbol': underlying},
        'settlement_time': settlement_time_iso
    }


def _future_expiry_iso(days_ahead: int) -> str:
    """Return an ISO timestamp N days in the future at 12:00 UTC."""
    dt = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    dt = dt.replace(hour=12, minute=0, second=0, microsecond=0)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def _past_expiry_iso(days_ago: int) -> str:
    """Return an ISO timestamp N days in the past at 12:00 UTC."""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    dt = dt.replace(hour=12, minute=0, second=0, microsecond=0)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


# ---------------------------------------------------------------------------
# Shared fixture — patches _request so we never hit the real exchange
# ---------------------------------------------------------------------------

@pytest.fixture
def service():
    """Create OptionsChainService with all external calls mocked."""
    with patch('webui.backend.options_chain.chain_service.get_config') as mock_cfg, \
         patch('webui.backend.options_chain.chain_service.get_api_credentials'):

        mock_cfg.return_value = MagicMock(trading_mode='live')

        # Import here so patches are active during __init__
        from webui.backend.options_chain.chain_service import OptionsChainService, _cache
        _cache.invalidate()  # clear cache between tests

        svc = OptionsChainService()
        yield svc


# ---------------------------------------------------------------------------
# CONTRACT TEST 1 — Basic return shape
# ---------------------------------------------------------------------------

def test_get_expirations_returns_list(service):
    """get_expirations must always return a list, never None."""
    fake_products = [
        _make_product(_future_expiry_iso(7)),
        _make_product(_future_expiry_iso(14)),
    ]

    with patch.object(service, '_get_option_products', return_value=fake_products):
        result = service.get_expirations('BTC')

    assert result is not None, "Must never return None"
    assert isinstance(result, list), "Must return a list"


# ---------------------------------------------------------------------------
# CONTRACT TEST 2 — Output format: every item must be DDMMYYYY (8 digits)
# ---------------------------------------------------------------------------

def test_get_expirations_format_is_ddmmyyyy(service):
    """Every item in result must be exactly 8 digits in DDMMYYYY format."""
    fake_products = [
        _make_product(_future_expiry_iso(3)),
        _make_product(_future_expiry_iso(10)),
        _make_product(_future_expiry_iso(17)),
    ]

    with patch.object(service, '_get_option_products', return_value=fake_products):
        result = service.get_expirations('BTC')

    for expiry in result:
        assert len(expiry) == 8, f"Each expiry must be 8 chars, got: {expiry!r}"
        assert expiry.isdigit(), f"Each expiry must be all digits, got: {expiry!r}"
        # Must be parseable as a real date
        datetime.strptime(expiry, '%d%m%Y')


# ---------------------------------------------------------------------------
# CONTRACT TEST 3 — Result must be sorted ascending by date
# ---------------------------------------------------------------------------

def test_get_expirations_sorted_ascending(service):
    """Expiry dates must come back in ascending order (nearest first)."""
    fake_products = [
        _make_product(_future_expiry_iso(30)),
        _make_product(_future_expiry_iso(7)),
        _make_product(_future_expiry_iso(14)),
    ]

    with patch.object(service, '_get_option_products', return_value=fake_products):
        result = service.get_expirations('BTC')

    parsed = [datetime.strptime(d, '%d%m%Y') for d in result]
    assert parsed == sorted(parsed), "Expirations must be sorted ascending"


# ---------------------------------------------------------------------------
# CONTRACT TEST 4 — Past expiry dates must never appear in result
# ---------------------------------------------------------------------------

def test_get_expirations_filters_out_past(service):
    """Expiry dates in the past must be filtered out."""
    fake_products = [
        _make_product(_past_expiry_iso(5)),   # 5 days ago — must be excluded
        _make_product(_past_expiry_iso(30)),  # 30 days ago — must be excluded
        _make_product(_future_expiry_iso(7)), # future — must be included
    ]

    with patch.object(service, '_get_option_products', return_value=fake_products):
        result = service.get_expirations('BTC')

    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    for expiry in result:
        dt = datetime.strptime(expiry, '%d%m%Y').date()
        assert dt >= today, f"Past expiry leaked through: {expiry}"


# ---------------------------------------------------------------------------
# CONTRACT TEST 5 — Works for ETH too, not just BTC
# ---------------------------------------------------------------------------

def test_get_expirations_works_for_eth(service):
    """get_expirations must work for ETH the same way it does for BTC."""
    fake_products = [
        _make_product(_future_expiry_iso(7), underlying='ETH'),
    ]

    with patch.object(service, '_get_option_products', return_value=fake_products):
        result = service.get_expirations('ETH')

    assert isinstance(result, list)
    assert len(result) >= 1


# ---------------------------------------------------------------------------
# CONTRACT TEST 6 — Empty exchange response must return empty list, not crash
# ---------------------------------------------------------------------------

def test_get_expirations_handles_empty_products_gracefully(service):
    """If exchange returns no products, function must return [] not raise."""
    with patch.object(service, '_get_option_products', return_value=[]):
        result = service.get_expirations('BTC')

    assert result == [], "Empty product list must return empty list, not crash"
