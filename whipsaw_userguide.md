# Smart Whipsaw Engine — Operator User Guide

**Applies to:** MMM Algo, all strategies (STRADDLE_WITH_ADJUSTMENT, 0DTE, 5DTE, SHORT_WINDOW)
**Settings location:** Strategy Settings → Safety Limits
**All params are hot-reloadable** — changes take effect on the next heartbeat, no restart needed.

---

## What Is Whipsaw?

Whipsaw happens when spot price oscillates around a strike, causing the bot to alternate between CE and PE adjustments repeatedly. Each adjustment is individually valid, but together they burn lot budget, widen positions unnecessarily, and erode P&L without directional conviction.

The whipsaw engine sits between the heartbeat's decision to adjust and the actual order — it can block, reduce size, or widen triggers when it detects oscillatory market behaviour.

---

## Two Engines: LEGACY vs SMART

| | LEGACY | SMART |
|---|---|---|
| **Detection method** | Count alternating aggressors in a rolling window | 7 independent signal detectors → composite score |
| **Score type** | Integer (0, 1, 2, 3, 4…) | Float 0.0–1.0 |
| **Modes** | NORMAL → CAUTION → RESTRICT → COOLDOWN | NORMAL → DEFENSIVE → OBSERVE → LOCKDOWN |
| **Size reduction** | Halves lots at RESTRICT | Gradual: 0.5× DEFENSIVE, 0.25× OBSERVE |
| **Trigger widening** | +50% CAUTION, +100% RESTRICT | +50% DEFENSIVE, +100% OBSERVE, +200% LOCKDOWN |
| **State keys** | `_whipsaw_*` | `_smart_ws_*` |
| **Active by default** | No (Shadow) | **Yes (Primary)** |

Both engines run every heartbeat. SMART's decision binds on live orders; LEGACY runs as a shadow for comparison (visible in the Whipsaw Compare tab).

---

## Engine Selector (`whipsaw_engine`)

| Value | Behaviour |
|---|---|
| `SMART` | Smart engine is primary (current default). Legacy runs as shadow. |
| `LEGACY` | Legacy engine is primary. Smart runs as shadow. |
| `OFF` | All whipsaw logic disabled. No blocking, no size reduction, no trigger widening. |

**Emergency rollback — no UI needed:**
```bash
export MMM_WHIPSAW_FORCE_LEGACY=1
```
Takes effect on the next heartbeat. Clear with `unset MMM_WHIPSAW_FORCE_LEGACY` to return to UI setting.

---

## Smart Engine — How It Works

### Step 1: Seven Detectors

Each detector produces a score in **[0.0, 1.0]**. Higher = more whipsaw evidence.

| # | Detector | Param | What it measures |
|---|---|---|---|
| 1 | **Aggressor Flip Counter** | `smart_ws_flip_window_mins` (30) | Weighted count of CE↔PE alternations in the rolling window. Recent flips weighted 3× vs older ones. 3 weighted flips → score 1.0 |
| 2 | **Kaufman Efficiency Ratio (ER)** | `smart_ws_er_window_mins` (30) | Measures choppiness. `1 - ER`. ER=1 means trending (score 0). ER near 0 means pure chop (score 1). Insufficient data → 0.5 |
| 3 | **Spot Oscillation** | `smart_ws_oscillation_sensitivity_pct` (0.15%) | Counts local spot extrema (reversals ≥ sensitivity%). 6 extrema → score 1.0 |
| 4 | **Premium Symmetry** | — | Counts CE/PE dominance sign-flips. 4 flips → score 1.0. Detects premium see-saw |
| 5 | **Adjustment Outcome Memory** | — | Fraction of last 3 adjustments that alternated aggressor. All alternate → score 1.0 |
| 6 | **RV/IV Divergence** | `smart_ws_rv_iv_ratio_floor` (0.6) | If realized vol < `floor × implied vol`, triggers are noise-driven. Score rises as RV/IV falls |
| 7 | **Gamma Zone** | — | Weights oscillation by spot proximity to active strikes. Oscillation at-strike = highest danger |

### Step 2: Composite Score

Weighted sum of all 7 detectors:

| Detector | Weight |
|---|---|
| Aggressor Flip | **30%** |
| Kaufman ER | 20% |
| Adjustment Outcome | 15% |
| Spot Oscillation | 10% |
| Premium Symmetry | 10% |
| RV/IV Divergence | 10% |
| Gamma Zone | 5% |

**Result: a single float in [0.0, 1.0]**

### Step 3: Mode Assignment

| Composite Score | Mode | Effect |
|---|---|---|
| < 0.30 | **NORMAL** | Full size, full trigger. Multi-gate still evaluated (3 of 5 required) |
| 0.30 – 0.59 | **DEFENSIVE** | Triggers widen +50%, lot size × 0.5. Stricter gates (4 of 5 required) |
| 0.60 – 0.79 | **OBSERVE** | Block new sells. Closes and harvests still allowed. Triggers widen +100%, lot size × 0.25 |
| ≥ 0.80 | **LOCKDOWN** | All adjustments blocked. Triggers widen +200%. |

