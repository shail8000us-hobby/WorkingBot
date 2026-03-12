# MMM Code Quality Audit Report

> **Date:** March 12, 2026
> **Scope:** All 32 MMM modules (~32,900 lines) in `webui/backend/routes/mmm/`
> **Auditor:** Deep code review of every function, constant, and cross-module interaction
> **Format:** Human-readable — written for a trader/developer who built this system incrementally

---

## Executive Summary

The MMM algo has grown to 32,900+ lines across 32 modules. It was built feature-by-feature over weeks, and each feature works well in isolation. But when you look at the whole system together, there are **cross-module conflicts**, **duplicated logic**, **dead code paths**, and a few **logic bugs that can cause real money loss** in specific edge cases.

This report covers:
1. **Critical Bugs** — can cause wrong trades or lost money
2. **Logic Conflicts** — settings that fight each other
3. **Code Duplication** — same thing done in multiple places
4. **Dead Code** — code that runs but does nothing, or never runs at all
5. **Design Issues** — things that work but are fragile

---

## Part 1: Critical Bugs (Can Cause Money Loss)

### BUG-1: Perp Hedge Uses Hardcoded Delta = 0.5 for All Options

**Where:** `mmm_perp_hedge.py` lines ~114-121
**What happens:** When calculating how much perp futures to buy/sell, the code assumes every option has a delta of 0.5. In reality, options delta ranges from near 0.0 (far OTM) to near 1.0 (deep ITM).

**In plain English:** Imagine you have 50 far-OTM call lots with real delta = 0.1 each. The true portfolio delta is `50 × 0.1 × 0.001 = 0.005 BTC`. But the code calculates `50 × 0.5 × 0.001 = 0.025 BTC` — 5x too large. The perp hedge buys 5x more than needed, creating a NEW directional bet instead of neutralizing.

**When it hurts:** When you have many lots at strikes far from spot (which happens after multiple shifts). The hedge over-corrects and you lose money on the perp side.

**Fix:** Fetch real greeks from Delta Exchange API (`GET /v3/products/{product_id}/greeks`) or at minimum use a Black-Scholes approximation based on strike distance from spot.

---

### BUG-2: Partial Fill Not Propagated to Position Ledger

**Where:** `mmm_executor.py` → callers in `mmm_engine.py`, `mmm_close_at_5.py`, `mmm_wind_down.py`
**What happens:** `smart_execute()` can return `filled_size = 3` when you requested `size = 5`. But callers record 5 lots in the position ledger, not 3.

**In plain English:** You told the exchange "sell 5 lots" but only 3 got filled. The algo thinks it sold 5 and records 5 in its books. Now your internal state says you have 5 lots at that strike but the exchange only has 3. Every P&L calculation from this point is wrong.

**When it hurts:** During illiquid markets, fast-moving prices, or when the exchange partially fills and cancels the rest. This is documented in `MMM_REMAINING_WORK.md` as P1-D but has NOT been fixed yet.

**Fix:** Every caller of `smart_execute()` must use `result['filled_size']` instead of the requested `size` when updating position state. Add a guard: `actual_lots = result.get('filled_size', size)`.

---

### BUG-3: `_atm_wind_down_triggered` Was Partially Fixed But Can Still Stick

**Where:** `mmm_monitor.py` ~line 1259
**What happens:** The P1-C fix added clearing when both sides close. But if the session is paused by one-side-close guard (line 1320) and then manually resumed, `_atm_wind_down_triggered` stays True forever. The ATM wind-down can never re-arm.

**In plain English:** Spot hits your CE strike → ATM wind-down activates → CE side closes → session pauses (one-side-close guard) → you manually resume and re-enter CE → spot hits CE again → nothing happens because the flag is still set.

**When it hurts:** Any session where ATM wind-down fires once and you continue trading in the same session.

**Fix:** Clear `_atm_wind_down_triggered` in the `resume()` method alongside the other stale flag clearing.

---

