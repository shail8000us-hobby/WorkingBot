"""
MMM Analytics Storage - Persistent Historical Records

SQLite-based storage for analytics (consistent with session storage).
Stores analytics separately from sessions to preserve historical data
even after sessions are deleted or expired.

Created: February 18, 2026
"""

import logging
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path

log = logging.getLogger('mmm_analytics_storage')

# Use same database as session storage
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
DB_FILE = os.path.join(DATA_DIR, 'mmm_sessions.db')


class MMMAnalyticsStorage:
    """
    Persistent SQLite storage for MMM session analytics.
    
    Keeps analytics history separate from session lifecycle.
    Analytics are never deleted automatically.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_FILE
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a new connection with WAL mode for concurrent reads."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self):
        """Create analytics table if it doesn't exist."""
        conn = self._get_conn()
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mmm_analytics (
                    session_id TEXT PRIMARY KEY,
                    session_status TEXT,
                    expiry TEXT,
                    analytics_json TEXT NOT NULL,
                    saved_at TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            
            # Index for common queries
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_analytics_expiry 
                ON mmm_analytics(expiry)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_analytics_status 
                ON mmm_analytics(session_status)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_analytics_saved_at 
                ON mmm_analytics(saved_at DESC)
            ''')
            
            conn.commit()
            log.info(f"MMM Analytics SQLite storage ready: {self.db_path}")
        except Exception as e:
            log.error(f"Failed to init Analytics table: {e}")
            raise
        finally:
            conn.close()

    def save_session_analytics(self, session: Dict) -> None:
        """
        Save or update analytics for a session.
        Called on session stop or periodically during run.
        """
        session_id = session.get('session_id')
        if not session_id:
            return

        analytics = session.get('analytics', {})
        
        # Build analytics record
        record = {
            **analytics,
            'session_id': session_id,
            'session_status': session.get('strategy_status', 'UNKNOWN'),
            'saved_at': datetime.now(timezone.utc).isoformat(),
            
            # Session metadata
            'expiry': session.get('params', {}).get('expiry', ''),
            'created_at': session.get('created_at', ''),
            'entry_time': session.get('entry_time', ''),
            
            # Final state
            'final_ce_lots': session.get('ce', {}).get('total_lots', 0),
            'final_pe_lots': session.get('pe', {}).get('total_lots', 0),
            'final_realized_pnl': session.get('realized_pnl', 0),
            'final_unrealized_pnl': session.get('unrealized_pnl', 0),
            'final_total_pnl': (
                session.get('realized_pnl', 0) + 
                session.get('unrealized_pnl', 0)
            ),
            'total_adjustments': session.get('adjustment_count', 0),
            'total_reversals': session.get('reversal_count', 0),
            'total_shifts': session.get('shift_count', 0),
            'total_close_at_5': session.get('close_at_5_count', 0),
            'total_harvests': session.get('harvest_count', 0),
            'total_harvest_lots': session.get('harvest_lots_freed', 0),
            'total_recycles': session.get('recycle_count', 0),
        }

        conn = self._get_conn()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO mmm_analytics 
                (session_id, session_status, expiry, analytics_json, saved_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                record.get('session_status'),
                record.get('expiry'),
                json.dumps(record),
                record.get('saved_at'),
                record.get('created_at'),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
            log.info(f"Saved analytics for session {session_id} to SQLite")
        except Exception as e:
            log.error(f"Failed to save analytics for {session_id}: {e}")
        finally:
            conn.close()

    def get_session_analytics(self, session_id: str) -> Optional[Dict]:
        """Get analytics for a specific session."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                'SELECT analytics_json FROM mmm_analytics WHERE session_id = ?',
                (session_id,)
            ).fetchone()
            
            if row:
                return json.loads(row['analytics_json'])
            return None
        except Exception as e:
            log.error(f"Failed to get analytics for {session_id}: {e}")
            return None
        finally:
            conn.close()

    def get_all_analytics(
        self, 
        limit: int = 50, 
        status_filter: str = None,
        expiry_filter: str = None
    ) -> List[Dict]:
        """
        Get analytics history with optional filters.
        
        Args:
            limit: Max records to return (newest first)
            status_filter: Filter by session_status
            expiry_filter: Filter by expiry date
        """
        conn = self._get_conn()
        try:
            query = 'SELECT analytics_json FROM mmm_analytics WHERE 1=1'
            params = []
            
            if status_filter:
                query += ' AND session_status = ?'
                params.append(status_filter)
            
            if expiry_filter:
                query += ' AND expiry = ?'
                params.append(expiry_filter)
            
            query += ' ORDER BY saved_at DESC LIMIT ?'
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            return [json.loads(row['analytics_json']) for row in rows]
        except Exception as e:
            log.error(f"Failed to get analytics history: {e}")
            return []
        finally:
            conn.close()

    def delete_analytics(self, session_id: str) -> bool:
        """
        Manually delete analytics for a session.
        (Typically not used - analytics persist by design)
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                'DELETE FROM mmm_analytics WHERE session_id = ?',
                (session_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                log.info(f"Deleted analytics for session {session_id}")
            return deleted
        except Exception as e:
            log.error(f"Failed to delete analytics for {session_id}: {e}")
            return False
        finally:
            conn.close()


# Singleton instance
_analytics_storage = None
_analytics_storage_lock = threading.Lock()


def get_analytics_storage() -> MMMAnalyticsStorage:
    """Get or create the analytics storage singleton."""
    global _analytics_storage
    if _analytics_storage is None:
        with _analytics_storage_lock:
            if _analytics_storage is None:
                _analytics_storage = MMMAnalyticsStorage()
    return _analytics_storage
