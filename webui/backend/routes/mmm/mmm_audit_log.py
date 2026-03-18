"""
MMM Trade Audit Log — Institutional-Grade Trade Ledger

Two write-only tables in mmm_sessions.db:
  - position_audit_log : every order fill (BUY/SELL) that touches real money
  - session_event_log  : operational state changes (regime, margin, params, lifecycle)

Design guarantees:
  - enqueue_trade() / enqueue_event() complete in < 1µs (queue.put_nowait)
  - Background daemon thread batches writes to SQLite (WAL mode)
  - INSERT OR IGNORE on idempotency_key prevents duplicate rows on crash/restart
  - No UPDATE or DELETE is ever issued against these tables
  - atexit handler flushes remaining queue entries on backend shutdown
  - Read connections are separate from the writer — no lock contention

Usage:
    from .mmm_audit_log import get_audit_log, get_event_log

    get_audit_log().enqueue_trade(session_id=..., action='SELL', ...)
    get_event_log().enqueue_event(session_id=..., event_category='REGIME', ...)

Created: 2026-03-18
"""

import atexit
import json
import logging
import os
import queue
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

log = logging.getLogger('mmm_audit_log')

# ── IST timezone ──────────────────────────────────────────────────────────────
try:
    from zoneinfo import ZoneInfo as _ZoneInfo
    _IST = _ZoneInfo('Asia/Kolkata')
except Exception:
    _IST = None

LOT_SIZE_BTC = 0.001

# ── DB path — same file as mmm_storage.py ────────────────────────────────────
_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data'
)
DB_FILE = os.path.join(_DATA_DIR, 'mmm_sessions.db')

# ── Writer config ─────────────────────────────────────────────────────────────
_BATCH_SIZE   = 10      # flush after this many queued entries
_FLUSH_SECS   = 2.0     # flush at least this often
_MAX_QUEUE    = 2000    # drop with error log above this (practically impossible)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_ist(utc_dt: datetime) -> str:
    """Return ISO8601 string in IST (+05:30). Falls back to manual offset."""
    try:
        if _IST:
            return utc_dt.astimezone(_IST).isoformat()
    except Exception:
        pass
    ist = utc_dt + timedelta(hours=5, minutes=30)
    return ist.strftime('%Y-%m-%dT%H:%M:%S+05:30')


def _safe_float(v, default=None):
    try:
        f = float(v)
        return f if f == f else default   # NaN guard
    except Exception:
        return default


def _safe_int(v, default=None):
    try:
        return int(v)
    except Exception:
        return default


# ─────────────────────────────────────────────────────────────────────────────
# Schema SQL
# ─────────────────────────────────────────────────────────────────────────────

_CREATE_POSITION_AUDIT = """
CREATE TABLE IF NOT EXISTS position_audit_log (
    id                      INTEGER  PRIMARY KEY AUTOINCREMENT,
    idempotency_key         TEXT,
    session_id              TEXT     NOT NULL,
    expiry                  TEXT     NOT NULL DEFAULT '',
    timestamp_ist           TEXT     NOT NULL,
    created_at              TEXT     NOT NULL,
    action                  TEXT     NOT NULL,
    option_type             TEXT     NOT NULL,
    strike                  INTEGER,
    order_id                TEXT,
    quantity_requested      INTEGER  NOT NULL DEFAULT 0,
    quantity_filled         INTEGER  NOT NULL,
    is_partial_fill         INTEGER  NOT NULL DEFAULT 0,
    premium                 REAL     NOT NULL,
    gross_premium_usd       REAL     NOT NULL,
    closing_entry_premium   REAL,
    closing_entry_lots      INTEGER,
    realized_pnl_usd        REAL,
    event_type              TEXT     NOT NULL,
    adj_type                TEXT,
    mechanism               TEXT,
    aggressor_side          TEXT,
    trigger_premium         REAL,
    trigger_snapshot_at     REAL,
    loss_covered_usd        REAL,
    whipsaw_state           TEXT,
    margin_tier             TEXT,
    regime_action           TEXT,
    spot_price_usd          REAL,
    remark                  TEXT     NOT NULL DEFAULT '',
    written_at              TEXT     NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pal_idempotency
    ON position_audit_log (idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pal_session_time
    ON position_audit_log (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_pal_session_strike
    ON position_audit_log (session_id, strike, option_type);
"""

