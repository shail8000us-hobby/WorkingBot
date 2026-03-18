# MMM Lessons Learned

## [2026-03-18] exit_all: realized_pnl not persisted + slow sequential closes caused extra slippage loss

**Root cause 1 — P&L not persisted after exit (wrong save order):**
`run_exit_all()` called `update_session()` (safety-net write) BEFORE `monitor.stop()`. Between the update and stop(), a concurrent heartbeat from one of the 3 simultaneously-running monitors could write a higher `_monitor_generation` to DB, causing stop()'s generation-check to reject its save. Result: DB kept the pre-exit `realized_pnl = $7.99` instead of the post-exit `-$2.73`. Dashboard showed wrong values: R=$7.99, U=-$10.12 (stale unrealized from open positions), Total=-$2.13 instead of correct -$2.73.

**Fix:** Move `update_session()` to AFTER `monitor.stop()`. By then: `_save_disabled=True` (no concurrent heartbeats), stop() has already attempted its own save (correct in most cases), and the post-stop `update_session()` is the definitive write. Also sets `unrealized_pnl=0.0` and `strategy_status='STOPPED'` explicitly.

**Root cause 2 — Sequential closes caused 82-second execution, extra slippage:**
Original interleaved loop was `CE[0] → PE[0] → CE[1] → PE[1]` etc., processed one position at a time. For 5 positions, total wall-clock = ~82s. The most damaging position was PE @ 74000 (entry 132.50, close 257.50 = -$8.25). It was closed 28s after the exit started while BTC was near 73960 (PE deeply ITM). Every second of delay while ITM = more slippage.

**Fix:** Use `asyncio.gather()` to close CE and PE sides concurrently. Within each side, positions close sequentially by ATM proximity. Result: CE and PE close in parallel → halves wall-clock time. Also reduced INTER_ROUND_DELAY_SEC from 2s to 1s.

**Prevention rule:** exit_all is a time-critical operation. Never close CE then wait then close PE — they MUST run concurrently. Always place the safety-net DB write AFTER stop(), not before. Never trust that stop()'s save succeeded when multiple monitors may be running simultaneously.

## [2026-03-17] UnboundLocalError in `_process_adjustment` causes 83% miss rate

**Root cause:** `params = session.get('params', {})` was assigned only inside the `if is_reversal:` branch (line ~3106). When a standard adjustment fires (`is_reversal=False`), `params` was never assigned. Python sees the local assignment elsewhere in the function and raises `UnboundLocalError: cannot access local variable 'params'` when line ~3175 runs `params.get('pre_sell_shift_enabled', False)`.

