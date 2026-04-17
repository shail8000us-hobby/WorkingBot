# Last 3 Sessions — Auto-maintained. Full log: mmm_workdone_march.md

---

## 2026-04-17 — P0 crash fix: UnboundLocalError kills sessions on first_reversal adjustment

**Root cause:** `_pre_adj_trigger` in `_process_adjustment()` was only assigned in the `else` (standard)
branch. The `if is_reversal:` path (`adj_type='first_reversal'`) never assigned it, but both paths fall
through to `self._hb_wt['adjustment']` dict ~line 5054 where it's referenced → `UnboundLocalError`.
The straddle reversal-skip bypass (Fix 3, previous session) enabled the reversal path to reach the fill
code for STRADDLE+ADJ — that's why this only manifested today.

**Fix:** One line — `_pre_adj_trigger = 0` initialized before the `if is_reversal:` block (line 4528).
`else` branch still overwrites with real snapshot for standard adjustments. Tests: 1421 passed / 0 failed.

---

## 2026-04-17 — Full guard audit: 7 more bypasses for STRADDLE_WITH_ADJUSTMENT

Comprehensive audit of all guards in `mmm_monitor.py` that were written for standard MMM but wrongly apply to `STRADDLE_WITH_ADJUSTMENT`. All changes are in `mmm_monitor.py` only.

### Fix 1 — `stop_adjustments` bypass (~line 2557)
- `_is_straddle_adj` added alongside `_dangerous_mode` in the `elif` chain for `stop_adjustments` safety events.
- Covers: whipsaw cooldown, lot_velocity limit, position_cap, trailing_stop.
- Rationale: for a short straddle the adjustment IS the hedge — blocking it makes the position MORE dangerous, not less. Whipsaw = price bouncing = both legs need constant rebalancing. Lot velocity = market is moving fast = hedge must keep up. Position cap = straddle needs to accumulate hedge lots. Trailing stop = adjustments reduce loss, not cause it.
- max_loss (`auto_close`) and session `stop` are still enforced — those two branches are above this one.

### Fix 2 — Reversal cooldown bypass (~line 2977)
- `_is_straddle_adj` added alongside `_dangerous_mode` in cooldown bypass.
- Rationale: "reversal" in straddle = spot bounced, the other leg just became the aggressor, hedge must fire immediately. Cooldown window would leave the straddle unbalanced for minutes.

### Fix 3 — Reversal skip bypass (`_process_adjustment` ~line 4557)
- Added `_straddle_adj` local flag in `_process_adjustment()` (alongside existing `_dangerous_mode_adj`).
- After `should_skip_reversal_adjustment()` returns `skip=True`, immediately override `skip=False` when `_straddle_adj`. Logs a deduplicated warning.
- Rationale: reversal skip logic ("if active-strike P&L is positive, skip the hedge") doesn't apply to straddles — both legs are at the same strike, so "profitable" on one leg just means the other leg is being squeezed. The hedge must always fire.

### Fix 4 — Whipsaw lot reduction bypass (~line 4789)
- Added `and not _straddle_adj` to the `if _ws_score >= _ws_restrict and lots > 1` condition.
- Rationale: whipsaw = price bouncing hard = both straddle legs alternately trigger. Halving lots systematically under-hedges in exactly the scenario that needs full-size hedging.

### Fix 5 — Consecutive direction limit bypass (~line 4800)
- Added `and not _straddle_adj` to the `if not _dangerous_mode_adj` gate before `_apply_consecutive_dir_limit()`.
- Rationale: in a trending market the aggressor side fires repeatedly (e.g. BTC keeps rallying → CE keeps triggering → PE hedge sells are needed each time). The consecutive limiter interprets this as suspicious same-direction churn; for straddle it is the normal expected behavior.

### Fix 6 — Proactive shift disabled for straddle (~line 3054)
- Added `and not _is_straddle_adj` to the Step 5.6 proactive shift gate.
- Rationale: proactive shift moves a low-premium leg to a new OTM strike. For straddle, both legs are intentionally at the original ATM strike — proactive shift breaks the straddle structure.

