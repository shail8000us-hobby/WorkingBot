"""
Contract tests for get_spot_price

SEALED — v1.0.0 — March 2026
Do not modify without UNSEAL command in AI_SEAL.md

Function: get_spot_price()
File: webui/backend/routes/market.py
Route: GET /api/market/spot-price?symbol=BTC|ETH

Contracts:
  - Returns JSON with keys: symbol, price, source
  - price is always a positive float
  - symbol in response matches the requested symbol (BTC or ETH)
  - Invalid symbol returns 400 with error key
  - Default symbol is BTC when not specified
  - On exception during external calls: falls back to hardcoded price, never raises
  - Response status 200 for valid symbols
"""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

pytestmark = pytest.mark.sealed

from webui.backend.routes.market import market_bp, get_spot_price
from webui.backend.cache import cache, init_cache


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(market_bp)
    app.config['TESTING'] = True
    init_cache(app)
    return app


def _no_websocket():
    """Patch get_price_websocket to return None (no WS available)."""
    return patch('webui.backend.routes.market.get_price_websocket', None)


class TestGetSpotPriceBTC:

    def test_btc_returns_required_keys(self):
        with _make_app().test_client() as client:
            with _no_websocket():
                with patch('requests.get') as mock_get:
                    mock_get.return_value.status_code = 200
                    mock_get.return_value.json.return_value = {
                        'success': True,
                        'result': {'mark_price': '95000.0'}
                    }
                    resp = client.get('/api/market/spot-price?symbol=BTC')
        assert resp.status_code == 200
        data = resp.get_json()
        for key in ('symbol', 'price', 'source'):
            assert key in data, f"Missing key: {key}"

    def test_btc_price_is_positive_float(self):
        with _make_app().test_client() as client:
            with _no_websocket():
                with patch('requests.get') as mock_get:
                    mock_get.return_value.status_code = 200
                    mock_get.return_value.json.return_value = {
                        'success': True,
                        'result': {'mark_price': '95000.0'}
                    }
                    resp = client.get('/api/market/spot-price?symbol=BTC')
        data = resp.get_json()
        assert isinstance(data['price'], (int, float))
        assert data['price'] > 0

    def test_btc_symbol_matches_request(self):
        with _make_app().test_client() as client:
            with _no_websocket():
                with patch('requests.get') as mock_get:
                    mock_get.return_value.status_code = 200
                    mock_get.return_value.json.return_value = {
                        'success': True,
                        'result': {'mark_price': '95000.0'}
                    }
                    resp = client.get('/api/market/spot-price?symbol=BTC')
        data = resp.get_json()
        assert data['symbol'] == 'BTC'


class TestGetSpotPriceETH:

    def test_eth_returns_required_keys(self):
        with _make_app().test_client() as client:
            with _no_websocket():
                with patch('requests.get') as mock_get:
                    mock_get.return_value.status_code = 200
                    mock_get.return_value.json.return_value = {
                        'success': True,
                        'result': {'mark_price': '3500.0'}
                    }
                    resp = client.get('/api/market/spot-price?symbol=ETH')
        assert resp.status_code == 200
        data = resp.get_json()
        for key in ('symbol', 'price', 'source'):
            assert key in data, f"Missing key: {key}"

    def test_eth_symbol_matches_request(self):
        with _make_app().test_client() as client:
            with _no_websocket():
                with patch('requests.get') as mock_get:
                    mock_get.return_value.status_code = 200
                    mock_get.return_value.json.return_value = {
                        'success': True,
                        'result': {'mark_price': '3500.0'}
                    }
                    resp = client.get('/api/market/spot-price?symbol=ETH')
        data = resp.get_json()
        assert data['symbol'] == 'ETH'


class TestGetSpotPriceInvalidSymbol:

    def test_invalid_symbol_returns_400(self):
        with _make_app().test_client() as client:
            with _no_websocket():
                resp = client.get('/api/market/spot-price?symbol=XRP')
        assert resp.status_code == 400

    def test_invalid_symbol_returns_error_key(self):
        with _make_app().test_client() as client:
            with _no_websocket():
                resp = client.get('/api/market/spot-price?symbol=DOGE')
        data = resp.get_json()
        assert 'error' in data


class TestGetSpotPriceFallback:

    def test_api_failure_returns_fallback_price(self):
        """On API exception, function falls back to hardcoded price and never raises."""
        with _make_app().test_client() as client:
            with _no_websocket():
                with patch('requests.get', side_effect=Exception("Connection refused")):
                    resp = client.get('/api/market/spot-price?symbol=BTC')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['price'] > 0
        assert data['symbol'] == 'BTC'

    def test_fallback_source_label_present(self):
        """Fallback response still has a source field."""
        with _make_app().test_client() as client:
            with _no_websocket():
                with patch('requests.get', side_effect=Exception("timeout")):
                    resp = client.get('/api/market/spot-price?symbol=ETH')
        data = resp.get_json()
        assert 'source' in data

    def test_default_symbol_is_btc(self):
        """When symbol param is omitted, defaults to BTC."""
        with _make_app().test_client() as client:
            with _no_websocket():
                with patch('requests.get', side_effect=Exception("timeout")):
                    resp = client.get('/api/market/spot-price')
        data = resp.get_json()
        assert data['symbol'] == 'BTC'
