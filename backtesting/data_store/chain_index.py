"""
Chain Index
============
SQLite-based index of collected expiry dates.

Tracks which (expiry_date, underlying) combinations have been collected,
partially collected, or failed. Prevents re-downloading existing data.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict

log = logging.getLogger("backtesting.chain_index")

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "historical_data" / "index.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS collection_index (
    expiry_date    TEXT NOT NULL,
    underlying     TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',   -- pending | collected | failed | partial
    row_count      INTEGER DEFAULT 0,
    strike_count   INTEGER DEFAULT 0,
    collected_at   TEXT,
    error_message  TEXT,
    PRIMARY KEY (expiry_date, underlying)
)
"""


class ChainIndex:
    """
    SQLite index for tracking which expiry dates have been collected.

    Usage:
        idx = ChainIndex()
        if idx.is_collected("10-03-2026", "BTC"):
            print("Already have the data!")
        idx.mark_collected("10-03-2026", "BTC", row_count=150000, strike_count=200)
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.commit()
        log.debug(f"ChainIndex initialized: {self.db_path}")

    # ── Status checks ─────────────────────────────────────────────────────────

    def is_collected(self, expiry_date: str, underlying: str) -> bool:
        """Return True if data was successfully collected for this expiry."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT status FROM collection_index WHERE expiry_date=? AND underlying=?",
                (expiry_date, underlying.upper())
            ).fetchone()
        return row is not None and row["status"] == "collected"

    def get_status(self, expiry_date: str, underlying: str) -> Optional[str]:
        """Return the collection status: 'collected', 'failed', 'partial', 'pending', or None."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT status FROM collection_index WHERE expiry_date=? AND underlying=?",
                (expiry_date, underlying.upper())
            ).fetchone()
        return row["status"] if row else None

    def get_row_count(self, expiry_date: str, underlying: str) -> int:
        """Return the number of rows stored for this expiry (0 if not found)."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT row_count FROM collection_index WHERE expiry_date=? AND underlying=?",
                (expiry_date, underlying.upper())
            ).fetchone()
        return row["row_count"] if row else 0

    # ── Status updates ────────────────────────────────────────────────────────

    def mark_collected(
        self,
        expiry_date: str,
        underlying: str,
        row_count: int = 0,
        strike_count: int = 0,
    ):
        """Mark an expiry as successfully collected."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO collection_index
                    (expiry_date, underlying, status, row_count, strike_count, collected_at, error_message)
                VALUES (?, ?, 'collected', ?, ?, ?, NULL)
                ON CONFLICT(expiry_date, underlying) DO UPDATE SET
                    status=excluded.status,
                    row_count=excluded.row_count,
                    strike_count=excluded.strike_count,
                    collected_at=excluded.collected_at,
                    error_message=NULL
            """, (expiry_date, underlying.upper(), row_count, strike_count, now))
            conn.commit()
        log.debug(f"Marked collected: {expiry_date} {underlying} ({row_count} rows)")

    def mark_failed(self, expiry_date: str, underlying: str, error_message: str):
        """Mark an expiry as failed."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO collection_index
                    (expiry_date, underlying, status, collected_at, error_message)
                VALUES (?, ?, 'failed', ?, ?)
                ON CONFLICT(expiry_date, underlying) DO UPDATE SET
                    status='failed',
                    collected_at=excluded.collected_at,
                    error_message=excluded.error_message
            """, (expiry_date, underlying.upper(), now, error_message))
            conn.commit()
        log.debug(f"Marked failed: {expiry_date} {underlying}: {error_message}")

    # ── Queries ───────────────────────────────────────────────────────────────

    def list_all(self) -> List[Dict]:
        """Return all index records as a list of dicts."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM collection_index ORDER BY expiry_date DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_collected(self, underlying: str = "BTC") -> List[str]:
        """Return list of successfully collected expiry dates for an underlying."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT expiry_date FROM collection_index WHERE underlying=? AND status='collected' ORDER BY expiry_date DESC",
                (underlying.upper(),)
            ).fetchall()
        return [r["expiry_date"] for r in rows]

    def list_failed(self, underlying: str = "BTC") -> List[str]:
        """Return list of failed expiry dates."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT expiry_date FROM collection_index WHERE underlying=? AND status='failed'",
                (underlying.upper(),)
            ).fetchall()
        return [r["expiry_date"] for r in rows]

    def summary(self) -> Dict:
        """Return a summary dict of collection status."""
        with self._get_conn() as conn:
            total      = conn.execute("SELECT COUNT(*) FROM collection_index").fetchone()[0]
            collected  = conn.execute("SELECT COUNT(*) FROM collection_index WHERE status='collected'").fetchone()[0]
            failed     = conn.execute("SELECT COUNT(*) FROM collection_index WHERE status='failed'").fetchone()[0]
            total_rows = conn.execute("SELECT SUM(row_count) FROM collection_index WHERE status='collected'").fetchone()[0] or 0

        return {
            "total_expiries": total,
            "collected":      collected,
            "failed":         failed,
            "pending":        total - collected - failed,
            "total_rows":     total_rows,
        }
