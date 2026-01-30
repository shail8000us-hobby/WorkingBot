"""
OHLCV Data Collector - Production Ready
Downloads historical candlestick data from Binance (free, no API key needed)
"""
import requests
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import yaml
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
from data.database_manager import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OHLCVCollector:
    """
    Collects OHLCV data from Binance public API.
    No API key required for public data.
    """
    
    BINANCE_API = "https://api.binance.com/api/v3/klines"
    
    # Binance interval mapping
    TIMEFRAME_MAP = {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '1h': '1h',
        '4h': '4h',
        '1d': '1d',
    }
    
    def __init__(self, db_manager: DatabaseManager = None):
        """Initialize collector"""
        self.db = db_manager or DatabaseManager()
        
        # Load config
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
    
    def download_historical_data(
        self,
        symbol: str,
        timeframe: str,
        days: int = 365,
        force_update: bool = False
    ) -> int:
        """
        Download historical OHLCV data.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframe: Candle timeframe ('5m', '1h', '1d')
            days: Number of days to download
            force_update: If True, re-download all data
        
        Returns:
            Number of candles downloaded
        """
        logger.info(f"Downloading {symbol} {timeframe} data for last {days} days...")
        
        # Convert symbol format (BTCUSD -> BTCUSDT for Binance)
        binance_symbol = symbol.replace('USD', 'USDT') if 'USDT' not in symbol else symbol
        
        # Check what we already have
        if not force_update:
            latest_timestamp = self.db.get_latest_ohlcv_timestamp(symbol, timeframe)
            if latest_timestamp:
                # Resume from last timestamp
                start_time = datetime.fromtimestamp(latest_timestamp)
                logger.info(f"Found existing data up to {start_time}, resuming...")
                days = (datetime.now() - start_time).days + 1
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Download in chunks (Binance limit: 1000 candles per request)
        candles_downloaded = 0
        current_time = int(start_time.timestamp() * 1000)  # Binance uses milliseconds
        end_time_ms = int(end_time.timestamp() * 1000)
        
        while current_time < end_time_ms:
            try:
                # Make API request
                params = {
                    'symbol': binance_symbol,
                    'interval': self.TIMEFRAME_MAP[timeframe],
                    'startTime': current_time,
                    'limit': 1000
                }
                
                response = requests.get(self.BINANCE_API, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                if not data:
                    break
                
                # Convert to our format
                candles = []
                for candle in data:
                    candles.append({
                        'symbol': symbol,
                        'timestamp': int(candle[0] / 1000),  # Convert ms to seconds
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': float(candle[5]),
                        'timeframe': timeframe
                    })
                
                # Insert into database
                self.db.insert_ohlcv_bulk(candles)
                
                candles_downloaded += len(candles)
                current_time = int(data[-1][0]) + 1  # Move to next timestamp
                
                logger.info(f"Downloaded {candles_downloaded} candles so far...")
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error downloading data: {e}")
                break
        
        logger.info(f"✅ Downloaded {candles_downloaded} {timeframe} candles for {symbol}")
        return candles_downloaded
    
    def download_multiple_symbols(
        self,
        symbols: List[str],
        timeframes: List[str],
        days: int = 365
    ):
        """Download data for multiple symbols and timeframes"""
        total_candles = 0
        
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    count = self.download_historical_data(symbol, timeframe, days)
                    total_candles += count
                except Exception as e:
                    logger.error(f"Failed to download {symbol} {timeframe}: {e}")
        
        logger.info(f"\n✅ TOTAL: Downloaded {total_candles} candles")
        return total_candles
    
    def update_latest_data(self, symbol: str, timeframe: str) -> int:
        """Update to latest candles (for live updates)"""
        latest_timestamp = self.db.get_latest_ohlcv_timestamp(symbol, timeframe)
        
        if not latest_timestamp:
            # No data yet, download last 7 days
            return self.download_historical_data(symbol, timeframe, days=7)
        
        # Download from latest to now
        days_since = (datetime.now() - datetime.fromtimestamp(latest_timestamp)).days + 1
        return self.download_historical_data(symbol, timeframe, days=days_since)


def main():
    """Main entry point for data collection"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Download OHLCV data')
    parser.add_argument('--symbol', type=str, default='BTCUSD', help='Trading symbol')
    parser.add_argument('--timeframe', type=str, default='5m', help='Timeframe (5m, 1h, 1d)')
    parser.add_argument('--days', type=int, default=365, help='Days of history')
    parser.add_argument('--all', action='store_true', help='Download all configured symbols')
    
    args = parser.parse_args()
    
    collector = OHLCVCollector()
    
    if args.all:
        # Download all symbols from config
        symbols = collector.config['data']['symbols']
        timeframes = collector.config['data']['ohlcv']['timeframes']
        days = collector.config['data']['ohlcv']['lookback_days']
        
        print(f"\n📥 Downloading data for {len(symbols)} symbols x {len(timeframes)} timeframes")
        print(f"Symbols: {symbols}")
        print(f"Timeframes: {timeframes}")
        print(f"History: {days} days\n")
        
        collector.download_multiple_symbols(symbols, timeframes, days)
    else:
        # Download single symbol
        collector.download_historical_data(args.symbol, args.timeframe, args.days)
    
    # Show stats
    print("\n=== Database Statistics ===")
    stats = collector.db.get_database_stats()
    for table, count in stats.items():
        print(f"{table}: {count:,} records")


if __name__ == '__main__':
    main()
