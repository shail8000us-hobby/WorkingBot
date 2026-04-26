# Whipsaw Control-Plane Audit Report

**Date:** 2026-04-20  
**Scope:** All VIPSO/Smart Whipsaw WebUI settings, backend params, hot-reload state flow, validators, engine selector, and runtime decision logic  
**Method:** Full trace — WebUI param → API PATCH → storage → monitor hot-reload → `select_engine()` / `engine.evaluate()` → live decision output  
**Test baseline before:** 1562 passed  
**Test baseline after:** 1624 passed (+62 new, 0 regressions)

---

## Hot-Reload Path (verified correct, no changes needed)

```
Operator changes param in WebUI
  → PATCH /api/mmm/session/<id>/params
    → validate_params() (mmm_config.py)
    → storage.save_session()
  → monitor _run_loop() top-of-cycle: fresh_session = storage.get_session()
  → self.session = fresh_session  ← params live on NEXT heartbeat, no restart
  → _heartbeat() → whipsaw_decide() → select_engine(session) → engine.evaluate(session, ctx)
  → session['params'] contains updated value → decision reflects new param immediately
```

Hot-reload works correctly for every `hot: True` param. No fixes needed to this path.

---

## Complete Param Wiring Audit

### Engine Selector Params

| Param | Default | Runtime path | Status |
|---|---|---|---|
| `whipsaw_engine` | `'SMART'` | `select_engine()` → `WHIPSAW_ENGINE_DISPATCH[engine_name]` | ✅ Wired |
| `whipsaw_engine_shadow` | `False` | `_maybe_run_shadow()` shadow enable gate | ✅ Wired |
| `whipsaw_smart_enabled` | `True` | **Was read but never used in any conditional** | ❌ Dead → deprecated |

### Smart Engine Score Thresholds

| Param | Default | Runtime path | Status |
|---|---|---|---|
| `smart_ws_score_defensive` | `0.30` | `mode_from_score(defensive=...)` | ✅ Wired |
| `smart_ws_score_observe` | `0.60` | `mode_from_score(observe=...)` | ✅ Wired |
| `smart_ws_score_lockdown` | `0.80` | `mode_from_score(lockdown=...)` | ✅ Wired |

### Token Budget

| Param | Default | Runtime path | Status |
|---|---|---|---|
| `smart_ws_tokens_per_session` | `10.0` | `_load_budget(tokens_per_session=...)` | ✅ Wired |
| `smart_ws_token_refresh_per_hour` | `1.0` | `_load_budget(refresh_per_hour=...)` → per-beat drip | ✅ Wired |

### Gate Counts (previously dead — wired 2026-04-20)

| Param | Default | Runtime path | Status |
|---|---|---|---|
| `smart_ws_gate_count_normal` | `3` | `multi_gate_decide() → gate_normal = params.get(...)` | ✅ Wired (fixed) |
| `smart_ws_gate_count_defensive` | `4` | `multi_gate_decide() → gate_def = params.get(...)` | ✅ Wired (fixed) |

### Size Scalars (previously dead — wired 2026-04-20)

| Param | Default | Runtime path | Status |
|---|---|---|---|
| `smart_ws_size_scalar_defensive` | `0.5` | `multi_gate_decide() → scalar_def = params.get(...)` | ✅ Wired (fixed) |
| `smart_ws_size_scalar_observe` | `0.25` | `multi_gate_decide() → scalar_obs = params.get(...)` | ✅ Wired (fixed) |

### Flip Penalty (previously dead — wired 2026-04-20)

| Param | Default | Runtime path | Status |
|---|---|---|---|
| `smart_ws_flip_penalty` | `0.5` | `evaluate() → lot_scalar *= flip_penalty ** flip_count` | ✅ Wired (fixed) |

### Detector Tuning

