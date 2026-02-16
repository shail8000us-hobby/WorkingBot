# MMM Session `mmm_d8b725` — Post-Mortem Analysis

> **Date:** February 16, 2026  
> **Session:** `mmm_d8b725` (Fresh Mode)  
> **Created:** 2026-02-16T04:24:35 UTC  
> **Last Updated:** 2026-02-16T08:39:58 UTC  
> **Reference Spec:** `MONEY_POWER_CALCULATION_LOGIC.md`

---

## 1. Session Overview

### Entry Positions

| Side | Entry Strike | Entry Fill Price | Original Premium (Stored) | Original Lots | Symbol |
|------|-------------|-----------------|--------------------------|--------------|--------|
| CE   | 69600       | 92.0            | 303.5 ❌ (wrong)          | 1            | C-BTC-69600-160226 |
| PE   | 67800       | 83.0            | 83.0 ✅                   | 1            | P-BTC-67800-160226 |

### Session State at Analysis Time

| Metric | Value |
|--------|-------|
| `strategy_status` | RUNNING |
| `last_aggressor` | PE |
| `adjustment_count` | 3 |
| `reversal_count` | 26 ❌ (inflated from infinite loop) |
| `shift_count` | 1 (CE shift from 69600 → 68400) |
| `close_at_5_count` | 0 |

### CE Side State (at analysis)

```
active_strike:      68400 (shifted from 69600)
active_lots:        1 (0 original + 1 via sanitization)
frozen_positions:   3 lots at 69600 (1 original, 2 adjustments)
total_lots:         4
trigger_snapshot:   {69600: 72.85, 68400: 26.19} ← STALE at 68400
```

### PE Side State (at analysis)

```
active_strike:      67800
active_lots:        1 (1 original + 0 adjustments)
total_lots:         1
trigger_snapshot:   {67800: 83.0}
```

---

## 2. Timeline of Events

### Phase 1: Initialization (T=0)
- Entry orders placed: SELL 1 CE @ 69600, SELL 1 PE @ 67800
- CE fill: 92.0, PE fill: 83.0
- Triggers set: CE[69600]=92.0 (or 303.5 due to bug), PE[67800]=83.0

### Phase 2: CE Aggressor (T+1 to T+3)
- CE premium rises above trigger → standard adjustments on PE side
- `last_aggressor` = "CE"
- 2 PE adjustment lots sold to cover CE losses
- Triggers updated after each adjustment

### Phase 3: CE Strike Shift (T≈+2h)
- CE premium at 69600 drops below shift_threshold
- `freeze_current_positions()` moves all 69600 lots to frozen
- CE shifted to 68400, new lots sold at 68400
- CE trigger_snapshot[68400] = 26.19 (fill premium at new strike)

### Phase 4: Reversal Detected — THE LOOP BEGINS (T+2h onwards)
- PE becomes aggressor → `detect_reversal()` returns True (last was CE)
- `calculate_reversal_loss()` checks PE adjustment P&L → still profitable
- `should_skip_reversal_adjustment()` returns skip=True
- **BUG:** `last_aggressor` stays as "PE's opposite=CE", so NEXT heartbeat detects the SAME reversal
- **BUG:** Triggers NOT updated → CE[68400] stays at 26.19 forever
- **BUG:** `record_reversal()` increments `reversal_count` every heartbeat
- **BUG:** `activate_cooldown()` called every heartbeat → cooldown spam

### Phase 5: Infinite Loop (rest of session)
- Every heartbeat: CE trigger fires (premium >> 26.19) → reversal detected → skip → cooldown → repeat
- `reversal_count` inflates from 1 to 26
- Zero useful adjustments made during this entire phase

---

## 3. Bug Analysis

### BUG #1 — CRITICAL: Infinite Reversal Detection Loop

**Spec Reference:** §9 (Reversal Logic), §5.2 Case B

**Root Cause:** When a reversal is detected but skipped (`adj_pnl ≥ 0`), the code did NOT update `last_aggressor`. Per the original code comment:

```python
# Do NOT update last_aggressor when skipping — the original
# aggressor direction is still the dominant one until an
# actual adjustment is executed
```

