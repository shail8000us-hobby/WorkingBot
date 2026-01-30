"""
Delta Exchange Data Manager
===========================
Unified interface for historical + live data management.
Handles data storage, retrieval, and synchronization.

Author: WorkingBot
Version: 1.0.0
"""

import sqlite3
import json
import threading
import time
from typing import List, Dict, Optional, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import logging
from dataclasses import dataclass

# Local imports
from .delta_historical_fetcher import DeltaHistoricalFetcher
from .delta_live_stream import DeltaLiveStreamer, ConnectionState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DataConfig:
    """Configuration for data management."""
    db_path: str = "user_data/market_data.db"
    data_dir: str = "user_data/ohlcv"
    default_resolution: str = "1h"
    auto_fill_gaps: bool = True
    max_gap_hours: int = 24
    testnet: bool = False


class DeltaDataManager:
    """
    Unified data manager for Delta Exchange data.
    
    Features:
    - Combine historical fetching with live streaming
    - SQLite database for persistent storage
    - Automatic gap filling
    - Data validation and deduplication
    - Easy data loading for backtesting
    
    Usage:
        manager = DeltaDataManager()
        
        # Fetch historical data and store
        manager.fetch_and_store_historical("BTCUSD", "1h", days=30)
        
        # Start live data collection
        manager.start_live_collection(["BTCUSD", "ETHUSD"], "1m")
        
        # Load data for analysis
        df = manager.load_data("BTCUSD", "1h", days=7)
    """
    
    def __init__(self, config: Optional[DataConfig] = None):
        """
        Initialize the data manager.
        
        Args:
            config: Data configuration settings
        """
        self.config = config or DataConfig()
        
        # Create directories
        Path(self.config.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Initialize fetcher and streamer
        self.fetcher = DeltaHistoricalFetcher(testnet=self.config.testnet)
        self.streamer: Optional[DeltaLiveStreamer] = None
        
        # Live data buffer
        self._live_buffer: List[Dict] = []
        self._buffer_lock = threading.Lock()
        self._flush_interval = 60  # Flush buffer every 60 seconds
        self._flush_thread: Optional[threading.Thread] = None
        self._is_collecting = False
        
        logger.info(f"Initialized DeltaDataManager")
        logger.info(f"Database: {self.config.db_path}")
        logger.info(f"Data directory: {self.config.data_dir}")
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required tables."""
        conn = sqlite3.connect(self.config.db_path)
        cursor = conn.cursor()
        
        # OHLCV table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                resolution TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                datetime TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                source TEXT DEFAULT 'historical',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, resolution, timestamp)
            )
        """)
        
        # Index for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_resolution_timestamp 
            ON ohlcv(symbol, resolution, timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_resolution 
            ON ohlcv(symbol, resolution)
        """)
        
        # Products/symbols table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                symbol TEXT UNIQUE NOT NULL,
                description TEXT,
                contract_type TEXT,
                underlying_asset TEXT,
                quoting_asset TEXT,
                is_active INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Data collection log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                resolution TEXT NOT NULL,
                action TEXT NOT NULL,
                start_time INTEGER,
                end_time INTEGER,
                candles_count INTEGER,
                status TEXT,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("Database initialized successfully")
    
    def fetch_and_store_historical(
        self,
        symbol: str,
        resolution: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        days: Optional[int] = None
    ) -> int:
        """
        Fetch historical data and store in database.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            resolution: Candle resolution (e.g., "1h", "1m")
            start_time: Start datetime
            end_time: End datetime
            days: Alternative to start_time - fetch last N days
            
        Returns:
            Number of candles stored
        """
        logger.info(f"Fetching historical data for {symbol} ({resolution})")
        
        # Calculate time range
        if days is not None:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
        elif end_time is None:
            end_time = datetime.utcnow()
        
        if start_time is None:
            start_time = end_time - timedelta(days=30)
        
        # Convert to unix timestamps
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())
        
        # Fetch data
        candles = self.fetcher.fetch_candles(
            symbol=symbol,
            resolution=resolution,
            start_timestamp=start_ts,
            end_timestamp=end_ts
        )
        
        if not candles:
            logger.warning(f"No candles fetched for {symbol}")
            return 0
        
        # Normalize candle data (API returns 'time', database expects 'timestamp')
        for candle in candles:
            if 'time' in candle and 'timestamp' not in candle:
                candle['timestamp'] = candle['time']
        
        # Store in database
        stored_count = self._store_candles(symbol, resolution, candles, "historical")
        
        # Log the collection
        self._log_collection(
            symbol=symbol,
            resolution=resolution,
            action="fetch_historical",
            start_time=int(start_time.timestamp()),
            end_time=int(end_time.timestamp()),
            candles_count=stored_count,
            status="success"
        )
        
        logger.info(f"Stored {stored_count} candles for {symbol}")
        return stored_count
    
    def fetch_maximum_history(
        self,
        symbol: str,
        resolution: str
    ) -> int:
        """
        Fetch maximum available historical data.
        
        Args:
            symbol: Trading symbol
            resolution: Candle resolution
            
        Returns:
            Number of candles stored
        """
        logger.info(f"Fetching maximum history for {symbol} ({resolution})")
        
        candles = self.fetcher.fetch_maximum_history(symbol, resolution)
        
        if not candles:
            logger.warning(f"No candles fetched for {symbol}")
            return 0
        
        stored_count = self._store_candles(symbol, resolution, candles, "historical")
        
        # Log the collection
        self._log_collection(
            symbol=symbol,
            resolution=resolution,
            action="fetch_maximum_history",
            candles_count=stored_count,
            status="success"
        )
        
        logger.info(f"Stored {stored_count} candles for {symbol}")
        return stored_count
    
    def _store_candles(
        self,
        symbol: str,
        resolution: str,
        candles: List[Dict],
        source: str
    ) -> int:
        """
        Store candles in database.
        
        Args:
            symbol: Trading symbol
            resolution: Candle resolution
            candles: List of candle dicts
            source: Data source (historical/live)
            
        Returns:
            Number of candles stored
        """
        conn = sqlite3.connect(self.config.db_path)
        cursor = conn.cursor()
        
        stored = 0
        for candle in candles:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO ohlcv 
                    (symbol, resolution, timestamp, datetime, open, high, low, close, volume, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    resolution,
                    candle["timestamp"],
                    candle.get("datetime", datetime.fromtimestamp(candle["timestamp"]).isoformat()),
                    candle["open"],
                    candle["high"],
                    candle["low"],
                    candle["close"],
                    candle["volume"],
                    source
                ))
                stored += 1
            except sqlite3.Error as e:
                logger.error(f"Error storing candle: {e}")
        
        conn.commit()
        conn.close()
        
        return stored
    
    def _log_collection(
        self,
        symbol: str,
        resolution: str,
        action: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        candles_count: Optional[int] = None,
        status: str = "success",
        error: Optional[str] = None
    ) -> None:
        """Log data collection activity."""
        conn = sqlite3.connect(self.config.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO collection_log 
            (symbol, resolution, action, start_time, end_time, candles_count, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, resolution, action, start_time, end_time, candles_count, status, error))
        
        conn.commit()
        conn.close()
    
    def start_live_collection(
        self,
        symbols: List[str],
        resolution: str = "1m",
        also_fetch_history: bool = True,
        history_days: int = 1
    ) -> None:
        """
        Start collecting live data.
        
        Args:
            symbols: List of symbols to stream
            resolution: Candle resolution
            also_fetch_history: Fetch recent history first
            history_days: Days of history to fetch
        """
        if self._is_collecting:
            logger.warning("Already collecting live data")
            return
        
        # Optionally fetch recent history first
        if also_fetch_history:
            for symbol in symbols:
                self.fetch_and_store_historical(
                    symbol=symbol,
                    resolution=resolution,
                    days=history_days
                )
        
        # Initialize streamer
        self.streamer = DeltaLiveStreamer(
            on_candle=self._handle_live_candle,
            on_error=self._handle_live_error,
            on_connect=self._handle_live_connect,
            on_disconnect=self._handle_live_disconnect,
            testnet=self.config.testnet
        )
        
        # Subscribe to candles
        self.streamer.subscribe_candles(symbols, resolution)
        
        # Start streaming
        self.streamer.start()
        self._is_collecting = True
        
        # Start buffer flush thread
        self._start_flush_thread()
        
        logger.info(f"Started live collection for {symbols} ({resolution})")
    
    def _handle_live_candle(self, candle: Dict) -> None:
        """Handle incoming live candle."""
        with self._buffer_lock:
            self._live_buffer.append({
                "symbol": candle["symbol"],
                "resolution": candle["resolution"],
                "timestamp": int(datetime.fromisoformat(candle["candle_start_time"]).timestamp()),
                "datetime": candle["candle_start_time"],
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"]
            })
    
    def _handle_live_error(self, error: str) -> None:
        """Handle streaming error."""
        logger.error(f"Live streaming error: {error}")
    
    def _handle_live_connect(self) -> None:
        """Handle successful connection."""
        logger.info("Live streaming connected")
    
    def _handle_live_disconnect(self, reason: str) -> None:
        """Handle disconnection."""
        logger.warning(f"Live streaming disconnected: {reason}")
    
    def _start_flush_thread(self) -> None:
        """Start the buffer flush thread."""
        def flush_loop():
            while self._is_collecting:
                time.sleep(self._flush_interval)
                self._flush_buffer()
        
        self._flush_thread = threading.Thread(target=flush_loop, daemon=True)
        self._flush_thread.start()
    
    def _flush_buffer(self) -> None:
        """Flush live data buffer to database."""
        with self._buffer_lock:
            if not self._live_buffer:
                return
            
            candles_to_store = self._live_buffer.copy()
            self._live_buffer.clear()
        
        # Group by symbol and resolution
        grouped = {}
        for candle in candles_to_store:
            key = (candle["symbol"], candle["resolution"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(candle)
        
        # Store each group
        total_stored = 0
        for (symbol, resolution), candles in grouped.items():
            stored = self._store_candles(symbol, resolution, candles, "live")
            total_stored += stored
        
        if total_stored > 0:
            logger.info(f"Flushed {total_stored} live candles to database")
    
    def stop_live_collection(self) -> None:
        """Stop live data collection."""
        self._is_collecting = False
        
        # Flush remaining buffer
        self._flush_buffer()
        
        if self.streamer:
            self.streamer.stop()
            self.streamer = None
        
        if self._flush_thread:
            self._flush_thread.join(timeout=5)
            self._flush_thread = None
        
        logger.info("Stopped live collection")
    
    def load_data(
        self,
        symbol: str,
        resolution: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        days: Optional[int] = None,
        as_dataframe: bool = True
    ) -> Union[pd.DataFrame, List[Dict]]:
        """
        Load data from database.
        
        Args:
            symbol: Trading symbol
            resolution: Candle resolution
            start_time: Start datetime
            end_time: End datetime
            days: Alternative - load last N days
            as_dataframe: Return as pandas DataFrame
            
        Returns:
            DataFrame or list of candles
        """
        conn = sqlite3.connect(self.config.db_path)
        
        # Build query
        query = """
            SELECT timestamp, datetime, open, high, low, close, volume, source
            FROM ohlcv
            WHERE symbol = ? AND resolution = ?
        """
        params = [symbol, resolution]
        
        if days is not None:
            start_time = datetime.utcnow() - timedelta(days=days)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(int(start_time.timestamp()))
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(int(end_time.timestamp()))
        
        query += " ORDER BY timestamp ASC"
        
        if as_dataframe:
            df = pd.read_sql_query(query, conn, params=params)
            df["datetime"] = pd.to_datetime(df["datetime"])
            conn.close()
            return df
        else:
            cursor = conn.cursor()
            cursor.execute(query, params)
            columns = ["timestamp", "datetime", "open", "high", "low", "close", "volume", "source"]
            rows = cursor.fetchall()
            conn.close()
            return [dict(zip(columns, row)) for row in rows]
    
    def get_latest_timestamp(self, symbol: str, resolution: str) -> Optional[int]:
        """Get the latest timestamp for a symbol/resolution pair."""
        conn = sqlite3.connect(self.config.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT MAX(timestamp) FROM ohlcv
            WHERE symbol = ? AND resolution = ?
        """, (symbol, resolution))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else None
    
    def get_data_range(self, symbol: str, resolution: str) -> Optional[Dict]:
        """Get the date range of available data."""
        conn = sqlite3.connect(self.config.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                MIN(timestamp) as start_ts,
                MAX(timestamp) as end_ts,
                COUNT(*) as count
            FROM ohlcv
            WHERE symbol = ? AND resolution = ?
        """, (symbol, resolution))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return {
                "start": datetime.fromtimestamp(result[0]),
                "end": datetime.fromtimestamp(result[1]),
                "count": result[2]
            }
        return None
    
    def fill_gaps(
        self,
        symbol: str,
        resolution: str,
        max_gap_hours: Optional[int] = None
    ) -> int:
        """
        Find and fill gaps in data.
        
        Args:
            symbol: Trading symbol
            resolution: Candle resolution
            max_gap_hours: Maximum gap size to fill (in hours)
            
        Returns:
            Number of gaps filled
        """
        max_gap = max_gap_hours or self.config.max_gap_hours
        
        data_range = self.get_data_range(symbol, resolution)
        if not data_range:
            logger.warning(f"No data available for {symbol} ({resolution})")
            return 0
        
        # Load existing data
        df = self.load_data(
            symbol=symbol,
            resolution=resolution,
            start_time=data_range["start"],
            end_time=data_range["end"]
        )
        
        if df.empty:
            return 0
        
        # Calculate expected interval
        resolution_minutes = {
            "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "2h": 120, "4h": 240, "6h": 360,
            "1d": 1440, "1w": 10080
        }
        
        interval_minutes = resolution_minutes.get(resolution, 60)
        max_gap_minutes = max_gap * 60
        
        # Find gaps
        df = df.sort_values("timestamp")
        df["time_diff"] = df["timestamp"].diff()
        
        gaps = df[df["time_diff"] > interval_minutes * 60 * 1.5]  # 1.5x tolerance
        
        filled_count = 0
        for _, row in gaps.iterrows():
            gap_minutes = row["time_diff"] / 60
            
            if gap_minutes <= max_gap_minutes:
                # Fetch data for the gap
                gap_start = datetime.fromtimestamp(row["timestamp"] - row["time_diff"])
                gap_end = datetime.fromtimestamp(row["timestamp"])
                
                logger.info(f"Filling gap: {gap_start} to {gap_end}")
                
                filled = self.fetch_and_store_historical(
                    symbol=symbol,
                    resolution=resolution,
                    start_time=gap_start,
                    end_time=gap_end
                )
                filled_count += filled
        
        return filled_count
    
    def update_products(self) -> int:
        """Update the products table with available symbols."""
        products = self.fetcher.get_available_products()
        
        conn = sqlite3.connect(self.config.db_path)
        cursor = conn.cursor()
        
        updated = 0
        for product in products:
            cursor.execute("""
                INSERT OR REPLACE INTO products 
                (id, symbol, description, contract_type, underlying_asset, quoting_asset, is_active, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product.get("id"),
                product.get("symbol"),
                product.get("description"),
                product.get("contract_type"),
                product.get("underlying_asset", {}).get("symbol"),
                product.get("quoting_asset", {}).get("symbol"),
                1 if product.get("state") == "live" else 0,
                datetime.utcnow().isoformat()
            ))
            updated += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated {updated} products")
        return updated
    
    def get_available_symbols(
        self,
        contract_type: Optional[str] = None,
        active_only: bool = True
    ) -> List[str]:
        """
        Get list of available symbols.
        
        Args:
            contract_type: Filter by contract type (futures, perpetual_futures, etc.)
            active_only: Only return active symbols
            
        Returns:
            List of symbol strings
        """
        conn = sqlite3.connect(self.config.db_path)
        cursor = conn.cursor()
        
        query = "SELECT symbol FROM products WHERE 1=1"
        params = []
        
        if active_only:
            query += " AND is_active = 1"
        
        if contract_type:
            query += " AND contract_type = ?"
            params.append(contract_type)
        
        query += " ORDER BY symbol"
        
        cursor.execute(query, params)
        symbols = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return symbols
    
    def get_collection_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get data collection history."""
        conn = sqlite3.connect(self.config.db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT symbol, resolution, action, start_time, end_time, 
                   candles_count, status, error, created_at
            FROM collection_log
        """
        params = []
        
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        columns = ["symbol", "resolution", "action", "start_time", "end_time",
                   "candles_count", "status", "error", "created_at"]
        rows = cursor.fetchall()
        
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    
    def export_data(
        self,
        symbol: str,
        resolution: str,
        output_path: str,
        format: str = "csv",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> str:
        """
        Export data to file.
        
        Args:
            symbol: Trading symbol
            resolution: Candle resolution
            output_path: Output file path (without extension)
            format: Output format (csv, parquet, json)
            start_time: Start datetime filter
            end_time: End datetime filter
            
        Returns:
            Path to exported file
        """
        df = self.load_data(
            symbol=symbol,
            resolution=resolution,
            start_time=start_time,
            end_time=end_time
        )
        
        if df.empty:
            raise ValueError(f"No data available for {symbol} ({resolution})")
        
        if format == "csv":
            filepath = f"{output_path}.csv"
            df.to_csv(filepath, index=False)
        elif format == "parquet":
            filepath = f"{output_path}.parquet"
            df.to_parquet(filepath, index=False)
        elif format == "json":
            filepath = f"{output_path}.json"
            df.to_json(filepath, orient="records", date_format="iso")
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Exported {len(df)} rows to {filepath}")
        return filepath
    
    def get_status(self) -> Dict:
        """Get current status of the data manager."""
        conn = sqlite3.connect(self.config.db_path)
        cursor = conn.cursor()
        
        # Get database stats
        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM ohlcv")
        unique_symbols = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM ohlcv")
        total_candles = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
        active_products = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "database_path": self.config.db_path,
            "unique_symbols": unique_symbols,
            "total_candles": total_candles,
            "active_products": active_products,
            "is_collecting_live": self._is_collecting,
            "live_buffer_size": len(self._live_buffer),
            "streamer_status": (
                self.streamer.get_stats() if self.streamer else None
            )
        }

    def get_database_stats(self) -> Dict:
        """
        Get comprehensive database statistics.
        
        Returns:
            Dictionary with database size, record counts, and data coverage
        """
        try:
            conn = sqlite3.connect(self.config.db_path)
            cursor = conn.cursor()
            
            # Get total records
            cursor.execute("SELECT COUNT(*) FROM ohlcv")
            total_records = cursor.fetchone()[0]
            
            # Get unique symbols
            cursor.execute("SELECT COUNT(DISTINCT symbol) FROM ohlcv")
            unique_symbols = cursor.fetchone()[0]
            
            # Get unique resolutions
            cursor.execute("SELECT COUNT(DISTINCT resolution) FROM ohlcv")
            unique_resolutions = cursor.fetchone()[0]
            
            # Get date range
            cursor.execute("SELECT MIN(datetime), MAX(datetime) FROM ohlcv")
            date_range = cursor.fetchone()
            
            # Get per-symbol counts
            cursor.execute("""
                SELECT symbol, resolution, COUNT(*) as count,
                       MIN(datetime) as start, MAX(datetime) as end
                FROM ohlcv 
                GROUP BY symbol, resolution
                ORDER BY symbol, resolution
            """)
            symbol_stats = [
                {
                    'symbol': row[0],
                    'resolution': row[1],
                    'count': row[2],
                    'start': row[3],
                    'end': row[4]
                }
                for row in cursor.fetchall()
            ]
            
            # Get database file size
            import os
            db_size_bytes = os.path.getsize(self.config.db_path) if os.path.exists(self.config.db_path) else 0
            db_size_mb = round(db_size_bytes / (1024 * 1024), 2)
            
            conn.close()
            
            return {
                'total_records': total_records,
                'unique_symbols': unique_symbols,
                'unique_resolutions': unique_resolutions,
                'date_range': {
                    'start': date_range[0] if date_range else None,
                    'end': date_range[1] if date_range else None
                },
                'symbol_stats': symbol_stats,
                'database_size_mb': db_size_mb,
                'database_path': self.config.db_path
            }
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {
                'total_records': 0,
                'unique_symbols': 0,
                'error': str(e)
            }

    def get_data_coverage(self) -> List[Dict]:
        """
        Get data coverage report for all symbols.
        
        Returns:
            List of coverage statistics for each symbol/resolution pair
        """
        try:
            conn = sqlite3.connect(self.config.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT symbol, resolution, COUNT(*) as count,
                       MIN(datetime) as start, MAX(datetime) as end,
                       MIN(timestamp) as start_ts, MAX(timestamp) as end_ts
                FROM ohlcv 
                GROUP BY symbol, resolution
                ORDER BY symbol, resolution
            """)
            
            coverage = []
            for row in cursor.fetchall():
                symbol, resolution, count, start, end, start_ts, end_ts = row
                
                # Calculate expected candles based on time range
                resolution_seconds = {
                    '1m': 60, '5m': 300, '15m': 900, '30m': 1800,
                    '1h': 3600, '4h': 14400, '1d': 86400, '1w': 604800
                }.get(resolution, 3600)
                
                if start_ts and end_ts:
                    time_span = end_ts - start_ts
                    expected_candles = max(1, time_span // resolution_seconds)
                    coverage_pct = round((count / expected_candles) * 100, 1) if expected_candles > 0 else 0
                else:
                    expected_candles = 0
                    coverage_pct = 0
                
                coverage.append({
                    'symbol': symbol,
                    'resolution': resolution,
                    'candle_count': count,
                    'expected_count': expected_candles,
                    'coverage_percent': coverage_pct,
                    'start': start,
                    'end': end
                })
            
            conn.close()
            return coverage
            
        except Exception as e:
            logger.error(f"Error getting data coverage: {e}")
            return []


# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Delta Exchange data manager")
    parser.add_argument("command", choices=["fetch", "live", "status", "export", "gaps"],
                       help="Command to execute")
    parser.add_argument("--symbol", default="BTCUSD", help="Trading symbol")
    parser.add_argument("--resolution", default="1h", help="Candle resolution")
    parser.add_argument("--days", type=int, default=30, help="Days of history")
    parser.add_argument("--output", help="Output path for export")
    parser.add_argument("--format", choices=["csv", "parquet", "json"], default="csv",
                       help="Export format")
    parser.add_argument("--testnet", action="store_true", help="Use testnet")
    parser.add_argument("--duration", type=int, default=300, 
                       help="Live collection duration in seconds")
    
    args = parser.parse_args()
    
    config = DataConfig(testnet=args.testnet)
    manager = DeltaDataManager(config)
    
    if args.command == "fetch":
        print(f"Fetching {args.days} days of {args.resolution} data for {args.symbol}...")
        count = manager.fetch_and_store_historical(
            symbol=args.symbol,
            resolution=args.resolution,
            days=args.days
        )
        print(f"Stored {count} candles")
        
        data_range = manager.get_data_range(args.symbol, args.resolution)
        if data_range:
            print(f"Data range: {data_range['start']} to {data_range['end']}")
            print(f"Total candles: {data_range['count']}")
    
    elif args.command == "live":
        print(f"Starting live collection for {args.symbol} ({args.resolution})...")
        print(f"Will run for {args.duration} seconds")
        
        manager.start_live_collection([args.symbol], args.resolution)
        
        try:
            start = time.time()
            while time.time() - start < args.duration:
                time.sleep(10)
                status = manager.get_status()
                print(f"Buffer size: {status['live_buffer_size']}")
        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            manager.stop_live_collection()
    
    elif args.command == "status":
        status = manager.get_status()
        print("\nData Manager Status:")
        for key, value in status.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for k, v in value.items():
                    print(f"    {k}: {v}")
            else:
                print(f"  {key}: {value}")
        
        print("\nRecent Collection History:")
        history = manager.get_collection_history(limit=10)
        for entry in history:
            print(f"  {entry['created_at']}: {entry['action']} "
                  f"{entry['symbol']} ({entry['candles_count']} candles)")
    
    elif args.command == "export":
        if not args.output:
            args.output = f"user_data/export/{args.symbol}_{args.resolution}"
        
        print(f"Exporting {args.symbol} ({args.resolution}) to {args.format}...")
        filepath = manager.export_data(
            symbol=args.symbol,
            resolution=args.resolution,
            output_path=args.output,
            format=args.format
        )
        print(f"Exported to: {filepath}")
    
    elif args.command == "gaps":
        print(f"Finding and filling gaps for {args.symbol} ({args.resolution})...")
        filled = manager.fill_gaps(args.symbol, args.resolution)
        print(f"Filled {filled} gap candles")
