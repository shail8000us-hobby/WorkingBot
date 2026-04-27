# PHASE 08 — Execution & API Audit
**Lead Agent:** Execution & API Agent
**Status:** COMPLETE
**Date:** 2026-04-26
**Prior Phases Read:** Phase 01–07

---

## Executive Summary

The execution layer (`mmm_executor.py`, `mmm_fill_sync.py`, `mmm_ledger.py`, `mmm_ws_executions.py`) is robustly engineered. Mid-price limit orders with 60s fill timeout, reprice loop, partial fill recovery, and duplicate `client_order_id` detection are all present. FillSync REST polling with 3-page pagination and cursor advancement forms the universal ground-truth backstop. The real-time WS executions channel supplements FillSync with immediate fill routing. The previously P1 string-match fragility for M2 recycling trigger (A6-04) is **confirmed fixed** via the `is_position_cap_hit` bool return value.

Two execution layer findings remain: `client_order_id` collision risk on same-side concurrent orders within one second, and an external-close P&L gap for options that expire without a buyback fill.

**Execution Layer Architecture Grade: A-** — solid execution pipeline; minor edge cases documented.

---

## 1. Smart Execution Engine — `mmm_executor.py`

### 1.1 Order Placement Flow

```
smart_execute(symbol, side, size, ...)
  → register_order(coid) in WS registry
  → fetch L2 orderbook
  → place limit order at mid-price (or bid for close buybacks)
  → wait FILL_TIMEOUT (60s default, DTE/gamma-scaled) polling every 3s
  → if dead order: check partial fill → continue with remaining
  → if timeout: re-fetch quotes, amend in-place (edit_order)
  → repeat up to MAX_REPRICE_ATTEMPTS (4)
  → after halfway: switch from mid to best_bid (more aggressive)
```

### 1.2 Key Design Decisions

- **In-place amendment** (edit_order) instead of cancel+replace — preserves queue priority
- **0.5s re-fetch after fill detection** — handles exchange latency in `average_fill_price` population
- **`_parse_fill_price()` helper** — deduplicates 4 prior copies of fill price validation logic; validates non-null, non-zero, finite, positive, <$1M
- **`max_buy_price` cap** — for `close_at_threshold`: aborts at initial placement if premium already above cap; during reprice loop, cancels and returns failure (never over-pays)
- **Partial fill accumulation** — `_cumulative_filled` + `_cumulative_fill_value` track weighted-average price across exchange-cancelled partial orders; prevents double-placement

### 1.3 Duplicate client_order_id Handling

On `duplicate_client_order_id` exchange error:
1. Search open orders for the coid
2. Found → resume monitoring the existing order
3. Not found → critical alert, stop retries (order may be filled or cancelled on exchange)

### 1.4 client_order_id Format

```
mmm_{sess_tag8}_{side_tag}{opt_tag}_{ts_tag8}  (max 32 chars)
```
- `sess_tag`: first 8 non-hyphen chars of session_id (after stripping 'mmm')
- `side_tag`: 'b' (buy) or 's' (sell)
- `opt_tag`: first char of symbol ('c'=CE, 'p'=PE) — added to prevent concurrent CE+PE orders at same timestamp getting identical coids
- `ts_tag`: last 8 digits of `int(time.time())`

**Finding A8-01 (P2):** Two concurrent SELL orders for the SAME option side (both CE, placed within the same second) would produce `side_tag='s'`, `opt_tag='c'`, `ts_tag=same` → identical coids. This is unlikely in normal operation (adjustment only sells one side at a time) but possible if the recycler or scaler fires a CE sell while an adjustment CE sell is already in flight for the same session. The `duplicate_client_order_id` handler catches this, but if the original order already filled and left open orders, the critical alert fires and the second order is never placed — leaving the position under-hedged.

Mitigation: a monotonic counter suffix or nonce would eliminate the collision entirely.

### 1.5 Audit Log Integration

`ORDER_INTENT` is written to the audit log before fill confirmation, `ORDER_CONFIRMED` after. `ORDER_FAILED` written on all-attempts failure. Durable pre-fill intent survives backend crash — supports orphan check on EXITING restore.

---

## 2. FillSync — `mmm_fill_sync.py`

### 2.1 Architecture