This is **wrong** according to the spec. §9 states:

> "After the first reversal adjustment is done: triggers updated, `last_aggressor` set to new direction, all subsequent adjustments use standard formula."

When the reversal is SKIPPED (profitable), the same transition SHOULD apply because:
1. The market HAS reversed (the direction change is real)
2. The adjustment positions are profitable (no hedge needed **yet**)
3. If the premium continues to rise, subsequent triggers should use the **standard formula** (Case A: `loss = (premium_now - trigger) × active_lots`)

Without updating `last_aggressor`, the next heartbeat sees the same direction mismatch and re-detects the reversal — creating an infinite loop.

**Fix Applied (mmm_reversal.py):**
```python
def handle_reversal_skip_transition(session, aggressor, ce_now, pe_now):
    """After a reversal is skipped (profitable), transition to standard mode."""
    session['last_aggressor'] = aggressor.upper()
    update_trigger_snapshots(session, ce_now, pe_now)
```

**Called from mmm_monitor.py `_process_adjustment()` when skip=True.**

---

### BUG #2 — CRITICAL: Stale CE Trigger Snapshot

**Spec Reference:** §6.2 (Update Trigger Snapshots), §7 (Trigger System)

**Root Cause:** The CE trigger snapshot at strike 68400 was set to `26.19` when the strike shift occurred and was **never updated** because:
1. No adjustment was ever executed at that strike (all reversals skipped)
2. `update_trigger_snapshots()` is only called after successful adjustments or during initialization

This meant every heartbeat saw: `ce_excess = CE_now - 26.19 > min_trigger_move` → CE triggered → feeds into Bug #1's reversal loop.

§6.2 states:
> **CRITICAL RULE: Both sides' snapshots update, regardless of which side was the aggressor.**

**Fix Applied:** The `handle_reversal_skip_transition()` function now calls `update_trigger_snapshots()` when a reversal is skipped, setting both triggers to current premiums. This resets the trigger baseline.

---

### BUG #3 — LOW: Incorrect `original_premium`

**Spec Reference:** §2 (State), §3 (Initialization)

**Observed:** `ce.original_premium = 303.5` but `ce.entry_fill_price = 92.0`.

**Root Cause:** Timeline:
1. Session created → `initialize_side_from_entry()` called with `premium=303.5` (mark price from chain scan)
2. Entry orders executed → actual fill at 92.0
3. `_execute_entry_background()` sets `session['ce']['original_premium'] = ce_fill` (92.0)
4. But the session data still shows 303.5 — likely saved before the fill update was persisted, or a race condition in the save/reload cycle.

The code at line 509 of `mmm_api.py` IS correct: `session['ce']['original_premium'] = ce_fill`. This was a timing bug in this specific session.

**Fix Applied (mmm_monitor.py `sanitize_session_state()`):**
- Added Fix 2: checks if `original_premium != entry_fill_price` and corrects it
- Runs once per session (guarded by `_sanitized` flag)

---

### BUG #4 — HIGH: Persistent Cooldown Spam

**Spec Reference:** §14.3 (Cooldown After Reversal)

**Root Cause:** `activate_cooldown()` was called on EVERY reversal detection, even when it was already active. Combined with Bug #1 (same reversal detected every heartbeat), this meant:
- Heartbeat 1: Reversal → cooldown set for +300s
- Heartbeat 2 (during cooldown): Skip due to cooldown → OK
- Heartbeat 3 (after cooldown): Reversal detected AGAIN → cooldown reset → cycle repeats

§14.3 states:
> "When reversal detected, wait one extra interval before adjusting. This filters noise."

The intent is to cooldown **once** per reversal direction change, not indefinitely.

**Fix Applied (mmm_reversal.py):**
```python
def activate_cooldown(session):
    # Prevent re-activation if already in cooldown
    if session.get('cooldown_active', False):
        log.debug("Cooldown already active, not re-activating")
        return
    # ... set cooldown
```

Combined with Bug #1's fix (updating `last_aggressor`), this ensures:
1. Cooldown only activates once for each actual direction change
2. After cooldown expires, the next trigger uses standard formula (not reversal)

---

