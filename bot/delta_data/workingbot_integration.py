"""
WorkingBot Integration Layer
============================
Bridge between Delta Exchange data modules and WorkingBot infrastructure.
Designed for seamless migration to /Users/ssr/Projects/WorkingBot/

Author: WorkingBot
Version: 1.0.0
"""

import sqlite3
import json
import time
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class WorkingBotConfig:
    """Configuration matching WorkingBot structure."""
    
    # API Settings
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    
    # Base URLs (Delta Exchange India)
    base_url_production: str = "https://api.india.delta.exchange"
    base_url_testnet: str = "https://cdn-ind.testnet.deltaex.org"
    ws_url_production: str = "wss://socket.india.delta.exchange"
    ws_url_testnet: str = "wss://socket-ind.testnet.deltaex.org"
    
    # Data paths
    data_dir: str = "user_data"
    db_path: str = "user_data/trading.db"
    ohlcv_dir: str = "user_data/ohlcv"
    
    # Rate limiting (matches Delta Exchange specs)
    rate_limit_window: int = 300  # 5 minutes
    rate_limit_units: int = 10000
    candle_request_weight: int = 3
    
    # Trading defaults
    default_symbol: str = "BTCUSD"
    default_resolution: str = "1h"
    
    @property
    def base_url(self) -> str:
        return self.base_url_testnet if self.testnet else self.base_url_production
    
    @property
    def ws_url(self) -> str:
        return self.ws_url_testnet if self.testnet else self.ws_url_production


