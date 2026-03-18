# MMM Trade Transparency System — Institutional-Grade Implementation Guide

> **Status:** Phase 1 ✅ COMPLETE | Phase 2 ✅ COMPLETE | Phase 3 ⬜ pending | Phase 4 ⬜ pending
> **Scope:** Every order fill, every penny of P&L, every operational state change — captured, persisted, verifiable.
> **Created:** 2026-03-18 | **Last updated:** 2026-03-18

---

## 1. Purpose & Non-Negotiable Requirements

MMM executes live BTC options orders with real money. This system transforms it from a black-box into a fully auditable engine:

| Requirement | Why |
|---|---|
| Every filled order recorded | Cannot argue about what the bot did |
| P&L computable purely from audit table | Session state is mutable — DB is truth |
| Write-once: no UPDATE/DELETE ever | Audit integrity |
| Idempotency: duplicate events ignored | Crash/restart must not double-count |
| Non-blocking: microseconds per write | Heartbeat cannot stall |
| Self-reconciliation: audit sum vs session state | Detect any discrepancy |

---

## 2. Architecture

```
All execution paths (async hot loop)
│
├── execute_adjustment() → fill confirmed → audit.enqueue()  [< 1µs, non-blocking]
├── close_position()     → fill confirmed → audit.enqueue()  [< 1µs]
├── _execute_entry_bg()  → fill confirmed → audit.enqueue()  [< 1µs, in sync thread]
├── _process_wind_down() → fill confirmed → audit.enqueue()  [< 1µs]
├── inject_position()    → fill confirmed → audit.enqueue()  [< 1µs, sync context]
├── close_strike_route() → fill confirmed → audit.enqueue()  [< 1µs, sync context]
├── perp_hedge execute() → fill confirmed → audit.enqueue()  [< 1µs]
└── Any state transition  → event_log.enqueue()              [< 1µs]
                                    │
                        queue.Queue(maxsize=2000)
                                    │
                    Background Daemon Thread (1 thread)
                    ├── WAL-mode SQLite
                    ├── Batch flush: every 10 entries OR every 2 seconds
                    ├── executemany() for batch efficiency
                    └── atexit handler: flush remaining on shutdown

Read Path (REST API, never in heartbeat)
├── GET /api/mmm/sessions/<id>/audit_log
├── GET /api/mmm/sessions/<id>/strike_summary
├── GET /api/mmm/sessions/<id>/pnl_attribution
└── GET /api/mmm/sessions/<id>/reconcile_audit
```

---

## 3. Database: Two Tables

**File:** `webui/backend/data/mmm_sessions.db` (existing SQLite — add tables here, do not create a new DB file)

---

### 3.1 Table: `position_audit_log`

Every order fill that affects real money. Write-once, never updated.

```sql
CREATE TABLE IF NOT EXISTS position_audit_log (
    -- Identity
    id                      INTEGER  PRIMARY KEY AUTOINCREMENT,
    idempotency_key         TEXT     UNIQUE,           -- prevents duplicate writes on restart

    -- Session
    session_id              TEXT     NOT NULL,
    expiry                  TEXT     NOT NULL,          -- e.g. "27Mar26"

    -- Timing (IST for display, UTC for ordering)
    timestamp_ist           TEXT     NOT NULL,          -- "2026-03-18T14:32:05+05:30"
    created_at              TEXT     NOT NULL,          -- UTC ISO8601 — authoritative for ordering

    -- Trade identity
    action                  TEXT     NOT NULL CHECK(action IN ('BUY','SELL')),
    option_type             TEXT     NOT NULL CHECK(option_type IN ('CE','PE','PERP')),
    strike                  INTEGER,                    -- NULL for PERP
    order_id                TEXT,                       -- Exchange order ID (may be empty for imports)

    -- Fill quantities
    quantity_requested      INTEGER  NOT NULL,          -- what we asked exchange for
    quantity_filled         INTEGER  NOT NULL,          -- actual confirmed fill
    is_partial_fill         INTEGER  NOT NULL DEFAULT 0,-- 1 if quantity_filled < quantity_requested

    -- Pricing (raw USD — exchange returns USD)
    premium                 REAL     NOT NULL,          -- fill price (USD per option, or USD/BTC for PERP)
    gross_premium_usd       REAL     NOT NULL,          -- quantity_filled × premium × 0.001

    -- P&L attribution (for BUY rows — computed at write time)
    closing_entry_premium   REAL,                       -- SELL premium of the position being closed
    closing_entry_lots      INTEGER,                    -- lots being closed
    realized_pnl_usd        REAL,                       -- (entry_prem - close_prem) × qty_filled × 0.001

    -- Event classification
    event_type              TEXT     NOT NULL,          -- see §3.1a ENUM
    adj_type                TEXT,                       -- standard | reversal | first_reversal | recycle_phase_a | recycle_phase_b | perp_buy | perp_sell
    mechanism               TEXT,                       -- close_at_5 | harvest | wind_down | recycler | atm_shield | emergency | operator | import | adopt

    -- Causal context (for ADJUSTMENT/REVERSAL rows)
    aggressor_side          TEXT,                       -- 'ce' | 'pe' — the side that triggered this
    trigger_premium         REAL,                       -- aggressor premium at trigger time
    trigger_snapshot_at     REAL,                       -- trigger baseline (what it needed to exceed)
    loss_covered_usd        REAL,                       -- total loss this adjustment was sized to cover

    -- System state at time of trade (for post-incident analysis)
    whipsaw_state           TEXT,                       -- NORMAL | CAUTION | RESTRICT | COOLDOWN
    margin_tier             TEXT,                       -- GREEN | YELLOW | ORANGE | RED | CRITICAL
    regime_action           TEXT,                       -- NORMAL | WARN | BLOCK_CE_SELLS | BLOCK_ALL_SELLS
    spot_price_usd          REAL,                       -- BTC spot price at execution time

    -- Human-readable
    remark                  TEXT     NOT NULL,

    -- Integrity
    written_at              TEXT     NOT NULL DEFAULT (datetime('now'))
);

-- Primary query: all trades for a session in time order
CREATE INDEX IF NOT EXISTS idx_pal_session_time
    ON position_audit_log (session_id, created_at);

-- Strike summary aggregation
CREATE INDEX IF NOT EXISTS idx_pal_session_strike
    ON position_audit_log (session_id, strike, option_type);

-- Dedup prevention
CREATE UNIQUE INDEX IF NOT EXISTS idx_pal_idempotency
    ON position_audit_log (idempotency_key)
    WHERE idempotency_key IS NOT NULL;
```

#### 3.1a `event_type` ENUM

| Value | Meaning |
|---|---|
| `ENTRY` | Initial session SELL (Mode A/B/C) or Operator Inject |
| `ADJUSTMENT` | Algo hedge SELL — standard trigger breach |
| `REVERSAL` | Algo hedge SELL — direction reversal triggered |
| `CLOSE` | BUY — close-at-5 threshold or M1 Harvest |
| `WIND_DOWN` | BUY — wind-down LIFO buyback (direct path in monitor) |
| `EXIT` | BUY — ATM shield, emergency, operator close-strike, max-loss |
| `RECYCLE_BUY` | BUY — M2 Recycle Phase A (cheap frozen position buyback) |
| `RECYCLE_SELL` | SELL — M2 Recycle Phase B (sell at better strike) |
| `PERP_HEDGE` | BUY or SELL of BTCUSD perpetual futures (delta hedge) |

#### 3.1b `idempotency_key` construction

```python
# For exchange-filled orders (order_id known):
key = f"{session_id}:{order_id}:{action}"

# For import/adopt (no exchange order):
key = f"{session_id}:import:{side}:{int(strike)}:{timestamp_utc[:19]}"

# For perp hedge:
key = f"{session_id}:perp:{action}:{timestamp_utc[:19]}"
```

If an entry with the same key already exists (crash+restart replayed), SQLite UNIQUE constraint silently ignores the duplicate (INSERT OR IGNORE).

---

### 3.2 Table: `session_event_log`

Every operationally significant non-trade event. Write-once.

```sql
CREATE TABLE IF NOT EXISTS session_event_log (
    id              INTEGER  PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT     NOT NULL,
    timestamp_ist   TEXT     NOT NULL,
    created_at      TEXT     NOT NULL,

    -- Classification
    event_category  TEXT     NOT NULL,  -- see §3.2a
    event_type      TEXT     NOT NULL,  -- specific event name
    severity        TEXT     NOT NULL CHECK(severity IN ('INFO','WARN','CRITICAL')),

    -- Structured payload (JSON string, nullable)
    details         TEXT,

    -- Human-readable
    remark          TEXT     NOT NULL,

    written_at      TEXT     NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sel_session_time
    ON session_event_log (session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_sel_session_category
    ON session_event_log (session_id, event_category);
```

#### 3.2a `event_category` ENUM

