"""
MMM Storage — Money Mind & Method

Thread-safe SQLite persistence for MMM sessions.
Consistent with the rest of the bot (alerts_db, strategy_manager, trades).

On first init, automatically migrates any existing mmm_sessions.json data
into the SQLite database so no running session is lost.

Created: February 15, 2026
Updated: February 17, 2026 — Migrated from JSON to SQLite
"""

import json
import os
import sqlite3
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

log = logging.getLogger('mmm_storage')

# Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
DB_FILE = os.path.join(DATA_DIR, 'mmm_sessions.db')
LEGACY_JSON_FILE = os.path.join(DATA_DIR, 'mmm_sessions.json')

# Singleton instance
_storage_instance = None


class MMMStorage:
    """
    Thread-safe SQLite storage for MMM sessions.

    Schema:
      mmm_sessions (
          session_id   TEXT PRIMARY KEY,
          status       TEXT NOT NULL DEFAULT 'IDLE',
          params_json  TEXT NOT NULL DEFAULT '{}',
          data_json    TEXT NOT NULL,
          created_at   TEXT NOT NULL,
          updated_at   TEXT NOT NULL
      )

    - params_json: stores session['params'] separately for atomic hot-reload
    - data_json:   stores the full session dict (including params as snapshot)
    - On read, data_json is merged with the authoritative params_json
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_FILE
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self._migrate_from_json()

    # =========================================================================
    # Database Setup
    # =========================================================================

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
                CREATE TABLE IF NOT EXISTS mmm_sessions (
                    session_id   TEXT PRIMARY KEY,
                    status       TEXT NOT NULL DEFAULT 'IDLE',
                    params_json  TEXT NOT NULL DEFAULT '{}',
                    data_json    TEXT NOT NULL,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL
                )
            ''')
            conn.commit()
            log.info(f"MMM SQLite storage ready: {self.db_path}")
        except Exception as e:
            log.error(f"Failed to init MMM DB: {e}")
            raise
        finally:
            conn.close()

    def _migrate_from_json(self):
        """
        One-time migration: import sessions from legacy mmm_sessions.json.
        After successful import, renames the JSON file to .json.migrated
        so it is never re-imported.
        """
        if not os.path.exists(LEGACY_JSON_FILE):
            return

        try:
            with open(LEGACY_JSON_FILE, 'r') as f:
                data = json.load(f)

            sessions = data.get('sessions', {})
            if not sessions:
                # Empty JSON — just rename and return
                os.rename(LEGACY_JSON_FILE, LEGACY_JSON_FILE + '.migrated')
                log.info("Empty legacy JSON renamed (no sessions to migrate)")
                return

            conn = self._get_conn()
            migrated = 0
            try:
                for session_id, session in sessions.items():
                    # Skip if already in DB (idempotent)
                    row = conn.execute(
                        'SELECT session_id FROM mmm_sessions WHERE session_id = ?',
                        (session_id,)
                    ).fetchone()
                    if row:
                        continue

                    params = session.get('params', {})
                    status = session.get('strategy_status', 'IDLE')
                    created = session.get('created_at', datetime.now(timezone.utc).isoformat())
                    updated = session.get('updated_at', datetime.now(timezone.utc).isoformat())

                    conn.execute('''
                        INSERT INTO mmm_sessions
                            (session_id, status, params_json, data_json, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id,
                        status,
                        json.dumps(params, default=str),
                        json.dumps(session, default=str),
                        created,
                        updated,
                    ))
                    migrated += 1

                conn.commit()
            finally:
                conn.close()

            # Rename legacy file to prevent re-migration
            os.rename(LEGACY_JSON_FILE, LEGACY_JSON_FILE + '.migrated')
            log.info(f"Migrated {migrated} session(s) from JSON to SQLite")

        except Exception as e:
            log.error(f"JSON to SQLite migration failed (JSON untouched): {e}")
            # Don't rename — migration can be retried on next restart

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _row_to_session(self, row) -> Dict:
        """Convert a DB row back to the expected session dict."""
        session = json.loads(row['data_json'])
        # Authoritative params always come from params_json column
        session['params'] = json.loads(row['params_json'])
        return session

    # =========================================================================
    # CRUD Operations — Identical API to old MMMStorage
    # =========================================================================

    def save_session(self, session: Dict) -> str:
        """
        Save or update a session (full replacement of data_json).

        Args:
            session: Complete session dictionary (must have 'session_id')

        Returns:
            session_id
        """
        session_id = session.get('session_id')
        if not session_id:
            raise ValueError("Session must have a session_id")

        now = datetime.now(timezone.utc).isoformat()
        session['updated_at'] = now

        status = session.get('strategy_status', 'IDLE')
        params = session.get('params', {})
        created = session.get('created_at', now)

        conn = self._get_conn()
        try:
            conn.execute('''
                INSERT INTO mmm_sessions
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
            log.debug(f"Saved MMM session {session_id} (status: {status})")
        except Exception as e:
            log.error(f"Failed to save session {session_id}: {e}")
            raise
        finally:
            conn.close()

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session dictionary or None
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                'SELECT * FROM mmm_sessions WHERE session_id = ?',
                (session_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_session(row)
        except Exception as e:
            log.error(f"Failed to get session {session_id}: {e}")
            return None
        finally:
            conn.close()

    def list_sessions(self, active_only: bool = False) -> List[Dict]:
        """
        List all sessions, optionally filtered to active only.

        Args:
            active_only: If True, only return active sessions

        Returns:
            List of session dictionaries (newest first)
        """
        conn = self._get_conn()
        try:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM mmm_sessions WHERE status IN ('RUNNING','PAUSED','BOTH_SIDES_UP') "
                    "ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM mmm_sessions ORDER BY created_at DESC"
                ).fetchall()
            return [self._row_to_session(r) for r in rows]
        except Exception as e:
            log.error(f"Failed to list sessions: {e}")
            return []
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                'DELETE FROM mmm_sessions WHERE session_id = ?',
                (session_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                log.info(f"Deleted MMM session {session_id}")
            return deleted
        except Exception as e:
            log.error(f"Failed to delete session {session_id}: {e}")
            return False
        finally:
            conn.close()

    def update_session(self, session_id: str, updates: Dict) -> Optional[Dict]:
        """
        Partially update a session with the given fields.
        Atomic — reads, merges, and writes in a single transaction.

        Args:
            session_id: Session ID
            updates: Dictionary of fields to update

        Returns:
            Updated session or None if not found
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                'SELECT * FROM mmm_sessions WHERE session_id = ?',
                (session_id,)
            ).fetchone()

            if not row:
                return None

            session = self._row_to_session(row)

            # Deep merge for nested dicts (ce, pe, params)
            for key, value in updates.items():
                if key in ('ce', 'pe', 'params') and isinstance(value, dict) and isinstance(session.get(key), dict):
                    session[key].update(value)
                else:
                    session[key] = value

            now = datetime.now(timezone.utc).isoformat()
            session['updated_at'] = now

            status = session.get('strategy_status', 'IDLE')
            params = session.get('params', {})

            conn.execute('''
                UPDATE mmm_sessions SET
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
            return session
        except Exception as e:
            log.error(f"Failed to update session {session_id}: {e}")
            return None
        finally:
            conn.close()

    def get_active_session_ids(self) -> List[str]:
        """Get list of active session IDs."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT session_id FROM mmm_sessions WHERE status IN ('RUNNING','PAUSED','BOTH_SIDES_UP')"
            ).fetchall()
            return [r['session_id'] for r in rows]
        except Exception as e:
            log.error(f"Failed to get active session IDs: {e}")
            return []
        finally:
            conn.close()

    def get_session_count(self) -> int:
        """Get total number of sessions."""
        conn = self._get_conn()
        try:
            row = conn.execute('SELECT COUNT(*) as cnt FROM mmm_sessions').fetchone()
            return row['cnt'] if row else 0
        except Exception as e:
            log.error(f"Failed to get session count: {e}")
            return 0
        finally:
            conn.close()


def get_storage(storage_path: str = None) -> MMMStorage:
    """
    Get singleton storage instance.

    Args:
        storage_path: Optional custom path

    Returns:
        MMMStorage singleton
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = MMMStorage(storage_path)
    return _storage_instance
