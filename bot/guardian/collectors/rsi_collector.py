"""
RSI Collector - Fetches hourly OHLCV data and calculates RSI (IMPROVED VERSION)

Fetches hourly candles from Delta Exchange India and calculates
Relative Strength Index (RSI) for guardian Layer 6 monitoring.

IMPROVEMENTS (Senior Developer Review):
- Fixed RSI calculation to use Wilder's smoothing method (industry standard)
- Added input validation for candle data
- Added retry logic with exponential backoff
- Improved hysteresis logic (uses range instead of exact threshold)
- Added comprehensive error handling
- Added signal change tracking and logging
- Added status monitoring method
- Added configuration validation
"""
import time
import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

log = logging.getLogger(__name__)


class RSICollector:
    """
    Collects RSI data from Delta Exchange hourly OHLCV candles.
    
    Features:
    - Fetches hourly candles from Delta Exchange API
    - Calculates RSI using Wilder's smoothing method (industry standard)
    - Caches RSI values to reduce API calls
    - Mode-aware thresholds (LONG/SHORT)
    - Hysteresis to prevent signal oscillation
    - Fail-safe: Returns None if data unavailable (doesn't block trading)
    - Signal change tracking for monitoring
    - Comprehensive error handling with retries
    """
    
    def __init__(self, exchange, config, symbol_name: str = None):
        """
        Initialize RSI collector.
        
        Args:
            exchange: CCXT exchange instance (for consistency, though we use REST API)
            config: Guardian configuration (RootConfig object)
            symbol_name: Optional symbol override (e.g., "BTCUSD", "ETHUSD")
                        If provided, uses this symbol instead of config.bot.symbol
                        This enables multi-symbol RSI collection in v5.0
        """
        self.exchange = exchange
        self.config = config
        
        # Get API base URL from config
        if hasattr(config, 'api'):
            if hasattr(config.api, 'live') and hasattr(config.api.live, 'base_url'):
                self.api_base = config.api.live.base_url
            elif hasattr(config.api, 'live') and hasattr(config.api.live, 'public_url'):
                self.api_base = config.api.live.public_url
            else:
                self.api_base = "https://api.india.delta.exchange"
        else:
            self.api_base = "https://api.india.delta.exchange"
        
        # Get symbol - prefer explicit symbol_name parameter (v5.0 multi-symbol support)
        if symbol_name:
            self.symbol = symbol_name
        elif hasattr(config, 'bot') and hasattr(config.bot, 'symbol'):
            self.symbol = config.bot.symbol
        else:
            self.symbol = "BTCUSD"
        
        # Get bot mode (LONG/SHORT) - check symbol config first, then global
        if symbol_name and hasattr(config, 'symbols') and config.symbols and symbol_name in config.symbols:
            self.bot_mode = config.symbols[symbol_name].mode.upper()
        elif hasattr(config, 'bot') and hasattr(config.bot, 'mode'):
            self.bot_mode = config.bot.mode.upper()  # LONG or SHORT
        else:
            self.bot_mode = "LONG"  # Default to LONG
        
        # Initialize cache and state tracking variables FIRST
        # (required before reload_thresholds can be called)
        self._cached_rsi: Optional[float] = None
        self._cache_timestamp: float = 0
        self._current_signal: Optional[str] = None  # 'GO' or 'STOP'
        self._hysteresis_start_time: Optional[float] = None  # When RSI entered threshold zone
        self._signal_changes: List[Dict] = []  # Track signal change history
        self._last_logged_rsi: Optional[float] = None  # For rate-limited logging
        self._last_log_time: float = 0
        
        # v6.0: Try instance-specific RSI config first, then fall back to global
        instance_rsi_config = None
        if hasattr(config, 'instances') and hasattr(config, 'bot') and hasattr(config.bot, 'instance'):
            instance_name = config.bot.instance
            if instance_name in config.instances:
                instance_cfg = config.instances[instance_name]
                if hasattr(instance_cfg, 'safety') and hasattr(instance_cfg.safety, 'rsi'):
                    instance_rsi_config = instance_cfg.safety.rsi
                    log.info(f"Using instance-specific RSI config for {instance_name}")
        
        # Get RSI config (NO HARDCODED DEFAULTS - must be in config.yaml)
        if instance_rsi_config:
            # v6.0: Instance-specific RSI config uses stop_threshold based on mode
            rsi_config = instance_rsi_config
            self.enabled = getattr(rsi_config, 'enabled', True)
            self.period = getattr(rsi_config, 'period', 14)
            self.timeframe = getattr(rsi_config, 'timeframe', '1h')
            self.cache_ttl = getattr(rsi_config, 'cache_ttl', 60)
            self.hysteresis_seconds = getattr(rsi_config, 'hysteresis_seconds', 60)
            self.hysteresis_band = getattr(rsi_config, 'hysteresis_band', 2.0)
            # Instance config uses stop_threshold for the mode-specific value
            stop_threshold = getattr(rsi_config, 'stop_threshold', None)
            resume_threshold = getattr(rsi_config, 'resume_threshold', None)
            if self.bot_mode == "LONG":
                # LONG mode: stop when RSI <= threshold (oversold)
                self.long_threshold = stop_threshold if stop_threshold is not None else 30
                self.short_threshold = 75  # Not used for LONG, but set a default
            else:
                # SHORT mode: stop when RSI >= threshold (overbought)
                self.short_threshold = stop_threshold if stop_threshold is not None else 70
                self.long_threshold = 25  # Not used for SHORT, but set a default
        elif hasattr(config, 'safety') and hasattr(config.safety, 'rsi'):
            rsi_config = config.safety.rsi
            self.enabled = getattr(rsi_config, 'enabled', True)
            self.period = getattr(rsi_config, 'period', 14)
            self.timeframe = getattr(rsi_config, 'timeframe', '1h')
            self.cache_ttl = getattr(rsi_config, 'cache_ttl', 60)
            # NO DEFAULTS - these MUST be in config
            if not hasattr(rsi_config, 'long_threshold'):
                raise ValueError("safety.rsi.long_threshold missing in config.yaml")
            if not hasattr(rsi_config, 'short_threshold'):
                raise ValueError("safety.rsi.short_threshold missing in config.yaml")
            self.long_threshold = rsi_config.long_threshold
            self.short_threshold = rsi_config.short_threshold
            self.hysteresis_seconds = getattr(rsi_config, 'hysteresis_seconds', 60)
            self.hysteresis_band = getattr(rsi_config, 'hysteresis_band', 2.0)
        else:
            raise ValueError("safety.rsi configuration section missing in config.yaml")
        
        # Validate configuration
        self._validate_config()
        
        # Log initialization
        log.info(f"RSICollector initialized: {self.symbol} {self.timeframe}")
        log.info(f"  Bot Mode: {self.bot_mode}")
        log.info(f"  Period: {self.period}")
        log.info(f"  Long Threshold: {self.long_threshold} (STOP when RSI <= this - oversold)")
        log.info(f"  Short Threshold: {self.short_threshold} (STOP when RSI >= this - overbought)")
        log.info(f"  Hysteresis: {self.hysteresis_seconds}s delay, ±{self.hysteresis_band} RSI band")
        log.info(f"  Cache TTL: {self.cache_ttl}s")
    
    def reload_thresholds(self, config):
        """Reload RSI thresholds from config (for hot reload support)"""
        if hasattr(config, 'safety') and hasattr(config.safety, 'rsi'):
            rsi_config = config.safety.rsi
            if not hasattr(rsi_config, 'long_threshold'):
                raise ValueError("safety.rsi.long_threshold missing in config.yaml")
            if not hasattr(rsi_config, 'short_threshold'):
                raise ValueError("safety.rsi.short_threshold missing in config.yaml")
            
            old_long = self.long_threshold
            old_short = self.short_threshold
            
            self.long_threshold = rsi_config.long_threshold
            self.short_threshold = rsi_config.short_threshold
            self.hysteresis_seconds = getattr(rsi_config, 'hysteresis_seconds', 60)
            
            # Validate new thresholds
            if not (0 < self.long_threshold <= 100):
                raise ValueError(f"Invalid long_threshold {self.long_threshold} - must be between 0 and 100")
            if not (0 <= self.short_threshold < 100):
                raise ValueError(f"Invalid short_threshold {self.short_threshold} - must be between 0 and 100")
            
            if old_long != self.long_threshold or old_short != self.short_threshold:
                log.warning(f"🔄 RSI Thresholds reloaded: LONG {old_long}→{self.long_threshold}, SHORT {old_short}→{self.short_threshold}")
                # Reset hysteresis when thresholds change
                self._hysteresis_start_time = None
                self._current_signal = None
        else:
            raise ValueError("safety.rsi configuration section missing in config.yaml")
    
    def _validate_config(self) -> None:
        """Validate RSI configuration parameters."""
        # Validate timeframe
        valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1D']
        if self.timeframe not in valid_timeframes:
            log.warning(f"Invalid timeframe '{self.timeframe}', defaulting to '1h'")
            self.timeframe = '1h'
        
        # Validate period
        if self.period < 2 or self.period > 100:
            log.warning(f"Invalid RSI period {self.period}, defaulting to 14")
            self.period = 14
        
        # Validate thresholds - NO HARDCODED FALLBACKS
        if not (0 < self.long_threshold <= 100):
            raise ValueError(f"Invalid long_threshold {self.long_threshold} - must be between 0 and 100")
        
        if not (0 <= self.short_threshold < 100):
            raise ValueError(f"Invalid short_threshold {self.short_threshold} - must be between 0 and 100")
        
        # Validate cache TTL
        if self.cache_ttl < 10:
            log.warning(f"Cache TTL too low ({self.cache_ttl}s), setting to 30s minimum")
            self.cache_ttl = 30
    
    def get_latest_rsi(self) -> Optional[float]:
        """
        Get current RSI value.
        
        Returns:
            RSI value (0-100) or None if unavailable
        """
        if not self.enabled:
            log.debug("RSI monitoring disabled")
            return None
        
        # Check cache
        current_time = time.time()
        if (self._cached_rsi is not None and 
            (current_time - self._cache_timestamp) < self.cache_ttl):
            log.debug(f"Returning cached RSI: {self._cached_rsi:.2f}")
            return self._cached_rsi
        
        # Fetch fresh data
        try:
            rsi = self._fetch_and_calculate_rsi()
            if rsi is not None:
                self._cached_rsi = rsi
                self._cache_timestamp = current_time
                
                # Log RSI value (rate-limited: only if changed significantly or every 5 minutes)
                should_log = (
                    self._last_logged_rsi is None or
                    abs(rsi - self._last_logged_rsi) > 5.0 or  # Log if changed by 5+ points
                    (current_time - self._last_log_time) > 300  # Or every 5 minutes
                )
                if should_log:
                    threshold = self.long_threshold if self.bot_mode == 'LONG' else self.short_threshold
                    log.info(f"📊 RSI Update: {rsi:.2f} ({self.bot_mode} mode, threshold: {threshold})")
                    self._last_logged_rsi = rsi
                    self._last_log_time = current_time
            
            return rsi
        except Exception as e:
            log.error(f"Error fetching RSI: {e}", exc_info=True)
            # Fail-safe: return cached value if available, otherwise None
            return self._cached_rsi
    
    def should_stop_trading(self) -> bool:
        """
        Determine if trading should be stopped based on RSI and mode.
        Implements hysteresis to prevent signal jumping at threshold.
        
        Returns:
            True if trading should be stopped, False otherwise
        """
        if not self.enabled:
            return False
        
        rsi = self.get_latest_rsi()
        if rsi is None:
            return False  # Fail-safe: assume healthy if RSI unavailable
        
        current_time = time.time()
        
        # Use configurable hysteresis band to prevent oscillation at threshold
        hysteresis_band = self.hysteresis_band
        
        if self.bot_mode == "LONG":
            threshold = self.long_threshold  # e.g., 25
            # LONG mode: STOP when RSI <= threshold (oversold - market too weak to buy)
            # When RSI is low (≤25), market is oversold → bad time to open LONG positions
            # Hysteresis zone: [threshold - band, threshold] e.g., [23, 25]
            is_in_threshold_zone = (threshold - hysteresis_band) <= rsi <= threshold
            should_stop = rsi <= threshold
        else:  # SHORT mode
            threshold = self.short_threshold  # e.g., 75
            # SHORT mode: STOP when RSI >= threshold (overbought - market too strong to short)
            # When RSI is high (≥75), market is overbought → bad time to open SHORT positions
            # Hysteresis zone: [threshold, threshold + band] e.g., [75, 77]
            is_in_threshold_zone = threshold <= rsi <= (threshold + hysteresis_band)
            should_stop = rsi >= threshold
        
        # Handle hysteresis when RSI is in threshold zone
        if is_in_threshold_zone:
            if self._hysteresis_start_time is None:
                # Start hysteresis timer
                self._hysteresis_start_time = current_time
                log.debug(f"RSI in threshold zone ({rsi:.1f} near {threshold:.1f}), starting {self.hysteresis_seconds}s hysteresis timer")
            
            # Check if hysteresis period has elapsed
            elapsed = current_time - self._hysteresis_start_time
            if elapsed < self.hysteresis_seconds:
                # During hysteresis, maintain previous signal
                if self._current_signal is None:
                    # First time at threshold, use current should_stop value
                    self._current_signal = 'STOP' if should_stop else 'GO'
                log.debug(f"RSI in threshold zone, hysteresis active ({elapsed:.1f}s/{self.hysteresis_seconds}s), maintaining {self._current_signal}")
                return self._current_signal == 'STOP'
            else:
                # Hysteresis period elapsed, apply new signal
                self._hysteresis_start_time = None
                new_signal = 'STOP' if should_stop else 'GO'
                if self._current_signal != new_signal:
                    self._track_signal_change(self._current_signal, new_signal, rsi)
                self._current_signal = new_signal
                log.debug(f"RSI in threshold zone, hysteresis elapsed, applying {self._current_signal}")
                return should_stop
        else:
            # Not in threshold zone, clear hysteresis and apply signal immediately
            if self._hysteresis_start_time is not None:
                log.debug(f"RSI moved out of threshold zone, clearing hysteresis")
                self._hysteresis_start_time = None
            
            new_signal = 'STOP' if should_stop else 'GO'
            
            # Track signal changes
            if self._current_signal != new_signal:
                self._track_signal_change(self._current_signal, new_signal, rsi)
            
            self._current_signal = new_signal
            return should_stop
    
    def _track_signal_change(self, old_signal: Optional[str], new_signal: str, rsi: float) -> None:
        """Track and log signal changes for monitoring."""
        change_record = {
            'timestamp': time.time(),
            'datetime': datetime.now(timezone.utc).isoformat(),
            'old_signal': old_signal,
            'new_signal': new_signal,
            'rsi': rsi,
            'mode': self.bot_mode,
            'threshold': self.long_threshold if self.bot_mode == 'LONG' else self.short_threshold
        }
        
        # Keep last 50 signal changes
        self._signal_changes.append(change_record)
        if len(self._signal_changes) > 50:
            self._signal_changes.pop(0)
        
        # Log significant changes
        if new_signal == 'STOP':
            log.warning(f"🚨 RSI STOP Signal: {old_signal or 'NONE'} -> {new_signal} (RSI: {rsi:.2f}, Mode: {self.bot_mode})")
        else:
            log.info(f"✅ RSI GO Signal: {old_signal or 'NONE'} -> {new_signal} (RSI: {rsi:.2f}, Mode: {self.bot_mode})")
    
    def get_signal_history(self) -> List[Dict]:
        """Get recent signal change history for monitoring."""
        return self._signal_changes.copy()
    
    def _fetch_and_calculate_rsi(self) -> Optional[float]:
        """
        Fetch OHLCV data and calculate RSI with validation logging.
        
        Returns:
            RSI value (0-100) or None if calculation fails
        """
        try:
            # Fetch hourly candles (need at least period+1 candles for RSI)
            candles = self._fetch_ohlcv_data()
            
            if not candles or len(candles) < self.period + 1:
                log.warning(f"Insufficient candles for RSI calculation: {len(candles) if candles else 0} < {self.period + 1}")
                return None
            
            # Extract close prices
            close_prices = [float(candle['close']) for candle in candles]
            
            # LOG DATA VALIDATION
            log.info(f"📊 RSI Data Validation:")
            log.info(f"  Data Source: {self.api_base}")
            log.info(f"  Symbol: {self.symbol}, Timeframe: {self.timeframe}, Period: {self.period}")
            log.info(f"  Candles Received: {len(candles)}")
            log.info(f"  Time Range: {datetime.fromtimestamp(candles[0]['time'], tz=timezone.utc).strftime('%Y-%m-%d %H:%M')} to {datetime.fromtimestamp(candles[-1]['time'], tz=timezone.utc).strftime('%Y-%m-%d %H:%M')}")
            log.info(f"  Price Range: ${min(close_prices):.2f} - ${max(close_prices):.2f}")
            log.info(f"  First Price: ${close_prices[0]:.2f}, Last Price: ${close_prices[-1]:.2f}")
            log.info(f"  Price Change: ${close_prices[-1] - close_prices[0]:+.2f} ({((close_prices[-1] - close_prices[0]) / close_prices[0] * 100):+.2f}%)")
            
            # Calculate RSI
            rsi = self._calculate_rsi(close_prices, self.period)
            
            if rsi is not None:
                log.info(f"  ✅ Calculated RSI: {rsi:.2f}")
            else:
                log.warning(f"  ❌ RSI Calculation Failed")
            
            return rsi
            
        except Exception as e:
            log.error(f"Error in RSI calculation: {e}", exc_info=True)
            return None
    
    def _fetch_ohlcv_data(self) -> Optional[List[Dict]]:
        """
        Fetch hourly OHLCV candles from Delta Exchange with retry logic.
        
        Returns:
            List of candle dictionaries or None if fetch fails
        """
        max_retries = 3
        retry_delay = 1  # seconds
        
        # Expected interval for gap detection (in seconds)
        INTERVAL_MAP = {
            '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
            '1h': 3600, '2h': 7200, '4h': 14400, '6h': 21600,
            '12h': 43200, '1D': 86400, '1d': 86400, '1w': 604800
        }
        
        for attempt in range(max_retries):
            try:
                # Calculate time range: need at least period+1 hours of data
                end_time = int(time.time())
                # Fetch extra candles for safety (period + 5 hours)
                hours_needed = self.period + 5
                start_time = end_time - (hours_needed * 3600)
                
                # Fetch candles from Delta Exchange
                # Delta India API accepts: 5s,1m,3m,5m,15m,30m,1h,2h,4h,6h,12h,1d,1w
                candles_url = f"{self.api_base}/v2/history/candles"
                params = {
                    'symbol': self.symbol,
                    'resolution': self.timeframe,  # Use timeframe directly (e.g., '1h')
                    'start': start_time,
                    'end': end_time
                }
                
                log.debug(f"Fetching candles (attempt {attempt + 1}/{max_retries}): {candles_url}")
                log.debug(f"API Params: symbol={params['symbol']}, resolution={params['resolution']}, timeframe={self.timeframe}")
                response = requests.get(candles_url, params=params, timeout=10)
                
                if response.status_code != 200:
                    log.warning(f"Failed to fetch candles: HTTP {response.status_code}")
                    log.debug(f"Response text: {response.text[:500]}")
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        log.info(f"Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    return None
                
                data = response.json()
                
                # ✅ IMPROVED: Better response validation
                if not data or 'result' not in data:
                    log.warning(f"Invalid response structure - missing 'result' field")
                    log.debug(f"Response keys: {list(data.keys()) if data else 'None'}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return None
                
                candles = data['result']
                if not candles or len(candles) == 0:
                    log.warning("Empty candle data received from API")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return None
                
                # Validate candle data structure
                valid_candles = []
                for candle in candles:
                    # Check required fields
                    if not all(k in candle for k in ['time', 'open', 'high', 'low', 'close', 'volume']):
                        log.warning(f"Skipping invalid candle (missing fields): {candle}")
                        continue
                    
                    # Validate close price is a valid number
                    try:
                        close_price = float(candle['close'])
                        if close_price <= 0:
                            log.warning(f"Skipping candle with invalid close price: {close_price}")
                            continue
                        valid_candles.append(candle)
                    except (ValueError, TypeError) as e:
                        log.warning(f"Skipping candle with non-numeric close: {candle.get('close')} - {e}")
                        continue
                
                if len(valid_candles) < len(candles):
                    log.warning(f"Filtered {len(candles) - len(valid_candles)} invalid candles")
                
                if not valid_candles:
                    log.warning("No valid candles after filtering")
                    return None
                
                # Sort by time (ascending) to ensure correct order
                valid_candles.sort(key=lambda x: x.get('time', 0))
                
                # ✅ IMPROVED: Dynamic gap detection based on timeframe
                expected_interval = INTERVAL_MAP.get(self.timeframe, 3600)
                gap_warnings = []
                for i in range(1, len(valid_candles)):
                    time_diff = valid_candles[i]['time'] - valid_candles[i-1]['time']
                    if abs(time_diff - expected_interval) > 60:  # Allow 1 minute tolerance
                        gap_msg = f"Gap detected: {time_diff}s (expected {expected_interval}s) between candle {i-1} and {i}"
                        gap_warnings.append(gap_msg)
                        log.warning(f"⚠️  {gap_msg}")
                
                if gap_warnings:
                    log.warning(f"⚠️  Found {len(gap_warnings)} gaps in candle data - RSI may be inaccurate!")
                else:
                    log.debug(f"✅ All {len(valid_candles)} candles are continuous (no gaps)")
                
                log.debug(f"Fetched {len(valid_candles)} valid candles from Delta Exchange")
                log.debug(f"Full API Request: {candles_url}?symbol={self.symbol}&resolution={params['resolution']}&start={start_time}&end={end_time}")
                return valid_candles
                
            except requests.exceptions.Timeout:
                log.warning(f"API request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                return None
            except requests.exceptions.RequestException as e:
                log.warning(f"API request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                return None
            except Exception as e:
                log.error(f"Unexpected error fetching OHLCV data: {e}", exc_info=True)
                return None
    
    def _calculate_rsi(self, prices: List[float], period: int) -> Optional[float]:
        """
        Calculate RSI using Wilder's smoothing method (industry standard).
        
        Formula (Wilder's method):
        1. Calculate price changes: change = price[i] - price[i-1]
        2. Separate gains and losses: gain = max(change, 0), loss = max(-change, 0)
        3. First average: avg_gain = sum(first 14 gains) / 14, avg_loss = sum(first 14 losses) / 14
        4. Smoothed average: avg_gain = (prev_avg_gain * 13 + current_gain) / 14
        5. Calculate RS: RS = avg_gain / avg_loss
        6. Calculate RSI: RSI = 100 - (100 / (1 + RS))
        
        Args:
            prices: List of close prices (ascending order, oldest first)
            period: RSI calculation period (default 14)
        
        Returns:
            RSI value (0-100) or None if calculation fails
        """
        if len(prices) < period + 1:
            log.warning(f"Insufficient prices for RSI: {len(prices)} < {period + 1}")
            return None
        
        try:
            # Calculate price changes
            changes = []
            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                changes.append(change)
            
            if len(changes) < period:
                log.warning(f"Insufficient changes for RSI: {len(changes)} < {period}")
                return None
            
            # Separate gains and losses
            gains = [max(change, 0) for change in changes]
            losses = [max(-change, 0) for change in changes]
            
            # Calculate initial average gain and loss using first 'period' values
            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period
            
            # Apply Wilder's smoothing to remaining data points
            for i in range(period, len(gains)):
                avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
                avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
            
            # Handle division by zero (if avg_loss is 0, RSI = 100)
            if avg_loss == 0:
                if avg_gain > 0:
                    return 100.0  # All gains, no losses = maximum RSI
                else:
                    # Both avg_gain and avg_loss are 0 = no price movement
                    # Return neutral RSI (extremely rare scenario)
                    return 50.0
            
            # Calculate RS and RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # Ensure RSI is in valid range [0, 100]
            rsi = max(0, min(100, rsi))
            
            log.debug(f"RSI calculated: {rsi:.2f} (avg_gain={avg_gain:.4f}, avg_loss={avg_loss:.4f}, RS={rs:.4f})")
            
            return rsi
            
        except Exception as e:
            log.error(f"Error calculating RSI: {e}", exc_info=True)
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive RSI collector status for monitoring and debugging.
        
        Returns:
            Dictionary with RSI status, configuration, and state
        """
        current_rsi = self.get_latest_rsi()
        
        status = {
            'enabled': self.enabled,
            'rsi': current_rsi,
            'mode': self.bot_mode,
            'config': {
                'period': self.period,
                'timeframe': self.timeframe,
                'long_threshold': self.long_threshold,
                'short_threshold': self.short_threshold,
                'hysteresis_seconds': self.hysteresis_seconds,
                'cache_ttl': self.cache_ttl
            },
            'current_signal': self._current_signal,
            'hysteresis_active': self._hysteresis_start_time is not None,
            'cache_status': {
                'cached_rsi': self._cached_rsi,
                'cache_age_seconds': time.time() - self._cache_timestamp if self._cache_timestamp > 0 else None,
                'cache_valid': (time.time() - self._cache_timestamp) < self.cache_ttl if self._cache_timestamp > 0 else False
            },
            'signal_changes_count': len(self._signal_changes),
            'last_signal_change': self._signal_changes[-1] if self._signal_changes else None
        }
        
        # Add threshold status
        if current_rsi is not None:
            if self.bot_mode == 'LONG':
                status['threshold_breach'] = current_rsi >= self.long_threshold
                status['distance_to_threshold'] = current_rsi - self.long_threshold
            else:
                status['threshold_breach'] = current_rsi <= self.short_threshold
                status['distance_to_threshold'] = self.short_threshold - current_rsi
        
        return status
