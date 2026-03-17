# MMM Algorithm: Deep Code Analysis & Hidden Bugs Report

## Executive Summary
A comprehensive, line-by-line analysis of the MMM codebase was conducted focusing on logic conflicts, race conditions, and integration issues between modules. The analysis revealed **4 potential bugs**. After independent senior code review against the actual source code:

- **2 bugs confirmed REAL and FIXED** (Bug 1 critical, Bug 3 high)
- **1 bug confirmed FALSE** (Bug 2 — already had defensive guard)
- **1 bug PARTIALLY TRUE and FIXED** (Bug 4 — narrower than originally claimed)

All 436 sealed tests pass after fixes. Zero regressions.

---

## 1. CRITICAL BUG: Guaranteed Double-Hedging of Frozen Positions
**Severity:** CRITICAL
**Modules:** `mmm_trigger.py` vs `mmm_engine.py`
**Verdict:** REAL — FIXED

**The Conflict:**
There was a contradiction between how the Trigger system and the Engine treated losses on shifted/frozen positions.
*   In `mmm_trigger.py` (line 201), `update_trigger_snapshots` explicitly updates the trigger snapshot for all frozen positions to their *current* premium. The inline comments state: *"This makes frozen position loss INCREMENTAL (since last hedge) instead of lifetime (since entry), preventing double-counting."*
*   However, in `mmm_engine.py` (line 167), `calculate_standard_loss` completely ignored this trigger snapshot. It computed the loss for frozen positions using `(_D(p_current) - _D(p_entry)) * _D(p_lots)`. The inline comments stated: *"Use entry_premium as baseline for frozen positions (lifetime loss)."*

**Root Cause:** The frozen trigger snapshots were **dead writes** — `update_trigger_snapshots()` wrote them after every hedge, but no code anywhere ever read `trigger_snapshot[frozen_strike_key]` for any loss calculation. Only the active strike key was ever consumed.

**The Financial Impact:**
This logic gap caused compounding over-hedging:
1. Frozen CE position entered at $100, shifts when premium reaches $120 — $20 loss hedged.
2. Trigger system ratchets snapshot up to $120.
3. Premium hits $130 — incremental loss should be $10.
4. But engine used lifetime `p_entry` ($100), calculated $30 loss — re-hedging the $20 already covered.
5. Over-hedging compounds on every subsequent trigger event.

**Fix Applied (`mmm_engine.py`):**
Changed `calculate_standard_loss` to use `trigger_snapshot[frozen_strike_key]` as baseline for frozen positions when available (incremental loss since last hedge). Falls back to `entry_premium` only if no snapshot exists yet (first hedge cycle for that position). This aligns with the documented intent of `update_trigger_snapshots`.

---

## 2. ~~HIGH BUG: ITM Guard is Silently Bypassed by Auto-Shift Fallback~~
**Severity:** ~~HIGH~~ N/A
**Modules:** `mmm_monitor.py`
**Verdict:** FALSE — no bug exists

**Original Claim:**
The `_process_shift_fallback` method executes a sell at the current active strike, which would be the exact ITM strike that the ITM Guard just refused to sell.

**Actual Code (verified):**
`_process_shift_fallback` (line ~4005) has its **own independent ITM Guard check** that blocks the sell if the fallback strike is ITM:

```python
# _process_shift_fallback (lines 4005-4029)
itm_guard_on = session.get('params', {}).get('itm_guard_enabled', True)
if hedge_strike:
    spot_price = await self._fetch_spot_price()
    if is_itm and itm_guard_on:
        log.warning(f"ITM GUARD (shift fallback): ...")
        log_activity('itm_guard_blocked', ..., {'context': 'shift_fallback'})
        return  # BLOCKS THE SELL
```

The comment even states: `# ITM Guard check (same as normal adjustment)`. This defensive guard was already in place — the bug report's claim is incorrect.

---

## 3. HIGH BUG: Partial Wind-Down Failure Corrupts Trigger Snapshots
**Severity:** HIGH
**Modules:** `mmm_monitor.py`
**Verdict:** REAL — FIXED

**The Conflict:**
In `_process_wind_down_buyback` (line 2571), the algorithm groups fills and places separate buy orders for each strike. If *any* single order fails, `any_failed = True`. The `update_trigger_snapshots` call was gated by `if not any_failed:`, meaning it was skipped entirely on partial failure.

**The Impact:**
When Strike 1 succeeds but Strike 2 fails:
- Session state is already mutated (lots removed, P&L booked for Strike 1 at lines 2710-2716)
- But trigger snapshots don't update because `any_failed = True`
- Stale snapshots cause the trigger system to mis-evaluate on subsequent heartbeats for positions that were already closed

**Fix Applied (`mmm_monitor.py`):**
Removed the `if not any_failed:` gate. `update_trigger_snapshots` is now called unconditionally after the buyback loop. Rationale: successful buybacks already mutated session state — the snapshots must stay in sync regardless of whether unrelated strikes failed.

---

## 4. MEDIUM BUG: ATM Shield Deferral Gate Mismatch
**Severity:** MEDIUM (narrower than originally claimed)
**Modules:** `mmm_monitor.py`, `mmm_atm_shield.py`
**Verdict:** PARTIALLY TRUE — FIXED

**Original Claim (inaccurate parts):**
> "The ATM Shield only reduces the position by up to 50% max"

This is **false**. The ATM Shield closes **100%** of positions on the endangered side, then re-establishes at a safer OTM strike. It is a full position shift, not a partial reduction.

