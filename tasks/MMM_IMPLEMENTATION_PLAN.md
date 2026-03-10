# MMM Audit Implementation Plan — March 10, 2026

> Derived from comprehensive audit of all MMM code files. Implement in order of tier.
> Mark each item DONE as implemented. Cross-reference to AI_MMM_CONTEXT.md §X for context.

---

## TIER 1 — Safety Risks (Implement First)

### [DONE] T1-1: M2 P&L Rollback Fix
**File:** `webui/backend/routes/mmm/mmm_recycler.py`  
**Bug:** Phase B failure/exception restores positions but does NOT undo `session['realized_pnl']`  
**Fix:** Add `session['realized_pnl'] = session.get('realized_pnl', 0.0) - phase_a_pnl` in BOTH:
- Phase B exception handler (line ~472)
- Phase B failure handler (line ~489)

---

### [DONE] T1-2: Peak P&L Decay Floor
**File:** `webui/backend/routes/mmm/mmm_safety.py`  
**Bug:** `peak = current_peak * 0.9 + total_pnl * 0.1` can go below zero → trailing stop never fires  
**Fix:** `session['peak_pnl'] = max(new_peak, 0.0)` in `update_peak_pnl()`

---

### [DONE] T1-3: Wire consecutive_critical Escalation
**File:** `webui/backend/routes/mmm/mmm_margin_guardian.py`  
**Bug:** `self._consecutive_critical` increments but is never read → no escalation after 3 CRITICAL beats  
**Fix:** After N ≥ 3 consecutive CRITICAL beats, add `'force_stop_session'` to actions + Telegram alert

---

### [DONE] T1-4: Session Dict Heartbeat Lock
**File:** `webui/backend/routes/mmm/mmm_monitor.py`  
**Risk:** Multiple API threads + heartbeat thread mutate session dict concurrently  
**Fix:** Module-level `_session_locks: dict` + `_get_session_lock(session_id)` helper  
Acquire with `with _get_session_lock(session_id):` at heartbeat entry

---

## TIER 2 — Operational Improvements

### [DONE] T2-1: Fix min_trigger_move Fallback Default
**File:** `webui/backend/routes/mmm/mmm_trigger.py`  
**Bug:** Code fallback `params.get('min_trigger_move', 3.0)` contradicts DEFAULT_PARAMS value of 10.0  
**Fix:** Change fallback from `3.0` to `10.0`

---

### [DONE] T2-2: Wire Circuit Breaker should_alert
**File:** `webui/backend/routes/mmm/mmm_monitor.py`  
**Bug:** `circuit.should_alert` property returns True after 3+ consecutive OPEN episodes but nobody checks it  
**Fix:** After fetching prices with circuit breaker, check `self._circuit_breaker.should_alert` → emit safety event

---

### [DONE] T2-3: Fill Price Bounds Check
**File:** `webui/backend/routes/mmm/mmm_executor.py`  
**Bug:** `_parse_fill_price()` validates NaN/Inf but no bounds check for price < 0 or > $1M  
**Fix:** Add `if fill_price <= 0 or fill_price > 1_000_000: raise ValueError(...)` after float conversion

---

### [DONE] T2-4: Lot Velocity Limiter
**Files:** `mmm_safety.py`, `mmm_state.py`  
**New Feature:** Cap lot growth rate to prevent exponential accumulation  
**Params (hot-reload):**
- `lot_velocity_enabled` (default True)
- `lot_velocity_limit` (default 10 lots/window)
- `lot_velocity_window_mins` (default 30)

---

### [DONE] T2-5: P&L Attribution Fields
**Files:** `mmm_state.py`, `mmm_engine.py`, `mmm_close_at_5.py`, `mmm_harvester.py`, `mmm_recycler.py`  
**Feature:** Track P&L by source: initial / adjustment / harvest / recycle / perp  
**New session fields:**
- `pnl_initial` — P&L from original entry position closes
- `pnl_adjustment` — P&L from adjustment fill closes
- `pnl_harvest` — P&L from M1 harvesting
- `pnl_recycle` — P&L from M2 Phase A buybacks
- `pnl_perp` — Mirror of `perp_hedge.realized_pnl`

---

### [DONE] T2-6: Session Analytics Array Cap
**File:** `webui/backend/routes/mmm/mmm_monitor.py`  
**Bug:** `auto_close_events`, `safety_trigger_events` arrays grow unboundedly  
**Fix:** Cap at 200 entries when appending

---

## TIER 3 — Strategic Enhancements

### [DONE] T3-1: Proactive Shift Scanner
**File:** `webui/backend/routes/mmm/mmm_monitor.py`  
**Feature:** Before close-at-5 in heartbeat, check if any side's premium < shift_threshold AND other side has lots AND other side is near trigger. Shift proactively without waiting for trigger evaluation.  
**New param:** `proactive_shift_enabled` (default True)  
**Condition:** `ce_now < shift_threshold AND pe_excess_pct > min_trigger_move * 0.5 AND pe_total_lots > 0`

---

