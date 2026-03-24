"""
IC Storage — Iron Condor

Thread-safe SQLite persistence for IC sessions.
Mirrors mmm_storage.py pattern — WAL mode, UPSERT, atomic updates.

Created: 2026-03-24
"""

import json
import os
import sqlite3
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

log = logging.getLogger('ic_storage')

# Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
DB_FILE = os.path.join(DATA_DIR, 'ic_sessions.db')

# Singleton instance
_storage_instance = None


class ICStorage:
    """
    Thread-safe SQLite storage for IC sessions.

    Schema:
      ic_sessions (
          session_id   TEXT PRIMARY KEY,
          status       TEXT NOT NULL DEFAULT 'IDLE',
          params_json  TEXT NOT NULL DEFAULT '{}',
          data_json    TEXT NOT NULL,
          created_at   TEXT NOT NULL,
          updated_at   TEXT NOT NULL
      )
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
        """Create tables if they don't exist."""
        conn = self._get_conn()
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ic_sessions (
                    session_id   TEXT PRIMARY KEY,
                    status       TEXT NOT NULL DEFAULT 'IDLE',
                    params_json  TEXT NOT NULL DEFAULT '{}',
                    data_json    TEXT NOT NULL,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL
                )
            ''')
            conn.commit()
            log.info(f"IC SQLite storage ready: {self.db_path}")
        except Exception as e:
            log.error(f"Failed to init IC DB: {e}")
            raise
        finally:
            conn.close()

    def _row_to_session(self, row) -> Dict:
        """Convert a DB row back to the expected session dict."""
        session = json.loads(row['data_json'])
        # Authoritative params always come from params_json column
        session['params'] = json.loads(row['params_json'])
        return session

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def save_session(self, session: Dict) -> str:
        """
        Save or update a session (full replacement of data_json).
        Returns session_id.
        """
        session_id = session.get('session_id')
        if not session_id:
            raise ValueError("Session must have a session_id")

        now = datetime.now(timezone.utc).isoformat()
        session['updated_at'] = now

        status = session.get('status', 'IDLE')
        params = session.get('params', {})
        created = session.get('created_at', now)

        conn = self._get_conn()
        try:
            conn.execute('''
                INSERT INTO ic_sessions
                    (session_id, status, params_json, data_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status      = excluded.status,
                    params_json = excluded.params_json,
                    data_json   = excluded.data_json,
                    updated_at  = excluded.updated_at
            ''', (
                session_id,
                status,
                json.dumps(params, default=str),
                json.dumps(session, default=str),
                created,
                now,
            ))
            conn.commit()
            log.debug(f"Saved IC session {session_id} (status: {status})")
        except Exception as e:
            log.error(f"Failed to save IC session {session_id}: {e}")
            raise
        finally:
            conn.close()

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get a session by ID. Returns None if not found."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                'SELECT * FROM ic_sessions WHERE session_id = ?',
                (session_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_session(row)
        except Exception as e:
            log.error(f"Failed to get IC session {session_id}: {e}")
            return None
        finally:
            conn.close()

    def list_sessions(self, active_only: bool = False) -> List[Dict]:
        """
        List all sessions, optionally filtered to active only.
        Returns list of session dictionaries (newest first).
        """
        conn = self._get_conn()
        try:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM ic_sessions WHERE status IN ('RUNNING','PAUSED') "
                    "ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM ic_sessions ORDER BY created_at DESC"
                ).fetchall()
            return [self._row_to_session(r) for r in rows]
        except Exception as e:
            log.error(f"Failed to list IC sessions: {e}")
            return []
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if deleted."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                'DELETE FROM ic_sessions WHERE session_id = ?',
                (session_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                log.info(f"Deleted IC session {session_id}")
            return deleted
        except Exception as e:
            log.error(f"Failed to delete IC session {session_id}: {e}")
            return False
        finally:
            conn.close()

    def update_session(self, session_id: str, updates: Dict) -> Optional[Dict]:
        """
        Partially update a session with the given fields.
        Atomic — reads, merges, and writes in a single transaction.
        """
        conn = self._get_conn()
        try:
            conn.execute('BEGIN IMMEDIATE')
            try:
                row = conn.execute(
                    'SELECT * FROM ic_sessions WHERE session_id = ?',
                    (session_id,)
                ).fetchone()

                if not row:
                    conn.rollback()
                    return None

                session = self._row_to_session(row)

                # Deep merge for nested dicts
                for key, value in updates.items():
                    if key in ('params', 'current_cycle') and isinstance(value, dict) and isinstance(session.get(key), dict):
                        session[key].update(value)
                    else:
                        session[key] = value

                now = datetime.now(timezone.utc).isoformat()
                session['updated_at'] = now

                status = session.get('status', 'IDLE')
                params = session.get('params', {})

                conn.execute('''
                    UPDATE ic_sessions SET
                        status      = ?,
                        params_json = ?,
                        data_json   = ?,
                        updated_at  = ?
                    WHERE session_id = ?
                ''', (
                    status,
                    json.dumps(params, default=str),
                    json.dumps(session, default=str),
                    now,
                    session_id,
                ))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            return session
        except Exception as e:
            log.error(f"Failed to update IC session {session_id}: {e}")
            return None
        finally:
            conn.close()

    def get_active_session_ids(self) -> List[str]:
        """Get list of active (RUNNING or PAUSED) session IDs."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT session_id FROM ic_sessions WHERE status IN ('RUNNING','PAUSED')"
            ).fetchall()
            return [r['session_id'] for r in rows]
        except Exception as e:
            log.error(f"Failed to get active IC session IDs: {e}")
            return []
        finally:
            conn.close()


def get_storage() -> ICStorage:
    """Get the singleton ICStorage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = ICStorage()
    return _storage_instance