**The Real Bug (confirmed):**
Both `wind_down_on_atm` (~line 1188) and `close_at_atm` (~line 1268) deferred to the ATM Shield based solely on **capacity** (`shield_count < max_per_session`). However, the actual shield execution at Step 5.5 is gated by `_check_shield_gates()` which checks 6 additional conditions: session status, margin tier, auto-close window, per-side cooldown, capacity, and proactive shift status.

This mismatch meant: if the shield had capacity but was blocked by cooldown, margin RED/CRITICAL, or the `_skip_to_pnl` flag, both wind-down and close-at-ATM were suppressed for nothing — the shield wouldn't fire either.

**Fix Applied (`mmm_monitor.py`):**
Replaced the simple capacity check at both deferral points with a call to `_check_shield_gates()`, which validates all 6 gate conditions. If any gate fails, wind-down/close-at-ATM proceeds normally instead of being suppressed. Added import of `_check_shield_gates` from `mmm_atm_shield`.

---

## Conclusion (Session 1)

| Bug | Original Claim | Verdict | Action |
|-----|---------------|---------|--------|
| 1. Double-hedging frozen positions | CRITICAL | **REAL** | Fixed in `mmm_engine.py` |
| 2. ITM Guard bypass by fallback | HIGH | **FALSE** | No action needed — guard already existed |
| 3. Wind-down partial failure snapshots | HIGH | **REAL** | Fixed in `mmm_monitor.py` |
| 4. ATM Shield deferral mismatch | MEDIUM | **PARTIALLY TRUE** | Fixed in `mmm_monitor.py` |

**Tests:** 436 sealed tests pass, 0 failures, 0 regressions.

---

## Session 2 Analysis (2026-03-17)

A second independent deep analysis was performed. 5 potential bugs were raised by a subagent; after verifying each against actual source code, 2 were confirmed real. The remaining 3 were false positives with existing mitigations.

### FALSE POSITIVES (mitigated by existing code)

| Agent Bug | Claim | Why FALSE |
|-----------|-------|-----------|
| Optimistic state before fill confirmation | HIGH | `smart_execute` validates `filled_size` and only returns `success=True` after exchange fill is confirmed. State update is post-confirmation. |
| Partial fill `filled_size` defaults to requested | MEDIUM | Executor returns `failure` if `unfilled_size` is missing (line 388-392). `filled_size` always present on `success=True`. |
| Trigger guard blocks both sides on missing snapshot | MEDIUM | Trigger snapshot HEAL at `mmm_monitor.py:1099–1118` initializes both CE+PE snapshots to current premiums **before** `evaluate_triggers()` runs every heartbeat. |

---

## 5. HIGH BUG: Trigger Snapshot Set to Stale Pre-Execution Premium
**Severity:** HIGH
**Module:** `mmm_monitor.py`
**Verdict:** REAL — FIXED

**The Problem:**
After `execute_adjustment` succeeds, `_update_state_after_adjustment` calls `update_trigger_snapshots(session, ce_now, pe_now, ...)`. These `ce_now`/`pe_now` values were captured at **heartbeat start** (line 959). `smart_execute` takes 30–60 seconds. In a trending market:

1. Heartbeat: CE = $100, trigger = $85 → fires.
2. `smart_execute` runs 45s. CE moves to $115 during execution.
3. Trigger snapshot set to **stale $100**.
4. Next heartbeat: CE = $115. Excess = 15% → **immediate re-trigger**.

The strike-shift path already had this fix (BUG-1 FIX at `_process_strike_shift`). Normal adjustments did not.

**Fix Applied (`mmm_monitor.py`):**
After `execute_adjustment` succeeds, call `_fetch_premiums()` to get live CE and PE premiums, then call `update_trigger_snapshots` with the fresh values. Wrapped in try/except — a failed refresh degrades gracefully to the stale snapshot rather than breaking the adjustment.

---

## 6. MEDIUM BUG: Frozen Position Fetch Failure → Silent Loss Understatement
**Severity:** MEDIUM
**Module:** `mmm_engine.py`, `mmm_monitor.py`
**Verdict:** REAL — FIXED

**The Problem:**
`calculate_standard_loss` skips frozen positions when their premium fetch fails (`continue` on exception or `None`). The `calculation_incomplete=True` flag is returned, but the monitor only logged a warning and proceeded with the understated loss. During API degradation all frozen position fetches can fail simultaneously, causing the hedge to be sized from active-strike loss only — potentially missing 80%+ of total exposure.

**Fix Applied (`mmm_monitor.py`):**
When `_std_incomplete=True`, a `_last_complete_std_loss` floor is applied: the last successful loss calculation is cached per-aggressor-side on every clean beat. If the current incomplete calculation returns less than the cached complete value, the cached value is used as the loss floor. This prevents under-hedging when API degradation causes cascading fetch failures.

---

## Updated Summary

| Bug | Severity | Verdict | Action |
|-----|----------|---------|--------|
| 1. Double-hedging frozen positions | CRITICAL | REAL | Fixed — Session 1 |
| 2. ITM Guard bypass by fallback | HIGH | FALSE | No action |
| 3. Wind-down partial failure snapshots | HIGH | REAL | Fixed — Session 1 |
| 4. ATM Shield deferral mismatch | MEDIUM | PARTIALLY TRUE | Fixed — Session 1 |
| 5. Stale trigger snapshot post-execution | HIGH | REAL | Fixed — Session 2 |
| 6. Fetch failure → loss understatement | MEDIUM | REAL | Fixed — Session 2 |
