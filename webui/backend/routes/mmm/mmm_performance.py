"""
mmm_performance.py — Performance Intelligence Layer

Evaluates session quality at session end and stores results in SQL.
NO writes during heartbeat. Collects data in-memory, writes ONCE at stop.

Phases: ENTRY (0-20%) → ACTIVE (20-70%) → EXIT_PREP (70-90%) → EXIT (90-100%)
"""

import logging
import math
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

PHASE_ENTRY = 'ENTRY'         # 0-20% of session
PHASE_ACTIVE = 'ACTIVE'       # 20-70%
PHASE_EXIT_PREP = 'EXIT_PREP' # 70-90%
PHASE_EXIT = 'EXIT'           # 90-100%

PHASE_BOUNDARIES = [
    (0.0, 0.20, PHASE_ENTRY),
    (0.20, 0.70, PHASE_ACTIVE),
    (0.70, 0.90, PHASE_EXIT_PREP),
    (0.90, 1.0, PHASE_EXIT),
]

EXIT_CLEAN = 'CLEAN'       # >85% closed before deadline
EXIT_MODERATE = 'MODERATE'  # 50-85%
EXIT_MESSY = 'MESSY'        # <50%

# DB path — same directory as mmm_sessions.db
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')


# =============================================================================
# Phase Classification
# =============================================================================

def get_session_phase(now: datetime, start_time: datetime, end_time: datetime) -> str:
    """Classify current time into session phase based on elapsed percentage."""
    total = (end_time - start_time).total_seconds()
    if total <= 0:
        return PHASE_ACTIVE
    elapsed = (now - start_time).total_seconds()
    pct = max(0.0, min(1.0, elapsed / total))
    for lo, hi, phase in PHASE_BOUNDARIES:
        if lo <= pct < hi:
            return phase
    return PHASE_EXIT


# =============================================================================
# In-Memory Collector (attached to monitor, zero DB writes)
# =============================================================================

class PerformanceCollector:
    """Collects performance data during session lifetime. Zero I/O."""

    def __init__(self, session_id: str, start_time: datetime, end_time: datetime):
        self.session_id = session_id
        self.start_time = start_time
        self.end_time = end_time
        self._last_phase = None

        # Phase P&L snapshots: {phase: {total, realized, unrealized}}
        self.phase_snapshots: Dict[str, Dict] = {}

        # Track phase transitions
        self._current_phase = PHASE_ENTRY

    def on_heartbeat(self, now: datetime, total_pnl: float, realized_pnl: float, unrealized_pnl: float):
        """Called each heartbeat to track phase transitions. No DB writes."""
        phase = get_session_phase(now, self.start_time, self.end_time)

        # Capture snapshot at phase transition
        if phase != self._current_phase:
            # Save the P&L at the moment we leave the old phase
            self.phase_snapshots[self._current_phase] = {
                'total_pnl': total_pnl,
                'realized_pnl': realized_pnl,
                'unrealized_pnl': unrealized_pnl,
                'timestamp': now.isoformat(),
            }
            self._current_phase = phase

    def get_current_phase(self) -> str:
        return self._current_phase


# =============================================================================
# Adjustment Quality Analysis (runs ONCE at session end)
# =============================================================================

def classify_adjustments(adjustment_history: List[Dict]) -> Dict:
    """
    Classify each adjustment as GOOD or BAD based on subsequent price action.

    GOOD: spot continued moving in the aggressor direction (adjustment was warranted)
    BAD: spot reversed within the next 2-3 entries (whipsaw / unnecessary adjustment)
    """
    total = len(adjustment_history)
    if total == 0:
        return {
            'total_adjustments': 0,
            'good_adjustments': 0,
            'bad_adjustments': 0,
            'neutral_adjustments': 0,
            'adjustment_efficiency': 0.0,
            'classifications': [],
        }

    good = 0
    bad = 0
    neutral = 0
    classifications = []

    for i, adj in enumerate(adjustment_history):
        # Skip non-standard adjustments
        adj_type = adj.get('type', '')
        if adj_type in ('strike_shift', 'recycle', 'harvest', 'atm_shield'):
            neutral += 1
            classifications.append({'index': i, 'classification': 'NEUTRAL', 'reason': adj_type})
            continue

        spot_at_adj = adj.get('spot', 0)
        aggressor = adj.get('aggressor', '').upper()
        if not spot_at_adj or not aggressor or aggressor == 'NONE':
            neutral += 1
            classifications.append({'index': i, 'classification': 'NEUTRAL', 'reason': 'no_data'})
            continue

        # Look at spot in the next 2-3 adjustments
        future_spots = []
        for j in range(i + 1, min(i + 4, total)):
            fs = adjustment_history[j].get('spot', 0)
            if fs:
                future_spots.append(fs)

        if not future_spots:
            # Last adjustment(s) — can't evaluate
            neutral += 1
            classifications.append({'index': i, 'classification': 'NEUTRAL', 'reason': 'end_of_session'})
            continue

        avg_future_spot = sum(future_spots) / len(future_spots)
        spot_move = avg_future_spot - spot_at_adj

        # CE aggressor means spot went UP → if spot continued up, adjustment was GOOD
        # PE aggressor means spot went DOWN → if spot continued down, adjustment was GOOD
        if aggressor == 'CE':
            is_good = spot_move > 0  # continued upward
        else:
            is_good = spot_move < 0  # continued downward

        if is_good:
            good += 1
            classifications.append({'index': i, 'classification': 'GOOD'})
        else:
            bad += 1
            classifications.append({'index': i, 'classification': 'BAD'})

    scoreable = good + bad
    efficiency = (good / scoreable * 100) if scoreable > 0 else 0.0

    return {
        'total_adjustments': total,
        'good_adjustments': good,
        'bad_adjustments': bad,
        'neutral_adjustments': neutral,
        'adjustment_efficiency': round(efficiency, 1),
        'classifications': classifications,
    }


