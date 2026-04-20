# VIPSO (Smart Whipsaw Engine) — Independent Institutional Audit Report

**Audit type:** Read-only institutional review (no code changes)  
**Repository:** `WorkingBot`  
**Audit target:** Smart Whipsaw Engine (VIPSO) + production wiring (monitor/API/UI/tests)  
**Date:** 2026-04-20

---

## 1) Executive Summary

VIPSO’s core detector logic is strong and generally coherent, but production control semantics are currently inconsistent across backend, UI, and docs. The most serious issue is an operator-trust mismatch: `whipsaw_smart_enabled` is treated as non-binding in backend runtime selection, while UI and parameter docs still present it as a final enable gate. In a real-money system, this can lead to incorrect mental models and delayed rollback actions.

The second major issue is control-plane drift: multiple Smart parameters are exposed, validated, and hot-reloadable, but are not actually consumed by runtime logic. This creates “phantom controls” that appear configurable but have no effect.

Third, replay/metrics observability is materially biased for Legacy in current implementation, weakening Smart-vs-Legacy compare confidence.

**Overall verdict:** **Conditionally Ready** (safe only under strict supervised operation and reduced capital until must-fix items are completed).

---

## 2) Scope and Method

This audit reviewed:

- Core engine code (`mmm_whipsaw.py`, `mmm_whipsaw_smart.py`, spot-log, replay)
- Live monitor integration and execution order (`mmm_monitor.py`)
- Parameter defaults, validation, and hot-reload (`mmm_state.py`, `mmm_config.py`)
- Whipsaw API surfaces (`mmm_api.py`)
- Frontend operator controls/status/compare (`MMMSettingsDialog.js`, `MMMSafetyPanel.js`, `MMMWhipsawCompareTab.js`, `MMMDashboard.js`, service/socket/context hooks)
- Whipsaw and adjacent safety tests

Validation included static traceability + targeted runtime probes and test runs.

---

## 3) Readiness Verdict

### Final decision

**Conditionally Ready**

### Why not “Ready”

Because operator-facing control semantics and telemetry are not fully truthful to runtime behavior in critical areas (Smart enable gate semantics, dead parameter knobs, replay bias). In real-money operations, this is a governance and risk-control gap even if core math is sound.

---

## 4) Domain Scorecard

| Domain | Score (10) | Notes |
|---|---:|---|
| Core Smart logic (detectors/modes/gates) | 8.0 | Solid architecture and internal safety mechanisms. |
| Runtime integration in heartbeat path | 7.5 | Strong ordering and explicit block/scalar application; some bypass complexity. |
| Real-money safety controls | 6.5 | Important invariants preserved, but control-plane drift is material. |
| Config/parameter governance | 4.5 | Several exposed controls are currently non-binding. |
| Observability & diagnostics | 5.0 | Compare/replay surfaces exist, but replay bias + placeholder timeline reduce trust. |
| Test quality (whipsaw-specific) | 6.5 | Good unit coverage; limited monitor/API contract coverage. |
| Operator UX accuracy | 5.0 | Status logic partly contradicts runtime semantics. |

---

## 5) What Is Working Well

1. **Smart engine architecture is mature**: detector set, composite scoring, mode transitions, cooldown, token budget, pressure override, and late-session weighting are implemented coherently.
2. **Monitor integration is explicit**:
   - Early per-beat Smart decision caching,
   - Smart block gate after safety handling,
   - Trigger widening merge via `max(...)` (avoids multiplicative over-widening).
3. **Risk-path invariants are preserved**:
   - Hard reverse-mode mutual exclusion branch remains intact,
   - STRADDLE_WITH_ADJUSTMENT bypass logic remains explicit in both engine and monitor application path.
4. **Emergency rollback path exists and works**: `MMM_WHIPSAW_FORCE_LEGACY=1` force-selects Legacy.
5. **Whipsaw test suite breadth is decent** for detector/score/gate/token and parity-level behaviors.

---

## 6) Critical Findings (Must Address)

### C1 — Smart enable-gate semantics are inconsistent across runtime vs UI/docs

**Observed behavior**

- Backend `select_engine()` resolves primary by `whipsaw_engine` (plus env kill-switch), not by `whipsaw_smart_enabled` gate behavior as still described in comments/docs/UI.
- Frontend compare/safety views still compute “Smart active” using `whipsaw_engine === 'SMART' && whipsaw_smart_enabled`.

**Impact**

- Operator can believe Smart is “shadow/inactive” while Smart is actually primary.
- Rollback and incident response can be delayed due to incorrect dashboard interpretation.

**Risk class:** **Critical (governance/operational truth gap)**

---

### C2 — Exposed Smart control knobs are non-binding (dead controls)

**Parameters affected**

- `smart_ws_gate_count_normal`
- `smart_ws_gate_count_defensive`
- `smart_ws_size_scalar_defensive`
- `smart_ws_size_scalar_observe`
- `smart_ws_flip_penalty`

**Observed behavior**

- They are present in defaults, validation, hot-reload sets, and UI.
- Runtime logic uses hardcoded gate requirements and lot scalars in `multi_gate_decide()`.
- Runtime probe with extreme opposite values produced identical decisions.

**Impact**