| Category | Events Captured |
|---|---|
| `SESSION_LIFECYCLE` | created, started, paused, resumed, stopped, completed |
| `SAFETY` | position_cap_hit, max_loss_breach, asymmetry_alert, pnl_guardrail |
| `REGIME` | state change only (NORMAL→ALERT→GUARD→BLOCK→WIND_DOWN) |
| `MARGIN` | tier change only (GREEN→YELLOW→ORANGE→RED→CRITICAL) |
| `PARAM_CHANGE` | hot-reload applied: which param, old value, new value |
| `STRIKE_SHIFT` | new active_strike set: old strike, new strike, reason |
| `CIRCUIT_BREAKER` | state change: CLOSED→OPEN, OPEN→HALF_OPEN, HALF_OPEN→CLOSED |
| `RECONCILIATION` | mismatch detected, auto-corrected, or verified-ok |
| `BOTH_SIDES_UP` | triggered (both CE+PE exceeded), resolved (user decision) |
| `WHIPSAW` | guard level change (NORMAL→CAUTION→RESTRICT→COOLDOWN) |
| `ORDER_FAILURE` | failed order attempt (not a fill — for diagnosis) |
| `ATM_SHIELD` | activation, position close, re-establish, deactivation |

---

## 4. New Files to Create

### 4.1 `mmm_audit_remark.py`

Zero external dependencies. Pure string building.

```python
"""
MMM Audit Remark Engine — Converts system events to trader-readable strings.
All remarks must be readable by someone who is NOT a developer.
"""
import json

LOT_SIZE_BTC = 0.001

# ─────────────────────────────────────────────────────────────────────────────
# REMARK TEMPLATES
# ─────────────────────────────────────────────────────────────────────────────

def build_trade_remark(
    action: str,
    event_type: str,
    side: str,             # 'ce' | 'pe' | 'perp'
    strike: int = 0,
    lots: int = 0,
    premium: float = 0.0,
    mechanism: str = '',
    adj_type: str = '',
    aggressor: str = '',
    loss_covered: float = 0.0,
    threshold: float = 0.0,
    entry_premium: float = 0.0,
    realized_pnl: float = 0.0,
    new_strike: int = 0,
    profit_pct: float = 0.0,
    age_mins: int = 0,
    wind_down_pct: float = 0.0,
    proximity_pct: float = 0.0,
    is_partial: bool = False,
    **_extra,
) -> str:
    """
    Build a human-readable remark for a trade audit entry.
    Returns a concise, trader-facing string. Never raises.
    """
    try:
        partial_tag = " [PARTIAL FILL]" if is_partial else ""
        side_up = side.upper()
        gross = lots * premium * LOT_SIZE_BTC

        # ── SELL events ───────────────────────────────────────────────────
        if action == 'SELL':
            if event_type == 'ENTRY':
                if mechanism == 'import':
                    return f"Mode B import — user-supplied fill price (no order placed)"
                if mechanism == 'adopt':
                    return f"Mode C adopt — mapped from live exchange position"
                if mechanism == 'operator':
                    return f"Operator inject — manual lot placement at strike {strike}"
                return f"Initial entry — Short Strangle {side_up} leg | ${gross:.3f} collected{partial_tag}"

            if event_type in ('ADJUSTMENT', 'REVERSAL'):
                other = 'PE' if side_up == 'CE' else 'CE'
                agg_str = f"{other} aggressor" if aggressor else "aggressor"
                if event_type == 'REVERSAL':
                    detail = "adj P&L was negative" if adj_type == 'reversal' else "first reversal"
                    return f"Reversal: {agg_str} → {side_up} hedge | {detail} | ${gross:.3f} collected{partial_tag}"
                loss_str = f" | Loss covered: ${loss_covered:.3f}" if loss_covered > 0 else ""
                return (
                    f"{agg_str} → {side_up} hedge | {lots} lots @ ${premium:.2f}"
                    f"{loss_str} | ${gross:.3f} collected{partial_tag}"
                )

            if event_type == 'RECYCLE_SELL':
                return (
                    f"M2 Recycle Phase B — sell {lots} {side_up} @ new strike {new_strike} "
                    f"| ${gross:.3f} collected{partial_tag}"
                )

            if event_type == 'PERP_HEDGE':
                return f"Perp delta hedge SELL {lots} BTCUSD @ ${premium:.2f} | delta rebalance"

        # ── BUY events ────────────────────────────────────────────────────
        if action == 'BUY':
            pnl_str = f" | P&L: ${realized_pnl:.3f}" if realized_pnl != 0 else ""
            entry_str = f" (entry ${entry_premium:.2f})" if entry_premium > 0 else ""

            if event_type == 'CLOSE':
                if mechanism == 'harvest':
                    return (
                        f"M1 Harvest — {profit_pct:.0f}% profit locked"
                        f"{entry_str} | age {age_mins}min | ${premium:.2f}{pnl_str}{partial_tag}"
                    )
                thresh_str = f" ≤ ${threshold:.0f}" if threshold > 0 else ""
                return (
                    f"Close-at-5 threshold hit — premium ${premium:.2f}{thresh_str}"
                    f"{entry_str}{pnl_str}{partial_tag}"
                )

            if event_type == 'WIND_DOWN':
                pct_str = f" ({wind_down_pct:.0f}% of entry)" if wind_down_pct > 0 else ""
                return (
                    f"Wind-down LIFO buyback{pct_str}"
                    f"{entry_str} | close ${premium:.2f}{pnl_str}{partial_tag}"
                )

            if event_type == 'RECYCLE_BUY':
                return (
                    f"M2 Recycle Phase A — buy back cheap frozen lot{partial_tag}"
                    f"{entry_str} | close ${premium:.2f}{pnl_str}"
                )

            if event_type == 'EXIT':
                if mechanism == 'atm_shield':
                    return (
                        f"ATM Shield close — spot within {proximity_pct:.1f}% of strike {strike}"
                        f"{pnl_str}{partial_tag}"
                    )
                if mechanism == 'operator':
                    return f"Operator close-strike — manual buyback @ ${premium:.2f}{pnl_str}"
                if mechanism == 'emergency':
                    return f"Forced close — max-loss / emergency trigger{pnl_str}{partial_tag}"
                return f"Forced exit — {mechanism or 'auto_close'}{pnl_str}{partial_tag}"

            if event_type == 'PERP_HEDGE':
                return f"Perp delta hedge BUY {lots} BTCUSD @ ${premium:.2f}{pnl_str}"

        return f"{action} {side_up} @ {strike} | {event_type} | {mechanism}"

    except Exception:
        return f"{action} {side} | {event_type}"


def build_event_remark(event_category: str, event_type: str, **ctx) -> str:
    """Build a human-readable remark for a session_event_log entry. Never raises."""
    try:
        if event_category == 'SESSION_LIFECYCLE':
            msgs = {
                'created': 'Session created',
                'started': 'Session RUNNING — heartbeat monitor active',
                'paused': f"Session paused — {ctx.get('reason', '')}",
                'resumed': 'Session resumed',
                'stopped': f"Session stopped — {ctx.get('reason', '')}",
                'completed': 'Session complete — all positions closed',
            }
            return msgs.get(event_type, f"Session {event_type}")

        if event_category == 'SAFETY':
            msgs = {
                'position_cap_hit': f"Position cap reached ({ctx.get('side','?').upper()}: {ctx.get('active_lots',0)} active lots)",
                'max_loss_breach': f"Max-loss breached — P&L ${ctx.get('pnl',0):.2f} < limit ${ctx.get('limit',0):.2f}",
                'asymmetry_alert': f"Lot asymmetry {ctx.get('ratio',0):.1f}:1 ({ctx.get('heavy_side','?').upper()} heavy)",
                'pnl_guardrail': f"P&L guardrail {ctx.get('level','?').upper()} — ${ctx.get('pnl',0):.2f}",
            }
            return msgs.get(event_type, f"Safety: {event_type}")

        if event_category == 'REGIME':
            old = ctx.get('old_state', '?')
            new = ctx.get('new_state', '?')
            return f"Regime: {old} → {new} ({ctx.get('reason','')})"

        if event_category == 'MARGIN':
            old = ctx.get('old_tier', '?')
            new = ctx.get('new_tier', '?')
            return f"Margin tier: {old} → {new} (utilization {ctx.get('utilization_pct',0):.1f}%)"

        if event_category == 'PARAM_CHANGE':
            param = ctx.get('param', '?')
            old = ctx.get('old_value', '?')
            new = ctx.get('new_value', '?')
            return f"Param change: {param} {old!r} → {new!r}"

        if event_category == 'STRIKE_SHIFT':
            return (
                f"Strike shift {ctx.get('side','?').upper()}: "
                f"{ctx.get('old_strike',0)} → {ctx.get('new_strike',0)} "
                f"(old premium ${ctx.get('old_premium',0):.2f} below threshold)"
            )

        if event_category == 'CIRCUIT_BREAKER':
            return f"Circuit breaker: {ctx.get('old_state','?')} → {ctx.get('new_state','?')}"

        if event_category == 'RECONCILIATION':
            if ctx.get('mismatch'):
                return f"Reconciliation MISMATCH: {ctx.get('detail','')}"
            return "Reconciliation OK — audit sum matches session state"

        if event_category == 'BOTH_SIDES_UP':
            if event_type == 'triggered':
                return f"Both-sides-up: CE +{ctx.get('ce_excess',0):.2f} / PE +{ctx.get('pe_excess',0):.2f} — session paused"
            return f"Both-sides-up resolved: user chose {ctx.get('decision','?').upper()}"

        if event_category == 'WHIPSAW':
            return f"Whipsaw guard: {ctx.get('old_level','?')} → {ctx.get('new_level','?')} (score {ctx.get('score',0)})"

        if event_category == 'ORDER_FAILURE':
            return f"Order failed: {ctx.get('side','?').upper()} {ctx.get('action','?')} @ {ctx.get('strike',0)} — {ctx.get('error','unknown')}"

        if event_category == 'ATM_SHIELD':
            if event_type == 'activated':
                return f"ATM Shield activated — spot {ctx.get('proximity_pct',0):.2f}% from {ctx.get('side','?').upper()} strike {ctx.get('strike',0)}"
            if event_type == 'reestablished':
                return f"ATM Shield re-established at safer strike {ctx.get('new_strike',0)}"
            return f"ATM Shield: {event_type}"

        return f"{event_category}: {event_type}"

    except Exception:
        return f"{event_category}: {event_type}"
```

