"""
MMM Position Sub-Ledger — Persistent fill-level accounting.

Permanent solution for the "virtual position" problem:
  Delta Exchange aggregates positions at the contract level — the exchange cannot
  tell you which lots belong to which session/algo.  This module maintains that
  mapping locally by recording every fill tagged with session_id + client_order_id.

  Source of truth:  net_lots(session, symbol) = SUM(sell_qty) - SUM(buy_qty)
  If net_lots > 0, the session still has open short exposure at that symbol.

Design:
  - SQLite database (persistent across restarts and crashes)
  - fill_id is UNIQUE → record_fill() is fully idempotent; safe to call multiple times
  - All writes are synchronous SQLite (fast, no asyncio overhead)
  - Thread-safe via connection-per-call pattern (WAL mode)

Fill sources:
  REST: fill_sync calls record_fill() for every fill from /v2/fills
  WS:   executions channel handler will call record_fill() for real-time fills
        (executions channel not yet subscribed — see mmm_ws_executions.py when added)

Architected per Delta Exchange India recommendation (2026-04-26):
  Use client_order_id tagging + local sub-ledger as the permanent virtual-position system.
"""

import sqlite3
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict

from webui.backend.sealed import sealed

log = logging.getLogger(__name__)

_DB_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'data', 'mmm_position_ledger.db'
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_fills (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at       TEXT    NOT NULL,
    session_id        TEXT    NOT NULL,
    symbol            TEXT    NOT NULL,
    side              TEXT    NOT NULL,   -- 'sell' (open) or 'buy' (close)
    qty               INTEGER NOT NULL,  -- lots (always positive)
    price             REAL    NOT NULL,  -- fill price in USD
    fill_id           TEXT    NOT NULL,  -- Delta fill_id — unique per fill event
    order_id          TEXT    DEFAULT '',
    client_order_id   TEXT    DEFAULT '',
    commission        REAL    DEFAULT 0.0,
    option_side       TEXT    DEFAULT '',  -- 'ce' or 'pe'
    strike            REAL    DEFAULT 0.0,
    expiry            TEXT    DEFAULT '',
    UNIQUE(fill_id)
);

CREATE INDEX IF NOT EXISTS idx_sf_session_symbol
    ON session_fills(session_id, symbol);

CREATE INDEX IF NOT EXISTS idx_sf_client_order_id
    ON session_fills(client_order_id);

CREATE INDEX IF NOT EXISTS idx_sf_session_id
    ON session_fills(session_id);
"""


def _connect() -> sqlite3.Connection:
    """Open a WAL-mode connection to the ledger database."""
    db_path = os.path.abspath(_DB_PATH)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    # A11-03 fix: match mmm_storage.py busy_timeout so concurrent fill recordings
    # from multiple sessions wait up to 5s instead of failing immediately.
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def init_ledger() -> None:
    """Create schema if it doesn't exist. Called once at startup."""
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
        log.info("[Ledger] Initialized at %s", os.path.abspath(_DB_PATH))
    except Exception as e:
        log.error("[Ledger] init_ledger failed: %s", e)


def record_fill(
    session_id: str,
    symbol: str,
    side: str,                 # 'sell' or 'buy'
    qty: int,
    price: float,
    fill_id: str,
    order_id: str = '',
    client_order_id: str = '',
    commission: float = 0.0,
    option_side: str = '',     # 'ce' or 'pe'
    strike: float = 0.0,
    expiry: str = '',
) -> bool:
    """
    Record a single fill event.

    Returns True if the fill was newly inserted, False if already present
    (duplicate fill_id), None on error.

    Idempotent: safe to call multiple times for the same fill_id.
    """
    if not fill_id or not session_id or not symbol:
        return False
    if side not in ('sell', 'buy'):
        log.warning("[Ledger] record_fill: invalid side=%r for fill %s", side, fill_id)
        return False
    if qty <= 0 or price <= 0:
        return False

    now = datetime.now(timezone.utc).isoformat()
    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO session_fills
                    (recorded_at, session_id, symbol, side, qty, price,
                     fill_id, order_id, client_order_id, commission,
                     option_side, strike, expiry)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now, session_id, symbol, side, int(qty), float(price),
                 fill_id, order_id, client_order_id, float(commission),
                 option_side, float(strike), expiry),
            )
            inserted = cur.rowcount > 0
            if inserted:
                log.debug(
                    "[Ledger] Recorded %s fill: sid=%s sym=%s qty=%d @%.2f fill_id=%s",
                    side.upper(), session_id, symbol, qty, price, fill_id,
                )
            return inserted
    except Exception as e:
        log.error("[Ledger] record_fill error (fill_id=%s): %s", fill_id, e)
        return False


