"""
Patience IV Module — Deribit DVOL percentile collector.

Source: Deribit DVOL index (30-day BTC IV benchmark). Public API, no auth.
Polling: Every 15 minutes. Stores in patience.db dvol_history table.
Bootstrap: First run backfills 30 days of historical data.
Percentile: count(values < current) / total * 100

Deribit endpoints (public, no auth required):
  Current DVOL:  GET /api/v2/public/get_index_price?index_name=dvol_btc
  Historical:    GET /api/v2/public/get_tradingview_chart_data
                     ?instrument_name=DVOL_BTC&resolution=1440
                     &start_timestamp=<ms>&end_timestamp=<ms>

Created: March 14, 2026
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

log = logging.getLogger(__name__)

# Eventlet-safe real OS thread
try:
    from eventlet.patcher import original as _ep_original
    _RealThread = _ep_original('threading').Thread
except (ImportError, AttributeError):
    _RealThread = threading.Thread

DERIBIT_BASE = "https://www.deribit.com/api/v2/public"
POLL_INTERVAL = 900           # 15 minutes between collections
BACKFILL_DAYS = 30
REQUEST_TIMEOUT = 15          # seconds

# Correct Deribit endpoint: get_volatility_index_data
# Data format: [timestamp_ms, open, high, low, close]
# currency=BTC, resolution in seconds (86400=1D, 3600=1H)


class PatienceIV:
    """
    DVOL collector daemon.
    Backfills on first start, then polls every 15 minutes.
    """

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._current_dvol: Optional[float] = None
        self._current_percentile: Optional[float] = None
        self._last_updated: Optional[str] = None
        log.info("PatienceIV: initialized")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = _RealThread(
            target=self._run,
            daemon=True,
            name="patience-iv",
        )
        self._thread.start()
        log.info("PatienceIV: daemon started")

    def stop(self):
        self._running = False

    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    # ── Main loop ─────────────────────────────────────────────────────

    def _run(self):
        from webui.backend.routes.patience.patience_models import get_db
        db = get_db()

        # Backfill on first run if history is sparse
        existing = db.get_dvol_history(days=BACKFILL_DAYS)
        if len(existing) < 10:
            log.info("PatienceIV: backfilling historical DVOL from Deribit...")
            self._backfill(db, days=BACKFILL_DAYS)

        while self._running:
            try:
                self._collect_current(db)
            except Exception as e:
                log.error(f"PatienceIV: collection error: {e}", exc_info=True)
            time.sleep(POLL_INTERVAL)

    # ── Data collection ───────────────────────────────────────────────

    def _fetch_current_dvol(self) -> Optional[float]:
        """Fetch current DVOL value — latest close from 1-hour bars."""
        try:
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            start_ms = now_ms - 7_200_000  # 2 hours back guarantees at least one closed bar
            resp = requests.get(
                f"{DERIBIT_BASE}/get_volatility_index_data",
                params={
                    "currency": "BTC",
                    "resolution": 3600,
                    "start_timestamp": start_ms,
                    "end_timestamp": now_ms,
                },
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("result", {}).get("data", [])
            if rows:
                # Each row: [ts_ms, open, high, low, close]
                return float(rows[-1][4])
            log.warning(f"PatienceIV: fetch_current_dvol returned no rows: {data}")
            return None
        except Exception as e:
            log.warning(f"PatienceIV: fetch_current_dvol failed: {e}")
            return None

    def _backfill(self, db, days: int = 30):
        """Fetch historical daily DVOL from Deribit and populate dvol_history."""
        try:
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            start_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

            resp = requests.get(
                f"{DERIBIT_BASE}/get_volatility_index_data",
                params={
                    "currency": "BTC",
                    "resolution": 86400,   # daily bars
                    "start_timestamp": start_ms,
                    "end_timestamp": now_ms,
                },
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("result", {}).get("data", [])

            if not rows:
                log.warning(f"PatienceIV: backfill returned empty data: {data}")
                return

            inserted = 0
            for row in rows:
                # row = [ts_ms, open, high, low, close]
                ts_ms, _o, _h, _l, close_val = row
                if close_val is None:
                    continue
                ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
                try:
                    db.insert_dvol(ts, float(close_val))
                    inserted += 1
                except Exception:
                    pass  # duplicate — skip

            log.info(f"PatienceIV: backfilled {inserted} DVOL values ({days} days)")

        except Exception as e:
            log.error(f"PatienceIV: backfill failed: {e}", exc_info=True)

    def _collect_current(self, db):
        """Fetch current DVOL, store in DB, recalculate percentile."""
        value = self._fetch_current_dvol()
        if value is None:
            return

        ts = datetime.now(timezone.utc).isoformat()
        db.insert_dvol(ts, value)
        self._current_dvol = value
        self._last_updated = ts

        # Recalculate percentile
        below, total = db.count_dvol_below_v2(value, days=30)
        if total > 0:
            self._current_percentile = round(below / total * 100, 1)
        else:
            self._current_percentile = None

        log.info(
            f"PatienceIV: DVOL={value:.1f} percentile={self._current_percentile}% "
            f"(below={below}/{total})"
        )

    # ── Public getters ────────────────────────────────────────────────

    def get_current_dvol(self) -> Optional[float]:
        if self._current_dvol is not None:
            return self._current_dvol
        # Try DB if daemon just started
        try:
            from webui.backend.routes.patience.patience_models import get_db
            return get_db().get_latest_dvol()
        except Exception:
            return None

    def get_current_percentile(self, lookback_days: int = 30) -> Optional[float]:
        if self._current_percentile is not None and lookback_days == 30:
            return self._current_percentile
        # Recalculate on demand for different lookback
        try:
            from webui.backend.routes.patience.patience_models import get_db
            db = get_db()
            current = self.get_current_dvol()
            if current is None:
                return None
            below, total = db.count_dvol_below_v2(current, days=lookback_days)
            if total == 0:
                return None
            return round(below / total * 100, 1)
        except Exception as e:
            log.warning(f"PatienceIV: percentile calc failed: {e}")
            return None

    def get_history(self, days: int = 30) -> list:
        try:
            from webui.backend.routes.patience.patience_models import get_db
            return get_db().get_dvol_history(days=days)
        except Exception:
            return []

    def get_status(self) -> dict:
        return {
            'running': self.is_running(),
            'current_dvol': self._current_dvol,
            'current_percentile': self._current_percentile,
            'last_updated': self._last_updated,
        }


# ── Singleton ─────────────────────────────────────────────────────────

_iv: Optional[PatienceIV] = None


def get_patience_iv() -> PatienceIV:
    global _iv
    if _iv is None:
        _iv = PatienceIV()
    return _iv


def get_current_iv_percentile(lookback_days: int = 30) -> Optional[float]:
    """Convenience function used by patience_trigger."""
    return get_patience_iv().get_current_percentile(lookback_days)
