# Close-at-5 — Source Document

> **Function:** Profit-taking buyback engine — closes option positions when premium ≤ threshold
> **Primary file:** `webui/backend/routes/mmm/mmm_close_at_5.py`
> **Updated:** March 15, 2026

---

## What It Does

Buys back sold options when their premium decays to ≤ `close_at_threshold` (default $5).
Locks in profit: sold at high premium, buy back at low premium.

**Example:** Sold CE @ $120 → premium decays to $4.20 → close_at_5 buys back → realized P&L ≈ ($120 - $4.20) × lots × 0.001 BTC

---

## Architecture

```
Proactive Watcher (background thread)
  → sleeps 60s when outside expiry window AND force_enabled=False
  → activates in last close_at_watch_hours_before_expiry hours (default 3h)
     → polls every close_at_watch_near_expiry_interval seconds (default 10s)
  → force-enabled: polls every close_at_watch_interval seconds (default 30s)
  → if any bid ≤ threshold → force_heartbeat()
  ↓
Heartbeat Step 2: _process_close_at_5()  [mmm_monitor.py]
  → scan_closeable_positions()           [mmm_close_at_5.py]
  → for each position: close_position()  [mmm_close_at_5.py]
      → Guardian G1+G2 gate
      → Observer gate
      → smart_execute(BUY, reduce_only=True, use_bid_entry=True)
      → _remove_closed_position() or _partial_close_position()
      → log_activity('close_at_5', ...)  ← persistent audit trail
      → emit_close_at_5() WebSocket
```

---

## Config Parameters (all hot-reloadable)

| Parameter | Default | Purpose |
|---|---|---|
| `close_at_threshold` | `5.0` | Premium at or below which position is eligible |
| `close_at_use_bid` | `True` | Use bid price (not mark) — more accurate for illiquid options |
| `close_at_max_per_beat` | `3` | Max positions to close per heartbeat (prevents stall) |
| `wind_down_close_threshold` | `20.0` | Elevated threshold when wind-down mode is active |
| **Watcher params** | | |
| `close_at_watch_hours_before_expiry` | `3.0` | Watcher auto-activates within this many hours of expiry. `0` = always on |
| `close_at_watch_near_expiry_interval` | `10` | Watcher polling interval (s) when inside expiry window — fast for 0DTE |
| `close_at_watch_interval` | `30` | Watcher polling interval (s) when force-enabled |
| `close_at_watcher_force_enabled` | `False` | UI toggle — force watcher on outside expiry window |

---

## Key Invariants (never violate)

1. `_being_closed` is set **BEFORE** the exchange call — never after
2. `_being_closed` is **always cleared** on failure (result.success=False) AND in except block
3. Only BUY orders with `reduce_only=True` — cannot open new positions
4. `use_bid_entry=True` always — start at bid price, not mid
5. `recompute_side_lots()` called after every state mutation
6. G1 bypass only on `both_sides_closing=True` — no other bypass

---

## `_being_closed` Flag — Lifecycle + TTL

**Purpose:** Prevent duplicate close orders if state-removal crashes post-fill.

**Lifecycle:**
```
scan detects eligible position
  → _check_stale_being_closed(): auto-clear if set >180s ago (March 11 fix)
  → close_position() called
    → set pos['_being_closed'] = True, pos['_being_closed_at'] = time.monotonic()
    → order placed
      → Success: flag removed by _remove_closed_position()
      → Failure: flag explicitly cleared (retry next scan)
      → Exception: flag cleared in except block + recompute forced
```

**March 11 incident:** 3 PE positions had `_being_closed=True` stuck 30+ minutes — never retried.
**Fix:** `_BEING_CLOSED_TTL = 180s` — `_check_stale_being_closed()` auto-clears on next scan.

---

## Execution Flow Detail

### scan_closeable_positions()

Scans all positions on both sides: original_lots, adjustment_fills[], frozen_positions[].
- Skips `_being_closed` positions (with TTL auto-clear)
- Uses bid price if `close_at_use_bid=True` (fallback: mark price, then 0)
- Returns sorted list: side → type (frozen>adj>orig) → profit descending
- Stamps `threshold_used` on each item (normal or wind-down elevated)

### close_position() — gates in order

