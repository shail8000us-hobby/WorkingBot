# AUDIT_STRATEGY_UI_MAPPING

Date: 2026-04-17  
Scope: UI control ownership by strategy (MMM)

## 1. Executive Summary

This audit maps which UI controls are appropriate for each strategy: `0DTE`, `5DTE`, `SHORT_WINDOW`, `STRADDLE_WITH_ADJUSTMENT`, and `STRADDLE_ROLL`.

What is working well:
- Strategy identity and parameter namespaces are strongly enforced server-side.
- `STRADDLE_ROLL` is tightly isolated (explicit risk inputs required; non-applicable controls locked).
- Reverse mode availability is correctly constrained to `0DTE` / `5DTE` / `SHORT_WINDOW`.

Key risks found:
- `Dangerous Mode` is exposed on running sessions regardless of strategy, despite explicit 0DTE-only warning language.
- Minor UI ownership inconsistency for `STRADDLE_WITH_ADJUSTMENT`: comments and runtime hints imply roll tuning in settings, but `straddleRoll` settings group is hidden unless strategy is `STRADDLE_ROLL`.

No code was changed in this audit.

---

## 2. Files Audited

- `MMM_LAST_3_SESSIONS.md`
- `webui/frontend/src/components/mmm/MMMDashboard.js`
- `webui/frontend/src/components/mmm/MMMSettingsDialog.js`
- `webui/frontend/src/components/mmm/MMMConfigPanel.js`
- `webui/frontend/src/components/mmm/MMMReverseModePanel.js`
- `webui/frontend/src/components/mmm/MMMStatusBanner.js`
- `webui/backend/routes/mmm/mmm_api.py`
- `webui/backend/routes/mmm/mmm_config.py`
- `webui/backend/routes/mmm/mmm_dte_presets.py`
- `MMM_AI_Context_PureStraddle_Roll.md`
- `webui/backend/routes/mmm/tests/test_sealed_straddle_adjustment.py`
- `webui/backend/routes/mmm/tests/test_sealed_mmm_dte_presets.py`
- `webui/backend/routes/mmm/tests/test_mmm_strategy_type_identity.py`

---

## 3. Findings

### Strategy UI mapping

### 0DTE

- **required controls**
  - Strategy preset: `0DTE`
  - `expiry`
  - `desired_ce_premium`, `desired_pe_premium`
  - `initial_lots`
  - Session init path (`Auto-Find` / `Manual Select` / `Import Existing` / `Adopt`)
- **optional controls**
  - `adjustment_interval`, `max_loss_amount`
  - Settings groups: `core`, `triggers`, `safety`, `expiry`, `adaptive`, `marginGuardian`, `regimeControls`, `lotVelocity`, `consecutiveDir`, `closeAt5Watcher`, `breakevenEngine`, `godLayer`, etc.
  - Reverse mode controls (supported)
- **irrelevant controls**
  - Straddle-roll control surface (`straddle_roll_*`, `price_guard_*`, `straddle_dynamic_*`, pure-roll hard stop mode)
  - Straddle ATM-only create flow controls
- **dangerous controls**
  - `dangerous_mode` toggle (bypasses multiple safety gates)
  - Reverse mode enable/disable and “Close All Reverse Positions”
- **recommended layout**
  1. Core setup row (`expiry`, lots, target CE/PE premium)
  2. Initialization actions row (auto-find/manual/import/adopt)
  3. Safety row (`max_loss_amount`, expiry protections)
  4. Advanced controls collapsed (reverse + dangerous)

### 5DTE

- **required controls**
  - Strategy preset: `5DTE`
  - `expiry`
  - `desired_ce_premium`, `desired_pe_premium`
  - `initial_lots`
  - Session init path (`Auto-Find` / `Manual Select` / `Import Existing` / `Adopt`)
- **optional controls**
  - `adjustment_interval`, `max_loss_amount`
  - Same broad settings groups as 0DTE (except straddle-roll-only groups)
  - Reverse mode controls (supported)
- **irrelevant controls**
  - All straddle-roll namespace controls (backend forbidden)
  - ATM-only straddle creation controls
- **dangerous controls**
  - `dangerous_mode` (especially high-risk for multi-day sessions)
  - Reverse mode controls
- **recommended layout**
  1. Multi-day core row (`expiry`, lots, CE/PE premium targets)
  2. Initialization row
  3. Risk row (`max_loss_amount`, lot caps)
  4. Advanced row (reverse + dangerous, collapsed by default)

### SHORT_WINDOW

- **required controls**
  - Strategy preset: `SHORT_WINDOW`
  - `session_window_hours` (strategy-defining)
  - `expiry`
  - `desired_ce_premium`, `desired_pe_premium`
  - `initial_lots`
  - Session init path
- **optional controls**
  - `adjustment_interval`, `max_loss_amount`
  - Wind-down/expiry tuning and deadline-monitoring UX
  - Reverse mode controls (supported)
- **irrelevant controls**
  - Straddle-roll control namespace (backend forbidden)
  - ATM-only straddle controls
- **dangerous controls**
  - `dangerous_mode`
  - Reverse mode controls
  - Misconfiguring session deadline behavior (if window safeguards are relaxed too far)
- **recommended layout**
  1. Session-window row (`session_window_hours`, deadline context)
  2. Core entry row (expiry, CE/PE premium, lots)
  3. Initialization row
  4. Safety + close-timing row (deadline countdown always visible)

### STRADDLE_WITH_ADJUSTMENT

- **required controls**
  - Strategy preset: `STRADDLE_WITH_ADJUSTMENT`
  - `expiry` (must imply future `hours_to_expiry > 0`)
  - `initial_lots` (explicit; validated server-side)
  - `straddle_roll_max_per_session` (explicit; validated server-side)
  - ATM-based init path (`Find ATM` in config panel)
