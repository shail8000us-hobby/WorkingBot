"""
MMMX Storage — Thread-Safe SQLite Persistence

Separate DB from MMM: mmmx_sessions.db (never touches the MMM session database).
Spec: MMMX_IMPLEMENTATION_PLAN.md Section 1.

Schema tables:
  sessions       — one row per session (full JSON blob + fast-access columns)
  generations    — monotonic generation counter per session (written atomically)
  audit_log      — append-only trade/order journal (written by mmmx_audit_log.py)
  activity_log   — ring-buffer of activity events
  param_audit    — hot-reload param change history

Rules:
  - WAL mode for concurrent readers.
  - All session saves are generation-checked: save rejects if stored_gen != expected_gen.
  - bump_generation() is always called BEFORE spawning a new monitor thread.
  - Never call UPDATE or DELETE on audit_log or param_audit.
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .mmmx_constants import DB_FILE, SessionStatus

log = logging.getLogger('mmmx_storage')

_storage_instance: Optional['MMMXStorage'] = None
_instance_lock = threading.Lock()


class GenerationConflict(Exception):
    """Raised when a save is rejected because stored_gen != expected_gen."""
    pass


class MMMXStorage:
    """Thread-safe SQLite storage for MMMX sessions."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_FILE
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._write_lock = threading.Lock()
        self._init_db()

    # ── DB setup ───────────────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        with self._write_lock:
            conn = self._get_conn()
            try:
                conn.executescript('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id   TEXT PRIMARY KEY,
                        status       TEXT NOT NULL DEFAULT 'DRAFT',
                        data_json    TEXT NOT NULL,
                        created_at   TEXT NOT NULL,
                        updated_at   TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS generations (
                        session_id   TEXT PRIMARY KEY,
                        generation   INTEGER NOT NULL DEFAULT 0,
                        updated_at   TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                    );

                    CREATE TABLE IF NOT EXISTS audit_log (
                        id               INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id       TEXT NOT NULL,
                        idempotency_key  TEXT UNIQUE,
                        event_type       TEXT NOT NULL,
                        generation       INTEGER,
                        data_json        TEXT NOT NULL,
                        created_at       TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_audit_session
                        ON audit_log(session_id, created_at);

                    CREATE TABLE IF NOT EXISTS activity_log (
                        id           INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id   TEXT,
                        event_type   TEXT NOT NULL,
                        data_json    TEXT NOT NULL,
                        created_at   TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_activity_session
                        ON activity_log(session_id, created_at);

                    CREATE TABLE IF NOT EXISTS param_audit (
                        id           INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id   TEXT NOT NULL,
                        diff_json    TEXT NOT NULL,
                        changed_by   TEXT NOT NULL DEFAULT 'operator',
                        created_at   TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_param_session
                        ON param_audit(session_id, created_at);
                ''')
                conn.commit()
            finally:
                conn.close()

    # ── Session CRUD ───────────────────────────────────────────────────────────

    def save_session(self, session: Dict[str, Any], expected_gen: Optional[int] = None) -> None:
        """
        Save (upsert) session to DB.

        If expected_gen is provided, atomically checks that generations.generation
        == expected_gen before writing. Raises GenerationConflict if stale.
        This is the generation-checked write path used by the monitor.

        For initial creation (no generation yet), pass expected_gen=None.
        """
        now = datetime.now(timezone.utc).isoformat()
        session_id = session['session_id']
        status = session.get('status', SessionStatus.DRAFT)
        data_json = json.dumps(session, default=str)

        with self._write_lock:
            conn = self._get_conn()
            try:
                if expected_gen is not None:
                    row = conn.execute(
                        "SELECT generation FROM generations WHERE session_id=?",
                        (session_id,)
                    ).fetchone()
                    stored_gen = row['generation'] if row else 0
                    if stored_gen != expected_gen:
                        raise GenerationConflict(
                            f"MMMX save rejected: stored_gen={stored_gen} != expected={expected_gen} "
                            f"(session {session_id})"
                        )

                conn.execute('''
                    INSERT INTO sessions (session_id, status, data_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        status     = excluded.status,
                        data_json  = excluded.data_json,
                        updated_at = excluded.updated_at
                ''', (session_id, status, data_json, session.get('created_at', now), now))

                # Ensure generations row exists
                conn.execute('''
                    INSERT OR IGNORE INTO generations (session_id, generation, updated_at)
                    VALUES (?, 0, ?)
                ''', (session_id, now))

                conn.commit()
            finally:
                conn.close()

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load a session by ID. Returns None if not found."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT data_json FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if row is None:
                return None
            return json.loads(row['data_json'])
        finally:
            conn.close()

    def list_sessions(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all sessions, optionally filtered by status.
        Returns lightweight dicts including expiry fields extracted from data_json.
        """
        conn = self._get_conn()
        try:
            if status_filter:
                rows = conn.execute(
                    "SELECT session_id, status, created_at, updated_at, data_json FROM sessions "
                    "WHERE status=? ORDER BY created_at ASC",
                    (status_filter,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT session_id, status, created_at, updated_at, data_json FROM sessions "
                    "ORDER BY created_at ASC"
                ).fetchall()

            result = []
            for r in rows:
                d = dict(r)
                # Extract lightweight fields from data_json without loading full blob
                try:
                    blob = json.loads(d.pop('data_json') or '{}')
                    d['expiry_ddmmyy'] = blob.get('expiry_ddmmyy') or blob.get('params', {}).get('target_expiry_ddmmyy') or ''
                    d['expiry_date'] = blob.get('expiry_date', '')
                    d['portfolio_pnl'] = blob.get('portfolio_pnl', 0.0)
                    d['total_premium_collected'] = blob.get('total_premium_collected', 0.0)
                    d['tranches_deployed'] = blob.get('tranches_deployed', 0)
                    d['hard_stop_usd'] = blob.get('hard_stop_usd', 0.0)
                    d['beat_count'] = blob.get('beat_number', 0)
                    d['last_beat_at'] = blob.get('_last_beat_at', '')
                    d['reconcile_required'] = blob.get('reconcile_required', False)
                    d['ce_reserve_remaining'] = blob.get('ce_reserve_remaining', 30)
                    d['pe_reserve_remaining'] = blob.get('pe_reserve_remaining', 30)
                except Exception:
                    d.pop('data_json', None)
                result.append(d)

            # Return in reverse-chronological order (newest first) for display
            result.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return result
        finally:
            conn.close()

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """Return full session dicts for RUNNING and PAUSED sessions (for restore on startup)."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT data_json FROM sessions WHERE status IN (?, ?) ORDER BY created_at",
                (SessionStatus.RUNNING, SessionStatus.PAUSED)
            ).fetchall()
            return [json.loads(r['data_json']) for r in rows]
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> None:
        """Delete a session and its generation row. Only for DRAFT/ERROR sessions."""
        with self._write_lock:
            conn = self._get_conn()
            try:
                conn.execute("DELETE FROM generations WHERE session_id=?", (session_id,))
                conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
                conn.commit()
            finally:
                conn.close()

    # ── Generation management ──────────────────────────────────────────────────

    def bump_generation(self, session_id: str) -> int:
        """
        Atomically increment and return the new generation counter.

        MUST be called before spawning a new monitor thread. The new monitor
        reads this value as its _my_generation. The old monitor's saves will
        then fail the generation check and self-stop.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._write_lock:
            conn = self._get_conn()
            try:
                # Ensure row exists
                conn.execute('''
                    INSERT OR IGNORE INTO generations (session_id, generation, updated_at)
                    VALUES (?, 0, ?)
                ''', (session_id, now))

                conn.execute('''
                    UPDATE generations
                    SET generation = generation + 1, updated_at = ?
                    WHERE session_id = ?
                ''', (now, session_id))

                row = conn.execute(
                    "SELECT generation FROM generations WHERE session_id=?",
                    (session_id,)
                ).fetchone()
                conn.commit()
                return row['generation']
            finally:
                conn.close()

    def get_generation(self, session_id: str) -> int:
        """Read current generation without incrementing."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT generation FROM generations WHERE session_id=?",
                (session_id,)
            ).fetchone()
            return row['generation'] if row else 0
        finally:
            conn.close()

    # ── Audit log ──────────────────────────────────────────────────────────────

    def append_audit_event(
        self,
        session_id: str,
        event_type: str,
        data: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        generation: Optional[int] = None,
    ) -> None:
        """Append an audit event. INSERT OR IGNORE on idempotency_key prevents duplicates."""
        now = datetime.now(timezone.utc).isoformat()
        with self._write_lock:
            conn = self._get_conn()
            try:
                conn.execute('''
                    INSERT OR IGNORE INTO audit_log
                        (session_id, idempotency_key, event_type, generation, data_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (session_id, idempotency_key, event_type, generation,
                      json.dumps(data, default=str), now))
                conn.commit()
            finally:
                conn.close()

    def get_audit_events(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        """Read most recent audit events for a session."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit)
            ).fetchall()
            events = []
            for r in rows:
                e = dict(r)
                e['data'] = json.loads(e.pop('data_json', '{}'))
                events.append(e)
            return events
        finally:
            conn.close()

    # ── Activity log ───────────────────────────────────────────────────────────

    def append_activity(
        self,
        event_type: str,
        data: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> None:
        """Append an activity event (ring-buffer pruning handled by mmmx_activity.py)."""
        now = datetime.now(timezone.utc).isoformat()
        with self._write_lock:
            conn = self._get_conn()
            try:
                conn.execute('''
                    INSERT INTO activity_log (session_id, event_type, data_json, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (session_id, event_type, json.dumps(data, default=str), now))
                conn.commit()
            finally:
                conn.close()

    def get_recent_activities(self, session_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Fetch recent activity entries."""
        conn = self._get_conn()
        try:
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM activity_log WHERE session_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (session_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            result = []
            for r in rows:
                e = dict(r)
                e['data'] = json.loads(e.pop('data_json', '{}'))
                result.append(e)
            return result
        finally:
            conn.close()

    # ── Param audit ────────────────────────────────────────────────────────────

    def append_param_audit(
        self,
        session_id: str,
        diff: Dict[str, Any],
        changed_by: str = 'operator',
    ) -> None:
        """Record a hot-reload param change. Append-only."""
        now = datetime.now(timezone.utc).isoformat()
        with self._write_lock:
            conn = self._get_conn()
            try:
                conn.execute('''
                    INSERT INTO param_audit (session_id, diff_json, changed_by, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (session_id, json.dumps(diff, default=str), changed_by, now))
                conn.commit()
            finally:
                conn.close()

    def get_param_audit(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Read param change history for a session."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM param_audit WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit)
            ).fetchall()
            result = []
            for r in rows:
                e = dict(r)
                e['diff'] = json.loads(e.pop('diff_json', '{}'))
                result.append(e)
            return result
        finally:
            conn.close()


# ── Singleton accessor ─────────────────────────────────────────────────────────

def get_storage(db_path: str = None) -> MMMXStorage:
    global _storage_instance
    if _storage_instance is None:
        with _instance_lock:
            if _storage_instance is None:
                _storage_instance = MMMXStorage(db_path)
    return _storage_instance