def get_session_net_lots(session_id: str, symbol: str) -> int:
    """
    Net short lots this session holds at a symbol.

    Formula: SUM(sell_qty) - SUM(buy_qty)
    Positive → session is net short (open position)
    Zero     → fully closed
    Negative → over-closed (should not happen; flag if seen)

    Returns 0 on error (fail-safe: don't block exit_all on ledger failure).
    """
    try:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN side='sell' THEN qty ELSE 0 END), 0) AS sell_lots,
                    COALESCE(SUM(CASE WHEN side='buy'  THEN qty ELSE 0 END), 0) AS buy_lots
                FROM session_fills
                WHERE session_id = ? AND symbol = ?
                """,
                (session_id, symbol),
            ).fetchone()
            sell_lots = row['sell_lots'] if row else 0
            buy_lots  = row['buy_lots']  if row else 0
            return max(int(sell_lots - buy_lots), 0)
    except Exception as e:
        log.error("[Ledger] get_session_net_lots error: %s", e)
        return 0


def get_session_open_symbols(session_id: str) -> List[Dict]:
    """
    Return all symbols where the session still has net short lots > 0.

    Each entry: {'symbol': str, 'net_lots': int, 'sell_lots': int, 'buy_lots': int}
    """
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    symbol,
                    COALESCE(SUM(CASE WHEN side='sell' THEN qty ELSE 0 END), 0) AS sell_lots,
                    COALESCE(SUM(CASE WHEN side='buy'  THEN qty ELSE 0 END), 0) AS buy_lots
                FROM session_fills
                WHERE session_id = ?
                GROUP BY symbol
                HAVING sell_lots > buy_lots
                """,
                (session_id,),
            ).fetchall()
            return [
                {
                    'symbol':    r['symbol'],
                    'net_lots':  int(r['sell_lots'] - r['buy_lots']),
                    'sell_lots': int(r['sell_lots']),
                    'buy_lots':  int(r['buy_lots']),
                }
                for r in rows
            ]
    except Exception as e:
        log.error("[Ledger] get_session_open_symbols error: %s", e)
        return []


