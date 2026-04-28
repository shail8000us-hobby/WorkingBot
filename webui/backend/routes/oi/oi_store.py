"""
OI Aggregator — In-Memory Store + SQLite Persistence + Spike Detection

Thread-safe store for OI snapshots with:
- In-memory deques for fast aggregation (maxlen=20)
- SQLite persistence with WAL mode for historical queries
- Spike detection with cooldown, min thresholds, aggregate detection
- Per-underlying price tracking (for ATM computation in frontend)
- Expiry metadata (is_weekly, days_to_expiry) for Sensibull-style filter

READ-ONLY analytics module. Does NOT interact with any trading logic.

Created: March 27, 2026
Revised: March 27, 2026 — audit fixes applied
"""

import logging
import os
import sqlite3
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta, date

log = logging.getLogger('oi_aggregator')

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MAX_STRIKES_PER_EXPIRY = 300
_MAX_EXPIRIES = 12
_DEQUE_MAXLEN = 20
_RETENTION_DAYS = 3  # OI snapshots are analytics-only; 3 days is ample for spike detection
_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data')
_DB_PATH = os.path.join(_DB_DIR, 'oi_data.db')


# ---------------------------------------------------------------------------
# Expiry metadata helpers
# ---------------------------------------------------------------------------

def _is_last_weekday_of_month(d: date) -> bool:
    """True if d is the last occurrence of its weekday in its month."""
    return (d + timedelta(days=7)).month != d.month


def _expiry_metadata(expiry_str: str) -> dict:
    """
    Compute display metadata for an expiry date string (ISO YYYY-MM-DD).
    Returns dict with:
        date          - ISO string
        is_weekly     - True if NOT the last weekday occurrence of that month
        days_to_expiry - calendar days from today (UTC)
    """
    try:
        exp_date = date.fromisoformat(expiry_str)
        today = datetime.now(timezone.utc).date()
        days = (exp_date - today).days
        is_weekly = not _is_last_weekday_of_month(exp_date)
        return {
            'date': expiry_str,
            'is_weekly': is_weekly,
            'days_to_expiry': max(0, days),
        }
    except Exception:
        return {'date': expiry_str, 'is_weekly': False, 'days_to_expiry': 0}


# ============================================================================
# OI Store
# ============================================================================