- False sense of controllability in live risk tuning.
- Operator interventions may appear accepted but do nothing.

**Risk class:** **Critical (control-plane integrity)**

---

## 7) High / Medium / Low Findings

### High

1. **Replay/metrics legacy bias due state reset each beat**
   - Replay sub-session reset clears legacy whipsaw state (`_whipsaw_score`, `_whipsaw_last_checked_idx`, etc.) every beat.
   - This breaks path dependence and tends to under-report Legacy blocks/modes.
   - `/whipsaw/metrics` depends on this replay summary.

2. **Cross-layer semantic drift in comments/tooltips**
   - Backend and frontend texts still describe deprecated Smart gate semantics.
   - Raises operational confusion during incidents.

### Medium

1. **`/whipsaw/shadow-diff` timeline fields are placeholders** (`legacy_score`/`smart_score` returned as `None`).
2. **Insufficient monitor/API contract tests** for:
   - `_beat_whipsaw_decision` ordering,
   - Smart block gate precedence,
   - compare/replay endpoint correctness.

### Low

1. Naming/comment debt in some tests (legacy names reflecting older semantics).
2. UI labeling can imply “Legacy primary” even when runtime mode changes.

---

## 8) Hidden Failure Scenarios

1. **Shadow confidence illusion**  
   Operator disables `whipsaw_smart_enabled` expecting shadow-only behavior, but Smart remains primary.

2. **Parameter tuning no-op during stress**  
   Operator changes gate counts/scalars/flip penalty under volatility spike; behavior stays unchanged.

3. **Biased promotion decision**  
   Replay metrics understate Legacy blocking, making Smart appear overly divergent or better/worse for wrong reasons.

---

## 9) Real-Money Risk Impact

The most meaningful risk here is **not detector math failure**, but **operator control mismatch**:

- If dashboards/docs are semantically wrong, operators can execute wrong mitigations under time pressure.
- In live derivatives systems, control-truth mismatch can be as dangerous as logic bugs.

Positive note: hard safety constructs (kill-switch fallback, mode block path, reverse mutual exclusion, straddle bypass invariants) are visible and robustly coded.

---

## 10) Test Coverage Assessment

### Strengths

- Good unit-level depth across detector math, composite score boundaries, gate outcomes, token budget arithmetic.
- Legacy parity and Smart-vs-shadow behavior tests exist.

### Gaps

- Missing/weak tests for API compare/replay endpoint truthfulness.
- Missing monitor-level integration tests for per-beat ordering and gate precedence.
- No tests ensuring exposed Smart params actually influence decisions.
- No cross-layer contract test ensuring UI state semantics match backend engine selection.

---

## 11) Performance & Stability Notes

- Runtime engine cost appears bounded and acceptable for heartbeat cadence.
- Replay endpoint computes per request; acceptable for moderate beat counts, but correctness should be fixed before using as decision authority.
- No immediate performance red flags found that outweigh correctness concerns.

---

## 12) Operator UX / Control Surface Assessment

The control surface is feature-rich, but trust is degraded by semantic drift:

- Some status components infer Smart activity with old gate logic.
- Settings/tooltips still document outdated gate semantics.
- Compare telemetry can be misleading due replay bias and placeholder timeline fields.

In institutional operations, **truthful controls > rich controls**.

---

## 13) Must-Fix Before Full Production Scale

### P0 (immediate)

1. **Unify Smart primary semantics across backend/UI/docs** (single source of truth).
2. **Resolve dead Smart parameters**: either wire into runtime or remove from defaults/validation/UI/hot-reload.
3. **Fix replay path dependence** so Legacy and Smart are both replayed with faithful state progression.

### P1 (next)

4. Add API and monitor integration tests for whipsaw compare/replay and gate ordering.
5. Add cross-layer contract tests for `whipsaw_engine` / `whipsaw_smart_enabled` semantics.
6. Populate score timeline fields in shadow-diff with real values.

---

## 14) 7-Day Controlled Rollout & Monitoring Plan

If operating before full fixes, use **reduced-size supervised mode** only:

- Day 1–2: strict human-supervised sessions, reduced lot caps.
- Day 3–4: monitor Smart block rate, mode distribution, token depletion, and manual overrides.
- Day 5–6: compare live event logs vs dashboard semantics; verify no status contradictions.
- Day 7: go/no-go decision only after P0 closure evidence.

### Minimum daily checks

- Engine-selection truth check (`whipsaw_engine` vs displayed active state)
- Smart block events and mode transitions vs expected thresholds
- Replay/metrics sanity checks against raw event logs
- Any operator action where param change produced no behavioral change

---

## Evidence Highlights (Run During Audit)

- Whipsaw-focused tests executed: **106 passed** (targeted suite).
- Runtime probe outputs:
  - `ENGINE_WITH_SMART_DISABLED= SMART`
  - Extreme dead-knob parameter flips produced identical decision tuple
  - Replay sample showed `REPLAY_LEGACY_MODES=['NORMAL']` with non-zero Smart blocks

---

### Final Statement

VIPSO’s algorithmic core is promising and close to institutional quality, but operational truth gaps must be closed before full-scale real-money deployment. The path to “Ready” is clear and tractable, with control-plane consistency as the top priority.