**Effect:** Every heartbeat that triggered a standard adjustment crashed with this error. The exception was caught at the top-level loop but NOT flagged as unrecoverable (because the str-based check looked for "nameerror" in the message string, but `UnboundLocalError`'s message is "cannot access local variable 'params'..."). The circuit breaker accumulated failures, opened, caused miss beats — resulting in 83.3% miss/error rate and Grade F heartbeat health.

**Fix:** Moved `params = session.get('params', {})` to the top of `_process_adjustment` (after `sid = self.session_id`). Removed the redundant assignment inside the reversal branch. Also fixed the unrecoverable check to use `isinstance(e, (TypeError, AttributeError, NameError, AssertionError))` instead of `str(e).lower()` — `isinstance` correctly catches subclasses like `UnboundLocalError` (which is a `NameError` subclass).

**Prevention:** Variables used after an if/else block must be assigned before it, not inside one branch. The unrecoverable check must use `isinstance`, not string matching on the error message — error messages don't contain the exception class name.

## [2026-03-17] Patience loop: cancel always failed + infinite retry on bad leg

**Root cause 1 — `AsyncDeltaClient.cancel_order()` requires `product_id` (`patience_loop.py`):**
`cancel_order_with_verification` (SEALED) calls `client.rest_client.cancel_order(order_id)` with only one argument, but `AsyncDeltaClient.cancel_order(order_id, product_id)` requires both. Every cancel attempt threw `TypeError: missing 1 required positional argument: 'product_id'`. Orders were never cancelled — each retry accumulated 2 new open orders on the exchange (10 retries × 2 orders = 20 stranded open orders).
**Fix:** Replaced `cancel_order_with_verification` with direct `await rest.cancel_order(str(oid), int(pid))` — same pattern as `MMMExecutor._cancel_order`. Added `product_id` to `_execute_single` return dict (it's present in `place_options_order` response). Changed `_cancel_orders` signature to accept order dicts with both `order_id` and `product_id`.
**Prevention:** Never use `cancel_order_with_verification` from patience code — it bypasses the unified client and calls `AsyncDeltaClient` directly with the wrong signature. Copy MMM's `_cancel_order` pattern instead.

**Root cause 2 — Persistent leg placement failure not detected (`patience_loop.py`):**
When one leg fails to PLACE with 400 Bad Request on every attempt (e.g., wrong symbol, margin issue, post-only rejection), the loop kept retrying for all 10 MAX_RETRIES. The other legs were placed and then NOT cancelled (due to bug 1 above), leaving 10 pairs of open orders on the exchange.
**Fix:** Added `placement_failures` counter per symbol. After 3 consecutive placement failures for any maker_only leg, abort the round immediately with PAUSE status.
**Prevention:** A placement failure (400 from exchange) is different from a fill failure (order open but not yet traded). Placement failures should not be retried indefinitely — they indicate a systematic problem. Market orders already aborted on failure; apply the same principle to maker orders after 3 failures.

## [2026-03-17] Production risk audit — 8 bugs fixed across engine, monitor, executor, strike shift, close-at-5, pending orders

**Bugs found and fixed (no live session was running at time of fix):**

**C1 — Frozen losses silently excluded (`calculate_standard_loss`):**
When `fetch_premium_fn` is `None` (circuit breaker active, cache cold), the frozen-positions loop was skipped entirely but `calculation_incomplete` returned `False`. Caller believed loss was fully accounted; it was not. Fixed: detect `None` + frozen positions → return `(active_loss, True)` immediately.

**H1 — Stale `_breakeven_multiplier` persists across beats (`mmm_monitor.py` Step 5.7):**
If `_regime_spot_price == 0` or the engine threw, the multiplier written in the previous beat remained in session. A stale CRITICAL (2.5×) multiplier applied silently until the engine recovered. Fixed: reset `session['_breakeven_multiplier'] = 1.0` at the start of Step 5.7 every beat before attempting the computation.

**C5 — IMP-2 dangerous-side reduction cancelled by breakeven multiplier (`calculate_lots_to_sell`):**
Breakeven (1.5×) is applied at step 3; IMP-2 reduce (0.70×) at step 5. Net: 1.05× above baseline instead of 0.70× below. IMP-2 intent ("sell fewer on dangerous side in a trend") was overridden by the aggression feature. Fixed: after IMP-2 reduce, enforce `imp2_ceiling = ceil(raw_lots × multiplier)` so the final result is always ≤ the IMP-2–intended value regardless of upstream multipliers.

**H3 — `activate_new_strike()` used `MMMInitializer()` inline with silent swallow (`mmm_strike_shift.py`):**
If the inline initializer raised (API timeout, missing creds), `log.warning` was emitted and execution continued with the wrong symbol in `side_state`. The next sell order used a wrong symbol, burning through the full 4-minute reprice loop. Fixed: use `get_initializer()` singleton; promote failure to `log.error`.

**H4 — `trigger_snapshot` not cleared on position close (`mmm_close_at_5.py`):**
When `_remove_closed_position()` closed a frozen position, its strike key remained in `trigger_snapshot`. If the same strike was later re-used, `calculate_standard_loss()` used the stale old snapshot as the baseline, making incremental loss look near-zero → under-sized hedge. Fixed: pop the strike key from `trigger_snapshot` in `_remove_closed_position()`.

**C2 — `'pending'` sentinel blocks side for 15 min on hung `smart_execute` (`mmm_pending_orders.py`):**
The pre-registration placeholder `order_id='pending'` had the same 15-minute stale TTL as real orders. If `smart_execute()` hangs (network stall, exchange timeout), the side is blind for 15 min. Fixed: added `_PENDING_SENTINEL_STALE_SECONDS = 90`; `check_and_resolve_pending()` now uses the shorter TTL for `order_id == 'pending'` entries.

**C4 — Emergency SELL with missing `average_fill_price` recorded `aggressive_price` (`mmm_executor.py`):**
When `average_fill_price` was absent in an IOC fill response, `aggressive_price` (the order floor) was silently recorded as fill. For a SELL this understates `premium_collected`, which could trigger a spurious follow-on hedge next beat. Fixed: return `_failure()` so the pending guard re-checks the order next beat and records the real fill once the exchange populates it.

**M1 — `adjustment_history` unbounded growth (`mmm_engine.py`):**
Every adjustment appended ~200 bytes to `adjustment_history`. After 1,000 adjustments the list was ~200 KB, carried in every SQLite save. Fixed: cap to last 500 entries after each append.

**Prevention rules:**
- `fetch_premium_fn` being `None` is a valid degraded state (circuit breaker). Any function that skips logic when `None` must explicitly set `calculation_incomplete=True` rather than returning a result that looks clean.
- Any session key written by a subsystem (breakeven multiplier, gamma result, regime tier) that can also fail to write must be reset to a safe default at the START of the beat, not left to accumulate from the previous beat.
- IMP-2 (reduce mode) and breakeven multiplier have opposing objectives. IMP-2 ceiling (`ceil(raw_lots × multiplier)`) must be enforced AFTER all aggression multipliers to ensure the safety reduction always wins.
- `MMMInitializer()` inline instantiation is forbidden. Always use `get_initializer()`. Failures must be `log.error`, not `log.warning`.
- `trigger_snapshot` entries for closed positions are stale baselines waiting to cause an under-sized hedge. Clear the strike key whenever `_remove_closed_position()` fires.
- Pre-registration sentinel (`order_id='pending'`) must have a shorter TTL than real order_ids. Use 90 s (reprice loop time) not the full 15-minute verification window.
- Emergency IOC fills without `average_fill_price` must defer recording, not fall back to the order limit price — conservative-looking numbers can cause real over-hedging next beat.
- `adjustment_history` and any other append-only list in session state must be pruned. Unbounded growth hits SQLite write limits and slows every heartbeat save.



## [2026-03-17] Active-lots=0 silent blind spot — close-at-5 drains active, frozen bleeds undetected

**Bug (3-part failure observed in session mmm17mar26-1):**
1. close-at-5 watcher bought back all PE active positions at 74,800 when premiums decayed to ≤$5. `active_lots` became 0, `active_strike` stayed 74,800.
2. Every subsequent heartbeat ran the trigger heal: `pe_trigger[74800] = pe_now = $485`. So `pe_excess = pe_now - pe_trigger = 0` every beat. PE never triggered even at +1307%.
3. `min_frozen_trigger_dollar` defaulted to 0.0 (disabled). The only trigger path for frozen-only losses was off. 46 frozen PE lots bled with zero algo response.
4. Manual set-active-strike (📌) promotion failed: `_save_session`'s API-inject race fix only merged new positions by ID. Active_strike field and position status (shifted→active) changes were silently overwritten by the in-flight heartbeat's save.

**Fixes applied:**
1. `_auto_promote_atm_strike` (Step 0.75): added zero-lots recovery path — when `active_lots == 0` and frozen positions exist, promotes the highest-lots frozen strike as the new active regardless of open-strike count (including the single-strike case the old code skipped).
2. `_save_session`: after the new-positions merge, checks if stored has `active_strike_pinned=True` but in-memory doesn't — if so, syncs `active_strike` + all position statuses from stored and recomputes. Manual promotion now survives in-flight heartbeat saves.
3. `min_frozen_trigger_dollar` default changed from `0.0` → `0.2`. Frozen losses > $0.20 now trigger hedging even with zero active lots, always on.

**Prevention rules:**
- `min_frozen_trigger_dollar` must be > 0 in all sessions. $0.20 is safe for any reasonable session size (1 lot × $34 entry premium = $0.034/beat at typical levels — $0.20 is ~6 lots' worth of 1-tick movement).
- Any code that changes `active_strike` must also handle what happens when active_lots drops to 0 on that side after a drain. The trigger heal creates a permanent blind spot if baseline = current.
- `_save_session`'s race fix for API-concurrent writes only covered new positions. Any API that mutates existing position state (status, strike) must be tracked similarly — check `active_strike_pinned` flag as the marker that an API explicitly changed state.

**[2026-03-18 addendum] Pin flag blocks zero-lots recovery:**
The original zero-lots recovery checked `active_strike_pinned` BEFORE checking `active_lots==0`. If the user pinned a strike (📌) and then close-at-5 drained all lots at that strike, the pin blocked recovery forever. The fix: move zero-lots recovery BEFORE the pin check, and clear `active_strike_pinned=False` when recovery fires (the pin is stale once the strike has no lots). Normal ATM-proximity promotion still respects the pin (pin check placed after the `continue` that exits zero-lots recovery).

## [2026-03-17] Trigger snapshot set to stale pre-execution premium — causes false re-triggers

**Bug:** After a successful adjustment, `_update_state_after_adjustment` called `update_trigger_snapshots(session, ce_now, pe_now, ...)`. But `ce_now`/`pe_now` were captured at heartbeat **start**, and `smart_execute` takes 30–60s. In a fast-moving market, the aggressor's premium can move significantly during execution. The stale snapshot makes the next heartbeat's trigger check compare against the old baseline, causing an immediate re-trigger if the premium moved >min_trigger_move during execution. Example: CE $100→$115 during execution, snapshot set to $100 → next heartbeat excess = 15% → fires again.

**Fix:** After `execute_adjustment` succeeds in `_process_adjustment`, re-fetch live premiums via `_fetch_premiums()` and call `update_trigger_snapshots` with fresh values. Wrapped in try/except so a failed refresh degrades gracefully to the stale snapshot.

**Prevention rule:** Any trigger snapshot update that uses `ce_now`/`pe_now` captured before a long-running async operation should be followed by a post-operation re-fetch. The strike-shift case already did this (BUG-1 FIX). Normal adjustments now follow the same pattern.

## [2026-03-17] Frozen position fetch failure → silent loss understatement during API degradation

**Bug:** `calculate_standard_loss` skips frozen positions when their premium fetch fails (`continue` on exception or None). The `calculation_incomplete=True` flag is returned, but the monitor just logs a warning and proceeds with the understated loss. During API degradation, ALL frozen position fetches can fail simultaneously, causing the hedge size to be computed from active-strike loss only — potentially missing 80%+ of total exposure.

**Fix:** When `_std_incomplete=True`, use `session['_last_complete_std_loss'][aggressor]` as a floor for the loss value. The last complete calculation is cached on every successful beat. This prevents loss from decreasing below the last-known-good value when fetches degrade.

**Prevention rule:** Any calculation that sets `incomplete=True` and the caller skips/ignores it needs a conservative fallback. "Warn and continue with understated value" is never safe for financial calculations.

## [2026-03-17] Patience: Always verify exchange symbol format from live data, not comments

**What happened:** Analysis claimed Delta Exchange uses YYMMDD format based on a comment in position_greeks.py (`C-BTC-72000-260313`). Implemented a "fix" that changed DDMMYY → YYMMDD in all symbol builders. This would have caused 100% order failure.

**What saved us:** Checked `mmm_activity_log.json` for real symbols before shipping. Found `C-BTC-75200-170326` = March 17, 2026 = DDMMYY format. Reverted immediately.

**The confusion:** `260313` (the example in comments) interpreted as YYMMDD = March 13, 2026. But real data confirms DDMMYY. The comment example may have been for a March 26, 2013 option (expired), or the comment was simply wrong about the format name.

**Prevention rules:**
- For any exchange symbol format question, **verify from live data first**: `grep -o '[CP]-BTC-[0-9]*-[0-9]*' mmm_activity_log.json | tail -5`
- Cross-check the date suffix against today's known date before implementing any format change.
- Comments can be wrong. Data doesn't lie.
- The actual Delta Exchange format: `C-BTC-STRIKE-DDMMYY` (e.g., `C-BTC-75200-170326` = March 17, 2026 call at 75200 strike)

## [2026-03-17] shift_recycle fires without capacity gate — closes winning positions, wastes fees

**Bug:** `_shift_time_recycle` had no capacity pressure check. It ran at EVERY strike shift, closing any frozen position with premium < `shift_recycle_premium_floor` (default was 60.0), regardless of whether the lot book needed the space. When market moves favorably (e.g., BTC up → PE premiums decaying), this premature close:
1. Pays broker fees for a position that would have reached `close_at_threshold` naturally
2. Leaves premium on the table: closing at 39.5 vs waiting for 10 = $0.29/lot × lots × LOT_SIZE foregone
3. The "buyback cost folded into new lot calculation" is circular — you could sell those extra lots anyway without closing the frozen position if capacity isn't constrained

**Contrast with M1 Harvest:** correctly gates on `capacity_pressure >= harvest_pressure_threshold` before running. Shift-time recycle had no equivalent gate.

**Fix:**
1. Added `shift_recycle_pressure_threshold` param (default 0.7) — recycle only runs when `total_lots/max_lots >= 0.7`
2. Lowered default `shift_recycle_premium_floor` from 60.0 → 20.0 (aligned with wind_down_close_threshold; closing at 60 when close_at_threshold=10 means 6× overshoot)

**Prevention rules:**
- Any proactive close logic must have a capacity or profit threshold gate. Closing winners "opportunistically" without need is strictly P&L-negative (fees + foregone theta).
- `shift_recycle_premium_floor` should be ≤ `wind_down_close_threshold` and ideally ≤ 2× `close_at_threshold`.
- Market direction matters: when spot moves away from frozen strikes, theta does the work for free. Don't fight it.

## [2026-03-16] shift_recycle closes logged as close_at_5 — misleading activity log

**Bug:** `close_position()` in `mmm_close_at_5.py` always logged type `'close_at_5'` regardless of the `mechanism` parameter. Shift-time recycle (`mechanism='shift_recycle'`) closes appeared as `close_at_5` in the activity log, making it look like the normal close-at-5 threshold was violated.

**Observed symptom:** User saw positions closed at 39.5 and 16.5 with `close_at_threshold = 10` in the activity log, all showing `close_at_5` type. But `shift_recycle_premium_floor = 60` — both closes were legitimate shift-time recycle (60 > 39.5 and 60 > 16.5). The `shift_recycle` summary event appeared correctly afterward but the per-position lines were wrong.

**Fix:** Changed the hardcoded `'close_at_5'` activity type to `mechanism` so each close type is correctly identified: `close_at_5`, `shift_recycle`, `harvest`, `atm_shield`, etc.

**Prevention rules:**
- `close_position()` is shared by ALL close paths. Never hardcode the activity type — always use `mechanism`.
- When investigating "algo closed above threshold": check if `shift_recycle` summary event appears immediately after the `close_at_5` entries. If it does, the closes were shift-time recycle, not threshold-based.
- `shift_recycle_premium_floor` (default 60) is completely independent of `close_at_threshold`. Shift-time recycle intentionally bypasses the normal close threshold.

## [2026-03-16] close_strike auto-promotion silently zeroes active_lots

**Bug:** When operator used `close_strike` (🔴) to close the current active strike, the auto-promotion logic filtered for `status == 'active'` to find a replacement. But all remaining open positions at other strikes have `status == 'shifted'` — so the filter always returned empty, setting `new_active = 0` and `active_strike = 0`. `recompute_side_lots` then found no active positions → `active_lots = 0`, while all frozen lots remained as `frozen_total_lots`. The side went dark: no adjustments fired, ATM shield skipped, position cap was effectively 0.

**Root cause:** Two bugs in `mmm_api.py close_strike_route` (lines ~3852–3870):
1. Candidate filter used `status == 'active'` instead of `status in ('active', 'shifted')`
2. After finding `new_active` strike, never un-shifted positions at that strike — unlike `set_active_strike` which explicitly marks them back to `'active'`

**Fix:** Changed filter to include 'shifted'. Added un-shift loop for promoted strike (mirroring `set_active_strike` lines 3615–3618).

**Prevention rules:**
- Any code that changes `active_strike` must ALSO promote positions at the new strike from 'shifted' → 'active'. `recompute_side_lots` auto-normalize only works in one direction (active→shifted), never the reverse.
- When searching for "open" positions that could serve as a new active, the filter must include BOTH `'active'` and `'shifted'` status — shifted positions are live risk, not closed.

## [2026-03-16] Frozen position double-hedging — trigger_snapshot written but never read

**Bug:** `calculate_standard_loss` in `mmm_engine.py` used `entry_premium` (lifetime loss) as baseline for frozen positions, while `update_trigger_snapshots` in `mmm_trigger.py` ratcheted frozen snapshots up after every hedge. The snapshots were dead writes — never consumed — causing every hedge cycle to re-count and re-hedge the full frozen loss from original entry.

**Root cause:** Two files had contradictory comments and logic. `mmm_trigger.py` said "incremental", `mmm_engine.py` said "lifetime". Engine won because it's the one that actually computes the loss.

**Fix:** Changed `calculate_standard_loss` to use `trigger_snapshot[frozen_strike_key]` as baseline when available, falling back to `entry_premium` only for first hedge cycle.

**Prevention rules:**
- When a function writes state that is meant to be consumed by another module, grep the codebase to verify the consumer actually reads it.
- Any loss computation for frozen positions must use incremental baseline (trigger_snapshot), not lifetime (entry_premium). The trigger system ratchets snapshots specifically to prevent double-counting.

## [2026-03-16] Wind-down partial failure skips trigger snapshot update for all strikes

**Bug:** `_process_wind_down_buyback` gated `update_trigger_snapshots` behind `if not any_failed:`. If any one strike's buyback failed, snapshots were skipped for ALL strikes — including the ones that succeeded. But session state (lots, P&L) was already mutated for successful strikes, creating a mismatch.

**Fix:** Made `update_trigger_snapshots` unconditional after the buyback loop.

**Prevention rules:**
- Never gate state sync operations (trigger snapshots, lot counts) behind an all-or-nothing flag when the preceding loop already mutates state per-iteration.
- If orders are processed per-strike, state updates must also be per-strike or unconditional.

## [2026-03-16] ATM Shield deferral checked capacity but not execution gates

**Bug:** `wind_down_on_atm` and `close_at_atm` deferred to ATM Shield based only on `shield_count < max_per_session`. But the shield's actual execution has 6 additional gates (cooldown, margin tier, status, etc.). If any gate blocked the shield, the safety features were suppressed for nothing.

**Fix:** Replaced capacity-only check with `_check_shield_gates()` call at both deferral points.

**Prevention rules:**
- When deferring a safety action to another subsystem, verify the subsystem can actually execute — not just that it has theoretical capacity.
- If subsystem X has `_check_gates()`, callers who defer to X must use the same gate check.

## [2026-03-16] MMM settings dialog 400 error — internal params filtered causing empty update

**Bug:** Settings dialog returns 400 "No valid parameters to update" even when user changed visible parameters.

**Root cause:** The frontend merged ALL params from `DEFAULT_PARAMS` (including internal ones like `close_at_use_bid`, `shift_cooldown_sec`) into `formValues`. When user saved settings, if the only changed params were internal ones (not in `PARAM_RULES`), the backend validation would skip them all, leaving no valid parameters → 400 error.

**Trigger:** Old sessions that get new default params on dialog open, or sessions where internal params differ from current defaults. If those internal params change value and are the only changes, the save fails.

**Fix #1 (Frontend — main fix):** `MMMSettingsDialog.js` line 586-596. Added filter to only send params that exist in `paramsInfo.params` (editable params). Internal params are now excluded from PATCH requests.

**Fix #2 (Backend — logging only):** `mmm_api.py` `update_session_params` endpoint. Added logging of received/validated/skipped params. Better 400 error messages showing which params were rejected and why.

**Location:**
- `webui/frontend/src/components/mmm/MMMSettingsDialog.js:586-596`
- `webui/backend/routes/mmm/mmm_api.py:1700-1729`

**Prevention rules:**
- When a UI component merges defaults into editable form state, filter out internal/system params that aren't meant to be user-editable.
- Backend validation should silently skip unknown params (already does this), but log what was skipped so 400 errors are debuggable.
- If ALL submitted params are skipped during validation, return a 400 with details showing what was submitted and why each was rejected.
- Frontend should never send params that don't exist in the backend's editable params list (`PARAM_RULES` or `paramsInfo.params`).

---

## [2026-03-16] inject-position race condition: heartbeat overwrites API-injected positions

**Bug:** `inject-position` returns 200, but the position disappears from the session within seconds. Subsequent `set-active-strike` returns 400 "No open positions". Reconciliation then reports an untracked exchange position.

**Root cause:** The monitor reloads the full session from storage at the START of each heartbeat, but then saves `self.session` (its in-memory copy) at the END. If `inject-position` saves a new position to storage while a heartbeat is in-flight (between the reload and the save), the heartbeat's save overwrites the inject. Same pattern that existed for `params` hot-reload (already fixed for params), but not for positions.

**Fix:** In `_save_session`, after re-reading params, also compare stored `positions[]` by position ID. Any position in storage that doesn't exist in the monitor's in-memory session (new IDs added by API) is merged back in before saving.

**Location:** `mmm_monitor.py` `_save_session()` — same block as params hot-reload fix.

**Prevention rules:**
- Any API endpoint that modifies `session[side]['positions']` is vulnerable to this race. The fix in `_save_session` protects inject-position and any future position-writing APIs.
- The same race applies to any session field that can be written by an API AND by the heartbeat. The pattern: re-read the stored field before saving, then merge (for add-only fields like positions) or preserve (for replace fields like params).
- When debugging a 400 from `set-active-strike`, check the backend log for the inject that preceded it — if the session has "NO record" of the exchange position, this race is the cause.

---

## [2026-03-16] DTE-aware breakeven engine: 4 implementation bugs found in code review

**Bug 1 — pnl_clamp used wrong premium denominator**
Implementation used `sum(p['entry_premium'] * p['lots'] for p in positions)` (current open positions only).
After the bot harvests some lots, the denominator shrinks dramatically. Example: session collected $1000 premium total, harvested half, current positions only have $200 premium. A normal $300 loss would show as 300/200 = 1.5× (clamp fires) when vs total it's only 0.3× (clamp should NOT fire).
**Fix:** Use `session.get('total_premium_collected', 0)` — the session-level accumulated total.
**Also:** Missing `pnl_at_spot < 0` guard — `abs()` without the negative check would fire the clamp even when position is profitable.

**Bug 2 — high_risk_mode didn't force dte_scale=1.0**
The engine only zeroed `aggression_damp` (lot boost) when `high_risk_mode=True`. But `dte_scale` stayed at 1.5 — thresholds were still wide. Operator's FOMC/CPI override was half-broken: max lots when triggered but still triggering less often than expected.
**Fix:** Add `dte_scale = 1.0` in the high_risk_active block — both threshold tightening AND max aggression.

**Bug 3 — vol_regime_damp only affected aggression_damp, not dte_scale**
Plan: vol_regime_damp should reduce dte_scale inside `_compute_dte_scale()`. Implementation: vol_regime_damp was only used to override aggression_damp in `_build_result()`. In HIGH vol, thresholds were NOT tightened — only lot aggression was changed.
**Fix:** Added vol_regime damping inside `_compute_dte_scale()`: `dte_scale = 1.0 + (dte_scale - 1.0) * (1.0 - damp)`.

**Bug 4 — `_high_risk_mode_expires_at` was never written**
Engine read `session.get('_high_risk_mode_expires_at')` for auto-expiry. Nothing in the API set it. Result: high_risk_mode stayed active forever once toggled on — no 4h auto-expiry.
**Fix:** Added setter in `mmm_api.py` `update_session_params` endpoint. When `breakeven_high_risk_mode` changes to True, sets `session['_high_risk_mode_expires_at'] = (now + 4h).isoformat()`. Clears it when toggled False.

**Prevention rules:**
- When a feature reads a session field for control logic, verify something WRITES that field. A read without a writer is dead code.
- When overriding a behavior (high_risk_mode), override ALL the dimensions it's supposed to change (dte_scale AND aggression_damp). Check the plan carefully.
- Use session-level aggregates (`total_premium_collected`) as denominators for ratio checks, not position-level aggregates. Positions change; the session total captures the full history.
- Always add `value < 0` guard before using `abs(value) / total > threshold` ratio checks. The ratio firing on the wrong sign inverts the logic.

---

## [2026-03-15] Trend T3 BLOCK locked indefinitely — stale anchor with no plateau reset path

**What went wrong:**
`_update_trend_guard` in `mmm_regime.py` has two reset paths:
1. Spot crosses back below anchor (immediate reset)
2. 30% retracement from high/low + EMA calm for N beats (gradual reset)

When the market moves up, hits T3 (≥1.5% from anchor), then **plateaus near the high**
without retracing back 30%, neither path fires. The tier-escalation-only rule (`new_tier = max(raw, current)`)
keeps it at T3 indefinitely even though the market has been calm for days.
Concrete case: anchor=$70,647, spot=$71,507 (+1.18%), T3 was set when spot was ~$71,700.
Only ~15% retracement from high — far below the 30% threshold. EMA slope = 0.2 (flat).
Result: T3 BLOCK active for 3 days on a completely calm market.

**Fix applied:**
1. Save `raw_tier` (pre-escalation) separately from `new_tier`.
2. Added plateau reset path in `else` branch of the retracement block:
   when `raw_tier < current_tier AND ema_calmed` for `trend_plateau_reset_beats` (default 20)
   consecutive beats, advance anchor to current price and reset to NORMAL.
   At 5-min heartbeat, 20 beats ≈ 100 minutes of calm → resets.

**Prevention rule:**
The trend engine must have a plateau reset path. A stale anchor + tier-escalation-only
will keep the trend locked indefinitely when the market moves up and plateaus near the high.
Always save `raw_tier` before the escalation clamp so reset checks can use the pre-clamp value.

---

## [2026-03-15] WIDE-SPREAD GUARD silently skipped close-at-5 when bid ≤ threshold but mark > threshold

**What went wrong:**
`_process_close_at_5` had a "wide-spread guard" that fetched the mark price AFTER bid-price detection.
If `bid ≤ threshold` but `mark > threshold`, the position was silently skipped and never closed.
Example: bid=$13, mark=$17, threshold=$15 → skipped indefinitely. Watcher kept triggering heartbeats
but every heartbeat skipped the position. No log line said "position blocked"; it just wasn't in closeable.

**Why it's wrong:**
Close_at_5 execution uses `use_bid_entry=True` — the order goes to the exchange at bid price.
We always pay ≤ bid ≤ threshold. The mark price is irrelevant to whether we should close.
Carrying the position is the risk; mark > threshold doesn't change that.

**Fix applied:**
Removed the wide-spread guard entirely from `_process_close_at_5` in `mmm_monitor.py`.
If bid ≤ threshold, close it. No secondary mark-price check.

**Prevention rule:**
Never gate close-at-5 on mark price when using bid-price detection. If we're willing to close
at bid, the mark price is not a blocker — it's just a reference.

---

## [2026-03-15] close-at-5 was placing orders at mid-price instead of bid

**What went wrong:**
`smart_execute` always started at mid-price. For close_at_5 buybacks (BUY orders),
mid-price is worse than bid — we pay more than necessary. The option market is illiquid;
paying mid instead of bid costs real money at scale (430 lots × $0.25 spread = $10+ extra per close).

**Fix applied:**
Added `use_bid_entry=True` parameter to `smart_execute`. When True and side=='buy',
the initial limit order is placed at `best_bid` instead of mid-price.
`close_position()` passes `use_bid_entry=(mechanism == 'close_at_5')` to smart_execute.

**Prevention rule:**
For close_at_5 buys: always start at bid. For sells (adjustments): always start at mid then bid.
Never pay mid for a buyback when we can join the bid queue.

---

## [2026-03-15] SHIFT-BEFORE-CLOSE GUARD silently blocked all close-at-5 orders

**What went wrong:**
A guard added to `_process_close_at_5` in `mmm_monitor.py` prevented close-at-5 from executing
when a position's mark premium was below `shift_threshold` AND the other side had open lots.
The rationale was "preserve hedge for a trigger-based shift". In practice, this blocked every
close-at-5 indefinitely — e.g. PE @ 71400 at $10.14 was never closed because CE had 119 lots.

**Why it's wrong:**
When a position hits `close_at_threshold`, the profit-taking decision is final. Holding it
carries unnecessary risk (the position can reverse and rise back above threshold). The shift
guard was over-engineering — if a shift fires later, it sells fresh lots at a new strike.
Closing the cheap position first is always safe.

**Fix applied:**
Removed the SHIFT-BEFORE-CLOSE GUARD entirely from `_process_close_at_5` in `mmm_monitor.py`.
Close-at-5 now executes unconditionally when premium hits threshold.

**Prevention rule:**
Never add guards to close-at-5 that defer execution based on other-side state. If premium
hits threshold, close it. No exceptions.

## [2026-03-15] Gamma Detector: wrong perp state key `perp_hedge` vs `_perp_state`

**What went wrong:**
`mmm_gamma_detector.py` line 236 used `session.get('perp_hedge', {})` to check whether
a perp hedge was included in the scan. The actual session key for perp state is `_perp_state`
(used consistently everywhere else including `mmm_breakeven_engine.py`). Result: `perp_included`
was always `False` even when a perp hedge was active.

**Fix applied:**
Changed to `session.get('_perp_state', {})` with the same `lots != 0` check.

**Prevention rule:**
The perp hedge position lives at `session['_perp_state']`, NOT `session['perp_hedge']`.
Fields: `lots`, `avg_entry`, `direction` ('long'/'short'). Always verify against
`mmm_breakeven_engine.py` `_collect_open_positions()` when accessing perp state.

---

## [2026-03-15] Gamma Detector: boundary scan starting at i=0 caused both boundaries to collapse to same kink

**What went wrong:**
`mmm_gamma_detector.py` `_run_boundary_scan()` used `range(scan_steps)` (starting at i=0)
for both the lower and upper scans. When i=0, `test_spot = spot - 0 * step = spot` and
`test_spot = spot + 0 * step = spot`. When spot was near a strike kink, both scans detected
the kink at i=0 (current spot), setting both `lower_gamma_boundary` and `upper_gamma_boundary`
to the same price (current spot). Zone and distance calculations then produced nonsense.

**Fix applied:**
Changed both loops to `range(1, scan_steps + 1)`. Lower scan starts strictly below current
spot; upper scan starts strictly above current spot.

**Prevention rule:**
Boundary scan loops that walk outward from spot must start at i=1, not i=0. Starting at i=0
evaluates the current spot in both directions, which is both logically wrong (spot can't be
simultaneously a lower and upper boundary) and produces degenerate results when spot sits
near a strike.

---

## [2026-03-15] close_at_5 caused spurious UNTRACKED_EXCHANGE_POSITION reconciliation mismatch

**What went wrong:**
Session mmm15mar26-2 showed recurring reconciliation mismatch errors after close_at_5 fired.
Two root causes:

1. **Race condition (primary):** After `close_position` successfully closes a position (fill confirmed
   by executor), `_remove_closed_position` immediately removes the position from session state.
   The exchange positions API takes 1–5 s to reflect the fill. Reconciliation runs in the very
   next heartbeat, sees the position still on the exchange but no longer in `known_strikes`,
   and raises a spurious `UNTRACKED_EXCHANGE_POSITION` warning.

2. **Partial fill (secondary):** If `smart_execute` returns `filled_size < requested_lots`,
   `_remove_closed_position` still removed the ENTIRE position from session state. Exchange
   retained the unfilled lots at that strike, causing a persistent mismatch.

**Fix applied:**
- `mmm_close_at_5.py`: `close_position` now registers every successful close in
  `session['_pending_close_verification'][symbol]` with `grace_beats=3`.
- `mmm_close_at_5.py`: `_partial_close_position` added — for partial fills the position's `lots`
  field is reduced rather than the position being marked closed entirely.
- `mmm_monitor.py` (`_reconcile_exchange_positions`): Before flagging `UNTRACKED_EXCHANGE_POSITION`,
  reconciliation checks `_pending_close_verification`. If the symbol is in the registry, the
  mismatch is suppressed and `grace_beats` decremented. Once grace runs out, a genuine stale
  position surfaces as a real mismatch. Expired entries (grace_beats ≤ 0) are purged at the
  top of each reconciliation run.

**Prevention rule:**
Any code that removes a position from session state based on an exchange order confirmation
MUST also register the symbol in `_pending_close_verification` with a 3-beat grace period.
The exchange positions API is not instantaneously consistent with order fills — never treat
fill confirmation as proof that the positions API already reflects the change.

---

## [2026-03-13] Portfolio Greeks delta/gamma were 1000× too large

**What went wrong:**
Delta showed -60.08 BTC (≈$4.3M exposure) on a portfolio with only ~2 BTC total notional. Gamma similarly inflated 1000×. Theta and Vega were correct.

**Root cause:**
Delta Exchange API returns greeks per **1 BTC of notional**. But 1 lot = 0.001 BTC, so every lot-weighted sum needs `× 0.001`. Theta and Vega already had the correction (`÷ 1000`). Delta and Gamma did not. `pnl_attribution.py` had a `CONTRACT_MULT = 0.001` that silently compensated for the wrong delta in PnL calculations — masking the bug.

**Files fixed:**
- `dashboard.py::calculate_portfolio_greeks()` — added `× 0.001` to delta, gamma, btcDelta, ethDelta (UNSEALED v1→v2, re-sealed)
- `test_sealed_calculate_portfolio_greeks.py` — updated expected values (e.g. `-5.0` → `-0.005`)
- `OptionsPanel.js::aggregatedGreeks` — same `× 0.001` fix
- `OptionsPanel.js::calculateSmartScaling` — same fix
- `pnl_attribution.py` — removed `CONTRACT_MULT` (was compensating for the bug; would double-apply after fix)

**Prevention rule:**
When writing any greek aggregation: delta per lot = `api_delta × lot_size (0.001)`. Theta and Vega on Delta Exchange are already in USD-per-day scaled to lot size (their internal unit requires ÷1000, same thing). If a downstream function applies a multiplier to "fix" greeks, that's a red flag — the source is wrong.

---

## [2026-03-13] Live bid/ask WebSocket — wrong field names + wrong channel

**What went wrong:**
Options bid/ask prices in the UI were only refreshing every 20+ seconds. The full WebSocket pipeline (Delta Exchange → subprocess → SocketIO → frontend) was already built and correctly wired, but bid/ask values were always emitting as `0`.

**Root causes (3 bugs):**
1. `_ws_subprocess_worker.py` extracted `best_bid_price` / `best_ask_price` from the `v2/ticker` message — fields that don't exist. Actual fields are nested: `data['quotes']['best_bid']` / `data['quotes']['best_ask']`. Every ticker emit carried `best_bid=0, best_ask=0`.
2. `v2/ticker` channel only pushes on significant price change — quiet options can go 20+ seconds without an update. Wrong channel for real-time bid/ask.
3. `read_commands()` in the worker: if a `subscribe` command arrived before WS connected (`ws_ref[0]` was None), the whole block was skipped including `subscribed_options.update()` — symbols were lost and never re-subscribed on reconnect.

**Fixes applied:**
- Switched channel from `v2/ticker` to `l1_orderbook` with category subscriptions (`"call_options"`, `"put_options"`) — pushes every ~500ms on quote change, no per-symbol tracking needed.
- Fixed field extraction: `quotes = data.get('quotes', {}); float(quotes.get('best_bid', 0))`.
- Removed `ping_interval=30` from `run_forever()` — was causing `kqueue` crashes on macOS (websocket-client bug).
- Added `enable_heartbeat` + 35s watchdog thread to detect and recover from stale connections.
- Added REST polling broadcaster in `app.py` (every 3s) as fallback for symbols with no quote changes.

**Prevention rule:**
When reading Delta Exchange WS message fields, always test the actual message structure first (`python3 -c "import websocket..."`) — field names differ between REST (`/v2/tickers`) and WS (`v2/ticker`) responses. For options bid/ask specifically: REST response has `quotes.best_bid`; WS `l1_orderbook` has top-level `best_bid`. Use `l1_orderbook` with category names for options — never `v2/ticker` (too slow) and never `l1ob` (forbidden for options).

---

## [2026-03-13] ATM Shield fired 6 times but never closed — `KeyError: 'side'` (CRITICAL)

**What went wrong:**
Session mmm15mar26-1: BTC spot moved from $72,048 → $72,506, approaching and then breaching CE active strike 72400. ATM Shield correctly detected the danger and fired 6 times between 14:07–16:21, but EVERY firing failed with `KeyError: 'side'` at `close_position()`. No positions were closed, no retreat happened. Worse, because ATM Shield was enabled with remaining capacity, both `close_at_atm` and `wind_down_on_atm` were **deferred** to the shield — the new safety system suppressed the old fallbacks but couldn't do its own job.

**Root causes (2 bugs):**
1. `close_position()` in `mmm_close_at_5.py` does `side = position['side']` — requires position dicts to carry a `'side'` key. The unified position ledger (session[side]['positions']) never stores `'side'` on individual positions — side is implicit from the parent dict. All other callers (close_at_5 scan, harvester, recycler, shift-recycle) build NEW dicts with `'side'` included. ATM Shield was the only caller passing raw ledger dicts.
2. `pos_id = position.get('_pos_id')` — ledger positions use key `'id'`, not `'_pos_id'`. Even if the side bug were fixed, the ID-based position removal would have failed, falling through to unreliable content-match.

**Fixes applied:**
- `close_position()` now accepts an explicit `side` parameter (keyword arg, default None). Falls back to `position.get('side')` for backward compat. Errors gracefully if neither is available.
- `pos_id` extraction now uses `position.get('_pos_id') or position.get('id')` to handle both constructed dicts and raw ledger positions.
- ATM shield caller passes `side=endangered_side` explicitly.

**Prevention rule:**
When any new code path calls `close_position()` with raw ledger positions (from `session[side]['positions']`), it MUST pass `side=` explicitly. The ledger position schema does NOT include 'side' — it's always derived from the parent. Any new function receiving position dicts should use explicit parameters for context that's implicit in the data structure.

---

## [2026-03-12] Proactive Shift + Shift-Time Recycle cascade wiped PE then CE (CRITICAL)

**What went wrong:**
PE premium dropped to $46.85 (below shift_threshold $50). Proactive shift triggered, froze 167 PE lots, then shift_time_recycle bought back ALL 177 frozen lots via 9 serial BUY orders over 5+ minutes. Heartbeat was blocked the entire time. Watchdog killed the session at 450s timeout, but exchange orders already placed kept filling. The restarted monitor's reconciliation auto-corrected state from the mid-settlement exchange view (session=52 → 2 PE lots). PE went to 0, CE still had 126 → ONE-SIDE CLOSE. User manually restored PE positions, but the EXACT SAME cascade happened again 45 minutes later, wiping PE a second time. Then CE also went to 0.

**Root causes (5 bugs):**
1. Proactive shift runs at Step 1.5, BEFORE safety checks at Step 3 — bypasses lot_velocity, asymmetry, margin tier, regime blocks
2. `_shift_time_recycle()` has no MAX_CLOSES_PER_HEARTBEAT cap (close_at_5 has one, shift_recycle doesn't)
3. Serial BUY orders block heartbeat for >5 minutes — exceeds watchdog timeout
4. Watchdog restarts immediately — reconciliation runs against mid-settlement exchange state
5. Delta-neutral matching inflated lots from 81→126 (uncapped), amplifying the cascade

**Fixes applied:**
- A1: Moved proactive shift to Step 5.6 (after safety/regime/cooldown checks), gated behind `_skip_to_pnl`
- A2: Added `shift_recycle_max_per_beat` param (default 10) to cap lots closed per heartbeat
- A3: Added `guardian_max_beat_sec` wall-clock deadline (default 120s) checked inside recycle loop
- A4: Added 30s settlement delay in watchdog before restarting monitor
- A5: Added `shift_match_max_inflate_mult` (default 1.5) to cap delta-neutral inflation
- Created MMMGuardian (heartbeat-level integrity monitor) with 4 invariant checks: G1 hedge integrity, G2 per-beat lot velocity, G3 side balance wipeout detection, G4 beat duration guard
- Consolidated hedge integrity guard from 3 locations (close_position inline, wind_down_buyback inline, observer CHECK 1) into MMMGuardian G1

**Post-fix audit (March 13):** Found guardian G2/G3 were dead code — `guardian.record_close()` was never called (only `observer.record_close()`), and `close_position()` created throwaway `MMMGuardian()` instances instead of using the monitor's real guardian. Fixed by:
- Made guardian a per-session registry (`get_guardian(session_id)` / `register_guardian()` / `deregister_guardian()`)
- `close_position()` now looks up the real guardian and calls `record_close()` after every successful close
- Integrated G2 velocity check directly into `check_close_allowed()` (preventive, not just post-beat)
- Shift_recycle loop breaks on guardian block (was `continue`)
- Added `_should_stop()` check in shift_recycle loop (orders kept placing after watchdog kill)
- Changed mechanism from `'close_at_5'` to `'shift_recycle'` with proper observer price check

**Prevention rule:** Every code path that places exchange BUY orders MUST be gated behind safety checks AND have a per-beat lot cap. Every close mechanism MUST use its own mechanism label (never masquerade as another). The guardian registry (`get_guardian`) is the single source of truth for per-beat tracking — never create standalone MMMGuardian instances for tracking purposes.

---

## [2026-03-10] One-sided exposure after CE fully closed via close-at-5

**What went wrong:**
When all CE positions fell to ≤close_at_threshold (market moved making calls worthless), `_process_close_at_5` closed them all. The code at that point just logged "For now, just log. Full auto-re-entry needs user config." — the session kept running with CE=0 and PE still open. This is a strategy violation: the two sides are meant to offset each other, and running single-sided leaves unlimited loss exposure on the open side.

**Root cause (detection):**
Incomplete feature in `mmm_monitor.py` — the `_process_close_at_5` inner check (`check_side_fully_closed`) had no action, only a log. No pause or alert was triggered.

**Fix applied (detection/reactive):**
Added ONE-SIDE CLOSE GUARD in `mmm_monitor.py` `_heartbeat()`, right after `check_both_sides_closed`. When one side is fully closed but the other has open lots, the session is immediately PAUSED with a critical safety alert.

---

## [2026-03-10] CE positions closed at premium ~38-41 instead of triggering a strike shift (SHIFT-GUARD fix)

**What went wrong:**
In today's session (mmm10mar26-3): CE @ 71200 had premium 38-41 (below shift_threshold=50). During a 30-minute window where PE was slowly rising but not yet hitting its trigger, close-at-5 fired and closed ALL 17 CE lots at 38-41. This left PE open with zero CE hedge. When PE later triggered, there was no CE to shift/sell. PE was closed at 151.5 vs entry 67.5 — a significant loss.

**Root cause:**
`close_at_5` runs unconditionally every heartbeat using bid price, BEFORE trigger evaluation. When CE bid fell below `close_at_threshold` (user had set it higher than default $5 to take profits at ~$40 range), close-at-5 fired. BUT: CE mark price was still slightly above/near shift_threshold ($50). If PE had triggered even once more, `check_shift_needed(ce, mark=42)` → 42 < 50 → SHIFT would have fired, moving CE to a new OTM strike with better premium and keeping both sides hedged.

**The strategy violation:**
Close-at-5 takes profit on the cheap/winning side without checking whether the expensive/losing side still needs coverage. The shift mechanism (which would maintain coverage) only fires on PE trigger, not proactively.

**Fix applied (preventive):**
Added SHIFT-BEFORE-CLOSE GUARD in `_process_close_at_5()` in `mmm_monitor.py`. Before closing any ACTIVE position (original, adjustment, strike_shift type): check if mark premium < shift_threshold AND the other side still has open lots. If so, SKIP this close and log — the position is preserved for the trigger-based shift mechanism.

Does NOT apply to:
- `frozen` type positions (already shifted away, independent risk)
- Wind-down mode (`using_elevated=True`) — let wind-down do its own cleanup

**Prevention rule:**
Whenever close-at-5 would fire on a side below shift_threshold AND the other side is open, the shift mechanism should get priority. The SHIFT-BEFORE-CLOSE guard enforces this. This preserves CE positions as "alive but cheap" so that the next PE trigger produces a proper CE shift rather than leaving CE at zero.

---

## [2026-03-10] MMM Heartbeat Fails 100% — asyncio/eventlet Event Loop Conflict

**Symptom:** Every heartbeat fails. Miss rate 100%. Circuit breaker permanently OPEN. All premiums show "–" in UI. Error in logs: `Heartbeat error: Cannot run the event loop while another loop is running`.

**Root cause:**
`gunicorn_config.py` uses `worker_class = "eventlet"`. Eventlet monkey-patches `threading.Thread` into a greenlet. `MMMMonitor._run_loop()` creates `asyncio.new_event_loop()` and calls `self._loop.run_until_complete(self._heartbeat())`. Inside a greenlet (not a real OS thread), asyncio cannot take over execution because eventlet's hub is already running in that greenlet context.

**Fix applied (mmm_monitor.py `start()` method):**
Use `eventlet.patcher.original('threading').Thread` to get the un-monkey-patched Thread class, creating a real OS thread where asyncio works without conflicts.

```python
try:
    from eventlet.patcher import original as _ep_original
    _RealThread = _ep_original('threading').Thread
except (ImportError, AttributeError):
    _RealThread = threading.Thread
self._thread = _RealThread(target=self._run_loop, name=f"mmm-monitor-{self.session_id}", daemon=True)
```

**Prevention rule:**
When gunicorn uses `worker_class=eventlet`, any background thread that runs `asyncio.run_until_complete()` MUST use `eventlet.patcher.original('threading').Thread`. The monkey-patched `threading.Thread` creates a greenlet, not a real OS thread, causing asyncio conflicts. `_socketio.emit()` from a real OS thread is safe with Flask-SocketIO in eventlet mode.

---

## [2026-03-11] MMM Lot Velocity Limit Too Restrictive

**Symptom:** "LOT VELOCITY LIMIT: 12 lots sold in last 30min (limit: 10)" — algo blocked from trading with max_lots_per_side=100.
**Root cause:** Default `lot_velocity_limit=10` in mmm_state.py was too low. A single strike_shift selling 12 lots instantly exceeded it. Also, `lot_velocity_limit` was missing from `PARAM_RULES` in mmm_config.py, so it couldn't be updated via API.
**Fix:** Changed default to 30. Added `lot_velocity_enabled`, `lot_velocity_limit`, `lot_velocity_window_mins` to PARAM_RULES.
**Prevention rule:** Any new safety parameter added to DEFAULT_PARAMS/HOT_RELOAD_PARAMS MUST also be added to PARAM_RULES, or it becomes un-configurable via the API.

---

## [2026-03-11] Whipsaw False Positive from OPERATOR Injections

**Symptom:** Session auto-pauses with "Whipsaw detected: 3 alternating adjustments" when the last adjustments include operator-injected manual positions.
**Root cause:** Operator manual adjustments (aggressor=OPERATOR) were counted in whipsaw detection alongside algo adjustments. T3-3 pre-filter boosted the consecutive counter, lowering the effective whipsaw limit from 3 to 2. With effective limit 2, OPERATOR→PE appeared "alternating" → false positive.
**Fix:** (1) mmm_safety.py: Filter OPERATOR from history before whipsaw alternation check. (2) mmm_monitor.py: Skip T3-3 pre-filter increment when either aggressor is OPERATOR. (3) mmm_api.py: Resume endpoint clears whipsaw state on both storage AND live monitor session.
**Prevention rule:** Safety detectors that analyze adjustment patterns MUST exclude OPERATOR (manual) entries. Manual rebalancing is not algo whipsaw.

---

## [2026-03-11] Backend Crash from Zombie Gunicorn Processes

**Symptom:** Backend at 97% CPU, health endpoint times out, `launchctl list` shows LastExitStatus=9 (SIGKILL). Multiple PIDs on port 5555. Error: `greenlet.error: Cannot switch to a different thread`.
**Root cause:** Rapid `launchctl stop/start` cycles don't always kill old gunicorn workers. Old zombie workers hold port 5555 resources, and concurrent eventlet hubs from different processes cause cross-thread greenlet switching errors that crash the hub.
**Fix:** Kill all processes on port 5555 (`lsof -ti:5555 | xargs kill -9`) before restarting. Also: don't add `log.warning()` calls at the very start of real OS threads — they fire before the asyncio event loop exists and can trigger eventlet lock contention.
**Prevention rule:** Before restarting the backend, always kill ALL processes on port 5555 first. Use: `lsof -ti:5555 | xargs kill -9; sleep 1; launchctl start com.gridbot.production.webui`.

---

## [2026-03-11] heartbeat_count API Shows 0 — Wrong Attribute Name

**Symptom:** Monitor API endpoint reports `heartbeat_count: 0` even when heartbeats are running.
**Root cause:** API used `getattr(monitor, '_heartbeat_count', 0)` but the actual counter is `session['_heartbeat_counter']` (stored in session dict, not as monitor attribute).
**Fix:** Changed to `monitor.session.get('_heartbeat_counter', 0)` in mmm_api.py.
**Prevention rule:** When reading session-specific counters in API endpoints, check whether the value lives in `monitor.session[...]` vs `monitor._attribute`. Session dict is the source of truth for heartbeat state.

## [2026-03-12] Comprehensive MMM Code Audit — 37 Bugs Found Across 8 Modules

**Scope:** Deep audit of mmm_engine, mmm_trigger, mmm_safety, mmm_close_at_5, mmm_strike_shift, mmm_state, mmm_harvester, mmm_monitor.

**Critical bugs fixed (HIGH severity):**
1. **Engine:** `calculate_standard_loss` trigger defaults to 0 → massive over-hedge. Fix: Early return with incomplete=True when trigger≤0.
2. **Engine:** `reconcile_pnl` formula missing fee subtraction → reconciliation never detects real drift. Fix: `tracked = realized + unrealized - fees`.
3. **Engine:** `calculate_lots_to_sell` forces min 1 lot even when loss=0. Fix: Early return if loss_to_cover≤0.
4. **Trigger:** Frozen loop overwrites active trigger snapshot with 0 (cache miss). Fix: Skip frozen strikes that match active strike + validate return values.
5. **Trigger:** `evaluate_triggers` has no defense against 0-value snapshot → false triggers. Fix: Return NONE when trigger≤0.
6. **Safety:** `max_loss_amount ≤ 0` triggers instant auto-close. Fix: Early return if max_loss≤0.
7. **Safety:** Whipsaw infinite pause loop (counter never reset, re-triggers on same history). Fix: Reset counter + record checked_up_to.
8. **Safety:** Peak PnL decay at 10%/heartbeat nullifies trailing stop in <2 min. Fix: Time-based decay with 15-min half-life.
9. **Safety:** Lot velocity counts OPERATOR lots, blocking algo hedging for 30min. Fix: Skip OPERATOR entries.
10. **Close-at-5:** Fallback original removal reverted by recompute_side_lots. Fix: Also mark position in positions[].
11. **Strike shift:** Dynamic threshold collapses after first shift (original_premium→0). Fix: Persistent `_initial_hedge_premium`.
12. **Monitor:** `_interruptible_sleep` doesn't exist → storage failure kills session permanently. Fix: Use `_wait_for_next_cycle`.
13. **Monitor:** resume() doesn't clear stale margin flags → false wind-down after resume. Fix: Pop margin flags.
14. **Monitor:** `_make_fetch_fn` returns 0 on cache miss → hides losses. Fix: Return None.
15. **Monitor:** `_bid_cache` accumulates stale entries across heartbeats. Fix: Fresh dict each beat.
16. **State:** Bare dict access `orig_pos['lots']` → KeyError crash on corrupted data. Fix: `.get('lots', 0)`.
17. **Harvester:** `other_lots==0` disables M3 boost in worst-case (one-sided accumulation). Fix: Enable extreme boost.

**Prevention rules:**
- Always use `.get()` with defaults — never bare dict access in state management code
- Cache miss must return None/sentinel, never 0 (0 is a valid value that hides errors)
- Safety checks must handle misconfigured thresholds (≤0) gracefully
- Any counter used for re-trigger detection must be reset when the trigger fires
- Derived state fields (original_premium) that get zeroed by recompute need persistent backups (_initial_hedge_premium)

### Round 2 Audit Fixes (2026-03-11) — 15 bugs across 6 files

**close_at_5.py (5 fixes):**
18. Profit calc in scan missing `× LOT_SIZE_BTC` → 1000x inflated sort priority. Fix: Add multiplier at all 3 scan locations.
19. `_being_closed` guard only worked for pos_id path → adjustment/frozen positions could double-buyback. Fix: Content-match guard + propagate flag through recompute views.
20. No double-close guard when pos_id is falsy (pre-migration). Fix: Content-match on adjustment_fills/frozen_positions views.
21. External close records `realized_pnl: 0.0` → PnL drift. Fix: Estimate from entry_premium - current_premium.
22. None premium from fetch could trigger comparison crash. Fix: Guard `if current is None: continue` in adj/frozen scan loops.

**mmm_state.py (3 fixes):**
23. `recompute_side_lots` uses `next()` for original — silently drops lots from 2nd+ original. Fix: Sum all active originals + warning log.
24. `_being_closed` flag not propagated to adjustment_fills/frozen_positions views. Fix: Include in view dict comprehensions.
25. `close_at_use_bid` missing from HOT_RELOAD_PARAMS. Fix: Add to set.

**mmm_strike_shift.py (3 fixes):**
26. `freeze_current_positions` doesn't clear old strike's trigger_snapshot → stale data on shift-back. Fix: Pop old key.
27. `find_new_strike` allows shift-back to frozen strike → duplicate positions. Fix: Skip frozen strikes in candidate filter.
28. Missing `frozen_entry` in freeze return dict (promised by docstring). Fix: Compute lot-weighted avg premium.

**mmm_safety.py (1 fix):**
29. perp_pnl missing from 80% warning details (was only in CRITICAL). Fix: Add to alert-level details dict.

**mmm_harvester.py (2 fixes):**
30. `total_lots` used for asymmetry calc inflated by frozen. Fix: Use `active_lots`.
31. Capacity pressure includes frozen lots. Fix: Use `active_lots` for pressure calculation.

**mmm_monitor.py (1 fix):**
32. No re-entrancy guard on `_heartbeat()` — overlapping heartbeats possible. Fix: Boolean flag + wrapper/inner split.

**Prevention rules (added):**
- Scan profit calculations must match actual execution formula (both need `× LOT_SIZE_BTC`)
- In-flight guards (`_being_closed`) must work on ALL position types, not just ID-based paths
- View dicts rebuilt by recompute must propagate ALL transient flags from source positions[]
- HOT_RELOAD_PARAMS must be updated when adding new runtime-tunable params
- Strike shift must check frozen strikes to prevent duplicate positions at same strike
- Active-vs-total lot distinction matters: asymmetry/capacity should use active_lots only

---

## [2026-03-11] OPTIONS Positions Endpoint Freezes Single Eventlet Worker — Session Creation Blocked

**Symptom:** User clicks "+ New Session" — nothing happens. Globe stays green (WebSocket alive) but all HTTP requests (health check, session creation, everything) time out for 12-15 seconds every ~13s. Logs show repeated `"Failed to fetch options positions: "` (empty exception = `concurrent.futures.TimeoutError`) alternating with `"Failed to get positions from API: Read timed out (10s)"`.

**Root cause:**
`options_client.py` `_run_async()` called `asyncio.run_coroutine_threadsafe(coro, loop)` then `future.result(timeout=60)`. With `gunicorn worker_class=eventlet`, the Flask request handler is an eventlet greenlet. `future.result(timeout=60)` uses `threading.Condition.wait()` (eventlet-patched). The patched wait is supposed to yield, but `concurrent.futures.Future` synchronization does NOT properly cooperate with eventlet's hub — the greenlet FREEZES for the full duration of the async API call (12-15 seconds). With `workers=1`, the ENTIRE backend becomes unresponsive for that duration. New session creation requests queue up and time out silently.

Secondary problem: `_get_dedicated_loop()` used `threading.Thread` (monkey-patched → eventlet greenlet) to host the asyncio event loop. An asyncio loop running inside an eventlet greenlet has I/O selector conflicts that can cause the loop to stall under load.

**Fix applied (options_client.py):**

1. `_get_dedicated_loop()` — use a **real OS thread** for the asyncio loop:
```python
from eventlet.patcher import original as _orig
_RealThread = _orig('threading').Thread
_loop_thread = _RealThread(target=_dedicated_loop.run_forever, daemon=True, ...)
```

2. `_run_async()` — replace blocking `future.result()` with **cooperative polling**:
```python
future = asyncio.run_coroutine_threadsafe(coro, loop)
deadline = time.time() + 60
while not future.done():
    if time.time() >= deadline:
        future.cancel()
        raise TimeoutError("Async operation timed out after 60s")
    eventlet.sleep(0)   # yield to hub each iteration
return future.result(timeout=0)  # already done — returns immediately
```
`eventlet.sleep(0)` yields the greenlet on every iteration, allowing the eventlet hub to serve health checks, session creation, and WebSocket heartbeats while the async API call is in flight. Because the asyncio loop IS in a real OS thread, `future.done()` becomes True when the coroutine completes, and the poll loop exits naturally.

3. `options_control.py` — added one-at-a-time fetch lock (`_positions_fetch_lock`) with double-checked caching to prevent thundering herd when cache expires:
```python
# Fast path (no lock)
if cache is fresh: return cached_data
# Slow path — serialize all concurrent cache-miss requests
with _positions_fetch_lock:
    if cache is now fresh (another greenlet fetched): return cached_data
    options = _run_async(fetch())  # only ONE call in flight at a time
```

**Verified:** After fix, `health: OK in 0.05s` and `sessions: OK in 0.04s` while `positions` live-fetches from Delta Exchange (`OK in 1.08s`). Previously those would time out for 12-15 seconds.

**Prevention rule:**
NEVER call `future.result()` (blocking) from an eventlet greenlet — even with eventlet's monkey-patched `threading.Condition`, cross-thread notification between a real OS thread (asyncio loop) and a greenlet (Flask request handler) does NOT propagate correctly. Always use `eventlet.sleep(0)` polling OR run the entire async operation in the real OS thread used by the dedicated asyncio event loop.

---

## [2026-03-11] Watchdog restart race condition — orphaned exchange positions

**What went wrong:**
PE showed 0 lots in MMM but exchange had 38 PE lots at strike 69600. During a watchdog restart at 09:49, the old monitor was mid-way through a PE strike shift (69400→69600). The watchdog called `stop()` (setting `_save_disabled=True`), then spawned a new monitor from persisted storage. But the old monitor's async `_process_strike_shift` completed AFTER `stop()` — the order was placed on exchange (38 lots PE at 69600), `activate_new_strike()` updated in-memory state, but `_save_my_session()` was blocked by `_save_disabled`. The new monitor loaded the pre-shift state from storage (PE at 69400) and never knew about the PE at 69600.

**Root cause (two cascading bugs):**
1. **No pre-order guard in `_process_strike_shift`**: Exchange-mutating operations (sell orders) executed even after `stop()` set `_running=False` and `_save_disabled=True`. The async operation was already in flight and couldn't be cancelled by the flag check.
2. **Reconciliation blind spot**: `_reconcile_exchange_positions()` builds `session_symbols` only from known strikes. P-BTC-69600 wasn't in `session_symbols` because the session didn't know about 69600. The isolation filter `if symbol not in session_symbols: continue` excluded the orphan completely. The "UNTRACKED_EXCHANGE_POSITION" detection (which iterates `exchange_positions`) was effectively dead code — it could only find positions already in the filtered `exchange_positions` dict, which by definition are already at known strikes.

**Fixes applied:**
1. **Guard in `_process_strike_shift`** (`mmm_monitor.py`): Before placing the sell order, check `if not self._running or session.get('_save_disabled')` → abort the shift and unfreeze positions. Prevents orphaned exchange orders.
2. **Broader orphan scan in reconciliation** (`mmm_monitor.py`): Instead of iterating the pre-filtered `exchange_positions`, iterate ALL raw exchange `positions` matching this session's option type prefix and expiry suffix. When untracked positions are found (not owned by other sessions), auto-adopt them into the session with `type='orphan_adopted'`. This recovers from crashed monitors' in-flight shifts.

**Prevention rule:**
Any code that modifies exchange state (placing/cancelling orders) MUST check `self._running` and `_save_disabled` immediately before the exchange call. If the monitor has been stopped, abort and unfreeze — the new monitor will detect the condition and retry. Reconciliation must scan ALL exchange positions matching the session's expiry, not just those at known strikes.

---

## [2026-03-11] WebUI performance regression — eventlet worker blocking & CPU spin

**What went wrong:**
WebUI became completely unresponsive. `/api/health` took 6.7s (should be 2ms). `/api/options/positions` timed out entirely (0 bytes in 8s). All endpoints were slow because requests queued behind a blocked worker.

**Root causes:**
1. **`_run_async()` 90-second timeout**: In `options_client.py`, the cooperative polling loop waited up to 90s for exchange API responses. During this time, it held `_positions_fetch_lock`, blocking all other position requests.
2. **CPU spin from `eventlet.sleep(0)`**: The polling loop called `_yield(0)` (yield immediately) millions of times per second, consuming 94% CPU even while waiting for a response.
3. **HTTP self-referencing calls**: `sl_tp_monitor`, `take_profit_manager`, and `max_loss_manager` all made internal HTTP requests to `http://localhost:5555/api/options/positions`. With a single eventlet worker, these self-calls competed with the same worker already handling the request — causing cascading timeouts and potential deadlocks.

**Fixes applied:**
1. **Reduced `_run_async` timeout** (`options_client.py`): 90s → 20s, made configurable via parameter.
2. **Added 10ms sleep** (`options_client.py`): `_yield(0)` → `_yield(0.01)`. CPU dropped from 94% → 0.2%.
3. **Created `get_cached_positions()` helper** (`options_control.py`): Returns cached positions directly for background monitors — zero network overhead, zero deadlock risk.
4. **Eliminated HTTP self-calls**: `sl_tp_monitor`, `take_profit_manager`, `max_loss_manager` now use `get_cached_positions(max_age=30)` instead of `requests.get("http://localhost:5555/api/options/positions")`.

**Prevention rule:**
Background monitors must NEVER make HTTP requests to localhost:5555 — use shared cache or direct function calls instead. Polling loops with `eventlet.sleep()` should always use a nonzero sleep (≥10ms) to prevent CPU spin.

---

## [2026-03-11] Heartbeat crash: `pressure_threshold` referenced before assignment

**What went wrong:**
Every heartbeat for session mmm11mar26-2 crashed with `UnboundLocalError: local variable 'pressure_threshold' referenced before assignment` in `mmm_harvester.py`. This prevented reconciliation state from being saved, and prevented the orphan adoption from persisting.

**Root cause:**
In `_compute_asymmetry_overrides()` (mmm_harvester.py), when `other_lots == 0` (the PE side had 0 lots), the code branched to an early-return path at line 64 that used `pressure_threshold` — but this variable was only defined at line 78, AFTER the `if other_lots == 0` block.

**Fix applied:**
Moved `pressure_threshold`, `asym_threshold`, and `base_profit_pct` definitions to BEFORE the `if other_lots == 0` check.

**Prevention rule:**
When adding early-return branches, verify all referenced variables are defined before the branch point. Python does not hoist variable declarations.

---

## [2026-03-11] Orphan scan expiry suffix mismatch (ddmmyyyy vs ddmmyy)

**What went wrong:**
The orphan scan in `_reconcile_exchange_positions()` used `expiry_suffix = f'-{expiry}'` where `expiry` was in ddmmyyyy format (e.g., `11032026`). But Delta Exchange symbols use ddmmyy suffix (e.g., `110326`). The `sym.endswith('-11032026')` check failed for every symbol (`P-BTC-69600-110326`), so ALL orphan candidates were silently filtered out and never adopted.

**Fix applied:**
Added `from .mmm_initializer import expiry_to_symbol_suffix` and converted: `sym_expiry = expiry_to_symbol_suffix(expiry)` → produces `110326` from `11032026`.

**Prevention rule:**
When building or comparing symbol strings, always use `expiry_to_symbol_suffix()` to convert ddmmyyyy → ddmmyy. The session stores ddmmyyyy; symbols use ddmmyy. Never use the raw expiry parameter directly in symbol comparisons.

---

## [2026-03-12] Orphan adopted positions had entry_premium=0

**What went wrong:**
The orphan adoption code in `_reconcile_exchange_positions()` (~line 5487) hardcoded `'entry_premium': 0, 'premium': 0` when auto-adopting positions discovered on the exchange during reconciliation. This made loss calculations treat the entire current premium as loss, broke close-at-5 profit% checks, and corrupted trigger snapshots.

**Fix applied:**
1. Changed orphan adoption to use `float(pos.get('entry_price', 0))` from the exchange position object (the average entry price the exchange reports).
2. Added §26.9b self-heal block: each reconciliation cycle, scans all active positions for `entry_premium=0`, looks up the exchange `entry_price`, and patches them.

**Prevention rule:**
When creating position records from exchange data, always populate `entry_premium` from the exchange's `entry_price` field. Never hardcode financial values to 0 — use the exchange as source of truth.

---

## [2026-03-12] wind_down_on_atm and close_at_atm checked original_strike, not active_strike

**What went wrong:**
Both `wind_down_on_atm` and `close_at_atm` proximity checks used `original_strike`
(the session's initial entry strike — set at first sell, never updated on shifts).
After 6 strike shifts the original CE strike was 71,800 and PE was 66,400 — both
3-4% from spot (~69,234). The active strikes (CE=69,600, PE=69,400) were ATM/ITM
but the checks were blind to them. Wind-down never fired. User had to manually pause.

**Fix applied:**
Changed all 3 ATM-proximity checks in `mmm_monitor.py` to use `active_strike` +
`active_lots > 0` guard (instead of `original_strike` + `total_lots > 0`):
1. `wind_down_on_atm` block
2. `close_at_atm` block
3. `perp_hedge atm_only` gate

**Prevention rule:**
Any code that checks whether the market has approached our position MUST use
`active_strike` (current exposure), not `original_strike` (historical entry,
irrelevant after shifts). The `original_strike` field exists only for P&L
attribution — it has no role in proximity/safety checks.

### 2026-03-12: SL/TP set_sl_tp() UnboundLocalError
**Bug:** `manager` variable used before `manager = get_sl_tp_manager()` assignment in `set_sl_tp()`.
Previous AI moved the `manager = get_sl_tp_manager()` line BELOW the `manager.get_sl_tp(symbol)` call when adding tp_order_id lookup logic.
**Prevention:** When reordering code to add a "read before write" pattern, always ensure the variable is initialized first. Run the endpoint manually after refactoring.

### 2026-03-12: AUTO-ADOPT orphan positions catastrophic bug
**Bug:** `_reconcile_exchange_positions()` had an AUTO-ADOPT feature that adopted exchange positions at unknown strikes as "orphan_adopted" positions. Combined with `_get_other_sessions_lots_at_symbol()` only checking RUNNING monitors (ignoring stopped/idle sessions from storage), it caused a new session to adopt ALL exchange positions from previous stopped sessions, manual trades, and other algos.
**Impact:** Session mmm13mar26-2 adopted 8 extra lots per side within 6 minutes of starting. A subsequent strike shift placed REAL 18-lot orders (instead of correct 10) because the inflated lot count was used.
**Fix:**
1. Disabled AUTO-ADOPT entirely — sessions must NEVER claim positions they didn't create. UNTRACKED positions are now logged as warnings only.
2. Fixed `_get_other_sessions_lots_at_symbol()` to check ALL sessions from storage (stopped/idle/historical), not just running monitors.
3. Added one-time cleanup to close all `orphan_adopted` positions in existing sessions.
**Prevention:** Never auto-add exchange positions to a session. Only auto-REMOVE phantom positions (session > exchange). A session should only track positions it explicitly created via sell orders.

## [2026-03-12] Asymmetry 7:1 hard block wrongly blocked ALL sells including the light side

**What went wrong:**
When CE=126 lots and PE=2 lots (ratio 63:1), the asymmetry hard block fired `action: 'stop_adjustments'` which set `_skip_to_pnl = True` in the monitor. This skipped ALL trigger evaluation — including PE sells. But PE sells would REDUCE the asymmetry. Only CE sells should be blocked when CE is the heavy side.

The Safety panel displayed: "ASYMMETRY HARD BLOCK: CE=126, PE=2 — all new sells blocked" which was factually wrong. The user saw orders blocked and correctly identified this as a bug.

**Root cause:**
`check_asymmetry()` in `mmm_safety.py` used `action: 'stop_adjustments'` — a blunt instrument that halts all trigger evaluation. The asymmetry block should be side-specific, not global.

**Fix applied (`mmm_safety.py`, `mmm_monitor.py`):**
1. Changed asymmetry 7:1 action from `'stop_adjustments'` to `'block_heavy_side_sells'`
2. `should_block_adjustment()` does NOT recognize `'block_heavy_side_sells'` so trigger evaluation continues
3. Monitor now stores `session['_asymmetry_blocked_side'] = heavy_side` after safety events
4. `_process_adjustment()` checks `_asymmetry_blocked_side` and skips only if `hedge == blocked_side`
5. Message updated: "CE sells blocked, PE sells allowed to rebalance"

**Prevention rule:**
Asymmetry protection must ALWAYS be side-specific. Blocking the light side when it's trying to rebalance directly worsens the asymmetry. Any safety event that is directional (one side is heavy, other is light) must use targeted block logic, not a global `stop_adjustments`.

---

## [2026-03-12] close_at_use_bid caused positions to close at 2× threshold due to wide bid-ask spread

**What went wrong:**
Session mmm13mar26-2: PE 67500 positions closed at $36-45.5 even though `close_at_threshold=20`. User said "premiums 36-45 should NOT trigger close_at_5". The asymmetry CE=126/PE=2 was caused by this spurious close of 167 PE lots.

**Root cause:**
`close_at_use_bid=True` uses the BID price to decide close eligibility: if `bid ≤ threshold`, position is marked closeable. On illiquid OTM options with wide bid-ask spreads (bid=$10-18, ask=$40-50, mark=$30-40), the bid drops below $20 but the mark price (fair value) and actual fill price (mid/ask) are $36-45. The `close_position()` call then executes `smart_execute` which places a limit order at MID price and fills at $36-45.

**Investigation evidence:**
- 8 PE positions show `status=closed, being_closed=True` — matches `close_at_5_count: 8`
- Exchange: 9 close-buy orders at 17:03-17:06 UTC, fills at $36.0, $39.0, $40.5, $41.0, $41.5, $43.0, $43.0, $44.0, $45.5
- Bid prices at those times were ≤ $20 (below threshold)
- Mark prices at those times were $36-45 (well above threshold)

**Fix applied (`mmm_monitor.py` `_process_close_at_5`):**
Added WIDE-SPREAD GUARD immediately after `scan_closeable_positions()`: when `use_bid=True`, for each position the bid scan flagged as closeable, also check the mark price from `_make_fetch_fn()`. If `mark > effective_threshold`, skip the close and log. Only proceed if `mark ≤ threshold` (bid AND mark both confirm the position is cheap).

**Prevention rule:**
When using bid price for close-at-5 eligibility, ALWAYS also verify the mark price ≤ threshold before executing the buyback. Bid price alone is insufficient for illiquid options — the bid-ask spread can be 50-200% of the mid price on crypto option exchanges, causing severe overpays.

---

## [2026-03-12] HEDGE INTEGRITY GUARD — systemic fix for one-sided PE wipeout

**What went wrong:**
Session mmm13mar26-2: PE=101 active lots at 68000 were fully closed (BUY 1+30+50+20 @ $56-60) during a single 325.9s heartbeat. CE remained at 101 lots. PE was manually re-injected and wiped AGAIN.

**Root cause (design flaw):**
No mechanism prevented `close_position()` from closing the LAST position on a side while the other side had substantial positions. Multiple close mechanisms (close_at_5, harvest, shift_recycle, wind-down, ATM shield) all funnel through `close_position()` but none checked whether closing would leave the strategy one-sided.

**Fix applied (SYSTEMIC — 3 files):**
1. `mmm_close_at_5.py close_position()`: Added `hedge_guard` parameter (default True). Before placing exchange order, checks: if closing would reduce side's `total_lots` to ≤0 while other side has >0 `total_lots`, blocks close and returns `{success: False, hedge_guard_blocked: True}`.
2. `mmm_monitor.py _process_close_at_5()`: Added both-sides-closing detection — if closeable list covers ALL lots on BOTH sides, sets `hedge_guard=False` to allow clean strategy exit. Also added early `break` on `hedge_guard_blocked` to stop wasted iterations.
3. `mmm_monitor.py _process_wind_down_buyback()`: Added separate hedge check before `smart_execute` (bypasses `close_position`).

**Prevention rule:**
NEVER allow automated mechanisms to reduce one side to 0 lots while the other side has positions. The hedge integrity guard in `close_position()` is the chokepoint — all close mechanisms flow through it. Any new close mechanism MUST use `close_position()` (not direct `smart_execute`) to inherit this protection.

---

## [2026-03-13] Wrong margin utilization — portfolio_margin ≠ blocked margin in Delta Exchange UI

**What went wrong:**
WebUI showed 76.7% margin utilization ($1,343.33 / $1,750.47) while Delta Exchange's own UI showed 48% ($850.29 blocked as margin). The `mmm_margin_guardian.py` code prioritized `portfolio_margin` over `blocked_margin` when both are non-zero.

**Root cause:**
`portfolio_margin` in Delta's API wallet response is the **theoretical portfolio margin requirement** (a risk model value) — it can be higher than actual collateral locked. `blocked_margin` is what Delta Exchange actually freezes and what their UI labels "Blocked as Margin". The original code did `if portfolio > 0: total_used = portfolio` which picked the wrong field.

**Fix:**
Swapped priority in `mmm_margin_guardian.py` lines 176-185: now `blocked > portfolio > pos+order+cross`. The logic comment was updated to explain why.

**Prevention rule:**
For Delta Exchange wallet API: `blocked_margin` = actual locked collateral = what their UI shows. `portfolio_margin` = theoretical risk model value. Always prefer `blocked_margin` for utilization display. If you add a new margin calculation anywhere, verify it against the Delta Exchange UI "Blocked as Margin" field.


---

## [2026-03-15] Theta acceleration overriding adaptive interval (SILENT BUG)

**What went wrong:**
The monitor loop (Layer 1 = adaptive, Layer 2 = theta) had the comment "Can only make interval SHORTER, never longer" but no enforcement. Layer 2 blindly assigned `interval = accel['effective_interval']`. The theta `apply_theta_acceleration()` function computes its "transition zone" interval as `max(30, base_interval // 2)` — reading the RAW `params['adjustment_interval']`, not the already-reduced `interval`.

Concrete example: `base_interval=300`, `theta_window=120min`, `hours_to_expiry=1.5h (90min)`:
- Adaptive (Layer 1): tier `1-3h`, 0.10x → 30s  
- Theta (Layer 2): 90min is inside window, > 30min → `max(30, 300//2) = 150s`  
- Line 674: `interval = 150s` — **undid adaptive's 30s, tripling the actual interval**

This means for the entire 30–120 minute window before expiry, the adaptive tier's work was silently reversed by theta's "halve the base" formula.

**Fix (mmm_monitor.py line 674):**
```python
# Before (wrong):
interval = accel['effective_interval']
# After (correct):
interval = min(interval, accel['effective_interval'])
```

**Prevention rule:**
Any time a downstream layer is documented as "can only shrink X, never grow", enforce it with `min()` (or `max()` if the direction is reversed). Never use plain assignment for a "can only tighten" constraint — comments don't run.

---

## [2026-03-15] Three hidden bugs in MMM algo — lot cap, loss floor, stale gamma trigger

### Bug A: `_apply_consecutive_dir_limit` lot cap always = 1

**What went wrong:**
`session.get('lots', 1)` was used to read "initial lot count" but `session['lots']` is only set during entry initialization in mmm_api.py — not present in create_session(). Always fell back to 1, making lot_cap_pct produce `max(1, int(1 * 0.25)) = 1`. The consecutive-direction lot cap was permanently non-functional. Same bug existed in `mmm_perp_hedge.py` (full-delta mode).

**Fix:**
Changed to `session.get('params', {}).get('initial_lots', 10)` in both files — matches how mmm_scaler.py and mmm_safety.py read the canonical key.

**Prevention rule:**
For session-level configuration values, always read from `session['params']` (populated from DEFAULT_PARAMS). Top-level `session['lots']` is a runtime tracking field set during entry — never use it as a config source.

### Bug B: `calculate_standard_loss` over-hedging when active position is profitable

**What went wrong:**
`total_loss = max(active_loss, zero) + shifted_loss` floored active_loss at 0 before adding frozen position losses. When the active position was profitable (premium dropped), that profit was discarded, and frozen losses alone triggered hedging — even when the net portfolio was profitable. This caused unnecessary sell adjustments.

**Fix:**
Changed to `total_loss = active_loss + shifted_loss`. The outer `max(total_loss, zero)` on the return line already ensures non-negative output. Removing the inner floor allows active profits to offset frozen losses at the portfolio level.

**Prevention rule:**
When computing aggregate P&L across active + frozen positions, let profits offset losses before flooring. Premature flooring at the component level systematically overstates exposure.

### Bug C: Stale `_last_trigger_result` in both-sides auto-decision path

**What went wrong:**
When both CE and PE premiums exceeded their triggers simultaneously (BOTH_SIDES_UP), the 30s auto-decision path called `_process_adjustment` directly, bypassing `evaluate_triggers`. The gamma-aware multiplier in `calculate_lots_to_sell` read `session['_last_trigger_result']` — still containing the PREVIOUS heartbeat's trigger data. This caused the multiplier to fire (or not fire) based on stale excess percentages.

**Fix:**
Added `_last_trigger_result` update inside `_auto_decide_both_sides`, computing fresh `excess_pct` values from current premiums and trigger snapshots before returning the decision. Now when the subsequent `_process_adjustment` → `calculate_lots_to_sell` reads the trigger result, it has current data.

**Prevention rule:**
Any code path that calls `_process_adjustment` (or any function that reads `_last_trigger_result`) MUST ensure `session['_last_trigger_result']` is current. If bypassing `evaluate_triggers`, manually compute and set the trigger result first.

---

## [2026-03-15] Wind-down buyback race condition — missing `_being_closed` guard

**What went wrong:**
`_process_wind_down_buyback` called `smart_execute` (async, can take 60s+ with repricing) without pre-marking positions as `_being_closed`. During the await, other mechanisms (close-at-5, M2 recycler, M1 harvest) could concurrently attempt to close the same positions, causing double-close on the exchange.

**Root cause:**
The `_being_closed` guard was added to `_process_harvest` (Fix F1.2) but never applied to `_process_wind_down_buyback`. Both paths close positions via async order execution, both need the same race protection.

**Fix:**
Added `_being_closed = True` on matching positions (by `_pos_id`) before `smart_execute`, and cleanup (pop the flag) on failure or exception — identical pattern to harvest's Fix F1.2.

**Prevention rule:**
Any code path that closes positions via an async exchange call MUST pre-mark positions with `_being_closed = True` before the await, and clear the flag on failure. Search for `smart_execute` and `close_position` calls and verify the guard exists.

## [2026-03-15] `_being_closed` flag had no TTL — positions permanently locked after crash (March 11 incident)

**What went wrong:**
On March 11, 3 PE positions had `_being_closed=True` stuck for 30+ minutes (22:55–23:22 UTC). The first close attempt set the flag, then crashed in a path that didn't clear it. Every subsequent heartbeat saw the flag and skipped the positions. They were never closed — carrying unnecessary risk for 30+ minutes.

**Fix:**
Added `_being_closed_at = time.monotonic()` when setting the flag. In `scan_closeable_positions()`, `_check_stale_being_closed()` auto-clears the flag if stuck > 180 seconds, with a warning log.

**Prevention rule:**
Never set `_being_closed` without also setting `_being_closed_at`. Never add new exit paths from `close_position()` without ensuring the flag is cleared on failure.

---

## [2026-03-15] `MAX_CLOSES_PER_HEARTBEAT = 3` was dead code — cap never enforced

**What went wrong:**
The class constant `MAX_CLOSES_PER_HEARTBEAT = 3` was defined and referenced in the docstring, but never actually used in the loop. The only real cap was the beat deadline. Near expiry with many eligible positions, all of them could be attempted in one heartbeat, potentially stalling for 10+ minutes.

**Fix:**
Removed the dead constant. Added `close_at_max_per_beat` to `DEFAULT_PARAMS` (default 3, hot-reloadable). `_process_close_at_5()` now reads it from params and enforces the cap in the loop.

**Prevention rule:**
If a constant is meant to gate a loop, verify with grep that it's actually used in the loop condition. Dead constants in docstrings only are misleading.

---

## [2026-03-15] close_at_5 closes had no persistent activity log entry

**What went wrong:**
`'close_at_5'` existed in `ACTIVITY_TYPES` but `close_position()` never called `log_activity()`. Successful closes only wrote to the ephemeral heartbeat walkthrough and analytics[]. The persistent activity log (the main audit trail) had no record of which positions were closed, at what premium, and what P&L was realized.

**Fix:**
Added `log_activity('close_at_5', ...)` call inside `close_position()` after every successful fill.

**Prevention rule:**
Any function that realizes P&L must write a `log_activity` entry. Check `ACTIVITY_TYPES` to ensure the type is defined, then verify the call exists with grep.

---

## [2026-03-15] Breakeven Engine cache invalidation missing for 5 of 8 position-changing events

**What went wrong:**
The other coding AI that implemented the Breakeven Engine only added `invalidate_cache()` calls at 3 of 8 position-changing events (adjustment fill, strike shift fill, shift fallback fill). Missing from: close-at-5, M1 harvest, M2 lot recycle, shift-time recycle, operator inject.

Without invalidation, the breakeven engine would serve stale cached breakeven prices after these events, leading to wrong zone classification, wrong aggression multiplier, and potentially under/over-hedging.

**Fix:**
Added `invalidate_cache()` calls at all 5 missing locations (4 in mmm_monitor.py, 1 in mmm_api.py with local import).

**Prevention rule:**
When adding a caching layer that depends on position state, enumerate ALL code paths that modify positions and add invalidation at each one. The complete list of position-changing events in MMM is: adjustment fill, strike shift fill, shift fallback fill, close-at-5 fill, M1 harvest fill, M2 lot recycle fill, shift-time recycle close, operator inject fill, adopt (mmm_adopter.py), perp fill. Search for `close_position`, `smart_execute`, `recompute_side_lots` calls to find them all.

---

## [2026-03-18] Exit All failed silently — _being_closed flags blocked all 3 rounds

**What went wrong:**
The Global Graceful Exit (`mmm_exit_all.py`) ran 3 rounds but closed zero positions. All positions showed "Position already being closed (in-flight guard)" in every round. Session stopped as PARTIAL with live open positions on the exchange.

Root cause: A previous heartbeat's `close_at_5` scan had set `_being_closed=True` on positions and stored the monotonic timestamp. Exit All ran within ~6 seconds (3 rounds × 2s delay), which is far below the 180s auto-clear TTL. The `_collect_side_positions()` function skipped every position flagged as in-flight. Since the heartbeat gate blocks all normal logic during EXITING, those close attempts from the prior scan were never in-flight anymore — the flags were stale artifacts.

**Fix:**
Added `_force_clear_being_closed()` called at the top of `run_exit_all()`, before any rounds begin. This clears all `_being_closed` flags and `_being_closed_at` timestamps on all positions in both sides. Safe because the EXITING gate in `_heartbeat_inner()` ensures no concurrent order placements can be in-flight when exit_all runs.

**Prevention rule:**
Any multi-round retry mechanism that interacts with `_being_closed` guards must explicitly clear stale flags before the first round, not rely on TTL auto-clear. TTL (180s) is designed for detecting genuinely abandoned in-flight orders, not for short retry windows. When entering an "exit mode" that blocks all normal logic, any pre-existing in-flight flags from normal operation become stale immediately and must be cleared.

---

## [2026-03-18] Exit All: unrealized_pnl not zeroed + exit P&L not persisted in DB

**What went wrong:**
After exit_all closed all positions, the session showed R=$7.99, U=-$10.12, Total=-$2.13. R was the pre-exit realized only (exit trade P&Ls missing). U was the stale last-heartbeat unrealized (should be $0 with no open positions). The total happened to be approximately correct only by coincidence (stale U ≈ exit buyback cost).

Two bugs:
1. `session['unrealized_pnl']` was never zeroed after exit_all closed all positions
2. `session['realized_pnl']` was updated in memory by `close_position()` line 495 but the stop() save has edge cases (generation check, _save_disabled race) where this doesn't persist to DB

**Fix:**
Added to `run_exit_all()` before `monitor.stop()`:
1. `session['unrealized_pnl'] = 0.0` — explicit zero since no open positions remain
2. `get_storage().update_session(sid, {'realized_pnl': ..., 'unrealized_pnl': 0.0})` — belt-and-suspenders DB write that bypasses the generation-check/save-disabled guards

**Prevention rule:**
Any "close all positions" handler must explicitly zero `unrealized_pnl` before calling `monitor.stop()`. Never rely solely on stop()'s `_save_my_session()` for critical P&L fields — add an explicit `update_session()` call as belt-and-suspenders when the in-memory update MUST survive a stop().

**Also note (market reality):**
The user saw +$8 total P&L before triggering exit. During the 82s exit execution, BTC drifted toward PE@74000 strike, pushing that position's premium from ~132 to 257.50 (buyback cost $8.25). This is real market movement loss, not a software bug. Exit_all does not attempt to time or minimize buyback prices.
