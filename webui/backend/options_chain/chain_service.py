"""
Options Chain Service
=====================
Service layer for fetching options chain data from Delta Exchange.
Includes caching to reduce API calls.

Delta Exchange API Endpoints:
- GET /v2/products - Get all products (including options)
- GET /v2/tickers?underlying_asset_symbols=BTC&contract_types=call_options,put_options

Author: Options Chain Module
Date: January 5, 2026
"""

import os
import sys
import time
import logging
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Any
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.loader import get_config, get_api_credentials
from webui.backend.sealed import sealed

log = logging.getLogger(__name__)

# ============================================================================
# Cache Layer (Simple In-Memory)
# ============================================================================

class ChainCache:
    """
    Simple in-memory cache with TTL support.
    For production, consider Redis.
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._ttl = {
            'products': 300,      # 5 minutes for product list
            'expirations': 300,   # 5 minutes for expiry list
            'chain_data': 10,     # 10 seconds for chain data
            'tickers': 5          # 5 seconds for ticker data
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        if time.time() > entry['expires_at']:
            del self._cache[key]
            return None
        
        return entry['value']
    
    def set(self, key: str, value: Any, cache_type: str = 'chain_data'):
        """Set value in cache with TTL based on type"""
        ttl = self._ttl.get(cache_type, 10)
        self._cache[key] = {
            'value': value,
            'expires_at': time.time() + ttl,
            'cached_at': time.time()
        }
    
    def invalidate(self, pattern: str = None):
        """Invalidate cache entries matching pattern"""
        if pattern is None:
            self._cache.clear()
            return
        
        keys_to_delete = [k for k in self._cache if pattern in k]
        for k in keys_to_delete:
            del self._cache[k]


# Global cache instance
_cache = ChainCache()


# ============================================================================
# Options Chain Service
# ============================================================================

class OptionsChainService:
    """
    Service for fetching options chain data from Delta Exchange.
    """
    
    def __init__(self):
        self.cfg = get_config()
        self.api_base = self._get_api_base()
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def _get_api_base(self) -> str:
        """Get API base URL based on trading mode"""
        mode = self.cfg.trading_mode
        if mode == 'testnet':
            return 'https://testnet-api.delta.exchange'
        else:
            return 'https://api.india.delta.exchange'
    
    def _request(self, method: str, endpoint: str, params: Dict = None) -> Dict:
        """Make HTTP request to Delta Exchange API"""
        url = f"{self.api_base}{endpoint}"
        
        try:
            log.debug(f"API Request: {method} {url} params={params}")
            
            if method == 'GET':
                response = self.session.get(url, params=params, timeout=10)
            else:
                response = self.session.post(url, json=params, timeout=10)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            log.error(f"API timeout: {url}")
            raise Exception(f"API timeout after 10 seconds")
        except requests.exceptions.HTTPError as e:
            log.error(f"API HTTP error: {e}")
            raise
        except Exception as e:
            log.error(f"API error: {e}")
            raise
    
    @sealed
    def get_expirations(self, underlying: str = 'BTC') -> List[str]:
        """
        Get list of available expiry dates for options.
        Filters out contracts that have expired (expired at 5:30 PM IST).

        SEALED — v1.0.0 — March 4, 2026
        Do not modify without UNSEAL command in AI_SEAL.md

        Returns:
            List of expiry dates in DDMMYYYY format (only active contracts)
        """
        cache_key = f"expirations_{underlying}"
        cached = _cache.get(cache_key)
        if cached:
            log.debug(f"Cache hit: {cache_key}")
            return cached
        
        log.info(f"Fetching expirations for {underlying} from API")
        
        # Get all products
        products = self._get_option_products(underlying)
        
        # Get current time in IST
        ist_tz = ZoneInfo('Asia/Kolkata')
        now_ist = datetime.now(ist_tz)
        
        # Extract unique expiry dates and filter expired contracts
        expirations = set()
        for product in products:
            expiry = product.get('settlement_time')
            if expiry:
                # Parse expiry and convert to DDMMYYYY
                try:
                    dt = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                    
                    # Convert to IST for comparison
                    dt_ist = dt.astimezone(ist_tz)
                    
                    # Check if contract has expired (expires at 5:30 PM IST)
                    # If today's date matches expiry date and current time is >= 5:30 PM IST, skip it
                    expiry_cutoff = dt_ist.replace(hour=17, minute=30, second=0, microsecond=0)
                    
                    if now_ist >= expiry_cutoff and now_ist.date() == dt_ist.date():
                        log.debug(f"Filtering expired contract: {dt.strftime('%d%m%Y')} (expired at 5:30 PM IST)")
                        continue
                    
                    # Also filter if expiry date is in the past
                    if dt_ist.date() < now_ist.date():
                        log.debug(f"Filtering past expiry: {dt.strftime('%d%m%Y')}")
                        continue
                    
                    formatted = dt.strftime('%d%m%Y')
                    expirations.add(formatted)
                except Exception as e:
                    log.warning(f"Failed to parse expiry {expiry}: {e}")
        
        # Sort by date
        sorted_expirations = sorted(list(expirations), 
                                    key=lambda x: datetime.strptime(x, '%d%m%Y'))
        
        _cache.set(cache_key, sorted_expirations, 'expirations')
        log.info(f"Found {len(sorted_expirations)} active expirations for {underlying} (filtered expired contracts)")
        
        return sorted_expirations
    
    def _get_option_products(self, underlying: str = 'BTC') -> List[Dict]:
        """
        Get all option products for underlying asset.
        
        Returns:
            List of product dictionaries
        """
        cache_key = f"products_{underlying}"
        cached = _cache.get(cache_key)
        if cached:
            return cached
        
        log.info(f"Fetching products for {underlying} from API")
        
        response = self._request('GET', '/v2/products')
        all_products = response.get('result', [])
        
        # Filter for options
        option_products = []
        for product in all_products:
            contract_type = product.get('contract_type', '')
            product_underlying = product.get('underlying_asset', {}).get('symbol', '')
            
            # Filter: options only, matching underlying
            if contract_type in ['call_options', 'put_options']:
                if product_underlying == underlying:
                    option_products.append(product)
        
        _cache.set(cache_key, option_products, 'products')
        log.info(f"Found {len(option_products)} option products for {underlying}")
        
        return option_products
    
    @sealed
    def get_chain_data(self, underlying: str, expiry: str) -> Dict:
        """
        Get full options chain data for specific underlying and expiry.

        SEALED — v1.0.0 — March 4, 2026
        Do not modify without UNSEAL command in AI_SEAL.md

        Args:
            underlying: BTC or ETH
            expiry: Expiry date in DDMMYYYY format

        Returns:
            Chain data with spot price, ATM strike, and all strikes
        """
        cache_key = f"chain_{underlying}_{expiry}"
        cached = _cache.get(cache_key)
        if cached:
            log.debug(f"Cache hit: {cache_key}")
            return cached
        
        log.info(f"Fetching chain data for {underlying} expiry {expiry}")
        
        # Get spot price
        spot_price = self._get_spot_price(underlying)
        
        # Get all tickers for this underlying (with Greeks, IV, volume)
        tickers = self._get_option_tickers(underlying)
        
        # Filter and organize by strike
        chain = self._build_chain(tickers, expiry, spot_price)
        
        result = {
            'underlying': underlying,
            'expiry': expiry,
            'spot_price': spot_price,
            'atm_strike': chain.get('atm_strike'),
            'chain': chain.get('strikes', []),
            'summary': {
                'total_calls': chain.get('total_calls', 0),
                'total_puts': chain.get('total_puts', 0),
                'call_oi': chain.get('call_oi', 0),
                'put_oi': chain.get('put_oi', 0)
            },
            'cached_at': time.time()
        }
        
        _cache.set(cache_key, result, 'chain_data')
        
        return result
    
    def _get_spot_price(self, underlying: str) -> float:
        """Get current spot price for underlying"""
        cache_key = f"spot_{underlying}"
        cached = _cache.get(cache_key)
        if cached:
            return cached
        
        symbol = f"{underlying}USD"
        
        try:
            response = self._request('GET', f'/v2/tickers/{symbol}')
            result = response.get('result', {})
            
            # Get mark price or close price
            spot = float(result.get('mark_price') or result.get('close') or 0)
            
            if spot > 0:
                _cache.set(cache_key, spot, 'tickers')
                return spot
            
        except Exception as e:
            log.error(f"Failed to get spot price for {underlying}: {e}")
        
        return 0.0
    
    def _get_option_tickers(self, underlying: str) -> List[Dict]:
        """
        Get all option tickers with Greeks and IV.
        
        Uses: GET /v2/tickers?underlying_asset_symbols=BTC&contract_types=call_options,put_options
        """
        cache_key = f"tickers_{underlying}"
        cached = _cache.get(cache_key)
        if cached:
            return cached
        
        log.debug(f"Fetching option tickers for {underlying}")
        
        params = {
            'underlying_asset_symbols': underlying,
            'contract_types': 'call_options,put_options'
        }
        
        response = self._request('GET', '/v2/tickers', params=params)
        tickers = response.get('result', [])
        
        _cache.set(cache_key, tickers, 'tickers')
        log.debug(f"Fetched {len(tickers)} option tickers for {underlying}")
        
        return tickers
    
    def _build_chain(self, tickers: List[Dict], expiry: str, spot_price: float) -> Dict:
        """
        Build organized chain structure from tickers.
        
        Returns:
            {
                'atm_strike': 93000,
                'strikes': [
                    {
                        'strike': 91000,
                        'call': {...},
                        'put': {...}
                    },
                    ...
                ],
                'total_calls': 50,
                'total_puts': 50,
                'call_oi': 1234,
                'put_oi': 2345
            }
        """
        # Convert expiry to expected format for matching
        # DDMMYYYY -> different formats to check
        expiry_dt = datetime.strptime(expiry, '%d%m%Y')
        
        # Group by strike
        strikes_map: Dict[float, Dict] = {}
        total_calls = 0
        total_puts = 0
        call_oi = 0
        put_oi = 0
        
        for ticker in tickers:
            symbol = ticker.get('symbol', '')
            
            # Parse symbol to extract type, underlying, strike, expiry
            parsed = self._parse_option_symbol(symbol)
            if not parsed:
                continue
            
            # Check expiry matches
            ticker_expiry = parsed.get('expiry')
            if ticker_expiry != expiry:
                continue
            
            strike = parsed['strike']
            option_type = parsed['type']  # 'call' or 'put'
            
            if strike not in strikes_map:
                strikes_map[strike] = {
                    'strike': strike,
                    'call': None,
                    'put': None
                }
            
            # Build option data
            option_data = {
                'symbol': symbol,
                'bid': self._safe_float(ticker.get('quotes', {}).get('best_bid')),
                'ask': self._safe_float(ticker.get('quotes', {}).get('best_ask')),
                'bid_size': self._safe_int(ticker.get('quotes', {}).get('bid_size')),
                'ask_size': self._safe_int(ticker.get('quotes', {}).get('ask_size')),
                'bid_iv': self._safe_float(ticker.get('quotes', {}).get('bid_iv')),
                'ask_iv': self._safe_float(ticker.get('quotes', {}).get('ask_iv')),
                'mark_price': self._safe_float(ticker.get('mark_price')),
                'iv': self._safe_float(ticker.get('quotes', {}).get('mark_iv') or ticker.get('mark_vol')),
                'delta': self._safe_float(ticker.get('greeks', {}).get('delta')),
                'gamma': self._safe_float(ticker.get('greeks', {}).get('gamma')),
                'theta': self._safe_float(ticker.get('greeks', {}).get('theta')),
                'vega': self._safe_float(ticker.get('greeks', {}).get('vega')),
                'volume': self._safe_float(ticker.get('volume')),
                'oi': self._safe_int(ticker.get('oi_contracts') or ticker.get('oi')),
                'turnover': self._safe_float(ticker.get('turnover_usd') or ticker.get('turnover')),
                'strike_price': self._safe_float(ticker.get('strike_price')),
                'spot_price': self._safe_float(ticker.get('spot_price'))
            }
            
            strikes_map[strike][option_type] = option_data
            
            if option_type == 'call':
                total_calls += 1
                call_oi += option_data['oi']
            else:
                total_puts += 1
                put_oi += option_data['oi']
        
        # Convert to sorted list
        sorted_strikes = sorted(strikes_map.values(), key=lambda x: x['strike'])
        
        # Find ATM strike (closest to spot)
        atm_strike = None
        min_diff = float('inf')
        for s in sorted_strikes:
            diff = abs(s['strike'] - spot_price)
            if diff < min_diff:
                min_diff = diff
                atm_strike = s['strike']
        
        return {
            'atm_strike': atm_strike,
            'strikes': sorted_strikes,
            'total_calls': total_calls,
            'total_puts': total_puts,
            'call_oi': call_oi,
            'put_oi': put_oi
        }
    
    def _parse_option_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Parse Delta Exchange option symbol.
        
        Format: C-BTC-99000-300126 or P-BTC-99000-300126
        
        Returns:
            {
                'type': 'call' or 'put',
                'underlying': 'BTC',
                'strike': 99000,
                'expiry': '30012026'
            }
        """
        try:
            parts = symbol.split('-')
            if len(parts) != 4:
                return None
            
            option_type = 'call' if parts[0] == 'C' else 'put' if parts[0] == 'P' else None
            if not option_type:
                return None
            
            underlying = parts[1]
            strike = float(parts[2])
            
            # Expiry is in DDMMYY format, convert to DDMMYYYY
            expiry_raw = parts[3]
            if len(expiry_raw) == 6:
                # DDMMYY -> DDMMYYYY
                expiry = expiry_raw[:4] + '20' + expiry_raw[4:]
            else:
                expiry = expiry_raw
            
            return {
                'type': option_type,
                'underlying': underlying,
                'strike': strike,
                'expiry': expiry
            }
            
        except Exception as e:
            log.debug(f"Failed to parse symbol {symbol}: {e}")
            return None
    
    def _safe_float(self, value) -> float:
        """Safely convert to float"""
        if value is None:
            return 0.0
        try:
            return float(value)
        except:
            return 0.0
    
    def _safe_int(self, value) -> int:
        """Safely convert to int"""
        if value is None:
            return 0
        try:
            return int(float(value))
        except:
            return 0
    
    def invalidate_cache(self, underlying: str = None, expiry: str = None):
        """Invalidate cache entries.

        When invalidating a specific chain (underlying + expiry), also clear the
        tickers_{underlying} cache.  The retry path in mmm_monitor calls
        invalidate_cache immediately before re-calling get_chain_data; without
        this, _get_option_tickers() gets a cache-hit on the same stale data
        (tickers TTL = 5 s) and the rebuilt chain is identical — causing repeated
        "Nearest OTM strikes: NONE" failures even though a fresh chain was
        nominally fetched.
        """
        if underlying and expiry:
            _cache.invalidate(f"chain_{underlying}_{expiry}")
            # Also clear the tickers cache so _get_option_tickers() fetches fresh
            # data when get_chain_data rebuilds the chain on the next call.
            _cache.invalidate(f"tickers_{underlying}")
        elif underlying:
            _cache.invalidate(underlying)
            _cache.invalidate(f"tickers_{underlying}")
        else:
            _cache.invalidate()

        log.info(f"Cache invalidated: underlying={underlying}, expiry={expiry}")
    
    def get_option_ticker(self, symbol: str) -> Dict:
        """
        Get current ticker for a specific option symbol.
        
        Args:
            symbol: Option symbol (e.g., C-BTC-95000-060126)
            
        Returns:
            Ticker data with bid/ask, IV, Greeks
        """
        # Extract underlying from symbol
        parts = symbol.split('-')
        if len(parts) < 2:
            return None
        
        underlying = parts[1]  # BTC or ETH
        
        # Get all tickers for underlying
        tickers = self._get_option_tickers(underlying)
        
        # Find matching ticker
        for ticker in tickers:
            ticker_symbol = ticker.get('symbol', '')
            if ticker_symbol == symbol:
                quotes = ticker.get('quotes', {})
                greeks = ticker.get('greeks', {})
                
                return {
                    'symbol': symbol,
                    'bid': self._safe_float(quotes.get('best_bid')),
                    'ask': self._safe_float(quotes.get('best_ask')),
                    'bid_size': self._safe_int(quotes.get('best_bid_size')),
                    'ask_size': self._safe_int(quotes.get('best_ask_size')),
                    'mark_price': self._safe_float(quotes.get('mark_price')),
                    'iv': self._safe_float(quotes.get('mark_iv')),
                    'delta': self._safe_float(greeks.get('delta')),
                    'gamma': self._safe_float(greeks.get('gamma')),
                    'theta': self._safe_float(greeks.get('theta')),
                    'vega': self._safe_float(greeks.get('vega')),
                    'volume': self._safe_float(ticker.get('turnover_usd')),
                    'oi': self._safe_int(ticker.get('oi'))
                }
        
        return None
