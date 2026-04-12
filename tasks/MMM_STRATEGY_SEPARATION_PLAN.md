# MMM Strategy Separation Plan

**Goal**: Cleanly separate all 5 strategies at both backend and frontend so each strategy is unambiguous, self-contained, and produces predictable behavior.  
**Status**: Execution complete for Phases 1–6 (backend + frontend strategy separation delivered).  
**Branch**: SSR → merge target BTEH  
**Author**: ssr + Claude Sonnet 4.6  
**Date**: 2026-04-12  
**Last Updated**: 2026-04-12 (Phase 5.2–5.4 + Phase 6 completion)

---

## Execution Snapshot (Audit-Friendly)

> Note: Implementation occurred in safety-first batches. Some backend dispatch work landed before the original sequential phase order below.

### Completed so far

- ✅ Canonical strategy identity groundwork (`strategy_type`) landed across state/storage/API.
- ✅ Runtime strategy dispatch migrated to canonical `strategy_type` in monitor + straddle modules.
- ✅ Strategy namespace enforcement for param patching is active in backend (`forbidden` params rejected per strategy).
- ✅ Frontend strategy identity now reads canonical `strategy_type` for settings/dashboard behavior.
- ✅ Settings dialog now surfaces backend `total_exposure_warning` / `cap_raise_warning` after save.
- ✅ Dashboard now includes strategy-specific KPI bar + strategy filter chips in session list.
- ✅ Activity feed now has strategy-context filtering (including STRADDLE_ROLL `adjustment_skipped` suppression + bug signal surfacing).
- ✅ Create Session flow now uses strategy-specific form sections with strategy-specific validation and inline strategy tooltip/help.
- ✅ Regression verification complete:
    - Focused suite: **57 passed**
    - Full MMM suite: **1315 passed**

### Invariants explicitly preserved

- Stale monitor 3-layer stop protections (CLAUDE.md §4) untouched.
- Reverse mode isolation and hard if/else contract (CLAUDE.md §5) untouched.
- STRADDLE_ROLL and STRADDLE_WITH_ADJUSTMENT remain mutually isolated at dispatch gate.

## Completed Work Ledger (for audit + debugging)

### Batch A — Strategy identity groundwork

**Why this batch:** remove runtime identity drift by stamping immutable canonical strategy identity.

**Files changed**
- `webui/backend/routes/mmm/mmm_state.py`
    - Added canonical helpers (`derive_strategy_type`, alias handling).
    - `create_session()` now stamps top-level `session['strategy_type']`.
    - `get_session_summary()` now emits `strategy_type` with legacy fallback support.
- `webui/backend/routes/mmm/mmm_storage.py`
    - Added `strategy_type` DB column + startup migration/backfill.
    - Persist/read/list paths updated to carry `strategy_type`.
    - Active-session strategy mutation protection hardened.
- `webui/backend/routes/mmm/mmm_api.py`
    - Session create blocks immutable identity key injection.
    - Params patch blocks strategy drift updates (`strategy_type`, `dte_category`, `_preset_source`).
- Tests:
    - `webui/backend/routes/mmm/tests/test_mmm_summary_preset_source.py`
    - `webui/backend/routes/mmm/tests/test_mmm_strategy_type_identity.py`

**Verification evidence**
- Focused identity test run passed (`20 passed`).

### Batch B — Strategy dispatch migration to canonical `strategy_type`

**Why this batch:** remove legacy `_preset_source` dispatch checks from runtime behavior routing.

**Files changed**
- `webui/backend/routes/mmm/mmm_api.py`
    - Create-time strategy validation branches moved to canonical `strategy_type`.
    - Straddle strategy required-field enforcement retained.
- `webui/backend/routes/mmm/mmm_monitor.py`
    - Runtime strategy resolution centralized via canonical derivation.
    - Step 5.4 and straddle gates now keyed by `strategy_type`.
