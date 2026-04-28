---
title: AI Arbiter Context — MMM Coordination Arbiter (Phase 3)
created: 2026-04-28
status: LIVE (no shadow)
source_of_truth: MMM_COORDINATION_PLAN.md
---

# MMM Coordination Arbiter — AI Context Document

> **Purpose**: Enable any AI to understand, extend, or debug the coordination arbiter without re-deriving context.
> Read this first. Then read `MMM_COORDINATION_PLAN.md` for full design rationale and Phase 2 Q&A.

---

## 1. What Problem This Solves

MMM has 50+ independent expert modules (whipsaw, regime, gamma, breakeven, harvester, etc.). Each is sound in isolation. The problem: **they have no coordination** — when two modules conflict, the winner is determined by heartbeat execution order, not considered judgment.

**Symptom that triggered this work (2026-04-27)**: PE became ATM after a 1000-pt drop. Breakeven engine wrote `_breakeven_zone='CRITICAL'`. Smart whipsaw, running later in the same beat, did not read that signal — it blocked the very adjustment needed to protect the position.

This is a **structural coordination bug**, not a tuning bug. The arbiter is the explicit coordination layer.

---

## 2. The Architecture

```
Heartbeat
  Step 1–5.7  (existing modules: ATM, breakeven, whipsaw, regime…)
  Step 5.8    (gamma detector → writes _gamma_regime)
  ─────────────────────────────────────────
  ARBITER     ← inserts here, reads all signals, returns ONE decision
  ─────────────────────────────────────────
  Skip-to-PNL gate (downstream)
  Step 6+     (PNL, lot-count logging, etc.)
```

The arbiter is **read-only** at decision time (`evaluate()` returns an `ArbiterDecision` dataclass, no side effects). `mmm_monitor` executes the decision via existing tested infrastructure.

---

## 3. The 7 Sealed Hierarchy Rules

These are **non-negotiable**. Never propose changes without user approval.

| Rule | Tier | Name | What it means |
|---|---|---|---|
| 1 | 0 | Tier 0 absolute | Hard stop, ATM shield, time stop — NOTHING overrides these |
| 2 | 1 | Tier 1 acts, doesn't block | Extreme conditions → bypass gates, execute defensive action |
| 3 | 2 | Tier 2 silent | Elevated risk → modules work as designed, arbiter is no-op |
| 4 | — | Premium quality > quantity | Fewer high-premium policies, not many cheap ones (insurance doctrine) |
| 5 | — | Last-30-min cool-down | No Tier 1 bypass in last 30 min. Operational gates run. |
| 6 | — | Stale = danger | Signal not refreshed → escalate one tier, log STALE event |
| 7 | — | Audit everything | Concise activity-log line + structured JSON per Tier 1 beat |

**Tier 0 examples**: max_loss hit, ATM shield fires, time-based auto-close.
**Tier 1 examples**: `_breakeven_zone='CRITICAL'`, `_margin_tier='RED'`, `_gamma_regime='EMERGENCY'`.
**Tier 2 examples**: `_breakeven_zone='DANGER'`, `_margin_tier='ORANGE'`, `_gamma_regime='HARD'`.
**Tier 3 / normal**: all other states — whipsaw, regime, gamma_soft, asymmetry gates run normally.

---

## 4. The 3 Tier 1 Actions

When `evaluate()` returns a non-noop decision, `mmm_monitor._execute_arbiter_decision()` routes to one of:

### 4.1 `defensive_shift` (trigger: breakeven CRITICAL)

**What**: premium-aware strike shift on the safe (opposite-of-threatened) side.

**Execution**: `self._process_strike_shift(opposite_side, loss, ce_now, pe_now)` with `_arbiter_shift_bypass_cooldown=True`. This bypasses the 120s shift cooldown.

**Premium doctrine**: find strike where `premium ≈ params['shift_target_premium']`. Sell minimum lots needed. Never pile cheap-premium lots (Rule 4).