| Param | Default | Runtime path | Status |
|---|---|---|---|
| `smart_ws_flip_window_mins` | `30` | `flip_counter_score(window_mins=...)` | ✅ Wired |
| `smart_ws_er_window_mins` | `30` | `efficiency_ratio_score` window series slice | ✅ Wired |
| `smart_ws_oscillation_sensitivity_pct` | `0.15` | `oscillation_score(sensitivity_pct=...)` | ✅ Wired |
| `smart_ws_rv_iv_ratio_floor` | `0.6` | `rv_iv_divergence_score(rv_iv_floor=...)` | ✅ Wired |

### Cooldown & Late Session

| Param | Default | Runtime path | Status |
|---|---|---|---|
| `smart_ws_cooldown_base_beats` | `1` | `compute_cooldown_beats(base_beats=...)` | ✅ Wired |
| `smart_ws_late_session_relax_mins` | `180` | `_late_session = dte is not None and 30 < dte <= relax_mins` | ✅ Wired |

### Legacy Engine Params (verified correct)

| Param | Default | Runtime path | Status |
|---|---|---|---|
| `whipsaw_window_mins` | `30` | `check_whipsaw()` rolling window | ✅ Wired |
| `whipsaw_spot_move_pct` | `0.3` | `check_whipsaw()` noise filter | ✅ Wired |
| `whipsaw_caution_score` | `2` | `check_whipsaw()` + `LegacyWhipsawEngine.evaluate()` mode + widen | ✅ Wired |
| `whipsaw_restrict_score` | `3` | `check_whipsaw()` + lot_scalar=0.5 gate | ✅ Wired |
| `whipsaw_cooldown_score` | `4` | `check_whipsaw()` + block gate | ✅ Wired |

---

## Bugs Found and Fixed

### Bug 1 (C2-a): `smart_ws_gate_count_normal` — dead control

**Root cause:** `multi_gate_decide()` hardcoded `required = 4 if mode == 'DEFENSIVE' else 3`. The param existed in DEFAULT_PARAMS, PARAM_RULES, HOT_RELOAD_PARAMS, and UI but was never read.

**Before:** Changing `smart_ws_gate_count_normal` from 3 → 5 produced identical decision output.

**After:** `required = gate_def if mode == 'DEFENSIVE' else gate_normal` where `gate_normal = int(params.get('smart_ws_gate_count_normal', 3))`.

**Files:** `mmm_whipsaw_smart.py` (`multi_gate_decide`)

---

### Bug 2 (C2-b): `smart_ws_gate_count_defensive` — dead control

Same root cause as Bug 1. Hardcoded `4` for DEFENSIVE mode.

**Files:** `mmm_whipsaw_smart.py` (`multi_gate_decide`)

---

### Bug 3 (C2-c): `smart_ws_size_scalar_defensive` — dead control

**Root cause:** `multi_gate_decide()` hardcoded `lot_scalar = 0.5` in DEFENSIVE mode.

**Before:** Changing to 0.9 had no effect. Sessions in DEFENSIVE mode always got 0.5× sizing.

**After:** `lot_scalar = scalar_def` where `scalar_def = float(params.get('smart_ws_size_scalar_defensive', 0.5))`.

**Files:** `mmm_whipsaw_smart.py` (`multi_gate_decide`)

---

### Bug 4 (C2-d): `smart_ws_size_scalar_observe` — dead control

**Root cause:** `multi_gate_decide()` hardcoded `return True, 2.0, 0.25, events` for OBSERVE mode.

**After:** `return True, 2.0, scalar_obs, events` where `scalar_obs = float(params.get('smart_ws_size_scalar_observe', 0.25))`.

**Files:** `mmm_whipsaw_smart.py` (`multi_gate_decide`)

---

### Bug 5 (C2-e): `smart_ws_flip_penalty` — dead control (entire mechanism unimplemented)

**Root cause:** Param existed with description "per-flip lot size multiplier (applied exponentially)" but was never read anywhere in the engine. Flip penalty = 0 effect regardless of value.