### Fix 7 — Whipsaw trigger widening bypass (~line 3240)
- Added `and not _is_straddle_adj` to the `if _ws_factor > 1.0` block that widens `_effective_min_trigger_move`.
- Rationale: trigger widening reduces adjustment frequency under whipsaw. For straddle, under-adjusting in a whipsaw market compounds losses on both legs simultaneously.

**Tests:** 1421 passed / 0 failed.

### Fix 8 — Gamma cap projected-gamma bypass (`_process_adjustment` ~line 4954)
- **Bug:** Inside `_process_adjustment()`, before executing the hedge sell, the algo fetches the new strike's gamma and calls `check_projected_gamma()`. If projected portfolio gamma would exceed `gamma_hard_limit`, the adjustment is blocked with "Gamma Cap Blocked". Only `_dangerous_mode_adj` bypassed this.
- **Root cause:** For a short straddle, the straddle itself is a large-gamma position by definition (both CE and PE sold ATM). The existing straddle already saturates the gamma cap. Every hedge sell attempt hits the projected-gamma block — adjustments are silently dropped even when all other regime gates are bypassed.
- **Fix:** Added `elif _straddle_adj:` bypass — logs a deduplicated warning and proceeds. The hedge sell is reactive (trigger fired because spot moved); unhedged straddle exposure is more dangerous than incremental hedge-lot gamma.

---

## 2026-04-17 — Post-Session Forensic Audit Fixes (session mmm17apr26-6)

Forensic audit of session `mmm17apr26-6` (adopt + monitor + stop, 80s, STRADDLE_WITH_ADJUSTMENT)
identified 3 confirmed bugs. All 3 fixed in `mmm_api.py`.

**BUG-1 (P1) — Stop reason empty string not rejected** (`mmm_api.py: stop_session`)
- Root cause: `data.get('reason', 'User stopped')` — default only applies when key is ABSENT.
  When frontend sends `{"reason": ""}`, the empty string is used, persisting `stop_reason=""`
  in the DB, destroying forensic traceability.
- Fix: `reason = (data.get('reason') or '').strip() or 'User stopped'` — strips and falls back.

**BUG-2 (P0) — Strategy invariant violations non-blocking at start** (`mmm_api.py: start_session`)
- Root cause: `start_session_monitor()` calls `validate_session_for_strategy()` but only logs
  a warning — the monitor starts regardless. In session mmm17apr26-6, CE active_strike=75000
  vs PE active_strike=74400 (mismatch) was ignored. The session then ran with `_is_straddle_adj=True`,
  incorrectly bypassing FORCE_REDUCE even though the straddle was invalid. Portfolio gamma was
  13875 (emergency limit = 10000) with no de-risk path.
- Fix: Added PREFLIGHT A in `start_session` (before `storage.update_session` — so no broken RUNNING
  state is written on failure). Calls `validate_session_for_strategy(session)` and returns HTTP 400
  with `invariant_violations` list. Operator can pass `force_start=true` in request body to override
  for emergency/recovery scenarios (logged as warning).

**BUG-3 (P1) — Cap vs adopted lots not checked at start** (`mmm_api.py: start_session`)
- Root cause: `validate_adoptable()` generates a WARNING (not error) when total_lots > max_lots_per_side,
  but the start flow never re-checks this. In session mmm17apr26-6, CE had 300 active_lots and PE
  had 142 active_lots against max_lots_per_side=5. Engine §13.1 position-cap gate: `if current_total +
  lots_to_sell > max_lots_per_side → lots_to_sell = 5 - 300 = -295 ≤ 0 → return 0`. ALL adjustments
  silently blocked from heartbeat 1. Operator had to manually PATCH cap 5→500 at 08:46:48.
- Fix: Added PREFLIGHT B in `start_session` for `entry_mode='adopt'` sessions. Checks
  `ce.active_lots > max_lots_per_side` and `pe.active_lots > max_lots_per_side`; returns HTTP 400
  with `cap_violations` list. Operator can pass `force_start=true` to acknowledge and proceed.

**No trading logic changed. No monitor restart. API-only.** Preflights only run on the import/adopt
code path (not the fresh entry path which has its own guards). Both checks happen before
`storage.update_session(strategy_status=RUNNING)` so a failed preflight never leaves the session
in a broken RUNNING state.