1. **In-flight check**: if already `_being_closed` → return early (no exchange call)
2. **Guardian G1** (hedge integrity): would this leave one side at 0? → block. Bypassed when `both_sides_closing=True`
3. **Guardian G2** (beat velocity): lots closed this heartbeat > `max_beat_buyback_lots`? → block
4. **Observer CHECK 1** (price consistency): current premium > entry premium? → block (would realize loss)
5. **Observer CHECK 2** (ledger integrity): position still in ledger? → block if already removed
6. **smart_execute**: BUY limit at bid, reduce_only=True
7. On failure: clear `_being_closed`, check if already closed externally via REST
8. On success: `_remove_closed_position()` or `_partial_close_position()`, then:
   - `_pending_close_verification[symbol]` — 3-beat grace (suppresses reconciliation false alarm)
   - P&L recorded with Decimal arithmetic (Fix #19)
   - `session['analytics']['auto_close_events']` appended
   - `log_activity('close_at_5', ...)` — persistent audit log entry
   - `emit_close_at_5()` WebSocket
   - Observer + Guardian velocity record

### _process_close_at_5() in mmm_monitor.py

- Reads `close_at_max_per_beat` from params (default 3) — caps positions closed per heartbeat
- Detects `_both_sides_closing` (all lots on both sides eligible) → bypasses G1
- Checks `_should_stop()` + beat deadline before each close
- Returns `sides_closed: set` — used by Step 6 to skip redundant adjustment on same side

---

## State Removal

**Full fill** (`_remove_closed_position`):
- ID-based (modern): `pos['status'] = 'closed'`, `pos['closed_at'] = now`, then `recompute_side_lots()`
- Content-match fallback (pre-migration): match on lots+premium+strike, pop from adjustment_fills[] or frozen_positions[]

**Partial fill** (`_partial_close_position`):
- Reduces `positions[].lots` by `closed_lots`, clears `_being_closed`, calls `recompute_side_lots()`
- Remaining lots stay in state — picked up on next scan

---

## P&L Arithmetic

```python
realized_pnl = float((_D(entry_prem) - _D(close_price)) * _D(actual_lots) * _LOT)
# entry_prem > close_price → profit (normal case)
# entry_prem < close_price → loss (rare — bought back more expensive than sold)
```

Attribution: `pnl_initial` for original positions, `pnl_adjustment` for adj/frozen, or explicit `pnl_attribution_key`.

---

## Calling Patterns

| Caller | mechanism | hedge_guard |
|---|---|---|
| `_process_close_at_5()` | `'close_at_5'` | True (or False if both-sides) |
| `_process_harvest()` (M1) | `'harvest'` | True |
| M2 recycler | `'recycler'` | True |
| ATM Shield | `'atm_shield'` | True |
| Wind-down | `'wind_down'` | True |
| Emergency close-all | `'emergency'` | False |

---

## Fixed Bugs (do not reintroduce)

| Bug | Fix |
|---|---|
| Wide-spread guard skipped close when bid ≤ threshold but mark > threshold | Removed entirely — if bid ≤ threshold, close unconditionally |
| Orders placed at mid-price instead of bid | `use_bid_entry=True` always passed |
| Shift-before-close guard blocked closes indefinitely | Removed entirely |
| `_being_closed` stuck permanently (March 11) | TTL=180s auto-clear via `_check_stale_being_closed()` |

---

## Remaining Risks (not yet addressed)

1. **Untracked lots** (March 15): Reconciliation mismatch means exchange had 120 lots, session tracked 78. The 42 unknown lots sat at $1-3 premium — invisible to close_at_5. Fix: auto-adopt untracked positions on expiry day.
2. **Proactive watcher latency**: 30s polling → heartbeat → close = up to 60s lag near expiry. Watcher could execute directly but needs executor access + lock.
3. **Partial fill not retried immediately**: Remainder waits for next heartbeat (30-60s). Could re-insert into current closeable list.

---

## Test Coverage

```bash
python3 -m pytest webui/ bot/ -m sealed -v -k "close"
```

Sealed: `check_side_fully_closed()`, `check_both_sides_closed()`
Not sealed (require mock executor): `scan_closeable_positions()`, `close_position()`