- `webui/backend/routes/mmm/mmm_straddle_adjustment.py`
    - Gate 2 switched to canonical strategy validation (legacy fallback retained).
- `webui/backend/routes/mmm/mmm_straddle_roll_pure.py`
    - Gate 2 switched to canonical strategy validation (legacy fallback retained).

**Regression + fix notes**
- Fixed one refactor regression in `mmm_api.py` (indentation error in STRADDLE_ROLL validation block).
- Focused strategy/dispatch suite passed (`57 passed`).

### Batch C — Post-migration safety sweep

**Why this batch:** prove no hidden breakage after dispatch migration.

**Checks performed**
- Re-audited monitor/straddle modules for legacy runtime `_preset_source` branching.
- Confirmed remaining `dte_category` references in monitor are non-dispatch behavior (adaptive/replenish context).

**Verification evidence**
- Full MMM backend tests passed:
    - `python3 -m pytest webui/backend/routes/mmm/tests`
    - Result: **1315 passed, 599 warnings, 0 failed**

## Problem Statement

All 5 strategies share a single `MMMMonitor`, single session schema, and a monolithic dashboard. Behavioral differences are enforced through `_preset_source` string checks, `if/elif` chains, and "hack" params like `min_trigger_move=9999`. This causes:

1. Wrong strategy badge shown in UI (derived from multiple fallback fields)
2. Settings dialog shows settings irrelevant to the current strategy
3. STRADDLE_ROLL using `min_trigger_move=9999` as a fake isolation guard instead of a structural one
4. `max_total_exposure` / `max_lots_per_side` confusion because fields mean different things per strategy
5. Session cards show identical UI layout regardless of strategy — no strategy-specific KPIs
6. No enforcement that a running session cannot "drift" to a different behavioral path mid-session

---

## The 5 Strategies

| Key | Label | Entry | Risk Mgmt | Exit |
|-----|-------|-------|-----------|------|
| `0DTE` | Short Strangle 0DTE | CE+PE sell at ATM ±step | Adjustment engine (hedge) | close_at_5, auto_close_mins |
| `5DTE` | Short Strangle 5DTE | Same as 0DTE | Adjustment engine (slower) | Same |
| `SHORT_WINDOW` | Short Window | Same as 0DTE | Adjustment engine | Same + session_window_hours hard stop |
| `STRADDLE_WITH_ADJUSTMENT` | Straddle + Adj | ATM straddle (equal CE=PE strike) | Adjustment engine (ATM-focused) | close_at_5 |
| `STRADDLE_ROLL` | Pure Straddle Roll | ATM straddle | Roll on trigger ONLY (no adjustments) | Hard stop (market orders), expiry guard |

---

## Separation Architecture

### Principle: Single Source of Truth via `strategy_type`

Every session gets a **single, immutable** `strategy_type` field stamped at creation:
- Stored as `strategy_type` in `data_json` and as a dedicated DB column
- Never derived from `_preset_source` or `dte_category` at runtime
- Used by backend monitor, API, and frontend as the ONLY routing key

### Two Code Dimensions to Separate

**Dimension A — Runtime Behavior** (backend monitor)  
What the heartbeat actually does: which modules are called, which checks apply, which order types are used.

**Dimension B — Configuration Namespace** (params + UI)  
Which settings are relevant, which fields are shown/hidden, which KPI cards appear.

---

## Phase 1 — DB + Schema: `strategy_type` as First-Class Field

**Goal**: `strategy_type` exists as a non-nullable DB column and is always stamped at session creation.  
**Files**: `mmm_storage.py`, `mmm_api.py`, `mmm_dte_presets.py`

### 1.1 Add DB column

```sql
ALTER TABLE mmm_sessions ADD COLUMN strategy_type TEXT NOT NULL DEFAULT '0DTE';
```

Run migration in `_migrate_from_json()`: set `strategy_type` from existing `params_json._preset_source` or `dte_category`.

