# PHASE 09 — WebUI / Parameter Truth Audit
**Lead Agent:** WebUI & Parameter Truth Agent
**Status:** COMPLETE
**Date:** 2026-04-26
**Prior Phases Read:** Phase 01–08

---

## Executive Summary

The parameter system is well-architected. `PARAM_RULES` in `mmm_config.py` provides type coercion, range validation, hot-reload gating, and strategy namespace enforcement in a single structure. The parameter update API has strong guardrails: identity protection, strategy namespace stripping, cross-param interdependency checks on the merged effective config, and IMP-10 cap-raise impact preview. A previously documented gap (A5-13: god layer params absent from PARAM_RULES) is **not confirmed** — those params are present via the F01-P1-009 fix. The primary structural risk is the two independent hot-reload sources (`HOT_RELOAD_PARAMS` set vs `PARAM_RULES hot=True`), which can diverge silently when new params are added.

**WebUI & Parameter Architecture Grade: A-** — well-validated; dual hot-reload source is the main maintenance risk.

---

## 1. PARAM_RULES — Single Validation Source

`PARAM_RULES` in `mmm_config.py` is a dict mapping `param_name → {type, min, max, hot}`:
- `type`: coercion target (int, float, bool, str)
- `min`/`max`: inclusive range (None = no bound)
- `hot`: True if editable while session is running

The F01-P1-009 fix (comment at line 328) explicitly added entries that were in `HOT_RELOAD_PARAMS` but missing from `PARAM_RULES`, including: `shift_cooldown_sec`, `close_at_use_bid`, `gamma_aware_enabled`, `consecutive_critical_threshold`, perp/reversal/asymmetry/direction limiter params, and OTM scaling params.

**Finding A9-01 Correction (Phase 5 A5-13 was incorrect):** God layer params `god_enabled`, `god_check_interval_min`, `god_pnl_threshold`, `god_min_silence_min`, `god_cooldown_min` are present in `PARAM_RULES` (lines 323–327) with appropriate bounds and `hot=True`. Phase 5 finding A5-13 was incorrect — these params were already validated and hot-reloadable via the F01-P1-009 fix.

---

## 2. Two Hot-Reload Sources — Structural Divergence Risk

**Finding A9-01 (P2):** There are two independent authoritative sets for hot-reloadable params:

| Source | Location | Used By |
|--------|----------|---------|
| `HOT_RELOAD_PARAMS` (set, ~180 entries) | `mmm_state.py` | Conceptual documentation; some internal check code |
| `PARAM_RULES` with `hot=True` | `mmm_config.py` | API `validate_params(hot_only=True)` — the enforcing path |

The API uses `PARAM_RULES`. A param in `HOT_RELOAD_PARAMS` but NOT in `PARAM_RULES` cannot be changed via the API while a session is running — `validate_params` silently returns it as unknown. An operator trying to change such a param would receive "No valid parameters to update" and assume the value cannot be changed, when it just needs a `PARAM_RULES` entry.

Known case: `gamma_severity_multiplier_enabled` — explicitly excluded from `HOT_RELOAD_PARAMS` (commented in mmm_state.py as "NOT hot-reloadable") and absent from PARAM_RULES. This is intentional. However, the F01-P1-009 fix shows the pattern of accidental omission is real; any future param added to DEFAULT_PARAMS + HOT_RELOAD_PARAMS without a PARAM_RULES entry will silently fail API update while running.

---

## 3. Parameter Update Endpoint — `PATCH /api/mmm/session/<id>/params`

### 3.1 Guardrail Pipeline

```
1. Reject if session not found
2. Strategy identity check — reject if dte_category, strategy_type, expiry (running), _preset_source change
3. Strategy namespace strip — silent WARNING on forbidden params (not hard error)
4. validate_params(data, hot_only=is_running) — type coerce + range + hot gate
5. Cross-param interdependency check on MERGED effective config
6. IMP-10 cap raise warning preview (max_lots_per_side raise while running)
7. Auto-sync max_total_exposure if max_lots_per_side raised (prevents silent blocker)
8. Apply to session + save + hot-reload to live monitor
```

### 3.2 Strategy Identity Protection

Protected params (cannot be changed on existing session):
- `dte_category` — determines strategy type; immutable after creation
- `strategy_type` — top-level identity
- `expiry` — immutable while session is running (would leave positions at wrong strike)
- `_preset_source` — internal field; always stripped

### 3.3 Strategy Namespace Enforcement

`STRATEGY_PARAM_NAMESPACES` defines forbidden param sets per strategy:
- `0DTE`/`5DTE`/`SHORT_WINDOW`: forbid all straddle-roll control surface params
- `STRADDLE_WITH_ADJUSTMENT`: forbids pure-roll-only params (`straddle_roll_hard_stop_market_order`, `straddle_dynamic_trigger_enabled`, `straddle_min_trigger_pts`)
- `STRADDLE_ROLL`: forbids all adjustment-engine params (~50 params: trigger, shift, whipsaw, harvest, M1/M2/M3, ATM shield, etc.)

**Finding A9-02 (P2):** Forbidden params are **silently stripped** (WARNING log, not 400 error) when mixed with valid params in the same request. If ALL submitted params are forbidden → 400 error with details. If SOME are forbidden → silent strip, response contains `changed_keys` showing what actually changed, but the UI may not surface the warning prominently to the operator. An operator editing multiple params across a STRADDLE_ROLL-forbidden boundary might believe all params were applied.

Note: The `_ADJUSTMENT_ENGINE_ONLY_PARAMS` set (STRADDLE_ROLL forbidden) contains ~50 entries but does NOT include all adjustment-related params (e.g., `trend_*`, `breakeven_*`, `gamma_cap_*` are not forbidden for STRADDLE_ROLL). These params have no effect on STRADDLE_ROLL sessions but are still settable — silent dead weight.

