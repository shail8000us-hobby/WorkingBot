# SMART WHIPSAW ENGINE — Phased Implementation & Wiring Plan
**Goal:** build a new Smart Whipsaw engine in parallel with the existing (legacy) whipsaw logic, behind a WebUI switch, with zero regression risk to any other MMM module.

**Audience:** any coding AI (Claude / GPT / Copilot) executing the plan. Rules are explicit so the AI cannot drift. Every step declares the files it touches, the invariants it must not break, and the tests it must pass.

**Source of truth for strategy content:** [WHIPSAW_INTELLIGENCE_UPGRADE.md](WHIPSAW_INTELLIGENCE_UPGRADE.md)
**Repo invariants that must never break:** [CLAUDE.md](CLAUDE.md), `CLAUDE.md §0 self-check`, `CLAUDE.md §4 stale-monitor 3-layer fix`, `CLAUDE.md §5 reverse-mode if/else`.

---

## 0. Non-negotiable ground rules (read first, every phase)

1. **Legacy whipsaw is frozen.** You may *extract* it into a wrapper, but you may not change a single line of its decision logic, state keys, thresholds, or event output during Phases 0–4. Phase 6 is the earliest a change to legacy behavior could even be considered — and even then, only by operator promotion, not by code.
2. **State key isolation.** Legacy writes to `_whipsaw_*` session keys. Smart writes **only** to `_smart_ws_*` keys. Never cross-write. On engine switch, neither engine touches the other's state.
3. **Default engine = `LEGACY`.** Every new param, every new feature flag, every new code path must default to the legacy behavior. A fresh install, a restored session, a missing param — all must resolve to legacy.
4. **One decision, one engine.** The dispatcher is the single entry point. Only the *active* engine returns a binding `WhipsawDecision`. The non-active engine may run in *shadow mode* (observe + log only).
5. **Mutex in the UI.** Legacy ON ⇒ Smart OFF. Smart ON ⇒ Legacy OFF. The param `whipsaw_engine` is a single enum (`LEGACY | SMART | OFF`), not two bools — this makes mutex impossible to violate.
6. **No cross-strategy bleed.** `STRADDLE_WITH_ADJUSTMENT` already bypasses legacy whipsaw widening/lot-reduction in [mmm_monitor.py:3356-3363](webui/backend/routes/mmm/mmm_monitor.py#L3356-L3363) and [mmm_monitor.py:4918-4929](webui/backend/routes/mmm/mmm_monitor.py#L4918-L4929). The Smart engine must honor the same bypass (gate via `STRATEGY_DISPATCH` flag), not re-introduce the cross-strategy bug.
7. **Real-money bot.** Before *any* file write that touches `mmm_monitor.py`, `mmm_engine.py`, `mmm_constants.py`, or anything in `webui/backend/routes/mmm/`, state the exact lines changing, the pre value, the post value. If uncertain — stop and ask. (CLAUDE.md §0.)
8. **Baseline test count.** The sealed test baseline is **1312 passing** (2026-03-31). Every phase must end with **≥1312 passing** plus all new tests added in that phase. If any sealed test breaks, stop and report — do not silently fix.
9. **Hot reload.** All new params **must** be added to both `DEFAULT_PARAMS` (in `mmm_state.py`) and `HOT_RELOAD_PARAMS` (same file). Missing from the second list means the param silently ignores UI edits. This is a trap.
10. **Rollback in one flip.** The operator must be able to return to pure legacy behavior by setting a single dropdown in the WebUI, with no backend restart required (hot reload). An env-var kill-switch (`MMM_WHIPSAW_FORCE_LEGACY=1`) overrides the param and is checked on every decision.

---

## 1. Current-state inventory (what exists today)

### 1.1 Legacy whipsaw integration points (DO NOT MOVE OR EDIT in Phase 0–1)

| # | File | Lines | Role |
|---|---|---|---|
| A | [mmm_safety.py](webui/backend/routes/mmm/mmm_safety.py) | `check_whipsaw()` ~322–end | Core score logic: count alternations in window, decay, produce `events[]` with `action in {'stop_adjustments','resume','warn'}` |
| B | [mmm_safety.py](webui/backend/routes/mmm/mmm_safety.py) | ~65 `check_whipsaw` call inside `run_safety_checks` | Invocation point per heartbeat |
| C | [mmm_monitor.py:3338-3363](webui/backend/routes/mmm/mmm_monitor.py#L3338-L3363) | Trigger widening | Multiplies `_effective_min_trigger_move` by 1.5× (CAUTION) or 2.0× (RESTRICT) |
| D | [mmm_monitor.py:4918-4929](webui/backend/routes/mmm/mmm_monitor.py#L4918-L4929) | Lot reduction at RESTRICT | Halves `lots` when `_whipsaw_score ≥ whipsaw_restrict_score` |
| E | [mmm_monitor.py:2628-2670](webui/backend/routes/mmm/mmm_monitor.py#L2628-L2670) | `stop_adjustments` honoring + auto-resume | Pauses adjustments on COOLDOWN, resumes after interval |
| F | [mmm_api.py:1601-1621](webui/backend/routes/mmm/mmm_api.py#L1601-L1621) | Manual resume | Clears `_whipsaw_paused_at`, `_whipsaw_consecutive_alternating` on operator resume |
| G | [mmm_audit_log.py:246](webui/backend/routes/mmm/mmm_audit_log.py#L246) | `whipsaw_state` audit field | Written at every `execute_adjustment` |

### 1.2 Legacy session state keys (read + write)

```
_whipsaw_score               int
_whipsaw_state               str   ('NORMAL' | 'CAUTION' | 'RESTRICT' | 'COOLDOWN')
_whipsaw_last_noise_at       ISO
_whipsaw_skip_until          ISO
_whipsaw_last_checked_idx    int
_whipsaw_trigger_widened     bool  (set by monitor line 3363)
```
(Plus legacy-migration keys `_whipsaw_paused_at`, `_whipsaw_checked_up_to`, `_whipsaw_consecutive_alternating` — cleared on migration in `check_whipsaw`.)

### 1.3 Legacy params (in `DEFAULT_PARAMS` + `HOT_RELOAD_PARAMS`, validated in `mmm_config.py`)

- `whipsaw_limit` (int, DEPRECATED alias)
- `whipsaw_window_mins` (int, default 30)
- `whipsaw_spot_move_pct` (float, default 0.3)
- `whipsaw_caution_score` (int, default 2)
- `whipsaw_restrict_score` (int, default 3)
- `whipsaw_cooldown_score` (int, default 4)

### 1.4 Frontend surfaces

- [MMMSettingsDialog.js](webui/frontend/src/components/mmm/MMMSettingsDialog.js) — param UI with HOT badges, warning blurbs
- [MMMStatusBanner.js](webui/frontend/src/components/mmm/MMMStatusBanner.js) — shows `_whipsaw_state` badge
- [MMMSafetyPanel.js](webui/frontend/src/components/mmm/MMMSafetyPanel.js) — shows whipsaw events
- [MMMDashboard.js](webui/frontend/src/components/mmm/MMMDashboard.js) — tab layout

### 1.5 Existing dispatch pattern we will mimic

[mmm_strategy_dispatch.py](webui/backend/routes/mmm/mmm_strategy_dispatch.py) — table-driven handler selection. Same shape will be reused for `WHIPSAW_ENGINE_DISPATCH`.

---

## 2. Target architecture (end state)

```
┌──────────────────────────────────────────────────────────────────┐
│                      mmm_monitor.py heartbeat                    │
│                                                                  │
│   ... Step 4.5 ─────► whipsaw_decide(session, ctx)               │
│   ... Step 6  ─────►    .trigger_widen_factor                    │
│   ... Step 7  ─────►    .lot_scalar / .block_adjustment          │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
      ┌───────────────────────────────────────────────┐
      │         mmm_whipsaw.py  (dispatcher)          │
      │                                               │
      │   def whipsaw_decide(session, ctx):           │
      │       engine = select_engine(session)         │
      │       primary  = engine.evaluate(...)         │
      │       shadow   = maybe_run_shadow(...)        │
      │       log_trace(primary, shadow)              │
      │       return primary                          │
      └───────────────────────────────────────────────┘
                 │                         │
                 ▼                         ▼
      ┌────────────────────────┐  ┌────────────────────────┐
      │ LegacyWhipsawEngine    │  │ SmartWhipsawEngine     │
      │ (pure wrapper around   │  │ (new, in               │
      │  mmm_safety.check_     │  │  mmm_whipsaw_smart.py) │
      │  whipsaw + legacy      │  │                        │
      │  widen + legacy        │  │ - 7-detector panel     │
      │  lot-reduce)           │  │ - whipsaw score        │
      │                        │  │ - 4-mode state machine │
      │ state: _whipsaw_*      │  │ - token budget         │
      │                        │  │ - multi-gate trigger   │
      │                        │  │ state: _smart_ws_*     │
      └────────────────────────┘  └────────────────────────┘
```

### 2.1 Decision contract

Both engines return the same dataclass:

```python
@dataclass(frozen=True)
class WhipsawDecision:
    engine:              str             # 'LEGACY' | 'SMART' | 'OFF'
    block_adjustment:    bool            # equivalent to legacy stop_adjustments
    trigger_widen_factor: float          # 1.0 = no change; applied in monitor.py:3338
    lot_scalar:          float           # 1.0 = no change; applied in monitor.py:4918
    score:               float           # 0–1 (SMART) or raw int (LEGACY); display only
    mode:                str             # LEGACY: NORMAL/CAUTION/RESTRICT/COOLDOWN
                                         # SMART:  NORMAL/DEFENSIVE/OBSERVE/LOCKDOWN
    events:              Tuple[dict,...] # passthrough to websocket + audit
    trace:               dict            # structured debug — goes to _whipsaw_trace
```

No other module reads anything outside this dataclass. That is the entire public surface.

### 2.2 Engine protocol (exact interface)

```python
class WhipsawEngine(Protocol):
    name: str  # 'LEGACY' | 'SMART' | 'OFF'
    def evaluate(
        self,
        session: dict,
        ctx: "WhipsawCtx",           # dataclass: ce_now, pe_now, spot, iv, heartbeat_ts, recent_fills
    ) -> WhipsawDecision: ...
    def reset_state(self, session: dict) -> None: ...  # called on engine switch
```

### 2.3 Engine table

```python
# mmm_whipsaw.py
WHIPSAW_ENGINE_DISPATCH: Dict[str, WhipsawEngine] = {
    'LEGACY': LegacyWhipsawEngine(),
    'SMART':  SmartWhipsawEngine(),
    'OFF':    NullWhipsawEngine(),  # returns a no-op decision (all 1.0, block=False)
}
DEFAULT_ENGINE = 'LEGACY'
```

### 2.4 Env kill-switch (emergency rollback)

```python
# mmm_whipsaw.py::select_engine()
if os.environ.get('MMM_WHIPSAW_FORCE_LEGACY') == '1':
    return WHIPSAW_ENGINE_DISPATCH['LEGACY']
```

Checked on every decision. The operator can `export MMM_WHIPSAW_FORCE_LEGACY=1` and the next heartbeat honors it — no code change, no UI click. Verified by a unit test.

---

## 3. Phase plan (execute in strict order; each phase is independently shippable)

### STATUS AS OF 2026-04-19

| Phase | Status | Test count | Notes |
|---|---|---|---|
| 0 | ✅ DONE | — | Baseline confirmed: 1456 passing (actual) |
| 1 | ✅ DONE | 1465 (+9) | `mmm_whipsaw.py` created; monitor wired; 9 parity tests pass |
| 2 | ✅ DONE | 1470 (+5) | Params added; select_engine() updated; UI badge + selector added |
| 3 | ✅ DONE | 1553 (+83) | Smart engine skeleton; shadow wiring; 5 test files |
| 4 | ✅ DONE | 1561 (+8) | Replay harness; 3 API endpoints; MMMWhipsawCompareTab; MMMSafetyPanel fix |
| 5 | ⏭ SKIPPED | — | Operator decision: no shadow waiting period; promoted directly to live trading |
| 6 | ✅ DONE | 1562 (+1) | Smart is now primary (`engine=SMART`, `smart_enabled=True`); Legacy runs as shadow |

---

### PHASE 0 — Guardrails & baseline (no code change)

**Deliverables**
1. Confirm sealed baseline: run full sealed-test suite, record passing count in the phase-0 handoff note. Expected: 1312.
2. Create this file and the strategy-change header (per `feedback_strategy_change_protocol.md`) before every subsequent phase's commit.
3. Produce `mmm_workdone_march.md` entry template for Phase 1 (per CLAUDE.md §1 MMM work log).

**Exit criteria**
- Baseline test count recorded.
- No file modified.

**Rollback**: N/A.

---

### PHASE 1 — Extract legacy into dispatcher (behavior-identical)

**Intent:** introduce the `WhipsawEngine` abstraction and route the three legacy integration points through it, **without changing the decisions or state writes by a single bit**. This is the hardest phase because any drift is a real-money regression.

**Files created**
- `webui/backend/routes/mmm/mmm_whipsaw.py` — dispatcher, `WhipsawDecision`, `WhipsawCtx`, `LegacyWhipsawEngine`, `NullWhipsawEngine`, `select_engine()`, `whipsaw_decide()`. **Contains no behavior — `LegacyWhipsawEngine.evaluate()` calls the existing `check_whipsaw()` unchanged and translates its event list into a `WhipsawDecision`.**
- `webui/backend/routes/mmm/tests/test_mmm_whipsaw_legacy_parity.py` — golden-trace tests. Feeds 30+ recorded sessions (real-tape fixture) through both old-direct path and new-dispatcher path, asserts byte-identical session state after N heartbeats and byte-identical `events[]` output.

**Files modified**
- `mmm_safety.py::run_safety_checks()` — **do not remove** `check_whipsaw()` call. Instead add a fast `if session_uses_new_dispatcher_for_whipsaw()` gate so the legacy call is skipped only when the dispatcher has already consumed the result. During Phase 1, dispatcher *delegates to* `check_whipsaw()`, so the gate is always False — legacy call path is preserved. (This is the hinge that lets Phase 2 stop double-firing without a rewrite.)
- `mmm_monitor.py` — near line 3338 (trigger widening): replace inline `_ws_score` / `_ws_factor` computation with `decision = _wsd` where `_wsd` is cached from earlier in the heartbeat via a new helper `_get_whipsaw_decision(session, ctx)`. That helper caches per-beat (so neither Step 4.5 nor Step 6 nor Step 7 re-runs the engine).
- `mmm_monitor.py` — near line 4918 (lot reduction): same — use `decision.lot_scalar` instead of inline `_ws_score` check.

**Hard invariants**
- `LegacyWhipsawEngine.evaluate()` **must** call `check_whipsaw(session)` and read back the **same** session keys (`_whipsaw_score`, `_whipsaw_state`, etc.) that legacy sets. It does not itself write any state.
- The computed `trigger_widen_factor` must equal the original inline factor exactly (1.0 / 1.5 / 2.0) for all same inputs.
- The computed `lot_scalar` must equal the original inline scalar exactly (1.0 / 0.5 for legacy RESTRICT+ per line 4918-4929).
- `STRADDLE_WITH_ADJUSTMENT` bypass (`_is_straddle_adj` check in monitor) must still bypass — the dispatcher reads the strategy flag and returns `trigger_widen_factor=1.0`, `lot_scalar=1.0` for that strategy. Test case: session with `strategy_type='STRADDLE_WITH_ADJUSTMENT'` and `_whipsaw_score=5` → decision must have both scalars = 1.0.
- The `CLAUDE.md §4` stale-monitor guard, `§5` reverse-mode if/else, and `§2c` `_being_closed` invariant must all be untouched. Grep before and after to confirm the lines are byte-identical.
- `emit_safety()` is sync — do not wrap in `run_until_complete` (CLAUDE.md §4).

**Tests added**
1. `test_legacy_parity_empty_session` — fresh session, no history → dispatcher returns decision with no events, no state writes, scalars all 1.0.
2. `test_legacy_parity_three_alternations_within_window` — build a session with 3 alternating adjustments in 10 min → legacy direct path and dispatcher path produce identical state + events.
3. `test_legacy_parity_cooldown_skip` — session in COOLDOWN with `_whipsaw_skip_until` in future → decision.block_adjustment True and identical event.
4. `test_legacy_parity_cooldown_expired` — `_whipsaw_skip_until` in past → score reduced by 2, same as direct path.
5. `test_legacy_parity_trigger_widen_at_caution_and_restrict` — given `_whipsaw_score ∈ {caution, restrict}` → factor 1.5 / 2.0 and `_whipsaw_trigger_widened=True`.
6. `test_legacy_parity_lot_reduction_at_restrict` — lot input = 10 at RESTRICT → decision.lot_scalar = 0.5.
7. `test_straddle_bypass` — strategy_type `STRADDLE_WITH_ADJUSTMENT`, `_whipsaw_score=10` → both scalars 1.0.
8. `test_env_kill_switch` — `MMM_WHIPSAW_FORCE_LEGACY=1` + `whipsaw_engine='SMART'` → legacy engine used.
9. `test_audit_log_field_unchanged` — `execute_adjustment` call site still writes `whipsaw_state=<legacy value>` (grep audit row).

**Exit criteria**
- All 9 new tests pass. ✅
- Full sealed suite: ≥ 1321 passing. ✅ **Actual: 1465**
- Diff of `_whipsaw_*` session state after 100-beat replay = 0 bytes (golden-trace test). ✅
- Operator-visible behavior: zero change. ✅

**Rollback**: revert the Phase 1 commit; `check_whipsaw()` and inline monitor logic still exist untouched, so revert fully restores the prior binary.

---

### PHASE 2 — Settings plumbing & mutex UI

**Intent:** give the operator a visible, hot-reloadable switch. Still no Smart behavior yet.

**Params added**

| Name | Type | Range | Default | Hot | Purpose |
|---|---|---|---|---|---|
| `whipsaw_engine` | enum str | `LEGACY \| SMART \| OFF` | `LEGACY` | ✔ | selects active engine |
| `whipsaw_engine_shadow` | bool | | `False` | ✔ | run the non-active engine in observe mode |
| `whipsaw_smart_enabled` | bool | | `False` | ✔ | additional guard — Smart decisions bind only when both `engine=SMART` AND `smart_enabled=True` |

*Rationale for the third param:* it is an extra belt on top of the suspenders. Early in life-cycle we want `whipsaw_engine=SMART` to be selectable from the UI *without* binding decisions — shadow-only. The operator flips `smart_enabled=True` once shadow data is trusted.

**Files modified**
- `mmm_state.py::DEFAULT_PARAMS` — add three keys with defaults above.
- `mmm_state.py::HOT_RELOAD_PARAMS` — add all three.
- `mmm_config.py::VALID_PARAMS` — add type rules.
- `mmm_config.py::PARAM_RULES` — add a new rule: if `whipsaw_engine=SMART` and `whipsaw_smart_enabled=False`, issue a validation *warning* (not error) that Smart is running in shadow-only. Another rule: `engine in {LEGACY, SMART, OFF}` exact match.
- `mmm_config.py` — param description map: human-readable explanation for each.
- `mmm_whipsaw.py::select_engine()` — read `whipsaw_engine`, honor kill-switch, respect `whipsaw_smart_enabled` (if False and engine==SMART, return LEGACY as primary and SMART as shadow).

**Frontend**
- `MMMSettingsDialog.js` — add a new "Whipsaw Engine" accordion section. Radio group or Select with three options. Mutex is automatic (single enum). Render the current backend value; HOT badge; warning blurb *"Switching engines mid-session does not disturb open positions. State is isolated per engine."*.
- `MMMStatusBanner.js` — show active engine name + mode as a compact badge (`WS: LEGACY / CAUTION` or `WS: SMART / DEFENSIVE`).
- `MMMSafetyPanel.js` — render Smart events when they appear (same event shape; new `source: 'SMART'` field).

**Tests added**
1. `test_param_defaults` — new install → `whipsaw_engine='LEGACY'`, shadow=False, smart_enabled=False.
2. `test_param_validation_invalid_engine` — `whipsaw_engine='GARBAGE'` → rejected by validator.
3. `test_param_hot_reload` — flipping `whipsaw_engine` live updates `select_engine()` on next beat.
4. `test_smart_without_smart_enabled_is_shadow` — engine=SMART, smart_enabled=False → primary engine returned is LEGACY, `whipsaw_engine_shadow` autopromoted to True for the beat's trace.
5. `test_engine_off` — engine=OFF → `NullWhipsawEngine` returns scalars 1.0, no events, no state writes.

**Exit criteria**
- All Phase-1 tests still pass. ✅
- 5 new Phase-2 tests pass. ✅
- Full suite ≥ 1326 passing. ✅ **Actual: 1470**
- WebUI renders the new section; flipping the radio updates `/api/mmm/config` and reflects in the banner within one heartbeat. ✅ (UI wired; badge shows on non-NORMAL/non-LEGACY state)
- Operator-visible default behavior: identical to Phase 1 (LEGACY default). ✅

**Rollback**: revert Phase 2 commit. The dispatcher reverts to hard-coded `DEFAULT_ENGINE='LEGACY'`. Legacy operational.

---

### PHASE 3 — Smart engine skeleton (shadow-only)

**Intent:** implement the SmartWhipsaw engine from [WHIPSAW_INTELLIGENCE_UPGRADE.md](WHIPSAW_INTELLIGENCE_UPGRADE.md). Binding is disabled (`whipsaw_smart_enabled=False` default), so this phase cannot affect live trades. Only telemetry changes.

**Files created**
- `webui/backend/routes/mmm/mmm_whipsaw_smart.py` — the engine. Contains:
  - `SmartWhipsawEngine.evaluate()` — calls detectors, computes composite score, picks mode, runs multi-gate trigger, returns `WhipsawDecision`.
  - Detector functions (pure, stateless-where-possible):
    - `flip_counter_score(session, now)` — uses `adjustment_history`.
    - `efficiency_ratio_score(spot_series)` — requires rolling spot log.
    - `oscillation_score(spot_series)`.
    - `premium_symmetry_score(ce_series, pe_series)`.
    - `adjustment_outcome_score(session)`.
    - `rv_iv_divergence_score(session, ctx)`.
    - `gamma_zone_score(session, ctx)`.
  - `compute_composite(scores: dict) -> float` — weighted sum per [§3.8 of the upgrade report](WHIPSAW_INTELLIGENCE_UPGRADE.md#38-composite-whipsaw-score).
  - `mode_from_score(score: float, in_expiry_window: bool) -> str`.
  - `multi_gate_decide(session, ctx, score, mode) -> (block, widen, scalar, events)`.
  - `TokenBudget` — dataclass with `tokens_remaining`, `spend(cost)`, `credit_patience()`.
- `webui/backend/routes/mmm/mmm_whipsaw_spot_log.py` — rolling spot / CE / PE price log used by detectors. Writes to `_smart_ws_series` session key. Capped at last N samples. New heartbeat appends one sample. Migration-safe (missing key ⇒ empty list).
- `webui/backend/routes/mmm/tests/test_smart_whipsaw_detectors.py` — unit tests per detector with deterministic fixtures.
- `webui/backend/routes/mmm/tests/test_smart_whipsaw_score.py` — composite + mode thresholds.
- `webui/backend/routes/mmm/tests/test_smart_whipsaw_gates.py` — 3-of-5 gate evaluation matrix.
- `webui/backend/routes/mmm/tests/test_smart_whipsaw_token_budget.py` — budget arithmetic.
- `webui/backend/routes/mmm/tests/test_smart_whipsaw_shadow_does_not_bind.py` — integration: engine=SMART + smart_enabled=False → live session's `_whipsaw_*` state is written by legacy; `_smart_ws_*` state is written by smart; **no** scalar from smart is applied to lot sizing or trigger widening.

**State keys** (Smart's exclusive namespace)
```
_smart_ws_series              list of {ts, spot, ce, pe, iv}; cap len N (e.g. 240)
_smart_ws_score               float in [0,1]
_smart_ws_mode                str  (NORMAL/DEFENSIVE/OBSERVE/LOCKDOWN)
_smart_ws_tokens              float
_smart_ws_last_flip_at        ISO
_smart_ws_flip_count_30m      int
_smart_ws_last_decision       dict (full trace snapshot)
_smart_ws_shadow_last         dict (for shadow-mode diffs)
```

**Hot reload for Smart-specific params** (added to `DEFAULT_PARAMS` + `HOT_RELOAD_PARAMS`):

| Name | Default | Notes |
|---|---|---|
| `smart_ws_score_defensive` | 0.30 | mode threshold |
| `smart_ws_score_observe` | 0.60 | mode threshold |
| `smart_ws_score_lockdown` | 0.80 | mode threshold |
| `smart_ws_tokens_per_session` | 10 | daily budget |
| `smart_ws_gate_count_normal` | 3 | 3-of-5 |
| `smart_ws_gate_count_defensive` | 4 | 4-of-5 |
| `smart_ws_flip_window_mins` | 30 | rolling window |
| `smart_ws_er_window_mins` | 30 | Kaufman ER window |
| `smart_ws_oscillation_sensitivity_pct` | 0.15 | min move to count |
| `smart_ws_rv_iv_ratio_floor` | 0.6 | vol-divergence gate |
| `smart_ws_size_scalar_defensive` | 0.5 | size reduction |
| `smart_ws_size_scalar_observe` | 0.25 | size reduction |
| `smart_ws_flip_penalty` | 0.5 | halve per flip |
| `smart_ws_cooldown_base_beats` | 1 | base exponential cooldown |

Weights for the composite (0.30 / 0.20 / 0.10 / 0.10 / 0.15 / 0.10 / 0.05) are kept as module-level constants, *not* params, for Phase 3 to limit surface area. Phase 5 may promote them to hot-reload params after replay tuning.

**Wiring**
- In `whipsaw_decide(session, ctx)`:
  1. Build spot-log sample, append to `_smart_ws_series`.
  2. If `whipsaw_engine_shadow` is True *or* (engine=SMART and smart_enabled=False) → run `SmartWhipsawEngine.evaluate()` and store the result under `_smart_ws_shadow_last`. **Do not return it** as primary.
  3. Primary decision: `LegacyWhipsawEngine.evaluate()` (unchanged).
  4. Emit a structured log line per heartbeat: `{engine_primary, engine_shadow, legacy_mode, legacy_score, smart_mode, smart_score, disagree: bool}`.

**Hard invariants**
- No write to any `_whipsaw_*` key by Smart engine. Ever.
- No read of any `_smart_ws_*` key by legacy engine. Ever.
- When `smart_enabled=False`, `SmartWhipsawEngine.evaluate()` return values are *discarded*. No scalar from Smart reaches the monitor.
- Spot-log memory: must cap. Unbounded list in session state = long-term memory leak + slow save.
- Expiry-window whipsaw tightening (see [§9.2 of the report](WHIPSAW_INTELLIGENCE_UPGRADE.md#92-whipsaw-at-expiry)) is implemented only in SMART, not retrofitted into legacy.

**Tests added**
- Per-detector unit test (7 detectors × 3–5 scenarios each).
- Score composition test (boundary transitions at 0.3 / 0.6 / 0.8).
- 3-of-5 and 4-of-5 gate matrix tests.
- Asymmetric gate test (adding to thinner side → +1 gate).
- Token budget spend / patience-credit test.
- Shadow-mode integration test (Phase 3 definitive regression guard).
- Kill-switch + shadow interaction test.
- Post-shift cooldown test ([§8 of the report](WHIPSAW_INTELLIGENCE_UPGRADE.md#8-smart-cooldown-logic) — 2-beat silence after every strike shift).

**Exit criteria**
- Full suite passes (Phase-2 count + new Phase-3 tests).
- Live session run for ≥ 24 h in staging: legacy primary decisions unchanged; smart shadow decisions logged with zero state bleed (grep `_whipsaw_*` vs `_smart_ws_*` in session dump).
- New endpoint `GET /api/mmm/whipsaw/shadow-diff/<session_id>` returns last 100 heartbeats' legacy-vs-smart disagreement frequency.

**Rollback**: revert Phase 3 commit. Dispatcher still works with legacy-only.

---

### PHASE 4 — Comparison tools & operator dashboards

**Intent:** let the operator see the Smart engine's behavior before trusting it.

**Deliverables**
- `webui/backend/routes/mmm/mmm_whipsaw_replay.py` — deterministic replay harness: given a historical `adjustment_history` + spot log, produces legacy decisions vs smart decisions for every beat. CLI entry point + API endpoint.
- API endpoints:
  - `POST /api/mmm/whipsaw/replay` — body `{session_id, engine_a, engine_b, param_overrides}` → returns diff report.
  - `GET /api/mmm/whipsaw/shadow-diff/<session_id>` — live shadow-mode disagreement feed.
  - `GET /api/mmm/whipsaw/metrics/<session_id>` — aggregate metrics (adjustments-fired, adjustments-skipped, lot-saved, false-trigger-rate-estimate).
- Frontend: `MMMWhipsawCompareTab.js` under MMMDashboard — tabular diff, inline chart of both scores across heartbeats. Lives on its own tab; zero impact on existing tabs.
- Trace artifacts: every heartbeat writes `_whipsaw_trace` to `mmm_activity_log` for later forensic review.

**Tests added**
- Replay determinism: same input → same output across invocations.
- Metrics endpoint schema contract (sealed).
- Frontend smoke test (component renders with empty data).

**Exit criteria**
- Operator can look at any real session and see: legacy-fired, smart-would-fire, legacy-widened, smart-would-widen, legacy-lot-reduced, smart-would-lot-reduce, per heartbeat. Plus aggregate summary.
- 7-day shadow data review before Phase 5.

**Rollback**: revert Phase 4 commit; no live decisions affected.

---

### PHASE 5 — Parameter tuning (SKIPPED by operator decision 2026-04-19)

**Intent:** originally, use 7+ days of shadow data to tune Smart params before promotion.

**Operator decision:** Skipped. Smart engine promoted directly to live trading on 2026-04-19 without a shadow observation period. Params are live defaults from Phase 3 design. Tune via the compare tab + replay harness (`/api/mmm/whipsaw/metrics`) while running live.

**Ongoing tuning (post-promotion):**
- Use the Whipsaw tab in the dashboard to watch Smart vs Legacy disagree events in real time.
- Use `GET /api/mmm/whipsaw/replay/<session_id>` to replay any session and compare.
- If Smart is too aggressive: raise `smart_ws_score_defensive` (default 0.30) and/or `smart_ws_gate_count_normal` (default 3).
- If Smart is too passive: lower thresholds or `smart_ws_gate_count_defensive` (default 4).
- All changes are hot-reload — no backend restart needed.

---

### PHASE 6 — Promotion to binding ✅ DONE 2026-04-19

**Change applied (code):**
- `mmm_state.py` DEFAULT_PARAMS: `whipsaw_engine='SMART'`, `whipsaw_smart_enabled=True`, `whipsaw_engine_shadow=True`
- `mmm_whipsaw.py`: `DEFAULT_ENGINE = 'SMART'`
- `mmm_whipsaw.py` `_maybe_run_shadow()`: bidirectional — when Smart is primary + shadow_enabled=True, Legacy runs as shadow and writes `_ws_legacy_shadow_last` (for compare tab and forensics)
- `MMMSafetyPanel.js`: whipsaw indicator now shows Smart data as primary when `whipsaw_engine=SMART`; Legacy data shown as supplemental

**Current behavior:**
- `SmartWhipsawEngine.evaluate()` is the primary decision — scalars bind on monitor lines 3338 + 4918.
- `LegacyWhipsawEngine.evaluate()` runs in shadow (deepcopy), result stored in `_ws_legacy_shadow_last`.
- Compare tab shows Smart primary vs Legacy shadow in real time.

**Rollback procedures** (three levels, fastest first)
1. **Instant (no login)**: `export MMM_WHIPSAW_FORCE_LEGACY=1` on backend host → next heartbeat uses LEGACY.
2. **Fast (operator UI)**: flip `whipsaw_engine` to `LEGACY` in Settings → Safety → hot reload on next heartbeat.
3. **Full (code)**: revert Phase 6 defaults commit. Reload backend.

---

## 4. Invariant checklist (paste into every PR description)

Before merging any phase, confirm each line:

- [ ] `mmm_safety.py::check_whipsaw()` body unchanged (phase ≤ 5).
- [ ] `mmm_monitor.py` lines 3338–3363 replaced by `decision.trigger_widen_factor` only; no other changes in that region.
- [ ] `mmm_monitor.py` lines 4918–4929 replaced by `decision.lot_scalar` only; no other changes in that region.
- [ ] `STRATEGY_DISPATCH` untouched; `STRADDLE_WITH_ADJUSTMENT` still bypasses whipsaw widening + lot reduction.
- [ ] Stale-monitor 3-layer fix (CLAUDE.md §4) intact — grep `emit_safety()`, `handle_stale_monitor()`, `thread.join(15`.
- [ ] Reverse-mode if/else (CLAUDE.md §5) intact — `mmm_monitor.py` around line 2781 unchanged.
- [ ] `_being_closed` + `_being_closed_at` pairs (CLAUDE.md §2c) untouched.
- [ ] `HOT_RELOAD_PARAMS` updated for every new param.
- [ ] `DEFAULT_ENGINE='LEGACY'` unchanged.
- [ ] Env kill-switch test passes.
- [ ] Sealed test count ≥ prior baseline + new tests added this phase.
- [ ] `mmm_workdone_march.md` entry appended.
- [ ] STRATEGY/SCOPE/CHANGE header present on the PR per `feedback_strategy_change_protocol.md`.

---

## 5. File-level wiring summary (one-line per touch)

| File | Phase | Action |
|---|---|---|
| `webui/backend/routes/mmm/mmm_whipsaw.py` | 1 | **CREATE** — dispatcher + Legacy + Null engines + decision dataclass |
| `webui/backend/routes/mmm/mmm_whipsaw_smart.py` | 3 | **CREATE** — Smart engine |
| `webui/backend/routes/mmm/mmm_whipsaw_spot_log.py` | 3 | **CREATE** — rolling price log |
| `webui/backend/routes/mmm/mmm_whipsaw_replay.py` | 4 | **CREATE** — replay harness |
| `webui/backend/routes/mmm/mmm_monitor.py` | 1 | MODIFY lines 3338–3363 + 4918–4929; introduce `_get_whipsaw_decision(session, ctx)` helper |
| `webui/backend/routes/mmm/mmm_safety.py` | 1 | MODIFY `run_safety_checks` only — gate direct `check_whipsaw` call behind dispatcher-owned flag (Phase 1 gate always False) |
| `webui/backend/routes/mmm/mmm_state.py` | 2, 3 | MODIFY `DEFAULT_PARAMS` + `HOT_RELOAD_PARAMS` — add engine params (Phase 2) + smart params (Phase 3) |
| `webui/backend/routes/mmm/mmm_config.py` | 2, 3 | MODIFY `VALID_PARAMS`, `PARAM_RULES`, description map |
| `webui/backend/routes/mmm/mmm_api.py` | 4 | MODIFY — add replay, shadow-diff, metrics endpoints |
| `webui/frontend/src/components/mmm/MMMSettingsDialog.js` | 2 | MODIFY — new Whipsaw Engine section |
| `webui/frontend/src/components/mmm/MMMStatusBanner.js` | 2 | MODIFY — engine badge |
| `webui/frontend/src/components/mmm/MMMSafetyPanel.js` | 3 | MODIFY — show Smart events |
| `webui/frontend/src/components/mmm/MMMDashboard.js` | 4 | MODIFY — add Whipsaw Compare tab |
| `webui/frontend/src/components/mmm/MMMWhipsawCompareTab.js` | 4 | **CREATE** — compare UI |
| `webui/backend/routes/mmm/tests/test_mmm_whipsaw_legacy_parity.py` | 1 | **CREATE** |
| `webui/backend/routes/mmm/tests/test_mmm_whipsaw_params.py` | 2 | **CREATE** |
| `webui/backend/routes/mmm/tests/test_smart_whipsaw_*.py` | 3 | **CREATE** — 5 files |
| `webui/backend/routes/mmm/tests/test_mmm_whipsaw_replay.py` | 4 | **CREATE** |
| `MMM_LAST_3_SESSIONS.md` | each | APPEND session summary |
| `mmm_workdone_march.md` | each | APPEND `## 2026-MM-DD — phase N` entry |

---

## 6. What the Smart engine must implement (specification reference)

All behavior is specified in [WHIPSAW_INTELLIGENCE_UPGRADE.md](WHIPSAW_INTELLIGENCE_UPGRADE.md). Map from section → code:

| Report section | Code location |
|---|---|
| §3.1 flip counter | `mmm_whipsaw_smart.py::flip_counter_score` |
| §3.2 Kaufman ER | `mmm_whipsaw_smart.py::efficiency_ratio_score` |
| §3.3 oscillation | `mmm_whipsaw_smart.py::oscillation_score` |
| §3.4 premium symmetry | `mmm_whipsaw_smart.py::premium_symmetry_score` |
| §3.5 adjustment outcome | `mmm_whipsaw_smart.py::adjustment_outcome_score` |
| §3.6 RV/IV divergence | `mmm_whipsaw_smart.py::rv_iv_divergence_score` |
| §3.7 gamma zone | `mmm_whipsaw_smart.py::gamma_zone_score` |
| §3.8 composite | `mmm_whipsaw_smart.py::compute_composite` |
| §4.1 3-mode stance | `mmm_whipsaw_smart.py::mode_from_score` |
| §4.2 token budget | `mmm_whipsaw_smart.py::TokenBudget` |
| §4.3 patience credit | `TokenBudget.credit_patience()` |
| §4.4 asymmetric lockdown | `mmm_whipsaw_smart.py::asymmetric_gate_adjustment` |
| §5 multi-gate 3-of-5 / 4-of-5 | `mmm_whipsaw_smart.py::multi_gate_decide` |
| §5.3 pressure-release override | `mmm_whipsaw_smart.py::pressure_override_active` |
| §7 trader-intuition table | implemented as rules within `multi_gate_decide` + `mode_from_score` |
| §8 exponential cooldown | `mmm_whipsaw_smart.py::compute_cooldown_beats` |
| §9.1–9.5 edge cases | explicit branches in `SmartWhipsawEngine.evaluate` |
| §10 decision framework 9-step | the body of `SmartWhipsawEngine.evaluate` in same order |

---

## 7. Risk register (top hazards for a coding AI)

| # | Hazard | Mitigation |
|---|---|---|
| R1 | AI accidentally edits legacy `check_whipsaw()` while "refactoring" | Phase-1 parity test (byte-level state diff) fails the build |
| R2 | AI forgets to add new param to `HOT_RELOAD_PARAMS` | Param-hot-reload test fails if any new key is not in the list |
| R3 | AI writes to `_whipsaw_*` from Smart (state bleed) | `test_smart_whipsaw_shadow_does_not_bind` asserts diff=0 on legacy keys during smart shadow run |
| R4 | AI routes Smart decision to monitor while `smart_enabled=False` | Integration test: engine=SMART + smart_enabled=False + recipe-that-would-block → live adjustment still fires |
| R5 | AI removes `STRADDLE_WITH_ADJUSTMENT` bypass while refactoring | Dedicated bypass test for every engine |
| R6 | AI rewords `DEFAULT_ENGINE` or mistypes enum | `test_param_defaults` pins the literal `'LEGACY'` |
| R7 | AI introduces cross-module import cycle | Dispatcher imports engines; engines do not import dispatcher |
| R8 | AI triggers a backend restart to "apply" hot-reload param | Hot-reload test asserts change takes effect without restart |
| R9 | AI deletes `_whipsaw_trigger_widened` display flag | Status banner sealed test checks for its presence |
| R10 | AI overwrites an uncommitted operator-tuned param | Phase 5 is operator-driven, not AI-driven; AI must not modify param defaults after Phase 3 without explicit sign-off |

---

## 8. Definition of Done (program-level)

The program is Done when all of:

1. Phase 6 sign-off memo is committed.
2. Smart engine has been binding (`smart_enabled=True`) for ≥ 30 calendar days in production.
3. No rollback to LEGACY has been required in those 30 days.
4. Comparison metrics (Phase 4) show ≥ 20% reduction in whipsaw-era adjustment count, zero missed real-breakout adjustments.
5. Operator explicitly agrees to deprecate legacy widening + lot-reduction logic (separate decision — NOT automatic). Until that decision, legacy stays in the codebase as a rollback.

---

## 9. Appendix — commands & environment

```bash
# Run full sealed suite
cd /Users/ssr/Projects/WorkingBot
python -m pytest webui/backend/routes/mmm/tests/ -q

# Run only whipsaw-related tests
python -m pytest webui/backend/routes/mmm/tests/test_*whipsaw* -q

# Enable kill-switch at runtime
export MMM_WHIPSAW_FORCE_LEGACY=1
kill -9 $(lsof -ti:5555)   # launchd auto-restarts backend

# Operator flip (API)
curl -X POST http://localhost:5555/api/mmm/config \
  -H 'Content-Type: application/json' \
  -d '{"whipsaw_engine":"SMART","whipsaw_smart_enabled":false,"whipsaw_engine_shadow":true}'
```

---

_End of plan._