### 1.2 Stamp at session creation

In `mmm_api.py → create_session()`:
```python
strategy_type = _derive_strategy_type(data)
session['strategy_type'] = strategy_type
```

Where `_derive_strategy_type` maps:
- `dte_category = '0DTE'` → `'0DTE'`
- `dte_category = '5DTE'` → `'5DTE'`
- `dte_category = 'SHORT_WINDOW'` → `'SHORT_WINDOW'`
- `dte_category = 'STRADDLE_WITH_ADJUSTMENT'` → `'STRADDLE_WITH_ADJUSTMENT'`
- `dte_category = 'STRADDLE_ROLL'` → `'STRADDLE_ROLL'`

### 1.3 Immutability enforcement

In `update_session_params()`: if `strategy_type` in request body → reject with 400.  
In `update_session()`: if `strategy_type` in updates and session is RUNNING → reject.

### 1.4 Storage CRUD update

`save_session()` and `update_session()` write the `strategy_type` column.  
`get_session()` reads it back and sets `session['strategy_type']`.  
`list_session_summaries()` includes it in the SELECT for the card list.

**Deliverable**: Every session in DB has `strategy_type`. All CRUD operations preserve it. No runtime derivation from params.

---

## Phase 2 — Backend: Strategy-Specific Param Namespaces

**Goal**: Each strategy has a declared set of relevant params. Settings API rejects changes to irrelevant params for that strategy.  
**Files**: `mmm_config.py`, `mmm_api.py`

### 2.1 Define strategy param namespaces

**Implementation note (2026-04-12):** The live implementation in `mmm_config.py` is the source of truth. It intentionally treats `STRADDLE_WITH_ADJUSTMENT` as sharing most `straddle_roll_*` controls, while keeping `straddle_roll_hard_stop_market_order` as pure-roll-only.

Add to `mmm_config.py`:

```python
STRATEGY_PARAM_NAMESPACES = {
    '0DTE': {
        'required': ['expiry', 'initial_lots', 'min_trigger_move', 'max_lots_per_side', 'max_loss_amount'],
        'allowed_hot': ALL_HOT_PARAMS,     # Full param set
        'forbidden': ['straddle_roll_max_per_session'],
    },
    '5DTE': {
        'required': ['expiry', 'initial_lots', 'min_trigger_move', 'max_lots_per_side', 'max_loss_amount'],
        'allowed_hot': ALL_HOT_PARAMS,
        'forbidden': ['straddle_roll_max_per_session'],
    },
    'SHORT_WINDOW': {
        'required': ['session_window_hours', 'initial_lots', 'min_trigger_move'],
        'allowed_hot': ALL_HOT_PARAMS,
        'forbidden': ['straddle_roll_max_per_session'],
    },
    'STRADDLE_WITH_ADJUSTMENT': {
        'required': ['initial_lots', 'max_loss_amount'],
        'allowed_hot': ALL_HOT_PARAMS - {'expiry'},   # expiry is computed from hours_to_expiry
        'forbidden': ['straddle_roll_max_per_session', 'wind_down_hours_before_expiry'],
    },
    'STRADDLE_ROLL': {
        'required': ['initial_lots', 'max_loss_amount', 'straddle_roll_max_per_session'],
        'allowed_hot': {
            'max_loss_amount', 'straddle_roll_max_per_session', 'max_lots_per_side',
            'lot_velocity_limit', 'lot_velocity_window_mins',
        },
        'forbidden': [
            # STRADDLE_ROLL never adjusts — these are meaningless
            'min_trigger_move', 'shift_threshold', 'shift_target_premium',
            'whipsaw_window_mins', 'whipsaw_restrict_score',
            'harvest_profit_pct', 'recycle_enabled',
            'breakeven_control_enabled', 'gamma_detector_enabled',
        ],
    },
}
```

### 2.2 Enforce in `update_session_params()`

