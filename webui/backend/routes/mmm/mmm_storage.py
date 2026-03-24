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
        # Backfill side premiums if missing — ensures restart doesn't reset to 0
        self._backfill_session_side_premiums(session)
        # One-time: correct FillSync double-booking (BUG-1 retroactive fix)
        self._correct_fillsync_double_booking(session)
        return session

    def _backfill_session_side_premiums(self, session: Dict) -> None:
        """
        Backfill ce_premium_collected / pe_premium_collected from adjustment_history.

        Uses whichever is larger: the stored value or the history-derived value.
        This handles two cases:
          1. Field missing/zero after a fresh session or first run → backfill from history
          2. Field was partially reset by a restart (e.g., stored=0.14 but history=2.38)
             → history-derived value wins

        Called on every session load so that post-restart engine updates accumulate
        on top of the correct historical total, not from 0.
        """
        LOT = 0.001
        history = session.get('adjustment_history', []) or []
        lots = session.get('lots', 0) or 0
        for side in ('ce', 'pe'):
            key = f'{side}_premium_collected'
            stored = session.get(key) or 0
            side_data = session.get(side) or {}
            entry_fill = side_data.get('entry_fill_price', 0) or 0
            prem = entry_fill * lots * LOT
            for entry in history:
                if (entry.get('side') or '').upper() == side.upper():
                    prem += entry.get('premium_collected', 0) or 0
            # Use whichever is larger — history-derived is authoritative if stored < history
            if prem > stored:
                session[key] = round(prem, 6)

    def _correct_fillsync_double_booking(self, session: Dict) -> None:
        """
        One-time retroactive fix for BUG-1: FillSync double-counted P&L.

        Before the fix, close paths did not stamp _estimated_pnl_booked on
        positions. FillSyncer then treated the estimate as 0 and re-booked
        the full P&L. The fingerprint is:
          _fill_confirmed=True AND _estimated_pnl_booked in (0, None)
          AND _pnl_correction_applied == _actual_pnl_booked (i.e. full re-book)

        This correction runs once per session load. It subtracts the
        double-booked amount from realized_pnl, stamps the positions so the
        correction is idempotent, and logs the event.
        """
        if session.get('_fillsync_double_booking_corrected'):
            return  # Already corrected — idempotent

        total_over = 0.0
        count = 0
        for side_key in ('ce', 'pe'):
            side = session.get(side_key, {})
            for pos in side.get('positions', []):
                if not pos.get('_fill_confirmed'):
                    continue
                est = pos.get('_estimated_pnl_booked')
                corr = pos.get('_pnl_correction_applied', 0) or 0
                actual = pos.get('_actual_pnl_booked', 0) or 0
                # Fingerprint: estimate was 0/None and correction == actual
                # (meaning FillSync re-booked the full amount)
                if (est is None or est == 0) and abs(corr - actual) < 1e-8 and abs(corr) > 1e-8:
                    total_over += corr
                    count += 1
                    # Stamp so this position is not corrected again
                    pos['_estimated_pnl_booked'] = actual
                    pos['_pnl_correction_applied'] = 0.0

        if count > 0 and abs(total_over) > 1e-8:
            session['realized_pnl'] = round(
                session.get('realized_pnl', 0) - total_over, 8)
            session['_fillsync_double_booking_corrected'] = True
            session['_fillsync_correction_amount'] = round(total_over, 8)
            session['_fillsync_correction_count'] = count
            log.info(
                f"[{session.get('session_id', '?')}] BUG-1 retroactive fix: "
                f"subtracted ${total_over:.6f} double-booked P&L from "
                f"{count} positions"
            )
        else:
            # No correction needed — mark so we don't re-scan
            session['_fillsync_double_booking_corrected'] = True

    def _calculate_checksum(self, session: Dict) -> str:
        """
        Legacy v1 checksum — kept for backward compatibility only.
        Prefer _calculate_checksum_v2() for new saves.

        Known problems with v1:
        - ce_frozen/pe_frozen are derived views rebuilt on load; transient
          _being_closed flags can cause false-positive mismatch reports.
        - fills/trade_history/positions are always [] / {} in MMM sessions;
          checksumming them adds noise without protecting real data.
        """
        critical_data = {
            'session_id': session.get('session_id'),
            'params': session.get('params', {}),
            'strategy_status': session.get('strategy_status'),
            'positions': session.get('positions', {}),
            'ce_positions': session.get('ce', {}).get('positions', []),
            'pe_positions': session.get('pe', {}).get('positions', []),
            'ce_frozen': session.get('ce', {}).get('frozen_positions', []),
            'pe_frozen': session.get('pe', {}).get('frozen_positions', []),
            'fills': session.get('fills', []),
            'trade_history': session.get('trade_history', []),
            'realized_pnl': session.get('realized_pnl', 0),
            'total_fees': session.get('total_fees', 0),
        }
        # Sort keys for deterministic hashing
        data_str = json.dumps(critical_data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]

    def _calculate_checksum_v2(self, session: Dict) -> str:
        """
        V2 checksum — covers only canonical (source-of-truth) fields.

        Excluded intentionally:
        - ce_frozen / pe_frozen: derived views rebuilt by recompute_side_lots();
          may differ from saved state due to transient _being_closed stamps.
        - fills / trade_history / positions (top-level): always [] / {} in MMM
          sessions; checksumming empty containers hides real drift.

        The canonical position data lives in ce.positions[] and pe.positions[].
        These are the only lists that are directly written (never rebuilt from
        another source), making them the correct integrity anchor.
        """
        canonical_data = {
            'session_id': session.get('session_id'),
            'params': session.get('params', {}),
            'strategy_status': session.get('strategy_status'),
            'ce_positions': session.get('ce', {}).get('positions', []),
            'pe_positions': session.get('pe', {}).get('positions', []),
            'realized_pnl': session.get('realized_pnl', 0),
            'total_fees': session.get('total_fees', 0),
        }
        data_str = json.dumps(canonical_data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]

    def _validate_checksum(self, session: Dict) -> bool:
        """
        Validate session checksum. Returns True if valid or no checksum exists.
        Logs warning on mismatch but doesn't fail (backward compatibility).

        Prefers _checksum_v2 (canonical fields only) over legacy _checksum.
        """
        session_id = session.get('session_id', '?')

        # Prefer v2 checksum if present — it covers canonical fields only
        stored_v2 = session.get('_checksum_v2')
        if stored_v2:
            calculated_v2 = self._calculate_checksum_v2(session)
            if calculated_v2 != stored_v2:
                log.warning(
                    f"Session {session_id} checksum_v2 mismatch: "
                    f"stored={stored_v2}, calculated={calculated_v2}. "
                    "Possible corruption or manual edit of canonical position data."
                )
                return False
            return True

        # Fall back to legacy v1 checksum for older sessions
        stored_checksum = session.get('_checksum')
        if not stored_checksum:
            # No checksum = legacy session, consider valid
            return True

        calculated = self._calculate_checksum(session)
        if calculated != stored_checksum:
            log.warning(
                f"Session {session_id} checksum mismatch (v1): "
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
        
        # Calculate and store checksums for corruption detection.
        # v2 covers canonical fields only (no derived views, no empty containers).
        # v1 kept for backward compatibility with older monitoring tools.
        session['_checksum'] = self._calculate_checksum(session)
        session['_checksum_v2'] = self._calculate_checksum_v2(session)

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
            # BEGIN IMMEDIATE acquires a write lock before reading,
            # preventing another writer from modifying between our SELECT and UPDATE.
            conn.execute('BEGIN IMMEDIATE')
            try:
                row = conn.execute(
                    'SELECT * FROM mmm_sessions WHERE session_id = ?',
                    (session_id,)
                ).fetchone()

                if not row:
                    conn.rollback()
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
            except Exception:
                conn.rollback()
                raise
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
                "SELECT session_id FROM mmm_sessions WHERE status IN ('RUNNING','PAUSED','BOTH_SIDES_UP','EXITING')"
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
                    json_extract(data_json, '$.ce_premium_collected')     AS ce_premium_collected,
                    json_extract(data_json, '$.pe_premium_collected')     AS pe_premium_collected,
                    json_extract(data_json, '$.ce.entry_fill_price')      AS ce_entry_fill,
                    json_extract(data_json, '$.pe.entry_fill_price')      AS pe_entry_fill,
                    json_extract(data_json, '$.lots')                     AS lots,
                    json_extract(data_json, '$.adjustment_history')       AS adjustment_history_json,
                    json_extract(data_json, '$.realized_pnl')             AS realized_pnl,
                    json_extract(data_json, '$.unrealized_pnl')           AS unrealized_pnl,
                    json_extract(data_json, '$.total_fees')               AS total_fees,
                    json_extract(data_json, '$.peak_pnl')                 AS peak_pnl,
                    json_extract(data_json, '$.last_heartbeat')           AS last_heartbeat,
                    json_extract(data_json, '$.next_heartbeat')           AS next_heartbeat,
                    json_extract(data_json, '$.expiry_time')              AS expiry_time,
                    json_extract(params_json, '$.adjustment_interval')    AS adjustment_interval,
                    json_extract(params_json, '$.expiry')                 AS expiry,
                    json_extract(params_json, '$.dte_category')           AS dte_category,
                    json_extract(data_json, '$._health_grade')            AS _health_grade,
                    json_extract(data_json, '$._gamma_regime')            AS _gamma_regime,
                    json_extract(data_json, '$._paused_reason')           AS _paused_reason,
                    json_extract(data_json, '$._regime_action')           AS _regime_action,
                    json_extract(data_json, '$._trend_tier')              AS _trend_tier,
                    json_extract(data_json, '$._breakeven_result.nearest_distance_pct') AS _be_nearest_pct,
                    json_extract(data_json, '$._breakeven_result.enabled')              AS _be_enabled,
                    json_extract(data_json, '$._gamma_result.nearest_distance_pct')    AS _gamma_nearest_pct,
                    json_extract(data_json, '$._gamma_result.enabled')                 AS _gamma_enabled,
                    json_extract(data_json, '$._gamma_result.gamma_zone')              AS _gamma_zone,
                    json_extract(data_json, '$._data_confidence')                      AS _data_confidence
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
                    'ce_premium_collected': self._get_side_premium(r, 'ce'),
                    'pe_premium_collected': self._get_side_premium(r, 'pe'),
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
                    'dte_category': r['dte_category'] or '',
                    '_health_grade': r['_health_grade'] or '',
                    '_gamma_regime': r['_gamma_regime'] or 'NORMAL',
                    '_paused_reason': r['_paused_reason'] or '',
                    '_regime_action': r['_regime_action'] or 'NORMAL',
                    '_trend_tier': r['_trend_tier'] if r['_trend_tier'] is not None else 0,
                    '_be_nearest_pct': r['_be_nearest_pct'],
                    '_be_enabled': bool(r['_be_enabled']),
                    '_gamma_nearest_pct': r['_gamma_nearest_pct'],
                    '_gamma_enabled': bool(r['_gamma_enabled']),
                    '_gamma_zone': r['_gamma_zone'] or 'SAFE',
                    '_data_confidence': r['_data_confidence'],
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

    def _get_side_premium(self, r, side: str) -> float:
        """
        Return ce/pe_premium_collected from a SQL summary row.

        Always derives the history-based total from entry_fill + adjustment_history,
        then returns whichever is larger: stored vs history-derived. This handles:
          - NULL stored (session predates this feature) → use history-derived
          - Partial stored (reset by a backend restart) → history-derived wins
          - Correct stored (normal operation) → stored wins if larger
        """
        LOT = 0.001
        stored = r[f'{side}_premium_collected'] or 0

        # History-derived total: initial entry leg
        try:
            fill = r[f'{side}_entry_fill'] or 0
        except (IndexError, KeyError):
            fill = 0
        try:
            lots = r['lots'] or r['ce_original_lots'] or 0
        except (IndexError, KeyError):
            lots = 0
        prem = fill * lots * LOT

        # History-derived total: sum adjustment_history for this side
        try:
            adj_json = r['adjustment_history_json']
        except (IndexError, KeyError):
            adj_json = None
        if adj_json:
            try:
                history = json.loads(adj_json) if isinstance(adj_json, str) else adj_json
                for entry in history:
                    if (entry.get('side') or '').upper() == side.upper():
                        prem += entry.get('premium_collected', 0) or 0
            except Exception:
                pass

        return round(max(stored, prem), 6)

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
            '_health_grade': session.get('_health_grade', ''),
            '_gamma_regime': session.get('_gamma_regime', 'NORMAL'),
            '_paused_reason': session.get('_paused_reason', ''),
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