class WorkingBotDataProvider:
    """
    Data provider for WorkingBot backtest and strategy engines.
    
    This class provides a clean interface for:
    - Loading historical OHLCV data
    - Calculating technical indicators
    - Managing real-time data feeds
    - Exporting data for analysis
    
    Designed to integrate with WorkingBot's existing infrastructure:
    - bot/api/async_delta_client.py
    - bot/api/delta_client.py
    - bot/delta_websocket/
    
    Usage:
        provider = WorkingBotDataProvider()
        
        # Load data for backtesting
        df = provider.get_ohlcv("BTCUSD", "1h", days=30)
        
        # Add indicators
        df = provider.add_technical_indicators(df)
        
        # Use in backtest
        backtest = BacktestEngine(provider)
        results = backtest.run(strategy)
    """
    
    def __init__(self, config: Optional[WorkingBotConfig] = None):
        """
        Initialize the data provider.
        
        Args:
            config: WorkingBot configuration
        """
        self.config = config or WorkingBotConfig()
        
        # Create directories
        Path(self.config.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.ohlcv_dir).mkdir(parents=True, exist_ok=True)
        
        # Import data modules (lazy loading)
        self._fetcher = None
        self._streamer = None
        self._manager = None
        
        logger.info("Initialized WorkingBotDataProvider")
        logger.info(f"Mode: {'Testnet' if self.config.testnet else 'Production'}")
    
    @property
    def fetcher(self):
        """Lazy load historical data fetcher."""
        if self._fetcher is None:
            from .delta_historical_fetcher import DeltaHistoricalFetcher
            self._fetcher = DeltaHistoricalFetcher(testnet=self.config.testnet)
        return self._fetcher
    
    @property
    def streamer(self):
        """Lazy load live data streamer."""
        if self._streamer is None:
            from .delta_live_stream import DeltaLiveStreamer
            self._streamer = DeltaLiveStreamer(testnet=self.config.testnet)
        return self._streamer
    
    @property
    def manager(self):
        """Lazy load data manager."""
        if self._manager is None:
            from .delta_data_manager import DeltaDataManager, DataConfig
            data_config = DataConfig(
                db_path=self.config.db_path,
                data_dir=self.config.ohlcv_dir,
                testnet=self.config.testnet
            )
            self._manager = DeltaDataManager(data_config)
        return self._manager
    
    def get_ohlcv(
        self,
        symbol: str,
        resolution: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        days: Optional[int] = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get OHLCV data for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            resolution: Candle resolution (1m, 5m, 1h, etc.)
            start_time: Start datetime
            end_time: End datetime
            days: Alternative to start_time - get last N days
            use_cache: Use cached data if available
            
        Returns:
            DataFrame with columns: timestamp, datetime, open, high, low, close, volume
        """
        if days is not None:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
        elif end_time is None:
            end_time = datetime.utcnow()
        
        if start_time is None:
            start_time = end_time - timedelta(days=30)
        
        # Try loading from cache/database first
        if use_cache:
            df = self.manager.load_data(
                symbol=symbol,
                resolution=resolution,
                start_time=start_time,
                end_time=end_time
            )
            
            if not df.empty:
                return self._prepare_dataframe(df)
        
        # Convert datetime to unix timestamps for API call
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())
        
        # Fetch from API
        candles = self.fetcher.fetch_candles(
            symbol=symbol,
            resolution=resolution,
            start_timestamp=start_ts,
            end_timestamp=end_ts
        )
        
        if not candles:
            return pd.DataFrame()
        
        # Normalize candle data (API returns 'time', database expects 'timestamp')
        for candle in candles:
            if 'time' in candle and 'timestamp' not in candle:
                candle['timestamp'] = candle['time']
        
        # Store for future use
        self.manager._store_candles(symbol, resolution, candles, "historical")
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        return self._prepare_dataframe(df)
    
    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare DataFrame for backtesting."""
        if df.empty:
            return df
        
        # Ensure proper column types
        df = df.copy()
        
        # Handle 'time' field (unix timestamp from API)
        if "time" in df.columns and "datetime" not in df.columns:
            df["datetime"] = pd.to_datetime(df["time"], unit='s', utc=True)
            df["timestamp"] = df["time"]
        elif "timestamp" in df.columns and "datetime" not in df.columns:
            df["datetime"] = pd.to_datetime(df["timestamp"], unit='s', utc=True)
        
        # Convert datetime if string
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
        
        # Set datetime as index if not already
        if "datetime" in df.columns and df.index.name != "datetime":
            df = df.set_index("datetime")
        
        # Ensure numeric columns
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Sort by index
        df = df.sort_index()
        
        return df
    
    def add_technical_indicators(
        self,
        df: pd.DataFrame,
        indicators: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Add technical indicators to OHLCV DataFrame.
        
        Args:
            df: OHLCV DataFrame
            indicators: List of indicator names to add (default: common set)
            
        Returns:
            DataFrame with added indicator columns
        """
        if indicators is None:
            indicators = ["sma_20", "sma_50", "ema_12", "ema_26", "rsi_14", 
                         "macd", "bollinger", "atr_14"]
        
        df = df.copy()
        
        for indicator in indicators:
            if indicator.startswith("sma_"):
                period = int(indicator.split("_")[1])
                df[indicator] = df["close"].rolling(window=period).mean()
            
            elif indicator.startswith("ema_"):
                period = int(indicator.split("_")[1])
                df[indicator] = df["close"].ewm(span=period, adjust=False).mean()
            
            elif indicator.startswith("rsi_"):
                period = int(indicator.split("_")[1])
                df[indicator] = self._calculate_rsi(df["close"], period)
            
            elif indicator == "macd":
                ema12 = df["close"].ewm(span=12, adjust=False).mean()
                ema26 = df["close"].ewm(span=26, adjust=False).mean()
                df["macd"] = ema12 - ema26
                df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
                df["macd_hist"] = df["macd"] - df["macd_signal"]
            
            elif indicator == "bollinger":
                sma = df["close"].rolling(window=20).mean()
                std = df["close"].rolling(window=20).std()
                df["bb_upper"] = sma + (std * 2)
                df["bb_middle"] = sma
                df["bb_lower"] = sma - (std * 2)
                df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
            
            elif indicator.startswith("atr_"):
                period = int(indicator.split("_")[1])
                df[indicator] = self._calculate_atr(df, period)
        
        return df
    
    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        """Calculate RSI indicator."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Average True Range."""
        high = df["high"]
        low = df["low"]
        close = df["close"]
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    def get_mark_price_history(
        self,
        symbol: str,
        resolution: str,
        days: int = 7
    ) -> pd.DataFrame:
        """
        Get mark price history for derivatives.
        
        Args:
            symbol: Trading symbol
            resolution: Candle resolution
            days: Days of history
            
        Returns:
            DataFrame with mark price data
        """
        # Mark price uses MARK: prefix
        mark_symbol = f"MARK:{symbol}" if not symbol.startswith("MARK:") else symbol
        
        return self.get_ohlcv(
            symbol=mark_symbol,
            resolution=resolution,
            days=days,
            use_cache=True
        )
    
    def get_funding_rate_history(
        self,
        symbol: str,
        resolution: str = "1h",
        days: int = 7
    ) -> pd.DataFrame:
        """
        Get funding rate history for perpetual futures.
        
        Args:
            symbol: Perpetual futures symbol
            resolution: Candle resolution
            days: Days of history
            
        Returns:
            DataFrame with funding rate data
        """
        # Funding rate uses FUNDING: prefix
        funding_symbol = f"FUNDING:{symbol}" if not symbol.startswith("FUNDING:") else symbol
        
        return self.get_ohlcv(
            symbol=funding_symbol,
            resolution=resolution,
            days=days,
            use_cache=True
        )
    
    def get_open_interest_history(
        self,
        symbol: str,
        resolution: str = "1h",
        days: int = 7
    ) -> pd.DataFrame:
        """
        Get open interest history.
        
        Args:
            symbol: Trading symbol
            resolution: Candle resolution
            days: Days of history
            
        Returns:
            DataFrame with open interest data
        """
        # Open interest uses OI: prefix
        oi_symbol = f"OI:{symbol}" if not symbol.startswith("OI:") else symbol
        
        return self.get_ohlcv(
            symbol=oi_symbol,
            resolution=resolution,
            days=days,
            use_cache=True
        )
    
    def get_available_symbols(self, contract_type: Optional[str] = None) -> List[str]:
        """
        Get list of available trading symbols.
        
        Args:
            contract_type: Filter by contract type (perpetual_futures, futures, etc.)
            
        Returns:
            List of symbol strings
        """
        return self.manager.get_available_symbols(contract_type=contract_type)
    
    def update_symbol_list(self) -> int:
        """Update the list of available symbols from exchange."""
        return self.manager.update_products()


class BacktestDataAdapter:
    """
    Adapter for using WorkingBotDataProvider with BacktestEngine.
    
    This provides compatibility with the existing BacktestEngine
    in the workingbot-prototype.
    
    Usage:
        provider = WorkingBotDataProvider()
        adapter = BacktestDataAdapter(provider)
        
        backtest = BacktestEngine(adapter)
        results = backtest.run(strategy)
    """
    
    def __init__(self, provider: WorkingBotDataProvider):
        """
        Initialize adapter.
        
        Args:
            provider: WorkingBotDataProvider instance
        """
        self.provider = provider
        self._data_cache: Dict[str, pd.DataFrame] = {}
    
    def load_data(
        self,
        symbol: str,
        resolution: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Load data for backtesting.
        
        Args:
            symbol: Trading symbol
            resolution: Candle resolution
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame ready for backtesting
        """
        cache_key = f"{symbol}_{resolution}_{start_date}_{end_date}"
        
        if cache_key in self._data_cache:
            return self._data_cache[cache_key]
        
        start_time = datetime.strptime(start_date, "%Y-%m-%d")
        end_time = datetime.strptime(end_date, "%Y-%m-%d")
        
        df = self.provider.get_ohlcv(
            symbol=symbol,
            resolution=resolution,
            start_time=start_time,
            end_time=end_time
        )
        
        # Add indicators for strategy use
        df = self.provider.add_technical_indicators(df)
        
        self._data_cache[cache_key] = df
        return df
    
    def clear_cache(self) -> None:
        """Clear data cache."""
        self._data_cache.clear()


class LiveDataAdapter:
    """
    Adapter for using WorkingBotDataProvider with live trading.
    
    Manages real-time data streaming and provides latest prices
    for trading decisions.
    
    Usage:
        provider = WorkingBotDataProvider()
        live = LiveDataAdapter(provider)
        
        live.start(["BTCUSD", "ETHUSD"], "1m")
        
        while trading:
            latest = live.get_latest("BTCUSD")
            # Make trading decision...
            
        live.stop()
    """
    
    def __init__(self, provider: WorkingBotDataProvider):
        """
        Initialize adapter.
        
        Args:
            provider: WorkingBotDataProvider instance
        """
        self.provider = provider
        self._latest_prices: Dict[str, Dict] = {}
        self._candle_buffer: Dict[str, List[Dict]] = {}
        self._is_running = False
    
    def _on_candle(self, candle: Dict) -> None:
        """Handle incoming candle."""
        symbol = candle["symbol"]
        
        self._latest_prices[symbol] = {
            "price": candle["close"],
            "timestamp": candle["timestamp"],
            "volume": candle["volume"],
            "high": candle["high"],
            "low": candle["low"]
        }
        
        if symbol not in self._candle_buffer:
            self._candle_buffer[symbol] = []
        
        self._candle_buffer[symbol].append(candle)
        
        # Keep only last 1000 candles in buffer
        if len(self._candle_buffer[symbol]) > 1000:
            self._candle_buffer[symbol] = self._candle_buffer[symbol][-1000:]
    
    def start(
        self,
        symbols: List[str],
        resolution: str = "1m",
        on_candle: Optional[Callable] = None
    ) -> None:
        """
        Start live data streaming.
        
        Args:
            symbols: Symbols to stream
            resolution: Candle resolution
            on_candle: Optional callback for each candle
        """
        if self._is_running:
            logger.warning("Live data already running")
            return
        
        # Set up streamer
        from .delta_live_stream import DeltaLiveStreamer
        
        def handle_candle(candle):
            self._on_candle(candle)
            if on_candle:
                on_candle(candle)
        
        self.provider._streamer = DeltaLiveStreamer(
            on_candle=handle_candle,
            testnet=self.provider.config.testnet
        )
        
        self.provider.streamer.subscribe_candles(symbols, resolution)
        self.provider.streamer.start()
        
        self._is_running = True
        logger.info(f"Started live data for {symbols}")
    
    def stop(self) -> None:
        """Stop live data streaming."""
        if not self._is_running:
            return
        
        self.provider.streamer.stop()
        self._is_running = False
        logger.info("Stopped live data")
    
    def get_latest(self, symbol: str) -> Optional[Dict]:
        """
        Get latest price for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dict with latest price info or None
        """
        return self._latest_prices.get(symbol)
    
    def get_recent_candles(
        self,
        symbol: str,
        count: int = 100
    ) -> pd.DataFrame:
        """
        Get recent candles from buffer.
        
        Args:
            symbol: Trading symbol
            count: Number of candles
            
        Returns:
            DataFrame with recent candles
        """
        candles = self._candle_buffer.get(symbol, [])
        
        if not candles:
            return pd.DataFrame()
        
        recent = candles[-count:]
        df = pd.DataFrame(recent)
        
        return self.provider._prepare_dataframe(df)
    
    def is_running(self) -> bool:
        """Check if live data is running."""
        return self._is_running


def create_workingbot_provider(
    testnet: bool = True,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None
) -> WorkingBotDataProvider:
    """
    Factory function to create a configured WorkingBotDataProvider.
    
    Args:
        testnet: Use testnet (default: True for safety)
        api_key: Delta Exchange API key
        api_secret: Delta Exchange API secret
        
    Returns:
        Configured WorkingBotDataProvider instance
    """
    config = WorkingBotConfig(
        testnet=testnet,
        api_key=api_key or "",
        api_secret=api_secret or ""
    )
    
    return WorkingBotDataProvider(config)


# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="WorkingBot data provider")
    parser.add_argument("command", choices=["fetch", "indicators", "test"],
                       help="Command to execute")
    parser.add_argument("--symbol", default="BTCUSD", help="Trading symbol")
    parser.add_argument("--resolution", default="1h", help="Candle resolution")
    parser.add_argument("--days", type=int, default=7, help="Days of data")
    parser.add_argument("--testnet", action="store_true", help="Use testnet")
    
    args = parser.parse_args()
    
    provider = create_workingbot_provider(testnet=args.testnet)
    
    if args.command == "fetch":
        print(f"Fetching {args.days} days of {args.resolution} data for {args.symbol}...")
        df = provider.get_ohlcv(
            symbol=args.symbol,
            resolution=args.resolution,
            days=args.days
        )
        
        print(f"\nFetched {len(df)} candles")
        print(f"Date range: {df.index.min()} to {df.index.max()}")
        print(f"\nLast 5 candles:")
        print(df.tail())
    
    elif args.command == "indicators":
        print(f"Fetching data with indicators for {args.symbol}...")
        df = provider.get_ohlcv(
            symbol=args.symbol,
            resolution=args.resolution,
            days=args.days
        )
        
        df = provider.add_technical_indicators(df)
        
        print(f"\nColumns: {list(df.columns)}")
        print(f"\nLast 5 rows with indicators:")
        print(df[["close", "sma_20", "rsi_14", "macd"]].tail())
    
    elif args.command == "test":
        print("Testing WorkingBot integration...")
        
        # Test backtest adapter
        adapter = BacktestDataAdapter(provider)
        
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
        
        df = adapter.load_data(
            symbol=args.symbol,
            resolution=args.resolution,
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"\nBacktest data loaded: {len(df)} candles")
        print(f"Columns: {list(df.columns)}")
        print("\n✅ WorkingBot integration test passed!")