### 3.4 Cross-Param Interdependency Checks

`_interdependency_checks()` runs on `{**current_params, **validated}` — the MERGED effective config, not just submitted keys. This prevents a single-key patch from silently violating a constraint with an existing param (e.g., raising `whipsaw_caution_score` above `whipsaw_restrict_score` without changing `restrict_score`). This is a strong design.

### 3.5 IMP-10 Cap Raise Preview

When `max_lots_per_side` is raised while running, the response includes a `cap_raise_warning` with:
- Old/new cap values
- Current CE/PE lot counts
- Current unrealized P&L
- Current asymmetry ratio
- Human-readable message noting that raising PE cap does not reduce CE exposure

### 3.6 max_total_exposure Auto-Sync

If the new `max_lots_per_side` would exceed the existing `max_total_exposure` ceiling, `max_total_exposure` is auto-raised to `new_lots_per_side × 2`. This prevents the silent blocker where an operator raises the per-side cap but adjustments continue failing with "Total exposure ceiling" due to a stale global cap.

---

## 4. `validate_params()` Logic

```python
def validate_params(params, hot_only=False):
    validated = {}
    errors = []
    for key, value in params.items():
        if key not in PARAM_RULES:
            continue  # silently skip unknown
        rule = PARAM_RULES[key]
        if hot_only and not rule.get('hot'):
            continue  # silently skip non-hot params when running
        # Type coerce + range check
        ...
```

Unknown params are silently skipped (not errors). Non-hot params when `hot_only=True` are silently skipped. Only type errors and out-of-range values produce error entries. This is correct behavior — unknown params from old UI versions don't break saves.

**Finding A9-03 (P3):** There is no validation of `expiry` format in `PARAM_RULES` for the `expiry` param (defined as `{'type': str, 'min': None, 'max': None, 'hot': False}`). The API separately normalizes expiry via `normalize_expiry()` at session creation, but the PARAM_RULES for `expiry` has no regex or format validator. An invalid expiry string (e.g., "INVALID") passes type validation. Runtime failures would occur when the symbol builder tries to construct an option symbol from it. This is not a hot-reload risk (expiry is `hot=False`), but a session creation path risk.

---

## 5. Architecture Issues — Phase 9

| ID | Problem | Risk | Priority |
|---|---|---|---|
| A9-01 | Two independent hot-reload sets (`HOT_RELOAD_PARAMS` + `PARAM_RULES hot=True`); can diverge silently on new param addition | Operator cannot change a param via API while running; gets confusing "No valid parameters" error | P2 |
| A9-02 | Forbidden-for-strategy params silently stripped (not hard error) on mixed-valid+forbidden requests | Operator believes all params were applied; some silently dropped | P2 |
| A9-03 | `expiry` param has no format validation in `PARAM_RULES` | Invalid expiry string creates broken session; runtime failure at symbol construction | P3 |

---

## 6. Phase 5 A5-13 Correction

**Phase 5 Finding A5-13 (P1): "god_check_interval_min/min_silence/cooldown absent from PARAM_RULES" — INCORRECT.**

These params are present in `PARAM_RULES` (lines 323–327, comment "F01-P1-009 fix"). The finding was based on incomplete reading. These params are:
- `god_enabled`: bool, hot=True
- `god_check_interval_min`: int, min=5, max=120, hot=True
- `god_pnl_threshold`: float, min=1.0, max=500.0, hot=True
- `god_min_silence_min`: int, min=1, max=120, hot=True
- `god_cooldown_min`: int, min=5, max=240, hot=True

A5-13 should be closed with **RESOLVED** status.

---

## 7. Positive Findings

1. **PARAM_RULES is the single enforcing validation source** — type coercion, range, hot-reload, and strategy namespace all derived from one structure
2. **God layer params fully covered** — A5-13 false alarm; all 5 god params validated with bounds and hot=True
3. **F01-P1-009 fix** — systematic audit identified and closed HOT_RELOAD_PARAMS/PARAM_RULES gap
4. **Cross-param interdependency on merged config** — single-key patches cannot silently violate constraints with existing params
5. **IMP-10 cap raise warning** — operator gets current lots, unrealized P&L, asymmetry ratio before applying
6. **max_total_exposure auto-sync** — prevents silent "Total exposure ceiling" blocker after per-side cap raise
7. **Strategy namespace enforcement** — STRADDLE_ROLL cannot accidentally enable adjustment-engine behavior via API; 0DTE cannot set straddle-roll control surface
8. **Strategy identity immutability** — dte_category, strategy_type, expiry (running), _preset_source all blocked from mutation on existing sessions
9. **Unknown params silently skipped** — old UI payload keys from deprecated params don't break saves
10. **_watchdog_restarts reset on resume** — confirmed in Phase 7; also confirmed here via API code reading

---

## 8. Pass Criteria Checklist

- [x] PARAM_RULES validated as single enforcing source (type, range, hot, strategy namespace)
- [x] God layer params confirmed in PARAM_RULES — A5-13 Phase 5 finding corrected
- [x] Hot-reload dual-source divergence risk documented (A9-01)
- [x] Strategy namespace enforcement verified (forbidden sets per strategy)
- [x] Cross-param interdependency check on merged config confirmed
- [x] Identity param protection verified
- [x] IMP-10 cap raise warning and auto-sync verified
- [x] Architecture Issue Register updated (Section 5)

**Phase 9 Status: PASSED. Two P2 gaps documented. A5-13 from Phase 5 closed as resolved.**
