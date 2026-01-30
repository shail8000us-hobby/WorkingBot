"""
Delta Exchange Historical Data Fetcher
======================================
Fetches maximum historical OHLCV candles with pagination and rate limiting.
Production-ready for Delta Exchange India API.

Author: WorkingBot
Version: 1.0.0
"""

import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
from dataclasses import dataclass, field
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration for Delta Exchange API."""
    window_seconds: int = 300  # 5 minute window
    max_units: int = 10000  # Maximum units per window
    candle_weight: int = 3  # Weight per candle request
    safety_buffer: float = 0.9  # Use 90% of limit for safety


@dataclass
class FetchStats:
    """Statistics for data fetching operations."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_candles: int = 0
    rate_limit_waits: int = 0
    start_time: float = field(default_factory=time.time)
    
    @property
    def duration_seconds(self) -> float:
        return time.time() - self.start_time
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests * 100


class DeltaHistoricalFetcher:
    """
    Fetch maximum historical OHLCV data from Delta Exchange India.
    
    Features:
    - Pagination handling (2000 candle limit per request)
    - Rate limiting (10,000 units per 5-minute window)
    - Automatic retry on failures
    - Data validation and deduplication
    - Progress logging
    
    Usage:
        fetcher = DeltaHistoricalFetcher()
        df = fetcher.fetch_maximum_history("BTCUSD", "1h", years_back=3)
        fetcher.save_to_csv(df, "btcusd_1h.csv")
    """
    
    # API Configuration
    BASE_URL_PRODUCTION = "https://api.india.delta.exchange"
    BASE_URL_TESTNET = "https://cdn-ind.testnet.deltaex.org"
    
    # Maximum candles per request (API limitation)
    MAX_CANDLES_PER_REQUEST = 2000
    
    # Supported resolutions with seconds per candle
    RESOLUTION_SECONDS = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "2h": 7200,
        "4h": 14400,
        "6h": 21600,
        "1d": 86400,
        "1w": 604800
    }
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    REQUEST_TIMEOUT = 30
    
    def __init__(self, testnet: bool = False):
        """
        Initialize the historical data fetcher.
        
        Args:
            testnet: Use testnet environment if True
        """
        self.base_url = self.BASE_URL_TESTNET if testnet else self.BASE_URL_PRODUCTION
        self.testnet = testnet
        self.rate_limit = RateLimitConfig()
        self.request_count = 0
        self.window_start = time.time()
        self.stats = FetchStats()
        
        # Configure session with proper headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DeltaHistoricalFetcher/1.0 (WorkingBot)',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        logger.info(f"Initialized DeltaHistoricalFetcher (testnet={testnet})")
        logger.info(f"Base URL: {self.base_url}")
    
    def _check_rate_limit(self) -> None:
        """
        Check rate limit and wait if necessary.
        Implements 5-minute rolling window with 10,000 unit quota.
        """
        current_time = time.time()
        elapsed = current_time - self.window_start
        
        # Reset window if 5 minutes passed
        if elapsed >= self.rate_limit.window_seconds:
            self.request_count = 0
            self.window_start = current_time
            logger.debug("Rate limit window reset")
            return
        
        # Calculate used weight
        used_weight = self.request_count * self.rate_limit.candle_weight
        max_safe_weight = int(self.rate_limit.max_units * self.rate_limit.safety_buffer)
        
        # Wait if would exceed limit
        if used_weight + self.rate_limit.candle_weight > max_safe_weight:
            sleep_time = self.rate_limit.window_seconds - elapsed + 1
            logger.warning(f"Rate limit approaching ({used_weight}/{max_safe_weight}). "
                          f"Sleeping {sleep_time:.1f}s...")
            self.stats.rate_limit_waits += 1
            time.sleep(sleep_time)
            self.request_count = 0
            self.window_start = time.time()
    
    def _make_request(
        self, 
        endpoint: str, 
        params: Dict
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Make an API request with retry logic.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            Tuple of (success, data)
        """
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.MAX_RETRIES):
            try:
                self._check_rate_limit()
                
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.REQUEST_TIMEOUT
                )
                
                self.request_count += 1
                self.stats.total_requests += 1
                
                # Check for rate limit response
                if response.status_code == 429:
                    logger.warning("Rate limit hit (429). Waiting 60 seconds...")
                    time.sleep(60)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                if data.get("success"):
                    self.stats.successful_requests += 1
                    return True, data
                else:
                    logger.warning(f"API returned success=false: {data}")
                    self.stats.failed_requests += 1
                    return False, None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{self.MAX_RETRIES})")
                time.sleep(self.RETRY_DELAY * (attempt + 1))
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                time.sleep(self.RETRY_DELAY * (attempt + 1))
        
        self.stats.failed_requests += 1
        return False, None
    
    def fetch_candles(
        self,
        symbol: str,
        resolution: str,
        start_timestamp: int,
        end_timestamp: int,
        show_progress: bool = True
    ) -> List[Dict]:
        """
        Fetch OHLCV candles with pagination for maximum history.
        
        Args:
            symbol: Product symbol (e.g., "BTCUSD", "MARK:BTCUSD", "FUNDING:BTCUSD")
            resolution: Candle resolution (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
            start_timestamp: Start time (Unix seconds)
            end_timestamp: End time (Unix seconds)
            show_progress: Show progress logs
            
        Returns:
            List of OHLCV candles sorted by time
        """
        if resolution not in self.RESOLUTION_SECONDS:
            raise ValueError(f"Invalid resolution: {resolution}. "
                           f"Valid: {list(self.RESOLUTION_SECONDS.keys())}")
        
        all_candles = []
        seconds_per_candle = self.RESOLUTION_SECONDS[resolution]
        
        # Calculate time range per request (2000 candles max)
        time_per_request = self.MAX_CANDLES_PER_REQUEST * seconds_per_candle
        
        # Calculate total expected requests
        total_time = end_timestamp - start_timestamp
        expected_requests = max(1, total_time // time_per_request + 1)
        
        current_start = start_timestamp
        request_num = 0
        
        if show_progress:
            logger.info(f"Fetching {symbol} {resolution} candles...")
            logger.info(f"Date range: {datetime.fromtimestamp(start_timestamp)} to "
                       f"{datetime.fromtimestamp(end_timestamp)}")
            logger.info(f"Expected requests: ~{expected_requests}")
        
        while current_start < end_timestamp:
            current_end = min(current_start + time_per_request, end_timestamp)
            request_num += 1
            
            params = {
                "symbol": symbol,
                "resolution": resolution,
                "start": current_start,
                "end": current_end
            }
            
            success, data = self._make_request("/v2/history/candles", params)
            
            if success and data.get("result"):
                candles = data["result"]
                all_candles.extend(candles)
                self.stats.total_candles += len(candles)
                
                if show_progress:
                    progress = min(100, (request_num / expected_requests) * 100)
                    logger.info(f"[{progress:.1f}%] Fetched {len(candles)} candles "
                               f"({datetime.fromtimestamp(current_start).strftime('%Y-%m-%d')})")
            else:
                logger.warning(f"Failed to fetch candles for period starting "
                              f"{datetime.fromtimestamp(current_start)}")
            
            current_start = current_end
            
            # Small delay between requests to be nice to the API
            time.sleep(0.1)
        
        # Remove duplicates and sort
        unique_candles = self._deduplicate_candles(all_candles)
        
        if show_progress:
            logger.info(f"Total unique candles: {len(unique_candles)}")
            logger.info(f"Fetch stats: {self.stats.successful_requests} successful, "
                       f"{self.stats.failed_requests} failed, "
                       f"{self.stats.rate_limit_waits} rate limit waits")
        
        return unique_candles
    
    def _deduplicate_candles(self, candles: List[Dict]) -> List[Dict]:
        """Remove duplicate candles and sort by time."""
        seen = set()
        unique = []
        
        for candle in candles:
            candle_time = candle.get("time")
            if candle_time is not None and candle_time not in seen:
                seen.add(candle_time)
                unique.append(candle)
        
        unique.sort(key=lambda x: x["time"])
        return unique
    
    def fetch_maximum_history(
        self,
        symbol: str,
        resolution: str = "1h",
        years_back: int = 3,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch maximum available historical data for a symbol.
        
        Args:
            symbol: Product symbol (e.g., "BTCUSD")
            resolution: Candle resolution (default: "1h")
            years_back: Years of history to fetch (default: 3)
            end_date: End date (default: now)
            
        Returns:
            DataFrame with columns: open, high, low, close, volume, unix_time
            Index: timestamp (UTC datetime)
        """
        if end_date is None:
            end_date = datetime.now()
        
        start_date = end_date - timedelta(days=365 * years_back)
        
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())
        
        logger.info(f"Fetching maximum history for {symbol}")
        logger.info(f"Resolution: {resolution}, Years back: {years_back}")
        
        # Reset stats for this fetch
        self.stats = FetchStats()
        
        candles = self.fetch_candles(
            symbol=symbol,
            resolution=resolution,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp
        )
        
        if not candles:
            logger.warning("No candles fetched")
            return pd.DataFrame()
        
        df = self._candles_to_dataframe(candles)
        
        logger.info(f"Fetch completed in {self.stats.duration_seconds:.1f}s")
        logger.info(f"DataFrame shape: {df.shape}")
        logger.info(f"Date range: {df.index.min()} to {df.index.max()}")
        
        return df
    
    def _candles_to_dataframe(self, candles: List[Dict]) -> pd.DataFrame:
        """Convert candle list to pandas DataFrame."""
        df = pd.DataFrame(candles)
        
        # Convert timestamp
        df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("timestamp")
        
        # Rename and select columns
        df = df.rename(columns={"time": "unix_time"})
        
        # Ensure proper column order
        columns = ["open", "high", "low", "close", "volume", "unix_time"]
        df = df[[col for col in columns if col in df.columns]]
        
        # Convert to proper types
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def get_available_products(
        self,
        contract_types: Optional[List[str]] = None,
        states: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Get list of available trading products.
        
        Args:
            contract_types: Filter by types (perpetual_futures, call_options, put_options)
            states: Filter by states (live, expired, upcoming)
            
        Returns:
            List of product details
        """
        params = {}
        
        if contract_types:
            params["contract_types"] = ",".join(contract_types)
        if states:
            params["states"] = ",".join(states)
        
        success, data = self._make_request("/v2/products", params)
        
        if success and data:
            products = data.get("result", [])
            logger.info(f"Found {len(products)} products")
            return products
        
        return []
    
    def get_perpetual_symbols(self) -> List[str]:
        """Get list of perpetual futures symbols."""
        products = self.get_available_products(
            contract_types=["perpetual_futures"],
            states=["live"]
        )
        return [p["symbol"] for p in products if "symbol" in p]
    
    def save_to_csv(
        self,
        df: pd.DataFrame,
        filepath: str,
        include_index: bool = True
    ) -> None:
        """
        Save DataFrame to CSV file.
        
        Args:
            df: DataFrame to save
            filepath: Output file path
            include_index: Include timestamp index
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(filepath, index=include_index)
        logger.info(f"Saved {len(df)} candles to {filepath}")
    
    def save_to_parquet(
        self,
        df: pd.DataFrame,
        filepath: str
    ) -> None:
        """
        Save DataFrame to Parquet file (more efficient).
        
        Args:
            df: DataFrame to save
            filepath: Output file path
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_parquet(filepath)
        logger.info(f"Saved {len(df)} candles to {filepath}")
    
    def validate_data(self, df: pd.DataFrame) -> Dict:
        """
        Validate OHLCV data quality.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            Dict with validation results
        """
        results = {
            "total_rows": len(df),
            "null_counts": df.isnull().sum().to_dict(),
            "has_gaps": False,
            "gap_count": 0,
            "invalid_ohlc": 0,
            "date_range": {
                "start": str(df.index.min()) if len(df) > 0 else None,
                "end": str(df.index.max()) if len(df) > 0 else None
            }
        }
        
        if len(df) > 1:
            # Check for gaps
            time_diffs = df["unix_time"].diff().dropna()
            expected_diff = time_diffs.mode().iloc[0] if len(time_diffs) > 0 else 0
            gaps = time_diffs[time_diffs > expected_diff * 1.5]
            results["has_gaps"] = len(gaps) > 0
            results["gap_count"] = len(gaps)
            
            # Check OHLC validity (high >= low, etc.)
            invalid = (
                (df["high"] < df["low"]) |
                (df["high"] < df["open"]) |
                (df["high"] < df["close"]) |
                (df["low"] > df["open"]) |
                (df["low"] > df["close"])
            )
            results["invalid_ohlc"] = invalid.sum()
        
        return results


# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fetch Delta Exchange historical data")
    parser.add_argument("--symbol", default="BTCUSD", help="Trading symbol")
    parser.add_argument("--resolution", default="1h", help="Candle resolution")
    parser.add_argument("--years", type=int, default=2, help="Years of history")
    parser.add_argument("--output", default=None, help="Output CSV file")
    parser.add_argument("--testnet", action="store_true", help="Use testnet")
    parser.add_argument("--list-products", action="store_true", help="List products")
    
    args = parser.parse_args()
    
    fetcher = DeltaHistoricalFetcher(testnet=args.testnet)
    
    if args.list_products:
        products = fetcher.get_perpetual_symbols()
        print(f"\nAvailable Perpetual Futures ({len(products)}):")
        for symbol in products:
            print(f"  - {symbol}")
    else:
        df = fetcher.fetch_maximum_history(
            symbol=args.symbol,
            resolution=args.resolution,
            years_back=args.years
        )
        
        if not df.empty:
            # Validate data
            validation = fetcher.validate_data(df)
            print(f"\nValidation Results:")
            print(f"  Total rows: {validation['total_rows']}")
            print(f"  Has gaps: {validation['has_gaps']} ({validation['gap_count']} gaps)")
            print(f"  Invalid OHLC: {validation['invalid_ohlc']}")
            
            # Save to file
            output_file = args.output or f"{args.symbol.lower()}_{args.resolution}_historical.csv"
            fetcher.save_to_csv(df, output_file)
            
            print(f"\nSample data:")
            print(df.tail())