**Which side is threatened**: read from `session['_breakeven_result']['nearest_side']` — lower → PE threatened; upper → CE threatened. Arbiter shifts the opposite.

### 4.2 `gamma_emergency_close` (trigger: gamma EMERGENCY)

**What**: defensive close on the dominant-gamma side to reduce curvature exposure.

**Execution**: scans `session[dominant_side]['positions']` sorted by premium DESC, closes top-N via `close_position(mechanism='emergency')` until `close_lots` reached.

**close_lots**: currently `max(1, int(dominant_lots * 0.25))` — closes 25% of dominant-side lots. Phase 4 replay will tune this.

**Replaces**: legacy `self.pause('Gamma emergency')` — the session no longer pauses.

**STRADDLE_WITH_ADJUSTMENT exception**: ATM gamma is structural; gamma Tier 1 is bypassed for this strategy (checked via `resolve_strategy_type`).

### 4.3 `margin_recovery_buyback` (trigger: margin RED or CRITICAL)

**What**: buy back cheapest OTM positions on the bigger-lots side to free margin.

**Execution**: scans `session[scan_side]['positions']` sorted by premium ASC (cheapest first), closes via `close_position(mechanism='emergency')`.

**Why cheapest-first**: per Rule 4 (insurance doctrine). In a black swan, contract count is what hurts you, not premium value. Cheap OTM lots are the highest black-swan exposure per dollar of margin freed.

**Priority**: margin RED is checked first in `evaluate()` dispatch order (capital constraint binds everything else).

---

## 5. Key Files

| File | Role |
|---|---|
| `webui/backend/routes/mmm/mmm_arbiter.py` | Arbiter decision engine — `CoordinationArbiter.evaluate()`, stale-signal accessors, `ArbiterDecision` dataclass, `get_arbiter()` singleton |
| `webui/backend/routes/mmm/mmm_monitor.py` | Heartbeat wire-in (`_heartbeat_inner` after Step 5.8), live execution methods (`_execute_arbiter_decision`, `_arbiter_execute_defensive_shift`, `_arbiter_execute_gamma_close`, `_arbiter_execute_margin_recovery`) |
| `webui/backend/routes/mmm/mmm_state.py` | Signal freshness helpers: `record_signal_update(session, signal_name)`, `is_signal_fresh(session, signal_name, max_age_seconds)` |
| `webui/backend/routes/mmm/mmm_gamma.py` | DTE relax ladder fix (`_update_gamma_cap`) |
| `webui/backend/routes/mmm/mmm_whipsaw_smart.py` | Surgical straddle bypass fix (lines ~697-711) |
| `webui/frontend/src/components/mmm/MMMSettingsDialog.js` | WebUI toggle — "⚖️ Coordination Arbiter (Phase 3 — Live)" in Advanced settings |
| `webui/backend/routes/mmm/tests/test_sealed_audit_fixes.py` | 29 sealed tests covering all arbiter behaviour |
| `MMM_COORDINATION_PLAN.md` | Full design rationale, Phase 2 Q&A, sealed hierarchy |
| `audit/mmm/coordination/` | 7 Phase 1 audit documents (gate map, stale detection, gamma audit, etc.) |

---

## 6. Session State Signals the Arbiter Reads

| Signal | Session key | Freshness key | Written by |
|---|---|---|---|
| Breakeven zone | `_breakeven_zone` | `_breakeven_zone_last_updated_at` | `mmm_breakeven_engine.py` |
| Gamma regime | `_gamma_regime` | `_gamma_regime_last_updated_at` | `mmm_gamma.py` |
| Margin tier | `_margin_tier` | `_margin_tier_last_updated_at` | `mmm_monitor.py` (margin guardian block) |

**Stale escalation maps** (in `mmm_arbiter.py`):
- Breakeven: SAFE → WARNING → DANGER → CRITICAL
- Gamma: NORMAL → SOFT → HARD → EMERGENCY
- Margin: GREEN → YELLOW → ORANGE → RED → CRITICAL