**After:** Applied in `evaluate()` after `multi_gate_decide()`:
```python
flip_count_approx = int(flip_sc * 3)
flip_penalty_val  = float(params.get('smart_ws_flip_penalty', 0.5))
if not is_straddle_adj and flip_count_approx > 0 and flip_sc > 0.1 and lot_scalar > 0:
    lot_scalar = max(0.1, lot_scalar * (flip_penalty_val ** flip_count_approx))
```

**Files:** `mmm_whipsaw_smart.py` (`evaluate`)

---

### Bug 6 (C1): `whipsaw_smart_enabled` — dead variable in `_maybe_run_shadow()`

**Root cause:** `_maybe_run_shadow()` read `smart_enabled = params.get('whipsaw_smart_enabled', False)` and `engine_param = params.get('whipsaw_engine', DEFAULT_ENGINE)` but neither variable appeared in any conditional. The docstring described intended shadow-routing logic that was never implemented.

**Decision:** Deprecated `whipsaw_smart_enabled`. Single source of truth for engine selection is `whipsaw_engine`. This matches the existing Phase-6 test (`test_smart_without_smart_enabled_is_shadow`) which already documented this as the intended design.

**Before:**
```python
engine_param   = params.get('whipsaw_engine', DEFAULT_ENGINE)   # read, never used
smart_enabled  = params.get('whipsaw_smart_enabled', False)     # read, never used
shadow_enabled = params.get('whipsaw_engine_shadow', False)
```

**After:** Removed both dead variables. Only `shadow_enabled` controls shadow routing.

**Files:** `mmm_whipsaw.py` (`_maybe_run_shadow`)

---

### Bug 7 (C1): UI displayed `whipsaw_smart_enabled` as a live operator control

**Root cause:** `MMMSettingsDialog.js` safety group included `whipsaw_smart_enabled` in its params list. Operators could change a param that had zero runtime effect.