# =============================================================================
# Exit Quality Analysis
# =============================================================================

def classify_exit(session: Dict) -> Tuple[str, float]:
    """
    Evaluate exit quality based on how positions were closed.

    CLEAN (>85%): most positions closed before auto_close / expiry
    MODERATE (50-85%): mixed
    MESSY (<50%): mostly force-closed or left to expiry
    """
    close_at_5_count = session.get('close_at_5_count', 0)
    harvest_count = session.get('harvest_count', 0)
    graceful_closes = close_at_5_count + harvest_count

    # Count total positions that were ever opened
    ce_total_traded = session.get('analytics', {}).get('total_ce_lots_traded', 0)
    pe_total_traded = session.get('analytics', {}).get('total_pe_lots_traded', 0)
    total_positions = ce_total_traded + pe_total_traded

    if total_positions == 0:
        return EXIT_CLEAN, 100.0

    # Graceful closes vs total traded
    # Each close_at_5 event can close multiple lots, but the count is events
    # Use lots freed as a better proxy
    harvest_lots = session.get('harvest_lots_freed', 0)

    # Check remaining open positions at session end
    ce_remaining = session.get('ce', {}).get('total_lots', 0)
    pe_remaining = session.get('pe', {}).get('total_lots', 0)
    remaining = ce_remaining + pe_remaining

    if total_positions == 0:
        pct_closed = 100.0
    else:
        closed_lots = total_positions - remaining
        pct_closed = max(0.0, min(100.0, (closed_lots / total_positions) * 100))

    # Check for force close events
    stop_reason = session.get('_stopped_reason', '')
    was_force_closed = any(kw in stop_reason.lower() for kw in ['max_loss', 'emergency', 'critical', 'force'])

    if was_force_closed:
        # Force close is always messy regardless of numbers
        return EXIT_MESSY, pct_closed

    if pct_closed > 85:
        return EXIT_CLEAN, round(pct_closed, 1)
    elif pct_closed > 50:
        return EXIT_MODERATE, round(pct_closed, 1)
    else:
        return EXIT_MESSY, round(pct_closed, 1)


# =============================================================================
# Session Score
# =============================================================================

def compute_session_score(
    adjustment_efficiency: float,
    exit_quality: str,
    max_drawdown: float,
    peak_pnl: float,
    total_pnl: float,
    is_running: bool = False,
) -> float:
    """
    Compute session score (0-10).

    adjustment_score (0-4): based on efficiency %
    exit_score (0-3): based on exit quality (omitted for RUNNING sessions)
    drawdown_score (0-3): based on max drawdown relative to peak
    """
    # Adjustment score: 0-4
    if adjustment_efficiency >= 80:
        adj_score = 4.0
    elif adjustment_efficiency >= 60:
        adj_score = 3.0
    elif adjustment_efficiency >= 40:
        adj_score = 2.0
    elif adjustment_efficiency >= 20:
        adj_score = 1.0
    else:
        adj_score = 0.0

    # Exit score: 0-3 (omitted for live sessions — not meaningful yet)
    if is_running:
        exit_score = 0.0
        exit_max = 0.0  # score is out of 7 for running sessions
    else:
        exit_scores = {EXIT_CLEAN: 3.0, EXIT_MODERATE: 1.5, EXIT_MESSY: 0.0}
        exit_score = exit_scores.get(exit_quality, 0.0)
        exit_max = 3.0

    # Drawdown score: 0-3 (how well drawdown was contained)
    if peak_pnl > 0 and max_drawdown > 0:
        dd_ratio = max_drawdown / peak_pnl
        if dd_ratio < 0.2:
            dd_score = 3.0
        elif dd_ratio < 0.4:
            dd_score = 2.0
        elif dd_ratio < 0.6:
            dd_score = 1.0
        else:
            dd_score = 0.0
    elif total_pnl >= 0:
        dd_score = 3.0  # Profitable with no significant drawdown
    else:
        dd_score = 0.0  # Net loss

    raw = adj_score + exit_score + dd_score
    max_score = 4.0 + exit_max + 3.0
    # Normalise to 0-10
    return round((raw / max_score) * 10, 1) if max_score > 0 else 0.0


