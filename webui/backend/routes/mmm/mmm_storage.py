"""
MMM Storage — Money Mind & Method

Thread-safe SQLite persistence for MMM sessions.
Consistent with the rest of the bot (alerts_db, strategy_manager, trades).

On first init, automatically migrates any existing mmm_sessions.json data
into the SQLite database so no running session is lost.

Created: February 15, 2026
Updated: February 17, 2026 — Migrated from JSON to SQLite
Updated: February 26, 2026 — Added session state checksum for corruption detection
"""

import json
import os
import sqlite3
import logging
import hashlib
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

    def _calculate_checksum(self, session: Dict) -> str:
        """
        Calculate a checksum of critical session fields for corruption detection.
        
        Critical fields: session_id, params, strategy_status, positions, fills, trade_history
        """
        critical_data = {
            'session_id': session.get('session_id'),
            'params': session.get('params', {}),
            'strategy_status': session.get('strategy_status'),
            'positions': session.get('positions', {}),
            'fills': session.get('fills', []),
            'trade_history': session.get('trade_history', []),
        }
        # Sort keys for deterministic hashing
        data_str = json.dumps(critical_data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]

    def _validate_checksum(self, session: Dict) -> bool:
        """
        Validate session checksum. Returns True if valid or no checksum exists.
        Logs warning on mismatch but doesn't fail (backward compatibility).
        """
        stored_checksum = session.get('_checksum')
        if not stored_checksum:
            # No checksum = legacy session, consider valid
            return True
        
        calculated = self._calculate_checksum(session)
        if calculated != stored_checksum:
            log.warning(
                f"Session {session.get('session_id')} checksum mismatch: "
                f"stored={stored_checksum}, calculated={calculated}. "
                "Possible corruption or manual edit."
            )
            return False
        return True

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
        
        # Calculate and store checksum for corruption detection
        session['_checksum'] = self._calculate_checksum(session)

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
            session = self._row_to_session(row)
            # Audit fix: checksum mismatch now marks the session with a warning flag
            # so callers (monitor startup, API) can emit a WebSocket safety alert.
            # We still return the session for backward compatibility — a mismatch
            # could be a legitimate manual DB edit or a format change, not always
            # corruption. The _checksum_warning flag lets the monitor decide the
            # right action (pause, alert, or continue).
            if not self._validate_checksum(session):
                session['_checksum_warning'] = True
                log.critical(
                    f"[CORRUPTION RISK] Session {session_id} checksum mismatch — "
                    f"data may have been corrupted. Session loaded with warning flag. "
                    f"Monitor will emit safety alert on next heartbeat."
                )
            else:
                session.pop('_checksum_warning', None)
            return session
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

            # Recalculate checksum after merging updates so get_session won't
            # flag this as corrupted on the next read.
            session['_checksum'] = self._calculate_checksum(session)
            session.pop('_checksum_warning', None)

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

    def list_session_summaries(self, active_only: bool = False) -> List[Dict]:
        """
        List compact session summaries WITHOUT deserializing full data_json.

        Uses SQLite json_extract() to pull only the fields needed for
        get_session_summary(), avoiding the deserialization of multi-MB
        data_json blobs (28 sessions × ~300KB each = 8.3MB).

        Performance: ~10ms vs ~10s for full deserialization.
        """
        conn = self._get_conn()
        try:
            where = (
                "WHERE status IN ('RUNNING','PAUSED','BOTH_SIDES_UP')"
                if active_only else ""
            )
            rows = conn.execute(f'''
                SELECT
                    session_id,
                    status,
                    created_at,
                    json_extract(data_json, '$.mode')                     AS mode,
                    json_extract(data_json, '$.entry_time')               AS entry_time,
                    json_extract(data_json, '$.ce.active_strike')         AS ce_active_strike,
                    json_extract(data_json, '$.ce.original_lots')         AS ce_original_lots,
                    json_extract(data_json, '$.ce.active_lots')           AS ce_active_lots,
                    json_extract(data_json, '$.ce.total_lots')            AS ce_total_lots,
                    json_extract(data_json, '$.ce.frozen_total_lots')     AS ce_frozen_lots,
                    json_extract(data_json, '$.pe.active_strike')         AS pe_active_strike,
                    json_extract(data_json, '$.pe.original_lots')         AS pe_original_lots,
                    json_extract(data_json, '$.pe.active_lots')           AS pe_active_lots,
                    json_extract(data_json, '$.pe.total_lots')            AS pe_total_lots,
                    json_extract(data_json, '$.pe.frozen_total_lots')     AS pe_frozen_lots,
                    json_extract(data_json, '$.last_aggressor')           AS last_aggressor,
                    json_extract(data_json, '$.adjustment_count')         AS adjustment_count,
                    json_extract(data_json, '$.reversal_count')           AS reversal_count,
                    json_extract(data_json, '$.shift_count')              AS shift_count,
                    json_extract(data_json, '$.close_at_5_count')         AS close_at_5_count,
                    json_extract(data_json, '$.total_premium_collected')  AS total_premium_collected,
                    json_extract(data_json, '$.realized_pnl')             AS realized_pnl,
                    json_extract(data_json, '$.unrealized_pnl')           AS unrealized_pnl,
                    json_extract(data_json, '$.total_fees')               AS total_fees,
                    json_extract(data_json, '$.peak_pnl')                 AS peak_pnl,
                    json_extract(data_json, '$.last_heartbeat')           AS last_heartbeat,
                    json_extract(data_json, '$.next_heartbeat')           AS next_heartbeat,
                    json_extract(data_json, '$.expiry_time')              AS expiry_time,
                    json_extract(params_json, '$.adjustment_interval')    AS adjustment_interval,
                    json_extract(params_json, '$.expiry')                 AS expiry
                FROM mmm_sessions
                {where}
                ORDER BY created_at DESC
            ''').fetchall()

            summaries = []
            for r in rows:
                realized = r['realized_pnl'] or 0
                unrealized = r['unrealized_pnl'] or 0
                fees = r['total_fees'] or 0
                summaries.append({
                    'session_id': r['session_id'],
                    'status': r['status'] or 'IDLE',
                    'mode': r['mode'] or 'fresh',
                    'created_at': r['created_at'],
                    'entry_time': r['entry_time'],
                    'ce_strike': r['ce_active_strike'] or 0,
                    'ce_original_lots': r['ce_original_lots'] or 0,
                    'ce_active_lots': r['ce_active_lots'] or 0,
                    'ce_total_lots': r['ce_total_lots'] or 0,
                    'ce_frozen_lots': r['ce_frozen_lots'] or 0,
                    'pe_strike': r['pe_active_strike'] or 0,
                    'pe_original_lots': r['pe_original_lots'] or 0,
                    'pe_active_lots': r['pe_active_lots'] or 0,
                    'pe_total_lots': r['pe_total_lots'] or 0,
                    'pe_frozen_lots': r['pe_frozen_lots'] or 0,
                    'last_aggressor': r['last_aggressor'] or 'NONE',
                    'adjustment_count': r['adjustment_count'] or 0,
                    'reversal_count': r['reversal_count'] or 0,
                    'shift_count': r['shift_count'] or 0,
                    'close_at_5_count': r['close_at_5_count'] or 0,
                    'total_premium_collected': r['total_premium_collected'] or 0,
                    'realized_pnl': realized,
                    'unrealized_pnl': unrealized,
                    'total_fees': fees,
                    'net_pnl': realized + unrealized - fees,
                    'peak_pnl': r['peak_pnl'] or 0,
                    'adjustment_interval': r['adjustment_interval'] or 300,
                    'last_heartbeat': r['last_heartbeat'],
                    'next_heartbeat': r['next_heartbeat'],
                    'expiry': r['expiry'] or '',
                    'expiry_time': r['expiry_time'],
                })
            return summaries
        except Exception as e:
            log.error(f"Failed to list session summaries: {e}")
            # Fallback to full deserialization
            return [
                self._row_to_summary_fallback(s)
                for s in self.list_sessions(active_only=active_only)
            ]
        finally:
            conn.close()

    def _row_to_summary_fallback(self, session: Dict) -> Dict:
        """Fallback: extract summary from fully deserialized session."""
        ce = session.get('ce', {})
        pe = session.get('pe', {})
        realized = session.get('realized_pnl', 0)
        unrealized = session.get('unrealized_pnl', 0)
        fees = session.get('total_fees', 0)
        return {
            'session_id': session.get('session_id'),
            'status': session.get('strategy_status', 'IDLE'),
            'mode': session.get('mode', 'fresh'),
            'created_at': session.get('created_at'),
            'entry_time': session.get('entry_time'),
            'ce_strike': ce.get('active_strike', 0),
            'ce_original_lots': ce.get('original_lots', 0),
            'ce_active_lots': ce.get('active_lots', 0),
            'ce_total_lots': ce.get('total_lots', 0),
            'ce_frozen_lots': ce.get('frozen_total_lots', 0),
            'pe_strike': pe.get('active_strike', 0),
            'pe_original_lots': pe.get('original_lots', 0),
            'pe_active_lots': pe.get('active_lots', 0),
            'pe_total_lots': pe.get('total_lots', 0),
            'pe_frozen_lots': pe.get('frozen_total_lots', 0),
            'last_aggressor': session.get('last_aggressor', 'NONE'),
            'adjustment_count': session.get('adjustment_count', 0),
            'reversal_count': session.get('reversal_count', 0),
            'shift_count': session.get('shift_count', 0),
            'close_at_5_count': session.get('close_at_5_count', 0),
            'total_premium_collected': session.get('total_premium_collected', 0),
            'realized_pnl': realized,
            'unrealized_pnl': unrealized,
            'total_fees': fees,
            'net_pnl': realized + unrealized - fees,
            'peak_pnl': session.get('peak_pnl', 0),
            'adjustment_interval': session.get('params', {}).get('adjustment_interval', 300),
            'last_heartbeat': session.get('last_heartbeat'),
            'next_heartbeat': session.get('next_heartbeat'),
            'expiry': session.get('params', {}).get('expiry', ''),
            'expiry_time': session.get('expiry_time'),
        }

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