---

### 4.2 `mmm_audit_log.py`

The write engine. Singleton. Thread-safe.

```python
"""
MMM Position Audit Log — Institutional-grade trade ledger.

Design principles:
- enqueue() is fire-and-forget: < 1µs, never blocks, never raises
- Background daemon thread batches SQLite writes
- WAL mode: reads never block writes
- INSERT OR IGNORE on idempotency_key: crash-safe, no duplicates
- No UPDATE or DELETE ever issued against these tables
- atexit handler: flush remaining queue entries on backend shutdown

Usage:
    from .mmm_audit_log import get_audit_log, get_event_log
    get_audit_log().enqueue_trade(...)
    get_event_log().enqueue_event(...)
"""

import json
import logging
import queue
import sqlite3
import threading
import atexit
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

try:
    from zoneinfo import ZoneInfo
    _IST = ZoneInfo('Asia/Kolkata')
except ImportError:
    _IST = None

from .mmm_constants import LOT_SIZE_BTC

log = logging.getLogger('mmm_audit_log')

# ── Database path (same file as mmm_storage.py) ──────────────────────────────
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data'
)
DB_FILE = os.path.join(DATA_DIR, 'mmm_sessions.db')

# ── Writer config ─────────────────────────────────────────────────────────────
_BATCH_SIZE    = 10       # flush after this many queued entries
_FLUSH_SECS    = 2.0      # flush at least this often (seconds)
_MAX_QUEUE     = 2000     # drop with warning above this (practically impossible)


# ─────────────────────────────────────────────────────────────────────────────
# IST helper
# ─────────────────────────────────────────────────────────────────────────────

def _to_ist(utc_dt: datetime) -> str:
    """Return ISO8601 string in IST (+05:30)."""
    if _IST:
        return utc_dt.astimezone(_IST).isoformat()
    # Fallback: manual offset
    return (utc_dt + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%dT%H:%M:%S+05:30')


# ─────────────────────────────────────────────────────────────────────────────
# Trade Audit Log
# ─────────────────────────────────────────────────────────────────────────────

class MMMTradeAuditLog:
    """
    Write-only trade ledger. One background thread, one persistent writer connection.
    """

    def __init__(self, db_path: str = DB_FILE):
        self._db_path = db_path
        self._queue: queue.Queue = queue.Queue(maxsize=_MAX_QUEUE)
        self._writer_conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._init_schema()
        self._writer_thread = threading.Thread(
            target=self._writer_loop, name='mmm-audit-writer', daemon=True
        )
        self._writer_thread.start()
        atexit.register(self._flush_on_shutdown)

    def _get_write_conn(self) -> sqlite3.Connection:
        """Get or create the persistent writer connection (writer thread only)."""
        if self._writer_conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA wal_autocheckpoint=100")
            self._writer_conn = conn
        return self._writer_conn

    def _init_schema(self):
        """Create tables + indexes if not present. Safe to call on every startup."""
        conn = sqlite3.connect(self._db_path, timeout=10)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS position_audit_log (
                    id                      INTEGER  PRIMARY KEY AUTOINCREMENT,
                    idempotency_key         TEXT     UNIQUE,
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
                    remark                  TEXT     NOT NULL,
                    written_at              TEXT     NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_pal_session_time
                    ON position_audit_log (session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_pal_session_strike
                    ON position_audit_log (session_id, strike, option_type);
            """)
            conn.commit()
        finally:
            conn.close()

    def enqueue_trade(
        self,
        session_id: str,
        action: str,                   # 'BUY' | 'SELL'
        option_type: str,              # 'CE' | 'PE' | 'PERP'
        strike: Optional[int],
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
        Fire-and-forget. Completes in < 1µs. Never raises.
        All validation happens asynchronously in the writer thread.
        """
        try:
            now_utc = datetime.now(timezone.utc)
            gross = quantity_filled * premium * LOT_SIZE_BTC
            is_partial = 1 if quantity_filled < quantity_requested else 0

            # Auto-build idempotency key if not provided
            if not idempotency_key:
                if order_id:
                    idempotency_key = f"{session_id}:{order_id}:{action}"
                elif mechanism in ('import', 'adopt'):
                    idempotency_key = f"{session_id}:import:{option_type.lower()}:{strike}:{now_utc.isoformat()[:19]}"
                # else: no key — not idempotent (fine for intra-session writes)

            # Realized P&L for BUY rows
            if action == 'BUY' and closing_entry_premium > 0 and quantity_filled > 0:
                realized_pnl_usd = (closing_entry_premium - premium) * quantity_filled * LOT_SIZE_BTC

            entry = {
                'idempotency_key': idempotency_key or None,
                'session_id': session_id,
                'expiry': expiry,
                'timestamp_ist': _to_ist(now_utc),
                'created_at': now_utc.isoformat(),
                'action': action.upper(),
                'option_type': option_type.upper(),
                'strike': strike,
                'order_id': order_id or None,
                'quantity_requested': quantity_requested,
                'quantity_filled': quantity_filled,
                'is_partial_fill': is_partial,
                'premium': float(premium),
                'gross_premium_usd': float(gross),
                'closing_entry_premium': float(closing_entry_premium) if closing_entry_premium else None,
                'closing_entry_lots': int(closing_entry_lots) if closing_entry_lots else None,
                'realized_pnl_usd': float(realized_pnl_usd) if realized_pnl_usd != 0 else None,
                'event_type': event_type,
                'adj_type': adj_type or None,
                'mechanism': mechanism or None,
                'aggressor_side': aggressor_side or None,
                'trigger_premium': float(trigger_premium) if trigger_premium else None,
                'trigger_snapshot_at': float(trigger_snapshot_at) if trigger_snapshot_at else None,
                'loss_covered_usd': float(loss_covered_usd) if loss_covered_usd else None,
                'whipsaw_state': whipsaw_state or None,
                'margin_tier': margin_tier or None,
                'regime_action': regime_action or None,
                'spot_price_usd': float(spot_price_usd) if spot_price_usd else None,
                'remark': remark,
            }

            try:
                self._queue.put_nowait(entry)
            except queue.Full:
                log.error(
                    "audit_log queue full — trade entry DROPPED "
                    "(session=%s action=%s event=%s)",
                    session_id, action, event_type
                )
        except Exception:
            log.exception("audit_log.enqueue_trade() unexpectedly raised — entry dropped")

    def _writer_loop(self):
        """Daemon thread: batch-write to SQLite."""
        import time
        last_flush = time.monotonic()
        batch = []
        conn = self._get_write_conn()

        INSERT_SQL = """
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

        import time as _time
        while True:
            try:
                # Drain queue with timeout
                try:
                    entry = self._queue.get(timeout=_FLUSH_SECS)
                    batch.append(entry)
                    # Try to collect more without waiting
                    while len(batch) < _BATCH_SIZE:
                        try:
                            batch.append(self._queue.get_nowait())
                        except queue.Empty:
                            break
                except queue.Empty:
                    pass

                now = _time.monotonic()
                should_flush = (
                    len(batch) >= _BATCH_SIZE
                    or (batch and now - last_flush >= _FLUSH_SECS)
                )
                if should_flush and batch:
                    try:
                        conn.executemany(INSERT_SQL, batch)
                        conn.commit()
                        batch.clear()
                        last_flush = now
                    except sqlite3.Error as e:
                        log.error("audit_log DB write failed: %s — retrying next cycle", e)
                        try:
                            conn.rollback()
                        except Exception:
                            pass

            except Exception:
                log.exception("audit_log writer_loop unexpected error")

    def _flush_on_shutdown(self):
        """atexit: drain remaining queue entries before process exits."""
        try:
            batch = []
            while True:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if batch:
                conn = self._get_write_conn()
                conn.executemany(
                    "INSERT OR IGNORE INTO position_audit_log (idempotency_key, session_id, expiry, "
                    "timestamp_ist, created_at, action, option_type, strike, order_id, "
                    "quantity_requested, quantity_filled, is_partial_fill, premium, gross_premium_usd, "
                    "closing_entry_premium, closing_entry_lots, realized_pnl_usd, event_type, adj_type, "
                    "mechanism, aggressor_side, trigger_premium, trigger_snapshot_at, loss_covered_usd, "
                    "whipsaw_state, margin_tier, regime_action, spot_price_usd, remark) "
                    "VALUES (:idempotency_key, :session_id, :expiry, :timestamp_ist, :created_at, "
                    ":action, :option_type, :strike, :order_id, :quantity_requested, :quantity_filled, "
                    ":is_partial_fill, :premium, :gross_premium_usd, :closing_entry_premium, "
                    ":closing_entry_lots, :realized_pnl_usd, :event_type, :adj_type, :mechanism, "
                    ":aggressor_side, :trigger_premium, :trigger_snapshot_at, :loss_covered_usd, "
                    ":whipsaw_state, :margin_tier, :regime_action, :spot_price_usd, :remark)",
                    batch
                )
                conn.commit()
                log.info("audit_log: flushed %d pending entries on shutdown", len(batch))
        except Exception:
            log.exception("audit_log shutdown flush failed")

    def query_session(
        self,
        session_id: str,
        side: Optional[str] = None,
        event_type: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
    ) -> List[Dict]:
        """Read-only query. New connection per call. Never blocks writer."""
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            where = ["session_id = ?"]
            params = [session_id]
            if side:
                where.append("option_type = ?")
                params.append(side.upper())
            if event_type:
                where.append("event_type = ?")
                params.append(event_type.upper())
            offset = (page - 1) * limit
            params += [limit, offset]
            cursor = conn.execute(
                f"SELECT * FROM position_audit_log WHERE {' AND '.join(where)} "
                f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params
            )
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return rows
        except Exception:
            log.exception("audit_log.query_session() failed")
            return []

    def get_strike_summary(self, session_id: str) -> List[Dict]:
        """
        Aggregate P&L, quantities, and status per (strike, option_type).
        Uses SUM(realized_pnl_usd) for P&L — computed per-close at write time.
        """
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            cursor = conn.execute("""
                SELECT
                    COALESCE(strike, 0) AS strike,
                    option_type,
                    SUM(CASE WHEN action='SELL' THEN quantity_filled ELSE 0 END) AS total_sell_qty,
                    SUM(CASE WHEN action='BUY'  THEN quantity_filled ELSE 0 END) AS total_buy_qty,
                    SUM(CASE WHEN action='SELL' THEN quantity_filled * premium ELSE 0 END)
                        / NULLIF(SUM(CASE WHEN action='SELL' THEN quantity_filled ELSE 0 END), 0)
                        AS avg_sell_price,
                    SUM(CASE WHEN action='BUY' THEN quantity_filled * premium ELSE 0 END)
                        / NULLIF(SUM(CASE WHEN action='BUY' THEN quantity_filled ELSE 0 END), 0)
                        AS avg_buy_price,
                    SUM(COALESCE(realized_pnl_usd, 0)) AS realized_pnl_usd,
                    SUM(CASE WHEN action='SELL' THEN quantity_filled ELSE 0 END)
                        - SUM(CASE WHEN action='BUY' THEN quantity_filled ELSE 0 END)
                        AS open_qty,
                    COUNT(*) AS trade_count,
                    MIN(created_at) AS first_trade_at,
                    MAX(created_at) AS last_trade_at
                FROM position_audit_log
                WHERE session_id = ?
                  AND option_type IN ('CE','PE')
                GROUP BY strike, option_type
                ORDER BY strike, option_type
            """, [session_id])
            rows = []
            for r in cursor.fetchall():
                row = dict(r)
                row['status'] = 'ACTIVE' if row['open_qty'] > 0 else 'CLOSED'
                rows.append(row)
            conn.close()
            return rows
        except Exception:
            log.exception("audit_log.get_strike_summary() failed")
            return []

    def get_pnl_attribution(self, session_id: str) -> Dict:
        """
        P&L breakdown by event_type.
        Used for self-reconciliation: sum must equal session['realized_pnl'].
        """
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.execute("PRAGMA query_only=ON")
            cursor = conn.execute("""
                SELECT
                    event_type,
                    SUM(COALESCE(realized_pnl_usd, 0)) AS pnl_usd,
                    SUM(CASE WHEN action='SELL' THEN gross_premium_usd ELSE 0 END) AS premium_collected,
                    SUM(CASE WHEN action='BUY'  THEN gross_premium_usd ELSE 0 END) AS premium_paid,
                    COUNT(*) AS trade_count
                FROM position_audit_log
                WHERE session_id = ?
                GROUP BY event_type
            """, [session_id])
            rows = cursor.fetchall()
            conn.close()
            return {
                'by_event_type': [dict(zip([d[0] for d in cursor.description], r)) for r in rows]
                    if rows else [],
                'total_realized_pnl_usd': sum(r[1] for r in rows),
                'total_premium_collected_usd': sum(r[2] for r in rows),
                'total_premium_paid_usd': sum(r[3] for r in rows),
            }
        except Exception:
            log.exception("audit_log.get_pnl_attribution() failed")
            return {}


# ─────────────────────────────────────────────────────────────────────────────
# Session Event Log
# ─────────────────────────────────────────────────────────────────────────────

class MMMSessionEventLog:
    """Non-trade operational event log (regime, margin, params, safety events)."""

    def __init__(self, db_path: str = DB_FILE):
        self._db_path = db_path
        self._queue: queue.Queue = queue.Queue(maxsize=_MAX_QUEUE)
        self._writer_conn: Optional[sqlite3.Connection] = None
        self._init_schema()
        self._writer_thread = threading.Thread(
            target=self._writer_loop, name='mmm-event-writer', daemon=True
        )
        self._writer_thread.start()
        atexit.register(self._flush_on_shutdown)

    def _init_schema(self):
        conn = sqlite3.connect(self._db_path, timeout=10)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS session_event_log (
                    id              INTEGER  PRIMARY KEY AUTOINCREMENT,
                    session_id      TEXT     NOT NULL,
                    timestamp_ist   TEXT     NOT NULL,
                    created_at      TEXT     NOT NULL,
                    event_category  TEXT     NOT NULL,
                    event_type      TEXT     NOT NULL,
                    severity        TEXT     NOT NULL DEFAULT 'INFO',
                    details         TEXT,
                    remark          TEXT     NOT NULL,
                    written_at      TEXT     NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_sel_session_time
                    ON session_event_log (session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_sel_session_category
                    ON session_event_log (session_id, event_category);
            """)
            conn.commit()
        finally:
            conn.close()

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
                'session_id': session_id,
                'timestamp_ist': _to_ist(now_utc),
                'created_at': now_utc.isoformat(),
                'event_category': event_category,
                'event_type': event_type,
                'severity': severity.upper(),
                'details': json.dumps(details) if details else None,
                'remark': remark,
            }
            try:
                self._queue.put_nowait(entry)
            except queue.Full:
                log.error("event_log queue full — entry dropped (session=%s)", session_id)
        except Exception:
            log.exception("event_log.enqueue_event() unexpectedly raised")

    def _writer_loop(self):
        import time
        last_flush = time.monotonic()
        batch = []
        conn_holder = [None]

        INSERT_SQL = """
            INSERT INTO session_event_log
                (session_id, timestamp_ist, created_at, event_category, event_type,
                 severity, details, remark)
            VALUES
                (:session_id, :timestamp_ist, :created_at, :event_category, :event_type,
                 :severity, :details, :remark)
        """
        if conn_holder[0] is None:
            c = sqlite3.connect(self._db_path, timeout=10)
            c.execute("PRAGMA journal_mode=WAL")
            conn_holder[0] = c

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
                if (len(batch) >= _BATCH_SIZE or (batch and now - last_flush >= _FLUSH_SECS)):
                    try:
                        conn_holder[0].executemany(INSERT_SQL, batch)
                        conn_holder[0].commit()
                        batch.clear()
                        last_flush = now
                    except sqlite3.Error as e:
                        log.error("event_log DB write failed: %s", e)
                        try:
                            conn_holder[0].rollback()
                        except Exception:
                            pass
            except Exception:
                log.exception("event_log writer_loop error")

    def _flush_on_shutdown(self):
        try:
            batch = []
            while True:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if batch and self._writer_conn:
                self._writer_conn.executemany(
                    "INSERT INTO session_event_log (session_id, timestamp_ist, created_at, "
                    "event_category, event_type, severity, details, remark) VALUES "
                    "(:session_id, :timestamp_ist, :created_at, :event_category, :event_type, "
                    ":severity, :details, :remark)",
                    batch
                )
                self._writer_conn.commit()
        except Exception:
            log.exception("event_log shutdown flush failed")

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
            conn.execute("PRAGMA query_only=ON")
            where = ["session_id = ?"]
            params = [session_id]
            if category:
                where.append("event_category = ?")
                params.append(category)
            if severity:
                where.append("severity = ?")
                params.append(severity.upper())
            params.append(limit)
            cursor = conn.execute(
                f"SELECT * FROM session_event_log WHERE {' AND '.join(where)} "
                f"ORDER BY created_at DESC LIMIT ?",
                params
            )
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return rows
        except Exception:
            log.exception("event_log.query_session() failed")
            return []


# ─────────────────────────────────────────────────────────────────────────────
# Singletons
# ─────────────────────────────────────────────────────────────────────────────

_trade_log: Optional[MMMTradeAuditLog] = None
_event_log: Optional[MMMSessionEventLog] = None
_singleton_lock = threading.Lock()


def get_audit_log() -> MMMTradeAuditLog:
    global _trade_log
    if _trade_log is None:
        with _singleton_lock:
            if _trade_log is None:
                _trade_log = MMMTradeAuditLog(DB_FILE)
    return _trade_log


def get_event_log() -> MMMSessionEventLog:
    global _event_log
    if _event_log is None:
        with _singleton_lock:
            if _event_log is None:
                _event_log = MMMSessionEventLog(DB_FILE)
    return _event_log
```