### [DONE] T3-2: Gamma-Aware Lot Multiplier
**File:** `webui/backend/routes/mmm/mmm_engine.py` (`calculate_lots_to_sell()`)  
**Feature:** When premium has moved aggressively above trigger (>50% excess), apply multiplier to lots  
**Logic:**
- excess_pct 50-100%: multiplier 1.1x (10% more lots)
- excess_pct 100-200%: multiplier 1.2x
- excess_pct 200%+: multiplier 1.3x (capped)
**New param:** `gamma_aware_enabled` (default True), `gamma_aware_max_multiplier` (default 1.3)

---

### [DONE] T3-3: Whipsaw Pre-Filter Enhancement
**File:** `webui/backend/routes/mmm/mmm_monitor.py`  
**Feature:** Before processing adjustment, check if new_lots would largely cancel last adjustment. Log warning + boost whipsaw counter.  
**Logic:** If `last_adjustment.side != current_aggressor AND new_calculated_lots ≈ last_adjustment.lots (±20%)` → flag as potential micro-whipsaw, increment consecutive_alternating for faster detection

---

## TIER 4 — Nice to Have

### [DONE] T4-1: Mark MONEY_POWER_ALGORITHM_PLAN.md as Historical
**File:** `MONEY_POWER_ALGORITHM_PLAN.md`  
**Fix:** Add header banner pointing to AI_MMM_CONTEXT.md as the authoritative reference

---

### [DONE] T4-2: Pending Order TTL Cleanup in Heartbeat
**File:** `webui/backend/routes/mmm/mmm_monitor.py`  
Audited `_STALE_SECONDS = 900` TTL logic — the in-memory registry is at risk when the watchdog re-instantiates a `MMMMonitor` within the same process (PID reuse keeps old entries).  
Fix: `clear_all_pending(self.session_id)` added to `start()` (before thread launch) so every new monitor instance begins with a clean pending-order registry for its session.

---

### [DONE] T4-3: Pre-Adjustment Delta Projection for Perp
**Files:** `webui/backend/routes/mmm/mmm_perp_hedge.py` + `mmm_monitor.py`  
Implemented as lightweight optional-kwarg extension to the existing API — no rework required.  
- Added `projected_lots: int = 0` and `projected_side: str = ''` kwargs to `compute_required_hedge()` and `run_perp_hedge()`  
- Projection logic: `sell call → Δ = -approx_delta × lots × LOT_SIZE_BTC`, `sell put → +Δ`  
- Uses param `perp_hedge_approx_option_delta` (default 0.5) to avoid live greeks API call  
- Step 7.5 call site in `mmm_monitor.py` reads `_hb_wt['adjustment']` (set by `_process_adjustment`) and passes lots+side when `perp_hedge_project_adjustment=True` (default True)  
- Fully backward-compatible — zero-default kwargs, all existing callers unchanged

---

### [DONE] T4-4: Consistent Price Basis Close/Shift
**Analysis result:** The mark/bid split is **intentional and correct**.  
- Shift detection → mark price (conservative; fires on market-consensus move, not transient bid dips in illiquid options)  
- Close-at-5 → bid price (accurate; reflects what the market will actually pay for a buyback)  
- SHIFT-BEFORE-CLOSE guard uses mark (same as shift detection) → consistent with the shift signal  
Added explicit documentation in `_fetch_premiums()` docstring in `mmm_monitor.py` explaining this design decision.

---

### [DEFERRED] T4-5: Refactor mmm_monitor.py Pipeline  
**Scope:** 5500 lines → extract heartbeat steps into composable pipeline functions  
**Status:** Formally deferred — dedicated sprint required, zero behavioral change, not part of this implementation plan.

---

## DOCUMENTATION UPDATES

### [DONE] Doc-1: Update AI_MMM_CONTEXT.md
Add sections for: Lot Velocity Limiter, P&L Attribution, Gamma-Aware Multiplier, Proactive Shift Scanner, all new params

### [DONE] Doc-2: Create MMM_USERGUIDE.md  
Full user-facing guide with examples and illustrations

---

## Syntax Validation Checklist

After all changes:
```bash
python3 -c "import py_compile; py_compile.compile('webui/backend/routes/mmm/mmm_recycler.py', doraise=True); print('OK')"
python3 -c "import py_compile; py_compile.compile('webui/backend/routes/mmm/mmm_safety.py', doraise=True); print('OK')"
python3 -c "import py_compile; py_compile.compile('webui/backend/routes/mmm/mmm_margin_guardian.py', doraise=True); print('OK')"
python3 -c "import py_compile; py_compile.compile('webui/backend/routes/mmm/mmm_trigger.py', doraise=True); print('OK')"
python3 -c "import py_compile; py_compile.compile('webui/backend/routes/mmm/mmm_executor.py', doraise=True); print('OK')"
python3 -c "import py_compile; py_compile.compile('webui/backend/routes/mmm/mmm_state.py', doraise=True); print('OK')"
python3 -c "import py_compile; py_compile.compile('webui/backend/routes/mmm/mmm_engine.py', doraise=True); print('OK')"
python3 -c "import py_compile; py_compile.compile('webui/backend/routes/mmm/mmm_close_at_5.py', doraise=True); print('OK')"
python3 -c "import py_compile; py_compile.compile('webui/backend/routes/mmm/mmm_harvester.py', doraise=True); print('OK')"
python3 -c "import py_compile; py_compile.compile('webui/backend/routes/mmm/mmm_monitor.py', doraise=True); print('OK')"
```