### BUG #5 — MEDIUM: Missing CE Adjustment Fill at 68400

**Spec Reference:** §6.1 (Record the Fill), §10 (Strike Shifting)

**Observed:** After CE strike shift to 68400:
- `ce.active_lots = 1` but `ce.adjustment_fills = []`
- The lots at 68400 come from `sanitize_session_state()` converting `original_lots` to an adjustment fill

**Root Cause:** `activate_new_strike()` correctly appends to `adjustment_fills`, but the `sanitize_session_state()` function was running every heartbeat and potentially re-creating adjustment fills from `original_lots` that hadn't been zeroed yet. Additionally, `activate_new_strike()` already sets `original_lots = 0`, so the sanitizer shouldn't need to do this work.

**Fix Applied (mmm_monitor.py `sanitize_session_state()`):**
- Added `_sanitized` flag to prevent duplicate runs
- Added guard: only move `original_lots` if `active_strike != original_strike` (actual shift)
- Uses `entry_fill_price` instead of the possibly-wrong `original_premium`

---

### BUG #6 — CRITICAL: No Transition from Reversal to Standard Mode

**Spec Reference:** §9 (After First Reversal → Standard Mode)

**Root Cause:** This is the same root cause as Bug #1 but from the perspective of the state machine transition. The spec clearly defines a state machine:

```
FIRST_EVER → (first adj) → STANDARD
STANDARD → (reversal detected) → REVERSAL_CHECK
REVERSAL_CHECK → (adj P&L < 0) → EXECUTE_REVERSAL → STANDARD
REVERSAL_CHECK → (adj P&L ≥ 0) → DO NOTHING → [SHOULD → STANDARD]
```

The "DO NOTHING" path had no transition back to STANDARD. Without updating `last_aggressor`, the system was stuck in REVERSAL_CHECK indefinitely.

**Fix Applied:** `handle_reversal_skip_transition()` completes the missing state transition:
1. `last_aggressor = aggressor.upper()` → next trigger evaluation sees "continuation" not "reversal"
2. `update_trigger_snapshots()` → trigger baseline reset to current prices

---

## 4. Calculation Walkthrough

### 4.1 Entry Premiums

Per §3 (Initial State):
```
CE fill: 92.0 at strike 69600  →  trigger_snapshot[69600] = 92.0
PE fill: 83.0 at strike 67800  →  trigger_snapshot[67800] = 83.0
total_premium_collected = (92.0 + 83.0) × 1 × 0.001 = 0.175 BTC
```

### 4.2 Standard Adjustment (CE aggressor, sell PE)

Per §5.2 Case A:
```
CE_now = 120.0 (example)
ce_trigger = 92.0
ce_excess = 120.0 - 92.0 = 28.0  (> min_trigger_move=3)

loss = (CE_now - trigger) × ce_active_lots
     = (120.0 - 92.0) × 1
     = 28.0

lots_to_sell = ⌈loss / hedge_premium × (1 + 0.05)⌉
             = ⌈28.0 / 83.0 × 1.05⌉
             = ⌈0.354⌉
             = 1
```

### 4.3 Strike Shift Calculation

Per §10: When PE premium at 67800 < shift_threshold (50):
```
1. Freeze 69600 positions → frozen_positions
2. Scan chain for new PE strike with premium ≥ 50
3. Sell new lots at shifted strike
4. Update trigger_snapshot[new_strike] = fill_premium
```

### 4.4 Reversal Calculate (PE as aggressor after CE was aggressor)

Per §5.2 Case B / §9:
```
adjustment_pnl = 0
for each CE adjustment fill:
    current = fetch_premium(fill.strike, "CE")
    adjustment_pnl += (fill.entry_premium - current) × fill.lots

Example with frozen positions at 69600:
  Fill 1: entry=78.5, current=45.0, lots=1  → pnl += (78.5 - 45.0) × 1 = 33.5
  Fill 2: entry=63.5, current=45.0, lots=1  → pnl += (63.5 - 45.0) × 1 = 18.5
  Total adj_pnl = 52.0 (POSITIVE)

Since adj_pnl ≥ 0 → DO NOTHING (skip)
→ Transition to standard mode (last_aggressor = current direction)
→ Update triggers to current premiums
```