### BUG-4: Safety Checks Can Fire 2-3× Per Degraded Heartbeat

**Where:** `mmm_monitor.py` ~lines 917, 970, 1382
**What happens:** `run_all_checks()` is called up to 3 times per heartbeat: once in the partial-beat path, once in the miss-beat path, and once in the normal path. The P1-A dedup flag only prevents miss-beat from running if partial already ran. But if a partial beat runs safety AND then falls through to the normal beat path (which shouldn't happen but the control flow is complex), safety runs twice.

**In plain English:** Safety events like "whipsaw detected" could fire twice in one heartbeat, causing the score to jump by 2 instead of 1. The session pauses earlier than it should.

**When it hurts:** During network issues when the exchange is flaky — exactly when you need safety to be precise.

**Fix:** Extract `_run_safety_phase()` as described in P1-A of `MMM_REMAINING_WORK.md`. Use a per-beat boolean guard.

---

### BUG-5: Recycler Proceeds With Fewer Freed Lots Than Expected

**Where:** `mmm_recycler.py` Phase A → Phase B transition
**What happens:** If Phase A targets 3 positions for buyback but only 2 succeed, Phase B still runs. It sells new lots based on the original plan (3 freed lots), not the actual (2 freed lots). The position cap check may pass because it expected 3 lots freed.

**In plain English:** You planned to recycle 30 lots but only bought back 20. The code then sells 25 new lots at the better strike. But your actual freed capacity is only 20, so you now have 5 more active lots than max_lots_per_side allows. The cap is silently violated.

**When it hurts:** During fast markets when some buyback orders fail or partially fill.

**Fix:** After Phase A completes, recount actual freed lots and recompute Phase B target. Add a strict guard: `if actual_freed < planned_freed: recompute new_lots`.

---

## Part 2: Logic Conflicts Between Settings

### CONFLICT-1: `regime_enabled=False` But Error Defaults to `BLOCK_ALL_SELLS`

**Where:** `mmm_monitor.py` ~line 1509
**What happens:** When `regime_enabled=False`, the code runs regime engines in "observation mode" (line 1502). But if the regime engine throws an exception (line 1508), the error handler sets `session['_regime_action'] = ACTION_BLOCK_ALL_SELLS`.

**In plain English:** You explicitly disabled regime controls because you don't want them. But if the regime code crashes (import error, bad data, etc.), it silently enables the hardest block — ALL sells stopped. You didn't ask for this, and you won't know why your algo stopped adjusting.

**Fix:** When `regime_enabled=False`, the error handler should set `ACTION_NORMAL` (or at most `ACTION_WARN`), not `BLOCK_ALL_SELLS`.

---

### CONFLICT-2: ATM Shield Bypasses Regime Blocks on Safe Side Re-Sell

**Where:** `mmm_atm_shield.py` lines ~331-361
**What happens:** When ATM shield fires, it closes the endangered side and re-sells at a new OTM strike. For the endangered side, regime blocks are explicitly exempted (intentional — emergency action). But the "sympathetic rebalance" also re-sells on the SAFE side without checking regime blocks.

**In plain English:** Regime says "BLOCK ALL SELLS because IV is spiking." ATM shield fires and (correctly) closes the endangered CE side. But then it also sells new PE lots on the safe side without asking the regime engine. You end up adding new risk during a vol spike, which is exactly what the regime was trying to prevent.

**Fix:** Check `regime_engine.should_block_sell(session, safe_side)` before sympathetic rebalance. If blocked, skip the safe-side re-sell.

---

### CONFLICT-3: Whipsaw Detection Uses Adjustment Count But Reversal Resets Aggressor

**Where:** `mmm_safety.py` whipsaw check vs `mmm_reversal.py` transition
**What happens:** Whipsaw detects CE→PE→CE alternation by counting direction changes. But when a reversal is detected (and skipped because P&L is positive), `handle_reversal_skip_transition()` updates `last_aggressor` WITHOUT incrementing `adjustment_count`. The whipsaw detector doesn't see this direction change.

**In plain English:** The market whipsaws but each reversal is skipped (profitable). Whipsaw protection never fires because the alternation happens through the reversal-skip path which doesn't count as an adjustment. The algo keeps selling into a choppy market until it hits the position cap.

**Fix:** Record reversal-skip transitions in the whipsaw detector's history, even when no actual adjustment occurs.

---

### CONFLICT-4: Wind-Down `floor_action='pause'` Behavior Undefined

**Where:** `mmm_wind_down.py` ~line 380, `mmm_monitor.py` trigger processing
**What happens:** `compute_wind_down_action()` can return `floor_action='pause'`. The wind_down module logs it and returns it. But the monitor's trigger processing only checks for `floor_action='skip'` and `floor_action='normal'`. The 'pause' value falls through to... nothing.

**In plain English:** You set `wind_down_floor_action=pause` thinking "pause the session if there's nothing to wind down." But the code ignores this value entirely. The session keeps running normally.

**Fix:** Add explicit handling in the monitor's trigger processing for `floor_action == 'pause'` → call `self.pause('Wind-down floor: no action available')`.

---

### CONFLICT-5: Margin Guardian Thresholds and Regime Controls Can Double-Block

**Where:** `mmm_monitor.py` Step 0.5 (margin) + Step 3.5 (regime)
**What happens:** Margin Guardian at YELLOW sets `_margin_block_sells = True`. Later, regime controls at VOL_HIGH also set `_regime_action = BLOCK_ALL_SELLS`. The adjustment engine checks BOTH and logs two separate block reasons, but the activity log and WebSocket emit two separate alerts for what is effectively the same action.

**In plain English:** You get two alerts: "Margin blocks sells" and "Regime blocks sells" on the same heartbeat. The operator thinks there are two problems when really it's one market condition causing both systems to react.

**Fix:** Add a dedup layer in the adjustment engine: if both margin and regime block sells, emit a single unified alert mentioning both reasons.

---

### CONFLICT-6: `close_at_atm` and `wind_down_on_atm` Fire at Same Threshold (0.5%)

**Where:** `mmm_monitor.py` lines ~1085 and ~1153
**What happens:** Both features use the same 0.5% proximity threshold. If both are enabled, `wind_down_on_atm` runs first (it's checked first in the code). It sets `_atm_wind_down_triggered = True` and activates wind-down. Then `close_at_atm` runs, sees the same proximity, and immediately closes ALL positions.

**In plain English:** You enable both features thinking "try wind-down first, close if it fails." But both fire on the same heartbeat. Wind-down activates, then close_at_atm immediately overrides it and closes everything. The wind-down never gets a chance to work.

**Fix:** Add a guard in `close_at_atm` block: `if session.get('_atm_wind_down_triggered'): skip close_at_atm` (wind-down takes priority). Or: use separate thresholds (e.g., wind-down at 0.8%, close at 0.3%).

---

### CONFLICT-7: Shift Frequency Has No Cooldown

**Where:** `mmm_strike_shift.py`
**What happens:** There's no cooldown between strike shifts. If BTC oscillates around a level, the algo can shift CE, then shift PE, then shift CE again — all within consecutive heartbeats.

**In plain English:** Each shift creates a new position and freezes old ones. Rapid shifts create a trail of frozen positions, each with a tiny premium. The frozen lot count explodes, M1/M2 recycling gets overwhelmed, and you end up with 50+ frozen positions scattered across 10 strikes. The close-at-5 scan takes longer, the P&L computation gets slow, and reconciliation with the exchange becomes unreliable.

**Fix:** Add `shift_cooldown_sec` parameter (suggest default: 300s). Record `_last_shift_time` in session. Skip shift if within cooldown.

---

## Part 3: Code Duplication

### DUP-1: Heartbeat Cleanup Pattern (5+ copies)

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

### DUP-2: ATM Proximity Check Logic (2 copies)

**Where:** `mmm_monitor.py` — `wind_down_on_atm` block (~lines 1085-1151) and `close_at_atm` block (~lines 1153-1229)
**What happens:** Both blocks do the same thing: fetch spot, calculate 0.5% threshold, check CE and PE active strikes, check active_lots > 0, defer to ATM Shield if enabled. The only difference is what happens when triggered (wind-down vs close-all).

**Why it matters:** The March 12 bug fix (switching from `original_strike` to `active_strike`) had to be applied in BOTH blocks. If someone fixes one and forgets the other, they'll diverge.

**Fix:** Extract `_check_atm_proximity() -> Optional[str]` that returns the triggered side (or None). Both features call this function.

---

### DUP-3: ATM Shield Deferral Logic (2 copies)

**Where:** Inside both ATM proximity blocks (lines ~1109-1116 and ~1179-1186)
**What happens:** Identical check: `if atm_shield_enabled and shield_count < max_per_session: skip`.

**Fix:** Move into the extracted `_check_atm_proximity()` function.

---

### DUP-4: P&L Calculation Formula (3+ copies)

**Where:** `mmm_monitor.py` multiple locations, `mmm_safety.py` `check_max_loss()`, `mmm_engine.py` `compute_total_pnl()`
**What happens:** The formula `unrealized + realized - fees + perp_pnl` is computed inline in multiple places, each with slightly different field names or inclusion of perp P&L.

**Why it matters:** Some places include perp P&L, others don't. In `mmm_monitor.py` the cleanup block computes `unrealized + realized - fees` (no perp), while `check_max_loss()` adds perp. If the max-loss check thinks P&L is -4900 but the heartbeat cleanup thinks it's -5100 (or vice versa), you get inconsistent behavior.

**Fix:** Use `engine.compute_total_pnl(session)` everywhere. It already exists and includes all components.

---

### DUP-5: Regime Status Logging (3 copies)

**Where:** `mmm_monitor.py` lines ~1531-1550 (regime enabled), ~1490-1510 (regime disabled observation mode)
**What happens:** Both paths compute regime status, call `emit_regime()`, and conditionally log. The observation-mode path is a stripped copy of the enforced path.

**Fix:** Extract `_emit_regime_status(session, observation_mode: bool)`.

---

## Part 4: Dead Code

### DEAD-1: `close_5_enabled` Parameter

**Where:** `mmm_state.py` DEFAULT_PARAMS
**What:** This param exists in DEFAULT_PARAMS but is never checked anywhere in the codebase. Close-at-5 always runs (it's called unconditionally in the heartbeat). There's no way to disable it.

**Impact:** Operator confusion — they might set `close_5_enabled=False` thinking it'll disable buybacks. Nothing happens.

**Fix:** Either implement the gate (add `if params.get('close_5_enabled', True):` before the close-at-5 call) or remove the parameter entirely.

---

### DEAD-2: `enable_reversal` Parameter

**Where:** `mmm_state.py` DEFAULT_PARAMS
**What:** This boolean exists but reversal detection always runs in the heartbeat. The `detect_reversal()` function doesn't check this flag.

**Impact:** Same as DEAD-1 — misleading parameter.

**Fix:** Either wire it in or remove it.

---

### DEAD-3: P2-E Force Event Already Implemented

**Where:** `MMM_REMAINING_WORK.md` P2-E says `_force_event = threading.Event()` is "set but never .set() called."
**What:** This is WRONG — the P2-E doc is outdated. `force_heartbeat()` (line ~501) calls `self._force_event.set()`. The feature IS implemented and working.

**Impact:** Misleading remaining-work doc. Someone might try to "implement" it again and break the existing working code.

**Fix:** Update `MMM_REMAINING_WORK.md` to mark P2-E item about `_force_event` as DONE.

---

### DEAD-4: Tombstone Comment at Line ~1340

**Where:** `mmm_monitor.py` line 1340
**What:** Comment says "NOTE: Proactive wind-down (buying back on every heartbeat) was removed." This is historical context that belongs in git history, not in production code.

**Impact:** None functionally, but adds noise to an already 6,500-line file.

**Fix:** Delete the comment. Git blame preserves the history.

---

### DEAD-5: `perp_hedge_*` Parameters in Non-Perp Sessions

**Where:** `mmm_state.py` DEFAULT_PARAMS
**What:** All 15+ `perp_hedge_*` parameters are included in every session even when `perp_hedge_enabled=False`. They're never read unless perp hedging is on.

**Impact:** UI clutter — the settings dialog shows 15 perp parameters even when the feature is off.

**Fix:** Move to a feature-flag block or hide from UI when disabled.

---

### DEAD-6: Stale `_being_closed` Flags Can Persist Across Restarts

**Where:** `mmm_close_at_5.py`
**What:** The `_being_closed` in-flight guard is set on position dicts before placing orders. If the process crashes mid-order, the flag persists in storage. On restart, the position is permanently skipped by close-at-5 because it thinks an order is in flight.

**Impact:** Position never gets closed. Premium decays to zero but the position stays in the ledger consuming capacity.

**Fix:** In `start()`, clear all `_being_closed` flags on all positions. Or add a TTL: if `_being_closed_at` is >5 minutes old, clear the flag.

---

## Part 5: Design Issues (Not Bugs, But Fragile)

### DESIGN-1: `mmm_monitor.py` Is a 6,579-Line God Object

The monitor handles: lifecycle, heartbeat loop, premium fetching, close-at-5 orchestration, shift orchestration, ATM checks, regime orchestration, trigger evaluation, adjustment execution, P&L computation, delta calculation, WebSocket emission, session saving, analytics tracking, reconciliation, and more.

**Why it matters:** Any change to one feature risks breaking another because they share local variables, control flow flags (`_skip_to_pnl`, `_partial_safety_checked`), and implicit ordering.

**Recommendation:** Follow P2-A from `MMM_REMAINING_WORK.md`. Start with `_finalize_heartbeat()` extraction — lowest risk, highest readability gain.

---

### DESIGN-2: Session Dict Is an Untyped God Dictionary

The session is a plain dict with 300+ keys. Any module can add/read/modify any key. There's no schema validation, no type hints on what keys exist, and no compile-time error if you misspell a key.

**Examples of keys added ad-hoc:** `_whipsaw_last_noise_at`, `_consecutive_dir_blocked`, `_atm_wind_down_triggered`, `_margin_rapid_check`, `_regime_spot_price`, `_proactive_shifted_ce`, `_one_side_closed_ce`, etc.

**Why it matters:** A typo like `_atm_wind_down_triggred` (note missing 'e') silently creates a new key. The real flag is never set/read, and the ATM wind-down guard fails.

**Recommendation:** P3 backlog — create a `SessionKeys` constants class or TypedDict for critical keys.

---

### DESIGN-3: Margin Guardian Wallet Selection Heuristic

**Where:** `mmm_margin_guardian.py` ~lines 150-158
**What:** The code searches for a wallet named "USD" or "USDT" or falls back to the largest wallet. If Delta Exchange changes their naming convention, the code could pick the wrong wallet and report incorrect margin utilization.

**Why it matters:** Wrong utilization → wrong tier → wrong defense action. At RED tier, it closes all positions. If it picks the wrong wallet and sees 90% utilization on a tiny test wallet, it'll emergency-close your main trading positions.

**Recommendation:** Log the selected wallet clearly. Add a configurable `margin_wallet_name` parameter.

---

### DESIGN-4: Theta Acceleration Can Push Intervals to 5 Seconds

**Where:** `mmm_trigger.py` `apply_theta_acceleration()`
**What:** In the last 5 minutes before expiry, the interval can shrink to 5s and the trigger sensitivity widens. This means the algo fires an adjustment every 5 seconds.

**Why it matters:** Each adjustment involves: premium fetch (1s), safety checks (0.1s), lot calculation (0.1s), order placement with 60s fill timeout, state save (0.1s). At 5s intervals, you'll have overlapping heartbeats. The re-entrancy guard (line 740) will reject them, causing "skipping" warnings to flood the logs.

**Recommendation:** Add a floor: `effective_interval = max(interval, heartbeat_execution_time * 2)`. Or: add `min_heartbeat_interval` parameter (suggest 30s).

---

### DESIGN-5: Ring Buffer Deque↔List Conversions in Regime Engine

**Where:** `mmm_regime.py` lines ~110-124
**What:** IV, spot, and gamma history use `deque(maxlen=60)` for automatic eviction. But they're stored as lists in the session dict (for JSON serialization). Every heartbeat: load list → convert to deque → append → convert back to list.

**Why it matters:** If the list grows beyond 60 (e.g., manual session edit), the deque conversion silently truncates. The data is correct but the conversion overhead happens 3× per heartbeat for 3 ring buffers.

**Recommendation:** Minor — the fix is already applied (L-5). Just be aware of it.

---

## Part 6: Documentation vs Code Conflicts

### DOC-1: `min_trigger_move` Default Inconsistency

- **AI_MMM_CONTEXT.md §2.9:** Says default is "3%"
- **MMM_USERGUIDE.md §4:** Shows default as "10%"
- **Code (mmm_state.py DEFAULT_PARAMS):** Actual default is **10.0**

**Verdict:** Code is correct (10%). The AI_MMM_CONTEXT.md is outdated.

---

### DOC-2: Whipsaw Protection in Userguide Is Oversimplified

- **Userguide §12:** Describes the OLD binary whipsaw detection (limit + pause)
- **Code:** Uses the new graduated CAUTION/RESTRICT/COOLDOWN score system

**Verdict:** Userguide needs updating to describe the score-based system.

---

### DOC-3: `MMM_REMAINING_WORK.md` P2-E Has Stale Item

- **P2-E:** Lists `_force_event` as dead code ("set but never .set() called")
- **Code:** `force_heartbeat()` does call `self._force_event.set()` — this is implemented and working

**Verdict:** Remove from P2-E. Mark as DONE.

---

### DOC-4: Safety Table Missing Entries

- **Userguide §5:** Lists 10 safety checks
- **Code:** Actually has 12+ checks including: `check_total_exposure()`, `check_max_loss_sizing()`, `check_margin()` (proxy), `check_lot_velocity()`

**Verdict:** Add missing checks to the userguide table.

---

## Summary Table

| ID | Severity | Type | Module | Description |
|---|---|---|---|---|
| BUG-1 | **CRITICAL** | Bug | mmm_perp_hedge | Hardcoded delta=0.5 causes over/under-hedging |
| BUG-2 | **CRITICAL** | Bug | mmm_executor/engine | Partial fill not propagated to ledger |
| BUG-3 | **HIGH** | Bug | mmm_monitor | `_atm_wind_down_triggered` sticks after resume |
| BUG-4 | **HIGH** | Bug | mmm_monitor | Safety checks fire 2-3× per degraded beat |
| BUG-5 | **HIGH** | Bug | mmm_recycler | Phase B proceeds with fewer freed lots |
| CONFLICT-1 | **HIGH** | Conflict | mmm_monitor | Disabled regime defaults to BLOCK_ALL on error |
| CONFLICT-2 | **MEDIUM** | Conflict | mmm_atm_shield | Safe side re-sell bypasses regime |
| CONFLICT-3 | **MEDIUM** | Conflict | mmm_safety/reversal | Whipsaw misses reversal-skip transitions |
| CONFLICT-4 | **LOW** | Conflict | mmm_wind_down | `floor_action='pause'` does nothing |
| CONFLICT-5 | **LOW** | Conflict | mmm_monitor | Margin+regime double-alert |
| CONFLICT-6 | **HIGH** | Conflict | mmm_monitor | close_at_atm and wind_down_on_atm clash |
| CONFLICT-7 | **MEDIUM** | Conflict | mmm_strike_shift | No shift cooldown |
| DUP-1 | **MEDIUM** | Duplication | mmm_monitor | Heartbeat cleanup 6× copy-paste |
| DUP-2 | **MEDIUM** | Duplication | mmm_monitor | ATM proximity check 2× |
| DUP-3 | **LOW** | Duplication | mmm_monitor | ATM Shield deferral 2× |
| DUP-4 | **MEDIUM** | Duplication | multiple | P&L formula inconsistent |
| DUP-5 | **LOW** | Duplication | mmm_monitor | Regime status emit 2× |
| DEAD-1 | **LOW** | Dead code | mmm_state | `close_5_enabled` never checked |
| DEAD-2 | **LOW** | Dead code | mmm_state | `enable_reversal` never checked |
| DEAD-3 | **LOW** | Dead doc | MMM_REMAINING_WORK | P2-E lists working code as dead |
| DEAD-4 | **LOW** | Dead code | mmm_monitor | Tombstone comment |
| DEAD-5 | **LOW** | Dead code | mmm_state | Perp params in non-perp sessions |
| DEAD-6 | **HIGH** | Bug | mmm_close_at_5 | `_being_closed` persists across restart |
| DESIGN-1 | **MEDIUM** | Design | mmm_monitor | 6,579-line god object |
| DESIGN-2 | **MEDIUM** | Design | mmm_state | Untyped session dict |
| DESIGN-3 | **MEDIUM** | Design | mmm_margin_guardian | Fragile wallet selection |
| DESIGN-4 | **MEDIUM** | Design | mmm_trigger | 5s interval floor |
| DOC-1 | **LOW** | Doc conflict | AI_MMM_CONTEXT | min_trigger_move default wrong |
| DOC-2 | **LOW** | Doc conflict | Userguide | Whipsaw section outdated |
| DOC-3 | **LOW** | Doc conflict | REMAINING_WORK | _force_event marked dead but working |
| DOC-4 | **LOW** | Doc conflict | Userguide | Missing safety checks in table |

---

## Recommended Fix Priority

### Week 1 (Stop the Bleeding)
1. **BUG-2** — Partial fill propagation (P1-D) — 4 hours
2. **BUG-5** — Recycler Phase B recount — 2 hours
3. **DEAD-6** — Clear `_being_closed` on restart — 1 hour
4. **CONFLICT-1** — Regime error handler when disabled — 15 minutes
5. **CONFLICT-6** — ATM close vs wind-down priority — 30 minutes

### Week 2 (Correctness)
6. **BUG-3** — Clear `_atm_wind_down_triggered` on resume — 15 minutes
7. **BUG-4** — Safety dedup (P1-A) — 3 hours
8. **CONFLICT-2** — ATM Shield regime check for safe side — 1 hour
9. **CONFLICT-3** — Whipsaw tracking reversal skips — 2 hours
10. **CONFLICT-7** — Shift cooldown parameter — 2 hours

### Week 3 (Clean Up)
11. **DUP-1** — Extract `_finalize_heartbeat()` — 2 hours
12. **DUP-2/3** — Extract ATM proximity check — 1 hour
13. **DUP-4** — Unify P&L formula — 1 hour
14. **DEAD-1/2** — Remove or wire dead parameters — 30 minutes
15. **DOC-1/2/3/4** — Documentation updates — 1 hour

### Backlog (When Time Permits)
16. **BUG-1** — Real delta for perp hedge — 4-8 hours (needs API integration)
17. **DESIGN-1** — Monitor god object decomposition — multi-week effort
18. **DESIGN-2** — TypedDict for session keys — 4-8 hours

---

*This audit was conducted by reading every line of all 32 MMM modules, cross-referencing with 28 documentation files, and tracing logic flow across module boundaries.*