- Cursor-based: `session['_fill_sync_cursor_us']` advances to `newest_fill_ts + 1` after each sync
- Paginated: up to 3 pages × 100 fills = 300 fills per sync window
- Runs every heartbeat — fills are deduped by `fill_id` (UNIQUE constraint in ledger)
- First sync: looks back to session `entry_time` (or 1 hour, whichever is recent)

### 2.2 Matching Logic

BUY fills only (shorts closed by buyback). Matching: **strict `close_order_id` only**.
- Each close path (close_at_5, wind_down, shift_recycle, manual_reduce) writes `pos['close_order_id']` when placing the buy order
- FillSync matches `fill.order_id == pos.close_order_id`
- No match → logged at DEBUG (external close, expiry) — not an error

### 2.3 Sub-fill Awareness

A single close order can produce multiple exchange fill events (same `order_id`, different `fill_id`):
- `_cumulative_lots_filled` accumulates across sub-fills
- Position only marked `closed` + `_fill_confirmed=True` when `cumulative_filled >= pos_lots`
- Intermediate sub-fills reduce `pos['lots']` and stay in the active position list

### 2.4 P&L Reconciliation

On fill match:
1. Calls `_pnl_confirm()` — corrects the existing estimate in `_fill_ledger`
2. If no estimate (no prior `record_close()` call — e.g. external fill): calls `_pnl_record()` to create a confirmed entry
3. P&L correction delta (`actual_pnl - estimated_booked`) logged at WARNING if |correction| > 0.0001

### 2.5 Ledger Record

ALL fills (both SELL opens and BUY closes) are written to `mmm_position_ledger.db` via `record_fill()`. Idempotent by `fill_id`. This is the virtual-position sub-ledger used for watchdog reconciliation.

**Finding A8-02 (P2):** Fills without a matching `close_order_id` (external closes, manual buybacks, options expiring worthless at price=0) are logged and skipped by FillSync. For an option that expires worthless:
- Exchange sends expiry fill at price=0 → rejected by `fill_price <= 0` guard
- Position remains `status=open` in `positions[]` indefinitely
- `recompute_side_lots()` continues counting it toward `total_lots`
- The bot's position count stays overstated by the expired lots until the position is manually cleaned up or the session ends

If `close_at_threshold` fires before expiry (standard flow), this path is avoided. Gap only manifests if `close_at_threshold` is disabled or fails to fire before expiry.

**Finding A8-03 (P3 — clock skew detection):** `now_us <= cursor_us` produces a warning and skips the entire sync cycle. This is correct and safe — prevents processing fills "before" the cursor — but the session's position state remains unreconciled for that heartbeat. If clock skew persists (NTP correction), multiple consecutive heartbeats could skip sync, leaving fill acknowledgments delayed.

---

## 3. Position Sub-Ledger — `mmm_ledger.py`

### 3.1 Schema

SQLite WAL-mode database (`mmm_position_ledger.db`) separate from session state:
```sql
session_fills(
    fill_id     TEXT UNIQUE,    -- Delta fill_id, idempotent key
    session_id  TEXT,           -- owner session
    symbol      TEXT,           -- option symbol
    side        TEXT,           -- 'sell' (open) / 'buy' (close)
    qty         INTEGER,        -- lots (always positive)
    price       REAL,           -- fill price in USD
    client_order_id TEXT,       -- coid for session attribution
    commission  REAL,
    option_side TEXT,           -- 'ce' / 'pe'
    strike      REAL,
    expiry      TEXT
)
```

### 3.2 Idempotency

`INSERT OR IGNORE` on `(fill_id)` UNIQUE constraint. Safe to call multiple times — fill_sync REST and WS channel can both record the same fill without double-counting.

### 3.3 Net Lots Query

`get_session_lots_by_side(session_id)` returns `{ce: N, pe: N}` — used by watchdog reconciliation. Formula: `SUM(sell_qty) - SUM(buy_qty)` per side.

---

## 4. WS Executions — `mmm_ws_executions.py`

### 4.1 Architecture

- Subprocess pattern: `_ws_executions_worker.py` holds the WS connection (isolated from eventlet monkey-patching)
- Registry: `{coid → {session_id, symbol, side, lots}}` maintained in parent process
- On fill event: registry lookup → `record_fill()` in ledger