# =============================================================================
# Final Analysis (called ONCE at session end)
# =============================================================================

def analyze_session(session: Dict, collector: Optional[PerformanceCollector] = None) -> Dict:
    """
    Run full performance analysis on a completed session.
    Called once from monitor.stop(). Returns dict ready for SQL insert.
    """
    sid = session.get('session_id', '')
    now = datetime.now(timezone.utc)

    # Timing
    start_str = session.get('analytics', {}).get('session_start_time') or session.get('entry_time') or session.get('created_at', '')
    end_str = session.get('analytics', {}).get('session_end_time') or now.isoformat()

    try:
        start_dt = datetime.fromisoformat(start_str)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        start_dt = now

    try:
        end_dt = datetime.fromisoformat(end_str)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        end_dt = now

    duration_minutes = max(0, (end_dt - start_dt).total_seconds() / 60)

    # P&L
    total_pnl = session.get('realized_pnl', 0) + session.get('unrealized_pnl', 0)
    realized_pnl = session.get('realized_pnl', 0)
    peak_pnl = session.get('peak_pnl', 0)
    max_drawdown = session.get('analytics', {}).get('max_drawdown_from_peak', 0)

    # Phase P&L — derive from pnl_history stored in session state
    # pnl_history: [{timestamp, total_pnl, realized, unrealized}, ...]
    entry_pnl = 0.0
    active_pnl = 0.0
    exit_pnl = 0.0
    pnl_history = session.get('pnl_history', [])
    if pnl_history and duration_minutes > 0:
        try:
            # Find the total_pnl value at each phase boundary
            boundary_active = start_dt.timestamp() + (end_dt - start_dt).total_seconds() * 0.20
            boundary_exit   = start_dt.timestamp() + (end_dt - start_dt).total_seconds() * 0.70

            pnl_at_active_boundary = None
            pnl_at_exit_boundary   = None

            for entry in pnl_history:
                ts_str = entry.get('timestamp', '')
                if not ts_str:
                    continue
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                t = ts.timestamp()
                val = entry.get('total_pnl', 0.0) or 0.0

                if pnl_at_active_boundary is None and t >= boundary_active:
                    pnl_at_active_boundary = val
                if pnl_at_exit_boundary is None and t >= boundary_exit:
                    pnl_at_exit_boundary = val

            first_pnl = (pnl_history[0].get('total_pnl') or 0.0) if pnl_history else 0.0
            pnl_at_active = pnl_at_active_boundary if pnl_at_active_boundary is not None else total_pnl
            pnl_at_exit   = pnl_at_exit_boundary   if pnl_at_exit_boundary   is not None else total_pnl

            entry_pnl  = round(pnl_at_active - first_pnl, 4)
            active_pnl = round(pnl_at_exit - pnl_at_active, 4)
            exit_pnl   = round(total_pnl - pnl_at_exit, 4)
        except Exception:
            pass  # Leave as 0.0 if pnl_history is malformed

    # Adjustment quality
    adj_history = session.get('adjustment_history', [])
    adj_result = classify_adjustments(adj_history)

    # Exit quality — skip for RUNNING sessions (not meaningful yet)
    is_running = session.get('strategy_status', '') == 'RUNNING'
    if is_running:
        exit_quality = 'RUNNING'
        exit_pct_closed = 0.0
    else:
        exit_quality, exit_pct_closed = classify_exit(session)

    # Session score — omit exit component for RUNNING sessions
    score = compute_session_score(
        adj_result['adjustment_efficiency'],
        exit_quality,
        abs(max_drawdown),
        peak_pnl,
        total_pnl,
        is_running=is_running,
    )

    return {
        'session_id': sid,
        'start_time': start_dt.isoformat(),
        'end_time': end_dt.isoformat(),
        'duration_minutes': round(duration_minutes, 1),
        'total_pnl': round(total_pnl, 4),
        'realized_pnl': round(realized_pnl, 4),
        'max_drawdown': round(abs(max_drawdown), 4),
        'peak_pnl': round(peak_pnl, 4),
        'entry_pnl': round(entry_pnl, 4),
        'active_pnl': round(active_pnl, 4),
        'exit_pnl': round(exit_pnl, 4),
        'total_adjustments': adj_result['total_adjustments'],
        'good_adjustments': adj_result['good_adjustments'],
        'bad_adjustments': adj_result['bad_adjustments'],
        'adjustment_efficiency': adj_result['adjustment_efficiency'],
        'exit_quality': exit_quality,
        'exit_pct_closed': round(exit_pct_closed, 1),
        'session_score': score,
        'created_at': now.isoformat(),
    }