def get_fills_by_client_order_id(client_order_id: str) -> List[Dict]:
    """
    Return all fill records for a specific client_order_id.
    Useful for verifying whether a specific open or close order was filled.
    """
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM session_fills WHERE client_order_id = ?",
                (client_order_id,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        log.error("[Ledger] get_fills_by_client_order_id error: %s", e)
        return []


def get_session_fill_summary(session_id: str) -> Dict:
    """
    Summary of all fills for a session. For audit / reporting.
    """
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT symbol, side, SUM(qty) AS total_qty, COUNT(*) AS fill_count
                FROM session_fills WHERE session_id = ?
                GROUP BY symbol, side
                ORDER BY symbol, side
                """,
                (session_id,),
            ).fetchall()
            return {
                'session_id': session_id,
                'fills': [dict(r) for r in rows],
            }
    except Exception as e:
        log.error("[Ledger] get_session_fill_summary error: %s", e)
        return {}


@sealed
def get_session_open_positions_by_side(session_id: str) -> Dict[str, List[Dict]]:
    """
    A7-01 fix: Reconstruct positions[] per side from ledger DB fills.

    Used by watchdog reconciliation to rebuild session['ce']['positions'] and
    session['pe']['positions'] when the in-memory positions[] is lost or stale
    after a monitor thread crash.

    Returns: {'ce': [pos_dicts], 'pe': [pos_dicts]}
    Each pos_dict is compatible with recompute_side_lots() format:
      id, strike, lots, entry_premium, premium, type, status, source='ledger_restore'

    One position entry is created per unique (option_side, symbol, strike) combination
    that still has net open lots > 0.  The entry_premium is the lot-weighted average
    sell price recorded in the ledger.
    """
    result: Dict[str, List[Dict]] = {'ce': [], 'pe': []}
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    option_side,
                    symbol,
                    strike,
                    COALESCE(SUM(CASE WHEN side='sell' THEN qty   ELSE 0 END), 0)           AS sell_lots,
                    COALESCE(SUM(CASE WHEN side='buy'  THEN qty   ELSE 0 END), 0)           AS buy_lots,
                    CASE
                        WHEN SUM(CASE WHEN side='sell' THEN qty ELSE 0 END) > 0
                        THEN SUM(CASE WHEN side='sell' THEN qty * price ELSE 0 END) /
                             SUM(CASE WHEN side='sell' THEN qty          ELSE 0 END)
                        ELSE 0
                    END AS avg_sell_price
                FROM session_fills
                WHERE session_id = ? AND option_side IN ('ce', 'pe')
                GROUP BY option_side, symbol, strike
                HAVING sell_lots > buy_lots
                """,
                (session_id,),
            ).fetchall()

        now = datetime.now(timezone.utc).isoformat()
        for i, r in enumerate(rows):
            opt_side = r['option_side']
            net_lots = int(r['sell_lots'] - r['buy_lots'])
            if net_lots <= 0 or opt_side not in result:
                continue
            avg_price = float(r['avg_sell_price']) if r['avg_sell_price'] else 0.0
            result[opt_side].append({
                'id': f"{opt_side}_restore_{i:03d}",
                'strike': float(r['strike']) if r['strike'] else 0.0,
                'lots': net_lots,
                'entry_premium': avg_price,
                'premium': avg_price,
                'type': 'adjustment',
                'status': 'active',
                'created_at': now,
                'fill_confirmed_at': now,
                'order_id': '',
                'client_order_id': '',
                'shifted_at': None,
                'closed_at': None,
                'realized_pnl': None,
                'timestamp': now,
                'source': 'ledger_restore',
                '_symbol': str(r['symbol']),
            })
    except Exception as e:
        log.error("[Ledger] get_session_open_positions_by_side error: %s", e)
    return result


def get_session_lots_by_side(session_id: str) -> Dict[str, int]:
    """
    AUDIT FIX (Fix 4): Return net open lots grouped by option_side.

    Returns: {'ce': N, 'pe': M} where each value is max(sell_lots - buy_lots, 0).
    Used by watchdog reconciliation to verify in-memory total_lots against DB truth.
    """
    result = {'ce': 0, 'pe': 0}
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    option_side,
                    COALESCE(SUM(CASE WHEN side='sell' THEN qty ELSE 0 END), 0) AS sell_lots,
                    COALESCE(SUM(CASE WHEN side='buy'  THEN qty ELSE 0 END), 0) AS buy_lots
                FROM session_fills
                WHERE session_id = ? AND option_side IN ('ce', 'pe')
                GROUP BY option_side
                """,
                (session_id,),
            ).fetchall()
            for r in rows:
                opt_side = r['option_side']
                net = max(int(r['sell_lots'] - r['buy_lots']), 0)
                result[opt_side] = net
    except Exception as e:
        log.error("[Ledger] get_session_lots_by_side error: %s", e)
    return result


def get_session_fills_for_export(session_id: str) -> List[Dict]:
    """
    Return all fills for a session ordered by recorded_at, for CSV/PDF export.

    Columns returned (human-friendly names):
        recorded_at, option_side, strike, expiry, side, qty, price,
        commission, fill_id, order_id, client_order_id, symbol
    """
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    recorded_at,
                    UPPER(option_side)     AS option_side,
                    strike,
                    expiry,
                    side,
                    qty,
                    price,
                    commission,
                    fill_id,
                    order_id,
                    client_order_id,
                    symbol
                FROM session_fills
                WHERE session_id = ?
                ORDER BY recorded_at ASC
                """,
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        log.error("[Ledger] get_session_fills_for_export error: %s", e)
        return []
