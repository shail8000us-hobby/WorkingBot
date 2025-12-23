"""
Delta Exchange OHLCV Data Fetcher

Fetches historical 1-minute OHLCV candles from Delta Exchange via ccxt.
Implements intelligent caching, rate limiting, and data validation.
"""

import os
import time
import logging
import pandas as pd
import ccxt
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

log = logging.getLogger("backtest.data")


class DeltaOHLCV:
    """
    Fetches and caches OHLCV data from Delta Exchange.
    
    Features:
    - Rate limit compliance (max 10 req/sec)
    - Local parquet cache by symbol+timeframe+date range
    - Data validation (gaps, OHLCV integrity)
    - Chunked fetching (1000 candles per request)
    """
    
    def __init__(
        self,
        symbol: str = "BTC/USD:USD",
        timeframe: str = "1m",
        is_testnet: bool = False,
        cache_dir: str = "backtest/data/cache"
    ):
        """
        Initialize Delta OHLCV fetcher.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USD:USD")
            timeframe: Candle interval (1m, 5m, 15m, 1h, etc.)
            is_testnet: Use testnet or production API
            cache_dir: Directory for parquet cache files
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.is_testnet = is_testnet
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ccxt exchange
        self.exchange = self._init_exchange()
        
        # Rate limiting (10 req/sec = 100ms between requests)
        self.rate_limit_ms = 100
        self.last_request_time = 0
        
        log.info(f"DeltaOHLCV initialized: {symbol} {timeframe} {'TESTNET' if is_testnet else 'LIVE'}")
    
    def _init_exchange(self) -> ccxt.Exchange:
        """Initialize ccxt Delta Exchange instance."""
        if self.is_testnet:
            base_url = "https://cdn-ind.testnet.deltaex.org"
        else:
            base_url = "https://api.india.delta.exchange"
        
        exchange = ccxt.delta({
            'enableRateLimit': True,
            'rateLimit': self.rate_limit_ms,
            'urls': {
                'api': {
                    'public': base_url,
                    'private': base_url
                }
            },
            'options': {'defaultType': 'future'}
        })
        
        return exchange
    
    def fetch(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for the specified date range.
        
        Args:
            since: Start datetime (default: 30 days ago)
            until: End datetime (default: now)
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        # Set default date range
        if until is None:
            until = datetime.utcnow()
        if since is None:
            since = until - timedelta(days=30)
        
        log.info(f"Fetching {self.symbol} {self.timeframe} from {since} to {until}")
        
        # Check cache first
        if not force_refresh:
            cached_data = self._load_from_cache(since, until)
            if cached_data is not None:
                log.info(f"Loaded {len(cached_data)} candles from cache")
                return cached_data
        
        # Fetch from exchange
        data = self._fetch_from_exchange(since, until)
        
        # Validate data
        data = self._validate_data(data)
        
        # Save to cache
        self._save_to_cache(data, since, until)
        
        log.info(f"Fetched {len(data)} candles from exchange")
        return data
    
    def _fetch_from_exchange(
        self,
        since: datetime,
        until: datetime
    ) -> pd.DataFrame:
        """Fetch data from Delta Exchange in chunks."""
        since_ms = int(since.timestamp() * 1000)
        until_ms = int(until.timestamp() * 1000)
        
        all_candles = []
        current_since = since_ms
        
        # Chunk size: 1000 candles per request (ccxt limit)
        chunk_size = 1000
        
        while current_since < until_ms:
            # Rate limiting
            self._respect_rate_limit()
            
            try:
                # Fetch chunk
                candles = self.exchange.fetch_ohlcv(
                    self.symbol,
                    timeframe=self.timeframe,
                    since=current_since,
                    limit=chunk_size
                )
                
                if not candles:
                    break
                
                all_candles.extend(candles)
                
                # Move to next chunk
                last_timestamp = candles[-1][0]
                if last_timestamp <= current_since:
                    # Prevent infinite loop
                    break
                current_since = last_timestamp + 1
                
                log.debug(f"Fetched chunk: {len(candles)} candles, up to {datetime.fromtimestamp(last_timestamp/1000)}")
                
            except Exception as e:
                log.error(f"Error fetching chunk at {datetime.fromtimestamp(current_since/1000)}: {e}")
                break
        
        # Convert to DataFrame
        if not all_candles:
            log.warning("No candles fetched")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        df = pd.DataFrame(
            all_candles,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Filter to requested range
        df = df[(df['timestamp'] >= since) & (df['timestamp'] <= until)]
        
        return df.reset_index(drop=True)
    
    def _validate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate OHLCV data quality.
        
        Checks:
        - OHLCV relationships (high >= low, high >= open/close, etc.)
        - Gaps in timestamps
        - Suspicious volume spikes
        """
        if df.empty:
            return df
        
        # Check OHLCV integrity
        invalid_ohlc = (
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close'])
        )
        
        if invalid_ohlc.any():
            n_invalid = invalid_ohlc.sum()
            log.warning(f"Found {n_invalid} candles with invalid OHLCV relationships")
            # Remove invalid candles
            df = df[~invalid_ohlc].reset_index(drop=True)
        
        # Check for gaps (only for 1m timeframe)
        if self.timeframe == '1m' and len(df) > 1:
            df_sorted = df.sort_values('timestamp')
            time_diffs = df_sorted['timestamp'].diff()
            expected_diff = pd.Timedelta(minutes=1)
            
            gaps = time_diffs[time_diffs > expected_diff * 1.5]  # Allow 50% tolerance
            if len(gaps) > 0:
                log.warning(f"Found {len(gaps)} gaps in timestamp sequence")
                log.debug(f"Gap locations: {gaps.index.tolist()}")
        
        # Check for zero volume
        zero_volume = df['volume'] == 0
        if zero_volume.any():
            log.info(f"Found {zero_volume.sum()} candles with zero volume")
        
        return df
    
    def _respect_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = (time.time() * 1000) - self.last_request_time
        if elapsed < self.rate_limit_ms:
            time.sleep((self.rate_limit_ms - elapsed) / 1000)
        self.last_request_time = time.time() * 1000
    
    def _get_cache_filename(self, since: datetime, until: datetime) -> Path:
        """Generate cache filename based on parameters."""
        symbol_safe = self.symbol.replace('/', '_').replace(':', '_')
        since_str = since.strftime('%Y%m%d')
        until_str = until.strftime('%Y%m%d')
        
        filename = f"{symbol_safe}_{self.timeframe}_{since_str}_{until_str}.parquet"
        return self.cache_dir / filename
    
    def _load_from_cache(
        self,
        since: datetime,
        until: datetime
    ) -> Optional[pd.DataFrame]:
        """Load data from parquet cache if available."""
        cache_file = self._get_cache_filename(since, until)
        
        if cache_file.exists():
            try:
                df = pd.read_parquet(cache_file)
                # Validate cache covers requested range
                if not df.empty:
                    cached_since = df['timestamp'].min()
                    cached_until = df['timestamp'].max()
                    
                    if cached_since <= since and cached_until >= until:
                        return df[(df['timestamp'] >= since) & (df['timestamp'] <= until)]
            except Exception as e:
                log.warning(f"Failed to load cache: {e}")
        
        return None
    
    def _save_to_cache(
        self,
        df: pd.DataFrame,
        since: datetime,
        until: datetime
    ):
        """Save data to parquet cache."""
        if df.empty:
            return
        
        cache_file = self._get_cache_filename(since, until)
        
        try:
            df.to_parquet(cache_file, compression='snappy', index=False)
            log.debug(f"Saved {len(df)} candles to cache: {cache_file.name}")
        except Exception as e:
            log.warning(f"Failed to save cache: {e}")
    
    def clear_cache(self):
        """Remove all cached data for this symbol+timeframe."""
        symbol_safe = self.symbol.replace('/', '_').replace(':', '_')
        pattern = f"{symbol_safe}_{self.timeframe}_*.parquet"
        
        removed = 0
        for cache_file in self.cache_dir.glob(pattern):
            cache_file.unlink()
            removed += 1
        
        log.info(f"Cleared {removed} cache files")

