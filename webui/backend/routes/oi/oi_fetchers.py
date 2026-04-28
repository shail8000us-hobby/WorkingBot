"""
OI Aggregator — Exchange Fetchers

Base class + implementations for Deribit, Binance, Delta Exchange Global.
Each fetcher outputs normalised OIRow dicts. No exchange-specific fields
leak past the fetcher layer.

READ-ONLY analytics module. Does NOT interact with any trading logic.

Created: March 27, 2026
"""

import logging
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import requests

log = logging.getLogger('oi_aggregator')

# ---------------------------------------------------------------------------
# Normalised OIRow schema
# ---------------------------------------------------------------------------
# Every fetcher returns a list of dicts matching this shape:
#
# {
#     "exchange":    str,      # "deribit" | "binance" | "delta_global"
#     "underlying":  str,      # "BTC" | "ETH"
#     "expiry":      str,      # ISO date "YYYY-MM-DD"
#     "strike":      float,
#     "type":        str,      # "call" | "put"
#     "oi":          float,    # open interest in contract/coin units
#     "oi_usd":      float,    # notional USD value
#     "timestamp":   str,      # ISO datetime UTC
# }

_EXPIRY_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# Month abbreviation → number mapping for Deribit/Binance instrument parsing
_MONTH_MAP = {
    'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
    'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
    'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12',
}


# ============================================================================
# Base Fetcher
# ============================================================================

