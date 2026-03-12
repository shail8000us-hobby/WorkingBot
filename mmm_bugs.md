# MMM Bugs & Issues — Living Source Document

> **Created:** March 12, 2026
> **Last Updated:** March 12, 2026
> **Scope:** All 32 MMM modules (~32,900 lines) in `webui/backend/routes/mmm/`
> **Purpose:** Living tracker for all known bugs, conflicts, and improvement areas. Updated as issues are found, fixed, or verified.

---

## Status Legend

| Status | Meaning |
|---|---|
| ✅ FIXED | Verified and fixed in code (commit referenced) |
| ❌ NOT A BUG | Investigated — code is correct, auditor was wrong |
| 🔶 BACKLOG | Real issue but low priority / refactoring task |
| 🔴 OPEN | Confirmed bug, not yet fixed |

---

## Executive Summary

The MMM algo has grown to 32,900+ lines across 32 modules. This document tracks all known issues — bugs, logic conflicts, duplicated logic, dead code, and design fragility.

**Audit verification (March 12, 2026):** Of 31 items originally reported, 8 were real bugs and fixed (commit `11d50b003`), 5 were false positives (NOT bugs), and 18 remain as backlog/low-priority items.

| Category | Total | Fixed | Not a Bug | Backlog |
|---|---|---|---|---|
| Critical Bugs | 5 | 3 | 2 | 0 |
| Logic Conflicts | 7 | 4 | 2 | 1 |
| Code Duplication | 5 | 0 | 0 | 5 |
| Dead Code | 6 | 1 | 2 | 3 |
| Design Issues | 5 | 0 | 0 | 5 |
| Documentation | 4 | 0 | 0 | 4 |

---

## Part 1: Critical Bugs (Can Cause Money Loss)

### BUG-1: Perp Hedge Uses Hardcoded Delta = 0.5 for All Options — ❌ NOT A BUG

**Status:** ❌ NOT A BUG — `_calculate_portfolio_delta()` (line 6214 in mmm_monitor.py) fetches real greeks from the Delta Exchange API via `/v2/tickers/{symbol}`. The 0.5 value is only a fallback default for T4-3 projection, configurable via `perp_hedge_approx_option_delta`. The audit incorrectly analyzed the code path.

**Where:** `mmm_perp_hedge.py` lines ~114-121
**What happens:** When calculating how much perp futures to buy/sell, the code assumes every option has a delta of 0.5. In reality, options delta ranges from near 0.0 (far OTM) to near 1.0 (deep ITM).

**In plain English:** Imagine you have 50 far-OTM call lots with real delta = 0.1 each. The true portfolio delta is `50 × 0.1 × 0.001 = 0.005 BTC`. But the code calculates `50 × 0.5 × 0.001 = 0.025 BTC` — 5x too large. The perp hedge buys 5x more than needed, creating a NEW directional bet instead of neutralizing.

**When it hurts:** When you have many lots at strikes far from spot (which happens after multiple shifts). The hedge over-corrects and you lose money on the perp side.

**Fix:** Fetch real greeks from Delta Exchange API (`GET /v3/products/{product_id}/greeks`) or at minimum use a Black-Scholes approximation based on strike distance from spot.

---

### BUG-2: Partial Fill Not Propagated to Position Ledger — ✅ FIXED

**Status:** ✅ FIXED in commit `11d50b003` — All callers (close_at_5, wind_down, strike_shift) now use `result.get('filled_size', lots)` instead of the requested size.

**Where:** `mmm_executor.py` → callers in `mmm_engine.py`, `mmm_close_at_5.py`, `mmm_wind_down.py`
**What happens:** `smart_execute()` can return `filled_size = 3` when you requested `size = 5`. But callers record 5 lots in the position ledger, not 3.

**In plain English:** You told the exchange "sell 5 lots" but only 3 got filled. The algo thinks it sold 5 and records 5 in its books. Now your internal state says you have 5 lots at that strike but the exchange only has 3. Every P&L calculation from this point is wrong.

**When it hurts:** During illiquid markets, fast-moving prices, or when the exchange partially fills and cancels the rest. This is documented in `MMM_REMAINING_WORK.md` as P1-D but has NOT been fixed yet.

**Fix:** Every caller of `smart_execute()` must use `result['filled_size']` instead of the requested `size` when updating position state. Add a guard: `actual_lots = result.get('filled_size', size)`.

