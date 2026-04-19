# Last 3 Sessions — Auto-maintained. Full log: mmm_workdone_march.md

---

## 2026-04-19 (evening) — Fix: max_lots_per_side is now a HARD ceiling on active+frozen

**Incident:** Live STRADDLE_WITH_ADJUSTMENT session sold far more lots than the configured
`max_lots_per_side` budget — accumulated real exchange exposure ≈ 2× the cap.

**Root cause:** §13.1 position cap at `mmm_engine.py:620` used `active_lots` only. After
CAP AUTO-SHIFT froze the current side, `active_lots` reset to 0 and the engine allowed
another full cap's worth at the new strike. Secondary `max_total_exposure` defaulted to
`max_lots_per_side * 2`, so combined exposure was silently capped at double the budget.

**User directive:** "in any condition it should not sell more than the desired lots … flash
capacity full no further adjustment." Real-money hard invariant.

**Fix (`mmm_engine.py`, `mmm_monitor.py`, `mmm_activity.py`):**
1. §13.1 position cap now uses `total_lots` (active + frozen) — hard ceiling.
2. CAP AUTO-SHIFT short-circuits when `total_lots >= max_lots_per_side` — emits rate-limited
   `capacity_full` activity + `emit_safety` alert instead of pointless freeze+shift.
3. Registered `capacity_full` activity type in `ACTIVITY_TYPES` + `safety` category.

**Consequence:** Once capped, that side stops selling until frozen lots drain (close_at_5 /
M1 harvest / manual close). If opposite side breaches while capped → unhedged, max-loss is
the only protection. Operator must raise `max_lots_per_side` or drain frozen lots.

**Files changed:** `mmm_engine.py`, `mmm_monitor.py`, `mmm_activity.py`, `test_sealed_calculate_lots_to_sell.py`
**Tests:** All MMM sealed — 1456 passed / 0 failed

---

## 2026-04-19 — Fix: F6 gamma shift widening bypass for STRADDLE_WITH_ADJUSTMENT + starvation guard

**Incident:** mmm19apr26-1 (live STRADDLE_WITH_ADJUSTMENT). Proactive shift for CE at
strike=76000 (premium=$59–$68) failed for 10+ beats; strikes 75600 ($186) and 75800
($109) were ignored. Escalated through L1→L2→L3 shift-starvation alerts.

**Root cause:** Gamma zone = DANGER → F6 set `_gamma_shift_min_otm = spot × 1.8% ≈ 1359`.
Passed as `min_otm_distance` to `find_new_strike`, this required new CE strike
distance from spot ≥ 1359, i.e. new strike > 76861. But old_strike=76000 was only
498 from spot (already INSIDE the F6 floor), so the only strikes F6 allowed had
less premium than the already-decayed current strike — no candidate could clear
`shift_threshold=$70`.

**Strategy invariant (user directive):** In STRADDLE_WITH_ADJUSTMENT, ATM gamma
is structural (both legs at ATM). Gamma must NEVER block adjustment/shift —
reactive hedge must fire. Same rationale as Fix 8 (2026-04-17) projected-gamma
cap bypass at `_process_adjustment`.

**Fix (mmm_monitor.py, `_process_strike_shift`, F6 block ~L5402–5462):**
1. `_is_straddle_adj_shift` short-circuits F6 computation entirely for
   STRADDLE_WITH_ADJUSTMENT — F6 never applies in this strategy. Rate-limited
   INFO log via `_should_emit_warning`.
2. For non-straddle strategies, if `old_strike` is already inside the F6 floor,
   reset `_gamma_shift_min_otm = 0.0` and log a warning (starvation guard).

**Files changed:** `mmm_monitor.py`
**Tests:** `test_sealed_mmm_strike_shift.py` — 30 passed / 0 failed

---

## 2026-04-18 — Fix: Proactive shift enabled for STRADDLE_WITH_ADJUSTMENT after first adjustment

**Incident:** mmm18apr26-3 (real money, live). CE decayed to $37 vs shift_threshold=$70.
Proactive shift was disabled for STRADDLE_WITH_ADJUSTMENT → no shift fired. PE trigger
was also delayed to 80% by theta acceleration (window=288 min), so `_process_adjustment`
shift check never ran either. By trigger time, no valid OTM CE strike existed.
shift_fallback sold at old decayed strike; user manually added 100 CE lots at $36.5.

**Fix (mmm_monitor.py Step 5.6, ~line 3141):**
Added `_straddle_adj_allow_proactive` guard: proactive shift now fires for
STRADDLE_WITH_ADJUSTMENT when `adjustment_count > 0` (straddle already asymmetric).
At `adjustment_count=0` (session just started), proactive shift remains disabled (unchanged).

**Files changed:** `mmm_monitor.py`
**Tests:** 1456 passed / 0 failed