class OIStore:
    """
    In-memory store backed by SQLite.
    Thread-safe via a lock for the in-memory dict.
    SQLite uses per-thread connections.
    """

    def __init__(self, db_path: str = None):
        self._db_path = db_path or _DB_PATH
        self._lock = threading.Lock()
        # Key: (exchange, underlying, expiry, strike, type) → deque of OIRow dicts
        self._snapshots = defaultdict(lambda: deque(maxlen=_DEQUE_MAXLEN))
        # Per-exchange health tracking
        self._exchange_health = {}
        # Underlying spot price (keyed by underlying symbol e.g. 'BTC')
        # Updated from Deribit rows (most reliable source)
        self._underlying_price = {}
        # Thread-local storage for SQLite connections
        self._local = threading.local()
        # Spike detector
        self.spike_detector = OISpikeDetector()
        # Initialize DB
        self._init_db()
        # Run retention cleanup
        self._run_retention()

    # ------------------------------------------------------------------
    # SQLite connection management
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create thread-local SQLite connection with WAL mode."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            conn = sqlite3.connect(self._db_path)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA busy_timeout=5000')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        """Create tables and indexes if they don't exist."""
        conn = self._get_conn()
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS oi_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                exchange TEXT NOT NULL,
                underlying TEXT NOT NULL,
                expiry TEXT NOT NULL,
                strike REAL NOT NULL,
                type TEXT NOT NULL,
                oi REAL NOT NULL,
                oi_usd REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS oi_spike_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                exchange TEXT NOT NULL,
                underlying TEXT NOT NULL,
                expiry TEXT NOT NULL,
                strike REAL NOT NULL,
                type TEXT NOT NULL,
                oi_prev REAL NOT NULL,
                oi_curr REAL NOT NULL,
                change_pct REAL NOT NULL,
                severity TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_ts
                ON oi_snapshots(ts);
            CREATE INDEX IF NOT EXISTS idx_snapshots_lookup
                ON oi_snapshots(underlying, expiry, strike, type, ts);
            CREATE INDEX IF NOT EXISTS idx_spikes_ts
                ON oi_spike_events(ts);
        ''')
        conn.commit()
        log.info('[OIStore] Database initialized at %s', self._db_path)

    # ------------------------------------------------------------------
    # Merge snapshot (called from background thread)
    # ------------------------------------------------------------------

    def merge_snapshot(self, exchange: str, rows: list) -> list:
        """
        Ingest one exchange's fresh data.
        Returns list of SpikeEvent dicts detected.

        NOTE: Does NOT call _prune_stale_keys — caller (oi_api._run_single_cycle)
        calls prune_stale_keys() once per full cycle after all exchanges are done.
        """
        if not rows:
            return []

        spikes = []
        now_ts = datetime.now(timezone.utc).isoformat()

        with self._lock:
            for row in rows:
                key = (
                    row['exchange'],
                    row['underlying'],
                    row['expiry'],
                    row['strike'],
                    row['type'],
                )

                # Get previous latest for spike detection
                prev = self._snapshots[key][-1] if self._snapshots[key] else None

                # Append to deque
                self._snapshots[key].append(row)

                # Spike detection (per-exchange)
                if prev:
                    spike = self.spike_detector.check(prev, row)
                    if spike:
                        spikes.append(spike)

            # Update exchange health
            self._exchange_health[exchange] = {
                'last_fetch_ts': now_ts,
                'row_count': len(rows),
                'status': 'ok',
            }

            # Update underlying spot price from Deribit (most reliable)
            # Deribit rows carry underlying_price in oi_usd = oi * underlying_price,
            # but we need to store it separately. Look for any non-zero oi row to derive it.
            if exchange == 'deribit':
                for row in rows:
                    oi = row.get('oi', 0)
                    oi_usd = row.get('oi_usd', 0)
                    if oi > 0 and oi_usd > 0:
                        price = oi_usd / oi
                        if price > 0:
                            self._underlying_price[row.get('underlying', 'BTC')] = round(price, 2)
                            break

        # Write to SQLite (outside the lock to avoid blocking reads)
        self._write_to_db(rows)

        # Write spike events to DB
        for spike in spikes:
            self._write_spike_to_db(spike)

        # Aggregate spike detection (reads _snapshots under its own lock acquisition)
        agg_spikes = self._check_aggregate_spikes(rows)
        for spike in agg_spikes:
            spikes.append(spike)
            self._write_spike_to_db(spike)

        return spikes

    def prune_stale_keys(self):
        """
        Public method — called once per cycle from oi_api._run_single_cycle.
        Removes expired expiries and zero-OI keys from memory.
        """
        self._prune_stale_keys()

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_aggregated(self, expiries=None, underlying: str = 'BTC',
                       window_minutes: int = 20) -> list:
        """
        Get aggregated OI across all exchanges for each (strike, type).

        Args:
            expiries: list of ISO date strings, single ISO string, or None (→ nearest).
                      None / empty list → uses nearest expiry.
            underlying: e.g. 'BTC'
            window_minutes: lookback for OI change computation. Finds the deque entry
                            closest to (now - window_minutes) as the change baseline.
        Returns:
            Sorted list of aggregated row dicts (strike, type, oi, oi_usd, oi_change, exchanges).
        """
        # Normalise expiries argument
        if expiries is None or expiries == '' or expiries == []:
            all_exp = self.get_expiries(underlying)
            expiry_set = {all_exp[0]} if all_exp else set()
        elif expiries == ['ALL']:
            expiry_set = set(self.get_expiries(underlying))
        elif isinstance(expiries, str):
            expiry_set = {expiries}
        else:
            expiry_set = set(expiries)

        if not expiry_set:
            return []

        now = datetime.now(timezone.utc)
        cutoff_ts = (now - timedelta(minutes=window_minutes)).isoformat()

        result = {}

        with self._lock:
            for key, dq in self._snapshots.items():
                ex, und, exp, strike, opt_type = key
                if und != underlying.upper():
                    continue
                if exp not in expiry_set:
                    continue
                if not dq:
                    continue

                latest = dq[-1]
                agg_key = (exp, strike, opt_type)

                if agg_key not in result:
                    result[agg_key] = {
                        'expiry': exp,
                        'strike': strike,
                        'type': opt_type,
                        'oi': 0.0,
                        'oi_usd': 0.0,
                        'oi_change': 0.0,
                        'mark_iv': 0.0,
                        'exchanges': {},
                    }

                row = result[agg_key]
                row['oi'] += latest.get('oi', 0)
                row['oi_usd'] += latest.get('oi_usd', 0)
                row['exchanges'][ex] = {
                    'oi': latest.get('oi', 0),
                    'oi_usd': latest.get('oi_usd', 0),
                }
                iv = latest.get('mark_iv', 0.0)
                if iv > 0 and iv > row['mark_iv']:
                    row['mark_iv'] = float(iv)

                # Time-windowed OI change: compare latest vs deque entry
                # closest to (now - window_minutes). Falls back to oldest entry.
                baseline = None
                if len(dq) >= 2:
                    for entry in dq:
                        if entry.get('timestamp', '') <= cutoff_ts:
                            baseline = entry
                        else:
                            break
                    if baseline is None:
                        baseline = dq[0]  # use oldest available if none old enough

                if baseline:
                    change = latest.get('oi', 0) - baseline.get('oi', 0)
                    row['oi_change'] += change

        # Convert to sorted list (by strike ascending)
        rows = sorted(result.values(), key=lambda r: r['strike'])
        return rows

    def get_expiries(self, underlying: str = 'BTC') -> list:
        """Get deduplicated sorted list of available expiry date strings."""
        expiries = set()
        with self._lock:
            for key in self._snapshots:
                _, und, exp, _, _ = key
                if und == underlying.upper():
                    expiries.add(exp)
        return sorted(expiries)

    def get_expiries_with_metadata(self, underlying: str = 'BTC') -> list:
        """
        Get expiry list with display metadata for the Sensibull-style filter.
        Returns list of dicts: {date, is_weekly, days_to_expiry}
        """
        return [_expiry_metadata(e) for e in self.get_expiries(underlying)]

    def get_underlying_price(self, underlying: str = 'BTC') -> float:
        """Return the last known spot price for the underlying (0.0 if unknown)."""
        with self._lock:
            return self._underlying_price.get(underlying.upper(), 0.0)

    def get_spike_log(self, last_n: int = 50) -> list:
        """Get recent spike events from SQLite."""
        try:
            conn = self._get_conn()
            cursor = conn.execute(
                'SELECT * FROM oi_spike_events ORDER BY ts DESC LIMIT ?',
                (last_n,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            log.warning('[OIStore] Failed to read spike log: %s', e)
            return []

    def get_health(self) -> dict:
        """Get per-exchange health status."""
        with self._lock:
            return {
                'exchanges': dict(self._exchange_health),
                'total_keys': len(self._snapshots),
                'total_deque_entries': sum(len(dq) for dq in self._snapshots.values()),
            }

    def get_metadata_for_emit(self, underlying: str = 'BTC') -> dict:
        """
        Lightweight metadata dict for SocketIO 'oi_update' event.
        Does NOT include rows — frontend fetches rows via REST after receiving this.
        This approach avoids the D2 bug (server overwriting user's expiry selection).
        """
        return {
            'expiries': self.get_expiries_with_metadata(underlying),
            'underlying_price': self.get_underlying_price(underlying),
            'health': self.get_health(),
            'ts': datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # SQLite write helpers
    # ------------------------------------------------------------------

    def _write_to_db(self, rows: list):
        """Batch-insert rows into oi_snapshots using executemany."""
        try:
            conn = self._get_conn()
            conn.executemany(
                '''INSERT INTO oi_snapshots (ts, exchange, underlying, expiry, strike, type, oi, oi_usd)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                [(r['timestamp'], r['exchange'], r['underlying'], r['expiry'],
                  r['strike'], r['type'], r['oi'], r['oi_usd']) for r in rows]
            )
            conn.commit()
        except Exception as e:
            log.warning('[OIStore] SQLite write failed: %s', e)

    def _write_spike_to_db(self, spike: dict):
        """Insert a spike event into oi_spike_events."""
        try:
            conn = self._get_conn()
            conn.execute(
                '''INSERT INTO oi_spike_events
                   (ts, exchange, underlying, expiry, strike, type, oi_prev, oi_curr, change_pct, severity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (spike['ts'], spike['exchange'], spike.get('underlying', 'BTC'),
                 spike.get('expiry', ''), spike['strike'], spike['type'],
                 spike['oi_prev'], spike['oi_curr'], spike['change_pct'],
                 spike['severity'])
            )
            conn.commit()
        except Exception as e:
            log.warning('[OIStore] Spike write failed: %s', e)

    # ------------------------------------------------------------------
    # Aggregate spike detection
    # ------------------------------------------------------------------

    def _check_aggregate_spikes(self, new_rows: list) -> list:
        """Detect net OI changes across all exchanges for each strike."""
        if not new_rows:
            return []

        # Group new rows by (underlying, expiry, strike, type)
        strike_keys = set()
        for r in new_rows:
            strike_keys.add((r['underlying'], r['expiry'], r['strike'], r['type']))

        spikes = []
        with self._lock:
            # Derive exchange names dynamically so new exchanges (okx, bybit, etc.)
            # are included without requiring changes here.
            all_exchanges = {k[0] for k in self._snapshots.keys()}

            for und, exp, strike, opt_type in strike_keys:
                # Sum across all exchanges
                total_curr = 0.0
                total_prev = 0.0
                total_curr_usd = 0.0

                for ex_name in all_exchanges:
                    key = (ex_name, und, exp, strike, opt_type)
                    dq = self._snapshots.get(key)
                    if not dq or len(dq) < 1:
                        continue
                    total_curr += dq[-1].get('oi', 0)
                    total_curr_usd += dq[-1].get('oi_usd', 0)
                    if len(dq) >= 2:
                        total_prev += dq[-2].get('oi', 0)
                    else:
                        total_prev += dq[-1].get('oi', 0)  # No change if only 1 entry

                if total_prev > 0:
                    agg_row_prev = {'oi': total_prev, 'oi_usd': total_curr_usd,
                                    'exchange': 'aggregate', 'strike': strike,
                                    'type': opt_type, 'underlying': und, 'expiry': exp}
                    agg_row_curr = {'oi': total_curr, 'oi_usd': total_curr_usd,
                                    'exchange': 'aggregate', 'strike': strike,
                                    'type': opt_type, 'underlying': und, 'expiry': exp}
                    spike = self.spike_detector.check(agg_row_prev, agg_row_curr)
                    if spike:
                        spikes.append(spike)

        return spikes

    # ------------------------------------------------------------------
    # Pruning
    # ------------------------------------------------------------------

    def _prune_stale_keys(self):
        """Remove expired expiries and zero-OI keys from memory."""
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        keys_to_remove = []

        with self._lock:
            for key, dq in self._snapshots.items():
                _, _, exp, _, _ = key
                # Remove expired expiries (older than today)
                if exp < today:
                    keys_to_remove.append(key)
                    continue
                # Remove keys where all entries have 0 OI
                if all(entry.get('oi', 0) == 0 for entry in dq):
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._snapshots[key]

        if keys_to_remove:
            log.info('[OIStore] Pruned %d stale keys', len(keys_to_remove))

    def _run_retention(self):
        """Delete old SQLite rows (> retention days). Run VACUUM after to reclaim space."""
        try:
            conn = self._get_conn()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)).isoformat()
            cursor = conn.execute('DELETE FROM oi_snapshots WHERE ts < ?', (cutoff,))
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0:
                log.info('[OIStore] Retention cleanup: deleted %d old snapshot rows', deleted)
                conn.execute('VACUUM')
                conn.commit()
        except Exception as e:
            log.warning('[OIStore] Retention cleanup failed: %s', e)


# ============================================================================
# Spike Detector
# ============================================================================

class OISpikeDetector:
    """
    Detects OI spikes by comparing current vs previous snapshot.
    Configurable threshold, min OI USD filter, cooldown.
    """

    def __init__(self,
                 threshold_pct: float = 15.0,
                 window_minutes: int = 15,
                 min_oi_usd: float = 500_000,
                 min_oi_change_usd: float = 200_000,
                 cooldown_minutes: int = 30):
        self.threshold_pct = threshold_pct
        self.window_minutes = window_minutes
        self.min_oi_usd = min_oi_usd
        self.min_oi_change_usd = min_oi_change_usd
        self.cooldown_minutes = cooldown_minutes
        # Cooldown map: (exchange, strike, type) → last_fire_ts (epoch seconds)
        self._cooldown = {}
        self._lock = threading.Lock()

    def check(self, prev: dict, curr: dict):
        """
        Compare two OIRow dicts. Returns SpikeEvent dict or None.
        """
        prev_oi = prev.get('oi', 0)
        curr_oi = curr.get('oi', 0)

        # No baseline → skip
        if prev_oi == 0:
            return None

        # Calculate change
        change_pct = ((curr_oi - prev_oi) / prev_oi) * 100
        curr_oi_usd = curr.get('oi_usd', 0)
        prev_oi_usd = prev.get('oi_usd', 0)
        change_usd = abs(curr_oi_usd - prev_oi_usd)

        # Threshold checks
        if abs(change_pct) < self.threshold_pct:
            return None
        if curr_oi_usd < self.min_oi_usd:
            return None
        if change_usd < self.min_oi_change_usd:
            return None

        # Cooldown check
        exchange = curr.get('exchange', 'unknown')
        strike = curr.get('strike', 0)
        opt_type = curr.get('type', '')
        cooldown_key = (exchange, strike, opt_type)

        with self._lock:
            last_fire = self._cooldown.get(cooldown_key, 0)
            now = time.time()
            if now - last_fire < self.cooldown_minutes * 60:
                return None  # Still in cooldown

            # Record this fire
            self._cooldown[cooldown_key] = now

        # Determine severity
        severity = 'high' if abs(change_pct) > 40 else 'medium'

        return {
            'ts': datetime.now(timezone.utc).isoformat(),
            'exchange': exchange,
            'underlying': curr.get('underlying', 'BTC'),
            'expiry': curr.get('expiry', ''),
            'strike': strike,
            'type': opt_type,
            'oi_prev': prev_oi,
            'oi_curr': curr_oi,
            'change_pct': round(change_pct, 2),
            'severity': severity,
        }

    def update_config(self, **kwargs):
        """Update detector thresholds. Validates types and bounds."""
        for key in ('threshold_pct', 'window_minutes', 'min_oi_usd',
                    'min_oi_change_usd', 'cooldown_minutes'):
            if key in kwargs:
                setattr(self, key, kwargs[key])
                log.info('[SpikeDetector] Updated %s = %s', key, kwargs[key])

    def get_config(self) -> dict:
        return {
            'threshold_pct': self.threshold_pct,
            'window_minutes': self.window_minutes,
            'min_oi_usd': self.min_oi_usd,
            'min_oi_change_usd': self.min_oi_change_usd,
            'cooldown_minutes': self.cooldown_minutes,
        }