# =============================================================================
# SQL Storage (singleton, same DB as mmm_sessions)
# =============================================================================

class PerformanceStorage:
    """SQLite storage for performance_sessions table."""

    def __init__(self):
        self.db_path = os.path.join(DATA_DIR, 'mmm_sessions.db')
        self._init_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_table(self):
        conn = self._get_conn()
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS performance_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    start_time TEXT,
                    end_time TEXT,
                    duration_minutes REAL,
                    total_pnl REAL,
                    realized_pnl REAL,
                    max_drawdown REAL,
                    peak_pnl REAL,
                    entry_pnl REAL,
                    active_pnl REAL,
                    exit_pnl REAL,
                    total_adjustments INTEGER,
                    good_adjustments INTEGER,
                    bad_adjustments INTEGER,
                    adjustment_efficiency REAL,
                    exit_quality TEXT,
                    exit_pct_closed REAL,
                    session_score REAL,
                    created_at TEXT NOT NULL
                )
            ''')
            conn.commit()
            log.info("Performance sessions table ready")
        except Exception as e:
            log.error(f"Failed to create performance_sessions table: {e}")
        finally:
            conn.close()

    def save(self, record: Dict) -> bool:
        """Insert or replace a performance record. Called ONCE at session end."""
        conn = self._get_conn()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO performance_sessions (
                    session_id, start_time, end_time, duration_minutes,
                    total_pnl, realized_pnl, max_drawdown, peak_pnl,
                    entry_pnl, active_pnl, exit_pnl,
                    total_adjustments, good_adjustments, bad_adjustments, adjustment_efficiency,
                    exit_quality, exit_pct_closed, session_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record['session_id'], record['start_time'], record['end_time'],
                record['duration_minutes'], record['total_pnl'], record['realized_pnl'],
                record['max_drawdown'], record['peak_pnl'],
                record['entry_pnl'], record['active_pnl'], record['exit_pnl'],
                record['total_adjustments'], record['good_adjustments'],
                record['bad_adjustments'], record['adjustment_efficiency'],
                record['exit_quality'], record['exit_pct_closed'],
                record['session_score'], record['created_at'],
            ))
            conn.commit()
            log.info(f"Saved performance record for {record['session_id']} (score={record['session_score']})")
            return True
        except Exception as e:
            log.error(f"Failed to save performance record: {e}")
            return False
        finally:
            conn.close()

    def get(self, session_id: str) -> Optional[Dict]:
        """Get performance record for a session."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                'SELECT * FROM performance_sessions WHERE session_id = ?',
                (session_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None
        except Exception as e:
            log.error(f"Failed to get performance record: {e}")
            return None
        finally:
            conn.close()

    def get_all(self, limit: int = 50) -> List[Dict]:
        """Get all performance records, most recent first."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                'SELECT * FROM performance_sessions ORDER BY created_at DESC LIMIT ?',
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            log.error(f"Failed to get performance records: {e}")
            return []
        finally:
            conn.close()

    def get_summary(self) -> Dict:
        """Aggregate stats across all sessions."""
        conn = self._get_conn()
        try:
            row = conn.execute('''
                SELECT
                    COUNT(*) as total_sessions,
                    AVG(session_score) as avg_score,
                    AVG(adjustment_efficiency) as avg_efficiency,
                    SUM(CASE WHEN exit_quality = 'CLEAN' THEN 1 ELSE 0 END) as clean_exits,
                    SUM(CASE WHEN exit_quality = 'MODERATE' THEN 1 ELSE 0 END) as moderate_exits,
                    SUM(CASE WHEN exit_quality = 'MESSY' THEN 1 ELSE 0 END) as messy_exits,
                    AVG(total_pnl) as avg_pnl,
                    SUM(total_pnl) as total_pnl,
                    MAX(session_score) as best_score,
                    MIN(session_score) as worst_score
                FROM performance_sessions
            ''').fetchone()
            if row:
                return dict(row)
            return {}
        except Exception as e:
            log.error(f"Failed to get performance summary: {e}")
            return {}
        finally:
            conn.close()


# Singleton
_perf_storage: Optional[PerformanceStorage] = None
_perf_storage_lock = threading.Lock()

def get_performance_storage() -> PerformanceStorage:
    global _perf_storage
    if _perf_storage is None:
        with _perf_storage_lock:
            if _perf_storage is None:
                _perf_storage = PerformanceStorage()
    return _perf_storage