_CREATE_SESSION_EVENTS = """
CREATE TABLE IF NOT EXISTS session_event_log (
    id              INTEGER  PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT     NOT NULL,
    timestamp_ist   TEXT     NOT NULL,
    created_at      TEXT     NOT NULL,
    event_category  TEXT     NOT NULL,
    event_type      TEXT     NOT NULL,
    severity        TEXT     NOT NULL DEFAULT 'INFO',
    details         TEXT,
    remark          TEXT     NOT NULL DEFAULT '',
    written_at      TEXT     NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sel_session_time
    ON session_event_log (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sel_session_category
    ON session_event_log (session_id, event_category);
"""

_INSERT_TRADE = """
INSERT OR IGNORE INTO position_audit_log (
    idempotency_key, session_id, expiry, timestamp_ist, created_at,
    action, option_type, strike, order_id,
    quantity_requested, quantity_filled, is_partial_fill,
    premium, gross_premium_usd,
    closing_entry_premium, closing_entry_lots, realized_pnl_usd,
    event_type, adj_type, mechanism,
    aggressor_side, trigger_premium, trigger_snapshot_at, loss_covered_usd,
    whipsaw_state, margin_tier, regime_action, spot_price_usd,
    remark
) VALUES (
    :idempotency_key, :session_id, :expiry, :timestamp_ist, :created_at,
    :action, :option_type, :strike, :order_id,
    :quantity_requested, :quantity_filled, :is_partial_fill,
    :premium, :gross_premium_usd,
    :closing_entry_premium, :closing_entry_lots, :realized_pnl_usd,
    :event_type, :adj_type, :mechanism,
    :aggressor_side, :trigger_premium, :trigger_snapshot_at, :loss_covered_usd,
    :whipsaw_state, :margin_tier, :regime_action, :spot_price_usd,
    :remark
)
"""

_INSERT_EVENT = """
INSERT INTO session_event_log
    (session_id, timestamp_ist, created_at, event_category, event_type,
     severity, details, remark)
VALUES
    (:session_id, :timestamp_ist, :created_at, :event_category, :event_type,
     :severity, :details, :remark)
"""


# ─────────────────────────────────────────────────────────────────────────────
# Trade Audit Log
# ─────────────────────────────────────────────────────────────────────────────

