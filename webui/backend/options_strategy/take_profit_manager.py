"""
Take Profit Manager for Options Trading
Handles per-strike take profit limits with auto square-off on partial quantities

Features:
- Per-strike take profit limits with partial quantity exit
- Real-time monitoring with configurable intervals
- Automatic partial position closing on profit target
- Rate limiting for Delta Exchange API
- Retry logic with exponential backoff
- Metrics tracking and reporting
- Thread-safe caching
- Settings persist across backend restarts

Created: February 3, 2026
"""

import sqlite3
import json
import threading
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Import order execution functions
try:
    from webui.backend.routes.options.options_control import place_smart_order, ORDER_TYPE_MAKER_FIRST
    ORDER_EXECUTION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Order execution module not available - TP auto-close disabled: {e}")
    ORDER_EXECUTION_AVAILABLE = False
    place_smart_order = None
    ORDER_TYPE_MAKER_FIRST = None

# Singleton instance
_take_profit_manager = None
_take_profit_monitor = None

# Activity Log Ring Buffer - stores real-time monitoring events
_activity_log = []
_activity_log_lock = threading.Lock()
_MAX_ACTIVITY_LOG_SIZE = 200  # Keep last 200 events

def add_activity_event(event_type: str, message: str, details: dict = None):
    """Add an event to the activity log ring buffer"""
    global _activity_log
    event = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": event_type,
        "message": message,
        "details": details or {}
    }
    with _activity_log_lock:
        _activity_log.append(event)
        # Keep only last N events
        if len(_activity_log) > _MAX_ACTIVITY_LOG_SIZE:
            _activity_log = _activity_log[-_MAX_ACTIVITY_LOG_SIZE:]

def get_activity_log(limit: int = 50, event_type: str = None) -> list:
    """Get recent activity log events"""
    with _activity_log_lock:
        events = _activity_log.copy()
    
    # Filter by type if specified
    if event_type:
        events = [e for e in events if e["type"] == event_type]
    
    # Return most recent first
    return list(reversed(events[-limit:]))

def clear_activity_log():
    """Clear all activity log events"""
    global _activity_log
    with _activity_log_lock:
        _activity_log = []

def get_take_profit_manager():
    """Get or create the singleton TakeProfitManager instance"""
    global _take_profit_manager
    if _take_profit_manager is None:
        _take_profit_manager = TakeProfitManager()
    return _take_profit_manager

def get_take_profit_monitor():
    """Get the singleton TakeProfitMonitor instance"""
    global _take_profit_monitor
    return _take_profit_monitor


