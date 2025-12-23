"""
IV/RV Tracker - Real-Time Volatility Monitoring

Fetches Implied Volatility (IV) and Realized Volatility (RV) from Delta Exchange
and determines if market conditions are safe for grid trading.

Safety Rules:
1. IV must be < MAX_IV (default: 35%)
2. RV must be < MAX_RV (default: 40%)
3. |IV - RV| must be < MAX_SPREAD (default: 10%)

If any condition is violated, trading is blocked.
"""

import os
import sys
import json
import time
import logging
import requests
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from threading import Thread, Lock
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

log = logging.getLogger("volatility")


class VolatilityTracker:
    """
    Tracks IV and RV from Delta Exchange and enforces volatility-based safety rules.
    """
    
    def __init__(self):
        """Initialize volatility tracker"""
        # Configuration from YAML
        cfg = get_config()
        self.enabled = cfg.safety.volatility.enabled
        self.max_iv = cfg.safety.volatility.max_iv
        self.max_rv = cfg.safety.volatility.max_rv
        self.max_spread = cfg.safety.volatility.max_spread
        self.check_interval = cfg.safety.volatility.check_interval
        self.auto_resume = cfg.safety.volatility.auto_resume
        self.resume_buffer = cfg.safety.volatility.resume_buffer
        
        # State persistence file
        self.status_file = '.volatility_status.json'
        
        # State
        self.current_iv: Optional[float] = None
        self.current_rv: Optional[float] = None
        self.last_update: Optional[datetime] = None
        self.is_safe: bool = True
        self.violation_reason: Optional[str] = None
        self.last_notification: Optional[datetime] = None
        
        # Thread safety
        self._lock = Lock()
        self._running = False
        self._thread: Optional[Thread] = None
        
        # File watcher for instant hot reload
        self._config_file_path = Path('config.yaml')
        self._last_config_mtime = 0
        if self._config_file_path.exists():
            self._last_config_mtime = self._config_file_path.stat().st_mtime
        
        # API configuration
        # Always use production API for volatility data (public market data)
        # Volatility metrics don't require authentication and testnet lacks historical data
        self.api_base = "https://api.delta.exchange"
        
        self.symbol = cfg.bot.symbol
        
        log.info("=" * 70)
        log.info("🌊 VOLATILITY TRACKER INITIALIZED")
        log.info("=" * 70)
        log.info(f"Enabled: {self.enabled}")
        log.info(f"Max IV: {self.max_iv}%")
        log.info(f"Max RV: {self.max_rv}%")
        log.info(f"Max Spread: ±{self.max_spread}%")
        log.info(f"Check Interval: {self.check_interval}s")
        log.info(f"Symbol: {self.symbol}")
        log.info(f"API: {self.api_base}")
        log.info("=" * 70)
    
    def start(self):
        """Start background volatility monitoring"""
        if not self.enabled:
            log.info("Volatility safety disabled, not starting tracker")
            return
        
        if self._running:
            log.warning("Volatility tracker already running")
            return
        
        self._running = True
        self._thread = Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        log.info("✅ Volatility tracker started")
    
    def stop(self):
        """Stop background monitoring"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Volatility tracker stopped")
    
    def _check_config_file_changed(self) -> bool:
        """Check if config file was modified (file watcher for instant reload)"""
        try:
            if self._config_file_path.exists():
                current_mtime = self._config_file_path.stat().st_mtime
                if current_mtime > self._last_config_mtime:
                    self._last_config_mtime = current_mtime
                    return True
        except Exception as e:
            log.debug(f"Config file check failed: {e}")
        return False
    
    def _reload_config(self, force: bool = False):
        """
        Reload configuration values (hot reload support)
        
        Args:
            force: If True, reload even if file hasn't changed
        """
        try:
            from config.loader import reload_config
            
            # Reload YAML config to get latest values
            reload_config()
            cfg = get_config()
            
            # Read from YAML config
            new_max_iv = cfg.safety.volatility.max_iv
            new_max_rv = cfg.safety.volatility.max_rv
            new_max_spread = cfg.safety.volatility.max_spread
            
            # Check if values changed
            if (new_max_iv != self.max_iv or new_max_rv != self.max_rv or new_max_spread != self.max_spread):
                log.info("🔥 CONFIG HOT RELOAD: Volatility thresholds updated!")
                if new_max_iv != self.max_iv:
                    log.info(f"   IV Limit: {self.max_iv}% → {new_max_iv}%")
                if new_max_rv != self.max_rv:
                    log.info(f"   RV Limit: {self.max_rv}% → {new_max_rv}%")
                if new_max_spread != self.max_spread:
                    log.info(f"   Spread Limit: {self.max_spread}% → {new_max_spread}%")
                
                # Update values
                self.max_iv = new_max_iv
                self.max_rv = new_max_rv
                self.max_spread = new_max_spread
                
                # Re-check safety with new thresholds
                self._check_safety()
        except Exception as e:
            log.debug(f"Config reload failed: {e}")
    
    def _monitor_loop(self):
        """Background monitoring loop with instant config reload"""
        log.info("🔥 File watcher active: Config changes reload instantly!")
        
        while self._running:
            try:
                # Hot reload config before each check (instant detection)
                self._reload_config()
                self.update()
            except Exception as e:
                log.error(f"Volatility update failed: {e}")
            
            # Sleep in 1-second increments for instant config detection
            # This checks config file every second for changes
            for _ in range(self.check_interval):
                if not self._running:
                    break
                
                # Check for config changes every second (INSTANT!)
                try:
                    self._reload_config()
                except Exception:
                    pass
                
                time.sleep(1)
    
    def update(self) -> bool:
        """
        Fetch latest IV/RV and check safety conditions.
        
        Returns:
            bool: True if update successful
        """
        try:
            # Fetch IV and RV from Delta Exchange
            iv = self._fetch_iv()
            rv = self._fetch_rv()
            
            if iv is None or rv is None:
                log.warning("Failed to fetch IV/RV data")
                return False
            
            with self._lock:
                self.current_iv = iv
                self.current_rv = rv
                self.last_update = datetime.now(timezone.utc)
                
                # Check safety conditions
                old_safe = self.is_safe
                self.is_safe, self.violation_reason = self._check_safety(iv, rv)
                
                # Log status
                spread = iv - rv
                log.info(
                    f"Volatility: IV={iv:.1f}% RV={rv:.1f}% Spread={spread:+.1f}% "
                    f"Status={'✅ SAFE' if self.is_safe else '❌ UNSAFE'}"
                )
                
                # Persist status to file immediately after update
                self._persist_status()
                
                # Send notifications on state change
                if old_safe != self.is_safe:
                    self._send_notification()
            
            return True
            
        except Exception as e:
            log.error(f"Volatility update error: {e}")
            return False
    
    def _fetch_iv(self) -> Optional[float]:
        """
        Fetch Implied Volatility with Delta Exchange as PRIMARY source.
        
        Strategy: Delta Primary → Deribit Fallback → RV-based Estimate
        
        Delta Exchange (Primary):
        - Faster and more accurate for Indian market
        - Real-time options IV from /v2/tickers with quotes.bid_iv/ask_iv
        
        Deribit (Fallback):
        - Industry-standard DVOL (Deribit Volatility Index)
        - Same methodology as VIX for equities
        - Source: https://www.deribit.com/api/v2/public/get_volatility_index_data
        
        RV-based Estimate (Last Resort):
        - Estimates IV from RV (volatility risk premium)
        
        Returns:
            float: IV percentage (e.g., 43.98 for 43.98%)
        """
        try:
            # PRIMARY: Try Delta Exchange first
            log.info("Fetching IV from Delta Exchange (primary)...")
            delta_iv = self._fetch_iv_from_delta()
            if delta_iv is not None:
                log.info(f"✅ Using Delta Exchange IV: {delta_iv:.2f}%")
                return delta_iv
            else:
                log.warning("❌ Delta Exchange IV unavailable")
            
            # FALLBACK 1: Try Deribit
            log.warning("Trying Deribit as fallback...")
            deribit_iv = self._fetch_iv_from_deribit()
            if deribit_iv is not None:
                log.info(f"✅ Using Deribit IV: {deribit_iv:.2f}%")
                return deribit_iv
            else:
                log.warning("❌ Deribit IV unavailable")
            
            # FALLBACK 2: Estimate from RV
            log.warning("Both sources failed, estimating IV from RV...")
            rv = self._fetch_rv()
            if rv is None:
                return None
            
            # IV is typically 1.1x to 1.3x of RV (volatility risk premium)
            iv_estimate = rv * 1.15
            log.warning(f"⚠️  Using estimated IV: {iv_estimate:.2f}% (RV: {rv:.2f}%)")
            
            return iv_estimate
                
        except Exception as e:
            log.error(f"Failed to fetch IV: {e}")
            
            # Last resort fallback
            try:
                rv = self._fetch_rv()
                if rv:
                    return rv * 1.15
            except:
                pass
            
            return None
    
    def _fetch_iv_from_delta(self) -> Optional[float]:
        """
        Fetch Implied Volatility from Delta Exchange options (PRIMARY METHOD).
        
        Uses Delta Exchange India's options tickers with bid_iv/ask_iv data.
        Calculates weighted average IV for at-the-money (ATM) options.
        
        Returns:
            float: Approximate IV percentage (e.g., 43.5 for 43.5%)
        """
        try:
            from pathlib import Path
            
            # Load API credentials
            env_file = Path('secrets/api_keys.env')
            if not env_file.exists():
                log.warning("secrets/api_keys.env not found, skipping Delta IV fetch")
                return None
            
            from dotenv import load_dotenv
            load_dotenv(env_file, verbose=False)
            
            delta_base = "https://api.india.delta.exchange"
            
            # Step 1: Get current BTC price to find ATM options
            ticker_url = f"{delta_base}/v2/tickers/{self.symbol}"
            ticker_response = requests.get(ticker_url, timeout=10)
            
            if ticker_response.status_code != 200:
                log.warning(f"Failed to fetch ticker from Delta: HTTP {ticker_response.status_code}")
                return None
            
            ticker_data = ticker_response.json()
            if 'result' not in ticker_data or 'mark_price' not in ticker_data['result']:
                log.warning("Mark price not found in Delta ticker")
                return None
            
            spot_price = float(ticker_data['result']['mark_price'])
            
            # Step 2: Get all BTC option tickers with IV data
            tickers_url = f"{delta_base}/v2/tickers"
            params = {
                'underlying_asset_symbols': 'BTC',
                'contract_types': 'call_options,put_options'
            }
            tickers_response = requests.get(tickers_url, params=params, timeout=10)
            
            if tickers_response.status_code != 200:
                log.warning(f"Failed to fetch tickers from Delta: HTTP {tickers_response.status_code}")
                return None
            
            tickers_data = tickers_response.json()
            if 'result' not in tickers_data:
                log.warning("No tickers data from Delta")
                return None
            
            # Step 3: Find ATM options with IV data
            atm_options = []
            for ticker in tickers_data['result']:
                # Check if it has IV data
                quotes = ticker.get('quotes', {})
                bid_iv = quotes.get('bid_iv')
                ask_iv = quotes.get('ask_iv')
                
                if bid_iv is None and ask_iv is None:
                    continue
                
                # Use mark IV if available, otherwise use mid of bid/ask
                mark_iv = quotes.get('mark_iv')
                if mark_iv is None:
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
                
                # Find options within 10% of spot (ATM range)
                price_diff_pct = abs((strike - spot_price) / spot_price * 100)
                if price_diff_pct < 15:  # Wider range for more data
                    # Convert mark_iv to percentage if needed (already a decimal)
                    iv_value = mark_iv * 100  # Convert 0.43 to 43%
                    
                    atm_options.append({
                        'symbol': ticker.get('symbol', ''),
                        'strike': strike,
                        'iv': iv_value,
                        'diff': price_diff_pct
                    })
            
            if not atm_options:
                log.warning("No ATM options with IV found on Delta Exchange")
                return None
            
            # Step 4: Calculate weighted average (closer to ATM = higher weight)
            total_weight = 0
            weighted_iv = 0
            for opt in atm_options:
                # Weight: inverse of price difference (closer = higher weight)
                weight = 1 / (1 + opt['diff'])
                weighted_iv += opt['iv'] * weight
                total_weight += weight
            
            avg_iv = weighted_iv / total_weight if total_weight > 0 else None
            
            if avg_iv:
                log.info(f"Calculated IV from {len(atm_options)} Delta options (ATM range): {avg_iv:.2f}%")
                return avg_iv
            
            return None
                
        except Exception as e:
            log.error(f"Failed to fetch IV from Delta Exchange: {e}")
            import traceback
            log.debug(traceback.format_exc())
            return None
    
    def _fetch_iv_from_deribit(self) -> Optional[float]:
        """
        Fetch Implied Volatility from Deribit (FALLBACK METHOD).
        
        Deribit provides the industry-standard DVOL (Deribit Volatility Index)
        which is calculated from BTC options prices. This is the same methodology
        used by VIX for equities.
        
        Source: https://www.deribit.com/api/v2/public/get_volatility_index_data
        
        Returns:
            float: IV percentage (e.g., 43.98 for 43.98%)
        """
        try:
            from datetime import datetime, timedelta
            import time
            
            # Get last 24 hours of volatility data
            end_time = int(time.time() * 1000)  # milliseconds
            start_time = int((datetime.utcnow() - timedelta(days=1)).timestamp() * 1000)
            
            deribit_url = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
            params = {
                'currency': 'BTC',
                'resolution': '1d',  # Daily resolution
                'start_timestamp': start_time,
                'end_timestamp': end_time
            }
            
            response = requests.get(deribit_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'result' in data and 'data' in data['result'] and data['result']['data']:
                    # Get the latest IV value
                    # Data format: [timestamp, open, high, low, close]
                    latest_candle = data['result']['data'][-1]
                    iv = float(latest_candle[4])  # Close price (latest IV)
                    
                    log.info(f"Fetched IV from Deribit: {iv:.2f}%")
                    return iv
                else:
                    log.warning("No IV data in Deribit response")
                    return None
            else:
                log.warning(f"Deribit API returned HTTP {response.status_code}")
                return None
                
        except Exception as e:
            log.error(f"Failed to fetch IV from Deribit: {e}")
            return None
    
    def _fetch_rv(self) -> Optional[float]:
        """
        Fetch Realized Volatility (1h) from Delta Exchange volatility collector.
        
        Uses the same data source as the Volatility Regime chart for consistency.
        Fetches 1-hour realized volatility from the collector's database.
        
        Returns:
            float: RV percentage (e.g., 32.1 for 32.1%)
        """
        try:
            from bot.volatility.delta_volatility_collector import get_collector
            
            # Get collector instance
            collector = get_collector()
            
            # Fetch latest RV values (all timeframes)
            data = collector.get_latest_values()
            
            if not data or 'rv' not in data:
                log.warning("No RV data available from collector")
                return None
            
            # Use 1-hour RV for faster response to volatility changes
            rv_data = data['rv'].get('1h')
            if not rv_data or 'value' not in rv_data:
                log.warning("No 1h RV data available, trying fallback to 1d")
                # Fallback to 1d if 1h not available
                rv_data = data['rv'].get('1d')
                if not rv_data or 'value' not in rv_data:
                    log.warning("No RV data available in any timeframe")
                    return None
            
            rv_percent = float(rv_data['value'])
            log.info(f"Fetched RV from collector (1h): {rv_percent:.2f}%")
            return rv_percent
                
        except Exception as e:
            log.error(f"Failed to fetch RV from collector: {e}")
            return None
    
    def _check_safety(self, iv: float, rv: float) -> Tuple[bool, Optional[str]]:
        """
        Check if current volatility conditions are safe for trading.
        
        Args:
            iv: Implied Volatility (%)
            rv: Realized Volatility (%)
        
        Returns:
            Tuple of (is_safe, violation_reason)
        """
        # Check IV limit
        if iv > self.max_iv:
            return False, f"IV too high ({iv:.1f}% > {self.max_iv}%)"
        
        # Check RV limit
        if rv > self.max_rv:
            return False, f"RV too high ({rv:.1f}% > {self.max_rv}%)"
        
        # Check IV-RV spread
        spread = abs(iv - rv)
        if spread > self.max_spread:
            return False, f"IV-RV spread too large ({spread:.1f}% > {self.max_spread}%)"
        
        # Check if we should resume (with buffer to prevent flapping)
        if not self.is_safe and self.auto_resume:
            # Apply resume buffer (more conservative thresholds)
            if (iv < self.max_iv - self.resume_buffer and
                rv < self.max_rv - self.resume_buffer and
                spread < self.max_spread - self.resume_buffer):
                return True, None
        
        # All checks passed
        return True, None
    
    def _send_notification(self):
        """Send Telegram notification on safety status change"""
        # Prevent notification spam (max 1 per 5 minutes)
        if self.last_notification:
            elapsed = (datetime.utcnow() - self.last_notification).total_seconds()
            if elapsed < 300:  # 5 minutes
                return
        
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'tools'))
            from telepush import send_telegram_alert
            
            if self.is_safe:
                # Recovery notification
                message = (
                    f"✅ VOLATILITY NORMALIZED\n\n"
                    f"Trading RESUMED\n"
                    f"IV: {self.current_iv:.1f}%\n"
                    f"RV: {self.current_rv:.1f}%\n"
                    f"Spread: {abs(self.current_iv - self.current_rv):.1f}%\n\n"
                    f"Bot will resume placing orders."
                )
            else:
                # Violation notification
                spread = self.current_iv - self.current_rv
                message = (
                    f"🚨 VOLATILITY ALERT!\n\n"
                    f"Trading STOPPED\n"
                    f"Reason: {self.violation_reason}\n\n"
                    f"Current Conditions:\n"
                    f"• IV: {self.current_iv:.1f}% (max: {self.max_iv}%)\n"
                    f"• RV: {self.current_rv:.1f}% (max: {self.max_rv}%)\n"
                    f"• Spread: {spread:+.1f}% (max: ±{self.max_spread}%)\n\n"
                    f"Bot will not place new orders until volatility normalizes."
                )
            
            send_telegram_alert(message)
            self.last_notification = datetime.utcnow()
            log.info(f"Volatility notification sent: {'SAFE' if self.is_safe else 'UNSAFE'}")
            
        except Exception as e:
            log.error(f"Failed to send volatility notification: {e}")
    
    def can_trade(self) -> Tuple[bool, Optional[str]]:
        """
        Check if trading is allowed based on current volatility.
        
        🚨 EMERGENCY OVERRIDE: Can be disabled via WebUI for emergency situations.
        🔄 HOT RELOAD: Config values refreshed on every check for immediate effect
        
        Returns:
            Tuple of (can_trade, reason)
        """
        # 🚨 Check emergency override first
        try:
            from bot.safety.emergency_override import should_check_risk_management
            risk_mgmt_enabled = should_check_risk_management()
            
            if not risk_mgmt_enabled:
                log.warning("⚠️ RISK MANAGEMENT OVERRIDDEN: Volatility checks bypassed")
                return True, None  # Allow trading regardless of volatility
        except ImportError:
            # Fallback: always check if import fails
            pass
        
        if not self.enabled:
            return True, None
        
        # 🔄 Hot reload config for immediate effect when bot checks
        self._reload_config()
        
        with self._lock:
            if self.current_iv is None or self.current_rv is None:
                # 🔒 CRITICAL: No data yet - BLOCK trading until we have actual volatility data
                # Changed from fail-open to fail-closed for safety
                log.warning("⚠️ Volatility data not available yet - blocking trade")
                return False, "Volatility data not available (IV or RV is None)"
            
            if not self.is_safe:
                return False, self.violation_reason
            
            return True, None
    
    def _build_status_dict(self) -> Dict[str, Any]:
        """Build status dictionary (must be called with lock held)"""
        spread = None
        if self.current_iv is not None and self.current_rv is not None:
            spread = self.current_iv - self.current_rv
        
        return {
            'enabled': self.enabled,
            'iv': self.current_iv,
            'rv': self.current_rv,
            'spread': spread,
            'is_safe': self.is_safe,
            'violation_reason': self.violation_reason,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'thresholds': {
                'max_iv': self.max_iv,
                'max_rv': self.max_rv,
                'max_spread': self.max_spread
            },
            'config': {
                'check_interval': self.check_interval,
                'auto_resume': self.auto_resume,
                'resume_buffer': self.resume_buffer
            }
        }
    
    def _persist_status(self) -> None:
        """Persist current status to file (must be called with lock held)"""
        try:
            status = self._build_status_dict()
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
            
            # Also save to history for charts
            self._save_to_history(status)
        except Exception as e:
            log.debug(f"Failed to write volatility status file: {e}")
    
    def _save_to_history(self, status: Dict[str, Any]) -> None:
        """Save current volatility reading to history file for charts"""
        try:
            from pathlib import Path
            
            # Create reports directory if it doesn't exist
            reports_dir = Path('bot/reports')
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            history_file = reports_dir / 'volatility_history.json'
            
            # Load existing history
            history = []
            if history_file.exists():
                try:
                    with open(history_file, 'r') as f:
                        history = json.load(f)
                        if not isinstance(history, list):
                            history = []
                except:
                    history = []
            
            # Add new entry
            entry = {
                'rv': status.get('rv'),
                'iv': status.get('iv'),
                'zone': self._determine_zone(status.get('rv'), status.get('iv')),
                'timestamp': time.time(),
                'time': datetime.now(timezone.utc).isoformat()
            }
            history.append(entry)
            
            # Keep last 500 entries (about 42 hours at 5-min intervals)
            history = history[-500:]
            
            # Save updated history
            with open(history_file, 'w') as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            log.debug(f"Failed to save volatility history: {e}")
    
    def _determine_zone(self, rv: Optional[float], iv: Optional[float]) -> str:
        """Determine volatility zone based on RV and IV levels"""
        if rv is None:
            return "UNKNOWN"
        
        if rv < 20:
            return "LOW"
        elif rv < 30:
            return "NORMAL"
        elif rv < 40:
            return "ELEVATED"
        elif rv < 60:
            return "HIGH"
        else:
            return "EXTREME"
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current volatility status.
        If tracker is not running, loads from persisted status file.
        
        Returns:
            dict: Status information
        """
        with self._lock:
            # If not running, try to load from file
            if not self._running and os.path.exists(self.status_file):
                try:
                    with open(self.status_file, 'r') as f:
                        return json.load(f)
                except Exception:
                    pass  # Fall back to in-memory data
            
            return self._build_status_dict()


# Global singleton instance
_tracker: Optional[VolatilityTracker] = None


def get_volatility_tracker() -> VolatilityTracker:
    """Get or create global volatility tracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = VolatilityTracker()
    return _tracker