---

## 5. Instrumentation Map — Exact File and Line

For each insertion point below, add the `enqueue_trade()` call **after** the success path is confirmed and **after** state is updated. Never insert before the fill is confirmed. Never insert in the exception/failure path (those go to session_event_log as ORDER_FAILURE).

---

### 5.1 ENTRY — `mmm_api.py` line 816

**After** `log_activity('entry_complete', ...)` at line 816, **before** `resolve_progress_activities()` at line 822.

Both CE and PE in Mode A fresh entry. Insert 2 rows.

```python
# ── AUDIT: Initial entry (Mode A — both legs filled) ─────────────────────
try:
    from .mmm_audit_log import get_audit_log
    from .mmm_audit_remark import build_trade_remark
    _aud = get_audit_log()
    for _side, _fill, _oid, _strike in [
        ('ce', ce_fill, ce_res.get('order_id',''), session['ce']['active_strike']),
        ('pe', pe_fill, pe_res.get('order_id',''), session['pe']['active_strike']),
    ]:
        _filled = ce_res.get('filled_size', lots) if _side == 'ce' else pe_res.get('filled_size', lots)
        if _filled is None or _filled <= 0:
            _filled = lots
        _aud.enqueue_trade(
            session_id=session_id,
            action='SELL',
            option_type=_side.upper(),
            strike=int(_strike),
            quantity_requested=lots,
            quantity_filled=_filled,
            premium=_fill,
            event_type='ENTRY',
            mechanism='fresh_entry',
            order_id=str(_oid),
            expiry=session.get('params', {}).get('expiry', ''),
            spot_price_usd=session.get('_regime_spot_price', 0),
            remark=build_trade_remark(
                action='SELL', event_type='ENTRY',
                side=_side, strike=int(_strike),
                lots=_filled, premium=_fill,
                mechanism='fresh_entry',
                is_partial=(_filled < lots),
            ),
        )
except Exception:
    pass  # audit must never abort trading logic
# ── END AUDIT ─────────────────────────────────────────────────────────────
```