If a signal is stale (> `adjustment_interval * 1.5` seconds old), the arbiter escalates it one tier and logs a `StaleSignal` record.

---

## 7. Params and WebUI

All arbiter params are hot-reloadable (no backend restart needed).

| Param | Default | Description |
|---|---|---|
| `arbiter_enabled` | `True` | Master switch. When False, arbiter is a no-op and legacy behaviour resumes. |
| `gamma_dte_ladder_far_mult` | `1.5` | Gamma cap multiplier for sessions > 5 DTE |
| `gamma_dte_ladder_multi_mult` | `1.25` | Gamma cap multiplier for sessions 1–5 DTE |

**WebUI location**: `MMMSettingsDialog` → Advanced tab → "⚖️ Coordination Arbiter (Phase 3 — Live)" section.

**Disabling**: set `arbiter_enabled=False` in the WebUI. Falls back to un-coordinated legacy behaviour. No restart.

---

## 8. What Was Fixed Alongside the Arbiter

### 8.1 Gamma DTE Relax Ladder
**Problem**: gamma engine treated 5-DTE and 0-DTE sessions identically — false EMERGENCY triggers at 5 DTE.
**Fix** (`mmm_gamma.py`, `_update_gamma_cap`): ladder multiplier applied before near-expiry tightening:
- `minutes_to_expiry > 5 * 24 * 60` → multiply soft/hard/emergency limits by `gamma_dte_ladder_far_mult` (1.5×)
- `minutes_to_expiry > 24 * 60` → multiply by `gamma_dte_ladder_multi_mult` (1.25×)
- Otherwise → 1.0× (existing logic unchanged)

### 8.2 Straddle Whipsaw Bypass (Surgical Fix)
**Problem** (`mmm_whipsaw_smart.py:~697-711`): STRADDLE_WITH_ADJUSTMENT forced `block=False` and skipped token budget entirely — bypassing user-wanted whipsaw protection.
**Fix**: kept the two rationale-backed scalar bypasses (`trigger_widen_factor=1.0`, `lot_scalar=1.0` — prevent under-adjusting/under-hedging the ATM straddle), but removed `block=False` and token budget skip. Whipsaw can still block now; just at ATM-calibrated thresholds.

### 8.3 `_margin_tier` Never Written (Latent Bug)
**Problem**: `_margin_tier` was read in 8+ places (whipsaw, reverse, adaptive…) but never written to session — the default `'GREEN'` or `''` always won, regardless of real margin state.
**Fix** (`mmm_monitor.py`, margin guardian block): added `session['_margin_tier'] = margin_result['tier']` + `record_signal_update(session, 'margin_tier')`.

---

## 9. Sealed Tests (Regression Guards)

File: `webui/backend/routes/mmm/tests/test_sealed_audit_fixes.py`

Key test classes:
- `TestArbiterTier1DefensiveShift` — CRITICAL → defensive_shift decision
- `TestArbiterRule5Last30MinCooldown` — last 30 min → noop
- `TestArbiterRule6StaleEscalation` — stale signal → one-tier escalation
- `TestArbiterTier1GammaEmergency` — gamma EMERGENCY → gamma_emergency_close
- `TestArbiterTier1MarginRecovery` — margin RED → margin_recovery_buyback
- `TestArbiterParamDefaults` — all 3 params present in DEFAULT_PARAMS + HOT_RELOAD_PARAMS
- `TestArbiterShiftBypassesCooldown` — cooldown bypass flag flows from arbiter to `_process_strike_shift`
- `TestArbiterLiveExecutionWired` — **regression guards**:
  - `test_no_shadow_mode_flag`: fails loudly if `arbiter_shadow_mode` is reintroduced
  - `test_execute_arbiter_decision_method_exists`: `_execute_arbiter_decision` present in `mmm_monitor.py`
  - `test_heartbeat_calls_execute`: heartbeat calls `_execute_arbiter_decision`