After validation, check `forbidden` params for this session's `strategy_type`. Reject with 400 + message.

### 2.3 Auto-fix `max_total_exposure` cross-param check

When `max_lots_per_side` is changed AND `max_total_exposure > 0 AND max_total_exposure < new max_lots_per_side`:
- Log a warning (already done — PR #current)
- Include `total_exposure_warning` in response (already done)
- **NEW**: Offer auto-fix in the response: `suggest_max_total_exposure: max_lots_per_side * 2`

**Deliverable**: Cannot hot-reload STRADDLE_ROLL settings that only apply to adjustment strategies (and vice versa). Each strategy's settings surface is bounded.

---

## Phase 3 — Backend: Strategy Dispatcher in Monitor

**Goal**: Replace `if _preset_source == 'STRADDLE_ROLL'` chains with a clean dispatch table.  
**Files**: `mmm_monitor.py`, new `mmm_strategy_dispatch.py`

### 3.1 Create `mmm_strategy_dispatch.py`

```python
# Dispatch table: strategy_type → heartbeat step handlers
STRATEGY_DISPATCH = {
    '0DTE':                     StraddleAdjustmentHandler,
    '5DTE':                     StraddleAdjustmentHandler,
    'SHORT_WINDOW':             StraddleAdjustmentHandler,
    'STRADDLE_WITH_ADJUSTMENT': StraddleAdjustmentHandler,
    'STRADDLE_ROLL':            StraddleRollHandler,
}
```

Each handler is a small dataclass or module-level dict mapping step names to async callables:

```python
@dataclass
class StrategyHandler:
    should_run_adjustment: Callable   # Returns bool — gate for adjustment logic
    run_step_5_4: Callable            # Called at Step 5.4 of heartbeat
    validate_session: Callable        # Called at session start / each beat
    get_strategy_type: str
```

### 3.2 Refactor heartbeat Step 5.4

Current (in `_heartbeat`):
```python
# Step 5.4 — today's messy if/elif
if _preset_source == 'STRADDLE_ROLL':
    await execute_pure_straddle_roll(...)
elif session.get('params', {}).get('reverse_enabled'):
    await process_reverse_entry(...)
else:
    await _process_adjustment(...)
```

New (in `_heartbeat`):
```python
# Step 5.4 — strategy dispatch
handler = STRATEGY_DISPATCH.get(session.get('strategy_type'), StraddleAdjustmentHandler)
await handler.run_step_5_4(self, session, ...)
```

`StraddleAdjustmentHandler.run_step_5_4` contains the current adjustment + reverse logic.  
`StraddleRollHandler.run_step_5_4` contains the current `execute_pure_straddle_roll` call.

### 3.3 Remove the `min_trigger_move=9999` hack

STRADDLE_ROLL preset sets `min_trigger_move=9999` to prevent the adjustment engine from firing. After Phase 3, the STRADDLE_ROLL handler simply never calls `_process_adjustment`. The `min_trigger_move=9999` can be removed from the preset and the `forbidden` namespace check (Phase 2.1) will prevent it from being set.

### 3.4 Strategy invariant validator

Each handler has a `validate_session(session) → List[str]` that returns a list of errors. Called in:
- `start_session_monitor()` before starting
- `_heartbeat()` at the top of each beat (log warnings, don't abort)
- `create_session()` API before committing to DB

STRADDLE_ROLL validator checks:
- `session['ce']['active_strike'] == session['pe']['active_strike']` (true straddle)
- No frozen positions (roll replaces, never freezes)
- `_preset_source == 'STRADDLE_ROLL'`

STRADDLE_WITH_ADJUSTMENT validator checks:
- CE strike == PE strike (true ATM straddle, not strangle)
- `hours_to_expiry` set and > 0

**Deliverable**: Monitor dispatch is clean. STRADDLE_ROLL can never accidentally call adjustment logic. Invariants are checked at startup and logged on violation.

---

## Phase 4 — Frontend: Strategy-Aware Settings Dialog

**Goal**: `MMMSettingsDialog` only shows params relevant to the current strategy. No adjustment params shown for STRADDLE_ROLL.  
**Files**: `MMMSettingsDialog.js`

### 4.1 Strategy-aware param filter

Add to MMMSettingsDialog:

```javascript
const STRATEGY_FORBIDDEN_PARAMS = {
  STRADDLE_ROLL: new Set([
    'min_trigger_move', 'shift_threshold', 'shift_target_premium',
    'whipsaw_window_mins', 'whipsaw_spot_move_pct',
    'harvest_profit_pct', 'harvest_min_age_mins',
    'recycle_enabled', 'recycle_premium_ceiling',
    'breakeven_control_enabled', 'gamma_detector_enabled',
    // ... etc
  ]),
};

const strategyType = session?.strategy_type || session?.params?._preset_source || '0DTE';
const forbiddenParams = STRATEGY_FORBIDDEN_PARAMS[strategyType] || new Set();
```

### 4.2 Hide forbidden params from group rendering

In `renderParam()`: if `forbiddenParams.has(paramName)` → return null.  
In search mode: exclude forbidden params from results.

### 4.3 Strategy banner at top of settings dialog

Show a colored badge at the top:
```
⚖️ Straddle + Adj  |  ⚡ 0DTE  |  📅 5DTE  |  🪟 Short Window  |  🔄 Pure Roll
```
Color-coded, read-only, matches the session card badge.

### 4.4 Show `total_exposure_warning` from API

When API response includes `total_exposure_warning`, show it as an amber Alert in the dialog AFTER save. Currently the warning is returned but the frontend ignores it.

**Deliverable**: STRADDLE_ROLL settings dialog shows only roll-specific params. No irrelevant fields cluttering the view.

---

## Phase 5 — Frontend: Strategy-Aware Session Cards & Dashboard

**Goal**: Strategy badge is always present and unambiguous. Strategy-specific KPI cards.  
**Files**: `MMMDashboard.js`, `MMMSafetyPanel.js`

### 5.1 Strategy badge from `strategy_type` (not derived)

Replace the current badge derivation logic (which reads from `_preset_source`, `dte_category`, `params?._preset_source` with multiple fallbacks) with a single read:

```javascript
const strategyType = session.strategy_type || '0DTE';
const badge = STRATEGY_META[strategyType];
```

`STRATEGY_META` is the existing dict at the top of MMMDashboard.js — just remove the derivation logic.

### 5.2 Strategy-specific KPI cards in dashboard

Each strategy shows different primary KPIs:

| Strategy | Primary KPIs |
|----------|-------------|
| 0DTE / 5DTE / SHORT_WINDOW | CE lots, PE lots, P&L, adj count, breakeven band |
| STRADDLE_WITH_ADJUSTMENT | Same + hours_to_expiry, initial credit |
| STRADDLE_ROLL | Roll count, max_per_session %, net P&L, hard stop distance |

Add a `StrategyKPIBar` component that renders based on `strategy_type`.

### 5.3 Strategy-specific activity log filter

In the Activity tab, add a "strategy context" filter that defaults to hiding cross-strategy noise. STRADDLE_ROLL sessions don't show "adjustment_skipped" events (they should never appear, but if they do, they indicate a bug worth highlighting separately).

### 5.4 Session list: strategy filter chip

In the session list header, add strategy filter chips:
```
[All] [0DTE] [5DTE] [Short Window] [Straddle+Adj] [Pure Roll]
```

**Deliverable**: Users can instantly identify strategy from the card. Dashboard shows strategy-appropriate metrics.

---

## Phase 6 — Frontend: Strategy-Specific Session Creation Forms

**Goal**: The session creation form changes based on selected strategy — no irrelevant fields.  
**Files**: `MMMDashboard.js` (create session dialog)

### 6.1 Strategy-aware form fields

Current state: A giant form with `if (dtePreset === 'STRADDLE_ROLL')` and `if (dtePreset === 'STRADDLE_WITH_ADJUSTMENT')` inline conditionals. This is brittle.

New state: Extract strategy-specific form sections into components:

```javascript
const STRATEGY_FORM = {
  '0DTE':                     StrangleFormFields,
  '5DTE':                     StrangleFormFields,
  'SHORT_WINDOW':             ShortWindowFormFields,
  'STRADDLE_WITH_ADJUSTMENT': StraddleAdjFormFields,
  'STRADDLE_ROLL':            StraddleRollFormFields,
};
```

Each component renders only its own fields with its own validation.

### 6.2 Required field validation per strategy

STRADDLE_ROLL requires `max_loss_amount` and `straddle_roll_max_per_session` before enabling Create.  
STRADDLE_WITH_ADJUSTMENT requires `hours_to_expiry`.  
0DTE/5DTE requires `expiry`.

### 6.3 Preset description tooltip

Clicking the "?" next to strategy name shows a brief description: what it does, how it manages risk, typical use case.

**Deliverable**: Creating a STRADDLE_ROLL session only asks for STRADDLE_ROLL-relevant fields. No confusion between strategies at creation time.

---

## Implementation Order

Execute phases in sequence. Each phase is a distinct PR. Each phase can be code-reviewed independently.

| Phase | Scope | Risk | Est. Files Changed | Current State |
|-------|-------|------|--------------------|---------------|
| 1 | DB schema + `strategy_type` | Medium (migration) | 3 | ✅ Completed |
| 2 | Param namespaces | Low | 2 | ✅ Completed |
| 3 | Backend dispatch | High (monitor refactor) | 4 | ✅ Completed |
| 4 | Settings dialog filter | Low | 1 | ✅ Completed |
| 5 | Dashboard cards + badge | Low | 2 | ✅ Completed |
| 6 | Create form split | Medium | 1 | ✅ Completed |

Backend and frontend separation milestones are now complete end-to-end.

### Execution note (current)

- The execution stream prioritized backend safety + canonical dispatch first, then frontend identity parity and UX completion.
- Current focus after this plan: maintenance, regression hardening, and UX polish (no remaining Phase 5/6 blockers).

---

## What NOT to Change

- The shared `MMMMonitor` class itself (don't split into 5 monitor classes — dispatch is sufficient)
- The shared engine (`mmm_engine.py`) — it is strategy-agnostic for the adjustment strategies
- The shared P&L core (`mmm_pnl_core.py`)
- The stale monitor invariants (CLAUDE.md §4)
- The reverse mode isolation (CLAUDE.md §5)
- `mmm_straddle_roll_pure.py` — it's already isolated; just connect it through the dispatch

---

## Key Risks

| Risk | Mitigation |
|------|-----------|
| Migration breaks existing running sessions | Migration reads `_preset_source` as fallback; no session loses its type |
| Phase 3 monitor refactor introduces regressions | Run full sealed test suite before and after; add strategy-dispatch unit tests |
| Settings forbidden list too aggressive (blocks a param the user wants) | Forbidden list is advisory only in Phase 2; surfaced as warning, not hard reject, until Phase 3 validates it |
| `strategy_type` column breaks old versions on rollback | Migration is additive (ADD COLUMN with DEFAULT) — safe to rollback |

---

## Session-Level Context Window Management

Each phase is written to be self-contained for a new AI session. Before starting any phase:

1. **Read** `mmm_workdone_march.md` (mandatory)
2. **Read** this file (`tasks/MMM_STRATEGY_SEPARATION_PLAN.md`)
3. **Read** only the files listed in "Files Changed" for that phase
4. **Implement** the phase
5. **Update** `mmm_workdone_march.md` with what changed

Do NOT attempt multiple phases in a single session. The monitor refactor (Phase 3) alone is a full session.