---

### 5.2 ENTRY — `mmm_api.py` Mode B (resolve_partial_entry / manual import)

Around line 1094 where `session[side]['entry_fill_price'] = fill_price` is set for manual import. Insert 1 row per side confirmed.

```python
# ── AUDIT: Mode B import ──────────────────────────────────────────────────
try:
    from .mmm_audit_log import get_audit_log
    from .mmm_audit_remark import build_trade_remark
    get_audit_log().enqueue_trade(
        session_id=session_id,
        action='SELL',
        option_type=side.upper(),
        strike=int(session[side]['active_strike']),
        quantity_requested=lots,
        quantity_filled=lots,
        premium=fill_price,
        event_type='ENTRY',
        mechanism='import',
        expiry=session.get('params', {}).get('expiry', ''),
        remark=build_trade_remark(
            'SELL', 'ENTRY', side=side, mechanism='import',
            lots=lots, premium=fill_price,
        ),
    )
except Exception:
    pass
# ── END AUDIT ─────────────────────────────────────────────────────────────
```

---

### 5.3 ADJUSTMENT/REVERSAL — `mmm_engine.py` `execute_adjustment()` line ~756

**After** `clear_pending(session_id, hedge_side)` at line ~753, **before** the `return { 'success': True, ... }` at line 758.

```python
# ── AUDIT: Adjustment / Reversal sell ────────────────────────────────────
try:
    from .mmm_audit_log import get_audit_log
    from .mmm_audit_remark import build_trade_remark
    _event = 'REVERSAL' if adj_type in ('reversal', 'first_reversal') else 'ADJUSTMENT'
    _aggressor = 'pe' if hedge_side == 'ce' else 'ce'
    _side_state = session.get(hedge_side, {})
    _trig_snap = _side_state.get('trigger_snapshot', {}).get(
        str(int(round(float(hedge_strike)))), 0.0
    )
    # loss_covered is stored on session by _update_state_after_adjustment (if available)
    _loss = session.get('_last_adjustment_loss', 0.0)
    get_audit_log().enqueue_trade(
        session_id=session.get('session_id', ''),
        action='SELL',
        option_type=hedge_side.upper(),
        strike=int(hedge_strike),
        quantity_requested=lots_to_sell,
        quantity_filled=filled_lots,
        premium=fill_price,
        event_type=_event,
        adj_type=adj_type,
        mechanism='algo',
        aggressor_side=_aggressor,
        trigger_snapshot_at=_trig_snap,
        loss_covered_usd=_loss,
        order_id=str(result.get('order_id', '')),
        expiry=session.get('params', {}).get('expiry', ''),
        spot_price_usd=session.get('_regime_spot_price', 0),
        whipsaw_state=session.get('_whipsaw_state', ''),
        margin_tier=session.get('_margin_tier', ''),
        regime_action=str(session.get('_regime_action', '')),
        remark=build_trade_remark(
            'SELL', _event,
            side=hedge_side, strike=int(hedge_strike),
            lots=filled_lots, premium=fill_price,
            adj_type=adj_type, aggressor=_aggressor,
            loss_covered=_loss,
            is_partial=(filled_lots < lots_to_sell),
        ),
    )
except Exception:
    pass
# ── END AUDIT ─────────────────────────────────────────────────────────────
```

**Companion**: In `calculate_standard_loss()` and `calculate_reversal_loss()`, after the loss is computed, store it temporarily:
```python
session['_last_adjustment_loss'] = float(total_loss)  # used by audit log only
```
Clear after `execute_adjustment()` returns (or let it be overwritten next heartbeat).

---

### 5.4 CLOSE (all mechanisms) — `mmm_close_at_5.py` `close_position()` line ~529

**After** the `log_activity(mechanism, ...)` block at line ~516-530, **before** the observer `record_close()` call at line ~533.

```python
# ── AUDIT: Position buyback ───────────────────────────────────────────────
try:
    from .mmm_audit_log import get_audit_log
    from .mmm_audit_remark import build_trade_remark
    _MECH_EVENT = {
        'close_at_5':       'CLOSE',
        'harvest':          'CLOSE',
        'recycler':         'RECYCLE_BUY',
        'atm_shield':       'EXIT',
        'wind_down':        'WIND_DOWN',
        'both_sides_close': 'CLOSE',
        'emergency':        'EXIT',
        'operator':         'EXIT',
    }
    _event_type = _MECH_EVENT.get(mechanism, 'CLOSE')
    get_audit_log().enqueue_trade(
        session_id=session.get('session_id', ''),
        action='BUY',
        option_type=side.upper(),
        strike=int(strike),
        quantity_requested=lots,
        quantity_filled=actual_lots,
        premium=close_price,
        event_type=_event_type,
        mechanism=mechanism,
        order_id=str(result.get('order_id', '')),
        expiry=session.get('params', {}).get('expiry', ''),
        closing_entry_premium=float(entry_prem),
        closing_entry_lots=actual_lots,
        realized_pnl_usd=float(realized_pnl),
        spot_price_usd=session.get('_regime_spot_price', 0),
        margin_tier=session.get('_margin_tier', ''),
        remark=build_trade_remark(
            'BUY', _event_type,
            side=side, strike=int(strike),
            lots=actual_lots, premium=close_price,
            mechanism=mechanism,
            threshold=position.get('threshold_used', 5.0),
            entry_premium=float(entry_prem),
            realized_pnl=float(realized_pnl),
            is_partial=(actual_lots < lots),
        ),
    )
except Exception:
    pass
# ── END AUDIT ─────────────────────────────────────────────────────────────
```

---

### 5.5 WIND_DOWN direct path — `mmm_monitor.py` `_process_wind_down_buyback()` line ~2826

**After** `log_activity('wind_down', f'🌙 Wind-Down leg: Bought back ...')` at line 2826. This is the path that does NOT go through `close_position()` — it calls `smart_execute()` directly.

