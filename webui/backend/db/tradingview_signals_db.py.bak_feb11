"""
TradingView Signals Database
Store and manage TradingView webhook signals
"""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import uuid

# Database path
DB_PATH = Path(__file__).parent.parent / 'data' / 'tradingview_signals.db'

def get_db_connection():
    """Get database connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_tradingview_signals_db():
    """Initialize TradingView signals database schema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create signals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tradingview_signals (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            price REAL NOT NULL,
            strategy TEXT,
            timeframe TEXT,
            message TEXT,
            metadata TEXT,
            source_ip TEXT,
            created_at TEXT NOT NULL,
            processed BOOLEAN DEFAULT 0,
            processed_at TEXT,
            notes TEXT
        )
    ''')
    
    # Create indexes for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_signals_symbol 
        ON tradingview_signals(symbol)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_signals_action 
        ON tradingview_signals(action)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_signals_created_at 
        ON tradingview_signals(created_at DESC)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_signals_strategy 
        ON tradingview_signals(strategy)
    ''')
    
    # Create signal execution history table (for tracking when signals are acted upon)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_executions (
            id TEXT PRIMARY KEY,
            signal_id TEXT NOT NULL,
            executed_at TEXT NOT NULL,
            execution_type TEXT,
            execution_price REAL,
            quantity REAL,
            order_id TEXT,
            status TEXT,
            error_message TEXT,
            FOREIGN KEY (signal_id) REFERENCES tradingview_signals(id)
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_executions_signal_id 
        ON signal_executions(signal_id)
    ''')
    
    conn.commit()
    conn.close()


class TradingViewSignalsDB:
    """Database operations for TradingView signals."""
    
    @staticmethod
    def create_signal(
        symbol: str,
        action: str,
        price: float,
        strategy: str = None,
        timeframe: str = None,
        message: str = None,
        metadata: dict = None,
        source_ip: str = None
    ) -> dict:
        """Create a new TradingView signal."""
        signal_id = str(uuid.uuid4())[:12]
        now = datetime.utcnow().isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tradingview_signals (
                id, symbol, action, price, strategy, timeframe, 
                message, metadata, source_ip, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal_id,
            symbol.upper(),
            action.lower(),
            price,
            strategy,
            timeframe,
            message,
            json.dumps(metadata) if metadata else None,
            source_ip,
            now
        ))
        
        conn.commit()
        
        # Fetch and return the created signal
        cursor.execute('SELECT * FROM tradingview_signals WHERE id = ?', (signal_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    @staticmethod
    def get_signals(
        symbol: str = None,
        action: str = None,
        strategy: str = None,
        timeframe: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[dict]:
        """Get signals with optional filters."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM tradingview_signals WHERE 1=1'
        params = []
        
        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol.upper())
        
        if action:
            query += ' AND action = ?'
            params.append(action.lower())
        
        if strategy:
            query += ' AND strategy = ?'
            params.append(strategy)
        
        if timeframe:
            query += ' AND timeframe = ?'
            params.append(timeframe)
        
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    @staticmethod
    def get_signal(signal_id: str) -> Optional[dict]:
        """Get a specific signal by ID."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM tradingview_signals WHERE id = ?', (signal_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    @staticmethod
    def count_signals(
        symbol: str = None,
        action: str = None,
        strategy: str = None,
        timeframe: str = None
    ) -> int:
        """Count signals with optional filters."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = 'SELECT COUNT(*) as count FROM tradingview_signals WHERE 1=1'
        params = []
        
        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol.upper())
        
        if action:
            query += ' AND action = ?'
            params.append(action.lower())
        
        if strategy:
            query += ' AND strategy = ?'
            params.append(strategy)
        
        if timeframe:
            query += ' AND timeframe = ?'
            params.append(timeframe)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()
        
        return result['count'] if result else 0
    
    @staticmethod
    def mark_as_processed(signal_id: str, notes: str = None) -> bool:
        """Mark a signal as processed."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE tradingview_signals 
            SET processed = 1, processed_at = ?, notes = ?
            WHERE id = ?
        ''', (datetime.utcnow().isoformat(), notes, signal_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    @staticmethod
    def delete_signal(signal_id: str) -> bool:
        """Delete a signal."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM tradingview_signals WHERE id = ?', (signal_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    @staticmethod
    def get_signal_stats() -> dict:
        """Get statistics about signals."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total signals
        cursor.execute('SELECT COUNT(*) as total FROM tradingview_signals')
        total = cursor.fetchone()['total']
        
        # Signals by action
        cursor.execute('''
            SELECT action, COUNT(*) as count 
            FROM tradingview_signals 
            GROUP BY action
        ''')
        by_action = {row['action']: row['count'] for row in cursor.fetchall()}
        
        # Signals by symbol
        cursor.execute('''
            SELECT symbol, COUNT(*) as count 
            FROM tradingview_signals 
            GROUP BY symbol 
            ORDER BY count DESC 
            LIMIT 10
        ''')
        by_symbol = {row['symbol']: row['count'] for row in cursor.fetchall()}
        
        # Signals by strategy
        cursor.execute('''
            SELECT strategy, COUNT(*) as count 
            FROM tradingview_signals 
            WHERE strategy IS NOT NULL
            GROUP BY strategy 
            ORDER BY count DESC
        ''')
        by_strategy = {row['strategy']: row['count'] for row in cursor.fetchall()}
        
        # Recent signals (last 24 hours)
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        cursor.execute('''
            SELECT COUNT(*) as count 
            FROM tradingview_signals 
            WHERE created_at > ?
        ''', (yesterday,))
        last_24h = cursor.fetchone()['count']
        
        # Processed vs unprocessed
        cursor.execute('''
            SELECT processed, COUNT(*) as count 
            FROM tradingview_signals 
            GROUP BY processed
        ''')
        processed_stats = {row['processed']: row['count'] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            'total_signals': total,
            'by_action': by_action,
            'by_symbol': by_symbol,
            'by_strategy': by_strategy,
            'last_24h': last_24h,
            'processed': processed_stats.get(1, 0),
            'unprocessed': processed_stats.get(0, 0)
        }
    
    @staticmethod
    def record_execution(
        signal_id: str,
        execution_type: str,
        execution_price: float = None,
        quantity: float = None,
        order_id: str = None,
        status: str = 'success',
        error_message: str = None
    ) -> dict:
        """Record execution of a signal."""
        execution_id = str(uuid.uuid4())[:12]
        now = datetime.utcnow().isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO signal_executions (
                id, signal_id, executed_at, execution_type, 
                execution_price, quantity, order_id, status, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            execution_id, signal_id, now, execution_type,
            execution_price, quantity, order_id, status, error_message
        ))
        
        conn.commit()
        
        cursor.execute('SELECT * FROM signal_executions WHERE id = ?', (execution_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    @staticmethod
    def get_signal_executions(signal_id: str) -> List[dict]:
        """Get all executions for a signal."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM signal_executions 
            WHERE signal_id = ? 
            ORDER BY executed_at DESC
        ''', (signal_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