---

## 5. Summary of Fixes Applied

| File | Change | Bug(s) Fixed |
|------|--------|-------------|
| `mmm_reversal.py` | Added `handle_reversal_skip_transition()` — updates `last_aggressor` and triggers after reversal skip | #1, #2, #6 |
| `mmm_reversal.py` | Made `activate_cooldown()` idempotent — skips if already active | #4 |
| `mmm_reversal.py` | Made `record_reversal()` deduplicate — no duplicate records for same direction | #1 |
| `mmm_monitor.py` | Updated `_process_adjustment()` to call `handle_reversal_skip_transition()` on skip | #1, #2, #6 |
| `mmm_monitor.py` | Improved `sanitize_session_state()` — runs once, fixes `original_premium` mismatch, uses `entry_fill_price` | #3, #5 |

### Impact on Spec Compliance

| Spec Section | Before Fix | After Fix |
|-------------|-----------|----------|
| §5.2 Case B | Reversal P&L computed but transition incomplete | Full transition: adj check → skip/adjust → standard mode |
| §6.2 | Triggers only updated on successful adjustment | Triggers also updated on reversal skip transitions |
| §9 | Infinite reversal loop possible | Clean state machine: reversal → check → transition |
| §14.3 | Cooldown activated on every reversal detection | Cooldown activated once per direction change |

---

## 6. Recommendations for Future Robustness

1. **Add state machine validation** — Implement explicit states (STANDARD, REVERSAL_CHECK, COOLDOWN) with validated transitions. Log illegal transitions as errors. *(Deferred — lower priority now that state transitions are correctly handled)*

2. ✅ **Cap reversal_count growth** — Added `_check_reversal_count_health()` in `mmm_monitor.py`. If `reversal_count > adjustment_count × 3` (and > 5 absolute), force-resets to `adjustment_count + 1` and flags `_reversal_loop_detected`. Runs every heartbeat as defense-in-depth.

3. ✅ **Add trigger staleness detection** — Added `_check_trigger_staleness()` in `mmm_monitor.py`. Tracks the last heartbeat where each trigger snapshot changed. If a trigger hasn't changed in 10+ heartbeats AND premium has moved >50% from the trigger value, logs a warning via `log_activity('trigger_stale', ...)`.

4. **Persistent save after every state mutation** — Ensure `_save_session()` is called immediately after any state change (not deferred to end of heartbeat). This prevents the Bug #3 race condition. *(Existing save behavior reviewed — saves occur at end of heartbeat and after critical state changes; acceptable for now)*

5. ✅ **Unit test the reversal skip path** — Added 22 tests in `test_mmm_reversal.py`:
   - Reversal detected + adj profitable → verify `last_aggressor` updated ✅
   - Reversal detected + adj profitable → verify triggers updated ✅
   - Subsequent heartbeat after skip → verify standard formula used (not reversal) ✅
   - Cooldown idempotency ✅
   - Record reversal deduplication ✅
   - Multiple sequential skip transitions ✅
   - All 22 tests passing (`pytest --import-mode=importlib`)

6. ✅ **Activity log deduplication** — Added dedup guard in `MMMActivityLog.add()` (`mmm_activity.py`). Uses `(type, session_id, message[:80])` key with 30-second suppression window. Only deduplicates spammy types (`heartbeat_start/complete`, `safety_warning`, `trigger_stale`, `info`, `warning`); never deduplicates critical events like fills or errors.

### Additional Fixes Applied During Audit

| Fix | File | Detail |
|-----|------|--------|
| `detect_reversal()` handles `None` | `mmm_reversal.py` | `last_aggressor=None` no longer causes `AttributeError` on `.lower()` |
| `_auto_close_all()` P&L fix | `mmm_monitor.py` | Now sums P&L from both original lots AND adjustment fills, not just `original_premium` |
| `trigger_stale` activity type | `mmm_activity.py` | Registered in `ACTIVITY_TYPES` for proper WebUI display |
| Top-level trigger import | `mmm_reversal.py` | Moved `from .mmm_trigger import update_trigger_snapshots` to top level for clean imports |

