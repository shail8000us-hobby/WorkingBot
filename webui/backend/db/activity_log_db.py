"""
Activity Log Persistence
========================
Independent SQLite store for options monitoring events.
Keeps last 24 hours of events. Fully decoupled from the in-memory buffer.

Usage:
    from webui.backend.db.activity_log_db import persist_event, get_persisted_log, export_csv_string
"""

import sqlite3
import json
import logging
import threading
import time
import io
import csv
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent / "data" / "activity_log.db"
_RETENTION_HOURS = 24
_db_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                type      TEXT    NOT NULL,
                category  TEXT    NOT NULL DEFAULT 'system',
                message   TEXT    NOT NULL,
                details   TEXT,
                created_at REAL   DEFAULT (strftime('%s', 'now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_al_created ON activity_log(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_al_category ON activity_log(category)")
        conn.commit()


# Initialise on first import
try:
    _init_db()
except Exception:
    pass  # Don't crash the app if DB init fails


def persist_event(event: dict):
    """Write a single event to SQLite. Auto-prunes entries older than 24 h."""
    try:
        cutoff = time.time() - (_RETENTION_HOURS * 3600)
        with _db_lock, _get_conn() as conn:
            conn.execute(
                "INSERT INTO activity_log (timestamp, type, category, message, details) VALUES (?,?,?,?,?)",
                (
                    event.get("timestamp", ""),
                    event.get("type", "system"),
                    event.get("category", "system"),
                    event.get("message", ""),
                    json.dumps(event.get("details") or {}),
                )
            )
            # Prune old rows on every write (cheap because index exists)
            conn.execute("DELETE FROM activity_log WHERE created_at < ?", (cutoff,))
            conn.commit()
    except Exception as e:
        logger.warning("Failed to persist activity event: %s", e)  # Best-effort; never raise


def get_persisted_log(
    hours: float = 24,
    category: Optional[str] = None,
    limit: int = 500,
) -> list:
    """Return events from SQLite, newest first."""
    try:
        cutoff = time.time() - (hours * 3600)
        query = "SELECT * FROM activity_log WHERE created_at >= ?"
        params: list = [cutoff]
        if category and category != "all":
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with _db_lock, _get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        result = []
        for row in rows:
            try:
                details = json.loads(row["details"]) if row["details"] else {}
            except Exception:
                details = {}
            result.append({
                "timestamp": row["timestamp"],
                "type": row["type"],
                "category": row["category"],
                "message": row["message"],
                "details": details,
            })
        return result
    except Exception:
        return []


def export_csv_string(hours: float = 24) -> str:
    """Return all events in the last N hours as a CSV string."""
    events = get_persisted_log(hours=hours, limit=10000)
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["timestamp", "type", "category", "message", "details"],
        extrasaction="ignore",
    )
    writer.writeheader()
    for ev in events:
        writer.writerow({
            **ev,
            "details": json.dumps(ev.get("details", {})),
        })
    return output.getvalue()
