"""
Maximum Loss Manager for Options Trading
Handles per-strike and per-expiry max loss limits with auto square-off

Features:
- Per-strike and per-expiry max loss limits
- Real-time monitoring with configurable intervals
- Automatic position closing on breach
- Warning system at 80% threshold
- Rate limiting for Delta Exchange API
- Retry logic with exponential backoff
- Metrics tracking and reporting
- Configuration file support
- Thread-safe caching
- WebSocket support (optional)

Created: January 16, 2026
"""

import sqlite3
import json
import asyncio
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Singleton instance
_max_loss_manager = None
_max_loss_monitor = None

def get_max_loss_manager():
    """Get or create the singleton MaxLossManager instance"""
    global _max_loss_manager
    if _max_loss_manager is None:
        _max_loss_manager = MaxLossManager()
    return _max_loss_manager

def get_max_loss_monitor():
    """Get the singleton MaxLossMonitor instance"""
    global _max_loss_monitor
    return _max_loss_monitor


class MaxLossManager:
    """Manages maximum loss limits for options positions"""
    
    def __init__(self, db_path: str = "data/options_max_loss.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for max loss settings"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Per-strike max loss settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strike_max_loss (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                max_loss REAL NOT NULL,
                enabled INTEGER DEFAULT 1,
                triggered INTEGER DEFAULT 0,
                triggered_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Per-expiry max loss settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expiry_max_loss (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expiry_code TEXT NOT NULL UNIQUE,
                max_loss REAL NOT NULL,
                enabled INTEGER DEFAULT 1,
                triggered INTEGER DEFAULT 0,
                triggered_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # History of triggered max loss events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS max_loss_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                identifier TEXT NOT NULL,
                max_loss_limit REAL NOT NULL,
                actual_loss REAL NOT NULL,
                positions_closed TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Max Loss database initialized at {self.db_path}")
    
    def _get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _is_valid_option_symbol(self, symbol: str) -> bool:
        """
        Validate Delta Exchange option symbol format.
        Format: OptionType-UnderlyingAsset-StrikePrice-ExpiryDate(DDMMYY)
        Example: C-BTC-90000-310126
        """
        parts = symbol.split("-")
        if len(parts) != 4:
            return False
        
        option_type, underlying, strike, expiry = parts
        
        # Check option type (C = Call, P = Put)
        if option_type not in ["C", "P"]:
            return False
        
        # Check underlying asset (common ones on Delta Exchange)
        valid_underlyings = ["BTC", "ETH", "SOL", "BNB", "XRP", "MATIC", "DOGE", "ADA", "AVAX", "DOT"]
        if underlying not in valid_underlyings:
            logger.warning(f"Unusual underlying asset: {underlying}")
        
        # Check strike is numeric and reasonable
        try:
            strike_price = float(strike)
            if strike_price <= 0:
                return False
        except ValueError:
            return False
        
        # Check expiry format (DDMMYY) and validate date
        if len(expiry) != 6 or not expiry.isdigit():
            return False
        
        try:
            day = int(expiry[:2])
            month = int(expiry[2:4])
            year = 2000 + int(expiry[4:6])
            
            # Validate date is reasonable
            from datetime import datetime as dt
            expiry_date = dt(year, month, day)
            if expiry_date < dt.now():
                logger.warning(f"Expiry date {expiry} is in the past")
                return False
        except ValueError:
            logger.warning(f"Invalid expiry date format: {expiry}")
            return False
        
        return True
    
    # =========================================================================
    # PER-STRIKE MAX LOSS METHODS
    # =========================================================================
    
    def set_strike_max_loss(self, symbol: str, max_loss: float) -> Dict:
        """
        Set maximum loss limit for a specific strike/position.
        
        Args:
            symbol: Option symbol (e.g., "C-BTC-95000-170126")
            max_loss: Maximum loss in USD (positive number, e.g., 100 means $100 max loss)
            
        Returns:
            Dict with success status and settings
        """
        try:
            if max_loss <= 0:
                return {"success": False, "error": "Max loss must be positive"}
            
            if max_loss > 1000000:
                return {"success": False, "error": "Max loss seems unreasonably high. Please verify."}
            
            if not self._is_valid_option_symbol(symbol):
                logger.warning(f"Invalid option symbol format: {symbol} (continuing anyway)")
            
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO strike_max_loss (symbol, max_loss, enabled, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    max_loss = excluded.max_loss,
                    enabled = 1,
                    triggered = 0,
                    triggered_at = NULL,
                    updated_at = excluded.updated_at
            """, (symbol, max_loss, now, now))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Max loss set for {symbol}: ${max_loss}")
            return {
                "success": True,
                "symbol": symbol,
                "max_loss": max_loss,
                "enabled": True
            }
            
        except Exception as e:
            logger.error(f"Error setting strike max loss: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def get_strike_max_loss(self, symbol: str) -> Optional[Dict]:
        """Get max loss setting for a specific strike"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM strike_max_loss WHERE symbol = ? AND enabled = 1
            """, (symbol,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "symbol": row["symbol"],
                    "max_loss": row["max_loss"],
                    "enabled": bool(row["enabled"]),
                    "triggered": bool(row["triggered"]),
                    "triggered_at": row["triggered_at"]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting strike max loss: {e}")
            return None
    
    def get_all_strike_max_loss(self) -> List[Dict]:
        """Get all active strike max loss settings"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM strike_max_loss WHERE enabled = 1
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                "symbol": row["symbol"],
                "max_loss": row["max_loss"],
                "enabled": bool(row["enabled"]),
                "triggered": bool(row["triggered"]),
                "triggered_at": row["triggered_at"]
            } for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting all strike max loss: {e}")
            return []
    
    def remove_strike_max_loss(self, symbol: str) -> Dict:
        """Remove/disable max loss for a strike"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE strike_max_loss SET enabled = 0, updated_at = ?
                WHERE symbol = ?
            """, (datetime.now().isoformat(), symbol))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Max loss removed for {symbol}")
            return {"success": True, "symbol": symbol}
            
        except Exception as e:
            logger.error(f"Error removing strike max loss: {e}")
            return {"success": False, "error": str(e)}
    
    # =========================================================================
    # PER-EXPIRY MAX LOSS METHODS
    # =========================================================================
    
    def set_expiry_max_loss(self, expiry_code: str, max_loss: float) -> Dict:
        """
        Set maximum loss limit for all positions of a specific expiry.
        
        Args:
            expiry_code: Expiry date code (e.g., "170126" for 17/01/26)
            max_loss: Maximum combined loss for all positions of this expiry
            
        Returns:
            Dict with success status and settings
        """
        try:
            if max_loss <= 0:
                return {"success": False, "error": "Max loss must be positive"}
            
            if max_loss > 1000000:
                return {"success": False, "error": "Max loss seems unreasonably high. Please verify."}
            
            if len(expiry_code) != 6 or not expiry_code.isdigit():
                return {"success": False, "error": f"Invalid expiry format: {expiry_code} (expected DDMMYY)"}
            
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO expiry_max_loss (expiry_code, max_loss, enabled, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(expiry_code) DO UPDATE SET
                    max_loss = excluded.max_loss,
                    enabled = 1,
                    triggered = 0,
                    triggered_at = NULL,
                    updated_at = excluded.updated_at
            """, (expiry_code, max_loss, now, now))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Expiry max loss set for {expiry_code}: ${max_loss}")
            return {
                "success": True,
                "expiry_code": expiry_code,
                "max_loss": max_loss,
                "enabled": True
            }
            
        except Exception as e:
            logger.error(f"Error setting expiry max loss: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def get_expiry_max_loss(self, expiry_code: str) -> Optional[Dict]:
        """Get max loss setting for a specific expiry"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM expiry_max_loss WHERE expiry_code = ? AND enabled = 1
            """, (expiry_code,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "expiry_code": row["expiry_code"],
                    "max_loss": row["max_loss"],
                    "enabled": bool(row["enabled"]),
                    "triggered": bool(row["triggered"]),
                    "triggered_at": row["triggered_at"]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting expiry max loss: {e}")
            return None
    
    def get_all_expiry_max_loss(self) -> List[Dict]:
        """Get all active expiry max loss settings"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM expiry_max_loss WHERE enabled = 1
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                "expiry_code": row["expiry_code"],
                "max_loss": row["max_loss"],
                "enabled": bool(row["enabled"]),
                "triggered": bool(row["triggered"]),
                "triggered_at": row["triggered_at"]
            } for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting all expiry max loss: {e}")
            return []
    
    def remove_expiry_max_loss(self, expiry_code: str) -> Dict:
        """Remove/disable max loss for an expiry"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE expiry_max_loss SET enabled = 0, updated_at = ?
                WHERE expiry_code = ?
            """, (datetime.now().isoformat(), expiry_code))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Expiry max loss removed for {expiry_code}")
            return {"success": True, "expiry_code": expiry_code}
            
        except Exception as e:
            logger.error(f"Error removing expiry max loss: {e}")
            return {"success": False, "error": str(e)}
    
    # =========================================================================
    # TRIGGER RECORDING
    # =========================================================================
    
    def mark_strike_triggered(self, symbol: str, actual_loss: float, positions_closed: List[str]) -> None:
        """Mark a strike max loss as triggered and log to history"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Get the max loss limit before marking triggered
            cursor.execute("SELECT max_loss FROM strike_max_loss WHERE symbol = ?", (symbol,))
            row = cursor.fetchone()
            max_loss_limit = row["max_loss"] if row else 0
            
            # Mark as triggered
            cursor.execute("""
                UPDATE strike_max_loss SET triggered = 1, triggered_at = ?, updated_at = ?
                WHERE symbol = ?
            """, (now, now, symbol))
            
            # Log to history
            cursor.execute("""
                INSERT INTO max_loss_history (type, identifier, max_loss_limit, actual_loss, positions_closed, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("strike", symbol, max_loss_limit, actual_loss, json.dumps(positions_closed), now))
            
            conn.commit()
            conn.close()
            
            logger.warning(f"🛑 STRIKE MAX LOSS TRIGGERED: {symbol} lost ${actual_loss:.2f} (limit: ${max_loss_limit:.2f})")
            
        except Exception as e:
            logger.error(f"Error marking strike triggered: {e}")
    
    def mark_expiry_triggered(self, expiry_code: str, actual_loss: float, positions_closed: List[str]) -> None:
        """Mark an expiry max loss as triggered and log to history"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Get the max loss limit before marking triggered
            cursor.execute("SELECT max_loss FROM expiry_max_loss WHERE expiry_code = ?", (expiry_code,))
            row = cursor.fetchone()
            max_loss_limit = row["max_loss"] if row else 0
            
            # Mark as triggered
            cursor.execute("""
                UPDATE expiry_max_loss SET triggered = 1, triggered_at = ?, updated_at = ?
                WHERE expiry_code = ?
            """, (now, now, expiry_code))
            
            # Log to history
            cursor.execute("""
                INSERT INTO max_loss_history (type, identifier, max_loss_limit, actual_loss, positions_closed, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("expiry", expiry_code, max_loss_limit, actual_loss, json.dumps(positions_closed), now))
            
            conn.commit()
            conn.close()
            
            logger.warning(f"🛑 EXPIRY MAX LOSS TRIGGERED: {expiry_code} lost ${actual_loss:.2f} (limit: ${max_loss_limit:.2f})")
            
        except Exception as e:
            logger.error(f"Error marking expiry triggered: {e}")
    
    def get_history(self, limit: int = 50, loss_type: str = None) -> List[Dict]:
        """Get max loss trigger history"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if loss_type:
                cursor.execute("""
                    SELECT * FROM max_loss_history 
                    WHERE type = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (loss_type, limit))
            else:
                cursor.execute("""
                    SELECT * FROM max_loss_history 
                    ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                "type": row["type"],
                "identifier": row["identifier"],
                "max_loss_limit": row["max_loss_limit"],
                "actual_loss": row["actual_loss"],
                "positions_closed": json.loads(row["positions_closed"]) if row["positions_closed"] else [],
                "timestamp": row["timestamp"]
            } for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting max loss history: {e}")
            return []


class MaxLossMonitor:
    """
    Real-time monitor that checks positions against max loss limits.
    
    Supports two modes:
    1. REST API polling (default): Fetches positions every N seconds
    2. WebSocket streaming (optional): Real-time position updates
    
    Features:
    - Automatic position closing on max loss breach
    - Warning system at configurable threshold (default 80%)
    - API rate limiting for Delta Exchange
    - Retry logic with exponential backoff
    - Thread-safe position caching
    - Comprehensive metrics tracking
    - Configuration file support
    """
    
    def __init__(self, api_client, manager: MaxLossManager, check_interval: float = 5.0, config_path: str = None):
        self.api_client = api_client
        self.manager = manager
        
        # Load configuration if provided
        config = {}
        if config_path and Path(config_path).exists():
            try:
                with open(config_path) as f:
                    config = json.load(f).get("max_loss_monitor", {})
                logger.info(f"📝 Loaded max loss config from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        
        self.check_interval = config.get("check_interval", check_interval)  # Check every 5 seconds
        self._running = False
        self._thread = None
        self._last_check = 0
        self._check_count = 0
        self._positions_cache = None
        self._cache_time = 0
        self._cache_ttl = config.get("cache_ttl", 3.0)  # Short cache for frequent checks
        self._cache_lock = threading.Lock()  # Thread-safe cache access
        self.test_mode = config.get("test_mode", False)
        self._test_positions = []
        self.warning_threshold = config.get("warning_threshold", 0.8)  # Warn when 80% of max loss
        self._warned_symbols = set()  # Track which symbols we've warned about
        
        # API rate limiting (Delta Exchange: 10,000 units per 5min window)
        self._api_call_count = 0
        self._api_call_window_start = time.time()
        self._max_calls_per_minute = config.get("max_calls_per_minute", 60)  # Conservative limit for safety
        
        # Retry configuration
        self._max_retries = config.get("max_retries", 3)
        self._retry_backoff_base = config.get("retry_backoff_base", 2)
        
        # Metrics tracking
        self._metrics = {
            "total_checks": 0,
            "total_breaches": 0,
            "total_warnings": 0,
            "positions_closed": 0,
            "api_errors": 0,
            "last_breach_time": None,
            "failed_closes": 0,
            "retried_closes": 0
        }
    
    def start(self):
        """Start the monitoring thread"""
        if self._running:
            logger.warning("MaxLossMonitor already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"✅ MaxLossMonitor started (interval: {self.check_interval}s, warning at {self.warning_threshold*100}%)")
    
    def stop(self):
        """Stop the monitoring thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        
        # Clear cache and reset state
        with self._cache_lock:
            self._positions_cache = None
            self._cache_time = 0
        self._warned_symbols.clear()
        
        logger.info("⏹️ MaxLossMonitor stopped")
    
    def get_status(self) -> Dict:
        """Get monitor status"""
        return {
            "running": self._running,
            "last_check": self._last_check,
            "check_count": self._check_count,
            "check_interval": self.check_interval,
            "warning_threshold": self.warning_threshold,
            "mode": "real_time"
        }
    
    def get_metrics(self) -> Dict:
        """Get monitoring metrics and statistics"""
        return {
            "metrics": self._metrics.copy(),
            "status": self.get_status(),
            "cache_info": {
                "cached": self._positions_cache is not None,
                "cache_age": time.time() - self._cache_time if self._cache_time > 0 else None
            }
        }
    
    def check_now(self) -> Dict:
        """
        Manually trigger a max loss check (on-demand).
        This is the recommended way to check max loss limits.
        """
        try:
            self._check_max_loss()
            self._check_count += 1
            self._last_check = time.time()
            
            return {
                "success": True,
                "message": "Max loss check completed",
                "check_count": self._check_count,
                "last_check": self._last_check
            }
        except Exception as e:
            logger.error(f"Error in manual check: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _monitor_loop(self):
        """Main monitoring loop - runs continuously in background"""
        logger.info("🔄 Max loss monitor loop started")
        
        while self._running:
            try:
                # Only check if there are active max loss limits
                strike_limits = self.manager.get_all_strike_max_loss()
                expiry_limits = self.manager.get_all_expiry_max_loss()
                
                if strike_limits or expiry_limits:
                    self._check_max_loss()
                    self._check_count += 1
                
                self._last_check = time.time()
            except Exception as e:
                logger.error(f"Error in max loss monitor loop: {e}", exc_info=True)
            
            time.sleep(self.check_interval)
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within API rate limits (Delta Exchange)"""
        now = time.time()
        
        # Reset counter every minute
        if now - self._api_call_window_start > 60:
            self._api_call_count = 0
            self._api_call_window_start = now
        
        if self._api_call_count >= self._max_calls_per_minute:
            logger.warning("⚠️ API rate limit reached, skipping check")
            return False
        
        self._api_call_count += 1
        return True
    
    def _check_max_loss(self):
        """Check all positions against max loss limits"""
        try:
            # Increment check counter
            self._metrics["total_checks"] += 1
            
            # Check API rate limits before making calls
            if not self._check_rate_limit():
                return
            
            # Use test mode positions if enabled
            if self.test_mode and self._test_positions:
                positions = self._test_positions
                logger.info(f"🧪 TEST MODE: Using {len(positions)} mock positions")
            else:
                # Use cached positions if available and fresh (thread-safe)
                now = time.time()
                with self._cache_lock:
                    if self._positions_cache and (now - self._cache_time) < self._cache_ttl:
                        positions = self._positions_cache.copy()
                        logger.debug(f"Using cached positions: {len(positions)} positions")
                    else:
                        positions = None
                
                if positions is None:
                    # Fetch positions from Delta Exchange with proper async handling
                    try:
                        # Proper async event loop management in thread
                        try:
                            loop = asyncio.get_running_loop()
                            should_close_loop = False
                        except RuntimeError:
                            # No running loop, create one
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            should_close_loop = True
                        
                        try:
                            positions = loop.run_until_complete(
                                self.api_client.get_all_positions_with_options()
                            )
                            logger.info(f"✅ Fetched {len(positions)} positions from Delta Exchange")
                            
                            # Log position symbols for debugging
                            if positions:
                                losing_positions = [p for p in positions if p.get('unrealized_pnl', 0) < 0]
                                if losing_positions:
                                    logger.debug(f"Found {len(losing_positions)} losing positions")
                            
                            # Update cache with lock
                            with self._cache_lock:
                                self._positions_cache = positions
                                self._cache_time = now
                        finally:
                            if should_close_loop:
                                loop.close()
                            
                    except Exception as e:
                        logger.error(f"❌ Error fetching positions from Delta Exchange: {e}")
                        self._metrics["api_errors"] += 1
                        return
            
            if not positions:
                logger.debug(f"No positions found to check against max loss limits")
                return
            
            # Check per-strike max loss
            strike_limits = self.manager.get_all_strike_max_loss()
            strike_limits_map = {s["symbol"]: s for s in strike_limits}
            
            if strike_limits:
                logger.debug(f"🔍 Checking {len(positions)} positions against {len(strike_limits)} max loss limits")
            
            for pos in positions:
                symbol = pos.get("product_symbol")
                pnl = pos.get("unrealized_pnl", 0)
                
                # ONLY check positions with NEGATIVE PnL (losses)
                if symbol in strike_limits_map and pnl < 0:
                    limit = strike_limits_map[symbol]
                    max_loss = limit["max_loss"]
                    actual_loss = abs(pnl)  # Use absolute value of negative PnL
                    loss_percentage = (actual_loss / max_loss) if max_loss > 0 else 0
                    
                    # Log at info level only if approaching or exceeding limit
                    if loss_percentage >= self.warning_threshold:
                        logger.info(f"📊 {symbol}: Loss ${actual_loss:.4f} / ${max_loss:.2f} ({loss_percentage*100:.1f}%)")
                    else:
                        logger.debug(f"📊 {symbol}: Loss ${actual_loss:.4f} / ${max_loss:.2f} ({loss_percentage*100:.1f}%)")
                    
                    # WARNING: Approaching max loss threshold (80%)
                    if loss_percentage >= self.warning_threshold and loss_percentage < 1.0:
                        if symbol not in self._warned_symbols:
                            logger.warning(f"⚠️ WARNING: {symbol} at {loss_percentage*100:.1f}% of max loss (${actual_loss:.4f} / ${max_loss:.2f})")
                            self._warned_symbols.add(symbol)
                            self._metrics["total_warnings"] += 1
                    
                    # CRITICAL: Max loss EXCEEDED - auto close position
                    if actual_loss >= max_loss and not limit["triggered"]:
                        logger.error(f"🛑 MAX LOSS BREACH: {symbol} loss ${actual_loss:.4f} >= limit ${max_loss:.2f} - AUTO CLOSING")
                        success = self._close_position_with_retry(symbol, actual_loss, "strike")
                        if success:
                            self._metrics["total_breaches"] += 1
                            self._metrics["last_breach_time"] = datetime.now().isoformat()
                        self._warned_symbols.discard(symbol)  # Remove from warned set
                    
                    # Reset warning if loss decreases below threshold
                    elif loss_percentage < self.warning_threshold and symbol in self._warned_symbols:
                        logger.info(f"✅ {symbol} loss decreased to {loss_percentage*100:.1f}% - below warning threshold")
                        self._warned_symbols.discard(symbol)
                
                # Skip positions with positive PnL (profits)
                elif pnl >= 0 and symbol in strike_limits_map:
                    logger.debug(f"ℹ️ {symbol}: In profit ${pnl:.4f} - skipping max loss check")
            
            # Check per-expiry max loss
            expiry_limits = self.manager.get_all_expiry_max_loss()
            if expiry_limits:
                # Group positions by expiry
                expiry_pnl = {}  # expiry_code -> total_pnl
                expiry_positions = {}  # expiry_code -> [positions]
                
                for pos in positions:
                    symbol = pos.get("product_symbol", "")
                    parts = symbol.split("-")
                    if len(parts) >= 4:
                        expiry_code = parts[3]
                        pnl = pos.get("unrealized_pnl", 0)
                        
                        if expiry_code not in expiry_pnl:
                            expiry_pnl[expiry_code] = 0
                            expiry_positions[expiry_code] = []
                        
                        expiry_pnl[expiry_code] += pnl
                        expiry_positions[expiry_code].append(pos)
                
                # Check each expiry against limits
                expiry_limits_map = {e["expiry_code"]: e for e in expiry_limits}
                
                for expiry_code, total_pnl in expiry_pnl.items():
                    if expiry_code in expiry_limits_map and total_pnl < 0:
                        limit = expiry_limits_map[expiry_code]
                        max_loss = limit["max_loss"]
                        actual_loss = abs(total_pnl)
                        
                        if actual_loss >= max_loss and not limit["triggered"]:
                            logger.warning(f"🛑 EXPIRY MAX LOSS BREACH: {expiry_code} loss ${actual_loss:.2f} >= limit ${max_loss:.2f}")
                            self._close_expiry_positions(expiry_code, expiry_positions[expiry_code], actual_loss)
                            
        except Exception as e:
            logger.error(f"Error checking max loss: {e}", exc_info=True)
    
    def _close_position_with_retry(self, symbol: str, actual_loss: float, loss_type: str) -> bool:
        """Close position with retry logic and exponential backoff"""
        for attempt in range(self._max_retries):
            try:
                self._close_position(symbol, actual_loss, loss_type)
                return True
            except Exception as e:
                if attempt < self._max_retries - 1:
                    wait_time = self._retry_backoff_base ** attempt  # Exponential backoff
                    logger.warning(f"⚠️ Retry {attempt+1}/{self._max_retries} for {symbol} in {wait_time}s: {e}")
                    self._metrics["retried_closes"] += 1
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ Failed to close {symbol} after {self._max_retries} attempts: {e}")
                    self._metrics["failed_closes"] += 1
                    return False
        return False
    
    def _close_position(self, symbol: str, actual_loss: float, loss_type: str):
        """Close a single position due to max loss breach - Delta Exchange API"""
        try:
            # TEST MODE: Only log, don't actually close
            if self.test_mode:
                logger.warning(f"🧪 TEST MODE: Would close {symbol} - loss ${actual_loss:.4f}")
                self.manager.mark_strike_triggered(symbol, actual_loss, [symbol])
                return
            
            logger.info(f"🔴 CLOSING {symbol} (max loss breach: ${actual_loss:.4f})")
            
            # Proper async event loop management
            try:
                loop = asyncio.get_running_loop()
                should_close_loop = False
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                should_close_loop = True
            
            try:
                from webui.backend.routes.options.options_control import place_smart_order, ORDER_TYPE_MARKET_ONLY
                
                # Get position details to know size and side
                positions = loop.run_until_complete(
                    self.api_client.get_all_positions_with_options()
                )
                
                pos = next((p for p in positions if p.get("product_symbol") == symbol), None)
                if not pos:
                    logger.error(f"❌ Position not found: {symbol}")
                    return
                
                # Verify position still has size (not already closed)
                current_size = abs(pos.get("size", 0))
                if current_size == 0:
                    logger.warning(f"⚠️ Position {symbol} already closed (size=0)")
                    self.manager.mark_strike_triggered(symbol, actual_loss, [symbol])
                    return
                
                # Delta Exchange: size must be absolute value
                size = current_size
                
                # Delta Exchange: side is opposite of position
                # Long position (size > 0) -> sell to close
                # Short position (size < 0) -> buy to close
                is_long = pos.get("size", 0) > 0
                close_side = "sell" if is_long else "buy"
                
                logger.info(f"📊 Position details: {close_side} {size} contracts (reduce_only=True)")
                
                # Place market close order with reduce_only=True
                # This ensures we only close existing position, never open new one
                result = loop.run_until_complete(
                    place_smart_order(
                        self.api_client, 
                        symbol, 
                        size, 
                        close_side, 
                        ORDER_TYPE_MARKET_ONLY, 
                        reduce_only=True  # Critical: prevents opening new positions
                    )
                )
                
                logger.info(f"✅ Successfully closed {symbol}: {result}")
                self.manager.mark_strike_triggered(symbol, actual_loss, [symbol])
                self._metrics["positions_closed"] += 1
                
            finally:
                if should_close_loop:
                    loop.close()
                
        except Exception as e:
            logger.error(f"❌ Error closing position for max loss: {e}", exc_info=True)
    
    def _close_expiry_positions(self, expiry_code: str, positions: List[Dict], actual_loss: float):
        """Close all positions of an expiry due to max loss breach"""
        try:
            # Proper async event loop management
            try:
                loop = asyncio.get_running_loop()
                should_close_loop = False
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                should_close_loop = True
            
            try:
                from webui.backend.routes.options.options_control import place_smart_order, ORDER_TYPE_MARKET_ONLY
                
                closed_positions = []
                
                for pos in positions:
                    symbol = pos.get("product_symbol")
                    size = abs(pos.get("size", 0))
                    is_long = pos.get("size", 0) > 0
                    close_side = "sell" if is_long else "buy"
                    
                    # TEST MODE: Only log, don't actually close
                    if self.test_mode:
                        logger.warning(f"🧪 TEST MODE: Would close {symbol} (expiry {expiry_code}): {close_side} {size}")
                        closed_positions.append(symbol)
                        continue
                    
                    logger.info(f"🔴 CLOSING {symbol} (expiry {expiry_code} max loss): {close_side} {size}")
                    
                    try:
                        result = loop.run_until_complete(
                            place_smart_order(self.api_client, symbol, size, close_side, ORDER_TYPE_MARKET_ONLY, reduce_only=True)
                        )
                        closed_positions.append(symbol)
                        logger.info(f"✅ Closed {symbol}: {result}")
                    except Exception as e:
                        logger.error(f"Failed to close {symbol}: {e}")
                
                # Mark expiry as triggered
                self.manager.mark_expiry_triggered(expiry_code, actual_loss, closed_positions)
                
            finally:
                if should_close_loop:
                    loop.close()
                
        except Exception as e:
            logger.error(f"Error closing expiry positions for max loss: {e}", exc_info=True)


def init_max_loss_monitoring(api_client, manager: MaxLossManager = None, auto_start: bool = True, config_path: str = None) -> MaxLossMonitor:
    """
    Initialize and optionally start the max loss monitor.
    
    Args:
        api_client: Delta Exchange API client
        manager: MaxLossManager instance (creates new if None)
        auto_start: Start monitoring immediately
        config_path: Path to JSON config file
    
    Returns:
        MaxLossMonitor instance
    """
    global _max_loss_monitor
    
    if manager is None:
        manager = get_max_loss_manager()
    
    _max_loss_monitor = MaxLossMonitor(api_client, manager, config_path=config_path)
    
    if auto_start:
        _max_loss_monitor.start()
    
    return _max_loss_monitor


# =============================================================================
# WebSocket Integration (Optional - Future Enhancement)
# =============================================================================

class MaxLossWebSocketMonitor:
    """
    WebSocket-based monitor for real-time position updates.
    More efficient than REST API polling for high-frequency monitoring.
    
    Usage:
        ws_monitor = MaxLossWebSocketMonitor(api_client, manager)
        await ws_monitor.connect()
        await ws_monitor.start_monitoring()
    
    Note: Requires websockets library: pip install websockets
    """
    
    def __init__(self, api_client, manager: MaxLossManager, ws_url: str = "wss://socket.india.delta.exchange"):
        self.api_client = api_client
        self.manager = manager
        self.ws_url = ws_url
        self._ws = None
        self._running = False
        self._positions = {}
        logger.info(f"📡 WebSocket monitor initialized (url: {ws_url})")
    
    async def connect(self):
        """Connect to Delta Exchange WebSocket"""
        try:
            import websockets
            self._ws = await websockets.connect(self.ws_url)
            logger.info(f"✅ Connected to {self.ws_url}")
            
            # Subscribe to positions channel
            subscribe_msg = {
                "type": "subscribe",
                "payload": {
                    "channels": [{"name": "positions"}]
                }
            }
            await self._ws.send(json.dumps(subscribe_msg))
            logger.info("📬 Subscribed to positions channel")
            
        except ImportError:
            logger.error("❌ websockets library not installed. Run: pip install websockets")
            raise
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            raise
    
    async def start_monitoring(self):
        """Start monitoring positions via WebSocket"""
        self._running = True
        logger.info("🔄 WebSocket monitoring started")
        
        try:
            while self._running:
                message = await self._ws.recv()
                data = json.loads(message)
                
                # Handle position updates
                if data.get("type") == "positions":
                    positions = data.get("payload", {}).get("positions", [])
                    await self._check_positions(positions)
                    
        except Exception as e:
            logger.error(f"❌ WebSocket monitoring error: {e}")
            self._running = False
    
    async def _check_positions(self, positions: List[Dict]):
        """Check positions against max loss limits (WebSocket version)"""
        try:
            # Get active max loss limits
            strike_limits = self.manager.get_all_strike_max_loss()
            expiry_limits = self.manager.get_all_expiry_max_loss()
            
            if not strike_limits and not expiry_limits:
                return  # No limits configured
            
            # Check per-strike max loss
            strike_limits_map = {s["symbol"]: s for s in strike_limits}
            
            for pos in positions:
                symbol = pos.get("product_symbol")
                pnl = pos.get("unrealized_pnl", 0)
                
                # Only check positions with NEGATIVE PnL (losses)
                if symbol in strike_limits_map and pnl < 0:
                    limit = strike_limits_map[symbol]
                    max_loss = limit["max_loss"]
                    actual_loss = abs(pnl)
                    
                    # Check if max loss exceeded
                    if actual_loss >= max_loss and not limit["triggered"]:
                        logger.error(f"🛑 WS: MAX LOSS BREACH: {symbol} loss ${actual_loss:.4f} >= limit ${max_loss:.2f}")
                        await self._close_position_ws(symbol, actual_loss)
            
            # Check per-expiry max loss
            if expiry_limits:
                expiry_pnl = {}
                expiry_positions_map = {}
                
                for pos in positions:
                    symbol = pos.get("product_symbol", "")
                    parts = symbol.split("-")
                    if len(parts) >= 4:
                        expiry_code = parts[3]
                        pnl = pos.get("unrealized_pnl", 0)
                        
                        if expiry_code not in expiry_pnl:
                            expiry_pnl[expiry_code] = 0
                            expiry_positions_map[expiry_code] = []
                        
                        expiry_pnl[expiry_code] += pnl
                        expiry_positions_map[expiry_code].append(pos)
                
                expiry_limits_map = {e["expiry_code"]: e for e in expiry_limits}
                
                for expiry_code, total_pnl in expiry_pnl.items():
                    if expiry_code in expiry_limits_map and total_pnl < 0:
                        limit = expiry_limits_map[expiry_code]
                        max_loss = limit["max_loss"]
                        actual_loss = abs(total_pnl)
                        
                        if actual_loss >= max_loss and not limit["triggered"]:
                            logger.warning(f"🛑 WS: EXPIRY MAX LOSS BREACH: {expiry_code} loss ${actual_loss:.2f} >= limit ${max_loss:.2f}")
                            await self._close_expiry_positions_ws(expiry_code, expiry_positions_map[expiry_code], actual_loss)
                            
        except Exception as e:
            logger.error(f"Error checking positions (WebSocket): {e}", exc_info=True)
    
    async def _close_position_ws(self, symbol: str, actual_loss: float):
        """Close a single position via WebSocket monitor"""
        try:
            from webui.backend.routes.options.options_control import place_smart_order, ORDER_TYPE_MARKET_ONLY
            
            # Get position details
            loop = asyncio.get_event_loop()
            positions = await self.api_client.get_all_positions_with_options()
            
            pos = next((p for p in positions if p.get("product_symbol") == symbol), None)
            if not pos:
                logger.error(f"❌ WS: Position not found: {symbol}")
                return
            
            size = abs(pos.get("size", 0))
            if size == 0:
                logger.warning(f"⚠️ WS: Position {symbol} already closed")
                return
            
            is_long = pos.get("size", 0) > 0
            close_side = "sell" if is_long else "buy"
            
            logger.info(f"🔴 WS: Closing {symbol}: {close_side} {size} contracts")
            
            result = await place_smart_order(
                self.api_client,
                symbol,
                size,
                close_side,
                ORDER_TYPE_MARKET_ONLY,
                reduce_only=True
            )
            
            logger.info(f"✅ WS: Closed {symbol}: {result}")
            self.manager.mark_strike_triggered(symbol, actual_loss, [symbol])
            
        except Exception as e:
            logger.error(f"❌ WS: Error closing {symbol}: {e}", exc_info=True)
    
    async def _close_expiry_positions_ws(self, expiry_code: str, positions: List[Dict], actual_loss: float):
        """Close all positions of an expiry via WebSocket monitor"""
        try:
            from webui.backend.routes.options.options_control import place_smart_order, ORDER_TYPE_MARKET_ONLY
            
            closed_positions = []
            
            for pos in positions:
                symbol = pos.get("product_symbol")
                size = abs(pos.get("size", 0))
                is_long = pos.get("size", 0) > 0
                close_side = "sell" if is_long else "buy"
                
                logger.info(f"🔴 WS: Closing {symbol} (expiry {expiry_code}): {close_side} {size}")
                
                try:
                    result = await place_smart_order(
                        self.api_client,
                        symbol,
                        size,
                        close_side,
                        ORDER_TYPE_MARKET_ONLY,
                        reduce_only=True
                    )
                    closed_positions.append(symbol)
                    logger.info(f"✅ WS: Closed {symbol}: {result}")
                except Exception as e:
                    logger.error(f"Failed to close {symbol}: {e}")
            
            self.manager.mark_expiry_triggered(expiry_code, actual_loss, closed_positions)
            
        except Exception as e:
            logger.error(f"Error closing expiry positions (WebSocket): {e}", exc_info=True)
    
    async def stop(self):
        """Stop monitoring and close WebSocket connection"""
        self._running = False
        if self._ws:
            await self._ws.close()
        logger.info("⏹️ WebSocket monitoring stopped")


# =============================================================================
# Utility Functions
# =============================================================================

def create_sample_config(output_path: str = "max_loss_config.json"):
    """Create a sample configuration file with all options"""
    config = {
        "max_loss_monitor": {
            "check_interval": 5.0,
            "warning_threshold": 0.8,
            "cache_ttl": 3.0,
            "max_calls_per_minute": 60,
            "test_mode": False,
            "max_retries": 3,
            "retry_backoff_base": 2,
            "websocket": {
                "enabled": False,
                "url": "wss://socket.india.delta.exchange",
                "reconnect_delay": 5,
                "ping_interval": 30
            },
            "notifications": {
                "enabled": False,
                "channels": ["log"],
                "webhook_url": None,
                "telegram_bot_token": None,
                "telegram_chat_id": None
            }
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"📝 Created sample config at {output_path}")
    return output_path