```python
# ── AUDIT: Wind-down LIFO buyback ─────────────────────────────────────────
try:
    from .mmm_audit_log import get_audit_log
    from .mmm_audit_remark import build_trade_remark
    get_audit_log().enqueue_trade(
        session_id=sid,
        action='BUY',
        option_type=aggressor.upper(),
        strike=int(strike_val),
        quantity_requested=group_lots,
        quantity_filled=actual_filled,
        premium=close_price,
        event_type='WIND_DOWN',
        mechanism='wind_down',
        order_id=str(result.get('order_id', '')),
        expiry=session.get('params', {}).get('expiry', ''),
        closing_entry_premium=float(group_avg_entry),
        closing_entry_lots=actual_filled,
        realized_pnl_usd=float(group_realized),
        spot_price_usd=session.get('_regime_spot_price', 0),
        remark=build_trade_remark(
            'BUY', 'WIND_DOWN',
            side=aggressor, strike=int(strike_val),
            lots=actual_filled, premium=close_price,
            mechanism='wind_down',
            entry_premium=float(group_avg_entry),
            realized_pnl=float(group_realized),
            is_partial=(actual_filled < group_lots),
        ),
    )
except Exception:
    pass
# ── END AUDIT ─────────────────────────────────────────────────────────────
```

---

### 5.6 OPERATOR INJECT — `mmm_api.py` line ~3420

**After** `premium_collected = fill_price * lots_param * LOT_SIZE_BTC` at line ~3420, **before** `session['total_premium_collected'] +=` at line 3421.

```python
# ── AUDIT: Operator inject ────────────────────────────────────────────────
try:
    from .mmm_audit_log import get_audit_log
    from .mmm_audit_remark import build_trade_remark
    _mech = 'adopt' if adopt else 'operator'
    get_audit_log().enqueue_trade(
        session_id=session_id,
        action='SELL',
        option_type=side_param.upper(),
        strike=int(strike_val),
        quantity_requested=lots_param,
        quantity_filled=lots_param,
        premium=fill_price,
        event_type='ENTRY',
        mechanism=_mech,
        order_id=order_id,
        expiry=params.get('expiry', ''),
        spot_price_usd=session.get('_regime_spot_price', 0),
        remark=build_trade_remark(
            'SELL', 'ENTRY',
            side=side_param, strike=int(strike_val),
            lots=lots_param, premium=fill_price,
            mechanism=_mech,
        ),
    )
except Exception:
    pass
# ── END AUDIT ─────────────────────────────────────────────────────────────
```

---

### 5.7 OPERATOR CLOSE-STRIKE — `mmm_api.py` line ~3932

**After** `log_activity('manual_close_strike', f'🔴 Close Strike OK: ...')` at line 3933, **before** `return jsonify(...)`.

The close-strike closes multiple positions in a single order. Total realized P&L is `total_realized`. The single audit row represents the aggregate buyback.

```python
# ── AUDIT: Operator close-strike ─────────────────────────────────────────
try:
    from .mmm_audit_log import get_audit_log
    from .mmm_audit_remark import build_trade_remark
    # Compute average entry premium across all closed positions
    _total_lots = sum(p.get('lots', 0) for p in target_positions)
    _weighted_entry = sum(
        float(p.get('entry_premium', p.get('premium', 0))) * p.get('lots', 0)
        for p in target_positions
    )
    _avg_entry = _weighted_entry / _total_lots if _total_lots > 0 else 0.0
    get_audit_log().enqueue_trade(
        session_id=session_id,
        action='BUY',
        option_type=side_param.upper(),
        strike=int(strike_val),
        quantity_requested=total_lots,
        quantity_filled=total_lots,
        premium=fill_price,
        event_type='EXIT',
        mechanism='operator',
        order_id=order_id,
        expiry=params.get('expiry', ''),
        closing_entry_premium=round(_avg_entry, 4),
        closing_entry_lots=total_lots,
        realized_pnl_usd=float(total_realized),
        spot_price_usd=session.get('_regime_spot_price', 0),
        remark=build_trade_remark(
            'BUY', 'EXIT',
            side=side_param, strike=int(strike_val),
            lots=total_lots, premium=fill_price,
            mechanism='operator',
            entry_premium=round(_avg_entry, 4),
            realized_pnl=float(total_realized),
        ),
    )
except Exception:
    pass
# ── END AUDIT ─────────────────────────────────────────────────────────────
```

---

### 5.8 PERP HEDGE — `mmm_perp_hedge.py` after `update_perp_state_after_fill()`

Lines ~688 and ~774 (both call `update_perp_state_after_fill`). Insert after each successful fill.

```python
# ── AUDIT: Perp hedge fill ────────────────────────────────────────────────
try:
    from .mmm_audit_log import get_audit_log
    from .mmm_audit_remark import build_trade_remark
    _action = 'SELL' if action == 'sell' else 'BUY'
    get_audit_log().enqueue_trade(
        session_id=session.get('session_id', ''),
        action=_action,
        option_type='PERP',
        strike=None,
        quantity_requested=required,
        quantity_filled=filled_lots,
        premium=fill_price,
        event_type='PERP_HEDGE',
        mechanism='perp_hedge',
        adj_type=f"perp_{action}",
        order_id=str(result.get('order_id', '')),
        expiry='',
        realized_pnl_usd=float(realized_pnl) if realized_pnl else 0.0,
        spot_price_usd=float(fill_price),
        remark=build_trade_remark(
            _action, 'PERP_HEDGE',
            side='perp', lots=filled_lots, premium=fill_price,
        ),
    )
except Exception:
    pass
# ── END AUDIT ─────────────────────────────────────────────────────────────
```

---

### 5.9 Session Event Log — Key Hook Points

For non-trade events, use `get_event_log().enqueue_event()`. Hook into existing `log_activity()` call sites:

| Event | File | Where to add | Category | severity |
|---|---|---|---|---|
| Session RUNNING | `mmm_api.py` line 825 | After `log_activity('session_started', ...)` | SESSION_LIFECYCLE | INFO |
| Session stopped | `mmm_api.py` stop endpoint | After status = 'STOPPED' | SESSION_LIFECYCLE | INFO |
| Session complete (both sides closed) | `mmm_monitor.py` | After `strategy_status = 'COMPLETE'` | SESSION_LIFECYCLE | INFO |
| Regime state change | `mmm_regime.py` | When `_action` changes value | REGIME | WARN if BLOCK, CRITICAL if FORCE_REDUCE |
| Margin tier change | `mmm_margin_guardian.py` | When `last_tier` changes | MARGIN | WARN if YELLOW, CRITICAL if RED |
| Position cap hit | `mmm_safety.py` | In `check_position_cap()` result | SAFETY | WARN |
| Max-loss breach | `mmm_monitor.py` | In max-loss check path | SAFETY | CRITICAL |
| Strike shift | `mmm_strike_shift.py` | After new active_strike set | STRIKE_SHIFT | INFO |
| Hot-reload applied | `mmm_config.py` | After params validated and merged | PARAM_CHANGE | INFO (per-param) |
| Both-sides-up triggered | `mmm_monitor.py` | When status = 'BOTH_SIDES_UP' | BOTH_SIDES_UP | WARN |
| Circuit breaker opened | `mmm_circuit_breaker.py` | On CLOSED → OPEN transition | CIRCUIT_BREAKER | WARN |
| Reconciliation mismatch | `mmm_monitor.py` | In reconciliation path | RECONCILIATION | CRITICAL |

---

## 6. Self-Reconciliation Module

### 6.1 New file: `mmm_audit_reconciler.py`

```python
"""
MMM Audit Reconciler — Verify position_audit_log matches session state.

Called: on-demand via API, never in heartbeat.
"""

def reconcile_session(session_id: str, session: dict, db_path: str = None) -> dict:
    """
    Compare audit log totals against live session state.
    Returns a reconciliation report with any discrepancies.
    """
    from .mmm_audit_log import get_audit_log
    from .mmm_constants import LOT_SIZE_BTC

    aud = get_audit_log()
    summary = aud.get_strike_summary(session_id)
    attribution = aud.get_pnl_attribution(session_id)

    # 1. P&L check: audit total vs session['realized_pnl']
    audit_total_pnl = attribution.get('total_realized_pnl_usd', 0.0)
    session_realized = session.get('realized_pnl', 0.0)
    pnl_delta = abs(audit_total_pnl - session_realized)
    pnl_ok = pnl_delta < 0.001  # $0.001 tolerance (rounding only)

    # 2. Open qty check: audit open_qty vs session active_lots
    discrepancies = []
    for row in summary:
        side = 'ce' if row['option_type'] == 'CE' else 'pe'
        strike = row['strike']
        audit_open = row['open_qty']

        # Find matching position in session
        side_state = session.get(side, {})
        session_lots = 0
        for pos in side_state.get('positions', []):
            if (abs(float(pos.get('strike', 0)) - strike) < 1
                    and pos.get('status') in ('active', 'shifted')):
                session_lots += pos.get('lots', 0)

        if audit_open != session_lots:
            discrepancies.append({
                'side': side.upper(),
                'strike': strike,
                'audit_open_qty': audit_open,
                'session_lots': session_lots,
                'delta': audit_open - session_lots,
            })

    return {
        'session_id': session_id,
        'pnl_ok': pnl_ok,
        'pnl_audit': round(audit_total_pnl, 6),
        'pnl_session': round(session_realized, 6),
        'pnl_delta': round(pnl_delta, 6),
        'position_discrepancies': discrepancies,
        'is_clean': pnl_ok and len(discrepancies) == 0,
    }
```