---

### BUG-3: `_atm_wind_down_triggered` Was Partially Fixed But Can Still Stick — ✅ FIXED

**Status:** ✅ FIXED in commit `11d50b003` — `resume()` now clears `_atm_wind_down_triggered` alongside other stale flag cleanup.

**Where:** `mmm_monitor.py` ~line 1259
**What happens:** The P1-C fix added clearing when both sides close. But if the session is paused by one-side-close guard (line 1320) and then manually resumed, `_atm_wind_down_triggered` stays True forever. The ATM wind-down can never re-arm.

**In plain English:** Spot hits your CE strike → ATM wind-down activates → CE side closes → session pauses (one-side-close guard) → you manually resume and re-enter CE → spot hits CE again → nothing happens because the flag is still set.

**When it hurts:** Any session where ATM wind-down fires once and you continue trading in the same session.

**Fix:** Clear `_atm_wind_down_triggered` in the `resume()` method alongside the other stale flag clearing.

---

### BUG-4: Safety Checks Can Fire 2-3× Per Degraded Heartbeat — ❌ NOT A BUG

**Status:** ❌ NOT A BUG — The partial/miss beat path ends with `return` at line 1011, so the normal beat safety at line 1382 never double-fires. The control flow is correct; the audit misread the code flow.

**Where:** `mmm_monitor.py` ~lines 917, 970, 1382
**What happens:** `run_all_checks()` is called up to 3 times per heartbeat: once in the partial-beat path, once in the miss-beat path, and once in the normal path. The P1-A dedup flag only prevents miss-beat from running if partial already ran. But if a partial beat runs safety AND then falls through to the normal beat path (which shouldn't happen but the control flow is complex), safety runs twice.

**In plain English:** Safety events like "whipsaw detected" could fire twice in one heartbeat, causing the score to jump by 2 instead of 1. The session pauses earlier than it should.

**When it hurts:** During network issues when the exchange is flaky — exactly when you need safety to be precise.

**Fix:** Extract `_run_safety_phase()` as described in P1-A of `MMM_REMAINING_WORK.md`. Use a per-beat boolean guard.

---

### BUG-5: Recycler Proceeds With Fewer Freed Lots Than Expected — ✅ FIXED

**Status:** ✅ FIXED in commit `11d50b003` — Phase B now uses `actual_buyback_cost = abs(phase_a_pnl) if phase_a_pnl < 0 else 0` instead of the pre-planned `buyback_cost`.

**Where:** `mmm_recycler.py` Phase A → Phase B transition
**What happens:** If Phase A targets 3 positions for buyback but only 2 succeed, Phase B still runs. It sells new lots based on the original plan (3 freed lots), not the actual (2 freed lots). The position cap check may pass because it expected 3 lots freed.

**In plain English:** You planned to recycle 30 lots but only bought back 20. The code then sells 25 new lots at the better strike. But your actual freed capacity is only 20, so you now have 5 more active lots than max_lots_per_side allows. The cap is silently violated.

**When it hurts:** During fast markets when some buyback orders fail or partially fill.

**Fix:** After Phase A completes, recount actual freed lots and recompute Phase B target. Add a strict guard: `if actual_freed < planned_freed: recompute new_lots`.

---

## Part 2: Logic Conflicts Between Settings

### CONFLICT-1: `regime_enabled=False` But Error Defaults to `BLOCK_ALL_SELLS` — ✅ FIXED

**Status:** ✅ FIXED in commit `11d50b003` — Error handler now sets `ACTION_NORMAL` instead of `ACTION_BLOCK_ALL_SELLS` when `regime_enabled=False`.

**Where:** `mmm_monitor.py` ~line 1509
**What happens:** When `regime_enabled=False`, the code runs regime engines in "observation mode" (line 1502). But if the regime engine throws an exception (line 1508), the error handler sets `session['_regime_action'] = ACTION_BLOCK_ALL_SELLS`.

**In plain English:** You explicitly disabled regime controls because you don't want them. But if the regime code crashes (import error, bad data, etc.), it silently enables the hardest block — ALL sells stopped. You didn't ask for this, and you won't know why your algo stopped adjusting.

**Fix:** When `regime_enabled=False`, the error handler should set `ACTION_NORMAL` (or at most `ACTION_WARN`), not `BLOCK_ALL_SELLS`.

---

### CONFLICT-2: ATM Shield Bypasses Regime Blocks on Safe Side Re-Sell — ❌ NOT A BUG

**Status:** ❌ NOT A BUG — Safe-side re-sell already checks `regime_engine.should_block_sell()` at line 331 of `mmm_atm_shield.py`. Sympathetic shift doesn't check regime but shifts aren't sells — they reposition, which is correct behavior.

**Where:** `mmm_atm_shield.py` lines ~331-361
**What happens:** When ATM shield fires, it closes the endangered side and re-sells at a new OTM strike. For the endangered side, regime blocks are explicitly exempted (intentional — emergency action). But the "sympathetic rebalance" also re-sells on the SAFE side without checking regime blocks.

**In plain English:** Regime says "BLOCK ALL SELLS because IV is spiking." ATM shield fires and (correctly) closes the endangered CE side. But then it also sells new PE lots on the safe side without asking the regime engine. You end up adding new risk during a vol spike, which is exactly what the regime was trying to prevent.

**Fix:** Check `regime_engine.should_block_sell(session, safe_side)` before sympathetic rebalance. If blocked, skip the safe-side re-sell.

---

### CONFLICT-3: Whipsaw Detection Uses Adjustment Count But Reversal Resets Aggressor — ✅ FIXED

**Status:** ✅ FIXED in commit `11d50b003` — `handle_reversal_skip_transition()` now records in `adjustment_history` with `type: 'reversal_skip'` so whipsaw detector sees direction changes.

**Where:** `mmm_safety.py` whipsaw check vs `mmm_reversal.py` transition
**What happens:** Whipsaw detects CE→PE→CE alternation by counting direction changes. But when a reversal is detected (and skipped because P&L is positive), `handle_reversal_skip_transition()` updates `last_aggressor` WITHOUT incrementing `adjustment_count`. The whipsaw detector doesn't see this direction change.

**In plain English:** The market whipsaws but each reversal is skipped (profitable). Whipsaw protection never fires because the alternation happens through the reversal-skip path which doesn't count as an adjustment. The algo keeps selling into a choppy market until it hits the position cap.

**Fix:** Record reversal-skip transitions in the whipsaw detector's history, even when no actual adjustment occurs.

---

### CONFLICT-4: Wind-Down `floor_action='pause'` Behavior Undefined — ❌ NOT A BUG

**Status:** ❌ NOT A BUG — `_process_wind_down_buyback()` already handles `action='pause'` at lines 2310-2314 of `mmm_monitor.py`, calling `self.pause()`. The audit missed this handler.

**Where:** `mmm_wind_down.py` ~line 380, `mmm_monitor.py` trigger processing
**What happens:** `compute_wind_down_action()` can return `floor_action='pause'`. The wind_down module logs it and returns it. But the monitor's trigger processing only checks for `floor_action='skip'` and `floor_action='normal'`. The 'pause' value falls through to... nothing.

**In plain English:** You set `wind_down_floor_action=pause` thinking "pause the session if there's nothing to wind down." But the code ignores this value entirely. The session keeps running normally.

**Fix:** Add explicit handling in the monitor's trigger processing for `floor_action == 'pause'` → call `self.pause('Wind-down floor: no action available')`.

---

### CONFLICT-5: Margin Guardian Thresholds and Regime Controls Can Double-Block — 💠 BACKLOG

**Status:** 💠 BACKLOG — Low priority. Cosmetic issue — double alerts are noisy but don't cause wrong behavior.

**Where:** `mmm_monitor.py` Step 0.5 (margin) + Step 3.5 (regime)
**What happens:** Margin Guardian at YELLOW sets `_margin_block_sells = True`. Later, regime controls at VOL_HIGH also set `_regime_action = BLOCK_ALL_SELLS`. The adjustment engine checks BOTH and logs two separate block reasons, but the activity log and WebSocket emit two separate alerts for what is effectively the same action.

**In plain English:** You get two alerts: "Margin blocks sells" and "Regime blocks sells" on the same heartbeat. The operator thinks there are two problems when really it's one market condition causing both systems to react.

**Fix:** Add a dedup layer in the adjustment engine: if both margin and regime block sells, emit a single unified alert mentioning both reasons.

---

### CONFLICT-6: `close_at_atm` and `wind_down_on_atm` Fire at Same Threshold (0.5%) — ✅ FIXED

**Status:** ✅ FIXED in commit `11d50b003` — `close_at_atm` now checks `session.get('_atm_wind_down_triggered')` and skips if set — wind-down takes priority.

**Where:** `mmm_monitor.py` lines ~1085 and ~1153
**What happens:** Both features use the same 0.5% proximity threshold. If both are enabled, `wind_down_on_atm` runs first (it's checked first in the code). It sets `_atm_wind_down_triggered = True` and activates wind-down. Then `close_at_atm` runs, sees the same proximity, and immediately closes ALL positions.

**In plain English:** You enable both features thinking "try wind-down first, close if it fails." But both fire on the same heartbeat. Wind-down activates, then close_at_atm immediately overrides it and closes everything. The wind-down never gets a chance to work.

**Fix:** Add a guard in `close_at_atm` block: `if session.get('_atm_wind_down_triggered'): skip close_at_atm` (wind-down takes priority). Or: use separate thresholds (e.g., wind-down at 0.8%, close at 0.3%).

---

### CONFLICT-7: Shift Frequency Has No Cooldown — ✅ FIXED

**Status:** ✅ FIXED in commit `11d50b003` — Added `shift_cooldown_sec` parameter (default 120s) with `_last_shift_time` tracking in `mmm_state.py` and `mmm_monitor.py`.

**Where:** `mmm_strike_shift.py`
**What happens:** There's no cooldown between strike shifts. If BTC oscillates around a level, the algo can shift CE, then shift PE, then shift CE again — all within consecutive heartbeats.

**In plain English:** Each shift creates a new position and freezes old ones. Rapid shifts create a trail of frozen positions, each with a tiny premium. The frozen lot count explodes, M1/M2 recycling gets overwhelmed, and you end up with 50+ frozen positions scattered across 10 strikes. The close-at-5 scan takes longer, the P&L computation gets slow, and reconciliation with the exchange becomes unreliable.

**Fix:** Add `shift_cooldown_sec` parameter (suggest default: 300s). Record `_last_shift_time` in session. Skip shift if within cooldown.

---

## Part 3: Code Duplication

### DUP-1: Heartbeat Cleanup Pattern (5+ copies) — 💠 BACKLOG

**Where:** `mmm_monitor.py` — lines 857-864, 1220-1228, 1273-1281, 1321-1331, 1410-1418, 1423-1431
**What happens:** The exact same 6-line block appears 6+ times:
```python
current_pnl = session.get('unrealized_pnl', 0) + session.get('realized_pnl', 0) - session.get('total_fees', 0)
update_peak_pnl(session, current_pnl)
self._emit_heartbeat_data(ce_now, pe_now)
self._save_my_session(session)
latency_ms = (time.monotonic() - beat_start_mono) * 1000
self._health.record_beat('ok', latency_ms=latency_ms)
```

**Why it matters:** If you need to add a step (e.g., analytics recording), you have to change 6 places. Miss one and you get inconsistent behavior on that exit path.

**Fix:** Extract `_finalize_heartbeat(session, ce_now, pe_now, beat_start_mono, outcome='ok')` as described in P2-A of `MMM_REMAINING_WORK.md`.

---

### DUP-2: ATM Proximity Check Logic (2 copies) — 💠 BACKLOG

**Where:** `mmm_monitor.py` — `wind_down_on_atm` block (~lines 1085-1151) and `close_at_atm` block (~lines 1153-1229)
**What happens:** Both blocks do the same thing: fetch spot, calculate 0.5% threshold, check CE and PE active strikes, check active_lots > 0, defer to ATM Shield if enabled. The only difference is what happens when triggered (wind-down vs close-all).

**Why it matters:** The March 12 bug fix (switching from `original_strike` to `active_strike`) had to be applied in BOTH blocks. If someone fixes one and forgets the other, they'll diverge.

**Fix:** Extract `_check_atm_proximity() -> Optional[str]` that returns the triggered side (or None). Both features call this function.

---

### DUP-3: ATM Shield Deferral Logic (2 copies) — 💠 BACKLOG

**Where:** Inside both ATM proximity blocks (lines ~1109-1116 and ~1179-1186)
**What happens:** Identical check: `if atm_shield_enabled and shield_count < max_per_session: skip`.

**Fix:** Move into the extracted `_check_atm_proximity()` function.

---

### DUP-4: P&L Calculation Formula (3+ copies) — 💠 BACKLOG

**Where:** `mmm_monitor.py` multiple locations, `mmm_safety.py` `check_max_loss()`, `mmm_engine.py` `compute_total_pnl()`
**What happens:** The formula `unrealized + realized - fees + perp_pnl` is computed inline in multiple places, each with slightly different field names or inclusion of perp P&L.

**Why it matters:** Some places include perp P&L, others don't. In `mmm_monitor.py` the cleanup block computes `unrealized + realized - fees` (no perp), while `check_max_loss()` adds perp. If the max-loss check thinks P&L is -4900 but the heartbeat cleanup thinks it's -5100 (or vice versa), you get inconsistent behavior.

**Fix:** Use `engine.compute_total_pnl(session)` everywhere. It already exists and includes all components.

---

### DUP-5: Regime Status Logging (3 copies) — 💠 BACKLOG

**Where:** `mmm_monitor.py` lines ~1531-1550 (regime enabled), ~1490-1510 (regime disabled observation mode)
**What happens:** Both paths compute regime status, call `emit_regime()`, and conditionally log. The observation-mode path is a stripped copy of the enforced path.

**Fix:** Extract `_emit_regime_status(session, observation_mode: bool)`.

---

## Part 4: Dead Code

### DEAD-1: `close_5_enabled` Parameter — ❌ NOT A BUG

**Status:** ❌ NOT A BUG — This parameter does NOT exist in `DEFAULT_PARAMS` in `mmm_state.py`. The audit incorrectly claimed it existed.

**Where:** `mmm_state.py` DEFAULT_PARAMS
**What:** This param exists in DEFAULT_PARAMS but is never checked anywhere in the codebase. Close-at-5 always runs (it's called unconditionally in the heartbeat). There's no way to disable it.

**Impact:** Operator confusion — they might set `close_5_enabled=False` thinking it'll disable buybacks. Nothing happens.

**Fix:** Either implement the gate (add `if params.get('close_5_enabled', True):` before the close-at-5 call) or remove the parameter entirely.

---

### DEAD-2: `enable_reversal` Parameter — ❌ NOT A BUG

**Status:** ❌ NOT A BUG — This parameter does NOT exist in `DEFAULT_PARAMS` in `mmm_state.py`. The audit incorrectly claimed it existed.

**Where:** `mmm_state.py` DEFAULT_PARAMS
**What:** This boolean exists but reversal detection always runs in the heartbeat. The `detect_reversal()` function doesn't check this flag.

**Impact:** Same as DEAD-1 — misleading parameter.

**Fix:** Either wire it in or remove it.

---

### DEAD-3: P2-E Force Event Already Implemented — 💠 BACKLOG

**Status:** 💠 BACKLOG — Doc-only fix needed. `MMM_REMAINING_WORK.md` should mark P2-E as DONE.

**Where:** `MMM_REMAINING_WORK.md` P2-E says `_force_event = threading.Event()` is "set but never .set() called."
**What:** This is WRONG — the P2-E doc is outdated. `force_heartbeat()` (line ~501) calls `self._force_event.set()`. The feature IS implemented and working.

**Impact:** Misleading remaining-work doc. Someone might try to "implement" it again and break the existing working code.

**Fix:** Update `MMM_REMAINING_WORK.md` to mark P2-E item about `_force_event` as DONE.

---

### DEAD-4: Tombstone Comment at Line ~1340 — 💠 BACKLOG

**Status:** 💠 BACKLOG — Low priority cosmetic cleanup.

**Where:** `mmm_monitor.py` line 1340
**What:** Comment says "NOTE: Proactive wind-down (buying back on every heartbeat) was removed." This is historical context that belongs in git history, not in production code.

**Impact:** None functionally, but adds noise to an already 6,500-line file.

**Fix:** Delete the comment. Git blame preserves the history.

---

### DEAD-5: `perp_hedge_*` Parameters in Non-Perp Sessions — 💠 BACKLOG

**Status:** 💠 BACKLOG — UI clutter only, no functional impact.

**Where:** `mmm_state.py` DEFAULT_PARAMS
**What:** All 15+ `perp_hedge_*` parameters are included in every session even when `perp_hedge_enabled=False`. They're never read unless perp hedging is on.

**Impact:** UI clutter — the settings dialog shows 15 perp parameters even when the feature is off.

**Fix:** Move to a feature-flag block or hide from UI when disabled.

---

### DEAD-6: Stale `_being_closed` Flags Can Persist Across Restarts — ✅ FIXED

**Status:** ✅ FIXED in commit `11d50b003` — `start()` now clears all `_being_closed` flags on all positions at startup.

**Where:** `mmm_close_at_5.py`
**What:** The `_being_closed` in-flight guard is set on position dicts before placing orders. If the process crashes mid-order, the flag persists in storage. On restart, the position is permanently skipped by close-at-5 because it thinks an order is in flight.

**Impact:** Position never gets closed. Premium decays to zero but the position stays in the ledger consuming capacity.

**Fix:** In `start()`, clear all `_being_closed` flags on all positions. Or add a TTL: if `_being_closed_at` is >5 minutes old, clear the flag.

---

## Part 5: Design Issues (Not Bugs, But Fragile)

### DESIGN-1: `mmm_monitor.py` Is a 6,579-Line God Object — 💠 BACKLOG

The monitor handles: lifecycle, heartbeat loop, premium fetching, close-at-5 orchestration, shift orchestration, ATM checks, regime orchestration, trigger evaluation, adjustment execution, P&L computation, delta calculation, WebSocket emission, session saving, analytics tracking, reconciliation, and more.

**Why it matters:** Any change to one feature risks breaking another because they share local variables, control flow flags (`_skip_to_pnl`, `_partial_safety_checked`), and implicit ordering.

**Recommendation:** Follow P2-A from `MMM_REMAINING_WORK.md`. Start with `_finalize_heartbeat()` extraction — lowest risk, highest readability gain.

---

### DESIGN-2: Session Dict Is an Untyped God Dictionary — 💠 BACKLOG

The session is a plain dict with 300+ keys. Any module can add/read/modify any key. There's no schema validation, no type hints on what keys exist, and no compile-time error if you misspell a key.

**Examples of keys added ad-hoc:** `_whipsaw_last_noise_at`, `_consecutive_dir_blocked`, `_atm_wind_down_triggered`, `_margin_rapid_check`, `_regime_spot_price`, `_proactive_shifted_ce`, `_one_side_closed_ce`, etc.

**Why it matters:** A typo like `_atm_wind_down_triggred` (note missing 'e') silently creates a new key. The real flag is never set/read, and the ATM wind-down guard fails.

**Recommendation:** P3 backlog — create a `SessionKeys` constants class or TypedDict for critical keys.

---

### DESIGN-3: Margin Guardian Wallet Selection Heuristic — 💠 BACKLOG

**Where:** `mmm_margin_guardian.py` ~lines 150-158
**What:** The code searches for a wallet named "USD" or "USDT" or falls back to the largest wallet. If Delta Exchange changes their naming convention, the code could pick the wrong wallet and report incorrect margin utilization.

**Why it matters:** Wrong utilization → wrong tier → wrong defense action. At RED tier, it closes all positions. If it picks the wrong wallet and sees 90% utilization on a tiny test wallet, it'll emergency-close your main trading positions.

**Recommendation:** Log the selected wallet clearly. Add a configurable `margin_wallet_name` parameter.

---

### DESIGN-4: Theta Acceleration Can Push Intervals to 5 Seconds — 💠 BACKLOG

**Where:** `mmm_trigger.py` `apply_theta_acceleration()`
**What:** In the last 5 minutes before expiry, the interval can shrink to 5s and the trigger sensitivity widens. This means the algo fires an adjustment every 5 seconds.

**Why it matters:** Each adjustment involves: premium fetch (1s), safety checks (0.1s), lot calculation (0.1s), order placement with 60s fill timeout, state save (0.1s). At 5s intervals, you'll have overlapping heartbeats. The re-entrancy guard (line 740) will reject them, causing "skipping" warnings to flood the logs.

**Recommendation:** Add a floor: `effective_interval = max(interval, heartbeat_execution_time * 2)`. Or: add `min_heartbeat_interval` parameter (suggest 30s).

---

### DESIGN-5: Ring Buffer Deque↔List Conversions in Regime Engine — 💠 BACKLOG

**Where:** `mmm_regime.py` lines ~110-124
**What:** IV, spot, and gamma history use `deque(maxlen=60)` for automatic eviction. But they're stored as lists in the session dict (for JSON serialization). Every heartbeat: load list → convert to deque → append → convert back to list.

**Why it matters:** If the list grows beyond 60 (e.g., manual session edit), the deque conversion silently truncates. The data is correct but the conversion overhead happens 3× per heartbeat for 3 ring buffers.

**Recommendation:** Minor — the fix is already applied (L-5). Just be aware of it.

---

## Part 6: Documentation vs Code Conflicts

### DOC-1: `min_trigger_move` Default Inconsistency — 💠 BACKLOG

- **AI_MMM_CONTEXT.md §2.9:** Says default is "3%"
- **MMM_USERGUIDE.md §4:** Shows default as "10%"
- **Code (mmm_state.py DEFAULT_PARAMS):** Actual default is **10.0**

**Verdict:** Code is correct (10%). The AI_MMM_CONTEXT.md is outdated.

---

### DOC-2: Whipsaw Protection in Userguide Is Oversimplified — 💠 BACKLOG

- **Userguide §12:** Describes the OLD binary whipsaw detection (limit + pause)
- **Code:** Uses the new graduated CAUTION/RESTRICT/COOLDOWN score system

**Verdict:** Userguide needs updating to describe the score-based system.

---

### DOC-3: `MMM_REMAINING_WORK.md` P2-E Has Stale Item — 💠 BACKLOG

- **P2-E:** Lists `_force_event` as dead code ("set but never .set() called")
- **Code:** `force_heartbeat()` does call `self._force_event.set()` — this is implemented and working

**Verdict:** Remove from P2-E. Mark as DONE.

---

### DOC-4: Safety Table Missing Entries — 💠 BACKLOG

- **Userguide §5:** Lists 10 safety checks
- **Code:** Actually has 12+ checks including: `check_total_exposure()`, `check_max_loss_sizing()`, `check_margin()` (proxy), `check_lot_velocity()`

**Verdict:** Add missing checks to the userguide table.

---

## Summary Table

| ID | Severity | Type | Module | Status | Description |
|---|---|---|---|---|---|
| BUG-1 | **CRITICAL** | Bug | mmm_perp_hedge | ❌ NOT A BUG | Hardcoded delta=0.5 — actually fetches real greeks |
| BUG-2 | **CRITICAL** | Bug | mmm_executor/engine | ✅ FIXED | Partial fill not propagated to ledger |
| BUG-3 | **HIGH** | Bug | mmm_monitor | ✅ FIXED | `_atm_wind_down_triggered` sticks after resume |
| BUG-4 | **HIGH** | Bug | mmm_monitor | ❌ NOT A BUG | Safety checks — partial beat returns, can't double-fire |
| BUG-5 | **HIGH** | Bug | mmm_recycler | ✅ FIXED | Phase B proceeds with fewer freed lots |
| CONFLICT-1 | **HIGH** | Conflict | mmm_monitor | ✅ FIXED | Disabled regime defaults to BLOCK_ALL on error |
| CONFLICT-2 | **MEDIUM** | Conflict | mmm_atm_shield | ❌ NOT A BUG | Safe side re-sell already checks regime |
| CONFLICT-3 | **MEDIUM** | Conflict | mmm_safety/reversal | ✅ FIXED | Whipsaw misses reversal-skip transitions |
| CONFLICT-4 | **LOW** | Conflict | mmm_wind_down | ❌ NOT A BUG | `floor_action='pause'` already handled |
| CONFLICT-5 | **LOW** | Conflict | mmm_monitor | 🔶 BACKLOG | Margin+regime double-alert |
| CONFLICT-6 | **HIGH** | Conflict | mmm_monitor | ✅ FIXED | close_at_atm and wind_down_on_atm clash |
| CONFLICT-7 | **MEDIUM** | Conflict | mmm_strike_shift | ✅ FIXED | No shift cooldown → 120s cooldown added |
| DUP-1 | **MEDIUM** | Duplication | mmm_monitor | 🔶 BACKLOG | Heartbeat cleanup 6× copy-paste |
| DUP-2 | **MEDIUM** | Duplication | mmm_monitor | 🔶 BACKLOG | ATM proximity check 2× |
| DUP-3 | **LOW** | Duplication | mmm_monitor | 🔶 BACKLOG | ATM Shield deferral 2× |
| DUP-4 | **MEDIUM** | Duplication | multiple | 🔶 BACKLOG | P&L formula inconsistent |
| DUP-5 | **LOW** | Duplication | mmm_monitor | 🔶 BACKLOG | Regime status emit 2× |
| DEAD-1 | **LOW** | Dead code | mmm_state | ❌ NOT A BUG | `close_5_enabled` doesn't exist in DEFAULT_PARAMS |
| DEAD-2 | **LOW** | Dead code | mmm_state | ❌ NOT A BUG | `enable_reversal` doesn't exist in DEFAULT_PARAMS |
| DEAD-3 | **LOW** | Dead doc | MMM_REMAINING_WORK | 🔶 BACKLOG | P2-E lists working code as dead |
| DEAD-4 | **LOW** | Dead code | mmm_monitor | 🔶 BACKLOG | Tombstone comment |
| DEAD-5 | **LOW** | Dead code | mmm_state | 🔶 BACKLOG | Perp params in non-perp sessions |
| DEAD-6 | **HIGH** | Bug | mmm_close_at_5 | ✅ FIXED | `_being_closed` persists across restart |
| DESIGN-1 | **MEDIUM** | Design | mmm_monitor | 🔶 BACKLOG | 6,579-line god object |
| DESIGN-2 | **MEDIUM** | Design | mmm_state | 🔶 BACKLOG | Untyped session dict |
| DESIGN-3 | **MEDIUM** | Design | mmm_margin_guardian | 🔶 BACKLOG | Fragile wallet selection |
| DESIGN-4 | **MEDIUM** | Design | mmm_trigger | 🔶 BACKLOG | 5s interval floor |
| DESIGN-5 | **LOW** | Design | mmm_regime | 🔶 BACKLOG | Deque↔list conversions |
| DOC-1 | **LOW** | Doc conflict | AI_MMM_CONTEXT | 🔶 BACKLOG | min_trigger_move default wrong |
| DOC-2 | **LOW** | Doc conflict | Userguide | 🔶 BACKLOG | Whipsaw section outdated |
| DOC-3 | **LOW** | Doc conflict | REMAINING_WORK | 🔶 BACKLOG | _force_event marked dead but working |
| DOC-4 | **LOW** | Doc conflict | Userguide | 🔶 BACKLOG | Missing safety checks in table |

---

## Remaining Work Priority

### Next Up (When Time Permits)
| Priority | ID | Effort | Description |
|---|---|---|---|
| 1 | DUP-1 | 2h | Extract `_finalize_heartbeat()` — readability win |
| 2 | DUP-2/3 | 1h | Extract ATM proximity check function |
| 3 | DUP-4 | 1h | Unify P&L formula to `engine.compute_total_pnl()` |
| 4 | DOC-1/2/3/4 | 1h | Documentation consistency updates |

### Backlog (Low Priority)
| ID | Description |
|---|---|
| CONFLICT-5 | Margin+regime double-alert dedup |
| DUP-5 | Regime status emit consolidation |
| DEAD-3/4/5 | Dead code/doc/comment cleanup |
| DESIGN-3 | Configurable margin wallet name |
| DESIGN-4 | Min heartbeat interval floor |
| DESIGN-5 | Ring buffer conversion optimization |

### Long-Term Architecture (Multi-Week)
| ID | Description |
|---|---|
| DESIGN-1 | Monitor god object decomposition |
| DESIGN-2 | TypedDict for session keys |

---

## Change Log

| Date | Items | Commit | Notes |
|---|---|---|---|
| 2026-03-12 | BUG-2, BUG-3, BUG-5, CONFLICT-1, CONFLICT-3, CONFLICT-6, CONFLICT-7, DEAD-6 | `11d50b003` | 8 fixes from audit verification |
| 2026-03-12 | BUG-1, BUG-4, CONFLICT-2, CONFLICT-4, DEAD-1, DEAD-2 | — | Verified as NOT bugs (7 false positives) |

---

*This is a living document. Update it when bugs are found, fixed, or verified. Use the Change Log to track all modifications.*