class MMMTradeAuditLog:
    """
    Write-only trade ledger. Singleton. One background daemon writer thread.
    All reads use separate short-lived connections.
    """

    def __init__(self, db_path: str = DB_FILE):
        self._db_path = db_path
        self._queue: queue.Queue = queue.Queue(maxsize=_MAX_QUEUE)
        self._init_schema()
        t = threading.Thread(
            target=self._writer_loop,
            name='mmm-audit-writer',
            daemon=True,
        )
        t.start()
        atexit.register(self._flush_on_shutdown)

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_schema(self):
        try:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript(_CREATE_POSITION_AUDIT)
            conn.commit()
            conn.close()
        except Exception:
            log.exception('audit_log: schema init failed')

    # ── Public write API ──────────────────────────────────────────────────────

    def enqueue_trade(
        self,
        session_id: str,
        action: str,
        option_type: str,
        strike,                        # int or None (None for PERP)
        quantity_requested: int,
        quantity_filled: int,
        premium: float,
        event_type: str,
        remark: str,
        order_id: str = '',
        expiry: str = '',
        adj_type: str = '',
        mechanism: str = '',
        aggressor_side: str = '',
        trigger_premium: float = 0.0,
        trigger_snapshot_at: float = 0.0,
        loss_covered_usd: float = 0.0,
        closing_entry_premium: float = 0.0,
        closing_entry_lots: int = 0,
        realized_pnl_usd: float = 0.0,
        whipsaw_state: str = '',
        margin_tier: str = '',
        regime_action: str = '',
        spot_price_usd: float = 0.0,
        idempotency_key: str = '',
    ) -> None:
        """
        Fire-and-forget. Returns immediately. Never raises.
        Only records confirmed exchange fills — never called on order failure.
        """
        try:
            now_utc = datetime.now(timezone.utc)
            qty_req = max(0, _safe_int(quantity_requested, 0))
            qty_fill = max(0, _safe_int(quantity_filled, 0))
            prem = _safe_float(premium, 0.0)
            gross = qty_fill * prem * LOT_SIZE_BTC

            # Auto-build idempotency key if not provided
            if not idempotency_key:
                oid = str(order_id).strip()
                if oid:
                    idempotency_key = f'{session_id}:{oid}:{action.upper()}'
                elif mechanism in ('import', 'adopt'):
                    ts_short = now_utc.isoformat()[:19]
                    idempotency_key = (
                        f'{session_id}:import:{option_type.lower()}:{strike}:{ts_short}'
                    )
                # else: no idempotency key — INSERT OR IGNORE won't deduplicate,
                # but these cases (perp, operator) don't replay on restart anyway.

            # For BUY rows: compute realized P&L if not provided
            if action.upper() == 'BUY' and realized_pnl_usd == 0.0:
                ep = _safe_float(closing_entry_premium, 0.0)
                if ep and ep > 0 and qty_fill > 0:
                    realized_pnl_usd = (ep - prem) * qty_fill * LOT_SIZE_BTC

            entry = {
                'idempotency_key':      idempotency_key or None,
                'session_id':           session_id,
                'expiry':               expiry or '',
                'timestamp_ist':        _to_ist(now_utc),
                'created_at':           now_utc.isoformat(),
                'action':               action.upper(),
                'option_type':          option_type.upper(),
                'strike':               _safe_int(strike) if strike is not None else None,
                'order_id':             str(order_id) if order_id else None,
                'quantity_requested':   qty_req,
                'quantity_filled':      qty_fill,
                'is_partial_fill':      1 if qty_fill < qty_req else 0,
                'premium':              prem,
                'gross_premium_usd':    gross,
                'closing_entry_premium': _safe_float(closing_entry_premium) or None,
                'closing_entry_lots':   _safe_int(closing_entry_lots) or None,
                'realized_pnl_usd':     _safe_float(realized_pnl_usd) or None,
                'event_type':           event_type,
                'adj_type':             adj_type or None,
                'mechanism':            mechanism or None,
                'aggressor_side':       aggressor_side or None,
                'trigger_premium':      _safe_float(trigger_premium) or None,
                'trigger_snapshot_at':  _safe_float(trigger_snapshot_at) or None,
                'loss_covered_usd':     _safe_float(loss_covered_usd) or None,
                'whipsaw_state':        whipsaw_state or None,
                'margin_tier':          margin_tier or None,
                'regime_action':        str(regime_action) if regime_action else None,
                'spot_price_usd':       _safe_float(spot_price_usd) or None,
                'remark':               remark or '',
                '_table':               'trade',
            }

            try:
                self._queue.put_nowait(entry)
            except queue.Full:
                log.error(
                    'audit_log queue FULL — trade entry DROPPED '
                    '(session=%s action=%s event=%s)',
                    session_id, action, event_type,
                )
        except Exception:
            log.exception('audit_log.enqueue_trade() unexpectedly raised')

    # ── Background writer ─────────────────────────────────────────────────────

    def _writer_loop(self):
        import time
        conn = None
        batch = []
        last_flush = time.monotonic()

        def _get_conn():
            nonlocal conn
            if conn is None:
                c = sqlite3.connect(self._db_path, timeout=10)
                c.execute('PRAGMA journal_mode=WAL')
                c.execute('PRAGMA synchronous=NORMAL')
                conn = c
            return conn

        while True:
            try:
                # Block until an entry arrives (or timeout for periodic flush)
                try:
                    entry = self._queue.get(timeout=_FLUSH_SECS)
                    batch.append(entry)
                    # Drain any additional entries without waiting
                    while len(batch) < _BATCH_SIZE:
                        try:
                            batch.append(self._queue.get_nowait())
                        except queue.Empty:
                            break
                except queue.Empty:
                    pass

                now = time.monotonic()
                if batch and (len(batch) >= _BATCH_SIZE or now - last_flush >= _FLUSH_SECS):
                    try:
                        c = _get_conn()
                        c.executemany(_INSERT_TRADE, batch)
                        c.commit()
                        batch.clear()
                        last_flush = now
                    except sqlite3.Error as e:
                        log.error('audit_log writer DB error: %s — will retry next cycle', e)
                        try:
                            conn.rollback()
                        except Exception:
                            pass

            except Exception:
                log.exception('audit_log writer_loop unexpected error')

    def _flush_on_shutdown(self):
        """atexit: write remaining queue entries before process exits."""
        try:
            remaining = []
            while True:
                try:
                    remaining.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if not remaining:
                return
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executemany(_INSERT_TRADE, remaining)
            conn.commit()
            conn.close()
            log.info('audit_log: flushed %d entries on shutdown', len(remaining))
        except Exception:
            log.exception('audit_log shutdown flush failed')

    # ── Read API ──────────────────────────────────────────────────────────────

    def query_session(
        self,
        session_id: str,
        side: Optional[str] = None,
        event_type: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
    ) -> List[Dict]:
        """
        Return rows from position_audit_log for a session.
        New read connection per call — never blocks the writer.
        """
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA query_only=ON')
            where = ['session_id = ?']
            params: List[Any] = [session_id]
            if side:
                where.append('option_type = ?')
                params.append(side.upper())
            if event_type:
                where.append('event_type = ?')
                params.append(event_type.upper())
            offset = max(0, (page - 1) * limit)
            params += [limit, offset]
            cur = conn.execute(
                f"SELECT * FROM position_audit_log "
                f"WHERE {' AND '.join(where)} "
                f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception:
            log.exception('audit_log.query_session() failed')
            return []

    def get_strike_summary(self, session_id: str) -> List[Dict]:
        """
        Aggregate per (strike, option_type):
          total_sell_qty, total_buy_qty, avg_sell_price, avg_buy_price,
          realized_pnl_usd (SUM of stored per-close values),
          open_qty, trade_count, status (ACTIVE/CLOSED).
        """
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA query_only=ON')
            cur = conn.execute("""
                SELECT
                    COALESCE(strike, 0)  AS strike,
                    option_type,
                    SUM(CASE WHEN action='SELL' THEN quantity_filled ELSE 0 END)
                        AS total_sell_qty,
                    SUM(CASE WHEN action='BUY'  THEN quantity_filled ELSE 0 END)
                        AS total_buy_qty,
                    SUM(CASE WHEN action='SELL' THEN quantity_filled * premium ELSE 0.0 END)
                        / NULLIF(SUM(CASE WHEN action='SELL' THEN quantity_filled ELSE 0 END), 0)
                        AS avg_sell_price,
                    SUM(CASE WHEN action='BUY'  THEN quantity_filled * premium ELSE 0.0 END)
                        / NULLIF(SUM(CASE WHEN action='BUY'  THEN quantity_filled ELSE 0 END), 0)
                        AS avg_buy_price,
                    SUM(COALESCE(realized_pnl_usd, 0.0))
                        AS realized_pnl_usd,
                    (  SUM(CASE WHEN action='SELL' THEN quantity_filled ELSE 0 END)
                     - SUM(CASE WHEN action='BUY'  THEN quantity_filled ELSE 0 END))
                        AS open_qty,
                    COUNT(*) AS trade_count,
                    MIN(created_at) AS first_trade_at,
                    MAX(created_at) AS last_trade_at
                FROM position_audit_log
                WHERE session_id = ?
                  AND option_type IN ('CE', 'PE')
                GROUP BY strike, option_type
                ORDER BY strike, option_type
            """, [session_id])
            rows = []
            for r in cur.fetchall():
                row = dict(r)
                row['status'] = 'ACTIVE' if (row.get('open_qty') or 0) > 0 else 'CLOSED'
                rows.append(row)
            conn.close()
            return rows
        except Exception:
            log.exception('audit_log.get_strike_summary() failed')
            return []

    def get_pnl_attribution(self, session_id: str) -> Dict:
        """
        P&L breakdown by event_type.
        total_realized_pnl_usd must equal session['realized_pnl'] if audit is complete.
        """
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA query_only=ON')
            cur = conn.execute("""
                SELECT
                    event_type,
                    SUM(COALESCE(realized_pnl_usd, 0.0)) AS pnl_usd,
                    SUM(CASE WHEN action='SELL' THEN gross_premium_usd ELSE 0.0 END)
                        AS premium_collected_usd,
                    SUM(CASE WHEN action='BUY'  THEN gross_premium_usd ELSE 0.0 END)
                        AS premium_paid_usd,
                    COUNT(*) AS trade_count
                FROM position_audit_log
                WHERE session_id = ?
                GROUP BY event_type
                ORDER BY event_type
            """, [session_id])
            by_event = [dict(r) for r in cur.fetchall()]
            total_pnl = sum(r.get('pnl_usd', 0) or 0 for r in by_event)
            total_collected = sum(r.get('premium_collected_usd', 0) or 0 for r in by_event)
            total_paid = sum(r.get('premium_paid_usd', 0) or 0 for r in by_event)
            conn.close()
            return {
                'session_id': session_id,
                'by_event_type': by_event,
                'total_realized_pnl_usd': round(total_pnl, 6),
                'total_premium_collected_usd': round(total_collected, 6),
                'total_premium_paid_usd': round(total_paid, 6),
                'net_premium_usd': round(total_collected - total_paid, 6),
            }
        except Exception:
            log.exception('audit_log.get_pnl_attribution() failed')
            return {'session_id': session_id, 'error': 'query failed'}

    def get_trade_count(self, session_id: str) -> int:
        """Quick count of audit rows for a session."""
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.execute('PRAGMA query_only=ON')
            (count,) = conn.execute(
                'SELECT COUNT(*) FROM position_audit_log WHERE session_id = ?',
                [session_id],
            ).fetchone()
            conn.close()
            return count
        except Exception:
            return 0


# ─────────────────────────────────────────────────────────────────────────────
# Session Event Log
# ─────────────────────────────────────────────────────────────────────────────

class MMMSessionEventLog:
    """
    Write-only operational event log.
    Captures regime transitions, margin tier changes, param hot-reloads,
    session lifecycle, and safety events.
    """

    def __init__(self, db_path: str = DB_FILE):
        self._db_path = db_path
        self._queue: queue.Queue = queue.Queue(maxsize=_MAX_QUEUE)
        self._init_schema()
        t = threading.Thread(
            target=self._writer_loop,
            name='mmm-event-writer',
            daemon=True,
        )
        t.start()
        atexit.register(self._flush_on_shutdown)

    def _init_schema(self):
        try:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript(_CREATE_SESSION_EVENTS)
            conn.commit()
            conn.close()
        except Exception:
            log.exception('event_log: schema init failed')

    def enqueue_event(
        self,
        session_id: str,
        event_category: str,
        event_type: str,
        remark: str,
        severity: str = 'INFO',
        details: Optional[Dict] = None,
    ) -> None:
        """Fire-and-forget. Never raises."""
        try:
            now_utc = datetime.now(timezone.utc)
            entry = {
                'session_id':     session_id,
                'timestamp_ist':  _to_ist(now_utc),
                'created_at':     now_utc.isoformat(),
                'event_category': event_category,
                'event_type':     event_type,
                'severity':       severity.upper(),
                'details':        json.dumps(details, default=str) if details else None,
                'remark':         remark or '',
                '_table':         'event',
            }
            try:
                self._queue.put_nowait(entry)
            except queue.Full:
                log.error(
                    'event_log queue FULL — entry dropped (session=%s category=%s)',
                    session_id, event_category,
                )
        except Exception:
            log.exception('event_log.enqueue_event() unexpectedly raised')

    def _writer_loop(self):
        import time
        conn = None
        batch = []
        last_flush = time.monotonic()

        def _get_conn():
            nonlocal conn
            if conn is None:
                c = sqlite3.connect(self._db_path, timeout=10)
                c.execute('PRAGMA journal_mode=WAL')
                c.execute('PRAGMA synchronous=NORMAL')
                conn = c
            return conn

        while True:
            try:
                try:
                    entry = self._queue.get(timeout=_FLUSH_SECS)
                    batch.append(entry)
                    while len(batch) < _BATCH_SIZE:
                        try:
                            batch.append(self._queue.get_nowait())
                        except queue.Empty:
                            break
                except queue.Empty:
                    pass

                now = time.monotonic()
                if batch and (len(batch) >= _BATCH_SIZE or now - last_flush >= _FLUSH_SECS):
                    try:
                        c = _get_conn()
                        c.executemany(_INSERT_EVENT, batch)
                        c.commit()
                        batch.clear()
                        last_flush = now
                    except sqlite3.Error as e:
                        log.error('event_log writer DB error: %s', e)
                        try:
                            conn.rollback()
                        except Exception:
                            pass
            except Exception:
                log.exception('event_log writer_loop unexpected error')

    def _flush_on_shutdown(self):
        try:
            remaining = []
            while True:
                try:
                    remaining.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if not remaining:
                return
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executemany(_INSERT_EVENT, remaining)
            conn.commit()
            conn.close()
            log.info('event_log: flushed %d entries on shutdown', len(remaining))
        except Exception:
            log.exception('event_log shutdown flush failed')

    def query_session(
        self,
        session_id: str,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA query_only=ON')
            where = ['session_id = ?']
            params: List[Any] = [session_id]
            if category:
                where.append('event_category = ?')
                params.append(category.upper())
            if severity:
                where.append('severity = ?')
                params.append(severity.upper())
            params.append(limit)
            cur = conn.execute(
                f"SELECT * FROM session_event_log "
                f"WHERE {' AND '.join(where)} "
                f"ORDER BY created_at DESC LIMIT ?",
                params,
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception:
            log.exception('event_log.query_session() failed')
            return []


# ─────────────────────────────────────────────────────────────────────────────
# Singletons
# ─────────────────────────────────────────────────────────────────────────────

_trade_log_instance: Optional[MMMTradeAuditLog] = None
_event_log_instance: Optional[MMMSessionEventLog] = None
_singleton_lock = threading.Lock()


def get_audit_log() -> MMMTradeAuditLog:
    """Return the singleton MMMTradeAuditLog. Thread-safe, lazy-initialised."""
    global _trade_log_instance
    if _trade_log_instance is None:
        with _singleton_lock:
            if _trade_log_instance is None:
                _trade_log_instance = MMMTradeAuditLog(DB_FILE)
    return _trade_log_instance


def get_event_log() -> MMMSessionEventLog:
    """Return the singleton MMMSessionEventLog. Thread-safe, lazy-initialised."""
    global _event_log_instance
    if _event_log_instance is None:
        with _singleton_lock:
            if _event_log_instance is None:
                _event_log_instance = MMMSessionEventLog(DB_FILE)
    return _event_log_instance
