"""
Stop-Loss and Take-Profit Manager for Options Trading
Handles SL/TP configuration, monitoring, and execution

Created: January 14, 2026
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class SLTPManager:
    """Manages stop-loss and take-profit for options positions"""
    
    def __init__(self, db_path: str = "data/options_sl_tp.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for SL/TP settings"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sl_tp_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                stop_loss_price REAL,
                stop_loss_pct REAL,
                take_profit_price REAL,
                take_profit_pct REAL,
                trailing_stop_enabled INTEGER DEFAULT 0,
                trailing_stop_pct REAL,
                trailing_stop_highest_price REAL,
                auto_execute INTEGER DEFAULT 1,
                alert_only INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                triggered_at TEXT,
                trigger_type TEXT,
                status TEXT DEFAULT 'active'
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sl_tp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                trigger_price REAL NOT NULL,
                position_size REAL NOT NULL,
                pnl REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                executed INTEGER DEFAULT 0,
                execution_order_id TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"SL/TP database initialized at {self.db_path}")
    
    def _get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def set_sl_tp(
        self,
        symbol: str,
        stop_loss_price: Optional[float] = None,
        stop_loss_pct: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        trailing_stop_enabled: bool = False,
        trailing_stop_pct: Optional[float] = None,
        auto_execute: bool = True,
        alert_only: bool = False
    ) -> Dict:
        """
        Set stop-loss and take-profit for a position
        
        Args:
            symbol: Option symbol (e.g., "C-BTC-95000-130126")
            stop_loss_price: Absolute price for stop-loss
            stop_loss_pct: Percentage loss to trigger stop-loss (negative number)
            take_profit_price: Absolute price for take-profit
            take_profit_pct: Percentage profit to trigger take-profit (positive number)
            trailing_stop_enabled: Enable trailing stop-loss
            trailing_stop_pct: Trailing stop percentage from highest price
            auto_execute: Automatically execute orders when triggered
            alert_only: Only send alerts, don't execute
            
        Returns:
            Dict with success status and settings
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Check if settings already exist
            cursor.execute("SELECT id FROM sl_tp_settings WHERE symbol = ?", (symbol,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing settings
                cursor.execute("""
                    UPDATE sl_tp_settings SET
                        stop_loss_price = ?,
                        stop_loss_pct = ?,
                        take_profit_price = ?,
                        take_profit_pct = ?,
                        trailing_stop_enabled = ?,
                        trailing_stop_pct = ?,
                        auto_execute = ?,
                        alert_only = ?,
                        updated_at = ?,
                        status = 'active'
                    WHERE symbol = ?
                """, (
                    stop_loss_price, stop_loss_pct, take_profit_price, take_profit_pct,
                    1 if trailing_stop_enabled else 0, trailing_stop_pct,
                    1 if auto_execute else 0, 1 if alert_only else 0,
                    now, symbol
                ))
                logger.info(f"Updated SL/TP for {symbol}")
            else:
                # Insert new settings
                cursor.execute("""
                    INSERT INTO sl_tp_settings (
                        symbol, stop_loss_price, stop_loss_pct, take_profit_price, take_profit_pct,
                        trailing_stop_enabled, trailing_stop_pct, auto_execute, alert_only,
                        created_at, updated_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """, (
                    symbol, stop_loss_price, stop_loss_pct, take_profit_price, take_profit_pct,
                    1 if trailing_stop_enabled else 0, trailing_stop_pct,
                    1 if auto_execute else 0, 1 if alert_only else 0,
                    now, now
                ))
                logger.info(f"Created SL/TP for {symbol}")
            
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "symbol": symbol,
                "settings": {
                    "stop_loss_price": stop_loss_price,
                    "stop_loss_pct": stop_loss_pct,
                    "take_profit_price": take_profit_price,
                    "take_profit_pct": take_profit_pct,
                    "trailing_stop_enabled": trailing_stop_enabled,
                    "trailing_stop_pct": trailing_stop_pct,
                    "auto_execute": auto_execute,
                    "alert_only": alert_only
                }
            }
            
        except Exception as e:
            logger.error(f"Error setting SL/TP for {symbol}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def get_sl_tp(self, symbol: str) -> Optional[Dict]:
        """Get SL/TP settings for a symbol"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM sl_tp_settings 
                WHERE symbol = ? AND status = 'active'
            """, (symbol,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            logger.error(f"Error getting SL/TP for {symbol}: {e}", exc_info=True)
            return None
    
    def get_all_active_sl_tp(self) -> List[Dict]:
        """Get all active SL/TP settings"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM sl_tp_settings WHERE status = 'active'
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting all SL/TP: {e}", exc_info=True)
            return []
    
    def remove_sl_tp(self, symbol: str) -> Dict:
        """Remove (deactivate) SL/TP settings for a symbol"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE sl_tp_settings 
                SET status = 'removed', updated_at = ?
                WHERE symbol = ?
            """, (datetime.now().isoformat(), symbol))
            
            affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if affected > 0:
                logger.info(f"Removed SL/TP for {symbol}")
                return {"success": True, "message": f"SL/TP removed for {symbol}"}
            else:
                return {"success": False, "error": "No SL/TP found for symbol"}
            
        except Exception as e:
            logger.error(f"Error removing SL/TP for {symbol}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def check_triggers(self, symbol: str, current_price: float, entry_price: float, pnl_pct: float) -> Optional[Dict]:
        """
        Check if SL/TP should trigger for a position
        
        Args:
            symbol: Option symbol
            current_price: Current mark/mid price
            entry_price: Entry price of position
            pnl_pct: Current P&L percentage
            
        Returns:
            Dict with trigger info if triggered, None otherwise
        """
        settings = self.get_sl_tp(symbol)
        if not settings:
            return None
        
        trigger_result = None
        
        # Check Stop-Loss by percentage
        if settings.get('stop_loss_pct') is not None:
            sl_pct = settings['stop_loss_pct']
            # stop_loss_pct is stored as negative (e.g., -20 for 20% loss)
            if pnl_pct <= sl_pct:
                trigger_result = {
                    "type": "stop_loss",
                    "reason": f"P&L ({pnl_pct:.1f}%) reached stop-loss ({sl_pct}%)",
                    "current_price": current_price,
                    "trigger_value": sl_pct
                }
        
        # Check Stop-Loss by price
        if not trigger_result and settings.get('stop_loss_price') is not None:
            sl_price = settings['stop_loss_price']
            if current_price <= sl_price:
                trigger_result = {
                    "type": "stop_loss",
                    "reason": f"Price (${current_price:.2f}) reached stop-loss (${sl_price:.2f})",
                    "current_price": current_price,
                    "trigger_value": sl_price
                }
        
        # Check Take-Profit by percentage
        if not trigger_result and settings.get('take_profit_pct') is not None:
            tp_pct = settings['take_profit_pct']
            if pnl_pct >= tp_pct:
                trigger_result = {
                    "type": "take_profit",
                    "reason": f"P&L ({pnl_pct:.1f}%) reached target ({tp_pct}%)",
                    "current_price": current_price,
                    "trigger_value": tp_pct
                }
        
        # Check Take-Profit by price
        if not trigger_result and settings.get('take_profit_price') is not None:
            tp_price = settings['take_profit_price']
            if current_price >= tp_price:
                trigger_result = {
                    "type": "take_profit",
                    "reason": f"Price (${current_price:.2f}) reached target (${tp_price:.2f})",
                    "current_price": current_price,
                    "trigger_value": tp_price
                }
        
        # Check Trailing Stop
        if not trigger_result and settings.get('trailing_stop_enabled') and settings.get('trailing_stop_pct'):
            trailing_pct = settings['trailing_stop_pct']
            highest_price = settings.get('trailing_stop_highest_price') or entry_price
            
            # Update highest price if current is higher
            if current_price > highest_price:
                self._update_trailing_highest(symbol, current_price)
                highest_price = current_price
            
            # Calculate trailing stop level
            trailing_stop_price = highest_price * (1 - trailing_pct / 100)
            
            if current_price <= trailing_stop_price:
                trigger_result = {
                    "type": "trailing_stop",
                    "reason": f"Price (${current_price:.2f}) hit trailing stop (${trailing_stop_price:.2f})",
                    "current_price": current_price,
                    "trigger_value": trailing_stop_price,
                    "highest_price": highest_price
                }
        
        if trigger_result:
            trigger_result["symbol"] = symbol
            trigger_result["settings"] = settings
            trigger_result["auto_execute"] = settings.get('auto_execute', True)
            trigger_result["alert_only"] = settings.get('alert_only', False)
        
        return trigger_result
    
    def _update_trailing_highest(self, symbol: str, new_highest: float):
        """Update trailing stop highest price"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE sl_tp_settings 
                SET trailing_stop_highest_price = ?, updated_at = ?
                WHERE symbol = ?
            """, (new_highest, datetime.now().isoformat(), symbol))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating trailing highest for {symbol}: {e}")
    
    def mark_triggered(self, symbol: str, trigger_type: str):
        """Mark SL/TP as triggered"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE sl_tp_settings 
                SET triggered_at = ?, trigger_type = ?, status = 'triggered', updated_at = ?
                WHERE symbol = ?
            """, (datetime.now().isoformat(), trigger_type, datetime.now().isoformat(), symbol))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error marking triggered for {symbol}: {e}")
    
    def add_history(
        self,
        symbol: str,
        trigger_type: str,
        trigger_price: float,
        position_size: float,
        pnl: float,
        pnl_pct: float,
        executed: bool = False,
        execution_order_id: Optional[str] = None
    ):
        """Add entry to SL/TP history"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO sl_tp_history (
                    symbol, trigger_type, trigger_price, position_size,
                    pnl, pnl_pct, executed, execution_order_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, trigger_type, trigger_price, position_size,
                pnl, pnl_pct, 1 if executed else 0, execution_order_id,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Added SL/TP history for {symbol}: {trigger_type}")
            
        except Exception as e:
            logger.error(f"Error adding history for {symbol}: {e}")
    
    def get_history(self, limit: int = 50, symbol: Optional[str] = None) -> List[Dict]:
        """Get SL/TP trigger history"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute("""
                    SELECT * FROM sl_tp_history 
                    WHERE symbol = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (symbol, limit))
            else:
                cursor.execute("""
                    SELECT * FROM sl_tp_history 
                    ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []


# Singleton instance
_sl_tp_manager = None

def get_sl_tp_manager() -> SLTPManager:
    """Get singleton SL/TP manager instance"""
    global _sl_tp_manager
    if _sl_tp_manager is None:
        _sl_tp_manager = SLTPManager()
    return _sl_tp_manager
