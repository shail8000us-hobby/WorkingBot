"""
Delta Exchange Portfolio Margin API Client

HMAC-SHA256 authenticated REST client for portfolio margin operations.
Reuses credentials from config.loader.get_api_credentials().
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

log = logging.getLogger(__name__)

BASE_URL = 'https://api.india.delta.exchange'
TICKERS_CDN_URL = 'https://cdn.india.deltaex.org/v2/tickers'
CONNECT_TIMEOUT = 3
READ_TIMEOUT = 27


class DeltaPortfolioMarginClient:
    """REST client for Delta Exchange portfolio margin API."""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """Initialise with explicit credentials or fall back to env / config."""
        if api_key and api_secret:
            self._api_key = api_key
            self._api_secret = api_secret
        else:
            self._api_key, self._api_secret = self._load_credentials()

        self._base_url = BASE_URL
        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        log.info('DeltaPortfolioMarginClient initialised (key=%s…)', self._api_key[:8] if self._api_key else 'NONE')

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_credentials() -> tuple:
        """Load API credentials from env or config.loader."""
        key = os.environ.get('DELTA_API_KEY', '')
        secret = os.environ.get('DELTA_API_SECRET', '')
        if key and secret:
            return key, secret

        try:
            from config.loader import get_api_credentials
            creds = get_api_credentials()
            return creds.get('api_key', ''), creds.get('api_secret', '')
        except Exception:
            log.warning('Could not load API credentials from config.loader')
            return '', ''

    # ------------------------------------------------------------------
    # HMAC-SHA256 signature
    # ------------------------------------------------------------------

    def _generate_signature(self, method: str, path: str, timestamp: str,
                            query_string: str = '', body: str = '') -> str:
        """Generate HMAC-SHA256 signature for Delta Exchange API."""
        payload = method + timestamp + path
        if query_string:
            payload += '?' + query_string
        if body:
            payload += body

        signature = hmac.new(
            self._api_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _auth_headers(self, method: str, path: str,
                      query_string: str = '', body: str = '') -> Dict[str, str]:
        """Build authentication headers for a request."""
        ts = str(int(time.time()))
        sig = self._generate_signature(method, path, ts, query_string, body)
        return {
            'api-key': self._api_key,
            'signature': sig,
            'timestamp': ts,
        }

    # ------------------------------------------------------------------
    # Generic HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Authenticated GET request."""
        qs = urlencode(params) if params else ''
        headers = self._auth_headers('GET', path, query_string=qs)
        url = self._base_url + path
        if qs:
            url += '?' + qs

        try:
            resp = self._session.get(url, headers=headers,
                                     timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            log.error('GET %s timed out', path)
            raise
        except requests.exceptions.RequestException as exc:
            log.error('GET %s failed: %s', path, exc)
            raise

    def _put(self, path: str, payload: Dict) -> Dict[str, Any]:
        """Authenticated PUT request."""
        body = json.dumps(payload)
        headers = self._auth_headers('PUT', path, body=body)
        url = self._base_url + path
        try:
            resp = self._session.put(url, data=body, headers=headers,
                                     timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            log.error('PUT %s timed out', path)
            raise
        except requests.exceptions.RequestException as exc:
            log.error('PUT %s failed: %s', path, exc)
            raise

    # ------------------------------------------------------------------
    # Portfolio Margin API methods
    # ------------------------------------------------------------------

    def get_wallet_balances(self) -> List[Dict]:
        """GET /v2/wallet/balances — wallet with portfolio margin details."""
        data = self._get('/v2/wallet/balances')
        return data.get('result', [])

    def get_positions(self, contract_types: Optional[List[str]] = None) -> List[Dict]:
        """GET /v2/positions/margined — open positions."""
        params: Dict[str, str] = {}
        if contract_types:
            params['contract_types'] = ','.join(contract_types)
        data = self._get('/v2/positions/margined', params or None)
        return data.get('result', [])

    def get_tickers(self) -> List[Dict]:
        """GET tickers from CDN — public endpoint, no auth needed.

        Returns list of ticker dicts with symbol, mark_price, greeks, etc.
        """
        try:
            resp = requests.get(TICKERS_CDN_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get('result', data if isinstance(data, list) else [])
        except Exception as exc:
            log.warning('get_tickers from CDN failed: %s', exc)
            return []

    def set_margin_mode(self, mode: str, subaccount_user_id: Optional[str] = None) -> Dict:
        """PUT /v2/users/margin_mode — switch margin mode."""
        payload: Dict[str, str] = {'margin_mode': mode}
        if subaccount_user_id:
            payload['subaccount_user_id'] = subaccount_user_id
        log.info('Switching margin mode to %s (subaccount=%s)', mode, subaccount_user_id or 'main')
        data = self._put('/v2/users/margin_mode', payload)
        return data

    def get_margin_mode(self) -> str:
        """Infer current margin mode from wallet balances."""
        try:
            balances = self.get_wallet_balances()
            for b in balances:
                if float(b.get('portfolio_margin', 0)) > 0:
                    return 'portfolio'
            return 'isolated'
        except Exception:
            return 'unknown'

    # ------------------------------------------------------------------
    # Signature helper for WebSocket auth
    # ------------------------------------------------------------------

    def generate_ws_auth(self) -> Dict[str, str]:
        """Generate WebSocket auth payload."""
        ts = str(int(time.time()))
        method = 'GET'
        path = '/live'
        sig = self._generate_signature(method, path, ts)
        return {
            'api-key': self._api_key,
            'signature': sig,
            'timestamp': ts,
        }
