# Last 3 Sessions — Auto-maintained. Full log: mmm_workdone_march.md

---

## 2026-05-06 — Profit Ratchet Fresh-Reset (mmm06may26-1 root cause)

**Incident**: mmm06may26-1 ended with severe asymmetry — CE=2 active vs PE=200 (103 active + 97 frozen, cap reached). 467 activity events including 114 whipsaw_smart_block, 81 PE-cap adjustments_stopped, 8 arbiter Tier 1 PE-decay events that fought CE shift starvation L1/L2.

**Root cause**: User's original `profit_ratchet` design intent — "treat each milestone like a fresh algo, drop accumulated baggage" — was never implemented. The current code at `mmm_monitor.py:3725-3760` only calls `update_trigger_snapshots()` (re-anchors price thresholds). It does NOT clear `_shift_starv_count`, `_consecutive_*`, `_whipsaw_*/_smart_ws_*`, `_trend_calm/plateau_beats`, `_gamma_blocked_count`, `_regime_action`, etc. So baggage accumulated through ratchet #4 ($20) and #5 ($25), pinning the algo into pathological behavior despite profit milestones being hit.

**Fix**: Tiered fresh-reset, all flag-gated, default OFF. Master `profit_ratchet_fresh_reset` + 3 sub-flags: Tier A `ratchet_reset_cooldowns` (default ON when master enabled — pure cooldown/block counters, all verified safe), Tier B `ratchet_reset_whipsaw` (default OFF — whipsaw state, preserves `_smart_ws_series` source buffer), Tier C `ratchet_reset_regime_tier` (default OFF — regime tier reset, deliberately preserves `_trend_anchor_spot` so regime self-detects within 1-2 beats without losing trend baseline). All 4 params hot-reloadable. Activity log entry only fires when ≥1 field cleared. NEVER cleared: positions, P&L, fill cursor, monitor_generation, paused/awaiting/emergency state, adjustment history, `_smart_ws_series`, `_trend_anchor_spot`.

**Files**: `mmm_state.py`, `mmm_config.py`, `mmm_monitor.py` (new method `_profit_ratchet_fresh_reset`), `mmm_activity.py`, `tests/test_sealed_audit_fixes.py` (8 new test classes, 17 sealed contracts) | **Tests**: 1274 sealed pass (+17 new, 0 regressions)

---

## 2026-05-05 — Design: Session Mode Controller for trending markets (mmm05may26-1 post-mortem)

**Problem**: Session mmm05may26-1 started with 50 CE lots (correct for TREND_DOWN), market reversed +2,000 pts over 19 hours, CE went deep ITM. Bot had no posture-switching mechanism. Both sides hit 300/300 cap → paralysis for hours. First PE hedge was 43 minutes after CE hit cap.

**Root causes identified (8)**:
1. Regime anchor reset blindness — grinding trends always appear NORMAL to regime system
2. No dangerous-side concept — algo is symmetric, no "which side is causing damage"
3. "Calculated loss ≤ 0" formula skips hedges in early ITM beats (monitor.py:~5534)
4. Double-sell guard suppresses correct arbiter breakeven_critical response every ~10 min
5. ITM guard + F6 gamma floor dual block — CE had no path to reduce
6. Both-sides-at-cap paralysis — no circuit breaker
7. Stale PnlCore estimates (16+ hour staleness on 2 orders all session)
8. Watchdog restart (#4 at 13:41 UTC) loses transient state

**Solution designed (no code yet, awaiting implementation confirmation)**:
- **Component A — God Layer Side Asymmetry**: `_check_side_asymmetry()` using per-position `entry_premium` to compute SD = `abs(ce_unrealized - pe_unrealized)`. Fires when SD > $25 AND PP < -$20. Sets `_god_dangerous_side` + recovery target.
- **Component B — Three Modes**: Conservative (unchanged), Moderate (1.5× velocity, 60s cooldown, 70% loss threshold, dangerous side blocked), Aggressive (velocity disabled, 0 cooldown, double-sell disabled, loss formula bypassed, ITM ±$50, F6 suspended, dangerous side hard blocked)
- **Component C — Auto Escalation**: 4 signals (SD, PP, ITM depth, P&L velocity), 3-beat escalation / 5-beat de-escalation hysteresis, fast-track bypass (SD>$70 AND PP<-$50 AND PV<-$2/min), mode state in `session['_mode']` survives restarts, manual override with 30-min expiry

**Document**: `MMM_SESSION_MODE_DESIGN.md` created with full design (30+ params, guard profiles, notification templates, 5 implementation phases, risk assessment).

**Files**: `MMM_SESSION_MODE_DESIGN.md` (design only — no code changes) | **Tests**: None yet (Phase 1 pending user confirmation)

---

## 2026-05-05 — Three-bug fix: velocity direction, God inactivity, double-sell guard (mmm05may26-1)

**Incident**: Session mmm05may26-1 accumulated 300 CE lots in a TREND_DOWN market. When market reversed to TREND_UP, CE went deep ITM (CE at 79600, spot at 80639). The algo kept cycling CE lots (wrong direction) while the correct PE hedge response was blocked. User manually reduced CE lots to cut upside risk.

**Root-cause analysis revealed 3 compound bugs:**

**Bug 1 — Velocity bypass is direction-blind** (`mmm_monitor.py`):
- Rule 2 arbiter override clears `_skip_to_pnl = False` for all downstream steps including `_proactive_shift_scan`
- Intended: CE emergency → bypass velocity for PE (safe side) only
- Actual: bypass freed CE proactive shift too → more CE lots placed on the dangerous side
- Fix: after clearing `_skip_to_pnl`, set `session['_arbiter_velocity_dangerous_side']` = opposite of `_arb_side`. `_proactive_shift_scan` skips that side. Cleared each beat via `pop()` at line ~3469. Only applies when `action_type == 'defensive_shift'`.

**Bug 2 — God layer starved by arbiter activity** (`mmm_monitor.py` + `mmm_god_layer.py`):
- God layer fires when PNL drifts AND algo inactive for 20 min
- Arbiter shifts recorded in `adjustment_history` reset the inactivity clock every 5–10 min → God never fires
- Arbiter shifts are mechanical corrections, not organic trigger responses — they should not count as "algo activity" for God's inactivity check
- Fix: `_process_strike_shift` records `'is_arbiter_correction': session.get('_arbiter_decision_active', False)` in history. God's `_minutes_since_last_adjustment()` skips those entries (alongside existing OPERATOR/STRADDLE_ROLL/GOD_CORRECTION skips).

**Bug 3 — Double-sell guard kills correct market response** (`mmm_monitor.py`):
- Guard suppresses arbiter PE defensive shift when proactive PE shift already fired same beat
- At 08:09:18 IST when TREND_UP escalated, PE proactive shift had just fired → arbiter PE defensive shift (the correct upmarket hedge) was suppressed at the worst possible moment
- Fix: `_trend_emergency_bypass` exception — when `trend_tier >= 2 (GUARD)` AND arbiter trigger is breakeven_critical/hedge_decay/trend-related, guard is lifted. Log `arbiter_trend_emergency_override` activity when bypass fires.

**Files**: `mmm_monitor.py` (3 locations), `mmm_god_layer.py` | **Tests**: 149 passed (baseline 136 + 13 new sealed)

---