---

## 7. API Endpoints

Add to `mmm_api.py`:

```python
# ─────────────────────────────────────────────────────────────────────────────
# Trade Audit API
# ─────────────────────────────────────────────────────────────────────────────

@mmm_bp.route('/session/<session_id>/audit/trades', methods=['GET'])
def get_trade_audit(session_id: str):
    """
    GET /api/mmm/session/<id>/audit/trades
    ?side=CE&event_type=ADJUSTMENT&page=1&limit=100
    """
    from .mmm_audit_log import get_audit_log
    side       = request.args.get('side')
    event_type = request.args.get('event_type')
    page       = max(1, int(request.args.get('page', 1)))
    limit      = min(500, max(1, int(request.args.get('limit', 100))))
    rows = get_audit_log().query_session(session_id, side, event_type, page, limit)
    return jsonify({'rows': rows, 'page': page, 'limit': limit, 'count': len(rows)})


@mmm_bp.route('/session/<session_id>/audit/strike_summary', methods=['GET'])
def get_strike_summary(session_id: str):
    """
    GET /api/mmm/session/<id>/audit/strike_summary
    ?include_unrealized=true
    """
    from .mmm_audit_log import get_audit_log
    summary = get_audit_log().get_strike_summary(session_id)

    if request.args.get('include_unrealized') == 'true':
        # Fetch live premiums for ACTIVE strikes (best-effort, non-blocking)
        session = get_storage().get_session(session_id)
        if session:
            for row in summary:
                if row['status'] == 'ACTIVE' and row['open_qty'] > 0:
                    try:
                        from .mmm_executor import get_executor
                        from .mmm_initializer import get_initializer
                        side = 'call' if row['option_type'] == 'CE' else 'put'
                        expiry = session.get('params', {}).get('expiry', '')
                        sym = get_initializer().build_symbol('BTC', side, row['strike'], expiry)
                        mid = _run_sync_safe(get_executor().get_mid_price(sym))
                        if mid and mid > 0:
                            row['current_premium'] = round(mid, 2)
                            row['unrealized_pnl_usd'] = round(
                                (row['avg_sell_price'] - mid) * row['open_qty'] * 0.001, 6
                            )
                    except Exception:
                        row['current_premium'] = None
                        row['unrealized_pnl_usd'] = None

    return jsonify({'summary': summary})


@mmm_bp.route('/session/<session_id>/audit/pnl', methods=['GET'])
def get_pnl_attribution(session_id: str):
    """
    GET /api/mmm/session/<id>/audit/pnl
    P&L breakdown by event type. Source of truth for "where did the money go?"
    """
    from .mmm_audit_log import get_audit_log
    return jsonify(get_audit_log().get_pnl_attribution(session_id))


@mmm_bp.route('/session/<session_id>/audit/reconcile', methods=['GET'])
def reconcile_audit(session_id: str):
    """
    GET /api/mmm/session/<id>/audit/reconcile
    Compare audit log totals against live session state.
    """
    from .mmm_audit_reconciler import reconcile_session
    session = get_storage().get_session(session_id)
    if not session:
        return jsonify({'error': 'session not found'}), 404
    result = reconcile_session(session_id, session)
    status_code = 200 if result['is_clean'] else 409
    return jsonify(result), status_code


@mmm_bp.route('/session/<session_id>/audit/events', methods=['GET'])
def get_session_events(session_id: str):
    """
    GET /api/mmm/session/<id>/audit/events
    ?category=REGIME&severity=WARN&limit=100
    """
    from .mmm_audit_log import get_event_log
    category = request.args.get('category')
    severity = request.args.get('severity')
    limit    = min(500, max(1, int(request.args.get('limit', 100))))
    rows = get_event_log().query_session(session_id, category, severity, limit)
    return jsonify({'events': rows, 'count': len(rows)})
```

---

## 8. Frontend Components

### 8.1 `mmmService.js` — New API calls

```javascript
// Add to mmmService.js

async getTradeAudit(sessionId, { side, eventType, page = 1, limit = 100 } = {}) {
  const params = new URLSearchParams({ page, limit });
  if (side) params.append('side', side);
  if (eventType) params.append('event_type', eventType);
  const res = await fetch(`/api/mmm/session/${sessionId}/audit/trades?${params}`);
  return res.json();
},

async getStrikeSummary(sessionId, includeUnrealized = false) {
  const res = await fetch(
    `/api/mmm/session/${sessionId}/audit/strike_summary?include_unrealized=${includeUnrealized}`
  );
  return res.json();
},

async getPnLAttribution(sessionId) {
  const res = await fetch(`/api/mmm/session/${sessionId}/audit/pnl`);
  return res.json();
},

async reconcileAudit(sessionId) {
  const res = await fetch(`/api/mmm/session/${sessionId}/audit/reconcile`);
  return { status: res.status, data: await res.json() };
},

async getSessionEvents(sessionId, { category, severity, limit = 100 } = {}) {
  const params = new URLSearchParams({ limit });
  if (category) params.append('category', category);
  if (severity) params.append('severity', severity);
  const res = await fetch(`/api/mmm/session/${sessionId}/audit/events?${params}`);
  return res.json();
},
```

---

### 8.2 `MMMTradeAuditTable.js`

New component. Key design decisions:

```
┌─────────────────────────────────────────────────────────────────────┐
│ Trade Audit Log  [CE ▾] [All Events ▾]   [Export CSV]   ← 1/14 →  │
├────────────────┬──────┬──────┬────────┬─────┬─────────┬────────────┤
│ Time (IST)     │ Act  │ Type │ Strike │ Qty │ Premium │ Remark     │
├────────────────┼──────┼──────┼────────┼─────┼─────────┼────────────┤
│ 14:32:05 IST   │ SELL │ CE   │ 85000  │  10 │  142.50 │ Initial... │ ← light-red bg
│ 14:32:06 IST   │ SELL │ PE   │ 75000  │  10 │  138.20 │ Initial... │ ← light-red bg
│ 15:14:22 IST   │ SELL │ PE   │ 74000  │   5 │  201.80 │ CE aggr... │ ← amber bg (adj)
│ 16:42:11 IST   │ BUY  │ PE   │ 75000  │  10 │    4.80 │ Close-at-5 │ ← light-green bg
└────────────────┴──────┴──────┴────────┴─────┴─────────┴────────────┘
                                                          Total P&L: $X.XXX
```

**Row color coding:**
- `SELL ENTRY` → light blue background
- `SELL ADJUSTMENT` → light amber / orange background
- `SELL REVERSAL` → yellow background
- `BUY CLOSE` → light green background
- `BUY WIND_DOWN` → purple background
- `BUY EXIT` → red background
- `RECYCLE_BUY/SELL` → teal background
- `PERP_HEDGE` → gray background
- `is_partial_fill = 1` → orange dashed border

**Summary bar (bottom):**
- Total premium collected (SELL rows)
- Total premium paid (BUY rows)
- Total realized P&L
- Open positions count

**Export CSV** → download all rows for session as CSV with all columns.

---

### 8.3 `MMMStrikeSummary.js`

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Strike Summary                                   [Refresh] [Show Unrealized P&L] │
├────────┬──────┬──────────┬─────────┬──────────┬─────────┬──────────────┬────────┤
│ Strike │ Type │ Sell Qty │ Buy Qty │ Avg Sell │ Avg Buy │ Realized P&L │ Status │
├────────┼──────┼──────────┼─────────┼──────────┼─────────┼──────────────┼────────┤
│  85000 │  CE  │       10 │      10 │   142.50 │    4.80 │    +$1.377   │ CLOSED │ ← gray
│  74000 │  PE  │        5 │       0 │   201.80 │      —  │      —       │ ACTIVE │ ← amber highlight
│  75000 │  PE  │       10 │      10 │   138.20 │    4.20 │    +$1.340   │ CLOSED │ ← gray
├────────┴──────┴──────────┴─────────┴──────────┴─────────┼──────────────┤        │
│                                            TOTAL         │    +$2.717   │        │
└──────────────────────────────────────────────────────────┴──────────────┴────────┘
```

**Conditional columns:**
- `Unrealized P&L` — only shown when user enables, fetched on-demand, shown for ACTIVE rows only
- `Trades` — count of individual fills at this strike (click to filter Trade Audit table)

---

### 8.4 `MMMPnLAttribution.js`

Small breakdown panel:

```
P&L Attribution
──────────────────────────────────────
ENTRY     → collected $2.845 (18 lots)
ADJUSTMENT → collected $1.240 (8 lots)
CLOSE      → returned  $0.145 (18 lots)
WIND_DOWN  → returned  $0.087 (5 lots)
──────────────────────────────────────
Net Realized P&L: $3.853
(Premium collected - Premium paid)
```

---

### 8.5 Adding tabs to `MMMDashboard.js`

Add a new "Audit" section (not replacing existing tabs, adding):

```jsx
// New tab in dashboard tab bar
<Tab value="audit_trades">Trade Log</Tab>
<Tab value="audit_strikes">Strike Summary</Tab>