- **optional controls**
  - `max_loss_amount` override in create dialog
  - Unlocked settings groups such as `core`, `triggers`, `safety`, `expiry`, `adaptive`, `marginGuardian`, `regimeControls`, `lotVelocity`, `consecutiveDir`, `closeAt5Watcher`, `breakevenEngine`, `godLayer`
- **irrelevant controls**
  - Locked groups in settings: `windDown`, `positionLifecycle`, `balanceControl`, `favorableScaleUp`, `reverseMode`, `perpHedge`, `adaptiveTuning`, `atmShield`, `gammaDetector`
  - `straddle_roll_hard_stop_market_order` (forbidden for this strategy)
  - Pure-roll-only controls
- **dangerous controls**
  - `dangerous_mode`
  - Over-aggressive lot/risk changes in unlocked safety/trigger controls
- **recommended layout**
  1. Straddle identity row (ATM-only, expiry, lots, max rolls/session)
  2. Core risk row (`max_loss_amount`, expiry validity)
  3. Adjustment/safety controls row
  4. Locked sections shown but non-editable with rationale badges

### STRADDLE_ROLL (Pure Roll)

- **required controls**
  - Strategy preset: `STRADDLE_ROLL`
  - `expiry`
  - `initial_lots` (explicit; required)
  - `straddle_roll_max_per_session` (explicit; required, `0` allowed)
  - `max_loss_amount` (explicit; required)
  - ATM-based init path (`Find ATM`)
- **optional controls**
  - `core` group tuning (where applicable)
  - `expiry` group tuning (limited relevance)
  - `straddleRoll` group tuning: cooldown, emergency multiplier, dynamic trigger floor, spread/trigger fallback, price guard
- **irrelevant controls**
  - All non-`core`/`expiry`/`straddleRoll` groups (hard-locked)
  - Adjustment-engine-only params (backend forbidden)
  - Reverse mode controls
- **dangerous controls**
  - `dangerous_mode` exposure in active sessions
  - Setting extremely loose roll/hard-stop parameters (operational risk)
- **recommended layout**
  1. Minimal core row (`expiry`, `initial_lots`, `max_loss_amount`, max rolls)
  2. Roll mechanics row (`straddleRoll` settings)
  3. Monitoring row (roll count, next trigger, guard status)
  4. Hide all non-applicable controls by default (already largely enforced)

### Cross-strategy findings

- **F1**: `Dangerous Mode` is strategy-agnostic in session detail UI (available for running/paused sessions), while warning text says it is intended for 0DTE expiry.
- **F2**: `STRADDLE_WITH_ADJUSTMENT` has a control-ownership inconsistency: comments/hints imply roll tuning from settings, but `straddleRoll` settings group is hidden for all non-`STRADDLE_ROLL` sessions.
- **F3**: Backend strategy-namespace enforcement is strong and prevents most cross-strategy parameter bleed.
- **F4**: `STRADDLE_ROLL` hardens risk ownership correctly (explicit required inputs; `max_lots_per_side` lock to `initial_lots`).
- **F5**: Reverse mode ownership is correctly scoped to `0DTE` / `5DTE` / `SHORT_WINDOW`.

---

## 4. Severity (P0/P1/P2/P3)

- **P0:** 0 findings
- **P1:** 1 finding (`F1`)
- **P2:** 1 finding (`F2`)
- **P3:** 3 findings (`F3`, `F4`, `F5`)

---

## 5. Why It Matters

- **F1 (P1):** A strategy-agnostic dangerous toggle increases operator error surface in real-money workflows, especially for strategies where its behavior is undefined or non-standard.
- **F2 (P2):** Mixed UI signals (“tune in settings” vs hidden settings group) can cause operational confusion and delayed risk response mid-session.
- **F3/F4/F5 (P3):** These are protective strengths that reduce cross-strategy drift and accidental misuse; preserving them is essential for safety.

---

## 6. Suggested Fix

- **For F1 (P1):**
  - Gate `dangerous_mode` by strategy (default: only `0DTE`; optional explicit allow-list).
  - Add second-factor confirmation for non-0DTE if deliberately allowed.
- **For F2 (P2):**
  - Choose one source-of-truth behavior and align UI + copy:
    - either expose a narrow roll-tuning subsection for `STRADDLE_WITH_ADJUSTMENT`,
    - or keep it hidden and remove “change in settings” guidance from related tooltips.
- **For F3/F4/F5 (P3):**
  - Keep backend namespace enforcement and strategy identity immutability unchanged.
  - Keep reverse eligibility and pure-roll locking behavior unchanged.

---

## 7. Safe Implementation Notes for Claude

- Do **not** weaken strategy identity immutability in `PATCH /session/<id>/params`.
- Preserve namespace guards in `mmm_config.py` + `mmm_api.py` (`forbidden` sets and filtering behavior).
- Preserve `STRADDLE_ROLL` invariants: explicit required fields, `max_lots_per_side` lock to `initial_lots`, and pure-roll isolation.
- If touching MMM logic files, follow repository safety protocol first (pre-change behavior declaration + invariant checks).
- Any UI-only fixes should avoid changing runtime trading logic paths.
- Add or update sealed tests for any control-ownership change (especially around strategy gating and forbidden params).

---

## 8. Final Score /10

**8.6 / 10**

Rationale:
- Strong backend enforcement and strategy isolation: **high confidence**.
- One material UX-risk surface (`Dangerous Mode` scope) and one consistency gap (straddle+adjustment roll-settings visibility) reduce operational clarity/safety.