class BaseOIFetcher(ABC):
    """Abstract base for exchange OI fetchers."""

    exchange_name: str = 'unknown'
    base_url: str = ''
    enabled: bool = True
    contract_multiplier: float = 1.0

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'OI-Aggregator/1.0',
        })
        self._last_fetch_ts = None
        self._last_row_count = 0
        self._consecutive_failures = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, underlying: str = 'BTC') -> list:
        """Fetch OI data, validate, and return normalised rows."""
        if not self.enabled:
            log.debug('[%s] Fetcher disabled, skipping', self.exchange_name)
            return []

        try:
            raw_rows = self._do_fetch(underlying)
            valid_rows = [r for r in raw_rows if self._validate_row(r)]

            self._last_fetch_ts = datetime.now(timezone.utc).isoformat()
            self._last_row_count = len(valid_rows)
            self._consecutive_failures = 0

            log.info('[%s] Fetched %d valid rows (underlying=%s)',
                     self.exchange_name, len(valid_rows), underlying)
            return valid_rows

        except Exception as e:
            self._consecutive_failures += 1
            log.warning('[%s] Fetch failed (attempt #%d): %s',
                        self.exchange_name, self._consecutive_failures, e)
            return []

    @abstractmethod
    def _do_fetch(self, underlying: str) -> list:
        """Subclass implements actual API call + parsing."""
        ...

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _http_get(self, url: str, params: dict = None, timeout: tuple = (3, 10)) -> dict:
        """
        GET with retry (3 attempts, exponential backoff 1s/2s/4s).
        connect_timeout=3s, read_timeout=10s.
        """
        last_err = None
        for attempt in range(3):
            try:
                resp = self._session.get(url, params=params, timeout=timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_err = e
                if attempt < 2:
                    delay = 2 ** attempt  # 1s, 2s, 4s
                    log.debug('[%s] Retry %d after %.0fs: %s',
                              self.exchange_name, attempt + 1, delay, e)
                    time.sleep(delay)
        raise last_err

    def _validate_row(self, row: dict) -> bool:
        """Validate a normalised OIRow dict. Drop and log invalid rows."""
        try:
            if row.get('oi', -1) < 0:
                log.debug('[%s] Invalid oi=%s for strike=%s',
                          self.exchange_name, row.get('oi'), row.get('strike'))
                return False
            if row.get('strike', 0) <= 0:
                log.debug('[%s] Invalid strike=%s', self.exchange_name, row.get('strike'))
                return False
            if row.get('oi_usd', -1) < 0:
                return False
            expiry = row.get('expiry', '')
            if not _EXPIRY_PATTERN.match(expiry):
                log.debug('[%s] Invalid expiry format: %s', self.exchange_name, expiry)
                return False
            if row.get('type') not in ('call', 'put'):
                return False
            return True
        except Exception:
            return False

    def get_health(self) -> dict:
        """Return fetcher health status."""
        return {
            'exchange': self.exchange_name,
            'enabled': self.enabled,
            'last_fetch_ts': self._last_fetch_ts,
            'last_row_count': self._last_row_count,
            'consecutive_failures': self._consecutive_failures,
        }

    def close(self):
        """Cleanup session."""
        try:
            self._session.close()
        except Exception:
            pass


# ============================================================================
# Deribit Fetcher
# ============================================================================

class DeribitOIFetcher(BaseOIFetcher):
    """
    Deribit public API — largest crypto options market.
    Single call returns ALL option book summaries for a currency.
    OI is in BTC (coin-margined), so oi_usd = oi × underlying_price.
    """

    exchange_name = 'deribit'
    base_url = 'https://www.deribit.com/api/v2/public'

    # Instrument name: BTC-27JUN25-65000-C
    _INST_RE = re.compile(
        r'^(?P<asset>[A-Z]+)-(?P<day>\d{1,2})(?P<mon>[A-Z]{3})(?P<year>\d{2})-(?P<strike>\d+)-(?P<type>[CP])$'
    )

    def _do_fetch(self, underlying: str) -> list:
        url = f'{self.base_url}/get_book_summary_by_currency'
        data = self._http_get(url, params={
            'currency': underlying.upper(),
            'kind': 'option',
        })

        results = data.get('result', [])
        if not results:
            log.warning('[deribit] Empty result from book summary')
            return []

        rows = []
        now_ts = datetime.now(timezone.utc).isoformat()

        for item in results:
            inst = item.get('instrument_name', '')
            m = self._INST_RE.match(inst)
            if not m:
                continue

            oi = float(item.get('open_interest', 0) or 0)
            if oi == 0:
                continue  # Skip zero-OI strikes to save memory

            underlying_price = float(item.get('underlying_price', 0) or 0)
            mark_iv = float(item.get('mark_iv', 0) or 0) / 100.0 if item.get('mark_iv') else 0.0
            
            strike = float(m.group('strike'))
            opt_type = 'call' if m.group('type') == 'C' else 'put'

            # Parse expiry: 27JUN25 → 2025-06-27
            day = m.group('day').zfill(2)
            mon = _MONTH_MAP.get(m.group('mon'), '01')
            year = f"20{m.group('year')}"
            expiry = f"{year}-{mon}-{day}"

            rows.append({
                'exchange': 'deribit',
                'underlying': underlying.upper(),
                'underlying_price': underlying_price,
                'expiry': expiry,
                'strike': strike,
                'type': opt_type,
                'oi': oi,
                'oi_usd': oi * underlying_price,
                'mark_iv': mark_iv,
                'timestamp': now_ts,
            })

        return rows


# ============================================================================
# Binance Options Fetcher
# ============================================================================

class BinanceOIFetcher(BaseOIFetcher):
    """
    Binance eapi — per-expiry OI calls.
    Uses native sumOpenInterestUSD (no manual oi × price).

    NOTE: As of 2026-03-27, Binance eapi /openInterest returns -6010
    'open interest error data' for all BTC expiries regardless of format.
    The fetcher is disabled by default. Re-enable if Binance fixes their API.
    """

    exchange_name = 'binance'
    base_url = 'https://eapi.binance.com/eapi/v1'
    enabled = False  # Disabled: eapi /openInterest returns -6010 for all expiries

    # Symbol: BTC-250627-65000-C
    _SYM_RE = re.compile(
        r'^(?P<asset>[A-Z]+)-(?P<date>\d{6})-(?P<strike>\d+)-(?P<type>[CP])$'
    )

    def _do_fetch(self, underlying: str) -> list:
        # Step 1: Get available expiry dates from exchange info
        expiries = self._get_expiries(underlying)
        if not expiries:
            log.warning('[binance] No expiries found')
            return []

        # Step 2: Fetch OI per expiry (rate-limited)
        all_rows = []
        now_ts = datetime.now(timezone.utc).isoformat()

        for exp_str in expiries:
            try:
                rows = self._fetch_expiry_oi(underlying, exp_str, now_ts)
                all_rows.extend(rows)
                time.sleep(0.25)  # Rate limit: ~4 req/sec (safe under 5/s limit)
            except Exception as e:
                log.warning('[binance] Failed to fetch expiry %s: %s', exp_str, e)
                continue

        return all_rows

    def _get_expiries(self, underlying: str) -> list:
        """Get unique expiry dates from exchange info."""
        try:
            data = self._http_get(f'{self.base_url}/exchangeInfo')
            symbols = data.get('optionSymbols', [])
            expiries = set()
            for sym in symbols:
                if sym.get('underlying', '').upper() == underlying.upper():
                    # expiryDate is timestamp in ms
                    exp_ts = sym.get('expiryDate')
                    if exp_ts:
                        exp_dt = datetime.fromtimestamp(exp_ts / 1000, tz=timezone.utc)
                        # Only future/current-day expiries
                        if exp_dt.date() >= datetime.now(timezone.utc).date():
                            expiries.add(exp_dt.strftime('%y%m%d'))  # YYMMDD format for API
            return sorted(expiries)[:12]  # Cap at 12 expiries
        except Exception as e:
            log.warning('[binance] Failed to get expiries: %s', e)
            return []

    def _fetch_expiry_oi(self, underlying: str, exp_str: str, now_ts: str) -> list:
        """Fetch OI for a single expiry date."""
        data = self._http_get(f'{self.base_url}/openInterest', params={
            'underlyingAsset': underlying.upper(),
            'expiration': exp_str,
        })

        rows = []
        for item in data if isinstance(data, list) else []:
            symbol = item.get('symbol', '')
            m = self._SYM_RE.match(symbol)
            if not m:
                continue

            oi = float(item.get('sumOpenInterest', 0) or 0)
            if oi == 0:
                continue

            oi_usd = float(item.get('sumOpenInterestUsd', 0) or
                           item.get('sumOpenInterestUSD', 0) or 0)
            strike = float(m.group('strike'))
            opt_type = 'call' if m.group('type') == 'C' else 'put'

            # Parse expiry: 250627 → 2025-06-27
            date_str = m.group('date')
            expiry = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"

            rows.append({
                'exchange': 'binance',
                'underlying': underlying.upper(),
                'expiry': expiry,
                'strike': strike,
                'type': opt_type,
                'oi': oi,
                'oi_usd': oi_usd,
                'mark_iv': 0.0,
                'timestamp': now_ts,
            })

        return rows


# ============================================================================
# Delta Exchange Global Fetcher
# ============================================================================

class DeltaGlobalOIFetcher(BaseOIFetcher):
    """
    Delta Exchange Global — public tickers endpoint.
    Returns OI for all option contracts in one call.
    """

    exchange_name = 'delta_global'
    base_url = 'https://api.delta.exchange/v2'

    def _do_fetch(self, underlying: str) -> list:
        # Fetch products first (for strike/expiry metadata)
        products = self._get_products(underlying)
        if not products:
            log.warning('[delta_global] No products found')
            return []

        # Fetch tickers for OI data
        tickers = self._get_tickers()
        if not tickers:
            log.warning('[delta_global] No tickers found')
            return []

        # Build product_id → metadata map
        product_map = {}
        for p in products:
            pid = p.get('id') or p.get('product_id')
            if pid:
                product_map[pid] = p

        rows = []
        now_ts = datetime.now(timezone.utc).isoformat()

        for ticker in tickers:
            pid = ticker.get('product_id')
            product = product_map.get(pid)
            if not product:
                continue

            oi = float(ticker.get('oi', 0) or
                       ticker.get('open_interest', 0) or 0)
            if oi == 0:
                continue

            # Extract strike and type from product metadata
            strike = float(product.get('strike_price', 0) or 0)
            if strike <= 0:
                continue

            contract_type = (product.get('contract_type', '') or '').lower()
            if 'call' in contract_type:
                opt_type = 'call'
            elif 'put' in contract_type:
                opt_type = 'put'
            else:
                continue

            # Parse expiry
            expiry_ts = product.get('settlement_time') or product.get('expiry_date', '')
            expiry = self._parse_expiry(expiry_ts)
            if not expiry:
                continue

            # Underlying price from ticker for USD conversion
            mark_price = float(ticker.get('mark_price', 0) or 0)
            spot_price = float(ticker.get('spot_price', 0) or
                               product.get('spot_price', 0) or 0)
            # OI is in contracts; oi_usd ≈ oi × spot_price (simplified)
            # Fall back to 0.0 (not oi) when spot_price unknown — avoids treating
            # each contract as $1 and producing garbage notional values.
            oi_usd = oi * spot_price if spot_price > 0 else 0.0

            underlying_sym = (product.get('underlying_asset', {}).get('symbol', '') or
                              product.get('underlying_asset_symbol', '') or
                              underlying).upper()

            if underlying_sym != underlying.upper():
                continue

            rows.append({
                'exchange': 'delta_global',
                'underlying': underlying.upper(),
                'expiry': expiry,
                'strike': strike,
                'type': opt_type,
                'oi': oi,
                'oi_usd': oi_usd,
                'mark_iv': 0.0,
                'timestamp': now_ts,
            })

        return rows

    def _get_products(self, underlying: str) -> list:
        """Fetch option products for underlying."""
        try:
            data = self._http_get(f'{self.base_url}/products', params={
                'contract_types': 'call_options,put_options',
                'state': 'live',
            })
            return data.get('result', []) if isinstance(data, dict) else []
        except Exception as e:
            log.warning('[delta_global] Products fetch failed: %s', e)
            return []

    def _get_tickers(self) -> list:
        """Fetch all tickers."""
        try:
            data = self._http_get(f'{self.base_url}/tickers', params={
                'contract_types': 'call_options,put_options',
            })
            return data.get('result', []) if isinstance(data, dict) else []
        except Exception as e:
            log.warning('[delta_global] Tickers fetch failed: %s', e)
            return []

    @staticmethod
    def _parse_expiry(expiry_val):
        """Parse various expiry formats to YYYY-MM-DD."""
        if not expiry_val:
            return None
        try:
            # Try ISO datetime string
            if isinstance(expiry_val, str):
                if _EXPIRY_PATTERN.match(expiry_val):
                    return expiry_val
                # Try parsing ISO datetime
                dt = datetime.fromisoformat(expiry_val.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')
            # Try unix timestamp (seconds or milliseconds)
            if isinstance(expiry_val, (int, float)):
                ts = expiry_val
                if ts > 1e12:  # milliseconds
                    ts = ts / 1000
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
        return None


# ============================================================================
# OKX Fetcher
# ============================================================================

class OKXOIFetcher(BaseOIFetcher):
    """
    OKX public API — single call returns all BTC-USD option OI.
    OKX BTC-USD options are coin-margined (1 contract = 0.01 BTC).

    instId format: BTC-USD-260328-60000-P
      asset  = BTC
      expiry = 260328 (YYMMDD) → 2026-03-28
      strike = 60000
      type   = P / C

    OI fields:
      oi     = number of contracts
      oiCcy  = OI in BTC (oi × 0.01)
      oiUsd  = OI in USD (oiCcy × index_price)  — use this directly

    Underlying price retrieved from the BTC-USD index ticker in the same call.
    """

    exchange_name = 'okx'
    base_url = 'https://www.okx.com/api/v5'

    # instId: BTC-USD-260328-60000-P
    _INST_RE = re.compile(
        r'^(?P<asset>[A-Z]+)-USD-(?P<date>\d{6})-(?P<strike>\d+)-(?P<type>[CP])$'
    )

    def _do_fetch(self, underlying: str) -> list:
        # Fetch all BTC-USD option OI in a single call
        data = self._http_get(f'{self.base_url}/public/open-interest', params={
            'instType': 'OPTION',
            'uly': f'{underlying.upper()}-USD',
        })

        items = data.get('data', [])
        if not items:
            log.warning('[okx] Empty OI response')
            return []

        rows = []
        for item in items:
            inst_id = item.get('instId', '')
            m = self._INST_RE.match(inst_id)
            if not m:
                continue

            oi_ccy = float(item.get('oiCcy', 0) or 0)  # OI in BTC
            if oi_ccy == 0:
                continue

            oi_usd_raw = float(item.get('oiUsd', 0) or 0)  # OI in USD

            strike = float(m.group('strike'))
            opt_type = 'call' if m.group('type') == 'C' else 'put'

            # Parse expiry: 260328 → 2026-03-28
            date_str = m.group('date')  # YYMMDD
            expiry = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"

            # OKX ts is in milliseconds
            ts_ms = int(item.get('ts', 0) or 0)
            if ts_ms:
                ts_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
            else:
                ts_str = datetime.now(timezone.utc).isoformat()

            rows.append({
                'exchange': 'okx',
                'underlying': underlying.upper(),
                'expiry': expiry,
                'strike': strike,
                'type': opt_type,
                'oi': oi_ccy,        # BTC units (consistent with Deribit)
                'oi_usd': oi_usd_raw,
                'mark_iv': float(item.get('markVol', 0) or 0),
                'timestamp': ts_str,
            })

        return rows


# ============================================================================
# Bybit Fetcher
# ============================================================================

class BybitOIFetcher(BaseOIFetcher):
    """
    Bybit public API — options tickers endpoint, single call for all BTC options.
    Bybit options are USDT-settled.

    Symbol format: BTC-24APR26-94000-C-USDT
      asset  = BTC
      expiry = 24APR26 (DDMMMYY)
      strike = 94000
      type   = C / P
      settle = USDT

    OI fields:
      openInterest      = OI in BTC
      underlyingPrice   = current BTC spot price
      oi_usd computed as openInterest × underlyingPrice
    """

    exchange_name = 'bybit'
    base_url = 'https://api.bybit.com/v5'

    # Symbol: BTC-24APR26-94000-C-USDT
    _SYM_RE = re.compile(
        r'^(?P<asset>[A-Z]+)-(?P<day>\d{1,2})(?P<mon>[A-Z]{3})(?P<year>\d{2})-(?P<strike>\d+)-(?P<type>[CP])-(?P<settle>[A-Z]+)$'
    )

    def _do_fetch(self, underlying: str) -> list:
        # Bybit options tickers — single call, all BTC options
        data = self._http_get(f'{self.base_url}/market/tickers', params={
            'category': 'option',
            'baseCoin': underlying.upper(),
        })

        items = data.get('result', {}).get('list', [])
        if not items:
            log.warning('[bybit] Empty tickers response')
            return []

        rows = []
        now_ts = datetime.now(timezone.utc).isoformat()

        for item in items:
            symbol = item.get('symbol', '')
            m = self._SYM_RE.match(symbol)
            if not m:
                continue

            oi = float(item.get('openInterest', 0) or 0)  # in BTC
            if oi == 0:
                continue

            underlying_price = float(item.get('underlyingPrice', 0) or 0)
            oi_usd = oi * underlying_price if underlying_price > 0 else 0.0
            mark_iv = float(item.get('markIv', 0) or 0)

            strike = float(m.group('strike'))
            opt_type = 'call' if m.group('type') == 'C' else 'put'

            # Parse expiry: 24APR26 → 2026-04-24
            day = m.group('day').zfill(2)
            mon = _MONTH_MAP.get(m.group('mon').upper(), '01')
            year = f"20{m.group('year')}"
            expiry = f"{year}-{mon}-{day}"

            rows.append({
                'exchange': 'bybit',
                'underlying': underlying.upper(),
                'underlying_price': underlying_price,
                'expiry': expiry,
                'strike': strike,
                'type': opt_type,
                'oi': oi,
                'oi_usd': oi_usd,
                'mark_iv': mark_iv,
                'timestamp': now_ts,
            })

        return rows


# ============================================================================
# Factory
# ============================================================================

def create_fetchers() -> list:
    """
    Create all enabled exchange fetchers.
    Active: Deribit, OKX, Bybit, Delta Global
    Disabled: Binance (eapi /openInterest returns -6010 for all expiries as of 2026-03-27)
    """
    fetchers = [
        DeribitOIFetcher(),
        OKXOIFetcher(),
        BybitOIFetcher(),
        DeltaGlobalOIFetcher(),
        BinanceOIFetcher(),   # disabled=True, kept for easy re-enable
    ]
    active = [f.exchange_name for f in fetchers if f.enabled]
    log.info('Created %d OI fetchers (%d active): %s',
             len(fetchers), len(active), active)
    return fetchers