// Tab content
{activeTab === 'audit_trades' && (
  <MMMTradeAuditTable sessionId={session.session_id} />
)}
{activeTab === 'audit_strikes' && (
  <MMMStrikeSummary sessionId={session.session_id} />
)}
```

---

## 9. Implementation Phases

Complete in this order. Each phase is independently deployable.

### Phase 1: Backend Core ✅ COMPLETE

| Step | File | Action | Status |
|---|---|---|---|
| 1 | `mmm_audit_remark.py` | Create — pure string building, no deps | ✅ Done |
| 2 | `mmm_audit_log.py` | Create — both classes, singletons | ✅ Done |
| 3 | `mmm_audit_reconciler.py` | Create — reconcile_session() | ✅ Done |
| 4 | `mmm_close_at_5.py` | Instrument §5.4 — all buybacks | ✅ Done |
| 5 | `mmm_engine.py` | Instrument §5.3 — adjustment sells | ✅ Done |
| 6 | `mmm_api.py` | Instrument §5.1 — Mode A entry | ✅ Done |
| 7 | `mmm_api.py` | Instrument §5.6 — operator inject | ✅ Done |
| 8 | `mmm_api.py` | Instrument §5.7 — operator close-strike | ✅ Done |
| 9 | `mmm_monitor.py` | Instrument §5.5 — wind-down LIFO path | ✅ Done |
| 10 | `mmm_api.py` | Add 5 new REST endpoints | ✅ Done |
| 11 | Backend health check | Verify DB tables created on startup | ⬜ Verify on next restart |

### Phase 2: Session Event Log ✅ COMPLETE

| Step | File | Action | Status |
|---|---|---|---|
| 12 | `mmm_api.py` | SESSION_LIFECYCLE hooks (started/stopped/complete) | ✅ Done |
| 13 | `mmm_monitor.py` | SAFETY hooks (critical events → event_log) | ✅ Done |
| 14 | `mmm_monitor.py` | REGIME transition hooks (transition-only, sentinel) | ✅ Done |
| 15 | `mmm_margin_guardian.py` | MARGIN tier change hooks | ✅ Done |
| 16 | `mmm_strike_shift.py` | STRIKE_SHIFT hook | ✅ Done |
| 17 | `mmm_api.py` | PARAM_CHANGE hook (one event per changed param) | ✅ Done |

### Phase 3: Frontend (do third)

| Step | File | Action |
|---|---|---|
| 18 | `mmmService.js` | Add 5 API calls |
| 19 | `MMMTradeAuditTable.js` | Create component |
| 20 | `MMMStrikeSummary.js` | Create component |
| 21 | `MMMPnLAttribution.js` | Create component |
| 22 | `MMMDashboard.js` | Add Audit tabs |

### Phase 4: Perp Hedge + Reconciliation UI (do last)

| Step | File | Action |
|---|---|---|
| 23 | `mmm_perp_hedge.py` | Instrument §5.8 |
| 24 | `mmm_api.py` | Mode B import audit §5.2 |
| 25 | Frontend | Add reconcile button + mismatch alert |

---

## 10. Critical Implementation Guards

Every instrumentation point must follow these rules exactly:

### G1 — Never abort trading logic
Every audit call must be wrapped in `try/except: pass`. An audit write failure must NEVER propagate up and interrupt order execution.

### G2 — Use `quantity_filled`, not `quantity_requested`
For every order, use the actual exchange-confirmed fill size:
- `close_position()` → use `actual_lots` (already computed, line ~451)
- `execute_adjustment()` → use `filled_lots` (already computed, line ~723)
- Wind-down → use `actual_filled` (already computed, line ~2796)
- Entry → use `ce_res.get('filled_size', lots)` and `pe_res.get('filled_size', lots)`
- Inject/close-strike → use `total_lots` (these don't report partial fills currently)

### G3 — INSERT OR IGNORE, never UPDATE
The `idempotency_key` constraint handles this. The writer always uses `INSERT OR IGNORE`. If a fill event fires twice (WS + REST race, or crash replay), only the first row is inserted.

### G4 — P&L in USD only
Delta Exchange premiums are USD. Store raw USD in `premium`, `gross_premium_usd`, `realized_pnl_usd`. Frontend multiplies by exchange rate for INR display. Never do USD→INR conversion in the audit system.

### G5 — No enqueue before fill is confirmed
Only call `enqueue_trade()` after `result.get('success') == True`. Never in the `if not result.get('success'):` branch. Failed orders go to `session_event_log` as `ORDER_FAILURE`.

### G6 — Session event log: state transitions only
For `REGIME`, `MARGIN`, and `WHIPSAW`: only log when the state **changes**. Use a `_last_regime_action`, `_last_margin_tier` sentinel on the monitor to avoid emitting a row every heartbeat.

### G7 — Wind-down path vs close_position path
There are TWO paths for buybacks:
1. `close_position()` in `mmm_close_at_5.py` — handles: close_at_5, harvest, recycler, atm_shield, both_sides_close, emergency, operator
2. `_process_wind_down_buyback()` in `mmm_monitor.py` — handles: wind-down LIFO only

The wind-down path does NOT call `close_position()`. It calls `smart_execute()` directly. Both paths need independent instrumentation (§5.4 and §5.5).

---

## 11. Self-Reconciliation Protocol

Run manually after any of these events:
1. Backend crash + restart
2. Session restore from DB
3. After any manual operator intervention (inject/close-strike)
4. Daily at session wind-down

```bash
# Via curl:
curl http://localhost:5555/api/mmm/session/<SESSION_ID>/audit/reconcile | python3 -m json.tool

# Clean output:
# { "is_clean": true, "pnl_ok": true, "pnl_delta": 0.000001, "position_discrepancies": [] }

# Dirty output (discrepancy):
# { "is_clean": false, "pnl_delta": 0.147, "position_discrepancies": [
#     { "side": "CE", "strike": 85000, "audit_open_qty": 10, "session_lots": 8, "delta": 2 }
# ] }
```

If `is_clean: false`:
- `pnl_delta > 0.01` → audit P&L and session P&L have diverged. Do not trust P&L numbers until root-caused.
- `position_discrepancies` not empty → the audit log shows different open quantity than live session state. Either a trade was not recorded (missing instrumentation point) or a state mutation happened without a corresponding audit entry.

---

## 12. Testing Checklist

Before marking any phase complete:

**Phase 1:**
- [ ] `mmm_sessions.db` has `position_audit_log` and `session_event_log` tables after backend startup
- [ ] After a test session entry, exactly 2 rows appear in `position_audit_log` (CE + PE)
- [ ] After an adjustment, 1 SELL row appears with correct adj_type and aggressor_side
- [ ] After a close-at-5, 1 BUY row appears with correct realized_pnl_usd
- [ ] No row is duplicated when backend restarts mid-session (idempotency_key works)
- [ ] `curl .../audit/reconcile` returns `is_clean: true` on a clean session
- [ ] Performance: 100 consecutive heartbeats with no measurable slowdown

**Phase 2:**
- [ ] Session start creates a SESSION_LIFECYCLE row
- [ ] A hot-reload parameter change creates a PARAM_CHANGE row
- [ ] A regime change (force via test) creates a REGIME row

**Phase 3:**
- [ ] Trade Audit table shows all fills in time order
- [ ] CE/PE filter works
- [ ] Strike Summary shows correct ACTIVE/CLOSED status
- [ ] Export CSV has all columns

**Sealed test targets (add after implementation):**
- `build_trade_remark()` — test all (action, event_type) combinations return non-empty strings
- `reconcile_session()` — test with known audit rows vs known session state, clean and dirty cases
- `get_strike_summary()` — test SQL aggregation with known data (known sell qty, buy qty, P&L)

---

## 13. File Creation Checklist

New files to create:

```
webui/backend/routes/mmm/
├── mmm_audit_log.py          ← §4.2 — writer + reader singleton
├── mmm_audit_remark.py       ← §4.1 — remark templates
└── mmm_audit_reconciler.py   ← §6 — self-reconciliation

webui/frontend/src/components/mmm/
├── MMMTradeAuditTable.js     ← §8.2 — paginated trade table
├── MMMStrikeSummary.js       ← §8.3 — strike-level aggregation
└── MMMPnLAttribution.js      ← §8.4 — P&L by event type
```

Modified files:

```
webui/backend/routes/mmm/
├── mmm_close_at_5.py         ← §5.4 — instrument close_position()
├── mmm_engine.py             ← §5.3 — instrument execute_adjustment()
├── mmm_monitor.py            ← §5.5 — instrument _process_wind_down_buyback()
├── mmm_api.py                ← §5.1 §5.2 §5.6 §5.7 + 5 new endpoints
└── mmm_perp_hedge.py         ← §5.8 — instrument perp fills

webui/frontend/src/components/mmm/
├── MMMDashboard.js           ← §8.5 — add Audit tabs
└── mmmService.js             ← §8.1 — add 5 API calls
```

---

*End of implementation guide. All code in this document is specification-quality pseudocode — implementations must handle imports, edge cases, and integration with existing error handling as described in the guards above.*