- `TestGammaDTERelaxLadder` — DTE ladder multipliers applied correctly

**Total MMM-area sealed tests**: 1173 passing, 0 failed (baseline 1144 + 29 new).

---

## 10. Phase 4 Open Items

1. **God Layer coordination**: when both `god_enabled=True` and `arbiter_enabled=True`, arbiter decision should suppress God Layer for that beat. Design: `if session.get('_arbiter_decision_active'): skip God this beat`. See `audit/mmm/coordination/06_god_layer_disposition.md`.

2. **Replay harness**: extend `mmm_whipsaw_replay.py` to consume `_arbiter_last_decision` audit trail. Enables scientific parameter tuning (change → replay 30 sessions → diff outcomes).

3. **Gamma close lot-sizing**: `close_lots = max(1, int(dominant_lots * 0.25))` is a safe starting value. Phase 4 replay will produce data to tune this fraction.

---

## 11. Peer Module: Profit Ratchet

**Context file**: `AI_profit_ratchet_context.md`

### What it does
At each cumulative P&L milestone (every `profit_ratchet_step_usd` dollars, default $10), re-anchors CE and PE trigger snapshots to current premium levels so the algo stays responsive to reversals as profit grows. Off by default, hot-reloadable.

### Execution order relative to arbiter
```
Arbiter evaluates + executes Tier 1 action   ← sets _arbiter_decision_active=True
God Layer
Delta engine
if not _skip_to_pnl:
    Profit Ratchet   ← runs AFTER arbiter
    evaluate_triggers()
```

### Arbiter gate in ratchet (2026-04-28)
When arbiter fires Tier 1, `_arbiter_decision_active=True` is set. The ratchet block checks this flag and **skips** re-anchoring that beat.

**Why**: The arbiter's `defensive_shift` action calls `_process_strike_shift`, which internally calls `update_trigger_snapshots(fill_price)` after the order fills. If the ratchet also ran, it would overwrite the fill-based anchor with the pre-fill market price — discarding the more accurate fill anchor.

**Sealed guard**: `TestProfitRatchetSourcePresence::test_ratchet_skipped_when_arbiter_active` — fails if the `_arbiter_decision_active` check is removed from the ratchet block.

### No other conflicts
- Arbiter reads `_breakeven_zone`, `_gamma_regime`, `_margin_tier` — never trigger snapshots. Ratchet state (`_profit_ratchet_hwm`, `_profit_ratchet_count`) is irrelevant to arbiter decisions.
- HWM guard naturally prevents ratchet from firing during emergencies (P&L is typically declining at Tier 1).
- Ratchet is disabled in `_skip_to_pnl=True` beats (trailing stop etc.) — same gate as arbiter Tier 2/3 path.

---

## 12. Arbiter Behavior — Session mmm28apr26-1 Analysis (2026-04-28)

**Strategy**: Short Strangle 0DTE | **Duration**: ~20 hours | **Result**: +$16.14 (R: $35.95, U: -$17.26, F: -$2.54)

### What the arbiter did: correctly nothing (Tier 2 max)

| Beat | Tier | Trigger | be_zone | gamma | margin | Action |
|---|---|---|---|---|---|---|
| 4 (last) | 2 | no_tier1_condition | WARNING | NORMAL | YELLOW (stale) | NOOP |

The arbiter was a no-op throughout. The session never reached Tier 1:
- Nearest BE distance minimum was ~0.63% (WARNING threshold = 1.0%, CRITICAL = 0.2%)
- Gamma stayed NORMAL/SOFT, never EMERGENCY
- Margin never reached RED

### What actually ran the session (Tier 3 operational modules)
- **13 close_at events**: cleaned cheap-premium CE positions at $13-19 after they decayed (e.g., 100 lots at $44.5 bought back at $18-19)
- **3 strike shifts**: CE followed BTC downward (79400→78800→78000→77200→77000)
- **4 adjustments**: operator-driven sells at good premiums ($74–$125 range)

