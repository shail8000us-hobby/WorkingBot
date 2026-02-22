# MMM Robust v2 — Comprehensive Audit & Improvement Plan

> **Purpose:** Complete audit of all calculation flaws, edge cases, race conditions, and architectural weaknesses in the MMM algorithm. Each issue includes root cause, production impact, and recommended fix.
>
> **Date:** February 22, 2026
> **Scope:** All 15 backend modules in `webui/backend/routes/mmm/`

---

## Table of Contents

1. [CRITICAL: Heartbeat Ordering & P&L Timing](#1-critical-heartbeat-ordering--pnl-timing)
2. [CRITICAL: Silent Error Swallowing in Calculations](#2-critical-silent-error-swallowing-in-calculations)
3. [CRITICAL: Partial Fill Assumed Full](#3-critical-partial-fill-assumed-full)
4. [CRITICAL: Cross-Session Position Adoption (FIXED)](#4-critical-cross-session-position-adoption-fixed)
5. [HIGH: Position Cap is Advisory, Not Enforced](#5-high-position-cap-is-advisory-not-enforced)
6. [HIGH: Trigger Snapshot Uninitialized on First Heartbeat](#6-high-trigger-snapshot-uninitialized-on-first-heartbeat)
7. [HIGH: Peak P&L Never Resets](#7-high-peak-pnl-never-resets)
8. [HIGH: Close-at-5 Index Safety After Multiple Closes](#8-high-close-at-5-index-safety-after-multiple-closes)
9. [HIGH: Close-at-5 Checks Original at active_strike, Not original_strike](#9-high-close-at-5-checks-original-at-active_strike-not-original_strike)
10. [HIGH: Reversal Detection Case Sensitivity](#10-high-reversal-detection-case-sensitivity)
11. [HIGH: Concurrent Close-at-5 and Adjustment in Same Heartbeat](#11-high-concurrent-close-at-5-and-adjustment-in-same-heartbeat)
12. [MEDIUM: Premium Fetch Per-Side Fallback Missing](#12-medium-premium-fetch-per-side-fallback-missing)
13. [MEDIUM: Strike Key Hashing Inconsistency](#13-medium-strike-key-hashing-inconsistency)
14. [MEDIUM: Timezone Handling Inconsistencies](#14-medium-timezone-handling-inconsistencies)
15. [MEDIUM: Hot-Reload Parameter Interdependency Not Validated](#15-medium-hot-reload-parameter-interdependency-not-validated)
16. [MEDIUM: Activity Log Non-Atomic Writes](#16-medium-activity-log-non-atomic-writes)
17. [MEDIUM: WebSocket Emission Failures Silent](#17-medium-websocket-emission-failures-silent)
18. [MEDIUM: Both-Sides-Up Auto-Decision Stale Premium](#18-medium-both-sides-up-auto-decision-stale-premium)
19. [LOW: Float Precision in Financial Calculations](#19-low-float-precision-in-financial-calculations)
20. [LOW: Session ID Collision on Weak Fallback](#20-low-session-id-collision-on-weak-fallback)
21. [LOW: Theta Acceleration Missing Cap](#21-low-theta-acceleration-missing-cap)
22. [LOW: Executor fill_price Parse Without Guard](#22-low-executor-fill_price-parse-without-guard)
23. [ARCHITECTURAL: Frozen Positions Data Model Fragility](#23-architectural-frozen-positions-data-model-fragility)
24. [ARCHITECTURAL: Derived State Consistency (recompute_side_lots footgun)](#24-architectural-derived-state-consistency)
25. [Future Improvements Summary](#25-future-improvements-summary)

---

## 1. CRITICAL: Heartbeat Ordering & P&L Timing

**Files:** `mmm_monitor.py` lines 809–834, `mmm_engine.py`

**Problem:**
The heartbeat executes in this order:
```
Step 1: Close-at-5 scan + close positions    (line 810)
Step 2: Compute fresh unrealized P&L         (line 825)
Step 3: Safety checks (max_loss, trailing)   (line 832)
Step 4: Trigger evaluation                   (line ~1087)
Step 5: Execute adjustment                   (line ~1214)
Step 6: Recompute P&L after adjustment       (line ~1220)
```

**The flaw:** Close-at-5 (Step 1) removes positions and updates `realized_pnl`. Then Step 2 computes `unrealized_pnl` — but this unrealized value is stale because it was computed AFTER positions changed. The safety checks in Step 3 use `realized_pnl + unrealized_pnl`, but the two values are from different "snapshots" of the position state.

Additionally, after adjustment (Step 5), the P&L recompute (Step 6) should force a fresh `compute_unrealized_pnl()` from the new position state, but it may be using cached premium data from Step 2.

**Production Impact:**
- Max-loss safety check uses stale combined P&L — may not trigger when it should
- Trailing stop uses stale peak comparison
- Session continues trading when it should have hard-stopped

**Fix:**
Recompute unrealized P&L TWICE: once after close-at-5 (for accurate safety checks), and once after adjustment (for accurate state). Or restructure the heartbeat to: fetch premiums → safety checks → close-at-5 → trigger → adjust → final P&L update.

---

## 2. CRITICAL: Silent Error Swallowing in Calculations

**Files:** `mmm_engine.py` lines 118–124, 192–203, 547–572; `mmm_trigger.py` lines 195–198

**Problem:**
Throughout the engine, when `fetch_premium_fn(strike, option_type)` fails for a specific strike, the code logs a warning and **silently skips that position**:

```python
# mmm_engine.py calculate_standard_loss()
for pos in side_state.get('frozen_positions', []):
    try:
        p_current = fetch_premium_fn(p_strike, option_type)
        pos_loss = (p_current - p_baseline) * p_lots * LOT_SIZE_BTC
        shifted_loss += pos_loss
    except Exception as e:
        log.warning(f"Failed to fetch premium for frozen @ {p_strike}: {e}")
        # ← Position silently excluded from loss calculation!
```

This pattern repeats in:
- `calculate_standard_loss()` — frozen position loss silently excluded
- `calculate_reversal_loss()` — adjustment P&L silently incomplete
- `compute_unrealized_pnl()` — three separate try/except blocks skip failed fetches
- `update_trigger_snapshots()` — frozen trigger baseline not updated

**Production Impact:**
- Loss calculation is incomplete → algo sells FEWER hedge lots than needed → under-hedged
- Unrealized P&L reported to user is incorrect (missing positions)
- Trigger snapshots go stale → next trigger fires incorrectly
- User has no indication that calculations are incomplete

**Fix:**
1. Add a `calculation_incomplete` flag to the return value when any fetch fails
2. Track `_fetch_error_count` in session state
3. If >50% of positions fail to fetch, PAUSE the session instead of proceeding with partial data
4. Emit a `mmm_safety` event with type `calculation_incomplete` so the UI warns the user

---

## 3. CRITICAL: Partial Fill Assumed Full

**File:** `mmm_executor.py` lines 295–299

**Problem:**
```python
raw_unfilled = final_order_data.get('unfilled_size')
if raw_unfilled is not None:
    filled_size = size - int(raw_unfilled)
else:
    filled_size = size  # ← Assumes FULL fill if field is missing!
```

If the exchange API omits the `unfilled_size` field (network issue, API version change, or response parsing error), the code assumes the entire order filled. This inflates position sizes and corrupts all downstream P&L calculations.

**Production Impact:**
- Session thinks it sold 20 lots but only 12 actually filled
- Loss calculations based on 20 lots instead of 12
- Position cap reached prematurely (phantom lots)
- Close-at-5 tries to buy back 20 lots but exchange only has 12 → order rejected

**Fix:**
Require `unfilled_size` in response. If missing, treat as execution failure and return error, not assume full fill. Add a post-fill position size verification via the exchange positions API.

---

## 4. CRITICAL: Cross-Session Position Adoption (FIXED)

**File:** `mmm_monitor.py` `_reconcile_exchange_positions()`

**Problem (now fixed):**
The exchange reconciliation auto-synced "extra" exchange positions into individual sessions as frozen positions. When multiple sessions traded the same expiry, each session imported the other's positions, inflating `total_lots` and corrupting all calculations.

**Fix Applied (Feb 22, 2026):**
- Auto-sync disabled entirely — reconciliation is now log-only
- One-time cleanup removes all `exchange_sync` frozen position artifacts
- Added `_get_other_sessions_lots_at_symbol()` for accurate comparison logging

**Status:** FIXED. No further action needed.

---

## 5. HIGH: Position Cap is Advisory, Not Enforced

**File:** `mmm_safety.py` lines 80–122, `mmm_engine.py` lines 278–295

**Problem:**
The safety check `check_position_cap()` fires a warning event with `action: 'warn'` when positions reach 80% or 100% of `max_lots_per_side`. But `should_block_adjustment()` only blocks on actions `'stop'`, `'auto_close'`, or `'stop_adjustments'` — the `'warn'` action does NOT block.

The position cap IS enforced in `calculate_lots_to_sell()` (engine line 283–289), which caps the sell quantity. So the ENGINE prevents over-selling, but the SAFETY CHECK doesn't actually stop the heartbeat from attempting the adjustment.

**The gap:** If `calculate_lots_to_sell()` returns 0 due to cap, the adjustment is skipped silently. But the safety warning was already emitted with `action: 'warn'`, which the user sees as a "soft" warning, not a hard stop. There's no explicit "POSITION CAP HIT — ADJUSTMENT BLOCKED" safety event.

**Production Impact:**
- User sees position cap warning but doesn't realize adjustments are actually blocked
- No clear "adjustments stopped due to cap" message
- If engine cap logic has a bug, safety provides no backstop

**Fix:**
Change `check_position_cap()` to return `action: 'stop_adjustments'` when `total >= max_lots`, not `action: 'warn'`. This makes the safety check a hard block, providing defense-in-depth with the engine cap.

---

## 6. HIGH: Trigger Snapshot Uninitialized on First Heartbeat

**File:** `mmm_trigger.py` lines 83–95

**Problem:**
```python
ce_trigger = ce_side.get('trigger_snapshot', {}).get(str(int(active_ce_strike)), 0)
# If trigger_snapshot doesn't have the key → returns 0
ce_excess = ce_now - ce_trigger  # = ce_now - 0 = ce_now (always large!)

ce_base = max(ce_trigger, TRIGGER_PCT_FLOOR)  # = max(0, 1.0) = 1.0
ce_excess_pct = (ce_excess / ce_base) * 100    # = (ce_now / 1.0) * 100 = huge%
```

If `trigger_snapshot` was never properly initialized (or the key is missing due to strike key hashing mismatch), the trigger baseline is 0. This makes `ce_excess` equal to the full premium (e.g., 95.0), and `ce_excess_pct` = 9500%. The trigger ALWAYS fires.

**When this happens:**
- After session restart where trigger_snapshot isn't persisted correctly
- After strike shift where the new strike key uses different formatting
- On adopted sessions where trigger_snapshot is set to entry prices incorrectly

**Production Impact:**
- Spurious adjustment on first heartbeat after restart
- Unnecessary hedge lots sold based on phantom trigger breach
- P&L distorted by unnecessary position

**Fix:**
1. Validate trigger_snapshot has the active_strike key at session start
2. If missing, initialize it with the current premium (not 0)
3. Add a `_first_heartbeat_after_restart` flag that skips trigger evaluation once (allows snapshot to populate)

---

## 7. HIGH: Peak P&L Never Resets

**File:** `mmm_safety.py` lines 536–570, `mmm_monitor.py` line ~1224

**Problem:**
`peak_pnl` is a high-water mark used for trailing stop protection. It's updated via `update_peak_pnl(session, total_pnl)` after every heartbeat but is NEVER reset.

Scenarios where this breaks:
1. Session reaches +$1000 peak with 100 lots. Close-at-5 closes 80 lots with realized profit. Now only 20 lots remain, and peak is still $1000. The trailing stop floor is $500 (50%), but with only 20 lots, the P&L might be +$200. Alert fires constantly even though the profit was already realized.
2. After a reversal, the profit baseline changes dramatically but peak stays at the old level.

**Production Impact:**
- Trailing stop fires false alerts based on stale peak
- User gets constant "trailing stop" warnings that are no longer meaningful
- May cause unnecessary session pauses

**Fix:**
Reset `peak_pnl` when:
- A reversal is detected (new profit phase begins)
- Close-at-5 closes >50% of lots on a side (position profile changed)
- Or implement a "rolling peak" that decays over time (e.g., 80% of peak + 20% of current)

---

## 8. HIGH: Close-at-5 Index Safety After Multiple Closes

**File:** `mmm_close_at_5.py` lines 137–148, 259–297

**Problem:**
The scan returns multiple closeable positions with `fill_index` or `frozen_index` values captured at scan time. The sort (line 141) orders them descending by index within the same type and side — so higher indices are popped first, which SHOULD preserve lower indices.

**However**, there's a cross-type ordering issue: if both an `adjustment` fill (index 2) and a `frozen` position (index 1) on the same side are closeable, they're processed in type-descending order (frozen first, then adjustment). The frozen pop doesn't affect the adjustment_fills array, so the adjustment index remains valid. This IS safe.

**BUT** there's a subtle edge case: if TWO adjustment fills on the same side at DIFFERENT strikes are closeable, and both have different current indices because a previous heartbeat already closed some fills, the indices in `closeable` are stale from scan time. The content-match fallback (line 269–276) handles this, but it's a linear scan of the entire fills array on each mismatch — O(n) per close × m closes = O(n×m).

**Production Impact:**
- Correctness is maintained via content-match fallback (no wrong position closed)
- Performance degrades with many positions (100+ fills × multiple closes per heartbeat)
- Log noise from "mismatch, searching by content" warnings

**Fix:**
Instead of index-based removal, use a content-match-first approach: always find by content (strike, lots, premium), never rely on indices. Or assign unique IDs to each fill/frozen position and remove by ID.

---

## 9. HIGH: Close-at-5 Checks Original at active_strike, Not original_strike

**File:** `mmm_close_at_5.py` lines 51–69

**Problem:**
```python
orig_lots = side_state.get('original_lots', 0)
if orig_lots > 0 and active_strike > 0:
    current = fetch_premium_fn(active_strike, option_type)
    if current <= threshold:
        closeable.append(...)
```

After a strike shift, `original_lots` is reset to 0 (they move to frozen). So this check only applies before any shift. However, the check uses `active_strike` to fetch premium — if somehow `original_lots > 0` but the position was actually sold at `original_strike` (which may differ from `active_strike` after initialization), the wrong premium is used.

In the current flow, `original_lots` at the active strike is always correct because `original_strike == active_strike` until a shift (at which point `original_lots` becomes 0). **This is safe in the current code** but fragile — any future change that decouples `original_strike` from `active_strike` would break this.

**Production Impact:** Currently safe but fragile against future changes.

**Fix:**
Use `side_state.get('original_strike', active_strike)` instead of `active_strike` for the original lots premium fetch. This is defensive coding.

---

## 10. HIGH: Reversal Detection Case Sensitivity

**File:** `mmm_reversal.py` lines 42–46

**Problem:**
```python
def detect_reversal(session, current_aggressor):
    last = session.get('last_aggressor')
    if last is None or last == 'NONE':    # ← Only checks uppercase 'NONE'
        return False
    if last.lower() == current_aggressor.lower():  # ← Continuation
        return False
    return True   # ← Reversal detected
```

If `last_aggressor` is stored as lowercase `'none'` (e.g., from a serialization round-trip or API input), line 42 doesn't match. The code proceeds to line 44 where `'none'.lower() != 'CE'.lower()` → returns True (false positive reversal).

**Production Impact:**
- False reversal detected on first adjustment after session restore
- Cooldown activated unnecessarily
- Adjustment skipped when it shouldn't be

**Fix:**
```python
if last is None or last.upper() == 'NONE':
    return False
```

---

## 11. HIGH: Concurrent Close-at-5 and Adjustment in Same Heartbeat

**File:** `mmm_monitor.py` lines 810, ~1214

**Problem:**
In a single heartbeat:
1. Close-at-5 closes some positions on the AGGRESSOR side (reduces lots, records realized P&L)
2. Trigger evaluation finds the aggressor side triggered
3. Loss calculation runs on the aggressor side — but position state changed in step 1

The loss calculation uses current positions (post-close-at-5), which is actually correct for computing how much CURRENT loss there is. But the trigger comparison uses `trigger_snapshot` that was set before close-at-5. If close-at-5 closed a high-premium position, the loss should be lower, but the trigger may still show "triggered" based on stale premium comparison.

**Production Impact:**
- Adjustment sells more hedge lots than needed (over-hedging)
- Premium used in loss calculation is post-close, but trigger evaluation was pre-close
- Minor P&L drag from over-hedging

**Fix:**
Re-evaluate triggers AFTER close-at-5 completes, using the updated position state. If close-at-5 closed positions on the aggressor side, the trigger may no longer be breached.

---

## 12. MEDIUM: Premium Fetch Per-Side Fallback Missing

**File:** `mmm_monitor.py` lines 587–641

**Problem:**
Premium fetch treats CE and PE as an atomic pair. If CE fetches successfully but PE fails (network error on that specific option), the entire heartbeat falls back to cached prices for BOTH sides or skips entirely.

**Production Impact:**
- One side's cache miss blocks heartbeat processing for the other healthy side
- Close-at-5 opportunities missed for the healthy side
- Safety checks don't run

**Fix:**
Implement per-side circuit breaker. If CE fetches OK but PE fails, run heartbeat with fresh CE premium and cached PE premium. Flag the PE side as `_premium_stale` so downstream code can account for it.

---

## 13. MEDIUM: Strike Key Hashing Inconsistency

**Files:** `mmm_trigger.py` lines 83, 185; `mmm_strike_shift.py` line 328; `mmm_engine.py`

**Problem:**
Strike keys in `trigger_snapshot` are created via `str(int(strike))` in multiple places. If a strike has a decimal (e.g., 23100.5), `int(23100.5) = 23100`, and the key becomes `"23100"`. But another code path might use `str(23100.5)` = `"23100.5"`, causing key mismatches.

BTC options strikes are typically integers, so this rarely triggers. But it's a latent bug.

**Production Impact:**
- Trigger snapshot lookup returns 0 (uninitialized) → spurious trigger fire
- Close-at-5 might not find the correct premium for a position

**Fix:**
Create a canonical `strike_key(strike)` utility:
```python
def strike_key(strike: float) -> str:
    return str(int(round(strike)))
```
Use it everywhere instead of inline `str(int(...))`.

---

## 14. MEDIUM: Timezone Handling Inconsistencies

**File:** `mmm_initializer.py` lines 42–64, `mmm_state.py`

**Problem:**
- `expiry_to_utc_datetime()` converts IST 17:30 → UTC 12:00 but strips timezone info from the return value
- `mmm_state.py` uses `datetime.utcnow().isoformat()` (naive UTC)
- Minutes-to-expiry calculation compares naive UTC timestamps

If any code path accidentally uses `datetime.now()` (local time) instead of `datetime.utcnow()`, the time-to-expiry will be off by the local timezone offset (5.5 hours for IST).

**Production Impact:**
- Wind-down mode activates 5.5 hours early or late
- Near-expiry safety checks (stop adjustments, auto-close) fire at wrong time
- Theta acceleration applied at wrong expiry proximity

**Fix:**
Standardize on timezone-aware UTC everywhere:
```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc)  # Always timezone-aware
```
Store and compare only timezone-aware datetimes.

---

## 15. MEDIUM: Hot-Reload Parameter Interdependency Not Validated

**File:** `mmm_config.py` lines 84–137

**Problem:**
`validate_params()` checks individual parameter ranges but not relationships. Invalid combinations that pass validation:
- `shift_threshold` > `desired_pe_premium` → shift always triggers, infinite loop
- `margin_yellow_pct` > `margin_orange_pct` → tier ordering violated
- `close_at_threshold` > `shift_threshold` → close-at-5 fires before shift can happen
- `max_adjustments = 1` + `whipsaw_limit = 3` → max_adj reached before whipsaw can detect
- `wind_down_close_threshold` < `close_at_threshold` → wind-down less aggressive than normal

**Production Impact:**
- User hot-reloads a bad combination mid-session
- Algo enters degenerate behavior (infinite shifting, never adjusting, etc.)
- No warning that the config is invalid

**Fix:**
Add interdependency rules to `validate_params()`:
```python
if validated.get('wind_down_close_threshold', 20) < validated.get('close_at_threshold', 5):
    errors.append("wind_down_close_threshold must be >= close_at_threshold")
```

---

## 16. MEDIUM: Activity Log Non-Atomic Writes

**File:** `mmm_activity.py` lines 114–131

**Problem:**
1. Only 1 in 5 writes persists to disk (80% throttling). Up to 4 heartbeats of activity lost on crash.
2. File is opened with `'w'` (truncate + write), not atomic. Crash mid-write = corrupted file.
3. Ring buffer maxlen=200, but with throttling, effective persistence is ~40 entries.

**Production Impact:**
- Post-crash debugging impossible — activity log is incomplete or corrupted
- No record of what the algo was doing before failure

**Fix:**
1. Use atomic write: write to `.tmp`, then `os.rename()`
2. Reduce throttling to 1-in-2 or remove it
3. Increase ring buffer to 500+

---

## 17. MEDIUM: WebSocket Emission Failures Silent

**File:** `mmm_websocket.py` lines 27–50, throughout `mmm_monitor.py`

**Problem:**
All WebSocket emissions catch exceptions and log them but don't re-raise. If `_socketio` is None or network fails, emissions silently fail. The algo continues trading but the UI is stale — user doesn't see heartbeats, safety alerts, or close-at-5 events.

**Production Impact:**
- UI out of sync with actual trading state
- Safety alerts invisible to user
- User may take wrong manual action based on stale UI

**Fix:**
Add emission failure counter. If N consecutive emissions fail, emit a `mmm_safety` event (which itself may fail, but the counter tracks this). Consider pausing the session if emissions fail for >5 minutes (user flying blind).

---

## 18. MEDIUM: Both-Sides-Up Auto-Decision Stale Premium

**File:** `mmm_monitor.py` lines 2402–2484

**Problem:**
When both triggers fire, the algo pauses for 30 seconds waiting for user decision. If no response, it auto-decides by comparing which side has more excess loss. But the premiums used in the comparison are from the scan that triggered both-sides-up (30+ seconds old). By execution time, premiums may have moved significantly.

**Production Impact:**
- Auto-decision hedges the wrong side (loser at T=0 becomes winner at T=30)
- True loser side left unhedged
- Both-sides situation worsens

**Fix:**
Re-fetch premiums just before executing the auto-decision, not at detection time.

---

## 19. LOW: Float Precision in Financial Calculations

**Files:** Multiple — `mmm_engine.py`, `mmm_executor.py`, `mmm_close_at_5.py`

**Problem:**
All P&L calculations use Python `float` (IEEE 754 double). After 100+ adjustments with premium calculations like `(95.23 - 4.87) * 17 * 0.001`, rounding errors accumulate. Estimated drift: $0.50–$1.00 over a session's lifetime.

**Production Impact:**
- P&L report slightly inaccurate
- Reconciliation with exchange P&L shows minor discrepancies
- Trailing stop threshold slightly off

**Fix:**
Use `decimal.Decimal` for all P&L accounting internally. Convert to `float` only at API/display boundaries.

---

## 20. LOW: Session ID Collision on Weak Fallback

**File:** `mmm_state.py` lines 264–291

**Problem:**
If the storage collision check fails (exception), the fallback uses only 4 hex characters: `mmm22feb26-{uuid[:4]}` → only 65,536 possible IDs. In multi-session environments, collision is possible.

**Production Impact:**
- Two sessions could share the same ID → data overwritten
- Extremely rare but catastrophic when it happens

**Fix:**
Use 8+ hex characters in fallback. Add a retry loop with exponential backoff for the collision check.

---

## 21. LOW: Theta Acceleration Missing Cap

**File:** `mmm_trigger.py` lines 211–263

**Problem:**
Near expiry, theta acceleration doubles `min_trigger_move_pct`. If the base is already 50%, the effective becomes 100% — triggers can never fire. No upper cap.

**Production Impact:**
- Very near expiry, triggers might never fire even during massive moves
- Algo becomes passive when it should be responsive

**Fix:**
Cap effective min_trigger_move to 80% or max(base * 2, 0.5 * trigger_snapshot).

---

## 22. LOW: Executor fill_price Parse Without Guard

**File:** `mmm_executor.py` lines 374–376

**Problem:**
```python
fill_price = float(raw_fill)  # No try/except for ValueError
```
If API returns `"NaN"`, `"Inf"`, or `"null"` string, this crashes.

**Production Impact:**
- Executor crash on malformed API response
- Adjustment half-executed (order placed but state not updated)
- Orphaned exchange position not tracked

**Fix:**
```python
try:
    fill_price = float(raw_fill)
    if math.isnan(fill_price) or math.isinf(fill_price):
        raise ValueError(f"Invalid fill_price: {raw_fill}")
except (ValueError, TypeError):
    return self._failure(f"Cannot parse fill_price: {raw_fill}", ...)
```

---

## 23. ARCHITECTURAL: Frozen Positions Data Model Fragility

**Current Model:**
Positions live in 3 separate arrays per side:
- `original_lots` (scalar) + `original_premium` (scalar)
- `adjustment_fills[]` (array of fill dicts at active strike)
- `frozen_positions[]` (array of position dicts at old strikes)

Plus 5 derived scalars: `adjustment_total_lots`, `adjustment_avg`, `frozen_total_lots`, `active_lots`, `total_lots`

**Problems:**
1. Every mutation must call `recompute_side_lots()` — if forgotten, derived values go stale
2. The name "frozen" is misleading — these are fully live, priced, and included in all calculations
3. Three separate loops needed for every calculation (original, adjustment, frozen)
4. Index-based removal from arrays is fragile (addressed by content-match fallback but noisy)
5. No unique identifier per position — positions matched by content (lots + premium)

**Recommended v2 Architecture: Unified Position Ledger**

```python
# Each position has a unique ID and lifecycle status
{
    'active_strike': 68000,
    'positions': [
        {
            'id': 'pos_001',
            'strike': 68000,
            'lots': 10,
            'entry_premium': 95.0,
            'type': 'original',          # original | adjustment | shift_entry
            'status': 'active',          # active | shifted | closed
            'created_at': '2026-02-22T08:00:00',
            'shifted_at': None,
            'closed_at': None,
            'realized_pnl': None,
        },
        # ... more positions
    ],
}

# Derived values computed on-the-fly via properties:
#   total_lots = sum(p['lots'] for p in positions if p['status'] != 'closed')
#   active_lots = sum(p['lots'] for p in positions if p['status'] == 'active')
#   shifted_lots = sum(p['lots'] for p in positions if p['status'] == 'shifted')
```

**Benefits:**
- No `recompute_side_lots()` needed — values are always computed from source
- Single loop for all calculations
- Unique ID per position — safe removal, no index issues
- Strike shift = status change, not array-to-array move
- Full audit trail (created_at, shifted_at, closed_at)
- Position lifecycle is explicit and verifiable

**Migration:** This is a significant refactor touching engine, close-at-5, monitor, API, state, strike_shift, wind-down. Best done when algo is NOT in active production trading.

---

## 24. ARCHITECTURAL: Derived State Consistency

**Current Problem:**
Five values (`adjustment_total_lots`, `adjustment_avg`, `frozen_total_lots`, `active_lots`, `total_lots`) are stored in session state alongside their source data. These MUST be recomputed via `recompute_side_lots()` after every mutation. The function is called in 10+ locations across 6 files.

**Where `recompute_side_lots()` is called:**
- `mmm_engine.py` line 484 (after adjustment fill)
- `mmm_close_at_5.py` line 296 (after position removal)
- `mmm_strike_shift.py` lines 146, 330 (after freeze/activate)
- `mmm_wind_down.py` line 331 (after LIFO removal)
- `mmm_monitor.py` lines 1678, 2698 (after recovery/emergency)
- `mmm_adopter.py` line 492 (after adoption)

**Risk:** If ANY new code path mutates `adjustment_fills` or `frozen_positions` without calling `recompute_side_lots()`, the derived values silently go stale. This is exactly what happened with the `exchange_sync` bug — positions were added and recomputed, but the recomputed values were wrong because the source data was wrong.

**Fix (Short-term):**
Add an assertion at the top of every heartbeat:
```python
# Verify derived values match source data
for side_key in ['ce', 'pe']:
    side = session.get(side_key, {})
    expected_total = (
        side.get('original_lots', 0) +
        sum(f.get('lots', 0) for f in side.get('adjustment_fills', [])) +
        sum(f.get('lots', 0) for f in side.get('frozen_positions', []))
    )
    if side.get('total_lots', 0) != expected_total:
        log.critical(f"CONSISTENCY CHECK FAILED: {side_key} total_lots={side.get('total_lots')} != computed={expected_total}")
        recompute_side_lots(side)
```

**Fix (Long-term):** Move to computed properties (see #23 Unified Position Ledger).

---

## 25. Future Improvements Summary

### Priority 1 — Fix Before Next Trading Session
| # | Issue | Est. Effort |
|---|-------|-------------|
| 1 | Heartbeat P&L ordering | Small — reorder 3 blocks |
| 2 | Silent error swallowing | Medium — add `calculation_incomplete` flag |
| 3 | Partial fill assumed full | Small — add validation |
| 5 | Position cap enforcement | Small — change `action: 'warn'` to `'stop_adjustments'` |
| 6 | Trigger snapshot init | Small — validate at start, skip first heartbeat |
| 10 | Reversal case sensitivity | Trivial — add `.upper()` |

### Priority 2 — Fix This Week
| # | Issue | Est. Effort |
|---|-------|-------------|
| 7 | Peak P&L reset | Small — reset on reversal |
| 8 | Close-at-5 content-match first | Medium — refactor removal logic |
| 11 | Close-at-5 + adjustment interaction | Medium — re-evaluate triggers |
| 12 | Per-side premium fallback | Medium — split circuit breaker |
| 13 | Strike key canonicalization | Small — utility function |
| 15 | Param interdependency validation | Medium — add rules |
| 24 | Derived state consistency check | Small — add assertion |

### Priority 3 — Improve Over Time
| # | Issue | Est. Effort |
|---|-------|-------------|
| 14 | Timezone standardization | Medium |
| 16 | Atomic activity log writes | Small |
| 17 | WebSocket failure detection | Medium |
| 18 | Both-sides re-fetch | Small |
| 19 | Decimal precision | Large — throughout |
| 20 | Session ID collision | Small |
| 21 | Theta acceleration cap | Trivial |
| 22 | fill_price parse guard | Trivial |

### Priority 4 — Major Refactor (Plan for v2)
| # | Issue | Est. Effort |
|---|-------|-------------|
| 23 | Unified Position Ledger | Large — full refactor |

---

*This document is the comprehensive audit of the MMM algorithm. All issues are based on line-by-line code review of the production codebase as of February 22, 2026.*
