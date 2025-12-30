"""
RSI Collector - Fetches hourly OHLCV data and calculates RSI

Fetches hourly candles from Delta Exchange India and calculates
Relative Strength Index (RSI) for guardian Layer 6 monitoring.
"""
import time
import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)


class RSICollector:
    """
    Collects RSI data from Delta Exchange hourly OHLCV candles.
    
    Features:
    - Fetches hourly candles from Delta Exchange API
    - Calculates RSI using standard formula (14-period default)
    - Caches RSI values to reduce API calls
    - Fail-safe: Returns None if data unavailable (doesn't block trading)
    """
    
    def __init__(self, exchange, config):
        """
        Initialize RSI collector.
        
        Args:
            exchange: CCXT exchange instance (for consistency, though we use REST API)
            config: Guardian configuration (RootConfig object)
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
        
        # Get symbol from config
        if hasattr(config, 'bot') and hasattr(config.bot, 'symbol'):
            self.symbol = config.bot.symbol
        else:
            self.symbol = "BTCUSD"
        
        # Get bot mode (LONG/SHORT)
        if hasattr(config, 'bot') and hasattr(config.bot, 'mode'):
            self.bot_mode = config.bot.mode.upper()  # LONG or SHORT
        else:
            self.bot_mode = "LONG"  # Default to LONG
        
        # Get RSI config (with defaults)
        if hasattr(config, 'safety') and hasattr(config.safety, 'rsi'):
            rsi_config = config.safety.rsi
            self.enabled = getattr(rsi_config, 'enabled', True)
            self.period = getattr(rsi_config, 'period', 14)
            self.timeframe = getattr(rsi_config, 'timeframe', '1h')
            self.cache_ttl = getattr(rsi_config, 'cache_ttl', 60)
            self.long_threshold = getattr(rsi_config, 'long_threshold', 75.0)
            self.short_threshold = getattr(rsi_config, 'short_threshold', 25.0)
            self.hysteresis_seconds = getattr(rsi_config, 'hysteresis_seconds', 60)
        else:
            # Defaults if config not available
            self.enabled = True
            self.period = 14
            self.timeframe = '1h'
            self.cache_ttl = 60
            self.long_threshold = 75.0
            self.short_threshold = 25.0
            self.hysteresis_seconds = 60
        
        # Validate configuration
        self._validate_config()
        
        # Cache
        self._cached_rsi: Optional[float] = None
        self._cache_timestamp: float = 0
        
        # Hysteresis state tracking
        self._current_signal: Optional[str] = None  # 'GO' or 'STOP'
        self._hysteresis_start_time: Optional[float] = None  # When RSI hit exact threshold
        
        # Signal history for monitoring
        self._signal_changes = []  # Track signal change history
        self._last_logged_rsi = None  # For rate-limited logging
        self._last_log_time = 0
        
        log.info(f"RSICollector initialized: {self.symbol} {self.timeframe}")
        log.info(f"  Bot Mode: {self.bot_mode}")
        log.info(f"  API Base: {self.api_base}")
        log.info(f"  Period: {self.period}")
        log.info(f"  Long Threshold: {self.long_threshold} (STOP when RSI >= this in LONG mode)")
        log.info(f"  Short Threshold: {self.short_threshold} (STOP when RSI <= this in SHORT mode)")
        log.info(f"  Hysteresis: {self.hysteresis_seconds}s delay at threshold")
        log.info(f"  Cache TTL: {self.cache_ttl}s")
    
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
                    log.info(f"📊 RSI Update: {rsi:.2f} ({self.bot_mode} mode, threshold: {self.long_threshold if self.bot_mode == 'LONG' else self.short_threshold})")
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
        
        # Determine threshold based on mode with hysteresis band
        # Hysteresis band: ±2 RSI points around threshold to prevent oscillation
        hysteresis_band = 2.0
        
        if self.bot_mode == "LONG":
            threshold = self.long_threshold
            # LONG mode: STOP when RSI >= 75
            # Hysteresis zone: 73-77 (threshold ± 2)
            is_at_threshold = (threshold - hysteresis_band) <= rsi <= (threshold + hysteresis_band)
            should_stop = rsi >= threshold
        else:  # SHORT mode
            threshold = self.short_threshold
            # SHORT mode: STOP when RSI <= 25
            # Hysteresis zone: 23-27 (threshold ± 2)
            is_at_threshold = (threshold - hysteresis_band) <= rsi <= (threshold + hysteresis_band)
            should_stop = rsi <= threshold
        
        # Handle hysteresis when RSI is in threshold zone
        if is_at_threshold:
            if self._hysteresis_start_time is None:
                # Start hysteresis timer
                self._hysteresis_start_time = current_time
                log.debug(f"RSI at threshold {threshold:.1f}, starting {self.hysteresis_seconds}s hysteresis timer")
            
            # Check if hysteresis period has elapsed
            elapsed = current_time - self._hysteresis_start_time
            if elapsed < self.hysteresis_seconds:
                # During hysteresis, maintain previous signal
                if self._current_signal is None:
                    # First time at threshold, use current should_stop value
                    self._current_signal = 'STOP' if should_stop else 'GO'
                log.debug(f"RSI at threshold, hysteresis active ({elapsed:.1f}s/{self.hysteresis_seconds}s), maintaining {self._current_signal}")
                return self._current_signal == 'STOP'
            else:
                # Hysteresis period elapsed, apply new signal
                self._hysteresis_start_time = None
                self._current_signal = 'STOP' if should_stop else 'GO'
                log.debug(f"RSI at threshold, hysteresis elapsed, applying {self._current_signal}")
                return should_stop
        else:
            # Not at threshold, clear hysteresis and apply signal immediately
            if self._hysteresis_start_time is not None:
                log.debug(f"RSI moved away from threshold, clearing hysteresis")
                self._hysteresis_start_time = None
            
            new_signal = 'STOP' if should_stop else 'GO'
            
            # Track signal changes
            if self._current_signal != new_signal:
                self._track_signal_change(self._current_signal, new_signal, rsi)
            
            self._current_signal = new_signal
            return should_stop
    
    def _track_signal_change(self, old_signal: Optional[str], new_signal: str, rsi: float) -> None:
        \"\"\"Track and log signal changes for monitoring.\"\"\"\n        change_record = {
            'timestamp': time.time(),
            'datetime': datetime.now(timezone.utc).isoformat(),
            'old_signal': old_signal,
            'new_signal': new_signal,
            'rsi': rsi,
            'mode': self.bot_mode,
            'threshold': self.long_threshold if self.bot_mode == 'LONG' else self.short_threshold
        }
        \n        # Keep last 50 signal changes
        self._signal_changes.append(change_record)
        if len(self._signal_changes) > 50:
            self._signal_changes.pop(0)
        \n        # Log significant changes
        if new_signal == 'STOP':
            log.warning(f\"🚨 RSI STOP Signal: {old_signal or 'NONE'} → {new_signal} (RSI: {rsi:.2f}, Mode: {self.bot_mode})\")\n        else:
            log.info(f\"✅ RSI GO Signal: {old_signal or 'NONE'} → {new_signal} (RSI: {rsi:.2f}, Mode: {self.bot_mode})\")\n    \n    def get_signal_history(self) -> list:
        \"\"\"Get recent signal change history for monitoring.\"\"\"\n        return self._signal_changes.copy()
    
    def _fetch_and_calculate_rsi(self) -> Optional[float]:
        """
        Fetch OHLCV data and calculate RSI.
        
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
            
            # Calculate RSI
            rsi = self._calculate_rsi(close_prices, self.period)
            
            if rsi is not None:
                log.debug(f"Calculated RSI: {rsi:.2f} (from {len(candles)} candles)")
            
            return rsi
            
        except Exception as e:
            log.error(f"Error in RSI calculation: {e}", exc_info=True)
            return None
    
    def _fetch_ohlcv_data(self) -> Optional[list]:
        """
        Fetch hourly OHLCV candles from Delta Exchange with retry logic.
        
        Returns:
            List of candle dictionaries or None if fetch fails
        """
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Calculate time range: need at least period+1 hours of data
                end_time = int(time.time())
                # Fetch extra candles for safety (period + 5 hours)
                hours_needed = self.period + 5
                start_time = end_time - (hours_needed * 3600)
                
                # Fetch candles from Delta Exchange
                candles_url = f"{self.api_base}/v2/history/candles"
                params = {
                    'symbol': self.symbol,
                    'resolution': self.timeframe,
                    'start': start_time,
                    'end': end_time
                }
                
                log.debug(f"Fetching candles (attempt {attempt + 1}/{max_retries}): {candles_url}")
                response = requests.get(candles_url, params=params, timeout=10)
                
                if response.status_code != 200:
                    log.warning(f"Failed to fetch candles: HTTP {response.status_code}")
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        log.info(f"Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    return None
                
                data = response.json()
                if 'result' not in data:
                    log.warning("No candle data in response")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return None
                
                candles = data['result']
                if not candles:
                    log.warning("Empty candle data")
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
            
            log.debug(f"Fetched {len(valid_candles)} valid candles from Delta Exchange")
            return valid_candles
                
                # Success - break retry loop and continue with validation
                break
                
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
    
    def _calculate_rsi(self, prices: list, period: int) -> Optional[float]:
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
                    return 100.0
                else:
                    return 50.0  # No change
            
            # Calculate RS and RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # Ensure RSI is in valid range [0, 100]
            rsi = max(0, min(100, rsi))
            
            log.debug(f"RSI calculated: {rsi:.2f} (avg_gain={avg_gain:.4f}, avg_loss={avg_loss:.4f}, RS={rs:.4f})")
            
            return rsi
            
        except Exception as e:
            log.error(f"Error calculating RSI: {e}\", exc_info=True)
            return None
    
    def _validate_config(self) -> None:
        \"\"\"Validate RSI configuration parameters.\"\"\"\n        # Validate timeframe\n        valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1D']
        if self.timeframe not in valid_timeframes:
            log.warning(f\"Invalid timeframe '{self.timeframe}', defaulting to '1h'\")\n            self.timeframe = '1h'
        \n        # Validate period
        if self.period < 2 or self.period > 100:
            log.warning(f\"Invalid RSI period {self.period}, defaulting to 14\")\n            self.period = 14
        \n        # Validate thresholds
        if not (0 < self.long_threshold <= 100):
            log.warning(f\"Invalid long_threshold {self.long_threshold}, defaulting to 75.0\")\n            self.long_threshold = 75.0
        \n        if not (0 <= self.short_threshold < 100):
            log.warning(f\"Invalid short_threshold {self.short_threshold}, defaulting to 25.0\")\n            self.short_threshold = 25.0
        \n        # Validate cache TTL
        if self.cache_ttl < 10:
            log.warning(f\"Cache TTL too low ({self.cache_ttl}s), setting to 30s minimum\")\n            self.cache_ttl = 30
    
    def get_status(self) -> Dict[str, Any]:
        \"\"\"
        Get comprehensive RSI collector status for monitoring and debugging.
        
        Returns:
            Dictionary with RSI status, configuration, and state
        \"\"\"
        current_rsi = self.get_latest_rsi()
        \n        status = {
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
        \n        # Add threshold status
        if current_rsi is not None:
            if self.bot_mode == 'LONG':
                status['threshold_breach'] = current_rsi >= self.long_threshold
                status['distance_to_threshold'] = current_rsi - self.long_threshold
            else:
                status['threshold_breach'] = current_rsi <= self.short_threshold
                status['distance_to_threshold'] = self.short_threshold - current_rsi
        \n        return status