### One insurance doctrine observation
At 16:07, 100 CE lots were sold at $44.5 on strike 78800. This is the cheap-premium anti-pattern (Rule 4). The positions were later cleaned by close_at. **Had Tier 1 fired at that moment**, the arbiter would instead have done a premium-aware defensive shift at `shift_target_premium=$100` — selling fewer lots at better premium.

### Margin tier stale note
All beats showed `margin_tier` stale (raw=GREEN, escalated to YELLOW). Root cause: session started before the `_margin_tier` write bug fix was deployed. The fix writes `_margin_tier` fresh every beat going forward; new sessions will not show this stale.

---

## 13. Critical User Doctrines (Non-Negotiable)

1. **Survival > earning**: hard stop and ATM shield are absolute and take precedence over any Tier 1 defensive action.
2. **Insurance company doctrine**: sell fewer high-premium policies, not many cheap ones. Contract count is what kills you in a black swan event, not premium value.
3. **Tier 1 acts, doesn't block**: extreme conditions must trigger defensive action, not impose more restrictions.
4. **Last 30 min is cool-down**: no Tier 1 bypass in the final 30 minutes. Operational gates do their job; Tier 0 handles disasters.
5. **Stale data = danger**: a signal not refreshed in the current beat is treated as one tier worse, never silently ignored.

---

## 14. How to Resume Work in a New Session

1. Read `MMM_LAST_3_SESSIONS.md` (required by CLAUDE.md before any MMM work).
2. Read this file.
3. Check `MMM_COORDINATION_PLAN.md` → **Status** table for current phase.
4. Run sealed tests: `python3 -m pytest webui/backend/routes/mmm/tests/ -m sealed -q` from repo root — must be 1191 passing.
5. For Phase 4 God Layer link: add `if session.get('_arbiter_decision_active'): return` at the top of the God Layer block in `_heartbeat_inner`.
6. For Phase 4 replay: extend `mmm_whipsaw_replay.py` to load `data/arbiter_audit_<sid>.jsonl`.

---

## 15. Phase 4 — AI Model Prompt (Live Validation)

> **Use this section when starting any Phase 4 session.** Copy the prompt block below and prepend it to your task description.

### Why Phase 4 Exists (Read This First)

Phase 3 shipped the arbiter in LIVE mode. But as of 2026-04-28, the arbiter has only ever returned NOOP in real trading (session mmm28apr26-1, Tier 2 maximum — BE zone never reached CRITICAL). This means:

- **The three Tier 1 execution paths have never fired a real order.** `defensive_shift`, `gamma_emergency_close`, and `margin_recovery_buyback` are proven only in unit tests, not in live trading.
- **The God Layer coordination gate is missing.** When both `god_enabled=True` and `arbiter_enabled=True` simultaneously, there is no gate. Both can act on the same beat. This is a live production risk.
- **Gamma close lot-sizing is untuned.** `close_lots = max(1, int(dominant_lots * 0.25))` is a safe starting value chosen before any real data existed. Phase 4 replay will produce data to tune this fraction.

Phase 4 live check = first real-world validation that when Tier 1 *does* trigger, the execution paths work correctly without creating double-orders, wrong-side shifts, or orphaned positions.

---

### AI Model Prompt — Phase 4 Live Check Session

