"""
Delta Exchange IV vs RV Volatility Data Collector

Professional data collection service for IV/RV chart system.
Polls Delta Exchange APIs every 30 seconds and stores historical data in SQLite.

Features:
- Fetches IV from Delta Exchange options tickers (ATM strikes)
- Calculates RV from OHLCV data (daily, weekly, monthly)
- Stores timestamped snapshots in SQLite database
- Supports multiple timeframes (1d, 7d, 30d)
- Fast queries optimized for chart rendering
- Auto-cleanup of old data (keeps 90 days)
"""

import os
import sys
import time
import json
import logging
import sqlite3
import requests
import math
from pathlib import Path
from datetime import datetime, timedelta, timezone
from threading import Thread, Lock
from typing import Dict, Any, Optional, List, Tuple, Callable

# Setup logging first
log = logging.getLogger(__name__)

# Import prediction engine
try:
    from .predictive_engine import get_predictor
except ImportError:
    log.warning("Predictive engine not available")
    get_predictor = None

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
log = logging.getLogger("volatility_collector")

DEFAULT_DB_PATH = str((project_root / "data" / "volatility.db").resolve())


class DeltaVolatilityCollector:
    """
    Collects and stores IV/RV data from Delta Exchange for charting.
    """
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        Initialize volatility collector.
        
        Args:
            db_path: Path to SQLite database file
        """
        if db_path != ":memory:" and not os.path.isabs(db_path):
            self.db_path = str((project_root / db_path).resolve())
        else:
            self.db_path = db_path
        self.api_base = "https://api.india.delta.exchange"
        self.symbol = "BTCUSD"
        self.collection_interval = 30  # seconds
        
        # State
        self._running = False
        self._thread: Optional[Thread] = None
        self._lock = Lock()
        self._emit_callback: Optional[Callable[[], None]] = None
        
        # Prediction engine
        self._predictor = get_predictor() if get_predictor else None
        self._last_warning_time = 0
        
        # Initialize database
        self._init_database()
        
        log.info("=" * 70)
        log.info("📊 DELTA VOLATILITY COLLECTOR INITIALIZED")
        log.info("=" * 70)
        log.info(f"Database: {self.db_path}")
        log.info(f"API Base: {self.api_base}")
        log.info(f"Symbol: {self.symbol}")
        log.info(f"Collection Interval: {self.collection_interval}s")
        log.info("=" * 70)
    
    def _init_database(self):
        """Initialize SQLite database with optimized schema"""
        # Create data directory if needed
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path, timeout=10.0)  # 10 second timeout
        cursor = conn.cursor()
        
        # Create IV snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS iv_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                datetime TEXT NOT NULL,
                iv_value REAL NOT NULL,
                source TEXT NOT NULL,
                atm_strike REAL,
                num_options INTEGER
            )
        """)
        
        # Create RV calculations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rv_calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                datetime TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                rv_value REAL NOT NULL,
                num_candles INTEGER,
                start_price REAL,
                end_price REAL
            )
        """)
        
        # Create indexes for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_iv_timestamp 
            ON iv_snapshots(timestamp DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rv_timestamp_timeframe 
            ON rv_calculations(timestamp DESC, timeframe)
        """)
        
        conn.commit()
        conn.close()
        
        log.info("✅ Database initialized with optimized schema")
    
    def start(self):
        """Start background collection thread"""
        if self._running:
            log.warning("Collector already running")
            return
        
        self._running = True
        self._thread = Thread(target=self._collection_loop, daemon=True)
        self._thread.start()
        log.info("✅ Volatility collector started")
    
    def stop(self):
        """Stop background collection"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Volatility collector stopped")
    
    def _collection_loop(self):
        """Main collection loop - runs every 30 seconds"""
        log.info("🔄 Collection loop started")
        
        while self._running:
            try:
                updated = False
                # Collect IV
                iv_data = self._fetch_and_store_iv()
                if iv_data:
                    log.info(f"✅ IV: {iv_data['value']:.2f}% (from {iv_data['num_options']} options)")
                    updated = True
                
                # Collect RV for all timeframes (including hourly)
                for timeframe in ['1h', '1d', '7d', '30d']:
                    rv_data = self._fetch_and_store_rv(timeframe)
                    if rv_data:
                        log.info(f"✅ RV ({timeframe}): {rv_data['value']:.2f}% ({rv_data['num_candles']} candles)")
                        updated = True
                
                # Cleanup old data (keep 90 days)
                self._cleanup_old_data(days=90)

                if updated:
                    self._trigger_emit()
                    
                    # Check for volatility spike prediction
                    self._check_spike_prediction()
                
            except Exception as e:
                log.error(f"Collection error: {e}", exc_info=True)
            
            # Sleep for collection interval
            for _ in range(self.collection_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def set_emit_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """
        Register a callback to be invoked whenever new data is stored.
        The callback is expected to emit updates over WebSocket.
        """
        with self._lock:
            self._emit_callback = callback

    def _trigger_emit(self) -> None:
        """Invoke the registered emit callback in a safe manner."""
        callback = None
        with self._lock:
            callback = self._emit_callback
        if not callback:
            return
        try:
            callback()
        except Exception as exc:
            log.warning(f"Failed to broadcast volatility update: {exc}", exc_info=True)
    
    def _check_spike_prediction(self):
        """Check for volatility spike predictions and emit warnings"""
        if not self._predictor:
            return
        
        try:
            warning = self._predictor.get_early_warning()
            if warning:
                # Avoid spam - only warn once per 5 minutes
                current_time = time.time()
                if current_time - self._last_warning_time > 300:  # 5 minutes
                    log.warning("🚨 VOLATILITY SPIKE PREDICTION:")
                    log.warning(f"   {warning['message']}")
                    log.warning(f"   Confidence: {warning['confidence']}")
                    log.warning(f"   Current IV: {warning['current_iv']}")
                    log.warning(f"   Predicted IV: {warning['predicted_iv']}")
                    log.warning(f"   Pattern: {warning['pattern']}")
                    
                    self._last_warning_time = current_time
                    
                    # Emit warning via callback if available
                    self._emit_prediction_warning(warning)
        
        except Exception as e:
            log.error(f"Spike prediction error: {e}")
    
    def _emit_prediction_warning(self, warning: Dict[str, Any]):
        """Emit prediction warning via WebSocket"""
        # This would integrate with WebSocket system
        # For now, just log the structured warning
        log.info(f"📡 Emitting spike prediction: {warning}")
    
    def _fetch_and_store_iv(self) -> Optional[Dict[str, Any]]:
        """
        Fetch IV from Delta Exchange options and store in database.
        
        Returns:
            Dict with IV data if successful, None otherwise
        """
        try:
            # Get current BTC price
            ticker_url = f"{self.api_base}/v2/tickers/{self.symbol}"
            ticker_resp = requests.get(ticker_url, timeout=10)
            
            if ticker_resp.status_code != 200:
                log.warning(f"Failed to fetch ticker: HTTP {ticker_resp.status_code}")
                return None
            
            ticker_data = ticker_resp.json()
            if 'result' not in ticker_data or 'mark_price' not in ticker_data['result']:
                log.warning("Mark price not found in ticker response")
                return None
            
            spot_price = float(ticker_data['result']['mark_price'])
            
            # Get all BTC option tickers
            tickers_url = f"{self.api_base}/v2/tickers"
            params = {
                'underlying_asset_symbols': 'BTC',
                'contract_types': 'call_options,put_options'
            }
            tickers_resp = requests.get(tickers_url, params=params, timeout=10)
            
            if tickers_resp.status_code != 200:
                log.warning(f"Failed to fetch option tickers: HTTP {tickers_resp.status_code}")
                return None
            
            tickers_data = tickers_resp.json()
            if 'result' not in tickers_data:
                log.warning("No tickers data in response")
                return None
            
            # Find ATM options with IV data - filter for nearest expiry only (industry standard)
            options_by_expiry = {}
            for ticker in tickers_data['result']:
                quotes = ticker.get('quotes', {})
                
                # Get mark_iv (or calculate from bid/ask)
                mark_iv = quotes.get('mark_iv')
                if mark_iv is None:
                    bid_iv = quotes.get('bid_iv')
                    ask_iv = quotes.get('ask_iv')
                    if bid_iv and ask_iv:
                        mark_iv = (float(bid_iv) + float(ask_iv)) / 2
                    elif bid_iv:
                        mark_iv = float(bid_iv)
                    elif ask_iv:
                        mark_iv = float(ask_iv)
                    else:
                        continue
                else:
                    mark_iv = float(mark_iv)
                
                # Get strike price
                strike_price = ticker.get('strike_price')
                if strike_price is None:
                    continue
                
                strike = float(strike_price)
                
                # Extract expiry from symbol (e.g., 'C-BTC-111000-301025' -> '301025')
                symbol = ticker.get('symbol', '')
                parts = symbol.split('-')
                if len(parts) < 4:
                    continue
                
                expiry_str = parts[3]
                
                # Find options within 5% of spot (tight ATM range for accuracy)
                price_diff_pct = abs((strike - spot_price) / spot_price * 100)
                if price_diff_pct < 5:
                    iv_value = mark_iv * 100  # Convert to percentage
                    
                    if expiry_str not in options_by_expiry:
                        options_by_expiry[expiry_str] = []
                    
                    options_by_expiry[expiry_str].append({
                        'strike': strike,
                        'iv': iv_value,
                        'diff': price_diff_pct,
                        'symbol': symbol
                    })
            
            if not options_by_expiry:
                log.warning("No ATM options with IV found")
                return None
            
            # Use only the nearest expiry (industry standard for ATM IV)
            # Parse expiry dates properly: format is DDMMYY (e.g., '301025' = Oct 30, 2025)
            def parse_expiry(exp_str):
                try:
                    day = int(exp_str[0:2])
                    month = int(exp_str[2:4])
                    year = 2000 + int(exp_str[4:6])
                    return datetime(year, month, day)
                except:
                    return datetime.max  # Invalid dates go to end
            
            # Sort by actual date, get nearest
            nearest_expiry = min(options_by_expiry.keys(), key=parse_expiry)
            atm_options = options_by_expiry[nearest_expiry]
            
            nearest_date = parse_expiry(nearest_expiry)
            log.info(f"Using nearest expiry: {nearest_expiry} ({nearest_date.strftime('%Y-%m-%d')}) with {len(atm_options)} ATM options)")
            
            if not atm_options:
                log.warning("No ATM options with IV found")
                return None
            
            # Calculate weighted average (closer to ATM = higher weight)
            total_weight = 0
            weighted_iv = 0
            for opt in atm_options:
                weight = 1 / (1 + opt['diff'])
                weighted_iv += opt['iv'] * weight
                total_weight += weight
            
            avg_iv = weighted_iv / total_weight if total_weight > 0 else None
            
            if avg_iv is None:
                return None
            
            # Store in database
            timestamp = time.time()
            dt = datetime.now(timezone.utc).isoformat()
            
            try:
                conn = sqlite3.connect(self.db_path, timeout=5.0)  # 5 second timeout
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO iv_snapshots (timestamp, datetime, iv_value, source, atm_strike, num_options)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (timestamp, dt, avg_iv, 'delta_exchange', spot_price, len(atm_options)))
                conn.commit()
                conn.close()
            except sqlite3.OperationalError as e:
                log.warning(f"Database locked, skipping IV store: {e}")
                return None
            
            return {
                'value': avg_iv,
                'timestamp': timestamp,
                'datetime': dt,
                'num_options': len(atm_options),
                'atm_strike': spot_price
            }
            
        except Exception as e:
            log.error(f"Failed to fetch/store IV: {e}", exc_info=True)
            return None
    
    def _fetch_and_store_rv(self, timeframe: str) -> Optional[Dict[str, Any]]:
        """
        Calculate RV from Delta Exchange OHLCV data and store in database.
        
        Args:
            timeframe: '1h', '1d', '7d', or '30d'
        
        Returns:
            Dict with RV data if successful, None otherwise
        """
        try:
            # Map timeframe to resolution and lookback period
            timeframe_config = {
                '1h': {'resolution': '1m', 'hours': 1, 'annualize_factor': math.sqrt(365 * 24 * 60)},
                '1d': {'resolution': '1h', 'days': 1, 'annualize_factor': math.sqrt(365 * 24)},
                '7d': {'resolution': '1d', 'days': 7, 'annualize_factor': math.sqrt(365)},
                '30d': {'resolution': '1d', 'days': 30, 'annualize_factor': math.sqrt(365)}
            }
            
            if timeframe not in timeframe_config:
                log.warning(f"Invalid timeframe: {timeframe}")
                return None
            
            config = timeframe_config[timeframe]
            
            # Calculate time range
            end_time = int(time.time())
            if 'hours' in config:
                start_time = int((datetime.now(timezone.utc) - timedelta(hours=config['hours'])).timestamp())
            else:
                start_time = int((datetime.now(timezone.utc) - timedelta(days=config['days'])).timestamp())
            
            # Fetch candles from Delta Exchange
            candles_url = f"{self.api_base}/v2/history/candles"
            params = {
                'symbol': self.symbol,
                'resolution': config['resolution'],
                'start': start_time,
                'end': end_time
            }
            
            response = requests.get(candles_url, params=params, timeout=10)
            
            if response.status_code != 200:
                log.warning(f"Failed to fetch candles for {timeframe}: HTTP {response.status_code}")
                return None
            
            data = response.json()
            if 'result' not in data:
                log.warning(f"No candle data for {timeframe}")
                return None
            
            candles = data['result']
            if len(candles) < 2:
                log.warning(f"Insufficient candles for {timeframe} RV calculation")
                return None
            
            # Extract close prices
            close_prices = [float(candle['close']) for candle in candles]
            
            # Calculate log returns
            log_returns = []
            for i in range(1, len(close_prices)):
                if close_prices[i-1] > 0 and close_prices[i] > 0:
                    log_return = math.log(close_prices[i] / close_prices[i-1])
                    log_returns.append(log_return)
            
            if len(log_returns) < 2:
                log.warning(f"Insufficient returns for {timeframe} RV calculation")
                return None
            
            # Calculate standard deviation
            mean_return = sum(log_returns) / len(log_returns)
            variance = sum((r - mean_return) ** 2 for r in log_returns) / (len(log_returns) - 1)
            std_dev = math.sqrt(variance)
            
            # Annualize volatility
            annualized_vol = std_dev * config['annualize_factor']
            rv_percent = annualized_vol * 100
            
            # Store in database
            timestamp = time.time()
            dt = datetime.now(timezone.utc).isoformat()
            
            try:
                conn = sqlite3.connect(self.db_path, timeout=5.0)  # 5 second timeout
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO rv_calculations (timestamp, datetime, timeframe, rv_value, num_candles, start_price, end_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, dt, timeframe, rv_percent, len(candles), close_prices[0], close_prices[-1]))
                conn.commit()
                conn.close()
            except sqlite3.OperationalError as e:
                log.warning(f"Database locked, skipping RV store for {timeframe}: {e}")
                return None
            
            return {
                'value': rv_percent,
                'timestamp': timestamp,
                'datetime': dt,
                'timeframe': timeframe,
                'num_candles': len(candles),
                'start_price': close_prices[0],
                'end_price': close_prices[-1]
            }
            
        except Exception as e:
            log.error(f"Failed to fetch/store RV for {timeframe}: {e}", exc_info=True)
            return None
    
    def _cleanup_old_data(self, days: int = 90):
        """
        Remove data older than specified days to keep database small.
        
        Args:
            days: Number of days to keep
        """
        try:
            cutoff_timestamp = time.time() - (days * 24 * 3600)
            
            conn = sqlite3.connect(self.db_path, timeout=5.0)  # 5 second timeout
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM iv_snapshots WHERE timestamp < ?", (cutoff_timestamp,))
            deleted_iv = cursor.rowcount
            
            cursor.execute("DELETE FROM rv_calculations WHERE timestamp < ?", (cutoff_timestamp,))
            deleted_rv = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if deleted_iv > 0 or deleted_rv > 0:
                log.info(f"🧹 Cleaned up old data: {deleted_iv} IV records, {deleted_rv} RV records")
        
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            log.warning(f"Database locked during cleanup, skipping: {e}")
        except Exception as e:
            log.error(f"Failed to cleanup old data: {e}")
    
    def get_historical_data(self, timeframe: str = 'daily', limit: int = 100) -> Dict[str, List]:
        """
        Get historical IV/RV data for charting.
        
        Args:
            timeframe: 'daily', 'weekly', or 'monthly'
            limit: Maximum number of data points to return
        
        Returns:
            Dict with 'iv' and 'rv' arrays, each containing {timestamp, value} objects
        """
        try:
            # Map chart timeframe to RV timeframe
            rv_timeframe_map = {
                'hourly': '1h',
                'daily': '1d',
                'weekly': '7d',
                'monthly': '30d'
            }
            
            rv_timeframe = rv_timeframe_map.get(timeframe, '1d')
            
            conn = sqlite3.connect(self.db_path, timeout=5.0)  # 5 second timeout
            cursor = conn.cursor()
            
            # First, determine how much IV data we have (for adaptive sampling)
            cursor.execute("SELECT (MAX(timestamp) - MIN(timestamp)) / 86400.0 FROM iv_snapshots")
            days_of_data = cursor.fetchone()[0] or 0
            
            # Determine the time window to show based on IV data availability
            # This ensures both lines are visible and comparable
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM iv_snapshots")
            iv_range = cursor.fetchone()
            
            if iv_range[0] and iv_range[1]:
                # We have IV data - determine intelligent time window based on selected timeframe
                iv_span_seconds = iv_range[1] - iv_range[0]
                iv_span_days = iv_span_seconds / 86400
                
                # Adaptive time window based on chart timeframe
                if timeframe == 'hourly':
                    # For hourly view, show last 24 hours for full day visibility
                    # Data collected every 30 seconds, chart displays with 1-hour X-axis ticks
                    cutoff_timestamp = time.time() - (24 * 3600)  # 24 hours
                elif timeframe == 'weekly':
                    # For weekly view, show last 4 weeks (28 days)
                    cutoff_timestamp = time.time() - (28 * 86400)  # 28 days = 4 weeks
                elif timeframe == 'monthly':
                    # For monthly view, show last 3 months (90 days)
                    cutoff_timestamp = time.time() - (90 * 86400)  # 90 days = ~3 months
                else:
                    # For other timeframes, adaptive based on IV data age
                    if iv_span_days < 1:
                        window_days = 7
                    elif iv_span_days < 7:
                        window_days = 30
                    elif iv_span_days < 30:
                        window_days = 60
                    else:
                        window_days = 90
                    
                    cutoff_timestamp = time.time() - (window_days * 86400)
            else:
                # No IV data yet - default windows
                if timeframe == 'hourly':
                    cutoff_timestamp = time.time() - (24 * 3600)  # 24 hours
                else:
                    cutoff_timestamp = time.time() - (30 * 86400)  # 30 days
            
            # Adaptive sampling based on timeframe and IV data age
            if timeframe == 'hourly':
                # For hourly view: 30-second intervals for real-time tracking
                # Data collected every 30s, chart will show with 1-hour X-axis labels
                rv_sample_interval = 30  # 30 seconds
                sample_interval = 30  # 30 seconds for IV
            elif timeframe == 'weekly':
                # For weekly view: 6-hour intervals across 4 weeks for smooth trend
                rv_sample_interval = 21600  # 6 hours
                sample_interval = 21600  # 6 hours
            elif timeframe == 'monthly':
                # For monthly view: 1-day intervals across 3 months for smooth trend
                rv_sample_interval = 86400  # 1 day
                sample_interval = 86400  # 1 day
            elif days_of_data < 7:
                # Less than a week: sample every 10 minutes for smooth lines
                rv_sample_interval = 600  # 10 minutes
                sample_interval = 600  # 10 minutes
            elif days_of_data < 30:
                # 1-4 weeks: sample hourly
                rv_sample_interval = 3600  # 1 hour
                sample_interval = 3600  # 1 hour
            else:
                # 30+ days: sample every 4 hours
                rv_sample_interval = 14400  # 4 hours
                sample_interval = 14400  # 4 hours
            
            # Return data for the FULL requested time window (cutoff_timestamp to now)
            # Frontend will handle displaying empty sections where data doesn't exist yet
            
            current_time = time.time()
            
            # Align cutoff to bucket boundary for consistent timestamps
            aligned_cutoff = int(cutoff_timestamp / rv_sample_interval) * rv_sample_interval
            
            log.info(f"Fetching {timeframe} data: cutoff={datetime.fromtimestamp(aligned_cutoff)}, now={datetime.fromtimestamp(current_time)}, span={(current_time-aligned_cutoff)/86400:.1f} days")
            
            # Get RV data for the FULL time window
            cursor.execute(f"""
                SELECT 
                    CAST(timestamp / {rv_sample_interval} AS INTEGER) * {rv_sample_interval} as aligned_timestamp,
                    AVG(rv_value) as rv_value
                FROM rv_calculations
                WHERE timeframe = ?
                AND timestamp >= ?
                AND timestamp <= ?
                GROUP BY CAST(timestamp / {rv_sample_interval} AS INTEGER)
                ORDER BY aligned_timestamp ASC
            """, (rv_timeframe, aligned_cutoff, current_time))
            rv_rows = cursor.fetchall()
            rv_data = [{'timestamp': int(row[0] * 1000), 'value': round(row[1], 2)} for row in rv_rows]
            
            # Get IV data for the FULL time window
            cursor.execute(f"""
                SELECT 
                    CAST(timestamp / {rv_sample_interval} AS INTEGER) * {rv_sample_interval} as aligned_timestamp,
                    AVG(iv_value) as iv_value
                FROM iv_snapshots
                WHERE timestamp >= ?
                AND timestamp <= ?
                GROUP BY CAST(timestamp / {rv_sample_interval} AS INTEGER)
                ORDER BY aligned_timestamp ASC
            """, (aligned_cutoff, current_time))
            iv_rows = cursor.fetchall()
            iv_data = [{'timestamp': int(row[0] * 1000), 'value': round(row[1], 2)} for row in iv_rows]
            
            conn.close()
            
            return {
                'iv': iv_data,
                'rv': rv_data
            }
            
        except Exception as e:
            log.error(f"Failed to get historical data: {e}")
            return {'iv': [], 'rv': []}
    
    def get_latest_values(self) -> Dict[str, Any]:
        """
        Get latest IV and RV values.
        
        Returns:
            Dict with latest IV and RV values
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)  # 5 second timeout
            cursor = conn.cursor()
            
            # Get latest IV
            cursor.execute("""
                SELECT iv_value, timestamp FROM iv_snapshots
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            iv_row = cursor.fetchone()
            latest_iv = {'value': round(iv_row[0], 2), 'timestamp': int(iv_row[1] * 1000)} if iv_row else None
            
            # Get latest RV for each timeframe (including hourly)
            latest_rv = {}
            for tf in ['1h', '1d', '7d', '30d']:
                cursor.execute("""
                    SELECT rv_value, timestamp FROM rv_calculations
                    WHERE timeframe = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (tf,))
                rv_row = cursor.fetchone()
                if rv_row:
                    latest_rv[tf] = {'value': round(rv_row[0], 2), 'timestamp': int(rv_row[1] * 1000)}
            
            conn.close()
            
            return {
                'iv': latest_iv,
                'rv': latest_rv
            }
            
        except Exception as e:
            log.error(f"Failed to get latest values: {e}")
            return {'iv': None, 'rv': {}}


# Global singleton instance
_collector: Optional[DeltaVolatilityCollector] = None


def get_collector() -> DeltaVolatilityCollector:
    """Get or create global collector instance"""
    global _collector
    if _collector is None:
        _collector = DeltaVolatilityCollector(DEFAULT_DB_PATH)
    return _collector


def main():
    """Run collector as standalone service"""
    collector = get_collector()
    collector.start()
    
    log.info("Volatility collector running. Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping collector...")
        collector.stop()
        log.info("Collector stopped")


if __name__ == "__main__":
    main()