**Near-expiry tightening (automatic):**
- ≤ 30 min to expiry: DEFENSIVE threshold drops to 0.20 (earlier protection)
- ≤ 5 min to expiry: DEFENSIVE → 0.20, OBSERVE → 0.40 (very aggressive)

### Step 4: Multi-Gate Check (5 Gates)

Even if the score allows an adjustment, 5 gates vote on whether the specific move is real:

| Gate | Checks |
|---|---|
| G1: Trigger Fired | Premium trigger actually fired (always true if heartbeat reached adjustment) |
| G2: Spot Confirmation | Spot moved meaningfully relative to recent ATR |
| G3: Aggressor Persistence | Same aggressor for ≥ 2 consecutive adjustments |
| G4: Efficiency | Kaufman ER ≥ 0.35 (not pure chop) |
| G5: Vol Alignment | Realized vol ≥ 80% of IV, or spot broke recent range |

**Required gates to allow the adjustment:**
- NORMAL: 3 of 5
- DEFENSIVE: 4 of 5
- Adding to thinner side: +1 gate required (capped at 5)

If gates fail → adjustment is blocked for that beat (skips to P&L update).

### Step 5: Pressure-Release Override

The engine bypasses gate evaluation entirely if critical pressure indicators fire:
- Margin tier reaches ORANGE, RED, or CRITICAL
- Loss velocity > $50/min

In these cases, mode is forced to NORMAL and all gates pass — the bot must be able to defend itself.

### Step 6: Token Budget

Each session starts with **10 tokens** (`smart_ws_tokens_per_session`).

| Situation | Token cost |
|---|---|
| Normal adjustment | 1.0 |
| Adjustment after aggressor flip | 2.0 |
| Adjustment in DEFENSIVE mode | +0.5 (base or flip cost + 0.5) |

When tokens are exhausted:
- Adjustments are blocked (only closes/harvests allowed)
- Each blocked beat credits **+0.5 tokens** back (patience bonus — the engine rewards waiting)
- Budget resets to 10 at session start (not per day — per session restart)

---

## All Tunable Parameters

### Engine Controls

| Param | Default | Range | What it does |
|---|---|---|---|
| `whipsaw_engine` | `SMART` | SMART/LEGACY/OFF | Active engine selector |
| `whipsaw_smart_enabled` | `True` | bool | Final gate — Smart binds only when True |
| `whipsaw_engine_shadow` | `True` | bool | Legacy runs as shadow for compare tab |

### Smart Mode Thresholds

| Param | Default | Range | What it does |
|---|---|---|---|
| `smart_ws_score_defensive` | `0.30` | 0.05–0.59 | Score to enter DEFENSIVE (half size, +50% triggers) |
| `smart_ws_score_observe` | `0.60` | 0.10–0.79 | Score to enter OBSERVE (block new sells) |
| `smart_ws_score_lockdown` | `0.80` | 0.20–1.00 | Score to enter LOCKDOWN (block all) |

**Constraint:** defensive < observe < lockdown (enforced by backend validator).

### Smart Gate Counts

| Param | Default | Range | What it does |
|---|---|---|---|
| `smart_ws_gate_count_normal` | `3` | 1–5 | Gates required in NORMAL mode (of 5) |
| `smart_ws_gate_count_defensive` | `4` | 1–5 | Gates required in DEFENSIVE mode (of 5) |

### Smart Size Scalars

| Param | Default | Range | What it does |
|---|---|---|---|
| `smart_ws_size_scalar_defensive` | `0.5` | 0.1–1.0 | Lot multiplier in DEFENSIVE (0.5 = half size) |
| `smart_ws_size_scalar_observe` | `0.25` | 0.0–1.0 | Lot multiplier in OBSERVE (0.25 = quarter size) |

### Smart Budget

| Param | Default | Range | What it does |
|---|---|---|---|
| `smart_ws_tokens_per_session` | `10.0` | 1–50 | Total adjustment tokens per session |

### Smart Detector Windows

| Param | Default | Range | What it does |
|---|---|---|---|
| `smart_ws_flip_window_mins` | `30` | 5–120 | Rolling window for aggressor-flip counter |
| `smart_ws_er_window_mins` | `30` | 5–120 | Rolling window for Kaufman ER |
| `smart_ws_oscillation_sensitivity_pct` | `0.15` | 0.01–2.0 | Min % spot move to count as extremum |
| `smart_ws_rv_iv_ratio_floor` | `0.6` | 0.1–1.5 | RV/IV below this → divergence detector fires |
| `smart_ws_flip_penalty` | `0.5` | 0.1–1.0 | Lot multiplier per additional aggressor flip |
| `smart_ws_cooldown_base_beats` | `1` | 1–10 | Base for exponential cooldown (beats = base × 2^flips) |

### Legacy Thresholds (still active in shadow)