```
PHASE 4 LIVE CHECK — MMM Coordination Arbiter

Context documents to read before starting:
1. MMM_LAST_3_SESSIONS.md (mandatory per CLAUDE.md)
2. AI_Arbiter_context.md (this file — sections 1–13 minimum)
3. MMM_COORDINATION_PLAN.md → Status table + Phase 4 section

Baseline verification (run first, do not proceed if this fails):
  python3 -m pytest webui/backend/routes/mmm/tests/ -m sealed -q --tb=short
  Expected: 1191 passed, 0 failed.

Phase 4 tasks (in priority order):

TASK P4-1 — God Layer Coordination Gate [BLOCKING — live risk]
  File: webui/backend/routes/mmm/mmm_monitor.py
  Location: God Layer block inside _heartbeat_inner()
  Action: Add at the TOP of the God Layer block (before any God Layer logic):
    if session.get('_arbiter_decision_active'):
        pass  # arbiter acted this beat — skip God Layer to avoid double-action
  Reference: audit/mmm/coordination/06_god_layer_disposition.md
  Sealed test required: add test confirming God Layer is skipped when
    _arbiter_decision_active=True. Merge into test_sealed_audit_fixes.py.
  Do NOT proceed to P4-2 or P4-3 without this gate in place and sealed.

TASK P4-2 — Live Execution Path Audit (read-only)
  After at least ONE session where Tier 1 fired:
  1. Read webui/backend/data/mmm_activity_log.json — grep for 'arbiter'
  2. Read data/arbiter_audit_<session_id>.jsonl if it exists
  3. Confirm the activity log shows: action_type != 'noop', tier == 1,
     and the correct execution method was called (defensive_shift /
     gamma_emergency_close / margin_recovery_buyback)
  4. Verify no reconciliation mismatch appeared in the same session window
     (grep logs for 'RECONCILIATION' and 'MISMATCH')
  5. Report: which Tier 1 action fired, what the trigger was, did orders
     execute, did the session remain stable afterwards?

TASK P4-3 — Gamma Close Lot-Sizing Review (data-driven)
  Only after P4-2 has produced at least 2 gamma_emergency_close events:
  Current formula: close_lots = max(1, int(dominant_lots * 0.25))
  Review: was 25% too aggressive (session destabilized) or too conservative
    (gamma risk persisted for 3+ beats after close)?
  Sealed rules to preserve:
    - Insurance doctrine (Rule 4): never close more than needed
    - Tier 1 acts (Rule 2): close must be decisive enough to actually reduce
      curvature exposure, not cosmetic
  If adjustment needed: change only the fraction constant, add sealed test
  verifying the new lot-sizing formula, update this document.

TASK P4-4 — Replay Harness (deferred, no live-session dependency)
  File: mmm_whipsaw_replay.py
  Action: extend to load data/arbiter_audit_<sid>.jsonl alongside existing
    whipsaw replay data. Goal: replay historical sessions and diff outcomes
    under different arbiter parameters (e.g. CRITICAL threshold, close_lots fraction).
  This is a tooling task — do NOT touch live heartbeat code for this.

Sealed invariants you must not break:
  - 7 sealed hierarchy rules (Section 3 of this document)
  - No shadow mode reintroduction (test_no_shadow_mode_flag will fail)
  - Ratchet skips when _arbiter_decision_active (test_ratchet_skipped_when_arbiter_active)
  - Tier 0 absolute — God Layer gate must never block Tier 0 logic, only Tier 1

When Phase 4 is complete:
  - All 4 tasks done (or explicitly deferred with rationale)
  - Sealed test count confirmed (run --collect-only to verify)
  - Update MMM_COORDINATION_PLAN.md → Status table: Phase 4 → COMPLETE
  - Update Section 10 of this document to reflect resolved open items
  - Add entry to mmm_workdone_march.md (mandatory per CLAUDE.md)
```

---

### What "Live Check" Means Concretely

| Check | Pass condition | Fail condition |
|---|---|---|
| God Layer gate | `_arbiter_decision_active` check in God Layer block, sealed test passing | God Layer runs on same beat as Tier 1 arbiter action |
| Tier 1 execution | Activity log shows `action_type != noop` + no reconciliation mismatch in same session | Mismatch after Tier 1 fire → order double-counted or missed |
| Gamma lot-sizing | Position count visibly reduced on dominant side after `gamma_emergency_close` | Dominant lots unchanged in next beat → close silently failed |
| Ratchet isolation | No ratchet log entry on same beat as arbiter Tier 1 | Ratchet fires same beat → fill anchor overwritten |
