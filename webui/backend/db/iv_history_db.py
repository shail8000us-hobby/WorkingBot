"""
IV History Store  (Feature 2 — IV Rank / IV Percentile)
=========================================================
Independent SQLite store.  Records IV snapshots every 5 minutes
(rate-limited internally), computes IVR and IVP on demand.

Tables:
  iv_snapshots — one row per (symbol, 5-minute bucket)

Usage:
  from webui.backend.db.iv_history_db import record_iv_snapshot, get_iv_stats
"""

import sqlite3
import threading
import time
import math
from pathlib import Path
from typing import Dict, List, Optional

_DB_PATH = Path(__file__).parent.parent / "data" / "iv_history.db"
_RECORD_INTERVAL = 300      # record at most once per 5 minutes per symbol
_MAX_DAYS = 400             # keep up to 400 days of history
_MIN_DAYS_REQUIRED = 2      # minimum days needed to return useful IVR/IVP

_db_lock = threading.Lock()
_last_record: Dict[str, float] = {}  # symbol -> last record timestamp
_last_record_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS iv_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol      TEXT    NOT NULL,
                strike      REAL    NOT NULL,
                expiry      TEXT    NOT NULL,
                option_type TEXT    NOT NULL,  -- 'call' or 'put'
                iv          REAL    NOT NULL,  -- decimal (e.g. 0.654)
                spot        REAL,
                recorded_at REAL    NOT NULL DEFAULT (strftime('%s','now')),
                UNIQUE(symbol, recorded_at)    -- one row per symbol per second
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_iv_sym ON iv_snapshots(symbol, recorded_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_iv_exp ON iv_snapshots(expiry)")
        conn.commit()


try:
    _init_db()
except Exception:
    pass


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def _parse_symbol(symbol: str):
    """Return (option_type, strike, expiry_str) or None."""
    try:
        parts = symbol.split('-')
        if len(parts) < 4:
            return None
        opt_type = 'call' if parts[0].upper() == 'C' else 'put'
        strike = float(parts[2])
        raw = parts[3]  # "270326" = DDMMYY (27-Mar-2026)
        dd, mm, yy = int(raw[0:2]), int(raw[2:4]), int(raw[4:6])
        expiry = f"20{yy:02d}-{mm:02d}-{dd:02d}"
        return opt_type, strike, expiry
    except Exception:
        return None


def record_iv_snapshot(positions: List[Dict], spot_price: float = 0.0):
    """
    Record IV for all positions.  Rate-limited to once per symbol per 5 min.
    Call this from any periodic background task that has fresh positions data.
    """
    now = time.time()
    to_insert = []

    for pos in positions:
        symbol = pos.get('product_symbol', '')
        iv_raw = pos.get('iv') or 0.0
        if not symbol or not iv_raw:
            continue

        with _last_record_lock:
            last = _last_record.get(symbol, 0)
            if now - last < _RECORD_INTERVAL:
                continue
            _last_record[symbol] = now

        iv = float(iv_raw)
        if iv > 5:
            iv = iv / 100.0  # convert % to decimal

        parsed = _parse_symbol(symbol)
        if not parsed:
            continue
        opt_type, strike, expiry = parsed
        to_insert.append((symbol, strike, expiry, opt_type, iv, spot_price, now))

    if not to_insert:
        return

    cutoff = now - (_MAX_DAYS * 86400)
    try:
        with _db_lock, _get_conn() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO iv_snapshots (symbol, strike, expiry, option_type, iv, spot, recorded_at) VALUES (?,?,?,?,?,?,?)",
                to_insert
            )
            conn.execute("DELETE FROM iv_snapshots WHERE recorded_at < ?", (cutoff,))
            conn.commit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def get_iv_stats(symbol: str, lookback_days: int = 365) -> Optional[Dict]:
    """
    Compute IVR and IVP for a symbol.

    Returns:
        {ivr, ivp, high_52w, low_52w, current_iv, days_available}
        or None if insufficient history.
    """
    try:
        cutoff = time.time() - (lookback_days * 86400)
        with _db_lock, _get_conn() as conn:
            rows = conn.execute(
                "SELECT iv, recorded_at FROM iv_snapshots WHERE symbol=? AND recorded_at>=? ORDER BY recorded_at",
                (symbol, cutoff)
            ).fetchall()

        if not rows:
            return None

        ivs = [r['iv'] for r in rows]
        # Daily low/high (group by day, take one sample per day)
        by_day: Dict[str, List[float]] = {}
        for r in rows:
            day = str(int(r['recorded_at'] // 86400))
            by_day.setdefault(day, []).append(r['iv'])

        if len(by_day) < _MIN_DAYS_REQUIRED:
            return None

        daily_ivs = [sum(v) / len(v) for v in by_day.values()]
        current_iv = ivs[-1]
        hi = max(daily_ivs)
        lo = min(daily_ivs)

        ivr = round((current_iv - lo) / (hi - lo) * 100, 1) if hi > lo else 50.0
        ivp = round(sum(1 for v in daily_ivs if v < current_iv) / len(daily_ivs) * 100, 1)

        return {
            'ivr': ivr,
            'ivp': ivp,
            'high_52w': round(hi * 100, 2),   # as %
            'low_52w': round(lo * 100, 2),
            'current_iv_pct': round(current_iv * 100, 2),
            'days_available': len(by_day),
        }
    except Exception:
        return None


def get_iv_stats_batch(symbols: List[str], lookback_days: int = 365) -> Dict[str, Dict]:
    """Return IV stats for all symbols in one pass (batch-optimised)."""
    result = {}
    if not symbols:
        return result
    try:
        cutoff = time.time() - (lookback_days * 86400)
        with _db_lock, _get_conn() as conn:
            placeholders = ','.join('?' * len(symbols))
            rows = conn.execute(
                f"SELECT symbol, iv, recorded_at FROM iv_snapshots WHERE symbol IN ({placeholders}) AND recorded_at>=? ORDER BY symbol, recorded_at",
                symbols + [cutoff]
            ).fetchall()

        # Group by symbol
        by_symbol: Dict[str, List] = {}
        for r in rows:
            by_symbol.setdefault(r['symbol'], []).append(r)

        for sym, sym_rows in by_symbol.items():
            by_day: Dict[str, List[float]] = {}
            for r in sym_rows:
                day = str(int(r['recorded_at'] // 86400))
                by_day.setdefault(day, []).append(r['iv'])

            if len(by_day) < _MIN_DAYS_REQUIRED:
                continue

            daily_ivs = [sum(v) / len(v) for v in by_day.values()]
            current_iv = sym_rows[-1]['iv']
            hi = max(daily_ivs)
            lo = min(daily_ivs)
            ivr = round((current_iv - lo) / (hi - lo) * 100, 1) if hi > lo else 50.0
            ivp = round(sum(1 for v in daily_ivs if v < current_iv) / len(daily_ivs) * 100, 1)
            result[sym] = {
                'ivr': ivr,
                'ivp': ivp,
                'high_52w': round(hi * 100, 2),
                'low_52w': round(lo * 100, 2),
                'current_iv_pct': round(current_iv * 100, 2),
                'days_available': len(by_day),
            }
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# Background IV Recording
# ---------------------------------------------------------------------------
import logging as _logging
_iv_logger = _logging.getLogger(__name__)
_iv_bg_thread = None

def start_iv_background_recorder(app=None, interval: int = 300):
    """
    Start a daemon thread that records IV snapshots every `interval` seconds.
    Safe to call multiple times — only one thread will run.
    Pass the Flask app instance so the thread can push an application context.
    """
    global _iv_bg_thread
    if _iv_bg_thread and _iv_bg_thread.is_alive():
        return  # already running

    def _loop():
        from contextlib import nullcontext
        _iv_logger.info("IV background recorder started (interval=%ds)", interval)
        while True:
            try:
                time.sleep(interval)
                from webui.backend.routes.options.dashboard_service import fetch_options_positions_data
                from webui.backend.routes.market import _price_cache
                ctx = app.app_context() if app is not None else nullcontext()
                with ctx:
                    data = fetch_options_positions_data()
                positions = data.get('positions', [])
                if positions:
                    spot_entry = _price_cache.get('spot_BTC')
                    spot = float(spot_entry[1]) if spot_entry else 0.0
                    record_iv_snapshot(positions, spot_price=spot)
                    _iv_logger.debug("IV background: recorded %d positions", len(positions))
            except Exception as e:
                _iv_logger.warning("IV background recorder error: %s", e)

    _iv_bg_thread = threading.Thread(target=_loop, daemon=True, name="iv-bg-recorder")
    _iv_bg_thread.start()