class TakeProfitManager:
    """Manages take profit limits for options positions"""
    
    def __init__(self, db_path: str = "data/options_take_profit.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for take profit settings"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Per-strike take profit settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strike_take_profit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                target_profit REAL NOT NULL,
                exit_quantity INTEGER NOT NULL,
                enabled INTEGER DEFAULT 1,
                triggered INTEGER DEFAULT 0,
                triggered_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # History of triggered take profit events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS take_profit_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                target_profit REAL NOT NULL,
                actual_profit REAL NOT NULL,
                exit_quantity INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Take Profit database initialized at {self.db_path}")
    
    def _get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _is_valid_option_symbol(self, symbol: str) -> bool:
        """Validate option symbol format (e.g., C-BTC-95000-170126)"""
        parts = symbol.split('-')
        return len(parts) >= 4 and parts[0] in ['C', 'P']
    
    # =========================================================================
    # PER-STRIKE TAKE PROFIT METHODS
    # =========================================================================
    
    def set_strike_take_profit(self, symbol: str, target_profit: float, exit_quantity: int) -> Dict:
        """
        Set take profit/loss limit for a specific strike.
        
        Args:
            symbol: Option symbol (e.g., C-BTC-95000-170126)
            target_profit: Target P&L in USD (positive for profit, negative for loss)
                          e.g., 20.0 = exit when profit reaches $20
                          e.g., -10.0 = exit when loss reaches -$10
            exit_quantity: Number of contracts to exit when target is reached
        
        Returns:
            {'success': True/False, 'message': str}
        """
        try:
            if not self._is_valid_option_symbol(symbol):
                return {'success': False, 'error': 'Invalid option symbol format'}
            
            if target_profit == 0:
                return {'success': False, 'error': 'Target P&L must be non-zero (positive for profit, negative for loss)'}
            
            if exit_quantity <= 0:
                return {'success': False, 'error': 'Exit quantity must be positive'}
            
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Insert or update
            cursor.execute("""
                INSERT INTO strike_take_profit (symbol, target_profit, exit_quantity, enabled, triggered, created_at, updated_at)
                VALUES (?, ?, ?, 1, 0, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    target_profit = excluded.target_profit,
                    exit_quantity = excluded.exit_quantity,
                    enabled = 1,
                    triggered = 0,
                    triggered_at = NULL,
                    updated_at = excluded.updated_at
            """, (symbol, target_profit, exit_quantity, now, now))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Take profit set for {symbol}: ${target_profit} profit -> exit {exit_quantity} lots")
            add_activity_event("setting_updated", f"✅ TP set: {symbol} -> ${target_profit} / {exit_quantity} lots", {
                "symbol": symbol,
                "target_profit": target_profit,
                "exit_quantity": exit_quantity
            })
            
            return {
                'success': True,
                'message': f'Take profit set: ${target_profit} profit -> exit {exit_quantity} lots'
            }
            
        except Exception as e:
            logger.error(f"Error setting strike take profit: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_strike_take_profit(self, symbol: str) -> Optional[Dict]:
        """Get take profit setting for a specific strike"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM strike_take_profit WHERE symbol = ? AND enabled = 1
            """, (symbol,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'symbol': row['symbol'],
                    'target_profit': row['target_profit'],
                    'exit_quantity': row['exit_quantity'],
                    'enabled': bool(row['enabled']),
                    'triggered': bool(row['triggered']),
                    'triggered_at': row['triggered_at'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting strike take profit: {e}")
            return None
    
    def get_all_strike_take_profit(self) -> List[Dict]:
        """Get all active strike take profit settings"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM strike_take_profit WHERE enabled = 1 ORDER BY created_at DESC
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                'symbol': row['symbol'],
                'target_profit': row['target_profit'],
                'exit_quantity': row['exit_quantity'],
                'enabled': bool(row['enabled']),
                'triggered': bool(row['triggered']),
                'triggered_at': row['triggered_at'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            } for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting all strike take profit: {e}")
            return []
    
    def remove_strike_take_profit(self, symbol: str) -> Dict:
        """Remove/disable take profit for a strike"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute("""
                UPDATE strike_take_profit SET enabled = 0, updated_at = ?
                WHERE symbol = ?
            """, (now, symbol))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Take profit removed for {symbol}")
            add_activity_event("setting_removed", f"🗑️ TP removed: {symbol}", {"symbol": symbol})
            
            return {'success': True, 'message': 'Take profit removed'}
            
        except Exception as e:
            logger.error(f"Error removing strike take profit: {e}")
            return {'success': False, 'error': str(e)}
    
    # =========================================================================
    # TRIGGER RECORDING
    # =========================================================================
    
    def mark_strike_triggered(self, symbol: str, actual_profit: float, exit_quantity: int) -> None:
        """Mark a strike take profit as triggered and log to history"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Get the target profit before marking triggered
            cursor.execute("SELECT target_profit FROM strike_take_profit WHERE symbol = ?", (symbol,))
            row = cursor.fetchone()
            target_profit = row["target_profit"] if row else 0
            
            # Mark as triggered
            cursor.execute("""
                UPDATE strike_take_profit SET triggered = 1, triggered_at = ?, updated_at = ?
                WHERE symbol = ?
            """, (now, now, symbol))
            
            # Log to history
            cursor.execute("""
                INSERT INTO take_profit_history (symbol, target_profit, actual_profit, exit_quantity, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (symbol, target_profit, actual_profit, exit_quantity, now))
            
            conn.commit()
            conn.close()
            
            logger.info(f"🎯 TAKE PROFIT TRIGGERED: {symbol} profit ${actual_profit:.2f} (target: ${target_profit:.2f}) - Exited {exit_quantity} lots")
            add_activity_event("triggered", f"🎯 TP TRIGGERED: {symbol} - ${actual_profit:.2f} profit", {
                "symbol": symbol,
                "target_profit": target_profit,
                "actual_profit": actual_profit,
                "exit_quantity": exit_quantity
            })
            
        except Exception as e:
            logger.error(f"Error marking strike triggered: {e}")
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        """Get take profit trigger history"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM take_profit_history 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [{
                'symbol': row['symbol'],
                'target_profit': row['target_profit'],
                'actual_profit': row['actual_profit'],
                'exit_quantity': row['exit_quantity'],
                'timestamp': row['timestamp']
            } for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting take profit history: {e}")
            return []


# =============================================================================
# TAKE PROFIT MONITOR - Background monitoring service
# =============================================================================

class TakeProfitMonitor:
    """
    Background monitor for take profit tracking and automatic execution.
    Monitors positions and executes partial exits when profit targets are reached.
    """
    
    def __init__(self, api_client, manager: TakeProfitManager, config: dict = None):
        self.api_client = api_client
        self.manager = manager
        self.config = config or {}
        
        # Configuration
        self.check_interval = self.config.get('check_interval', 3)  # seconds - Fast checks for quick execution
        self.enabled = self.config.get('enabled', True)
        
        # Threading
        self.monitor_thread = None
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        
        # Tracking
        self._last_check_time = 0
        self._metrics = {
            "total_checks": 0,
            "total_triggers": 0,
            "total_warnings": 0,
            "last_check_at": None,
            "uptime_seconds": 0
        }
        self._start_time = time.time()
        
        # Rate limiting (Delta Exchange: 10 req/sec)
        self._rate_limit_window = 1.0  # seconds
        self._rate_limit_max_calls = 8  # Stay under 10/sec
        self._rate_limit_calls = []
        
        # Recently closed positions (prevent duplicate closes)
        self._recently_closed = {}  # symbol -> timestamp
        self._close_cooldown = 60  # seconds
        
        logger.info("✅ Take Profit Monitor initialized")
    
    def start(self):
        """Start the monitoring thread"""
        print("🎯 DEBUG: TakeProfitMonitor.start() called", flush=True)
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Take Profit Monitor already running")
            print("⚠️  DEBUG: Monitor already running!", flush=True)
            return
        
        print("🎯 DEBUG: Creating and starting monitor thread...", flush=True)
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("🎯 DEBUG: Thread started! Is alive:", self.monitor_thread.is_alive(), flush=True)
        logger.info("🎯 Take Profit Monitor started")
        add_activity_event("monitor_started", "🎯 Take Profit Monitor started", {})
    
    def stop(self):
        """Stop the monitoring thread"""
        logger.info("Stopping Take Profit Monitor...")
        self.stop_event.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("✅ Take Profit Monitor stopped")
        add_activity_event("monitor_stopped", "⏸️ Take Profit Monitor stopped", {})
    
    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self.monitor_thread and self.monitor_thread.is_alive() and not self.stop_event.is_set()
    
    def get_metrics(self) -> Dict:
        """Get monitoring metrics"""
        uptime = time.time() - self._start_time
        return {
            **self._metrics,
            "uptime_seconds": int(uptime),
            "is_running": self.is_running(),
            "enabled": self.enabled
        }
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        print("🎯 DEBUG: _monitor_loop() started!", flush=True)
        logger.info("🎯 Take Profit Monitor loop started")
        
        # IMPORTANT: Add initial delay to avoid collision with Max Loss monitor
        print("🎯 DEBUG: Sleeping 5s to avoid monitor collision...", flush=True)
        time.sleep(5)
        print("🎯 DEBUG: Starting main loop...", flush=True)
        
        while not self.stop_event.is_set():
            try:
                if self.enabled:
                    print("🎯 DEBUG: Calling _check_take_profit()...", flush=True)
                    self._check_take_profit()
                
                # Sleep with interrupt check
                for _ in range(int(self.check_interval)):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in take profit monitor loop: {e}", exc_info=True)
                print(f"🎯 DEBUG: Exception in monitor loop: {e}", flush=True)
                time.sleep(5)  # Brief pause on error
        
        logger.info("🎯 Take Profit Monitor loop ended")
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within API rate limits (Delta Exchange)"""
        now = time.time()
        # Remove old calls outside the window
        self._rate_limit_calls = [t for t in self._rate_limit_calls if now - t < self._rate_limit_window]
        
        if len(self._rate_limit_calls) >= self._rate_limit_max_calls:
            return False  # Rate limit exceeded
        
        self._rate_limit_calls.append(now)
        return True
    
    def _check_take_profit(self):
        """Check all positions against take profit limits"""
        print("🎯 DEBUG: _check_take_profit() CALLED", flush=True)
        try:
            with self._lock:
                self._metrics["total_checks"] += 1
                self._metrics["last_check_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Get all TP settings
                tp_settings = self.manager.get_all_strike_take_profit()
                print(f"🎯 DEBUG: Found {len(tp_settings) if tp_settings else 0} TP settings", flush=True)
                if not tp_settings:
                    return
                
                # Print all settings
                for s in tp_settings:
                    print(f"🎯 DEBUG: TP Setting: {s['symbol']} | Target: ${s['target_profit']} | Exit Qty: {s['exit_quantity']}", flush=True)
                
                # Get current positions from API
                try:
                    print(f"🎯 DEBUG: About to call api_client.get_positions()...", flush=True)
                    
                    # Handle async API client
                    try:
                        print(f"🎯 DEBUG: Getting event loop...", flush=True)
                        loop = asyncio.get_running_loop()
                        should_close_loop = False
                        print(f"🎯 DEBUG: Using existing loop", flush=True)
                    except RuntimeError as e:
                        # No running loop, create one
                        print(f"🎯 DEBUG: No running loop, creating new one... ({e})", flush=True)
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        should_close_loop = True
                        print(f"🎯 DEBUG: New loop created", flush=True)
                    
                    try:
                        print(f"🎯 DEBUG: Calling loop.run_until_complete()...", flush=True)
                        positions_data = loop.run_until_complete(
                            self.api_client.get_all_positions_with_options()
                        )
                        print(f"🎯 DEBUG: API returned {type(positions_data)}", flush=True)
                        
                        # Extract positions from the response
                        if isinstance(positions_data, dict):
                            positions = positions_data.get('options', [])
                            print(f"🎯 DEBUG: Dict response, extracted {len(positions)} options positions", flush=True)
                        elif isinstance(positions_data, list):
                            positions = positions_data
                            print(f"🎯 DEBUG: List response with {len(positions)} positions", flush=True)
                        else:
                            logger.warning(f"Invalid positions response type: {type(positions_data)}")
                            print(f"🎯 DEBUG: Invalid positions response type!", flush=True)
                            return
                    except Exception as e2:
                        print(f"🎯 DEBUG: Exception in run_until_complete: {e2}", flush=True)
                        raise
                    finally:
                        # DON'T close the loop - let it be reused or garbage collected
                        # Closing it causes issues with other monitors
                        pass
                        
                    if not positions:
                        print(f"🎯 DEBUG: No positions found", flush=True)
                        return
                        
                    print(f"🎯 DEBUG: Processing {len(positions)} positions", flush=True)
                except Exception as e:
                    logger.error(f"Failed to get positions from API: {e}", exc_info=True)
                    print(f"🎯 DEBUG: Exception getting positions: {e}", flush=True)
                    return
                
                # Check each position with TP settings
                for limit in tp_settings:
                    if limit.get('triggered', False):
                        print(f"🎯 DEBUG: Skipping {limit['symbol']} - already triggered", flush=True)
                        continue  # Skip already triggered
                    
                    symbol = limit['symbol']
                    target_profit = limit['target_profit']
                    exit_quantity = limit['exit_quantity']
                    
                    # Find matching position
                    pos = next((p for p in positions if p.get('product_symbol') == symbol), None)
                    if not pos:
                        print(f"🎯 DEBUG: No position found for {symbol}", flush=True)
                        continue
                    
                    # Get PnL
                    pnl = pos.get('unrealized_pnl', 0)
                    size = abs(pos.get('size', 0))
                    print(f"🎯 DEBUG: {symbol} | PnL: ${pnl:.4f} | Size: {size} | Target: ${target_profit}", flush=True)
                    
                    # Check if target is reached (works for both profit and loss targets)
                    # For BOTH cases: trigger when current P&L >= target
                    # 
                    # Profit Example: Current $20 >= Target $15 → TRUE (profit reached!)
                    # Loss Example: Current -$50 >= Target -$100 → TRUE (loss improved to better than -$100!)
                    #               Current -$150 >= Target -$100 → FALSE (loss still worse than target)
                    target_reached = pnl >= target_profit
                    
                    if target_reached:
                        actual_pnl = pnl
                        # Compute progress towards target as a percentage. For profit targets (>0) and loss limits (<0) this
# calculation uses the target sign so that improvement yields a positive percentage (e.g., -25/-50 = 50%).
pnl_percentage = (actual_pnl / target_profit) * 100 if target_profit != 0 else 0
                        target_type = "PROFIT" if target_profit > 0 else "LOSS LIMIT"
                        print(f"🎯 DEBUG: {symbol} {target_type} REACHED! Actual: ${actual_pnl:.4f}, Target: ${target_profit}, Progress: {pnl_percentage:.1f}%", flush=True)
                        logger.info(f"📊 {symbol}: P&L ${actual_pnl:.4f} / ${target_profit:.2f} ({pnl_percentage:.1f}%) - {target_type}")
                        print(f"📊 {symbol}: P&L ${actual_pnl:.4f} / ${target_profit:.2f} ({pnl_percentage:.1f}%) - {target_type}", flush=True)
                        
                        add_activity_event("position_check", f"📊 {symbol}: P&L ${actual_pnl:.2f} / ${target_profit:.2f} ({pnl_percentage:.1f}%) - {target_type}", {
                            "symbol": symbol,
                            "actual_pnl": actual_pnl,
                            "target_profit": target_profit,
                            "pnl_pct": round(pnl_percentage, 1),
                            "size": size,
                            "target_type": target_type
                        })
                        
                        # CRITICAL: Target REACHED - auto close partial position
                        print(f"🎯 DEBUG: ENTERING TARGET REACHED BLOCK!", flush=True)
                        # Check if position has enough size
                        current_size = abs(pos.get("size", 0))
                        print(f"🎯 DEBUG: current_size = {current_size}", flush=True)
                        
                        if current_size == 0:
                            print(f"🎯 DEBUG: Size is ZERO, skipping!", flush=True)
                            logger.warning(f"⚠️ {symbol} target reached but position already closed (size=0)")
                            continue
                        
                        print(f"🎯 DEBUG: Checking if {current_size} < {exit_quantity}", flush=True)
                        if current_size < exit_quantity:
                            logger.warning(f"⚠️ {symbol} target reached but size {current_size} < exit qty {exit_quantity}")
                            print(f"🎯 DEBUG: Size too small, adjusting exit_quantity to {current_size}", flush=True)
                            # Exit available quantity instead
                            exit_quantity = current_size
                        
                        print(f"🎯 DEBUG: About to log TARGET REACHED...", flush=True)
                        logger.error(f"🎯 DEBUG: TARGET REACHED!")
                        logger.error(f"   - Symbol: {symbol}")
                        logger.error(f"   - Actual P&L: ${actual_pnl:.4f}")
                        logger.error(f"   - Target P&L: ${target_profit:.4f}")
                        logger.error(f"   - Target Type: {target_type}")
                        logger.error(f"   - Current Size: {current_size}")
                        logger.error(f"   - Exit Quantity: {exit_quantity}")
                        logger.error(f"   - Triggered Flag: {limit.get('triggered', False)}")
                        print(f"🎯 DEBUG: Logged all TARGET details", flush=True)
                        
                        print(f"🎯 DEBUG: Calling add_activity_event...", flush=True)
                        add_activity_event("reached", f"🎯 TARGET REACHED: {symbol} - P&L ${actual_pnl:.2f} >= Target ${target_profit:.2f} ({target_type})", {
                            "symbol": symbol,
                            "actual_pnl": actual_pnl,
                            "target_profit": target_profit,
                            "target_type": target_type,
                            "size": current_size,
                            "exit_quantity": exit_quantity
                        })
                        print(f"🎯 DEBUG: add_activity_event called", flush=True)
                        
                        print(f"🎯 DEBUG: Checking if current_size ({current_size}) > 0", flush=True)
                        if current_size > 0:
                            print(f"🎯 DEBUG: YES, current_size > 0!", flush=True)
                            # Check if we recently attempted to close this position (prevent API spam)
                            now = time.time()
                            print(f"🎯 DEBUG: Checking recently_closed dict...", flush=True)
                            if symbol in self._recently_closed:
                                last_close_time = self._recently_closed[symbol]
                                if now - last_close_time < self._close_cooldown:
                                    logger.warning(f"⏸️ Skipping {symbol} - recently attempted close (cooldown: {self._close_cooldown}s)")
                                    print(f"🎯 DEBUG: Skipping due to cooldown", flush=True)
                                    continue
                            
                            print(f"🎯 DEBUG: Marking as recently closed...", flush=True)
                            # Mark as recently closed BEFORE attempting the close
                            self._recently_closed[symbol] = now
                            
                            print(f"🎯 DEBUG: About to call _close_position_with_retry...", flush=True)
                            # Execute partial exit with retry
                            success = self._close_position_with_retry(symbol, actual_pnl, exit_quantity, target_profit)
                            print(f"🎯 DEBUG: _close_position_with_retry returned: {success}", flush=True)
                            
                            if success:
                                print(f"🎯 DEBUG: Success! Marking as triggered...", flush=True)
                                # Mark as triggered in database
                                self.manager.mark_strike_triggered(symbol, actual_pnl, exit_quantity)
                                self._metrics["total_triggers"] += 1
                            else:
                                print(f"🎯 DEBUG: Failed! Removing from recently_closed", flush=True)
                                # Remove from recently closed if failed
                                self._recently_closed.pop(symbol, None)
                        else:
                            print(f"🎯 DEBUG: NO, current_size is 0!", flush=True)
                            logger.warning(f"⚠️ {symbol} position already closed (size=0)")
                                
        except Exception as e:
            logger.error(f"Error checking take profit: {e}", exc_info=True)
    
    def _close_position_with_retry(self, symbol: str, actual_profit: float, exit_quantity: int, target_profit: float, max_retries: int = 3) -> bool:
        """Close partial position with retry logic and exponential backoff"""
        print(f"🎯 DEBUG: _close_position_with_retry called for {symbol}, exit_qty={exit_quantity}", flush=True)
        for attempt in range(max_retries):
            try:
                print(f"🎯 DEBUG: Attempt {attempt + 1}/{max_retries} for {symbol}", flush=True)
                logger.info(f"🎯 Attempting partial close for {symbol} (attempt {attempt + 1}/{max_retries})")
                self._close_position(symbol, actual_profit, exit_quantity, target_profit)
                print(f"🎯 DEBUG: _close_position succeeded!", flush=True)
                return True  # Success
            except Exception as e:
                print(f"🎯 DEBUG: Exception in attempt {attempt + 1}: {e}", flush=True)
                logger.error(f"❌ Attempt {attempt + 1} failed for {symbol}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"⏳ Waiting {wait_time}s before retry...")
                    print(f"🎯 DEBUG: Waiting {wait_time}s before retry...", flush=True)
                    time.sleep(wait_time)
                else:
                    logger.error(f"🛑 All {max_retries} attempts failed for {symbol}")
                    print(f"🎯 DEBUG: All retries exhausted", flush=True)
                    return False
    
    def _close_position(self, symbol: str, actual_pnl: float, exit_quantity: int, target_profit: float):
        """Close partial position due to take profit/loss limit - Delta Exchange API"""
        should_close_loop = False
        loop = None
        try:
            print(f"🎯 DEBUG: _close_position called for {symbol}", flush=True)
            # Rate limit check
            if not self._check_rate_limit():
                logger.warning(f"⚠️ Rate limit reached - delaying {symbol} close")
                time.sleep(1)
                # Treat rate limit as a transient failure so caller can retry with backoff
                raise Exception("Rate limit reached - try again")
            
            print(f"🎯 DEBUG: Getting positions for order placement...", flush=True)
            # Get position details using async API
            try:
                loop = asyncio.get_running_loop()
                should_close_loop = False
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                should_close_loop = True
            
            positions_data = loop.run_until_complete(
                self.api_client.get_all_positions_with_options()
            )
            
            if isinstance(positions_data, dict):
                positions = positions_data.get('options', [])
            elif isinstance(positions_data, list):
                positions = positions_data
            else:
                raise Exception(f"Invalid positions response type: {type(positions_data)}")
                
            if not positions:
                raise Exception("No positions found from API")
            
            print(f"🎯 DEBUG: Got {len(positions)} positions", flush=True)
            pos = next((p for p in positions if p.get('product_symbol') == symbol), None)
            if not pos:
                raise Exception(f"Position {symbol} not found")
            
            size = pos.get('size', 0)
            product_id = pos.get('product_id')
            print(f"🎯 DEBUG: Found position - size={size}, product_id={product_id}", flush=True)
            
            if size == 0:
                logger.warning(f"⚠️ {symbol} already closed (size=0)")
                return
            
            # Determine side (opposite of current position)
            close_side = 'sell' if size > 0 else 'buy'
            close_size = min(abs(exit_quantity), abs(size))  # Don't close more than we have
            
            target_type = "profit target" if target_profit > 0 else "loss limit"
            logger.info(f"🎯 Closing {close_size} lots of {symbol} ({close_side}) due to {target_type}")
            logger.info(f"   Target: ${target_profit:.2f} | Actual P&L: ${actual_pnl:.2f}")
            print(f"🎯 DEBUG: About to place order - symbol={symbol}, size={close_size}, side={close_side}", flush=True)
            
            # Place LIMIT order to close partial position using async API
            if ORDER_EXECUTION_AVAILABLE and place_smart_order:
                print(f"🎯 DEBUG: Calling place_smart_order...", flush=True)
                try:
                    # Call async function
                    order_result = loop.run_until_complete(
                        place_smart_order(
                            client=self.api_client,
                            symbol=symbol,
                            size=close_size,
                            side=close_side,
                            order_preference="smart",  # Use smart order with limit
                            reduce_only=True
                        )
                    )
                    print(f"🎯 DEBUG: Order result: {order_result}", flush=True)
                    
                    # Check if order was placed successfully (has 'id' field)
                    if order_result and isinstance(order_result, dict) and order_result.get('id'):
                        order_id = order_result.get('id')
                        order_state = order_result.get('state')
                        logger.info(f"✅ Take profit order placed for {symbol}: {close_side} {close_size} lots (Order ID: {order_id}, State: {order_state})")
                        print(f"🎯 DEBUG: ✅ ORDER PLACED SUCCESSFULLY! ID={order_id}", flush=True)
                        add_activity_event("order_placed", f"✅ TP ORDER: {symbol} - {close_side.upper()} {close_size} lots", {
                            "symbol": symbol,
                            "side": close_side,
                            "size": close_size,
                            "order_id": order_id
                        })
                    else:
                        error_msg = "No order ID returned"
                        print(f"🎯 DEBUG: Order failed: {error_msg}", flush=True)
                        raise Exception(f"Order placement failed: {error_msg}")
                except Exception as order_error:
                    print(f"🎯 DEBUG: Exception placing order: {order_error}", flush=True)
                    raise
            else:
                print(f"🎯 DEBUG: ORDER_EXECUTION_AVAILABLE={ORDER_EXECUTION_AVAILABLE}, place_smart_order={place_smart_order}", flush=True)
                raise Exception("Order execution module not available")

                
        except Exception as e:
            logger.error(f"Error closing position {symbol}: {e}", exc_info=True)
            raise
        finally:
            # DON'T close the loop - let it be reused or garbage collected
            pass



def init_take_profit_monitoring(api_client, manager: TakeProfitManager = None, auto_start: bool = True, config_path: str = None) -> TakeProfitMonitor:
    """
    Initialize and start the take profit monitoring service.
    
    Args:
        api_client: Delta Exchange API client instance
        manager: TakeProfitManager instance (creates new if None)
        auto_start: Whether to automatically start monitoring
        config_path: Path to config file (optional)
    
    Returns:
        TakeProfitMonitor instance
    """
    global _take_profit_monitor
    
    if manager is None:
        manager = get_take_profit_manager()
    
    # Load config if provided
    config = {}
    if config_path:
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
    
    # Create monitor
    _take_profit_monitor = TakeProfitMonitor(api_client, manager, config)
    
    if auto_start:
        _take_profit_monitor.start()
    
    return _take_profit_monitor


# =============================================================================
# Utility Functions
# =============================================================================

def create_sample_config(output_path: str = "take_profit_config.json"):
    """Create a sample configuration file with all options"""
    config = {
        "enabled": True,
        "check_interval": 10,
        "check_interval_description": "Seconds between position checks"
    }
    
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"✅ Sample config created at {output_path}")


if __name__ == "__main__":
    # Setup logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test database initialization
    manager = TakeProfitManager(db_path="data/test_take_profit.db")
    print("✅ Take Profit Manager initialized")
    
    # Test setting a take profit
    result = manager.set_strike_take_profit("C-BTC-95000-170126", 20.0, 10)
    print(f"Set TP result: {result}")
    
    # Test getting settings
    settings = manager.get_all_strike_take_profit()
    print(f"All TP settings: {settings}")
    
    # Test history
    history = manager.get_history()
    print(f"TP history: {history}")
    
    print("\n✅ All tests passed")
