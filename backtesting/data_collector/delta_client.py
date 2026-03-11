"""
Delta Exchange India REST API Client
=====================================
Authenticated client for fetching historical options data.

Endpoints used:
  GET /v2/tickers           — options chain snapshot (incl. expired)
  GET /v2/history/candles   — 1-min OHLCV for any symbol
  GET /v2/products          — list of products for symbol discovery
"""

import os
import time
import logging
import requests
import hmac
import hashlib
from typing import Optional
from pathlib import Path

log = logging.getLogger("backtesting.delta_client")

# ── Delta Exchange India base URL ────────────────────────────────────────────
BASE_URL = "https://api.india.delta.exchange"

# ── Endpoint paths ────────────────────────────────────────────────────────────
EP_TICKERS   = "/v2/tickers"
EP_CANDLES   = "/v2/history/candles"
EP_PRODUCTS  = "/v2/products"


class DeltaClientError(Exception):
    """Raised when the Delta API returns a non-success response."""
    pass


class DeltaClient:
    """
    Thin, stateless REST client for Delta Exchange India.

    Authentication is optional for public endpoints (tickers, candles,
    products). Provide api_key + api_secret if rate-limit tier requires auth.

    Usage:
        client = DeltaClient()                       # unauthenticated
        client = DeltaClient(api_key="K", api_secret="S")   # authenticated
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: str = BASE_URL,
        timeout: int = 30,
        max_retries: int = 5,
        retry_backoff: float = 2.0,
    ):
        self.api_key    = api_key    or os.getenv("DELTA_API_KEY", "")
        self.api_secret = api_secret or os.getenv("DELTA_API_SECRET", "")
        self.base_url   = base_url.rstrip("/")
        self.timeout    = timeout
        self.max_retries    = max_retries
        self.retry_backoff  = retry_backoff

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        log.debug(f"DeltaClient initialized: {self.base_url}")

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _sign(self, method: str, path: str, query_string: str, body: str, timestamp: str) -> str:
        """HMAC-SHA256 signature for authenticated requests."""
        message = f"{method}{timestamp}{path}?{query_string}{body}"
        return hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

    def _build_headers(self, method: str, path: str, query_string: str, body: str = "") -> dict:
        """Build authentication headers if api_key is set."""
        if not self.api_key:
            return {}
        timestamp = str(int(time.time()))
        sig = self._sign(method, path, query_string, body, timestamp)
        return {
            "api-key": self.api_key,
            "timestamp": timestamp,
            "signature": sig,
        }

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        """
        Perform a GET request with automatic retry on 429 / 5xx.

        Returns the parsed JSON response body.
        Raises DeltaClientError on unrecoverable failure.
        """
        params = params or {}
        url = f"{self.base_url}{path}"
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        auth_headers = self._build_headers("GET", path, query_string)

        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    headers=auth_headers,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    wait = self.retry_backoff ** (attempt + 1)
                    log.warning(f"Rate limited on {path}. Waiting {wait:.1f}s (attempt {attempt+1})")
                    time.sleep(wait)
                    continue
                elif resp.status_code >= 500:
                    wait = self.retry_backoff ** (attempt + 1)
                    log.warning(f"Server error {resp.status_code} on {path}. Waiting {wait:.1f}s")
                    time.sleep(wait)
                    continue
                else:
                    raise DeltaClientError(
                        f"HTTP {resp.status_code} on GET {path}: {resp.text[:300]}"
                    )
            except requests.RequestException as e:
                wait = self.retry_backoff ** (attempt + 1)
                log.warning(f"Request error on {path}: {e}. Retrying in {wait:.1f}s")
                time.sleep(wait)

        raise DeltaClientError(f"All {self.max_retries} retries exhausted for GET {path}")

    # ── Public API methods ─────────────────────────────────────────────────────

    def get_tickers(
        self,
        contract_type: str,
        underlying: str = "BTC",
        expiry_date: Optional[str] = None,
        states: str = "live,expired",
    ) -> list:
        """
        Fetch options tickers (chain snapshot).

        Args:
            contract_type: "call_options" or "put_options"
            underlying:    "BTC" or "ETH"
            expiry_date:   "DD-MM-YYYY" format — for expired chains
            states:        "live", "expired", or "live,expired"

        Returns:
            List of ticker dicts from the Delta API.
        """
        params = {
            "contract_type": contract_type,
            "underlying_asset_symbol": underlying,
            "states": states,
        }
        if expiry_date:
            params["expiry_date"] = expiry_date

        result = self._get(EP_TICKERS, params)
        tickers = result.get("result", [])
        log.debug(
            f"Fetched {len(tickers)} {contract_type} tickers "
            f"(underlying={underlying}, expiry={expiry_date})"
        )
        return tickers

    def get_candles(
        self,
        symbol: str,
        from_ts: int,
        to_ts: int,
        resolution: str = "1m",
    ) -> list:
        """
        Fetch OHLCV candles for an option symbol.

        Args:
            symbol:     Delta Exchange symbol, e.g. "C-BTC-95000-260310"
            from_ts:    Unix timestamp (seconds), start of window (inclusive)
            to_ts:      Unix timestamp (seconds), end of window (exclusive)
            resolution: "1m", "5m", "15m", "1h", "1d"

        Returns:
            List of candle dicts: {time, open, high, low, close, volume}
        """
        params = {
            "symbol": symbol,
            "from": from_ts,
            "to": to_ts,
            "resolution": resolution,
        }
        result = self._get(EP_CANDLES, params)
        candles = result.get("result", {}).get("candles", [])
        log.debug(f"Fetched {len(candles)} candles for {symbol}")
        return candles

    def get_products(
        self,
        contract_type: str = "all",
        page_size: int = 500,
        after: str = "",
    ) -> list:
        """
        Fetch product listings for symbol discovery.

        Args:
            contract_type: "call_options", "put_options", "perpetual_futures", or "all"
            page_size:     Results per page (max 500)
            after:         Cursor for pagination

        Returns:
            List of product dicts.
        """
        params: dict = {"page_size": page_size}
        if contract_type != "all":
            params["contract_type"] = contract_type
        if after:
            params["after"] = after

        result = self._get(EP_PRODUCTS, params)
        products = result.get("result", [])
        log.debug(f"Fetched {len(products)} products (type={contract_type})")
        return products

    def get_spot_price(self, symbol: str = "BTCUSD") -> float:
        """
        Get the latest spot/index price for an underlying.

        Returns the mark price of the perp as a spot approximation.
        """
        # Use the candles endpoint for the most recent minute
        now_ts = int(time.time())
        candles = self.get_candles(symbol, now_ts - 120, now_ts, resolution="1m")
        if candles:
            return float(candles[-1].get("close", 0))
        raise DeltaClientError(f"Could not fetch spot price for {symbol}")