### 4.2 Registry Lifecycle

- `register_order()` called in `smart_execute()` before placing order (before the coid reaches exchange)
- `evict_session()` called on session stop (removes all coids for that session)
- Stale eviction after 24h or when registry > 5000 entries

### 4.3 Post-Restart Gap

**Finding A8-04 (P3):** On backend restart, the WS registry is empty (in-memory). Real-time WS fill events for orders placed before the restart won't match any registry entry — logged at WARNING and routed to fill_sync REST fallback. This is by design and safe (fill_sync is the authoritative backstop). The gap is bounded to at most one `adjustment_interval` (the next heartbeat will catch the fill via REST). All fill dedup is by `fill_id` so no double-booking occurs.

---

## 5. M2 Recycling Trigger — A6-04 Resolution

**Finding A6-04 (Phase 6) status: RESOLVED.**

`calculate_lots_to_sell()` now returns a 3-tuple `(lots, constraint_msg, is_position_cap_hit)`. The flag is `True` only for the position-cap path (not total exposure ceiling, not gamma block). Sealed test contracts C4, C5, C13 in `test_sealed_calculate_lots_to_sell.py` regression-lock this behavior.

In `mmm_monitor.py:5094`, M2 recycling trigger now uses `if is_position_cap:` instead of the old string-matching. The old string-match comment is preserved as reference. This is a **P1 fix** confirmed complete.

---

## 6. Architecture Issues — Phase 8

| ID | Problem | Risk | Priority |
|---|---|---|---|
| A8-01 | Two concurrent SELL orders for the same option side within one second → identical `client_order_id`; duplicate coid handler fires, second order not placed | Hedge position under-placed on rare same-side concurrent execution | P2 |
| A8-02 | Options expiring worthless (price=0 fill) are rejected by `fill_price<=0` guard; position stays open in bot view counting toward lot limits | Overstated position count if close_at_threshold missed | P2 |
| A8-03 | Clock skew (NTP correction) skips entire FillSync cycle | Fill acknowledgments delayed up to one heartbeat interval | P3 |
| A8-04 | WS registry empty on restart; real-time WS fills for pre-restart orders fall back to REST | At most one interval delay; safe via fill_sync backstop | P3 |

---

## 7. Positive Findings

1. **A6-04 RESOLVED** — `is_position_cap_hit` bool eliminates string-match fragility in M2 recycling trigger; sealed via C4/C5/C13 contracts
2. **`_parse_fill_price()` helper** — deduplicates fill price validation (prevents divergence from future edits)
3. **Partial fill recovery** — `_cumulative_filled`/`_cumulative_fill_value` accumulate across exchange-cancelled partial orders; prevents double-placement
4. **`max_buy_price` cap** — `close_at_threshold` can never over-pay; abort at initial placement if premium already above threshold
5. **Duplicate coid handler** — network drop between placement and response is handled; order is found and monitored rather than re-placed
6. **Sub-fill awareness in FillSync** — multi-event partial fills accumulated correctly before marking position closed
7. **Fill_sync cursor advances even on no-match** — prevents endless re-fetch of fills from other sessions/algos
8. **Ledger idempotency** — `INSERT OR IGNORE` on `fill_id`; WS + REST can both record same fill safely
9. **ORDER_INTENT audit log** — pre-fill intent survives crash; supports post-mortem and EXITING orphan check
10. **WS executions subprocess isolation** — eventlet monkey-patching cannot corrupt the WS connection

---

## 8. Pass Criteria Checklist

- [x] `smart_execute()` reprice loop, partial fill recovery, coid dedup verified
- [x] `client_order_id` format and collision risk analyzed
- [x] FillSync matching logic (close_order_id strict match) verified
- [x] Sub-fill accumulation logic verified
- [x] External close / expiry gap documented (A8-02)
- [x] Ledger idempotency confirmed (`INSERT OR IGNORE`)
- [x] WS executions architecture and fallback to REST confirmed
- [x] M2 recycling trigger fix (A6-04) confirmed complete
- [x] Architecture Issue Register updated (Section 6)

**Phase 8 Status: PASSED. A6-04 P1 gap confirmed resolved. Two P2 edge cases documented.**