**Fix:** Removed from UI params list. Param retained in DEFAULT_PARAMS/PARAM_RULES for session backward compat (old sessions won't crash); changing it via API is still accepted but has no effect.

**Files:** `MMMSettingsDialog.js`

---

### Bug 8 (C1): Stale description strings

`mmm_config.py` descriptions for `whipsaw_engine` still said "requires `whipsaw_smart_enabled=True` to bind" and `whipsaw_smart_enabled` still claimed to be a "final gate". Updated both to reflect actual behavior.

**Files:** `mmm_config.py`

---

### Bug 9 (High-1): Replay biased against Legacy (stateless per-beat reset)

**Root cause:** `_sub_session()` cleared `_whipsaw_score`, `_whipsaw_state`, `_whipsaw_last_checked_idx` on every replay beat. Legacy engine needs score to accumulate (0→1→2→3→4=block) across beats to fire. Resetting per-beat means Legacy almost never blocks in replay → block count systematically under-reported.

**Fix:** `replay_session()` now uses stateful running copies (`state_a`, `state_b`) via `_build_replay_state()`. State accumulates across beats exactly as in production.

**Files:** `mmm_whipsaw_replay.py`

---

### Bug 10 (C1): Frontend components used `whipsaw_smart_enabled` as active-state gate

**Root cause:** `MMMWhipsawCompareTab.js:125` computed `isSmartActive = wsEngine === 'SMART' && smartEnabled` and `MMMSafetyPanel.js:277` computed `isSmartPrimary = params.whipsaw_engine === 'SMART' && params.whipsaw_smart_enabled !== false`. Both wrongly implied that Smart could be inactive while `whipsaw_engine=SMART`.

**Fix:** Both now use `wsEngine === 'SMART'` / `params.whipsaw_engine === 'SMART'` only.

**Files:** `MMMWhipsawCompareTab.js`, `MMMSafetyPanel.js`

---

## Files Changed

| File | Change |
|---|---|
| `mmm_whipsaw_smart.py` | Wire gate counts, size scalars from params; implement flip_penalty; move `flip_count_approx` earlier |
| `mmm_whipsaw.py` | Remove dead `smart_enabled`/`engine_param` from `_maybe_run_shadow()`; update docstrings |
| `mmm_whipsaw_replay.py` | Stateful accumulation in `replay_session()`; add `_build_replay_state()` |
| `mmm_config.py` | Update descriptions for `whipsaw_engine` and `whipsaw_smart_enabled` |
| `mmm_state.py` | Deprecation comment on `whipsaw_smart_enabled` |
| `MMMSettingsDialog.js` | Remove `whipsaw_smart_enabled` from safety group params |
| `MMMWhipsawCompareTab.js` | `isSmartActive` uses `whipsaw_engine` only |
| `MMMSafetyPanel.js` | `isSmartPrimary` uses `whipsaw_engine` only |
| `MMMStatusBanner.js` | `isSmartPrimary` uses `whipsaw_engine` only (fixed prior session) |
| `tests/test_mmm_whipsaw_wiring.py` | **New file** — 62 param→live-decision proof tests |

---

## Tests Added (62 new)

| Class | Tests | What is proven |
|---|---|---|
| `TestEngineSelector` | 6 | `whipsaw_engine` changes live engine; `whipsaw_smart_enabled` is inert; kill-switch overrides all |
| `TestGateCounts` | 8 | Changing gate count alone flips block/allow in NORMAL and DEFENSIVE mode |
| `TestSizeScalars` | 7 | Changing scalar changes `lot_scalar` in DEFENSIVE, OBSERVE, LOCKDOWN |
| `TestFlipPenalty` | 4 | `flip_penalty=1.0` → no reduction; `0.5` → halved; no flips → no effect |
| `TestScoreThresholds` | 7 | Threshold changes change mode; `mode_from_score()` reflects params directly |
| `TestTokenBudget` | 4 | Near-zero budget blocks; budget decrements; halved budget halves beats-to-block |
| `TestTokenRefresh` | 2 | Refresh=0 no drip; positive refresh prevents starvation |
| `TestCooldownBase` | 2 | `cooldown_base_beats` reflected in trace |
| `TestDetectorWindows` | 3 | `flip_window_mins` narrows flip history; windows consumed without crash |
| `TestOscillationSensitivity` | 2 | Low sensitivity detects small moves; param consumed |
| `TestRvIvFloor` | 2 | Floor param consumed; higher floor → equal or higher divergence score |
| `TestLateSessionWeights` | 3 | `relax_mins` controls DTE window; `late_session` trace flag correct |
| `TestHotReload` | 4 | Same session object, changed param → changed decision (no restart needed) |
| `TestLegacyParams` | 2 | Legacy caution/restrict params consumed correctly |
| `TestWiringCompleteness` | 6 | All Smart params in `HOT_RELOAD_PARAMS` and `PARAM_RULES` with `hot=True`; `whipsaw_smart_enabled` inert in all 6 combinations |

---

## Remaining Risks

| Risk | Severity | Status |
|---|---|---|
| `shadow-diff` timeline `legacy_score`/`smart_score` are `None` placeholders | Low | **Open** — requires per-beat score storage during live operation; display-only, no trading impact |
| Missing monitor/API integration tests for beat ordering | Low | **Open** — test gap, not a runtime bug |
| `smart_ws_gate_count_*` asymmetric-thinner-side rule adds +1 to required: if `gate_count_defensive=5`, this becomes 6 which is clamped to 5 — correct, but not explicitly tested | Very Low | Capped correctly with `min(required, 5)` |

---

## Verdict

All P0 control-plane bugs are closed. Every Smart Whipsaw parameter that appears in the WebUI now affects live runtime behavior on the next heartbeat without restart. The single source of truth for engine selection is `whipsaw_engine`. Dead controls have been removed from the UI or deprecated with documentation.

**Before this audit:** 5 params were phantom controls; 1 param had a dead variable in the shadow dispatcher; UI/backend semantics disagreed on what `whipsaw_smart_enabled` meant; replay under-reported Legacy blocks.

**After this audit:** 0 phantom controls remain. All 18 Smart params + 5 Legacy params are wired, validated, hot-reloadable, and test-proven.