| Param | Default | Range | What it does |
|---|---|---|---|
| `whipsaw_window_mins` | `30` | 5–120 | Rolling window for alternation counting |
| `whipsaw_spot_move_pct` | `0.3` | 0.05–5 | % spot move to treat alternation as justified hedge |
| `whipsaw_caution_score` | `2` | 1–10 | CAUTION threshold (triggers +50%) |
| `whipsaw_restrict_score` | `3` | 2–15 | RESTRICT threshold (triggers +100%, lots halved) |
| `whipsaw_cooldown_score` | `4` | 3–20 | COOLDOWN threshold (block one interval) |

---

## Tuning Guide

### Engine Is Too Aggressive (blocking real breakouts)

**Symptom:** adjustments being blocked during clear directional moves; P&L not capturing real trends.

| Fix | Param | Change |
|---|---|---|
| Raise DEFENSIVE threshold | `smart_ws_score_defensive` | 0.30 → 0.40 |
| Raise OBSERVE threshold | `smart_ws_score_observe` | 0.60 → 0.70 |
| Reduce gates required in NORMAL | `smart_ws_gate_count_normal` | 3 → 2 |
| Widen flip window | `smart_ws_flip_window_mins` | 30 → 60 |
| Widen ER window | `smart_ws_er_window_mins` | 30 → 60 |

### Engine Is Too Passive (not stopping whipsaw)

**Symptom:** multiple CE↔PE alternations per hour, lot count climbing without P&L improvement.

| Fix | Param | Change |
|---|---|---|
| Lower DEFENSIVE threshold | `smart_ws_score_defensive` | 0.30 → 0.20 |
| Add gate in NORMAL | `smart_ws_gate_count_normal` | 3 → 4 |
| Narrow flip window | `smart_ws_flip_window_mins` | 30 → 15 |
| Increase oscillation sensitivity | `smart_ws_oscillation_sensitivity_pct` | 0.15 → 0.10 |

### Token Budget Running Out Too Fast

**Symptom:** `_smart_ws_tokens` near 0 early in session, no whipsaw happening but adjustments blocked.

| Fix | Param | Change |
|---|---|---|
| Increase budget | `smart_ws_tokens_per_session` | 10 → 15–20 |

### Token Budget Never Runs Out (not protecting against overtrading)

| Fix | Param | Change |
|---|---|---|
| Decrease budget | `smart_ws_tokens_per_session` | 10 → 6–8 |

---

## What to Watch in the UI

### Safety Panel (main dashboard)

Shows the active whipsaw indicator. When SMART is primary:
- Label: **Whipsaw (SMART)**
- Score: composite float (0.00–1.00)
- Mode: NORMAL / DEFENSIVE / OBSERVE / LOCKDOWN
- If Legacy shadow disagrees: shows `LEG:<LEGACY_MODE>` suffix

### Whipsaw Compare Tab (dashboard → Whipsaw tab)

Shows per-heartbeat comparison of Smart vs Legacy:
- Score and mode from both engines
- Disagree flag when they would make different decisions
- Historical trace for replay analysis

### Activity Log

| Event type | Meaning |
|---|---|
| `whipsaw_smart_block` | Smart engine blocked an adjustment (LOCKDOWN or gate failure) |
| `whipsaw_guard` | Legacy engine blocked an adjustment (COOLDOWN) |

---

## Rollback Procedures

**Level 1 — Instant (no login, no restart):**
```bash
export MMM_WHIPSAW_FORCE_LEGACY=1
```
Next heartbeat uses LEGACY. Clear with `unset MMM_WHIPSAW_FORCE_LEGACY`.

**Level 2 — UI flip (hot reload, one heartbeat):**
Settings → Safety Limits → `whipsaw_engine` → select `LEGACY` → Save Changes.

**Level 3 — Full code rollback:**
Revert the Phase 6 commit and run `./scripts/deploy_webui.sh`.

---

## Strategy Bypass

**STRADDLE_WITH_ADJUSTMENT** fully bypasses all whipsaw blocking:
- `trigger_widen_factor` forced to 1.0
- `lot_scalar` forced to 1.0
- `block_adjustment` forced to False

Reason: ATM gamma is structural for straddle — whipsaw protection would misfire constantly at ATM strikes. This bypass is hardcoded and cannot be overridden by params.

---

## Session State Keys (for debugging)

| Key | Type | Meaning |
|---|---|---|
| `_smart_ws_score` | float | Last composite score |
| `_smart_ws_mode` | str | Last mode (NORMAL/DEFENSIVE/OBSERVE/LOCKDOWN) |
| `_smart_ws_tokens` | float | Token budget remaining |
| `_smart_ws_flip_count_30m` | int | Approx flips in window (used for cooldown) |
| `_smart_ws_series` | list | Rolling spot/CE/PE price log (capped at N samples) |
| `_smart_ws_last_decision` | dict | Full trace of last evaluation (scores, gates, mode) |
| `_smart_ws_shadow_last` | dict | Shadow result when Legacy was primary |
| `_ws_legacy_shadow_last` | dict | Legacy shadow result when Smart is primary |
| `_whipsaw_score` | int | Legacy score (still written by Legacy shadow) |
| `_whipsaw_state` | str | Legacy mode (NORMAL/CAUTION/RESTRICT/COOLDOWN) |
