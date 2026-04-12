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
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from .mmm_state import derive_strategy_type

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
          strategy_type TEXT NOT NULL DEFAULT '0DTE',
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
        self._backfill_strategy_type_column()

    # =========================================================================
    # Database Setup
    # =========================================================================

    def _get_conn(self) -> sqlite3.Connection:
        """Get a new connection. WAL mode is set once in _init_db(); busy_timeout per-connection."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self):
        """Create tables and apply schema migrations if they don't exist."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            # WAL mode is DB-level — set once here, not on every connection open.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mmm_sessions (
                    session_id   TEXT PRIMARY KEY,
                    status       TEXT NOT NULL DEFAULT 'IDLE',
                    strategy_type TEXT NOT NULL DEFAULT '0DTE',
                    params_json  TEXT NOT NULL DEFAULT '{}',
                    data_json    TEXT NOT NULL,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL
                )
            ''')
            self._ensure_strategy_type_column(conn)
            # Indexes for active-session queries and time-based audit lookups.
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_mmm_sessions_status ON mmm_sessions(status)'
            )
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_mmm_sessions_updated_at ON mmm_sessions(updated_at)'
            )
            conn.commit()
            log.info(f"MMM SQLite storage ready: {self.db_path}")
        except Exception as e:
            log.error(f"Failed to init MMM DB: {e}")
            raise
        finally:
            conn.close()
        # Persist any pending retroactive fixes (FillSync double-booking correction).
        self._apply_retroactive_fixes_on_startup()

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
                    strategy_type = self._derive_strategy_type_legacy_aware(
                        session.get('strategy_type'),
                        params,
                    )
                    session['strategy_type'] = strategy_type
                    created = session.get('created_at', datetime.now(timezone.utc).isoformat())
                    updated = session.get('updated_at', datetime.now(timezone.utc).isoformat())

                    conn.execute('''
                        INSERT INTO mmm_sessions
                            (session_id, status, strategy_type, params_json, data_json, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id,
                        status,
                        strategy_type,
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

    def _apply_retroactive_fixes_on_startup(self):
        """
        One-time startup pass: persist the FillSync double-booking correction for
        any sessions where it was applied in-memory but never written back to the DB.

        Without this, every call to _row_to_session() re-applies the correction and
        changes realized_pnl, which then fails the v2 checksum (because the stored
        checksum was calculated against the uncorrected value) — producing a false
        [CORRUPTION RISK] alarm on every single read until the engine happens to call
        save_session().

        After this runs, data_json has _fillsync_double_booking_corrected=True and
        checksums match the corrected state. Subsequent _row_to_session() calls see
        the flag and short-circuit the correction immediately.

        Safe to run on every startup: skips sessions that are already patched.
        """
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            rows = conn.execute(
                'SELECT session_id, data_json, params_json FROM mmm_sessions'
            ).fetchall()
            patched = 0
            for row in rows:
                sid = row['session_id']
                try:
                    session = json.loads(row['data_json'])
                    if session.get('_fillsync_double_booking_corrected'):
                        continue  # Already patched — skip
                    # Apply authoritative params so checksum covers current params
                    session['params'] = json.loads(row['params_json'])
                    session['strategy_type'] = self._derive_strategy_type_legacy_aware(
                        session.get('strategy_type'),
                        session.get('params', {}),
                    )
                    # Apply the correction (idempotent; sets flag on session dict)
                    self._correct_fillsync_double_booking(session)
                    # Ensure flag is set even if no double-booking was found
                    session['_fillsync_double_booking_corrected'] = True
                    # Recalculate checksums against the now-correct state
                    session['_checksum'] = self._calculate_checksum(session)
                    session['_checksum_v2'] = self._calculate_checksum_v2(session)
                    now = datetime.now(timezone.utc).isoformat()
                    session['updated_at'] = now
                    conn.execute(
                        'UPDATE mmm_sessions SET data_json=?, params_json=?, updated_at=? '
                        'WHERE session_id=?',
                        (
                            json.dumps(session, default=str),
                            json.dumps(session.get('params', {}), default=str),
                            now,
                            sid,
                        )
                    )
                    patched += 1
                except Exception as e:
                    log.error(f"[startup] Failed to patch session {sid}: {e}")
            if patched:
                conn.commit()
                log.info(
                    f"[startup] FillSync double-booking fix persisted for {patched} session(s)"
                )
        except Exception as e:
            log.error(f"[startup] Retroactive fix scan failed: {e}")
        finally:
            conn.close()

    def _ensure_strategy_type_column(self, conn: sqlite3.Connection) -> None:
        """Schema migration: ensure canonical strategy_type column exists."""
        cols = {
            row['name']
            for row in conn.execute('PRAGMA table_info(mmm_sessions)').fetchall()
        }
        if 'strategy_type' not in cols:
            conn.execute(
                "ALTER TABLE mmm_sessions "
                "ADD COLUMN strategy_type TEXT NOT NULL DEFAULT '0DTE'"
            )
            log.info("[schema] Added mmm_sessions.strategy_type column")

    @staticmethod
    def _safe_json_dict(raw: Any) -> Dict[str, Any]:
        """Best-effort JSON decode that always returns a dict."""
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            decoded = json.loads(raw) if isinstance(raw, str) else raw
            return decoded if isinstance(decoded, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _parse_iso_timestamp(raw: Any) -> Optional[datetime]:
        """Best-effort ISO timestamp parse for stale-write arbitration."""
        if not raw:
            return None
        try:
            txt = str(raw).replace('Z', '+00:00')
            dt = datetime.fromisoformat(txt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def _derive_strategy_type_strict(self, strategy_type: Any, params: Dict[str, Any]) -> str:
        """Derive strategy_type honoring explicit strategy_type when present."""
        probe = dict(params or {})
        if strategy_type is not None:
            probe['strategy_type'] = strategy_type
        return derive_strategy_type(probe, fallback='0DTE')

    def _derive_strategy_type_legacy_aware(self, strategy_type: Any, params: Dict[str, Any]) -> str:
        """
        Derive strategy_type while handling migration default traps.

        If stored strategy_type is default 0DTE but legacy markers indicate
        another strategy, trust legacy markers (likely pre-migration row).
        """
        p = dict(params or {})
        legacy_only = derive_strategy_type(
            {
                '_preset_source': p.get('_preset_source'),
                'dte_category': p.get('dte_category'),
            },
            fallback='0DTE',
        )

        if strategy_type is None or str(strategy_type).strip() == '':
            return legacy_only

        strategy_upper = str(strategy_type).strip().upper()
        if strategy_upper == '0DTE' and legacy_only != '0DTE':
            return legacy_only

        return self._derive_strategy_type_strict(strategy_type, p)

    def _backfill_strategy_type_column(self) -> None:
        """Populate/repair strategy_type values for pre-migration sessions."""
        conn = self._get_conn()
        updated = 0
        try:
            rows = conn.execute(
                'SELECT session_id, strategy_type, params_json, data_json FROM mmm_sessions'
            ).fetchall()
            for row in rows:
                params = self._safe_json_dict(row['params_json'])
                data = self._safe_json_dict(row['data_json'])
                data_params = data.get('params', {}) if isinstance(data.get('params'), dict) else {}
                merged_params = dict(data_params)
                merged_params.update(params)

                explicit_in_data = data.get('strategy_type') if isinstance(data, dict) else None
                if explicit_in_data is not None:
                    inferred = self._derive_strategy_type_strict(explicit_in_data, merged_params)
                else:
                    inferred = self._derive_strategy_type_legacy_aware(
                        row['strategy_type'],
                        merged_params,
                    )

                current = row['strategy_type'] or ''
                if inferred != current:
                    conn.execute(
                        'UPDATE mmm_sessions SET strategy_type=? WHERE session_id=?',
                        (inferred, row['session_id']),
                    )
                    updated += 1

            if updated:
                conn.commit()
                log.info(f"[schema] Backfilled strategy_type for {updated} MMM session(s)")
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            log.error(f"[schema] strategy_type backfill failed: {e}")
        finally:
            conn.close()

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _validate_checksum_raw(self, session: Dict) -> bool:
        """
        Validate checksum against raw stored data — BEFORE any mutations.

        Must be called on the dict as loaded from data_json, before params_json
        override, premium backfill, or FillSync correction are applied. Those
        mutations change realized_pnl and params, which are covered by the v2
        checksum, so validating after them always produces false positives for
        sessions that need the FillSync fix or had a params hot-reload.

        Returns True if valid (or if no checksum is stored — legacy session).
        """
        session_id = session.get('session_id', '?')
        stored_v2 = session.get('_checksum_v2')
        if stored_v2:
            calc = self._calculate_checksum_v2(session)
            if calc != stored_v2:
                log.warning(
                    f"Session {session_id} v2 checksum mismatch (raw): "
                    f"stored={stored_v2}, calc={calc}. "
                    "Possible corruption or manual DB edit."
                )
                return False
            return True
        stored_v1 = session.get('_checksum')
        if not stored_v1:
            return True  # No checksum stored — legacy session, considered valid
        calc = self._calculate_checksum(session)
        if calc != stored_v1:
            log.warning(
                f"Session {session_id} v1 checksum mismatch (raw): "
                f"stored={stored_v1}, calc={calc}."
            )
            return False
        return True

    def _row_to_session(self, row) -> Dict:
        """
        Convert a DB row back to the expected session dict.

        Checksum validation runs FIRST against the raw stored data (before any
        mutations) so it compares against the exact state that was checksummed at
        save time. Mutations applied afterwards (params override, premium backfill,
        FillSync correction) legitimately change fields covered by the checksum —
        validating after them would produce false-positive [CORRUPTION RISK] alarms.
        """
        session = json.loads(row['data_json'])
        # Validate against raw state — BEFORE any mutations
        if not self._validate_checksum_raw(session):
            session['_checksum_warning'] = True
            log.critical(
                f"[CORRUPTION RISK] Session {session.get('session_id', '?')} checksum "
                f"mismatch on raw DB data — possible corruption or manual edit. "
                f"Monitor will emit safety alert on next heartbeat."
            )
        else:
            session.pop('_checksum_warning', None)
        # Apply authoritative overrides (may mutate params and realized_pnl)
        session['params'] = json.loads(row['params_json'])
        self._backfill_session_side_premiums(session)
        self._correct_fillsync_double_booking(session)
        stored_strategy = row['strategy_type'] if 'strategy_type' in row.keys() else None
        session['strategy_type'] = self._derive_strategy_type_legacy_aware(
            stored_strategy,
            session.get('params', {}),
        )
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

        NOTE: For sessions with a _fill_ledger, this fix is no longer needed —
        the ledger's dedup by fill_id prevents double-booking entirely.
        Kept for backward compatibility with pre-ledger sessions only.
        """
        if session.get('_fillsync_double_booking_corrected'):
            return  # Already corrected — idempotent

        # Sessions with fill ledger don't need this fix
        if session.get('_fill_ledger'):
            session['_fillsync_double_booking_corrected'] = True
            return

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
                if (est is None or est == 0) and abs(corr - actual) < 1e-8 and abs(corr) > 1e-8:
                    total_over += corr
                    count += 1
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

        Uses BEGIN IMMEDIATE to serialize concurrent writes — prevents a
        save_session() from interleaving with an in-progress update_session().

        Checksums are computed on a shallow copy so the caller's dict is only
        mutated (updated_at, _checksum, _checksum_v2) after a confirmed DB write,
        not before.

        Args:
            session: Complete session dictionary (must have 'session_id')

        Returns:
            session_id
        """
        session_id = session.get('session_id')
        if not session_id:
            raise ValueError("Session must have a session_id")

        now = datetime.now(timezone.utc).isoformat()

        # Compute checksums on a copy — don't mutate the caller's dict until
        # after the DB write succeeds (prevents stale checksum fields on the
        # in-memory session if the write fails).
        s = dict(session)
        s['updated_at'] = now

        status = s.get('strategy_status', 'IDLE')
        params = s.get('params', {})
        created = s.get('created_at', now)
        strategy_type = self._derive_strategy_type_strict(
            s.get('strategy_type'),
            params,
        )

        conn = self._get_conn()
        try:
            # BEGIN IMMEDIATE acquires a write lock upfront, serializing this save
            # against any concurrent update_session() calls (which also use BEGIN
            # IMMEDIATE). Without this, a save_session() UPSERT could overwrite
            # changes just committed by update_session() (lost update race).
            conn.execute('BEGIN IMMEDIATE')

            # Hot-reload param preservation: read the current params_json from DB
            # INSIDE this transaction so any update_session() hot-reload changes that
            # landed between when the monitor last loaded the session and now are not
            # overwritten.  For new sessions (no row yet) fall back to session's own
            # params.  Note: the _save_session caller in mmm_monitor.py also attempts
            # this merge, but that read is outside the transaction and subject to a
            # race.  This inner read is the authoritative, race-free version.
            existing_row = conn.execute(
                'SELECT params_json, updated_at FROM mmm_sessions WHERE session_id = ?',
                (session_id,)
            ).fetchone()
            if existing_row:
                existing_params = self._safe_json_dict(existing_row['params_json'])
                existing_updated = self._parse_iso_timestamp(existing_row['updated_at'])
                caller_updated = self._parse_iso_timestamp(session.get('updated_at'))

                # Preserve DB params only if DB row is strictly newer than caller snapshot.
                # This keeps hot-reload race protection while still allowing intentional
                # param changes through save_session on up-to-date caller objects.
                if (
                    existing_updated
                    and caller_updated
                    and existing_updated > caller_updated
                ):
                    final_params = existing_params
                    log.debug(
                        f"[{session_id}] save_session using newer DB params_json "
                        f"(caller_updated={session.get('updated_at')}, db_updated={existing_row['updated_at']})"
                    )
                else:
                    final_params = params
            else:
                final_params = params
            # Keep data_json consistent with the authoritative params
            s['params'] = final_params
            strategy_type = self._derive_strategy_type_strict(
                s.get('strategy_type'),
                final_params,
            )
            s['strategy_type'] = strategy_type

            # v2 covers canonical fields only (no derived views, no empty containers).
            # v1 kept for backward compatibility with older monitoring tools.
            s['_checksum'] = self._calculate_checksum(s)
            s['_checksum_v2'] = self._calculate_checksum_v2(s)

            conn.execute('''
                INSERT INTO mmm_sessions
                    (session_id, status, strategy_type, params_json, data_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status      = excluded.status,
                    strategy_type = excluded.strategy_type,
                    params_json = excluded.params_json,
                    data_json   = excluded.data_json,
                    updated_at  = excluded.updated_at
            ''', (
                session_id,
                status,
                strategy_type,
                json.dumps(final_params, default=str),
                json.dumps(s, default=str),
                created,
                now,
            ))
            conn.commit()
            log.debug(f"Saved MMM session {session_id} (status: {status})")
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            log.error(f"Failed to save session {session_id}: {e}")
            raise
        finally:
            conn.close()

        # Only mutate caller's dict after a confirmed write.
        session['updated_at'] = now
        session['_checksum'] = s['_checksum']
        session['_checksum_v2'] = s['_checksum_v2']
        session['strategy_type'] = strategy_type

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
            # _checksum_warning is already set/cleared by _row_to_session() based on
            # the raw DB state (pre-mutation). No second validation needed here —
            # re-validating post-mutation would produce false positives for every
            # FillSync-affected session and every hot-reloaded session.
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
                    "SELECT * FROM mmm_sessions WHERE status IN ('RUNNING','PAUSED','BOTH_SIDES_UP','EXITING') "
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
                active_statuses = {
                    'RUNNING',
                    'PAUSED',
                    'BOTH_SIDES_UP',
                    'STARTING',
                    'PARTIAL_ENTRY',
                    'EXITING',
                }
                current_strategy = self._derive_strategy_type_strict(
                    session.get('strategy_type'),
                    session.get('params', {}),
                )
                requested_strategy = updates.get('strategy_type')
                if requested_strategy is not None:
                    requested_strategy = self._derive_strategy_type_strict(
                        requested_strategy,
                        session.get('params', {}),
                    )
                    if (
                        session.get('strategy_status', 'IDLE') in active_statuses
                        and requested_strategy != current_strategy
                    ):
                        raise ValueError(
                            "strategy_type is immutable while session is active; "
                            "create a new session for a different strategy"
                        )

                # Deep merge for nested dicts (ce, pe, params)
                for key, value in updates.items():
                    if key in ('ce', 'pe', 'params') and isinstance(value, dict) and isinstance(session.get(key), dict):
                        session[key].update(value)
                    else:
                        session[key] = value

                # Canonical strategy identity is immutable post-creation.
                session['strategy_type'] = requested_strategy or current_strategy

                now = datetime.now(timezone.utc).isoformat()
                session['updated_at'] = now

                # Recalculate checksums after merging updates so get_session won't
                # flag this as corrupted on the next read.
                session['_checksum'] = self._calculate_checksum(session)
                session['_checksum_v2'] = self._calculate_checksum_v2(session)
                session.pop('_checksum_warning', None)

                status = session.get('strategy_status', 'IDLE')
                params = session.get('params', {})
                strategy_type = self._derive_strategy_type_strict(
                    session.get('strategy_type'),
                    params,
                )
                session['strategy_type'] = strategy_type

                conn.execute('''
                    UPDATE mmm_sessions SET
                        status      = ?,
                        strategy_type = ?,
                        params_json = ?,
                        data_json   = ?,
                        updated_at  = ?
                    WHERE session_id = ?
                ''', (
                    status,
                    strategy_type,
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
                "WHERE status IN ('RUNNING','PAUSED','BOTH_SIDES_UP','EXITING')"
                if active_only else ""
            )
            rows = conn.execute(f'''
                SELECT
                    session_id,
                    status,
                    strategy_type,
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
                    json_extract(params_json, '$._preset_source')         AS _preset_source,
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
                    json_extract(data_json, '$._data_confidence')                      AS _data_confidence,
                    json_extract(data_json, '$.perp_hedge.realized_pnl')               AS perp_realized_pnl,
                    json_extract(data_json, '$.perp_hedge.unrealized_pnl')             AS perp_unrealized_pnl,
                    json_extract(data_json, '$._reverse.net_pnl')                      AS reverse_net_pnl
                FROM mmm_sessions
                {where}
                ORDER BY created_at DESC
            ''').fetchall()

            summaries = []
            for r in rows:
                realized = r['realized_pnl'] or 0
                unrealized = r['unrealized_pnl'] or 0
                fees = r['total_fees'] or 0
                strategy_type = self._derive_strategy_type_legacy_aware(
                    r['strategy_type'],
                    {
                        'dte_category': r['dte_category'],
                        '_preset_source': r['_preset_source'],
                    },
                )
                summaries.append({
                    'session_id': r['session_id'],
                    'status': r['status'] or 'IDLE',
                    'mode': r['mode'] or 'fresh',
                    'strategy_type': strategy_type,
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
                    # BUG-C4 fix: include perp + reverse P&L in net_pnl
                    'net_pnl': realized + unrealized - fees
                            + (r['perp_realized_pnl'] or 0) + (r['perp_unrealized_pnl'] or 0)
                            + (r['reverse_net_pnl'] or 0),
                    'peak_pnl': r['peak_pnl'] or 0,
                    'adjustment_interval': r['adjustment_interval'] or 300,
                    'last_heartbeat': r['last_heartbeat'],
                    'next_heartbeat': r['next_heartbeat'],
                    'expiry': r['expiry'] or '',
                    'expiry_time': r['expiry_time'],
                    'dte_category': r['dte_category'] or '',
                    '_preset_source': r['_preset_source'] or '',
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
            # Fallback to the side-specific original_lots — ce_original_lots for CE,
            # pe_original_lots for PE. Using ce_original_lots for both sides was a bug:
            # it produced wrong PE premiums whenever lots was NULL and ce/pe lot counts differ.
            side_lots_key = f'{side}_original_lots'
            lots = r['lots'] or r[side_lots_key] or 0
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
        """
        Fallback: extract summary from fully deserialized session.

        Must stay in sync with the json_extract primary path in list_session_summaries().
        When adding a field to the primary path, add the equivalent here.
        """
        ce = session.get('ce', {})
        pe = session.get('pe', {})
        realized = session.get('realized_pnl', 0)
        unrealized = session.get('unrealized_pnl', 0)
        fees = session.get('total_fees', 0)
        perp = session.get('perp_hedge', {})
        perp_pnl = (perp.get('realized_pnl', 0) or 0) + (perp.get('unrealized_pnl', 0) or 0)
        reverse_pnl = float(session.get('_reverse', {}).get('net_pnl', 0) or 0)
        # _breakeven_result and _gamma_result are nested dicts written by the health modules
        be = session.get('_breakeven_result') or {}
        gamma_result = session.get('_gamma_result') or {}
        return {
            'session_id': session.get('session_id'),
            'status': session.get('strategy_status', 'IDLE'),
            'mode': session.get('mode', 'fresh'),
            'strategy_type': self._derive_strategy_type_legacy_aware(
                session.get('strategy_type'),
                session.get('params', {}),
            ),
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
            # _backfill_session_side_premiums() has already run on sessions from list_sessions()
            'ce_premium_collected': session.get('ce_premium_collected', 0),
            'pe_premium_collected': session.get('pe_premium_collected', 0),
            'realized_pnl': realized,
            'unrealized_pnl': unrealized,
            'total_fees': fees,
            'net_pnl': realized + unrealized - fees + perp_pnl + reverse_pnl,
            'peak_pnl': session.get('peak_pnl', 0),
            'adjustment_interval': session.get('params', {}).get('adjustment_interval', 300),
            'last_heartbeat': session.get('last_heartbeat'),
            'next_heartbeat': session.get('next_heartbeat'),
            'expiry': session.get('params', {}).get('expiry', ''),
            'expiry_time': session.get('expiry_time'),
            'dte_category': session.get('params', {}).get('dte_category', ''),
            '_preset_source': session.get('params', {}).get('_preset_source', ''),
            '_health_grade': session.get('_health_grade', ''),
            '_gamma_regime': session.get('_gamma_regime', 'NORMAL'),
            '_paused_reason': session.get('_paused_reason', ''),
            '_regime_action': session.get('_regime_action', 'NORMAL'),
            '_trend_tier': session.get('_trend_tier') if session.get('_trend_tier') is not None else 0,
            '_be_nearest_pct': be.get('nearest_distance_pct'),
            '_be_enabled': bool(be.get('enabled', False)),
            '_gamma_nearest_pct': gamma_result.get('nearest_distance_pct'),
            '_gamma_enabled': bool(gamma_result.get('enabled', False)),
            '_gamma_zone': gamma_result.get('gamma_zone', 'SAFE') or 'SAFE',
            '_data_confidence': session.get('_data_confidence'),
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


_storage_lock = threading.Lock()


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
        # BUG-C7 fix: thread-safe double-checked lock
        with _storage_lock:
            if _storage_instance is None:
                _storage_instance = MMMStorage(storage_path)
    return _storage_instance
