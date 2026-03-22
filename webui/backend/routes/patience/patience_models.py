"""
Patience — SQLite data access layer.

All card, leg, template, DVOL, execution log, and performance data.
Database: data/patience.db (auto-created on first use)

Created: March 14, 2026
"""

import sqlite3
import uuid
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / 'data' / 'patience.db'

SCHEMA = """
CREATE TABLE IF NOT EXISTS scenario_cards (
    card_id TEXT PRIMARY KEY,
    card_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    parent_card_id TEXT,
    trigger_price REAL NOT NULL,
    trigger_type TEXT NOT NULL,
    trigger_tolerance REAL DEFAULT 50,
    sustain_minutes INTEGER,
    iv_percentile_min REAL,
    iv_percentile_max REAL,
    iv_lookback_days INTEGER DEFAULT 30,
    created_at TEXT NOT NULL,
    triggered_at TEXT,
    completed_at TEXT,
    group_id TEXT,
    template_id TEXT
);

CREATE TABLE IF NOT EXISTS card_legs (
    leg_id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES scenario_cards(card_id),
    leg_order INTEGER NOT NULL,
    direction TEXT NOT NULL,
    option_type TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    strike REAL,
    lots INTEGER NOT NULL,
    is_relative_strike INTEGER DEFAULT 0,
    relative_offset REAL,
    post_only INTEGER DEFAULT 1,
    order_mode TEXT DEFAULT 'maker_only',
    stop_loss REAL,
    mmm_handoff_eligible INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING',
    fill_price REAL,
    filled_at TEXT,
    order_id TEXT,
    executed_symbol TEXT
);

CREATE TABLE IF NOT EXISTS card_templates (
    template_id TEXT PRIMARY KEY,
    template_name TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    trigger_tolerance REAL DEFAULT 50,
    iv_percentile_min REAL,
    iv_percentile_max REAL,
    iv_lookback_days INTEGER DEFAULT 30,
    legs_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dvol_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    dvol_value REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    leg_id TEXT,
    event_type TEXT NOT NULL,
    message TEXT,
    data_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS card_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT,
    card_name TEXT,
    entry_premium REAL,
    exit_value REAL,
    pnl REAL,
    duration_hours REAL,
    card_type TEXT,
    legs_handed_to_mmm INTEGER DEFAULT 0,
    handoff_pnl REAL,
    closed_at TEXT
);
"""


def _now() -> str:
    return datetime.utcnow().isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


class PatienceDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            # Migration: add use_gcd column to existing databases
            try:
                conn.execute("ALTER TABLE scenario_cards ADD COLUMN use_gcd INTEGER DEFAULT 1")
                log.info("PatienceDB: migrated — added use_gcd column")
            except Exception:
                pass  # column already exists
            # Migration: add order_id + executed_symbol to card_legs (traceability)
            for col, defn in [('order_id', 'TEXT'), ('executed_symbol', 'TEXT')]:
                try:
                    conn.execute(f"ALTER TABLE card_legs ADD COLUMN {col} {defn}")
                    log.info(f"PatienceDB: migrated — added {col} column to card_legs")
                except Exception:
                    pass  # column already exists
        log.info(f"PatienceDB: initialized at {self.db_path}")

    # ── Cards ──────────────────────────────────────────────────────────

    def create_card(self, card: dict) -> str:
        card_id = _new_id()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO scenario_cards (
                    card_id, card_name, status, parent_card_id,
                    trigger_price, trigger_type, trigger_tolerance, sustain_minutes,
                    iv_percentile_min, iv_percentile_max, iv_lookback_days,
                    created_at, template_id, use_gcd
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                card_id,
                card['card_name'],
                card.get('status', 'DRAFT'),
                card.get('parent_card_id'),
                card['trigger_price'],
                card['trigger_type'],
                card.get('trigger_tolerance', 50),
                card.get('sustain_minutes'),
                card.get('iv_percentile_min'),
                card.get('iv_percentile_max'),
                card.get('iv_lookback_days', 30),
                _now(),
                card.get('template_id'),
                1 if card.get('use_gcd', True) else 0,
            ))
        return card_id

    def get_card(self, card_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM scenario_cards WHERE card_id = ?", (card_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_cards_by_status(self, *statuses) -> list:
        placeholders = ','.join('?' for _ in statuses)
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM scenario_cards WHERE status IN ({placeholders}) ORDER BY created_at ASC",
                statuses
            ).fetchall()
        return [dict(r) for r in rows]

    def get_all_cards(self) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM scenario_cards ORDER BY created_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def update_card(self, card_id: str, **fields) -> None:
        if not fields:
            return
        set_clause = ', '.join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [card_id]
        with self._conn() as conn:
            conn.execute(
                f"UPDATE scenario_cards SET {set_clause} WHERE card_id = ?",
                values
            )

    def delete_card(self, card_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM card_legs WHERE card_id = ?", (card_id,))
            conn.execute("DELETE FROM scenario_cards WHERE card_id = ?", (card_id,))

    # ── Legs ───────────────────────────────────────────────────────────

    def create_leg(self, leg: dict, card_id: str) -> str:
        leg_id = _new_id()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO card_legs (
                    leg_id, card_id, leg_order, direction, option_type,
                    expiry_date, strike, lots, is_relative_strike, relative_offset,
                    post_only, order_mode, stop_loss, mmm_handoff_eligible, status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                leg_id, card_id,
                leg.get('leg_order', 0),
                leg['direction'],
                leg['option_type'],
                leg['expiry_date'],
                leg.get('strike'),
                leg['lots'],
                int(leg.get('is_relative_strike', False)),
                leg.get('relative_offset'),
                int(leg.get('post_only', True)),
                leg.get('order_mode', 'maker_only'),
                leg.get('stop_loss'),
                int(leg.get('mmm_handoff_eligible', False)),
                'PENDING',
            ))
        return leg_id

    def get_legs(self, card_id: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM card_legs WHERE card_id = ? ORDER BY leg_order ASC",
                (card_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_leg(self, leg_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM card_legs WHERE leg_id = ?", (leg_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_leg(self, leg_id: str, **fields) -> None:
        if not fields:
            return
        set_clause = ', '.join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [leg_id]
        with self._conn() as conn:
            conn.execute(
                f"UPDATE card_legs SET {set_clause} WHERE leg_id = ?",
                values
            )

    def replace_legs(self, card_id: str, legs: list) -> list:
        """Delete existing legs for card and create new ones. Returns new leg_ids."""
        with self._conn() as conn:
            conn.execute("DELETE FROM card_legs WHERE card_id = ?", (card_id,))
        leg_ids = []
        for leg in legs:
            lid = self.create_leg(leg, card_id)
            leg_ids.append(lid)
        return leg_ids

    # ── Templates ──────────────────────────────────────────────────────

    def save_template(self, tpl: dict) -> str:
        template_id = _new_id()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO card_templates (
                    template_id, template_name, trigger_type, trigger_tolerance,
                    iv_percentile_min, iv_percentile_max, iv_lookback_days,
                    legs_json, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                template_id,
                tpl['template_name'],
                tpl.get('trigger_type', 'CROSS_UP'),
                tpl.get('trigger_tolerance', 50),
                tpl.get('iv_percentile_min'),
                tpl.get('iv_percentile_max'),
                tpl.get('iv_lookback_days', 30),
                json.dumps(tpl.get('legs', [])),
                _now(),
            ))
        return template_id

    def get_templates(self) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM card_templates ORDER BY created_at DESC"
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d['legs'] = json.loads(d.pop('legs_json', '[]'))
            result.append(d)
        return result

    def get_template(self, template_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM card_templates WHERE template_id = ?", (template_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d['legs'] = json.loads(d.pop('legs_json', '[]'))
        return d

    def delete_template(self, template_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM card_templates WHERE template_id = ?", (template_id,)
            )

    # ── Execution log ──────────────────────────────────────────────────

    def log_event(self, card_id: str, leg_id: Optional[str],
                  event_type: str, message: str = '', data: dict = None) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO execution_log (card_id, leg_id, event_type, message, data_json, created_at)
                VALUES (?,?,?,?,?,?)
            """, (
                card_id, leg_id, event_type, message,
                json.dumps(data) if data else None,
                _now(),
            ))

    def get_log(self, card_id: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM execution_log WHERE card_id = ? ORDER BY id ASC",
                (card_id,)
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get('data_json'):
                try:
                    d['data'] = json.loads(d['data_json'])
                except Exception:
                    d['data'] = None
            else:
                d['data'] = None
            del d['data_json']
            result.append(d)
        return result

    # ── DVOL history ───────────────────────────────────────────────────

    def insert_dvol(self, timestamp: str, value: float) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO dvol_history (timestamp, dvol_value) VALUES (?,?)",
                (timestamp, value)
            )

    def get_dvol_history(self, days: int = 30) -> list:
        cutoff = datetime.utcnow().isoformat()[:10]  # crude date cutoff
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT timestamp, dvol_value FROM dvol_history
                ORDER BY timestamp DESC
                LIMIT ?
            """, (days * 96,)).fetchall()  # 96 = 4 × 24 (15-min interval max)
        return [dict(r) for r in rows]

    def get_latest_dvol(self) -> Optional[float]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT dvol_value FROM dvol_history ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return row['dvol_value'] if row else None

    def count_dvol_below(self, value: float, days: int = 30) -> tuple:
        """Returns (count_below, total) for percentile calculation."""
        limit = days * 96
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM (SELECT id FROM dvol_history ORDER BY id DESC LIMIT ?)",
                (limit,)
            ).fetchone()[0]
            below = conn.execute("""
                SELECT COUNT(*) FROM (
                    SELECT id FROM dvol_history ORDER BY id DESC LIMIT ?
                ) sub JOIN dvol_history h ON h.id = sub.id WHERE h.dvol_value < ?
            """, (limit, value)).fetchone()[0]
        return below, total

    def count_dvol_below_v2(self, current_value: float, days: int = 30) -> tuple:
        """Simpler percentile calc using recent rows."""
        limit = days * 96
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT dvol_value FROM dvol_history ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        values = [r['dvol_value'] for r in rows]
        if not values:
            return 0, 0
        below = sum(1 for v in values if v < current_value)
        return below, len(values)

    # ── Performance ────────────────────────────────────────────────────

    def save_performance(self, perf: dict) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO card_performance (
                    card_id, card_name, entry_premium, exit_value, pnl,
                    duration_hours, card_type, legs_handed_to_mmm, handoff_pnl, closed_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                perf.get('card_id'),
                perf.get('card_name'),
                perf.get('entry_premium'),
                perf.get('exit_value'),
                perf.get('pnl'),
                perf.get('duration_hours'),
                perf.get('card_type'),
                perf.get('legs_handed_to_mmm', 0),
                perf.get('handoff_pnl'),
                perf.get('closed_at', _now()),
            ))

    def get_performance(self) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM card_performance ORDER BY closed_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


# ── Singleton ─────────────────────────────────────────────────────────

_db: Optional[PatienceDB] = None


def get_db() -> PatienceDB:
    global _db
    if _db is None:
        _db = PatienceDB()
    return _db
