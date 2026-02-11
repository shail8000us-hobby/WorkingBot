"""
TradingView Signals Database — World-Class Edition
Store, manage, and monitor TradingView webhook signals with full observability.

Tables:
  - tradingview_signals: Validated, stored signals
  - signal_executions: Trade execution history per signal
  - webhook_request_log: Every raw incoming request (success or failure)
  - tv_health: Health/status tracking for the TradingView pipeline
"""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import uuid
import hashlib
import logging

logger = logging.getLogger("tradingview")

# Database path
DB_PATH = Path(__file__).parent.parent / 'data' / 'tradingview_signals.db'


def get_db_connection():
    """Get database connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_tradingview_signals_db():
    """Initialize TradingView signals database schema (idempotent)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # ── Core signals table ──
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
            notes TEXT,
            dedup_hash TEXT
        )
    ''')

    # Migration: ensure dedup_hash column exists in older DBs (must run BEFORE index)
    try:
        cursor.execute("SELECT dedup_hash FROM tradingview_signals LIMIT 0")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE tradingview_signals ADD COLUMN dedup_hash TEXT")
        logger.info("Migrated: added dedup_hash column")

    for idx_sql in [
        'CREATE INDEX IF NOT EXISTS idx_signals_symbol ON tradingview_signals(symbol)',
        'CREATE INDEX IF NOT EXISTS idx_signals_action ON tradingview_signals(action)',
        'CREATE INDEX IF NOT EXISTS idx_signals_created_at ON tradingview_signals(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_signals_strategy ON tradingview_signals(strategy)',
        'CREATE INDEX IF NOT EXISTS idx_signals_dedup ON tradingview_signals(dedup_hash)',
    ]:
        cursor.execute(idx_sql)

    # ── Signal execution history ──
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
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_executions_signal_id ON signal_executions(signal_id)')

    # ── Webhook request log (every raw request, success or fail) ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS webhook_request_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT NOT NULL,
            source_ip TEXT,
            method TEXT,
            content_type TEXT,
            raw_body TEXT,
            parsed_ok BOOLEAN DEFAULT 0,
            signal_id TEXT,
            error_message TEXT,
            response_code INTEGER,
            processing_ms REAL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reqlog_received ON webhook_request_log(received_at DESC)')

    # ── Health / status tracking ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tv_health (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("TradingView signals DB initialized")


def _dedup_hash(symbol: str, action: str, strategy: str, timeframe: str) -> str:
    """Create a deterministic hash for deduplication."""
    raw = f"{symbol}|{action}|{strategy or ''}|{timeframe or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class TradingViewSignalsDB:
    """Database operations for TradingView signals."""

    # ── Signal CRUD ──────────────────────────────────

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
        dhash = _dedup_hash(symbol, action, strategy, timeframe)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tradingview_signals (
                id, symbol, action, price, strategy, timeframe,
                message, metadata, source_ip, created_at, dedup_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal_id, symbol.upper(), action.lower(), price,
            strategy, timeframe, message,
            json.dumps(metadata) if metadata else None,
            source_ip, now, dhash,
        ))
        conn.commit()

        cursor.execute('SELECT * FROM tradingview_signals WHERE id = ?', (signal_id,))
        row = cursor.fetchone()
        conn.close()

        # Update health
        TradingViewSignalsDB.set_health('last_signal_at', now)
        TradingViewSignalsDB.set_health('last_signal_action', action)
        TradingViewSignalsDB.set_health('last_signal_symbol', symbol.upper())

        return dict(row) if row else None

    @staticmethod
    def is_duplicate(symbol: str, action: str, strategy: str, timeframe: str,
                     window_seconds: int = 60) -> bool:
        """Check if an identical signal was received within the dedup window."""
        dhash = _dedup_hash(symbol, action, strategy, timeframe)
        cutoff = (datetime.utcnow() - timedelta(seconds=window_seconds)).isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as cnt FROM tradingview_signals
            WHERE dedup_hash = ? AND created_at > ?
        ''', (dhash, cutoff))
        result = cursor.fetchone()
        conn.close()
        return result['cnt'] > 0

    @staticmethod
    def get_signals(
        symbol: str = None, action: str = None,
        strategy: str = None, timeframe: str = None,
        limit: int = 100, offset: int = 0
    ) -> List[dict]:
        """Get signals with optional filters."""
        conn = get_db_connection()
        cursor = conn.cursor()
        query = 'SELECT * FROM tradingview_signals WHERE 1=1'
        params = []
        if symbol:
            query += ' AND symbol = ?'; params.append(symbol.upper())
        if action:
            query += ' AND action = ?'; params.append(action.lower())
        if strategy:
            query += ' AND strategy = ?'; params.append(strategy)
        if timeframe:
            query += ' AND timeframe = ?'; params.append(timeframe)
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_signal(signal_id: str) -> Optional[dict]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tradingview_signals WHERE id = ?', (signal_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def count_signals(
        symbol: str = None, action: str = None,
        strategy: str = None, timeframe: str = None
    ) -> int:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = 'SELECT COUNT(*) as count FROM tradingview_signals WHERE 1=1'
        params = []
        if symbol:
            query += ' AND symbol = ?'; params.append(symbol.upper())
        if action:
            query += ' AND action = ?'; params.append(action.lower())
        if strategy:
            query += ' AND strategy = ?'; params.append(strategy)
        if timeframe:
            query += ' AND timeframe = ?'; params.append(timeframe)
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()
        return result['count'] if result else 0

    @staticmethod
    def mark_as_processed(signal_id: str, notes: str = None) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE tradingview_signals SET processed = 1, processed_at = ?, notes = ? WHERE id = ?
        ''', (datetime.utcnow().isoformat(), notes, signal_id))
        ok = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return ok

    @staticmethod
    def delete_signal(signal_id: str) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tradingview_signals WHERE id = ?', (signal_id,))
        ok = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return ok

    @staticmethod
    def get_signal_stats() -> dict:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) as total FROM tradingview_signals')
        total = cursor.fetchone()['total']

        cursor.execute('SELECT action, COUNT(*) as count FROM tradingview_signals GROUP BY action')
        by_action = {row['action']: row['count'] for row in cursor.fetchall()}

        cursor.execute('SELECT symbol, COUNT(*) as count FROM tradingview_signals GROUP BY symbol ORDER BY count DESC LIMIT 10')
        by_symbol = {row['symbol']: row['count'] for row in cursor.fetchall()}

        cursor.execute('SELECT strategy, COUNT(*) as count FROM tradingview_signals WHERE strategy IS NOT NULL GROUP BY strategy ORDER BY count DESC')
        by_strategy = {row['strategy']: row['count'] for row in cursor.fetchall()}

        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        cursor.execute('SELECT COUNT(*) as count FROM tradingview_signals WHERE created_at > ?', (yesterday,))
        last_24h = cursor.fetchone()['count']

        cursor.execute('SELECT processed, COUNT(*) as count FROM tradingview_signals GROUP BY processed')
        processed_stats = {row['processed']: row['count'] for row in cursor.fetchall()}

        cursor.execute('SELECT * FROM tradingview_signals ORDER BY created_at DESC LIMIT 1')
        last_row = cursor.fetchone()
        last_signal = dict(last_row) if last_row else None

        conn.close()
        return {
            'total_signals': total,
            'by_action': by_action,
            'by_symbol': by_symbol,
            'by_strategy': by_strategy,
            'last_24h': last_24h,
            'processed': processed_stats.get(1, 0),
            'unprocessed': processed_stats.get(0, 0),
            'last_signal': last_signal,
        }

    # ── Execution tracking ──────────────────────────

    @staticmethod
    def record_execution(
        signal_id: str, execution_type: str,
        execution_price: float = None, quantity: float = None,
        order_id: str = None, status: str = 'success',
        error_message: str = None
    ) -> dict:
        execution_id = str(uuid.uuid4())[:12]
        now = datetime.utcnow().isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO signal_executions (
                id, signal_id, executed_at, execution_type,
                execution_price, quantity, order_id, status, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (execution_id, signal_id, now, execution_type,
              execution_price, quantity, order_id, status, error_message))
        conn.commit()
        cursor.execute('SELECT * FROM signal_executions WHERE id = ?', (execution_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_signal_executions(signal_id: str) -> List[dict]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM signal_executions WHERE signal_id = ? ORDER BY executed_at DESC', (signal_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ── Webhook request log ─────────────────────────

    @staticmethod
    def log_webhook_request(
        source_ip: str, method: str, content_type: str, raw_body: str,
        parsed_ok: bool, signal_id: str = None, error_message: str = None,
        response_code: int = 200, processing_ms: float = 0,
    ):
        """Log every webhook request for full observability."""
        now = datetime.utcnow().isoformat()
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            truncated = raw_body[:10240] if raw_body else ''
            cursor.execute('''
                INSERT INTO webhook_request_log (
                    received_at, source_ip, method, content_type, raw_body,
                    parsed_ok, signal_id, error_message, response_code, processing_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (now, source_ip, method, content_type, truncated,
                  1 if parsed_ok else 0, signal_id, error_message, response_code, processing_ms))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log webhook request: {e}")

    @staticmethod
    def get_webhook_logs(limit: int = 50) -> List[dict]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM webhook_request_log ORDER BY received_at DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ── Health tracking ─────────────────────────────

    @staticmethod
    def set_health(key: str, value: str):
        now = datetime.utcnow().isoformat()
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tv_health (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            ''', (key, str(value), now))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to set health key {key}: {e}")

    @staticmethod
    def get_health(key: str = None) -> dict:
        conn = get_db_connection()
        cursor = conn.cursor()
        if key:
            cursor.execute('SELECT * FROM tv_health WHERE key = ?', (key,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else {}
        else:
            cursor.execute('SELECT * FROM tv_health')
            rows = cursor.fetchall()
            conn.close()
            return {row['key']: {'value': row['value'], 'updated_at': row['updated_at']} for row in rows}

    # ── Maintenance ─────────────────────────────────

    @staticmethod
    def cleanup_old_logs(days: int = 30):
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM webhook_request_log WHERE received_at < ?', (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted:
            logger.info(f"Cleaned up {deleted} old webhook log entries")
        return deleted

    @staticmethod
    def cleanup_old_signals(days: int = 90):
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tradingview_signals WHERE created_at < ? AND processed = 1', (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted:
            logger.info(f"Cleaned up {deleted} old processed signals")
        return deleted
